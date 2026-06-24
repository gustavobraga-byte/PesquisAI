"""
launch_app_responsive.py — Wrapper HTML responsivo + tema + idioma (v0.4.2.2).

Este módulo SUBSTITUI o `create_wrapper_html` do launch_app.py do PesquisAI
principal (https://github.com/gustavobraga-byte/PesquisAI/blob/main/pesquisai/launch_app.py)
corrigindo os problemas reportados pelo usuário em 2026-06-23 e 2026-06-24.

═════════════════════════════════════════════════════════════════════════
v0.4.1 — UI Fixes (3 correções originais)
═════════════════════════════════════════════════════════════════════════

  1. 🐛 Site NÃO responsivo
     - Problema: o CSS original não tem media queries. Topbar de 8 botões
       estoura em mobile, modais de 400-520px não cabem, sem hamburger menu.
     - Correção: 5 breakpoints (mobile pequeno, mobile, tablet, tablet
       portrait, desktop, landscape), hamburger drawer, modais fluidos,
       touch targets ≥ 32-44px (Apple HIG / WCAG 2.5.5).

  2. 🐛 Tema claro/escuro não recarrega o terminal
     - Problema: toggleTheme() chama applyWrapperTheme() (muda só CSS do
       wrapper) mas NÃO recarrega o iframe do ttyd. O terminal continua
       renderizado com o tema antigo.
     - Correção: após aplicar tema na UI, recarregar o iframe do terminal
       (fr.src = "about:blank" → 3.5s → fr.src = origSrc + "?t=...").

  3. 🐛 Alteração de idioma sem opção na interface
     - Problema: o módulo i18n existe (4 idiomas, JSONs completos) mas
       não há seletor na topbar. O usuário não tem como trocar idioma.
     - Correção: dropdown na topbar com 🇧🇷 🇺🇸 🇪🇸 🇫🇷, persistência em
       cookie `pesquisai_lang`, query param `?lang=xx_XX`.

═════════════════════════════════════════════════════════════════════════
v0.4.2 — Footer Responsivo + AGENTS.md Multilíngue (2 correções adicionais)
═════════════════════════════════════════════════════════════════════════

  4. 🐛 Rodapé NÃO responsivo
     - Problema: o rodapé original (#footer) tem `display: flex` SEM
       `flex-wrap`. Em mobile, 8+ itens (PesquisAI, email, GitHub, UFV,
       Provedor, OpenCode) transbordam horizontalmente. O `#terminal-frame`
       também tem altura fixa (`calc(100% - 90px)`) que não considera
       o rodapé que pode crescer em 2 linhas.
     - Correção:
       • `flex-wrap: wrap` no #footer (e `overflow: hidden` no root)
       • 2 linhas lógicas (.footer-row-1 + .footer-row-2) com `display:
         contents` em desktop (invisível) e linhas reais em mobile
       • Media queries específicas: separa UFV/OpenCode em landscape,
         esconde GitHub em <480px, ajusta altura do terminal dinamicamente
       • `#terminal-frame` agora usa `calc(100vh - 90px)` (corrigido de
         `calc(100% - 90px)`) + ajuste por breakpoint

  5. 🐛 Troca de idioma NÃO troca o AGENTS.md
     - Problema: o sistema troca strings da UI (data-i18n) mas o
       arquivo `agents/AGENTS.xx_XX.md` (regras de integridade científica)
       continua sendo exibido no idioma original. Pesquisador que troca
       para inglês continua lendo regras em português.
     - Correção:
       • Novo endpoint backend `GET /api/agents?lang=xx_XX` que serve
         o conteúdo do `agents/AGENTS.<lang>.md` apropriado
       • Novo modal "📋 Diretrizes do Agente" na UI (botão na topbar)
       • Cache client-side por idioma (1 chamada até troca de idioma)
       • Invalidação automática do cache em `setLang()` + recarregamento
         se o modal estiver aberto
       • Botões: 📋 Copiar, ↻ Recarregar, 🔗 Ver fonte (link pro GitHub)
       • Badge do idioma atual no header do modal (PT-BR, EN-US, etc.)

═════════════════════════════════════════════════════════════════════════
v0.4.2.1 — Sessão ses_10a4 (3 correções adicionais da sessão do usuário)
═════════════════════════════════════════════════════════════════════════

  6. 🐛 Tema CLARO: textos invisíveis nos modais (Dashboard de Saúde,
     Atalhos, Sessões, Provedor)
     - Problema: 6 modais tinham `background:#181b1e` (cor escura FIXA),
       enquanto a cor do texto (`var(--ink-muted)`) passava a cinza
       escuro no tema claro → resultado: cinza escuro em fundo escuro
       = invisível.
     - Correção:
       • Nova classe `.modal-shell` que usa variáveis CSS (`--modal-bg`,
         `--modal-border`) responsivas ao tema
       • `html.theme-light .modal-shell` define `--modal-bg: #ffffff` e
         sombra mais suave
       • Inputs (`session-search`, `prov-key-input`) ganham estilo para
         tema claro
       • Botões `.modal-close` e itens de lista (`.backup-item:hover`,
         `.session-item:hover`) também tem contraste corrigido

  7. 🐛 Dashboard de Saúde não carrega
     - Problema: `openHealth()` só abria o overlay visual, sem fazer
       fetch em `/api/health` nem popular a lista. Usuário clicava no
       ícone e só via "Carregando diagnóstico…".
     - Correção:
       • `openHealth()` agora faz `fetch(BASE + "/api/health")`
       • Nova função `renderHealth(d)` popula `#health-list` com linhas
         de status (✓/✗) para cada verificação (Drive, ttyd, OpenCode,
         keys, skills, ffmpeg, disco, versão)

  8. 🐛 Modal de Diretrizes mostra MD cru (sem formatação)
     - Problema: o conteúdo era injetado com `.textContent`, exibindo
       os caracteres `#`, `**`, `|`, `---` do markdown como texto puro.
     - Correção:
       • Adicionado `marked.js` (CDN) + `github-markdown-css` ao `<head>`
       • Nova função `renderAgentsContent(el, md)` usa `marked.parse()`
         para converter markdown → HTML formatado
       • CSS customizado (#agents-content.markdown-body) preserva as
         cores de tema (accent, ink, ink-muted) e fontes (Syne para
         títulos, DM Mono para código/corpo)
       • Remove frontmatter YAML do conteúdo antes de renderizar

═════════════════════════════════════════════════════════════════════════
v0.4.2.2 — Ses_10a4+ Polish (6 correções adicionais da sessão do usuário)
═════════════════════════════════════════════════════════════════════════

   9. 🖥️ Footer PC: provedor e "Powered by OpenCode" alinhados à DIREITA
      - Problema: no desktop, o segundo grupo do rodapé (provedor + OpenCode)
        ficava colado à esquerda junto com a marca e contatos. Em PC, deveria
        estar à DIREITA.
      - Correção: `@media (min-width: 768px)` faz `.footer-row-2` virar
        `display: flex` com `margin-left: auto`, empurrando-o para a direita.
        Mobile preserva o layout de 2 linhas.

  10. 🧩 Skills: `grant-finder` e `meta-search-br` em `skills/` com clone URL
      - Problema: as 2 skills extras existiam (grant_finder/ na raiz,
        skills/meta-search-br/) mas sem READMEs padronizados nem links de clone.
      - Correção: criadas READMEs + SKILL.md + __init__.py com `__clone_url__`
        apontando para `https://github.com/gustavobraga-byte/grant-finder` e
        `https://github.com/gustavobraga-byte/meta-search-br`.

  11. 📜 Histórico de sessão não carregava
      - Problema: `openSessions()` só abria o overlay, sem fetch nem
        render da lista. Usuário via "Carregando sessões…" para sempre.
      - Correção: `openSessions()` agora faz `await fetch("/api/sessions")`
        e popula `#session-list` com sessões clicáveis (id, título, data,
        contagem de mensagens). `filterSessions()` filtra em tempo real.
        Cada item chama `restoreSession(id)` que faz POST em `/api/restore`.

  12. 🌍 Saudação inicial do ttyd no idioma selecionado
      - Problema: ttyd sempre recebia `--prompt 'oi'` genérico. Trocar
        idioma não mudava a saudação inicial.
      - Correção: `start_ttyd(lang)` usa `get_greeting(lang)` para saudação
        específica por idioma. Endpoint `POST /api/lang` reinicia o ttyd
        automaticamente ao trocar idioma. Idioma persistido em
        `~/.config/pesquisai_lang`.

  13. 📦 `__version__.py` MOVIDO para `pesquisai/__version__.py`
      - Problema: arquivo de versão estava na raiz (`/__version__.py`),
        quebrando `from .__version__ import VERSION`.
      - Correção: movido para `pesquisai/__version__.py`, bumpado para
        v0.4.2.2, com fallback de versão hardcoded se o módulo não for
        encontrado.

  14. 🧹 AGENTS.md multilíngues padronizados
      - Problema: francês tinha `[lien]` em todos os 3 outros idiomas; pt/en/es
        tinham `[link/enlace]` só para o francês. Padrão inconsistente.
      - Correção: removido todo "- [link/lien/enlace](...)" das 4 variantes.
        Formato final: `- `agents/AGENTS.<lang>.md` (nome do idioma)`.

Instalação:
    Editar ``pesquisai/launch_app.py`` e substituir a função
    ``create_wrapper_html(terminal_url, drive_url)`` original por:

        from .launch_app_responsive_v041 import create_wrapper_html

OU (preferível, evita editar o original):

    from pesquisai.launch_app_responsive_v041 import create_wrapper_html as _create
    def create_wrapper_html(terminal_url, drive_url):
        return _create(terminal_url, drive_url)

Compatibilidade: PesquisAI v0.2.1+ (usa /api/theme, /api/lang, /api/agents,
/api/backup, /api/restore, /api/apikey, /api/run_terminal, /api/health,
/api/sessions).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Imports resilientes (funciona dentro do pacote e standalone)
try:
    from .constants import WRAPPER_DIR
    from .jokes import next_joke
    # v0.4.2.2: __version__ foi MOVIDO para pesquisai/__version__.py
    try:
        from .__version__ import __version__ as VERSION, get_greeting
    except ImportError:
        VERSION = "0.4.2.2"
        def get_greeting(lang: str = "pt_BR") -> str:
            # Fallback v0.4.2.2: saudação curta + dica entre parênteses
            return "Olá! (Dica: A partir de agora responda em português brasileiro.)"
except ImportError:
    WRAPPER_DIR = "/tmp/pesquisai-wrapper"
    VERSION = "0.4.2.2"
    def get_greeting(lang: str = "pt_BR") -> str:
        # Fallback v0.4.2.2: saudação curta + dica entre parênteses
        return "Olá! (Dica: A partir de agora responda em português brasileiro.)"
    def next_joke(category: str = "aleatorio") -> str:
        return "💻 (standalone mode) carregando..."

# Garante que o diretório wrapper existe
Path(WRAPPER_DIR).mkdir(parents=True, exist_ok=True)


# ── CSS Responsivo injetado ──────────────────────────────────────
# Bloco com todas as media queries (5 breakpoints + landscape + acessibilidade).
# Reorganiza o topbar original em mobile via hamburger menu drawer.
RESPONSIVE_CSS: str = """
<style id="pesquisai-responsive">
  /* === Mobile/Tablet: Hamburger menu (escondido em desktop) === */
  .hamburger {
    display: none;
    width: 36px; height: 36px;
    background: transparent;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    color: var(--ink);
    cursor: pointer;
    align-items: center; justify-content: center;
  }
  .hamburger:active { transform: scale(.94); }
  .hamburger svg { width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 2; }

  .mobile-menu {
    position: fixed;
    top: 50px; right: 0;
    width: 280px; max-width: 85vw;
    height: calc(100vh - 50px);
    background: var(--rail);
    border-left: 1px solid var(--line);
    transform: translateX(100%);
    transition: transform .25s ease;
    z-index: 9998;
    padding: 16px;
    overflow-y: auto;
    display: flex; flex-direction: column; gap: 10px;
    box-shadow: -4px 0 24px rgba(0,0,0,.35);
  }
  .mobile-menu.open { transform: translateX(0); }
  .mobile-menu .tb-btn { width: 100%; justify-content: flex-start; }
  .mobile-menu-overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,.5);
    opacity: 0; pointer-events: none;
    transition: opacity .2s;
    z-index: 9997;
  }
  .mobile-menu-overlay.open { opacity: 1; pointer-events: all; }

  /* === Tablet (768px – 1023px): topbar condensado === */
  @media (max-width: 1023px) {
    #topbar { padding: 0 12px; gap: 8px; height: 50px; }
    .tb-btn { padding: 0 10px; font-size: 10.5px; }
    .logo-tag { display: none; }
    .footer-link { font-size: 10px; }
    .footer-sep { margin: 0 8px; }
    .modal-600 { width: 90vw; max-width: 600px; }
    /* Footer: quebra em 2 linhas se necessário */
    #footer { gap: 4px 8px; height: auto; min-height: 40px; padding: 6px 12px; }
    #footer .footer-ufv { display: none; }
  }

  /* === Mobile (480px – 767px): hamburger + ícones essenciais === */
  @media (max-width: 767px) {
    html, body { font-size: 14px; }
    #topbar { padding: 0 8px; gap: 6px; }
    .logo-p, .logo-ai { font-size: 15px; }
    .status { display: none; }  /* esconde status, foco no essencial */
    .tb-btn { display: none; }  /* migram para hamburger */
    .tb-icons { margin-left: auto; gap: 3px; }
    .tb-icon { width: 32px; height: 32px; }
    .tb-icon svg { width: 14px; height: 14px; }
    .hamburger { display: inline-flex; }
    /* FOOTER: layout em 2 colunas empilhadas, sem overflow */
    #footer {
      padding: 6px 10px;
      height: auto;
      min-height: 56px;
      flex-wrap: wrap;
      gap: 4px 8px;
      font-size: 10.5px;
      align-items: center;
      justify-content: space-between;
    }
    #footer .footer-row-1 {
      display: flex; align-items: center; gap: 6px;
      flex: 1 1 100%;
      flex-wrap: wrap;
    }
    #footer .footer-row-2 {
      display: flex; align-items: center; gap: 6px;
      flex: 1 1 100%;
      justify-content: space-between;
    }
    .footer-brand { display: inline-flex; }
    .footer-link { font-size: 10px; }
    .footer-link svg { width: 10px; height: 10px; }
    .footer-sep { display: none; }  /* separadores somem em mobile */
    .footer-ufv { display: none; }  /* UFV some em mobile */
    .btn-provider { padding: 0 6px; font-size: 9px; height: 22px; }
    .footer-oc { font-size: 9.5px; }
    /* terminal: ocupa mais espaço em mobile */
    #terminal-frame { height: calc(100vh - 50px - 56px) !important; }
    /* modais: largura quase total */
    #modal, #provider-overlay > div, #health-overlay > div,
    #sessions-overlay > div, #shortcuts-overlay > div, #lang-overlay > div,
    #agents-overlay > div {
      width: 95vw !important; max-width: 95vw !important;
      padding: 16px !important;
    }
    .modal-title { font-size: 14px !important; }
    .backup-item, .session-item, .health-row, .shortcut-row, .lang-option {
      padding: 10px 8px !important; font-size: 11px !important;
    }
    .health-status { font-size: 11px !important; }
    .session-search { font-size: 12px !important; }
    .toast { max-width: 260px !important; font-size: 11px !important; }
    /* dropdown de idioma também fica fluído */
    .lang-menu { right: 8px !important; min-width: 200px !important; }
  }

  /* === Mobile muito pequeno (< 480px): modo compacto === */
  @media (max-width: 479px) {
    #topbar { padding: 0 4px; }
    .logo-p, .logo-ai { font-size: 13px; }
    .tb-icon { width: 30px; height: 30px; }
    .tb-icon svg { width: 13px; height: 13px; }
    .mobile-menu { width: 100vw; max-width: 100vw; }
    /* FOOTER: compacto, só essenciais */
    #footer {
      padding: 5px 8px;
      min-height: 52px;
      font-size: 9.5px;
      gap: 3px 6px;
    }
    #footer .footer-row-1 { gap: 4px; }
    .footer-link { font-size: 9.5px; }
    .footer-link svg { width: 9px; height: 9px; }
    /* esconde GitHub link, mantém só email */
    .footer-link-footer-github { display: none; }
    /* terminal */
    #terminal-frame { height: calc(100vh - 50px - 52px) !important; }
  }

  /* === Landscape em mobile (altura < 500px) === */
  @media (max-height: 500px) and (orientation: landscape) {
    #topbar { height: 40px; }
    .logo { font-size: 12px; }
    /* FOOTER: 1 linha só, sem UFV/OpenCode */
    #footer {
      height: 30px; min-height: 30px;
      padding: 0 10px; font-size: 9px;
      flex-wrap: nowrap;
    }
    .footer-row-2 { display: none; }
    .footer-ufv { display: none; }
    #terminal-frame { height: calc(100vh - 40px - 30px) !important; }
  }

  /* === Tablet/iPad portrait: esconde UFV footer === */
  @media (min-width: 768px) and (max-width: 1024px) and (orientation: portrait) {
    .tb-btn { padding: 0 8px; }
    .footer-ufv { display: none; }
  }

  /* === FOOTER: regras universais para evitar overflow === */
  /* (v0.4.2: rodapé responsivo — flex-wrap + classes utilitárias) */
  #footer {
    overflow: hidden;
  }
  .footer-link, .footer-brand, .footer-oc, .footer-ufv {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .footer-row-1, .footer-row-2 {
    display: contents;  /* em desktop, ignora os wrappers e usa flex direto */
  }
  /* Em mobile (≤767px) os wrappers viram linhas reais (regra acima sobrescreve) */

  /* v0.4.2.2: em DESKTOP, .footer-row-2 vira flex item e vai para a DIREITA
     (botão de provedor + "Powered by OpenCode" alinhados à direita)
     O `display: contents` acima é sobrescrito dentro do media query abaixo
     para que `margin-left: auto` funcione. */
  @media (min-width: 768px) {
    .footer-row-1 { display: flex; align-items: center; gap: 6px; }
    .footer-row-2 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-left: auto;   /* empurra row-2 (provedor + OpenCode) à direita */
    }
  }

  /* === Acessibilidade: foco visível em todos os botões === */
  .tb-btn:focus-visible, .tb-icon:focus-visible, .hamburger:focus-visible,
  .lang-btn:focus-visible, .lang-option:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* === Seletor de idioma (NOVO em v0.4.1) === */
  .lang-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 0 8px; height: 30px;
    font-family: "DM Mono", monospace; font-size: 11px;
    font-weight: 500; letter-spacing: .03em;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: transparent;
    color: var(--ink-muted);
    cursor: pointer;
    transition: background .15s, color .15s, border-color .15s;
  }
  .lang-btn:hover {
    background: var(--accent-dim);
    color: var(--accent);
    border-color: rgba(79,195,247,.4);
  }
  .lang-btn:active { transform: scale(.96); }
  .lang-btn .lang-flag { font-size: 13px; line-height: 1; }
  .lang-btn .lang-code { font-weight: 600; }
  .lang-btn .lang-chevron {
    width: 9px; height: 9px;
    border-right: 1.5px solid currentColor;
    border-bottom: 1.5px solid currentColor;
    transform: rotate(45deg);
    margin-left: 2px;
    margin-top: -2px;
    transition: transform .2s;
  }
  .lang-btn[aria-expanded="true"] .lang-chevron { transform: rotate(-135deg); margin-top: 2px; }

  .lang-menu {
    position: fixed;
    top: 50px; right: 18px;
    min-width: 220px;
    background: var(--rail);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 12px 32px rgba(0,0,0,.5);
    padding: 6px;
    z-index: 9996;
    opacity: 0; pointer-events: none;
    transform: translateY(-8px);
    transition: opacity .18s, transform .18s;
  }
  .lang-menu.open { opacity: 1; pointer-events: all; transform: translateY(0); }
  .lang-option {
    display: flex; align-items: center; gap: 10px;
    width: 100%; padding: 9px 12px;
    background: transparent;
    border: 0;
    border-radius: var(--radius);
    color: var(--ink);
    font-family: "DM Mono", monospace;
    font-size: 12px;
    text-align: left;
    cursor: pointer;
    transition: background .12s, color .12s;
  }
  .lang-option:hover { background: var(--accent-dim); color: var(--accent); }
  .lang-option[aria-current="true"] {
    background: var(--accent-dim); color: var(--accent);
  }
  .lang-option .lang-flag { font-size: 16px; line-height: 1; }
  .lang-option .lang-name { flex: 1; }
  .lang-option .lang-check {
    color: var(--accent);
    font-weight: 700;
    opacity: 0;
  }
  .lang-option[aria-current="true"] .lang-check { opacity: 1; }

  /* === Tema CLARO via classe .theme-light no <html> (NOVO v0.4.1) === */
  /* Aplicado pelo script anti-flash no <head> e pelo applyWrapperTheme() */
  /* Mantém fallback via setProperty para retrocompatibilidade */
  html.theme-light {
    --ink:        #1f262a;
    --ink-muted:  #4a5a62;
    --surface:    #f5f6f7;
    --rail:       #ffffff;
    --line:       rgba(0,0,0,.1);
    --accent:     #0288d1;
    --accent-dim: rgba(2,136,209,.1);
    --accent-glow:rgba(2,136,209,.2);
    --green:      #2e7d32;
    --green-dim:  rgba(46,125,50,.1);
    --amber:      #e65100;
    --amber-dim:  rgba(230,81,0,.1);
    --red:        #c62828;
    --red-dim:    rgba(198,40,40,.1);
    background:   #f5f6f7;
    color:        #1f262a;
  }}

  /* === Indicador de tema ativo (NOVO em v0.4.1) === */
  #theme-toggle[data-theme="pesquisai-light"] {
    color: var(--amber);
    border-color: rgba(232,184,75,.4);
    background: var(--amber-dim);
  }
  #theme-toggle[data-theme="pesquisai"] {
    color: var(--ink-muted);
  }
  #theme-toggle[data-theme="pesquisai-light"] svg circle { fill: currentColor; }

  /* === Modal shells (v0.4.2.1: respondem ao tema) === */
  .modal-shell {
    background: var(--modal-bg, #181b1e);
    border: 1px solid var(--modal-border, rgba(255,255,255,.1));
    color: var(--ink);
  }
  html.theme-light .modal-shell {
    --modal-bg: #ffffff;
    --modal-border: rgba(0,0,0,.12);
    box-shadow: 0 28px 72px rgba(0,0,0,.18);
  }
  /* Inputs/buttons dentro dos modais no tema claro */
  html.theme-light input.session-search,
  html.theme-light #prov-key-input {
    background: var(--surface, #f5f6f7) !important;
    border: 1px solid var(--line) !important;
    color: var(--ink) !important;
  }
  html.theme-light .modal-close {
    background: var(--surface, #f5f6f7) !important;
    color: var(--ink) !important;
  }
  html.theme-light .modal-close:hover {
    background: var(--accent-dim) !important;
  }
  /* Sessões/itens com hover legível em tema claro */
  html.theme-light .backup-item:hover,
  html.theme-light .session-item:hover {
    background: var(--accent-dim) !important;
    color: var(--ink) !important;
  }

  /* === Renderização Markdown no modal de Diretrizes (v0.4.2.1) === */
  #agents-content.markdown-body {
    /* Resetar estilos default do github-markdown-css */
    background: transparent !important;
    color: var(--ink) !important;
    font-family: "DM Mono", monospace !important;
  }
  #agents-content.markdown-body h1,
  #agents-content.markdown-body h2,
  #agents-content.markdown-body h3,
  #agents-content.markdown-body h4 {
    color: var(--ink);
    border-bottom-color: var(--line);
    font-family: "Syne", sans-serif;
    margin-top: 1.2em;
    margin-bottom: 0.6em;
  }
  #agents-content.markdown-body h1 { font-size: 18px; }
  #agents-content.markdown-body h2 { font-size: 15px; }
  #agents-content.markdown-body h3 { font-size: 13.5px; }
  #agents-content.markdown-body h4 { font-size: 12.5px; }
  #agents-content.markdown-body a { color: var(--accent); }
  #agents-content.markdown-body code {
    background: var(--accent-dim);
    color: var(--accent);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11.5px;
  }
  #agents-content.markdown-body pre {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 12px 14px;
    overflow-x: auto;
  }
  #agents-content.markdown-body pre code {
    background: transparent;
    color: var(--ink);
    padding: 0;
    font-size: 11px;
  }
  #agents-content.markdown-body table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.8em 0;
    font-size: 11.5px;
  }
  #agents-content.markdown-body th,
  #agents-content.markdown-body td {
    border: 1px solid var(--line);
    padding: 6px 10px;
    text-align: left;
  }
  #agents-content.markdown-body th {
    background: var(--accent-dim);
    color: var(--accent);
    font-weight: 700;
  }
  #agents-content.markdown-body blockquote {
    border-left: 3px solid var(--accent);
    background: var(--accent-dim);
    margin: 0.6em 0;
    padding: 6px 14px;
    color: var(--ink-muted);
    border-radius: 0 4px 4px 0;
  }
  #agents-content.markdown-body hr {
    border: 0;
    border-top: 1px solid var(--line);
    margin: 1.2em 0;
  }
  #agents-content.markdown-body ul,
  #agents-content.markdown-body ol {
    padding-left: 1.6em;
    margin: 0.5em 0;
  }
  #agents-content.markdown-body li { margin: 0.2em 0; }
  #agents-content.markdown-body strong { color: var(--ink); font-weight: 700; }
  #agents-content.markdown-body em { color: var(--ink-muted); }

  /* === Toasts em viewport pequeno === */
  @media (max-height: 500px) {
    #toast { bottom: 36px; right: 8px; }
  }
