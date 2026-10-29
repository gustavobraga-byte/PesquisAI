"""
launch_app_responsive.py — Wrapper HTML responsivo + tema + idioma (v0.4.1).

Este módulo SUBSTITUI o `create_wrapper_html` do launch_app.py do PesquisAI
principal (https://github.com/gustavobraga-byte/PesquisAI/blob/main/pesquisai/launch_app.py)
corrigindo 3 problemas reportados pelo usuário em 2026-06-23:

  1. 🐛 Site NÃO responsivo
     - Problema: o CSS original não tem media queries. Topbar de 8 botões
       estoura em mobile, modais de 400-520px não cabem, sem hamburger menu.
     - Correção: 5 breakpoints (mobile pequeno, mobile, tablet, tablet
       portrait, desktop, landscape), hamburger drawer, modais fluidos,
       touch targets ≥ 32-44px (Apple HIG / WCAG 2.5.5).

  2. 🐛 Tema claro/escuro não recarrega o terminal

Este módulo SUBSTITUI o `create_wrapper_html` do launch_app.py do PesquisAI
principal (https://github.com/gustavobraga-byte/PesquisAI/blob/main/pesquisai/launch_app.py)
corrigindo 3 problemas reportados pelo usuário em 2026-06-23:

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
       (fr.src = "about:blank" → 3.5s → fr.src = origSrc + "?t=..."),
       mesmo padrão usado em confirmProvider()/restoreSession().

  3. 🐛 Alteração de idioma sem opção na interface
     - Problema: o módulo i18n existe (4 idiomas, JSONs completos) mas
       não há seletor na topbar. O usuário não tem como trocar idioma.
     - Correção: dropdown na topbar com 🇧🇷 🇺🇸 🇪🇸 🇫🇷, persistência em
       cookie `pesquisai_lang`, query param `?lang=xx_XX`, atualização
       do atributo <html lang="..."> e das strings visíveis (toasts,
       modais, botões).

Instalação:
    Editar ``pesquisai/launch_app.py`` e substituir a função
    ``create_wrapper_html(terminal_url, drive_url)`` original por:

        from .launch_app_responsive_v041 import create_wrapper_html

OU (preferível, evita editar o original):

    from pesquisai.launch_app_responsive_v041 import create_wrapper_html as _create
    def create_wrapper_html(terminal_url, drive_url):
        return _create(terminal_url, drive_url)

Compatibilidade: PesquisAI v0.2.1+ (usa /api/theme, /api/lang, /api/backup,
/api/restore, /api/apikey, /api/run_terminal, /api/health, /api/sessions).
"""

from __future__ import annotations

import os
import secrets as _secrets
import sys
from pathlib import Path
from typing import Optional

# Imports resilientes (funciona dentro do pacote e standalone)
try:
    from .constants import WRAPPER_DIR, VERSION
    from .jokes import next_joke
except ImportError:
    WRAPPER_DIR = "/tmp/pesquisai-wrapper"
    VERSION = "0.4.1"
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
    .tb-btn { padding: 0 10px; font-size: 11px; }
    .logo-tag { display: none; }
    .footer-link { font-size: 11px; }
    .footer-sep { margin: 0 8px; }
    .modal-600 { width: 90vw; max-width: 600px; }
  }

  /* === Mobile (480px – 767px): hamburger + ícones essenciais === */
  @media (max-width: 767px) {
    html, body { font-size: 14px; }
    #topbar { padding: 0 8px; gap: 6px; }
    .logo-p, .logo-ai { font-size: 15px; }
    .status { display: none; }  /* esconde status, foco no essencial */
    .tb-btn { display: none; }  /* migram para hamburger */
    .tb-icons { margin-left: auto; gap: 3px; }
    /* === FIX (29/09/2026): hamburguer alinhado a DIREITA no mobile. ===
       Causa: o CSS base tem .sep { flex:1 }, que absorve TODO o espaco livre
       do #topbar. Na resolucao do flexbox o flex-grow e resolvido ANTES das
       margens auto, entao o margin-left:auto do .tb-icons recebia 0 e o
       grupo ficava colado no logo, a ESQUERDA. Os .tb-btn que o .sep
       separava ja estao display:none neste breakpoint, entao nao se perde
       nada ao escondê-lo: o espaco volta e o hamburguer encosta na borda
       direita. Especificidade #topbar para vencer o .sep do CSS base. */
    #topbar .sep { display: none; }
    .tb-icon { width: 32px; height: 32px; }
    .tb-icon svg { width: 14px; height: 14px; }
    /* === REGRA v2 (29/09/2026) — com o hamburger visivel, ZERO icone SVG na topbar.
       .hamburger e .lang-btn NAO sao .tb-icon: ficam de fora de proposito e
       continuam visiveis. Especificidade #topbar + !important para nao perder a
       cascata contra qualquer regra .tb-icon declarada depois. === */
    #topbar .tb-icon { display: none !important; }
    /* dentro do drawer: somente texto, nenhum SVG */
    .mobile-menu .tb-btn { display: inline-flex; }
    .mobile-menu .tb-btn svg,
    .mobile-menu .btn-provider svg { display: none !important; }
    .hamburger { display: inline-flex; }
    #footer { padding: 0 8px; height: 36px; gap: 12px; }
    /* v0.6.20-fix: rodapé mobile = SOMENTE ÍCONES (todo texto escondido).
       - .footer-link font-size:0 colapsa o texto do link; o SVG mantém tamanho fixo em px.
       - .footer-loc ("UFV · Viçosa, MG") sai TAMBÉM no mobile intermediário (480–767px),
         e não apenas abaixo de 480px.
       - Separadores (.footer-sep) desativados: sem texto, o separador fica órfão
         (ex.: o que precedia o texto oculto / o que antecedia o "Powered by").
         O gap do #footer passa a dar o espaçamento entre os ícones. */
    .footer-brand { display: none; }
    .footer-loc { display: none; }
    .footer-oc { display: none; }
    #footer .footer-sep { display: none; }
    .footer-link { font-size: 0; }
    .footer-link svg { margin-right: 0; }
    .btn-provider { padding: 0 6px; font-size: 9px; height: 20px; }
    .footer-right { gap: 10px; }
    .footer-right .btn-provider { gap: 0; }
    .footer-right .btn-provider span { display: none; }  /* "+ provedor" vira só o ícone */
    /* terminal: ocupa mais espaço em mobile */
    #terminal-frame { height: calc(100vh - 50px - 36px) !important; }
    /* modais: largura quase total */
    #modal, #provider-overlay > div, #health-overlay > div,
    #sessions-overlay > div, #shortcuts-overlay > div, #lang-overlay > div {
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
    #footer { font-size: 9px; }
    .footer-link svg { width: 9px; height: 9px; }
  }

  /* === Landscape em mobile (altura < 500px) === */
  @media (max-height: 500px) and (orientation: landscape) {
    #topbar { height: 40px; }
    .logo { font-size: 12px; }
    #footer { height: 28px; font-size: 9px; }
    #terminal-frame { height: calc(100vh - 40px - 28px) !important; }
  }

  /* === Tablet/iPad portrait: esconde UFV footer === */
  @media (min-width: 768px) and (max-width: 1024px) and (orientation: portrait) {
    .tb-btn { padding: 0 8px; }
    .footer-sep:nth-of-type(3) { display: none; }
  }

  /* v0.6.20-fix: coberto pelo bloco ≤767px — rodapé mobile = somente ícones
     (nada a fazer aqui para o rodapé). */

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
    font-family: var(--font-sans); font-size: 11px;
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
    border-color: rgba(var(--accent-rgb),.4);
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
    font-family: var(--font-sans);
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
    --accent:     #8a6d33;
    --accent-dim: rgba(138,109,51,.10);
    --accent-glow:rgba(138,109,51,.18);
    --accent-rgb: 138,109,51;
    --green:      #2e7d32;
    --green-dim:  rgba(46,125,50,.1);
    --amber:      #a67c00;
    --amber-dim:  rgba(166,124,0,.12);
    --red:        #c62828;
    --red-dim:    rgba(198,40,40,.1);
    --ov-dim:     rgba(30,42,52,.38);   /* v0.6.5: backdrop de modais no claro */
    background:   #f5f6f7;
    color:        #1f262a;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
    --font-mono: "DM Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  }

  /* === v0.6.25: Markdown do MANUAL e das DIRETRIZES no TEMA CLARO ==========
     O wrapper carrega apenas `github-markdown-dark.min.css`; no tema claro o
     MANUAL.md e as DIRETRIZES do agente saíam com a paleta ESCURA (texto
     claro sobre fundo claro). Aqui a paleta do markdown é remapeada para as
     variáveis do tema claro — sem depender de um segundo arquivo do CDN,
     portanto também funciona no ambiente offline (.deb). ================ */
  html.theme-light .markdown-body {
    color: var(--ink) !important;
    background-color: transparent !important;
  }
  html.theme-light .markdown-body h1,
  html.theme-light .markdown-body h2,
  html.theme-light .markdown-body h3,
  html.theme-light .markdown-body h4,
  html.theme-light .markdown-body h5,
  html.theme-light .markdown-body h6 {
    color: var(--ink) !important;
    border-bottom-color: var(--line) !important;
  }
  html.theme-light .markdown-body p,
  html.theme-light .markdown-body li,
  html.theme-light .markdown-body dl,
  html.theme-light .markdown-body dd,
  html.theme-light .markdown-body td,
  html.theme-light .markdown-body th,
  html.theme-light .markdown-body strong,
  html.theme-light .markdown-body b,
  html.theme-light .markdown-body summary,
  html.theme-light .markdown-body label {
    color: var(--ink) !important;
  }
  html.theme-light .markdown-body th {
    background-color: var(--surface) !important;
  }
  html.theme-light .markdown-body a,
  html.theme-light .markdown-body a:visited {
    color: var(--accent) !important;
  }
  html.theme-light .markdown-body a:hover {
    color: var(--ink) !important;
  }
  html.theme-light .markdown-body blockquote {
    color: var(--ink-muted) !important;
    border-left-color: var(--accent) !important;
    background-color: var(--accent-dim) !important;
  }
  html.theme-light .markdown-body code,
  html.theme-light .markdown-body tt {
    color: #7a3b1d !important;
    background-color: #f1efe9 !important;
    border-color: rgba(0,0,0,.08) !important;
  }
  html.theme-light .markdown-body pre {
    color: var(--ink) !important;
    background-color: #f1efe9 !important;
    border-color: rgba(0,0,0,.08) !important;
  }
  html.theme-light .markdown-body pre code,
  html.theme-light .markdown-body pre tt {
    color: #7a3b1d !important;
    background-color: transparent !important;
  }
  html.theme-light .markdown-body hr {
    background-color: var(--line) !important;
    border-color: var(--line) !important;
  }
  html.theme-light .markdown-body table th,
  html.theme-light .markdown-body table td {
    border-color: var(--line) !important;
  }
  html.theme-light .markdown-body table tr {
    background-color: transparent !important;
    border-top-color: var(--line) !important;
  }
  html.theme-light .markdown-body table tr:nth-child(2n) {
    background-color: var(--surface) !important;
  }
  html.theme-light .markdown-body img {
    background-color: transparent !important;
    border-color: var(--line) !important;
  }
  html.theme-light .markdown-body kbd {
    color: var(--ink) !important;
    background-color: #f1efe9 !important;
    border-color: rgba(0,0,0,.12) !important;
    box-shadow: inset 0 -1px 0 rgba(0,0,0,.08) !important;
  }
  html.theme-light .markdown-body .highlight,
  html.theme-light .markdown-body .highlight pre {
    background-color: #f1efe9 !important;
  }

  /* === Indicador de tema ativo (NOVO em v0.4.1) === */
  #theme-toggle[data-theme="pesquisai-light"] {
    color: var(--amber);
    border-color: rgba(166,124,0,.4);
    background: var(--amber-dim);
  }
  #theme-toggle[data-theme="pesquisai"] {
    color: var(--ink-muted);
  }
  #theme-toggle[data-theme="pesquisai-light"] svg circle { fill: currentColor; }

  /* === Toasts em viewport pequeno === */
  @media (max-height: 500px) {
    #toast { bottom: 36px; right: 8px; }
  }

    /* === v0.6.5: Splash de carregamento do terminal (boot) === */
  #boot-splash {
    position: fixed; inset: 0; z-index: 200000;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 16px;
    background: var(--surface, #141c24);
    transition: opacity .45s ease;
  }
  #boot-splash.hide { opacity: 0; pointer-events: none; }
  .boot-logo { width: 128px; height: auto; border-radius: 14px;
    box-shadow: 0 12px 40px rgba(0,0,0,.35); }
  .boot-spinner { width: 32px; height: 32px; border-radius: 50%;
    border: 3px solid rgba(var(--accent-rgb), .18);
    border-top-color: var(--accent);
    animation: bootspin .8s linear infinite; }
  @keyframes bootspin { to { transform: rotate(360deg); } }
  .boot-status { font-size: 13px; color: var(--ink-muted);
    font-family: var(--font-sans); letter-spacing: .02em; }
  .boot-bar { width: min(320px, 60vw); height: 4px; border-radius: 2px;
    overflow: hidden; background: rgba(var(--accent-rgb), .15);
    position: relative; }
  .boot-bar::after { content: ""; position: absolute; left: -40%;
    top: 0; bottom: 0; width: 40%; border-radius: 2px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    animation: bootslide 1.4s ease-in-out infinite; }
  @keyframes bootslide { to { left: 100%; } }
  .boot-error { color: var(--red); font-size: 12.5px;
    max-width: 70vw; text-align: center; line-height: 1.5; }
  .boot-retry { margin-top: 4px; padding: 8px 16px;
    background: var(--accent-dim); color: var(--accent);
    border: 1px solid rgba(var(--accent-rgb), .35);
    border-radius: var(--radius); cursor: pointer;
    font-size: 12px; font-family: var(--font-sans); }

  @media (prefers-reduced-motion: reduce) {
      * { animation-duration: .001ms !important; animation-iteration-count: 1 !important;
          transition-duration: .001ms !important; scroll-behavior: auto !important; }
    }

  /* === v0.6.10: Memória UFVAI responsiva (mobile + tablet) === */
  @media (max-width: 767px) {
    #memory-overlay > div { width: 95vw !important; max-width: 95vw !important; height: 92vh !important; max-height: 92vh !important; flex-direction: column !important; }
    #memory-sidebar { width: 100% !important; max-height: 38vh; border-right: none !important; border-bottom: 1px solid var(--line); flex-shrink: 0; }
    #memory-editor-pane { flex: 1; min-height: 0; display:flex; flex-direction:column; }
    #memory-editor-body { flex-direction: column !important; flex:1; min-height:0; overflow:hidden; }
    #memory-list { -webkit-overflow-scrolling: touch; }
    #memory-search-input { font-size: 14px !important; padding: 8px 10px !important; }
    #memory-note-meta { flex-wrap: wrap; }
    #memory-editor, #memory-preview { padding: 12px !important; font-size: 13px !important; }
    #memory-editor { min-height: 120px; flex: 1 1 40% !important; }
    #memory-preview { min-height: 150px; flex: 1 1 60% !important; overflow-y:auto !important; -webkit-overflow-scrolling:touch; display:block !important; }
    #memory-overlay .modal-title { font-size: 14px !important; }
    /* v0.6.25: empilha lista + editor no mobile (o pai era flex ROW). */
    #memory-body { flex-direction: column !important; }
    #memory-editor-pane { width: 100% !important; }
    /* v0.6.12 fix: garante preview visível no mobile mesmo quando em modo preview */
    #memory-editor-body #memory-preview[style*="display: none"] { display:none !important; }
    #memory-editor-body #memory-preview:not([style*="display: none"]) { display:block !important; }
  }
  @media (max-width: 479px) {
    #memory-overlay > div { width: 100vw !important; max-width: 100vw !important; height: 100vh !important; max-height: 100vh !important; border-radius: 0 !important; }
    #memory-sidebar { max-height: 42vh; }
  }
  @media (max-width: 380px) {
    #memory-sidebar { max-height: 44vh; }
    #memory-list { font-size: 11px !important; }
  }
  /* Touch: alvos ≥44px no mobile */
  @media (max-width: 767px) {
    .mem-note-item, .mem-folder-card { min-height: 44px; }
    #memory-btn-save, #memory-btn-delete, #memory-overlay .modal-close { min-height: 44px; min-width: 44px; }
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
    {"code": "zh_CN", "name": "中文（简体）",             "flag": "🇨🇳", "short": "ZH"},
]


def create_wrapper_html(
    terminal_url: str,
    drive_url: str,
    session_token: str | None = None,
    boot_id: str | None = None,
) -> str:
    """Cria a versão v0.4.1 do wrapper HTML do PesquisAI.

    Versão drop-in que substitui o HTML estático do launch_app.py por
    um layout adaptativo com 3 correções aplicadas:

      1. Responsividade completa (5 breakpoints + hamburger)
      2. toggleTheme() que recarrega o iframe do ttyd
      3. Seletor de idioma na topbar (5 idiomas, cookie, query param)

    Args:
        terminal_url: URL do terminal ttyd.
        drive_url: URL do Google Drive.
        session_token: token de sessão exigido pelas APIs (v0.6.0).
        boot_id: identificador DESTA execução do UFVAI. O frontend usa-o
            para escopar as telas de abertura ("uma vez por execução").
            None gera um novo (chamadas repetidas = nova execução).

    Returns:
        String HTML completa.
    """
    boot_id = str(boot_id or _secrets.token_hex(8))
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
  <title>UFVAI</title>
  <!-- v0.6.6: favicon UFVAI (SVG + PNG fallback + apple-touch) -->
  <link rel="icon" type="image/svg+xml" href="/assets/ico.svg">
  <link rel="alternate icon" type="image/png" sizes="64x64" href="/assets/ufvai-64.png">
  <link rel="apple-touch-icon" sizes="256x256" href="/assets/icon.png">
  <script>
    // v0.6.6: no Colab a UI é servida via /proxy/8001/ — links absolutos "/assets/…"
    // quebram; reescreve os favicons com o prefixo do pathname atual.
    (function(){try{
      var p=location.pathname.replace(/[^/]*$/,"");
      if(p==="/"||p==="") return; // raiz local: links absolutos já funcionam
      var h=document.head;
      var mk=function(rel,type,sizes,href){var l=document.createElement("link");l.rel=rel;if(type)l.type=type;if(sizes)l.sizes=sizes;l.href=p+href.replace(/^\\//,"");h.appendChild(l);};
      mk("icon","image/svg+xml",null,"/assets/ico.svg");
      mk("alternate icon","image/png","64x64","/assets/ufvai-64.png");
      mk("apple-touch-icon",null,"256x256","/assets/icon.png");
    }catch(e){}})();
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://cdn.jsdelivr.net">
  <!-- v0.7.5+: CSS de fontes NÃO bloqueia mais a renderização (media="print"
       + troca para "all" no onload). Era uma requisição externa no
       caminho crítico: em rede lenta a tela ficava em branco/inglês. -->
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Montserrat:wght@600;700&family=Syne:wght@700;800&display=swap"
        rel="stylesheet" media="print" onload="this.media='all'">
  <!-- v0.7.5: o CSS do xterm era baixado do CDN e NÃO era usado (o terminal
       roda dentro do iframe do ttyd). Removido: era uma requisição
       render-blocking no caminho crítico da abertura. -->
  <!-- github-markdown-css: estilização markdown para o modal de Diretrizes -->
  <!-- v0.7.5+: markdown só é usado nos modais (Diretrizes/Manual). Carregar
       fora do caminho crítico evita ~1 requisição bloqueante na abertura. -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.5.0/github-markdown-dark.min.css"
        media="print" onload="this.media='all'">
  <!-- marked.js: preload para acelerar renderização de markdown -->
  <!-- v0.6.0: marked.js EMBUTIDO (offline-first) com fallback CDN -->
  <script src="/vendor/marked.min.js"></script>
  <script>if(typeof marked==="undefined"){document.write('<scr'+'ipt src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></scr'+'ipt>');}</script>
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
    html { background: #141c24; color: #e8e6e0; }  /* anti-flash dark · UFVAI */

    :root {
      --ink:        #e8e6e0;
      --ink-muted:  #9a9790;
      --surface:    #141c24;
      --rail:       #1f2831;
      --line:       rgba(255,255,255,.07);
      --accent:     #b29149;
      --accent-dim: rgba(var(--accent-rgb),.12);
      --accent-glow:rgba(var(--accent-rgb),.22);
      --accent-rgb: 178,145,73;
      --green:      #5dba7e;
      --green-dim:  rgba(93,186,126,.12);
      --amber:      #D1A705;
      --amber-dim:  rgba(209,167,5,.14);
      --red:        #e07070;
      --red-dim:    rgba(224,112,112,.12);
      --ov-dim:     rgba(4,7,11,.8);      /* v0.6.5: backdrop de modais no escuro */
      --radius:     5px;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
      --font-mono: "DM Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    }

    html, body {
      height: 100%; width: 100%;
      background: var(--surface);
      color: var(--ink);
      font-family: var(--font-sans);
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

    .logo { display: flex; align-items: baseline; gap: 2px; }
    .logo-p  { font-family:"Montserrat","Syne",sans-serif; font-weight:700; font-size:17px; color:var(--ink); letter-spacing:-0.02em; }
    .logo-ai { font-family:"Montserrat","Syne",sans-serif; font-weight:600; font-size:17px; color:var(--accent); letter-spacing:-0.02em; margin-left:-0.02em; }
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
      font-family: var(--font-sans); font-size: 11px;
      font-weight: 500; letter-spacing: .04em;
      border-radius: var(--radius); cursor: pointer;
      border: 1px solid; transition: background .15s, transform .1s, border-color .15s;
      text-decoration: none; white-space: nowrap;
    }
    .tb-btn:active { transform: scale(.96); }
    .tb-btn svg { width:13px; height:13px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }

    .btn-drive  { color:var(--accent); background:var(--accent-dim); border-color:rgba(var(--accent-rgb),.25); }
    .btn-drive:hover  { background:var(--accent-glow); border-color:rgba(var(--accent-rgb),.5); }

    .btn-backup { color:var(--green); background:var(--green-dim); border-color:rgba(93,186,126,.25); }
    .btn-backup:hover { background:rgba(93,186,126,.2); border-color:rgba(93,186,126,.5); }

    .btn-restore { color:var(--amber); background:var(--amber-dim); border-color:rgba(232,184,75,.25); }
    .btn-restore:hover { background:rgba(232,184,75,.2); border-color:rgba(232,184,75,.5); }

    /* v0.6.20 — botão SAIR (encerrar ambiente de execução) */
    .btn-sair { color:var(--red); background:var(--red-dim); border-color:rgba(224,112,112,.25); }
    .btn-sair:hover { background:rgba(224,112,112,.2); border-color:rgba(224,112,112,.5); }

    /* v0.6.20 — modal de confirmação do SAIR */
    #sair-overlay {
      position: fixed; inset: 0;
      background: var(--ov-dim);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; opacity: 0; pointer-events: none;
      transition: opacity .2s;
    }
    #sair-overlay.open { opacity: 1; pointer-events: all; }
    #sair-modal {
      background: var(--rail); border: 1px solid var(--line);
      border-radius: 8px; padding: 24px; width: 400px; max-width: 90vw;
      box-shadow: 0 24px 64px rgba(0,0,0,.6);
    }
    #sair-modal .sair-warn {
      font-size: 11.5px; color: var(--ink-muted);
      line-height: 1.6; margin-bottom: 16px;
    }
    #sair-modal .sair-status {
      font-size: 11px; color: var(--accent);
      margin-top: 12px; min-height: 15px; text-align: center;
    }
    #sair-modal .sair-done {
      display: none; margin-top: 14px; padding: 12px;
      font-size: 12px; color: var(--ink); line-height: 1.6;
      background: rgba(255,255,255,.04);
      border: 1px solid var(--line); border-radius: var(--radius);
      text-align: center;
    }

    #toast {
      position: fixed; bottom: 58px; right: 18px;
      padding: 9px 16px; border-radius: var(--radius);
      font-size: 12px; font-family: var(--font-sans);
      display: flex; align-items: center; gap: 8px;
      opacity: 0; transform: translateY(6px);
      transition: opacity .22s, transform .22s;
      pointer-events: none; z-index: 9998; max-width: 340px;
      border: 1px solid;
    }
    #toast.show { opacity: 1; transform: translateY(0); }
    #toast.ok    { background:rgba(93,186,126,.15);  border-color:rgba(93,186,126,.35);  color:var(--green); }
    #toast.err   { background:rgba(224,112,112,.15); border-color:rgba(224,112,112,.35); color:var(--red);   }
    #toast.info  { background:var(--accent-dim);     border-color:rgba(var(--accent-rgb),.35);  color:var(--accent);}

    #modal-overlay {
      position: fixed; inset: 0;
      background: var(--ov-dim);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; opacity: 0; pointer-events: none;
      transition: opacity .2s;
    }
    #modal-overlay.open { opacity: 1; pointer-events: all; }
    #modal {
      background: var(--rail); border: 1px solid var(--line);
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
      font-size: 11px; padding: 2px 8px;
      background: var(--amber-dim); color: var(--amber);
      border: 1px solid rgba(232,184,75,.3); border-radius: 3px;
    }
    /* ── v0.7.0: "Restaurar" com CALENDARIO e FILTRO por data ── */
    #modal.restore-modal { width: 560px; max-width: 94vw; }
    .restore-sub {
      font-size: 11px; color: var(--ink-muted);
      margin: -10px 0 12px;
    }
    .restore-toolbar {
      display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .restore-toolbar .rnav {
      width: 26px; height: 26px; border-radius: var(--radius);
      background: rgba(255,255,255,.04); border: 1px solid var(--line);
      color: var(--ink-muted); cursor: pointer; font-size: 13px; line-height: 1;
      flex-shrink: 0;
    }
    .restore-toolbar .rnav:hover { background: var(--accent-dim); color: var(--accent); }
    .restore-toolbar .rmonth {
      font-size: 12px; font-weight: 700; color: var(--ink);
      min-width: 118px; text-align: center; text-transform: capitalize;
    }
    .restore-toolbar input[type="date"] {
      background: rgba(255,255,255,.04); border: 1px solid var(--line);
      color: var(--ink); border-radius: var(--radius); padding: 4px 6px;
      font-family: var(--font-sans); font-size: 11px; color-scheme: dark;
    }
    .restore-toolbar .rghost {
      font-size: 11px; padding: 4px 10px; border-radius: var(--radius);
      background: rgba(255,255,255,.04); border: 1px solid var(--line);
      color: var(--ink-muted); cursor: pointer; font-family: var(--font-sans);
    }
    .restore-toolbar .rghost:hover { background: var(--accent-dim); color: var(--accent); }
    .restore-cal {
      border: 1px solid var(--line); border-radius: var(--radius);
      padding: 8px 8px 6px; margin-bottom: 12px;
    }
    .restore-dow, .restore-grid {
      display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
    }
    .restore-dow div {
      text-align: center; font-size: 9.5px; color: var(--ink-muted);
      text-transform: uppercase; letter-spacing: .04em; padding-bottom: 4px;
    }
    .restore-day {
      position: relative; min-height: 26px;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; color: var(--ink-muted);
      border-radius: 4px; cursor: pointer; border: 1px solid transparent;
    }
    .restore-day:hover { background: rgba(255,255,255,.06); color: var(--ink); }
    .restore-day.empty { visibility: hidden; }
    .restore-day.today { border-color: rgba(var(--accent-rgb), .45); }
    .restore-day.has { color: var(--ink); font-weight: 700; }
    .restore-day.has::after {
      content: ""; position: absolute; bottom: 3px; left: 50%;
      transform: translateX(-50%);
      width: 3px; height: 3px; border-radius: 50%; background: var(--accent);
    }
    .restore-day.sel {
      background: var(--accent-dim); color: var(--accent);
      border-color: rgba(var(--accent-rgb), .5);
    }
    .restore-day.sel::after { background: var(--accent); }
    /* v0.7.2 — numero de backups no dia + chips dos meses com backup */
    .restore-day .rd-n {
      position: absolute; top: 1px; right: 2px;
      font-size: 8px; line-height: 1; font-weight: 700;
      color: var(--accent); opacity: .9;
    }
    .restore-months {
      display: flex; flex-wrap: wrap; gap: 4px;
      margin: -2px 0 10px;
    }
    .restore-months .rmonth-chip {
      font-size: 10px; padding: 3px 7px; border-radius: 999px;
      background: rgba(255,255,255,.04); border: 1px solid var(--line);
      color: var(--ink-muted); cursor: pointer; font-family: var(--font-sans);
      display: inline-flex; align-items: center; gap: 4px;
    }
    .restore-months .rmonth-chip b { color: var(--ink); font-weight: 700; }
    .restore-months .rmonth-chip:hover { background: var(--accent-dim); color: var(--accent); }
    .restore-months .rmonth-chip.on {
      border-color: rgba(var(--accent-rgb), .5); color: var(--accent);
      background: var(--accent-dim);
    }
    .restore-daygroup.nodate { opacity: .75; }
    .backup-item .b-main {
      display: flex; flex-direction: column; gap: 2px;
      min-width: 0; flex: 1;
    }
    .backup-item .b-time {
      font-size: 12px; color: var(--ink); font-weight: 600;
      display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
    }
    .backup-item .b-meta {
      font-size: 10px; color: var(--ink-muted);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .backup-item .b-badge {
      font-size: 9px; padding: 1px 5px; border-radius: 3px;
      border: 1px solid var(--line); color: var(--ink-muted);
      font-weight: 500; text-transform: uppercase; letter-spacing: .03em;
    }
    .backup-item .b-badge.auto { color: var(--accent); border-color: rgba(var(--accent-rgb),.35); }
    .backup-item .b-badge.bad { color: var(--amber); border-color: rgba(232,184,75,.35); }
    /* v0.7.1 — botao de apagar o backup (menu "Restaurar") */
    .backup-item .b-del {
      background: transparent; border: 1px solid var(--line); border-radius: 4px;
      color: var(--ink-muted); font-size: 11px; line-height: 1;
      padding: 3px 5px; cursor: pointer; margin-right: 6px;
      transition: color .12s, border-color .12s, background .12s;
    }
    .backup-item .b-del:hover {
      color: #e05a5a; border-color: rgba(224,90,90,.45);
      background: rgba(224,90,90,.08);
    }
    .restore-daygroup {
      font-size: 10px; text-transform: uppercase; letter-spacing: .05em;
      color: var(--ink-muted); padding: 8px 12px 4px;
      background: rgba(255,255,255,.02); border-bottom: 1px solid var(--line);
      position: sticky; top: 0; backdrop-filter: blur(2px);
    }
    .modal-empty { padding:20px; text-align:center; font-size:12px; color:var(--ink-muted); }
    .modal-close {
      display: block; width: 100%; padding: 8px;
      background: rgba(255,255,255,.05); border: 1px solid var(--line);
      border-radius: var(--radius); color: var(--ink-muted);
      font-family: var(--font-sans); font-size: 12px;
      cursor: pointer; transition: background .15s;
    }
    .modal-close:hover { background: rgba(255,255,255,.1); }
    .btn-ghost {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 8px 14px;
      background: rgba(255,255,255,.04); border: 1px solid var(--line);
      border-radius: var(--radius); color: var(--ink-muted);
      font-family: var(--font-sans); font-size: 12px;
      cursor: pointer; transition: background .15s, border-color .15s, color .15s;
      white-space: nowrap;
    }
    .btn-ghost:hover { background: rgba(255,255,255,.08); color: var(--ink); }

    #terminal-frame {
      position: absolute;
      inset: 50px 0 40px 0;
      width: 100%; height: calc(100% - 90px);
      border: none;
    }

    #footer {
      position: fixed; inset: auto 0 0 0;
      height: 40px;
      background: var(--rail);
      border-top: 1px solid var(--line);
      display: flex; align-items: center;
      padding: 0 18px; gap: 0;
      font-size: 11px; color: var(--ink-muted);
      z-index: 9999;
    }
    .footer-brand {
      font-family: "Syne", sans-serif; font-weight: 700;
      font-size: 11px; color: var(--ink);
      margin-right: 14px;
    }
    .footer-sep { width:1px; height:16px; background:var(--line); margin:0 12px; flex-shrink:0; }
    .footer-link {
      color: var(--ink-muted); text-decoration: none;
      letter-spacing: .03em;
      transition: color .15s;
    }
    .footer-link:hover { color: var(--accent); }
    .footer-link svg { width:11px; height:11px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; vertical-align:-.15em; margin-right:4px; }
    .footer-right { margin-left:auto; display:flex; align-items:center; gap:12px; }
    .footer-oc { color:var(--ink-muted); letter-spacing:.03em; }
    .footer-oc a { color:var(--ink-muted); text-decoration:none; }
    .footer-oc a:hover { color:var(--accent); }

    /* ── v0.7.0: chave liga/desliga do AUTOSAVE (canto direito inferior) ── */
    .autosave-switch {
      display: inline-flex; align-items: center; gap: 7px;
      cursor: pointer; user-select: none;
      font-size: 11px; color: var(--ink-muted);
      letter-spacing: .03em;
    }
    .autosave-switch input { position:absolute; opacity:0; width:0; height:0; }
    .autosave-track {
      position: relative; display:inline-block;
      width: 30px; height: 16px; flex-shrink:0;
      background: rgba(var(--accent-rgb),.14);
      border: 1px solid rgba(var(--accent-rgb),.28);
      border-radius: 999px;
      transition: background .18s, border-color .18s;
    }
    .autosave-knob {
      position: absolute; top: 1px; left: 1px;
      width: 12px; height: 12px; border-radius: 50%;
      background: rgba(var(--accent-rgb),.55);
      transition: transform .18s, background .18s;
    }
    .autosave-switch input:checked + .autosave-track {
      background: rgba(var(--accent-rgb),.42);
      border-color: rgba(var(--accent-rgb),.6);
    }
    .autosave-switch input:checked + .autosave-track .autosave-knob {
      transform: translateX(14px);
      background: var(--accent);
    }
    .autosave-switch input:focus-visible + .autosave-track {
      box-shadow: 0 0 0 2px rgba(var(--accent-rgb),.25);
    }
    .autosave-switch.on .autosave-label { color: var(--accent); }
    .autosave-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--accent); display: inline-block;
      opacity: 0; transition: opacity .2s;
    }
    .autosave-switch.on .autosave-dot { opacity: 1; }

    /* ── v0.7.0: modal de retomada do autosave ── */
    #autosave-overlay {
      position: fixed; inset: 0;
      background: var(--ov-dim);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; opacity: 0; pointer-events: none;
      transition: opacity .2s;
    }
    #autosave-overlay.open { opacity: 1; pointer-events: all; }
    #autosave-modal {
      background: var(--rail); border: 1px solid var(--line);
      border-radius: 8px; padding: 22px; width: 420px; max-width: 92vw;
      box-shadow: 0 24px 64px rgba(0,0,0,.6);
    }
    #autosave-modal .as-title {
      font-family: "Syne", sans-serif; font-weight: 700;
      font-size: 14px; color: var(--ink); margin: 0 0 10px;
    }
    #autosave-modal .as-when {
      font-size: 11.5px; color: var(--accent); margin: 0 0 6px;
    }
    #autosave-modal .as-text {
      font-size: 11.5px; color: var(--ink-muted);
      line-height: 1.6; margin: 0 0 18px;
    }
    #autosave-modal .as-actions { display:flex; gap:8px; justify-content:flex-end; }
    #autosave-modal .as-btn {
      padding: 7px 14px; font-size: 11.5px; cursor: pointer;
      border-radius: var(--radius); font-family: var(--font-sans);
      border: 1px solid var(--line); background: transparent;
      color: var(--ink-muted);
      transition: background .15s, color .15s, border-color .15s;
    }
    #autosave-modal .as-btn:hover { color: var(--ink); border-color: rgba(var(--accent-rgb),.4); }
    #autosave-modal .as-btn.primary {
      background: rgba(var(--accent-rgb),.16);
      border-color: rgba(var(--accent-rgb),.45);
      color: var(--accent);
    }
    #autosave-modal .as-btn.primary:hover { background: rgba(var(--accent-rgb),.26); }

    .btn-provider {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 0 10px; height: 24px;
      font-family: var(--font-sans); font-size: 11px;
      font-weight: 500; letter-spacing: .03em;
      border-radius: var(--radius); cursor: pointer;
      border: 1px solid rgba(var(--accent-rgb),.18);
      color: rgba(var(--accent-rgb),.55);
      background: transparent;
      transition: background .15s, color .15s, border-color .15s;
      white-space: nowrap;
    }
    .btn-provider:hover {
      background: var(--accent-dim);
      color: var(--accent);
      border-color: rgba(var(--accent-rgb),.4);
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
      border-color:rgba(var(--accent-rgb),.4);
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
      color:var(--ink); font-family:var(--font-sans); font-size:11px;
      outline:none; transition:border-color .15s;
    }
    .session-search:focus { border-color:rgba(var(--accent-rgb),.4); }
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
      font-family:var(--font-sans); font-size:10.5px; font-weight:600;
      padding:2px 8px; background:var(--accent-dim); color:var(--accent);
      border:1px solid rgba(var(--accent-rgb),.25); border-radius:3px;
    }
  </style>
  {RESPONSIVE_CSS}
