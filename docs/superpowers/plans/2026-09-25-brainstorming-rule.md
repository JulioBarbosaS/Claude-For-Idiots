# Plano de Implementação — Regra 10: alinhar antes de construir (v0.5.0)

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para rastreamento.

**Goal:** Quando o usuário pede uma feature que o projeto ainda não tem, o Claude para, apresenta as decisões escondidas como **opções para escolher**, e só escreve código depois do "sim". Hoje ele começa a codar em cima da primeira leitura que fizer do pedido.

**Architecture:** A regra nasce em `references/rules.md` (fonte da verdade) e é copiada para o `CLAUDE.md` gerado, como as outras nove. O *quando* e o *como perguntar* vivem em texto, porque dependem de interpretar linguagem — nenhum hook consegue fazer isso. O que o hook faz é diferente e menor: ele é a **rede**, e só pega o caso "o Claude começou a escrever código novo sem ter alinhado nada". A ponte entre os dois é um arquivo de registro, `.claude-for-idiots/current-feature.json`, que o Claude escreve quando o usuário aprova e o hook lê antes de deixar criar arquivo.

**Tech Stack:** Python 3.9+ (somente stdlib), `unittest`, GitHub Actions, git.

**Spec:** Não há documento de spec separado. As três decisões de produto foram tomadas pelo usuário em conversa e estão fixadas aqui:

1. **Força:** configurável por projeto — `off` | `ask` | `deny`. Padrão `ask` em projeto novo.
2. **Gatilho:** só pedido que cria comportamento que o projeto ainda não tem. Conserto de bug, ajuste visual e renomeação passam direto.
3. **Formato:** o Claude propõe as opções e o usuário escolhe. Não pergunta aberta.

---

## Global Constraints

Herdados da v0.4.0 e válidos aqui sem exceção:

- **Somente biblioteca padrão.** Nenhum `pip install` no hook. Ele roda na máquina do usuário final.
- **Piso de versão: Python 3.9.**
- **Fail-open é inviolável.** Qualquer entrada inesperada — stdin corrompido, registro malformado, `cwd` fora do projeto — resulta em `exit 0` sem saída. O hook nunca sai com código ≠ 0. Esta execução anterior encontrou **quatro** bugs dessa família (`RecursionError`, `TypeError` em campo não-string, duas variantes de `re.error`); o hook novo entra na varredura de `tests/test_repo_consistency.py` que trava isso.
- **Compatibilidade de config é aditiva.** Projeto em 0.4.0 continua funcionando sem migração.
- **Caminhos internos sempre POSIX.**
- **Toda mensagem de bloqueio contém a saída.** O público é iniciante: a mensagem diz o que fazer, e qualquer comando sugerido precisa rodar em shell de verdade.

Específicos deste plano:

- **Falso positivo é defeito, não zelo.** Um hook que trava trabalho legítimo é desinstalado, e aí não protege nada. Este hook policia **apenas arquivo novo de código** e nunca edição de arquivo existente.
- **O usuário sempre pode dizer "vai direto".** A recusa dele é registrada e respeitada. Regra que não pode ser dispensada vira regra que o usuário contorna desligando tudo.
- **O hook não decide o que é feature.** Ele não lê o prompt — `PreToolUse` só recebe a chamada de ferramenta. Quem classifica é o modelo, lendo o `CLAUDE.md`.

## Review Focus

Classes de entrada que este plano implica, que nenhuma tarefa exercitaria por padrão:

1. **Registro ausente em projeto legítimo** — usuário rodou `update` mas nunca alinhou nada. Precisa ser `off` por omissão, não bloqueio surpresa. → Tarefa 5.
2. **Registro velho de uma feature já entregue** — não pode autorizar a próxima feature em silêncio. → Tarefa 5, via `head`.
3. **Projeto sem git** (`vcs: none` no config) — a detecção de registro velho depende de `HEAD`. Precisa de caminho alternativo, fail-open. → Tarefa 5.
4. **Arquivo novo que não é código** — `README.md`, `.env.example`, `docs/*.md`, `Dockerfile`. Não pode disparar nada. Reusar `is_policed` da Regra 5, não reimplementar. → Tarefa 5.
5. **Arquivo novo que é teste** — `tests/test_x.py` durante TDD é o caminho normal da Regra 2. Se o hook bloquear, briga com a regra vizinha. → Tarefa 5, decisão explícita.
6. **Registro malformado** vindo de edição manual (`{}`, lista, string, JSON inválido, aninhamento profundo). → Tarefa 5.
7. **Caminho não-ASCII** (`src/configuração.py`) — público-alvo brasileiro. → Tarefa 5.
8. **`enforce` com valor inválido** (`"DENY"`, `true`, `null`, `42`) — cai em `off`/allow. Medido no código da Regra 5, que faz exatamente isso hoje (`mode not in ("deny","ask") -> cfi.allow()`). O plano afirmava o contrário; corrigido. A constituição do projeto manda entrada inesperada resultar em `exit 0` sem saída, e `ask` não é isso. → Tarefa 5.

---

## Inventário (o que este plano resolve)

**A.** O usuário escreve *"quero adicionar login com Google"*. O Claude escolhe sozinho se substitui o login atual, o que guarda do usuário, e onde põe o botão. Se errar, o usuário só descobre depois do código pronto — e a Regra 3 já fez o commit.

**B.** As decisões escondidas de uma feature não ficam registradas em lugar nenhum. A Regra 8 manda conhecimento caro para `docs/`, mas "por que o login convive com email/senha em vez de substituir" nunca chega lá.

**C.** A Regra 5 só avisa que um arquivo está fora da arquitetura **na hora de escrever**. Se o alinhamento declarasse os caminhos-alvo antes, o conflito apareceria enquanto ainda é barato mudar de ideia.

**D.** A Regra 7 (reusar antes de construir) manda buscar no código e no `docs/INDEX.md` antes de implementar. Hoje isso acontece — quando acontece — depois que o Claude já decidiu o desenho. A busca deveria alimentar as opções apresentadas, não vir depois delas.

---

## Estrutura de arquivos

```
references/
  rules.md                      # Regra 10 entra aqui (fonte da verdade)
  brainstorming.md              # NOVO — o roteiro completo
assets/
  CLAUDE.template.md            # Regra 10 na lista + como registrar
  config.example.json           # bloco "brainstorm"
  settings.template.json        # registra o quarto hook
  current-feature.example.json  # NOVO — forma do registro
hooks/
  require_feature_alignment.py  # NOVO — a rede
  _cfi_common.py                # reusado, não alterado
tests/
  test_hooks.py                 # casos do hook novo
  test_repo_consistency.py      # hook novo entra na varredura de fail-open
SKILL.md                        # Step 2.5 (o alinhamento) + Step 3 (escreve o config)
```

---

### Task 1: Escrever a Regra 10 na fonte da verdade

Primeiro porque todo o resto copia daqui. `references/rules.md` é a fonte única; `CLAUDE.template.md`, `SKILL.md` e os READMEs derivam dela.

**Files:**
- Modify: `references/rules.md` (nova seção após a Rule 9)
- Create: `references/brainstorming.md`

- [ ] **Step 1: Adicionar a Rule 10 em `references/rules.md`**

Seguir o formato das outras: título com `**[hook]**`, o que a regra exige, e por quê. O texto precisa dizer as três coisas decididas — quando dispara, que o formato é opção-para-escolher, e que o usuário pode dispensar.

Ponto obrigatório do texto: a regra **não** dispara em conserto de bug, ajuste visual ou renomeação. Dar os exemplos literais, porque a fronteira é o que o modelo erra:

```
dispara:      "quero login com Google" · "adiciona carrinho" · "exportar em PDF"
não dispara:  "arruma esse erro do console" · "muda a cor do botão" · "renomeia calcTotal"
```

- [ ] **Step 2: Criar `references/brainstorming.md`**

O roteiro que o `SKILL.md` e o `CLAUDE.md` apontam. Precisa cobrir:

**Como classificar.** Uma pergunta só: *o projeto já faz isso?* Se não faz, é feature nova. Se faz e está quebrado, é conserto. Dizer em uma linha ao usuário como classificou, para ele poder discordar — "isso me parece feature nova, vou alinhar antes de codar".

**O que buscar antes de perguntar** (é a Regra 7 acontecendo no momento certo): procurar no código algo reaproveitável, ler `docs/INDEX.md`, e checar `architecture.allowed_paths` para saber onde a feature caberia. A busca alimenta as opções.

**Como perguntar.** Opções para escolher, nunca pergunta aberta. Duas a quatro decisões, as que mudam o resultado. Cada opção com uma linha explicando a consequência — o usuário pode não saber o que é OAuth, mas sabe escolher entre "os dois convivem" e "Google substitui".

**Respeitar o modo de termos.** Os valores reais são `none` | `explain` | `raw` (ver a tabela em `SKILL.md`, seção "Technical-term modes"). Em `explain`, ler `.claude-for-idiots/glossary.json` antes, não repetir termo já explicado, e registrar os novos. Em `none`, parafrasear o jargão nas opções (é o modo mais difícil de fazer bem). Em `raw`, escrever direto.

**O que fazer com a resposta.** Escrever `.claude-for-idiots/current-feature.json` com as decisões, e só então implementar. Para feature grande, escrever também `docs/features/YYYY-MM-DD-<slug>.md` com uma linha em `docs/INDEX.md` (Regra 8) — é o inventário **B**.

**A saída.** Se o usuário disser "vai direto" / "não precisa perguntar", registrar com `skipped: true` e seguir. Não insistir.

- [ ] **Step 3: Verificar que a numeração não quebrou**

Run: `grep -nE "^## Rule [0-9]+" references/rules.md`
Expected: Rule 1 a Rule 10, em ordem, sem buraco.

- [ ] **Step 4: Commit**

```bash
git add references/rules.md references/brainstorming.md
git commit -m "docs(rule10): align on a feature before building it"
```

---

### Task 2: A forma do registro

Antes do hook, porque o hook lê este arquivo e os testes dele precisam de uma forma estável para montar cenário.

**Files:**
- Create: `assets/current-feature.example.json`
- Modify: `references/brainstorming.md` (seção descrevendo os campos)

- [ ] **Step 1: Definir os campos**

```json
{
  "slug": "login-google",
  "recorded_at": "2026-09-25T14:03:00Z",
  "head": "3db5115",
  "decisions": [
    "convive com o login de email/senha",
    "guarda email, nome e foto"
  ],
  "target_paths": ["src/auth/**", "tests/auth/**"],
  "doc": "docs/features/2026-09-25-login-google.md",
  "skipped": false
}
```

`head` é o `git rev-parse --short HEAD` no momento do registro. É o que resolve o **Review Focus 2**: enquanto o `HEAD` não se mover, o registro vale; quando a Regra 3 fizer o commit da feature, o `HEAD` muda e o registro fica velho sozinho. Nenhum passo de limpeza para o modelo esquecer.

`target_paths` é opcional e serve ao inventário **C**: se o alinhamento declarar onde a feature vai morar, dá para conferir contra `architecture.allowed_paths` **antes** de escrever, e avisar "isso ficaria fora da arquitetura" enquanto ainda é barato.

`skipped: true` é o registro do usuário ter dispensado. O hook trata como registro válido.

- [ ] **Step 2: Commit**

```bash
git add assets/current-feature.example.json references/brainstorming.md
git commit -m "docs(rule10): define the feature-alignment record"
```

---

### Task 3: A regra no `CLAUDE.md` gerado

É o que realmente faz a regra existir no dia a dia — o `SKILL.md` sai de contexto, o `CLAUDE.md` é lido toda sessão.

**Files:**
- Modify: `assets/CLAUDE.template.md` (lista de regras + seção "Knowledge & reuse")

- [ ] **Step 1: Adicionar o item 10 na lista de regras**

