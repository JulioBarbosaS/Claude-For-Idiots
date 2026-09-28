# Hooks — the technical guardrails

These four Python scripts add a technical check to rules 1, 5, 6 and 10 on the paths Claude Code most often takes. They run as Claude Code `PreToolUse` hooks: before a tool call runs,
the hook inspects it and can block it.

| Hook | Rule | Matcher | Blocks when… |
|---|---|---|---|
| `block_migration_edits.py` | 1 | `Edit\|Write\|MultiEdit` | the target file matches a protected migration path |
| `enforce_architecture.py` | 5 | `Write` | a **new code file** lands outside `architecture.allowed_paths` |
| `scan_secrets_before_push.py` | 6 | `Bash` | a publishing command (push, `gh repo create`, …) and a tracked file looks like it holds a secret |
| `require_feature_alignment.py` | 10 | `Write` | a **new code file** appears with no fresh `.claude-for-idiots/current-feature.json` record |

## How they're installed (by the skill)

During onboarding the skill:
1. copies these scripts into `<project>/.claude/hooks/`,
2. merges `assets/settings.template.json` into `<project>/.claude/settings.json`,
3. writes `<project>/.claude-for-idiots/config.json`, which the hooks read.

## Contract

- **Input:** the hook event JSON arrives on **stdin** (fields include `cwd`,
  `tool_name`, `tool_input`).
- **Allow:** exit `0` with no output. This is also the **fail-open** default when
  there is no config or the rule doesn't apply.
- **Block:** print
  ```json
  {"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "permissionDecision":"deny","permissionDecisionReason":"…"}}
  ```
  Use `"ask"` instead of `"deny"` for a soft nudge (architecture hook honors
  `architecture.enforce`: `deny` | `ask` | `off`; the alignment hook honors
  `brainstorm.enforce` the same way, except a *missing* `brainstorm`
  section means `off` — see below — not `ask`).

## Requirements

- `python3` on PATH (standard library only — no pip installs).

## Extending

`scan_secrets_before_push.py` has a `SECRET_PATTERNS` list — add regexes there.
The architecture and migration hooks are fully driven by `config.json`, so most
tuning is done in config, not code.

## The secrets scanner's escape hatch

A false positive with no way out is how a security hook gets uninstalled
instead of obeyed — so `scan_secrets_before_push.py` reads an optional
`secrets` section of `config.json`:

```json
"secrets": {
  "allowlist_paths": ["tests/fixtures/**"],
  "allow_patterns": ["AKIAIOSFODNN7EXAMPLE"]
}
```

- `allowlist_paths` exempts a whole tracked file by path (same glob syntax
  as `migrations.protected_paths` / `architecture.allowed_paths`).
- `allow_patterns` exempts any line matching one of these regexes, wherever
  it appears (a tracked file or the unpushed-history diff).
- `# cfi:allow-secret` on a line exempts just that line, no config needed —
  put it next to a fixture or a documented example.

Both mechanisms are deliberately narrow: they exempt a specific path or a
specific line, never a whole command or repo, so they can't quietly cancel
out Rule 6. **Never use them for a live credential** — only for test
fixtures and documented examples that were never a real secret to begin
with.

## Known gaps

- **`secrets.allow_patterns` does not run on Windows.** The field is
  evaluated only where `signal.SIGALRM` exists (Linux, macOS). A regex from
  `config.json` can backtrack catastrophically -- measured: `(a+)+$` against
  a 31-character line ran 96s under a 5s budget -- and there is no way to
  interrupt a `re.search` already in flight without SIGALRM (a watchdog
  thread never gets scheduled, because `re.search` holds the GIL for its
  whole run). Rather than ship a hook that can blow its 60s ceiling on a
  typo, the field degrades to nothing there and the block message says so.
  `secrets.allowlist_paths` and the `# cfi:allow-secret` pragma work on
  every platform -- both are plain string and path work.

These four hooks catch the common paths, not every path. Higher-level,
beginner-facing gaps are in the main READMEs' "Known limitations" — these
are the lower-level ones, for anyone extending or auditing the hooks:

- **`require_feature_alignment.py` never sees the user's prompt.**
  `PreToolUse` only receives the tool call, so classifying a request as
  "new feature" vs. "bug fix" is always the model's job, done by following
  `references/brainstorming.md` — the hook only catches the one mechanical
  case where that never happened: a brand-new code file with no alignment
  record at all, or a stale one. A design decision is never enforced.
- **`require_feature_alignment.py` never polices edits to an existing
  file.** A feature built entirely inside files that already exist — no
  new file created — passes the hook untouched, the same way
  `enforce_architecture.py` treats an edit as out of scope.
- **`require_feature_alignment.py` exempts every new test file
  unconditionally**, by path convention (`tests/`, `test/`,
  `integration_test/`, `*_test.*`, `*.spec.*`, …). This is deliberate — TDD
  (Rule 2) writes the test first — but it means a new file that merely
  *looks* like a test by naming convention also slips through.
- **`allowlist_paths` never exempts unpushed git history**, only tracked
  files on disk. A diff's hunks can't be reliably attributed back to a
  single path per line, so extending the exemption there would risk
  silently under-scanning history. Only `allow_patterns` and the inline
  `# cfi:allow-secret` pragma reach history, because they match text
  directly rather than a path.
- **`scp -r .` / `rsync -av .` from the repo root copy `.git` itself**, not
  just the files the scanner inspects — a literal history copy, not
  something a file-by-file scan is positioned to catch.
- **A brand-new branch with no upstream** falls back to scanning its last 50
  commits, which can re-scan commits already published on another ref. Wasted
  work, not a false negative.
- **On Windows, the time budget on `allow_patterns` evaluation (a `SIGALRM`
  based cap against a pathological regex in `config.json`) isn't available**;
  a pattern-length cap applies everywhere as a second line of defence, but a
  crafted regex could still run longer on Windows than on Linux/macOS.
- **The aggregate glob-matching budget (`MAX_GLOB_MATCH_WORK`) is a constant
  calibrated on ordinary hardware**, not a formal proof — on a much slower
  machine, a large `allowed_paths`/`protected_paths` list could approach the
  hook's own timeout instead of comfortably clearing it.
- **`GIT_DIR`/`GIT_WORK_TREE` in the calling environment are explicitly
  cleared** before every `git` subprocess call the hooks make, so a stray
  value pointing at a different repository can't redirect the scan — this
  used to be a gap and is called out here because it's easy to reintroduce
  by adding a new `subprocess.run(["git", ...])` call without the same
  explicit `env`.
