#!/usr/bin/env python3
"""Shared helpers for the claude-for-idiots PreToolUse hooks.

Every hook imports from here so path handling, glob semantics and the decision
protocol have exactly one implementation. Standard library only.
"""
import json
import os
import posixpath
import re
import sys
import warnings
from functools import lru_cache

CONFIG_REL = os.path.join(".claude-for-idiots", "config.json")

# Both are attacker-influenced: the event comes over stdin from whatever
# invoked the hook, and config.json can come from a repo the user cloned.
# MAX_JSON_CHARS bounds parse time/memory on a pathologically large payload;
# MAX_JSON_NESTING bounds recursion depth so CPython's recursive-descent
# decoder can never be pushed toward (or past) a RecursionError/C-stack
# overflow in the first place. Both are far beyond any real PreToolUse event.
MAX_JSON_CHARS = 2_000_000
MAX_JSON_NESTING = 200


def _max_nesting_depth(raw):
    """Greatest `[`/`{` nesting depth in `raw`, ignoring string content.

    Iterative, not recursive, so scanning itself can never overflow the
    stack. Used to reject dangerously nested input before it ever reaches
    `json.loads`, since the stdlib decoder recurses once per nesting level.
    """
    depth = 0
    max_depth = 0
    in_string = False
    escape = False
    for ch in raw:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > max_depth:
                max_depth = depth
        elif ch in "]}":
            depth -= 1
    return max_depth


def _safe_json_loads(raw):
    """Parse JSON defensively. None on ANY problem -- fail open, always.

    Bounds size and nesting before parsing, then wraps the parse itself in a
    broad `except Exception`. That breadth is deliberate here, not a stray
    catch-all: this is the one boundary where attacker-controlled bytes
    (stdin, or config.json from a cloned repo) turn into Python objects, and
    the project's invariant is that no hook may ever exit non-zero, on any
    input. RecursionError (raised by the decoder on deep-but-not-rejected
    nesting) is an Exception subclass, so it is covered without special-casing.
    """
    if not raw or len(raw) > MAX_JSON_CHARS:
        return None
    if _max_nesting_depth(raw) > MAX_JSON_NESTING:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def read_event():
    """Parse the PreToolUse event from stdin. None means: fail open."""
    try:
        raw = sys.stdin.read(MAX_JSON_CHARS + 1)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    event = _safe_json_loads(raw)
    return event if isinstance(event, dict) else None


def load_json_file(path):
    """Read and parse an arbitrary JSON file at an absolute path. None on
    ANY problem -- missing, unreadable, oversized, too deeply nested,
    invalid JSON, or a top-level value that isn't a JSON object -- fail
    open, always. `load_config` is defined in terms of this; a second
    caller (the Rule 10 hook, reading its own record file at a
    config-supplied path) reuses the exact same bounded, defensive
    contract instead of re-implementing it."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read(MAX_JSON_CHARS + 1)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    parsed = _safe_json_loads(raw)
    return parsed if isinstance(parsed, dict) else None


def load_config(cwd):
    """Read the project config. None means: fail open."""
    return load_json_file(os.path.join(cwd, CONFIG_REL))


def section(config, name):
    """config[name] when it is a mapping, {} otherwise. Never raises."""
    value = (config or {}).get(name)
    return value if isinstance(value, dict) else {}


def str_list(value):
    """Coerce a config field into a list of strings, tolerating a bare string."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _find_class_end(pattern, start):
    """Index of the `]` that closes the `[...]` class opened at `start`.

    None when there is no matching `]`, in which case the caller treats the
    `[` as a literal character instead of raising.
    """
    length = len(pattern)
    j = start + 1
    if j < length and pattern[j] == "!":
        j += 1
    # A `]` right after `[` or `[!` is a literal member of the class, not
    # its closing bracket (classic glob/POSIX behavior).
    if j < length and pattern[j] == "]":
        j += 1
    while j < length and pattern[j] != "]":
        j += 1
    return j if j < length else None


def _translate_class(glob_class):
    """`[...]` / `[!...]` glob class -> the equivalent regex `[...]` class."""
    body = glob_class[1:-1]
    negate = body.startswith("!")
    if negate:
        body = body[1:]
    body = body.replace("\\", "\\\\")
    if not negate and body.startswith("^"):
        # A literal leading `^` would otherwise flip the regex class to
        # negation, which glob `[...]` (without `!`) never means.
        body = "\\" + body
    return "[" + ("^" if negate else "") + body + "]"


