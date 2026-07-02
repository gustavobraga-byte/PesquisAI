# Changelog

## [0.5.1] — 2026-06-29 — 🤖 Obsidian Autopilot (Salvamento Autônomo)

### 🤖 O agente agora SALVA SOZINHO

A partir da v0.5.1, o PesquisAI **salva autonomamente** no vault do
Obsidian — **não espera o usuário pedir**. Isto é feito via:

1. **`pesquisai/obsidian/autopilot.py`** (NOVO) — API de alto nível
   com funções que o agente LLM chama diretamente:
   - `recall(query)` — busca no vault antes de responder
   - `save(title, body, tags)` — salva nota após concluir tarefa
   - `save_finding(text, source)` — captura rápida (1 linha)
   - `start_session()` / `end_session(summary)` — log automático
   - `log_skill(id)` / `log_file(path)` — tracking de atividades
   - `auto_init()` — inicializa vault + daily + MOC + sessão

2. **`run_fast.py`** (EDITADO) — chama `auto_init()` na inicialização:
   - Cria o vault automaticamente em `<DRIVE>/PesquisAI/vault/`
   - Cria a daily note de hoje
   - Cria o MOC raiz
   - Inicia a sessão de log automático
   - Instala `pyyaml>=6.0` como dependência

3. **Prompt do agente** (EDITADO) — `_setup_theme_and_agent()` injeta
   instruções de autopilot no `pesquisai.md` que o OpenCode carrega.
   O agente recebe instruções explícitas de:
   - QUANDO salvar autonomamente (após coletar dados, escrever seção…)
   - QUANDO NÃO salvar (respostas curtas, conversa informal)
   - COMO usar a API (exemplos de código prontos)

### 📋 O que o agente faz automaticamente

| Momento | Ação autônoma |
|---|---|
| Início da sessão | `auto_init()` cria vault + daily + MOC + sessão |
| Antes de responder | `recall("tema")` busca notas relevantes |
| Após coletar dados | `save(title, body, tags=["pesquisai/ibge"])` |
| Após escrever seção | `save(..., template="research")` |
| Ao usar skill | `log_skill("ibge-br")` |
| Ao gerar arquivo | `log_file("resultado.csv")` |
| Fim da conversa | `end_session(summary="...")` |

### 🛡️ Garantias

- **Tudo é no-op** se o vault não estiver disponível — o agente nunca quebra
- **Notas humanas são read-only** — o agente não sobrescreve
- **Vault SEMPRE no Google Drive** — validação `discovery._is_in_drive()`
- **Auditoria** — toda escrita é logada em `.pesquisai-audit.log`

### 📊 Estatísticas

| Métrica | Valor |
|---|---|
| Arquivo novo | `pesquisai/obsidian/autopilot.py` (~250 linhas) |
| Arquivos editados | `run_fast.py`, `__version__.py`, `pyproject.toml`, `Dockerfile`, `CHANGELOG.md` |
| Testes | 71 (skill) + 16 (repo) = 87 passing |
| Funções públicas do autopilot | 10 (`recall`, `save`, `save_finding`, `context_brief`, `start_session`, `end_session`, `log_request`, `log_skill`, `log_file`, `stats`, `is_active`, `auto_init`) |

---

## [0.5.0] — 2026-06-29 — 🧠 Obsidian Second Brain (Long-Term Memory)

### 🧠 Memória persistente via Obsidian (NOVO)

Esta é a **maior atualização** do PesquisAI desde a v0.2. Resolve a
limitação declarada no `AGENTS.md` desde a primeira versão:

> *"Sem memória entre sessões: o contexto é reiniciado a cada conversa."*

#### 📍 REGRA DE PERSISTÊNCIA: 100% no Google Drive

> **TUDO** (vault, backups, audit log, exemplos) é salvo **exclusivamente
> no Google Drive do usuário**. Nenhum byte em `/content/` (efêmero no
> Colab) ou `/tmp/` (volátil). A função `discovery._is_in_drive()`
> valida isso e o módulo se **recusa** a operar com vault fora do
> Drive quando no Colab.

Caminho padrão: `/content/drive/My Drive/PesquisAI/vault/`

#### O que é

A skill `obsidian-memory` (repositório git separado, como as demais
skills) transforma um vault do Obsidian em uma **camada de memória
persistente** do agente. Notas, tags, backlinks e wikilinks são
nativos do Obsidian — não inventamos um formato proprietário.

#### Componentes adicionados

- **Módulo Python** `pesquisai.obsidian` (8 arquivos, ~1.500 linhas)
  - `memory.py` — API pública (`ObsidianMemory`)
  - `vault.py` — CRUD de notas com fsync + audit log
  - `links.py` — `LinkIndex` (case + accent insensitive)
  - `search.py` — BM25 offline (sem dependências externas)
  - `models.py` — dataclasses (`Note`, `SearchResult`, `SessionLog`, `TagIndex`)
  - `discovery.py` — detecção automática de vault + validação Drive
  - `sync.py` — sincronização com Drive / git
  - `__init__.py` — API pública com lazy import (evita circular)

- **Skill** `obsidian-memory` (repositório git separado:
  `https://github.com/gustavobraga-byte/skill-obsidian-memory.git`)
  - `SKILL.md` — descrição formal
  - `README.md` — convenções e Dataview queries
  - `templates/` — **10 templates oficiais** (daily, research, literature,
    session, methodology, data-source, hypothesis, reference, moc, inbox)
  - `examples/` — 3 notas reais de exemplo
  - `tests/` — pytest com **71 testes** (100% passing)

- **Documentação** `docs/`
  - `OBSIDIAN_INTEGRATION.md` — guia de instalação e uso
  - `OBSIDIAN_MEMORY_MODEL.md` — modelo de dados e máquina de estados
  - `OBSIDIAN_WORKFLOW.md` — workflows por cenário (TCC, artigo, etc.)

- **Scripts** `scripts/`
  - `init_vault.sh` — bootstrap do vault (valida Drive)
  - `install_plugin.sh` — instala 7 plugins recomendados
  - `sync_drive_to_obsidian.sh` — sync bidirecional com proteção

#### Capacidades adicionadas

| Capacidade | Descrição |
|---|---|
| Memória persistente | Lê vault no início, grava ao final |
| Continuidade de projetos | Acompanha TCCs e artigos por meses |
| Backlinks e wikilinks | Conexões nativas `[[nota]]` |
| Tags padronizadas | Taxonomia `pesquisai/*` |
| Templates versionados | 10 templates oficiais |
| Busca textual + tag | BM25 offline |
| Dataview queries | Metadados YAML expostos |
| MOCs (Maps of Content) | Índices temáticos auto-montados |
| Sync bidirecional | Drive ↔ git ↔ dispositivos |
| Auditoria | `.pesquisai-audit.log` |

### 🧪 Teste de ponta a ponta validado

A integração foi testada **de ponta a ponta** em um vault real no
Google Drive, simulando o uso dentro do agente PesquisAI:

| Etapa | Resultado |
|---|---|
| Import do módulo `pesquisai.obsidian` | ✅ |
| Detecção automática do vault no Drive | ✅ |
| `ensure_drive_path()` cria pasta no Drive | ✅ |
| `ObsidianMemory.from_env()` inicializa | ✅ status=ready |
| `create_note()` com template `research-note` | ✅ |
| `update_note()` com `append=` | ✅ (após correção de bug) |
| `end_session()` grava log em `sessions/` | ✅ |
| Busca BM25 `search("diabetes")` | ✅ ranking correto |
| `by_tag("pesquisai/ibge")` | ✅ |
| `context_brief()` para prompt do agente | ✅ |
| Audit log `.pesquisai-audit.log` | ✅ |
| Tudo persistido no Google Drive | ✅ |

### 🐛 Bugs corrigidos (encontrados no teste e2e)

#### Bug crítico 1: `update_note()` quebrava com `NoteMetadata` frozen

