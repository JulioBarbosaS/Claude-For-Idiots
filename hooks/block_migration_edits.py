#!/usr/bin/env python3
"""Rule 1 — never hand-edit migration files.

PreToolUse hook (matcher: Edit|Write|MultiEdit|NotebookEdit). Reads the
per-project .claude-for-idiots/config.json for the protected paths and the
generator command. Fails open when there is no config or no migrations
section, so it never interferes with unrelated projects.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfi_common as cfi


def main():
    event = cfi.read_event()
    if not event:
        cfi.allow()

    file_path = cfi.target_path(event.get("tool_input"))
    cwd = event.get("cwd") or os.getcwd()
    config = cfi.load_config(cwd)
    if not config:
        cfi.allow()

    migrations = cfi.section(config, "migrations")
    protected = cfi.str_list(migrations.get("protected_paths"))
    if not protected:
        cfi.allow()

    rel = cfi.relativize(file_path, cwd)
    if not rel or not cfi.matches_any(rel, protected):
        cfi.allow()

    tool = migrations.get("tool", "your migration tool")
    command = migrations.get("command", tool + " autogenerate")
    cfi.decide("deny", (
        "BLOCKED by claude-for-idiots Rule 1: migration files are generated, "
        "never hand-edited.\n"
        "'" + rel + "' matches a protected migration path.\n"
        "Change the models/schema and run: " + command + "\n"
        "Explain this to the user in their language before retrying."
    ))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Last-resort net, not a substitute for fixing each cause: this
        # execution alone found three separate ways attacker/tool-influenced
        # input reached an uncaught exception (RecursionError parsing JSON,
        # re.error compiling a config glob, TypeError on a non-string
        # command) -- three instances of the SAME invariant violation this
        # module exists to prevent. Every known boundary already fails open
        # on its own; this is the backstop for the next one nobody has found
        # yet. `except Exception` does not catch the `SystemExit` that
        # `cfi.allow()`/`cfi.decide()` raise (SystemExit subclasses
        # BaseException, not Exception), so the normal exit paths are
        # unaffected -- this only ever fires for a genuinely unanticipated
        # failure.
        sys.exit(0)
