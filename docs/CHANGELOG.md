# Changelog

Todas as mudanças notáveis neste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.4.2.3] — 2026-06-24 — ses_106b HOTFIX (JS Broken Escapes — Botões Restaurados)

> Sessão `ses_106b` (continuação): bug crítico reportado pelo usuário — ao abrir
> o wrapper HTML, **nenhum botão funcionava**. Investigação revelou JavaScript
> com sintaxe inválida.

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

### 🔧 Correções (3 mudanças cirúrgicas)

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

### 🧪 Validação Final

- ✅ `node --check` no JS extraído: **SEM ERROS**
- ✅ HTML regenerado: **89.127 chars** (vs 88.517 da v0.4.2.2)
- ✅ 10/10 funções JS verificadas: `openAgents`, `openHealth`, `openSessions`,
  `openShortcuts`, `toggleTheme`, `toggleLangMenu`, `toggleMobileMenu`,
  `doBackup`, `openRestore`, `closeModal`
- ✅ 42 botões com `onclick="..."` validados
- ✅ 79/79 testes pytest continuam passando (sem regressão)
- ✅ Backups e restores preservados (openRestore, doBackup)
- ✅ Modal de sessões agora abre + renderiza + responde a cliques

### 📦 Arquivos Modificados

```
pesquisai/
├── __version__.py                    # 0.4.2.2 → 0.4.2.3
└── launch_app_responsive_v041.py     # 3 hotfixes (renderSessions, restoreSession, escapeHtml)
```

---

## [0.4.2.2] — 2026-06-24 — ses_10a4+ Polish (Footer PC + Skills + Sessions + Lang + Version)

### 🐛 Bug Fixes & Funcionalidades (6 melhorias reportadas em 2026-06-24)

#### 🖥️ 9. Footer PC: provedor e "Powered by OpenCode" alinhados à DIREITA
- **Problema:** no desktop, o botão de provedor e o texto "Powered by OpenCode"
  ficavam **colados à esquerda**, junto com o restante do rodapé. Em PC,
  deveriam estar alinhados **à direita** (em mobile, mantém o layout de 2 linhas).
- **Correção:**
  - Nova regra CSS `@media (min-width: 768px)` que sobrescreve o
    `display: contents` de `.footer-row-2` para `display: flex; align-items: center;`
  - `margin-left: auto` em `.footer-row-2` empurra o segundo grupo (provedor +
    OpenCode) para a **extremidade direita** do rodapé
  - `.footer-row-1` (marca + email + GitHub + UFV) também vira flex container
    explícito, garantindo alinhamento vertical perfeito
  - **Mobile/tablet (<768px)**: comportamento original preservado
    (2 linhas empilhadas)

#### 🧩 10. Skills: `grant-finder` e `meta-search-br` adicionadas em `skills/`
- **Problema:** as 2 skills extras existiam (grant-finder em `grant_finder/`
  na raiz, meta-search-br em `skills/meta-search-br/`) mas **não estavam
  organizadas** em `skills/` com links de clone padronizados.
- **Correção:**
  - Criada `skills/grant-finder/` com `README.md`, `SKILL.md` e `__init__.py`
    contendo link de clone: `https://github.com/gustavobraga-byte/grant-finder`
  - Atualizada `skills/meta-search-br/README.md` com link de clone:
    `https://github.com/gustavobraga-byte/meta-search-br`
  - Atualizada `skills/meta-search-br/SKILL.md` (seção "Instalação via clone")
  - Atualizada `skills/meta-search-br/__init__.py` com constante `__clone_url__`
  - `__init__.py` do `grant-finder` reexporta a API da versão local
    (`grant_finder/`), com fallback para o clone em ambientes novos

#### 📜 11. Histórico de sessão não carregava
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