</head>
<body>
<script>
/* v0.6.0 segurança — token de sessão em todo fetch /api/* (same-origin) */
(function(){
  var __T = "__UFVAI_TOKEN__";
  if (!__T) return;
  var _of = window.fetch;
  window.fetch = function(input, init){
    try {
      var url = (typeof input === "string") ? input : (input && input.url) || "";
      var u = new URL(url, location.href);
      if (u.origin === location.origin && u.pathname.indexOf("/api/") === 0) {
        init = init || {};
        var h = new Headers((init && init.headers) || {});
        h.set("X-UFVAI-Token", __T);
        init.headers = h;
        return _of.call(window, input, init);
      }
    } catch(e){}
    try { return _of.apply(window, arguments); } catch(e2){ throw e2; }
  };
})();
</script>

  <div id="topbar">
    <div class="logo">
      <span class="logo-p">UFV</span><span class="logo-ai">AI</span>
      <span>  <a href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/CHANGELOG.md" target="_blank" class="logo-tag"> v{__VERSION__} </a> </span>
    </div>

    <div class="status">
      <span class="status-dot"></span>
      <span data-i18n="ui.status_active">agente ativo</span>
    </div>

    <div class="tb-icons">
      <button class="tb-icon" onclick="openHealth()" title="Dashboard de Saúde" data-i18n-title="dashboard.title">
        <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </button>
      <button class="tb-icon" onclick="openManual()" title="Manual do UFVAI" data-i18n-title="manual.title">
        <svg viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
      </button>
      <button class="tb-icon" onclick="openSessions()" title="Histórico de Sessões" data-i18n-title="sessions.title">
        <svg viewBox="0 0 24 24"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/></svg>
      </button>
      <button class="tb-icon" onclick="openShortcuts()" title="Atalhos de Teclado" data-i18n-title="shortcuts.title">
        <svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10"/></svg>
      </button>
      <button class="tb-icon" onclick="openAgents()" title="Diretrizes do Agente" data-i18n-title="agents.title">
        <svg viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="M9 12h6M9 16h4"/></svg>
      </button>
      <button class="tb-icon" onclick="openMemory()" id="memory-btn" title="Memória UFVAI" data-i18n-title="memory.tooltip">
        <svg viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-7 7c0 3 1.5 5 3 7l1 1v3a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-3l1-1c1.5-2 3-4 3-7a7 7 0 0 0-7-7z"/><path d="M9 22h6"/><path d="M12 2v20"/></svg>
      </button>
      <button class="tb-icon" onclick="toggleTheme()" id="theme-toggle" title="Alternar tema" data-theme="pesquisai" data-i18n-title="theme.toggle">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
      </button>
      <button class="tb-icon" onclick="openTelemetry()" id="telemetry-btn" title="Telemetria (Admin)" style="display:none !important" data-i18n-title="telemetry.title">
        <svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6"/><rect x="12" y="8" width="3" height="10"/><rect x="17" y="4" width="3" height="14"/></svg>
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

    <!-- v0.6.20: SAIR — oculto por padrão; exibido via JS somente no Colab -->
    <button class="tb-btn btn-sair" id="sair-btn" onclick="ufvaiExit()" style="display:none;">
      <svg viewBox="0 0 24 24"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
      <span data-i18n="ui.sair">SAIR</span>
    </button>

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
    <!-- v0.6.20: SAIR no drawer mobile (idem topbar: exibido só no Colab) -->
    <button class="tb-btn btn-sair" id="sair-btn-mobile" onclick="ufvaiExit(); toggleMobileMenu();" style="display:none;width:100%;justify-content:flex-start;">
      <svg viewBox="0 0 24 24"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
      <span data-i18n="ui.sair">SAIR</span>
    </button>
    <button class="btn-provider" onclick="connectProvider(); toggleMobileMenu();" style="width:100%;justify-content:flex-start;">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>
      <span data-i18n="providers.title">+ provedor</span>
    </button>
    <div style="height:1px;background:var(--line);margin:8px 0;"></div>
    <button class="modal-close" onclick="openHealth(); toggleMobileMenu();">🩺 <span data-i18n="dashboard.title">Dashboard de Saúde</span></button>
    <button class="modal-close" onclick="openManual(); toggleMobileMenu();">📘 <span data-i18n="manual.title">Manual do UFVAI</span></button>
    <button class="modal-close" onclick="openSessions(); toggleMobileMenu();">📜 <span data-i18n="sessions.title">Histórico de Sessões</span></button>
    <button class="modal-close" onclick="openShortcuts(); toggleMobileMenu();">⌨️ <span data-i18n="shortcuts.title">Atalhos de Teclado</span></button>
    <button class="modal-close" onclick="openAgents(); toggleMobileMenu();">📋 <span data-i18n="agents.title">Diretrizes do Agente</span></button>
    <button class="modal-close" onclick="openMemory(); toggleMobileMenu();">🧠 <span data-i18n="memory.title">Memória UFVAI</span></button>
    <button class="modal-close" onclick="toggleTheme(); toggleMobileMenu();">◑ <span data-i18n="theme.toggle">Alternar Tema</span></button>
    <!-- v0.6.25: item "Idioma" REMOVIDO do drawer — o seletor .lang-btn da
         topbar continua visível no mobile (a media query ≤767px esconde
         apenas .tb-btn), então o botão aqui era redundante. -->
  </div>

  <!-- Dropdown de idioma (NOVO em v0.4.1) -->
  <div class="lang-menu" id="lang-menu" role="menu" aria-label="Idioma / Language">
    <!-- Preenchido dinamicamente por buildLangMenu() -->
  </div>

  <!-- v0.6.5: Splash de carregamento — polling /api/ttyd_ready antes de
       apontar o iframe; elimina ERR_CONNECTION_REFUSED visível e dá
       feedback imediato no boot, troca de idioma e restauração. -->
  <div id="boot-splash" role="status" aria-live="polite">
    <img class="boot-logo" src="/assets/logo-oficial-288.jpg" alt="UFVAI"
         onerror="this.style.display='none'">
    <div class="boot-spinner" aria-hidden="true"></div>
    <div class="boot-status" id="boot-status" data-i18n="boot.starting">Iniciando terminal…</div>
    <div class="boot-bar" aria-hidden="true"></div>
    <div class="boot-error" id="boot-error" style="display:none;"></div>
    <button class="boot-retry" id="boot-retry" style="display:none;"
            onclick="location.reload()" data-i18n="boot.retry">↻ Recarregar</button>
  </div>

 <iframe
  id="terminal-frame"
  src="about:blank"
  data-terminal-url="{__TERMINAL_URL__}"
  allow="clipboard-read; clipboard-write"
  tabindex="0"
  style="width:100%; height:calc(100% - 90px); border:none; outline:none;">