def _compile_class(glob_class):
    """`re.compile(_translate_class(glob_class))`, or None on ANY regex error.

    A `[...]` span can be well-formed glob syntax (a `[`, some content, a
    matching `]`, found by `_find_class_end`) and still not translate into a
    valid regex character class -- a backwards range like `[9-0]` or
    `[z-a]` compiles fine as a *glob* class but raises `re.error` (aka
    `re.PatternError`, same class, just renamed in newer Pythons) from
    `re.compile`. That exception surfaces while PARSING the pattern, before
    `.match()` is ever called, so the "unterminated bracket" fallback in
    `_parse_glob_tokens` does not cover it. `protected_paths` /
    `allowed_paths` come straight out of `config.json`, the same untrusted
    input as stdin, so this must fail open (treat the whole span as
    literal, same as an unterminated `[`) rather than let a malformed or
    hand-typed range crash the hook with a non-zero exit.

    Warnings are suppressed locally for the same reason. Some valid-but-
    unusual bodies (`[a-z-A]`) make CPython's `re` emit a FutureWarning for
    set-operation syntax it is reserving, rather than raise. A hook does not
    control the environment it runs in: under `PYTHONWARNINGS=error` or
    `-W error` that same config-supplied pattern would raise instead. Never
    let compiling a config value depend on the caller's warnings settings.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return re.compile(_translate_class(glob_class))
    except re.error:
        return None


# Round 1 of this fix collapsed a run of the SAME wildcard token repeated
# ("**/" * N). Round 2's own review then found that concatenating any two
# *different* unrestricted-quantifier regex fragments ((?:[^/]+/)*, .*,
# [^/]*) adjacently is exactly as prone to catastrophic backtracking as
# repeating one, and a hand-derived per-run algebraic collapse (checking only
# "is this run one contiguous span of wildcard characters") still missed it:
# a pattern like `("**/" + "*") * 40` re-tokenizes (adjacent "*" characters
# always merge greedily) into several separate `.*`/`(?:[^/]+/)*` fragments
# chained through single-character literal separators, and THAT chain is
# just as exponential -- a run boundary at a literal does not actually bound
# the backtracking, because `.*` freely crosses that literal too.
#
# Rather than keep hunting for more regex shapes that alias to the same
# blowup, matching is done with an explicit DP over (token index, path
# index) instead of building one backtracking regex for the whole pattern.
# This is the "reescrever o matcher para consumir segmento a segmento sem
# regex" option: `re` is still used, but only to test ONE character against
# a `[...]` class -- a fixed-width, non-quantified check that can never
# backtrack -- never to chain multiple unbounded quantifiers together. The
# DP is O(len(pattern) * len(path)) by construction, for ANY pattern shape,
# with no backtracking search space to blow up in the first place.
#
# Both dimensions are capped as defense in depth (a config.json value or a
# tool_input path could in principle still be very long): a pattern or path
# longer than these is treated as "does not match" rather than paying
# unbounded DP cost -- fail open in the same direction as the rest of this
# module (an absurd config value stops that one rule from applying instead
# of blocking the hook). Both ceilings are far beyond any real glob pattern
# or project-relative path.
MAX_GLOB_PATTERN_CHARS = 1024
MAX_GLOB_PATH_CHARS = 4096

# CRITICAL-A (fix round 3): the two caps above bound a SINGLE compile_glob()
# .match() call, but matches_any() iterates a whole protected_paths/
# allowed_paths LIST with no limit on how many patterns it tries -- the
# product of "cost per pattern" x "number of patterns" has no ceiling.
# Measured: a single near-both-caps pattern ("a"*510 + "*"*10 + "a"*500 +
# "z", ~1021 tokens, against a 4095-char non-matching path) costs ~0.42s.
# That one pattern already spends a noticeable slice of Claude Code's 60s
# PreToolUse timeout; a config.json listing a few hundred such patterns
# (150 -> ~44s, 600 -> ~175s measured on the reviewing machine) blows past
# it entirely, and protected_paths/allowed_paths come from config.json,
# which comes from a repo the user cloned -- third-party input, same as
# everything else this module bounds.
#
# MAX_GLOB_MATCH_WORK caps the TOTAL work matches_any() will spend across
# an entire pattern list, in "cells" -- the same unit the DP already
# processes one at a time: `len(tokens) * len(path)`, computed from the
# already-parsed (and lru_cache'd) token list, no extra parsing needed to
# estimate it. Patterns are tried in order, subtracting each one's cost
# from the remaining budget; the moment the NEXT pattern's cost would
# exceed what is left, matching stops without running that pattern's DP at
# all. This bounds total work to at most MAX_GLOB_MATCH_WORK cells no
# matter how many patterns the list holds or what order they come in.
#
# The measured rate above is ~4.18M cells in 0.42s, ~10M cells/s. A budget
# of 20_000_000 cells therefore bounds a single matches_any() call to
# roughly 2s at that rate -- and to roughly 10s even on hardware 5x slower,
# still a wide margin under the 60s hook timeout -- while staying far above
# the cost of any realistic protected_paths/allowed_paths list (a handful
# of short patterns against a path of a few dozen characters: a few hundred
# cells, not millions).
MAX_GLOB_MATCH_WORK = 20_000_000


class _NeverMatches:
    """compile_glob's result for a pattern over MAX_GLOB_PATTERN_CHARS."""

    __slots__ = ()

    def match(self, path):
        return False

    def cost(self, path_len):
        """Work `match()` would spend -- always 0: over-cap patterns never
        run the DP at all, so they never draw on the work budget either."""
        return 0


