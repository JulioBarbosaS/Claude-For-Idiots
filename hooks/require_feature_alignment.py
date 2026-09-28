#!/usr/bin/env python3
"""Rule 10 — align on a feature before building it.

PreToolUse hook (matcher: Write). This is the net, not the judge: it never
sees the user's prompt -- PreToolUse only receives the tool call -- so it
cannot itself tell "new feature" from "bug fix". That classification is the
model's, made by following references/brainstorming.md before it ever calls
Write. What this hook catches is narrower and purely mechanical: a brand
new CODE file appearing with no `.claude-for-idiots/current-feature.json`
record at all, or one that has gone stale (HEAD moved since it was written).

Two exemptions are unconditional, same reasoning as enforce_architecture.py
(Rule 5): a file that already exists is an edit, not a placement, and a new
TEST file is the normal first step of TDD (Rule 2) -- blocking it would put
this rule at war with that one.

Fails open aggressively. A malformed record, an unreachable git HEAD, or
any unexpected shape of input always resolves toward ALLOW, never toward
asking/denying -- this hook policing nothing it can't confidently resolve
is safer than it policing something wrong. See
`.superpowers/sdd/2026-09-25-brainstorming-rule/task-5-report.md` for the
full case table this was tested against.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfi_common as cfi

DEFAULT_RECORD_REL = ".claude-for-idiots/current-feature.json"

# Directory names that, anywhere in a new file's path, mark it as a test by
# convention across the stacks this project documents (see
# tests/fixtures/*/ for the real trees these were taken from: pytest's
# tests/, Flutter's test/ + integration_test/ + test_driver/, Playwright's
# e2e/, RSpec's spec/).
_TEST_DIR_NAMES = frozenset({
    "test", "tests", "__tests__", "spec", "specs", "e2e",
    "integration_test", "test_driver",
})

# A whole, separator-bounded "test"/"spec" token in the filename (ignoring
# its final extension): matches test_x.py, x_test.go, x.test.tsx, x.spec.ts,
# app.e2e-spec.ts, x_spec.rb. Deliberately does NOT match a bare substring,
# so "latest.py", "contest.py", "attest.py" are never mistaken for tests --
# a false positive here (exempting a real feature file) is no better than
# the false positive this whole hook exists to avoid causing.
_TEST_NAME_RE = re.compile(r"(?i)(?:^|[_.\-])(?:test|spec)s?(?:[_.\-]|$)")


def is_test_file(rel):
    """True when a NEW file counts as a test by path convention, so Rule 10
    never fights Rule 2 -- TDD's red-phase file is the first new file to
    appear, and it must never trigger an alignment prompt."""
    if not rel:
        return False
    segments = rel.split("/")
    if any(seg.lower() in _TEST_DIR_NAMES for seg in segments[:-1]):
        return True
    filename = segments[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return bool(_TEST_NAME_RE.search(stem))


def _git_env():
    """Same rationale as scan_secrets_before_push.py's _git_env: a stray
    GIT_DIR/GIT_WORK_TREE in the calling environment must never redirect
    which repository's HEAD this hook reads."""
    env = dict(os.environ)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def current_head(cwd):
    """`git rev-parse --short HEAD` at cwd. None on ANY failure: no git
    binary, cwd not inside a repo, no commits yet, a timeout. The caller
    treats None as "cannot prove the record is stale", not as "no record"
    -- a project with no git keeps whatever record is on disk valid
    forever (see "Riscos conhecidos" in the plan: Rule 3, commit per
    feature, already assumes git; a project without it has given up more
    guarantees than this one)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=cwd, env=_git_env(),
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    head = out.stdout.strip()
    return head or None


def _record_path(cwd, record_rel):
    """Absolute filesystem path for a project-relative, POSIX-style config
    value (e.g. ".claude-for-idiots/current-feature.json")."""
    return os.path.join(cwd, record_rel.replace("/", os.sep))


def load_record(cwd, record_rel):
    """The feature-alignment record, or None when it can't be trusted: not
    a JSON object, or missing a usable string `head`. Does NOT distinguish
    "file absent" from "file present but unusable" -- main() checks
    existence separately, because those two cases lead to different
    decisions (absent -> the normal ask/deny path; present-but-malformed ->
    allow, unconditionally -- see the module docstring)."""
    parsed = cfi.load_json_file(_record_path(cwd, record_rel))
    if not isinstance(parsed, dict):
        return None
    head = parsed.get("head")
    if not isinstance(head, str) or not head:
        return None
    return parsed


def main():
    event = cfi.read_event()
    if not event:
        cfi.allow()

    file_path = cfi.target_path(event.get("tool_input"))
    cwd = event.get("cwd") or os.getcwd()
    config = cfi.load_config(cwd)
    if not config:
        cfi.allow()

    brainstorm = config.get("brainstorm")
    if not isinstance(brainstorm, dict):
        # Section absent (or present with an unusable type) -> off. This is
        # DELIBERATELY different from Rule 5's missing-key default ("ask"):
        # a project generated by the 0.4.0 skill has no `brainstorm` key at
        # all and must keep working exactly as before, with zero new
        # prompts it never opted into.
        cfi.allow()

    mode = brainstorm.get("enforce", "ask")
    if mode not in ("deny", "ask"):
        # "off", a typo, or any other type ("DENY", true, null, 42) fails
        # open to off/allow -- same direction as Rule 5's own
        # `mode not in ("deny", "ask") -> allow`. "ask" is a decision, not
        # silence, so unrecognized config must never land there.
        cfi.allow()

    rel = cfi.relativize(file_path, cwd)
    if not rel:
        cfi.allow()

    # An existing file is an edit, not a new feature landing -- same
    # reasoning as enforce_architecture.py.
    if os.path.exists(os.path.join(cwd, rel)):
        cfi.allow()

    if not cfi.is_policed(rel):
        cfi.allow()

    if is_test_file(rel):
        cfi.allow()

    record_rel = brainstorm.get("record")
    if not isinstance(record_rel, str) or not record_rel:
        record_rel = DEFAULT_RECORD_REL

    if os.path.isfile(_record_path(cwd, record_rel)):
        record = load_record(cwd, record_rel)
        if record is None:
            # Present but unparseable or wrong-shaped ({}, a list, a
            # string, invalid JSON, pathological nesting) -- never trusted
            # enough to escalate to ask/deny. A corrupted record is not
            # evidence the user skipped alignment; it is noise.
            cfi.allow()
        head = current_head(cwd)
        if head is None or record.get("head") == head:
            # No git to compare against, or the record was written at the
            # HEAD we are still on -> fresh. (A skipped record is only
            # fresh for the HEAD it was written at too -- this check does
            # not special-case `skipped`.)
            cfi.allow()
        # else: the record is stale (HEAD moved) -- fall through exactly
        # as if there were no record at all.

    reason = (
        f"claude-for-idiots Regra 10: '{rel}' seria um arquivo novo de "
        "código e a feature ainda não foi alinhada.\n\n"
        "Me diz o que você quer construir e eu apresento as decisões em "
        "opções antes de escrever código. Se preferir seguir direto, é só "
        "dizer."
    )
    cfi.decide("deny" if mode == "deny" else "ask", reason)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Last-resort net -- see enforce_architecture.py for the rationale.
        # Never catches the SystemExit that cfi.allow()/cfi.decide() raise.
        sys.exit(0)