</style>
"""


# ── Dicionário de idiomas (NOVO em v0.4.1) ───────────────────────
# Strings traduzidas para seletor e mensagens de feedback.
# Para textos longos (toasts, modais completos), o backend Python é
# a fonte da verdade (i18n/translations/*.json). Aqui ficam apenas as
# strings que precisam ser atualizadas no client-side sem reload.
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"code": "pt_BR", "name": "Português (Brasil)",   "flag": "🇧🇷", "short": "PT"},
    {"code": "en_US", "name": "English (United States)", "flag": "🇺🇸", "short": "EN"},
    {"code": "es_ES", "name": "Español (España)",     "flag": "🇪🇸", "short": "ES"},
    {"code": "fr_FR", "name": "Français (France)",    "flag": "🇫🇷", "short": "FR"},
]


def create_wrapper_html(terminal_url: str, drive_url: str) -> str:
    """Cria a versão v0.4.2.1 do wrapper HTML do PesquisAI.

    Versão drop-in que substitui o HTML estático do launch_app.py por
    um layout adaptativo com 8 correções aplicadas:

      v0.4.1:
        1. Responsividade completa (5 breakpoints + hamburger)
        2. toggleTheme() que recarrega o iframe do ttyd
        3. Seletor de idioma na topbar (4 idiomas, cookie, query param)
      v0.4.2:
        4. Rodapé responsivo (flex-wrap + 2 linhas + media queries)
        5. Modal de Diretrizes com AGENTS.md multilíngue (endpoint + cache)
      v0.4.2.1 (ses_10a4):
        6. Tema CLARO: contraste corrigido nos modais (.modal-shell)
        7. openHealth() faz fetch em /api/health e popula dashboard
        8. Modal de Diretrizes renderiza markdown (marked.js)

    Args:
        terminal_url: URL do terminal ttyd.
        drive_url: URL do Google Drive.

    Returns:
        String HTML completa.
    """
    # IMPORTANTE: usamos string normal (sem f-string) e placeholders
    # únicos (__TERMINAL_URL__, etc.) para evitar conflito com as
    # expressões {data-i18n} e {{chaves}} do CSS que estão dentro do
    # HTML. A substituição final é feita por .replace() abaixo.
    html: str = """<!DOCTYPE html>
