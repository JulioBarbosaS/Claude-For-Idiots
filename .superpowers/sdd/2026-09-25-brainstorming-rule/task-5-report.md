# Task 5 report — the feature-alignment hook (Rule 10)

**Status:** done, committed.

**Hashes:**
- `31942d9` — `refactor(hooks): share is_policed + load_json_file via _cfi_common` (prep, verified behavior-identical for Rule 5 before touching the new hook)
- `eb2511f` — `feat(rule10): add the feature-alignment hook` (TDD: 35 new tests in `tests/test_hooks.py`, then `hooks/require_feature_alignment.py`)
- `1039bc7` — `docs(rule10): document the alignment hook; pin shared-module contracts` (`SKILL.md`, `hooks/README.md`, 15 new tests in `tests/test_common.py`)

**Tests:** all four suites green — `test_common.py` 53/53, `test_hooks.py` 128/128, `test_real_projects.py` 1/1, `test_repo_consistency.py` 8/8 (190/190 total). `test_settings_template_references_shipped_hooks` — the one known-failing test before this task, because `require_feature_alignment.py` didn't exist yet — now passes.

## Base check

HEAD started at `9685e6c` (wrong — a stale merge-commit tip), not the branch tip. Reset to `plan/brainstorming-0.5.0` (`c4c218c`) before touching anything, per the task instructions.

## What changed