**Sintoma:** `FrozenInstanceError: cannot assign to field 'updated'`
ao chamar `mem.update_note(note, append="...")`.

**Causa:** `NoteMetadata` é `frozen=True`, mas o código fazia
`new_note.metadata.updated = _dt.date.today()` (setattr direto).

**Correção:** usar `dataclasses.replace()` para criar nova instância.
Também recomputa `wikilinks` e `tags` do novo corpo.

**Arquivo:** `pesquisai/obsidian/memory.py::update_note()`

#### Bug 2: `write_from_template()` duplicava tag `pesquisai/draft`

**Sintoma:** tags da nota apareciam como
`('pesquisai/draft', 'pesquisai/draft', 'pesquisai/ibge', ...)`.

**Causa:** a tag era adicionada tanto em `merged["tags"]` quanto em
`tags=` do `Note`, duplicando.

**Correção:** dedup via `dict.fromkeys()` (preserva ordem) + extração
de wikilinks/tags do body renderizado.

**Arquivo:** `pesquisai/obsidian/vault.py::write_from_template()`

### 📋 Política de integridade (mantida)

| Princípio | Mantido? |
|---|---|
| Zero-fabricação | ✅ sim |
| `citation-management` obrigatório | ✅ sim |
| Sem simulação de coleta primária | ✅ sim |
| Dados nacionais (IBGE/DataSUS) prioridade | ✅ sim |
| Marcadores de evidência | ✅ sim |
| Fallback gracioso | ✅ sim |
| Criptografia de chaves | ✅ sim |
| **Vault SEMPRE no Google Drive** | ✅ sim (rejeita fora do Drive no Colab) |

**Regra de ouro:** notas humanas são **read-only** para o agente.
Apenas notas com `created_by: pesquisai` no frontmatter podem ser
editadas pelo PesquisAI (com log de auditoria).

### 📊 Estatísticas

| Métrica | Valor |
|---|---|
| Linhas de código Python adicionadas | ~1.500 |
| Linhas de Markdown (templates + docs) | ~3.000 |
| Testes pytest | 71 (100% passing) |
| Cobertura de testes | ≥ 80% no módulo `pesquisai.obsidian` |
| Teste e2e no Drive | ✅ validado |
| Bugs corrigidos | 2 (1 crítico + 1 menor) |

### 🛠️ Arquivos modificados

- `pesquisai/constants.py` — adicionada skill `obsidian-memory` ao
  `SKILL_REGISTRY` + `SKILL_MAPPINGS` + bloco `OBSIDIAN_*`
- `pesquisai/__version__.py` — `0.4.2.3` → `0.5.0`
- `AGENTS.md` — adicionada Seção 2.3 (Memória Persistente)
- `CHANGELOG.md` — esta entrada
- `pyproject.toml` — dependência `pyyaml>=6.0` (opcional), keywords,
  testpaths, fail_under 70 → 75
- `README.md` — adicionada skill `obsidian-memory` na lista

### 📦 Arquivos criados

- `pesquisai/obsidian/{__init__,discovery,memory,vault,links,search,models,sync}.py` (8)
- `docs/OBSIDIAN_{INTEGRATION,MEMORY_MODEL,WORKFLOW}.md` (3)
- `scripts/{init_vault,install_plugin,sync_drive_to_obsidian}.sh` (3)

### 🧩 Skill separada (repositório git)

A skill `obsidian-memory` é distribuída como repositório git separado
(padronização com as demais skills: ibge-br, opendatasus, etc.):

- `SKILL.md` + `README.md` (2)
- `templates/*.md` (10)
- `examples/*.md` (3)
- `tests/test_*.py` (5: vault, links, search, drive_validation, regression_e2e)

**Total:** 14 arquivos no repo principal + 20 arquivos na skill = 34 novos.

### 🔧 Compatibilidade

- **Backward compatible** — sem breaking changes
- **Opt-in** — o módulo é desativado se `PESQUISAI_OBSIDIAN_VAULT`
  não estiver definida
- **Sem dependência obrigatória** — `pyyaml` é opcional (há fallback)
- **Multiplataforma** — Linux, macOS, Windows, Colab, Docker

### 🚀 Migração

Para usuários existentes:

```bash
# 1. Atualize o repositório
git pull origin main

# 2. Inicialize o vault no Google Drive
./scripts/init_vault.sh

# 3. Defina a variável
export PESQUISAI_OBSIDIAN_VAULT="/content/drive/My Drive/PesquisAI/vault"

# 4. Rode os testes (opcional)
pytest skills/obsidian-memory/tests/ -v
```

---

## [0.4.2.3] — 2026-06-24 — ses_106b HOTFIX (JS Broken Escapes — Botões Restaurados)

### 🐛 Bug Crítico Resolvido

**Sintoma:** ao carregar `/tmp/pesquisai-wrapper/index.html` no navegador, NENHUM
botão respondia (📜 Histórico, 🌍 Idioma, 🌓 Tema, 🩺 Dashboard, etc.).

**Causa raiz:** a string tripla `"""..."""` em `pesquisai/launch_app_responsive_v041.py`
continha escapes de aspas (`\'` e `\"`) para representar caracteres de escape JavaScript.
Python, ao compilar a string, **removia os backslashes** (interpretando-os como
escape de aspa Python), gerando HTML com JavaScript inválido. O navegador abortava
o `<script>` inteiro com `SyntaxError`, e como todas as funções e event handlers
estavam nesse script, **nada funcionava**.

**Validação Node.js (antes):**
```
SyntaxError: Invalid or unexpected token
    return '<div class="session-item" onclick="restoreSession('' +
                                                              ^^^
```

###  Correções (3 mudanças cirúrgicas)

#### 1. `renderSessions()` (linha 1684) — onclick inline → event delegation
- **Antes:** `'<div onclick="restoreSession(\'' + ... + '\')">'` (frágil)
- **Depois:** `'<div data-session-id="..." class="session-item">'` + listener global
- **Por que:** elimina concatenação dinâmica de aspas dentro de string tripla Python

```javascript
// ANTES (quebrado)
return '<div class="session-item" onclick="restoreSession(\'' +
  String(id).replace(/'/g, "\\'") + '\')" title="\'">'

// DEPOIS (correto)
return '<div class="session-item" data-session-id="' + escapeHtml(String(id)) + '" title="...">'

// + event listener global
document.addEventListener("click", (ev) => {
  const item = ev.target.closest(".session-item");
  if (item && item.dataset.sessionId) {
    restoreSession(item.dataset.sessionId);
  }
});
```

#### 2. `restoreSession()` (linha 1714) — confirm() com chr(34)
- **Antes:** `confirm("Restaurar sessão \"" + sessionId + "\" ?")` (perdia o `\"`)
- **Depois:** `confirm("Restaurar sessão " + chr(34) + sessionId + chr(34) + " ?")`
- **Por que:** `chr(34)` é concatenação JS runtime, zero risco de escape Python

#### 3. `escapeHtml()` (linha 1736) — object literal → if/else chain
- **Antes:** `{"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]`
- **Depois:** `if (c === "&") return "&amp;"; ... if (c === '"') return "&quot;"; ...`
- **Por que:** evita conflito de aspas dentro do objeto literal mapeado

###  Validação Final

-  `node --check` no JS extraído: **SEM ERROS**
-  HTML regenerado: **89.127 chars** (vs 88.517 da v0.4.2.2)
-  10/10 funções JS verificadas: `openAgents`, `openHealth`, `openSessions`,
  `openShortcuts`, `toggleTheme`, `toggleLangMenu`, `toggleMobileMenu`,
  `doBackup`, `openRestore`, `closeModal`
-  42 botões com `onclick="..."` validados
-  79/79 testes pytest continuam passando (sem regressão)
-  Backups e restores preservados (openRestore, doBackup)
-  Modal de sessões agora abre + renderiza + responde a cliques

###  Arquivos Modificados

```
pesquisai/
├── __version__.py                    # 0.4.2.2 → 0.4.2.3
└── launch_app_responsive_v041.py     # 3 hotfixes (renderSessions, restoreSession, escapeHtml)
```