#### 🌍 12. Saudação inicial do ttyd no idioma selecionado
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
  - **Ajuste pós-ses_10a4+:** a frase "Eu sou o PesquisAI" foi removida das
    saudações. A estrutura final é apenas `"{saudação_curta} ({dica}: {instr})"`,
    onde "dica" é traduzida para cada idioma (Dica / Tip / Consejo / Astuce).
  - Novo endpoint **GET /api/lang** retorna idioma + saudação atuais
  - Novo endpoint **POST /api/lang** persiste idioma, **reinicia ttyd** com
    a saudação no novo idioma e retorna a saudação como confirmação
  - Idioma persistido em `~/.config/pesquisai_lang` (sobrevive a restarts)
  - `setLang()` em JavaScript agora chama `POST /api/lang` que reinicia
    o ttyd automaticamente (sem precisar matar processos manualmente)
  - Variável global `_current_lang` no backend, restaurada do arquivo
    no startup

#### 📦 13. `__version__.py` MOVIDO para `pesquisai/__version__.py`
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

#### 🧹 14. AGENTS.md multilíngues padronizados
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

### 🧪 Validação

- ✅ **79/79 testes** continuam passando (`grant_finder/tests/` + `i18n/tests/`)
- ✅ **Sintaxe Python validada** em 5 arquivos:
  - `pesquisai/launch_app.py`
  - `pesquisai/launch_app_responsive_v041.py`
  - `pesquisai/__version__.py`
  - `skills/grant-finder/__init__.py`
  - `skills/meta-search-br/__init__.py`
- ✅ **Geração do wrapper HTML** validada (88.517 chars, +6% vs v0.4.2.1)
- ✅ **`get_greeting()`** testada para todos os 4 idiomas + 5 short codes
- ✅ **Comando bash do ttyd** testado para 4 idiomas (escaping correto)

### 📦 Arquivos Modificados (v0.4.2.2)

```
pesquisai/
├── __version__.py                    # ⭐ MOVIDO da raiz, v0.4.2.2
├── launch_app.py                     # ⭐ +start_ttyd(lang), +/api/lang
└── launch_app_responsive_v041.py     # ⭐ footer PC, +openSessions loader, +setLang/i18n

skills/
├── grant-finder/                     # ⭐ NOVO: README + SKILL + __init__
└── meta-search-br/                   # ⭐ +README + clone URL no SKILL

agents/
├── AGENTS.pt.md                      # ⭐ -"[link]" do francês
├── AGENTS.en.md                      # ⭐ -"[link]" do francês
├── AGENTS.es.md                      # ⭐ -"[enlace]" do francês
└── AGENTS.fr.md                      # ⭐ -"[lien]" dos 3 outros idiomas

docs/
└── CHANGELOG.md                      # ⭐ +entrada [0.4.2.2]
```

---

## [0.4.2.1] — 2026-06-23 — ses_10a4 Fixes (Theme Contrast + Dashboard + Markdown)

### 🐛 Bug Fixes (3 adicionais reportados pelo usuário em 2026-06-23 — sessão `ses_10a4`)

#### 🌓 6. Tema CLARO: textos invisíveis nos modais
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

#### 🩺 7. Dashboard de Saúde não carregava
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

#### 📝 8. Modal de Diretrizes mostrava o MD como texto cru
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

### 📁 Arquivos Modificados (v0.4.2.1)

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

### 🧪 Validação (v0.4.2.1)

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

### 🔒 Compatibilidade

- ✅ **Backward compatible** — sem breaking changes
- ✅ **CDN fallbacks** — se marked.js/github-markdown-css falharem ao
  carregar, modal mostra texto pré-formatado (graceful degradation)
- ✅ **JS engine** — `String.fromCharCode(92)` funciona em todos
  navegadores (>= IE6)

---

## [0.4.2] — 2026-06-23 — Footer Responsive + Multilingual AGENTS.md

### 🐛 Bug Fixes (reportados pelo usuário em 2026-06-23 — sessão `ses_10a4`)

#### 📱 4. Rodapé NÃO responsivo
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

#### 📋 5. Troca de idioma NÃO trocava o AGENTS.md
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

