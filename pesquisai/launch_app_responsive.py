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
    .tb-btn { padding: 0 10px; font-size: 10.5px; }
    .logo-tag { display: none; }
    .footer-link { font-size: 10px; }
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
    .tb-icon { width: 32px; height: 32px; }
    .tb-icon svg { width: 14px; height: 14px; }
    .hamburger { display: inline-flex; }
    #footer { padding: 0 8px; height: 36px; }
    .footer-brand { display: none; }
    .footer-sep { margin: 0 6px; }
    .footer-link { font-size: 9.5px; }
    .btn-provider { padding: 0 6px; font-size: 9px; height: 20px; }
    .footer-oc { display: none; }
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
    """Cria a versão v0.4.1 do wrapper HTML do PesquisAI.

    Versão drop-in que substitui o HTML estático do launch_app.py por
    um layout adaptativo com 3 correções aplicadas:

      1. Responsividade completa (5 breakpoints + hamburger)
      2. toggleTheme() que recarrega o iframe do ttyd
      3. Seletor de idioma na topbar (4 idiomas, cookie, query param)

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
  <link rel="preconnect" href="https://cdn.jsdelivr.net">
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css">
  <!-- github-markdown-css: estilização markdown para o modal de Diretrizes -->
  <link rel="preload" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.5.0/github-markdown-dark.min.css" as="style">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.5.0/github-markdown-dark.min.css">
  <!-- marked.js: preload para acelerar renderização de markdown -->
  <link rel="preload" href="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js" as="script">
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
      background: #181b1e; border: 1px solid rgba(255,255,255,.1);
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
      font-size: 10.5px; color: var(--ink-muted);
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
      <button class="tb-icon" onclick="openHealth()" title="Dashboard de Saúde" data-i18n-title="dashboard.title">
        <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </button>
      <button class="tb-icon" onclick="openSessions()" title="Histórico de Sessões" data-i18n-title="sessions.title">
        <svg viewBox="0 0 24 24"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/></svg>
      </button>
      <button class="tb-icon" onclick="openShortcuts()" title="Atalhos de Teclado" data-i18n-title="shortcuts.title">
        <svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10"/></svg>
      </button>
      <button class="tb-icon" onclick="openAgents()" title="Diretrizes do Agente" data-i18n-title="agents.title">
        <svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M9 7h7M9 11h7"/></svg>
      </button>
      <button class="tb-icon" onclick="openMemory()" id="memory-btn" title="Memória PesquisAI" data-i18n-title="memory.tooltip">
        <svg viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-7 7c0 3 1.5 5 3 7l1 1v3a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-3l1-1c1.5-2 3-4 3-7a7 7 0 0 0-7-7z"/><path d="M9 22h6"/><path d="M12 2v20"/></svg>
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
    <button class="modal-close" onclick="openHealth(); toggleMobileMenu();">🩺 <pan data-i18n="dashboard.title">Dashboard de Saúde</span></button>
    <button class="modal-close" onclick="openSessions(); toggleMobileMenu();">📜 <span data-i18n="sessions.title">Histórico de Sessões</span></button>
    <button class="modal-close" onclick="openShortcuts(); toggleMobileMenu();">⌨️ <span data-i18n="shortcuts.title">Atalhos de Teclado</span></button>
    <button class="modal-close" onclick="openAgents(); toggleMobileMenu();">📋 <span data-i18n="agents.title">Diretrizes do Agente</span></button>
    <button class="modal-close" onclick="openMemory(); toggleMobileMenu();">🧠 <span data-i18n="memory.title">Memória PesquisAI</span></button>
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
    <span class="footer-brand">PesquisAI</span>
    <span class="footer-sep"></span>
    <a href="mailto:gustavo.braga@ufv.br" class="footer-link">
      <svg viewBox="0 0 24 24"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
      gustavo.braga@ufv.br
    </a>
    <span class="footer-sep"></span>
    <a href="https://github.com/gustavobraga-byte/PesquisAI" target="_blank" class="footer-link">
      <svg viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
      GitHub
    </a>
    <span class="footer-sep"></span>
    <span style="color:var(--ink-muted)">UFV · Viçosa, MG - Brasil</span>

    <div class="footer-right">
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
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:480px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
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
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:440px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">🩺 <span data-i18n="dashboard.title">Dashboard de Saúde</span></div>
      <div id="health-list" style="max-height:340px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty" data-i18n="ui.loading">Carregando diagnóstico…</div>
      </div>
      <button onclick="closeHealth()" class="modal-close" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="sessions-overlay" onclick="if(event.target===this)closeSessions()" style="position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:520px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">📜 <span data-i18n="sessions.title">Histórico de Sessões</span></div>
      <input id="session-search" class="session-search" placeholder="🔍 Buscar por id ou conteúdo…" oninput="filterSessions()" data-i18n-placeholder="sessions.search_placeholder">
      <div id="session-list" style="max-height:300px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty" data-i18n="ui.loading">Carregando sessões…</div>
      </div>
      <button onclick="closeSessions()" class="modal-close" data-i18n="ui.close">Fechar</button>
    </div>
  </div>

  <div id="shortcuts-overlay" onclick="if(event.target===this)closeShortcuts()" style="position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:420px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
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
      <div id="agents-content" class="markdown-body" style="flex:1;overflow-y:auto;padding:22px 26px;font-size:12.5px;line-height:1.65;color:var(--ink);" data-i18n="agents.loading">Carregando diretrizes…</div>
      <div style="padding:10px 18px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.02);">
        <button onclick="copyAgents()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;" data-i18n="agents.copy">Copiar</button>
        <button onclick="reloadAgents()" class="modal-close" style="width:auto;padding:5px 12px;font-size:11px;">↻ <span data-i18n="ui.loading">Recarregar</span></button>
        <div style="flex:1;"></div>
        <a id="agents-source-link" href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/agents/AGENTS.pt.md" target="_blank" class="footer-link" style="font-size:10.5px;" data-i18n="agents.open_source">Ver fonte</a>
      </div>
    </div>
  </div>

  <!-- Modal de Memória PesquisAI (v0.5.1.4 — navegar + editar) -->
  <div id="memory-overlay" onclick="if(event.target===this)closeMemory()" style="position:fixed;inset:0;background:rgba(0,0,0,.78);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:0;width:980px;max-width:96vw;max-height:92vh;box-shadow:0 28px 72px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <!-- Header -->
      <div style="padding:14px 18px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;">
        <span style="font-size:18px;">🧠</span>
        <div style="flex:1;min-width:0;">
          <div class="modal-title" style="margin-bottom:2px;" data-i18n="memory.title">Memória PesquisAI</div>
          <div id="memory-subtitle" style="font-size:10.5px;color:var(--ink-muted);" data-i18n="memory.subtitle">Camada de memória persistente do agente</div>
        </div>
        <span id="memory-status-badge" style="font-size:10px;padding:2px 8px;border:1px solid var(--line);border-radius:3px;color:var(--ink-muted);font-family:'DM Mono',monospace;">…</span>
        <span id="memory-dirty-indicator" style="display:none;font-size:10px;padding:2px 8px;background:var(--amber);color:#000;border-radius:3px;font-weight:600;">● <span data-i18n="memory.dirty">não salvo</span></span>
        <button onclick="closeMemory()" class="modal-close" style="width:auto;padding:4px 10px;font-size:11px;" aria-label="Fechar">✕</button>
      </div>

      <!-- Split view: lista (esq) + editor (dir) -->
      <div style="flex:1;display:flex;min-height:0;">
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
              <div id="memory-note-path" style="font-size:10px;color:var(--ink-muted);font-family:'DM Mono',monospace;margin-top:2px;word-break:break-all;">—</div>
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
            <textarea id="memory-editor" spellcheck="false" oninput="onEditorInput()" style="flex:1;background:transparent;color:var(--ink);border:none;outline:none;resize:none;padding:14px;font-family:'DM Mono',monospace;font-size:12px;line-height:1.55;display:none;" data-i18n-placeholder="memory.body_placeholder" placeholder="Selecione uma nota à esquerda ou crie uma nova."></textarea>
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
  <div id="memory-new-overlay" onclick="if(event.target===this)closeCreateNoteDialog()" style="position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(2px);display:flex;align-items:center;justify-content:center;z-index:100000;opacity:0;pointer-events:none;transition:opacity .15s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:18px;width:420px;max-width:92vw;box-shadow:0 16px 40px rgba(0,0,0,.6);">
      <div style="font-size:13px;font-weight:600;margin-bottom:14px;" data-i18n="memory.new_note_dialog_title">📝 Nova nota</div>
      <label style="display:block;font-size:11px;color:var(--ink-muted);margin-bottom:4px;" data-i18n="memory.field_path">Caminho (ex: research/minha-nota.md)</label>
      <input id="memory-new-path" type="text" placeholder="research/minha-nota.md" style="width:100%;background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--ink);border-radius:4px;padding:7px 9px;font-size:12px;font-family:'DM Mono',monospace;outline:none;margin-bottom:10px;" />
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
        <button onclick="submitCreateNote()" class="modal-close" style="width:auto;padding:5px 14px;font-size:11px;background:var(--accent);color:#000;border:1px solid var(--accent);border-radius:4px;font-weight:600;" data-i18n="memory.create">Criar</button>
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
      background: rgba(var(--accent-rgb, 99, 179, 237), .12);
      border-left-color: var(--accent);
    }
    .mem-note-item .mem-note-title {
      font-size: 12px; color: var(--ink); font-weight: 500;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .mem-note-item .mem-note-path {
      font-size: 9.5px; color: var(--ink-muted); font-family: 'DM Mono', monospace;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .mem-note-item.human .mem-note-title::before {
      content: '✎ '; color: var(--ink-muted);
    }
    .mem-folder-label {
      font-size: 9.5px; color: var(--ink-muted); text-transform: uppercase;
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
      background: rgba(var(--accent-rgb, 99, 179, 237), .1);
      color: var(--accent); padding: 1px 5px; border-radius: 3px;
      font-family: 'DM Mono', monospace; font-size: 11px;
    }
    .mem-preview .tag {
      background: var(--accent-dim); color: var(--accent);
      padding: 1px 6px; border-radius: 3px; font-size: 10.5px; margin-right: 3px;
    }
    .mem-preview hr { border: none; border-top: 1px solid var(--line); margin: 1em 0; }
  </style>
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
      try {
        fetch(BASE + "/api/lang", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lang: lang })
        }).catch(() => {});
      } catch (e) {}
      // Aplica imediatamente o que dá (UI strings)
      applyLang(lang);
      // Toast feedback
      const dict = I18N[lang] || I18N["pt_BR"];
      toast("🌐 " + (dict["languages.switched_to"] || lang), "info");
      // Fecha menu
      closeLangMenu();
      // Recarrega para que backend traduza também (toasts, modais completos)
      setTimeout(() => location.reload(), 700);
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
      // 🐛 HOTFIX v0.5.1.3 — guardar refs em variáveis locais ANTES de fechar overlay
      // O bug original: closeProvider() setava _selProv = null, e a linha seguinte
      // (_selProv.id no JSON.stringify) crashava com "Cannot read properties of null".
      const provId = _selProv.id;
      const provEnv = _selProv.env;
      const provName = _selProv.name;
      toast("💾 Salvando…", "info");
      try {
        const r = await fetch(BASE + "/api/apikey", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: provId, env: provEnv, apikey: key })
        });
        const d = await r.json().catch(() => ({}));
        if (r.ok && (d.ok !== false)) {
          toast(`✅ ${provName} conectado!`, "ok");
          closeProvider();
        } else {
          toast("❌ " + (d.error || `Erro HTTP ${r.status}`), "err");
        }
      } catch(e) {
        toast("❌ " + e.message, "err");
      }
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
        var icon = ok ? '✅' : '❌';
        var color = ok ? 'var(--accent)' : '#ff6b6b';
        h += '<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-bottom:1px solid var(--line);font-size:12px;">';
        h += '<span style="color:' + color + ';">' + icon + '</span>';
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
    const SESSIONS_PAGE_SIZE = 20;

    async function openSessions() {
      const overlay = document.getElementById("sessions-overlay");
      overlay.style.opacity = "1"; overlay.style.pointerEvents = "all";
      await loadSessions();
    }
    function closeSessions() {
      const o = document.getElementById("sessions-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
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
        h += '<div class="session-item" data-session-id="' + id.replace(/"/g,'&quot;') + '" onclick="restoreSession(this.dataset.sessionId)" style="padding:7px 10px;border-bottom:1px solid var(--line);cursor:pointer;transition:background .12s;font-size:12px;" onmouseover="this.style.background=\\x27rgba(255,255,255,.04)\\x27" onmouseout="this.style.background=\\x27transparent\\x27">';
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
      if (!confirm("Restaurar sessao " + sessionId + " ?")) return;
      try {
        var listEl = document.getElementById("session-list");
        if (listEl) listEl.innerHTML = '<div class="modal-empty">Restaurando sessão…</div>';
        const r = await fetch(BASE + "/api/run_terminal", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({cmd: "opencode session restore " + sessionId})
        });
        const d = await r.json();
        if (r.ok) {
          toast("✅ Sessão " + sessionId + " restaurada!", "ok");
          closeSessions();
        } else {
          toast("❌ Erro ao restaurar: " + (d.error || r.status), "err");
          loadSessions(true);
        }
      } catch(e) {
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
        sourceEl.href = "https://github.com/gustavobraga-byte/PesquisAI/blob/main/agents/AGENTS." + code + ".md";
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

    // ── Memória PesquisAI (v0.5.1.4 — navegar + editar) ────────
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
      // v0.5.1.8: cache de 5s — evita nova requisição se cache for recente
      const now = Date.now();
      if (!force && _memoryCache.tree && (now - _memoryCache.ts) < 5000) {
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
        if (!confirm("Há mudanças não salvas em '" + _memoryCurrent.path + "'.\\nFechar mesmo assim?")) {
          return;
        }
      }
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
        if (cnt) cnt.textContent = total + " " + (dict["memory.notes_count"] || "notas");
        if (total === 0) {
          list.innerHTML = '<div class="modal-empty" style="padding:14px;font-size:11.5px;">' +
            (dict["memory.no_results"] || "Nenhum resultado para '" + escapeHtml(q) + "'.") + '</div>';
          return;
        }
        let html = "";
        for (const folder of filtered) {
          const label = folder.folder || "📁 (raiz)";
          html += '<div class="mem-folder-label">' + escapeHtml(label) + '</div>';
          for (const n of folder.notes) {
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
      const ordered = Object.keys(folderMap).sort((a, b) => {
        if (a === "daily/") return -1;
        if (b === "daily/") return 1;
        return a.localeCompare(b);
      });
      for (const f of ordered) {
        const icon = folderIcons[f] || "📁";
        const label = f ? f.replace(/\/$/, "") : "(raiz)";
        const count = folderMap[f];
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
      const notes = [];
      for (const folder of _memoryTree) {
        if (folder.folder === folderName) {
          for (const n of folder.notes) notes.push(n);
        }
      }
      if (cnt) cnt.textContent = notes.length + " " + (dict["memory.notes_count"] || "notas");
      let html = '<div style="padding:6px 8px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:6px;">';
      html += '<button onclick="navigateBack()" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:10px;color:var(--accent);cursor:pointer;">← ' + (dict["memory.back"] || "Voltar") + '</button>';
      const iconMap = {
        "daily/": "📅", "research/": "🔬", "literature/": "📚",
        "sessions/": "📜", "reference/": "📖", "methodology/": "⚙️",
        "hypothesis/": "💡", "datasource/": "🗄️", "moc/": "🗺️",
        "inbox/": "📥", "assets/": "🎨"
      };
      html += '<span style="font-size:12px;font-weight:500;color:var(--ink-muted);">' + (iconMap[folderName] || "📁") + ' ' + escapeHtml(folderName.replace(/\/$/, "")) + '</span>';
      html += '</div>';

      if (folderName === "daily/") {
        html += renderCalendar();
      } else {
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
      const month = date.getMonth();
      const today = new Date();
      const todayStr = today.getFullYear() + "-" + String(today.getMonth()+1).padStart(2,"0") + "-" + String(today.getDate()).padStart(2,"0");
      const firstDay = new Date(year, month, 1).getDay();
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const monthNames = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                          "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];
      const weekDays = ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"];
      let h = '<div style="padding:8px;">';
      h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">';
      h += '<button onclick="prevMonth()" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:11px;color:var(--accent);cursor:pointer;">◀</button>';
      h += '<span style="font-size:13px;font-weight:600;">' + monthNames[month] + ' ' + year + '</span>';
      h += '<button onclick="nextMonth()" style="background:none;border:1px solid var(--line);border-radius:var(--radius);padding:3px 8px;font-size:11px;color:var(--accent);cursor:pointer;">▶</button>';
      h += '</div>';
      h += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;font-size:10px;color:var(--ink-muted);margin-bottom:4px;">';
      for (let w = 0; w < 7; w++) {
        h += '<div style="padding:4px 0;">' + weekDays[w] + '</div>';
      }
      h += '</div>';
      h += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;">';
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
        else if (isToday) styles += "background:rgba(79,195,247,.12);color:var(--accent);font-weight:600;";
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
        _memoryCalendarDate = new Date();
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
    function searchMemory(q) {
      if (_searchDebounce) clearTimeout(_searchDebounce);
      _searchDebounce = setTimeout(() => {
        _memorySearch = q;
        renderMemorySidebar();
      }, 150);
    }

    // ── Carregar nota no editor ───────────────────────────────────
    async function loadMemoryNote(path) {
      if (_memoryDirty && _memoryCurrent && _memoryCurrent.path !== path) {
        if (!confirm("Há mudanças não salvas em '" + _memoryCurrent.path + "'.\\nDescartar e abrir outra nota?")) {
          return;
        }
      }
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
          html = html.replace(/\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]/g,
            (m, target, alias) => '<span class="wikilink">[[' + escapeHtml(alias || target) + ']]</span>');
          html = html.replace(/(^|[\s(])#([a-zA-Z0-9_\-/]+)/g,
            (m, p, t) => p + '<span class="tag">#' + escapeHtml(t) + '</span>');
          prev.innerHTML = '<div class="mem-preview markdown-body">' + html + '</div>';
        } else {
          prev.innerHTML = '<pre style="white-space:pre-wrap;font-family:DM Mono,monospace;font-size:11.5px;">' + escapeHtml(src) + '</pre>';
        }
      } catch (e) {
        prev.innerHTML = '<pre>' + escapeHtml(src) + '</pre>';
      }
    }

    // ── Editor: input → dirty ─────────────────────────────────────
    function onEditorInput() {
      if (!_memoryDirty) { _memoryDirty = true; markDirty(); }
      if (_memoryTab === "split") renderPreview();
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
      const dict = I18N[_currentLang] || I18N["pt_BR"];
      const ok = confirm("Mover '" + _memoryCurrent.path + "' para .trash/?");
      if (!ok) return;
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
        if (!confirm("Há mudanças não salvas em '" + _memoryCurrent.path + "'.\\nContinuar?")) return;
      }
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
  <!-- marked.js: renderizador de markdown para o modal de Diretrizes do Agente e preview do editor -->
  <script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
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
            # v0.5.1.2 — Memória PesquisAI
            "memory.title": "Memória PesquisAI",
            "memory.subtitle": "Camada de memória persistente do agente",
            "memory.tooltip": "Memória PesquisAI (segundo cérebro)",
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
            # v0.5.1.2 — PesquisAI Memory
            "memory.title": "PesquisAI Memory",
            "memory.subtitle": "Agent's persistent memory layer",
            "memory.tooltip": "PesquisAI Memory (second brain)",
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
            # v0.5.1.2 — Memoria PesquisAI
            "memory.title": "Memoria PesquisAI",
            "memory.subtitle": "Capa de memoria persistente del agente",
            "memory.tooltip": "Memoria PesquisAI (segundo cerebro)",
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
            # v0.5.1.2 — Mémoire PesquisAI
            "memory.title": "Mémoire PesquisAI",
            "memory.subtitle": "Couche de mémoire persistante de l'agent",
            "memory.tooltip": "Mémoire PesquisAI (deuxième cerveau)",
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
