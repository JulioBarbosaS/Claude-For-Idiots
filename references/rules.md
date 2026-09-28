# Rules — single source of truth

These are the engineering rules `claude-for-idiots` enforces. The generated
`CLAUDE.md` copies this text (adapted to the chosen stack). Edit here first.

Rules marked **[hook]** are additionally checked by a script in `hooks/`. The
hooks intercept the most common paths (the `Edit`/`Write` tools and shell
commands that publish) — they are a safety net, **not a sandbox**. Known gaps
are listed in `hooks/README.md`; a determined or unlucky path can still get
through, so the written rule still matters.

---

## Rule 1 — Never hand-edit migration files **[hook]**

Migration files are *generated artifacts*. Never open or edit a file under the
migrations directory directly.

To change the database schema:
1. Change the models / schema definition.
2. Run the library's generator, e.g.:
   - Alembic: `alembic revision --autogenerate -m "describe change" && alembic upgrade head`
   - Prisma: `npx prisma migrate dev --name describe_change` (already applies it)
   - Django: `python manage.py makemigrations && python manage.py migrate`

   Generating the migration does not change the database. Skip the
   apply/migrate step and the schema stays the old one — the error only
   shows up on the next query, far from the actual cause.
3. Review the generated file (reading is fine; editing it by hand is not).

The protected paths and the exact command live in
`.claude-for-idiots/config.json` under `migrations`.

## Rule 2 — Always have tests

Unit **and** integration tests, on both frontend and backend, are on by default.

- During a feature, run only the **relevant** tests — fast feedback.
- **Ask the user for permission before running the full suite** (it is slow/costly).
- A beginner may disable tests, but only after Claude explains *why they matter*
  (they catch breakage before the user does, and make changes safe).

## Rule 3 — Commit per feature

If a version control system exists, commit after each working feature with a
clear message, so progress is never lost. Detect version control automatically;
don't force it on a user who didn't ask, but offer it to beginners (and explain
what Git is, in plain language, first).

## Rule 4 — Sanity check after each feature

After implementing a feature, verify you didn't break anything:
1. Lint + type-check.
2. Run the feature's own tests.
3. Smoke test: boot the app and confirm it starts and the feature responds.

(A successful smoke test implies a successful build.)

For web projects, when browser-automation tools are available (see
`references/browser-verification.md`), the smoke test also loads the page and
reads the **browser console** — console errors fail the check.

## Rule 5 — Keep new files inside the chosen architecture **[hook]**

Every new code file must land in the layer/folder defined by the project's
architecture (recorded in `CLAUDE.md` and `config.json` → `architecture`).
If a deliberate architectural change is needed, update the architecture in both
files first, then create the file.

## Rule 6 — Secrets never reach the remote **[hook]**

API keys, tokens, passwords, private keys → always in a **gitignored `.env`**,
with a committed **`.env.example`** documenting the variable names (no values).

Local Git is free (init, commit, branch). Any **publishing** action — `git push`,
creating a remote repo, making a repo public, opening a PR — must:
1. be explicitly confirmed by the user, and
2. pass a secret scan first.

The worst possible accident for a beginner is publishing a public repo with a
live API key inside. This rule exists to make that much harder — the hook scans what git is about to publish, and refuses the push when it finds something.

## Rule 7 — Reuse before you build

Before implementing a feature, look for something that already does it (or
nearly does): search the codebase and skim `docs/INDEX.md`. Extend or reuse
instead of duplicating. If something similar exists but genuinely can't be
reused, say why in one line before writing the new thing.

## Rule 8 — Hard-won knowledge lives in `docs/`, not in CLAUDE.md

`CLAUDE.md` is loaded every session — permanent context cost — so it must stay
short. Long-form knowledge goes in `docs/` as individual files, with at most a
one-line pointer in `CLAUDE.md`:

- architecture decisions (small ADRs: context → decision → consequences — see
  `assets/ADR.template.md`),
- bug investigations that cost real time,
- quirks of external API integrations.

Consult `docs/INDEX.md` when a task touches a documented area; write a new doc
(and index it) when you make a real architectural decision or close a costly
investigation. Keep it lightweight: a small project may go a long time with an
empty index — that's fine. Never write an ADR for a trivial choice.

Think in three layers: **always loaded** (`CLAUDE.md` — short), **on demand**
(`docs/`, config, glossary — deep, but zero cost until needed), **discovered
live** (the code and tests themselves).

## Rule 9 — Two failed fixes → stop guessing, research

If two attempts to fix the **same** problem have failed (the user reports it
still broken a second time), do NOT try a third variation of the same guess.
Escalate instead:

1. Re-read the **complete** error message/logs — slowly, top to bottom.
2. Check installed versions against the docs — version mismatch is the #1 cause
   of "mysterious" failures.
3. **Search the web deeply** (when web access is available): official docs,
   GitHub issues, changelogs — search for the exact error text.
4. Only then touch code again, with a genuinely **new** hypothesis.

If the investigation ends up costing real time, record it in
`docs/investigations/` with an index line (Rule 8) — the same bug is never paid
for twice.

## Rule 10 — Align before building a feature **[hook]**

When a request would add behavior the project doesn't have yet, stop and offer
the hidden decisions as **choices** before writing any code — implementation
doesn't start on Claude's first reading of the request. A bug fix, a visual
tweak, or a rename don't trigger this; those stay on the fast path.

```
fires:      "quero login com Google" · "adiciona carrinho" · "exportar em PDF"
does not:   "arruma esse erro do console" · "muda a cor do botão" · "renomeia calcTotal"
```

Ask as **options to pick from, never an open question**: 2–4 decisions that
actually change the outcome, each option carrying a one-line consequence, built
from what a codebase / `docs/INDEX.md` search turns up first (Rule 7, done at
the right time — before the options are drafted, not after). Once the user
picks — or says "just go," which is honored and recorded, not repeated — write
the decisions to `.claude-for-idiots/current-feature.json` before touching code.

Force is configurable per project (`config.json` → `brainstorm.enforce`:
`off` | `ask` | `deny`, default `ask`), and the user can always dismiss it for
the current request. The full script — classifying, searching, phrasing the
options, the term-mode handling — lives in `references/brainstorming.md`.

The hook only catches one shape of miss: a new code file created with no
alignment record at all. It can't read the prompt, so it can't itself tell a
bug fix from a feature — that classification is the model's, from this rule.
A feature built entirely inside files that already exist passes the hook
untouched; known gaps are listed in `hooks/README.md`.