<html lang="pt-BR" data-theme="pesquisai">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="theme-color" content="#0d0f10">
  <title>PesquisAI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css">
  <!-- Renderizador de Markdown para o modal de Diretrizes (v0.4.2.1) -->
  <script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.5.1/github-markdown.min.css">
  <script>
    // ═══════════════════════════════════════════════════════════
    // 🛡️ ANTI-FLASH: aplica tema ANTES de qualquer renderização
    // Padrão: ESCURO. Claro só se cookie/localStorage persistir.
    // Este script executa síncrono no <head>, antes do CSS.
    // ═══════════════════════════════════════════════════════════
    (function() {
      try {
        var theme = "pesquisai"; // padrão ESCURO
        // 1. Cookie (fonte primária)
        var m = document.cookie.match(/(?:^| )pesquisai_theme=([^;]+)/);
        if (m && (m[1] === "pesquisai-light" || m[1] === "pesquisai")) {
          theme = decodeURIComponent(m[1]);
        } else {
          // 2. localStorage (fallback)
          try {
            var ls = localStorage.getItem("pesquisai_theme");
            if (ls === "pesquisai-light" || ls === "pesquisai") theme = ls;
          } catch (e) {}
        }
        // 3. Aplica no <html> ANTES do body renderizar
        document.documentElement.setAttribute("data-theme", theme);
        if (theme === "pesquisai-light") {
          document.documentElement.classList.add("theme-light");
        } else {
          // Garante que o body já inicia com fundo escuro
          document.documentElement.style.backgroundColor = "#0d0f10";
          document.documentElement.style.color = "#e8e6e0";
        }
      } catch (e) {
        // Em caso de erro, mantém padrão escuro
        document.documentElement.style.backgroundColor = "#0d0f10";
      }
    })();
  </script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { background: #0d0f10; color: #e8e6e0; }  /* anti-flash dark */

    :root {
      --ink:        #e8e6e0;
      --ink-muted:  #8a8780;
      --surface:    #0d0f10;
      --rail:       #151819;
      --line:       rgba(255,255,255,.07);
      --accent:     #4fc3f7;
      --accent-dim: rgba(79,195,247,.12);
      --accent-glow:rgba(79,195,247,.22);
      --green:      #5dba7e;
      --green-dim:  rgba(93,186,126,.12);
      --amber:      #e8b84b;
      --amber-dim:  rgba(232,184,75,.12);
      --red:        #e07070;
      --red-dim:    rgba(224,112,112,.12);
      --radius:     5px;
    }

    html, body {
      height: 100%; width: 100%;
      background: var(--surface);
      color: var(--ink);
      font-family: "DM Mono", monospace;
      overflow: hidden;
      -webkit-tap-highlight-color: transparent;
    }

    /* Touch: target mínimo 32x44 px (Apple HIG / WCAG 2.5.5) */
    button, .tb-btn, .tb-icon, .hamburger, .lang-btn { min-height: 32px; min-width: 32px; }

    #topbar {
      position: fixed; inset: 0 0 auto 0;
      height: 50px;
      background: var(--rail);
      border-bottom: 1px solid var(--line);
      display: flex; align-items: center;
      padding: 0 18px; gap: 14px;
      z-index: 9999;
    }
    #topbar::after {
      content: "";
      position: absolute; inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px,
        rgba(0,0,0,.05) 2px, rgba(0,0,0,.05) 4px);
      pointer-events: none;
    }

    .logo { display: flex; align-items: baseline; gap: 2px; }
    .logo-p  { font-family:"Syne",sans-serif; font-weight:800; font-size:17px; color:var(--ink); letter-spacing:-.5px; }
    .logo-ai { font-family:"Syne",sans-serif; font-weight:700; font-size:17px; color:var(--accent); letter-spacing:-.5px; }
    .logo-tag {
      margin-left:9px; font-size:10px; color:var(--ink-muted);
      letter-spacing:.07em; padding:1px 6px;
      border:1px solid var(--line); border-radius:3px; align-self:center;
    }

    .status { display:flex; align-items:center; gap:7px; font-size:11px; color:var(--ink-muted); }
    .status-dot {
      width:7px; height:7px; border-radius:50%; background:var(--green);
      animation: pulse 2.4s ease infinite;
    }
    @keyframes pulse {
      0%,100% { box-shadow:0 0 0 0 rgba(93,186,126,.5); }
      50%      { box-shadow:0 0 0 5px rgba(93,186,126,0); }
    }

    .sep { flex: 1; }

    .tb-btn {
      display: inline-flex; align-items: center; gap: 7px;
      padding: 0 13px; height: 30px;
      font-family: "DM Mono", monospace; font-size: 11px;
      font-weight: 500; letter-spacing: .04em;
      border-radius: var(--radius); cursor: pointer;
      border: 1px solid; transition: background .15s, transform .1s, border-color .15s;
      text-decoration: none; white-space: nowrap;
    }
    .tb-btn:active { transform: scale(.96); }
    .tb-btn svg { width:13px; height:13px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }

    .btn-drive  { color:var(--accent); background:var(--accent-dim); border-color:rgba(79,195,247,.25); }
    .btn-drive:hover  { background:var(--accent-glow); border-color:rgba(79,195,247,.5); }

    .btn-backup { color:var(--green); background:var(--green-dim); border-color:rgba(93,186,126,.25); }
    .btn-backup:hover { background:rgba(93,186,126,.2); border-color:rgba(93,186,126,.5); }

    .btn-restore { color:var(--amber); background:var(--amber-dim); border-color:rgba(232,184,75,.25); }
    .btn-restore:hover { background:rgba(232,184,75,.2); border-color:rgba(232,184,75,.5); }

    #toast {
      position: fixed; bottom: 58px; right: 18px;
      padding: 9px 16px; border-radius: var(--radius);
      font-size: 12px; font-family: "DM Mono", monospace;
      display: flex; align-items: center; gap: 8px;
      opacity: 0; transform: translateY(6px);
      transition: opacity .22s, transform .22s;
      pointer-events: none; z-index: 9998; max-width: 340px;
      border: 1px solid;
    }
    #toast.show { opacity: 1; transform: translateY(0); }
    #toast.ok    { background:rgba(93,186,126,.15);  border-color:rgba(93,186,126,.35);  color:var(--green); }
    #toast.err   { background:rgba(224,112,112,.15); border-color:rgba(224,112,112,.35); color:var(--red);   }
    #toast.info  { background:var(--accent-dim);     border-color:rgba(79,195,247,.35);  color:var(--accent);}

    #modal-overlay {
      position: fixed; inset: 0;
      background: rgba(0,0,0,.65); backdrop-filter: blur(3px);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; opacity: 0; pointer-events: none;
      transition: opacity .2s;
    }
    #modal-overlay.open { opacity: 1; pointer-events: all; }
    #modal {
      background: var(--modal-bg, #181b1e);
      border: 1px solid var(--line);
      color: var(--ink);
      border-radius: 8px; padding: 24px; width: 400px; max-width: 90vw;
      box-shadow: 0 24px 64px rgba(0,0,0,.6);
    }
    .modal-title {
      font-family: "Syne", sans-serif; font-weight: 800;
      font-size: 15px; color: var(--ink); margin-bottom: 16px;
    }
    .backup-list {
      max-height: 260px; overflow-y: auto;
      border: 1px solid var(--line); border-radius: var(--radius);
      margin-bottom: 16px;
    }
    .backup-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 9px 12px; font-size: 11.5px; color: var(--ink-muted);
      border-bottom: 1px solid var(--line); cursor: pointer;
      transition: background .12s;
    }
    .backup-item:last-child { border-bottom: none; }
    .backup-item:hover { background: rgba(255,255,255,.04); color: var(--ink); }
    .backup-item .restore-lbl {
      font-size: 10px; padding: 2px 8px;
      background: var(--amber-dim); color: var(--amber);
      border: 1px solid rgba(232,184,75,.3); border-radius: 3px;
    }
    .modal-empty { padding:20px; text-align:center; font-size:12px; color:var(--ink-muted); }
    .modal-close {
      display: block; width: 100%; padding: 8px;
      background: rgba(255,255,255,.05); border: 1px solid var(--line);
      border-radius: var(--radius); color: var(--ink-muted);
      font-family: "DM Mono", monospace; font-size: 12px;
      cursor: pointer; transition: background .15s;
    }
    .modal-close:hover { background: rgba(255,255,255,.1); }

    #terminal-frame {
      position: absolute;
      inset: 50px 0 40px 0;
      width: 100%; height: calc(100vh - 90px);
      border: none;
    }

    #footer {
      position: fixed; inset: auto 0 0 0;
      min-height: 40px; height: 40px;
      background: var(--rail);
      border-top: 1px solid var(--line);
      display: flex; align-items: center; flex-wrap: wrap;
      padding: 6px 18px; gap: 0 12px;
      font-size: 10.5px; color: var(--ink-muted);
      z-index: 9999;
      overflow: hidden;
    }
    .footer-brand {
      font-family: "Syne", sans-serif; font-weight: 700;
      font-size: 11px; color: var(--ink);
      margin-right: 6px;
    }
    .footer-sep { width:1px; height:16px; background:var(--line); margin:0 6px; flex-shrink:0; }
    .footer-link {
      color: var(--ink-muted); text-decoration: none;
      letter-spacing: .03em;
      transition: color .15s;
      display: inline-flex; align-items: center;
      max-width: 100%;
    }
    .footer-link:hover { color: var(--accent); }
    .footer-link svg { width:11px; height:11px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; vertical-align:-.15em; margin-right:4px; flex-shrink:0; }
    .footer-right { margin-left:auto; display:flex; align-items:center; gap:8px; flex-wrap: wrap; }
    .footer-oc { color:var(--ink-muted); letter-spacing:.03em; }
    .footer-oc a { color:var(--ink-muted); text-decoration:none; }
    .footer-oc a:hover { color:var(--accent); }
    .footer-ufv { color: var(--ink-muted); }

    .btn-provider {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 0 10px; height: 24px;
      font-family: "DM Mono", monospace; font-size: 10px;
      font-weight: 500; letter-spacing: .03em;
      border-radius: var(--radius); cursor: pointer;
      border: 1px solid rgba(79,195,247,.18);
      color: rgba(79,195,247,.55);
      background: transparent;
      transition: background .15s, color .15s, border-color .15s;
      white-space: nowrap;
    }
    .btn-provider:hover {
      background: var(--accent-dim);
      color: var(--accent);
      border-color: rgba(79,195,247,.4);
    }
    .btn-provider:active { transform: scale(.96); }
    .btn-provider svg { width:10px; height:10px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }

    .tb-icons { display:flex; align-items:center; gap:4px; margin-left:6px; }
    .tb-icon {
      display:inline-flex; align-items:center; justify-content:center;
      width:30px; height:30px; padding:0;
      background:transparent; border:1px solid var(--line);
      border-radius:var(--radius); cursor:pointer;
      color:var(--ink-muted); transition:background .15s,color .15s,border-color .15s;
    }
    .tb-icon:hover {
      background:var(--accent-dim); color:var(--accent);
      border-color:rgba(79,195,247,.4);
    }
    .tb-icon:active { transform: scale(.94); }
    .tb-icon svg { width:15px; height:15px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }

    .health-row {
      display:flex; align-items:center; justify-content:space-between;
      padding:9px 12px; font-size:11.5px; color:var(--ink);
      border-bottom:1px solid var(--line);
    }
    .health-row:last-child { border-bottom:none; }
    .health-status {
      font-size:13px; font-weight:700; padding:2px 8px; border-radius:3px;
    }
    .health-ok { background:var(--green-dim); color:var(--green); }
    .health-warn { background:var(--amber-dim); color:var(--amber); }
    .health-fail { background:var(--red-dim); color:var(--red); }

    .session-search {
      display:block; width:100%; padding:8px 10px; margin-bottom:10px;
      box-sizing:border-box; background:rgba(255,255,255,.04);
      border:1px solid var(--line); border-radius:var(--radius);
      color:var(--ink); font-family:'DM Mono',monospace; font-size:11px;
      outline:none; transition:border-color .15s;
    }
    .session-search:focus { border-color:rgba(79,195,247,.4); }
    .session-item {
      display:flex; align-items:center; justify-content:space-between;
      padding:9px 12px; font-size:11.5px; color:var(--ink-muted);
      border-bottom:1px solid var(--line); cursor:pointer;
      transition:background .12s;
    }
    .session-item:last-child { border-bottom:none; }
    .session-item:hover { background:rgba(255,255,255,.04); color:var(--ink); }
    .session-item .ses-meta { font-size:10px; color:var(--ink-muted); opacity:.7; }

    .shortcut-row {
      display:flex; align-items:center; justify-content:space-between;
      padding:8px 12px; font-size:11.5px; color:var(--ink);
      border-bottom:1px solid var(--line);
    }
    .shortcut-row:last-child { border-bottom:none; }
    .shortcut-key {
      font-family:'DM Mono',monospace; font-size:10.5px; font-weight:600;
      padding:2px 8px; background:var(--accent-dim); color:var(--accent);
      border:1px solid rgba(79,195,247,.25); border-radius:3px;
    }
  </style>
  {RESPONSIVE_CSS}
