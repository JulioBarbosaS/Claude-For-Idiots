---
name: claude-for-idiots
description: >-
  Guided, guardrailed project setup for both beginners and experienced
  developers. Prefer EXPLICIT invocation: use when the user runs
  /claude-for-idiots (or "/claude-for-idiots update") or explicitly asks to
  start a guided, beginner-friendly, guardrailed setup (fixed architecture,
  always tests, commit per feature, sanity checks, never hand-edit migrations,
  never leak secrets) — or to update the skill / a configured project. Do NOT
  auto-apply to every new project — many projects (throwaway scripts, existing
  codebases with their own conventions) should be left alone unless the user
  opts in. Adapts explanations to the user's experience level and preferred use
  of technical terms. Day-to-day enforcement lives in a generated CLAUDE.md plus
  hooks, not in this skill staying loaded.
---

# Claude for Idiots

A setup-and-guardrails skill. It runs a short onboarding, then writes
**persistent artifacts** into the target project so the rules keep applying in
every future session — even after the skill itself drops out of context.

The skill is the *installer*. The real enforcement lives in the files it writes:

| Artifact | Path (in the user's project) | Purpose |
|---|---|---|
| Rules + profile | `CLAUDE.md` | Loaded automatically every session. Source of truth for behavior. |
| Config | `.claude-for-idiots/config.json` | Machine-readable answers from onboarding. Read by the hooks. |
| Glossary | `.claude-for-idiots/glossary.json` | Tracks which terms were explained and the user's growing level. |
| Hooks | `.claude/hooks/*.py` | Check Rules 1, 5 and 6 on the common paths and block violations (safety net, not a sandbox). |
| Hook wiring | `.claude/settings.json` | Registers the hooks as `PreToolUse`. |
| Knowledge base | `docs/INDEX.md` | Long-term memory on demand: ADRs, bug investigations, API quirks. |

> Design principle: **everything is meant to be edited and upgraded.** The
> stacks, architectures, and rule text all live in `references/` as data, not
> baked into prose. Add a new stack or architecture by editing a catalog file —
> not by rewriting this skill.

---

## Step 0 — Already set up?

**If the skill was invoked with the argument `update`** (e.g.
`/claude-for-idiots update`) or the user asked to update: skip everything below
and follow the **Updating** section instead.

When this skill runs, check the working directory for `.claude-for-idiots/config.json`.

- **If it exists:** onboarding is done. Read it (and `CLAUDE.md`), adopt the
  recorded language, experience level, and term mode, and just keep working
  under the rules. Do **not** re-run onboarding.
- **If it does not exist:** run onboarding (below).

> **How persistence actually works (important):** Claude invokes this skill only
> when the *task* matches its description (e.g. "start a project") — it does NOT
> auto-load every session, and it does NOT scan the disk for the config. The
> thing that keeps the rules and profile alive in every session is the
> **`CLAUDE.md`** this skill writes, which Claude Code auto-loads on entering the
> directory. The hooks enforce rules 1/5/6 regardless. So: this skill sets things
> up; `CLAUDE.md` + hooks do the day-to-day work. Re-invoke this skill only to
> create or change a project's configuration.

---

## Step 1 — Onboarding

Ask the questions in `references/onboarding-flow.md`. Summary:

1. **Interaction language** — what language should Claude speak to the user in?
   (Default: English. The skill's own files stay in English regardless.)
2. **Experience level** — `beginner` | `intermediate` | `advanced`. This drives
   the defaults for everything below.
3. **Use of technical terms** — `none` | `explain` | `raw`
   (see "Technical-term modes" below). Default is taken from experience level.
4. **Project objective** — what does the user want to build? Needed to pick a
   stack automatically.
5. **Stack & architecture** — `advanced` users choose; `beginner`/`intermediate`
   let Claude derive it from the objective (see Step 2).
6. **Version control** — *auto-detect*, don't ask blindly: is there a `.git`?
   a remote? If there is none and the user is a beginner, offer to set up Git
   and **explain in plain language what Git is** before doing it.
7. **Tests** — on by default. If a beginner wants them off, first explain why
   they matter (catching breakage early), then respect the choice.

Keep onboarding short and in the user's language. Let the experience level
pre-fill answers so a beginner answers as few questions as possible.

---

## Step 2 — Derive stack & architecture

The whole philosophy: **architecture is a function of `(stack, objective, scale)`
and is always idiomatic to the chosen stack.** There is no single universal
architecture (MVVM, Clean, etc.) — forcing one onto every project would violate
the very rule we want to enforce.

1. Map the objective → a recommended stack using `references/stack-catalog.md`.
2. Map the stack → its idiomatic architecture using
   `references/architecture-catalog.md` (folder layout, layer responsibilities,
   and suggested `allowed_paths`).
3. Scale the depth to the project size. A 200-line tool should **not** get
   enterprise layering — over-engineering is also "making a mess".
4. Present it by experience level:
   - **beginner** → pick it, explain in one simple sentence, proceed.
   - **intermediate** → propose the idiomatic option + a short rationale; allow override.
   - **advanced** → the user drives; Claude respects their choice.

Once chosen, the architecture is **frozen and written explicitly into
`CLAUDE.md` and the config** — variable *across* projects, fixed *within* a
project. That written structure is what Rule 5 (and its hook) enforces.

---

## Step 3 — Write the project artifacts

After stack/architecture are settled:

1. Fill `assets/CLAUDE.template.md` with the chosen values and write it to
   `<project>/CLAUDE.md` (merge, don't clobber, if one already exists).
2. Write `<project>/.claude-for-idiots/config.json` using
   `assets/config.example.json` as the shape. Fill `migrations`,
   `architecture.allowed_paths`, `architecture.enforce` (`deny` | `ask`),
   `brainstorm.enforce` (`off` | `ask` | `deny`; **default `ask`** for a new
   project — Rule 10), `tests`, etc. — the hooks read these. Record
   `skill_version` from this skill's `VERSION` file (updates use it to know
   where the project is starting from).
3. Create `<project>/.claude/hooks/` and copy the five files from this
   skill's `hooks/` directory (the four hooks plus `_cfi_common.py`, which
   they import) into it.
4. Merge `assets/settings.template.json` into `<project>/.claude/settings.json`
   (preserve any existing hooks/keys).
5. Initialize `<project>/.claude-for-idiots/glossary.json` (see
   `references/glossary-format.md`) only when term mode is `explain`.
6. Ensure `.env` is gitignored and a `.env.example` exists (Rule 6).
7. Install the stack's quality tooling (formatter / linter / type-checker) per
   `references/quality-tools.md` and fill `tests.lint_cmd` / `tests.format_cmd`.
   No question needed — on by default.
8. Create `docs/` with an `INDEX.md` from `assets/docs-INDEX.template.md`
   (Rule 8). For beginners, explain it in one sentence: "this folder is the
   project's long-term memory."
9. For web projects: check whether browser-automation tools (e.g. Playwright
   MCP) are available; if not, **offer** to set them up — see
   `references/browser-verification.md`. Never install without asking.

> **Facts must be verified, never assumed.** Before writing any concrete fact
> into `CLAUDE.md` or the config (a path, a port, a command), check it against
> the real project (`ls`, read the actual config files). Never write a path
> "from memory" — e.g. a Prisma SQLite file may live at `prisma/dev.db` *or* at
> the project root depending on configuration. If the artifact doesn't exist
> yet (a database file only appears after the first migration), verify it
> during the **first sanity check** and fix `CLAUDE.md` if it landed elsewhere.

Then confirm to the user, in their language, what was set up.

---

## Updating — `/claude-for-idiots update`

When invoked with the argument `update` (or the user asks to update), skip
onboarding and follow `references/update-flow.md`:

1. **Update the skill install** (`git pull` if it's a clone, fresh download
   otherwise) and report old → new version from the `VERSION` file.
2. **Update the current project**, if it has a `.claude-for-idiots/config.json`:
   summarize what's new (from `CHANGELOG.md`, in the user's language), refresh
   the hooks — copy the current `.claude/hooks/*.py` (including
   `require_feature_alignment.py` on an upgrade from pre-0.5.0) into the
   project and merge `assets/settings.template.json` into
   `<project>/.claude/settings.json` — merge new rules into `CLAUDE.md`, add
   new config fields — **preserving every onboarding choice and verified
   project fact** — then set `skill_version` to the current version.
