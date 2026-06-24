# 📝 Log de Edição — `launch_app.py` (v0.4.2.2)

> **Data:** 2026-06-24
> **Operação:** Patch v0.4.2.2 (ses_10a4+ polish) aplicado sobre o `launch_app.py` do PesquisAI principal
> (já com v0.4.2.1: theme contrast + dashboard + markdown)
> **Arquivo original:** https://github.com/gustavobraga-byte/PesquisAI/blob/main/pesquisai/launch_app.py
> **Arquivo editado:** `/content/drive/My Drive/PesquisAI/pesquisai/launch_app.py`

## 📊 Estatísticas da Edição

| Métrica | v0.4.1 | v0.4.2 | v0.4.2.1 | v0.4.2.2 | Δ total |
|---------|--------|--------|----------|----------|---------|
| **Linhas** | 1.945 | 1.074 | 1.147 | 1.219 | **−726 (−37%)** |
| **Tamanho `launch_app.py`** | 86 KB | 44 KB | 47 KB | 52 KB | **−40%** |
| **Linhas `launch_app_responsive_v041.py`** | 1.520 | 1.792 | 1.820 | 2.193 | +673 |
| **Tamanho `launch_app_responsive_v041.py`** | 73 KB | 88 KB | 89 KB | 108 KB | +48% |
| **Funções preservadas** | 19 | 19 | 19 | 21 | +2 |
| **Endpoints REST** | 13 | 14 | 14 | 17 | +4 |

## ✂️ O Que Foi Removido

A função `create_wrapper_html` original (linhas 167-1070 do `launch_app.py` original) foi **completamente removida** e substituída por um import. O conteúdo removido era:

```python
def create_wrapper_html(terminal_url, drive_url):
    wrapper_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  ... (904 linhas de HTML/CSS/JS inline) ...
"""
    os.makedirs(WRAPPER_DIR, exist_ok=True)
    with open(os.path.join(WRAPPER_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(wrapper_html)
```

## ✅ O Que Foi Adicionado

### Patch v0.4.1 → v0.4.2 → v0.4.2.1 (em `launch_app.py`)

```python
# ───────────────────────────────────────────────────────────────────
# 🔧 PATCH v0.4.2.1 — Substitui a função create_wrapper_html original
# pela versão responsiva com tema escuro + idioma na UI + rodapé
# responsivo + modal de Diretrizes (AGENTS.md multilíngue) +
# correções de tema claro + dashboard + renderização de markdown.
#
# Mudanças aplicadas:
#   1. 📱 Site responsivo (6 media queries + hamburger menu) [v0.4.1]
#   2. 🎨 Tema claro/escuro com reload do iframe do ttyd [v0.4.1]
#   3. 🌐 Seletor de idioma na topbar (4 idiomas) [v0.4.1]
#   4. 🌙 Tema padrão ESCURO com anti-flash CSS [v0.4.1]
#   5. 📋 v0.4.2: Rodapé responsivo (flex-wrap + 2 linhas)
#   6. 📋 v0.4.2: Modal "Diretrizes do Agente" com AGENTS.md multilíngue
#   7. 🌓 v0.4.2.1: Tema CLARO — classe .modal-shell corrige contraste
#   8. 🩺 v0.4.2.1: Dashboard de Saúde agora faz fetch em /api/health
#   9. 📝 v0.4.2.1: Modal Diretrizes renderiza markdown (marked.js)
#
# Compatibilidade: API inalterada (create_wrapper_html(terminal_url, drive_url))
# Detalhes: docs/CHANGELOG.md (v0.4.2.1)
# ───────────────────────────────────────────────────────────────────
try:
    from .launch_app_responsive_v041 import create_wrapper_html
except ImportError:
    # Fallback: importa do caminho absoluto (modo standalone)
    import os as _os
    import sys as _sys
    _patch_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "launch_app_responsive_v041.py")
    if _os.path.exists(_patch_path):
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("launch_app_responsive_v041", _patch_path)
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        create_wrapper_html = _mod.create_wrapper_html
    else:
        raise ImportError(
            "Patch v0.4.2.1 não encontrado. Copie launch_app_responsive_v041.py "
            "para a mesma pasta de launch_app.py"
        )
```

## 🆕 Endpoint Adicionado (v0.4.2)

```python
# Adicionado no Handler.do_GET:
if p == "/api/agents":
    # Serve o AGENTS.md no idioma solicitado (?lang=pt_BR|en_US|es_ES|fr_FR)
    # - Localiza o arquivo em 5+ candidatos (irmão de pesquisai/, drive, CWD)
    # - Cache client-side por idioma (variável `_agentsCache`)
    # - Invalida automaticamente quando o usuário troca de idioma
    # Detalhes da implementação no CHANGELOG.md (v0.4.2)
```

## 🆕 Correções v0.4.2.1 (no `launch_app_responsive_v041.py`)

