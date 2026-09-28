# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.5.0] — 2026-09-25
A new rule: Claude now pauses before building a feature you haven't described
yet, instead of guessing at the decisions hidden inside your request.

### Added

- **A write plainly outside the project could be DENIED on Windows with
  Python 3.13+.** `relativize` asked `os.path.isabs` alone to tell an outside
  path from a project-relative one, and 3.13 changed `ntpath.isabs` so a rooted
  path with no drive letter (`/etc/cron.d/x.py`) is no longer absolute there.
  It fell through as project-relative, got policed, and the hook blocked it —
  fail-closed, the one direction these hooks must never take. Found by the CI
  matrix: windows/3.13 red while windows/3.9 and every Linux and macOS job
  stayed green.

- **`secrets.allow_patterns` now degrades to nothing on Windows instead of
  risking a stalled hook.** The field is a regex straight out of `config.json`;
  a catastrophic-backtracking entry (`(a+)+$` against a 31-character line was
  measured at 96s under a 5s budget) cannot be interrupted without
  `signal.SIGALRM`, which Windows does not have — and a watchdog thread does
  not help, because `re.search` holds the GIL for its whole run. Where it
  cannot be bounded it is not evaluated, and the block message says so.
  `secrets.allowlist_paths` and the `# cfi:allow-secret` pragma are unaffected
  on every platform.
- **Rule 10 — align before building a feature.** A request that would add
  behavior the project doesn't have yet (a login method, a new export format,
  a new panel) now stops before any code gets written: Claude searches the
  codebase and `docs/INDEX.md` first, then lays out the decisions hidden in
  that request as a short list of **options to pick from** — never an
  open-ended question, never a wall of text. Once you pick (or say "just go
  ahead"), that choice is written down so the same feature is never asked
  about twice.
  - **What still goes straight through, unchanged:** a bug fix, a visual
    tweak, or a rename. Those were never the point of this rule and don't
    trigger it.
  - **It can be turned down, or up, per project.** `brainstorm.enforce` in
    `.claude-for-idiots/config.json` is `off` / `ask` (the default on a new
    project) / `deny`. A project set up before 0.5.0 has no `brainstorm`
    section at all — it keeps behaving exactly as it did before you update,
    because an absent section reads as `off`. The update flow never turns
    this on by itself: it asks first, offering the same off/ask/deny choices,
    and only writes the section once you've answered.
  - **What the hook backing this rule does *not* catch.** It never sees your
    prompt — a `PreToolUse` hook only sees the file being written — so
    telling "new feature" from "bug fix" is still entirely Claude's judgment
    call, not something this script enforces. What it catches is one narrow,
    mechanical case: a brand-new code file appearing with no alignment
    recorded at all. A feature built entirely inside files that already
    exist, with no new file created, passes through with no pause, no
    matter how large. And "is this a test file?" is decided by filename and
    folder convention (`tests/`, `test/`, `spec/`, `foo_test.py`,
    `foo.spec.ts`, …), not by what the file actually does — deliberate, so
    the rule never fights test-first development, but it also means a file
    that merely *looks* like a test by that convention slips through the
    same way a real one does.

## [0.4.0] — 2026-09-25
Ground-up reliability pass on the three enforcement hooks (Rules 1, 5, 6). An
audit of real projects found that the hooks blocked legitimate files and
missed real violations far more often than the previous docs let on; every
item below was verified against real project trees or an adversarial input,
not just read from the code.

### Fixed
- **The secrets scanner (Rule 6) had five separate blind spots.** It skipped
  files with accented/non-ASCII names, only scanned the working tree while
  `git push` sends the whole history behind it, never looked above the
  current directory, recognised only `git push` (`npm publish`,
  `vercel --prod`, `docker push`, `scp`, `gh gist create` all went through
  untouched), and never looked at a gitignored `.env` file on disk — the
  exact file this skill tells you to create — even though every non-git
  deploy uploads it. All five are closed: it now scans from the repo root,
  survives non-ASCII filenames, checks unpushed history before `git push`,
  recognises the common publishing commands above, and scans gitignored
  `.env` files (including nested ones, e.g. `apps/api/.env`) before any
  publishing command, not just `git push`.
- **Fixing the scanner's false positives opened a real bypass.** A follow-up
  fix that stopped `git commit -m "add push notification support"` from
  false-triggering did so by blanking out *all* quoted text — which also
  blanked the command itself when it was wrapped in `bash -c "git push"`,
  `sh -c "..."`, or `ssh host "git push"`, letting a secret through. This is
  now closed: those wrapped forms are blocked again, while the commit-message
  false positive stays fixed. Two unrelated spots in the same matching logic
  could also be driven from milliseconds to 30–45+ seconds by an ordinary
  word (`fly`, `surge`, or plain `git`) repeated a few thousand times in a
  command — both replaced with matching that can't blow up like that,
  regardless of input size.
- **Architecture enforcement (Rule 5) blocked real, unmodified scaffold
  files.** An audit of real Next.js, FastAPI, Flutter, NestJS and Astro
  projects found 42 of 63 stock files blocked: a default `create-next-app`
  project (no `--src-dir`) had its entire `app/` directory refused, and
  Flutter's own `integration_test/` was denied — contradicting Rule 2 (follow
  stack conventions). Digging further, all seven catalog stacks had gaps: the
  `allowed_paths` lists had been drawn from each stack's idealized textbook
  layout, not a real scaffolded tree, so files like `public/sw.js`,
  `prisma/schema.prisma` (present in NestJS but only allowed in Next.js),
  `scripts/build.mjs`, `docs/conf.py`, and `data/load.py` (in a *data*
  project) were all denied. Every stack's allowed paths are now derived from
  an actual scaffold tree, checked by a test that deletes each fixture file
  and confirms the hook doesn't re-block it.
  - **Flutter trade-off worth knowing:** only the platform-specific
    *configuration* files (e.g. `AndroidManifest.xml`, `Info.plist`) were
    opened, not the whole `android/**` / `ios/**` / `macos/**` trees. Native
    plugin code (a new `.kt`, `.swift`, or `project.pbxproj` change) is still
    checked against the architecture on purpose — opening those trees
    entirely would blind Rule 5 to a native layer bypassing the Dart
    architecture rules the skill is supposed to enforce. If you hit a false
    block while writing a native plugin, add that specific path to
    `architecture.allowed_paths`.
  - `architecture.enforce` silently defaulted to `off` when a project's
    `config.json` predated the setting — a rule that was never actually on
    unless you knew to turn it on. Now defaults to `ask`.
  - Rule 5 was effectively an undocumented file-extension allow-list —
    `.mjs`, `.cjs`, `.mts`, `.astro`, `.sql` and `.sh` were never checked, so
    `hack.mjs` passed while `hack.ts` next to it was blocked. Now every code
    extension is policed unless explicitly ignored (docs, configs, images,
    lockfiles, …), closing that gap for good instead of one extension at a
    time.