---

## [0.4.2.2] — 2026-06-24 — (Footer PC + Skills + Sessions + Lang + Version)

### 🐛 Bug Fixes & Funcionalidades (6 melhorias reportadas em 2026-06-24)

####  9. Footer PC: provedor e "Powered by OpenCode" alinhados à DIREITA
- **Problema:** no desktop, o botão de provedor e o texto "Powered by OpenCode"
  ficavam **colados à esquerda**, junto com o restante do rodapé. Em PC,
  deveriam estar alinhados **à direita** (em mobile, mantém o layout de 2 linhas).


####  10. Skills: `grant-finder` e `meta-search-br` adicionadas em `skills/`
- **Problema:** as 2 skills extras existiam (grant-finder em `grant_finder/`
  na raiz, meta-search-br em `skills/meta-search-br/`) mas **não estavam
  organizadas** em `skills/` com links de clone padronizados.


####  11. Histórico de sessão não carregava
- **Problema:** `openSessions()` apenas **abria o overlay** visual
  (`opacity: 1`) mas **não fazia fetch** em `/api/sessions` nem populava
  a lista. O usuário clicava no ícone 📜 e só via "Carregando sessões…"
  para sempre.
- **Correção:**
  - `openSessions()` agora faz `fetch(BASE + "/api/sessions")` + `await`
  - Nova função `renderSessions(sessions, query)` popula `#session-list`
    com linhas de sessão (id, título, data de criação, contagem de mensagens)
  - Cada item é **clicável** e chama `restoreSession(id)` que faz POST
    em `/api/restore` para importar a sessão
  - Busca em tempo real via `filterSessions()` (filtra por id/título)
  - 3 novas strings i18n por idioma (12 total): `sessions.empty`,
    `sessions.empty_filtered`, `sessions.click_to_restore`
  - Mensagem de erro amigável se a requisição falhar
  - Função utilitária `escapeHtml()` para prevenir XSS nos campos de sessão

####  12. Saudação inicial do ttyd no idioma selecionado
- **Problema:** ao iniciar o terminal (ttyd), o opencode recebia sempre
  `--prompt 'oi'` genérico. Ao trocar idioma via UI, a saudação continuava
  fixa em português.
- **Correção:**
  - `start_ttyd(lang=None)` agora aceita o idioma como parâmetro
  - Saudação = `get_greeting(lang)` que retorna texto específico por idioma:
    - **pt_BR**: "Olá! (Dica: A partir de agora responda em português brasileiro.)"
    - **en_US**: "Hello! (Tip: From now on, please respond in English.)"
    - **es_ES**: "¡Hola! (Consejo: A partir de ahora responda en español.)"
    - **fr_FR**: "Bonjour ! (Astuce: À partir de maintenant, répondez en français.)"
  

####  13. `__version__.py` MOVIDO para `pesquisai/__version__.py`
- **Problema:** o arquivo de versão estava na **raiz** do repositório
  (`/__version__.py`), enquanto o pacote Python está em `pesquisai/`. Isso
  quebrava imports relativos (`from .__version__ import VERSION`).
- **Correção:**
  - `__version__.py` movido de `/__version__.py` → `/pesquisai/__version__.py`
  - Versão bumpada para `0.4.2.2`
  - Codinome: `ses_10a4+ polish (footer PC + skills + sessions + lang + version)`
  - Mantida compatibilidade com import via fallback (valor hardcoded
    `"0.4.2.2"` se o módulo não for encontrado)
  - `launch_app.py` agora importa `get_greeting` de `.__version__` com
    fallback para definição local
  - `launch_app_responsive_v041.py` também atualizado para o novo path
  - Novas funções utilitárias: `get_greeting(lang)`, `__language_greetings__`
    (dicionário por idioma), `__extra_skills__` (lista das 2 skills extras
    com repositório)

####  14. AGENTS.md multilíngues padronizados
- **Problema:** o francês tinha `[lien](agents/AGENTS.pt.md)` em todos os
  itens da lista de variantes, enquanto pt/en/es tinham `- [link/enlace]`
  apenas no item do francês. Resultado: padrão inconsistente entre idiomas.
- **Correção:**
  - Removido `- [link](agents/AGENTS.fr.md)` do `AGENTS.pt.md`
  - Removido `- [link](agents/AGENTS.fr.md)` do `AGENTS.en.md`
  - Removido `- [enlace](agents/AGENTS.fr.md)` do `AGENTS.es.md`
  - Removidos **3** `- [lien](agents/AGENTS.pt.md|en.md|es.md)` do `AGENTS.fr.md`
  - Formato final padronizado em todos os 4 idiomas:
    `- \`agents/AGENTS.<lang>.md\` (nome do idioma)`
  - Sem link markdown inline (o filename já é o link relativo no GitHub)

###  Validação

-  **79/79 testes** continuam passando (`grant_finder/tests/` + `i18n/tests/`)
-  **Sintaxe Python validada** em 5 arquivos:
  - `pesquisai/launch_app.py`
  - `pesquisai/launch_app_responsive_v041.py`
  - `pesquisai/__version__.py`
  - `skills/grant-finder/__init__.py`
  - `skills/meta-search-br/__init__.py`
-  **Geração do wrapper HTML** validada (88.517 chars, +6% vs v0.4.2.1)
-  **`get_greeting()`** testada para todos os 4 idiomas + 5 short codes
-  **Comando bash do ttyd** testado para 4 idiomas (escaping correto)

---

## [0.4.2.1] — 2026-06-23 — ses_10a4 Fixes (Theme Contrast + Dashboard + Markdown)

### 🐛 Bug Fixes (3 adicionais reportados pelo usuário em 2026-06-23)

####  6. Tema CLARO: textos invisíveis nos modais
- **Problema:** 6 modais (Dashboard de Saúde, Atalhos de Teclado, Sessões,
  Provedor, Diretrizes, Restaurar) usavam `background:#181b1e` como **cor
  fixa CSS inline**. No tema claro, `--ink-muted` é `#4a5a62` (cinza
  escuro), mas o fundo continuava `#181b1e` (escuro), resultando em
  **texto invisível** (cinza escuro em fundo escuro).
- **Correção:**
  - Nova classe `.modal-shell` que usa **variáveis CSS** (`--modal-bg`,
    `--modal-border`) ao invés de cores fixas
  - Regra `html.theme-light .modal-shell` define `--modal-bg: #ffffff`
    e sombra mais suave
  - Inputs (`#prov-key-input`, `.session-search`) ganham estilo explícito
    para tema claro
  - Botões `.modal-close` e itens de lista (`.backup-item:hover`,
    `.session-item:hover`) também têm contraste corrigido
  - **6 modais atualizados** para usar a classe `.modal-shell`

####  7. Dashboard de Saúde não carregava
- **Problema:** `openHealth()` apenas abria o overlay visual (`opacity: 1`)
  mas **não fazia fetch** em `/api/health` nem populava `#health-list`.
  O usuário via "Carregando diagnóstico…" indefinidamente.
- **Correção:**
  - `openHealth()` agora faz `fetch(BASE + "/api/health")` + `await`
  - Nova função `renderHealth(d)` popula a lista com **badges de status**
    (✓/✗/·) para cada checagem:
    - Drive montado
    - Diretório de backup
    - Terminal (ttyd) vivo
    - Binário OpenCode encontrado
    - Chave de criptografia presente
    - Keys store existe
    - ffmpeg disponível
    - Skills carregadas (contagem)
    - API keys ativas no env
    - Espaço em disco (GB livres / totais)
    - Versão do PesquisAI
  - Mensagem de erro amigável se a requisição falhar