1. **`hooks/_cfi_common.py`** — generalized `load_config(cwd)` into a thin wrapper over a new `load_json_file(path)` (same bounded-size/bounded-nesting/fail-open contract, now reusable for the alignment record's own path, not just `config.json`). Moved `IGNORED_EXT`, `_normalize_ext`, `_is_dotenv`, `is_policed` here from `enforce_architecture.py`, generalizing `is_policed(rel, arch)` to `is_policed(rel, ignored_override=None)` so it no longer assumes an "architecture" config shape. Verified behavior-identical for Rule 5 (`test_common.py` 38/38, `test_hooks.py` 93/93 unchanged) before writing a single line of the new hook.
2. **`hooks/enforce_architecture.py`** — now calls `cfi.is_policed(rel, arch.get("ignored_extensions"))` instead of a local copy of the same logic. No behavior change.
3. **`hooks/require_feature_alignment.py`** (new) — Rule 10's hook.
4. **`tests/test_hooks.py`** — 35 new tests (`TestRequireFeatureAlignment`, `TestRequireFeatureAlignmentFailsOpen`, `TestBothWriteHooksAreConsulted`, `TestRequireFeatureAlignmentPerformance`, plus 2 more in `TestMainNeverExitsNonZero`).
5. **`tests/test_common.py`** — 15 new tests (`TestLoadJsonFile`, `TestIsPoliced`) pinning the shared functions directly, not just through hook subprocess tests.
6. **`SKILL.md`** — Step 3 item 3: "copy the four files" → "copy the five files" (four hooks + `_cfi_common.py`).
7. **`hooks/README.md`** — fourth hook added to the table and intro line; `brainstorm.enforce` noted next to `architecture.enforce` (missing-section-means-off called out explicitly); three new "Known gaps" entries (can't read the prompt, never polices edits, exempts test files unconditionally by convention).

## The enforce convention — implemented as corrected, not as first drafted

The plan document itself is internally inconsistent: its own Task 5 Step 1 case list says `ASK enforce com valor inválido`, but Review Focus #8 explicitly says this is wrong and corrects it to `off`/allow, measured against Rule 5's real code. The orchestrator's briefing restated the corrected version as authoritative. Implemented as corrected:

```python
mode = brainstorm.get("enforce", "ask")
if mode not in ("deny", "ask"):
    cfi.allow()   # "off", any typo, or any other type -> off, fail-open
```

Tested with `["DENY", "Ask", True, False, None, 42, [], {}]` — all allow, none ask.

## Case table (Task 5 Step 1 minimum + transversals + property tests)

| Case | Result | Test |
|---|---|---|
| Arquivo já existe (edição) | ALLOW | `test_allows_editing_an_existing_file` |
| Arquivo novo não-código (.md, .env.example, Dockerfile, .json, .svg) | ALLOW | `test_allows_new_non_code_files` |
| Arquivo novo de teste (11 convenções de stack) | ALLOW | `test_allows_new_test_files_across_stack_conventions` |
| Arquivo comum terminado em "test"/"contest"/"latest" (propriedade: token deve ter separador) | DENY (não confundido com teste) | `test_does_not_treat_ordinary_files_ending_in_test_as_tests` |
| Registro presente, `head` == HEAD atual | ALLOW | `test_allows_new_code_when_record_head_matches_current_head` |
| Registro `skipped: true`, `head` == HEAD atual | ALLOW | `test_allows_new_code_when_skipped_record_head_matches_current_head` |
| `enforce: off` | ALLOW | `test_allows_when_enforce_is_off` |
| Seção `brainstorm` ausente | ALLOW (off, compat 0.4.0) | `test_allows_when_brainstorm_section_is_absent` |
| Seção `brainstorm` de tipo errado (`"ask"`, lista, int, bool, null) | ALLOW (off) | `test_allows_when_brainstorm_section_has_the_wrong_type` |
| Fora do projeto / cwd inexistente | ALLOW | `test_fails_open_on_path_outside_the_project`, `test_fails_open_when_cwd_does_not_exist` |
| Registro malformado (`{}`, `[]`, string, JSON inválido, aninhamento 5000 níveis, `null`, `42`) × (ask, deny) | ALLOW | `test_allows_malformed_record_regardless_of_enforce_mode` |
| Registro com `head` presente mas não-string (`None`, int, lista, dict) | ALLOW | `test_allows_record_with_head_present_but_not_a_string` |
| Projeto sem git, registro presente | ALLOW | `test_allows_when_project_has_no_git_and_a_record_is_present` |
| Projeto sem git, sem registro | ASK (git ausente não é passe livre por si só) | `test_asks_when_project_has_no_git_and_no_record_at_all` |
| Arquivo novo de código, sem registro, `enforce: ask` (padrão) | ASK | `test_asks_new_code_with_no_record_and_enforce_ask` |
| Seção presente, `enforce` ausente (padrão) | ASK | `test_asks_by_default_when_section_present_but_enforce_is_absent` |
| `enforce` valor inválido (`"DENY"`, `true`, `null`, `42`, `[]`, `{}`) | ALLOW (off) — corrigido, não ASK | `test_allows_when_enforce_value_is_invalid` |
| Registro velho (HEAD mudou) | ASK | `test_asks_when_record_head_is_stale` |
| Registro `skipped: true` velho (HEAD mudou) | DENY (mode=deny) | `test_denies_when_skipped_record_head_is_stale` — prova que skip não perdoa a próxima feature |
| Arquivo novo de código, sem registro, `enforce: deny` | DENY | `test_denies_new_code_with_no_record_and_enforce_deny` |
| Caminho não-ASCII (`src/configuração.py`, `src/são-paulo/novo.py`) | mesma decisão que o equivalente ASCII | `test_non_ascii_path_gets_the_same_decision_as_the_ascii_equivalent`, `test_non_ascii_path_inside_architecture_style_allowed_dir_still_asks` |
| `record` customizado via config | lido corretamente | `test_custom_record_path_from_config_is_read` |
| stdin: `42`/`null`/`[1,2,3]`/`"str"`/lixo/JSON com 5000 níveis | exit 0, sem saída | `TestRequireFeatureAlignmentFailsOpen` (6 testes) |
| Campos não-string em `tool_input`/`cwd` (int, null, lista) | exit 0, sem Traceback | `test_fails_open_on_non_string_tool_input_fields` |
| Exceção forçada em `cfi.read_event` / `cfi.load_config` | exit 0, sem Traceback | `TestMainNeverExitsNonZero` (2 novos testes) |
| Mensagem de ASK diz o que fazer, não manda editar JSON | confirmado | `test_ask_message_tells_the_user_how_to_proceed_not_to_edit_json` |

## Medição de custo

Script em `/tmp/.../scratchpad/measure_cost.py`, 30 execuções do caminho completo (config + registro fresco + `git rev-parse` real) e 10 execuções de cada caminho de saída rápida:

```
full path (config+record+git, fresh, -> allow): N=30
  min=24.1ms  median=25.9ms  max=30.6ms  mean=26.3ms
hook timeout budget: 60000ms

no_config_file:              mean=21.7ms over 10 runs (no git subprocess reached)
brainstorm_section_absent:   mean=22.9ms over 10 runs (no git subprocess reached)
```

~24–31ms end to end, dominado pelo custo de iniciar o interpretador Python (o caminho sem git é quase igual ao caminho com git — a chamada `git rev-parse` em si soma poucos ms). Isso é ~0.05% do teto de 60s do hook; não há risco de timeout em nenhum cenário real.

## Prova de que os dois hooks de `Write` rodam

`assets/settings.template.json` já registrava ambos no mesmo grupo `Write` (feito na Tarefa 4, antes desta). Dois testes provam isso na prática:

- `test_settings_template_registers_both_under_the_write_matcher` — confirma que `settings.template.json` tem um único grupo `Write` contendo os comandos dos dois hooks.
- `test_both_hooks_independently_flag_the_same_new_file` — roda `enforce_architecture.py` e `require_feature_alignment.py` como subprocessos separados contra o **mesmo evento** (arquivo novo, fora de `allowed_paths` **e** sem alinhamento, ambos configurados com `enforce: deny`) e confirma que **os dois** retornam `"deny"` — nenhum dos dois fica em silêncio por causa do outro. Claude Code roda todos os hooks casados por um matcher; este teste prova que nada em nenhum dos dois scripts pressupõe ser o único hook do grupo.

## Decisões de design que vale registrar

- **`is_policed` movido para `_cfi_common.py`**, generalizado de `is_policed(rel, arch)` para `is_policed(rel, ignored_override=None)`. Rule 5 chama com `arch.get("ignored_extensions")`; Rule 10 chama sem override (não há campo equivalente em `brainstorm` — não foi inventado um, já que o plano não pede). Comportamento da Regra 5 confirmado idêntico antes de escrever qualquer linha do hook novo.
- **`load_config` virou wrapper fino de `load_json_file`** — mesmo contrato, mesmo limite de tamanho/aninhamento, mesmo fail-open. `require_feature_alignment.py` usa `load_json_file` para ler o registro em um caminho configurável (`brainstorm.record`, default `.claude-for-idiots/current-feature.json`), sem duplicar a lógica de parsing defensivo.
- **Registro malformado sempre ALLOW, independente de `enforce`** — distinto de "registro ausente" (que segue para ask/deny). Um arquivo presente mas ilegível (`{}`, lista, string, JSON inválido, aninhamento profundo) nunca é evidência de que o usuário pulou o alinhamento; é ruído, e a filosofia do projeto ("falso positivo é defeito") pesa contra escalar em cima de dado que não se pode confiar.
- **`head` ausente ou não-string no registro → mesmo tratamento de malformado (ALLOW)** — um registro `{}` ou com `head: null` não pode provar frescor nem staleness, então não escala.
- **Git indisponível não é passe livre por si só** — só resgata um registro **já presente** (não se pode provar staleness sem HEAD atual). Sem registro e sem git, o `enforce` normal ainda se aplica (testado: `test_asks_when_project_has_no_git_and_no_record_at_all`).
- **`skipped: true` não perdoa a próxima feature** — testado explicitamente com um registro `skipped: true` mas com `head` velho: resultado é DENY, não ALLOW, confirmando o texto de `references/brainstorming.md` ("A record only counts as fresh for the HEAD it was written at — including a skipped one").
- **Detecção de "arquivo de teste"** é por convenção de caminho (diretórios `test/`, `tests/`, `__tests__/`, `spec/`, `specs/`, `e2e/`, `integration_test/`, `test_driver/`; nome de arquivo com token `test`/`spec` delimitado por separador). Deliberadamente **não** captura substring solta (`latest.py`, `contest.py` continuam policiados) — testado como propriedade, não como exemplo do plano.

## Preocupações

- A heurística de "é arquivo de teste?" é por convenção de nome/diretório, não por vínculo real com um arquivo de implementação — um arquivo novo que só *parece* teste (ex.: `src/attestation_test_utils.py`, se alguém usasse esse nome) passaria sem alinhamento. Documentado em `hooks/README.md` "Known gaps" como limitação deliberada, não bug.
- `hooks/README.md` linha 3 ainda diz o matcher de `block_migration_edits.py` como `Edit|Write|MultiEdit` (sem `NotebookEdit`), já estava desatualizado antes desta tarefa e é de outra regra — não mexi, fora do escopo da Tarefa 5.
- Não toquei na seção "The rules" de `SKILL.md` (ainda lista só 1–9) nem no `references/architecture-catalog.md` — isso é explicitamente Tarefa 6, não Tarefa 5.