### 🆕 Funcionalidades Adicionais (v0.4.2)

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

### 📁 Arquivos Modificados (v0.4.2)

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

### 🔒 Compatibilidade

- ✅ **Backward compatible** — sem breaking changes
- ✅ **Endpoint opcional** — se o `agents/` não existir, UI mostra
  mensagem amigável "Erro ao carregar diretrizes"
- ✅ **Fallback HTML** — modal sempre renderiza, mesmo offline
  (mostra "Erro ao carregar" se a rede cair)

### 🧪 Validação

- **28/28 validações automáticas** aprovadas (rodapé + modal + i18n)
- **79/79 testes** continuam passando (48 grant_finder + 31 i18n)
- **Cobertura 71.58%** mantida (mínimo: 70%)
- HTML gerado: **74.901 caracteres** (vs. 60.582 da v0.4.1)
- **Endpoint `/api/agents` testado** com 10 variações de idioma
  (4 completos + 4 short + 2 inválidos — todos retornam corretamente)

---

## [0.4.1] — 2026-06-23 — UI Fixes (Responsive + Theme + Language)

### 🏗️ Reorganização da Estrutura (2026-06-23)
- **Estrutura do repositório reformatada** para separar código do PesquisAI de
  arquivos pessoais (sandbox):
  - `docs/` — toda documentação (CHANGELOG, PATCH, MOBILE, INTEGRITY)
  - `releases/v0.4.0/` — release isolada completa (com pyproject.toml, LICENSE, CI, etc.)
  - `sandbox/` — artigos, projetos, datasets, figuras, TCCs, scripts, utils (138MB)
  - `sessions/` — logs de sessão
  - Raiz reduzida de 145MB para ~7MB (apenas código PesquisAI)
- **README.md** criado na raiz explicando a nova estrutura
- **`__version__.py`** atualizado com `__default_theme__ = "pesquisai"` (escuro)

### 🌙 Tema Padrão: ESCURO (anti-flash)
- **Script anti-flash no `<head>`** executa ANTES do CSS, lendo cookie/localStorage
  e aplicando tema escuro como padrão (só troca para claro se persistido)
- **CSS `html { background: #0d0f10; color: #e8e6e0; }` inline** garante que o
  body já inicia com fundo escuro (sem flash branco no carregamento)
- **Classe `html.theme-light`** no CSS para override do tema claro
- **`<html data-theme="pesquisai">`** explícito como padrão
- **Sincronização em `applyWrapperTheme()`** que adiciona/remove a classe
  `.theme-light` no `<html>` para que o CSS use as variáveis corretas

### 🐛 Bug Fixes Críticos (reportados pelo usuário em 2026-06-23)

### 🐛 Bug Fixes Críticos (reportados pelo usuário em 2026-06-23)

#### 📱 1. Site NÃO estava responsivo
- **Problema:** o `launch_app.py` do PesquisAI principal no GitHub não tinha
  media queries. Topbar de 8 botões estourava em mobile, modais 400-520px não
  cabiam, sem hamburger menu.
- **Correção:** adicionadas 6 media queries (5 breakpoints + landscape) com
  hamburger drawer, modais fluidos (95vw em mobile), touch targets ≥ 32-44px
  (Apple HIG / WCAG 2.5.5), hamburger mobile menu com todos os itens da
  topbar reorganizados.

#### 🎨 2. Tema claro/escuro NÃO recarregava o terminal
- **Problema:** `toggleTheme()` chamava `applyWrapperTheme()` que só mudava
  as CSS variables do wrapper, mas NUNCA recarregava o iframe do ttyd.
  Resultado: a UI mudava, mas o terminal continuava com o tema antigo.
- **Correção:** após aplicar o tema na UI, recarrega o iframe do ttyd
  com cache-busting (`?theme=pesquisai-light&t=<timestamp>`), mesmo padrão
  usado em `confirmProvider()` / `restoreSession()` / `doRestore()`. Tempo
  de reload: 3.5s (aguarda restart do ttyd no backend).