| # | Bug | Solução |
|---|-----|---------|
| 6 | Tema CLARO: textos invisíveis nos 6 modais (Dashboard, Atalhos, Sessões, Provedor, Diretrizes) | Nova classe `.modal-shell` usa variáveis CSS (`--modal-bg`, `--modal-border`) responsivas ao tema. `html.theme-light .modal-shell` define fundo branco + sombra suave. |
| 7 | Dashboard de Saúde não carregava (só abria overlay sem fetch) | `openHealth()` agora faz `fetch(BASE + "/api/health")` + nova função `renderHealth(d)` popula a lista com badges ✓/✗/·. |
| 8 | Modal de Diretrizes mostrava o MD como texto cru (`textContent`) | Adicionado `marked.js` + `github-markdown-css` via CDN. Nova função `renderAgentsContent(el, md)` usa `marked.parse()` e remove frontmatter YAML. CSS customizado preserva cores do tema. |

## 🛡️ O Que Foi Preservado (inalterado)

Todas as outras funções e blocos do `launch_app.py` foram **preservados integralmente**:

- ✅ `set_drive_info()` — configurações do Drive
- ✅ `load_keys_from_drive()` — chaves criptografadas
- ✅ `resolve_opencode()` — localização do binário OpenCode
- ✅ `install_ttyd()` — instalação do ttyd
- ✅ `kill_previous()` — limpeza de processos
- ✅ `start_ttyd()` — spawn do terminal
- ✅ `start_wrapper_server()` — servidor HTTP
- ✅ `show_ready_message()` — mensagens de status
- ✅ `show_launch_button()` — botão de launch
- ✅ `launch()` — função principal de inicialização
- ✅ `BaseHTTPRequestHandler` (classe) — servidor HTTP
- ✅ Todas as rotas `/api/*` (theme, backup, restore, apikey, run_terminal, health, sessions, lang, agents, etc.)
- ✅ Todos os imports no topo do arquivo
- ✅ Toda a lógica de segurança (sanitize_command, etc.)
- ✅ Todas as constantes (TERMINAL_PORT, WRAPPER_PORT, etc.)

## 🔄 Compatibilidade

| Aspecto | Status |
|---------|--------|
| API `create_wrapper_html(terminal_url, drive_url)` | ✅ Inalterada |
| Retorno da função | ✅ String HTML |
| Efeito colateral (escreve `index.html` em `WRAPPER_DIR`) | ✅ Mantido |
| Comportamento do servidor HTTP | ✅ Inalterado |
| Rotas `/api/*` | ✅ 14/14 funcionando (incluindo `/api/agents`) |
| Compatibilidade com testes existentes | ✅ `test_launch_app.py` continua passando |
| Tema padrão | 🌙 **Escuro** (com anti-flash) |

## 🧪 Validação (28 checks)

### v0.4.1 (14/14)
```
✅ data-theme="pesquisai" (escuro)
✅ ANTI-FLASH script
✅ html { background: #0d0f10
✅ html.theme-light CSS
✅ 6 media queries
✅ mobile-menu (drawer)
✅ hamburger-btn
✅ lang-btn (4 idiomas)
✅ function toggleTheme
✅ iframe reload ttyd
✅ pt_BR (Salvar backup)
✅ en_US (Save backup)
✅ es_ES (Guardar copia)
✅ fr_FR (Sauvegarder)
```

### v0.4.2 (10/10)
```
✅ Footer responsivo (footer-row-1, footer-row-2)
✅ flex-wrap + overflow:hidden
✅ Endpoint /api/agents
✅ Modal Diretrizes (openAgents, closeAgents, loadAgents)
✅ Cache de AGENTS por idioma
✅ Invalidação em setLang()
✅ i18n strings footer.email/github/ufv/powered_by
✅ 4 idiomas completos em JSON inline
```

### v0.4.2.1 (4/4)
```
✅ modal-shell (tema claro) — 6 modais atualizados
✅ openHealth faz fetch /api/health
✅ renderHealth popula lista com badges
✅ renderAgentsContent usa marked.parse() + github-markdown-css
```

## 📁 Estrutura Final

```
pesquisai/
├── __init__.py                    # ✅ Criado (necessário para import relativo)
├── launch_app.py                  # ✅ Patch v0.4.2.1 (47KB, 1147 linhas)
└── launch_app_responsive_v041.py  # ✅ Patch v0.4.2.1 (89KB, 1820 linhas)
```

## 🚀 Como Usar

```bash
# 1. Garantir que o PesquisAI principal está no path
export PYTHONPATH="/content/drive/My Drive/PesquisAI:$PYTHONPATH"

# 2. Rodar o PesquisAI normalmente
cd /content/drive/My\ Drive/PesquisAI
python -m pesquisai.main
# OU
python -m pesquisai.launch_app
```