_NEVER_MATCHES = _NeverMatches()


def _parse_glob_tokens(pattern):
    """Tokenize a git-style glob into `(kind, payload)` pairs.

    `**/` matches zero or more leading directories, `**` crosses separators,
    `*` and `?` do not. This is what `fnmatch` gets wrong: it maps every `*`
    to `.*`, so `src/**` never matches `next.config.ts` while `**/x/**` fails
    to match a root-level `x/`. A `[...]` character class is also supported,
    including glob-style negation `[!...]` (translated to a regex `[^...]`
    class, compiled once here and matched against exactly one character at a
    time); an unterminated `[` is treated as a literal so a stray bracket
    never raises `re.error`.
    """
    pattern = pattern.strip().replace("\\", "/")
    tokens = []
    index, length = 0, len(pattern)
    while index < length:
        if pattern.startswith("**/", index):
            tokens.append(("starstar_slash", None))
            index += 3
        elif pattern.startswith("**", index):
            tokens.append(("starstar", None))
            index += 2
        elif pattern[index] == "*":
            tokens.append(("star", None))
            index += 1
        elif pattern[index] == "?":
            tokens.append(("qmark", None))
            index += 1
        elif pattern[index] == "[":
            end = _find_class_end(pattern, index)
            if end is None:
                tokens.append(("lit", pattern[index]))
                index += 1
            else:
                compiled = _compile_class(pattern[index:end + 1])
                if compiled is None:
                    # Well-formed glob-class syntax, invalid regex range
                    # (e.g. "[9-0]") once translated -- fall back to
                    # matching the bracket span literally, char by char,
                    # same fail-open direction as the unterminated-bracket
                    # branch above.
                    for ch in pattern[index:end + 1]:
                        tokens.append(("lit", ch))
                else:
                    tokens.append(("class", compiled))
                index = end + 1
        else:
            tokens.append(("lit", pattern[index]))
            index += 1
    return tokens


def _dp_match(tokens, path):
    """Does the full `tokens` sequence match the full `path`?

    Standard "wildcard matching" dynamic programming, generalized with a
    `starstar_slash` token alongside the usual single-char/`*`/`**` ones.
    `dp` holds, for the tokens consumed so far, every path index reachable
    at that point; each token folds `dp` into a `new_dp` in O(len(path))
    time, so the whole match is O(len(tokens) * len(path)) -- no
    backtracking, so no input can make it slower than that bound.
    """
    n = len(path)
    dp = [False] * (n + 1)
    dp[0] = True
    next_slash = None  # computed lazily, at most once, only if needed

    for kind, payload in tokens:
        if True not in dp:
            return False  # nothing reachable -- no later token can help
        new_dp = [False] * (n + 1)
        if kind == "lit":
            for j in range(1, n + 1):
                new_dp[j] = dp[j - 1] and path[j - 1] == payload
        elif kind == "qmark":
            for j in range(1, n + 1):
                new_dp[j] = dp[j - 1] and path[j - 1] != "/"
        elif kind == "class":
            for j in range(1, n + 1):
                new_dp[j] = dp[j - 1] and payload.match(path[j - 1]) is not None
        elif kind == "star":
            # Zero-or-more non-slash characters: reachable either by taking
            # zero reps from wherever `dp` already reached, or by extending
            # what THIS token just reached by one more non-slash character.
            new_dp[0] = dp[0]
            for j in range(1, n + 1):
                new_dp[j] = dp[j] or (new_dp[j - 1] and path[j - 1] != "/")
        elif kind == "starstar":
            new_dp[0] = dp[0]
            for j in range(1, n + 1):
                new_dp[j] = dp[j] or new_dp[j - 1]
        else:  # starstar_slash: zero-or-more complete "[^/]+/" segments
            if next_slash is None:
                next_slash = [n] * (n + 1)
                for p in range(n - 1, -1, -1):
                    next_slash[p] = p if path[p] == "/" else next_slash[p + 1]
            new_dp = dp[:]
            # A segment starting at `start` is deterministic -- glob "1 or
            # more non-slash chars then /" can only mean "up to the next
            # literal /", there is no ambiguity in where it ends. Walking
            # `start` in increasing order and hopping forward on each hit
            # therefore reaches every valid rep count in one O(n) pass: any
            # position newly marked True is still ahead of `start` (a
            # segment is never empty), so it gets its own turn later in the
            # same loop.
            for start in range(n):
                if new_dp[start] and path[start] != "/" and next_slash[start] < n:
                    new_dp[next_slash[start] + 1] = True
        dp = new_dp
    return dp[n]