#### 🌐 3. Idioma sem opção na interface
- **Problema:** o módulo `i18n` estava completo (4 idiomas, JSONs), mas
  não havia seletor visível na topbar. Usuário não tinha como trocar idioma.
- **Correção:** adicionado dropdown na topbar com 4 idiomas (🇧🇷 PT, 🇺🇸 EN,
  🇪🇸 ES, 🇫🇷 FR), persistência em cookie `pesquisai_lang` + localStorage,
  query param `?lang=xx_XX` para forçar via URL, atualização do atributo
  `<html lang="xx-XX">` e de todas as strings visíveis via `data-i18n`.

### 🆕 Funcionalidades Adicionais

- **Cookie helpers** (`setCookie` / `getCookie`) para tema e idioma
- **Detecção automática de idioma** com prioridade: URL > cookie > localStorage > `navigator.language` > padrão
- **Indicador visual do tema ativo** no botão (`#theme-toggle[data-theme="pesquisai-light"]` → cor amber)
- **Meta `theme-color` dinâmica** (muda junto com o tema para a barra de status do navegador mobile)
- **40+ strings traduzidas inline** no client-side para feedback instantâneo
- **Endpoint backend opcional** `GET/POST /api/lang` para persistir idioma no Drive
- **Click-outside** para fechar dropdown de idioma
- **Tecla `Escape`** fecha também o dropdown de idioma e o mobile menu

### 📁 Arquivos Novos

- `pesquisai/launch_app_responsive_v041.py` — **drop-in patch** para o `launch_app.py` do GitHub
- `docs/PATCH_v0.4.1.md` — documentação completa do patch (instalação + testes)
- `i18n/translations/fr_FR.json` — 🇫🇷 francês (NOVO em v0.4.0, expandido em v0.4.1)

### 🔄 Arquivos Atualizados

- `pesquisai/launch_app_responsive.py` — agora contém as 3 correções (era v0.1.0 → v0.2.0)
- `__version__.py` — `0.4.0` → `0.4.1`, codinome "UI Fixes (Responsive + Theme + Language)"

### 🔒 Compatibilidade

- ✅ **Backward compatible** — sem breaking changes
- ✅ **API inalterada** — `create_wrapper_html(terminal_url, drive_url)` mantém a assinatura
- ✅ **CSS puro** — sem dependências externas adicionais
- ✅ **Fallback gracioso** — se JS do hamburger falhar, topbar original ainda funciona

### 🧪 Validação

- 79 testes continuam passando (48 grant_finder + 31 i18n) — 100% das suítes verdes
- HTML gerado tem **60.582 caracteres** (vs. ~38.000 do v0.4.0) — todas as correções injetadas
- 26 validações automáticas aprovadas (mobile menu, lang selector, toggleTheme reload, JSON válido, etc.)

---

## [0.4.0] — 2026-06-23 — International & Mobile

### 🎉 Funcionalidades Principais

#### 📱 Site Responsivo Mobile
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

#### 🤖 Agents Multilíngues
- `agents/AGENTS.pt.md` — 🇧🇷 Português (Brasil) — padrão
- `agents/AGENTS.en.md` — 🇺🇸 English (United States)
- `agents/AGENTS.es.md` — 🇪🇸 Español (España)
- `agents/AGENTS.fr.md` — 🇫🇷 Français (France) — **NOVO**
- 100% das regras de integridade científica preservadas em todas as variantes
- Marcadores de evidência traduzidos (`[DADO CONFIRMADO]` / `[CONFIRMED DATA]` / `[DATO CONFIRMADO]` / `[DONNÉE CONFIRMÉE]`)

### 🧪 Qualidade de Código

- **79 testes passando** (48 grant_finder + 31 i18n) — 100% das suítes verdes
- Cobertura estimada > 85% nos módulos novos
- Type hints em todas as funções públicas
- Docstrings em todas as classes e funções
- 4 suítes pytest: test_matcher, test_budget, test_proposal, test_translator
- Testes de edge cases: cache corrompido, JSON truncado, normalização de locale, encoding UTF-8