- **`**` in a glob never matched what it looks like it should.** `src/**`
  did not match `next.config.ts`, and `**/migrations/**` did not match a
  root-level `migrations/` folder. Rewritten as a real glob matcher shared by
  all three hooks (also fixes falsely blocking `migrations/runner.ts` as if
  it were a migration file — the pattern now anchors on the numeric filename
  migration tools actually generate).
- **The command Rule 1 tells you to run to fix a migration didn't run.**
  `--name <describe_change>` is shell redirection syntax, not a placeholder —
  running it verbatim failed with `syntax error near unexpected token
  'newline'`. The suggested Alembic and Django commands were also missing
  their apply/migrate half, so the schema silently stayed on the old version
  even though the generator "succeeded."
- **A malformed `config.json` crashed the hook instead of stepping aside.**
  `{"architecture": "layered"}` (a string where an object was expected) threw
  an uncaught `AttributeError` and exited non-zero — breaking the documented
  promise that a hook without valid config gets out of your way. This was one
  of four separate fail-open bugs found during this work, all the same
  shape (input of an unexpected type reaching code that assumed a specific
  one): a deeply nested JSON payload could crash a hook with
  `RecursionError`; a crafted glob pattern could make matching take from
  milliseconds to minutes (a form of ReDoS); a non-string shell command could
  raise `TypeError`; and an inverted character-class glob range like
  `[9-0]` could raise a regex compile error. All three hooks now have a
  last-resort safety net around their entire `main()`, and CI feeds 14 forms
  of malformed input to every hook script it finds (by scanning `hooks/`, so
  a hook added later is covered automatically) and requires it to exit
  cleanly — locking this class of bug against ever coming back unnoticed.

### Added
- `hooks/_cfi_common.py` — one shared implementation of glob matching
  (proper `**`, character classes, a compute-budget cap so a long list of
  patterns can't be driven past the hook's own timeout), path
  normalisation, config reading, and the allow/ask/deny decision protocol,
  used by all three hooks instead of three separate copies.
- `tests/fixtures/` — real scaffolded project trees for seven stacks
  (Next.js, FastAPI, Flutter, NestJS, Astro, Python CLI, Data/ML), with the
  contract that no file present in a real scaffold may be blocked. This is
  what the previous test suite didn't have, and why the blocking bugs above
  shipped unnoticed.
- `secrets.allowlist_paths`, `secrets.allow_patterns`, and an inline
  `# cfi:allow-secret` pragma — a documented way out for a known false
  positive (test fixtures, documented example keys) instead of the scanner
  becoming annoying enough to disable. Deliberate gap: `allowlist_paths`
  never exempts unpushed git history (a diff can't be reliably attributed
  back to a path per line), so only `allow_patterns` and the pragma reach
  history — a path-based exemption only ever covers tracked files on disk.