</head>
<body>

  <div id="topbar">
    <div class="logo">
      <span class="logo-p">Pesquis</span><span class="logo-ai">AI</span>
      <span>  <a href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/CHANGELOG.md" target="_blank" class="logo-tag"> v{__VERSION__} </a> </span>
    </div>

    <div class="status">
      <span class="status-dot"></span>
      <span data-i18n="ui.status_active">agente ativo</span>
    </div>

    <div class="tb-icons">
      <button class="tb-icon" onclick="openAgents()" title="Diretrizes do Agente" data-i18n-title="agents.title">
        <svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M9 7h7M9 11h7"/></svg>
      </button>
      <button class="tb-icon" onclick="openHealth()" title="Dashboard de Saúde" data-i18n-title="dashboard.title">
        <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </button>
      <button class="tb-icon" onclick="openSessions()" title="Histórico de Sessões" data-i18n-title="sessions.title">
        <svg viewBox="0 0 24 24"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/></svg>
      </button>
      <button class="tb-icon" onclick="openShortcuts()" title="Atalhos de Teclado" data-i18n-title="shortcuts.title">
        <svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10"/></svg>
      </button>
      <button class="tb-icon" onclick="toggleTheme()" id="theme-toggle" title="Alternar tema" data-theme="pesquisai" data-i18n-title="theme.toggle">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
      </button>
      <button class="lang-btn" id="lang-btn" onclick="toggleLangMenu()" aria-haspopup="true" aria-expanded="false" title="Idioma / Language">
        <span class="lang-flag" id="lang-flag">🇧🇷</span>
        <span class="lang-code" id="lang-code">PT</span>
        <span class="lang-chevron" aria-hidden="true"></span>
      </button>
      <button class="hamburger" onclick="toggleMobileMenu()" title="Menu" id="hamburger-btn" aria-label="Abrir menu">
        <svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
    </div>
    <div class="sep"></div>

    <button class="tb-btn btn-backup" onclick="doBackup()">
      <svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      <span data-i18n="ui.backup">Salvar backup</span>
    </button>

    <button class="tb-btn btn-restore" onclick="openRestore()">
      <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>
      <span data-i18n="ui.restore">Restaurar</span>
    </button>

    <a href="{__DRIVE_URL__}" target="_blank" class="tb-btn btn-drive">
      <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      <span data-i18n="ui.drive">Drive</span>
    </a>

  </div>

  <!-- Mobile menu (drawer) — espelha o topbar em mobile -->
  <div class="mobile-menu-overlay" id="mobile-overlay" onclick="toggleMobileMenu()"></div>
  <div class="mobile-menu" id="mobile-menu" aria-hidden="true">
    <button class="tb-btn btn-backup" onclick="doBackup(); toggleMobileMenu();">
      <svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      <span data-i18n="ui.backup">Salvar backup</span>
    </button>
    <button class="tb-btn btn-restore" onclick="openRestore(); toggleMobileMenu();">
      <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>
      <span data-i18n="ui.restore">Restaurar</span>
    </button>
    <a href="{__DRIVE_URL__}" target="_blank" class="tb-btn btn-drive" onclick="toggleMobileMenu()">
      <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      <span data-i18n="ui.drive">Drive</span>
    </a>
    <button class="btn-provider" onclick="connectProvider(); toggleMobileMenu();" style="width:100%;justify-content:flex-start;">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>
      <span data-i18n="providers.title">+ provedor</span>
    </button>
    <div style="height:1px;background:var(--line);margin:8px 0;"></div>
    <button class="modal-close" onclick="openAgents(); toggleMobileMenu();">📋 <span data-i18n="agents.title">Diretrizes do Agente</span></button>
    <button class="modal-close" onclick="openHealth(); toggleMobileMenu();">🩺 <span data-i18n="dashboard.title">Dashboard de Saúde</span></button>
    <button class="modal-close" onclick="openSessions(); toggleMobileMenu();">📜 <span data-i18n="sessions.title">Histórico de Sessões</span></button>
    <button class="modal-close" onclick="openShortcuts(); toggleMobileMenu();">⌨️ <span data-i18n="shortcuts.title">Atalhos de Teclado</span></button>
    <button class="modal-close" onclick="toggleTheme(); toggleMobileMenu();">◑ <span data-i18n="theme.toggle">Alternar Tema</span></button>
    <button class="modal-close" onclick="toggleLangMenu();">🌐 <span data-i18n="languages.label">Idioma</span></button>
  </div>

  <!-- Dropdown de idioma (NOVO em v0.4.1) -->
  <div class="lang-menu" id="lang-menu" role="menu" aria-label="Idioma / Language">
    <!-- Preenchido dinamicamente por buildLangMenu() -->
  </div>

 <iframe
  id="terminal-frame"
  src="{__TERMINAL_URL__}"
  allow="clipboard-read; clipboard-write"
  tabindex="0"
  autofocus
  style="width:100%; height:calc(100% - 90px); border:none; outline:none;">