3. **A project with no `brainstorm` section in its config (pre-0.5.0) stays
   `off`** — the hook reads a missing section that way on purpose, for
   compatibility. Never turn it on as part of the update. Instead, ask, as
   options to pick from (one sentence on what changes: new-feature requests
   would start pausing for a quick choice before code gets written):
   - **`ask` (recommended)** — the hook will require your OK before a
     feature-shaped change lands with no recorded alignment; you can still
     say "just go" per request to skip it.
   - **`deny`** — stricter: it blocks outright until the decisions are
     recorded.
   - **`off`** — leave it exactly as it is today, no prompts.
   Write whichever the user picks (including an explicit `off`) to
   `brainstorm.enforce` in the config; if the user doesn't answer, leave the
   section absent rather than guessing.
4. Remind the user to restart the session so updated hooks/skill take effect.

---

## The rules (source of truth: `references/rules.md`)

1. **Never hand-edit migration files.** Change the models/schema and run the
   library's generator (e.g. `alembic revision --autogenerate`). *(Hook-enforced.)*
2. **Always have tests** — unit + integration, front and back. On by default.
   A beginner may disable them only after being told why they matter. Run only
   the relevant tests during a feature; **ask before running the full suite.**
3. **Commit per feature** when a version control system exists, so progress is
   never lost.