- CI now runs across Ubuntu/macOS/Windows and Python 3.9/3.13, and adds a
  repo-consistency suite (`tests/test_repo_consistency.py`) that locks
  together things nothing previously checked: the architecture catalog
  against the test table that mirrors it, the example commands the hooks
  print to users against real shell syntax, `VERSION` against this
  changelog and the config's `skill_version`, and a check that these docs
  don't start promising an unqualified guarantee again. Also lints the
  skill's own hook and test code with `ruff`.

### Changed
- The hooks are now described everywhere as a **safety net, not a
  guarantee**. The previous wording ("guarantees, not just promises",
  "Claude literally can't break it") told a beginner the hooks were
  airtight, with no way for them to verify it. They catch the common paths;
  see "Known limitations" below (and `hooks/README.md`'s "Known gaps") for
  what still gets through.
- `architecture.enforce` now defaults to `ask` instead of `off`.

## [0.3.0] — 2026-06-05
### Added
- Update flow (`/claude-for-idiots update`, `references/update-flow.md`):
  updates the skill install (git pull or fresh download) and brings
  already-configured projects up to date — refreshes hooks, merges new rules
  into `CLAUDE.md`, adds new config fields — while preserving every onboarding
  choice and verified project fact. Summarizes what changed (from this
  changelog, in the user's language) before touching anything.
- `VERSION` file at the repo root; setup now records `skill_version` in each
  project's config so updates know where the project is starting from.

## [0.2.1] — 2026-06-05
### Fixed
- Setup must now **verify** facts (paths, ports, commands) against the real
  project before writing them into `CLAUDE.md`/config — never from memory.
  Found in field testing: the database path was written as `prisma/dev.db`
  while the file actually lived at the project root. Facts about artifacts that
  don't exist yet are re-checked during the first sanity check.
- Generated `CLAUDE.md` now states that its facts are documentation, not law:
  Claude must fix them immediately when they turn out wrong (only the rules
  need the user's consent to change). Prevents the model from refusing to
  correct its own instructions file.

## [0.2.0] — 2026-06-05
### Added
- Portuguese README (`README.pt-br.md`) with a language switcher in both READMEs.
- Quality-tooling catalog (`references/quality-tools.md`) — setup now installs
  the stack's formatter/linter/type-checker by default (Python default: ruff,
  with pylint as a documented alternative).
- Rule 7 (reuse before you build) and Rule 8 (hard-won knowledge lives in
  `docs/`, three context layers: always loaded / on demand / discovered live).
- `docs/` scaffolding templates: `assets/docs-INDEX.template.md` and
  `assets/ADR.template.md`.
- Rule 9 (debugging escalation): after two failed fixes for the same problem,
  stop guessing — re-read the full error, check versions, research the web
  deeply, then retry with a genuinely new hypothesis.
- Browser-verification guide (`references/browser-verification.md`): web smoke
  tests read the browser console via Playwright MCP when available, degrade
  gracefully when not; setup offers to configure it (never installs unasked).
- Hook test suite (`tests/test_hooks.py`, 16 cases, stdlib only) covering
  block / allow / fail-open for all three hooks.
- GitHub Actions CI (`.github/workflows/ci.yml`): compiles hooks and runs the
  test suite on every push and pull request.

### Fixed
- Removed the non-standard `"//"` comment key from `assets/settings.template.json`
  (the merge instructions live in SKILL.md Step 3).

### Changed
- README rewritten for non-technical readers: plain-language intro, the original
  motivation, how to use, and what it improves.
- Skill is now explicit-invocation first (`/claude-for-idiots`); its description
  no longer aims to auto-apply to every new project.
- READMEs: new "Should you use it on your project?" section (sweet spot vs
  over-engineering), setup-time note (~10 minutes measured on Opus 4.8),
  auto-mode recommendation for beginners during setup, and a
  not-yet-tested-for-deployment disclaimer.

## [0.1.0] — initial skeleton
### Added
- `SKILL.md` — onboarding flow, stack/architecture derivation, rules, term modes.
- Six rules in `references/rules.md` (1, 5, 6 are hook-enforced).
- Editable data catalogs: `stack-catalog.md`, `architecture-catalog.md`.
- `onboarding-flow.md` and `glossary-format.md` (progressive-teaching glossary).
- Generated-project assets: `CLAUDE.template.md`, `config.example.json`,
  `settings.template.json`.
- Three `PreToolUse` hooks: block migration edits (Rule 1), enforce architecture
  (Rule 5), scan secrets before publishing (Rule 6).
- `README.md` and `CONTRIBUTING.md`.

### Notes
- Term modes: `none` / `explain` / `raw`.
- Experience levels: `beginner` / `intermediate` / `advanced` drive defaults.
- Hooks fail open: no `.claude-for-idiots/config.json` → no interference.
