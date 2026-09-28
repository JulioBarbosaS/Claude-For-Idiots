# Architecture catalog — stack → idiomatic architecture

Data file. For each stack, this gives the **idiomatic** layout, the
responsibility of each layer, and a suggested `allowed_paths` list for the
Rule-5 hook. **Edit freely** to refine or add stacks.

The `allowed_paths` below are a **starting point verified against
`tests/fixtures/`** (see `tests/test_real_projects.py`), not a prescription.
During setup, check them against the real project and add whatever else
exists — a scaffold tool's defaults change, and a stack has more than one
legitimate layout (e.g. Next.js with vs. without `--src-dir`).

Golden rules:
- Architecture must be **idiomatic to the stack** — never force MVVM/Clean/etc.
  onto a stack where it fights the framework.
- **Scale depth to size.** Tiny project → flat structure. Don't add layers a
  small project doesn't need; over-engineering is also a mess.
- Once chosen, copy the layout + `allowed_paths` into `config.json` and `CLAUDE.md`.

---

## FastAPI (backend API)

Layered: `routes → services → repositories → models`.

```
app/
  api/routes/        # HTTP endpoints, request/response only
  services/          # business logic
  repositories/      # DB access
  models/            # ORM models / schemas
  core/              # config, settings
tests/
  unit/
  integration/
```
`allowed_paths`: `["app/**", "tests/**", "alembic/**", "migrations/**",
"scripts/**", "*.py"]`
`enforce`: `deny` (layout is stable)
Migrations tool: Alembic (`alembic/versions/**` protected).
The `*.py` entry covers root-level files every FastAPI project has from day
one: `main.py`, `conftest.py`, task runners like `noxfile.py`. `alembic/**`
and `scripts/**` cover the migration tool and one-off maintenance scripts.
`migrations/**` covers the same tool under its other common name: Alembic's
directory is whatever name `alembic init <name>` was given, and `migrations`
(not `alembic`) is a frequent choice for teams coming from Django-style
naming — without it, `migrations/env.py` reads as an out-of-architecture
placement the first time a project uses that name.

## NestJS (backend API, TypeScript)

Module-per-feature (framework-native): `module → controller → service → repository`.

