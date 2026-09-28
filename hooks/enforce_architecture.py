#!/usr/bin/env python3
"""Rule 5 — new code stays inside the chosen architecture.

PreToolUse hook (matcher: Write). Checks NEW code files against the project's
allowed_paths from .claude-for-idiots/config.json. The `architecture.enforce`
mode can be "deny", "ask" or "off". Only polices code-file creation; ignores
docs/config and files that already exist (those are edits, not placements).
Fails open when not configured.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfi_common as cfi

# "is this a code file?" (IGNORED_EXT, the dotenv exemption, the
# no-extension exemption, and the ignored_extensions override) lives in
# _cfi_common.is_policed now -- require_feature_alignment.py (Rule 10) asks
# the exact same question and must agree with Rule 5 on the answer, so
# there is exactly one implementation instead of two that could drift.


def main():
    event = cfi.read_event()
    if not event:
        cfi.allow()

    file_path = cfi.target_path(event.get("tool_input"))
    cwd = event.get("cwd") or os.getcwd()
    config = cfi.load_config(cwd)
    if not config:
        cfi.allow()

    arch = cfi.section(config, "architecture")
    # "off" as the default meant a config written without this key silently
    # disabled the rule the skill advertises. "ask" is the safe default: it
    # surfaces the decision instead of swallowing it. Any OTHER value --
    # explicit "off", a typo, or a config field of the wrong type entirely --
    # still fails open here, so a malformed or intentionally-disabled config
    # can never crash the hook or escalate into an accidental deny.
    mode = arch.get("enforce", "ask")
    if mode not in ("deny", "ask"):
        cfi.allow()
    allowed = cfi.str_list(arch.get("allowed_paths"))
    if not allowed:
        cfi.allow()

    rel = cfi.relativize(file_path, cwd)
    if not rel:
        cfi.allow()

    # Only police new code files. Let docs/config and edits-to-existing through.
    if not cfi.is_policed(rel, arch.get("ignored_extensions")):
        cfi.allow()

    # An existing file is an edit, not a placement. Resolve against the
    # EVENT's cwd, never the process cwd — the hook may be invoked anywhere.
    if os.path.exists(os.path.join(cwd, rel)):
        cfi.allow()

    # on_incomplete=True: this hook ALLOWS on a match, so an allowed_paths
    # list too expensive to fully evaluate (see matches_any's docstring)
    # must fail open the same direction as everything else here -- allow,
    # not deny/ask. Without this, an absurd config would turn "the safety
    # net degrades" into "legitimate writes start getting denied".
    if cfi.matches_any(rel, allowed, on_incomplete=True):
        cfi.allow()

    layers = arch.get("layers") or {}
    layer_hint = "\n".join(f"    {k}: {v}" for k, v in layers.items()) or "    (see CLAUDE.md)"
    reason = (
        f"claude-for-idiots Rule 5: '{rel}' is outside the chosen architecture "
        f"({arch.get('name', 'project architecture')}).\n"
        f"Allowed locations: {', '.join(allowed)}\n"
        f"Layers:\n{layer_hint}\n"
        "Place the file in the correct layer, or update `architecture` in "
        ".claude-for-idiots/config.json + CLAUDE.md if this is a deliberate change."
    )
    cfi.decide("deny" if mode == "deny" else "ask", reason)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Last-resort net -- see block_migration_edits.py for the rationale
        # (this codebase has already found three distinct fail-open gaps of
        # this same shape across the three hooks). Never catches the
        # SystemExit that cfi.allow()/cfi.decide() raise.
        sys.exit(0)