Curto. A Regra 8 do próprio projeto manda: ponteiro, não ensaio. Precisa caber em cinco ou seis linhas e conter os exemplos da fronteira, porque é essa parte que o modelo erra.

- [ ] **Step 2: Conectar com a seção "Knowledge & reuse" que já existe**

Ela já diz *"Before building a feature: search the codebase for something to reuse and skim `docs/INDEX.md` (Rule 7)"*. Reescrever para que a busca seja o **primeiro passo do alinhamento**, não um passo solto — é o inventário **D**.

- [ ] **Step 3: Verificar que o template não tem placeholder órfão**

Run: `grep -o "{{[A-Z_]*}}" assets/CLAUDE.template.md | sort -u`
Expected: só placeholders que o `SKILL.md` Step 3 sabe preencher.

- [ ] **Step 4: Commit**

```bash
git add assets/CLAUDE.template.md
git commit -m "feat(rule10): carry the alignment rule into generated CLAUDE.md"
```

---

### Task 4: Config e registro do hook

**Files:**
- Modify: `assets/config.example.json`
- Modify: `assets/settings.template.json`

- [ ] **Step 1: Bloco `brainstorm` no config de exemplo**

```json
"brainstorm": {
  "enforce": "ask",
  "record": ".claude-for-idiots/current-feature.json"
}
```

**Convenção completa de `enforce`** — medida no código da Regra 5, não suposta:

| entrada | resultado | por quê |
|---|---|---|
| seção `brainstorm` ausente | `off` | feature nova; projeto em 0.4.0 não pode ganhar prompt que nunca pediu. É a ÚNICA divergência deliberada da Regra 5, que usa `ask` para chave ausente |
| seção presente, `enforce` ausente | `ask` | o usuário optou por ter a seção |
| `"deny"` / `"ask"` / `"off"` | como nomeado | |
| qualquer outro valor | `off` | fail-open. É o que a Regra 5 faz hoje, verificado |

- [ ] **Step 2: Registrar o quarto hook**

Em `settings.template.json`, adicionar entrada `PreToolUse` com matcher `Write` apontando para `require_feature_alignment.py`.

Já existe um `Write` registrado (`enforce_architecture.py`). Os dois convivem: o Claude Code roda todos os hooks que casam com o matcher. **Confirmar isso na prática durante a Tarefa 5** — se o segundo hook não for executado, a tarefa não está pronta, e o teste precisa provar que os dois rodam.

- [ ] **Step 3: Commit**

```bash
git add assets/config.example.json assets/settings.template.json
git commit -m "feat(rule10): ship brainstorm config and register the hook"
```

---

### Task 5: O hook

A tarefa grande. Tudo que a v0.4.0 aprendeu se aplica aqui — leia `docs/superpowers/plans/2026-09-23-hooks-reliability.md` e o `progress.md` da execução antes de começar.

**Files:**
- Create: `hooks/require_feature_alignment.py`
- Modify: `tests/test_hooks.py`
- Modify: `SKILL.md` (Step 3 copia agora quatro hooks + `_cfi_common.py`)
- Modify: `hooks/README.md`

- [ ] **Step 1: Escrever os testes primeiro**

TDD: teste que falha, roda, falha de verdade, aí implementa. Testar a **propriedade**, não os exemplos deste plano.

Casos que decidem se o hook presta:

```
ALLOW  arquivo que JÁ EXISTE                      (edição, não é feature)
ALLOW  arquivo novo que não é código (.md, .json, Dockerfile, .env.example)
ALLOW  arquivo novo de teste                      (Regra 2, TDD é o caminho normal)
ALLOW  registro presente e HEAD igual ao gravado
ALLOW  registro com skipped: true                 (usuário dispensou)
ALLOW  enforce: off
ALLOW  seção brainstorm ausente                   (projeto 0.4.0, compatibilidade)
ALLOW  fora de repositório git / cwd inexistente  (fail-open)
ALLOW  registro malformado: {} · [] · "str" · JSON inválido · aninhamento fundo
ALLOW  projeto com vcs: none                      (sem HEAD para comparar)

ASK    arquivo novo de código, sem registro, enforce ask (padrão)
ASK    enforce com valor inválido: "DENY" · true · null · 42
ASK    registro velho (HEAD mudou desde o registro)

DENY   arquivo novo de código, sem registro, enforce deny
```