####  8. Modal de Diretrizes mostrava o MD como texto cru
- **Problema:** o conteúdo do `AGENTS.md` era injetado via
  `contentEl.textContent = d.content`, exibindo os caracteres `#`, `**`,
  `|`, `---` e `` ` `` do markdown **como texto puro**, sem formatação.
- **Correção:**
  - Adicionado `marked.js` v12.0.0 (CDN jsdelivr) ao `<head>` da página
  - Adicionado `github-markdown-css` v5.5.1 para estilos de markdown
  - Nova função `renderAgentsContent(el, md)` usa `marked.parse()`
    para converter markdown → HTML formatado
  - CSS customizado (`#agents-content.markdown-body`) preserva:
    - Cores do tema (accent, ink, ink-muted) ao invés de cores GitHub
    - Fontes (Syne para títulos, DM Mono para corpo/código)
    - Bordas, espaçamentos, tabelas, blockquotes, code blocks
  - **Frontmatter YAML removido** antes da renderização (regex via
    `String.fromCharCode(92)` para evitar SyntaxWarning em py_compile)
  - Fallback automático: se `marked` não carregar (offline), mostra
    como texto pré-formatado

### Arquivos Modificados (v0.4.2.1)

- `pesquisai/launch_app_responsive_v041.py` — **+3 correções ses_10a4**
  - `<head>`: + `marked.js` CDN + `github-markdown-css` CDN
  - CSS: + classe `.modal-shell` + tema claro para 6 modais
  - CSS: + estilos `#agents-content.markdown-body` (cor, fonte, tabela,
    blockquote, code, headings, hr, ul, ol)
  - HTML: 6 modais trocados de `style="background:#181b1e"` para
    `class="modal-shell"`
  - HTML: `#agents-content` ganhou `class="markdown-body"`
  - JS: `openHealth()` agora faz `fetch` em `/api/health`
  - JS: nova função `renderHealth(d)` renderiza lista com badges
  - JS: nova função `renderAgentsContent(el, md)` usa `marked.parse()`
  - JS: `loadAgents()` chama `renderAgentsContent()` ao invés de
    `textContent`
- `agents/AGENTS.{pt,en,es,fr}.md` — **versão 0.2.1/0.4.0 → 0.4.1**
  - Versão corrigida no header (`**Versão:** 0.4.1`) e footer
    (`PesquisAI · v0.4.1`) em todos os 4 idiomas
  - "Três idiomas" → "Quatro idiomas" em pt/en/es
  - "Trois langues" → "Quatre langues" em fr
  - Adicionada referência cruzada `agents/AGENTS.fr.md` em todos os
    arquivos (pt/en/es/fr)
- `agents/README.md` — **+francês** na lista de idiomas
  - Tabela agora lista os 4 idiomas com bandeiras
  - Tabela de marcadores de evidência tem linha para `fr_FR`
  - Seção "Adicionar novo idioma" usa `de_DE` como exemplo
- `__version__.py` — `0.4.2` → `0.4.2.1`
  - Codinome: "ses_10a4 fixes (theme contrast + health + markdown)"
  - +2 componentes: `launch_app_responsive_v0421`, `agents_modal`

###  Validação (v0.4.2.1)

- **32/32 checks** passaram (4 da v0.4.1 + 10 da v0.4.2 + 3 da v0.4.2.1
  + 15 críticos diversos)
- **Sintaxe Python validada** com `py_compile(..., doraise=True)` +
  `warnings.simplefilter("error", SyntaxWarning)` — 3/3 arquivos
  compilam **sem warnings** (incluindo o JavaScript embutido com
  `String.fromCharCode` para evitar `\s` inválido)
- **HTML gerado:** 82.749 caracteres (vs. 74.901 da v0.4.2 — +10% por
  causa do modal Diretrizes com markdown renderer)
- **Endpoint `/api/agents`** testado em 10 variações de idioma
  (pt_BR, en_US, es_ES, fr_FR + 4 short + 2 inválidos — todos OK)
- **Renderização markdown** testada com marked.js v12.0.0
- **Contraste de tema claro** testado em todos os 6 modais

###  Compatibilidade

-  **Backward compatible** — sem breaking changes
- **CDN fallbacks** — se marked.js/github-markdown-css falharem ao
  carregar, modal mostra texto pré-formatado (graceful degradation)
-  **JS engine** — `String.fromCharCode(92)` funciona em todos
  navegadores (>= IE6)

---

## [0.4.2] — 2026-06-23 — Footer Responsive + Multilingual AGENTS.md

### 🐛 Bug Fixes (reportados pelo usuário em 2026-06-23 — sessão `ses_10a4`)

#### 4. Rodapé NÃO responsivo
- **Problema:** o `#footer` original tinha `display: flex` SEM `flex-wrap`,
  causando **transbordamento horizontal** em mobile. Os 8+ itens do rodapé
  (PesquisAI, email, GitHub, UFV, Provedor, OpenCode, separadores) estouravam
  a tela em larguras < 480px. O `#terminal-frame` também tinha altura fixa
  `calc(100% - 90px)` que não considerava o rodapé crescendo em 2 linhas.
- **Correção:**
  - `flex-wrap: wrap` + `overflow: hidden` no `#footer`
  - 2 linhas lógicas: `.footer-row-1` (marca + email + GitHub + UFV) e
    `.footer-row-2` (provedor + OpenCode)
  - `display: contents` em desktop (wrappers invisíveis → fluxo flex normal)
  - Em mobile (≤767px), wrappers viram linhas reais com `gap: 4px 8px`
  - Em mobile muito pequeno (<480px), GitHub some, e altura do terminal
    recalcula para `calc(100vh - 50px - 52px)`
  - Em landscape (altura <500px), só a primeira linha aparece, altura 30px
  - `#terminal-frame` corrigido de `calc(100% - 90px)` para
    `calc(100vh - 90px)` + ajustes por breakpoint

#### 5. Troca de idioma NÃO trocava o AGENTS.md
- **Problema:** ao trocar para inglês/espanhol/francês, **apenas as strings
  da UI** eram traduzidas (data-i18n), mas o arquivo `agents/AGENTS.xx.md`
  (regras de integridade científica) continuava sendo exibido/servido no
  idioma original. Pesquisador que trocava para inglês continuava lendo
  regras de "Não invente dados" em português.
- **Correção:**
  - **Novo endpoint backend** `GET /api/agents?lang=pt_BR|en_US|es_ES|fr_FR`
    que serve o conteúdo de `agents/AGENTS.<lang>.md` apropriado
  - **Novo modal "📋 Diretrizes do Agente"** com botão na topbar
  - **Cache client-side** por idioma (1 chamada até próxima troca)
  - **Invalidação automática do cache** em `setLang()` + recarregamento
    se o modal estiver aberto
  - **Botões auxiliares:** 📋 Copiar (com fallback para `execCommand`),
    ↻ Recarregar, 🔗 Ver fonte (link direto pro GitHub)
  - **Badge do idioma atual** no header do modal (PT-BR, EN-US, ES-ES, FR-FR)
  - **Link da fonte dinâmico:** aponta pro arquivo correto no GitHub
    (AGENTS.pt.md, AGENTS.en.md, etc.) baseado no idioma ativo

###  Funcionalidades Adicionais (v0.4.2)

- **Detecção de diretório `agents/`** robusta: busca em até 5 níveis acima
  do `launch_app.py`, em `_folder_path` (Drive) e em `os.getcwd()`
- **Fallback gracioso** se o AGENTS.md não for encontrado: retorna JSON
  com `ok: false` e lista de caminhos tentados
- **Toast de feedback** ao copiar diretrizes (`✅ Diretrizes copiadas!`)
- **Item "Diretrizes" no mobile menu** (drawer) com toggle automático
- **Tecla `Escape`** fecha também o modal de Diretrizes
- **4 novas strings traduzidas** (`footer.email`, `footer.github`,
  `footer.ufv`, `footer.powered_by`) + chaves `footer.email_title`,
  `footer.github_title` para tooltips
- **9 strings do modal de Diretrizes** (`agents.title`, `agents.subtitle`,
  `agents.loading`, `agents.error`, `agents.copy`, `agents.copy_ok`,
  `agents.open_source`) em 4 idiomas = **36 novas traduções**

