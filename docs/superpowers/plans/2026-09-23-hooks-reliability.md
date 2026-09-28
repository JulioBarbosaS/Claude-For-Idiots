# Plano de Implementação — Confiabilidade dos Hooks (v0.4.0)

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para rastreamento.

**Goal:** Fazer as Regras 1, 5 e 6 cumprirem o que o texto promete — hoje as três falham no caminho mais provável de cada uma — e ancorar a suíte em projetos reais para que a próxima regressão seja detectada.

**Architecture:** Extrair um módulo compartilhado (`hooks/_cfi_common.py`) com a única implementação de matching de glob, normalização de caminho e protocolo de decisão; os três hooks passam a consumi-lo. A validação deixa de usar árvores imaginárias e passa a usar fixtures de projetos reais versionadas, com o contrato "todo arquivo que um projeto legítimo deste stack contém precisa ser permitido".

**Tech Stack:** Python 3.9+ (somente stdlib), `unittest`, GitHub Actions, git.

**Spec:** Não existe documento de spec separado — o brainstorming foi interrompido a pedido do usuário. O inventário de defeitos que este plano implementa está na seção **Inventário** abaixo, e cada item traz a evidência que o reproduz.

## Global Constraints

- **Somente biblioteca padrão.** Nenhum `pip install` nos hooks. Eles rodam na máquina do usuário final.
- **Piso de versão: Python 3.9.** Nada de `match`, `X | Y` em anotação avaliada, nem `str.removeprefix` sem guarda.
- **Fail-open é inviolável.** Qualquer entrada inesperada — stdin corrompido, config malformado, caminho fora do projeto — resulta em `exit 0` sem saída. Um hook nunca pode sair com código ≠ 0.
- **Compatibilidade de config é aditiva.** Nenhum campo existente muda de nome ou de tipo. Projetos em 0.3.0 continuam funcionando sem migração.
- **Caminhos internos sempre POSIX.** Normalizar `\` para `/` na fronteira; nunca comparar com `os.sep`.
- **Toda mensagem de bloqueio precisa conter a saída.** O usuário-alvo é iniciante: o `permissionDecisionReason` diz o que fazer, e o comando que ele sugere precisa ser executável em shell.
- **O nome do módulo compartilhado é `_cfi_common.py`** e ele é copiado para `<project>/.claude/hooks/` junto com os três hooks.

## Review Focus

Classes de entrada que o inventário implica, que nenhuma tarefa exercitaria por padrão, e que quebram na mão de gente real. Cada uma tem seu teste atribuído à tarefa dona do código:

1. **Caminho com caractere não-ASCII** (`src/configuração.py`) — público-alvo brasileiro. Precisa ser tratado igual a um caminho ASCII em todos os três hooks. → Tarefa 2 e Tarefa 7.
2. **Caminho absoluto no estilo Windows** (`C:\proj\src\x.ts`) com `\` como separador — o README anuncia Windows. → Tarefa 2.
3. **`allowed_paths` como string em vez de lista** (`"src/**"`) — config editado à mão por iniciante; hoje iteraria caractere a caractere. → Tarefa 5.
4. **Caminho apontando para fora do projeto** (`../../etc/passwd`, symlink) — `relpath` devolve `../…` e nenhum glob casa; precisa ser fail-open explícito, não acidente. → Tarefa 2.
5. **Repositório grande no scan de segredos** — o timeout de hook do Claude Code é 60s; um monorepo com assets binários não pode estourar. → Tarefa 8.

---

## Inventário (o que este plano corrige)

Todos reproduzidos com os hooks reais. `✅` = verificado nesta sessão.

| ID | Defeito | Tarefa |
|---|---|---|
| E1 | Texto promete "guarantees… make that impossible"; as 3 regras têm furo ✅ | 1 |
| B4 | `fnmatch` não implementa `**` ✅ | 2 |
| C4 | `./alembic/versions/a.py` escapa ✅ | 2 |
| B7 | `file_path` relativo + cwd do processo → falso deny | 3 |
| C5 | `NotebookEdit` usa `notebook_path`, não lido | 3 |
| B3 | `CODE_EXT` não cobre `.astro .mjs .cjs .mts .sql .sh` ✅ | 4 |
| B2 | `enforce` ausente desliga a Regra 5 em silêncio ✅ | 5 |
| B6 | `{"architecture":"layered"}` → `rc=1 AttributeError` ✅ | 5 |
| B1 | 42 de 63 arquivos reais bloqueados; Next.js default negado inteiro ✅ | 6 |
| B5 | Flutter `integration_test/` negado — Regra 5 bloqueia Regra 2 ✅ | 6 |
| G1 | Nenhum teste usa projeto real ✅ | 6 |
| A1 | Nome com acento invisível ao scanner ✅ | 7 |
| A3 | Scanner só enxerga abaixo do `cwd` ✅ | 7 |
| A2 | Varre working tree, não o histórico ✅ | 8 |
| A6 | `.env` gitignorado é invisível ✅ | 8 |
| A4 | 11 de 12 comandos de publicação passam ✅ | 9 |
| A5 | `git -C` / `--git-dir` desarmam o regex ✅ | 9 |
| A7 | Sem allowlist; bloqueia o próprio repo ✅ | 10 |
| C1 | `**/migrations/**` bloqueia código de app e docs ✅ | 11 |
| C2 | `--name <describe_change>` é sintaxe inválida de shell ✅ | 11 |
| C3 | Falta `alembic upgrade head` / `manage.py migrate` | 11 |
| F1 | `npm run typecheck` não existe em projeto novo ✅ | 12 |
| F2 | `pip install ruff mypy` → PEP 668 | 12 |
| G2 | CI não valida JSONs nem `VERSION` × `CHANGELOG` ✅ | 12 |
| G3/G4 | CI só Ubuntu; não roda linter no próprio código ✅ | 12 |

**Fora deste plano** (vão para o Plano 2 — fluxo e `SKILL.md`): D1–D8, F3.

---

## Estrutura de arquivos

**Criar:**
- `hooks/_cfi_common.py` — matching de glob, normalização de caminho, leitura de config, protocolo de decisão. Única fonte dessas quatro coisas.
- `tests/test_common.py` — testes unitários do módulo compartilhado.
- `tests/fixtures/<stack>/…` — árvores reais de Next.js (App Router sem `src`), FastAPI, Flutter, NestJS e Astro.
- `tests/test_real_projects.py` — roda os hooks contra as fixtures.
- `pyproject.toml` — configuração do ruff para o próprio repo.

**Modificar:**
- `hooks/block_migration_edits.py`, `hooks/enforce_architecture.py`, `hooks/scan_secrets_before_push.py`
- `tests/test_hooks.py`, `.github/workflows/ci.yml`
- `assets/config.example.json`, `assets/settings.template.json`
- `references/rules.md`, `references/architecture-catalog.md`, `references/quality-tools.md`
- `README.md`, `README.pt-br.md`, `hooks/README.md`, `SKILL.md`, `CHANGELOG.md`

---

### Task 1: Parar de prometer garantia que não existe

Primeiro porque é a correção mais barata e o dano é o maior: o público-alvo é iniciante, que confia no texto e não tem como verificar.

**Files:**
- Modify: `references/rules.md:6-7`, `:73-74`
- Modify: `SKILL.md:30`
- Modify: `README.md` (seção "What it enforces"), `README.pt-br.md` (seção "O que ela garante")
- Modify: `hooks/README.md:4-5`

- [ ] **Step 1: Substituir o texto de `references/rules.md`**

Trocar `Rules marked **[hook]** are also enforced technically by a script in `hooks/`, so they are guarantees, not just promises.` por:

```markdown
Rules marked **[hook]** are additionally checked by a script in `hooks/`. The
hooks intercept the most common paths (the `Edit`/`Write` tools and shell
commands that publish) — they are a safety net, **not a sandbox**. Known gaps
are listed in `hooks/README.md`; a determined or unlucky path can still get
through, so the written rule still matters.
```

- [ ] **Step 2: Remover a promessa absoluta da Rule 6**

Em `references/rules.md`, trocar `This rule exists to make that impossible.` por `This rule exists to make that much harder — the hook scans what git is about to publish, and refuses the push when it finds something.`

- [ ] **Step 3: Alinhar `SKILL.md` e `hooks/README.md`**

Em `SKILL.md`, trocar `Technically enforce Rules 1, 5 and 6 (block, not just promise).` por `Check Rules 1, 5 and 6 on the common paths and block violations (safety net, not a sandbox).`
Em `hooks/README.md`, trocar `turn rules 1, 5, and 6 into **guarantees** rather than promises` por `add a technical check to rules 1, 5 and 6 on the paths Claude Code most often takes`.

- [ ] **Step 4: Alinhar os dois READMEs**

Em `README.md`, trocar o cabeçalho `**🔒 Enforced** = guaranteed by a hook; Claude literally can't break it.` por `**🔒 Checked by a hook** = a script blocks the common violation paths. See "Known limitations" for what still gets through.`
Em `README.pt-br.md`, trocar `**🔒 Garantido** = imposto por um hook; o Claude literalmente não consegue quebrar.` por `**🔒 Checado por hook** = um script bloqueia os caminhos mais comuns de violação. Veja "Limitações conhecidas" para o que ainda passa.`

- [ ] **Step 5: Verificar que nenhuma promessa absoluta sobrou**

Run: `grep -rniE "guarantee|impossible|literally can't|literalmente não consegue" --include=*.md . | grep -v CHANGELOG`
Expected: nenhuma linha afirmando garantia absoluta sobre os hooks.

- [ ] **Step 6: Commit**

```bash
git add references/rules.md SKILL.md hooks/README.md README.md README.pt-br.md
git commit -m "docs: describe hooks as a safety net, not a guarantee"
```

---

### Task 2: Módulo compartilhado com matching de glob correto

**Files:**
- Create: `hooks/_cfi_common.py`
- Test: `tests/test_common.py`

**Interfaces:**
- Consumes: nada (é a base).
- Produces:
  - `read_event() -> dict | None`
  - `load_config(cwd: str) -> dict | None`
  - `section(config: dict, name: str) -> dict`
  - `str_list(value) -> list[str]`
  - `compile_glob(pattern: str) -> re.Pattern`
  - `matches_any(rel_path: str, patterns: list[str]) -> bool`
  - `relativize(file_path: str, cwd: str) -> str | None`
  - `target_path(tool_input: dict) -> str`
  - `decide(decision: str, reason: str) -> NoReturn` (imprime e `exit 0`)
  - `allow() -> NoReturn` (`exit 0` silencioso)

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_common.py
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import _cfi_common as c


class TestCompileGlob(unittest.TestCase):
    def test_double_star_matches_zero_leading_dirs(self):
        self.assertTrue(c.matches_any("migrations/0001.py", ["**/migrations/**"]))

    def test_double_star_matches_nested_leading_dirs(self):
        self.assertTrue(c.matches_any("app/db/migrations/0001.py", ["**/migrations/**"]))

    def test_single_star_does_not_cross_separator(self):
        self.assertFalse(c.matches_any("src/app/page.tsx", ["*.tsx"]))
        self.assertTrue(c.matches_any("page.tsx", ["*.tsx"]))

    def test_root_config_glob(self):
        self.assertTrue(c.matches_any("next.config.mjs", ["*.config.*"]))
        self.assertFalse(c.matches_any("src/next.config.mjs", ["*.config.*"]))

    def test_prefix_glob_matches_nested(self):
        self.assertTrue(c.matches_any("src/a/b/c.ts", ["src/**"]))


class TestRelativize(unittest.TestCase):
    def test_strips_dot_segments(self):
        self.assertEqual(c.relativize("./alembic/./versions/a.py", "/proj"),
                         "alembic/versions/a.py")

    def test_absolute_inside_project(self):
        self.assertEqual(c.relativize("/proj/src/x.ts", "/proj"), "src/x.ts")

    def test_outside_project_returns_none(self):
        self.assertIsNone(c.relativize("/etc/passwd", "/proj"))
        self.assertIsNone(c.relativize("../../etc/passwd", "/proj"))

    def test_non_ascii_path_is_ordinary(self):
        self.assertEqual(c.relativize("/proj/src/configuração.py", "/proj"),
                         "src/configuração.py")
        self.assertTrue(c.matches_any("src/configuração.py", ["src/**"]))

    def test_windows_style_separators_are_normalized(self):
        self.assertEqual(c.relativize("src\\app\\page.tsx", "/proj"), "src/app/page.tsx")

    def test_empty_path_returns_none(self):
        self.assertIsNone(c.relativize("", "/proj"))


class TestConfigHelpers(unittest.TestCase):
    def test_section_rejects_non_mapping(self):
        self.assertEqual(c.section({"architecture": "layered"}, "architecture"), {})
        self.assertEqual(c.section({"architecture": ["a"]}, "architecture"), {})
        self.assertEqual(c.section({}, "architecture"), {})

    def test_str_list_wraps_bare_string(self):
        self.assertEqual(c.str_list("src/**"), ["src/**"])
        self.assertEqual(c.str_list(["a", 2, None, "b"]), ["a", "b"])
        self.assertEqual(c.str_list(None), [])


class TestTargetPath(unittest.TestCase):
    def test_reads_file_path(self):
        self.assertEqual(c.target_path({"file_path": "a.py"}), "a.py")

    def test_falls_back_to_notebook_path(self):
        self.assertEqual(c.target_path({"notebook_path": "a.ipynb"}), "a.ipynb")

    def test_missing_returns_empty(self):
        self.assertEqual(c.target_path({}), "")
        self.assertEqual(c.target_path(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_common.py`
Expected: FAIL com `ModuleNotFoundError: No module named '_cfi_common'`

- [ ] **Step 3: Implementar o módulo**

```python
#!/usr/bin/env python3
"""Shared helpers for the claude-for-idiots PreToolUse hooks.

Every hook imports from here so path handling, glob semantics and the decision
protocol have exactly one implementation. Standard library only.
"""
import json
import os
import posixpath
import re
import sys
from functools import lru_cache

CONFIG_REL = os.path.join(".claude-for-idiots", "config.json")


def read_event():
    """Parse the PreToolUse event from stdin. None means: fail open."""
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeDecodeError):
        return None
    return event if isinstance(event, dict) else None


def load_config(cwd):
    """Read the project config. None means: fail open."""
    try:
        with open(os.path.join(cwd, CONFIG_REL), encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return config if isinstance(config, dict) else None


def section(config, name):
    """config[name] when it is a mapping, {} otherwise. Never raises."""
    value = (config or {}).get(name)
    return value if isinstance(value, dict) else {}


def str_list(value):
    """Coerce a config field into a list of strings, tolerating a bare string."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str) and item]
    return []


@lru_cache(maxsize=512)
def compile_glob(pattern):
    """Translate a git-style glob into an anchored regex.

    `**/` matches zero or more leading directories, `**` crosses separators,
    `*` and `?` do not. This is what `fnmatch` gets wrong: it maps every `*`
    to `.*`, so `src/**` never matches `next.config.ts` while `**/x/**` fails
    to match a root-level `x/`.
    """
    pattern = pattern.strip().replace("\\", "/")
    out, index, length = [], 0, len(pattern)
    while index < length:
        if pattern.startswith("**/", index):
            out.append(r"(?:[^/]+/)*")
            index += 3
        elif pattern.startswith("**", index):
            out.append(r".*")
            index += 2
        elif pattern[index] == "*":
            out.append(r"[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append(r"[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("^" + "".join(out) + "$")


def matches_any(rel_path, patterns):
    if not rel_path:
        return False
    return any(compile_glob(p).match(rel_path) for p in str_list(patterns))


def relativize(file_path, cwd):
    """Project-relative POSIX path, or None when outside the project."""
    if not file_path or not isinstance(file_path, str):
        return None
    raw = file_path.replace("\\", "/")
    if os.path.isabs(file_path) or (len(file_path) > 1 and file_path[1] == ":"):
        try:
            raw = os.path.relpath(file_path, cwd).replace(os.sep, "/")
        except ValueError:
            return None
    rel = posixpath.normpath(raw)
    if rel in (".", "") or rel.startswith("../"):
        return None
    return rel


def target_path(tool_input):
    """The file a write-shaped tool aims at, whatever field name it uses."""
    for key in ("file_path", "notebook_path"):
        value = (tool_input or {}).get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def decide(decision, reason):
    """Emit a PreToolUse decision and exit 0."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def allow():
    """Silent allow — also the fail-open path."""
    sys.exit(0)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 tests/test_common.py`
Expected: PASS, todos os testes.

- [ ] **Step 5: Commit**

```bash
git add hooks/_cfi_common.py tests/test_common.py
git commit -m "feat(hooks): add shared module with correct ** glob semantics"
```

---

### Task 3: Migrar os três hooks para o módulo compartilhado

**Files:**
- Modify: `hooks/block_migration_edits.py`, `hooks/enforce_architecture.py`, `hooks/scan_secrets_before_push.py`
- Modify: `assets/settings.template.json` (acrescentar `NotebookEdit` ao matcher)
- Modify: `SKILL.md:125-126` (copiar 4 arquivos, não 3)
- Test: `tests/test_hooks.py`

**Interfaces:**
- Consumes: tudo o que a Tarefa 2 produz.
- Produces: os três hooks sem lógica de path/glob própria.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_hooks.py`:

```python
class TestSharedBehavior(TempProject):
    def test_migration_hook_handles_relative_dot_path(self):
        self.write_config(MIGRATIONS_CONFIG)
        proc = run_hook("block_migration_edits.py",
                        self.event("Edit", file_path="./alembic/versions/a.py"))
        self.assertEqual(decision(proc), "deny")

    def test_migration_hook_reads_notebook_path(self):
        self.write_config(MIGRATIONS_CONFIG)
        proc = run_hook("block_migration_edits.py",
                        self.event("NotebookEdit",
                                   notebook_path="alembic/versions/a.ipynb"))
        self.assertEqual(decision(proc), "deny")

    def test_arch_hook_ignores_path_outside_project(self):
        self.write_config(ARCH_CONFIG)
        proc = run_hook("enforce_architecture.py",
                        self.event("Write", file_path="/etc/cron.d/x.py"))
        self.assertIsNone(decision(proc))
        self.assertEqual(proc.returncode, 0)

    def test_arch_hook_existing_file_check_uses_event_cwd(self):
        """A relative path must resolve against event['cwd'], not the process cwd."""
        self.write_config(ARCH_CONFIG)
        target = Path(self.root) / "random" / "old.py"
        target.parent.mkdir(parents=True)
        target.write_text("x = 1\n")
        proc = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "enforce_architecture.py")],
            input=json.dumps(self.event("Write", file_path="random/old.py")),
            capture_output=True, text=True, timeout=30, cwd="/",
        )
        self.assertIsNone(decision(proc))
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestSharedBehavior -v`
Expected: FAIL — 4 falhas (dot-path permitido, notebook_path ignorado, `/etc` fora do projeto, deny falso com cwd `/`).

- [ ] **Step 3: Reescrever `block_migration_edits.py`**

```python
#!/usr/bin/env python3
"""Rule 1 — never hand-edit migration files.

PreToolUse hook (matcher: Edit|Write|MultiEdit|NotebookEdit). Reads the
per-project .claude-for-idiots/config.json for the protected paths and the
generator command. Fails open when there is no config or no migrations
section, so it never interferes with unrelated projects.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfi_common as cfi


def main():
    event = cfi.read_event()
    if not event:
        cfi.allow()

    file_path = cfi.target_path(event.get("tool_input"))
    cwd = event.get("cwd") or os.getcwd()
    config = cfi.load_config(cwd)
    if not config:
        cfi.allow()

    migrations = cfi.section(config, "migrations")
    protected = cfi.str_list(migrations.get("protected_paths"))
    if not protected:
        cfi.allow()

    rel = cfi.relativize(file_path, cwd)
    if not rel or not cfi.matches_any(rel, protected):
        cfi.allow()

    tool = migrations.get("tool", "your migration tool")
    command = migrations.get("command", tool + " autogenerate")
    cfi.decide("deny", (
        "BLOCKED by claude-for-idiots Rule 1: migration files are generated, "
        "never hand-edited.\n"
        "'" + rel + "' matches a protected migration path.\n"
        "Change the models/schema and run: " + command + "\n"
        "Explain this to the user in their language before retrying."
    ))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Reescrever o topo de `enforce_architecture.py`**

Substituir `load_config` e o bloco de `main()` que calcula `rel`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfi_common as cfi


def main():
    event = cfi.read_event()
    if not event:
        cfi.allow()

    file_path = cfi.target_path(event.get("tool_input"))
    cwd = event.get("cwd") or os.getcwd()
    config = cfi.load_config(cwd)
    if not config:
        cfi.allow()

    arch = cfi.section(config, "architecture")
    allowed = cfi.str_list(arch.get("allowed_paths"))
    rel = cfi.relativize(file_path, cwd)
    if not rel or not allowed:
        cfi.allow()

    # An existing file is an edit, not a placement. Resolve against the
    # EVENT's cwd, never the process cwd — the hook may be invoked anywhere.
    if os.path.exists(os.path.join(cwd, rel)):
        cfi.allow()
    # ... (a decisão de modo e extensão entra nas Tarefas 4 e 5)
```

- [ ] **Step 5: Trocar a leitura de config em `scan_secrets_before_push.py`**

Substituir o parsing manual de stdin por `cfi.read_event()` e a emissão de deny por `cfi.decide("deny", ...)`. A lógica de scan permanece; ela é reescrita nas Tarefas 7–10.

- [ ] **Step 6: Registrar `NotebookEdit` no matcher**

Em `assets/settings.template.json`, trocar `"matcher": "Edit|Write|MultiEdit"` por `"matcher": "Edit|Write|MultiEdit|NotebookEdit"`.

- [ ] **Step 7: Mandar o setup copiar 4 arquivos**

Em `SKILL.md`, trocar `copy the three scripts from this skill's hooks/ directory` por `copy the four files from this skill's hooks/ directory (the three hooks plus _cfi_common.py, which they import)`.

- [ ] **Step 8: Rodar a suíte inteira**

Run: `python3 tests/test_hooks.py && python3 tests/test_common.py`
Expected: PASS em ambos; os 16 testes originais continuam verdes.

- [ ] **Step 9: Commit**

```bash
git add hooks/ tests/test_hooks.py assets/settings.template.json SKILL.md
git commit -m "refactor(hooks): consume shared module; fix dot-paths and notebook_path"
```

---

### Task 4: Trocar a lista de extensões por uma lista de não-código

**Files:**
- Modify: `hooks/enforce_architecture.py`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Consumes: `cfi.str_list`, `cfi.section`.
- Produces: `is_policed(rel: str, arch: dict) -> bool` dentro de `enforce_architecture.py`.

- [ ] **Step 1: Escrever o teste que falha**

```python
class TestPolicedExtensions(TempProject):
    POLICED = ["x.ts", "x.mjs", "x.cjs", "x.mts", "x.astro", "x.sql",
               "x.sh", "x.py", "x.go", "x.rs", "x.vue"]
    IGNORED = ["notes.md", "data.json", "config.yml", "Cargo.lock", "logo.svg"]

    def test_every_code_extension_is_policed(self):
        self.write_config(ARCH_CONFIG)
        for name in self.POLICED:
            proc = run_hook("enforce_architecture.py", self.event(
                "Write", file_path=os.path.join(self.root, "random", name)))
            self.assertEqual(decision(proc), "deny", name)

    def test_non_code_is_never_policed(self):
        self.write_config(ARCH_CONFIG)
        for name in self.IGNORED:
            proc = run_hook("enforce_architecture.py", self.event(
                "Write", file_path=os.path.join(self.root, "random", name)))
            self.assertIsNone(decision(proc), name)

    def test_config_can_override_the_ignore_list(self):
        cfg = json.loads(json.dumps(ARCH_CONFIG))
        cfg["architecture"]["ignored_extensions"] = [".ts"]
        self.write_config(cfg)
        proc = run_hook("enforce_architecture.py", self.event(
            "Write", file_path=os.path.join(self.root, "random", "x.ts")))
        self.assertIsNone(decision(proc))
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestPolicedExtensions -v`
Expected: FAIL — `.mjs`, `.cjs`, `.mts`, `.astro`, `.sql`, `.sh` retornam `None` em vez de `deny`.

- [ ] **Step 3: Implementar a inversão**

Substituir o bloco `CODE_EXT` por:

```python
# Inverted on purpose: policing an allow-list of extensions silently exempted
# .mjs/.cjs/.astro/.sql/.sh, so Rule 5 did not apply to whole stacks the
# catalog recommends. Anything that is not obviously prose, data or a binary
# is treated as code.
IGNORED_EXT = {
    ".md", ".markdown", ".rst", ".txt", ".adoc",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".lock", ".csv", ".tsv", ".xml", ".env", ".example", ".sample",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pdf", ".zip", ".gz", ".tar", ".mp3", ".mp4", ".webm",
}


def is_policed(rel, arch):
    """True when this file counts as code for Rule 5."""
    _, ext = os.path.splitext(rel)
    if not ext:
        # No extension: LICENSE, Dockerfile, Makefile. Too noisy to police.
        return False
    override = cfi.str_list(arch.get("ignored_extensions"))
    ignored = set(override) if override else IGNORED_EXT
    return ext.lower() not in ignored
```

E no `main()`, trocar a checagem de extensão por `if not is_policed(rel, arch): cfi.allow()`.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 tests/test_hooks.py -v`
Expected: PASS, incluindo `test_allows_non_code_files` que já existia.

- [ ] **Step 5: Commit**

```bash
git add hooks/enforce_architecture.py tests/test_hooks.py
git commit -m "fix(rule5): police by exclusion so .mjs/.astro/.sql are covered"
```

---

### Task 5: `enforce` explícito e config malformado sem crash

**Files:**
- Modify: `hooks/enforce_architecture.py`
- Modify: `assets/config.example.json`, `SKILL.md:120-124`, `references/architecture-catalog.md`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Consumes: `cfi.section`, `cfi.str_list`.
- Produces: default de `enforce` passa de `"off"` para `"ask"`.

- [ ] **Step 1: Escrever os testes que falham**

```python
class TestEnforceMode(TempProject):
    def test_missing_enforce_defaults_to_ask_not_off(self):
        cfg = {"architecture": {"name": "x", "allowed_paths": ["src/**"],
                                "layers": {}}}
        self.write_config(cfg)
        proc = run_hook("enforce_architecture.py", self.event(
            "Write", file_path=os.path.join(self.root, "random", "x.py")))
        self.assertEqual(decision(proc), "ask")

    def test_malformed_config_fails_open_without_crashing(self):
        for raw in ['{"architecture": "layered"}',
                    '{"architecture": ["a"]}',
                    '{"architecture": {"allowed_paths": "src/**"}}',
                    '{broken', '[]', '']:
            cfg_dir = Path(self.root) / ".claude-for-idiots"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "config.json").write_text(raw)
            proc = run_hook("enforce_architecture.py", self.event(
                "Write", file_path=os.path.join(self.root, "random", "x.py")))
            self.assertEqual(proc.returncode, 0, raw)
            self.assertNotIn("Traceback", proc.stderr, raw)

    def test_allowed_paths_as_bare_string_still_works(self):
        cfg = {"architecture": {"name": "x", "enforce": "deny",
                                "allowed_paths": "src/**", "layers": {}}}
        self.write_config(cfg)
        ok = run_hook("enforce_architecture.py", self.event(
            "Write", file_path=os.path.join(self.root, "src", "x.py")))
        bad = run_hook("enforce_architecture.py", self.event(
            "Write", file_path=os.path.join(self.root, "random", "x.py")))
        self.assertIsNone(decision(ok))
        self.assertEqual(decision(bad), "deny")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestEnforceMode -v`
Expected: FAIL — o primeiro retorna `None`; o segundo produz `rc=1` e `AttributeError` no caso `"layered"`.

- [ ] **Step 3: Implementar**

Em `enforce_architecture.py`:

```python
    # "off" as the default meant a config written without this key silently
    # disabled the rule the skill advertises. "ask" is the safe default: it
    # surfaces the decision instead of swallowing it.
    mode = arch.get("enforce", "ask")
    if mode not in ("deny", "ask"):
        cfi.allow()
```

A proteção contra config malformado já vem de `cfi.section` e `cfi.str_list` (Tarefa 2); este passo apenas confirma que `enforce_architecture.py` não acessa `arch` sem passar por elas.

- [ ] **Step 4: Documentar o campo onde ele é escrito**

- Em `SKILL.md`, trocar `Fill \`migrations\`, \`architecture.allowed_paths\`, \`tests\`, etc.` por ``Fill `migrations`, `architecture.allowed_paths`, `architecture.enforce` (`deny` | `ask`), `tests`, etc.``
- Em `references/architecture-catalog.md`, acrescentar `enforce` à linha de cada stack, logo abaixo de `allowed_paths`. Exemplo para FastAPI: `` `enforce`: `deny` (layout estável) ``. Para Next.js: `` `enforce`: `ask` (configs de raiz variam) ``.

- [ ] **Step 5: Rodar e commitar**

Run: `python3 tests/test_hooks.py && python3 tests/test_common.py`
Expected: PASS.

```bash
git add hooks/enforce_architecture.py tests/test_hooks.py SKILL.md \
        references/architecture-catalog.md assets/config.example.json
git commit -m "fix(rule5): default enforce to ask and survive malformed config"
```

---

### Task 6: Fixtures de projetos reais — e corrigir os `allowed_paths` do catálogo

Esta é a tarefa que impede a próxima regressão. Hoje 42 de 63 arquivos reais são bloqueados porque nenhum teste jamais usou um projeto de verdade.

**Files:**
- Create: `tests/fixtures/nextjs-approuter/`, `tests/fixtures/fastapi/`, `tests/fixtures/flutter/`, `tests/fixtures/nestjs/`, `tests/fixtures/astro/`
- Create: `tests/test_real_projects.py`
- Modify: `references/architecture-catalog.md`

**Interfaces:**
- Consumes: os hooks já corrigidos nas Tarefas 2–5.
- Produces: contrato "todo arquivo de um projeto legítimo deste stack é permitido".

- [ ] **Step 1: Criar as fixtures**

```bash
mkdir -p tests/fixtures/nextjs-approuter/{app/api/users,components,lib,e2e,prisma/migrations/20260101_init}
touch tests/fixtures/nextjs-approuter/{next.config.mjs,middleware.ts,tailwind.config.ts,eslint.config.mjs,postcss.config.mjs,next-env.d.ts,instrumentation.ts,playwright.config.ts}
touch tests/fixtures/nextjs-approuter/app/{page.tsx,layout.tsx}
touch tests/fixtures/nextjs-approuter/app/api/users/route.ts
touch tests/fixtures/nextjs-approuter/components/Button.tsx
touch tests/fixtures/nextjs-approuter/lib/db.ts
touch tests/fixtures/nextjs-approuter/e2e/login.spec.ts
touch tests/fixtures/nextjs-approuter/prisma/seed.ts
touch tests/fixtures/nextjs-approuter/prisma/migrations/20260101_init/migration.sql

mkdir -p tests/fixtures/fastapi/{app/api/routes,app/services,tests/unit,alembic/versions,scripts}
touch tests/fixtures/fastapi/{main.py,conftest.py,noxfile.py}
touch tests/fixtures/fastapi/app/api/routes/users.py
touch tests/fixtures/fastapi/app/services/users.py
touch tests/fixtures/fastapi/tests/unit/test_users.py
touch tests/fixtures/fastapi/alembic/env.py
touch tests/fixtures/fastapi/alembic/versions/abc123_init.py
touch tests/fixtures/fastapi/scripts/seed_db.py

mkdir -p tests/fixtures/flutter/{lib/features/home/presentation,test,integration_test,test_driver,tool}
touch tests/fixtures/flutter/lib/main.dart
touch tests/fixtures/flutter/lib/features/home/presentation/home_page.dart
touch tests/fixtures/flutter/test/widget_test.dart
touch tests/fixtures/flutter/integration_test/app_test.dart
touch tests/fixtures/flutter/test_driver/integration_test.dart
touch tests/fixtures/flutter/tool/build.dart

mkdir -p tests/fixtures/nestjs/{src/users,test}
touch tests/fixtures/nestjs/{jest.config.js,eslint.config.mjs,data-source.ts}
touch tests/fixtures/nestjs/src/main.ts
touch tests/fixtures/nestjs/src/users/users.controller.ts
touch tests/fixtures/nestjs/test/app.e2e-spec.ts

mkdir -p tests/fixtures/astro/src/{pages,components}
touch tests/fixtures/astro/astro.config.mjs
touch tests/fixtures/astro/src/pages/index.astro
touch tests/fixtures/astro/src/components/Card.astro
```

- [ ] **Step 2: Escrever o teste que falha**

```python
#!/usr/bin/env python3
"""Every file a real project of each stack legitimately contains must be
allowed by the Rule 5 hook. Migration directories are the deliberate exception.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
HOOK = ROOT / "hooks" / "enforce_architecture.py"

# Mirrors references/architecture-catalog.md. When the catalog changes, this
# table changes with it — that is the point.
STACKS = {
    "nextjs-approuter": ["app/**", "src/**", "components/**", "lib/**",
                         "e2e/**", "tests/**", "prisma/**", "*.config.*",
                         "middleware.ts", "instrumentation.ts", "*.d.ts"],
    "fastapi": ["app/**", "tests/**", "alembic/**", "scripts/**", "*.py"],
    "flutter": ["lib/**", "test/**", "integration_test/**",
                "test_driver/**", "tool/**"],
    "nestjs": ["src/**", "test/**", "*.config.*", "*.ts"],
    "astro": ["src/**", "tests/**", "*.config.*"],
}


def run_hook(project, rel_path):
    event = {"cwd": str(project), "tool_name": "Write",
             "tool_input": {"file_path": str(project / rel_path)}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, timeout=30)


class TestRealProjects(unittest.TestCase):
    def test_no_legitimate_file_is_blocked(self):
        failures = []
        for stack, allowed in STACKS.items():
            project = FIXTURES / stack
            cfg_dir = project / ".claude-for-idiots"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "config.json").write_text(json.dumps({
                "architecture": {"name": stack, "enforce": "deny",
                                 "allowed_paths": allowed, "layers": {}}}))
            try:
                for path in sorted(project.rglob("*")):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(project).as_posix()
                    if rel.startswith(".claude-for-idiots/"):
                        continue
                    proc = run_hook(project, rel)
                    if proc.stdout.strip():
                        failures.append(stack + ": " + rel)
            finally:
                (cfg_dir / "config.json").unlink()
                cfg_dir.rmdir()
        self.assertEqual(failures, [], "arquivos legítimos bloqueados:\n" +
                         "\n".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `python3 tests/test_real_projects.py`
Expected: FAIL listando os arquivos bloqueados — e a lista é a prova de quais linhas do catálogo estão erradas.

- [ ] **Step 4: Corrigir `references/architecture-catalog.md`**

Ajustar cada seção para o layout real, espelhando a tabela `STACKS` acima. As mudanças obrigatórias:

- **Next.js:** `allowed_paths` passa a `["app/**", "src/**", "components/**", "lib/**", "e2e/**", "tests/**", "prisma/**", "*.config.*", "middleware.ts", "instrumentation.ts", "*.d.ts"]`, com a nota: *`create-next-app` sem `--src-dir` é o default e põe o app em `app/` na raiz; aceite os dois layouts.*
- **Flutter:** acrescentar `integration_test/**`, `test_driver/**`, `tool/**`, com a nota: *`integration_test/` é o diretório oficial de teste de integração — bloqueá-lo contradiz a Regra 2.*
- **FastAPI:** acrescentar `alembic/**`, `scripts/**` e `*.py` (raiz: `main.py`, `conftest.py`, `noxfile.py`).
- **NestJS:** acrescentar `*.config.*` e `*.ts` de raiz.
- **Astro:** criar a seção, que hoje não existe.

Acrescentar ao topo do arquivo: *Os `allowed_paths` abaixo são um **ponto de partida verificado contra `tests/fixtures/`**, não uma prescrição. Durante o setup, confira contra o projeto real e acrescente o que existir.*

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `python3 tests/test_real_projects.py`
Expected: PASS, zero arquivos legítimos bloqueados.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures tests/test_real_projects.py references/architecture-catalog.md
git commit -m "test(rule5): pin allowed_paths against real project trees"
```

---

### Task 7: Scanner — unicode e raiz do repositório

**Files:**
- Modify: `hooks/scan_secrets_before_push.py`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Produces: `repo_root(cwd) -> str | None`, `tracked_files(root) -> list[str]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
class TestScannerCoverage(TempProject):
    SECRET = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'

    def _repo(self, relpath, content):
        subprocess.run(["git", "-C", self.root, "init", "-q"],
                       check=True, capture_output=True)
        target = Path(self.root) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", self.root, "add", "-A"],
                       check=True, capture_output=True)

    def test_non_ascii_filename_is_scanned(self):
        self._repo("app/configuração.py", self.SECRET)
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="git push origin main"))
        self.assertEqual(decision(proc), "deny")

    def test_scans_whole_repo_from_a_subdirectory(self):
        self._repo("infra/deploy.py", self.SECRET)
        (Path(self.root) / "packages" / "web").mkdir(parents=True)
        (Path(self.root) / "packages" / "web" / "index.js").write_text("x\n")
        subprocess.run(["git", "-C", self.root, "add", "-A"],
                       check=True, capture_output=True)
        event = {"cwd": str(Path(self.root) / "packages" / "web"),
                 "tool_name": "Bash",
                 "tool_input": {"command": "git push origin main"}}
        proc = run_hook("scan_secrets_before_push.py", event)
        self.assertEqual(decision(proc), "deny")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestScannerCoverage -v`
Expected: FAIL — ambos retornam `None`.

- [ ] **Step 3: Implementar**

```python
def repo_root(cwd):
    """Top level of the working tree, so a push from a subdirectory still
    scans everything git is about to send."""
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    root = out.stdout.strip()
    return root or None


def tracked_files(root):
    """NUL-separated so filenames with accents or spaces survive. The default
    core.quotePath=true returns octal escapes that open() cannot resolve."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                             capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    names = out.stdout.split(b"\0")
    return [n.decode("utf-8", "surrogateescape") for n in names if n]
```

E em `main()`, trocar `cwd = event.get("cwd") or os.getcwd()` por:

```python
    cwd = event.get("cwd") or os.getcwd()
    root = repo_root(cwd) or cwd
```

usando `root` em todo o resto da função.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 tests/test_hooks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/scan_secrets_before_push.py tests/test_hooks.py
git commit -m "fix(rule6): scan from the repo root and survive non-ASCII names"
```

---

### Task 8: Scanner — histórico e o `.env` não rastreado

O furo mais consequente: a skill manda pôr a chave num `.env` gitignorado, e `git ls-files` por definição não lista arquivo ignorado.

**Files:**
- Modify: `hooks/scan_secrets_before_push.py`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Produces: `unpushed_diff(root) -> str`, `env_files_on_disk(root) -> list[str]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
class TestScannerHistoryAndEnv(TempProject):
    SECRET = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'

    def test_secret_living_only_in_history_is_caught(self):
        subprocess.run(["git", "-C", self.root, "init", "-q"],
                       check=True, capture_output=True)
        leak = Path(self.root) / "leak.py"
        leak.write_text(self.SECRET)
        self._commit("oops")
        leak.write_text('AWS_KEY = os.environ["AWS_KEY"]\n')
        self._commit("cleanup")
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="git push origin main"))
        self.assertEqual(decision(proc), "deny")

    def test_gitignored_env_blocks_a_non_git_deploy(self):
        subprocess.run(["git", "-C", self.root, "init", "-q"],
                       check=True, capture_output=True)
        (Path(self.root) / ".gitignore").write_text(".env\n")
        (Path(self.root) / ".env").write_text(
            'STRIPE_SECRET_KEY="sk_live_abcdefghijklmnop123456"\n')
        (Path(self.root) / "index.js").write_text("x\n")
        self._commit("init")
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="vercel --prod"))
        self.assertEqual(decision(proc), "deny")

    def test_gitignored_env_does_not_block_git_push(self):
        """git does not send ignored files, so pushing is fine."""
        subprocess.run(["git", "-C", self.root, "init", "-q"],
                       check=True, capture_output=True)
        (Path(self.root) / ".gitignore").write_text(".env\n")
        (Path(self.root) / ".env").write_text('KEY="sk_live_abcdefghij123456"\n')
        (Path(self.root) / "index.js").write_text("x\n")
        self._commit("init")
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="git push origin main"))
        self.assertIsNone(decision(proc))

    def _commit(self, message):
        subprocess.run(["git", "-C", self.root, "add", "-A"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", self.root, "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", message],
                       check=True, capture_output=True)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestScannerHistoryAndEnv -v`
Expected: FAIL nos dois primeiros; o terceiro já passa e serve de guarda contra falso positivo.

- [ ] **Step 3: Implementar**

```python
GIT_PUBLISH_RE = re.compile(r"\bgit\b[^|;&]*\bpush\b")


def unpushed_diff(root):
    """What git is about to send. Falls back to the last 50 commits when there
    is no upstream, because that is a first push."""
    for args in (["log", "-p", "--no-color", "@{upstream}..HEAD"],
                 ["log", "-p", "--no-color", "-n", "50"]):
        try:
            out = subprocess.run(["git"] + args, cwd=root,
                                 capture_output=True, text=True,
                                 errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError):
            return ""
        if out.returncode == 0:
            return out.stdout
    return ""


def env_files_on_disk(root):
    """Gitignored .env files. Invisible to git ls-files, but vercel, netlify,
    docker build, scp and rsync all upload them."""
    found = []
    for entry in os.listdir(root):
        if entry == ".env" or (entry.startswith(".env.")
                               and not entry.endswith((".example", ".sample"))):
            found.append(entry)
    return found
```

Em `main()`, depois de resolver `root`:

```python
    findings = []
    is_git_push = bool(GIT_PUBLISH_RE.search(command))

    # A gitignored .env is not sent by git, but every other publishing path
    # uploads the whole directory.
    if not is_git_push:
        for name in env_files_on_disk(root):
            findings.append(name + ": local .env would be uploaded by this command")

    history = unpushed_diff(root)
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(history):
            findings.append("git history (unpushed commits): " + label)
            break
```

mantendo a varredura de arquivos rastreados já existente.

- [ ] **Step 4: Medir o custo no pior caso** (Review Focus #5)

```bash
python3 - <<'PY'
import os, subprocess, tempfile, time, json, sys
root = tempfile.mkdtemp()
subprocess.run(["git","-C",root,"init","-q"], check=True)
for i in range(40):
    os.makedirs(f"{root}/assets", exist_ok=True)
    open(f"{root}/assets/img{i}.bin","wb").write(os.urandom(900_000))
subprocess.run(["git","-C",root,"add","-A"], check=True, capture_output=True)
subprocess.run(["git","-C",root,"-c","user.email=t@t","-c","user.name=t",
                "commit","-qm","x"], check=True, capture_output=True)
event = json.dumps({"cwd": root, "tool_name": "Bash",
                    "tool_input": {"command": "git push origin main"}})
start = time.time()
subprocess.run([sys.executable, "hooks/scan_secrets_before_push.py"],
               input=event, capture_output=True, text=True)
print(f"decorrido: {time.time()-start:.1f}s (limite do hook: 60s)")
PY
```

Expected: bem abaixo de 60s. Se passar de 10s, acrescentar `SKIP_EXT` com as extensões binárias de `IGNORED_EXT` antes de ler o arquivo.

- [ ] **Step 5: Rodar a suíte e commitar**

Run: `python3 tests/test_hooks.py -v`
Expected: PASS.

```bash
git add hooks/scan_secrets_before_push.py tests/test_hooks.py
git commit -m "fix(rule6): scan unpushed history and gitignored .env on deploys"
```

---

### Task 9: Scanner — o que conta como publicar

**Files:**
- Modify: `hooks/scan_secrets_before_push.py`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Produces: `PUBLISH_RE` ampliado.

- [ ] **Step 1: Escrever o teste tabular que falha**

```python
class TestPublishDetection(TempProject):
    PUBLISHES = [
        "git push origin main", "git -C . push origin main",
        "git --git-dir=.git --work-tree=. push",
        "git -c user.name=x push --force-with-lease",
        "gh repo create x --public", "gh pr create", "gh gist create leak.py",
        "gh repo edit --visibility public",
        "npm publish", "pnpm publish", "yarn publish", "bun publish",
        "poetry publish", "cargo publish", "twine upload dist/*",
        "docker push myreg/app:v1", "vercel --prod", "netlify deploy --prod",
        "firebase deploy", "flyctl deploy", "npx wrangler deploy",
        "scp -r . user@host:/srv", "rsync -av . user@host:/srv",
        "aws s3 sync . s3://bucket",
        "cd app && git push",
    ]
    IGNORES = [
        "ls -la", "git status", "git commit -m 'x'", "git log --oneline",
        "npm install", "npm run build", "docker build -t x .",
        "vercel dev", "git add -A",
    ]

    def _repo_with_secret(self):
        subprocess.run(["git", "-C", self.root, "init", "-q"],
                       check=True, capture_output=True)
        (Path(self.root) / "leak.py").write_text(
            'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        subprocess.run(["git", "-C", self.root, "add", "-A"],
                       check=True, capture_output=True)

    def test_every_publishing_command_is_intercepted(self):
        self._repo_with_secret()
        missed = [c for c in self.PUBLISHES
                  if decision(run_hook("scan_secrets_before_push.py",
                                       self.event("Bash", command=c))) != "deny"]
        self.assertEqual(missed, [], "comandos não interceptados: " + str(missed))

    def test_ordinary_commands_are_left_alone(self):
        self._repo_with_secret()
        blocked = [c for c in self.IGNORES
                   if decision(run_hook("scan_secrets_before_push.py",
                                        self.event("Bash", command=c))) is not None]
        self.assertEqual(blocked, [], "falsos positivos: " + str(blocked))
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestPublishDetection -v`
Expected: FAIL listando ~18 comandos não interceptados.

- [ ] **Step 3: Implementar**

```python
PUBLISH_RE = re.compile(r"""(?xi)
      \bgit\b [^|;&]*? \bpush\b
    | \bgh\s+(?: repo\s+(?:create|edit)
               | release\b
               | pr\s+create
               | gist\s+create )
    | \b(?:npm|pnpm|yarn|bun|poetry|cargo|flit)\s+publish\b
    | \btwine\s+upload\b
    | \bdocker\s+push\b
    | \b(?:vercel|netlify|firebase|flyctl|fly|surge|amplify)\b (?=[^|;&]*(?:deploy|publish|--prod))
    | \bwrangler\s+(?:deploy|publish)\b
    | \b(?:scp|rsync)\s
    | \baws\s+s3\s+(?:cp|sync)\b
""")
```

`\bgit\b [^|;&]*? \bpush\b` cobre `git -C`, `--git-dir` e `-c k=v` sem atravessar um separador de comando, então `git status && ls push` não dispara falso positivo.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 tests/test_hooks.py -k TestPublishDetection -v`
Expected: PASS nos dois testes.

- [ ] **Step 5: Commit**

```bash
git add hooks/scan_secrets_before_push.py tests/test_hooks.py
git commit -m "fix(rule6): detect npm/vercel/docker/scp publishing and git global flags"
```

---

### Task 10: Scanner — allowlist e saída do beco

Hoje o scanner bloqueia o push do próprio repositório (`tests/test_hooks.py` contém `AKIAIOSFODNN7EXAMPLE`) e não há escapatória documentada.

**Files:**
- Modify: `hooks/scan_secrets_before_push.py`, `assets/config.example.json`, `hooks/README.md`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Produces: `secrets.allowlist_paths: list[str]`, `secrets.allow_patterns: list[str]`, e o pragma `cfi:allow-secret`.

- [ ] **Step 1: Escrever os testes que falham**

```python
class TestSecretAllowlist(TempProject):
    def _repo(self, rel, content):
        subprocess.run(["git", "-C", self.root, "init", "-q"],
                       check=True, capture_output=True)
        target = Path(self.root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        subprocess.run(["git", "-C", self.root, "add", "-A"],
                       check=True, capture_output=True)

    def test_allowlisted_path_is_skipped(self):
        self._repo("tests/test_hooks.py", 'K = "AKIAIOSFODNN7EXAMPLE"\n')
        self.write_config({"secrets": {"allowlist_paths": ["tests/**"]}})
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="git push origin main"))
        self.assertIsNone(decision(proc))

    def test_inline_pragma_exempts_the_line(self):
        self._repo("fixtures.py",
                   'K = "AKIAIOSFODNN7EXAMPLE"  # cfi:allow-secret\n')
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="git push origin main"))
        self.assertIsNone(decision(proc))

    def test_allowlist_does_not_hide_a_real_secret_elsewhere(self):
        self._repo("tests/test_hooks.py", 'K = "AKIAIOSFODNN7EXAMPLE"\n')
        (Path(self.root) / "app.py").write_text('K = "AKIAIOSFODNN7EXAMPLE"\n')
        subprocess.run(["git", "-C", self.root, "add", "-A"],
                       check=True, capture_output=True)
        self.write_config({"secrets": {"allowlist_paths": ["tests/**"]}})
        proc = run_hook("scan_secrets_before_push.py",
                        self.event("Bash", command="git push origin main"))
        self.assertEqual(decision(proc), "deny")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestSecretAllowlist -v`
Expected: FAIL nos dois primeiros.

- [ ] **Step 3: Implementar**

```python
ALLOW_PRAGMA = "cfi:allow-secret"


def scan_text(text, label_prefix, allow_patterns):
    """Findings in `text`, skipping lines carrying the pragma or matching an
    operator-supplied allow pattern."""
    hits = []
    for line in text.splitlines():
        if ALLOW_PRAGMA in line:
            continue
        if any(p.search(line) for p in allow_patterns):
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append(label_prefix + label)
                break
        if hits:
            break
    return hits
```

Em `main()`, ler a seção nova e filtrar:

```python
    secrets_cfg = cfi.section(cfi.load_config(root) or {}, "secrets")
    allowed_paths = cfi.str_list(secrets_cfg.get("allowlist_paths"))
    allow_patterns = []
    for raw in cfi.str_list(secrets_cfg.get("allow_patterns")):
        try:
            allow_patterns.append(re.compile(raw))
        except re.error:
            continue
```

e, no laço de arquivos, `if cfi.matches_any(rel, allowed_paths): continue`.

- [ ] **Step 4: Documentar a saída na mensagem de bloqueio**

Acrescentar ao `permissionDecisionReason`:

```
If this is a test fixture or a documented example, add its path to
`secrets.allowlist_paths` in .claude-for-idiots/config.json, or put
`# cfi:allow-secret` on the line. Never do this for a live credential.
```

- [ ] **Step 5: Acrescentar a seção ao `config.example.json`**

```json
  "secrets": {
    "allowlist_paths": ["tests/fixtures/**"],
    "allow_patterns": ["AKIAIOSFODNN7EXAMPLE"]
  },
```

- [ ] **Step 6: Verificar que o próprio repo já pode ser publicado**

Run: `echo "{\"cwd\":\"$PWD\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"git push origin main\"}}" | python3 hooks/scan_secrets_before_push.py`
Expected: saída vazia, depois de acrescentar `# cfi:allow-secret` às linhas de fixture em `tests/test_hooks.py`.

- [ ] **Step 7: Commit**

```bash
git add hooks/ tests/test_hooks.py assets/config.example.json hooks/README.md
git commit -m "feat(rule6): add allowlist and inline pragma so the scan has an exit"
```

---

### Task 11: Regra 1 — padrões ancorados e comandos que rodam

**Files:**
- Modify: `assets/config.example.json`, `references/rules.md:19-21`
- Test: `tests/test_hooks.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
class TestMigrationPatterns(TempProject):
    CONFIG = {"migrations": {
        "tool": "prisma",
        "command": "npx prisma migrate dev --name describe_change",
        "protected_paths": ["prisma/migrations/**", "alembic/versions/**",
                            "**/migrations/[0-9]*", "**/migrations/*.sql"]}}

    BLOCK = ["prisma/migrations/20260101_init/migration.sql",
             "alembic/versions/abc123_init.py",
             "app/migrations/0001_initial.py",
             "migrations/0002_add_user.py"]
    ALLOW = ["src/lib/migrations/runner.ts",
             "src/features/migrations/MigrationBanner.tsx",
             "docs/migrations/guide.md",
             "tests/migrations/test_runner.py"]

    def test_real_migrations_are_blocked(self):
        self.write_config(self.CONFIG)
        for rel in self.BLOCK:
            proc = run_hook("block_migration_edits.py", self.event(
                "Edit", file_path=os.path.join(self.root, rel)))
            self.assertEqual(decision(proc), "deny", rel)

    def test_application_code_named_migrations_is_allowed(self):
        self.write_config(self.CONFIG)
        for rel in self.ALLOW:
            proc = run_hook("block_migration_edits.py", self.event(
                "Edit", file_path=os.path.join(self.root, rel)))
            self.assertIsNone(decision(proc), rel)

    def test_the_suggested_command_is_valid_shell(self):
        self.write_config(self.CONFIG)
        proc = run_hook("block_migration_edits.py", self.event(
            "Edit", file_path=os.path.join(self.root, self.BLOCK[0])))
        reason = json.loads(proc.stdout)["hookSpecificOutput"][
            "permissionDecisionReason"]
        command = reason.split("run: ")[1].split("\n")[0]
        check = subprocess.run(["bash", "-n", "-c", command],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 tests/test_hooks.py -k TestMigrationPatterns -v`
Expected: FAIL — `src/lib/migrations/runner.ts` bloqueado e `bash -n` recusando `<describe_change>`.

- [ ] **Step 3: Corrigir `assets/config.example.json`**

```json
  "migrations": {
    "tool": "prisma",
    "command": "npx prisma migrate dev --name describe_change",
    "protected_paths": [
      "prisma/migrations/**",
      "alembic/versions/**",
      "**/migrations/[0-9]*",
      "**/migrations/*.sql"
    ]
  },