```
src/
  <feature>/
    <feature>.controller.ts
    <feature>.service.ts
    <feature>.module.ts
  common/
test/
```
`allowed_paths`: `["src/**", "test/**", "prisma/**", "scripts/**",
"*.config.*", "*.ts"]`
`enforce`: `deny` (layout is stable)
`*.config.*` covers root tooling config (`jest.config.js`,
`eslint.config.mjs`); `*.ts` covers other root-level TypeScript such as a
TypeORM `data-source.ts`. `prisma/**` covers Prisma's schema/migrations
directory — as common a pairing with NestJS as it is with Next.js (already
listed below), and there is no framework reason to grant it to one and not
the other. `scripts/**` covers one-off scripts run outside Nest's DI
container, most often a Prisma seed script (`scripts/seed.ts`, wired up via
`package.json`'s `prisma.seed` field).
If using Prisma: protect `prisma/migrations/**`.

## Next.js (web app / full-stack, React)

Feature-folders + components. **Not MVVM** — React is component + hooks.

`create-next-app` **without** `--src-dir` is the default, and puts the App
Router at `app/` in the project root, not under `src/`. Accept both
layouts — don't force `--src-dir` on a project that didn't opt into it.

```
app/                 # routes (App Router) -- or src/app/ with --src-dir
  api/<route>/route.ts
components/           # reusable UI
lib/                  # helpers, clients
e2e/                  # Playwright/Cypress end-to-end tests
prisma/               # if using Prisma (protect prisma/migrations/**)
```
`allowed_paths`: `["app/**", "src/**", "components/**", "lib/**", "e2e/**",
"tests/**", "prisma/**", "public/**", "scripts/**", "*.config.*",
"middleware.ts", "instrumentation.ts", "*.d.ts"]`
`enforce`: `ask` (root-level configs vary)
If using Prisma: protect `prisma/migrations/**`.
`public/**` is `create-next-app`'s default static-assets directory — it
ships with the default `next.svg`/`vercel.svg` icons on every scaffold, and
is also where a PWA integration (e.g. `next-pwa`) writes a generated
`public/sw.js`. `scripts/**` covers one-off scripts run outside the Next.js
build (most commonly a Prisma seed script wired up via `package.json`'s
`prisma.seed` field).

## Flutter (mobile)

Feature-first + a state-management layer. **Here MVVM / BLoC / Riverpod fits.**

```
lib/
  features/<name>/
    presentation/    # widgets (the "View")
    application/     # state / view-models / blocs
    domain/          # entities, use-cases
    data/            # repositories, data sources
  core/
test/
```
`allowed_paths`: `["lib/**", "test/**", "integration_test/**",
"test_driver/**", "tool/**",
"android/**/build.gradle.kts", "android/**/build.gradle",
"android/**/settings.gradle.kts", "android/**/gradle.properties",
"android/**/MainActivity.kt", "android/**/MainActivity.java",
"ios/Runner/AppDelegate.swift", "ios/Runner/Info.plist",
"ios/Runner/*.entitlements",
"macos/Runner/AppDelegate.swift", "macos/Runner/MainFlutterWindow.swift",
"macos/Runner/Info.plist", "macos/Runner/*.entitlements",
"linux/runner/**", "windows/runner/**", "web/index.html"]`
`enforce`: `deny` (feature-first layout is stable)
`integration_test/` is Flutter's own official integration-test directory
(what `flutter test integration_test` runs) and `test_driver/` is its
legacy driver counterpart — blocking either would put this rule in direct
conflict with Rule 2, which tells the agent to write integration tests
there. `tool/` is the conventional home for one-off build/codegen scripts.

**Native platform folders.** Every `flutter create` also generates six
native platform trees (`android/`, `ios/`, `macos/`, `linux/`, `windows/`,
`web/`) that hold config and embedding code outside the Dart
`lib/` architecture entirely — a fresh scaffold's own entry-point and build
files (`android/app/build.gradle.kts`, `ios/Runner/AppDelegate.swift`,
`web/index.html`, ...) were denied by the old catalog because none of these
trees appeared in `allowed_paths` at all, and their extensions
(`.kt`, `.swift`, `.cc`, `.cpp`, `.plist`, `.html`) are all policed code
extensions, not exempted by `IGNORED_EXT`.

**Decision: allow only the specific config/entry-point files each platform
ships with, not the whole native trees, except for `linux/runner/**` and
`windows/runner/**`.** The alternative — `android/** ios/** web/** macos/**
linux/** windows/**` wholesale — was rejected. `android/` and `ios/` are
large, open-ended native source trees (arbitrary Kotlin/Java package paths
under `android/app/src/main/...`, an Xcode project under `ios/Runner.xcodeproj/`)
where an agent could place substantial native business logic that
duplicates or bypasses the chosen Dart feature-first architecture — exactly
what Rule 5 exists to catch. Opening those two trees fully would mean Rule 5
no longer notices a new native source file anywhere under them: a plugin
implementation, a whole parallel native networking layer, or a stray file
from a typo'd path all become silently permitted. `linux/runner/**` and
`windows/runner/**` are the one exception, opened in full: they are a small,
fixed, non-extensible set of files `flutter create` generates once (the
desktop embedder shell — `main.cpp`/`main.cc`, `flutter_window.*`,
`win32_window.*`, `my_application.*`, `utils.*`, `resource.h`, `Runner.rc`)
that hold no Dart-architecture-equivalent business logic and are not a
realistic vector for smuggling in unrelated code, so the risk of opening
them fully is negligible while the risk of missing one of their sibling
files (which vary slightly by Flutter SDK version) is real.
`ios/Runner/*.entitlements` and `macos/Runner/*.entitlements` are included
because capability configuration (push notifications, keychain groups, app
sandbox) is edited by name (`DebugProfile.entitlements`,
`Release.entitlements`) as part of routine platform setup.

Trade-off of the narrower choice: a genuinely new native file that is not
one of the listed entry points is still denied and needs an `allowed_paths`
update — e.g. a new Kotlin class for a custom platform channel
(`android/app/src/main/kotlin/.../MyPlugin.kt`), a new Swift file
(`ios/Runner/MyPlugin.swift`), or the Xcode project itself
(`ios/Runner.xcodeproj/project.pbxproj`, edited by CocoaPods/Xcode tooling
more than by hand). Also still denied: adding a **new** platform to a
project that did not have it yet on Android/iOS/macOS (e.g.
`flutter create --platforms=macos` writes a fresh `macos/` tree, only three
of whose files are in the explicit list). That is treated as correct, not a
gap: both cases are an architecture decision the human should confirm, the
same way this catalog asks for any other layout change. Windows and Linux
are the exception in both directions — their `runner/**` grant is already
wide enough that adding those platforms fresh needs no catalog update.

## Python CLI / automation (Typer)

Keep it flat. No layers.

```
src/<pkg>/
  __init__.py
  cli.py             # entrypoint / commands
  <module>.py        # one module per concern
tests/
```
`allowed_paths`: `["src/**", "tests/**", "scripts/**", "docs/**", "*.py"]`
`enforce`: `ask` (flat and small — a soft nudge is enough)
`*.py` covers root-level automation scripts (`noxfile.py`, `setup.py`) that
a flat project commonly keeps outside `src/`. `scripts/**` covers release
automation (`scripts/release.sh`) that doesn't belong in the package
itself. `docs/**` covers Sphinx documentation (`docs/conf.py` and its
`.rst` sources) — a common addition once a CLI has more than a handful of
commands.

## Data / ML prototype (Python)

Pipeline-style, not app-style.

```
src/
  data/              # loading / cleaning
  features/          # feature engineering
  models/            # training / eval
notebooks/
tests/
```
`allowed_paths`: `["src/**", "tests/**", "notebooks/**", "data/**",
"scripts/**", "*.py"]`
`enforce`: `ask` (pipeline stage boundaries are still explorative)
`*.py` covers root-level files common in this template (e.g. `setup.py`,
as in the classic cookiecutter-data-science layout). `data/**` is that same
template's top-level data directory (`data/raw`, `data/processed`, ...) —
in a small prototype it commonly also holds a loader script
(`data/load.py`) instead of factoring one out to `src/data/` from day one.
`scripts/**` covers ad-hoc pipeline-orchestration shell scripts
(`scripts/train.sh`) that sit outside the `src/` package.

## Astro (web app / content site)

Islands architecture: static-first, components hydrate individually.

```
src/
  pages/             # file-based routing (.astro, .md, .mdx)
  components/        # .astro / framework components (React, Vue, ...)
  layouts/
tests/
```
`allowed_paths`: `["src/**", "tests/**", "public/**", "scripts/**",
"*.config.*"]`
`enforce`: `ask` (small sites vary a lot in root tooling)
`public/**` is Astro's default static-assets directory (favicon,
`robots.txt`, and — with a PWA integration — a generated `public/sw.js`).
`scripts/**` covers Node build-time scripts (e.g. RSS feed generation,
content migration) commonly run outside Astro's own `src/` pipeline.

---

## Mapping to the Rule-5 hook

The hook reads `architecture.allowed_paths`, `architecture.layers`, and
`architecture.enforce` (`deny` | `ask` | `off`) from `config.json`. Use `ask`
when you want a soft nudge and `deny` when the layout must be strict.