###  Arquivos Modificados (v0.4.2)

- `pesquisai/launch_app_responsive_v041.py` — **+rodapé responsivo, +modal Diretrizes**
  - Footer CSS: `flex-wrap`, `overflow: hidden`, 2 linhas lógicas
  - Footer HTML: `<div class="footer-row-1">` + `<div class="footer-row-2">`
  - Topbar: novo botão `openAgents()` (📋) com tooltip i18n
  - Mobile menu: novo item "📋 Diretrizes do Agente"
  - HTML: novo modal `#agents-overlay` com header/content/footer
  - JS: `openAgents()`, `closeAgents()`, `loadAgents()`, `copyAgents()`,
    `reloadAgents()` + invalidação de cache em `setLang()`
  - CSS: ajustes no `@media (max-width: 1023px|767px|479px)` e
    `@media (max-height: 500px)` para o rodapé
- `pesquisai/launch_app.py` — **+endpoint `GET /api/agents`**
  - Suporta `?lang=pt_BR|en_US|es_ES|fr_FR|pt|en|es|fr`
  - Busca `agents/AGENTS.<lang>.md` em até 5 localizações
  - Retorna `{ok, lang, filename, content}` ou `{ok:false, error, tried}`
- `__version__.py` — `0.4.1` → `0.4.2`, codinome
  "Footer Responsive + Multilingual AGENTS.md"

###  Compatibilidade

-  **Backward compatible** — sem breaking changes
-  **Endpoint opcional** — se o `agents/` não existir, UI mostra
  mensagem amigável "Erro ao carregar diretrizes"
-  **Fallback HTML** — modal sempre renderiza, mesmo offline
  (mostra "Erro ao carregar" se a rede cair)

###  Validação

- **28/28 validações automáticas** aprovadas (rodapé + modal + i18n)
- **79/79 testes** continuam passando (48 grant_finder + 31 i18n)
- **Cobertura 71.58%** mantida (mínimo: 70%)
- HTML gerado: **74.901 caracteres** (vs. 60.582 da v0.4.1)
- **Endpoint `/api/agents` testado** com 10 variações de idioma
  (4 completos + 4 short + 2 inválidos — todos retornam corretamente)

---

## [0.4.1] — 2026-06-23 — UI Fixes (Responsive + Theme + Language)

###  Reorganização da Estrutura (2026-06-23)
- **Estrutura do repositório reformatada** para separar código do PesquisAI de
  arquivos pessoais (sandbox):
  - `docs/` — toda documentação (CHANGELOG, PATCH, MOBILE, INTEGRITY)
  - `releases/v0.4.0/` — release isolada completa (com pyproject.toml, LICENSE, CI, etc.)
  - `sandbox/` — artigos, projetos, datasets, figuras, TCCs, scripts, utils (138MB)
  - `sessions/` — logs de sessão
  - Raiz reduzida de 145MB para ~7MB (apenas código PesquisAI)
- **README.md** criado na raiz explicando a nova estrutura
- **`__version__.py`** atualizado com `__default_theme__ = "pesquisai"` (escuro)

###  Tema Padrão: ESCURO (anti-flash)
- **Script anti-flash no `<head>`** executa ANTES do CSS, lendo cookie/localStorage
  e aplicando tema escuro como padrão (só troca para claro se persistido)
- **CSS `html { background: #0d0f10; color: #e8e6e0; }` inline** garante que o
  body já inicia com fundo escuro (sem flash branco no carregamento)
- **Classe `html.theme-light`** no CSS para override do tema claro
- **`<html data-theme="pesquisai">`** explícito como padrão
- **Sincronização em `applyWrapperTheme()`** que adiciona/remove a classe
  `.theme-light` no `<html>` para que o CSS use as variáveis corretas

### 🐛 Bug Fixes Críticos (reportados pelo usuário em 2026-06-23)

#### 1. Site NÃO estava responsivo
- **Problema:** o `launch_app.py` do PesquisAI principal no GitHub não tinha
  media queries. Topbar de 8 botões estourava em mobile, modais 400-520px não
  cabiam, sem hamburger menu.
- **Correção:** adicionadas 6 media queries (5 breakpoints + landscape) com
  hamburger drawer, modais fluidos (95vw em mobile), touch targets ≥ 32-44px
  (Apple HIG / WCAG 2.5.5), hamburger mobile menu com todos os itens da
  topbar reorganizados.

####  2. Tema claro/escuro NÃO recarregava o terminal
- **Problema:** `toggleTheme()` chamava `applyWrapperTheme()` que só mudava
  as CSS variables do wrapper, mas NUNCA recarregava o iframe do ttyd.
  Resultado: a UI mudava, mas o terminal continuava com o tema antigo.
- **Correção:** após aplicar o tema na UI, recarrega o iframe do ttyd
  com cache-busting (`?theme=pesquisai-light&t=<timestamp>`), mesmo padrão
  usado em `confirmProvider()` / `restoreSession()` / `doRestore()`. Tempo
  de reload: 3.5s (aguarda restart do ttyd no backend).

#### 3. Idioma sem opção na interface
- **Problema:** o módulo `i18n` estava completo (4 idiomas, JSONs), mas
  não havia seletor visível na topbar. Usuário não tinha como trocar idioma.
- **Correção:** adicionado dropdown na topbar com 4 idiomas (🇧🇷 PT, 🇺🇸 EN,
  🇪🇸 ES, 🇫🇷 FR), persistência em cookie `pesquisai_lang` + localStorage,
  query param `?lang=xx_XX` para forçar via URL, atualização do atributo
  `<html lang="xx-XX">` e de todas as strings visíveis via `data-i18n`.

###  Funcionalidades Adicionais

- **Cookie helpers** (`setCookie` / `getCookie`) para tema e idioma
- **Detecção automática de idioma** com prioridade: URL > cookie > localStorage > `navigator.language` > padrão
- **Indicador visual do tema ativo** no botão (`#theme-toggle[data-theme="pesquisai-light"]` → cor amber)
- **Meta `theme-color` dinâmica** (muda junto com o tema para a barra de status do navegador mobile)
- **40+ strings traduzidas inline** no client-side para feedback instantâneo
- **Endpoint backend opcional** `GET/POST /api/lang` para persistir idioma no Drive
- **Click-outside** para fechar dropdown de idioma
- **Tecla `Escape`** fecha também o dropdown de idioma e o mobile menu

###  Arquivos Novos

- `pesquisai/launch_app_responsive_v041.py` — **drop-in patch** para o `launch_app.py` do GitHub
- `docs/PATCH_v0.4.1.md` — documentação completa do patch (instalação + testes)
- `i18n/translations/fr_FR.json` — 🇫🇷 francês (NOVO em v0.4.0, expandido em v0.4.1)

###  Arquivos Atualizados

- `pesquisai/launch_app_responsive.py` — agora contém as 3 correções (era v0.1.0 → v0.2.0)
- `__version__.py` — `0.4.0` → `0.4.1`, codinome "UI Fixes (Responsive + Theme + Language)"

###  Compatibilidade

-  **Backward compatible** — sem breaking changes
-  **API inalterada** — `create_wrapper_html(terminal_url, drive_url)` mantém a assinatura
-  **CSS puro** — sem dependências externas adicionais
-  **Fallback** — se JS do hamburger falhar, topbar original ainda funciona

###  Validação

- 79 testes continuam passando (48 grant_finder + 31 i18n) — 100% das suítes verdes
- HTML gerado tem **60.582 caracteres** (vs. ~38.000 do v0.4.0) — todas as correções injetadas
- 26 validações automáticas aprovadas (mobile menu, lang selector, toggleTheme reload, JSON válido, etc.)

---

## [0.4.0] — 2026-06-23 — International & Mobile

###  Funcionalidades Principais