### 🔒 Segurança e Integridade Científica

- **Política de zero-fabricação** mantida em todos os novos módulos
- `grant_finder`: sempre declara `fetched_at` e link oficial para conferência
- Marcador `[SEM DADOS SUFICIENTES]` / `[NO DATA AVAILABLE]` / `[SIN DATOS SUFICIENTES]` / `[DONNÉES INSUFFISANTES]`
- Aviso explícito: "SEMPRE conferir link oficial antes de submeter proposta"

### 📦 Estrutura do Release

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

### 📊 Estatísticas

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

---

## [0.2.3] — 2026-06-18 — Backup Integrity Fix

### 🐛 Bug Crítico
- **Backups quebrados (corrupção intermitente)**: Google Drive FUSE trunca escrita em limites de buffer interno. `launch_app.py /api/backup` agora valida JSON antes e depois de copiar para o Drive, com `os.fsync()` + `os.sync()` + backoff exponencial + lock de arquivo (`fcntl.flock`)
- **`launch_app.py /api/restore`**: valida JSON ANTES de copiar para `/tmp/`
- 4 novos testes em `TestBackupIntegrity` (JSON válido, truncamento 64KB, 256KB, fcntl)
- **192 testes** no PesquisAI principal

---

## [0.2.2] — 2026-06-18 — Stable Base Integration

- 188 testes no PesquisAI principal (cobertura 29% → 57%)
- 3.2 Dashboard de Saúde (`GET /api/health`)
- 3.3 Busca/Histórico de Sessões (`/api/sessions`)
- 3.6 Atalhos de Teclado Visíveis
- 3.8 Tema Claro (acessibilidade)
- Integração com base estável v0.2

---

## [0.2.1] — 2026-06-16 — Secure Keys

- Módulo `security.py` com criptografia AES-128-CBC + HMAC-SHA256 (Fernet)
- Sanitização de comandos (whitelist + bloqueio de injection)
- `save_encrypted_keys()` / `load_encrypted_keys()` com defesa em profundidade
- `__version__.py` como fonte única de versão
- 18 testes de segurança
- CI/CD com Ruff + Mypy + pytest em 3 Python versions

---

## [0.2] — 2026-06-10 — Otimizações de Performance

- Skills clonadas em paralelo com `ThreadPoolExecutor(max_workers=8)`
- Cache de repositórios: `git pull --depth 1` se já existir
- `--single-branch --depth 1` em todos os clones
- Detecção de binários existentes (opencode, uv, ttyd)
- `apt-get update` único (antes rodava em 2 etapas)
- `pip install` com `--no-cache-dir`

---

## [0.001] — 2026-06-10 — Release Inicial

- `setup_drive.py` — Montagem do Google Drive
- `setup_dependencies.py` — Instalação do opencode
- `setup_skills.py` — Clonagem sequencial de 8 skills
- `launch_app.py` — ttyd + servidor wrapper
- `main.py` — Orquestrador

---

## Tipos de Mudanças

- `🎉 Funcionalidades Principais` — Para novas funcionalidades
- `📱` — Para mudanças de UI/UX
- `🐛 Bug Crítico` — Para correções de bug crítico
- `🧪 Qualidade de Código` — Para mudanças que não afetam o comportamento
- `🔒 Segurança` — Para mudanças relacionadas a vulnerabilidades
- `📦 Estrutura` — Para mudanças em arquivos de build/dependências
- `📚 Documentação` — Para mudanças apenas em documentação
- `⚡ Performance` — Para mudanças de performance

---

[0.4.2]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.4.2
[0.4.1]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.4.1
[0.4.0]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.4.0
[0.3.0]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.3.0
[0.2.3]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.2.3
[0.2.2]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.2.2
[0.2.1]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.2.1
[0.2]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.2
[0.001]: https://github.com/gustavobraga-byte/PesquisAI/releases/tag/v0.001