Mais os dois transversais, que a v0.4.0 mostrou serem os que realmente quebram:

```
exit 0 para stdin: 42 · null · [] · lixo não-JSON · JSON com 5000 níveis
caminho não-ASCII (src/configuração.py) tratado igual a ASCII
```

- [ ] **Step 2: Implementar**

Reusar `_cfi_common.py` — `read_event`, `load_config`, `section`, `relativize`, `allow`, e o protocolo de decisão. **Não reimplementar nada disso.**

Para "é código?", reusar a noção de `is_policed` de `enforce_architecture.py` (`IGNORED_EXT` + isenção de arquivo sem extensão). Se a lógica tiver que ser compartilhada, movê-la para `_cfi_common.py` e fazer os dois hooks consumirem — mas então a Regra 5 precisa continuar passando idêntica, e a suíte inteira precisa provar isso.

Ordem das checagens, da mais barata para a mais cara, e todas fail-open:

1. `enforce` é `off` ou seção ausente → allow
2. arquivo já existe → allow (mesma razão de `enforce_architecture.py`: é edição)
3. não é código policiado → allow
4. é arquivo de teste → allow
5. registro válido e fresco → allow
6. caso contrário → `ask` ou `deny` conforme `enforce`

Envolver `main()` em `try/except Exception: sys.exit(0)`, como os outros três.

- [ ] **Step 3: A mensagem**

O público é iniciante. A mensagem precisa dizer o que aconteceu e como sair — e o caminho de saída não pode ser "edite este JSON":

```
Regra 10: a feature ainda não foi alinhada.

Me diz o que você quer construir e eu apresento as decisões em opções
antes de escrever código. Se preferir seguir direto, é só dizer.
```

- [ ] **Step 4: Medir o custo**

Teto de hook é 60s. Este hook lê dois arquivos pequenos e roda um `git rev-parse` — deve ficar em milissegundos, mas **medir**, não supor. Incluir a medição no relatório.

- [ ] **Step 5: Provar que os dois hooks de `Write` rodam**

Teste de integração: projeto com `enforce_architecture` e `require_feature_alignment` registrados, arquivo novo fora da arquitetura **e** sem alinhamento. Os dois precisam ter sido consultados.

- [ ] **Step 6: Atualizar `SKILL.md` e `hooks/README.md`**

`SKILL.md` Step 3 item 3 diz "copy the four files" — vira cinco. `hooks/README.md` ganha a descrição do hook novo e o que ele **não** pega (seção "Known gaps" já existe): não pega edição de arquivo existente, não pega feature construída inteira dentro de arquivo que já existe.

- [ ] **Step 7: Rodar as quatro suítes**

```bash
python3 tests/test_common.py && python3 tests/test_hooks.py && \
python3 tests/test_real_projects.py && python3 tests/test_repo_consistency.py
```

- [ ] **Step 8: Commit**

```bash
git add hooks/require_feature_alignment.py tests/test_hooks.py SKILL.md hooks/README.md
git commit -m "feat(rule10): add the feature-alignment hook"
```

---

### Task 6: O fluxo no `SKILL.md`

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Apontar para `references/brainstorming.md`**

Na seção "The rules", adicionar a Regra 10 com o ponteiro. Manter curto — o `SKILL.md` já delega o detalhe para `references/`.

- [ ] **Step 2: Escrever o bloco `brainstorm` no Step 3**

O Step 3 lista o que vai para o `config.json`. Acrescentar `brainstorm.enforce`, com **padrão `ask` para projeto novo**.

- [ ] **Step 3: O caminho de update**