####  Site Responsivo Mobile
- **`pesquisai/launch_app_responsive.py`** — Wrapper HTML adaptativo substitui layout estático
- **5 breakpoints:** mobile pequeno (< 480px), mobile (480-767px), tablet (768-1023px), tablet portrait, desktop (≥ 1024px), landscape
- **Hamburger menu drawer** lateral em mobile (280px / 85vw)
- **Modais fluidos** (95vw em mobile, até 600px em tablet)
- **Touch targets ≥ 32-44px** (Apple HIG / WCAG 2.5.5)
- **Acessibilidade:** `aria-label`, `aria-hidden`, foco visível, `Escape` para fechar
- **Meta tags:** `viewport-fit=cover`, `theme-color`, `-webkit-tap-highlight-color`

#### 🔍 Skill grant_finder (Nova)
- **13 agências** integradas:
  - **Brasil (8):** CNPq, CAPES, FAPEMIG, FAPESP, FINEP, FAPERJ, FAPERGS, BNDES
  - **Internacional (5):** NIH, NSF, ERC, Wellcome, Horizon Europe
- **5 funções públicas:** `search_grants`, `check_eligibility`, `generate_budget`, `draft_proposal`, `make_timeline`
- **4 dataclasses:** `ResearcherProfile`, `Grant`, `EligibilityReport`, `Budget`
- **Cache local** com TTL de 24h e `fetched_at` explícito
- **Verificação de elegibilidade** com score 0-1, razões, avisos e ações
- **Geração de orçamento** estruturado por rubricas (custeio, capital, bolsas)
- **Minutas de proposta** em PT e EN com seções padrão (IMRaD)
- **48 testes passando** em 3 suítes (test_matcher, test_budget, test_proposal)

#### 🌐 Suporte Multilíngue (i18n)
- **4 idiomas:** 🇧🇷 pt_BR, 🇺🇸 en_US, 🇪🇸 es_ES, 🇫🇷 fr_FR
- **Detecção automática** via variável `PESQUISAI_LANG`, `LANG`, `LC_ALL`, `Accept-Language`
- **API limpa:** `t("chave.subchave")` com fallback automático
- **Sistema de interpolação** com `{variavel}`
- **Quality-based selection** de `Accept-Language` (q=0.9, q=0.8…)
- **CLI helper:** `set_language()`, `get_language()`, `detect()`, `t_for()`, `available_languages()`
- **31 testes passando** em 5 categorias

#### Agents Multilíngues
- `agents/AGENTS.pt.md` — 🇧🇷 Português (Brasil) — padrão
- `agents/AGENTS.en.md` — 🇺🇸 English (United States)
- `agents/AGENTS.es.md` — 🇪🇸 Español (España)
- `agents/AGENTS.fr.md` — 🇫🇷 Français (France) — **NOVO**
- 100% das regras de integridade científica preservadas em todas as variantes
- Marcadores de evidência traduzidos (`[DADO CONFIRMADO]` / `[CONFIRMED DATA]` / `[DATO CONFIRMADO]` / `[DONNÉE CONFIRMÉE]`)

###  Qualidade de Código

- **79 testes passando** (48 grant_finder + 31 i18n) — 100% das suítes verdes
- Cobertura estimada > 85% nos módulos novos
- Type hints em todas as funções públicas
- Docstrings em todas as classes e funções
- 4 suítes pytest: test_matcher, test_budget, test_proposal, test_translator
- Testes de edge cases: cache corrompido, JSON truncado, normalização de locale, encoding UTF-8

###  Segurança e Integridade Científica

- **Política de zero-fabricação** mantida em todos os novos módulos
- `grant_finder`: sempre declara `fetched_at` e link oficial para conferência
- Marcador `[SEM DADOS SUFICIENTES]` / `[NO DATA AVAILABLE]` / `[SIN DATOS SUFICIENTES]` / `[DONNÉES INSUFFISANTES]`
- Aviso explícito: "SEMPRE conferir link oficial antes de submeter proposta"

###  Estrutura do Release

```
pesquisai-v0.4.0/
├── README.md
├── LICENSE
├── .gitignore
├── pyproject.toml
├── CHANGELOG.md
├── __version__.py
├── agents/
│   ├── AGENTS.pt.md
│   ├── AGENTS.en.md
│   ├── AGENTS.es.md
│   └── AGENTS.fr.md  ← NOVO
├── grant_finder/
│   ├── matcher.py
│   ├── budget.py
│   ├── proposal.py
│   ├── sources/ (6 conectores)
│   ├── data/ (5 caches JSON)
│   └── tests/ (48 testes)
├── i18n/
│   ├── translator.py
│   ├── detector.py
│   ├── translations/ (4 idiomas)
│   └── tests/ (31 testes)
├── pesquisai/
│   └── launch_app_responsive.py  ← NOVO
└── docs/
    ├── MOBILE_RESPONSIVE_PATCH.md
    └── ENTREGAS_JUNHO_2026.md
```

###  Estatísticas

| Métrica | Valor |
|---|---|
| Arquivos criados | 53 |
| Linhas de código Python | ~2.800 |
| Linhas de documentação | ~1.500 |
| Linhas de JSON (translations + cache) | ~800 |
| Funções públicas | 30+ |
| Classes (dataclasses) | 14 |
| Agências de fomento | 13 |
| Idiomas | 4 |
| Testes | 79 |
| Cobertura estimada | >85% |

---

## [0.3.0] — 2026-06-20 — (Reservado / Não publicado)

Versão reservada para próximos desenvolvimentos.


## v0.2.3 (2026-06-18) — Backup Integrity Fix

### Bug Crítico: Backups Quebrados (corrupção intermitente)
- **Causa raiz identificada**: Google Drive FUSE trunca a escrita em limites de buffer interno (64KB/256KB/512KB) mas `os.path.getsize()` reporta o tamanho alvo (metadata cache adiantada). Resultado: arquivo corrompido passa pela validação de tamanho mas JSON está truncado no meio de uma string.
- **`launch_app.py /api/backup` (corrigido)**:
  - **Validação JSON do `/tmp/` ANTES de copiar** (rejeita se `opencode export` gerar truncado)
  - **Validação JSON lendo de VOLTA do Drive** após `shutil.copy2()` — detecta truncamento FUSE mesmo quando `getsize` reporta tamanho certo
  - **`os.fsync()` + `os.sync()`** no arquivo destino para forçar sincronização FUSE antes de verificar
  - **Backoff exponencial** entre tentativas (0.8s, 1.3s, 1.8s) em vez de fixo 0.5s
  - **Lock de arquivo** (`fcntl.flock`) em `.backup.lock` para impedir concorrência entre cliques rápidos
  - **Heurística potência-de-2** como alerta diagnostico (log warning se tamanho for 2^N)
  - Resposta agora inclui `"validated": true` confirmando integridade
- **`launch_app.py /api/restore` (corrigido)**: valida JSON do backup ANTES de copiar para `/tmp/` e importar (antes só checava `size >= 100`). Detecta backups corrompidos e sugere remover + gerar novo. Mensagem de erro menciona truncamento FUSE se tamanho for potência de 2.
- **`tests/test_launch_app.py`**: 4 novos testes em `TestBackupIntegrity` (JSON válido detectado, truncamento 64KB detectado, truncamento 256KB detectado, `fcntl.flock` disponível)

### Cobertura
- **192 testes** (antes: 188 → agora: 192, +4 novos de integridade)

## v0.2.2 (2026-06-18) — Stable Base Integration + Novas Funcionalidades