4. **Sanity check after each feature:** lint + type-check → the feature's tests
   → smoke test (boot the app and verify it responds). Build is covered by the
   smoke test.
5. **Keep new files inside the chosen architecture.** *(Hook-enforced.)*
6. **Secrets never reach the remote.** Keys/tokens/passwords live in a
   gitignored `.env` with a committed `.env.example`. Local Git is free; any
   *publishing* action (push, create remote repo, make public, open PR) must be
   confirmed by the user **and** pass a secret scan first. *(Hook-enforced.)*
7. **Reuse before you build.** Search the codebase and `docs/INDEX.md` before
   implementing something new; extend instead of duplicating.
8. **Hard-won knowledge lives in `docs/`.** ADRs, costly bug investigations and
   API quirks go in `docs/` with one-line pointers in `CLAUDE.md` — never essays.
9. **Two failed fixes → stop guessing, research.** Re-read the full error, check
   versions, search the web deeply, then retry with a genuinely new hypothesis.
   Costly investigations become docs (Rule 8).
10. **Align before building a feature.** A request that adds behavior the
    project doesn't have yet pauses first: offer the hidden decisions as
    options to pick from, never an open question, before writing any code.
    Bug fixes, visual tweaks, and renames go straight through. *(Hook-enforced.)*
    Full script: `references/brainstorming.md`.

---

## Technical-term modes

| Mode | Behavior | Glossary? |
|---|---|---|
| `none` | Never use jargon. Always paraphrase (e.g. say "blocking requests from one domain to another" instead of "CORS"). | No |
| `explain` | Use the term, then explain it briefly right after, ramping from simple to advanced **as the user's understanding grows**. The glossary records what was explained and at what depth, so explanations level up over time and don't repeat needlessly. | Yes |
| `raw` | Use terms normally, no explanations. The user just wants the guardrails, not the teaching. | No |

`none` is the hardest to do well — always find the plain-language paraphrase.
See `references/glossary-format.md` for how the `explain` glossary works.

---

## Runtime behavior recap

- Commit after each working feature (Rule 3) with a clear message.
- After each feature, run the sanity check (Rule 4).
- Run only relevant tests during work; **ask permission before the full suite** (Rule 2).
- Before any publishing action, confirm with the user and let the secret-scan
  hook run (Rule 6).
- Before starting a feature, look for existing code to reuse and skim
  `docs/INDEX.md` (Rule 7).
- Record real architecture decisions and costly investigations in `docs/`, one
  index line each (Rule 8).
- If two fixes for the same problem failed: stop guessing — re-read the full
  error, check versions, search the web deeply, then try a NEW hypothesis
  (Rule 9).
- For web smoke tests, read the browser console when browser tools are
  available (`references/browser-verification.md`).
- Speak in the configured language; honor the term mode on every message.

---

## Extending this skill

- **New stack / objective mapping** → edit `references/stack-catalog.md`.
- **New architecture / folder layout** → edit `references/architecture-catalog.md`.
- **Change a rule's wording** → edit `references/rules.md` (and the template).
- **Change quality tooling defaults** → edit `references/quality-tools.md`.
- **New guardrail** → add a hook in `hooks/`, wire it in
  `assets/settings.template.json`, add its config keys to
  `assets/config.example.json`.

Bump `CHANGELOG.md` when you change behavior.
