import os
import subprocess
import time
import threading
import json
import shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:
    from google.colab import output
    from IPython.display import display, HTML
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
    output = None
    display = None
    HTML = None

from constants import TERMINAL_PORT, WRAPPER_PORT, WRAPPER_DIR, logger
from jokes import next_joke
from opencode_utils import find_opencode, build_env


_opencode_bin = None
_env = None
_drive_url = "https://drive.google.com/drive/my-drive"
_folder_path = "/content"


def set_drive_info(folder_path, drive_url):
    global _drive_url, _folder_path
    _drive_url = drive_url
    _folder_path = folder_path


def resolve_opencode():
    global _opencode_bin, _env
    try:
        _opencode_bin = find_opencode()
    except FileNotFoundError:
        logger.warning("opencode não encontrado, usando fallback 'opencode'")
        _opencode_bin = "opencode"
    _env = build_env()
    print(f"🔍 OpenCode binário: {_opencode_bin}")
    return _opencode_bin, _env


def install_ttyd():
    print(f"\n{next_joke('economia')}")
    print("📦 Instalando ttyd...")
    r1 = subprocess.run(
        "apt-get update -qq && apt-get install -y -qq ttyd",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if r1.returncode != 0:
        print("⚠️  apt-get falhou. Tentando download manual do ttyd...")
        url = "https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64"
        r2 = subprocess.run(
            f"curl -fsSL {url} -o /usr/local/bin/ttyd && chmod +x /usr/local/bin/ttyd",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if r2.returncode != 0:
            print("⚠️  Download manual do ttyd também falhou. Continuando mesmo assim.")
        else:
            print("✅ ttyd baixado manualmente.")
    else:
        print("✅ ttyd instalado.")


def kill_previous():
    subprocess.run("pkill -f ttyd 2>/dev/null || true", shell=True)
    subprocess.run(f"pkill -f 'python3.*{WRAPPER_PORT}' 2>/dev/null || true", shell=True)
    time.sleep(0.5)


def start_ttyd():
    print(f"\n{next_joke('economia')}")
    opencode_bin, env = resolve_opencode()
    
    subprocess.Popen(
        ["ttyd", "-p", str(TERMINAL_PORT), "bash", "-i", "-c", f"{opencode_bin}; exec bash"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    print("🚀 Terminal iniciado.")
    time.sleep(2)


def create_wrapper_html(terminal_url, drive_url):
    wrapper_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PesquisAI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Syne:wght@700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
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
    }}

    html, body {{
      height: 100%;
      background: var(--surface);
      color: var(--ink);
      font-family: "DM Mono", monospace;
      overflow: hidden;
    }}

    #topbar {{
      position: fixed; inset: 0 0 auto 0;
      height: 50px;
      background: var(--rail);
      border-bottom: 1px solid var(--line);
      display: flex; align-items: center;
      padding: 0 18px; gap: 14px;
      z-index: 9999;
    }}
    #topbar::after {{
      content: "";
      position: absolute; inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px,
        rgba(0,0,0,.05) 2px, rgba(0,0,0,.05) 4px);
      pointer-events: none;
    }}

    .logo {{ display: flex; align-items: baseline; gap: 2px; }}
    .logo-p  {{ font-family:"Syne",sans-serif; font-weight:800; font-size:17px; color:var(--ink); letter-spacing:-.5px; }}
    .logo-ai {{ font-family:"Syne",sans-serif; font-weight:700; font-size:17px; color:var(--accent); letter-spacing:-.5px; }}
    .logo-tag {{
      margin-left:9px; font-size:10px; color:var(--ink-muted);
      letter-spacing:.07em; padding:1px 6px;
      border:1px solid var(--line); border-radius:3px; align-self:center;
    }}

    .status {{ display:flex; align-items:center; gap:7px; font-size:11px; color:var(--ink-muted); }}
    .status-dot {{
      width:7px; height:7px; border-radius:50%; background:var(--green);
      animation: pulse 2.4s ease infinite;
    }}
    @keyframes pulse {{
      0%,100% {{ box-shadow:0 0 0 0 rgba(93,186,126,.5); }}
      50%      {{ box-shadow:0 0 0 5px rgba(93,186,126,0); }}
    }}

    .sep {{ flex: 1; }}

    .tb-btn {{
      display: inline-flex; align-items: center; gap: 7px;
      padding: 0 13px; height: 30px;
      font-family: "DM Mono", monospace; font-size: 11px;
      font-weight: 500; letter-spacing: .04em;
      border-radius: var(--radius); cursor: pointer;
      border: 1px solid; transition: background .15s, transform .1s, border-color .15s;
      text-decoration: none; white-space: nowrap;
    }}
    .tb-btn:active {{ transform: scale(.96); }}
    .tb-btn svg {{ width:13px; height:13px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }}

    .btn-drive  {{ color:var(--accent); background:var(--accent-dim); border-color:rgba(79,195,247,.25); }}
    .btn-drive:hover  {{ background:var(--accent-glow); border-color:rgba(79,195,247,.5); }}

    .btn-backup {{ color:var(--green); background:var(--green-dim); border-color:rgba(93,186,126,.25); }}
    .btn-backup:hover {{ background:rgba(93,186,126,.2); border-color:rgba(93,186,126,.5); }}

    .btn-restore {{ color:var(--amber); background:var(--amber-dim); border-color:rgba(232,184,75,.25); }}
    .btn-restore:hover {{ background:rgba(232,184,75,.2); border-color:rgba(232,184,75,.5); }}

    #toast {{
      position: fixed; bottom: 58px; right: 18px;
      padding: 9px 16px; border-radius: var(--radius);
      font-size: 12px; font-family: "DM Mono", monospace;
      display: flex; align-items: center; gap: 8px;
      opacity: 0; transform: translateY(6px);
      transition: opacity .22s, transform .22s;
      pointer-events: none; z-index: 9998; max-width: 340px;
      border: 1px solid;
    }}
    #toast.show {{ opacity: 1; transform: translateY(0); }}
    #toast.ok    {{ background:rgba(93,186,126,.15);  border-color:rgba(93,186,126,.35);  color:var(--green); }}
    #toast.err   {{ background:rgba(224,112,112,.15); border-color:rgba(224,112,112,.35); color:var(--red);   }}
    #toast.info  {{ background:var(--accent-dim);     border-color:rgba(79,195,247,.35);  color:var(--accent);}}

    #modal-overlay {{
      position: fixed; inset: 0;
      background: rgba(0,0,0,.65); backdrop-filter: blur(3px);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; opacity: 0; pointer-events: none;
      transition: opacity .2s;
    }}
    #modal-overlay.open {{ opacity: 1; pointer-events: all; }}
    #modal {{
      background: #181b1e; border: 1px solid rgba(255,255,255,.1);
      border-radius: 8px; padding: 24px; width: 400px; max-width: 90vw;
      box-shadow: 0 24px 64px rgba(0,0,0,.6);
    }}
    .modal-title {{
      font-family: "Syne", sans-serif; font-weight: 800;
      font-size: 15px; color: var(--ink); margin-bottom: 16px;
    }}
    .backup-list {{
      max-height: 260px; overflow-y: auto;
      border: 1px solid var(--line); border-radius: var(--radius);
      margin-bottom: 16px;
    }}
    .backup-item {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 9px 12px; font-size: 11.5px; color: var(--ink-muted);
      border-bottom: 1px solid var(--line); cursor: pointer;
      transition: background .12s;
    }}
    .backup-item:last-child {{ border-bottom: none; }}
    .backup-item:hover {{ background: rgba(255,255,255,.04); color: var(--ink); }}
    .backup-item .restore-lbl {{
      font-size: 10px; padding: 2px 8px;
      background: var(--amber-dim); color: var(--amber);
      border: 1px solid rgba(232,184,75,.3); border-radius: 3px;
    }}
    .modal-empty {{ padding:20px; text-align:center; font-size:12px; color:var(--ink-muted); }}
    .modal-close {{
      display: block; width: 100%; padding: 8px;
      background: rgba(255,255,255,.05); border: 1px solid var(--line);
      border-radius: var(--radius); color: var(--ink-muted);
      font-family: "DM Mono", monospace; font-size: 12px;
      cursor: pointer; transition: background .15s;
    }}
    .modal-close:hover {{ background: rgba(255,255,255,.1); }}

    #terminal-frame {{
      position: absolute;
      inset: 50px 0 40px 0;
      width: 100%; height: calc(100% - 10px);
      border: none;
    }}

    #footer {{
      position: fixed; inset: auto 0 0 0;
      height: 40px;
      background: var(--rail);
      border-top: 1px solid var(--line);
      display: flex; align-items: center;
      padding: 0 18px; gap: 0;
      font-size: 10.5px; color: var(--ink-muted);
      z-index: 9999;
    }}
    .footer-brand {{
      font-family: "Syne", sans-serif; font-weight: 700;
      font-size: 11px; color: var(--ink);
      margin-right: 14px;
    }}
    .footer-sep {{ width:1px; height:16px; background:var(--line); margin:0 12px; flex-shrink:0; }}
    .footer-link {{
      color: var(--ink-muted); text-decoration: none;
      letter-spacing: .03em;
      transition: color .15s;
    }}
    .footer-link:hover {{ color: var(--accent); }}
    .footer-link svg {{ width:11px; height:11px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; vertical-align:-.15em; margin-right:4px; }}
    .footer-right {{ margin-left:auto; display:flex; align-items:center; gap:12px; }}
    .footer-oc {{ color:var(--ink-muted); letter-spacing:.03em; }}
    .footer-oc a {{ color:var(--ink-muted); text-decoration:none; }}
    .footer-oc a:hover {{ color:var(--accent); }}

    .btn-provider {{
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
    }}
    .btn-provider:hover {{
      background: var(--accent-dim);
      color: var(--accent);
      border-color: rgba(79,195,247,.4);
    }}
    .btn-provider:active {{ transform: scale(.96); }}
    .btn-provider svg {{ width:10px; height:10px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }}
  </style>