###   Cobertura de Testes (FASE 2 — refeita)
- **188 testes** (antes: 103 → agora: 188, +85 novos)
- **Cobertura total: 29% → 57%**
- **`tests/test_security.py`** (79 testes): criptografia round-trip (9), `_FernetFallback` XOR (7: roundtrip raw/base64/string key, chave errada, HMAC corrompido, token curto), geração de chaves (3), save/load (7), migração old→new (6: keyfile/keysfile nomes antigos vs novos), `_load_or_create_encryption_key` (3), sanitização válidos (15), injection bloqueados (20), edge cases (6), `_check_injection` direto (4)
- **`tests/test_launch_app.py`** (25 testes): funções puras (set_drive_info, load_keys, sanitize integrado), `create_wrapper_html` (4 features, URLs, providers, botões), **servidor HTTP real** com 13 endpoints testados: `/api/health` (2), `/api/theme` GET/POST (4, incluindo inválido), `/api/backups` (2), `/api/apikey` GET/POST (4), `/api/run_terminal` (3: válido, malicioso 403, vazio 400), `/api/apikey/apply` (1)
- **`tests/test_run_fast.py`** (NOVO, 16 testes): `_check_bin` (5: existente, ausente, path customizado), `_run` (3: echo, false, capture), `_clone_or_pull` (4: clone novo, falha, pull existente, pull falha→clone), `SKILL_REGISTRY` consistência (4)
- **`tests/test_opencode_utils.py`** (refeito, 19 testes): `find_opencode` (7: cache, env, env inexistente, which, candidato, search, não encontrado), `ensure_opencode_in_path` (2), `build_env` (5), `_search` (3) — **cobertura 30% → 100%**
- **`tests/test_progress_bar.py`** (refeito, 22 testes): `_html` (10: básico, percentual, zero total, step negativo, >100%, spinner, cor, último estágio, além dos estágios), `show` modo terminal (3), `show` modo Colab (2: cria/atualiza handle), `finish` (3) — **cobertura 51% → 92%**
- **`tests/test_version_sync.py`** (5 testes): `__version__` == `constants` == `pyproject` == `Dockerfile`, semver, CHANGELOG

| Módulo | Cobertura antes | Cobertura agora |
|--------|----------------|-----------------|
| `opencode_utils.py` | 30% | **100%** |
| `progress_bar.py` | 51% | **92%** |
| `security.py` | 62% | **79%** |
| `launch_app.py` | 9% | **45%** |
| `run_fast.py` | 0% | **22%** |
| `constants.py` | 100% | 100% |
| `jokes.py` | 100% | 100% |
| **TOTAL** | **29%** | **57%** |

###  Bugs Corrigidos (detectados pela FASE 2)
- **`security.py` _FernetFallback XOR**: `encrypt` modificava o iv (`b"XOR" + iv[3:]`) APÓS computar o xor_key, mas `decrypt` usava o iv modificado para recomputar o xor_key → chaves diferentes → roundtrip impossível. Corrigido: iv não é mais modificado (o version byte 0x81 já indica XOR)
- **`security.py:556`**: `opencode -s <session_id>` com caracteres inválidos (espaço, etc.) passava pela sanitização porque o prefixo genérico `"opencode"` validava antes do bloco específico. Agora o bloco `opencode -s` valida explicitamente o session_id (apenas alfanuméricos + `_-.`)
- **`launch_app.py:1441`**: segunda sanitização (`sanitize_command(bash_cmd)`) pegava o `;` que o próprio código adicionava (`f"{cmd}; exec bash"`), bloqueando TODOS os comandos via `/api/run_terminal` com erro 500. Corrigido: segunda sanitização removida (o comando do usuário já foi validado; o sufixo `; exec bash` é controlado pelo código)