`/claude-for-idiots update` precisa tratar projeto vindo de 0.4.0: a seção `brainstorm` não existe, e por compatibilidade o hook lê isso como `off`. O update **pergunta** se o usuário quer ligar, explicando em uma frase o que muda, e escreve o valor escolhido. Nunca liga em silêncio.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit -m "feat(rule10): wire alignment into onboarding and update"
```

---

### Task 7: Travar a consistência

O CI da v0.4.0 existe para impedir que uma promessa volte a divergir do código. O hook novo precisa entrar nele.

**Files:**
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Hook novo entra na varredura de fail-open**

A varredura já é por glob em `hooks/` — confirmar que o hook novo entra sozinho. Se entrar, o teste passa sem alteração e isso precisa ser **demonstrado**, não suposto.

- [ ] **Step 2: Travar regra ↔ template**

Verificação nova: toda `## Rule N` em `references/rules.md` tem item correspondente na lista numerada de `assets/CLAUDE.template.md`. É a mesma classe de defeito que a divergência catálogo ↔ `STACKS`: duas cópias manuais que ninguém garante iguais.

- [ ] **Step 3: Travar hook ↔ settings**

Todo arquivo em `hooks/` que não começa com `_` aparece em `assets/settings.template.json`. Pega o caso "hook escrito e nunca registrado".

- [ ] **Step 4: Provar por mutação**

Para cada verificação nova: quebrar de propósito, mostrar a saída literal falhando, reverter com `git checkout --` (**não** com `cp` — é interativo neste ambiente e trava o script).

- [ ] **Step 5: Commit**

```bash
git add tests/test_repo_consistency.py
git commit -m "test: lock rule/template and hook/settings consistency"
```

---

### Task 8: Fechar a versão

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`, `README.md`, `README.pt-br.md`, `assets/config.example.json`

- [ ] **Step 1: Bump para 0.5.0**

`VERSION` e `skill_version` em `assets/config.example.json`.

- [ ] **Step 2: Entrada de CHANGELOG**

Derivar do que realmente aconteceu, não deste plano. Escrever para o **usuário final**: o que muda para ele, não qual tarefa rodou.

Precisa dizer, sem enfeite: a regra dispara só em feature nova; ela pode ser desligada; e o que o hook **não** pega. O plano anterior nasceu de documentação que prometia garantia inexistente — não repetir isso.

- [ ] **Step 3: READMEs**

A tabela de regras dos dois READMEs ganha a linha 10, marcada como checada por hook. A seção "Known limitations" / "Limitações conhecidas" ganha o que o hook não cobre.

- [ ] **Step 4: Verificar**

```bash
python3 tests/test_repo_consistency.py
grep -rniE "guarantee|impossible|garante|impossível" --include=*.md . | grep -v CHANGELOG
```

- [ ] **Step 5: Commit**

```bash
git add VERSION CHANGELOG.md README.md README.pt-br.md assets/config.example.json
git commit -m "chore: release 0.5.0 — align before building"
```

---

## Riscos conhecidos

**O hook não vê o prompt.** `PreToolUse` só recebe a chamada de ferramenta, então quem decide "isso é feature nova" é sempre o modelo lendo o `CLAUDE.md`. O hook pega um caso só: código novo sem alinhamento nenhum. Uma feature inteira construída dentro de arquivos que já existem passa batido. Isso é limitação de desenho, não bug — precisa estar escrito em `hooks/README.md` e nas limitações do README.

**Briga com a Regra 2.** TDD escreve o teste primeiro, e teste é arquivo novo. Por isso arquivo de teste é `allow` incondicional. Se essa isenção virar buraco grande na prática, a alternativa é reconhecer o par teste→implementação, mas isso é bem mais caro e não entra nesta versão.

**O `ask` pode virar ruído.** Se o modelo classificar mal e disparar em conserto de bug, o usuário desliga tudo. Os exemplos de fronteira em `rules.md` e no `CLAUDE.md` são a defesa. Vale medir depois de usar de verdade, e a próxima versão ajusta.

**`head` some em projeto sem git.** Com `vcs: none` não há `HEAD` para comparar, então o registro nunca fica velho por esse caminho. Fail-open: registro presente vale. Aceitável porque a Regra 3 (commit por feature) pressupõe git — quem está sem git já abriu mão de mais garantias que esta.