</head>
<body>

  <div id="topbar">
    <div class="logo">
      <span class="logo-p">Pesquis</span><span class="logo-ai">AI</span>
      <span class="logo-tag">v1.0</span>
    </div>

    <div class="status">
      <span class="status-dot"></span>
      agente ativo
    </div>

    <div class="sep"></div>

    <button class="tb-btn btn-backup" onclick="doBackup()">
      <svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      Salvar backup
    </button>

    <button class="tb-btn btn-restore" onclick="openRestore()">
      <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>
      Restaurar
    </button>

    <a href="{drive_url}" target="_blank" class="tb-btn btn-drive">
      <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      Drive
    </a>
  </div>

 <iframe
  id="terminal-frame"
  src="{terminal_url}"
  allow="clipboard-read; clipboard-write"
  tabindex="0"
  autofocus
  style="
    width:100%;
    height:calc(100% - 90px);
    border:none;
    outline:none;
  ">
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
    <span style="color:var(--ink-muted)">UFV · Viçosa, MG</span>

    <div class="footer-right">
      <button class="btn-provider" onclick="connectProvider()" title="Conectar novo provedor de IA">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>
        + provedor
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
      <div class="modal-title">🔄 Restaurar Sessão</div>
      <div class="backup-list" id="backup-list">
        <div class="modal-empty">Carregando backups…</div>
      </div>
      <button class="modal-close" onclick="closeModal()">Fechar</button>
    </div>
  </div>

  <!-- Modal: Conectar Provedor — Step 1: escolher, Step 2: inserir key -->
  <div id="provider-overlay" onclick="if(event.target===this)closeProvider()" style="
    position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);
    display:flex;align-items:center;justify-content:center;
    z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:480px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">

      <!-- STEP 1 -->
      <div id="prov-step1">
        <div class="modal-title">🔌 Conectar Provedor de IA</div>
        <p style="font-size:11.5px;color:var(--ink-muted);margin-bottom:14px;line-height:1.6;">
          Selecione o provedor para configurar a API key:
        </p>
        <div id="prov-list" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;"></div>
        <button onclick="closeProvider()" style="
          display:block;width:100%;padding:8px;background:rgba(255,255,255,.04);
          border:1px solid var(--line);border-radius:var(--radius);color:var(--ink-muted);
          font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;">Cancelar</button>
      </div>

      <!-- STEP 2 -->
      <div id="prov-step2" style="display:none;">
        <div class="modal-title">🔑 <span id="prov-name-title"></span></div>
        <p style="font-size:11px;color:var(--ink-muted);margin-bottom:4px;line-height:1.5;">
          Variável de ambiente: <code id="prov-env-code" style="color:var(--accent);background:rgba(79,195,247,.08);padding:1px 6px;border-radius:3px;font-size:11px;"></code>
        </p>
        <p style="font-size:11px;color:var(--ink-muted);margin-bottom:14px;line-height:1.5;">
          A key será salva no Drive e o terminal executará:<br>
          <code id="prov-cmd-preview" style="color:var(--amber);background:rgba(232,184,75,.07);padding:2px 6px;border-radius:3px;font-size:10.5px;"></code>
        </p>
        <label style="display:block;font-size:10.5px;color:var(--ink-muted);margin-bottom:6px;letter-spacing:.05em;">API KEY</label>
        <input id="prov-key-input" type="password" placeholder="Cole sua key aqui…" autocomplete="off" style="
          display:block;width:100%;padding:9px 12px;box-sizing:border-box;
          background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:var(--radius);
          color:var(--ink);font-family:'DM Mono',monospace;font-size:12px;
          outline:none;margin-bottom:14px;transition:border-color .15s;"
          onfocus="this.style.borderColor='rgba(79,195,247,.4)'"
          onblur="this.style.borderColor='var(--line)'"
          onkeydown="if(event.key==='Enter')confirmProvider()"/>
        <div style="display:flex;gap:8px;">
          <button onclick="provBack()" style="
            padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);
            border-radius:var(--radius);color:var(--ink-muted);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;">
            ← Voltar
          </button>
          <button onclick="confirmProvider()" style="
            flex:1;padding:9px;background:var(--accent-dim);border:1px solid rgba(79,195,247,.3);
            border-radius:var(--radius);color:var(--accent);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;">
            Salvar e Conectar
          </button>
          <button onclick="closeProvider()" style="
            padding:9px 14px;background:rgba(255,255,255,.04);border:1px solid var(--line);
            border-radius:var(--radius);color:var(--ink-muted);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;">
            Cancelar
          </button>
        </div>
      </div>

    </div>
  </div>

  <script>
    const BASE = location.origin;

    let _toastT;
    function toast(msg, type = "info") {{
      const el = document.getElementById("toast");
      el.className = "show " + type;
      el.textContent = msg;
      clearTimeout(_toastT);
      _toastT = setTimeout(() => el.classList.remove("show"), 3800);
    }}

    async function doBackup() {{
      toast("⏳ Exportando sessão…", "info");
      try {{
        const r = await fetch(BASE + "/api/backup", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{}})
        }});
        const d = await r.json();
        if (d.ok) {{
          toast("✅ Backup salvo: " + d.file, "ok");
        }} else {{
          toast("❌ " + (d.error || "Erro desconhecido"), "err");
        }}
      }} catch(e) {{
        toast("❌ Falha na conexão: " + e.message, "err");
      }}
    }}

    async function openRestore() {{
      document.getElementById("modal-overlay").classList.add("open");
      const list = document.getElementById("backup-list");
      list.innerHTML = '<div class="modal-empty">Carregando backups…</div>';
      try {{
        const r = await fetch(BASE + "/api/backups");
        const d = await r.json();
        if (!d.backups || d.backups.length === 0) {{
          list.innerHTML = '<div class="modal-empty">Nenhum backup encontrado no Drive.</div>';
          return;
        }}
        list.innerHTML = d.backups.map(f => `
          <div class="backup-item" onclick="doRestore('${{f}}')">
            <span>${{f}}</span>
            <span class="restore-lbl">restaurar</span>
          </div>
        `).join("");
      }} catch(e) {{
        list.innerHTML = '<div class="modal-empty">Erro ao carregar backups.</div>';
      }}
    }}

    function closeModal() {{
      document.getElementById("modal-overlay").classList.remove("open");
    }}

    async function doRestore(file) {{
      closeModal();
      toast("⏳ Importando " + file + "…", "info");
      try {{
        const r = await fetch(BASE + "/api/restore", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ file }})
        }});
        const d = await r.json();

        if (d.ok) {{
          const sessionId = d.session_id || "";
          const cmd = sessionId ? "opencode -s " + sessionId : "opencode";
          toast("✅ Importado! session_id: " + (sessionId || "(não encontrado)"), "ok");
          setTimeout(() => {{
            const msg = "Sessão restaurada!\\n" +
              (sessionId ? "Vai abrir: " + cmd : "Sem sessionId — vai abrir opencode padrão.") +
              "\\n\\nReiniciar o terminal agora?";
            if (window.confirm(msg)) {{
              toast("🔄 Rodando: " + cmd, "info");
              fetch(BASE + "/api/run_terminal", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ command: cmd, no_fallback: true }})
              }}).then(() => {{
                // Force iframe reload: blank → original URL after ttyd restarts
                const fr = document.getElementById("terminal-frame");
                const origSrc = fr.src.split("?")[0];
                fr.src = "about:blank";
                setTimeout(() => {{
                  fr.src = origSrc + "?t=" + Date.now();
                  toast("✅ Terminal recarregado com sessão!", "ok");
                }}, 3500);
              }}).catch(e => {{ toast("❌ Erro: " + e.message, "err"); }});
            }}
          }}, 600);

        }} else {{
          toast("❌ " + (d.error || "Erro ao importar"), "err");
        }}

      }} catch(e) {{
        toast("❌ Falha na conexão: " + e.message, "err");
      }}
    }}

    /* ── Provider list (all opencode-compatible) ───────────────── */
    const PROVIDERS = [
      {{ id:"anthropic",    name:"Anthropic",       env:"ANTHROPIC_API_KEY",      hint:"sk-ant-…"    }},
      {{ id:"openai",       name:"OpenAI",           env:"OPENAI_API_KEY",         hint:"sk-…"        }},
      {{ id:"google",       name:"Google Gemini",    env:"GOOGLE_GENERATIVE_AI_API_KEY",         hint:"AIza…"       }},
      {{ id:"groq",         name:"Groq",             env:"GROQ_API_KEY",           hint:"gsk_…"       }},
      {{ id:"mistral",      name:"Mistral",          env:"MISTRAL_API_KEY",        hint:"…"           }},
      {{ id:"xai",          name:"xAI (Grok)",       env:"XAI_API_KEY",            hint:"xai-…"       }},
      {{ id:"deepseek",     name:"DeepSeek",         env:"DEEPSEEK_API_KEY",       hint:"sk-…"        }},
      {{ id:"openrouter",   name:"OpenRouter",       env:"OPENROUTER_API_KEY",     hint:"sk-or-…"     }},
      {{ id:"nvidia",       name:"Nvidia NIM",       env:"NVIDIA_API_KEY",         hint:"nvapi-…"     }},
      {{ id:"together",     name:"Together AI",      env:"TOGETHER_API_KEY",       hint:"…"           }},
      {{ id:"bedrock",      name:"AWS Bedrock",      env:"AWS_ACCESS_KEY_ID",      hint:"AKIA…"       }},
      {{ id:"azure",        name:"Azure OpenAI",     env:"AZURE_OPENAI_API_KEY",   hint:"…"           }},
      {{ id:"vertex",       name:"Vertex AI",        env:"VERTEX_API_KEY",         hint:"…"           }},
    ]

    let _selProv = null;

    function connectProvider() {{
      // Build provider grid
      const grid = document.getElementById("prov-list");
      grid.innerHTML = PROVIDERS.map(p => `
        <button onclick="selectProvider('${{p.id}}')" style="
          display:flex;align-items:center;gap:8px;padding:9px 12px;
          background:rgba(255,255,255,.03);border:1px solid var(--line);
          border-radius:var(--radius);color:var(--ink-muted);
          font-family:'DM Mono',monospace;font-size:11px;cursor:pointer;
          text-align:left;transition:background .12s,color .12s,border-color .12s;"
          onmouseover="this.style.background='var(--accent-dim)';this.style.color='var(--accent)';this.style.borderColor='rgba(79,195,247,.35)'"
          onmouseout="this.style.background='rgba(255,255,255,.03)';this.style.color='var(--ink-muted)';this.style.borderColor='var(--line)'">
          ${{p.name}}
        </button>
      `).join("");
      // Show step 1
      document.getElementById("prov-step1").style.display = "block";
      document.getElementById("prov-step2").style.display = "none";
      document.getElementById("prov-key-input").value = "";
      const overlay = document.getElementById("provider-overlay");
      overlay.style.opacity = "1";
      overlay.style.pointerEvents = "all";
    }}

    function selectProvider(id) {{
      _selProv = PROVIDERS.find(p => p.id === id);
      if (!_selProv) return;
      document.getElementById("prov-name-title").textContent = _selProv.name;
      document.getElementById("prov-env-code").textContent = _selProv.env;
      document.getElementById("prov-cmd-preview").textContent =
        `opencode --set-key ${{_selProv.id}}="<sua-key>"`;
      document.getElementById("prov-key-input").placeholder = _selProv.hint || "Cole sua key aqui…";
      // Check if already saved
      fetch(BASE + "/api/apikey?provider=" + _selProv.id)
        .then(r => r.json())
        .then(d => {{ if (d.apikey) document.getElementById("prov-key-input").value = d.apikey; }})
        .catch(() => {{}});
      document.getElementById("prov-step1").style.display = "none";
      document.getElementById("prov-step2").style.display = "block";
      setTimeout(() => document.getElementById("prov-key-input").focus(), 80);
    }}

    function provBack() {{
      document.getElementById("prov-step1").style.display = "block";
      document.getElementById("prov-step2").style.display = "none";
      document.getElementById("prov-key-input").value = "";
    }}

    function closeProvider() {{
      const overlay = document.getElementById("provider-overlay");
      overlay.style.opacity = "0";
      overlay.style.pointerEvents = "none";
      _selProv = null;
    }}

    async function confirmProvider() {{
      const key = document.getElementById("prov-key-input").value.trim();
      if (!key) {{ toast("⚠️ Insira a API key.", "err"); return; }}
      if (!_selProv) {{ toast("⚠️ Selecione um provedor.", "err"); return; }}
      const prov = _selProv; // capture before closeProvider() sets _selProv = null
      closeProvider();

      // 1. Save key to Drive
      toast("💾 Salvando key no Drive…", "info");
      try {{
        const sr = await fetch(BASE + "/api/apikey", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ provider: prov.id, env: prov.env, apikey: key }})
        }});
        const sd = await sr.json();
        if (!sd.ok) {{ toast("❌ Erro ao salvar: " + (sd.error || ""), "err"); return; }}
        toast("✅ Key salva no Drive!", "ok");
      }} catch(e) {{
        toast("❌ Falha ao salvar key: " + e.message, "err");
        return;
      }}

      // 2. Run: export ENV="key" && opencode
      const cmd = `export ${{prov.env}}="${{key}}" && opencode`;
      toast("🔌 Configurando provedor e reiniciando terminal…", "info");
      try {{
        await fetch(BASE + "/api/run_terminal", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ command: cmd, no_fallback: true }})
        }});
        const fr = document.getElementById("terminal-frame");
        const origSrc = fr.src.split("?")[0];
        fr.src = "about:blank";
        setTimeout(() => {{
          fr.src = origSrc + "?t=" + Date.now();
          toast("✅ " + prov.name + " configurado! Terminal reaberto.", "ok");
        }}, 3500);
      }} catch(e) {{ toast("❌ Erro ao rodar comando.", "err"); }}
    }}

    /* ── Load saved keys on startup ─────────────────────────────── */
    window.addEventListener("load", () => {{
      fetch(BASE + "/api/apikey/apply", {{ method: "POST" }}).catch(() => {{}});
    }});
  </script>
