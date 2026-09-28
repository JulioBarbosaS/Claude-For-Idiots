# Update flow — `/claude-for-idiots update`

Two layers can be stale: the **skill install** itself, and **projects** that were
configured by an older version. Run both parts, in order.

## Part 1 — update the skill install

1. Locate the install: `~/.claude/skills/claude-for-idiots/`.
2. Read its `VERSION` file (absent = pre-0.3.0).
3. Update it:
   - If the install contains a `.git` directory → `git -C <install> pull`.
   - Otherwise → clone fresh to a temp dir
     (`git clone --depth 1 https://github.com/JulioBarbosaS/Claude-For-Idiots`)
     and copy it over the install, excluding `.git`.
4. Read `VERSION` again and report **old → new** to the user.
5. If `SKILL.md` itself changed, recommend restarting the session — the loaded
   skill body is from invocation time (reference files, however, are read fresh
   from disk).

## Part 2 — update the current project

Only if `<cwd>/.claude-for-idiots/config.json` exists; otherwise say so and stop.

1. Read `skill_version` from the config (absent = pre-0.3.0).
2. Read the skill's `CHANGELOG.md` between that version and the current one and
   **summarize what's new to the user in their language** before touching
   anything.
3. If the project has uncommitted work, suggest committing first (Rule 3
   spirit) before applying the update.
4. Apply — preserving **every onboarding choice and project fact**:
   - Overwrite `.claude/hooks/*.py` with the current ones (they are
     skill-managed). If a project hook differs from what the skill ships, show
     a short diff and **ask** first — the user may have customized it.
   - Merge any new hook entries into `.claude/settings.json` (never remove the
     user's own entries).
   - Add new config fields with their defaults (never change existing values).
   - **Exception — `brainstorm` (0.5.0+).** Do NOT add this section with a
     default. A missing section reads as `off`, on purpose, so an upgrading
     project keeps behaving exactly as it did. Rule 10 changes what happens
     when the user asks for a feature, so it is their call, not a default:
     ask, as options to pick from, and write only what they choose. If they
     don't answer, leave the section absent. See `SKILL.md`'s "Updating".
   - Merge new rules/sections into `CLAUDE.md` — **never** overwrite the stack,
     architecture, or verified facts.
   - Create artifacts that didn't exist in the old version (e.g. `docs/INDEX.md`
     for pre-0.2.0 projects).
5. Set `skill_version` in the config to the current version.
6. Remind the user: hooks load at session start — **restart the session** for
   updated hooks to take effect.