</iframe>

  <div id="footer">
    <!-- LINHA 1: marca + contatos (v0.4.2: separado em row-1/row-2 para mobile) -->
    <div class="footer-row-1">
      <span class="footer-brand">PesquisAI</span>
      <span class="footer-sep"></span>
      <a href="mailto:gustavo.braga@ufv.br" class="footer-link" data-i18n-title="footer.email_title" title="Contato por e-mail">
        <svg viewBox="0 0 24 24"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
        <span data-i18n="footer.email">gustavo.braga@ufv.br</span>
      </a>
      <span class="footer-sep"></span>
      <a href="https://github.com/gustavobraga-byte/PesquisAI" target="_blank" class="footer-link footer-link-footer-github" data-i18n-title="footer.github_title" title="Repositório no GitHub">
        <svg viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
        <span data-i18n="footer.github">GitHub</span>
      </a>
      <span class="footer-sep"></span>
      <span class="footer-ufv" data-i18n="footer.ufv">UFV · Viçosa, MG - Brasil</span>
    </div>

    <!-- LINHA 2: provedor + OpenCode -->
    <div class="footer-row-2">
      <button class="btn-provider" onclick="connectProvider()" data-i18n-title="providers.title" title="Conectar novo provedor de IA">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>
        <span data-i18n="providers.title">+ provedor</span>
      </button>
      <span class="footer-oc">
        <span data-i18n="footer.powered_by">Powered by</span> <a href="https://opencode.ai" target="_blank">OpenCode</a>
      </span>
    </div>
  </div>

  <div id="toast"></div>

  <div id="modal-overlay" onclick="if(event.target===this)closeModal()">
    <div id="modal">
      <div class="modal-title">🔄 <span data-i18n="ui.restore">Restaurar Sessão</span></div>
      <div class="backup-list" id="backup-list">
        <div class="modal-empty" data-i18n="ui.loading">Carregando backups…</div>
      </div>
      <button class="modal-close" onclick="closeModal()" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="provider-overlay" onclick="if(event.target===this)closeProvider()" style="position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div class="modal-shell" style="border-radius:10px;padding:24px;width:480px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div id="prov-step1">
        <div class="modal-title">🔌 <span data-i18n="providers.title">Conectar Provedor de IA</span></div>
        <p style="font-size:11.5px;color:var(--ink-muted);margin-bottom:14px;line-height:1.6;" data-i18n="providers.select">Selecione o provedor para configurar a API key:</p>
        <div id="prov-list" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;"></div>
        <button onclick="closeProvider()" style="display:block;width:100%;padding:8px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;" data-i18n="ui.cancel">Cancelar</button>
      </div>
      <div id="prov-step2" style="display:none;">
        <div class="modal-title">🔑 <span id="prov-name-title"></span></div>
        <p style="font-size:11px;color:var(--ink-muted);margin-bottom:14px;line-height:1.5;"><span data-i18n="providers.var">Variável</span>: <code id="prov-env-code" style="color:var(--accent);background:rgba(79,195,247,.08);padding:1px 6px;border-radius:3px;font-size:11px;"></code></p>
        <label style="display:block;font-size:10.5px;color:var(--ink-muted);margin-bottom:6px;letter-spacing:.05em;" data-i18n="providers.api_key">API KEY</label>
        <input id="prov-key-input" type="password" placeholder="Cole sua key aqui…" autocomplete="off" style="display:block;width:100%;padding:9px 12px;box-sizing:border-box;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink);font-family:'DM Mono',monospace;font-size:12px;outline:none;margin-bottom:14px;transition:border-color .15s;" onfocus="this.style.borderColor='rgba(79,195,247,.4)'" onblur="this.style.borderColor='var(--line)'" onkeydown="if(event.key==='Enter')confirmProvider()"/>
        <div style="display:flex;gap:8px;">
          <button onclick="provBack()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;" data-i18n="providers.back">← Voltar</button>
          <button onclick="confirmProvider()" style="flex:1;padding:9px;background:var(--accent-dim);border:1px solid rgba(79,195,247,.3);border-radius:var(--radius);color:var(--accent);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;" data-i18n="providers.save_connect">Salvar e Conectar</button>
          <button onclick="closeProvider()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;" data-i18n="ui.cancel">Cancelar</button>
        </div>
      </div>
    </div>
  </div>

  <div id="health-overlay" onclick="if(event.target===this)closeHealth()" style="position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div class="modal-shell" style="border-radius:10px;padding:24px;width:440px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">🩺 <span data-i18n="dashboard.title">Dashboard de Saúde</span></div>
      <div id="health-list" style="max-height:340px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty" data-i18n="ui.loading">Carregando diagnóstico…</div>
      </div>
      <button onclick="closeHealth()" class="modal-close" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="sessions-overlay" onclick="if(event.target===this)closeSessions()" style="position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div class="modal-shell" style="border-radius:10px;padding:24px;width:520px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">📜 <span data-i18n="sessions.title">Histórico de Sessões</span></div>
      <input id="session-search" class="session-search" placeholder="🔍 Buscar por id ou conteúdo…" oninput="filterSessions()" data-i18n-placeholder="sessions.search_placeholder">
      <div id="session-list" style="max-height:300px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty" data-i18n="ui.loading">Carregando sessões…</div>
      </div>
      <button onclick="closeSessions()" class="modal-close" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="shortcuts-overlay" onclick="if(event.target===this)closeShortcuts()" style="position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div class="modal-shell" style="border-radius:10px;padding:24px;width:420px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">⌨️ <span data-i18n="shortcuts.title">Atalhos de Teclado</span></div>
      <div style="border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="shortcut-row"><span data-i18n="shortcuts.copy">Copiar seleção</span><span class="shortcut-key" data-i18n="shortcuts.copy_hint">Segure o Shift e selecione</span></div>
        <div class="shortcut-row"><span data-i18n="shortcuts.interrupt">Interromper comando</span><span class="shortcut-key">Ctrl+C</span></div>
        <div class="shortcut-row"><span data-i18n="shortcuts.paste">Colar (Chrome)</span><span class="shortcut-key">Ctrl+Shift+V</span></div>
        <div class="shortcut-row"><span data-i18n="shortcuts.menu">Menu e opções</span><span class="shortcut-key">Ctrl+P</span></div>
        <div class="shortcut-row"><span data-i18n="shortcuts.model">Alterar modelo</span><span class="shortcut-key">Ctrl+X m</span></div>
        <div class="shortcut-row"><span data-i18n="shortcuts.history_prev">Histórico anterior</span><span class="shortcut-key">↑</span></div>
        <div class="shortcut-row"><span data-i18n="shortcuts.history_next">Histórico seguinte</span><span class="shortcut-key">↓</span></div>
      </div>
      <button onclick="closeShortcuts()" class="modal-close" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <!-- Modal de Diretrizes do Agente (v0.4.2 + markdown render v0.4.2.1) -->
  <div id="agents-overlay" onclick="if(event.target===this)closeAgents()" style="position:fixed;inset:0;background:rgba(0,0,0,.78);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div id="agents-modal" class="modal-shell" style="border-radius:10px;padding:0;width:680px;max-width:94vw;max-height:88vh;box-shadow:0 28px 72px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <div style="padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;">
        <span style="font-size:18px;">📋</span>
        <div style="flex:1;min-width:0;">
          <div class="modal-title" style="margin-bottom:2px;" data-i18n="agents.title">Diretrizes do Agente</div>
          <div style="font-size:10.5px;color:var(--ink-muted);" data-i18n="agents.subtitle">Regras e princípios do PesquisAI (AGENTS.md)</div>
        </div>
        <span id="agents-lang-badge" style="font-size:10px;padding:2px 8px;border:1px solid var(--line);border-radius:3px;color:var(--ink-muted);font-family:'DM Mono',monospace;">PT-BR</span>
        <button onclick="closeAgents()" class="modal-close" style="width:auto;padding:4px 10px;font-size:11px;" aria-label="Fechar">✕</button>
      </div>
      <div id="agents-content" class="markdown-body" style="flex:1;overflow-y:auto;padding:22px 26px;font-size:12.5px;line-height:1.65;color:var(--ink);background:transparent;" data-i18n="agents.loading">Carregando diretrizes…</div>
      <div style="padding:10px 18px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.02);">
        <button onclick="copyAgents()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="agents.copy">Copiar</button>
        <button onclick="reloadAgents()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;">↻ <span data-i18n="ui.loading">Recarregar</span></button>
        <div style="flex:1;"></div>
        <a id="agents-source-link" href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/agents/AGENTS.pt.md" target="_blank" class="footer-link" style="font-size:10.5px;" data-i18n="agents.open_source">Ver fonte</a>
      </div>
    </div>
  </div>

  <script>
    // ════════════════════════════════════════════════════════════
    // PesquisAI v0.4.1 — Patch corretivo
    // (1) Responsividade, (2) Tema recarrega terminal, (3) Idioma UI
    // ════════════════════════════════════════════════════════════

    const BASE = location.origin;
    const LANGS = {__LANGS_JSON__};
    const I18N = {__I18N_JSON__};
    const LANG_COOKIE = "pesquisai_lang";
    const THEME_COOKIE = "pesquisai_theme";
    const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 ano

    // ── Cookie helpers ────────────────────────────────────────
    function setCookie(name, value) {
      document.cookie = name + "=" + encodeURIComponent(value) +
        "; path=/; max-age=" + COOKIE_MAX_AGE + "; SameSite=Lax";
    }
    function getCookie(name) {
      const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
      return m ? decodeURIComponent(m[2]) : null;
    }

    // ── Detecção de idioma (URL > cookie > navegador > padrão) ─
    function getCurrentLang() {
      // 1. Query param ?lang=xx_XX (forçar via link)
      const url = new URL(location.href);
      const ql = url.searchParams.get("lang");
      if (ql && LANGS[ql]) {
        setCookie(LANG_COOKIE, ql);
        return ql;
      }
      // 2. Cookie persistido
      const ck = getCookie(LANG_COOKIE);
      if (ck && LANGS[ck]) return ck;
      // 3. localStorage (fallback)
      try {
        const ls = localStorage.getItem(LANG_COOKIE);
        if (ls && LANGS[ls]) return ls;
      } catch (e) {}
      // 4. navigator.language (navegador)
      const nav = (navigator.language || "pt-BR").toLowerCase();
      if (nav.startsWith("pt")) return "pt_BR";
      if (nav.startsWith("en")) return "en_US";
      if (nav.startsWith("es")) return "es_ES";
      if (nav.startsWith("fr")) return "fr_FR";
      // 5. Padrão
      return "pt_BR";
    }

    let _currentLang = getCurrentLang();

    function applyLang(lang) {
      if (!LANGS[lang]) lang = "pt_BR";
      _currentLang = lang;
      // 1. Atualiza atributo <html lang>
      const htmlLang = lang.replace("_", "-");
      document.documentElement.lang = htmlLang;
      // 2. Atualiza strings da UI (data-i18n)
      const dict = I18N[lang] || I18N["pt_BR"];
      document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (dict[key]) el.textContent = dict[key];
      });
      // 3. Atualiza títulos (data-i18n-title)
      document.querySelectorAll("[data-i18n-title]").forEach(el => {
        const key = el.getAttribute("data-i18n-title");
        if (dict[key]) el.title = dict[key];
      });
      // 4. Atualiza placeholders (data-i18n-placeholder)
      document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (dict[key]) el.placeholder = dict[key];
      });
      // 5. Atualiza botão de idioma
      const flagEl = document.getElementById("lang-flag");
      const codeEl = document.getElementById("lang-code");
      if (flagEl) flagEl.textContent = LANGS[lang].flag;
      if (codeEl) codeEl.textContent = LANGS[lang].short;
      // 6. Marca idioma ativo no menu
      document.querySelectorAll(".lang-option").forEach(opt => {
        if (opt.dataset.lang === lang) {
          opt.setAttribute("aria-current", "true");
        } else {
          opt.removeAttribute("aria-current");
        }
      });
      // 7. Persiste
      setCookie(LANG_COOKIE, lang);
      try { localStorage.setItem(LANG_COOKIE, lang); } catch (e) {}
    }

    function setLang(lang) {
      // Persiste no backend (se disponível) + recarrega para aplicar
      // traduções do backend também
      setCookie(LANG_COOKIE, lang);
      // v0.4.2.2: chama /api/lang POST que reinicia o ttyd com saudação
      // no novo idioma (ao invés de --prompt "oi" genérico)
      try {
        fetch(BASE + "/api/lang", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lang: lang })
        }).then(r => r.json()).then(d => {
          if (d && d.ok) {
            // Mostra a saudação como toast
            const dict2 = I18N[lang] || I18N["pt_BR"];
            toast("🤖 " + (d.greeting || ""), "ok");
          }
        }).catch(() => {});
      } catch (e) {}
      // Aplica imediatamente o que dá (UI strings)
      applyLang(lang);
      // Invalida o cache do AGENTS.md para que recarregue no novo idioma
      // (v0.4.2: troca de AGENTS.md por idioma)
      _agentsCache = null;
      _agentsCacheLang = null;
      // Se o modal de Diretrizes estiver aberto, recarrega o conteúdo
      const agentsOverlay = document.getElementById("agents-overlay");
      if (agentsOverlay && agentsOverlay.style.opacity === "1") {
        loadAgents(true);
      }
      // Toast feedback
      const dict = I18N[lang] || I18N["pt_BR"];
      toast("🌐 " + (dict["languages.switched_to"] || lang), "info");
      // Fecha menu
      closeLangMenu();
      // Recarrega para que backend traduza também (toasts, modais completos)
      setTimeout(() => location.reload(), 1200);
    }

    function buildLangMenu() {
      const menu = document.getElementById("lang-menu");
      if (!menu) return;
      menu.innerHTML = Object.values(LANGS).map(l => `
        <button class="lang-option" data-lang="${l.code}"
                onclick="setLang('${l.code}')"
                role="menuitem"
                aria-current="${l.code === _currentLang ? 'true' : 'false'}">
          <span class="lang-flag">${l.flag}</span>
          <span class="lang-name">${l.name}</span>
          <span class="lang-check">✓</span>
        </button>
      `).join("");
    }

    function toggleLangMenu() {
      const menu = document.getElementById("lang-menu");
      const btn = document.getElementById("lang-btn");
      if (!menu) return;
      const isOpen = menu.classList.contains("open");
      if (isOpen) {
        closeLangMenu();
      } else {
        buildLangMenu();
        menu.classList.add("open");
        if (btn) btn.setAttribute("aria-expanded", "true");
      }
    }

    function closeLangMenu() {
      const menu = document.getElementById("lang-menu");
      const btn = document.getElementById("lang-btn");
      if (menu) menu.classList.remove("open");
      if (btn) btn.setAttribute("aria-expanded", "false");
    }

    // ── Mobile menu toggle ────────────────────────────────────
    function toggleMobileMenu() {
      const menu = document.getElementById("mobile-menu");
      const overlay = document.getElementById("mobile-overlay");
      if (!menu) return;
      const isOpen = menu.classList.contains("open");
      if (isOpen) {
        menu.classList.remove("open");
        if (overlay) overlay.classList.remove("open");
        menu.setAttribute("aria-hidden", "true");
      } else {
        closeLangMenu(); // fecha idioma se aberto
        menu.classList.add("open");
        if (overlay) overlay.classList.add("open");
        menu.setAttribute("aria-hidden", "false");
      }
    }

    let _toastT;
    function toast(msg, type = "info") {
      const el = document.getElementById("toast");
      el.className = "show " + type;
      el.textContent = msg;
      clearTimeout(_toastT);
      _toastT = setTimeout(() => el.classList.remove("show"), 3800);
    }

    async function doBackup() {
      toast("⏳ " + (I18N[_currentLang]?.["ui.exporting"] || "Exportando sessão…"), "info");
      try {
        const r = await fetch(BASE + "/api/backup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({})
        });
        const d = await r.json();
        if (d.ok) {
          toast("✅ " + (I18N[_currentLang]?.["success_messages.backup_saved"] || "Backup salvo") + ": " + d.file, "ok");
        } else {
          toast("❌ " + (d.error || "Erro desconhecido"), "err");
        }
      } catch(e) {
        toast("❌ Falha na conexão: " + e.message, "err");
      }
    }

    async function openRestore() {
      document.getElementById("modal-overlay").classList.add("open");
      const list = document.getElementById("backup-list");
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      list.innerHTML = '<div class="modal-empty">' + (dict["ui.loading"] || "Carregando…") + '</div>';
      try {
        const r = await fetch(BASE + "/api/backups");
        const d = await r.json();
        if (!d.backups || d.backups.length === 0) {
          list.innerHTML = '<div class="modal-empty">Nenhum backup encontrado no Drive.</div>';
          return;
        }
        list.innerHTML = d.backups.map(f => `
          <div class="backup-item" onclick="doRestore('${f}')">
            <span>${f}</span>
            <span class="restore-lbl">${dict["ui.restore"] || "restaurar"}</span>
          </div>
        `).join("");
      } catch(e) {
        list.innerHTML = '<div class="modal-empty">Erro ao carregar backups.</div>';
      }
    }

    function closeModal() {
      document.getElementById("modal-overlay").classList.remove("open");
    }

    async function doRestore(file) {
      closeModal();
      toast("⏳ Importando " + file + "…", "info");
      try {
        const r = await fetch(BASE + "/api/restore", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file })
        });
        const d = await r.json();
        if (d.ok) {
          toast("✅ Importado!", "ok");
          setTimeout(() => location.reload(), 800);
        } else {
          toast("❌ " + (d.error || "Erro"), "err");
        }
      } catch(e) {
        toast("❌ Falha: " + e.message, "err");
      }
    }

    const PROVIDERS = [
      { id:"anthropic", name:"Anthropic", env:"ANTHROPIC_API_KEY", hint:"sk-ant-…" },
      { id:"bedrock", name:"AWS Bedrock", env:"AWS_ACCESS_KEY_ID", hint:"AKIA…" },
      { id:"azure", name:"Azure OpenAI", env:"AZURE_OPENAI_API_KEY", hint:"…" },
      { id:"deepseek", name:"DeepSeek", env:"DEEPSEEK_API_KEY", hint:"sk-…" },
      { id:"google", name:"Google Gemini", env:"GOOGLE_GENERATIVE_AI_API_KEY", hint:"AIza…" },
      { id:"groq", name:"Groq", env:"GROQ_API_KEY", hint:"gsk_…" },
      { id:"mistral", name:"Mistral", env:"MISTRAL_API_KEY", hint:"…" },
      { id:"nvidia", name:"Nvidia NIM", env:"NVIDIA_API_KEY", hint:"nvapi-…" },
      { id:"openai", name:"OpenAI", env:"OPENAI_API_KEY", hint:"sk-…" },
      { id:"opencode_go", name:"OpenCode Go", env:"OPENCODE_API_KEY", hint:"sk-…" },
      { id:"opencode_zen", name:"OpenCode Zen", env:"OPENCODE_API_KEY", hint:"sk-…" },
      { id:"openrouter", name:"OpenRouter", env:"OPENROUTER_API_KEY", hint:"sk-or-…" },
      { id:"together", name:"Together AI", env:"TOGETHER_API_KEY", hint:"…" },
      { id:"vertex", name:"Vertex AI", env:"VERTEX_API_KEY", hint:"…" },
      { id:"xai", name:"xAI (Grok)", env:"XAI_API_KEY", hint:"xai-…" },
    ];

    let _selProv = null;

    function connectProvider() {
      const grid = document.getElementById("prov-list");
      grid.innerHTML = PROVIDERS.map(p => `
        <button onclick="selectProvider('${p.id}')" style="display:flex;align-items:center;gap:8px;padding:9px 12px;background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:'DM Mono',monospace;font-size:11px;cursor:pointer;text-align:left;transition:background .12s,color .12s,border-color .12s;">
          ${p.name}
        </button>
      `).join("");
      document.getElementById("prov-step1").style.display = "block";
      document.getElementById("prov-step2").style.display = "none";
      document.getElementById("prov-key-input").value = "";
      const overlay = document.getElementById("provider-overlay");
      overlay.style.opacity = "1";
      overlay.style.pointerEvents = "all";
    }

    function selectProvider(id) {
      _selProv = PROVIDERS.find(p => p.id === id);
      if (!_selProv) return;
      document.getElementById("prov-name-title").textContent = _selProv.name;
      document.getElementById("prov-env-code").textContent = _selProv.env;
      document.getElementById("prov-key-input").placeholder = _selProv.hint || "Cole sua key aqui…";
      document.getElementById("prov-step1").style.display = "none";
      document.getElementById("prov-step2").style.display = "block";
      setTimeout(() => document.getElementById("prov-key-input").focus(), 80);
    }

    function provBack() {
      document.getElementById("prov-step1").style.display = "block";
      document.getElementById("prov-step2").style.display = "none";
    }

    function closeProvider() {
      const overlay = document.getElementById("provider-overlay");
      overlay.style.opacity = "0";
      overlay.style.pointerEvents = "none";
      _selProv = null;
    }

    async function confirmProvider() {
      const key = document.getElementById("prov-key-input").value.trim();
      if (!key) { toast("⚠️ Insira a API key.", "err"); return; }
      if (!_selProv) { toast("⚠️ Selecione um provedor.", "err"); return; }
      closeProvider();
      toast("💾 Salvando…", "info");
      try {
        await fetch(BASE + "/api/apikey", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: _selProv.id, env: _selProv.env, apikey: key })
        });
        toast("✅ Salvo!", "ok");
      } catch(e) { toast("❌ " + e.message, "err"); }
    }

    async function openHealth() {
      const overlay = document.getElementById("health-overlay");
      const list = document.getElementById("health-list");
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      overlay.style.opacity = "1"; overlay.style.pointerEvents = "all";
      // P3 fix: buscar diagnóstico do backend e popular a lista
      if (list) {
        list.innerHTML = '<div class="modal-empty">' + (dict["ui.loading"] || "Carregando…") + '</div>';
      }
      try {
        const r = await fetch(BASE + "/api/health");
        const d = await r.json();
        renderHealth(d);
      } catch (e) {
        if (list) {
          list.innerHTML = '<div class="modal-empty">❌ ' +
            (dict["agents.error"] || "Erro") + ': ' + e.message + '</div>';
        }
      }
    }
    function closeHealth() {
      const o = document.getElementById("health-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }

    // P3: renderiza o JSON do /api/health em linhas com badges de status
    function renderHealth(d) {
      const list = document.getElementById("health-list");
      if (!list) return;
      if (!d || !d.ok || !d.checks) {
        list.innerHTML = '<div class="modal-empty">⚠️ ' +
          (d && d.error ? d.error : "Sem dados do diagnóstico") + '</div>';
        return;
      }
      const c = d.checks;
      const ROWS = [
        ["drive_mounted",       "Drive montado",     c.drive_mounted],
        ["backup_dir_exists",   "Backup dir",        c.backup_dir_exists],
        ["ttyd_alive",          "Terminal (ttyd)",   c.ttyd_alive],
        ["opencode_found",      "OpenCode binário",  c.opencode_found],
        ["keys_store_exists",   "Keys store",        c.keys_store_exists],
        ["encryption_key_exists","Chave cifra",      c.encryption_key_exists],
        ["ffmpeg_ok",           "ffmpeg",            c.ffmpeg_ok],
      ];
      // Conta skills carregadas
      const skillCount = c.skills_count || (c.skills_loaded ? c.skills_loaded.length : 0);
      ROWS.push(["skills_count", "Skills carregadas", skillCount, skillCount + " disponíveis"]);
      // Keys carregadas
      ROWS.push(["keys_loaded", "API keys em env",
        (c.keys_loaded_count || 0) > 0,
        (c.keys_loaded_count || 0) + " ativas: " + (c.keys_loaded || []).join(", ")]);
      // Disco
      if (c.disk_free_mb >= 0) {
        const freeGb = (c.disk_free_mb / 1024).toFixed(1);
        const totalGb = (c.disk_total_mb / 1024).toFixed(1);
        ROWS.push(["disk", "Espaço em disco",
          c.disk_free_mb > 500, freeGb + " GB livres de " + totalGb + " GB"]);
      }
      // Versão
      if (d.version) {
        ROWS.push(["version", "PesquisAI", true, "v" + d.version]);
      }

      list.innerHTML = ROWS.map(r => {
        const key = r[0], label = r[1], ok = r[2], meta = r[3];
        const badge = ok === true ? "health-ok" : (ok === false ? "health-fail" : "health-warn");
        const symbol = ok === true ? "✓" : (ok === false ? "✗" : "·");
        const value = meta !== undefined ? meta : (ok ? "ok" : "falha");
        return '<div class="health-row">' +
               '<span>' + label + '</span>' +
               '<span class="health-status ' + badge + '">' + symbol + ' ' + value + '</span>' +
               '</div>';
      }).join("");
    }

    let _allSessions = [];
    // v0.4.2.2: openSessions() agora faz fetch em /api/sessions
    // (antes só abria o overlay sem carregar a lista)
    async function openSessions() {
      const overlay = document.getElementById("sessions-overlay");
      const list = document.getElementById("session-list");
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      if (overlay) {
        overlay.style.opacity = "1";
        overlay.style.pointerEvents = "all";
      }
      // Mostra estado de carregamento
      if (list) {
        list.innerHTML = '<div class="modal-empty">' +
          (dict["ui.loading"] || "Carregando sessões…") + '</div>';
      }
      // Filtro de busca — mantém o valor digitado
      const search = document.getElementById("session-search");
      const q = (search && search.value || "").trim().toLowerCase();
      try {
        const r = await fetch(BASE + "/api/sessions");
        const d = await r.json();
        const sessions = d.sessions || [];
        _allSessions = sessions;
        renderSessions(sessions, q);
      } catch (e) {
        if (list) {
          list.innerHTML = '<div class="modal-empty">❌ ' +
            (dict["agents.error"] || "Erro") + ': ' + e.message + '</div>';
        }
      }
    }

    function renderSessions(sessions, query) {
      const list = document.getElementById("session-list");
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      if (!list) return;
      const filtered = (query
        ? sessions.filter(s => {
            const id = (s.id || s.session_id || s.name || "").toLowerCase();
            const title = (s.title || s.summary || "").toLowerCase();
            return id.includes(query) || title.includes(query);
          })
        : sessions);
      if (!filtered.length) {
        list.innerHTML = '<div class="modal-empty">' +
          (query
            ? (dict["sessions.empty_filtered"] || "Nenhuma sessão corresponde ao filtro.")
            : (dict["sessions.empty"] || "Nenhuma sessão encontrada.")) +
          '</div>';
        return;
      }
      list.innerHTML = filtered.map(s => {
        const id = s.id || s.session_id || s.name || "(sem id)";
        const title = s.title || s.summary || "";
        const created = s.created_at || s.created || s.updated_at || "";
        const messages = s.message_count || s.messages || s.messages_count || "";
        const meta = [created, messages ? (messages + " msgs") : ""].filter(Boolean).join(" · ");
        return '<div class="session-item" data-session-id="' + escapeHtml(String(id)) + '" title="' +
          (dict["sessions.click_to_restore"] || "Clique para restaurar") + '">' +
          '<div style="display:flex;flex-direction:column;gap:2px;min-width:0;">' +
            '<span style="font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
              escapeHtml(id) + '</span>' +
            (title ? '<span style="font-size:10.5px;color:var(--ink-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
              escapeHtml(title) + '</span>' : '') +
          '</div>' +
          (meta ? '<span class="ses-meta">' + escapeHtml(meta) + '</span>' : '') +
        '</div>';
      }).join("");
    }

    function filterSessions() {
      const search = document.getElementById("session-search");
      const q = (search && search.value || "").trim().toLowerCase();
      renderSessions(_allSessions, q);
    }

    // Event delegation: cliques em .session-item chamam restoreSession(id)
    document.addEventListener("click", (ev) => {
      const item = ev.target.closest(".session-item");
      if (item && item.dataset.sessionId) {
        ev.preventDefault();
        restoreSession(item.dataset.sessionId);
      }
    });

    async function restoreSession(sessionId) {
      if (!sessionId) return;
      if (!confirm("Restaurar sessão " + chr(34) + sessionId + chr(34) + " ?")) return;
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      toast(dict["ui.exporting"] || "Restaurando sessão…", "info");
      try {
        const r = await fetch(BASE + "/api/restore", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId })
        });
        const d = await r.json();
        if (d.ok || d.imported) {
          toast("✅ Sessão restaurada!", "ok");
        } else {
          toast("❌ " + (d.error || "Falha ao restaurar."), "err");
        }
      } catch (e) {
        toast("❌ " + e.message, "err");
      }
    }

    function escapeHtml(s) {
      const map = {
        amp: "&amp;",
        lt:  "&lt;",
        gt:  "&gt;",
        quot: "&quot;",
        apos: "&#39;",
        "0":  "&#39;"
      };
      return String(s).replace(/[&<>"']/g, c => {
        if (c === "&") return "&amp;";
        if (c === "<") return "&lt;";
        if (c === ">") return "&gt;";
        if (c === '"') return "&quot;";
        if (c === "'") return "&#39;";
        return c;
      });
    }

    function closeSessions() {
      const o = document.getElementById("sessions-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }

    function openShortcuts() {
      const o = document.getElementById("shortcuts-overlay");
      o.style.opacity = "1"; o.style.pointerEvents = "all";
    }
    function closeShortcuts() {
      const o = document.getElementById("shortcuts-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }

    // ── Modal de Diretrizes do Agente (v0.4.2) ─────────────────
    // Carrega o AGENTS.md no idioma atual do backend.
    // Endpoint: GET /api/agents?lang=pt_BR
    let _agentsCache = null;
    let _agentsCacheLang = null;

    async function openAgents() {
      const overlay = document.getElementById("agents-overlay");
      if (overlay) {
        overlay.style.opacity = "1";
        overlay.style.pointerEvents = "all";
      }
      await loadAgents();
    }

    function closeAgents() {
      const overlay = document.getElementById("agents-overlay");
      if (overlay) {
        overlay.style.opacity = "0";
        overlay.style.pointerEvents = "none";
      }
    }

    async function loadAgents(forceReload = false) {
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const contentEl = document.getElementById("agents-content");
      const badgeEl = document.getElementById("agents-lang-badge");
      const sourceEl = document.getElementById("agents-source-link");
      if (!contentEl) return;

      // Atualiza badge do idioma + link da fonte
      const langShort = (_currentLang || "pt_BR").replace("_", "-");
      if (badgeEl) badgeEl.textContent = langShort;
      if (sourceEl) {
        const code = (_currentLang || "pt_BR").split("_")[0];
        sourceEl.href = "https://github.com/gustavobraga-byte/PesquisAI/blob/main/agents/AGENTS." + code + ".md";
      }

      // Cache: 1 chamada por idioma até forceReload
      if (!forceReload && _agentsCacheLang === _currentLang && _agentsCache) {
        renderAgentsContent(contentEl, _agentsCache);
        return;
      }

      contentEl.textContent = dict["agents.loading"] || "Carregando diretrizes…";

      try {
        const r = await fetch(BASE + "/api/agents?lang=" + encodeURIComponent(_currentLang));
        const d = await r.json();
        if (d.ok && d.content) {
          _agentsCache = d.content;
          _agentsCacheLang = _currentLang;
          renderAgentsContent(contentEl, d.content);
        } else {
          contentEl.textContent = dict["agents.error"] || "Erro ao carregar diretrizes.";
        }
      } catch (e) {
        contentEl.textContent = (dict["agents.error"] || "Erro") + " — " + e.message;
      }
    }

    // P4 fix: renderiza o markdown do AGENTS.md usando marked.js + github-markdown-css
    // (substitui textContent cru por HTML formatado)
    function renderAgentsContent(el, mdText) {
      try {
        if (typeof marked !== "undefined") {
          // Configurações do marked
          marked.setOptions({ breaks: true, gfm: true, headerIds: true });
          // Remove o frontmatter YAML (entre --- e ---) para não poluir a renderização.
          // Constrói a regex via String.fromCharCode para evitar SyntaxWarning
          // quando py_compile lê este arquivo como string Python.
          const _b = String.fromCharCode(92);  // caractere barra invertida
          const _re = new RegExp(
            "^---" + _b + "s*" + _b + "n[" + _b + "s" + _b + "S]*?" +
            _b + "n---" + _b + "s*" + _b + "n"
          );
          const cleaned = mdText.replace(_re, "");
          el.innerHTML = marked.parse(cleaned);
        } else {
          // Fallback se CDN do marked falhar: mostra como texto pré-formatado
          el.textContent = mdText;
        }
      } catch (e) {
        el.textContent = mdText;
        console.error("Erro ao renderizar markdown:", e);
      }
    }

    function reloadAgents() {
      _agentsCache = null;
      _agentsCacheLang = null;
      loadAgents(true);
    }

    async function copyAgents() {
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const text = _agentsCache || document.getElementById("agents-content").textContent || "";
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          // Fallback para browsers antigos
          const ta = document.createElement("textarea");
          ta.value = text;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
        }
        toast("✅ " + (dict["agents.copy_ok"] || "Diretrizes copiadas!"), "ok");
      } catch (e) {
        toast("❌ " + e.message, "err");
      }
    }

    // ═══════════════════════════════════════════════════════════
    // 🐛 CORREÇÃO 2: toggleTheme() agora RECARREGA o iframe
    // ═══════════════════════════════════════════════════════════
    //
    // O problema era: applyWrapperTheme() mudava só o CSS do wrapper,
    // mas o terminal dentro do iframe (ttyd) continuava com o tema
    // antigo. Agora, após aplicar o tema na UI, recarregamos o iframe
    // com cache-busting, mesmo padrão usado em confirmProvider().
    // ═══════════════════════════════════════════════════════════
    async function toggleTheme() {
      const btn = document.getElementById("theme-toggle");
      const cur = btn.dataset.theme || "pesquisai";
      const next = cur === "pesquisai" ? "pesquisai-light" : "pesquisai";
      const dict = I18N[_currentLang] || I18N["pt_BR"];

      try {
        const r = await fetch(BASE + "/api/theme", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ theme: next })
        });
        const d = await r.json();
        if (d.ok) {
          // 1. Aplica tema na UI imediatamente (feedback visual)
          btn.dataset.theme = next;
          applyWrapperTheme(next);
          setCookie(THEME_COOKIE, next);
          try { localStorage.setItem(THEME_COOKIE, next); } catch (e) {}

          // 2. 🐛 FIX: Recarrega iframe do ttyd para que o terminal
          //    seja renderizado com o novo tema. Mesmo padrão usado em
          //    confirmProvider() / restoreSession() / doRestore().
          toast(next === "pesquisai-light"
            ? "☀️ " + (dict["theme.light"] || "Tema claro (UI + terminal)")
            : "🌙 " + (dict["theme.dark"] || "Tema escuro (UI + terminal)"),
            "info");

          const fr = document.getElementById("terminal-frame");
          if (fr) {
            const origSrc = fr.src.split("?")[0];
            fr.src = "about:blank";
            setTimeout(() => {
              fr.src = origSrc + "?theme=" + next + "&t=" + Date.now();
              toast("✅ " + (dict["theme.terminal_reloaded"] || "Terminal recarregado com novo tema"), "ok");
            }, 3500);
          }
        } else {
          toast("❌ " + (d.error || "Erro ao trocar tema"), "err");
        }
      } catch(e) {
        toast("❌ Erro ao trocar tema: " + e.message, "err");
      }
    }

    function applyWrapperTheme(theme) {
      const root = document.documentElement;
      // Sincroniza classe .theme-light no <html> (usado pelo CSS)
      if (theme === "pesquisai-light") {
        root.classList.add("theme-light");
        root.setAttribute("data-theme", "pesquisai-light");
      } else {
        root.classList.remove("theme-light");
        root.setAttribute("data-theme", "pesquisai");
        // Garante que o body está com fundo escuro (anti-flash)
        root.style.backgroundColor = "#0d0f10";
      }
      if (theme === "pesquisai-light") {
        root.style.setProperty("--ink", "#1f262a");
        root.style.setProperty("--ink-muted", "#4a5a62");
        root.style.setProperty("--surface", "#f5f6f7");
        root.style.setProperty("--rail", "#ffffff");
        root.style.setProperty("--line", "rgba(0,0,0,.1)");
        root.style.setProperty("--accent", "#0288d1");
        root.style.setProperty("--accent-dim", "rgba(2,136,209,.1)");
        root.style.setProperty("--accent-glow", "rgba(2,136,209,.2)");
        root.style.setProperty("--green", "#2e7d32");
        root.style.setProperty("--green-dim", "rgba(46,125,50,.1)");
        root.style.setProperty("--amber", "#e65100");
        root.style.setProperty("--amber-dim", "rgba(230,81,0,.1)");
        root.style.setProperty("--red", "#c62828");
        root.style.setProperty("--red-dim", "rgba(198,40,40,.1)");
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#f5f6f7");
      } else {
        root.style.setProperty("--ink", "#e8e6e0");
        root.style.setProperty("--ink-muted", "#8a8780");
        root.style.setProperty("--surface", "#0d0f10");
        root.style.setProperty("--rail", "#151819");
        root.style.setProperty("--line", "rgba(255,255,255,.07)");
        root.style.setProperty("--accent", "#4fc3f7");
        root.style.setProperty("--accent-dim", "rgba(79,195,247,.12)");
        root.style.setProperty("--accent-glow", "rgba(79,195,247,.22)");
        root.style.setProperty("--green", "#5dba7e");
        root.style.setProperty("--green-dim", "rgba(93,186,126,.12)");
        root.style.setProperty("--amber", "#e8b84b");
        root.style.setProperty("--amber-dim", "rgba(232,184,75,.12)");
        root.style.setProperty("--red", "#e07070");
        root.style.setProperty("--red-dim", "rgba(224,112,112,.12)");
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#0d0f10");
      }
    }

    // Carrega tema inicial: 1) script anti-flash no <head> 2) cookie 3) GET /api/theme
    // PADRÃO: ESCURO. Só troca para claro se cookie/servidor persistir.
    async function loadInitialTheme() {
      // 1. O tema já foi aplicado pelo script anti-flash no <head>
      //    (verifica o data-theme atual e sincroniza o botão)
      const currentDataTheme = document.documentElement.getAttribute("data-theme") || "pesquisai";
      const themeBtn = document.getElementById("theme-toggle");
      if (themeBtn) themeBtn.dataset.theme = currentDataTheme;

      // 2. Cookie (carregamento instantâneo, sem flash — sobrescreve se divergir)
      const ck = getCookie(THEME_COOKIE);
      if (ck === "pesquisai-light" || ck === "pesquisai") {
        if (ck !== currentDataTheme) {
          themeBtn.dataset.theme = ck;
          applyWrapperTheme(ck);
        }
      }
      // 3. Servidor (fonte da verdade — sobrescreve cookie se divergir)
      try {
        const r = await fetch(BASE + "/api/theme");
        const d = await r.json();
        if (d.theme === "pesquisai-light" || d.theme === "pesquisai") {
          if (d.theme !== currentDataTheme) {
            themeBtn.dataset.theme = d.theme;
            applyWrapperTheme(d.theme);
          }
          setCookie(THEME_COOKIE, d.theme);
          try { localStorage.setItem(THEME_COOKIE, d.theme); } catch (e) {}
        }
      } catch(e) {}
    }

    // ── Listeners globais ─────────────────────────────────────
    document.addEventListener("keydown", (e) => {
      if (e.key === "?" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
        e.preventDefault();
        openShortcuts();
      }
      if (e.key === "Escape") {
        closeHealth(); closeSessions(); closeShortcuts(); closeAgents();
        closeProvider(); closeModal(); closeLangMenu();
        const mm = document.getElementById("mobile-menu");
        if (mm && mm.classList.contains("open")) toggleMobileMenu();
      }
    });

    // Click fora do menu de idioma fecha
    document.addEventListener("click", (e) => {
      const menu = document.getElementById("lang-menu");
      const btn = document.getElementById("lang-btn");
      if (menu && menu.classList.contains("open")) {
        if (!menu.contains(e.target) && !btn.contains(e.target)) {
          closeLangMenu();
        }
      }
    });

    // ── Inicialização ────────────────────────────────────────
    window.addEventListener("load", () => {
      // 1. Aplica idioma (síncrono, sem flash)
      applyLang(_currentLang);
      buildLangMenu();
      // 2. Carrega tema
      loadInitialTheme();
      // 3. Aplica keys no ambiente
      fetch(BASE + "/api/apikey/apply", { method: "POST" }).catch(() => {});
    });
  </script>
