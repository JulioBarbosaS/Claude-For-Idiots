# Task 6 report — the flow in `SKILL.md`

**Status:** done, committed.

## Base check

HEAD started at `9685e6c` (wrong — a stale merge-commit tip from another
branch, missing Rule 10 / the hook entirely), not the branch tip. Reset to
`plan/brainstorming-0.5.0` (`d53e435`) before touching anything, per the task
instructions.

## What changed

**`SKILL.md`** (the assigned target):

1. **"The rules" list** — added item 10, short, in the tone of 1–9, pointing
   to `references/brainstorming.md` for the full script. The pointer is
   legitimate here (unlike in the generated `CLAUDE.md`, which was fixed in
   Task 3 precisely because it can't reach the skill's own tree) because
   `SKILL.md` runs from inside the skill directory.
2. **Step 3 (project artifacts), bullet 2** — added `brainstorm.enforce`
   (`off` | `ask` | `deny`, **default `ask` for a new project**) alongside
   the existing `architecture.enforce` mention, since both are read by the
   hooks from the same `config.json`.
3. **Updating section** — extended, not rewritten:
   - Bullet 2 ("update the current project") now says explicitly that
     "refresh the hooks" means copying the current `.claude/hooks/*.py`
     (naming `require_feature_alignment.py` for a pre-0.5.0 upgrade) and
     merging `assets/settings.template.json` into the project's
     `.claude/settings.json` — this was previously left implicit and only
     spelled out in `references/update-flow.md` (out of scope, untouched).
   - New bullet 3: the pre-0.5.0 migration path. A project with no
     `brainstorm` section in its config keeps reading as `off` — the hook
     does this on purpose, for compatibility (see `hooks/require_feature_alignment.py`
     and `references/rules.md`). The update step must **never** flip it on
     silently. It asks, as options to pick from (per the project's standing
     rule that Rule 10 itself follows — offer choices, not an open
     question), naming in one sentence what changes:
     - `ask` (recommended) — the hook requires an OK before an unaligned
       feature-shaped change lands; "just go" still works per request.
     - `deny` — stricter, blocks outright until aligned.
     - `off` — leaves current behavior untouched.
     Whatever is picked (including an explicit `off`) is written to
     `brainstorm.enforce`; if the user doesn't answer, the section is left
     absent rather than guessed at.
   - Old bullet 3 (restart reminder) renumbered to 4, unchanged.

Left `hooks/`, `references/`, and `tests/` untouched, as instructed.

## The `docs/INDEX.md` category gap (Task 1 leftover)

`references/brainstorming.md` §5 tells Claude to write
`docs/features/YYYY-MM-DD-<slug>.md` with a one-line pointer in
`docs/INDEX.md` for a substantial feature. But `assets/docs-INDEX.template.md`
— the template the skill writes into every new project — only had three
categories: Decisions (ADRs), Investigations, Integrations. None of them fit:
a feature-alignment write-up isn't an ADR (a cross-cutting architecture
choice), a bug investigation, or a third-party API quirk. Pointing it at
"Decisions" would blur two different things people search for separately:
*why did we choose Postgres* vs. *why does Google login coexist with
email/password*.

**Decision: added a fourth category, "Features", to
`assets/docs-INDEX.template.md`**, placed right after Decisions (both are
"why we built it this way" content; Investigations and Integrations are more
troubleshooting-shaped), following the exact same pattern as the other three
(heading, one commented-out example line, `*(none yet)*`):

```markdown
## Features
<!-- - [Google login](features/2026-09-25-login-google.md) — decisions made before building it (Rule 10) -->

*(none yet)*
```

Rejected alternative: redirecting `references/brainstorming.md` to file
under "Decisions" instead. Rejected because it would be out of my assigned
scope (that file is explicitly off-limits for this task) and because it
would make "Decisions" a catch-all, defeating the point of Rule 8's index
being a fast lookup by kind of knowledge.

## Verification

```
grep -nE "^[0-9]+\." SKILL.md   # rules list now runs 1..10, confirmed
python3 tests/test_common.py            # 53/53 OK
python3 tests/test_hooks.py             # 128/128 OK
python3 tests/test_real_projects.py     # 1/1 OK
python3 tests/test_repo_consistency.py  # 8/8 OK
```

All four suites green, 190/190 total. No test file was touched by this task
(none needed — no code changed, only `SKILL.md` prose and the docs-index
template's static content), and none broke.