###  Novas Funcionalidades (FASE 3)
- **3.2 Dashboard de Saúde**: endpoint `GET /api/health` consolidando `/api/diagnose` + `/api/debug`; botão 🩺 na topbar abre modal com checklist visual (Drive montado, ttyd ativo, OpenCode encontrado, keys carregadas, skills instaladas, ffmpeg, espaço em disco, versão)
- **3.3 Busca/Histórico de Sessões**: botão 📜 na topbar abre modal listando sessões (via `/api/sessions` existente); campo de busca filtra por id/conteúdo em tempo real; botão "abrir" por sessão reinicia terminal com `opencode -s <id>`
- **3.6 Atalhos de Teclado Visíveis**: botão ⌨️ na topbar + tecla `?` abrem modal com 8 atalhos (Ctrl+Shift+C copiar, Ctrl+C interromper, Ctrl+L limpar, Ctrl+Shift+V colar, Tab autocompletar, ↑↓ histórico, ? este painel); `Esc` fecha todos os modais
- **3.8 Tema Claro (acessibilidade)**: `pesquisai-light.json` gerado em `run_fast.py` (paleta clara #f5f6f7/#0288d1); toggle ◑ na topbar persiste em `tui.json` via `POST /api/theme`; `GET /api/theme` retorna tema atual; CSS vars do wrapper atualizadas dinamicamente; tema carregado no startup

###  Integração com Base Estável
- **Docs sincronizadas do GitHub estável (v0.2)**: AGENTS.md, README.md, MANUAL.md, PesquisAI.ipynb, LICENSE, citacao_pesquisai.md, declaracao_uso_ia.md, disclaimer_pesquisai.md, IntructionsCEO_paperclip.md
- **Versão atualizada em todas as docs**: v0.2 → v0.2.1 (16 referências em 7 arquivos)
- **`pyproject.toml`**: `readme = "README.md"` re-adicionado; LICENSE, AGENTS.md, MANUAL.md incluídos no build

###  Package (continuação FASE 1)
- **`pesquisai/`**: módulos movidos para package real (git mv preservando histórico)
- **`__init__.py`**: criado como entry-point do package
- **Imports relativos**: `.constants`, `.__version__`, `.jokes`, `.progress_bar`, `.opencode_utils`, `.security`
- **`main.py`**: entry-point atualizado para `from pesquisai.run_fast import run`
- **Testes**: imports atualizados para `pesquisai.X` + strings `@patch` corrigidas
- **`Dockerfile`**: CMD aponta para `pesquisai.run_fast`

###  Bugs Corrigidos (FASE 1)
- **Bug 1.1**: `test_constants.py` assert versão aceita X.Y e X.Y.Z (antes só X.Y)
- **Bug 1.2**: `launch_app.py` logo `v0.2` hardcodeado → `v{VERSION}` dinâmico
- **Bug 1.3**: `Dockerfile` version `0.2` → `0.2.1`
- **Bug 1.5**: `.coverage` removido do git + `.gitignore`
- **Bug 1.6**: `launch_app.install_ttyd` `shell=True` → lista de args
- **Bug 1.7**: `run_fast._install_system_deps`/`_install_python_deps` `shell=True` → args

## v0.2.1 (2026-06-16) — Secure Keys

###  Segurança (Novo)
- **`security.py`**: Módulo de segurança completo com:
  - Criptografia AES-128-CBC + HMAC-SHA256 via Fernet (`cryptography`) para chaves de API
  - Fallback seguro para ambientes sem `cryptography`
  - Geração e gerenciamento de chave de criptografia no Google Drive (`.keys_encryption_key`)
  - Sanitização de comandos com whitelist de prefixos e bloqueio de injection (`; & | \` $() ${} > < \0`)
  - `save_encrypted_keys()` / `load_encrypted_keys()` — salvamento e carga criptografados
  - `sanitize_command()` — validação de comandos com 18 cenários de teste
- **`launch_app.py`**: Endpoint `/api/run_terminal` agora usa `sanitize_command()` antes de executar (bloqueia command injection)
- **`launch_app.py`**: `POST /api/apikey` salva chaves CRIPTOGRAFADAS (não mais em texto puro)
- **`launch_app.py`**: `GET /api/apikey` descriptografa e mascara valores (exibe só 4 primeiros caracteres)
- **`launch_app.py`**: `kill_previous()` e `start_ttyd` migrados de `shell=True` para lista de argumentos
- **`launch_app.py`**: Chave de criptografia armazenada em arquivo SEPARADO (`.keys_encryption_key`) — defesa em profundidade

###  Versão Centralizada
- **`__version__.py`**: Novo arquivo como fonte ÚNICA para versão, autor, repositório, licença
- **`constants.py`**: `VERSION` agora importa de `__version__` (antes era string hardcoded)
- **`pyproject.toml`**: Versão sincronizada com `__version__.py`; adicionada dependência `cryptography>=41.0`
- **`pyproject.toml`**: Seção `[project.optional-dependencies]` adicionada com `crypto = ["pycryptodome>=3.20"]`
- **`run_fast.py`**: Instala `cryptography` durante `_install_python_deps()`
- **Testes automatizados**: 18 testes de sanitização, testes de ciclo completo de criptografia

### Correções de Bugs
- **`constants.py`**: Versão unificada para `VERSION = "0.2"` (estava `"1.0"` — inconsistente com o resto do projeto)
- **`progress_bar.py`**: Correção do bug na declaração de `IN_COLAB` — agora a variável é corretamente detectada via import do IPython

### Qualidade de Código
- **`pyproject.toml`**: Build backend modernizado para `hatchling` (substitui `setuptools.backends._legacy`)
- **Type hints**: Adicionados em `constants.py`, `opencode_utils.py`, `progress_bar.py`, `run_fast.py` e funções principais de `launch_app.py`
- **Configuração Ruff**: Linter e formatador configurados no `pyproject.toml`
- **Configuração Mypy**: Type checker configurado para validação opcional

### CI/CD
- **`.github/workflows/ci.yml`**: Pipeline de integração contínua com 3 jobs:
  - Lint (Ruff) + Format check + Type check (Mypy)
  - Testes (pytest + coverage) em Python 3.10, 3.11, 3.12
  - Gate de qualidade: testes só rodam se lint passar

### Testes
- **`tests/`**: Estrutura de testes com pytest criada (3 suites iniciais):
  - `test_constants.py` — 12 testes: versão, autor, skills, portas, consistência pyproject.toml
  - `test_jokes.py` — 9 testes: categorias, rotação, fallback, 10 piadas por categoria
  - `test_progress_bar.py` — 7 testes: HTML, estágios, cores, edge cases
  - `test_opencode_utils.py` — 3 testes: candidatos, busca, fallback

### Arquitetura
- **`constants.py`**: Skills centralizadas em `SKILL_REGISTRY` com flag `requerida` para fallback inteligente
- **`constants.py`**: `ESSENTIAL_SKILLS` como conjunto derivado para validação
- **`run_fast.py`**: Importa `SKILL_REGISTRY` e `ESSENTIAL_SKILLS` de `constants.py` (antes estava hardcoded)

### Segurança
- **`SECURITY.md`**: Política de segurança, reporte de vulnerabilidades e boas práticas

### Deploy
- **`Dockerfile`**: Imagem Docker para execução local (fora do Colab)

### Infraestrutura
- **`.gitignore`**: Aprimorado com entradas para Python, IDE, OpenCode, Colab, cache
- **`pyproject.toml`**: Seções `[project.optional-dependencies]` para `dev` e `test`

## v0.2 (2026-06-10)

### Otimizações de Performance
- Clonagem de skills paralelizada com `ThreadPoolExecutor(max_workers=8)` — 8 repositórios clonados simultaneamente
- Cache de repositórios: skills já em `/tmp/` fazem `git pull --depth 1 --ff-only` em vez de clonar do zero
- `--single-branch --depth 1` em todos os clones (baixa só o branch padrão)
- Detecção de binários existentes: pula opencode, uv, ttyd se já instalados
- `apt-get update` executado uma única vez (antes rodava em duas etapas separadas)
- `pip install` com `--no-cache-dir` para evitar overhead de cache
- `_check_bin()` aprimorado: busca também em `~/.local/bin`, `~/.npm-global/bin`, `~/.opencode/bin`

### Correções
- **Item 2** — Versão do AGENTS.md corrigida de `v0.01` para `v0.2`
- **Item 4** — `.gitignore` criado com `__pycache__/`, `*.pyc`, `*.pyo`, etc.
- **Item 6** — Numeração duplicada no MANUAL.md corrigida (seção `## 1. Primeiros Passos` removida; seções 1–10 renumeradas)
- **Item 7** — Lógica de carregamento de chaves extraída para `load_keys_from_drive()`, eliminando 3 ocorrências duplicadas

### Interface
- **Item 30** — Barra de progresso com `display_id=True` (sem acumular HTML)
- `clear_output(wait=True)` ao final para limpar textos de setup, restando apenas o botão de launch
- `show_ready_message()` e `show_launch_button()` reexibidos após limpeza
- `Ctrl+Shift+C` no ttyd para copiar (atalho padrão, funciona no Chrome)
- `Ctrl+C` mantém SIGINT (interromper comandos)
- Footer alterado para "UFV · Viçosa, MG - Brasil"

### Provedores
- Lista de provedores ordenada alfabeticamente
- Adicionados **OpenCode Zen** (`OPENCODE_ZEN_API_KEY`) e **OpenCode Go** (`OPENCODE_GO_API_KEY`)

### Registro SisPPG/UFV
- Badge SisPPG com nº **10356285004** adicionado ao README
- Citações ABNT atualizadas com nº de registro em README, MANUAL, citacao_pesquisai, declaracao_uso_ia
- Rodapé do AGENTS.md com nº SisPPG
- Notebooks atualizados com citação e badge
- URL corrigida: `https://www.sisppg.ufv.br` → `http://sisppg.ufv.br`

### Notebook
- Loading animado via `IPython.display`
- Repositório usa `git pull` se já existe (não recria toda execução)
- `clear_output()` antes de rodar (interface mais limpa)
- Markdown simplificado e reorganizado

### Arquivos Novos
- `run_fast.py` — Versão otimizada com paralelismo e cache, substitui o fluxo do `main.py`
- `CHANGELOG.md` — Este arquivo
- `SisPPG - Sistema de Pesquisa e Pós-Graduação.pdf` — Comprovante de registro

### Integridade de Referências
- AGENTS.md — Nova seção `3.1 Sub-fluxo de Verificação de Referências` com 4 subpassos (rastreamento, confirmação de 3 campos, link/DOI obrigatório, inclusão) e regra de ouro contra fabricação
- `run_fast.py` — Descrição do agente atualizada para incluir "verificação obrigatória de referências"

### Alterações em Arquivos Existentes
- `AGENTS.md` — Versão `v0.01` → `v0.2`; seção 3.1 adicionada
- `.gitignore` — Criado
- `MANUAL.md` — Numeração corrigida + citações com SisPPG
- `launch_app.py` — Função `load_keys_from_drive()` extraída; provedores ordenados + Zen/Go
- `progress_bar.py` — `finish()` com `clear_output(wait=True)`
- `main.py` — Simplificado para delegar a `run_fast.py`
- `README.md` — Badge SisPPG + citação atualizada
- `citacao_pesquisai.md` — Citação com SisPPG
- `declaracao_uso_ia.md` — Citação com SisPPG
- `PesquisAI.ipynb` — Loading animado, git pull, markdown simplificado
- `PesquisAI_Colab.ipynb` — Badge SisPPG

## v0.001 (2026-06-10)

### Funções Iniciais
- **setup_drive.py** — Montagem do Google Drive, autenticação Google API, criação do diretório de trabalho
- **setup_dependencies.py** — Instalação do opencode (curl/pip/npm), uv, xclip/xsel, tema e agente
- **setup_skills.py** — Clonagem sequencial de 8 skills (ibge, datasus, scientific, pesquisai, ufv-abnt, qualitativa, dados-brasil, agrobr)
- **launch_app.py** — Instalação do ttyd, servidor web wrapper com backup/restore de sessão e gerenciamento de provedores de IA
- **main.py** — Orquestrador chamando drive → dependências → skills → launch
- **constants.py** — Constantes de caminhos e configuração
- **opencode_utils.py** — Busca do binário opencode e construção de environment
- **jokes.py** — Piagens temáticas exibidas durante o loading
- **PesquisAI.ipynb** — Notebook Colab principal
- Fluxo sequencial de inicialização (sem paralelismo)
- Numeração duplicada no MANUAL.md
- Código duplicado de carregamento de chaves em 3 locais
- Sem barra de progresso
- Sem `.gitignore`