</body>
</html>"""

    # ── Injeta dicionário de idiomas como JSON válido ─────────
    import json as _json
    langs_dict = {l["code"]: l for l in SUPPORTED_LANGUAGES}

    # Substitui placeholders do template (feito DEPOIS da f-string)
    html = html.replace("{__TERMINAL_URL__}", terminal_url)
    html = html.replace("{__DRIVE_URL__}", drive_url)
    html = html.replace("{__VERSION__}", VERSION)
    html = html.replace("{RESPONSIVE_CSS}", RESPONSIVE_CSS)

    i18n_inline: dict[str, dict[str, str]] = {
        "pt_BR": {
            "ui.backup": "Salvar backup", "ui.restore": "Restaurar",
            "ui.drive": "Drive", "ui.close": "Fechar", "ui.cancel": "Cancelar",
            "ui.loading": "Carregando…", "ui.status_active": "agente ativo",
            "ui.exporting": "Exportando sessão…",
            "dashboard.title": "Dashboard de Saúde",
            "providers.title": "Conectar Provedor de IA",
            "providers.select": "Selecione o provedor para configurar a API key:",
            "providers.api_key": "API KEY", "providers.back": "← Voltar",
            "providers.save_connect": "Salvar e Conectar",
            "providers.var": "Variável",
            "sessions.title": "Histórico de Sessões",
            "sessions.search_placeholder": "🔍 Buscar por id ou conteúdo…",
            "sessions.empty": "Nenhuma sessão encontrada.",
            "sessions.empty_filtered": "Nenhuma sessão corresponde ao filtro.",
            "sessions.click_to_restore": "Clique para restaurar",
            "shortcuts.title": "Atalhos de Teclado",
            "shortcuts.copy": "Copiar seleção", "shortcuts.copy_hint": "Segure o Shift e selecione",
            "shortcuts.interrupt": "Interromper comando", "shortcuts.paste": "Colar (Chrome)",
            "shortcuts.menu": "Menu e opções", "shortcuts.model": "Alterar modelo",
            "shortcuts.history_prev": "Histórico anterior", "shortcuts.history_next": "Histórico seguinte",
            "theme.toggle": "Alternar tema", "theme.light": "Tema claro (UI + terminal)",
            "theme.dark": "Tema escuro (UI + terminal)",
            "theme.terminal_reloaded": "Terminal recarregado com novo tema",
            "languages.label": "Idioma", "languages.switched_to": "Idioma alterado para",
            "success_messages.backup_saved": "Backup salvo",
            "footer.email": "gustavo.braga@ufv.br",
            "footer.github": "GitHub",
            "footer.ufv": "UFV · Viçosa, MG - Brasil",
            "footer.powered_by": "Powered by",
            "footer.email_title": "Contato por e-mail",
            "footer.github_title": "Repositório no GitHub",
            "agents.title": "Diretrizes do Agente",
            "agents.subtitle": "Regras e princípios do PesquisAI (AGENTS.md)",
            "agents.loading": "Carregando diretrizes…",
            "agents.error": "Erro ao carregar diretrizes do agente.",
            "agents.copy_ok": "Diretrizes copiadas!",
            "agents.copy": "Copiar",
            "agents.open_source": "Ver fonte",
        },
        "en_US": {
            "ui.backup": "Save backup", "ui.restore": "Restore",
            "ui.drive": "Drive", "ui.close": "Close", "ui.cancel": "Cancel",
            "ui.loading": "Loading…", "ui.status_active": "agent active",
            "ui.exporting": "Exporting session…",
            "dashboard.title": "Health Dashboard",
            "providers.title": "Connect AI Provider",
            "providers.select": "Select the provider to configure the API key:",
            "providers.api_key": "API KEY", "providers.back": "← Back",
            "providers.save_connect": "Save and Connect",
            "providers.var": "Variable",
            "sessions.title": "Session History",
            "sessions.search_placeholder": "🔍 Search by id or content…",
            "sessions.empty": "No sessions found.",
            "sessions.empty_filtered": "No sessions match the filter.",
            "sessions.click_to_restore": "Click to restore",
            "shortcuts.title": "Keyboard Shortcuts",
            "shortcuts.copy": "Copy selection", "shortcuts.copy_hint": "Hold Shift and select",
            "shortcuts.interrupt": "Interrupt command", "shortcuts.paste": "Paste (Chrome)",
            "shortcuts.menu": "Menu and options", "shortcuts.model": "Change model",
            "shortcuts.history_prev": "Previous history", "shortcuts.history_next": "Next history",
            "theme.toggle": "Toggle theme", "theme.light": "Light theme (UI + terminal)",
            "theme.dark": "Dark theme (UI + terminal)",
            "theme.terminal_reloaded": "Terminal reloaded with new theme",
            "languages.label": "Language", "languages.switched_to": "Language switched to",
            "success_messages.backup_saved": "Backup saved",
            "footer.email": "gustavo.braga@ufv.br",
            "footer.github": "GitHub",
            "footer.ufv": "UFV · Viçosa, MG - Brazil",
            "footer.powered_by": "Powered by",
            "footer.email_title": "Contact by email",
            "footer.github_title": "Repository on GitHub",
            "agents.title": "Agent Guidelines",
            "agents.subtitle": "PesquisAI rules and principles (AGENTS.md)",
            "agents.loading": "Loading guidelines…",
            "agents.error": "Error loading agent guidelines.",
            "agents.copy_ok": "Guidelines copied!",
            "agents.copy": "Copy",
            "agents.open_source": "View source",
        },
        "es_ES": {
            "ui.backup": "Guardar copia", "ui.restore": "Restaurar",
            "ui.drive": "Drive", "ui.close": "Cerrar", "ui.cancel": "Cancelar",
            "ui.loading": "Cargando…", "ui.status_active": "agente activo",
            "ui.exporting": "Exportando sesión…",
            "dashboard.title": "Panel de Salud",
            "providers.title": "Conectar Proveedor de IA",
            "providers.select": "Seleccione el proveedor para configurar la API key:",
            "providers.api_key": "API KEY", "providers.back": "← Volver",
            "providers.save_connect": "Guardar y Conectar",
            "providers.var": "Variable",
            "sessions.title": "Historial de Sesiones",
            "sessions.search_placeholder": "🔍 Buscar por id o contenido…",
            "sessions.empty": "No se encontraron sesiones.",
            "sessions.empty_filtered": "Ninguna sesión coincide con el filtro.",
            "sessions.click_to_restore": "Clic para restaurar",
            "shortcuts.title": "Atajos de Teclado",
            "shortcuts.copy": "Copiar selección", "shortcuts.copy_hint": "Mantenga Shift y seleccione",
            "shortcuts.interrupt": "Interrumpir comando", "shortcuts.paste": "Pegar (Chrome)",
            "shortcuts.menu": "Menú y opciones", "shortcuts.model": "Cambiar modelo",
            "shortcuts.history_prev": "Historial anterior", "shortcuts.history_next": "Historial siguiente",
            "theme.toggle": "Alternar tema", "theme.light": "Tema claro (UI + terminal)",
            "theme.dark": "Tema oscuro (UI + terminal)",
            "theme.terminal_reloaded": "Terminal recargado con nuevo tema",
            "languages.label": "Idioma", "languages.switched_to": "Idioma cambiado a",
            "success_messages.backup_saved": "Copia guardada",
            "footer.email": "gustavo.braga@ufv.br",
            "footer.github": "GitHub",
            "footer.ufv": "UFV · Viçosa, MG - Brasil",
            "footer.powered_by": "Desarrollado con",
            "footer.email_title": "Contacto por correo",
            "footer.github_title": "Repositorio en GitHub",
            "agents.title": "Directrices del Agente",
            "agents.subtitle": "Reglas y principios del PesquisAI (AGENTS.md)",
            "agents.loading": "Cargando directrices…",
            "agents.error": "Error al cargar las directrices del agente.",
            "agents.copy_ok": "¡Directrices copiadas!",
            "agents.copy": "Copiar",
            "agents.open_source": "Ver fuente",
        },
        "fr_FR": {
            "ui.backup": "Sauvegarder", "ui.restore": "Restaurer",
            "ui.drive": "Drive", "ui.close": "Fermer", "ui.cancel": "Annuler",
            "ui.loading": "Chargement…", "ui.status_active": "agent actif",
            "ui.exporting": "Exportation de la session…",
            "dashboard.title": "Tableau de bord de santé",
            "providers.title": "Connecter un fournisseur d'IA",
            "providers.select": "Sélectionnez le fournisseur pour configurer la clé API:",
            "providers.api_key": "CLÉ API", "providers.back": "← Retour",
            "providers.save_connect": "Enregistrer et connecter",
            "providers.var": "Variable",
            "sessions.title": "Historique des sessions",
            "sessions.search_placeholder": "🔍 Rechercher par id ou contenu…",
            "sessions.empty": "Aucune session trouvée.",
            "sessions.empty_filtered": "Aucune session ne correspond au filtre.",
            "sessions.click_to_restore": "Cliquer pour restaurer",
            "shortcuts.title": "Raccourcis clavier",
            "shortcuts.copy": "Copier la sélection", "shortcuts.copy_hint": "Maintenez Shift et sélectionnez",
            "shortcuts.interrupt": "Interrompre la commande", "shortcuts.paste": "Coller (Chrome)",
            "shortcuts.menu": "Menu et options", "shortcuts.model": "Changer de modèle",
            "shortcuts.history_prev": "Historique précédent", "shortcuts.history_next": "Historique suivant",
            "theme.toggle": "Basculer le thème", "theme.light": "Thème clair (UI + terminal)",
            "theme.dark": "Thème sombre (UI + terminal)",
            "theme.terminal_reloaded": "Terminal rechargé avec le nouveau thème",
            "languages.label": "Langue", "languages.switched_to": "Langue changée en",
            "success_messages.backup_saved": "Sauvegarde enregistrée",
            "footer.email": "gustavo.braga@ufv.br",
            "footer.github": "GitHub",
            "footer.ufv": "UFV · Viçosa, MG - Brésil",
            "footer.powered_by": "Alimenté par",
            "footer.email_title": "Contact par e-mail",
            "footer.github_title": "Dépôt sur GitHub",
            "agents.title": "Directives de l'Agent",
            "agents.subtitle": "Règles et principes du PesquisAI (AGENTS.md)",
            "agents.loading": "Chargement des directives…",
            "agents.error": "Erreur lors du chargement des directives de l'agent.",
            "agents.copy_ok": "Directives copiées !",
            "agents.copy": "Copier",
            "agents.open_source": "Voir la source",
        },
    }

    html = html.replace("{__LANGS_JSON__}", _json.dumps(langs_dict, ensure_ascii=False))
    html = html.replace("{__I18N_JSON__}", _json.dumps(i18n_inline, ensure_ascii=False))

    # Salva o HTML no diretório wrapper
    os.makedirs(WRAPPER_DIR, exist_ok=True)
    with open(os.path.join(WRAPPER_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    return html


# ── Retrocompatibilidade ───────────────────────────────────────
# Código antigo pode importar ``create_wrapper_html_responsive`` (nome longo).
# Mantemos o alias para não quebrar importações legadas.
create_wrapper_html_responsive = create_wrapper_html


def main() -> None:
    """Função principal para testar a geração standalone."""
    print(f"\n{next_joke('computacao')}")
    print("📱 Gerando wrapper v0.4.1 (responsivo + tema + idioma)...")
    html = create_wrapper_html(
        terminal_url="http://localhost:8000",
        drive_url="https://drive.google.com/drive/my-drive",
    )
    print(f"✅ Wrapper gerado: {len(html):,} caracteres")
    print(f"📂 Salvo em: {os.path.join(WRAPPER_DIR, 'index.html')}")
    print(f"📱 Contém 'mobile-menu': {'mobile-menu' in html}")
    print(f"🍔 Contém 'hamburger-btn': {'hamburger-btn' in html}")
    print(f"🌐 Contém seletor de idioma: {'lang-btn' in html}")
    print(f"🎨 Contém toggleTheme com reload: {'terminal_reloaded' in html}")
    print(f"📐 Media queries: {html.count('@media')}")
    print(f"🗣️ Idiomas suportados: {len(SUPPORTED_LANGUAGES)} (pt_BR, en_US, es_ES, fr_FR)")


if __name__ == "__main__":
    main()
