# Changelog — PesquisAI

---
## [0.5.1.9] - 2026-07-18 - Atualização do AGENTS.md

### 🚀 Major Changes

- **Reescrita completa do AGENTS.md**: Principal atualização desde a introdução da memória persistente. O documento foi reformulado do zero para maior clareza, consistência normativa, economia de tokens e alinhamento com o código-fonte (`constants.SKILL_REGISTRY`).
- **Nova arquitetura de diretórios**: Introduzida separação oficial entre `vault/` (memória interna do agente) e `outputs-<slug-do-projeto>/` (entregáveis finais organizados por projeto). Isso melhora organização, reprodutibilidade e experiência do usuário final.
- **Fortalecimento de Integridade e Segurança**: 
  - Protocolo completo de defesa contra prompt injection (ignorar, manter tarefa original e avisar usuário).
  - Proteção explícita contra acesso a arquivos de segredos (`keys_store.json` e `keys_encryption_key.bin`).
  - LGPD com "hard stop": interrupção obrigatória de gravação ao detectar dados sensíveis não anonimizados.

### ✨ Improvements

- **Catálogo de Skills**: Totalmente sincronizado com o registry real. Removidas referências infladas ("147+ skills") e adicionados IDs canônicos (`qualitativa`, `grant-finder`, `memorial`, `obsidian-memory`, `BR-DWGD`, `meta-search-br`).
- **Gestão de Memória**: 
  - Frontmatter enriquecido com `updated`, `accessed_at`, `dataset_version`, `evidence_refs` e `source_language`.
  - Atualização automática e obrigatória de `moc/last-state.md` no fim de sessões/tarefas relevantes.
  - Clarificada a condicionalidade do salvamento (obrigatório apenas quando `PESQUISAI_OBSIDIAN_VAULT` está ativa).
- **Regras de Precedência**: Seção dedicada e expandida, blindando integridade (§4.1), proibições de memória (§2.2.1), injeção de prompt e restrições de path traversal.
- **Geração de Arquivos**: PDF agora obrigatório apenas para entregáveis finais (artigos, memoriais, relatórios). Notas internas não geram mais PDF automaticamente.
- **Declaração de Uso de IA**: Agente agora sugere ativamente a inclusão da declaração em entregas acadêmicas finais.
- **Exemplos e Limitações**: Exemplos positivo/negativo mais robustos (incluindo proibição de URLs falsas). Seção de limitações expandida com "Non-goals" explícitos (pareceres médicos/jurídicos, CEP/CONEP, submissão automática, etc.).

### 🛡️ Security & Compliance

- Fechada brecha que permitia edição de notas humanas via `force=True`.
- LGPD reforçada com recusa explícita mesmo diante de insistência do usuário.
- Proteção contra path traversal e vazamento de segredos criptográficos.

### 📋 Documentation

- AGENTS.md agora funciona como fonte canônica de comportamento do agente em runtime.
- Melhoria significativa na legibilidade e na capacidade de manutenção futura.

### 🔄 Outras Alterações

- Alinhamento entre `AGENTS.md`, `docs/INTEGRITY.md`, `docs/OBSIDIAN_MEMORY_MODEL.md` e o código-fonte.
- Redução estimada de ~18–25% no consumo de tokens do prompt do sistema.
- Preparação para futuras features (Workspace de Projetos, Evidence Ledger e Reprodutibilidade) já contempladas na nova estrutura.


---
## [0.5.1.8] — 2026-07-10 — 🐛 3 bugfixes: provider buttons, session restore, backup confirm

### 🔧 Bugfix 1: Provider edit/delete buttons (SyntaxError)

**Problema:** `JSON.stringify(provider)` dentro de `onclick="..."` em uma string Python `"""..."""` gerava SyntaxError. O interpretador Python consumia as aspas escapadas, produzindo JavaScript inválido.

**Correção:**
- Substituído `onclick="editSavedKey(JSON.stringify(provider))"` por `data-provider="..." onclick="editSavedKey(this.dataset.provider)"`
- Mesmo padrão para `deleteSavedKey`
- Sem `JSON.stringify` inline = sem conflito de escapes com a string tripla do Python

**Arquivo:** `launch_app_responsive_v041.py` — função `renderSavedKeys()`

---

### 🔧 Bugfix 2: Session history não atualiza ttyd

**Problema:** O comando `opencode session restore <sessionId>` restaurava os dados da sessão no disco, mas o servidor sempre iniciava um **opencode novo do zero** após o comando (linha 1600 do `launch_app.py`: `bash_cmd = f"{cmd}; {_opencode_bin}; exec bash"`). O terminal nunca refletia a sessão restaurada.

