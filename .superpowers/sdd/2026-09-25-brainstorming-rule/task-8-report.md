# Task 8 report — fechar a versão 0.5.0

**Status:** done, committed.

**Hash:** `4df7c01` — "chore: release 0.5.0 — align before building"

## Base check

HEAD started at `9685e6c` (a stale merge-commit tip, not the branch tip;
`plan/brainstorming-0.5.0` was at `0eda75a`). Working tree was clean, so
`git reset --hard plan/brainstorming-0.5.0` before touching anything, per
task instructions.

## What changed (exactly the five files in scope)

- `VERSION`: `0.4.0` → `0.5.0`.
- `assets/config.example.json`: `skill_version` `0.4.0` → `0.5.0` (the
  `brainstorm` block itself was already present from Task 4 — untouched).
- `CHANGELOG.md`: new `## [0.5.0]` entry, written for the end user from the
  22-commit log (`3db5115..HEAD`), `progress.md`, and the task-3/5/6/7
  reports — not from the plan's prose. Covers, without hedging: what now
  pauses (a feature-shaped request stops and lays out hidden decisions as
  options before any code, while bug fix / visual tweak / rename still go
  straight through), that it's configurable (`brainstorm.enforce`:
  off/ask/deny) and never silently turned on for a pre-0.5.0 project on
  update, and what the backing hook does **not** catch (no prompt access —
  file-write-only; a feature built entirely inside existing files passes
  untouched; "is this a test file?" is filename/folder convention, so a
  file that merely looks like a test slips through the same way a real one
  does).
- `README.md` / `README.pt-br.md`: added Rule 10 as a 4th `*(checked)*`
  bullet (same format as the other nine), updated "three small hook
  scripts" → "four" in the Known limitations intro, and added two new
  Known-limitations bullets covering the same two "what it doesn't catch"
  points as the changelog (prompt-blindness / existing-files bypass, and
  the test-file-by-convention exemption). `README.pt-br.md` was written in
  its own register, not translated line-by-line from the English.

Confirmed `git diff --stat` touched only these five files, nothing else.

## Left alone, on purpose

Did not touch `hooks/`, `references/`, `SKILL.md`, or tests. Two things
noticed but **not fixed**, per scope:

1. **`README.md`/`README.pt-br.md` "Repository layout" section still says
   "the 9 rules (source of truth)"** for `references/rules.md`, and neither
   layout tree lists `require_feature_alignment.py` or
   `references/brainstorming.md`. This is real drift now that Rule 10
   shipped, but the task's Step 3 scoped README changes to exactly two
   things (the rule bullet + Known limitations), and this section wasn't
   named. Left as-is — flagging for a decision, not fixing.
2. Everything else checked (hooks/README.md's own "Known gaps" for Rule 10,
   `references/rules.md`'s Rule 10 entry, the config's `brainstorm` block)
   was already consistent with what got written above — no other drift
   found.

## Verification

```
python3 tests/test_common.py            # 53/53 OK
python3 tests/test_hooks.py             # 128/128 OK
python3 tests/test_real_projects.py     # 1/1 OK
python3 tests/test_repo_consistency.py  # 11/11 OK
```

193/193 total, all green.

```
grep -rniE "guarantee|impossible|garante|impossível" --include='*.md' . | grep -v CHANGELOG
```

All hits are in `docs/superpowers/plans/*.md` (historical planning
narrative, e.g. quoting the *old, already-fixed* 0.4.0 wording as the thing
that got replaced) — none in shipped docs (`README*`, `SKILL.md`,
`references/`, `hooks/README.md`). Nothing introduced by this task's diff
matches the pattern.

## Concerns

- The "9 rules" / missing-file drift in "Repository layout" noted above —
  real, but out of this task's explicit scope; someone should decide
  whether to fold it into this release or a follow-up doc pass.
- No other concerns. This was the last task in the plan; branch
  `plan/brainstorming-0.5.0` now has a version-consistent tip.