</body>
</html>"""
    
    os.makedirs(WRAPPER_DIR, exist_ok=True)
    with open(os.path.join(WRAPPER_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(wrapper_html)


def start_wrapper_server():
    # Determine correct backup dir — prefer the known Drive path
    _pesquisai_drive = "/content/drive/My Drive/PesquisAI"
    if os.path.isdir(_pesquisai_drive):
        _base = _pesquisai_drive
    elif os.path.isdir(_folder_path) and "drive" in _folder_path.lower():
        _base = _folder_path
    else:
        _base = _folder_path
    DRIVE_BACKUP_DIR = os.path.join(_base, "backups")
    os.makedirs(DRIVE_BACKUP_DIR, exist_ok=True)
    print(f"📁 Backup dir: {DRIVE_BACKUP_DIR}")
    
    # Possible opencode config/auth file locations
    OPENCODE_CONFIG_CANDIDATES = [
        os.path.expanduser("~/.config/opencode/auth.json"),
        os.path.expanduser("~/.config/opencode/config.json"),
        os.path.expanduser("~/.opencode/auth.json"),
        os.path.expanduser("~/.opencode/config.json"),
        "/root/.config/opencode/auth.json",
        "/root/.config/opencode/config.json",
        "/root/.opencode/auth.json",
        "/root/.opencode/config.json",
    ]
    DRIVE_CONFIG_BACKUP = os.path.join(DRIVE_BACKUP_DIR, "opencode_auth.json")
    
    def find_opencode_config():
        """Return the first existing opencode config/auth file."""
        for p in OPENCODE_CONFIG_CANDIDATES:
            if os.path.exists(p):
                return p
        # Also search dynamically
        try:
            r = subprocess.run(
                ["find", "/root", os.path.expanduser("~"), "-name", "auth.json", "-path", "*/opencode/*"],
                capture_output=True, text=True, timeout=3
            )
            hits = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if hits:
                return hits[0]
        except Exception:
            pass
        return None
    
    def save_opencode_config_to_drive():
        """Copy opencode auth/config to Drive backup folder."""
        src = find_opencode_config()
        if src and os.path.exists(src):
            shutil.copy2(src, DRIVE_CONFIG_BACKUP)
            return src
        return None
    
    def restore_opencode_config_from_drive():
        """Restore opencode auth/config from Drive backup if it exists."""
        if not os.path.exists(DRIVE_CONFIG_BACKUP):
            return False
        # Restore to all candidate locations to ensure opencode finds it
        restored = False
        for dest in OPENCODE_CONFIG_CANDIDATES:
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(DRIVE_CONFIG_BACKUP, dest)
                restored = True
            except Exception:
                pass
        return restored
    
    # Auto-restore opencode config from Drive on startup
    if restore_opencode_config_from_drive():
        print(f"🔑 Config do OpenCode restaurada do Drive.")
    
    # Auto-load all saved provider keys into environment on startup
    _keys_file = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
    if os.path.exists(_keys_file):
        try:
            with open(_keys_file, "r") as _kf:
                _saved_keys = json.load(_kf)
            _loaded = []
            for _k, _v in _saved_keys.items():
                if _k.startswith("_env_"):
                    continue
                _env_var = _saved_keys.get(f"_env_{_k}", "")
                if _env_var and _v:
                    os.environ[_env_var] = _v
                    _env[_env_var] = _v
                    # Also write to bashrc so bash -i sessions pick it up
                    try:
                        _bashrc = os.path.expanduser("~/.bashrc")
                        _marker = f"# opencode-key-{_k}"
                        _export = f'export {_env_var}="{_v}"'
                        _lines = open(_bashrc).readlines() if os.path.exists(_bashrc) else []
                        _lines = [l for l in _lines if _marker not in l and (_env_var not in l or "export" not in l)]
                        _lines.append(f"{_export}  {_marker}\n")
                        open(_bashrc, "w").writelines(_lines)
                    except Exception:
                        pass
                    _loaded.append(_env_var)
            if _loaded:
                print(f"🔑 Keys carregadas do Drive: {', '.join(_loaded)}")
        except Exception:
            pass
    
    def _run(cmd, **kw):
        return subprocess.run(cmd, capture_output=True, text=True, env=_env, **kw)
    
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        
        def _json(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        
        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.end_headers()
        
        def do_GET(self):
            p = urlparse(self.path).path
            
            if p in ("/", "/index.html"):
                idx = os.path.join(WRAPPER_DIR, "index.html")
                content = open(idx, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            
            if p == "/api/sessions":
                r = _run(cmd=["opencode", "session", "list", "--format", "json"])
                try:
                    sessions = json.loads(r.stdout) if r.stdout.strip() else []
                except Exception:
                    sessions = [{"id": l.strip()} for l in r.stdout.splitlines() if l.strip()]
                self._json(200, {"sessions": sessions})
                return
            
            if p == "/api/backups":
                try:
                    files = sorted(
                        [f for f in os.listdir(DRIVE_BACKUP_DIR) if f.endswith(".json") and not f.startswith(".")],
                        reverse=True
                    )
                except Exception:
                    files = []
                self._json(200, {"backups": files})
                return
            
            if p == "/api/debug":
                keys_file = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
                keys_exist = os.path.exists(keys_file)
                keys_data = {}
                if keys_exist:
                    try:
                        with open(keys_file) as f:
                            raw = json.load(f)
                        # Mask key values for security
                        keys_data = {k: (v[:6]+"…" if not k.startswith("_env_") and v else v) for k, v in raw.items()}
                    except Exception as e:
                        keys_data = {"error": str(e)}
                self._json(200, {
                    "drive_backup_dir": DRIVE_BACKUP_DIR,
                    "drive_dir_exists": os.path.isdir(DRIVE_BACKUP_DIR),
                    "keys_file_exists": keys_exist,
                    "keys_data": keys_data,
                    "opencode_bin": _opencode_bin,
                    "env_keys": [k for k in _env if "KEY" in k or "TOKEN" in k or "SECRET" in k],
                })
                return
            
            if p == "/api/apikey":
                qs = parse_qs(urlparse(self.path).query)
                provider = qs.get("provider", [""])[0].strip()
                keys_file = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
                try:
                    with open(keys_file, "r") as f:
                        keys = json.load(f)
                except Exception:
                    keys = {}
                if provider:
                    self._json(200, {"apikey": keys.get(provider, "")})
                else:
                    self._json(200, {"keys": keys})
                return
            
            self.send_error(404)
        
        def do_POST(self):
            p = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            
            if p == "/api/apikey":
                provider = body.get("provider", "").strip()
                env_var  = body.get("env", "").strip()
                key      = body.get("apikey", "").strip()
                if not key or not provider:
                    self._json(400, {"error": "provider e apikey obrigatórios."})
                    return
                # 1. Save to Drive .keys.json
                keys_file = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
                try:
                    try:
                        with open(keys_file, "r") as f:
                            keys = json.load(f)
                    except Exception:
                        keys = {}
                    keys[provider] = key
                    if env_var:
                        keys[f"_env_{provider}"] = env_var
                    with open(keys_file, "w") as f:
                        json.dump(keys, f, indent=2)
                except Exception as e:
                    self._json(500, {"error": f"Falha ao salvar no Drive: {e}"})
                    return
                # 2. Inject into current process env
                if env_var:
                    os.environ[env_var] = key
                    _env[env_var] = key
                # 3. Write into opencode config file so it persists across restarts
                # opencode reads provider keys from env vars — ensure ~/.bashrc exports them too
                bashrc = os.path.expanduser("~/.bashrc")
                try:
                    marker = f"# opencode-key-{provider}"
                    export_line = f'export {env_var}="{key}"'
                    lines = []
                    if os.path.exists(bashrc):
                        with open(bashrc, "r") as f:
                            lines = f.readlines()
                    # Remove previous entry for this provider
                    lines = [l for l in lines if marker not in l and (env_var not in l or "export" not in l)]
                    lines.append(f"{export_line}  {marker}\n")
                    with open(bashrc, "w") as f:
                        f.writelines(lines)
                except Exception:
                    pass
                self._json(200, {"ok": True})
                return
            
            if p == "/api/apikey/apply":
                # Inject all saved keys into the current environment
                keys_file = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
                applied = []
                try:
                    with open(keys_file, "r") as f:
                        keys = json.load(f)
                    for k, v in keys.items():
                        if k.startswith("_env_"):
                            # This is a mapping entry, skip
                            continue
                        env_var = keys.get(f"_env_{k}", "")
                        if env_var and v:
                            os.environ[env_var] = v
                            _env[env_var] = v
                            applied.append(env_var)
                    self._json(200, {"ok": True, "applied": applied})
                except Exception:
                    self._json(200, {"ok": False, "reason": "no keys stored"})
                return
            
            if p == "/api/run_terminal":
                cmd = body.get("command", "").strip()
                no_fallback = body.get("no_fallback", False)
                if not cmd:
                    self._json(400, {"error": "Comando vazio."})
                    return
                # Reload all saved provider keys into _env before restarting ttyd
                keys_file = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
                try:
                    with open(keys_file, "r") as f:
                        saved_keys = json.load(f)
                    for k, v in saved_keys.items():
                        if k.startswith("_env_"):
                            continue
                        env_var = saved_keys.get(f"_env_{k}", "")
                        if env_var and v:
                            _env[env_var] = v
                            os.environ[env_var] = v
                except Exception:
                    pass
                # Hard kill ttyd + opencode
                subprocess.run(
                    "pkill -9 -f ttyd 2>/dev/null; pkill -9 -f opencode 2>/dev/null; true",
                    shell=True
                )
                time.sleep(1.5)
                # Build bash -c command string
                # no_fallback=True → cmd is already the final invocation (e.g. "opencode -s xyz")
                # no_fallback=False → run cmd, then return to opencode afterwards
                if no_fallback:
                    bash_cmd = f"{cmd}; exec bash"
                else:
                    bash_cmd = f"{cmd}; {_opencode_bin}; exec bash"
                subprocess.Popen(
                    ["ttyd", "--writable", "-p", str(TERMINAL_PORT),
                     "bash", "-i", "-c", bash_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=_env,
                )
                self._json(200, {"ok": True, "command": cmd})
                return
            
            if p == "/api/backup":
                os.makedirs(DRIVE_BACKUP_DIR, exist_ok=True)
                
                session_id = body.get("session_id", "")
                ts = time.strftime("%H-%M-%S_%d-%m-%Y")
                
                if not session_id:
                    r = _run([_opencode_bin, "session", "list", "--format", "json"])
                    try:
                        sessions = json.loads(r.stdout)
                        session_id = sessions[0].get("id", "") if sessions else ""
                    except Exception:
                        lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
                        session_id = lines[0] if lines else ""
                
                if not session_id:
                    self._json(400, {"error": "Nenhuma sessão encontrada para exportar."})
                    return
                
                fname = f"backup_{session_id[:12]}_{ts}.json"
                outpath = os.path.join(DRIVE_BACKUP_DIR, fname)
                
                r = _run([_opencode_bin, "export", session_id, "--format", outpath])
                if r.returncode != 0 or not os.path.exists(outpath):
                    r2 = _run([_opencode_bin, "export", session_id])
                    if r2.returncode == 0 and r2.stdout.strip():
                        with open(outpath, "w") as f:
                            f.write(r2.stdout)
                    else:
                        self._json(500, {"error": r.stderr or r2.stderr or "Falha ao exportar."})
                        return
                
                self._json(200, {
                    "ok": True,
                    "file": fname,
                    "session_id": session_id,
                    "path": outpath,
                })
                return
            
            if p == "/api/restore":
                fname = body.get("file", "")
                if not fname:
                    self._json(400, {"error": "Nome do arquivo não informado."})
                    return
                fpath = os.path.join(DRIVE_BACKUP_DIR, fname)
                if not os.path.exists(fpath):
                    self._json(404, {"error": f"Arquivo não encontrado: {fname}"})
                    return
                
                # 1. Run import FIRST — block if it fails
                r = _run([_opencode_bin, "import", fpath])
                if r.returncode != 0:
                    self._json(500, {"error": r.stderr.strip() or "Falha ao importar."})
                    return
                
                # 2. Extract full session_id from file content via regex
                session_id = ""
                parse_error = ""
                try:
                    import re as _re
                    with open(fpath, "r", encoding="utf-8") as jf:
                        raw = jf.read(4096)
                    # Matches "id": "ses_XXXX" anywhere in the first 4KB
                    m = _re.search(r'"id"\s*:\s*"(ses_[a-zA-Z0-9]+)"', raw)
                    if m:
                        session_id = m.group(1)
                except Exception as e:
                    parse_error = str(e)
                
                # 3. Respond — frontend will call run_terminal with opencode -s {session_id}
                self._json(200, {
                    "ok": True,
                    "file": fname,
                    "session_id": session_id,
                    "parse_error": parse_error,
                    "import_stdout": r.stdout.strip()[:300],
                    "message": "Sessão importada com sucesso."
                })
                return
            
            self.send_error(404)
    
    threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", WRAPPER_PORT), Handler).serve_forever(),
        daemon=True,
    ).start()
    print(f"\n{next_joke('economia')}")
    print(f"🚀 Servidor wrapper iniciado na porta {WRAPPER_PORT}")


def show_ready_message():
    if not IN_COLAB or not display or not HTML:
        print("\n✨ PesquisAI pronto!\n")
        return
    
    display(HTML(f"""