**Correção:**
- Troca do comando para `opencode -s <sessionId>` com `no_fallback: true`
- `no_fallback: true` elimina o `; {_opencode_bin}` — o opencode já inicia **direto na sessão** restaurada
- `setTimeout(() => location.reload(), 2500)` recarrega a página para conectar ao novo ttyd
- Mesmo padrão do endpoint `/api/restore` (backup)

**Arquivo:** `launch_app_responsive_v041.py` — função `_doRestoreSession()`

---

### ✨ Feature 3: Confirmação antes de restaurar backup

**Problema:** `doRestore(file)` executava a importação do backup imediatamente, sem confirmação do usuário.

**Correção:**
- Toda a lógica de `doRestore()` foi envolvida em `pesquisaiConfirm()`
- Usa chave i18n `ui.restore` para o texto do botão
- Cancelar = não executa nada; Confirmar = importa o backup

**Arquivo:** `launch_app_responsive_v041.py` — função `doRestore()`

---

### 🧩 Nova skill: Memorial UFV

- **Nova skill `skill-memorial-ufv`** — Geração automática do Memorial RSC-PCCTAE (Relatório Detalhado → memorial formatado UFV/ABNT)
- Repositório: [github.com/gustavobraga-byte/Memorial_ufv](https://github.com/gustavobraga-byte/Memorial_ufv)
- Fluxo: lê o PDF do Relatório Detalhado RSC emitido pelo sistema oficial da UFV, extrai dados estruturados, gera narrativas longas em linguagem acadêmico-científica e formata conforme normas UFV/ABNT
- Gera saída em `.md` e `.docx` formatado

---

### 🧩 Alterações adicionais no provider flow

- **NOVO `prov-step0`**: Tela inicial do modal de provedores lista as chaves salvas no Drive com botões editar/excluir, antes de mostrar a lista de provedores para adicionar.
- **NOVO botão "Voltar"**: Navegação `prov-step1 → prov-step0` via `provBack()`.
- **NOVO botão "↻ Atualizar"**: No modal de sessões, recarrega a lista sem fechar.
- **Largura do modal de provedores**: 480px → 520px para acomodar os botões de ação das chaves salvas.

---

## [0.5.1.5] — 2026-07-01 — 🧠 Editor de Memória Obsidian no botão 🧠

> **Nota:** v0.5.1.5 foi um hotfix para v0.5.1.4. As versões 0.5.1.6 e 0.5.1.7 foram patches internos não lançados publicamente.

### 🧠 Editor de Memória (Obsidian Memory Editor)

- **Modal split view**: Lista de notas à esquerda + editor markdown com abas Edit / Preview / Split à direita
- **4 endpoints REST novos:**
  - `GET  /api/obsidian/note?path=...` — ler nota crua
  - `GET  /api/obsidian/tree?subdir=...` — árvore agrupada por subdiretório
  - `GET  /api/obsidian/search?q=...` — busca BM25 com debounce 150ms
  - `GET  /api/obsidian/tags` — lista de tags usadas com contagem
- **POST /api/obsidian/note** com 3 ações:
  - `action=save` — sobrescrever nota (force=true para notas humanas)
  - `action=create` — criar nova nota a partir de template
  - `action=delete` — mover para `.trash/` (force=true para notas humanas)
- **Preview markdown** via `marked.js` com destaque de `[[wikilinks]]` e `#tags`
- **Dirty indicator**: Indicador visual de edição não salva
- **20 novas chaves i18n** (`memory.editor.*`) em pt_BR, en_US, es_ES, fr_FR
- **Bugfix**: `from pathlib import Path` faltava — quebrava `tree` endpoint

### 🔧 Hotfix v0.5.1.5

- Botões do editor não funcionavam (SyntaxError JS em string multilinha) — **corrigido**

---

## [0.5.1.3] — 2026-06-30 — 🔌 Conectores de Provedor de IA

- **Bugfix:** `confirmProvider()` crashava com TypeError antes de salvar a API key
- Captura local de `_selProv.id`/`env`/`name` antes de `closeProvider()`
- Verifica `r.ok` e `d.ok` no fetch (antes: sempre exibia "✅ Salvo!")
- `closeProvider()` movido para após o sucesso do salvamento

---

## [0.5.1.2] — 2026-06-30 — 🧠 Botão Memória Obsidian no topbar

- **Overlay de Memória** mostra status (ready/disabled/...) + stats + notas recentes + daily notes
- **Endpoint**: `GET /api/obsidian` (status da memória persistente)

---

## [0.5.1] — 2026-06-29 — 🤖 Obsidian Autopilot (Salvamento Autônomo)

### 🤖 O agente agora SALVA SOZINHO

- **`pesquisai/obsidian/autopilot.py`** (NOVO) — API de alto nível com funções LLM:
  - `recall(query)` — busca no vault antes de responder
  - `save(title, body, tags)` — salva nota após concluir tarefa
  - `save_finding(text, source)` — captura rápida (1 linha)
  - `start_session()` / `end_session(summary)` — log automático
  - `log_skill(id)` / `log_file(path)` — tracking de atividades
  - `auto_init()` — inicializa vault + daily + MOC + sessão
- **`run_fast.py`** (EDITADO) — chama `auto_init()` na inicialização
- **Prompt do agente** injeta instruções de autopilot
- Vault criado automaticamente em `<DRIVE>/PesquisAI/vault/`
- Daily note e MOC raiz criados automaticamente
- **Tudo é no-op** se o vault não estiver disponível
- **Vault SEMPRE no Google Drive** (validação obrigatória)

---

## [0.5.0] — 2026-06-28 — 🧠 Obsidian Second Brain (Long-Term Memory)

- Módulo `pesquisai.obsidian` (8 arquivos, ~1.500 linhas)
- Skill `obsidian-memory` (repositório git separado)
- 10 templates Obsidian (daily, research, literature, session, methodology, datasource, hypothesis, reference, moc, inbox)
- Memória persistente entre sessões via vault no Google Drive
- Busca BM25 offline + backlinks + wikilinks + tags
- Taxonomia de tags `pesquisai/*` (19 tags oficiais)
- **REGRA:** vault SEMPRE no Google Drive (rejeita fora no Colab)
- 71 testes pytest (100% passing) + teste e2e validado

---

## [0.4.2.3] — 2026-06-27 — 🔥 BUGFIX CRÍTICO — Botões do wrapper quebrados

- **🛑 JS BROKEN:** A string tripla `"""..."""` do `launch_app_responsive_v041.py` continha escapes de aspas que Python removia durante a compilação, gerando JavaScript com sintaxe inválida → **TODOS os botões do HTML paravam de funcionar** (SyntaxError no `<script>`)
- ✅ `renderSessions`: `onclick` inline trocado por `data-session-id` + event delegation
- ✅ `restoreSession`: `confirm(...)` com aspas escapadas trocado por `confirm(...chr(34)...)` (concat JS)
- ✅ `escapeHtml`: object literal com aspas trocado por if/else chain
- ✅ Validado: Node.js `--check` passa, 79/79 testes pytest OK

---

## [0.4.2.2] — 2026-06-24 — Ses_10a4+: 6 correções adicionais

- **🖥️ FOOTER PC:** Botão provedor + "Powered by OpenCode" alinhados à direita no desktop (`margin-left: auto`)
- **🧩 SKILLS:** `grant-finder` e `meta-search-br` em `skills/` com links para clonar do GitHub
- **📜 SESSÕES:** `openSessions()` agora faz fetch em `/api/sessions` e popula a lista
- **🌍 LANG:** Ao trocar idioma, ttyd reinicia com saudação no idioma + instrução persistente
- **📦** `__version__.py` movido para `pesquisai/__version__.py`
- **🧹** AGENTS.md: removido `- [link/lien/enlace]` das 4 variantes

---

## [0.4.2.1] — 2026-06-23 — Ses_10a4: 3 correções

- **Tema CLARO:** Contraste corrigido nos 6 modais (`background:#181b1e` fixo → variável CSS `.modal-shell`)
- **Dashboard de Saúde:** `openHealth()` faz fetch em `/api/health` e popula lista com badges de status
- **Modal de Diretrizes:** Renderiza markdown (marked.js + github-markdown-css) ao invés de texto cru

---

## [0.4.2] — 2026-06-22 — Footer Responsivo + AGENTS.md Multilíngue

- Rodapé 100% responsivo (flex-wrap + 2 linhas)
- Modal de Diretrizes com AGENTS.md multilíngue
- Endpoint `GET /api/agents?lang=xx_XX`

---

## [0.4.1] — 2026-06-20 — UI Fixes (Responsivo + Tema + Idioma)

- 6 media queries + hamburger menu
- `toggleTheme()` recarrega iframe ttyd
- Dropdown 4 idiomas (pt_BR, en_US, es_ES, fr_FR)

---

## [0.4.0] — 2026-06-15 — Release Inicial

Primeira release do PesquisAI com:
- Agente de pesquisa científica via OpenCode
- Integração IBGE, DataSUS, dados-brasil, agrobr
- Wrapper HTML com ttyd
- Backup/restore de sessões
- Gerenciamento de provedores de IA
- Tema escuro "pesquisai"
- Suporte a 4 idiomas