```

Duas correções num só lugar: `<describe_change>` era redirecionamento de shell (`bash: erro de sintaxe próximo ao token 'newline'`), e o catch-all `**/migrations/**` bloqueava código de aplicação e documentação.

- [ ] **Step 4: Completar os comandos em `references/rules.md`**

```markdown
   - Alembic: `alembic revision --autogenerate -m "describe change" && alembic upgrade head`
   - Prisma: `npx prisma migrate dev --name describe_change` (already applies it)
   - Django: `python manage.py makemigrations && python manage.py migrate`
```

Acrescentar: *Gerar a migration não altera o banco. Sem o passo de `upgrade`/`migrate`, o schema continua o antigo e o erro aparece só na próxima query.*

- [ ] **Step 5: Rodar e commitar**

Run: `python3 tests/test_hooks.py -v`
Expected: PASS.

```bash
git add assets/config.example.json references/rules.md tests/test_hooks.py
git commit -m "fix(rule1): anchor migration globs and make the suggested command runnable"
```

---

### Task 12: CI que teria pego tudo isso

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `pyproject.toml`
- Modify: `references/quality-tools.md`

- [ ] **Step 1: Escrever o guard de consistência que falha**

```python
# tests/test_repo_consistency.py
import glob
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestRepoConsistency(unittest.TestCase):
    def test_every_asset_json_parses(self):
        for path in glob.glob(str(ROOT / "assets" / "*.json")):
            with open(path, encoding="utf-8") as handle:
                json.load(handle)

    def test_version_has_a_changelog_entry(self):
        version = (ROOT / "VERSION").read_text().strip()
        changelog = (ROOT / "CHANGELOG.md").read_text()
        self.assertIn("## [" + version + "]", changelog)

    def test_config_example_skill_version_matches(self):
        version = (ROOT / "VERSION").read_text().strip()
        config = json.loads((ROOT / "assets" / "config.example.json").read_text())
        self.assertEqual(config["skill_version"], version)

    def test_settings_template_references_shipped_hooks(self):
        settings = json.loads(
            (ROOT / "assets" / "settings.template.json").read_text())
        referenced = set(re.findall(r"hooks/(\w+\.py)", json.dumps(settings)))
        shipped = {p.name for p in (ROOT / "hooks").glob("*.py")}
        self.assertTrue(referenced <= shipped,
                        "settings aponta para hooks inexistentes: "
                        + str(referenced - shipped))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar**

Run: `python3 tests/test_repo_consistency.py`
Expected: PASS se `VERSION`, `CHANGELOG` e `skill_version` estiverem alinhados; FAIL apontando o desalinhamento, que é o ponto.

- [ ] **Step 3: Criar `pyproject.toml`**

```toml
[tool.ruff]
target-version = "py39"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "B", "UP", "SIM"]
```

- [ ] **Step 4: Reescrever o CI**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.9", "3.13"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: Compile hooks
        run: python -m compileall -q hooks
      - name: Hook contract tests
        run: python tests/test_hooks.py
      - name: Shared module tests
        run: python tests/test_common.py
      - name: Real-project fixtures
        run: python tests/test_real_projects.py
      - name: Repo consistency
        run: python tests/test_repo_consistency.py

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pipx install ruff
      - name: Lint the skill's own code
        run: ruff check hooks tests
```

A matriz de OS existe porque `relativize()` trata separador de Windows e o README anuncia suporte a Windows — esse código nunca foi executado em CI.

- [ ] **Step 5: Corrigir `references/quality-tools.md`**

Em "Setup duties", trocar o passo 1 e 2 por:

```markdown
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
```

- [ ] **Step 6: Rodar tudo localmente e commitar**

Run: `python3 tests/test_hooks.py && python3 tests/test_common.py && python3 tests/test_real_projects.py && python3 tests/test_repo_consistency.py`
Expected: PASS em todos.

```bash
git add .github/workflows/ci.yml pyproject.toml tests/test_repo_consistency.py \
        references/quality-tools.md
git commit -m "ci: matrix across OS and Python, asset validation, lint our own code"
```

---

### Task 13: Fechar a versão

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`, `assets/config.example.json`
- Modify: `README.md`, `README.pt-br.md` (seção "Known limitations")

- [ ] **Step 1: Bump da versão**

```bash
echo "0.4.0" > VERSION
```

Atualizar `skill_version` em `assets/config.example.json` para `"0.4.0"`.

- [ ] **Step 2: Escrever a entrada do CHANGELOG**

```markdown
## [0.4.0] — 2026-09-23
### Fixed
- **Rule 6 was blind in four ways.** The scanner skipped files with non-ASCII
  names (`git ls-files` returns octal escapes), read only the working tree
  while `git push` sends history, saw nothing above the current directory, and
  recognised only `git push` — `npm publish`, `vercel --prod`, `docker push`,
  `scp` and `gh gist create` all went through. A gitignored `.env` — the file
  the skill itself tells you to create — was invisible to the scan while every
  non-git deploy uploads it.
- **Rule 5 denied the projects the catalog recommends.** 42 of 63 files from
  real Next.js, FastAPI, Flutter, NestJS and Astro trees were blocked: a
  default `create-next-app` (no `--src-dir`) had its whole `app/` directory
  refused, and Flutter's official `integration_test/` was denied, contradicting
  Rule 2. The `enforce` key defaulted to `off`, so a config written without it
  disabled the rule silently.
- **`fnmatch` never supported `**`.** `src/**` did not match `next.config.ts`
  and `**/migrations/**` did not match a root-level `migrations/`. Replaced
  with a real glob matcher in the new shared module.
- **Rule 5 was an undocumented extension allow-list.** `.mjs`, `.cjs`, `.mts`,
  `.astro`, `.sql` and `.sh` were never policed — `hack.ts` was blocked while
  `hack.mjs` beside it was not. Now policed by exclusion.
- **The command Rule 1 told you to run did not run.** `--name <describe_change>`
  is shell redirection: `syntax error near unexpected token 'newline'`. The
  Alembic and Django commands were also missing their `upgrade`/`migrate` half,
  so the schema silently stayed on the old version.
- A malformed `config.json` (`{"architecture": "layered"}`) crashed the hook
  with `AttributeError` and exit 1, breaking the documented fail-open contract.

### Added
- `hooks/_cfi_common.py` — one implementation of glob matching, path
  normalisation, config reading and the decision protocol, shared by all hooks.
- `tests/fixtures/` — real project trees for five stacks, with the contract
  that no legitimate file may be blocked. This is what the previous suite
  lacked, and why these bugs survived.
- `secrets.allowlist_paths`, `secrets.allow_patterns` and the
  `# cfi:allow-secret` pragma — the scan finally has a documented exit.
- CI across Ubuntu/macOS/Windows and Python 3.9/3.13, asset JSON validation,
  `VERSION` × `CHANGELOG` consistency, and ruff on the skill's own code.

### Changed
- The hooks are now described as a **safety net, not a guarantee**. The old
  wording ("guarantees, not just promises", "make that impossible") promised
  absolute enforcement to beginners who had no way to verify it.
- `architecture.enforce` now defaults to `ask` instead of `off`.
```

- [ ] **Step 3: Atualizar as limitações conhecidas dos READMEs**

Remover os itens agora corrigidos (nome com acento, comandos de publicação) e manter os que seguem verdadeiros: escrita via Bash não interceptada, e o scan não cobrir histórico já enviado. Acrescentar: *o enforcement de arquitetura é por extensão e por glob; arquivo sem extensão (`Dockerfile`, `Makefile`) não é policiado.*

- [ ] **Step 4: Verificação final**

Run: `python3 tests/test_hooks.py && python3 tests/test_common.py && python3 tests/test_real_projects.py && python3 tests/test_repo_consistency.py && ruff check hooks tests`
Expected: PASS em tudo.

- [ ] **Step 5: Commit**

```bash
git add VERSION CHANGELOG.md assets/config.example.json README.md README.pt-br.md
git commit -m "chore: release 0.4.0 — hook reliability"
```

---

## Plano 2 (fora deste documento)

Bloco D — fluxo e `SKILL.md`. São mudanças de prosa instrucional, com forma de verificação diferente (simulação de fluxo, não teste unitário), e por isso merecem plano próprio:

- **D1** — escrever `config.json` por último no Step 3, e trocar o teste "já configurado" por checagem de completude. *A correção de maior retorno de todo o inventário: é uma linha movida, e não pede nada do modelo.*
- **D2** — `git -C <install> status --porcelain` antes do pull; parar em vez de "resolver".
- **D3** — `.bak` antes de cada um dos quatro merges.
- **D4** — install por `cp` deixa resíduo; mover o diretório antigo em vez de copiar por cima.
- **D5** — seção `## Fatos não verificados` no `CLAUDE.template.md`.
- **D6** — detectar a raiz antes de escrever `.claude/settings.json`.
- **D7** — campo de config para a resposta da Q7 (browser).
- **D8** — reescrever a Rule 9 em torno do evento observável, não de um contador.
- **F3** — seções de arquitetura faltantes (Astro, Tauri/Electron) e a nota de realtime órfã.