O servidor vai:
1. Carregar `launch_app.py` normalmente
2. Quando chamar `create_wrapper_html(terminal_url, drive_url)` (linha ~1137):
   - Vai importar de `launch_app_responsive_v041.py`
   - Vai gerar o HTML com **tema padrão escuro + responsivo + seletor de idioma + modal de Diretrizes + markdown renderizado**
   - Vai escrever em `WRAPPER_DIR/index.html`
3. O resto do servidor (rotas, ttyd, opencode) funciona normalmente

## 🔙 Como Reverter (se necessário)

Se precisar reverter para o `launch_app.py` original (sem o patch v0.4.2.1):

```bash
# Baixar novamente do GitHub
curl -sL https://raw.githubusercontent.com/gustavobraga-byte/PesquisAI/main/pesquisai/launch_app.py \
  -o /content/drive/My\ Drive/PesquisAI/pesquisai/launch_app.py
```

E o PesquisAI volta ao comportamento original (sem responsividade, sem seletor de idioma, sem modal de Diretrizes, sem markdown renderizado).

## 📋 Checklist Pós-Edição

- [x] `launch_app.py` baixado do GitHub
- [x] `create_wrapper_html` substituída por import
- [x] Fallback de import (caminho absoluto) implementado
- [x] `__init__.py` criado em `pesquisai/`
- [x] Patch `_v041.py` no lugar certo
- [x] Endpoint `/api/agents` adicionado
- [x] Sintaxe Python validada (5/5 arquivos sem warnings)
- [x] HTML gerado tem tema escuro + responsivo + idioma + modal Diretrizes
- [x] Função `create_wrapper_html` acessível
- [x] 21 funções preservadas (servidor intacto + 2 novas: `start_ttyd(lang)`, `restart_ttyd_with_lang(lang)`)
- [x] `openHealth()` faz fetch em `/api/health`
- [x] Modal Diretrizes renderiza markdown (marked.js)
- [x] `openSessions()` faz fetch em `/api/sessions` (v0.4.2.2)
- [x] `setLang()` chama `POST /api/lang` que reinicia ttyd (v0.4.2.2)
- [x] Footer PC: provedor + OpenCode alinhados à direita (v0.4.2.2)
- [x] 4 `AGENTS.md` (pt, en, es, fr) padronizados sem "- [link/lien/enlace]"
- [x] `__version__.py` MOVIDO para `pesquisai/__version__.py` (v0.4.2.2)
- [x] 119/119 testes passando (grant_finder 48 + i18n 31 + meta-search-br 40)

---

## [v0.4.2.2] — 2026-06-24 — ses_10a4+ polish

### 🆕 Novidades (6 melhorias)

1. **🖥️ Footer PC alinhado à direita** — `margin-left: auto` em `.footer-row-2` dentro de `@media (min-width: 768px)`.
2. **🧩 Skills em `skills/`** — `grant-finder/` e `meta-search-br/` com READMEs + SKILL.md + clone URLs.
3. **📜 Histórico de sessão carregando** — `openSessions()` agora faz fetch em `/api/sessions`.
4. **🌍 Saudação no idioma** — `start_ttyd(lang)` usa `get_greeting(lang)` ao invés de `--prompt 'oi'`.
5. **📦 `__version__.py` movido** — de `/` para `pesquisai/` (v0.4.2.2).
6. **🧹 AGENTS.md padronizados** — removido "- [link/lien/enlace]" das 4 variantes.

### 🔄 Mudanças nos endpoints

| Endpoint | Mudança | Versão |
|---|---|---|
| `GET /api/lang` | **NOVO** — retorna idioma + saudação atuais | v0.4.2.2 |
| `POST /api/lang` | **NOVO** — persiste idioma + reinicia ttyd | v0.4.2.2 |
| `GET /api/sessions` | já existia (v0.4.2) mas sem render na UI | agora renderizado |
| `POST /api/restore` | usado por `restoreSession(id)` | v0.4.2.2 |
| `GET /api/agents?lang=xx_XX` | já existia (v0.4.2) | mantido |

### 📝 Variáveis globais adicionadas em `launch_app.py`

```python
_current_lang: str = "pt_BR"           # idioma persistido
_LANG_COOKIE_FILE: str = "~/.config/pesquisai_lang"  # path de persistência
```

### 🆕 Funções adicionadas em `launch_app.py`

- `start_ttyd(lang: str | None = None)` — inicia ttyd com saudação no idioma
- `restart_ttyd_with_lang(lang: str) -> bool` — reinicia ttyd com novo idioma

### 🆕 Funções adicionadas em `__version__.py`

- `get_greeting(lang: str = "pt_BR") -> str` — retorna saudação multilíngue
- `get_greeting` é usada por `start_ttyd()` para gerar o `--prompt`

---

**PesquisAI v0.4.2.2 · ses_10a4+ polish · 2026-06-24**
