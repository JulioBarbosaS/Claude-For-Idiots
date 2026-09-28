# Task 3 report — Rule 10 in the generated CLAUDE.md

**Status:** done, committed.

**Hash:** `fb75e19` — "feat(rule10): carry the alignment rule into generated CLAUDE.md"

**Tests:** all four suites green — `test_common.py` 38/38, `test_hooks.py` 93/93, `test_real_projects.py` 1/1, `test_repo_consistency.py` 8/8 (140/140 total), no new failures.

**Summary:**
- Added item 10 to the numbered rules list in `assets/CLAUDE.template.md`, matching sibling length (~4 lines of prose) plus the mandatory fires/does-not boundary block copied verbatim from `references/rules.md`. States the options-to-pick-from format (never an open question, consequence per line) and points to `references/brainstorming.md` for the full script.
- Rewrote the "Knowledge & reuse" section's first bullet so the Rule 7 search (codebase + `docs/INDEX.md` + `architecture.allowed_paths`) is framed as the first step of alignment, feeding the options — not a separate step after the design is already decided. Rule 7's own numbered-list entry was left untouched to avoid duplication.
- Updated the closing config note ("Rules 1, 5, 6 are also enforced by hooks...") to include Rule 10, since `references/rules.md` marks it `[hook]` too.
- No new `{{PLACEHOLDER}}` introduced — `grep -o "{{[A-Z_]*}}" assets/CLAUDE.template.md | sort -u` returns the same set as before my change.
- Confirmed via `git status --porcelain` that only `assets/CLAUDE.template.md` changed.

**Concerns:**
- The Rule 10 entry points to `claude-for-idiots's references/brainstorming.md` for the full script. That path lives inside the skill's own install, not inside the user's project — same as how `SKILL.md` already points there. This mirrors the plan's intent ("o roteiro que o SKILL.md e o CLAUDE.md apontam") but is worth a sanity check once Task 6 wires `SKILL.md`'s own Rule 10 pointer, to make sure both read the same way to a beginner user with no access to the skill's source tree.
- `assets/config.example.json` and `assets/settings.template.json` still have no `brainstorm` block in this worktree (Task 4 is running elsewhere) — expected, out of scope here, not touched.