<style>
@keyframes glow {{
    0%, 100% {{ box-shadow: 0 0 20px rgba(93, 186, 126, 0.3); }}
    50% {{ box-shadow: 0 0 40px rgba(93, 186, 126, 0.6); }}
}}
.ready-container {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px 20px 0px 20px;
}}
.ready-badge {{
    display: inline-flex;
    align-items: center;
    gap: 12px;
    padding: 16px 32px;
    background: rgba(93, 186, 126, 0.12);
    border: 2px solid rgba(93, 186, 126, 0.4);
    border-radius: 12px;
    animation: glow 2s ease-in-out infinite;
}}
.ready-icon {{
    font-size: 28px;
}}
.ready-text {{
    font-family: 'DM Mono', monospace;
    font-size: 18px;
    font-weight: 600;
    color: #5dba7e;
}}
</style>
<div class="ready-container">
    <div class="ready-badge">
        <span class="ready-icon">✨</span>
        <span class="ready-text">PesquisAI pronto!</span>
    </div>
</div>
"""))


def show_launch_button(banner_url):
    if not IN_COLAB or not display or not HTML:
        print(f"\n🎉 Acesse: {banner_url}")
        return
    
    display(HTML(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@500;700&family=Syne:wght@700;800&display=swap');
  @keyframes pulse-glow {{
    0%, 100% {{ box-shadow: 0 0 20px rgba(79,195,247,0.3), 0 4px 12px rgba(0,0,0,0.3); }}
    50% {{ box-shadow: 0 0 40px rgba(79,195,247,0.6), 0 6px 20px rgba(0,0,0,0.4); }}
  }}
  .btn-container {{
    display: flex;
    justify-content: center;
    padding: 20px;
    margin-top: 10px;
  }}
  .pesquisai-launch {{
    display: inline-flex; 
    align-items: center; 
    justify-content: center;
    gap: 16px;
    padding: 24px 56px; 
    font-family: "Syne", sans-serif; 
    font-size: 22px;
    font-weight: 800; 
    letter-spacing: 0.08em;
    color: #0d0f10; 
    background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 50%, #03a9f4 100%);
    border: none; 
    border-radius: 14px; 
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s ease;
    animation: pulse-glow 2.5s ease-in-out infinite;
    position: relative;
    overflow: hidden;
  }}
  .pesquisai-launch::before {{
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    transition: left 0.5s;
  }}
  .pesquisai-launch:hover::before {{
    left: 100%;
  }}
  .pesquisai-launch:hover {{
    transform: translateY(-4px) scale(1.02);
    filter: brightness(1.1);
    box-shadow: 0 12px 40px rgba(79,195,247,0.5), 0 8px 24px rgba(0,0,0,0.4);
  }}
  .pesquisai-launch:active {{
    transform: translateY(-1px) scale(0.99);
  }}
  .btn-icon {{
    font-size: 28px;
  }}
  .btn-text {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }}
  .btn-main {{
    font-size: 22px;
    font-weight: 800;
  }}
  .btn-sub {{
    font-family: "DM Mono", monospace;
    font-size: 11px;
    font-weight: 500;
    opacity: 0.8;
    letter-spacing: 0.1em;
  }}
  .pesquisai-launch .arrow {{ 
    font-size: 28px;
    font-weight: 500;
    transition: transform 0.2s ease; 
  }}
  .pesquisai-launch:hover .arrow {{ 
    transform: translateX(8px); 
  }}
</style>
<div class="btn-container">
  <a href="{banner_url}" target="_blank" class="pesquisai-launch">
    <span class="btn-icon">🚀</span>
    <span class="btn-text">
      <span class="btn-main">ABRIR O PESQUISAI</span>
      <span class="btn-sub">clique para começar</span>
    </span>
    <span class="arrow">→</span>
  </a>
</div>
"""))


def launch():
    global _drive_url
    
    resolve_opencode()
    install_ttyd()
    kill_previous()
    start_ttyd()
    
    if IN_COLAB and output:
        terminal_url = output.eval_js(f"google.colab.kernel.proxyPort({TERMINAL_PORT})")
        banner_url = output.eval_js(f"google.colab.kernel.proxyPort({WRAPPER_PORT})")
    else:
        terminal_url = f"http://localhost:{TERMINAL_PORT}"
        banner_url = f"http://localhost:{WRAPPER_PORT}"
    
    create_wrapper_html(terminal_url, _drive_url)
    start_wrapper_server()
    
    time.sleep(1)
    show_ready_message()
    show_launch_button(banner_url)
    
    return banner_url


if __name__ == "__main__":
    launch()
