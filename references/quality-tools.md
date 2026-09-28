# Quality tools — formatter / linter / type-checker per stack

Data file. During setup (Step 3) Claude installs these automatically and fills
`tests.lint_cmd` / `tests.format_cmd` in the config — they are what Rule 4's
sanity check runs. **Edit freely** to change defaults or add stacks.

For beginners, explain the idea in one plain sentence: *"a spell-checker for
code — it catches sloppy or broken-looking code before it bites you."*

| Stack | Formatter | Linter | Type-checker | Notes |
|---|---|---|---|---|
| Python | `ruff format` | `ruff check` | `mypy` | Ruff replaces black/isort/flake8 and is very fast. `pylint` is a valid deeper (but slower) alternative. |
| JS/TS (Next.js, Nest, Node) | Prettier *(or Biome)* | ESLint *(or Biome)* | `tsc --noEmit` | Biome = one fast tool for both; ESLint+Prettier = bigger ecosystem. |
| Flutter / Dart | `dart format` | `flutter analyze` | built-in | Ships with the SDK; nothing to install. |
| Go | `gofmt` | `go vet` (+ `golangci-lint`) | built-in | gofmt is non-negotiable in Go culture. |
| Rust | `rustfmt` | `clippy` | built-in | Ship with the toolchain. |

## Setup duties

1. Install the tools as dev dependencies **inside an isolated environment**:
   - Python: `python3 -m venv .venv && .venv/bin/pip install ruff mypy`
     (a bare `pip install` fails with `externally-managed-environment` on
     Debian/Ubuntu/Arch — PEP 668)
   - JS/TS: `npm i -D eslint prettier typescript`
2. Create the tool's minimal config **and the npm scripts that run it** —
   `create-next-app`, `nest new` and `create-vite` do NOT generate a
   `typecheck` script, so `npm run typecheck` fails with
   `Missing script: "typecheck"`. Add to `package.json`:
   ```json
   "scripts": { "typecheck": "tsc --noEmit", "format": "prettier --write ." }
   ```
3. Only then fill `tests.lint_cmd` / `tests.format_cmd` — with commands you
   have actually run once in this project.
4. **No onboarding question** — quality tooling is on by default: it's cheap,
   silent, and prevents style debates. Advanced users change tools by editing
   this catalog / the config.