</iframe>

  <div id="footer">
    <span class="footer-brand">UFVAI</span>
    <span class="footer-sep"></span>
    <a href="mailto:gustavo.braga@ufv.br" class="footer-link" title="gustavo.braga@ufv.br" aria-label="E-mail">
      <svg viewBox="0 0 24 24"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
      gustavo.braga@ufv.br
    </a>
    <span class="footer-sep"></span>
    <a href="https://github.com/gustavobraga-byte/PesquisAI" target="_blank" class="footer-link" title="GitHub" aria-label="GitHub">
      <svg viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
      GitHub
    </a>
    <span class="footer-sep"></span>
    <!-- v0.6.20-fix: link do SITE OFICIAL no rodapé (falta reportada pelo usuário) -->
    <a href="https://der.ufv.br/ufvai/" target="_blank" rel="noopener" class="footer-link footer-site" title="Site oficial do UFVAI">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
      Site
    </a>
    <span class="footer-sep"></span>
    <span style="color:var(--ink-muted)" class="footer-loc">UFV · Viçosa, MG - Brasil</span>
    <span class="footer-sep"></span>

    <div class="footer-right">
      <!-- v0.7.0: chave liga/desliga do AUTOSAVE (a cada 3 min, no Drive) -->
      <label class="autosave-switch" id="autosave-switch" title="Salvar automaticamente a sessão a cada 3 minutos no Google Drive — ligado por padrão (desligue aqui se não quiser)">
        <input type="checkbox" id="autosave-toggle" onchange="toggleAutosave(this.checked)">
        <span class="autosave-track"><span class="autosave-knob"></span></span>
        <span class="autosave-dot"></span>
        <span class="autosave-label" data-i18n="autosave.title">Autosave</span>
      </label>
      <!-- v0.7.4: ESCOLHA do alcance do autosave — por PADRAO salva SO a
           sessao ativa (e so quando ela muda). Ligue aqui para gravar
           TODAS as conversas abertas (um arquivo por sessao). -->
      <label class="autosave-switch" id="autosave-all-switch"
             title="Salvar todas as conversas abertas (um arquivo por sessão). Desligado por padrão — sem isso o autosave grava só a sessão ativa.">
        <input type="checkbox" id="autosave-all-toggle" onchange="toggleAutosaveAll(this.checked)">
        <span class="autosave-track"><span class="autosave-knob"></span></span>
        <span class="autosave-dot"></span>
        <span class="autosave-label" data-i18n="autosave.all">Todas as conversas</span>
      </label>
      <!-- v0.7.2: reabrir a pergunta de retomada sob demanda (a pergunta
           automatica e oferecida UMA VEZ por aba; este botao reoferece). -->
      <button class="btn-provider" onclick="reofferAutosaveResume()"
              title="Retomar a última sessão salva" data-i18n-title="autosave.resume.again">↻</button>
      <span class="footer-sep"></span>
      <button class="btn-provider" onclick="connectProvider()" title="Conectar novo provedor de IA">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>
        <span data-i18n="providers.title">+ provedor</span>
      </button>
      <span class="footer-sep"></span>
      <span class="footer-oc">
        Powered by <a href="https://opencode.ai" target="_blank">OpenCode</a>
      </span>
    </div>
  </div>

  <div id="toast"></div>

  <!-- v0.6.20 — Modal de confirmação do SAIR (confirmação OBRIGATÓRIA antes
       de desconectar e excluir o ambiente de execução do Colab) -->
  <div id="sair-overlay" onclick="if(event.target===this)ufvaiExitCancel()">
    <div id="sair-modal" role="dialog" aria-modal="true" aria-labelledby="sair-title">
      <div class="modal-title" id="sair-title">⏻ <span data-i18n="sair.title">Encerrar sessão</span></div>
      <p class="sair-q" style="font-size:12.5px;color:var(--ink);margin-bottom:10px;" data-i18n="sair.confirm_q">Desconectar e excluir o ambiente de execução?</p>
      <p class="sair-warn" data-i18n="sair.warn">Tudo em memória será perdido — os arquivos no seu Google Drive continuam salvos. Não há como desfazer após confirmar.</p>
      <div style="display:flex;gap:8px;">
        <button id="sair-yes" onclick="ufvaiExitConfirm()" style="flex:1;padding:9px;background:rgba(224,112,112,.15);border:1px solid rgba(224,112,112,.4);border-radius:var(--radius);color:var(--red);font-family:var(--font-sans);font-size:12px;font-weight:700;cursor:pointer;" data-i18n="sair.yes">SIM, SAIR</button>
        <button onclick="ufvaiExitCancel()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="ui.cancel">Cancelar</button>
      </div>
      <div class="sair-status" id="sair-status"></div>
    </div>
  </div>

  <!-- v0.6.20 — tela "Ambiente desconectado" (após SIM, SAIR) — visual igual à
       tela de Termos recusados; fica visível quando o runtime é desconectado -->
  <!-- v0.7.0 — Modal de RETOMADA: ao reabrir com autosave valido, pergunta
       se o usuario continua do ultimo autosave (mostrando data/hora) ou
       inicia uma nova sessao. A pergunta nao bloqueia: sem resposta,
       abre-se uma sessao nova. -->
  <div id="autosave-overlay" onclick="if(event.target===this)autosaveResumeNew()">
    <div id="autosave-modal" role="dialog" aria-modal="true" aria-labelledby="autosave-title">
      <div class="as-title" id="autosave-title">💾 <span data-i18n="autosave.resume.title">Retomar sessão</span></div>
      <p class="as-when" id="autosave-when"></p>
      <p class="as-text" data-i18n="autosave.resume.text">Há um salvamento automático. Deseja continuar a partir dele ou iniciar uma nova sessão?</p>
      <div class="as-actions">
        <button class="as-btn" onclick="autosaveResumeNew()" data-i18n="autosave.resume.new">Nova sessão</button>
        <button class="as-btn primary" onclick="autosaveResumeContinue()" data-i18n="autosave.resume.continue">Continuar de onde parei</button>
      </div>
    </div>
  </div>

  <!-- v0.6.20 — tela "Ambiente desconectado" (após SIM, SAIR) — visual igual à
       tela de Termos recusados; fica visível quando o runtime é desconectado -->
  <div id="exit-overlay">
    <div class="t-card">
      <div class="t-brand"><b>UFV</b><em>AI</em></div>
      <p class="e-msg">✅ Ambiente desconectado e excluído.<br>
        Para usar o UFVAI de novo: reexecute a célula de boot no Colab.<br>
        Os arquivos no seu Google Drive continuam salvos.<br><br>
        <span style="opacity:.75">Environment disconnected and deleted. To use UFVAI again, re-run the boot cell in Colab. Files on your Google Drive remain saved.</span></p>
    </div>
  </div>

  <div id="modal-overlay" onclick="if(event.target===this)closeModal()">
    <div id="modal" class="restore-modal">
      <div class="modal-title">🔄 <span data-i18n="ui.restore">Restaurar Sessão</span></div>
      <div class="restore-sub" id="restore-summary"></div>

      <!-- v0.7.0: navegacao por mes + filtro por data -->
      <div class="restore-toolbar">
        <button class="rnav" onclick="restorePrevMonth()" title="Mês anterior" data-i18n-title="restore.prev">‹</button>
        <span class="rmonth" id="restore-month-label"></span>
        <button class="rnav" onclick="restoreNextMonth()" title="Próximo mês" data-i18n-title="restore.next">›</button>
        <input type="date" id="restore-date" onchange="restoreSetDate(this.value)"
               title="Filtrar por data" data-i18n-title="restore.filter" aria-label="Filtrar por data">
        <button class="rghost" onclick="restoreClearDate()" data-i18n="restore.all_dates">Todas as datas</button>
        <button class="rghost" onclick="restoreToday()" data-i18n="restore.today">Hoje</button>
        <button class="rghost" onclick="restoreGoNewest()" data-i18n="restore.newest"
                title="Ir para o backup mais recente" data-i18n-title="restore.newest">Mais recente</button>
      </div>

      <!-- v0.7.2: meses que TEM backup (chips). Sem isso o calendario
           abria no mes atual (quase vazio) e as datas ficavam
           "escondidas" atras das setas — a impressao de "faltaram datas". -->
      <div class="restore-months" id="restore-months"></div>

      <!-- v0.7.0: calendario (dias com backup sao marcados) -->
      <div class="restore-cal">
        <div class="restore-dow" id="restore-dow"></div>
        <div class="restore-grid" id="restore-grid"></div>
      </div>

      <!-- v0.7.0: lista dos backups (somente backups de sessao) -->
      <div class="backup-list" id="backup-list">
        <div class="modal-empty" data-i18n="ui.loading">Carregando backups…</div>
      </div>
      <button class="modal-close" onclick="closeModal()" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="provider-overlay" onclick="if(event.target===this)closeProvider()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:24px;width:520px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div id="prov-step0">
        <div class="modal-title">🔌 <span data-i18n="providers.title">Conectar Provedor de IA</span></div>
        <p style="font-size:11.5px;color:var(--ink-muted);margin-bottom:14px;line-height:1.6;" data-i18n="providers.saved_keys">Chaves salvas no Drive:</p>
        <div id="prov-saved-list" style="max-height:220px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);padding:8px 10px;margin-bottom:14px;">
          <div style="font-size:11px;color:var(--ink-muted);padding:8px 0;text-align:center;" data-i18n="ui.loading">Carregando…</div>
        </div>
        <div style="display:flex;gap:8px;">
          <button onclick="openNewProvider()" style="flex:1;padding:9px;background:var(--accent-dim);border:1px solid rgba(var(--accent-rgb),.3);border-radius:var(--radius);color:var(--accent);font-family:var(--font-sans);font-size:12px;cursor:pointer;">+ <span data-i18n="providers.add_new">Novo provedor</span></button>
          <button onclick="closeProvider()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="ui.close">Fechar</button>
        </div>
      </div>
      <div id="prov-step1" style="display:none;">
        <div class="modal-title">🔌 <span data-i18n="providers.title">Conectar Provedor de IA</span></div>
        <p style="font-size:11.5px;color:var(--ink-muted);margin-bottom:14px;line-height:1.6;" data-i18n="providers.select">Selecione o provedor para configurar a API key:</p>
        <input id="prov-search" type="text" placeholder="Buscar provedor…" data-i18n-placeholder="providers.search" oninput="filterProviders(this.value)" style="display:block;width:100%;padding:8px 12px;box-sizing:border-box;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink);font-family:var(--font-sans);font-size:12px;outline:none;margin-bottom:12px;" />
        <div id="prov-list" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;"></div>
        <div style="display:flex;gap:8px;">
          <button onclick="provBack()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="providers.back">← Voltar</button>
          <button onclick="closeProvider()" style="flex:1;padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="ui.cancel">Cancelar</button>
        </div>
      </div>
      <div id="prov-step2" style="display:none;">
        <div class="modal-title">🔑 <span id="prov-name-title"></span></div>
        <p style="font-size:11px;color:var(--ink-muted);margin-bottom:14px;line-height:1.5;"><span data-i18n="providers.var">Variável</span>: <code id="prov-env-code" style="color:var(--accent);background:rgba(var(--accent-rgb),.08);padding:1px 6px;border-radius:3px;font-size:11px;"></code></p>
        <label style="display:block;font-size:10.5px;color:var(--ink-muted);margin-bottom:6px;letter-spacing:.05em;" data-i18n="providers.api_key">API KEY</label>
        <input id="prov-key-input" type="password" placeholder="Cole sua key aqui…" autocomplete="off" style="display:block;width:100%;padding:9px 12px;box-sizing:border-box;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink);font-family:var(--font-sans);font-size:12px;outline:none;margin-bottom:14px;transition:border-color .15s;" onfocus="this.style.borderColor='rgba(var(--accent-rgb),.4)'" onblur="this.style.borderColor='var(--line)'" onkeydown="if(event.key==='Enter')confirmProvider()"/>
        <div style="display:flex;gap:8px;">
          <button onclick="provBack()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="providers.back">← Voltar</button>
          <button onclick="confirmProvider()" style="flex:1;padding:9px;background:var(--accent-dim);border:1px solid rgba(var(--accent-rgb),.3);border-radius:var(--radius);color:var(--accent);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="providers.save_connect">Salvar e Conectar</button>
          <button onclick="closeProvider()" style="padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:12px;cursor:pointer;" data-i18n="ui.cancel">Cancelar</button>
        </div>
      </div>
    </div>
  </div>

  <div id="health-overlay" onclick="if(event.target===this)closeHealth()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:24px;width:440px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">🩺 <span data-i18n="dashboard.title">Dashboard de Saúde</span></div>
      <div id="health-list" style="max-height:340px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty" data-i18n="ui.loading">Carregando diagnóstico…</div>
      </div>
      <button onclick="closeHealth()" class="modal-close" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="sessions-overlay" onclick="if(event.target===this)closeSessions()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:24px;width:520px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">📜 <span data-i18n="sessions.title">Histórico de Sessões</span></div>
      <input id="session-search" class="session-search" placeholder="🔍 Buscar por id ou conteúdo…" oninput="filterSessions()" data-i18n-placeholder="sessions.search_placeholder">
      <div id="session-list" style="max-height:300px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty" data-i18n="ui.loading">Carregando sessões…</div>
      </div>
      <div style="display:flex;gap:8px;">
        <button onclick="loadSessions(true)" class="modal-close" style="width:auto;" data-i18n="sessions.refresh">↻ Atualizar</button>
        <button onclick="closeSessions()" class="modal-close" style="flex:1;" data-i18n="ui.close">Fechar</button>
      </div>
    </div>
  </div>

  <div id="shortcuts-overlay" onclick="if(event.target===this)closeShortcuts()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:24px;width:420px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
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

  <!-- Modal de Diretrizes do Agente (v0.4.2 + markdown render v0.4.2.1) — HOTFIX v0.5.1.2 -->
  <div id="agents-overlay" onclick="if(event.target===this)closeAgents()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div id="agents-modal" class="modal-shell" style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:0;width:680px;max-width:94vw;max-height:88vh;box-shadow:0 28px 72px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <div style="padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;">
        <span style="font-size:18px;">📋</span>
        <div style="flex:1;min-width:0;">
          <div class="modal-title" style="margin-bottom:2px;" data-i18n="agents.title">Diretrizes do Agente</div>
          <div style="font-size:10.5px;color:var(--ink-muted);" data-i18n="agents.subtitle">Regras e princípios do UFVAI (AGENTS.md)</div>
        </div>
        <span id="agents-lang-badge" style="font-size:10px;padding:2px 8px;border:1px solid var(--line);border-radius:3px;color:var(--ink-muted);font-family:var(--font-sans);">PT-BR</span>
        <button onclick="closeAgents()" class="modal-close" style="width:auto;padding:4px 10px;font-size:11px;" aria-label="Fechar">✕</button>
      </div>
      <div id="agents-content" class="markdown-body" style="flex:1;overflow-y:auto;padding:22px 26px;font-size:12.5px;line-height:1.65;color:var(--ink);" data-i18n="agents.loading">Carregando diretrizes…</div>
      <div style="padding:10px 18px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.02);">
        <button onclick="copyAgents()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="agents.copy">Copiar</button>
        <button onclick="reloadAgents()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;">↻ <span data-i18n="ui.loading">Recarregar</span></button>
        <div style="flex:1;"></div>
        <a id="agents-source-link" href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/AGENTS.md" target="_blank" class="footer-link" style="font-size:10.5px;" data-i18n="agents.open_source">Ver fonte</a>
      </div>
    </div>
  </div>

  <!-- Modal do Manual do UFVAI (v0.6.9 — MANUAL.md renderizado) -->
  <div id="manual-overlay" onclick="if(event.target===this)closeManual()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div id="manual-modal" class="modal-shell" style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:0;width:720px;max-width:94vw;max-height:88vh;box-shadow:0 28px 72px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <div style="padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;">
        <span style="font-size:18px;">📘</span>
        <div style="flex:1;min-width:0;">
          <div class="modal-title" style="margin-bottom:2px;" data-i18n="manual.title">Manual do UFVAI</div>
          <div style="font-size:10.5px;color:var(--ink-muted);" data-i18n="manual.subtitle">Guia completo de uso (MANUAL.md)</div>
        </div>
        <button onclick="closeManual()" class="modal-close" style="width:auto;padding:4px 10px;font-size:11px;" aria-label="Fechar">✕</button>
      </div>
      <div id="manual-content" class="markdown-body" style="flex:1;overflow-y:auto;padding:22px 26px;font-size:12.5px;line-height:1.65;color:var(--ink);" data-i18n="manual.loading">Carregando manual…</div>
      <div style="padding:10px 18px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.02);">
        <button onclick="reloadManual()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;">↻ <span data-i18n="ui.loading">Recarregar</span></button>
        <div style="flex:1;"></div>
        <a id="manual-source-link" href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/MANUAL.md" target="_blank" class="footer-link" style="font-size:10.5px;" data-i18n="manual.open_source">Ver fonte</a>
      </div>
    </div>
  </div>

  <!-- Modal de Memória UFVAI (v0.5.1.4 — navegar + editar) -->
  <div id="memory-overlay" onclick="if(event.target===this)closeMemory()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:0;width:980px;max-width:96vw;max-height:92vh;box-shadow:0 28px 72px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <!-- Header -->
      <div style="padding:14px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;">
        <span style="font-size:18px;">🧠</span>
        <div style="flex:1;min-width:0;">
          <div class="modal-title" style="margin-bottom:2px;" data-i18n="memory.title">Memória UFVAI</div>
          <div id="memory-subtitle" style="font-size:10.5px;color:var(--ink-muted);" data-i18n="memory.subtitle">Camada de memória persistente do agente</div>
        </div>
        <span id="memory-status-badge" style="font-size:10px;padding:2px 8px;border:1px solid var(--line);border-radius:3px;color:var(--ink-muted);font-family:var(--font-sans);">…</span>
        <span id="memory-dirty-indicator" style="display:none;font-size:10px;padding:2px 8px;background:var(--amber);color:#000;border-radius:3px;font-weight:600;">● <span data-i18n="memory.dirty">não salvo</span></span>
        <button onclick="closeMemory()" class="modal-close" style="width:auto;padding:4px 10px;font-size:11px;" aria-label="Fechar">✕</button>
      </div>

      <!-- Split view: lista (esq) + editor (dir) -->
      <!-- v0.6.25: id no container — sem ele o CSS mobile não consegue
           empilhar a lista sobre o editor (o pai ficava em flex ROW,
           a sidebar com width:100% tomava a linha inteira e o pane da
           NOTA saía da tela). -->
      <div id="memory-body" style="flex:1;display:flex;min-height:0;">
        <!-- Coluna esquerda: busca + lista -->
        <div id="memory-sidebar" style="width:300px;border-right:1px solid var(--line);display:flex;flex-direction:column;background:rgba(0,0,0,.18);">
          <div style="padding:10px 12px;border-bottom:1px solid var(--line);">
            <input id="memory-search-input" type="text" placeholder="🔍 Buscar…" data-i18n-placeholder="memory.search_placeholder" oninput="searchMemory(this.value)" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:6px 8px;font-size:11.5px;font-family:inherit;outline:none;" />
          </div>
          <div id="memory-list" style="flex:1;overflow-y:auto;padding:6px 8px;font-size:12px;">
            <div class="modal-empty" data-i18n="ui.loading">Carregando…</div>
          </div>
          <div style="padding:8px 12px;border-top:1px solid var(--line);display:flex;gap:6px;align-items:center;font-size:10.5px;color:var(--ink-muted);">
            <span id="memory-count">—</span>
            <div style="flex:1;"></div>
            <button onclick="openCreateNoteDialog()" class="modal-close" style="width:auto;padding:4px 8px;font-size:11px;" title="Nova nota" data-i18n-title="memory.new_note_title">+ <span data-i18n="memory.new_note">Nova</span></button>
          </div>
        </div>

        <!-- Coluna direita: editor + preview -->
        <div id="memory-editor-pane" style="flex:1;display:flex;flex-direction:column;min-width:0;">
          <!-- Meta da nota -->
          <div id="memory-note-meta" style="padding:10px 14px;border-bottom:1px solid var(--line);display:none;align-items:center;gap:8px;background:rgba(255,255,255,.02);">
            <div style="flex:1;min-width:0;">
              <input id="memory-note-title" type="text" placeholder="Título" data-i18n-placeholder="memory.note_title" oninput="markDirty()" style="width:100%;background:transparent;border:none;color:var(--ink);font-size:13px;font-weight:500;outline:none;font-family:inherit;" />
              <div id="memory-note-path" style="font-size:10px;color:var(--ink-muted);font-family:var(--font-mono);margin-top:2px;word-break:break-all;">—</div>
            </div>
            <div id="memory-note-tags-display" style="display:flex;flex-wrap:wrap;gap:3px;max-width:280px;"></div>
          </div>

          <!-- Tabs Edit/Preview -->
          <div id="memory-editor-tabs" style="display:none;padding:6px 14px 0;border-bottom:1px solid var(--line);background:rgba(255,255,255,.01);">
            <button id="memory-tab-preview" class="mem-tab active" onclick="switchMemoryTab('preview')" data-i18n="memory.tab_preview">Preview</button>
            <button id="memory-tab-edit" class="mem-tab" onclick="switchMemoryTab('edit')" data-i18n="memory.tab_edit">Editar</button>
            <button id="memory-tab-split" class="mem-tab" onclick="switchMemoryTab('split')" data-i18n="memory.tab_split">Dividido</button>
          </div>

          <!-- Editor + Preview -->
          <div id="memory-editor-body" style="flex:1;display:flex;min-height:0;background:rgba(0,0,0,.2);">
            <textarea id="memory-editor" spellcheck="false" oninput="onEditorInput()" style="flex:1;background:transparent;color:var(--ink);border:none;outline:none;resize:none;padding:14px;font-family:var(--font-mono);font-size:12px;line-height:1.55;display:none;" data-i18n-placeholder="memory.body_placeholder" placeholder="Selecione uma nota à esquerda ou crie uma nova."></textarea>
            <div id="memory-preview" style="flex:1;overflow-y:auto;padding:14px 18px;font-size:12.5px;line-height:1.6;color:var(--ink);display:none;"></div>
            <div class="modal-empty" id="memory-editor-empty" style="margin:auto;color:var(--ink-muted);text-align:center;padding:20px;">
              <div style="font-size:30px;margin-bottom:10px;opacity:.5;">🧠</div>
              <div data-i18n="memory.empty_editor">Selecione uma nota na lista ou crie uma nova.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div style="padding:10px 18px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.02);">
        <button onclick="openMemory(true)" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="memory.refresh">↻ Atualizar</button>
        <button onclick="openCreateNoteDialog()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="memory.new_note">+ Nova nota</button>
        <div style="flex:1;"></div>
        <button id="memory-btn-save" onclick="saveCurrentNote()" disabled style="width:auto;padding:5px 14px;font-size:11px;background:var(--green);color:#000;border:1px solid var(--green);border-radius:4px;font-weight:600;cursor:not-allowed;opacity:.4;" data-i18n="memory.save">💾 Salvar</button>
        <button id="memory-btn-delete" onclick="deleteCurrentNote()" disabled style="width:auto;padding:5px 12px;font-size:11px;background:transparent;color:var(--red);border:1px solid var(--red);border-radius:4px;cursor:not-allowed;opacity:.4;" data-i18n="memory.delete">🗑 Excluir</button>
        <a id="memory-open-drive" href="#" target="_blank" class="footer-link" style="font-size:10.5px;display:none;" data-i18n="memory.open_vault">Abrir Drive</a>
        <button onclick="closeMemory()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="ui.close">Fechar</button>
      </div>
    </div>
  </div>

  <!-- Sub-modal: criar nova nota (v0.5.1.4) -->
  <!-- v0.6.4: Painel Admin de Telemetria -->
  <div id="telemetry-overlay" onclick="if(event.target===this)closeTelemetry()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:100000;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:22px;width:460px;max-width:92vw;max-height:86vh;overflow:auto;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title" data-i18n="telemetry.title">📊 Telemetria (Admin)</div>
      <div id="tel-status" style="font-size:11.5px;line-height:1.6;color:var(--ink-muted);margin-bottom:14px;">…</div>
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="telemetry.mid">ID de medição (G-XXXXXXXXXX)</label>
      <input id="tel-mid" type="text" placeholder="G-CMVTFP2M6F" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;font-family:var(--font-mono);outline:none;margin-bottom:10px;" />
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="telemetry.secret">API Secret (Measurement Protocol)</label>
      <input id="tel-secret" type="password" placeholder="••••••••••••" autocomplete="off" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;font-family:var(--font-mono);outline:none;margin-bottom:6px;" />
      <div style="font-size:10.5px;line-height:1.5;color:var(--ink-muted);margin-bottom:14px;">
        GA4 → Admin → Fluxos de dados → Eventos de Measurement Protocol → Configurar.
        O secret é gravado localmente (<code>~/.config/ufvai_telemetry.json</code>, permissão 600)
        e nunca é exibido novamente. Deixe em branco para manter o já salvo. Guia completo: TELEMETRY.md §0.
      </div>
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;">✉️ URL de contato — recebe o e-mail dos usuários que aceitaram (opcional)</label>
      <input id="tel-contact" type="text" placeholder="https://script.google.com/macros/s/SEU_ID/exec" autocomplete="off" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;font-family:var(--font-mono);outline:none;margin-bottom:6px;" />
      <div id="tel-contact-status" style="font-size:10.5px;line-height:1.5;color:var(--ink-muted);margin-bottom:14px;">
        Canal recomendado (Google, grátis): Planilha + <b>Apps Script</b> — cada aceite de contato
        chega como nova linha na sua planilha. Passo a passo pronto: TELEMETRY.md §Passo 9.
        Vazio = usuários NÃO são encaminhados (fica só o contador anônimo no GA4).
      </div>
      <div id="tel-msg" style="font-size:11.5px;margin-bottom:10px;display:none;"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button class="btn-ghost" onclick="closeTelemetry()" style="padding:9px 16px;">Fechar</button>
        <button class="btn-ghost" onclick="saveTelemetry()" id="tel-save-btn" style="padding:9px 16px;background:var(--accent);color:#000;border-color:var(--accent);font-weight:600;">Salvar</button>
      </div>
    </div>
  </div>

  <div id="memory-new-overlay" onclick="if(event.target===this)closeCreateNoteDialog()" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:100000;opacity:0;pointer-events:none;transition:opacity .15s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:8px;padding:18px;width:420px;max-width:92vw;box-shadow:0 16px 40px rgba(0,0,0,.6);">
      <div style="font-size:13px;font-weight:600;margin-bottom:14px;" data-i18n="memory.new_note_dialog_title">📝 Nova nota</div>
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="memory.field_path">Caminho (ex: research/minha-nota.md)</label>
      <input id="memory-new-path" type="text" placeholder="research/minha-nota.md" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;font-family:var(--font-mono);outline:none;margin-bottom:10px;" />
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="memory.field_title">Título</label>
      <input id="memory-new-title" type="text" placeholder="Título da nota" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;outline:none;margin-bottom:10px;" />
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="memory.field_template">Template</label>
      <select id="memory-new-template" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;outline:none;margin-bottom:10px;">
        <option value="inbox">inbox</option>
      </select>
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="memory.field_tags">Tags (separadas por vírgula, opcional)</label>
      <input id="memory-new-tags" type="text" placeholder="pesquisai/research, foo/bar" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;outline:none;margin-bottom:14px;" />
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button onclick="closeCreateNoteDialog()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="ui.cancel">Cancelar</button>
        <button onclick="submitCreateNote()" class="btn-ghost" style="width:auto;padding:5px 14px;font-size:11px;background:var(--accent);color:#000;border:1px solid var(--accent);border-radius:4px;font-weight:600;" data-i18n="memory.create">Criar</button>
      </div>
    </div>
  </div>

  <style>
    /* v0.5.1.4 — Editor de memória PesquisAI */
    .mem-tab {
      background: transparent; color: var(--ink-muted); border: none;
      border-bottom: 2px solid transparent; padding: 6px 12px; font-size: 11.5px;
      cursor: pointer; font-family: inherit; transition: all .15s;
    }
    .mem-tab:hover { color: var(--ink); }
    .mem-tab.active { color: var(--ink); border-bottom-color: var(--accent); }
    .mem-note-item {
      padding: 6px 8px; border-radius: 4px; cursor: pointer; margin-bottom: 2px;
      transition: background .12s; border-left: 2px solid transparent;
    }
    .mem-note-item:hover { background: rgba(255,255,255,.04); }
    .mem-folder-card:hover { background: rgba(255,255,255,.04); }
    .mem-cal-day:hover { background: rgba(255,255,255,.06) !important; }
    .mem-note-item.active {
      background: rgba(var(--accent-rgb, 21, 122, 115), .12);
      border-left-color: var(--accent);
    }
    .mem-note-item .mem-note-title {
      font-size: 12px; color: var(--ink); font-weight: 500;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .mem-note-item .mem-note-path {
      font-size: 11px; color: var(--ink-muted); font-family: 'DM Mono', monospace;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .mem-note-item.human .mem-note-title::before {
      content: '✎ '; color: var(--ink-muted);
    }
    .mem-folder-label {
      font-size: 11px; color: var(--ink-muted); text-transform: uppercase;
      letter-spacing: .05em; padding: 8px 4px 4px; font-weight: 600;
    }
    .mem-preview h1, .mem-preview h2, .mem-preview h3 {
      color: var(--ink); margin: 0.6em 0 0.3em; font-weight: 600;
    }
    .mem-preview h1 { font-size: 17px; border-bottom: 1px solid var(--line); padding-bottom: 4px; }
    .mem-preview h2 { font-size: 15px; }
    .mem-preview h3 { font-size: 13.5px; }
    .mem-preview p { margin: 0.5em 0; }
    .mem-preview code {
      background: rgba(255,255,255,.06); padding: 1px 4px; border-radius: 3px;
      font-family: 'DM Mono', monospace; font-size: 11.5px;
    }
    .mem-preview pre {
      background: rgba(0,0,0,.3); padding: 8px 10px; border-radius: 4px;
      overflow-x: auto; font-size: 11.5px;
    }
    .mem-preview pre code { background: transparent; padding: 0; }
    .mem-preview blockquote {
      border-left: 3px solid var(--accent); margin: 0.5em 0;
      padding: 4px 10px; color: var(--ink-muted);
    }
    .mem-preview a { color: var(--accent); text-decoration: none; }
    .mem-preview ul, .mem-preview ol { padding-left: 1.5em; margin: 0.4em 0; }
    .mem-preview .wikilink {
      background: rgba(var(--accent-rgb, 21, 122, 115), .1);
      color: var(--accent); padding: 1px 5px; border-radius: 3px;
      font-family: 'DM Mono', monospace; font-size: 11px;
    }
    .mem-preview .tag {
      background: var(--accent-dim); color: var(--accent);
      padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-right: 3px;
    }
    .mem-preview hr { border: none; border-top: 1px solid var(--line); margin: 1em 0; }
  </style>
  <script>
    // ════════════════════════════════════════════════════════════
    // UFVAI v0.4.1 — Patch corretivo (marca v0.6.0)
    // (1) Responsividade, (2) Tema recarrega terminal, (3) Idioma UI
    // ════════════════════════════════════════════════════════════

    const BASE = location.origin;
    // v0.6.20-fix: IS_COLAB precisa existir no escopo DESTE script.
    // Antes, o único `IS_COLAB` era declarado dentro da IIFE do GA4 (script
    // posterior, escopo local); o uso top-level no bloco do botão SAIR
    // lançava `ReferenceError: IS_COLAB is not defined`, abortando todo este
    // script ANTES de registrar o listener de `load` — o splash nunca era
    // escondido e a UI travava em "Iniciando terminal…".
    const IS_COLAB = {__IS_COLAB__};
    const LANGS = {__LANGS_JSON__};
    const I18N = {__I18N_JSON__};
    const LANG_COOKIE = "pesquisai_lang";
    // v0.7.5+ (sem bump): separa "escolhi no menu" de "foi detectado".
    // Sem isso, um cookie en_US gravado por uma adoção automática antiga
    // vencia o navegador — a interface abria em inglês com o navegador em
    // português.
    const LANG_SRC_COOKIE = "pesquisai_lang_src";
    const THEME_COOKIE = "pesquisai_theme";
    const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 ano

    // ════════════════════════════════════════════════════════════
    // v0.7.5 — ABERTURA: UMA VEZ POR EXECUÇÃO DO UFVAI
    // ════════════════════════════════════════════════════════════
    // Problema relatado (23/10/2026): as telas de abertura apareciam
    // VÁRIAS vezes na mesma entrada (o iframe do Colab particiona o
    // sessionStorage e bloqueia cookies) e, depois do ajuste anterior,
    // deixavam de aparecer em entradas NOVAS: a marca ficava 12 h no
    // localStorage — inclusive a pergunta "Continuar de onde parei".
    //
    // Correção: a marca é escopada pelo ID DESTA EXECUÇÃO, injetado pelo
    // servidor no HTML. Recargas da mesma execução (idioma → terminal →
    // restore) NÃO repetem as telas; uma nova execução do UFVAI (novo
    // runtime/novo launch) tem outro ID e volta a mostrá-las. A marca vai
    // para TRÊS camadas (sessionStorage + localStorage + cookie) e é
    // gravada ANTES de exibir. Só o botão ↻ limpa a marca "resume".
    const UFVAI_BOOT_ID = "{__BOOT_ID__}" || "boot";
    function ufvaiOpeningKey(key) { return "ufvai_seen_" + key; }
    function ufvaiOpeningGet(key) {
      const name = ufvaiOpeningKey(key);
      try { if (sessionStorage.getItem(name) === UFVAI_BOOT_ID) return true; } catch (e) {}
      try { if (localStorage.getItem(name) === UFVAI_BOOT_ID) return true; } catch (e) {}
      try {
        const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
        if (m && decodeURIComponent(m[1]) === UFVAI_BOOT_ID) return true;
      } catch (e) {}
      return false;
    }
    function ufvaiOpeningMark(key) {
      const name = ufvaiOpeningKey(key);
      try { sessionStorage.setItem(name, UFVAI_BOOT_ID); } catch (e) {}
      try { localStorage.setItem(name, UFVAI_BOOT_ID); } catch (e) {}
      // cookie de sessão (sem expires): sobrevive a recargas, some ao
      // fechar o navegador — é o fallback quando os storages falham.
      try {
        document.cookie = name + "=" + encodeURIComponent(UFVAI_BOOT_ID) +
          "; path=/; SameSite=Lax";
      } catch (e) {}
    }
    function ufvaiOpeningClear(key) {
      const name = ufvaiOpeningKey(key);
      try { sessionStorage.removeItem(name); } catch (e) {}
      try { localStorage.removeItem(name); } catch (e) {}
      try {
        document.cookie = name + "=; path=/; SameSite=Lax; " +
          "expires=Thu, 01 Jan 1970 00:00:00 GMT";
      } catch (e) {}
    }
    function ufvaiOpeningAnyVisible() {
      try {
        const t = document.getElementById("terms-overlay");
        const w = document.getElementById("welcome-overlay");
        const a = document.getElementById("autosave-overlay");
        return (!!t && t.style.display !== "none" && t.style.display !== "") ||
               (!!w && w.style.display === "flex") ||
               (!!a && a.classList.contains("open"));
      } catch (e) { return false; }
    }

    // ── Cookie helpers ────────────────────────────────────────
    function setCookie(name, value) {
      document.cookie = name + "=" + encodeURIComponent(value) +
        "; path=/; max-age=" + COOKIE_MAX_AGE + "; SameSite=Lax";
    }
    function getCookie(name) {
      const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
      return m ? decodeURIComponent(m[2]) : null;
    }

    // ── Detecção de idioma (URL > escolha do usuário > navegador > resto) ─
    // v0.7.5+ (sem bump): o cookie só manda se o usuário escolheu no menu
    // (LANG_SRC_COOKIE=user). Cookie automático (adoção antiga do backend em
    // inglês) NÃO vence mais o navigator.language.
    function browserLang() {
      const list = (navigator.languages && navigator.languages.length)
        ? navigator.languages
        : [navigator.language || ""];
      for (let i = 0; i < list.length; i++) {
        const l = String(list[i] || "").toLowerCase();
        if (l.startsWith("pt")) return "pt_BR";
        if (l.startsWith("en")) return "en_US";
        if (l.startsWith("es")) return "es_ES";
        if (l.startsWith("fr")) return "fr_FR";
        // v0.7.5: zh_CN é suportado desde a v0.6.25. Antes, um navegador em
        // chinês era forçado para en_US — o frontend e o backend divergiam
        // a cada entrada e o "sync" de idioma reiniciava o terminal.
        if (l.startsWith("zh")) return "zh_CN";
      }
      return "";
    }

    function getCurrentLang() {
      // 1. Query param ?lang=xx_XX (forçar via link) = escolha explícita
      const url = new URL(location.href);
      const ql = url.searchParams.get("lang");
      if (ql && LANGS[ql]) {
        setCookie(LANG_COOKIE, ql);
        setCookie(LANG_SRC_COOKIE, "user");
        return ql;
      }
      // 2. Cookie de escolha EXPLÍCITA do usuário
      const ck = getCookie(LANG_COOKIE);
      if (getCookie(LANG_SRC_COOKIE) === "user" && ck && LANGS[ck]) return ck;
      // 3. Navegador (fonte da detecção automática)
      const nav = browserLang();
      if (nav) return nav;
      // 4. Cookie/localStorage gravados automaticamente (fallback)
      if (ck && LANGS[ck]) return ck;
      try {
        const ls = localStorage.getItem(LANG_COOKIE);
        if (ls && LANGS[ls]) return ls;
      } catch (e) {}
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
      // 8. v0.7.0: redesenha o modal "Restaurar" (calendario + lista) no
      //    novo idioma, se ele estiver aberto.
      try {
        const overlay = document.getElementById("modal-overlay");
        if (overlay && overlay.classList.contains("open") && typeof renderRestore === "function") {
          renderRestore();
        }
      } catch (e) {}
    }

    async function setLang(lang) {
      // v0.6.1: AGUARDA o backend reiniciar o ttyd (saudação no novo idioma)
      // ANTES de recarregar a página — antes, o reload em 700ms interrompia
      // o restart (~3-4s) e o iframe reconectava num terminal morto/antigo.
      // v0.6.5: splash imediato ("Reiniciando terminal…") durante o restart;
      // se falhar, splash some + toast de erro (sem reload às cegas).
      if (!LANGS[lang]) lang = "pt_BR";
      // v0.7.5: escolher o idioma que já está ativo não reinicia nada
      // (antes: matava o ttyd e criava outra sessão sem necessidade).
      if (lang === _currentLang) {
        // ainda assim marca como escolha explícita (cookie antigo/auto)
        setCookie(LANG_COOKIE, lang);
        setCookie(LANG_SRC_COOKIE, "user");
        closeLangMenu();
        return;
      }
      setCookie(LANG_COOKIE, lang);
      setCookie(LANG_SRC_COOKIE, "user");
      const dict = I18N[lang] || I18N["pt_BR"];
      toast("🌐 " + (dict["languages.switched_to"] || lang), "info");
      closeLangMenu();
      applyLang(lang);
      showBootSplash(dict["boot.restarting"] || "Reiniciando terminal…");
      let ok = false;
      try {
        const ctrl = new AbortController();
        // v0.6.5: backend espera a porta abrir com retry (~worst 22s); 35s de folga
        const timer = setTimeout(() => ctrl.abort(), 35000);
        const resp = await fetch(BASE + "/api/lang", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          // v0.7.5: restart explícito — o backend reabre a sessão atual.
          body: JSON.stringify({ lang: lang, restart: true }),
          signal: ctrl.signal
        });
        clearTimeout(timer);
        ok = resp.ok;
      } catch (e) { ok = false; }
      if (!ok) {
        hideBootSplash();
        toast("❌ " + ((I18N[_currentLang] || I18N["pt_BR"])["boot.failed"] ||
              "Falha ao reiniciar o terminal. Tente novamente."), "err");
        return;
      }
      // Recarrega para aplicar traduções do backend (toasts, modais completos).
      // O backend só responde depois que a porta do ttyd já aceita conexões.
      setTimeout(() => location.reload(), 400);
    }

    function buildLangMenu() {
      const menu = document.getElementById("lang-menu");
      if (!menu) return;
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      menu.innerHTML = Object.values(LANGS).map(l => `
        <button class="lang-option" data-lang="${l.code}"
                onclick="setLang('${l.code}')"
                role="menuitem"
                aria-current="${l.code === _currentLang ? 'true' : 'false'}">
          <span class="lang-flag">${l.flag}</span>
          <span class="lang-name">${dict["languages." + l.code] || l.name}</span>
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

    // ─────────────────────────────────────────────────────────────────
    // v0.7.0 — "Restaurar": SOMENTE backups, com CALENDARIO e FILTRO
    // por data. Antes, o modal listava todos os .json da pasta de
    // backups (incluindo chaves e consentimentos, que nao sao backup).
    // ─────────────────────────────────────────────────────────────────
    let _restoreItems = [];      // backups (objetos) vindos de /api/backups
    let _restoreDate = "";       // "YYYY-MM-DD" selecionado ("" = todas)
    let _restoreMonth = null;    // {y, m} — mes exibido no calendario

    function restoreDict() {
      return I18N[_currentLang] || I18N["pt_BR"] || {};
    }

    function restoreLocale() {
      return ({ pt_BR: "pt-BR", en_US: "en-US", es_ES: "es-ES",
                fr_FR: "fr-FR", zh_CN: "zh-CN" })[_currentLang] || "pt-BR";
    }

    function restorePad(n) { return String(n).padStart(2, "0"); }

    function restoreDateKey(d) {
      return d.getFullYear() + "-" + restorePad(d.getMonth() + 1) + "-" + restorePad(d.getDate());
    }

    /** Grade do mes (semanas de 7) — 1a linha = segunda-feira. */
    function restoreBuildGrid(year, month) {
      const first = new Date(year, month, 1);
      const startDow = (first.getDay() + 6) % 7;     // 0 = segunda
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const cells = [];
      for (let i = 0; i < startDow; i++) cells.push(null);
      for (let d = 1; d <= daysInMonth; d++) cells.push(d);
      while (cells.length % 7 !== 0) cells.push(null);
      const weeks = [];
      for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
      return weeks;
    }

    /** Quantidade de backups por data ("YYYY-MM-DD"). */
    function restoreDayCounts(items) {
      const counts = {};
      (items || []).forEach(function (it) {
        if (!it || !it.date) return;
        counts[it.date] = (counts[it.date] || 0) + 1;
      });
      return counts;
    }

    /** Normaliza um item vindo da API: aceita objeto (v0.7.0) ou nome (legado).
     *  No formato antigo (apenas o nome do arquivo) a data/hora sao lidas do
     *  proprio nome: backup_ses_<id>_<HH-MM-SS>_<DD-MM-YYYY>.json */
    function restoreItemFromName(name) {
      const item = {
        file: name, kind: "backup", session_id: "", date: "", time: "",
        datetime: "", size: 0, size_h: "", title: "", valid: true,
      };
      const m = /^backup_ses_([0-9A-Za-z]{3,40})_(\\d{2})-(\\d{2})-(\\d{2})_(\\d{2})-(\\d{2})-(\\d{4})\\.json$/.exec(name);
      if (m) {
        item.session_id = m[1];
        item.time = m[2] + ":" + m[3] + ":" + m[4];
        item.date = m[7] + "-" + m[6] + "-" + m[5];
        item.datetime = item.date + "T" + item.time;
        return item;
      }
      const a = /^(?:autosave\\/)?autosave_(\\d+)\\.json$/.exec(name);
      if (a) item.kind = "autosave";
      return item;
    }

    /** Deriva "date"/"time" de um item que nao os traz. */
    function restoreFillDates(it) {
      if (!it || typeof it !== "object") return it;
      if (!it.date) {
        const iso = String(it.datetime || it.saved_at_iso || "");
        const m = /^(\\d{4})-(\\d{2})-(\\d{2})/.exec(iso);
        if (m) it.date = m[1] + "-" + m[2] + "-" + m[3];
        else {
          const ts = Number(it.timestamp || it.saved_at || 0);
          if (ts > 0) {
            const d = new Date(ts * 1000);
            if (!isNaN(d.getTime())) it.date = restoreDateKey(d);
          }
        }
      }
      if (!it.time) {
        const m2 = /T(\\d{2}:\\d{2}:\\d{2})/.exec(String(it.datetime || ""));
        if (m2) it.time = m2[1];
        else if (it.date && Number(it.timestamp || it.saved_at || 0) > 0) {
          const d = new Date(Number(it.timestamp || it.saved_at) * 1000);
          if (!isNaN(d.getTime())) it.time = restorePad(d.getHours()) + ":" + restorePad(d.getMinutes()) + ":" + restorePad(d.getSeconds());
        }
      }
      return it;
    }

    function restoreNormalizeItems(raw) {
      return (raw || []).map(function (it) {
        if (typeof it === "string") return restoreFillDates(restoreItemFromName(it));
        // v0.7.2: sem "date", o item nao entrava na contagem do calendario
        // e sumia do filtro por data (parecia que faltavam datas).
        return restoreFillDates(it);
      });
    }

    /** Filtro por data (vazio = todas as datas). */
    function restoreFilterByDate(items, date) {
      if (!date) return (items || []).slice();
      return (items || []).filter(function (it) {
        if (!it) return false;
        // v0.7.2: item sem data nao pode sumir do filtro.
        if (!it.date) return true;
        return it.date === date;
      });
    }

    function restoreFormatDate(dateKey) {
      if (!dateKey) return "—";
      try {
        const d = new Date(dateKey + "T00:00:00");
        if (isNaN(d.getTime())) return dateKey;
        return d.toLocaleDateString(restoreLocale(),
          { day: "2-digit", month: "short", year: "numeric" });
      } catch (e) {
        return dateKey;
      }
    }

    function restoreItemHtml(it, dict) {
      const badge = it.kind === "autosave"
        ? '<span class="b-badge auto">' + escapeHtml(dict["restore.autosave"] || "Autossave") + "</span>"
        : "";
      const bad = (it.valid === false)
        ? '<span class="b-badge bad">' + escapeHtml(dict["restore.invalid"] || "corrompido") + "</span>"
        : "";
      const title = it.title || it.session_id || it.file;
      // v0.7.1 — botao de APAGAR o backup (com confirmacao no backend).
      // O nome vai em data-file (nao em JS inline) para nao quebrar as
      // aspas; o onclick para a propagacao para nao disparar o restaurar.
      const delLabel = escapeHtml(dict["restore.delete"] || "apagar");
      return `<div class="backup-item" onclick="doRestore('${escapeHtml(it.file)}')">` +
        '<div class="b-main">' +
          '<span class="b-time">' + escapeHtml(it.time || "") + badge + bad + "</span>" +
          '<span class="b-meta">' + escapeHtml(title) +
            (it.size_h ? " · " + escapeHtml(it.size_h) : "") + "</span>" +
        "</div>" +
        '<button class="b-del" type="button" data-file="' + escapeHtml(it.file) + '"' +
          ' title="' + delLabel + '" aria-label="' + delLabel + '"' +
          ' onclick="event.stopPropagation(); doDeleteBackup(this.dataset.file)">🗑</button>' +
        '<span class="restore-lbl">' + escapeHtml(dict["ui.restore"] || "restaurar") + "</span>" +
      "</div>";
    }

    /** Desenha calendario + lista conforme o filtro atual. */
    function renderRestore() {
      const dict = restoreDict();
      const grid = document.getElementById("restore-grid");
      const dow = document.getElementById("restore-dow");
      const label = document.getElementById("restore-month-label");
      const list = document.getElementById("backup-list");
      const summary = document.getElementById("restore-summary");
      const dateInput = document.getElementById("restore-date");
      if (!grid || !list) return;

      if (!_restoreMonth) {
        const now = new Date();
        _restoreMonth = { y: now.getFullYear(), m: now.getMonth() };
      }
      if (dateInput && dateInput.value !== _restoreDate) dateInput.value = _restoreDate;

      const counts = restoreDayCounts(_restoreItems);

      // cabecalho: dias da semana (i18n)
      if (dow) {
        let html = "";
        for (let i = 0; i < 7; i++) html += "<div>" + escapeHtml(dict["restore.dow." + i] || "") + "</div>";
        dow.innerHTML = html;
      }

      // rotulo do mes
      if (label) {
        try {
          label.textContent = new Date(_restoreMonth.y, _restoreMonth.m, 1)
            .toLocaleDateString(restoreLocale(), { year: "numeric", month: "long" });
        } catch (e) {
          label.textContent = _restoreMonth.y + "-" + restorePad(_restoreMonth.m + 1);
        }
      }

      // v0.7.2 — chips dos meses que TEM backup (clica para navegar).
      // Sem isso, o calendario abre no mes atual (quase vazio) e o
      // usuario conclui que "faltaram datas".
      const monthsEl = document.getElementById("restore-months");
      if (monthsEl) {
        const byMonth = {};
        (_restoreItems || []).forEach(function (it) {
          if (!it || !it.date) return;
          const mk = String(it.date).slice(0, 7);
          byMonth[mk] = (byMonth[mk] || 0) + 1;
        });
        const mkeys = Object.keys(byMonth).sort().reverse();
        if (!mkeys.length) {
          monthsEl.innerHTML = "";
        } else {
          monthsEl.innerHTML = mkeys.map(function (mk) {
            const parts = mk.split("-");
            const y = Number(parts[0]), mi = Number(parts[1]) - 1;
            let label = mk;
            try {
              label = new Date(y, mi, 1)
                .toLocaleDateString(restoreLocale(), { year: "2-digit", month: "short" });
            } catch (e) { label = mk; }
            const cur = (_restoreMonth.y === y && _restoreMonth.m === mi);
            const tip = (dict["restore.month_tip"] || "{n} backups em {m}")
              .replace("{n}", byMonth[mk]).replace("{m}", label);
            return '<button type="button" class="rmonth-chip' + (cur ? " on" : "") + '"' +
              ' onclick="restoreGoMonth(' + y + "," + mi + ')"' +
              ' title="' + escapeHtml(tip) + '">' + escapeHtml(label) +
              " <b>" + byMonth[mk] + "</b></button>";
          }).join("");
        }
      }

      // grade do calendario
      const weeks = restoreBuildGrid(_restoreMonth.y, _restoreMonth.m);
      const todayKey = restoreDateKey(new Date());
      const prefix = _restoreMonth.y + "-" + restorePad(_restoreMonth.m + 1) + "-";
      grid.innerHTML = weeks.map(function (week) {
        return week.map(function (day) {
          if (!day) return '<div class="restore-day empty"></div>';
          const key = prefix + restorePad(day);
          const n = counts[key] || 0;
          const cls = ["restore-day"];
          if (n) cls.push("has");
          if (key === todayKey) cls.push("today");
          if (key === _restoreDate) cls.push("sel");
          // v0.7.2: tooltip correto (antes era "3)") + numero de backups.
          const tip = n ? ' title="' + escapeHtml((dict["restore.day_tip"] || "{n} backups").replace("{n}", n)) + '"' : "";
          return `<div class="${cls.join(" ")}" onclick="restorePickDate('${key}')"` + tip +
                 ">" + day + (n ? '<span class="rd-n">' + n + "</span>" : "") + "</div>";
        }).join("");
      }).join("");

      // resumo
      if (summary) {
        const total = _restoreItems.length;
        const shown = restoreFilterByDate(_restoreItems, _restoreDate).length;
        summary.textContent = _restoreDate
          ? (dict["restore.summary_filtered"] || "{shown} de {total} backups")
              .replace("{shown}", shown).replace("{total}", total)
          : (dict["restore.count"] || "{total} backups").replace("{total}", total);
      }

      // lista
      const filtered = restoreFilterByDate(_restoreItems, _restoreDate);
      if (!_restoreItems.length) {
        list.innerHTML = '<div class="modal-empty">' +
          escapeHtml(dict["restore.empty"] || "Nenhum backup encontrado.") + "</div>";
        return;
      }
      if (!filtered.length) {
        // v0.7.2: estado vazio ACCIONAVEL — oferece "Todas as datas"
        // (antes ficava um beco sem saida: "Nenhum backup nesta data").
        list.innerHTML = '<div class="modal-empty">' +
          escapeHtml(dict["restore.empty_date"] || "Nenhum backup nesta data.") +
          ' <button class="rghost" onclick="restoreClearDate()">' +
          escapeHtml(dict["restore.all_dates"] || "Todas as datas") + "</button></div>";
        return;
      }
      const byDate = {};
      filtered.forEach(function (it) {
        const key = it.date || "__nodate__";
        (byDate[key] = byDate[key] || []).push(it);
      });
      let html = "";
      // v0.7.2: datas em ordem decrescente; "sem data" sempre por ultimo.
      Object.keys(byDate).sort(function (a, b) {
        if (a === "__nodate__") return 1;
        if (b === "__nodate__") return -1;
        return a < b ? 1 : (a > b ? -1 : 0);
      }).forEach(function (date) {
        const noDate = (date === "__nodate__");
        html += '<div class="restore-daygroup' + (noDate ? " nodate" : "") + '">' +
          escapeHtml(noDate ? (dict["restore.nodate"] || "sem data") : restoreFormatDate(date)) + "</div>";
        byDate[date].forEach(function (it) { html += restoreItemHtml(it, dict); });
      });
      list.innerHTML = html;
    }

    function restorePickDate(key) {
      _restoreDate = (_restoreDate === key) ? "" : key;   // clique de novo = desmarcar
      if (_restoreDate) {
        const parts = _restoreDate.split("-");
        _restoreMonth = { y: parseInt(parts[0], 10), m: parseInt(parts[1], 10) - 1 };
      }
      renderRestore();
    }

    function restoreSetDate(value) {
      _restoreDate = value || "";
      if (_restoreDate) {
        const parts = _restoreDate.split("-");
        _restoreMonth = { y: parseInt(parts[0], 10), m: parseInt(parts[1], 10) - 1 };
      }
      renderRestore();
    }

    function restoreClearDate() {
      _restoreDate = "";
      renderRestore();
    }

    function restoreToday() {
      const now = new Date();
      _restoreDate = restoreDateKey(now);
      _restoreMonth = { y: now.getFullYear(), m: now.getMonth() };
      renderRestore();
    }

    function restoreShiftMonth(delta) {
      if (!_restoreMonth) { const now = new Date(); _restoreMonth = { y: now.getFullYear(), m: now.getMonth() }; }
      const d = new Date(_restoreMonth.y, _restoreMonth.m + delta, 1);
      _restoreMonth = { y: d.getFullYear(), m: d.getMonth() };
      renderRestore();
    }

    function restorePrevMonth() { restoreShiftMonth(-1); }
    function restoreNextMonth() { restoreShiftMonth(1); }

    /** v0.7.2 — vai para um mes especifico (chips de meses com backup). */
    function restoreGoMonth(y, m) {
      _restoreMonth = { y: Number(y), m: Number(m) };
      renderRestore();
    }

    /** v0.7.2 — vai para o mes do backup mais recente (sem filtrar data). */
    function restoreGoNewest() {
      if (!_restoreItems.length) return;
      const newest = _restoreItems[0];
      const parts = String(newest.date || "").split("-");
      if (parts.length === 3) {
        _restoreMonth = { y: parseInt(parts[0], 10), m: parseInt(parts[1], 10) - 1 };
      }
      _restoreDate = "";
      renderRestore();
    }

    async function openRestore() {
      document.getElementById("modal-overlay").classList.add("open");
      const list = document.getElementById("backup-list");
      const dict = restoreDict();
      list.innerHTML = '<div class="modal-empty">' + (dict["ui.loading"] || "Carregando…") + '</div>';
      try {
        const r = await fetch(BASE + "/api/backups");
        const d = await r.json();
        _restoreItems = restoreNormalizeItems(d && d.backups);
        // abre no mes do backup mais recente (ou hoje, se nao houver)
        if (_restoreItems.length) {
          const newest = _restoreItems[0];
          const parts = String(newest.date || "").split("-");
          if (parts.length === 3) _restoreMonth = { y: parseInt(parts[0], 10), m: parseInt(parts[1], 10) - 1 };
        }
        renderRestore();
      } catch(e) {
        list.innerHTML = '<div class="modal-empty">' +
          escapeHtml(dict["restore.error"] || "Erro ao carregar os backups.") + "</div>";
      }
    }

    function closeModal() {
      document.getElementById("modal-overlay").classList.remove("open");
    }

    // ═══════════════════════════════════════════════════════════
    // v0.6.20 — SAIR: desconectar e excluir o ambiente de execução
    // Botão vive na interface do app (topbar/drawer). Exibido somente
    // no Colab. Confirmação OBRIGATÓRIA; após confirmar:
    //   POST /api/shutdown {confirm:true} → backend salva a nota de fim
    //   de sessão na memória, encerra o keep-alive e desconecta o runtime.
    // ═══════════════════════════════════════════════════════════
    function _sairDict() {
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      return {
        status: dict["sair.status"] || "Encerrando o ambiente… aguarde",
        fail: dict["sair.fail"] || "Falha ao encerrar — use Runtime ▸ Desconectar e excluir ambiente.",
      };
    }
    function ufvaiExit() {
      const ov = document.getElementById("sair-overlay");
      document.getElementById("sair-status").textContent = "";
      const yes = document.getElementById("sair-yes");
      yes.disabled = false; yes.style.opacity = "1";
      ov.classList.add("open");
    }
    function ufvaiExitCancel() {
      document.getElementById("sair-overlay").classList.remove("open");
    }
    // v0.6.20 — tela "Ambiente desconectado": mostra o overlay full-screen
    // (mesmo visual da tela de Termos recusados) e fecha o modal; a tela
    // permanece visível quando o runtime do Colab é desconectado/excluído.
    function ufvaiExitDone() {
      ufvaiExitCancel();
      const eo = document.getElementById("exit-overlay");
      if (eo) eo.style.display = "flex";
    }
    async function ufvaiExitConfirm() {
      const d = _sairDict();
      const st = document.getElementById("sair-status");
      const yes = document.getElementById("sair-yes");
      yes.disabled = true; yes.style.opacity = ".6";
      st.textContent = d.status;
      try {
        const r = await fetch(BASE + "/api/shutdown", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirm: true })
        });
        const resp = await r.json().catch(() => ({}));
        if (r.ok && resp.ok) {
          // v0.6.20-fix: a rota responde na hora (o unassign é agendado em
          // thread daemon no backend). Mostramos imediatamente a tela
          // "Ambiente desconectado" — ela permanece visível quando a conexão
          // cai (sem a antiga espera fixa de 2,5 s).
          ufvaiExitDone();
        } else {
          yes.disabled = false; yes.style.opacity = "1";
          st.textContent = resp.error || d.fail;
        }
      } catch (e) {
        yes.disabled = false; yes.style.opacity = "1";
        st.textContent = d.fail;
      }
    }
    // Exibe os botões SAIR somente no Colab (no .deb/offline não há runtime a encerrar)
    if (IS_COLAB) {
      try {
        document.getElementById("sair-btn").style.display = "";
        document.getElementById("sair-btn-mobile").style.display = "";
      } catch (e) {}
    }

    async function doRestore(file) {
      const dict = restoreDict();
      // v0.7.0: a confirmacao mostra data/hora do backup (o que o usuario
      // ve no calendario), e nao o nome cru do arquivo.
      let when = file;
      try {
        const item = (_restoreItems || []).find(function (it) { return it.file === file; });
        if (item) when = restoreFormatDate(item.date) + " " + (item.time || "");
      } catch (e) {}
      // 🔔 CORREÇÃO v0.5.1.8: confirma antes de restaurar backup
      const question = (dict["restore.confirm"] || "Restaurar o backup de {when}?")
        .replace("{when}", when);
      pesquisaiConfirm(question, async function() {
        closeModal();
        toast("⏳ " + ((dict["restore.restoring"] || "Restaurando {when}…").replace("{when}", when)), "info");
        try {
          const r = await fetch(BASE + "/api/restore", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file })
          });
          const d = await r.json();
          if (d.ok) {
            if (d.ttyd_restarted) {
              const dropped = (d.fit && d.fit.messages_dropped) || 0;
              const base = (dict["restore.done"] || "Sessão restaurada");
              toast("✅ " + base + (dropped
                ? " · " + ((dict["restore.partial"] || "{n} mensagens antigas omitidas para caber no contexto").replace("{n}", dropped))
                : ""), "ok");
              // v0.7.5+: o backend já espera a porta do ttyd abrir — o
              // reload pode ser imediato (antes: 3,5 s fixos de espera).
              setTimeout(() => location.reload(), 1200);
            } else {
              toast("⚠️ Importado, mas ttyd não reiniciou. Recarregue manualmente (Ctrl+Shift+R).", "warn");
              // Fallback: tentar reload após 1.5s
              setTimeout(() => location.reload(), 1200);
            }
          } else {
            toast("❌ " + (d.error || "Erro"), "err");
          }
        } catch(e) {
          toast("❌ Falha: " + e.message, "err");
        }
      });
    }

    // ═══════════════════════════════════════════════════════════
    // v0.7.1 — APAGAR backup/autosave pelo menu "Restaurar".
    // Confirmacao OBRIGATORIA (dialogo do app + "confirm": true no
    // backend); depois de apagar, a lista e' recarregada.
    // ═══════════════════════════════════════════════════════════
    async function doDeleteBackup(file) {
      if (!file) return;
      const dict = restoreDict();
      // data/hora do item (o que o usuario ve no calendario)
      let when = file;
      try {
        const item = (_restoreItems || []).find(function (it) { return it.file === file; });
        if (item) when = restoreFormatDate(item.date) + " " + (item.time || "");
      } catch (e) {}
      const question = (dict["restore.delete_confirm"] ||
        "Apagar o backup de {when}? Esta ação não pode ser desfeita.")
        .replace("{when}", when);
      // a confirmacao do app e' OBRIGATORIA; o backend exige "confirm": true
      pesquisaiConfirm(question, async function() {
        toast("🗑 " + ((dict["restore.deleting"] || "Apagando {when}…")
          .replace("{when}", when)), "info");
        try {
          const r = await fetch(BASE + "/api/backup/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file: file, confirm: true })
          });
          const d = await r.json();
          if (d && d.ok) {
            toast("✅ " + (dict["restore.deleted"] || "Backup apagado."), "ok");
            await refreshRestoreList();
          } else {
            toast("❌ " + ((d && d.error) || (dict["restore.delete_failed"] ||
              "Falha ao apagar o backup.")), "err");
          }
        } catch (e) {
          toast("❌ " + e.message, "err");
        }
      });
    }

    /** Recarrega a lista de backups (usada apos apagar um). */
    async function refreshRestoreList() {
      try {
        const r = await fetch(BASE + "/api/backups");
        const d = await r.json();
        _restoreItems = restoreNormalizeItems(d && d.backups);
        renderRestore();
      } catch (e) { /* silencioso: a lista fica como estava */ }
    }

    const PROVIDERS = [
      { id:"anthropic", name:"Anthropic", env:"ANTHROPIC_API_KEY", hint:"sk-ant-…", recommended:true },
      { id:"bedrock", name:"AWS Bedrock", env:"AWS_ACCESS_KEY_ID", hint:"AKIA…" },
      { id:"azure", name:"Azure OpenAI", env:"AZURE_OPENAI_API_KEY", hint:"…" },
      { id:"deepseek", name:"DeepSeek", env:"DEEPSEEK_API_KEY", hint:"sk-…" },
      { id:"google", name:"Google Gemini", env:"GOOGLE_GENERATIVE_AI_API_KEY", hint:"AIza…", recommended:true },
      { id:"groq", name:"Groq", env:"GROQ_API_KEY", hint:"gsk_…" },
      { id:"mistral", name:"Mistral", env:"MISTRAL_API_KEY", hint:"…" },
      { id:"nvidia", name:"Nvidia NIM", env:"NVIDIA_API_KEY", hint:"nvapi-…" },
      { id:"openai", name:"OpenAI", env:"OPENAI_API_KEY", hint:"sk-…", recommended:true },
      { id:"opencode_go", name:"OpenCode Go", env:"OPENCODE_API_KEY", hint:"sk-…" },
      { id:"opencode_zen", name:"OpenCode Zen", env:"OPENCODE_API_KEY", hint:"sk-…" },
      { id:"openrouter", name:"OpenRouter", env:"OPENROUTER_API_KEY", hint:"sk-or-…" },
      { id:"together", name:"Together AI", env:"TOGETHER_API_KEY", hint:"…" },
      { id:"vertex", name:"Vertex AI", env:"VERTEX_API_KEY", hint:"…" },
      { id:"xai", name:"xAI (Grok)", env:"XAI_API_KEY", hint:"xai-…" },
    ];

    let _selProv = null;

    function connectProvider() {
      const overlay = document.getElementById("provider-overlay");
      overlay.style.opacity = "1";
      overlay.style.pointerEvents = "all";
      showProviderStep("prov-step0");
      loadSavedKeys(true);
    }

    function showProviderStep(stepId) {
      ["prov-step0", "prov-step1", "prov-step2"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = (id === stepId) ? "block" : "none";
      });
      if (stepId === "prov-step1") {
        document.getElementById("prov-search").value = "";
        renderProviderList("");
      }
      if (stepId === "prov-step2") {
        document.getElementById("prov-key-input").value = "";
      }
    }

    function openNewProvider() {
      _selProv = null;
      showProviderStep("prov-step1");
    }

    function renderProviderList(q) {
      q = (q || "").trim().toLowerCase();
      const recommended = PROVIDERS.filter(p => p.recommended && (!q || p.name.toLowerCase().includes(q) || p.id.includes(q)));
      const others = PROVIDERS.filter(p => !p.recommended && (!q || p.name.toLowerCase().includes(q) || p.id.includes(q)));
      const btn = (p) => `<button onclick="selectProvider('${p.id}')" style="display:flex;align-items:center;gap:8px;padding:9px 12px;background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);font-family:var(--font-sans);font-size:11px;cursor:pointer;text-align:left;transition:background .12s,color .12s,border-color .12s;">${p.name}</button>`;
      let html = "";
      if (recommended.length) html += '<div style="grid-column:1/-1;font-size:10px;letter-spacing:.06em;color:var(--ink-muted);text-transform:uppercase;margin:2px 0 4px;">Recomendados</div>' + recommended.map(btn).join("");
      if (others.length) html += others.map(btn).join("");
      if (!html) html = '<div style="grid-column:1/-1;font-size:11px;color:var(--ink-muted);padding:8px 0;">Nenhum provedor encontrado.</div>';
      document.getElementById("prov-list").innerHTML = html;
    }

    function filterProviders(q) { renderProviderList(q); }

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

    // ── Confirm dialog (replaces native confirm()) ─────────────
    function pesquisaiConfirm(msg, onYes) {
      document.getElementById("confirm-msg").textContent = msg;
      const ov = document.getElementById("confirm-overlay");
      const yes = document.getElementById("confirm-yes");
      const no = document.getElementById("confirm-no");
      yes.onclick = function() { ov.style.opacity = "0"; ov.style.pointerEvents = "none"; if (onYes) onYes(); };
      no.onclick = function() { ov.style.opacity = "0"; ov.style.pointerEvents = "none"; };
      ov.onclick = function(e) { if (e.target === ov) { ov.style.opacity = "0"; ov.style.pointerEvents = "none"; } };
      ov.style.opacity = "1"; ov.style.pointerEvents = "all";
    }

    function provBack() {
      if (document.getElementById("prov-step2").style.display === "block") {
        // Se estiver editando uma chave existente, volta para a lista de chaves
        if (_selProv && _selProv._edit) {
          _selProv = null;
          showProviderStep("prov-step0");
          loadSavedKeys(true);
          return;
        }
        showProviderStep("prov-step1");
      } else if (document.getElementById("prov-step1").style.display === "block") {
        showProviderStep("prov-step0");
        loadSavedKeys(true);
      }
    }

    function closeProvider() {
      const overlay = document.getElementById("provider-overlay");
      overlay.style.opacity = "0";
      overlay.style.pointerEvents = "none";
      _selProv = null;
    }

    async function confirmProvider() {
      const key = document.getElementById("prov-key-input").value.trim();
      if (!key) { toast("⚠️ " + (I18N[_currentLang]?.["providers.key_required"] || "Insira a API key."), "err"); return; }
      if (!_selProv) { toast("⚠️ " + (I18N[_currentLang]?.["providers.select_required"] || "Selecione um provedor."), "err"); return; }
      // HOTFIX v0.5.1.3+ — guardar refs em variáveis locais ANTES de fechar overlay
      const provId = _selProv.id;
      const provEnv = _selProv.env;
      const provName = _selProv.name;
      const isEdit = !!_selProv._edit;
      toast("💾 " + (I18N[_currentLang]?.["providers.saving"] || "Salvando…"), "info");
      try {
        const r = await fetch(BASE + "/api/apikey", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: provId, env: provEnv, apikey: key })
        });
        const d = await r.json().catch(() => ({}));
        if (r.ok && (d.ok !== false)) {
          // Aplica chaves no ambiente e recarrega ttyd para usar a nova key
          try {
            await fetch(BASE + "/api/apikey/apply", { method: "POST" });
            reloadTerminalFrame();
          } catch(_){}
          toast(`✅ ${provName} ${isEdit ? (I18N[_currentLang]?.["providers.updated"] || "atualizado") : (I18N[_currentLang]?.["providers.connected"] || "conectado")}!`, "ok");
          closeProvider();
          // Atualiza a lista de chaves salvas se estiver visível
          _savedKeys = {};
          setTimeout(() => loadSavedKeys(true).catch(()=>{}), 350);
        } else {
          toast("❌ " + (d.error || `Erro HTTP ${r.status}`), "err");
        }
      } catch(e) {
        toast("❌ " + e.message, "err");
      }
    }

    // Recarrega o iframe do ttyd (usado após salvar key/trocar tema/restaurar sessão)
    async function reloadTerminalFrame() {
      const fr = document.getElementById("terminal-frame");
      if (!fr) return;
      const theme = document.documentElement.getAttribute("data-theme") || "pesquisai";
      // v0.6.5: fonte da verdade agora é data-terminal-url (src pode ser
      // about:blank enquanto o splash aguarda /api/ttyd_ready).
      let origSrc = "";
      try { origSrc = (fr.dataset && fr.dataset.terminalUrl) || ""; } catch (e) {}
      if (!origSrc && fr.src && fr.src.indexOf("about:") !== 0) origSrc = fr.src;
      origSrc = (origSrc || "{__TERMINAL_URL__}").split("?")[0];
      if (!origSrc || origSrc === "about:blank") return;
      fr.src = "about:blank";
      // Uma nova sessão pode ter sido criada — invalida cache de histórico.
      _sessionsCache = { data: null, ts: 0 };
      // v0.6.5: reconecta somente com a porta respondendo (evita erro do
      // Chrome dentro do iframe); se morto, delega ao boot com splash.
      const quick = await waitTerminalReady(3000);
      if (!quick) { bootTerminal(25000); return; }
      fr.src = origSrc + "?theme=" + theme + "&t=" + Date.now();
    }

    // ── Gestão de chaves salvas ─────────────────────────────────
    let _savedKeys = {};

    async function loadSavedKeys(force) {
      const listEl = document.getElementById("prov-saved-list");
      if (!listEl) return;
      if (!force && Object.keys(_savedKeys).length) {
        renderSavedKeys();
        return;
      }
      listEl.innerHTML = '<div style="font-size:11px;color:var(--ink-muted);padding:8px 0;">' + (I18N[_currentLang]?.["ui.loading"] || "Carregando…") + '</div>';
      try {
        const r = await fetch(BASE + "/api/apikey");
        const d = await r.json();
        _savedKeys = d.keys || {};
        renderSavedKeys();
      } catch(e) {
        listEl.innerHTML = '<div style="font-size:11px;color:var(--red);padding:8px 0;">❌ ' + e.message + '</div>';
      }
    }

    function renderSavedKeys() {
      const listEl = document.getElementById("prov-saved-list");
      if (!listEl) return;
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const keys = Object.keys(_savedKeys).filter(k => !k.startsWith("_env_"));
      if (!keys.length) {
        listEl.innerHTML = '<div style="font-size:11px;color:var(--ink-muted);padding:8px 0;text-align:center;">' + (dict["providers.no_saved_keys"] || "Nenhuma chave salva ainda.") + '</div>';
        return;
      }
      let html = '<div style="display:flex;flex-direction:column;gap:6px;">';
      for (const provider of keys) {
        const p = PROVIDERS.find(x => x.id === provider);
        const name = p ? p.name : provider;
        const masked = _savedKeys[provider] || "••••";
        html += '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:var(--radius);">';
        html += '<div style="min-width:0;">';
        html += '<div style="font-size:12px;font-weight:500;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(name) + '</div>';
        html += '<div style="font-size:10px;color:var(--ink-muted);font-family:var(--font-mono);">' + escapeHtml(masked) + '</div>';
        html += '</div>';
        html += '<div style="display:flex;gap:6px;flex-shrink:0;">';
        // 🐛 CORREÇÃO v0.5.1.8: usa data-provider + escapa com escapeHtml()
        // para evitar conflito entre JSON.stringify (que adiciona "") e as aspas
        // do onclick. O bug anterior quebrava o HTML gerando SyntaxError:
        // "Uncaught SyntaxError: Unexpected end of input (at (index):1:16)"
        html += '<button data-provider="' + escapeHtml(provider) + '" onclick="editSavedKey(this.dataset.provider)" title="' + (dict["providers.edit"] || "Editar") + '" style="padding:5px 10px;font-size:11px;background:var(--accent-dim);color:var(--accent);border:1px solid rgba(var(--accent-rgb),.25);border-radius:4px;cursor:pointer;">' + (dict["providers.edit"] || "Editar") + '</button>';
        html += '<button data-provider="' + escapeHtml(provider) + '" onclick="deleteSavedKey(this.dataset.provider)" title="' + (dict["providers.delete"] || "Excluir") + '" style="padding:5px 10px;font-size:11px;background:var(--red-dim);color:var(--red);border:1px solid rgba(198,40,40,.25);border-radius:4px;cursor:pointer;">' + (dict["providers.delete"] || "Excluir") + '</button>';
        html += '</div>';
        html += '</div>';
      }
      html += '</div>';
      listEl.innerHTML = html;
    }

    function editSavedKey(provider) {
      let p = PROVIDERS.find(x => x.id === provider);
      if (!p) {
        // Fallback para providers customizados/antigos ainda salvos no Drive.
        const savedEnv = _savedKeys["_env_" + provider] || "";
        p = { id: provider, name: provider, env: savedEnv, hint: "Cole sua key aqui…" };
      }
      _selProv = { ...p, _edit: true };
      document.getElementById("prov-name-title").textContent = p.name;
      document.getElementById("prov-env-code").textContent = p.env || (provider.toUpperCase() + "_API_KEY");
      document.getElementById("prov-key-input").placeholder = p.hint || "Cole sua key aqui…";
      document.getElementById("prov-key-input").value = "";
      document.getElementById("prov-step0").style.display = "none";
      document.getElementById("prov-step1").style.display = "none";
      document.getElementById("prov-step2").style.display = "block";
      setTimeout(() => document.getElementById("prov-key-input").focus(), 80);
    }

    async function deleteSavedKey(provider) {
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const p = PROVIDERS.find(x => x.id === provider);
      const name = p ? p.name : provider;
      pesquisaiConfirm((dict["providers.confirm_delete"] || "Excluir chave de") + " " + name + "?", async function() {
        try {
          const r = await fetch(BASE + "/api/apikey", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: provider, action: "delete" })
          });
          const d = await r.json().catch(() => ({}));
          if (r.ok && (d.ok !== false)) {
            // Invalida cache local e recarrega do servidor para refletir estado real.
            _savedKeys = {};
            renderSavedKeys();
            await loadSavedKeys(true);
            toast("🗑 " + name + " " + (dict["providers.deleted"] || "excluído"), "ok");
          } else {
            toast("❌ " + (d.error || "Erro"), "err");
          }
        } catch(e) {
          toast("❌ " + e.message, "err");
        }
      });
    }

    // ── Cache compartilhado (5s) ──────────────────────────────────
    let _healthCache = { data: null, ts: 0 };
    let _sessionsCache = { data: null, ts: 0 };
    const CACHE_TTL = 5000;

    // ── Dashboard de Saude ───────────────────────────────────────
    async function openHealth() {
      const overlay = document.getElementById("health-overlay");
      overlay.style.opacity = "1"; overlay.style.pointerEvents = "all";
      await loadHealth();
    }
    function closeHealth() {
      const o = document.getElementById("health-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }

    async function loadHealth(force) {
      const listEl = document.getElementById("health-list");
      if (!listEl) return;
      const now = Date.now();
      if (!force && _healthCache.data && (now - _healthCache.ts) < CACHE_TTL) {
        renderHealth(listEl, _healthCache.data);
        return;
      }
      listEl.innerHTML = '<div class="modal-empty" data-i18n="ui.loading">Carregando diagnóstico…</div>';
      try {
        const r = await fetch(BASE + "/api/health");
        const d = await r.json();
        if (d.ok && d.checks) {
          _healthCache = { data: d, ts: Date.now() };
          renderHealth(listEl, d);
        } else {
          listEl.innerHTML = '<div class="modal-empty">❌ Erro ao carregar diagnóstico.</div>';
        }
      } catch (e) {
        listEl.innerHTML = '<div class="modal-empty">❌ ' + e.message + '</div>';
      }
    }

    function renderHealth(listEl, d) {
      var c = d.checks;
      var h = '<div style="padding:6px 0;">';
      h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">';
      h += '<span style="font-size:11px;color:var(--ink-muted);">v' + (d.version || '?') + '</span>';
      h += '<button onclick="loadHealth(true)" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:10px;color:var(--accent);cursor:pointer;">↻ Atualizar</button>';
      h += '</div>';
      var checks = [
        { k: "drive_mounted", l: "Google Drive montado" },
        { k: "backup_dir_exists", l: "Diretório de backup" },
        { k: "ttyd_alive", l: "Terminal ttyd ativo" },
        { k: "opencode_found", l: "OpenCode encontrado" },
        { k: "keys_loaded_count", l: "Chaves carregadas (" + (c.keys_loaded_count||0) + ")" },
        { k: "ffmpeg_ok", l: "FFmpeg disponível" },
        { k: "skills_count", l: "Skills instaladas (" + (c.skills_count||0) + ")" }
      ];
      for (var i = 0; i < checks.length; i++) {
        var ok = c[checks[i].k];
        var color = ok ? 'var(--accent)' : '#ff6b6b';
        var svg = ok
          ? '<svg viewBox="0 0 16 16" style="width:14px;height:14px;display:block;"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M5 8l2 2 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
          : '<svg viewBox="0 0 16 16" style="width:14px;height:14px;display:block;"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 6l4 4M10 6l-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
        h += '<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-bottom:1px solid var(--line);font-size:12px;">';
        h += '<span style="color:' + color + ';">' + svg + '</span>';
        h += '<span style="flex:1;">' + checks[i].l + '</span>';
        if (checks[i].k === 'keys_loaded_count' && c.keys_loaded && c.keys_loaded.length) {
          h += '<span style="font-size:10px;color:var(--ink-muted);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + c.keys_loaded.join(', ') + '</span>';
        }
        h += '</div>';
      }
      // disco
      var diskPct = c.disk_total_mb > 0 ? Math.round(c.disk_free_mb / c.disk_total_mb * 100) : 0;
      var diskColor = diskPct < 10 ? '#ff6b6b' : diskPct < 25 ? '#ffd93d' : 'var(--accent)';
      h += '<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;font-size:12px;">';
      h += '<span style="color:' + diskColor + ';">💾</span>';
      h += '<span style="flex:1;">Disco livre: ' + (c.disk_free_mb||'?') + ' MB / ' + (c.disk_total_mb||'?') + ' MB (' + diskPct + '%)</span>';
      h += '</div>';
      h += '</div>';
      listEl.innerHTML = h;
    }

    // ── Historico de Sessoes ─────────────────────────────────────
    let _allSessions = [];
    let _filteredSessions = [];
    let _sessionsPage = 0;
    let _sessionsPollId = null;
    const SESSIONS_PAGE_SIZE = 20;
    const SESSIONS_POLL_MS = 8000;  // atualiza a cada 8s enquanto modal aberto

    function _startSessionsPoll() {
      _stopSessionsPoll();
      _sessionsPollId = setInterval(() => {
        const o = document.getElementById("sessions-overlay");
        if (o && o.style.opacity === "1") {
          loadSessions(true).catch(() => {});
        } else {
          _stopSessionsPoll();
        }
      }, SESSIONS_POLL_MS);
    }
    function _stopSessionsPoll() {
      if (_sessionsPollId) { clearInterval(_sessionsPollId); _sessionsPollId = null; }
    }

    async function openSessions() {
      const overlay = document.getElementById("sessions-overlay");
      overlay.style.opacity = "1"; overlay.style.pointerEvents = "all";
      // Força recarregamento para sempre mostrar a sessão mais recente
      await loadSessions(true);
      _startSessionsPoll();
    }
    function closeSessions() {
      const o = document.getElementById("sessions-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
      _stopSessionsPoll();
    }

    async function loadSessions(force) {
      const listEl = document.getElementById("session-list");
      if (!listEl) return;
      const now = Date.now();
      if (!force && _sessionsCache.data && (now - _sessionsCache.ts) < CACHE_TTL) {
        _allSessions = _sessionsCache.data;
        _filteredSessions = _allSessions;
        _sessionsPage = 0;
        renderSessions(listEl);
        return;
      }
      listEl.innerHTML = '<div class="modal-empty" data-i18n="ui.loading">Carregando sessões…</div>';
      try {
        const r = await fetch(BASE + "/api/sessions");
        const d = await r.json();
        if (d && d.sessions) {
          _sessionsCache = { data: d.sessions, ts: Date.now() };
          _allSessions = d.sessions;
          _filteredSessions = d.sessions;
          _sessionsPage = 0;
          renderSessions(listEl);
        } else {
          listEl.innerHTML = '<div class="modal-empty" data-i18n="sessions.empty">Nenhuma sessão encontrada.</div>';
        }
      } catch (e) {
        listEl.innerHTML = '<div class="modal-empty">❌ ' + e.message + '</div>';
      }
    }

    function renderSessions(listEl) {
      var start = 0;
      var end = (_sessionsPage + 1) * SESSIONS_PAGE_SIZE;
      var items = _filteredSessions.slice(start, end);
      if (!items.length) {
        listEl.innerHTML = '<div class="modal-empty" data-i18n="sessions.empty_filtered">Nenhuma sessão corresponde ao filtro.</div>';
        return;
      }
      var h = '<div style="padding:4px 0;">';
      for (var i = 0; i < items.length; i++) {
        var s = items[i];
        var id = s.id || '';
        var title = s.title || s.name || id;
        var date = s.date || s.created || '';
        h += '<div class="session-item" data-session-id="' + id.replace(/"/g,'&quot;') + '" onclick="restoreSession(this.dataset.sessionId)" style="padding:7px 10px;border-bottom:1px solid var(--line);cursor:pointer;transition:background .12s;font-size:12px;">';
        h += '<div style="font-weight:500;">' + escapeHtml(title) + '</div>';
        if (date) h += '<div style="font-size:10px;color:var(--ink-muted);margin-top:2px;">' + escapeHtml(date) + '</div>';
        h += '<div style="font-size:10px;color:var(--ink-muted);opacity:.6;">' + escapeHtml(id) + '</div>';
        h += '</div>';
      }
      h += '</div>';
      if (end < _filteredSessions.length) {
        h += '<button onclick="loadMoreSessions()" style="width:100%;padding:8px;background:none;border:1px solid var(--line);border-radius:var(--radius);color:var(--accent);font-size:11px;cursor:pointer;margin-top:4px;">Ver mais (' + (_filteredSessions.length - end) + ' restantes)</button>';
      }
      listEl.innerHTML = h;
    }

    function loadMoreSessions() {
      _sessionsPage++;
      var listEl = document.getElementById("session-list");
      if (listEl) renderSessions(listEl);
    }

    function filterSessions() {
      var q = (document.getElementById("session-search").value || "").toLowerCase().trim();
      if (!q) {
        _filteredSessions = _allSessions;
      } else {
        _filteredSessions = _allSessions.filter(function(s) {
          var str = (s.id || "") + " " + (s.title || "") + " " + (s.name || "") + " " + (s.date || "") + " " + (s.created || "");
          return str.toLowerCase().indexOf(q) !== -1;
        });
      }
      _sessionsPage = 0;
      var listEl = document.getElementById("session-list");
      if (listEl) renderSessions(listEl);
    }

    async function restoreSession(sessionId) {
      if (!sessionId) return;
      var _confirmed = false;
      pesquisaiConfirm("Restaurar sessão " + sessionId + "?", function() {
        if (_confirmed) return; _confirmed = true;
        _doRestoreSession(sessionId);
      });
    }
    async function _doRestoreSession(sessionId) {
      try {
        var listEl = document.getElementById("session-list");
        if (listEl) listEl.innerHTML = '<div class="modal-empty">Restaurando sessão…</div>';
        // 🐛 CORREÇÃO v0.5.1.8: NÃO usa "opencode session restore <id>"
        // (que restaura dados mas depois inicia opencode do zero — linha 1600 do launch_app.py).
        // Em vez disso, usa "opencode -s <id>" com no_fallback=true para iniciar o opencode
        // diretamente na sessão desejada, mesmo padrão do /api/restore (doRestore()).
        // v0.6.5: splash imediato — o backend só responde quando a porta do
        // terminal novo já aceita conexões (ou erro).
        showBootSplash((I18N[_currentLang] || I18N["pt_BR"])["boot.restoring"] ||
                       "Restaurando sessão…");
        closeSessions();
        const r = await fetch(BASE + "/api/run_terminal", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({cmd: "opencode -s " + sessionId, no_fallback: true})
        });
        const d = await r.json();
        if (r.ok) {
          // v0.7.2: um restore feito pelo menu tambem conta como
          // "retomada ja oferecida" — senao a pergunta de retomada
          // reapareceria depois do reload (virando loop).
          markAutosaveResumeOffered();
          // Invalida cache para que a próxima abertura mostre a sessão atual
          _sessionsCache = { data: null, ts: 0 };
          toast("✅ Sessão " + sessionId + " restaurada! Recarregando página…", "ok");
          // Splash permanece cobrindo a tela; reload reconecta ao terminal pronto.
          setTimeout(() => location.reload(), 600);
        } else {
          hideBootSplash();
          toast("❌ Erro ao restaurar: " + (d.error || r.status), "err");
          loadSessions(true);
        }
      } catch(e) {
        hideBootSplash();
        toast("❌ " + e.message, "err");
        loadSessions(true);
      }
    }

    function openShortcuts() {
      const o = document.getElementById("shortcuts-overlay");
      o.style.opacity = "1"; o.style.pointerEvents = "all";
    }
    function closeShortcuts() {
      const o = document.getElementById("shortcuts-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }

    // ── Painel Admin de Telemetria (v0.6.4) ─────────────────────
    function openTelemetry() {
      // v0.6.8: painel invisível ao usuário comum - só abre para admin
      // Admin pode abrir via: URL ?admin=1, ou localStorage.setItem('ufvai_admin','1'), ou Ctrl+Shift+Alt+T
      const isAdmin = new URLSearchParams(window.location.search).has('admin') || localStorage.getItem('ufvai_admin') === '1';
      if (!isAdmin) {
        // Silenciosamente ignora para usuário comum - telemetria continua via opt-in dos Termos
        console.debug('Telemetria: painel restrito ao admin');
        return;
      }
      const o = document.getElementById("telemetry-overlay");
      o.style.opacity = "1"; o.style.pointerEvents = "all";
      fetch(BASE + "/api/admin/telemetry").then(r=>r.json()).then(s=>{
        const st = document.getElementById("tel-status");
        if(!s.configured){
          st.innerHTML = "<span style='color:var(--amber)'>● Não configurada</span> — preencha os campos abaixo para ativar a coleta.";
        } else if(s.enabled){
          st.innerHTML = "<span style='color:var(--green)'>● Ativa</span> · ID <code>" + s.measurement_id + "</code> (" + s.source + ") · consentimento do usuário: " + (s.consent_analytics ? "sim" : "aguardando opt-in");
        } else {
          let why = [];
          if(s.kill_switch) why.push("kill-switch UFVAI_TELEMETRY=0");
          if(!s.consent_accepted) why.push("Termos não aceitos");
          else if(!s.consent_analytics) why.push("usuário não autorizou estatísticas");
          st.innerHTML = "<span style='color:var(--red)'>● Inativa</span> · ID <code>" + s.measurement_id + "</code> · motivo: " + why.join("; ");
        }
        // v0.6.7: canal de contato — prefill da URL salva + status
        const cIn = document.getElementById("tel-contact");
        if(cIn && typeof s.contact_endpoint_url === "string") cIn.value = s.contact_endpoint_url;
        const cs = document.getElementById("tel-contact-status");
        if(cs){
          const src = s.contact_endpoint_source === "env" ? "variável de ambiente" :
                      (s.contact_endpoint_set ? "salva no painel" : "");
          cs.innerHTML = (s.contact_endpoint_set ? "✉️ Canal de contato <b>ativo</b> ("+src+"). "
                        : "✉️ Canal de contato inativo — vazio = usuários NÃO são encaminhados (só contador anônimo no GA4). ") +
                        "Canal recomendado (Google, grátis): Planilha + <b>Apps Script</b> — TELEMETRY.md §Passo 9.";
        }
      }).catch(()=>{ document.getElementById("tel-status").textContent = "Falha ao consultar estado."; });
    }
    function closeTelemetry() {
      const o = document.getElementById("telemetry-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }
    // Atalho secreto admin: Ctrl+Shift+Alt+T libera painel de telemetria
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey && e.altKey && e.key.toLowerCase() === 't') {
        localStorage.setItem('ufvai_admin', '1');
        openTelemetry();
      }
    });

    async function saveTelemetry() {
      const mid = document.getElementById("tel-mid").value.trim();
      const sec = document.getElementById("tel-secret").value.trim();
      const contact = document.getElementById("tel-contact").value.trim(); // v0.6.7
      const msg = document.getElementById("tel-msg");
      msg.style.display = "block";
      msg.textContent = "Salvando…"; msg.style.color = "var(--ink-muted)";
      try{
        const r = await fetch(BASE + "/api/admin/telemetry", {method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({measurement_id:mid, api_secret:sec, contact_endpoint:contact})});
        const j = await r.json();
        msg.textContent = j.message || (j.ok ? "Salvo." : "Erro.");
        msg.style.color = j.ok ? "var(--green)" : "var(--red)";
        if(j.ok && j.state){ document.getElementById("tel-secret").value=""; openTelemetry(); }
      }catch(e){ msg.textContent = "Falha de rede."; msg.style.color = "var(--red)"; }
    }

    // ── Diretrizes do Agente (HOTFIX v0.5.1.2) ──────────────────
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

      const langShort = (_currentLang || "pt_BR").replace("_", "-");
      if (badgeEl) badgeEl.textContent = langShort;
      if (sourceEl) {
        const code = (_currentLang || "pt_BR").split("_")[0];
        // pt-BR canônico vive na RAIZ (AGENTS.md), espelhado em
        // agents/AGENTS.pt.md — "Ver fonte" aponta para a raiz.
        sourceEl.href = code === "pt"
          ? "https://github.com/gustavobraga-byte/PesquisAI/blob/main/AGENTS.md"
          : "https://github.com/gustavobraga-byte/PesquisAI/blob/main/agents/AGENTS." + code + ".md";
      }

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
    function renderAgentsContent(el, mdText) {
      try {
        if (typeof marked !== "undefined") {
          marked.setOptions({ breaks: true, gfm: true, headerIds: true });
          const _b = String.fromCharCode(92);
          const _re = new RegExp(
            "^---" + _b + "s*" + _b + "n[" + _b + "s" + _b + "S]*?" +
            _b + "n---" + _b + "s*" + _b + "n"
          );
          const cleaned = mdText.replace(_re, "");
          el.innerHTML = marked.parse(cleaned);
        } else {
          el.textContent = mdText;
        }
      } catch (e) {
        console.error("Erro ao renderizar markdown:", e);
      }
    }

    // ── v0.6.9: Manual do UFVAI (botão 📘 ao lado do Dashboard de Saúde) ──
    let _manualCache = null;

    async function openManual() {
      const overlay = document.getElementById("manual-overlay");
      if (overlay) {
        overlay.style.opacity = "1";
        overlay.style.pointerEvents = "all";
      }
      await loadManual();
    }

    function closeManual() {
      const overlay = document.getElementById("manual-overlay");
      if (overlay) {
        overlay.style.opacity = "0";
        overlay.style.pointerEvents = "none";
      }
    }

    function reloadManual() {
      _manualCache = null;
      loadManual();
    }

    async function loadManual(forceReload = false) {
      const contentEl = document.getElementById("manual-content");
      if (!contentEl) return;
      if (!forceReload && _manualCache) {
        renderAgentsContent(contentEl, _manualCache);
        return;
      }
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      contentEl.textContent = dict["manual.loading"] || "Carregando manual…";
      try {
        const r = await fetch(BASE + "/api/manual");
        const d = await r.json();
        if (d.ok && d.content) {
          _manualCache = d.content;
          renderAgentsContent(contentEl, d.content);
        } else {
          // v0.6.9: fallback — abre o manual no GitHub
          const gh = d.github || "https://github.com/gustavobraga-byte/PesquisAI/blob/main/MANUAL.md";
          contentEl.innerHTML = (dict["manual.error"] || "Manual não encontrado localmente.")
            + ' <a href="' + gh + '" target="_blank" style="color:var(--gold,#b8912f)">'
            + (dict["manual.open_source"] || "Abrir no GitHub") + " ↗</a>";
        }
      } catch (e) {
        contentEl.textContent = (dict["manual.error"] || "Erro") + " — " + e.message;
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

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, c => {
        if (c === "&") return "&amp;";
        if (c === "<") return "&lt;";
        if (c === ">") return "&gt;";
        if (c === '"') return "&quot;";
        if (c === "'") return "&#39;";
        return c;
      });
    }

    // ── Memória UFVAI (v0.5.1.4 — navegar + editar) ────────
    // Estado:
    //   _memoryTree      — lista plana de notas carregada do /api/obsidian/tree
    //   _memoryStatus    — {status, root, writable, notes_count, ...}
    //   _memoryCurrent   — {path, body, title, tags, is_pesquisai, ...} da nota aberta
    //   _memoryDirty     — true se o editor tem mudanças não salvas
    //   _memorySearch    — termo de busca atual (filtro da sidebar)
    //   _memoryTab       — 'edit' | 'preview' | 'split'
    // v0.5.1.8: cache de 5s para evitar refetch em aberturas repetidas
    let _memoryCache = { tree: null, status: null, ts: 0 };
    let _memoryTree = [];
    let _memoryStatus = null;
    let _memoryCurrent = null;
    let _memoryDirty = false;
    let _memorySearch = "";
    let _memoryTab = "preview";
    // v0.5.1.9: navegação por pastas + calendário
    let _memoryCurrentFolder = null;     // null = lista de pastas, "daily/" = calendário, etc
    let _memoryCalendarDate = new Date(); // mês atual do calendário
    let _memoryCalendarDailies = [];     // paths das daily notes existentes

    async function openMemory(force) {
      const overlay = document.getElementById("memory-overlay");
      if (overlay) {
        overlay.style.opacity = "1";
        overlay.style.pointerEvents = "all";
      }
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const list = document.getElementById("memory-list");
      // v0.5.1.9: reseta para lista de pastas ao abrir
      _memoryCurrentFolder = null;
      _memoryCalendarDate = new Date();
      if (list) {
        list.innerHTML = '<div class="modal-empty" style="padding:14px;">' +
          (dict["ui.loading"] || "Carregando…") + '</div>';
      }
      // v0.6.17: cache de 120s + stale-while-revalidate — abertura instantânea
      // (render imediato do cache; se >30s, revalida em background sem bloquear)
      const now = Date.now();
      if (!force && _memoryCache.tree && (now - _memoryCache.ts) < 120000) {
        _memoryStatus = _memoryCache.status;
        _memoryTree = _memoryCache.tree;
        renderMemoryHeader(_memoryCache.status, dict);
        renderMemorySidebar();
        if (_memoryCache.status && _memoryCache.status.status === "ready") {
          if (!_memoryCurrent) {
            const lastDaily = findLastDaily();
            if (lastDaily) loadMemoryNote(lastDaily.path);
          }
        }
        // v0.6.17: stale-while-revalidate — cache >30s atualiza em background
        if (now - _memoryCache.ts > 30000) {
          fetch(BASE + "/api/obsidian?include=tree").then(r=>r.json()).then(d=>{
            if (d && d.ok) {
              _memoryCache = { tree: d.tree || [], status: d, ts: Date.now() };
            }
          }).catch(()=>{});
        }
        return;
      }
      try {
        // v0.5.1.8: tenta rota unificada ?include=tree (1 request ao invés de 2)
        let dStatus, dTree;
        const unifiedResp = await fetch(BASE + "/api/obsidian?include=tree");
        const unifiedData = await unifiedResp.json();
        if (unifiedData.ok && unifiedData.tree) {
          dStatus = unifiedData;
          dTree = { tree: unifiedData.tree };
        } else {
          // Fallback: 2 chamadas separadas (backend antigo)
          const [rStatus, rTree] = await Promise.all([
            fetch(BASE + "/api/obsidian"),
            fetch(BASE + "/api/obsidian/tree"),
          ]);
          dStatus = await rStatus.json();
          dTree = await rTree.json();
        }
        _memoryStatus = dStatus;
        _memoryTree = (dTree && dTree.tree) ? dTree.tree : [];
        // Atualiza cache
        _memoryCache = { tree: _memoryTree, status: dStatus, ts: Date.now() };
        renderMemoryHeader(dStatus, dict);
        renderMemorySidebar();
        if (dStatus.status !== "ready") {
          if (list) {
            list.innerHTML = '<div class="modal-empty" style="padding:14px;font-size:11.5px;">' +
              escapeHtml(dStatus.message || dStatus.status) + '</div>';
          }
        } else {
          // Abre automaticamente o último daily note se nenhuma nota estiver carregada
          if (!_memoryCurrent && !force) {
            const lastDaily = findLastDaily();
            if (lastDaily) {
              loadMemoryNote(lastDaily.path);
            }
          }
        }
      } catch (e) {
        if (list) {
          list.innerHTML = '<div class="modal-empty" style="padding:14px;">❌ ' +
            (dict["agents.error"] || "Erro") + ': ' + escapeHtml(e.message) + '</div>';
        }
      }
    }

    // ── Encontra o último daily note na árvore da memória ──────
    function findLastDaily() {
      const dailies = [];
      for (const folder of _memoryTree) {
        for (const n of folder.notes) {
          if (n.path && n.path.startsWith("daily/")) {
            dailies.push(n);
          }
        }
      }
      dailies.sort((a, b) => b.path.localeCompare(a.path));
      return dailies.length > 0 ? dailies[0] : null;
    }

    function closeMemory(force) {
      // Se houver mudanças não salvas, pedir confirmação (a menos que force=true)
      if (!force && _memoryDirty && _memoryCurrent) {
        var _confirmed = false;
        pesquisaiConfirm("Há mudanças não salvas em '" + _memoryCurrent.path + "'.\\nFechar mesmo assim?", function() {
          if (_confirmed) return; _confirmed = true;
          _doCloseMemory();
        });
        return;
      }
      _doCloseMemory();
    }
    function _doCloseMemory() {
      const overlay = document.getElementById("memory-overlay");
      if (overlay) {
        overlay.style.opacity = "0";
        overlay.style.pointerEvents = "none";
      }
      _memoryDirty = false;
      _memoryCurrent = null;
      _memoryCurrentFolder = null; // v0.5.1.9
      markDirty();
    }

    // ── Renderização: header (status badge + drive link) ───────────
    function renderMemoryHeader(d, dict) {
      const badge   = document.getElementById("memory-status-badge");
      const driveLnk = document.getElementById("memory-open-drive");
      const memBtn  = document.getElementById("memory-btn");
      const sub     = document.getElementById("memory-subtitle");
      if (!d) return;
      const statusMap = {
        ready:          { txt: dict["memory.status_ready"]     || "Ativa",            color: "var(--green)" },
        disabled:       { txt: dict["memory.status_disabled"]  || "Desativada",       color: "var(--ink-muted)" },
        no_vault:       { txt: dict["memory.status_no_vault"]  || "Sem vault",        color: "var(--amber)" },
        read_only:      { txt: dict["memory.status_read_only"] || "Somente leitura",  color: "var(--amber)" },
        error:          { txt: dict["memory.status_error"]     || "Erro",             color: "var(--red)" },
        module_unavailable: { txt: dict["memory.status_error"] || "Módulo indisponível", color: "var(--red)" },
      };
      const st = statusMap[d.status] || { txt: d.status || "?", color: "var(--ink-muted)" };
      if (badge) {
        badge.textContent = st.txt;
        badge.style.color = st.color;
        badge.style.borderColor = st.color;
      }
      if (memBtn) {
        memBtn.style.color = (d.status === "ready") ? "var(--green)" : st.color;
      }
      if (driveLnk) {
        if (d.root && d.status === "ready") {
          driveLnk.href = "https://drive.google.com/drive/my-drive";
          driveLnk.title = d.root;
          driveLnk.style.display = "";
        } else {
          driveLnk.style.display = "none";
        }
      }
      if (sub && d.status === "ready" && d.notes_count != null) {
        sub.textContent = (dict["memory.subtitle"] || "Camada de memória persistente do agente")
          + " · " + d.notes_count + " " + (dict["memory.notes_count"] || "notas");
      }
    }

    // ── Renderização: sidebar (navegação por pastas + calendário) ──
    // v0.5.1.9: três modos:
    //   1. Busca ativa → resultados filtrados (comportamento original)
    //   2. Nenhuma pasta → lista de pastas (primeiro nível)
    //   3. Pasta selecionada → calendário (daily/) ou lista de notas
    function renderMemorySidebar() {
      const list = document.getElementById("memory-list");
      const cnt  = document.getElementById("memory-count");
      if (!list) return;
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const q = (_memorySearch || "").toLowerCase().trim();

      // 1) Modo busca: exibe resultados filtrados (comportamento original)
      if (q) {
        const filtered = [];
        for (const folder of _memoryTree) {
          const matches = [];
          for (const n of folder.notes) {
            if ((n.title || "").toLowerCase().includes(q) ||
                (n.path || "").toLowerCase().includes(q) ||
                (n.tags || []).some(t => (t || "").toLowerCase().includes(q))) {
              matches.push(n);
            }
          }
          if (matches.length) filtered.push({ folder: folder.folder, notes: matches });
        }
        const total = filtered.reduce((s, f) => s + f.notes.length, 0);
        if (cnt) {
          if (total > _memorySearchLimit) cnt.textContent = Math.min(total, _memorySearchLimit) + " de " + total + " " + (dict["memory.notes_count"] || "notas") + " · paginado";
          else cnt.textContent = total + " " + (dict["memory.notes_count"] || "notas");
        }
        if (total === 0) {
          list.innerHTML = '<div class="modal-empty" style="padding:14px;font-size:11.5px;">' +
            (dict["memory.no_results"] || "Nenhum resultado para '" + escapeHtml(q) + "'.") + '</div>';
          return;
        }
        let html = "";
        let _shown = 0;
        for (const folder of filtered) {
          if (_shown >= _memorySearchLimit) break;
          const label = folder.folder || "📁 (raiz)";
          html += '<div class="mem-folder-label">' + escapeHtml(label) + ' (' + folder.notes.length + ')</div>';
          for (const n of folder.notes) {
            if (_shown >= _memorySearchLimit) break;
            _shown++;
            const active = (_memoryCurrent && _memoryCurrent.path === n.path) ? " active" : "";
            const human  = n.is_pesquisai_generated ? "" : " human";
            const tagHtml = (n.tags || []).slice(0, 3).map(t =>
              '<span style="display:inline-block;font-size:9px;padding:0 4px;background:var(--accent-dim);color:var(--accent);border-radius:2px;margin-right:2px;">#' + escapeHtml(String(t).replace(/^#/, "")) + '</span>'
            ).join("");
            html += '<div class="mem-note-item' + active + human + '" data-path="' + encodeURIComponent(n.path) + '" onclick="loadMemoryNote(decodeURIComponent(this.dataset.path))">' +
                 '<div class="mem-note-title">' + escapeHtml(n.title || n.path) + '</div>' +
                    '<div class="mem-note-path">' + escapeHtml(n.path) + '</div>' +
                    (tagHtml ? '<div style="margin-top:3px;">' + tagHtml + '</div>' : '') +
                    '</div>';
          }
        }
        if (total > _memorySearchLimit) {
          html += '<div style="padding:10px;text-align:center;"><button onclick="_loadMoreMemoryResults()" class="modal-close" style="width:auto;padding:6px 14px;font-size:11px;">Mostrar mais (' + (total - _memorySearchLimit) + ' restantes)</button></div>';
        }
        list.innerHTML = html;
        return;
      }

      // 2) Modo pasta selecionada: mostra conteúdo da pasta
      if (_memoryCurrentFolder) {
        renderFolderContent(_memoryCurrentFolder, list, cnt, dict);
        return;
      }

      // 3) Modo raiz: lista de pastas
      renderFolderList(list, cnt, dict);
    }

    // ── Lista de pastas (primeiro nível) ─────────────────────────
    function renderFolderList(list, cnt, dict) {
      // Agrupa e conta notas por pasta
      const folderMap = {};
      const folderIcons = {
        "daily/": "📅", "research/": "🔬", "literature/": "📚",
        "sessions/": "📜", "reference/": "📖", "methodology/": "⚙️",
        "hypothesis/": "💡", "datasource/": "🗄️", "moc/": "🗺️",
        "inbox/": "📥", "assets/": "🎨"
      };
      let totalNotes = 0;
      for (const folder of _memoryTree) {
        const f = folder.folder || "";
        if (!folderMap[f]) folderMap[f] = 0;
        folderMap[f] += folder.notes.length;
        totalNotes += folder.notes.length;
      }
      if (cnt) cnt.textContent = totalNotes + " " + (dict["memory.notes_count"] || "notas");
      let html = '<div style="padding:6px 0;">';
      // Ordem: daily sempre primeiro, depois alfabético
      const ordered = Object.keys(folderMap).sort((a, b) => {
        if (a === "daily/") return -1;
        if (b === "daily/") return 1;
        return a.localeCompare(b);
      });
      for (const f of ordered) {
        const icon = folderIcons[f] || "📁";
        const label = f ? f.replace(/\\/$/, "") : "(raiz)";
        const count = folderMap[f];
        const isDaily = f === "daily/";
        html += '<div class="mem-folder-card" data-folder="' + encodeURIComponent(f) + '" onclick="navigateToFolder(decodeURIComponent(this.dataset.folder))" style="padding:9px 12px;border-bottom:1px solid var(--line);cursor:pointer;transition:background .12s;display:flex;align-items:center;gap:10px;">';
        html += '<span style="font-size:16px;">' + icon + '</span>';
        html += '<div style="flex:1;min-width:0;">';
        html += '<div style="font-size:12px;font-weight:500;">' + escapeHtml(label) + '</div>';
        html += '<div style="font-size:10px;color:var(--ink-muted);">' + count + ' nota' + (count !== 1 ? 's' : '') + '</div>';
        html += '</div>';
        html += '<span style="color:var(--ink-muted);font-size:10px;">→</span>';
        html += '</div>';
      }
      html += '</div>';
      list.innerHTML = html;
    }

    // ── Conteúdo de uma pasta ────────────────────────────────────
    function renderFolderContent(folderName, list, cnt, dict) {
      // Encontra as notas da pasta
      const notes = [];
      for (const folder of _memoryTree) {
        if (folder.folder === folderName) {
          for (const n of folder.notes) notes.push(n);
        }
      }
      if (cnt) cnt.textContent = notes.length + " " + (dict["memory.notes_count"] || "notas");

      // Botão voltar
      let html = '<div style="padding:6px 8px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:6px;">';
      html += '<button onclick="navigateBack()" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:10px;color:var(--accent);cursor:pointer;">← ' + (dict["memory.back"] || "Voltar") + '</button>';
      const iconMap = {
        "daily/": "📅", "research/": "🔬", "literature/": "📚",
        "sessions/": "📜", "reference/": "📖", "methodology/": "⚙️",
        "hypothesis/": "💡", "datasource/": "🗄️", "moc/": "🗺️",
        "inbox/": "📥", "assets/": "🎨"
      };
      html += '<span style="font-size:12px;font-weight:500;color:var(--ink-muted);">' + (iconMap[folderName] || "📁") + ' ' + escapeHtml(folderName.replace(/\\/$/, "")) + '</span>';
      html += '</div>';

      if (folderName === "daily/") {
        // Calendário para daily notes
        html += renderCalendar();
      } else {
        // Lista de notas para demais pastas
        if (notes.length === 0) {
          html += '<div class="modal-empty" style="padding:14px;font-size:11.5px;">' + (dict["memory.no_notes"] || "Nenhuma nota ainda.") + '</div>';
        } else {
          html += '<div style="padding:4px 0;">';
          for (const n of notes) {
            const active = (_memoryCurrent && _memoryCurrent.path === n.path) ? " active" : "";
            const human  = n.is_pesquisai_generated ? "" : " human";
            const tagHtml = (n.tags || []).slice(0, 3).map(t =>
              '<span style="display:inline-block;font-size:9px;padding:0 4px;background:var(--accent-dim);color:var(--accent);border-radius:2px;margin-right:2px;">#' + escapeHtml(String(t).replace(/^#/, "")) + '</span>'
            ).join("");
            html += '<div class="mem-note-item' + active + human + '" data-path="' + encodeURIComponent(n.path) + '" onclick="loadMemoryNote(decodeURIComponent(this.dataset.path))">' +
                 '<div class="mem-note-title">' + escapeHtml(n.title || n.path) + '</div>' +
                    '<div class="mem-note-path">' + escapeHtml(n.path) + '</div>' +
                    (tagHtml ? '<div style="margin-top:3px;">' + tagHtml + '</div>' : '') +
                    '</div>';
          }
          html += '</div>';
        }
      }
      list.innerHTML = html;
    }

    // ── Calendário de Daily Notes ────────────────────────────────
    function renderCalendar() {
      // Extrai paths das daily notes existentes
      _memoryCalendarDailies = [];
      for (const folder of _memoryTree) {
        if (folder.folder === "daily/") {
          for (const n of folder.notes) {
            if (n.path) _memoryCalendarDailies.push(n.path);
          }
        }
      }
      const date = _memoryCalendarDate;
      const year = date.getFullYear();
      const month = date.getMonth(); // 0-based
      const today = new Date();
      const todayStr = today.getFullYear() + "-" + String(today.getMonth()+1).padStart(2,"0") + "-" + String(today.getDate()).padStart(2,"0");

      // Primeiro dia do mês (0=domingo..6=sábado)
      const firstDay = new Date(year, month, 1).getDay();
      const daysInMonth = new Date(year, month + 1, 0).getDate();

      // Mês e ano por extenso
      const monthNames = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                          "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];
      const weekDays = ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"];

      let h = '<div style="padding:8px;">';
      // Header: navegação entre meses
      h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">';
      h += '<button onclick="prevMonth()" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:11px;color:var(--accent);cursor:pointer;">◀</button>';
      h += '<span style="font-size:13px;font-weight:600;">' + monthNames[month] + ' ' + year + '</span>';
      h += '<button onclick="nextMonth()" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:11px;color:var(--accent);cursor:pointer;">▶</button>';
      h += '</div>';
      // Grid: dias da semana
      h += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;font-size:10px;color:var(--ink-muted);margin-bottom:4px;">';
      for (let w = 0; w < 7; w++) {
        h += '<div style="padding:4px 0;">' + weekDays[w] + '</div>';
      }
      h += '</div>';
      // Grid: dias do mês
      h += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;">';
      // Células vazias antes do primeiro dia
      for (let i = 0; i < firstDay; i++) {
        h += '<div style="padding:6px 0;"></div>';
      }
      for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = year + "-" + String(month+1).padStart(2,"0") + "-" + String(d).padStart(2,"0");
        const path = "daily/" + dateStr + ".md";
        const hasNote = _memoryCalendarDailies.indexOf(path) !== -1;
        const isToday = dateStr === todayStr;
        const isSelected = _memoryCurrent && _memoryCurrent.path === path;
        let styles = "padding:6px 0;border-radius:4px;font-size:11px;cursor:pointer;transition:background .12s;position:relative;";
        if (isSelected) styles += "background:var(--accent-dim);color:var(--accent);font-weight:700;";
        else if (isToday) styles += "background:rgba(var(--accent-rgb),.12);color:var(--accent);font-weight:600;";
        else styles += "color:var(--ink);";
         h += '<div class="mem-cal-day" style="' + styles + '" onclick="loadMemoryNote(\\'' + path + '\\')">';
        h += d;
        if (hasNote) {
          h += '<div style="position:absolute;bottom:2px;left:50%;transform:translateX(-50%);width:4px;height:4px;border-radius:50%;background:var(--accent);"></div>';
        }
        h += '</div>';
      }
      h += '</div></div>';
      return h;
    }

    // ── Navegação entre pastas ───────────────────────────────────
    function navigateToFolder(folderName) {
      _memoryCurrentFolder = folderName;
      if (folderName === "daily/") {
        _memoryCalendarDate = new Date(); // volta para o mês atual
      }
      renderMemorySidebar();
    }

    function navigateBack() {
      _memoryCurrentFolder = null;
      renderMemorySidebar();
    }

    function prevMonth() {
      _memoryCalendarDate.setMonth(_memoryCalendarDate.getMonth() - 1);
      renderMemorySidebar();
    }

    function nextMonth() {
      _memoryCalendarDate.setMonth(_memoryCalendarDate.getMonth() + 1);
      renderMemorySidebar();
    }

    // ── Busca ──────────────────────────────────────────────────────
    let _searchDebounce = null;
    let _memorySearchLimit = 50; // v0.6.10: paginação para vaults grandes (evita renderizar 1000+ divs)
    function searchMemory(q) {
      if (_searchDebounce) clearTimeout(_searchDebounce);
      _searchDebounce = setTimeout(() => {
        _memorySearch = q;
        _memorySearchLimit = 50; // reseta paginação a cada nova busca
        renderMemorySidebar();
        // v0.6.10: para queries ≥3 chars, tenta BM25 server-side (ranking melhor que substring)
        if ((q||"").trim().length >= 3) {
          fetch(BASE + "/api/obsidian/search?q=" + encodeURIComponent(q) + "&limit=20")
            .then(r=>r.json()).then(d=>{
              if (d && Array.isArray(d.results) && d.results.length) {
                // renderiza resultados BM25 como lista plana (ranking já ordenado)
                const list = document.getElementById("memory-list");
                const cnt  = document.getElementById("memory-count");
                const dict = I18N[_currentLang] || I18N["pt_BR"];
                if (!list) return;
                if (cnt) cnt.textContent = d.results.length + " " + (dict["memory.notes_count"] || "notas") + " · BM25";
                let html = '<div class="mem-folder-label">🔎 BM25 — top ' + d.results.length + '</div>';
                for (const r of d.results.slice(0, 20)) {
                  const n = r.note || r;
                  const active = (_memoryCurrent && _memoryCurrent.path === n.path) ? " active" : "";
                  const tagHtml = (n.tags || []).slice(0,3).map(t=>'<span style="display:inline-block;font-size:9px;padding:0 4px;background:var(--accent-dim);color:var(--accent);border-radius:2px;margin-right:2px;">#'+escapeHtml(String(t).replace(/^#/,""))+'</span>').join("");
                  html += '<div class="mem-note-item'+active+'" data-path="'+encodeURIComponent(n.path)+'" onclick="loadMemoryNote(decodeURIComponent(this.dataset.path))">'
                       + '<div class="mem-note-title">' + escapeHtml(n.title || n.path) + '</div>'
                       + '<div class="mem-note-path">' + escapeHtml(n.path) + ' · score ' + (r.score!=null?Number(r.score).toFixed(2):"") + '</div>'
                       + (r.snippet?'<div style="font-size:10.5px;color:var(--ink-muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+escapeHtml(r.snippet)+'</div>':"")
                       + (tagHtml?'<div style="margin-top:3px;">'+tagHtml+'</div>':"")
                       + '</div>';
                }
                list.innerHTML = html;
              }
            }).catch(()=>{});
        }
      }, 200);
    }
    function _loadMoreMemoryResults(){
      _memorySearchLimit += 50;
      renderMemorySidebar();
    }

    // ── Carregar nota no editor ───────────────────────────────────
    async function loadMemoryNote(path) {
      if (_memoryDirty && _memoryCurrent && _memoryCurrent.path !== path) {
        var _confirmed = false;
        pesquisaiConfirm("Há mudanças não salvas em '" + _memoryCurrent.path + "'.\\nDescartar e abrir outra nota?", function() {
          if (_confirmed) return; _confirmed = true;
          _continueLoadMemoryNote(path);
        });
        return;
      }
      _continueLoadMemoryNote(path);
    }
    async function _continueLoadMemoryNote(path) {
      // v0.5.1.9: navega automaticamente para a pasta da nota
      const slashIdx = path.indexOf("/");
      if (slashIdx !== -1) {
        const folder = path.substring(0, slashIdx + 1);
        if (_memoryCurrentFolder !== folder) {
          _memoryCurrentFolder = folder;
        }
      }
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const meta  = document.getElementById("memory-note-meta");
      const tabs  = document.getElementById("memory-editor-tabs");
      const ed    = document.getElementById("memory-editor");
      const prev  = document.getElementById("memory-preview");
      const empty = document.getElementById("memory-editor-empty");
      const titleEl = document.getElementById("memory-note-title");
      const pathEl  = document.getElementById("memory-note-path");
      const tagsEl  = document.getElementById("memory-note-tags-display");
      const btnSave = document.getElementById("memory-btn-save");
      const btnDel  = document.getElementById("memory-btn-delete");
      // UI: loading
      if (titleEl) titleEl.value = "…";
      if (pathEl)  pathEl.textContent = path;
      if (tagsEl)  tagsEl.innerHTML = "";
      if (ed)      ed.value = (dict["ui.loading"] || "Carregando…");
      if (empty)   empty.style.display = "none";
      try {
        const r = await fetch(BASE + "/api/obsidian/note?path=" + encodeURIComponent(path));
        const d = await r.json();
        if (!r.ok || !d.ok) {
          toast("❌ " + (d.error || r.status), "err");
          ed.value = "";
          if (empty) { empty.style.display = ""; empty.textContent = d.error || "Erro ao carregar nota."; }
          return;
        }
        _memoryCurrent = {
          path: d.path,
          title: d.title,
          tags: d.tags || [],
          body: d.body || "",
          is_pesquisai: d.is_pesquisai_generated,
          metadata: d.metadata,
        };
        if (titleEl) titleEl.value = d.title || "";
        if (pathEl)  pathEl.textContent = d.path;
        if (tagsEl) {
          tagsEl.innerHTML = (d.tags || []).map(t =>
            '<span style="display:inline-block;font-size:9.5px;padding:1px 6px;background:var(--accent-dim);color:var(--accent);border-radius:3px;">#' + escapeHtml(String(t).replace(/^#/, "")) + '</span>'
          ).join("") || '<span style="font-size:9.5px;color:var(--ink-muted);">— sem tags —</span>';
        }
        if (ed) ed.value = d.body || "";
        if (meta) meta.style.display = "flex";
        if (tabs) tabs.style.display = "block";
        if (btnSave) { btnSave.disabled = false; btnSave.style.cursor = "pointer"; btnSave.style.opacity = "1"; }
        if (btnDel)  { btnDel.disabled  = false; btnDel.style.cursor  = "pointer"; btnDel.style.opacity  = "1"; }
        _memoryDirty = false;
        markDirty();
        switchMemoryTab(_memoryTab);
        renderMemorySidebar(); // atualiza o item ativo
      } catch (e) {
        toast("❌ " + e.message, "err");
      }
    }

    // ── Switch tab Edit / Preview / Split ──────────────────────────
    function switchMemoryTab(t) {
      _memoryTab = t;
      const ed   = document.getElementById("memory-editor");
      const prev = document.getElementById("memory-preview");
      const tEdit = document.getElementById("memory-tab-edit");
      const tPrev = document.getElementById("memory-tab-preview");
      const tSpl  = document.getElementById("memory-tab-split");
      [tEdit, tPrev, tSpl].forEach(b => b && b.classList.remove("active"));
      if (t === "edit")   { tEdit && tEdit.classList.add("active"); ed.style.display = "";   prev.style.display = "none"; ed.style.flex = "1"; prev.style.flex = ""; }
      if (t === "preview"){ tPrev && tPrev.classList.add("active"); ed.style.display = "none"; prev.style.display = "";   prev.style.flex = "1"; ed.style.flex = ""; renderPreview(); }
      if (t === "split")  { tSpl  && tSpl.classList.add("active");  ed.style.display = "";   prev.style.display = "";   ed.style.flex = "1"; prev.style.flex = "1"; renderPreview(); }
    }

    function renderPreview() {
      const ed = document.getElementById("memory-editor");
      const prev = document.getElementById("memory-preview");
      if (!ed || !prev) return;
      const src = ed.value || "";
      try {
        // Usa marked.js se disponível; caso contrário, escapa como <pre>
        if (typeof marked !== "undefined" && marked.parse) {
          let html = marked.parse(src);
          // Destaque de wikilinks [[nota]] e tags #tag
          html = html.replace(/\\[\\[([^\\]|#]+)(?:#[^\\]|]+)?(?:\\|([^\\]]+))?\\]\\]/g,
            (m, target, alias) => '<span class="wikilink">[[' + escapeHtml(alias || target) + ']]</span>');
          html = html.replace(/(^|[\\s(])#([a-zA-Z0-9_\\-/]+)/g,
            (m, p, t) => p + '<span class="tag">#' + escapeHtml(t) + '</span>');
          prev.innerHTML = '<div class="mem-preview">' + html + '</div>';
        } else {
          prev.innerHTML = '<pre style="white-space:pre-wrap;font-family:var(--font-mono);font-size:11.5px;">' + escapeHtml(src) + '</pre>';
        }
      } catch (e) {
        prev.innerHTML = '<pre>' + escapeHtml(src) + '</pre>';
      }
    }

    // ── Editor: input → dirty ─────────────────────────────────────
    function onEditorInput() {
      if (!_memoryDirty) { _memoryDirty = true; markDirty(); }
      if (_memoryTab === "split" || _memoryTab === "preview") renderPreview();
    }

    function markDirty() {
      const ind = document.getElementById("memory-dirty-indicator");
      const btnSave = document.getElementById("memory-btn-save");
      if (ind) ind.style.display = _memoryDirty ? "" : "none";
      if (btnSave) {
        if (_memoryDirty && _memoryCurrent) {
          btnSave.style.background = "var(--amber)";
          btnSave.style.borderColor = "var(--amber)";
          btnSave.style.color = "#000";
        } else if (_memoryCurrent) {
          btnSave.style.background = "var(--green)";
          btnSave.style.borderColor = "var(--green)";
          btnSave.style.color = "#000";
        } else {
          btnSave.style.background = "";
          btnSave.style.borderColor = "";
          btnSave.style.color = "";
        }
      }
    }

    // ── Salvar nota ───────────────────────────────────────────────
    async function saveCurrentNote() {
      if (!_memoryCurrent) { toast("⚠️ Nenhuma nota aberta.", "err"); return; }
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const ed = document.getElementById("memory-editor");
      const titleEl = document.getElementById("memory-note-title");
      const body = ed ? ed.value : "";
      const title = titleEl ? titleEl.value : _memoryCurrent.title;
      const btnSave = document.getElementById("memory-btn-save");
      if (btnSave) { btnSave.disabled = true; btnSave.textContent = "…"; }
      try {
        const r = await fetch(BASE + "/api/obsidian/note", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "save",
            path: _memoryCurrent.path,
            title: title,
            body: body,
            tags: _memoryCurrent.tags,
            force: !_memoryCurrent.is_pesquisai,
          }),
        });
        const d = await r.json();
        if (!r.ok || !d.ok) {
          toast("❌ " + (d.error || r.status) + (d.hint ? " · " + d.hint : ""), "err");
          if (btnSave) { btnSave.disabled = false; btnSave.textContent = "💾 Salvar"; }
          return;
        }
        _memoryCurrent.body = body;
        _memoryCurrent.title = title;
        _memoryCurrent.is_pesquisai = true; // após salvar vira do agente
        _memoryDirty = false;
        markDirty();
        if (btnSave) {
          btnSave.textContent = "✅ Salvo";
          setTimeout(() => { btnSave.textContent = "💾 Salvar"; btnSave.disabled = false; }, 1500);
        }
        toast("✅ " + (d.message || "Nota salva."), "ok");
        // Recarrega a árvore
        openMemory(true);
      } catch (e) {
        toast("❌ " + e.message, "err");
        if (btnSave) { btnSave.disabled = false; btnSave.textContent = "💾 Salvar"; }
      }
    }

    // ── Excluir nota ──────────────────────────────────────────────
    async function deleteCurrentNote() {
      if (!_memoryCurrent) return;
      var _confirmed = false;
      pesquisaiConfirm("Mover '" + _memoryCurrent.path + "' para .trash/?", function() {
        if (_confirmed) return; _confirmed = true;
        _continueDeleteCurrentNote();
      });
      return;
    }
    async function _continueDeleteCurrentNote() {
      try {
        const r = await fetch(BASE + "/api/obsidian/note", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "delete",
            path: _memoryCurrent.path,
            force: !_memoryCurrent.is_pesquisai,
          }),
        });
        const d = await r.json();
        if (!r.ok || !d.ok) {
          toast("❌ " + (d.error || r.status) + (d.hint ? " · " + d.hint : ""), "err");
          return;
        }
        toast("🗑 " + (d.message || "Nota movida para .trash/."), "ok");
        // Limpa editor
        _memoryCurrent = null;
        _memoryDirty = false;
        const meta  = document.getElementById("memory-note-meta");
        const tabs  = document.getElementById("memory-editor-tabs");
        const ed    = document.getElementById("memory-editor");
        const prev  = document.getElementById("memory-preview");
        const empty = document.getElementById("memory-editor-empty");
        const btnSave = document.getElementById("memory-btn-save");
        const btnDel  = document.getElementById("memory-btn-delete");
        if (meta) meta.style.display = "none";
        if (tabs) tabs.style.display = "none";
        if (ed)   ed.value = "";
        if (prev) prev.innerHTML = "";
        if (empty){ empty.style.display = ""; }
        if (btnSave){ btnSave.disabled = true; btnSave.style.opacity = ".4"; btnSave.style.cursor = "not-allowed"; }
        if (btnDel) { btnDel.disabled  = true; btnDel.style.opacity  = ".4"; btnDel.style.cursor  = "not-allowed"; }
        markDirty();
        openMemory(true);
      } catch (e) {
        toast("❌ " + e.message, "err");
      }
    }

    // ── Diálogo de nova nota ──────────────────────────────────────
    async function openCreateNoteDialog() {
      if (_memoryDirty && _memoryCurrent) {
        var _confirmed = false;
        pesquisaiConfirm("Há mudanças não salvas em '" + _memoryCurrent.path + "'.\\nContinuar?", function() {
          if (_confirmed) return; _confirmed = true;
          _continueOpenCreateNoteDialog();
        });
        return;
      }
      _continueOpenCreateNoteDialog();
    }
    function _continueOpenCreateNoteDialog() {
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const overlay = document.getElementById("memory-new-overlay");
      if (overlay) { overlay.style.opacity = "1"; overlay.style.pointerEvents = "all"; }
      // Carrega templates disponíveis
      const sel = document.getElementById("memory-new-template");
      if (sel && _memoryStatus && _memoryStatus.templates && _memoryStatus.templates.length) {
        sel.innerHTML = _memoryStatus.templates.map(t =>
          '<option value="' + escapeHtml(t) + '">' + escapeHtml(t) + '</option>'
        ).join("");
      } else if (sel) {
        sel.innerHTML = '<option value="inbox">inbox</option>';
      }
      const p = document.getElementById("memory-new-path");
      if (p) { p.value = "inbox/" + new Date().toISOString().slice(0,10) + "-nova-nota.md"; p.focus(); p.select(); }
      const t = document.getElementById("memory-new-title");
      if (t) t.value = "";
      const tg = document.getElementById("memory-new-tags");
      if (tg) tg.value = "pesquisai/draft";
    }

    function closeCreateNoteDialog() {
      const overlay = document.getElementById("memory-new-overlay");
      if (overlay) { overlay.style.opacity = "0"; overlay.style.pointerEvents = "none"; }
    }

    async function submitCreateNote() {
      const path = (document.getElementById("memory-new-path").value || "").trim();
      const title = (document.getElementById("memory-new-title").value || "").trim();
      const template = document.getElementById("memory-new-template").value || "inbox";
      const tagsRaw = (document.getElementById("memory-new-tags").value || "").trim();
      const tags = tagsRaw ? tagsRaw.split(",").map(s => s.trim()).filter(Boolean) : [];
      if (!path) { toast("⚠️ Caminho obrigatório.", "err"); return; }
      if (!path.endsWith(".md")) {
        toast("⚠️ Caminho deve terminar com .md", "err"); return;
      }
      try {
        const r = await fetch(BASE + "/api/obsidian/note", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "create", path, title, template, tags }),
        });
        const d = await r.json();
        if (!r.ok || !d.ok) {
          toast("❌ " + (d.error || r.status), "err");
          return;
        }
        toast("✅ " + (d.message || "Nota criada."), "ok");
        closeCreateNoteDialog();
        await openMemory(true);
        // Abre a nota recém-criada
        if (d.path) loadMemoryNote(d.path);
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
        root.style.backgroundColor = "#141c24";
      }
      if (theme === "pesquisai-light") {
        root.style.setProperty("--ink", "#1f262a");
        root.style.setProperty("--ink-muted", "#4a5a62");
        root.style.setProperty("--surface", "#f5f6f7");
        root.style.setProperty("--rail", "#ffffff");
        root.style.setProperty("--line", "rgba(0,0,0,.1)");
        // v0.6.4: paleta UFVAI (dourado sobre papel quente; antes: teal #157a73)
        root.style.setProperty("--accent", "#8a6d33");
        root.style.setProperty("--accent-dim", "rgba(138,109,51,.10)");
        root.style.setProperty("--accent-glow", "rgba(138,109,51,.18)");
        root.style.setProperty("--green", "#2e7d32");
        root.style.setProperty("--green-dim", "rgba(46,125,50,.1)");
        root.style.setProperty("--amber", "#a67c00");
        root.style.setProperty("--amber-dim", "rgba(166,124,0,.12)");
        root.style.setProperty("--red", "#c62828");
        root.style.setProperty("--red-dim", "rgba(198,40,40,.1)");
        // v0.6.5: backdrop de modais acompanha o tema claro
        root.style.setProperty("--ov-dim", "rgba(30,42,52,.38)");
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#f5f6f7");
      } else {
        root.style.setProperty("--ink", "#e8e6e0");
        root.style.setProperty("--ink-muted", "#9a9790");
        // v0.6.4: alinhado ao :root UFVAI (antes: surface #0d0f10/rail #151819/accent teal #46a39b)
        root.style.setProperty("--surface", "#141c24");
        root.style.setProperty("--rail", "#1f2831");
        root.style.setProperty("--line", "rgba(255,255,255,.07)");
        root.style.setProperty("--accent", "#b29149");
        root.style.setProperty("--accent-dim", "rgba(var(--accent-rgb),.12)");
        root.style.setProperty("--accent-glow", "rgba(var(--accent-rgb),.22)");
        root.style.setProperty("--green", "#5dba7e");
        root.style.setProperty("--green-dim", "rgba(93,186,126,.12)");
        root.style.setProperty("--amber", "#D1A705");
        root.style.setProperty("--amber-dim", "rgba(209,167,5,.14)");
        root.style.setProperty("--red", "#e07070");
        root.style.setProperty("--red-dim", "rgba(224,112,112,.12)");
        // v0.6.5: backdrop de modais acompanha o tema escuro
        root.style.setProperty("--ov-dim", "rgba(4,7,11,.8)");
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#141c24");
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

    // ── v0.6.5: Splash de carregamento do terminal ─────────────
    // Polling em /api/ttyd_ready ANTES de apontar o iframe: o usuário vê
    // uma tela de espera com a marca em vez do ERR_CONNECTION_REFUSED do
    // Chrome dentro do retângulo do terminal.
    const TERMINAL_URL = (document.getElementById("terminal-frame") || {}).dataset
      ? (document.getElementById("terminal-frame").dataset.terminalUrl || "")
      : "";

    function _bootEls() {
      return {
        splash: document.getElementById("boot-splash"),
        status: document.getElementById("boot-status"),
        err: document.getElementById("boot-error"),
        retry: document.getElementById("boot-retry"),
        frame: document.getElementById("terminal-frame"),
      };
    }

    function _bootDict() { return I18N[_currentLang] || I18N["pt_BR"]; }

    function showBootSplash(msg) {
      const el = _bootEls();
      if (!el.splash) return;
      el.splash.style.display = "";
      el.splash.classList.remove("hide");
      const sp = el.splash.querySelector(".boot-spinner");
      const bar = el.splash.querySelector(".boot-bar");
      if (sp) sp.style.display = "";
      if (bar) bar.style.display = "";
      if (el.status) { el.status.style.display = ""; if (msg) el.status.textContent = msg; }
      if (el.err) el.err.style.display = "none";
      if (el.retry) el.retry.style.display = "none";
    }

    function hideBootSplash() {
      const el = _bootEls();
      if (!el.splash) return;
      el.splash.classList.add("hide");
      setTimeout(() => { el.splash.style.display = "none"; }, 500);
    }

    // v0.7.5+: pid do ttyd em exibição. Se o servidor for reiniciado por
    // baixo (idioma, restore, auto-cura), o iframe é recarregado sozinho —
    // antes o usuário ficava no "Reconnect" mesmo com o opencode vivo.
    let _ttydPid = null;
    let _ttydWatch = null;

    async function waitTerminalReady(maxMs) {
      const t0 = Date.now();
      maxMs = maxMs || 30000;
      while (Date.now() - t0 < maxMs) {
        try {
          const r = await fetch(BASE + "/api/ttyd_ready", { cache: "no-store" });
          if (r.ok) {
            const d = await r.json();
            if (d.ready) { if (d.pid) _ttydPid = d.pid; return true; }
          }
        } catch (e) {}
        await new Promise(z => setTimeout(z, 250));
      }
      return false;
    }

    async function bootTerminal(maxMs) {
      const el = _bootEls();
      if (!el.frame || !TERMINAL_URL) { hideBootSplash(); return; }
      showBootSplash(_bootDict()["boot.starting"] || "Iniciando terminal…");
      const ok = await waitTerminalReady(maxMs);
      if (!ok) {
        const dict = _bootDict();
        const sp = el.splash.querySelector(".boot-spinner");
        const bar = el.splash.querySelector(".boot-bar");
        if (sp) sp.style.display = "none";
        if (bar) bar.style.display = "none";
        if (el.status) el.status.style.display = "none";
        if (el.err) {
          el.err.textContent = (dict["boot.timeout"] ||
            "O terminal não respondeu. Verifique ~/PesquisAI/logs/ttyd.log.");
          el.err.style.display = "block";
        }
        if (el.retry) el.retry.style.display = "inline-block";
        return;
      }
      let loaded = false;
      el.frame.onload = () => { loaded = true; hideBootSplash(); };
      el.frame.src = TERMINAL_URL;
      if (!_ttydWatch) {
        _ttydWatch = setInterval(async () => {
          try {
            const r = await fetch(BASE + "/api/ttyd_ready", { cache: "no-store" });
            if (!r.ok) return;
            const d = await r.json();
            if (!d.ready || !d.pid) return;
            if (_ttydPid === null) { _ttydPid = d.pid; return; }
            if (d.pid === _ttydPid) return;
            _ttydPid = d.pid;                 // ttyd reiniciado por baixo
            const f = document.getElementById("terminal-frame");
            if (f) {
              try { f.contentWindow.location.reload(); }
              catch (e) { f.src = TERMINAL_URL; }
            }
          } catch (e) {}
        }, 20000);
      }
      setTimeout(() => { if (!loaded) hideBootSplash(); }, 8000); // fallback visual
    }

    // ── Listeners globais ─────────────────────────────────────
    document.addEventListener("keydown", (e) => {
      if (e.key === "?" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
        e.preventDefault();
        openShortcuts();
      }
      if (e.key === "Escape") {
        closeHealth(); closeSessions(); closeShortcuts(); closeAgents(); closeMemory();  // v0.5.1.2
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

    // ══════════════════════════════════════════════════════════
    // v0.7.0 — AUTOSAVE: chave liga/desliga, timer e pergunta de
    // retomada (com data/hora, no idioma do usuário).
    // v0.7.3: o intervalo caiu de 3 min para 1 min.
    // ══════════════════════════════════════════════════════════
    const AUTOSAVE_INTERVAL_MS = 60000;       // v0.7.3: 1 minuto
    const AUTOSAVE_KEY = "ufvai_autosave_enabled";
    // v0.7.4: alcance do autosave. "0" (PADRAO) = so a sessao ATIVA;
    // "1" = todas as conversas (um arquivo por sessao).
    const AUTOSAVE_ALL_KEY = "ufvai_autosave_all_sessions";
    let _autosaveTimer = null;
    let _autosaveBusy = false;
    let _autosaveLatest = null;               // autosave valido mais recente
    let _autosaveList = [];                   // v0.7.1: todos os autosaves validos (fallback)

    function autosaveDict() {
      return I18N[_currentLang] || I18N["pt_BR"];
    }

    function autosaveEnabled() {
      // v0.7.0 — LIGADO POR PADRAO. O autosave só fica desligado se o
      // usuario desligar explicitamente (chave "0" no localStorage).
      // Ausencia de preferencia => ligado.
      try {
        const saved = localStorage.getItem(AUTOSAVE_KEY);
        return !(saved === "0" || saved === "false");
      } catch (e) { return true; }
    }

    // v0.7.4 — so a sessao ATIVA e' salva por padrao; o autor pode ligar
    // "Todas as conversas" no rodape (um arquivo por sessao no Drive).
    function autosaveAllSessions() {
      try { return localStorage.getItem(AUTOSAVE_ALL_KEY) === "1"; }
      catch (e) { return false; }
    }

    function setAutosaveAllUI(on) {
      const box = document.getElementById("autosave-all-toggle");
      const sw = document.getElementById("autosave-all-switch");
      if (box) box.checked = !!on;
      if (sw) sw.classList.toggle("on", !!on);
    }

    function toggleAutosaveAll(on) {
      try { localStorage.setItem(AUTOSAVE_ALL_KEY, on ? "1" : "0"); } catch (e) {}
      setAutosaveAllUI(on);
      toast(on ? ("💾 " + (autosaveDict()["autosave.all_on"] ||
              "Todos as conversas passarão a ser salvas."))
               : (autosaveDict()["autosave.all_off"] ||
                  "O autosave voltará a salvar só a sessão ativa."), "info");
    }

    function setAutosaveUI(on) {
      const box = document.getElementById("autosave-toggle");
      const sw = document.getElementById("autosave-switch");
      if (box) box.checked = !!on;
      if (sw) sw.classList.toggle("on", !!on);
    }

    function toggleAutosave(on) {
      try { localStorage.setItem(AUTOSAVE_KEY, on ? "1" : "0"); } catch (e) {}
      setAutosaveUI(on);
      if (on) {
        startAutosaveTimer();
        // Grava um autosave logo ao ligar (não espera o intervalo)
        autosaveTick(true);
      } else {
        stopAutosaveTimer();
        toast(autosaveDict()["autosave.off_msg"] || "Autosave desligado", "info");
      }
    }

    function startAutosaveTimer() {
      stopAutosaveTimer();
      _autosaveTimer = setInterval(() => autosaveTick(false), AUTOSAVE_INTERVAL_MS);
    }

    function stopAutosaveTimer() {
      if (_autosaveTimer) { clearInterval(_autosaveTimer); _autosaveTimer = null; }
    }

    async function autosaveTick(silent) {
      if (_autosaveBusy) return;
      if (!autosaveEnabled() && !silent) return;
      _autosaveBusy = true;
      try {
        const r = await fetch(BASE + "/api/autosave", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({all_sessions: autosaveAllSessions()})
        });
        const d = await r.json();
        if (d && d.ok) {
          _autosaveLatest = d;
          if (!silent) {
            // v0.7.1: quando o conteudo e' identico ao do ultimo autosave,
            // o backend NAO grava outro arquivo (3 slots = 3 versoes
            // distintas). A interface diz isso explicitamente para o
            // usuario nao achar que o autosave falhou.
            // v0.7.4: quando ha VARIAS conversas, o autosave grava cada
            // uma (um arquivo por sessao) — o toast informa quantas.
            var _ss = (d && d.sessions_saved) || null;
            var _n = (_ss && _ss.saved && _ss.saved.length) || 0;
            if (d.skipped && !_n) {
              toast((autosaveDict()["autosave.unchanged"] ||
                "Sem novidades — o autosave mais recente já é o atual."), "info");
            } else if (_n > 1) {
              toast(("💾 " + _n + " conversas salvas no Drive (uma por sessão)"), "ok");
            } else {
              toast((autosaveDict()["autosave.saved"] || "Sessão salva no Drive"), "ok");
            }
          }
        } else if (!silent) {
          toast("❌ " + ((d && d.error) || "Falha no autosave"), "err");
        }
      } catch (e) {
        if (!silent) toast("❌ " + e.message, "err");
      } finally {
        _autosaveBusy = false;
      }
    }

    // ── v0.7.5 — a pergunta de retomada: UMA VEZ por execução, sem loop ──
    // Histórico: v0.7.1 "Continuar" recarregava e reoferecia (loop);
    // v0.7.2 a flag ficava para sempre na aba (nunca mais perguntava);
    // v0.7.3 tentou consumir o estado a cada carga (perguntava de novo);
    // v0.7.5 usava 12 h de TTL no localStorage — uma nova entrada no MESMO
    // dia não perguntava (bug "às vezes não aparece a pergunta").
    //
    // Correção: a marca é escopada por UFVAI_BOOT_ID (execução) e gravada
    // nas 3 camadas ANTES de exibir. Recargas da MESMA execução não repetem;
    // um novo launch (outro ID) volta a perguntar. O ↻ limpa a marca.
    // O menu "Restaurar" (calendário) continua disponível sempre.

    /** Marca a pergunta como já oferecida nesta execução. */
    function markAutosaveResumeOffered() {
      try { if (typeof ufvaiOpeningMark === "function") ufvaiOpeningMark("resume"); } catch (e) {}
    }

    /** v0.7.5 — reabrir a pergunta de retomada sob demanda (botão ↻). */
    async function reofferAutosaveResume() {
      try { if (typeof ufvaiOpeningClear === "function") ufvaiOpeningClear("resume"); } catch (e) {}
      await checkAutosaveResume();
    }

    /** Mostra a pergunta de retomada (data/hora do último autosave). */
    function showAutosaveResume(item) {
      const overlay = document.getElementById("autosave-overlay");
      const when = document.getElementById("autosave-when");
      if (!overlay) return;
      // v0.7.5: marca ANTES de exibir — a recarga que reconecta o terminal
      // não reoferece a pergunta (e um novo launch não é afetado).
      markAutosaveResumeOffered();
      if (when) {
        const stamp = item.saved_at_local || item.saved_at_iso || "";
        when.textContent = (autosaveDict()["autosave.resume.when"] || "Autosave de") + " " + stamp;
      }
      overlay.classList.add("open");
    }

    function closeAutosaveResume() {
      const overlay = document.getElementById("autosave-overlay");
      if (overlay) overlay.classList.remove("open");
    }

    /** Continuar do último autosave: restaura o arquivo no motor.
     *  v0.7.1: tenta o mais recente e, se falhar, o anterior (até 3) —
     *  os 3 últimos ficam como fallback. O nome vai prefixado com
     *  "autosave/" (é o formato que o /api/restore reconhece). */
    async function autosaveResumeContinue() {
      closeAutosaveResume();
      const list = (_autosaveList && _autosaveList.length)
        ? _autosaveList
        : (_autosaveLatest ? [_autosaveLatest] : []);
      if (!list.length) {
        toast("❌ " + (autosaveDict()["autosave.resume.none"] || "Nenhum autosave válido"), "err");
        return;
      }
      toast(autosaveDict()["autosave.resume.restoring"] || "Restaurando o último autosave…", "info");
      let lastError = "";
      for (const item of list.slice(0, 3)) {
        const raw = String((item && item.file) || "");
        if (!raw) continue;
        const file = raw.indexOf("autosave/") === 0 ? raw : ("autosave/" + raw);
        try {
          const r = await fetch(BASE + "/api/restore", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file: file })
          });
          const d = await r.json();
          if (d && d.ok) {
            // v0.7.5: o usuário RESPONDEU (continuar). Não reoferece nesta
            // execução — nem depois do reload que reconecta o terminal.
            markAutosaveResumeOffered();
            const dropped = (d.fit && d.fit.messages_dropped) || 0;
            const done = autosaveDict()["autosave.resume.done"] || "Sessão restaurada";
            const partial = dropped
              ? " · " + ((restoreDict()["restore.partial"] ||
                  "{n} mensagens antigas omitidas para caber no contexto").replace("{n}", dropped))
              : "";
            toast("✅ " + done + partial, "ok");
            // v0.7.5+: o backend já espera a porta do ttyd — reload imediato.
            setTimeout(() => location.reload(), 1200);
            return;
          }
          lastError = (d && d.error) || "Falha ao restaurar";
        } catch (e) {
          lastError = e.message;
        }
      }
      toast("❌ " + lastError, "err");
    }

    /** Iniciar uma nova sessão: descarta a pergunta e segue. */
    function autosaveResumeNew() {
      closeAutosaveResume();
      // v0.7.5: "Nova sessão" é uma RESPOSTA — não pergunta de novo nesta
      // execução (antes o estado era "new" e sobrevivia a tudo).
      markAutosaveResumeOffered();
    }

    /** Na abertura: se houver autosave válido, pergunta UMA vez por execução. */
    var _resumeWaitTries = 0;
    async function checkAutosaveResume() {
      // v0.7.5: a marca é por EXECUÇÃO (UFVAI_BOOT_ID). Recargas da mesma
      // execução não repetem a pergunta; um novo launch (nova marca) volta
      // a perguntar — antes o TTL de 12 h no localStorage suprimia a
      // pergunta em entradas novas no mesmo dia.
      try {
        if (typeof ufvaiOpeningGet === "function" && ufvaiOpeningGet("resume")) return;
      } catch (e) {}
      // não abrir por cima de outra tela de abertura: espera ela fechar
      let blocking = false;
      try { blocking = (typeof ufvaiOpeningAnyVisible === "function") && ufvaiOpeningAnyVisible(); } catch (e) {}
      if (blocking) {
        if (_resumeWaitTries++ < 60) setTimeout(checkAutosaveResume, 1500);
        return;
      }
      _resumeWaitTries = 0;
      try {
        const r = await fetch(BASE + "/api/autosave");
        const d = await r.json();
        if (d && d.latest) {
          _autosaveLatest = d.latest;
          // v0.7.1: guarda a lista completa (fallback: mais recente → anterior)
          _autosaveList = (d.autosaves && d.autosaves.length) ? d.autosaves : [d.latest];
          let blocked = false;
          try { blocked = (typeof ufvaiOpeningAnyVisible === "function") && ufvaiOpeningAnyVisible(); } catch (e) {}
          if (blocked) {
            if (_resumeWaitTries++ < 60) setTimeout(checkAutosaveResume, 1500);
            return;
          }
          showAutosaveResume(d.latest);
          // Sem resposta em 20s -> nova sessão (a pergunta não bloqueia)
          setTimeout(() => closeAutosaveResume(), 20000);
        }
      } catch (e) { /* silencioso: sem autosave, segue normal */ }
    }

    // ── Inicialização ────────────────────────────────────────
    // v0.7.5+ (sem bump): roda em DOMContentLoaded, não em `load`. O evento
    // `load` só dispara depois do iframe do terminal e dos assets externos —
    // a interface ficava sem tradução (e sem o relógio do autosave) até lá.
    function _ufvaiInit() {
      // 1. Aplica idioma (síncrono, sem flash)
      applyLang(_currentLang);
      buildLangMenu();
      // 1.1 v0.7.0/v0.7.3: chave do autosave + timer de 1 min + pergunta de retomada
      setAutosaveUI(autosaveEnabled());
      setAutosaveAllUI(autosaveAllSessions());
      if (autosaveEnabled()) startAutosaveTimer();
      // v0.7.5+: a listagem de autosaves vem do cache do servidor (~6 ms);
      // 350 ms já bastam para a pergunta aparecer sem espera perceptível.
      setTimeout(() => checkAutosaveResume(), 350);
      // Ao sair da aba, tenta gravar o estado (sendBeacon, não bloqueia)
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden" && autosaveEnabled() && !_autosaveBusy) {
          try {
            const payload = new Blob([JSON.stringify({})], { type: "application/json" });
            navigator.sendBeacon(BASE + "/api/autosave", payload);
          } catch (e) {}
        }
      });
      // v0.6.15 — ADOÇÃO SILENCIOSA DO IDIOMA DO NAVEGADOR (v0.7.5)
      // O backend sobe ANTES de o navegador existir e detecta o idioma pelo
      // locale do servidor (no Colab: en_US). Se o navegador está em outro
      // idioma, a versão anterior chamava setLang() → POST /api/lang →
      // reiniciava o ttyd → location.reload(). Isso criava uma SEGUNDA
      // sessão do motor (a conversa em andamento ficava na primeira),
      // recarregava a página e podia engolir a pergunta de retomada.
      //
      // Agora a divergência é resolvida SEM reiniciar nada:
      // POST /api/lang {restart:false} apenas persiste o idioma (UI + TUI na
      // próxima abertura). Sem splash, sem reload, sem tocar na sessão.
      // A guarda (por execução) evita repetir o POST a cada recarga.
      try {
        fetch(BASE + "/api/lang", { cache: "no-store" }).then(r => r.json()).then(d => {
          const backendLang = d && d.lang;
          if (!backendLang) return;
          // v0.7.5+: o POST também é necessário quando a saudação da sessão
          // nova ainda não foi semeada — mesmo que o idioma coincida.
          const pending = !!(d && d.greeting_pending);
          // v0.7.5+ (sem bump): escolha EXPLÍCITA do usuário (lang_source=user)
          // vale em qualquer navegador — o cookie local não a sobrescreve.
          if (d.lang_source === "user" && LANGS[backendLang] && backendLang !== _currentLang) {
            setCookie(LANG_COOKIE, backendLang);
            setCookie(LANG_SRC_COOKIE, "user");
            applyLang(backendLang);
          }
          if (backendLang === _currentLang && !pending) return;
          if (!LANGS[_currentLang]) return;
          const syncVal = UFVAI_BOOT_ID + "|" + _currentLang;
          let synced = "";
          try { synced = sessionStorage.getItem("ufvai_lang_synced") || ""; } catch (e) {}
          if (!synced) { try { synced = localStorage.getItem("ufvai_lang_synced") || ""; } catch (e) {} }
          if (!synced) synced = getCookie("ufvai_lang_synced") || "";
          if (synced === syncVal) return;
          fetch(BASE + "/api/lang", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lang: _currentLang, restart: false, source: "browser" })
          }).then(r => r.ok ? r.json() : null).then(res => {
            if (!res || !res.ok) return;
            try { sessionStorage.setItem("ufvai_lang_synced", syncVal); } catch (e) {}
            try { localStorage.setItem("ufvai_lang_synced", syncVal); } catch (e) {}
            try {
              document.cookie = "ufvai_lang_synced=" + encodeURIComponent(syncVal) +
                "; path=/; SameSite=Lax";
            } catch (e) {}
          }).catch(() => {});
        }).catch(() => {});
      } catch (e) {}
      // 2. Carrega tema
      loadInitialTheme();
      // 3. v0.7.5: aplica as keys DEPOIS do terminal conectar (evita disputar
      //    I/O do Drive com o boot do iframe); o motor já subiu com as chaves.
      setTimeout(() => {
        fetch(BASE + "/api/apikey/apply", { method: "POST" }).catch(() => {});
      }, 1500);
      // 4. v0.6.4: welcome-hint antigo REMOVIDO — a tela de Termos de Uso
      //    (terms-overlay, com a logomarca oficial UFVAI) é a única abertura.
      // 5. v0.6.5: conecta o terminal (com splash) só quando /api/ttyd_ready
      bootTerminal();
      // 6. v0.6.17: pré-aquece a memória (fire-and-forget) — o servidor constrói
      //    o índice BM25 em background E popula o cache local; o 1º clique no
      //    menu da memória abre instantâneo (sem esperar o Drive FUSE).
      //    v0.7.5: adiado 3 s para não competir com a conexão do terminal.
      setTimeout(() => {
        try {
          fetch(BASE + "/api/obsidian?include=tree").then(r=>r.json()).then(d=>{
            if (d && d.ok) {
              _memoryCache = { tree: d.tree || [], status: d, ts: Date.now() };
            }
          }).catch(()=>{});
        } catch(e){}
      }, 3000);
    }

    // Dispara a inicialização o mais cedo possível. Se o script já rodou
    // depois do parse (caso normal — está no fim do body), executa na hora.
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", _ufvaiInit, { once: true });
    } else {
      _ufvaiInit();
    }
    window.addEventListener("beforeunload", () => { _stopSessionsPoll(); });
  </script>
  <!-- marked.js: renderizador de markdown para o modal de Diretrizes do Agente e preview do editor -->
  <script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
  <!-- v0.6.4: welcome-hint (onboarding antigo PesquisAI) REMOVIDO.
       A logomarca oficial UFVAI agora abre na tela de Termos de Uso (terms-overlay). -->
  </div>
  <!-- Confirm dialog overlay (replaces native confirm()) -->
  <div id="confirm-overlay" style="position:fixed;inset:0;background:var(--ov-dim);display:flex;align-items:center;justify-content:center;z-index:100001;opacity:0;pointer-events:none;transition:opacity .18s;">
    <div style="background:var(--rail);border:1px solid var(--line);border-radius:10px;padding:22px;width:400px;max-width:92vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div id="confirm-msg" style="font-size:13px;line-height:1.55;color:var(--ink);margin-bottom:18px;"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button id="confirm-no" class="btn-ghost" style="padding:9px 16px;" data-i18n="ui.cancel">Cancelar</button>
        <button id="confirm-yes" class="btn-ghost" style="padding:9px 16px;background:var(--accent);color:#000;border-color:var(--accent);font-weight:600;" data-i18n="ui.confirm">Confirmar</button>
      </div>
    </div>
  </div>

<!-- ═══ v0.6.0 — Termos de Uso (aceite obrigatório na 1ª entrada) ═══ -->
<style>
  #terms-overlay{position:fixed;inset:0;z-index:99999;display:none;align-items:center;
    justify-content:center;background:rgba(10,13,17,.93);backdrop-filter:blur(6px);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;padding:16px;
    overflow-y:auto;-webkit-overflow-scrolling:touch;}
  #terms-overlay .t-card{max-width:660px;width:100%;background:#141c24;border:1px solid #b29149;
    border-radius:14px;padding:24px 26px;color:#e8e6e0;box-shadow:0 20px 60px rgba(0,0,0,.5);
    max-height:calc(100vh - 32px);max-height:calc(100dvh - 32px);overflow-y:auto;
    -webkit-overflow-scrolling:touch;margin:auto;}
  #terms-overlay .t-brand{font-family:"Montserrat","Syne",sans-serif;font-size:26px;
    letter-spacing:-0.02em;margin-bottom:2px;}
  #terms-overlay .t-brand b{font-weight:700}#terms-overlay .t-brand em{font-style:normal;font-weight:600;color:#b29149}
  #terms-overlay .t-sub{font-size:11px;color:#9a9790;margin-bottom:14px;}
  #terms-overlay .t-scroll{max-height:38vh;overflow:auto;border:1px solid rgba(178,145,73,.25);
    border-radius:8px;padding:12px 14px;font-size:12px;line-height:1.55;color:#cfcabf;margin-bottom:14px;}
  #terms-overlay .t-scroll h4{margin:10px 0 4px;color:#b29149;font-size:12px;}
  #terms-overlay .t-scroll p{margin:4px 0;}
  #terms-overlay .t-links{font-size:11px;margin-bottom:14px;display:flex;gap:14px;flex-wrap:wrap;}
  #terms-overlay .t-links a{color:#D1A705;text-decoration:none;border-bottom:1px dotted #D1A705;}
  #terms-overlay label.t-check{display:flex;gap:9px;align-items:flex-start;font-size:12px;
    margin-bottom:8px;cursor:pointer;line-height:1.45;}
  #terms-overlay input[type=checkbox]{accent-color:#b29149;width:15px;height:15px;margin-top:1px;flex:0 0 auto;}
  #terms-overlay .t-actions{display:flex;gap:10px;margin-top:14px;}
  #terms-overlay button{flex:1;padding:11px 14px;border-radius:9px;font-size:13px;font-weight:600;
    cursor:pointer;border:1px solid transparent;transition:.15s;}
  #terms-overlay .t-ok{background:linear-gradient(135deg,#D1A705,#b29149);color:#141c24;border:none;}
  #terms-overlay .t-ok:disabled{opacity:.35;cursor:not-allowed;}
  #terms-overlay .t-no{background:transparent;color:#9a9790;border-color:rgba(154,151,144,.35);}
  /* ── v0.6.20 — tela "Ambiente desconectado" (após SIM, SAIR) — mesmo visual
     da tela de Termos recusados (card escuro com borda dourada). Permanece
     visível quando o runtime do Colab é desconectado/excluído. ── */
  #exit-overlay{position:fixed;inset:0;z-index:100000;display:none;align-items:center;
    justify-content:center;background:rgba(10,13,17,.96);backdrop-filter:blur(6px);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;padding:16px;}
  #exit-overlay .t-card{max-width:520px;width:100%;background:#141c24;border:1px solid #b29149;
    border-radius:14px;padding:28px 26px;color:#e8e6e0;box-shadow:0 20px 60px rgba(0,0,0,.5);
    text-align:center;}
  #exit-overlay .t-brand{font-family:"Montserrat","Syne",sans-serif;font-size:26px;
    letter-spacing:-0.02em;margin-bottom:12px;}
  #exit-overlay .t-brand b{font-weight:700}#exit-overlay .t-brand em{font-style:normal;font-weight:600;color:#b29149}
  #exit-overlay .e-msg{font-size:13px;line-height:1.6;}
  /* ── v0.6.9: RESPONSIVO (celulares/tablets — tudo visível e rolável) ── */
  @media (max-width:640px){
    #terms-overlay{padding:10px;padding-left:max(10px,env(safe-area-inset-left));
      padding-right:max(10px,env(safe-area-inset-right));align-items:flex-start;
      -webkit-text-size-adjust:100%;text-size-adjust:100%;}
    #terms-overlay .t-card{padding:16px 14px;padding-bottom:calc(16px + env(safe-area-inset-bottom));
      border-radius:12px;max-height:calc(100vh - 20px);max-height:calc(100dvh - 20px);}
    #terms-overlay .t-card > div:first-child{margin-bottom:6px;}
    #terms-overlay .t-card img[alt^="UFVAI"]{width:64px !important;height:64px !important;}
    #terms-overlay .t-brand{font-size:21px;}
    #terms-overlay .t-sub{font-size:10px;margin-bottom:10px;}
    /* rolagem ÚNICA no card (sem scroll aninhado — mais natural no toque) */
    #terms-overlay .t-scroll{max-height:none;padding:10px 11px;font-size:11.5px;}
    #terms-overlay .t-scroll h4{font-size:11.5px;}
    #terms-overlay .t-links{gap:9px;font-size:10.5px;margin-bottom:10px;}
    #terms-overlay label.t-check{font-size:11.5px;gap:8px;}
    #terms-overlay input[type=checkbox]{width:14px;height:14px;}
    #terms-overlay input[type=email]{font-size:16px !important;padding:10px 11px !important;}
    #terms-overlay .t-actions{flex-direction:column;gap:8px;margin-top:12px;}
    /* v0.6.9: alvo de toque ≥44px (Apple HIG/Material) + sem highlight de tap */
    #terms-overlay button{padding:12px 10px;font-size:13px;flex:none;width:100%;
      min-height:46px;-webkit-tap-highlight-color:transparent;touch-action:manipulation;}
    #terms-overlay input[type=checkbox]{width:18px !important;height:18px !important;flex:0 0 auto;}
  }
  /* telas MUITO estreitas (ex.: iPhone SE, 320–400px) */
  @media (max-width:400px){
    #terms-overlay{padding:8px;}
    #terms-overlay .t-card{padding:14px 12px;}
    #terms-overlay .t-card img[alt^="UFVAI"]{width:54px !important;height:54px !important;}
    #terms-overlay .t-brand{font-size:19px;}
    #terms-overlay .t-scroll{font-size:11px;}
    #terms-overlay .t-links{flex-direction:column;gap:7px;}
    #terms-overlay label.t-check{font-size:11px;}
  }
  /* ALTURA baixa (landscape de celular OU tablet esticado) — prioriza o formulário */
  @media (max-height:520px){
    #terms-overlay{align-items:flex-start;}
    #terms-overlay .t-card{padding:12px 16px;max-height:calc(100vh - 16px);max-height:calc(100dvh - 16px);}
    #terms-overlay .t-card img[alt^="UFVAI"]{width:40px !important;height:40px !important;margin-bottom:4px !important;}
    #terms-overlay .t-brand{font-size:17px;margin-bottom:0;}
    #terms-overlay .t-sub{margin-bottom:6px;}
    #terms-overlay .t-scroll{max-height:none;font-size:10.5px;padding:8px 10px;}
    #terms-overlay .t-links{margin-bottom:8px;}
    #terms-overlay .t-actions{gap:6px;margin-top:8px;}
  }
  @media (max-height:600px) and (orientation:landscape){
    #terms-overlay{align-items:flex-start;}
    #terms-overlay .t-scroll{max-height:none;}
    #terms-overlay .t-card img[alt^="UFVAI"]{width:48px !important;height:48px !important;}
  }
</style>
<div id="terms-overlay" role="dialog" aria-modal="true" aria-label="Termos de Uso">
  <div class="t-card">
    <!-- v0.6.4: logomarca oficial UFVAI (asset local, offline-safe; some graciosamente se ausente) -->
    <div style="display:flex;justify-content:center;margin-bottom:10px;">
      <img src="assets/logo-oficial-288.jpg" alt="UFVAI — Universidade Federal de Viçosa"
           onerror="this.style.display='none'"
           style="width:96px;height:96px;border-radius:50%;border:2px solid rgba(178,145,73,.55);box-shadow:0 4px 18px rgba(0,0,0,.45);background:#fff;object-fit:cover;" />
    </div>
    <div class="t-brand"><b>UFV</b><em>AI</em></div>
    <div class="t-sub">Pesquisa científica com integridade · UFV/DER · v{__VERSION__}</div>
    <div class="t-scroll">
      <h4>🇧🇷 Português</h4>
      <p>O UFVAI é fornecido sob a <b>licença MIT</b>, sem garantias, e apoia pesquisa científica
      com <b>integridade</b>: valide as saídas da IA e declare o uso de IA conforme a Portaria CNPq
      nº 2.664/2026. Você é responsável pelas suas chaves de API (armazenadas cifradas no seu Google
      Drive), pelo conteúdo gerado e pelas políticas dos provedores de IA. Nenhum conteúdo do seu
      vault é enviado a terceiros pela telemetria — ela é <b>anônima, sem cookies, ativa por padrão
      após este aceite (legítimo interesse, LGPD art. 7º IX) e desligável a qualquer momento</b>
      (desmarque a opção acima ou UFVAI_TELEMETRY=0 — art. 18 §2º). Termos completos v2.1 no link abaixo.</p>
      <h4>🇺🇸 English</h4>
      <p>UFVAI is provided under the <b>MIT license</b>, without warranty. Validate AI outputs and
      disclose AI use per CNPq Ordinance 2.664/2026. You are responsible for your API keys,
      generated content and provider policies. Telemetry is anonymous, cookie-free, <b>on by
      default after accepting these terms</b> (legitimate interest, LGPD art. 7º IX) and can be
      disabled anytime (uncheck above or UFVAI_TELEMETRY=0).</p>
      <p style="opacity:.75">Español: licencia MIT, sin garantías; telemetría anónima activa por defecto, sin cookies, desactivable.
      · Français : licence MIT, sans garantie ; télémétrie anonyme active par défaut, sans cookies, désactivable.
      · 中文：MIT 许可证，不提供担保；遥测为匿名、默认开启（无 Cookie），可随时关闭。</p>
    </div>
    <div class="t-links">
      <a href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/LICENSE" target="_blank" rel="noopener">📜 Licença MIT + Notice / License</a>
      <a href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/docs/TERMS_OF_USE.md" target="_blank" rel="noopener">📄 Termos completos v2.1 / Full terms</a>
      <a href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/PRIVACY.md" target="_blank" rel="noopener">🔒 Privacidade · LGPD / Privacy</a>
    </div>
    <!-- v0.6.9: telemetria ATIVA POR PADRÃO (opt-out) — base: legítimo interesse (LGPD art. 7º IX),
         sem cookie _ga (analytics_storage:'denied'), direito de oposição art. 18 §2º + UFVAI_TELEMETRY=0.
         Opcionais ANTES do obrigatório (ordem crescente de exigência, v0.6.8) -->
    <label class="t-check"><input type="checkbox" id="t-analytics" checked>
      <span>Estatísticas anônimas de uso — <b>ativas por padrão</b> &nbsp;<span style="opacity:.7">(Anonymous usage stats — on by default, no cookies, no content. Desmarque para não contribuir / uncheck to opt out — LGPD art. 18 §2º; kill-switch UFVAI_TELEMETRY=0)</span></span></label>
    <!-- v0.6.10: Nome ao lado do e-mail (flex row: lado a lado no desktop, coluna no mobile) -->
    <div class="t-row" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:2px;">
      <label class="t-check" style="flex:1 1 160px;display:block;min-width:140px;margin:0;">
        <span style="display:block;margin-bottom:4px;font-size:12px;font-weight:600">Nome — <b>obrigatório</b>
          <span style="opacity:.7;font-weight:400">(Name — <b>required</b>)</span></span>
        <input type="text" id="t-name" placeholder="Seu nome"
               autocomplete="name" spellcheck="false"
               style="width:100%;box-sizing:border-box;padding:9px 11px;border-radius:8px;font-size:13px;
                      background:#0f151c;border:1px solid rgba(178,145,73,.35);color:#e8e6e0;outline:none;">
      </label>
      <label class="t-check" style="flex:1.2 1 180px;display:block;min-width:160px;margin:0;">
        <span style="display:block;margin-bottom:4px;font-size:12px;font-weight:600">E-mail — <b>obrigatório</b>
          <span style="opacity:.7;font-weight:400">(E-mail — <b>required</b>)</span></span>
        <input type="email" id="t-email" placeholder="nome@dominio.br"
               autocomplete="email" spellcheck="false"
               style="width:100%;box-sizing:border-box;padding:9px 11px;border-radius:8px;font-size:13px;
                      background:#0f151c;border:1px solid rgba(178,145,73,.35);color:#e8e6e0;outline:none;">
      </label>
    </div>
    <span style="display:block;font-size:10.5px;opacity:.65;margin:2px 0 6px;line-height:1.45">
      🔒 LGPD — nome e e-mail para ativação do UFVAI e contato sobre o produto (art. 7º V), guardados localmente
      (chmod 600) e em backups/ufvai_consentimento.json no SEU Drive; cifrados em trânsito. IP armazenado para métrica de ativação.
      O Google Analytics <b>nunca</b> recebe seu nome/e-mail/IP (apenas contador anônimo).
      Você pode apagar a qualquer momento (art. 18).<br>
      Name and e-mail to activate UFVAI and contact you; stored locally and in YOUR Drive; never sent to Google Analytics.</span>
    <label class="t-check"><input type="checkbox" id="t-accept">
      <span>Li e aceito os Termos de Uso e a Licença MIT &nbsp;<span style="opacity:.7">(I have read and accept the Terms of Use and the MIT License)</span></span></label>
    <div class="t-actions">
      <button class="t-no" id="t-decline-btn">Não aceitar / Decline</button>
      <button class="t-ok" id="t-accept-btn" disabled>Aceitar e começar / Accept</button>
    </div>
  </div>
</div>

<!-- ═══ v0.6.9 — Bem-vindo de volta (usuário já ativo na reabertura) ═══ -->
<style>
  #welcome-overlay{position:fixed;inset:0;z-index:99998;display:none;align-items:center;
    justify-content:center;background:rgba(10,13,17,.93);backdrop-filter:blur(6px);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;padding:16px;
    overflow-y:auto;-webkit-overflow-scrolling:touch;}
  #welcome-overlay .w-card{max-width:440px;width:100%;background:#141c24;border:1px solid #b29149;
    border-radius:14px;padding:28px 30px;color:#e8e6e0;box-shadow:0 20px 60px rgba(0,0,0,.5);
    text-align:center;max-height:calc(100vh - 32px);max-height:calc(100dvh - 32px);overflow-y:auto;
    -webkit-overflow-scrolling:touch;margin:auto;}
  #welcome-overlay .w-logo{width:96px;height:96px;border-radius:50%;border:2px solid rgba(178,145,73,.55);
    box-shadow:0 4px 18px rgba(0,0,0,.45);background:#fff;object-fit:cover;margin:0 auto 12px;display:block;}
  #welcome-overlay .w-brand{font-family:"Montserrat","Syne",sans-serif;font-size:26px;letter-spacing:-0.02em;}
  #welcome-overlay .w-brand b{font-weight:700}#welcome-overlay .w-brand em{font-style:normal;font-weight:600;color:#b29149}
  #welcome-overlay .w-title{font-size:18px;font-weight:600;margin:10px 0 4px;color:#e8e6e0;}
  #welcome-overlay .w-sub{font-size:12px;color:#9a9790;line-height:1.5;margin-bottom:16px;}
  #welcome-overlay .w-email{display:inline-block;background:rgba(178,145,73,.12);border:1px solid rgba(178,145,73,.4);
    border-radius:8px;padding:10px 18px;font-size:15px;font-weight:600;color:#F0E4C3;margin:4px 0 6px;word-break:break-all;}
  #welcome-overlay .w-note{font-size:10.5px;color:#7d7a72;line-height:1.45;margin:6px 0 18px;}
  #welcome-overlay .w-actions{display:flex;flex-direction:column;gap:9px;}
  #welcome-overlay button{padding:12px 14px;border-radius:9px;font-size:13px;font-weight:600;cursor:pointer;
    border:1px solid transparent;transition:.15s;width:100%;-webkit-tap-highlight-color:transparent;touch-action:manipulation;}
  #welcome-overlay .w-ok{background:linear-gradient(135deg,#D1A705,#b29149);color:#141c24;border:none;min-height:46px;}
  #welcome-overlay .w-switch{background:transparent;color:#9a9790;border-color:rgba(154,151,144,.35);font-weight:500;min-height:44px;}
  @media (max-width:640px){
    #welcome-overlay{padding:10px;padding-left:max(10px,env(safe-area-inset-left));
      padding-right:max(10px,env(safe-area-inset-right));align-items:flex-start;
      -webkit-text-size-adjust:100%;text-size-adjust:100%;}
    #welcome-overlay .w-card{padding:20px 16px;padding-bottom:calc(20px + env(safe-area-inset-bottom));
      border-radius:12px;max-height:calc(100vh - 20px);max-height:calc(100dvh - 20px);}
    #welcome-overlay .w-logo{width:72px !important;height:72px !important;}
    #welcome-overlay .w-brand{font-size:21px;}
    #welcome-overlay .w-title{font-size:16px;}
    #welcome-overlay .w-email{font-size:14px;}
  }
  @media (max-width:400px){
    #welcome-overlay{padding:8px;}
    #welcome-overlay .w-card{padding:16px 12px;}
    #welcome-overlay .w-logo{width:60px !important;height:60px !important;}
    #welcome-overlay .w-brand{font-size:19px;}
  }
  @media (max-height:520px){
    #welcome-overlay{align-items:flex-start;}
    #welcome-overlay .w-card{padding:14px 16px;max-height:calc(100vh - 16px);max-height:calc(100dvh - 16px);}
    #welcome-overlay .w-logo{width:44px !important;height:44px !important;margin-bottom:6px !important;}
    #welcome-overlay .w-title{font-size:15px;margin-top:6px;}
    #welcome-overlay .w-sub{margin-bottom:10px;}
    #welcome-overlay .w-actions{gap:6px;}
  }
</style>
<div id="welcome-overlay" role="dialog" aria-modal="true" aria-label="Bem-vindo de volta">
  <div class="w-card">
    <img src="assets/logo-oficial-288.jpg" alt="UFVAI — Universidade Federal de Viçosa"
         onerror="this.style.display='none'" class="w-logo" />
    <div class="w-brand"><b>UFV</b><em>AI</em></div>
    <div class="w-sub" style="font-size:11px;color:#9a9790;margin-bottom:8px;">Pesquisa científica com integridade · UFV/DER · v{__VERSION__}</div>
    <div class="w-title">👋 Bem-vindo de volta! / Welcome back!</div>
    <div class="w-sub">Continue sua pesquisa de onde parou.<br>
      <span style="opacity:.75">Pick up your research where you left off.</span></div>
    <div class="w-email" id="w-email">—</div>
    <div class="w-note">🔒 Seu e-mail de ativação — guardado no seu Drive (backups/ufvai_consentimento.json)
      · Your activation e-mail — stored in your Drive (backups/ufvai_consentimento.json).</div>
    <div class="w-actions">
      <button class="w-ok" id="w-ok-btn">Continuar como este usuário / Continue as this user</button>
      <button class="w-switch" id="w-switch-btn">Se não é você, alterar e-mail / Not you? Change e-mail</button>
    </div>
  </div>
</div>
<script>
(function(){
  // v0.6.14: captura IP público via ipify (CORS) — corrige Colab localhost (proxy sem XFF)
  var __UFVAI_CLIENT_IP__ = "";
  try {
    fetch("https://api.ipify.org?format=json", {cache:"no-store"}).then(function(r){return r.json();}).then(function(j){ if(j && j.ip) __UFVAI_CLIENT_IP__ = String(j.ip).trim(); }).catch(function(){});
    setTimeout(function(){ if(!__UFVAI_CLIENT_IP__) fetch("https://ipinfo.io/json", {cache:"no-store"}).then(function(r){return r.json();}).then(function(j){ if(j && j.ip) __UFVAI_CLIENT_IP__ = String(j.ip).trim(); }).catch(function(){}); }, 1800);
  } catch(e){}
  try{
    // v0.6.10: termos v6 → re-consentimento (nome+email obrigatórios, IP capturado)
    // v0.6.14: __UFVAI_CLIENT_IP__ enviado junto a /api/consent e /api/access
    var _TV="6";
    var ov=document.getElementById("terms-overlay");
    if(!ov) return;
    var chk=document.getElementById("t-accept"),
        btn=document.getElementById("t-accept-btn"),
        an=document.getElementById("t-analytics"),
        em=document.getElementById("t-email"),
        nm=document.getElementById("t-name"),
        profAnalytics=null,  // v0.6.10: prefs do perfil p/ o fluxo "Se não é você"
        err=null, errName=null;
    function _validMail(v){return !!v && /^[^@\\s]{1,64}@[^@\\s]+\\.[^@\\s]{2,}$/.test(v);}
    function _validName(v){ v=(v||"").trim(); return v.length>=2 && v.length<=100 && /^[A-Za-zÀ-ÿÀ-ÿ\\s'\\-]{2,100}$/.test(v); }
    function _updateBtn(){
      // v0.6.10: NOME + E-MAIL obrigatórios — habilita só com Termos aceitos + ambos válidos
      var okMail=_validMail((em&&em.value||"").trim());
      var okName=_validName((nm&&nm.value||"").trim());
      btn.disabled=!(chk.checked && okMail && okName);
    }
    function _post(accepted, analytics, contactEmail, contactName, onDone){
      try{
        var payload={accepted:accepted,analytics:analytics,terms_version:_TV};
        if(contactEmail!==undefined) payload.contact_email=contactEmail;
        if(contactName!==undefined) payload.contact_name=contactName;
        if(__UFVAI_CLIENT_IP__) payload.ip=__UFVAI_CLIENT_IP__;
        // v0.6.20-fix: quando onDone vem preenchido (fluxo do aceite), o
        // heartbeat "usuario_ativo" é disparado DEPOIS da resposta do
        // /api/consent — o perfil já está gravado no servidor e a planilha
        // recebe exatamente 1 linha (e-mail · nome · IP) por clique do botão.
        fetch("/api/consent",{method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify(payload)}).then(function(){ if(onDone) try{onDone();}catch(e){} })["catch"](function(){ if(onDone) try{onDone();}catch(e){} });
      }catch(e){ if(onDone) try{onDone();}catch(e2){} }
    }
    var _heartbeatSent=false;
    function _heartbeat(){
      try{
        if(_heartbeatSent) return;
        _heartbeatSent=true;
        var p={}; if(__UFVAI_CLIENT_IP__) p.ip=__UFVAI_CLIENT_IP__;
        fetch("/api/access",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)}).catch(function(){});
      }catch(e){}
    }
    var _shown=false;      // 23/10/2026: abertura (Termos OU "Bem-vindo") UMA vez
    function _openTerms(){
      if(_shown) return;   // já houve uma abertura nesta carga
      // v0.7.5: já apareceu nesta SESSÃO/aba (marca sobrevive às recargas)
      try{ if(window.ufvaiOpeningGet && window.ufvaiOpeningGet("terms")) return; }catch(e){}
      _shown=true;
      try{ if(window.ufvaiOpeningMark) window.ufvaiOpeningMark("terms"); }catch(e){}
      ov.style.display="flex";
      _updateBtn();
    }
    function _showErr(msg){
      if(!err){
        err=document.createElement("div");
        err.style.cssText="font-size:11px;color:#e07b5f;margin-top:4px;";
        var p=em?em.parentNode:null; if(p) p.appendChild(err); else ov.appendChild(err);
      }
      err.textContent=msg||"";
    }
    function _showErrName(msg){
      if(!errName){
        errName=document.createElement("div");
        errName.style.cssText="font-size:11px;color:#e07b5f;margin-top:4px;";
        var p=nm?nm.parentNode:null; if(p) p.appendChild(errName); else ov.appendChild(errName);
      }
      errName.textContent=msg||"";
    }
    chk.addEventListener("change",_updateBtn);
    if(em) em.addEventListener("input",function(){ if(err) err.textContent=""; _updateBtn(); });
    if(nm) nm.addEventListener("input",function(){ if(errName) errName.textContent=""; _updateBtn(); });
    // v0.6.10: MOBILE — autofill do celular preenche nome/e-mail SEM disparar "input";
    // sem isso o botão ficaria desabilitado e o usuário não conseguiria clicar.
    // Cobrimos com change/blur + verificação periódica leve (só com overlay visível).
    if(em){ em.addEventListener("change",_updateBtn); em.addEventListener("blur",_updateBtn); }
    if(nm){ nm.addEventListener("change",_updateBtn); nm.addEventListener("blur",_updateBtn); }
    var _autofillTimer=null;
    function _ensureAutofillWatch(){
      if(_autofillTimer) return;
      _autofillTimer=setInterval(function(){
        if(ov.style.display==="none"){ clearInterval(_autofillTimer); _autofillTimer=null; return; }
        _updateBtn();
      },400);
    }
    _ensureAutofillWatch();
    // v0.6.10: MOBILE — teclado virtual não pode cobrir o campo/botão: rola até o
    // elemento focado (visualViewport quando disponível; fallback scrollIntoView).
    function _reveal(elm,delay){
      try{ setTimeout(function(){
        if(window.visualViewport && typeof window.visualViewport.height==="number"){
          var r=elm.getBoundingClientRect(), vh=window.visualViewport.height;
          if(r.bottom>vh || r.top<0) elm.scrollIntoView({block:"center",behavior:"smooth"});
        } else {
          elm.scrollIntoView({block:"nearest",behavior:"smooth"});
        }
      },delay||250); }catch(e){}
    }
    if(em) em.addEventListener("focus",function(){ _reveal(em,300); });
    if(nm) nm.addEventListener("focus",function(){ _reveal(nm,300); });
    if(btn) btn.addEventListener("focus",function(){ _reveal(btn,150); });
    if(window.visualViewport){
      try{
        window.visualViewport.addEventListener("resize",function(){
          var ae=document.activeElement;
          if(ae===em || ae===nm) _reveal(ae,60);
        });
      }catch(e){}
    }
    btn.addEventListener("click",function(){
      var v=(em&&em.value||"").trim();
      var vn=(nm&&nm.value||"").trim();
      if(!_validName(vn)){ _showErrName("Nome obrigatório — informe seu nome (2–100 letras). / Name required — enter your name (2–100 letters)."); try{nm.focus();}catch(e){} return; }
      if(errName) errName.textContent="";
      if(!_validMail(v)){ _showErr("E-mail obrigatório — informe um e-mail válido para continuar. / E-mail required — enter a valid e-mail to continue."); try{em.focus();}catch(e){} return; }
      if(err) err.textContent="";
      localStorage.setItem("ufvai_terms_version",_TV);
      localStorage.setItem("ufvai_analytics", an.checked?"1":"0");
      // v0.6.20-fix: o aceite NÃO grava mais linha "novo_contato" na
      // planilha. A ÚNICA linha vem do heartbeat "usuario_ativo" (com IP),
      // disparado pelo clique deste botão APÓS o consent ser processado.
      _post(true, an.checked, v, vn, _heartbeat);
      ov.style.display="none";
      if(_autofillTimer){ clearInterval(_autofillTimer); _autofillTimer=null; }
      // v0.6.9: telemetria ativa por padrão — liga o GA se NÃO desmarcada (opt-out)
      if(an.checked && typeof window._ufvaiGaStart==="function"){ try{ window._ufvaiGaStart(); }catch(e){} }
    });
    document.getElementById("t-decline-btn").addEventListener("click",function(){
      _post(false,false);
      ov.innerHTML='<div class="t-card"><div class="t-brand"><b>UFV</b><em>AI</em></div>'+
        '<p style="font-size:13px;line-height:1.6">Você optou por não aceitar os Termos de Uso.<br>'+
        'A interface permanecerá bloqueada. Feche esta aba para encerrar.<br><br>'+
        '<span style="opacity:.75">You declined the Terms of Use — the UI stays locked. Close this tab to exit.</span></p></div>';
    });
    // ── v0.6.10: PRÉ-PREENCHIMENTO — perfil persistente (backups/ufvai_consentimento.json) ──
    try{
      // v0.6.10: overlay "Bem-vindo de volta" — referências (nome + e-mail)
      var wov=document.getElementById("welcome-overlay");
      var wOk=document.getElementById("w-ok-btn");
      var wSwitch=document.getElementById("w-switch-btn");
      var wEmail=document.getElementById("w-email");
      function _showWelcome(email, name){
        if(!wov) return false;
        // Correção 23/10/2026: a tela "Bem-vindo de volta" aparece UMA vez
        // por aba. Antes ela voltava a cada recarga — e a sincronização de
        // idioma recarrega a página — então o usuário via a mesma tela
        // duas (ou várias) vezes na mesma entrada.
        // v0.7.5: a marca vai para sessionStorage + localStorage + cookie
        // (o iframe do Colab pode bloquear um ou dois) e é gravada ANTES
        // de exibir; recargas internas não a consomem.
        try{
          if(window.ufvaiOpeningGet && window.ufvaiOpeningGet("welcome")) return false;
        }catch(e){}
        try{
          var txt="";
          if(name && email) txt=name + " — " + email;
          else if(email) txt=email;
          else if(name) txt=name;
          else txt="—";
          if(wEmail) wEmail.textContent=txt;
        }catch(e){}
        try{ if(window.ufvaiOpeningMark) window.ufvaiOpeningMark("welcome"); }catch(e){}
        wov.style.display="flex";
        return true;
      }
      function _hideWelcome(){
        try{ if(wov) wov.style.display="none"; }catch(e){}
      }
      // "Continuar" → heartbeat de acesso ativo (e-mail + hora + flag + IP) — v0.6.16: APENAS no clique
      if(wOk){
        wOk.addEventListener("click",function(){
          try{ _heartbeat(); }catch(e){}
          _hideWelcome();
          if(_autofillTimer){ clearInterval(_autofillTimer); _autofillTimer=null; }
        });
      }
      // "Se não é você" → abre os Termos com os campos nome/e-mail editáveis
      if(wSwitch){
        wSwitch.addEventListener("click",function(){
          _hideWelcome();
          var wTxt=(wEmail&&wEmail.textContent)||"";
          // tenta separar nome — email quando exibido como "Nome — email"
          var curEmail=wTxt, curName="";
          if(wTxt.indexOf(" — ")!==-1){ var parts=wTxt.split(" — "); curName=parts[0]||""; curEmail=parts[1]||""; }
          else if(wTxt.indexOf("@")!==-1){ curEmail=wTxt; }
          else if(wTxt!=="—"){ curName=wTxt; }
          if(nm && !nm.value && curName) nm.value=curName;
          if(em && !em.value && curEmail && curEmail!=="—") em.value=curEmail;
          // fallback: busca direto do profile carregado
          try{
            if(nm && profName && !nm.value) nm.value=profName;
            if(em && (d&&d.profile&&d.profile.email) && !em.value) em.value=d.profile.email;
          }catch(e){}
          if(an && typeof profAnalytics!=="undefined"){ an.checked=!!profAnalytics; }
          if(chk){ chk.checked=true; }
          _shown=true;               /* 23/10/2026: abertura deliberada */
          ov.style.display="flex";
          _updateBtn();
          try{ if(nm && !nm.value) setTimeout(function(){ nm.focus(); },260);
               else if(em) setTimeout(function(){ em.focus(); em.select(); },260); }catch(e){}
        });
      }
      var profName=""; // para uso no switch
      fetch("/api/consent").then(function(r){return r.json();}).then(function(d){
        var prof=(d&&d.profile)||{};
        profAnalytics=prof.analytics;
        profName=(prof.name||prof.nome||"");
        // Já aceitou ESTA versão (perfil sobrevive à sessão)?
        // v0.6.10: mostra "Bem-vindo de volta" com nome + e-mail
        if(prof.accepted && prof.terms_version===_TV){
          localStorage.setItem("ufvai_terms_version",_TV);
          localStorage.setItem("ufvai_analytics", prof.analytics?"1":"0");
          if(prof.analytics && typeof window._ufvaiGaStart==="function"){ try{ window._ufvaiGaStart(); }catch(e){} }
          if(!_showWelcome(prof.email, profName)){
            return; // sem overlay (fallback): segue sem exibir nada
          }
          // v0.6.16: heartbeat APENAS no clique "Continuar" (não automático ao exibir o welcome)
          return;
        }
        // 23/10/2026: este navegador já aceitou a versão atual dos Termos —
        // não reabre a tela se o perfil do servidor estiver ausente/atrasado
        // (Drive off-line, POST interrompido). Antes, a tela voltava a cada
        // recarga e o usuário via o aceite "duas vezes".
        if(localStorage.getItem("ufvai_terms_version")===_TV){ return; }
        // Sessão anterior (versão antiga dos Termos): pré-preenche nome+e-mail e só confirma
        if(profName && nm && !nm.value){ nm.value=profName; }
        if(prof.email && em && !em.value){ em.value=prof.email; }
        if(an && typeof prof.analytics!=="undefined"){ an.checked=!!prof.analytics; }
        if(chk){ chk.checked=true; }
        _openTerms();
      }).catch(function(){ _openTerms(); });
    }catch(e){ _openTerms(); }
  }catch(e){}
})();
</script>

<!-- ═══ Google tag (gtag.js) — GA4 client-side · v0.6.4 ═══
     ID: {__GA_MEASUREMENT_ID__} · Carregado APENAS após aceite dos Termos com
     opt-in de estatísticas (LGPD art. 7º I). Sem consentimento: nada é carregado,
     nenhum cookie _ga é criado, nenhuma requisição ao googletagmanager sai. -->
<script>
(function(){
  var MID="{__GA_MEASUREMENT_ID__}", IS_COLAB={__IS_COLAB__};
  if(!MID) return;
  var loaded=false;
  function _start(){
    if(loaded) return; loaded=true;
    try{
      window.dataLayer=window.dataLayer||[];
      window.gtag=function(){window.dataLayer.push(arguments);};
      var s=document.createElement("script");s.async=true;
      s.src="https://www.googletagmanager.com/gtag/js?id="+MID;
      document.head.appendChild(s);
      gtag('js',new Date());
      // v0.6.9: telemetria ativa por padrão (opt-out) e SEM cookie —
      // analytics_storage:'denied' impede o cookie _ga no dispositivo do
      // usuário (base: legítimo interesse, LGPD art. 7º IX; oposição art. 18 §2º).
      gtag('config',MID,{send_page_view:true,anonymize_ip:true,analytics_storage:'denied'});
      // v0.6.9: coleta resumida aos DADOS PADRÃO do Analytics (page_view) —
      // evento custom ufvai_session removido.
    }catch(e){}
  }
  window._ufvaiGaStart=_start;
  try{
    // v0.6.10: opt-out — inicia se o aceite da versão atual existir E o usuário
    // NÃO tiver desativado as estatísticas ("0"). undefined/"1" = ativo.
    if(localStorage.getItem("ufvai_terms_version")==="6" &&
       localStorage.getItem("ufvai_analytics")!=="0"){
      setTimeout(_start,1200); // deixa a UI carregar primeiro
    }
  }catch(e){}
})();
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
    # v0.6.8: garantir que qualquer variante do placeholder seja substituída
    # (screenshot mostrava v__UFVAI_VERSION__ literal por cache/branch antigo)
    html = html.replace("__UFVAI_VERSION__", VERSION)
    html = html.replace("__VERSION__", VERSION)
    html = html.replace("v__UFVAI_VERSION__", f"v{VERSION}")
    html = html.replace("__UFVAI_TOKEN__", session_token or "")
    html = html.replace("{__BOOT_ID__}", boot_id)
    html = html.replace("{RESPONSIVE_CSS}", RESPONSIVE_CSS)
    # v0.6.4: GA4 client-side (gtag.js) — ID do admin (env > default embutido);
    # vazio desliga o canal client-side (fica só o Measurement Protocol).
    _ga_id = os.environ.get("UFVAI_GA_MEASUREMENT_ID", "G-CMVTFP2M6F").strip()
    html = html.replace("{__GA_MEASUREMENT_ID__}", _ga_id)
    html = html.replace("{__IS_COLAB__}", "true" if os.path.isdir("/content") else "false")

    i18n_inline: dict[str, dict[str, str]] = {
        "pt_BR": {
            "ui.backup": "Salvar backup", "ui.restore": "Restaurar",
            "ui.sair": "SAIR",
            "sair.title": "Encerrar sessão", "sair.confirm_q": "Desconectar e excluir o ambiente de execução?", "sair.warn": "Tudo em memória será perdido — os arquivos no seu Google Drive continuam salvos. Não há como desfazer após confirmar.", "sair.yes": "SIM, SAIR", "sair.status": "Encerrando o ambiente… aguarde", "sair.fail": "Falha ao encerrar — use Runtime ▸ Desconectar e excluir ambiente.", "sair.done": "✅ Ambiente encerrado. Para usar o UFVAI de novo: reexecute a célula de boot.",
            "ui.drive": "Drive", "ui.close": "Fechar", "ui.cancel": "Cancelar",
            "ui.loading": "Carregando…", "ui.status_active": "agente ativo",
            "ui.exporting": "Exportando sessão…",
            "autosave.title": "Autosave", "autosave.saved": "Sessão salva no Drive",
            "autosave.unchanged": "Sem novidades — o autosave mais recente já é o atual.",
            "autosave.off_msg": "Autosave desligado",
            "autosave.all": "Todas as conversas",
            "autosave.all_on": "Todos os arquivos de conversa passarão a ser salvos no Drive.",
            "autosave.all_off": "O autosave voltará a salvar só a sessão ativa.",
            "autosave.resume.title": "Retomar sessão",
            "autosave.resume.text": "Há um salvamento automático. Deseja continuar a partir dele ou iniciar uma nova sessão?",
            "autosave.resume.when": "Autosave de",
            "autosave.resume.continue": "Continuar de onde parei",
            "autosave.resume.new": "Nova sessão",
            "autosave.resume.restoring": "Restaurando o último autosave…",
            "autosave.resume.done": "Sessão restaurada",
            "autosave.resume.none": "Nenhum autosave válido",
            "restore.count": "{total} backups",
            "restore.summary_filtered": "{shown} de {total} backups",
            "restore.all_dates": "Todas as datas",
            "restore.today": "Hoje",
            "restore.prev": "Mês anterior",
            "restore.next": "Próximo mês",
            "restore.filter": "Filtrar por data",
            "restore.dow.0": "S", "restore.dow.1": "T", "restore.dow.2": "Q",
            "restore.dow.3": "Q", "restore.dow.4": "S", "restore.dow.5": "S",
            "restore.dow.6": "D",
            "restore.empty": "Nenhum backup encontrado no Drive.",
            "restore.empty_date": "Nenhum backup nesta data.",
            "restore.error": "Erro ao carregar os backups.",
            "restore.autosave": "Autossave",
            "restore.day_tip": "{n} backups",
            "restore.month_tip": "{n} backups em {m}",
            "restore.nodate": "sem data",
            "restore.newest": "Mais recente",
            "autosave.resume.again": "Retomar",
            "restore.invalid": "corrompido",
            "restore.confirm": "Restaurar o backup de {when}?",
            "restore.done": "Sessão restaurada",
            "restore.partial": "{n} mensagens antigas omitidas para caber no contexto",
            "restore.restoring": "Restaurando {when}…",
            "restore.delete": "apagar",
            "restore.delete_confirm": "Apagar o backup de {when}? Esta ação não pode ser desfeita.",
            "restore.deleting": "Apagando {when}…",
            "restore.deleted": "Backup apagado.",
            "restore.delete_failed": "Falha ao apagar o backup.",
            "dashboard.title": "Dashboard de Saúde",
            "providers.title": "Conectar Provedor de IA",
            "providers.select": "Selecione o provedor para configurar a API key:",
            "providers.saved_keys": "Chaves salvas no Drive:",
            "providers.add_new": "Novo provedor",
            "providers.search": "Buscar provedor…",
            "providers.api_key": "API KEY", "providers.back": "← Voltar",
            "providers.save_connect": "Salvar e Conectar",
            "providers.var": "Variável",
            "providers.key_required": "Insira a API key.",
            "providers.select_required": "Selecione um provedor.",
            "providers.saving": "Salvando…",
            "providers.connected": "conectado",
            "providers.updated": "atualizado",
            "providers.no_saved_keys": "Nenhuma chave salva ainda.",
            "providers.edit": "Editar",
            "providers.delete": "Excluir",
            "providers.confirm_delete": "Excluir chave de",
            "providers.deleted": "excluído",
            "sessions.refresh": "↻ Atualizar",
            "sessions.title": "Histórico de Sessões",
            "sessions.search_placeholder": "🔍 Buscar por id ou conteúdo…",
            "shortcuts.title": "Atalhos de Teclado",
            "shortcuts.copy": "Copiar seleção", "shortcuts.copy_hint": "Segure o Shift e selecione",
            "shortcuts.interrupt": "Interromper comando", "shortcuts.paste": "Colar (Chrome)",
            "shortcuts.menu": "Menu e opções", "shortcuts.model": "Alterar modelo",
            "shortcuts.history_prev": "Histórico anterior", "shortcuts.history_next": "Histórico seguinte",
            "theme.toggle": "Alternar tema", "theme.light": "Tema claro (UI + terminal)",
            "theme.dark": "Tema escuro (UI + terminal)",
            "theme.terminal_reloaded": "Terminal recarregado com novo tema",
            # v0.6.5 — Splash de carregamento do terminal
            "boot.starting": "Iniciando terminal…",
            "boot.restarting": "Reiniciando terminal…",
            "boot.restoring": "Restaurando sessão…",
            "boot.timeout": "O terminal não respondeu. Verifique ~/PesquisAI/logs/ttyd.log e recarregue.",
            "boot.failed": "Falha ao reiniciar o terminal. Tente novamente.",
            "boot.retry": "↻ Recarregar",
            "languages.label": "Idioma", "languages.switched_to": "Idioma alterado para",
            "languages.pt_BR": "Português (Brasil)", "languages.en_US": "Inglês (Estados Unidos)",
            "languages.es_ES": "Espanhol (Espanha)", "languages.fr_FR": "Francês (França)",
            "languages.zh_CN": "Chinês (simplificado)",
            "success_messages.backup_saved": "Backup salvo",
            # v0.5.1.2 — Memória UFVAI
            "memory.title": "Memória UFVAI",
            "telemetry.title": "Telemetria (Admin)",
            "memory.subtitle": "Camada de memória persistente do agente",
            "memory.tooltip": "Memória UFVAI (segundo cérebro)",
            "memory.status_ready": "🟢 Ativa",
            "memory.status_disabled": "⚪ Desativada",
            "memory.status_no_vault": "🟡 Sem vault",
            "memory.status_read_only": "🟡 Somente leitura",
            "memory.status_error": "🔴 Erro",
            "memory.notes_count": "Notas",
            "memory.notes_unit": "",
            "memory.tags_count": "Tags",
            "memory.links_count": "Wikilinks",
            "memory.avg_len": "Tam. médio",
            "memory.recent_daily": "Daily notes",
            "memory.recent_notes": "Notas recentes",
            "memory.no_notes": "Nenhuma nota ainda. O agente salvará aqui automaticamente.",
            "memory.templates": "Templates",
            "memory.open_vault": "Abrir Drive",
            "memory.refresh": "Atualizar",
            # v0.5.1.4 — Editor de notas (split view)
            "memory.search_placeholder": "🔍 Buscar…",
            "memory.new_note": "+ Nova nota",
            "memory.new_note_title": "Nova nota",
            "memory.new_note_dialog_title": "📝 Nova nota",
            "memory.field_path": "Caminho (ex: research/minha-nota.md)",
            "memory.field_title": "Título",
            "memory.field_template": "Template",
            "memory.field_tags": "Tags (separadas por vírgula, opcional)",
            "memory.create": "Criar",
            "memory.save": "💾 Salvar",
            "memory.delete": "🗑 Excluir",
            "memory.tab_edit": "Editar",
            "memory.tab_preview": "Preview",
            "memory.tab_split": "Dividido",
            "memory.body_placeholder": "Selecione uma nota à esquerda ou crie uma nova.",
            "memory.empty_editor": "Selecione uma nota na lista ou crie uma nova.",
            "memory.dirty": "não salvo",
            "memory.note_title": "Título",
            "memory.no_results": "Nenhum resultado para a busca.",
            # v0.5.1.2 hotfix — Diretrizes do Agente
            "agents.title": "Diretrizes do Agente",
            "manual.title": "Manual do UFVAI",
            "manual.subtitle": "Guia completo de uso (MANUAL.md)",
            "manual.loading": "Carregando manual…",
            "manual.error": "Manual não encontrado localmente.",
            "manual.open_source": "Abrir no GitHub",
            "agents.subtitle": "Regras e princípios do UFVAI (AGENTS.md)",
            "agents.loading": "Carregando diretrizes…",
            "agents.error": "Erro ao carregar diretrizes do agente.",
            "agents.copy_ok": "Diretrizes copiadas!",
            "agents.copy": "Copiar",
            "agents.open_source": "Ver fonte",
        },
        "en_US": {
            "ui.backup": "Save backup", "ui.restore": "Restore",
            "ui.sair": "EXIT",
            "sair.title": "End session", "sair.confirm_q": "Disconnect and delete the execution environment?", "sair.warn": "Everything in memory will be lost — files on your Google Drive remain saved. Cannot be undone once confirmed.", "sair.yes": "YES, EXIT", "sair.status": "Shutting down the environment… please wait", "sair.fail": "Failed to shut down — use Runtime ▸ Disconnect and delete runtime.", "sair.done": "✅ Environment terminated. To use UFVAI again: re-run the boot cell.",
            "ui.drive": "Drive", "ui.close": "Close", "ui.cancel": "Cancel",
            "ui.loading": "Loading…", "ui.status_active": "agent active",
            "ui.exporting": "Exporting session…",
            "autosave.title": "Autosave", "autosave.saved": "Session saved to Drive",
            "autosave.unchanged": "No changes — the latest autosave is already up to date.",
            "autosave.off_msg": "Autosave off",
            "autosave.all": "All conversations",
            "autosave.all_on": "All conversation files will now be saved to Drive.",
            "autosave.all_off": "Autosave will go back to saving only the active session.",
            "autosave.resume.title": "Resume session",
            "autosave.resume.text": "There is an automatic save. Do you want to continue from it or start a new session?",
            "autosave.resume.when": "Autosave from",
            "autosave.resume.continue": "Continue where I left off",
            "autosave.resume.new": "New session",
            "autosave.resume.restoring": "Restoring the last autosave…",
            "autosave.resume.done": "Session restored",
            "autosave.resume.none": "No valid autosave",
            "restore.count": "{total} backups",
            "restore.summary_filtered": "{shown} of {total} backups",
            "restore.all_dates": "All dates",
            "restore.today": "Today",
            "restore.prev": "Previous month",
            "restore.next": "Next month",
            "restore.filter": "Filter by date",
            "restore.dow.0": "M", "restore.dow.1": "T", "restore.dow.2": "W",
            "restore.dow.3": "T", "restore.dow.4": "F", "restore.dow.5": "S",
            "restore.dow.6": "S",
            "restore.empty": "No backup found in Drive.",
            "restore.empty_date": "No backup on this date.",
            "restore.error": "Error loading the backups.",
            "restore.autosave": "Autosave",
            "restore.day_tip": "{n} backups",
            "restore.month_tip": "{n} backups in {m}",
            "restore.nodate": "no date",
            "restore.newest": "Newest",
            "autosave.resume.again": "Resume",
            "restore.invalid": "corrupted",
            "restore.confirm": "Restore the backup from {when}?",
            "restore.done": "Session restored",
            "restore.partial": "{n} older messages omitted to fit the context",
            "restore.restoring": "Restoring {when}…",
            "restore.delete": "delete",
            "restore.delete_confirm": "Delete the backup from {when}? This action cannot be undone.",
            "restore.deleting": "Deleting {when}…",
            "restore.deleted": "Backup deleted.",
            "restore.delete_failed": "Failed to delete the backup.",
            "dashboard.title": "Health Dashboard",
            "providers.title": "Connect AI Provider",
            "providers.select": "Select the provider to configure the API key:",
            "providers.saved_keys": "Keys saved on Drive:",
            "providers.add_new": "New provider",
            "providers.search": "Search provider…",
            "providers.api_key": "API KEY", "providers.back": "← Back",
            "providers.save_connect": "Save and Connect",
            "providers.var": "Variable",
            "providers.key_required": "Enter the API key.",
            "providers.select_required": "Select a provider.",
            "providers.saving": "Saving…",
            "providers.connected": "connected",
            "providers.updated": "updated",
            "providers.no_saved_keys": "No saved keys yet.",
            "providers.edit": "Edit",
            "providers.delete": "Delete",
            "providers.confirm_delete": "Delete key for",
            "providers.deleted": "deleted",
            "sessions.refresh": "↻ Refresh",
            "sessions.title": "Session History",
            "sessions.search_placeholder": "🔍 Search by id or content…",
            "shortcuts.title": "Keyboard Shortcuts",
            "shortcuts.copy": "Copy selection", "shortcuts.copy_hint": "Hold Shift and select",
            "shortcuts.interrupt": "Interrupt command", "shortcuts.paste": "Paste (Chrome)",
            "shortcuts.menu": "Menu and options", "shortcuts.model": "Change model",
            "shortcuts.history_prev": "Previous history", "shortcuts.history_next": "Next history",
            "theme.toggle": "Toggle theme", "theme.light": "Light theme (UI + terminal)",
            "theme.dark": "Dark theme (UI + terminal)",
            "theme.terminal_reloaded": "Terminal reloaded with new theme",
            # v0.6.5 — Terminal boot splash
            "boot.starting": "Starting the terminal…",
            "boot.restarting": "Restarting the terminal…",
            "boot.restoring": "Restoring session…",
            "boot.timeout": "The terminal did not respond. Check ~/PesquisAI/logs/ttyd.log and reload.",
            "boot.failed": "Failed to restart the terminal. Please try again.",
            "boot.retry": "↻ Reload",
            "languages.label": "Language", "languages.switched_to": "Language switched to",
            "languages.pt_BR": "Portuguese (Brazil)", "languages.en_US": "English (United States)",
            "languages.es_ES": "Spanish (Spain)", "languages.fr_FR": "French (France)",
            "languages.zh_CN": "Chinese (Simplified)",
            "success_messages.backup_saved": "Backup saved",
            # v0.5.1.2 — PesquisAI Memory
            "memory.title": "UFVAI Memory",
            "telemetry.title": "Telemetry (Admin)",
            "memory.subtitle": "Agent's persistent memory layer",
            "memory.tooltip": "UFVAI Memory (second brain)",
            "memory.status_ready": "🟢 Active",
            "memory.status_disabled": "⚪ Disabled",
            "memory.status_no_vault": "🟡 No vault",
            "memory.status_read_only": "🟡 Read-only",
            "memory.status_error": "🔴 Error",
            "memory.notes_count": "Notes",
            "memory.notes_unit": "",
            "memory.tags_count": "Tags",
            "memory.links_count": "Wikilinks",
            "memory.avg_len": "Avg. length",
            "memory.recent_daily": "Daily notes",
            "memory.recent_notes": "Recent notes",
            "memory.no_notes": "No notes yet. The agent will save here automatically.",
            "memory.templates": "Templates",
            "memory.open_vault": "Open Drive",
            "memory.refresh": "Refresh",
            # v0.5.1.4 — Note editor (split view)
            "memory.search_placeholder": "🔍 Search…",
            "memory.new_note": "+ New note",
            "memory.new_note_title": "New note",
            "memory.new_note_dialog_title": "📝 New note",
            "memory.field_path": "Path (e.g. research/my-note.md)",
            "memory.field_title": "Title",
            "memory.field_template": "Template",
            "memory.field_tags": "Tags (comma-separated, optional)",
            "memory.create": "Create",
            "memory.save": "💾 Save",
            "memory.delete": "🗑 Delete",
            "memory.tab_edit": "Edit",
            "memory.tab_preview": "Preview",
            "memory.tab_split": "Split",
            "memory.body_placeholder": "Select a note on the left or create a new one.",
            "memory.empty_editor": "Select a note from the list or create a new one.",
            "memory.dirty": "unsaved",
            "memory.note_title": "Title",
            "memory.no_results": "No results for the search.",
            # v0.5.1.2 hotfix — Agent Guidelines
            "agents.title": "Agent Guidelines",
            "manual.title": "UFVAI Manual",
            "manual.subtitle": "Complete user guide (MANUAL.md)",
            "manual.loading": "Loading manual…",
            "manual.error": "Manual not found locally.",
            "manual.open_source": "Open on GitHub",
            "agents.subtitle": "UFVAI rules and principles (AGENTS.md)",
            "agents.loading": "Loading guidelines…",
            "agents.error": "Error loading agent guidelines.",
            "agents.copy_ok": "Guidelines copied!",
            "agents.copy": "Copy",
            "agents.open_source": "View source",
        },
        "es_ES": {
            "ui.backup": "Guardar copia", "ui.restore": "Restaurar",
            "ui.sair": "SALIR",
            "sair.title": "Cerrar sesión", "sair.confirm_q": "¿Desconectar y eliminar el entorno de ejecución?", "sair.warn": "Todo en memoria se perderá — los archivos de tu Google Drive siguen guardados. No se puede deshacer tras confirmar.", "sair.yes": "SÍ, SALIR", "sair.status": "Cerrando el entorno… espere", "sair.fail": "Error al cerrar — usa Runtime ▸ Desconectar y eliminar el entorno.", "sair.done": "✅ Entorno cerrado. Para usar UFVAI de nuevo: reejecuta la celda de arranque.",
            "ui.drive": "Drive", "ui.close": "Cerrar", "ui.cancel": "Cancelar",
            "ui.loading": "Cargando…", "ui.status_active": "agente activo",
            "ui.exporting": "Exportando sesión…",
            "autosave.title": "Autoguardado", "autosave.saved": "Sesión guardada en Drive",
            "autosave.unchanged": "Sin novedades — el autoguardado más reciente ya es el actual.",
            "autosave.off_msg": "Autoguardado desactivado",
            "autosave.all": "Todas las conversaciones",
            "autosave.all_on": "Ahora se guardarán todos los archivos de conversación en Drive.",
            "autosave.all_off": "El autoguardado volverá a guardar solo la sesión activa.",
            "autosave.resume.title": "Reanudar sesión",
            "autosave.resume.text": "Hay un guardado automático. ¿Desea continuar desde él o iniciar una sesión nueva?",
            "autosave.resume.when": "Autoguardado del",
            "autosave.resume.continue": "Continuar donde lo dejé",
            "autosave.resume.new": "Sesión nueva",
            "autosave.resume.restoring": "Restaurando el último autoguardado…",
            "autosave.resume.done": "Sesión restaurada",
            "autosave.resume.none": "Ningún autoguardado válido",
            "restore.count": "{total} copias",
            "restore.summary_filtered": "{shown} de {total} copias",
            "restore.all_dates": "Todas las fechas",
            "restore.today": "Hoy",
            "restore.prev": "Mes anterior",
            "restore.next": "Mes siguiente",
            "restore.filter": "Filtrar por fecha",
            "restore.dow.0": "L", "restore.dow.1": "M", "restore.dow.2": "X",
            "restore.dow.3": "J", "restore.dow.4": "V", "restore.dow.5": "S",
            "restore.dow.6": "D",
            "restore.empty": "No se encontró ninguna copia en Drive.",
            "restore.empty_date": "No hay copias en esta fecha.",
            "restore.error": "Error al cargar las copias.",
            "restore.autosave": "Autoguardado",
            "restore.day_tip": "{n} respaldos",
            "restore.month_tip": "{n} respaldos en {m}",
            "restore.nodate": "sin fecha",
            "restore.newest": "Más reciente",
            "autosave.resume.again": "Reanudar",
            "restore.invalid": "corrupto",
            "restore.confirm": "¿Restaurar la copia del {when}?",
            "restore.done": "Sesión restaurada",
            "restore.partial": "{n} mensajes antiguos omitidos para caber en el contexto",
            "restore.restoring": "Restaurando {when}…",
            "restore.delete": "borrar",
            "restore.delete_confirm": "¿Borrar la copia del {when}? Esta acción no se puede deshacer.",
            "restore.deleting": "Borrando {when}…",
            "restore.deleted": "Copia borrada.",
            "restore.delete_failed": "No se pudo borrar la copia.",
            "dashboard.title": "Panel de Salud",
            "providers.title": "Conectar Proveedor de IA",
            "providers.select": "Seleccione el proveedor para configurar la API key:",
            "providers.saved_keys": "Claves guardadas en Drive:",
            "providers.add_new": "Nuevo proveedor",
            "providers.search": "Buscar proveedor…",
            "providers.api_key": "API KEY", "providers.back": "← Volver",
            "providers.save_connect": "Guardar y Conectar",
            "providers.var": "Variable",
            "providers.key_required": "Ingrese la API key.",
            "providers.select_required": "Seleccione un proveedor.",
            "providers.saving": "Guardando…",
            "providers.connected": "conectado",
            "providers.updated": "actualizado",
            "providers.no_saved_keys": "Aún no hay claves guardadas.",
            "providers.edit": "Editar",
            "providers.delete": "Eliminar",
            "providers.confirm_delete": "Eliminar clave de",
            "providers.deleted": "eliminado",
            "sessions.refresh": "↻ Actualizar",
            "sessions.title": "Historial de Sesiones",
            "sessions.search_placeholder": "🔍 Buscar por id o contenido…",
            "shortcuts.title": "Atajos de Teclado",
            "shortcuts.copy": "Copiar selección", "shortcuts.copy_hint": "Mantenga Shift y seleccione",
            "shortcuts.interrupt": "Interrumpir comando", "shortcuts.paste": "Pegar (Chrome)",
            "shortcuts.menu": "Menú y opciones", "shortcuts.model": "Cambiar modelo",
            "shortcuts.history_prev": "Historial anterior", "shortcuts.history_next": "Historial siguiente",
            "theme.toggle": "Alternar tema", "theme.light": "Tema claro (UI + terminal)",
            "theme.dark": "Tema oscuro (UI + terminal)",
            "theme.terminal_reloaded": "Terminal recargado con nuevo tema",
            # v0.6.5 — Splash de arranque del terminal
            "boot.starting": "Iniciando el terminal…",
            "boot.restarting": "Reiniciando el terminal…",
            "boot.restoring": "Restaurando sesión…",
            "boot.timeout": "El terminal no respondió. Revisa ~/PesquisAI/logs/ttyd.log y recarga.",
            "boot.failed": "No se pudo reiniciar el terminal. Inténtalo de nuevo.",
            "boot.retry": "↻ Recargar",
            "languages.label": "Idioma", "languages.switched_to": "Idioma cambiado a",
            "languages.pt_BR": "Portugués (Brasil)", "languages.en_US": "Inglés (Estados Unidos)",
            "languages.es_ES": "Español (España)", "languages.fr_FR": "Francés (Francia)",
            "languages.zh_CN": "Chino (simplificado)",
            "success_messages.backup_saved": "Copia guardada",
            # v0.5.1.2 — Memoria PesquisAI
            "memory.title": "Memoria UFVAI",
            "telemetry.title": "Telemetría (Admin)",
            "memory.subtitle": "Capa de memoria persistente del agente",
            "memory.tooltip": "Memoria UFVAI (segundo cerebro)",
            "memory.status_ready": "🟢 Activa",
            "memory.status_disabled": "⚪ Desactivada",
            "memory.status_no_vault": "🟡 Sin vault",
            "memory.status_read_only": "🟡 Solo lectura",
            "memory.status_error": "🔴 Error",
            "memory.notes_count": "Notas",
            "memory.notes_unit": "",
            "memory.tags_count": "Etiquetas",
            "memory.links_count": "Wikienlaces",
            "memory.avg_len": "Tam. medio",
            "memory.recent_daily": "Daily notes",
            "memory.recent_notes": "Notas recientes",
            "memory.no_notes": "Aún no hay notas. El agente guardará aquí automáticamente.",
            "memory.templates": "Plantillas",
            "memory.open_vault": "Abrir Drive",
            "memory.refresh": "Actualizar",
            # v0.5.1.4 — Editor de notas (split view)
            "memory.search_placeholder": "🔍 Buscar…",
            "memory.new_note": "+ Nueva nota",
            "memory.new_note_title": "Nueva nota",
            "memory.new_note_dialog_title": "📝 Nueva nota",
            "memory.field_path": "Ruta (ej: research/mi-nota.md)",
            "memory.field_title": "Título",
            "memory.field_template": "Plantilla",
            "memory.field_tags": "Etiquetas (separadas por coma, opcional)",
            "memory.create": "Crear",
            "memory.save": "💾 Guardar",
            "memory.delete": "🗑 Eliminar",
            "memory.tab_edit": "Editar",
            "memory.tab_preview": "Vista previa",
            "memory.tab_split": "Dividido",
            "memory.body_placeholder": "Selecciona una nota a la izquierda o crea una nueva.",
            "memory.empty_editor": "Selecciona una nota de la lista o crea una nueva.",
            "memory.dirty": "no guardado",
            "memory.note_title": "Título",
            "memory.no_results": "Sin resultados para la búsqueda.",
            # v0.5.1.2 hotfix — Directrices del Agente
            "agents.title": "Directrices del Agente",
            "manual.title": "Manual del UFVAI",
            "manual.subtitle": "Guía completa de uso (MANUAL.md)",
            "manual.loading": "Cargando manual…",
            "manual.error": "Manual no encontrado localmente.",
            "manual.open_source": "Abrir en GitHub",
            "agents.subtitle": "Reglas y principios del UFVAI (AGENTS.md)",
            "agents.loading": "Cargando directrices…",
            "agents.error": "Error al cargar las directrices del agente.",
            "agents.copy_ok": "¡Directrices copiadas!",
            "agents.copy": "Copiar",
            "agents.open_source": "Ver fuente",
        },
        "fr_FR": {
            "ui.backup": "Sauvegarder", "ui.restore": "Restaurer",
            "ui.sair": "QUITTER",
            "sair.title": "Terminer la session", "sair.confirm_q": "Déconnecter et supprimer l'environnement d'exécution ?", "sair.warn": "Tout en mémoire sera perdu — les fichiers de votre Google Drive restent sauvegardés. Irréversible après confirmation.", "sair.yes": "OUI, QUITTER", "sair.status": "Arrêt de l'environnement… veuillez patienter", "sair.fail": "Échec de l'arrêt — utilisez Runtime ▸ Déconnecter et supprimer l'environnement.", "sair.done": "✅ Environnement terminé. Pour réutiliser UFVAI : relancez la cellule de démarrage.",
            "ui.drive": "Drive", "ui.close": "Fermer", "ui.cancel": "Annuler",
            "ui.loading": "Chargement…", "ui.status_active": "agent actif",
            "ui.exporting": "Exportation de la session…",
            "autosave.title": "Sauvegarde auto", "autosave.saved": "Session enregistrée sur Drive",
            "autosave.unchanged": "Aucune nouveauté — la sauvegarde auto la plus récente est déjà à jour.",
            "autosave.off_msg": "Sauvegarde auto désactivée",
            "autosave.all": "Toutes les conversations",
            "autosave.all_on": "Tous les fichiers de conversation seront désormais enregistrés sur Drive.",
            "autosave.all_off": "La sauvegarde automatique reviendra à ne enregistrer que la session active.",
            "autosave.resume.title": "Reprendre la session",
            "autosave.resume.text": "Une sauvegarde automatique existe. Voulez-vous continuer à partir d’elle ou démarrer une nouvelle session ?",
            "autosave.resume.when": "Sauvegarde auto du",
            "autosave.resume.continue": "Continuer où j’en étais",
            "autosave.resume.new": "Nouvelle session",
            "autosave.resume.restoring": "Restauration de la dernière sauvegarde auto…",
            "autosave.resume.done": "Session restaurée",
            "autosave.resume.none": "Aucune sauvegarde auto valide",
            "restore.count": "{total} sauvegardes",
            "restore.summary_filtered": "{shown} sur {total} sauvegardes",
            "restore.all_dates": "Toutes les dates",
            "restore.today": "Aujourd'hui",
            "restore.prev": "Mois précédent",
            "restore.next": "Mois suivant",
            "restore.filter": "Filtrer par date",
            "restore.dow.0": "L", "restore.dow.1": "M", "restore.dow.2": "M",
            "restore.dow.3": "J", "restore.dow.4": "V", "restore.dow.5": "S",
            "restore.dow.6": "D",
            "restore.empty": "Aucune sauvegarde trouvée dans Drive.",
            "restore.empty_date": "Aucune sauvegarde à cette date.",
            "restore.error": "Erreur lors du chargement des sauvegardes.",
            "restore.autosave": "Sauvegarde auto",
            "restore.day_tip": "{n} sauvegardes",
            "restore.month_tip": "{n} sauvegardes en {m}",
            "restore.nodate": "sans date",
            "restore.newest": "Plus récent",
            "autosave.resume.again": "Reprendre",
            "restore.invalid": "corrompu",
            "restore.confirm": "Restaurer la sauvegarde du {when} ?",
            "restore.done": "Session restaurée",
            "restore.partial": "{n} messages anciens omis pour tenir dans le contexte",
            "restore.restoring": "Restauration de {when}…",
            "restore.delete": "supprimer",
            "restore.delete_confirm": "Supprimer la sauvegarde du {when} ? Cette action est irréversible.",
            "restore.deleting": "Suppression de {when}…",
            "restore.deleted": "Sauvegarde supprimée.",
            "restore.delete_failed": "Échec de la suppression de la sauvegarde.",
            "dashboard.title": "Tableau de bord de santé",
            "providers.title": "Connecter un fournisseur d'IA",
            "providers.select": "Sélectionnez le fournisseur pour configurer la clé API:",
            "providers.saved_keys": "Clés enregistrées sur Drive:",
            "providers.add_new": "Nouveau fournisseur",
            "providers.search": "Rechercher un fournisseur…",
            "providers.api_key": "CLÉ API", "providers.back": "← Retour",
            "providers.save_connect": "Enregistrer et connecter",
            "providers.var": "Variable",
            "providers.key_required": "Entrez la clé API.",
            "providers.select_required": "Sélectionnez un fournisseur.",
            "providers.saving": "Enregistrement…",
            "providers.connected": "connecté",
            "providers.updated": "mis à jour",
            "providers.no_saved_keys": "Aucune clé enregistrée pour l'instant.",
            "providers.edit": "Modifier",
            "providers.delete": "Supprimer",
            "providers.confirm_delete": "Supprimer la clé de",
            "providers.deleted": "supprimé",
            "sessions.refresh": "↻ Actualiser",
            "sessions.title": "Historique des sessions",
            "sessions.search_placeholder": "🔍 Rechercher par id ou contenu…",
            "shortcuts.title": "Raccourcis clavier",
            "shortcuts.copy": "Copier la sélection", "shortcuts.copy_hint": "Maintenez Shift et sélectionnez",
            "shortcuts.interrupt": "Interrompre la commande", "shortcuts.paste": "Coller (Chrome)",
            "shortcuts.menu": "Menu et options", "shortcuts.model": "Changer de modèle",
            "shortcuts.history_prev": "Historique précédent", "shortcuts.history_next": "Historique suivant",
            "theme.toggle": "Basculer le thème", "theme.light": "Thème clair (UI + terminal)",
            "theme.dark": "Thème sombre (UI + terminal)",
            "theme.terminal_reloaded": "Terminal rechargé avec le nouveau thème",
            # v0.6.5 — Écran de démarrage du terminal
            "boot.starting": "Démarrage du terminal…",
            "boot.restarting": "Redémarrage du terminal…",
            "boot.restoring": "Restauration de la session…",
            "boot.timeout": "Le terminal n'a pas répondu. Consultez ~/PesquisAI/logs/ttyd.log puis rechargez.",
            "boot.failed": "Échec du redémarrage du terminal. Veuillez réessayer.",
            "boot.retry": "↻ Recharger",
            "languages.label": "Langue", "languages.switched_to": "Langue changée en",
            "languages.pt_BR": "Portugais (Brésil)", "languages.en_US": "Anglais (États-Unis)",
            "languages.es_ES": "Espagnol (Espagne)", "languages.fr_FR": "Français (France)",
            "languages.zh_CN": "Chinois (simplifié)",
            "success_messages.backup_saved": "Sauvegarde enregistrée",
            # v0.5.1.2 — Mémoire PesquisAI
            "memory.title": "Mémoire UFVAI",
            "telemetry.title": "Télémétrie (Admin)",
            "memory.subtitle": "Couche de mémoire persistante de l'agent",
            "memory.tooltip": "Mémoire UFVAI (deuxième cerveau)",
            "memory.status_ready": "🟢 Active",
            "memory.status_disabled": "⚪ Désactivée",
            "memory.status_no_vault": "🟡 Pas de vault",
            "memory.status_read_only": "🟡 Lecture seule",
            "memory.status_error": "🔴 Erreur",
            "memory.notes_count": "Notes",
            "memory.notes_unit": "",
            "memory.tags_count": "Étiquettes",
            "memory.links_count": "Wikiliens",
            "memory.avg_len": "Taille moy.",
            "memory.recent_daily": "Daily notes",
            "memory.recent_notes": "Notes récentes",
            "memory.no_notes": "Aucune note pour l'instant. L'agent enregistrera ici automatiquement.",
            "memory.templates": "Modèles",
            "memory.open_vault": "Ouvrir Drive",
            "memory.refresh": "Actualiser",
            # v0.5.1.4 — Éditeur de notes (split view)
            "memory.search_placeholder": "🔍 Rechercher…",
            "memory.new_note": "+ Nouvelle note",
            "memory.new_note_title": "Nouvelle note",
            "memory.new_note_dialog_title": "📝 Nouvelle note",
            "memory.field_path": "Chemin (ex: research/ma-note.md)",
            "memory.field_title": "Titre",
            "memory.field_template": "Modèle",
            "memory.field_tags": "Étiquettes (séparées par virgule, optionnel)",
            "memory.create": "Créer",
            "memory.save": "💾 Enregistrer",
            "memory.delete": "🗑 Supprimer",
            "memory.tab_edit": "Éditer",
            "memory.tab_preview": "Aperçu",
            "memory.tab_split": "Divisé",
            "memory.body_placeholder": "Sélectionnez une note à gauche ou créez-en une nouvelle.",
            "memory.empty_editor": "Sélectionnez une note dans la liste ou créez-en une nouvelle.",
            "memory.dirty": "non enregistré",
            "memory.note_title": "Titre",
            "memory.no_results": "Aucun résultat pour la recherche.",
            # v0.5.1.2 hotfix — Directives de l'Agent
            "agents.title": "Directives de l'Agent",
            "manual.title": "Manuel du UFVAI",
            "manual.subtitle": "Guide complet d'utilisation (MANUAL.md)",
            "manual.loading": "Chargement du manuel…",
            "manual.error": "Manuel introuvable localement.",
            "manual.open_source": "Ouvrir sur GitHub",
            "agents.subtitle": "Règles et principes du UFVAI (AGENTS.md)",
            "agents.loading": "Chargement des directives…",
            "agents.error": "Erreur lors du chargement des directives de l'agent.",
            "agents.copy_ok": "Directives copiées !",
            "agents.copy": "Copier",
            "agents.open_source": "Voir la source",
        },
        "zh_CN": {
            "ui.backup": "保存备份", "ui.restore": "恢复",
            "ui.sair": "退出",
            "sair.title": "结束会话", "sair.confirm_q": "断开连接并删除执行环境？", "sair.warn": "内存中的所有内容都将丢失 — Google 云端硬盘中的文件仍会保存。确认后无法撤销。", "sair.yes": "确定，退出", "sair.status": "正在关闭环境…请稍候", "sair.fail": "关闭失败 — 请使用 Runtime ▸ 断开连接并删除环境。", "sair.done": "✅ 环境已终止。如需再次使用 UFVAI：重新运行引导单元。",
            "ui.drive": "云端硬盘", "ui.close": "关闭", "ui.cancel": "取消",
            "ui.loading": "加载中…", "ui.status_active": "智能体运行中",
            "ui.exporting": "正在导出会话…",
            "autosave.title": "自动保存", "autosave.saved": "会话已保存到 Drive",
            "autosave.unchanged": "没有新内容 —— 最近一次自动保存已是最新。",
            "autosave.off_msg": "已关闭自动保存",
            "autosave.all": "所有对话",
            "autosave.all_on": "现在将把所有对话文件保存到 Drive。",
            "autosave.all_off": "自动保存将恢复为只保存当前会话。",
            "autosave.resume.title": "恢复会话",
            "autosave.resume.text": "存在一个自动保存。要从它继续，还是开始新会话？",
            "autosave.resume.when": "自动保存于",
            "autosave.resume.continue": "继续上次进度",
            "autosave.resume.new": "新建会话",
            "autosave.resume.restoring": "正在恢复最近的自动保存…",
            "autosave.resume.done": "会话已恢复",
            "autosave.resume.none": "没有有效的自动保存",
            "restore.count": "{total} 个备份",
            "restore.summary_filtered": "{shown}/{total} 个备份",
            "restore.all_dates": "全部日期",
            "restore.today": "今天",
            "restore.prev": "上个月",
            "restore.next": "下个月",
            "restore.filter": "按日期筛选",
            "restore.dow.0": "一", "restore.dow.1": "二", "restore.dow.2": "三",
            "restore.dow.3": "四", "restore.dow.4": "五", "restore.dow.5": "六",
            "restore.dow.6": "日",
            "restore.empty": "Drive 中未找到备份。",
            "restore.empty_date": "该日期没有备份。",
            "restore.error": "加载备份时出错。",
            "restore.autosave": "自动保存",
            "restore.day_tip": "{n} 个备份",
            "restore.month_tip": "{m} 有 {n} 个备份",
            "restore.nodate": "无日期",
            "restore.newest": "最新",
            "autosave.resume.again": "继续",
            "restore.invalid": "已损坏",
            "restore.confirm": "恢复 {when} 的备份？",
            "restore.done": "会话已恢复",
            "restore.partial": "为适应上下文，已省略 {n} 条较早的消息",
            "restore.restoring": "正在恢复 {when}…",
            "restore.delete": "删除",
            "restore.delete_confirm": "删除 {when} 的备份？此操作无法撤销。",
            "restore.deleting": "正在删除 {when}…",
            "restore.deleted": "备份已删除。",
            "restore.delete_failed": "删除备份失败。",
            "dashboard.title": "健康状态面板",
            "providers.title": "连接 AI 提供商",
            "providers.select": "选择要配置 API key 的提供商：",
            "providers.saved_keys": "已保存到云端硬盘的密钥：",
            "providers.add_new": "新建提供商",
            "providers.search": "搜索提供商…",
            "providers.api_key": "API KEY", "providers.back": "← 返回",
            "providers.save_connect": "保存并连接",
            "providers.var": "变量",
            "providers.key_required": "请输入 API key。",
            "providers.select_required": "请选择一个提供商。",
            "providers.saving": "保存中…",
            "providers.connected": "已连接",
            "providers.updated": "已更新",
            "providers.no_saved_keys": "暂无已保存的密钥。",
            "providers.edit": "编辑",
            "providers.delete": "删除",
            "providers.confirm_delete": "删除以下提供商的密钥：",
            "providers.deleted": "已删除",
            "sessions.refresh": "↻ 刷新",
            "sessions.title": "会话历史",
            "sessions.search_placeholder": "🔍 按 ID 或内容搜索…",
            "shortcuts.title": "键盘快捷键",
            "shortcuts.copy": "复制所选内容", "shortcuts.copy_hint": "按住 Shift 并选择",
            "shortcuts.interrupt": "中断命令", "shortcuts.paste": "粘贴（Chrome）",
            "shortcuts.menu": "菜单与选项", "shortcuts.model": "更改模型",
            "shortcuts.history_prev": "上一条历史", "shortcuts.history_next": "下一条历史",
            "theme.toggle": "切换主题", "theme.light": "浅色主题（界面+终端）",
            "theme.dark": "深色主题（界面+终端）",
            "theme.terminal_reloaded": "终端已应用新主题并重新加载",
            # v0.6.5 — 终端启动画面
            "boot.starting": "正在启动终端…",
            "boot.restarting": "正在重启终端…",
            "boot.restoring": "正在恢复会话…",
            "boot.timeout": "终端无响应。请查看 ~/PesquisAI/logs/ttyd.log 后重新加载。",
            "boot.failed": "重启终端失败，请重试。",
            "boot.retry": "↻ 重新加载",
            "languages.label": "语言", "languages.switched_to": "语言已切换为",
            "languages.pt_BR": "葡萄牙语（巴西）", "languages.en_US": "英语（美国）",
            "languages.es_ES": "西班牙语（西班牙）", "languages.fr_FR": "法语（法国）",
            "languages.zh_CN": "中文（简体）",
            "success_messages.backup_saved": "备份已保存",
            "memory.title": "UFVAI 记忆库",
            "telemetry.title": "遥测（管理员）",
            "memory.subtitle": "智能体的持久记忆层（第二大脑）",
            "memory.tooltip": "UFVAI 记忆库（第二大脑）",
            "memory.status_ready": "🟢 运行中",
            "memory.status_disabled": "⚪ 未启用",
            "memory.status_no_vault": "🟡 缺少 vault",
            "memory.status_read_only": "🟡 只读",
            "memory.status_error": "🔴 错误",
            "memory.notes_count": "笔记",
            "memory.notes_unit": "篇",
            "memory.tags_count": "标签",
            "memory.avg_len": "平均长度",
            "memory.links_count": "链接",
            "memory.recent_notes": "最近笔记",
            "memory.recent_daily": "最近日志",
            "memory.templates": "模板",
            "memory.refresh": "刷新",
            "memory.save": "保存",
            "memory.new_note": "新建笔记",
            "memory.new_note_dialog_title": "新建笔记",
            "memory.new_note_title": "笔记标题",
            "memory.field_title": "标题",
            "memory.field_tags": "标签（逗号分隔）",
            "memory.field_template": "模板",
            "memory.field_path": "路径",
            "memory.empty_editor": "选择或创建一条笔记",
            "memory.body_placeholder": "在此编写 Markdown…",
            "memory.dirty": "有未保存的更改",
            "memory.delete": "删除",
            "memory.tab_edit": "编辑",
            "memory.tab_preview": "预览",
            "memory.tab_split": "分栏",
            "memory.no_notes": "暂无笔记",
            "memory.no_results": "无结果",
            "memory.note_title": "笔记标题",
            "memory.open_vault": "在 Obsidian 中打开",
            "agents.title": "智能体规则（AGENTS.md）",
            "manual.title": "UFVAI 使用手册",
            "manual.subtitle": "完整使用指南（MANUAL.md）",
            "manual.loading": "正在加载手册…",
            "manual.error": "本地未找到手册。",
            "manual.open_source": "在 GitHub 打开",
            "agents.subtitle": "UFVAI 的规则与原则（AGENTS.md）",
            "agents.copy": "复制 AGENTS.md",
            "agents.copy_ok": "已复制到剪贴板",
            "agents.error": "无法加载 AGENTS.md",
            "agents.loading": "正在加载 AGENTS.md…",
            "agents.open_source": "查看源码"
        }
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