class _GlobPattern:
    """compile_glob's result for a pattern within the length cap.

    `.match(path)` mirrors the truthy/falsy contract `matches_any` needs
    from `re.Pattern.match` -- that is the only thing this module (or any
    consumer of `compile_glob`) relies on; nothing calls `.pattern`,
    `.fullmatch()`, or any other `re.Pattern`-specific attribute.
    """

    __slots__ = ("_tokens",)

    def __init__(self, tokens):
        self._tokens = tokens

    def match(self, path):
        if len(path) > MAX_GLOB_PATH_CHARS:
            return False
        return _dp_match(self._tokens, path)

    def cost(self, path_len):
        """Upper bound on the work `match()` would spend against a path of
        `path_len` characters, in the same "cells" unit MAX_GLOB_MATCH_WORK
        budgets -- `len(tokens) * path_len`, mirroring `_dp_match`'s O(len
        (tokens) * len(path)) loop structure exactly (each token does O(path
        length) work; the `starstar_slash` branch's one-off next_slash
        precompute is itself O(path length), so it does not change the
        bound). 0 for a path over MAX_GLOB_PATH_CHARS, matching `match()`'s
        own early return -- that call never runs the DP either."""
        if path_len > MAX_GLOB_PATH_CHARS:
            return 0
        return len(self._tokens) * path_len


@lru_cache(maxsize=512)
def compile_glob(pattern):
    """Compile a git-style glob pattern for repeated matching.

    Returns an object with a `.match(path) -> bool`-ish method (not a real
    `re.Pattern` -- see `_GlobPattern` and the module-level comment above
    `MAX_GLOB_PATTERN_CHARS` for why). Deliberately not `@lru_cache`d on the
    (pattern, path) pair: patterns repeat across hook invocations (there are
    only ever a handful per project), paths don't, so caching the parse
    here and reusing it across `.match()` calls is what actually pays off.
    """
    if len(pattern) > MAX_GLOB_PATTERN_CHARS:
        return _NEVER_MATCHES
    return _GlobPattern(_parse_glob_tokens(pattern))


def matches_any(rel_path, patterns, *, on_incomplete=False):
    """True when rel_path matches any pattern in patterns.

    Bounded by MAX_GLOB_MATCH_WORK across the WHOLE list (see its docstring
    for why an aggregate cap is needed on top of compile_glob's per-pattern
    ones). Patterns are tried in order; the moment the next one's cost would
    exceed the remaining budget, iteration stops and `on_incomplete` is
    returned instead of quietly finishing the scan as "no match" -- a config
    absurd enough to blow the budget must never make matches_any() lie about
    having checked every pattern.

    `on_incomplete` lets each caller keep its OWN fail-open direction even
    when the list can't be fully evaluated: Rule 1's protected_paths DENIES
    on a match, so its caller should keep the default `False` (an
    unevaluated tail of patterns never manufactures a block). Rule 5's
    allowed_paths ALLOWS on a match, so its caller must pass `on_incomplete=
    True` -- otherwise an absurdly expensive config would flip Rule 5 from
    "safety net degrades" to "legitimate writes start getting denied",
    fail-closed, exactly backwards for a hook whose one hard invariant is
    fail-open. (Below the budget, this parameter has no effect: every
    pattern still gets tried and the result is the same as before.)
    """
    if not rel_path:
        return False
    budget = MAX_GLOB_MATCH_WORK
    path_len = len(rel_path)
    for pattern in str_list(patterns):
        compiled = compile_glob(pattern)
        cost = compiled.cost(path_len)
        if cost > budget:
            return on_incomplete
        budget -= cost
        if compiled.match(rel_path):
            return True
    return False


# Inverted on purpose: policing an allow-list of extensions silently exempted
# .mjs/.cjs/.astro/.sql/.sh, so Rule 5 did not apply to whole stacks the
# catalog recommends. Anything that is not obviously prose, data or a binary
# is treated as code. Shared between enforce_architecture.py (Rule 5) and
# require_feature_alignment.py (Rule 10) -- both ask the same "is this a
# code file?" question, for different reasons, and must agree on the answer.
IGNORED_EXT = {
    ".md", ".markdown", ".rst", ".txt", ".adoc",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".lock", ".csv", ".tsv", ".xml", ".env", ".example", ".sample",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pdf", ".zip", ".gz", ".tar", ".mp3", ".mp4", ".webm",
    ".parquet", ".pkl",
    ".bz2", ".7z", ".rar", ".xz",
}


def _normalize_ext(raw):
    """Best-effort normalize one config-supplied extension token: trim
    whitespace, lowercase, and add the leading dot os.path.splitext always
    returns. Without this, an override entry typed as "TS" or "ts" (missing
    the dot, or in the wrong case) matched nothing at all -- not even the
    extension the author meant to exempt -- and since the override REPLACES
    the whole default list, a one-character typo silently turned Rule 5 into
    "police every file in the project." Returns None for a token that is
    empty after trimming (e.g. a whitespace-only entry)."""
    token = raw.strip().lower()
    if not token:
        return None
    if not token.startswith("."):
        token = "." + token
    return token


def _is_dotenv(rel):
    """.env and its common siblings (.env.local, .env.production, ...) are
    never code, regardless of their trailing "extension". os.path.splitext
    treats a file's leading dot as part of the name, not as a separator, so
    ".env.local" reports its extension as ".local" -- which is not in
    IGNORED_EXT, and used to get denied. This check is unconditional, the
    same way the no-extension check below is: a project's
    ignored_extensions override should never be able to accidentally turn a
    secrets file into a policed "code" file."""
    name = os.path.basename(rel)
    return name == ".env" or name.startswith(".env.")


def is_policed(rel, ignored_override=None):
    """True when this file counts as code for Rule 5 (and Rule 10, which
    reuses this exact notion of "code" rather than re-deriving it).

    `ignored_override` is an optional config-supplied list of extension
    tokens (e.g. `architecture.ignored_extensions`) that REPLACES the
    default IGNORED_EXT set when it normalizes to something non-empty.
    """
    if _is_dotenv(rel):
        return False
    _, ext = os.path.splitext(rel)
    if not ext:
        # No extension: LICENSE, Dockerfile, Makefile. Too noisy to police.
        return False
    override = str_list(ignored_override)
    if override:
        normalized = {n for n in (_normalize_ext(o) for o in override) if n}
        # Every entry normalized away to nothing (e.g. all whitespace) is a
        # malformed config, not a deliberate "ignore nothing" instruction --
        # fail open to the default list rather than policing everything.
        ignored = normalized or IGNORED_EXT
    else:
        ignored = IGNORED_EXT
    return ext.lower() not in ignored


def relativize(file_path, cwd):
    """Project-relative POSIX path, or None when outside the project."""
    if not file_path or not isinstance(file_path, str):
        return None
    raw = file_path.replace("\\", "/")
    # `raw.startswith("/")` is checked explicitly, NOT left to os.path.isabs:
    # Python 3.13 changed ntpath.isabs so that a rooted path with no drive
    # ("/etc/cron.d/x.py") is no longer absolute on Windows. Without this,
    # such a path falls through as if it were project-relative, gets policed,
    # and a hook DENIES a write that is plainly outside the project -- a
    # fail-CLOSED regression, on a platform difference no Linux run can see.
    if (raw.startswith("/") or os.path.isabs(file_path)
            or (len(file_path) > 1 and file_path[1] == ":")):
        try:
            raw = os.path.relpath(file_path, cwd).replace(os.sep, "/")
        except ValueError:
            return None
    rel = posixpath.normpath(raw)
    if rel in (".", "..", "") or rel.startswith("../"):
        return None
    return rel


def target_path(tool_input):
    """The file a write-shaped tool aims at, whatever field name it uses."""
    for key in ("file_path", "notebook_path"):
        value = (tool_input or {}).get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def decide(decision, reason):
    """Emit a PreToolUse decision and exit 0."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def allow():
    """Silent allow — also the fail-open path."""
    sys.exit(0)
