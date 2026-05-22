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

TERMINAL_PORT = 8000
WRAPPER_PORT = 8001
WRAPPER_DIR = "/tmp/pesquisai-wrapper"

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
    
    if "OPENCODE_BIN" in os.environ and os.path.isfile(os.environ["OPENCODE_BIN"]):
        _opencode_bin = os.environ["OPENCODE_BIN"]
    else:
        _candidates = [
            os.path.expanduser("~/.local/bin/opencode"),
            os.path.expanduser("~/bin/opencode"),
            "/root/.local/bin/opencode",
            "/root/bin/opencode",
            "/usr/local/bin/opencode",
            "/usr/bin/opencode",
        ]
        _found = next((p for p in _candidates if os.path.isfile(p)), None)
        
        if _found is None:
            _which = shutil.which("opencode")
            if _which:
                _found = _which
            else:
                result = subprocess.run(
                    ["find", "/root", "/home", "/usr/local", "-name", "opencode", "-type", "f"],
                    capture_output=True, text=True
                )
                hits = [l.strip() for l in result.stdout.splitlines() if l.strip()]
                _found = hits[0] if hits else "opencode"
        
        _opencode_bin = _found
    
    _extra_path = os.path.dirname(_opencode_bin) if os.path.isfile(_opencode_bin) else os.path.expanduser("~/.local/bin")
    
    _env = {
        **os.environ,
        "OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT": "1",
        "PATH": os.environ.get("PATH", "") + ":" + _extra_path,
    }
    
    print(f"🔍 OpenCode binário: {_opencode_bin}")
    return _opencode_bin, _env


def install_ttyd():
    print("📦 Instalando ttyd...")
    subprocess.run(
        "apt-get update -qq && apt-get install -y -qq ttyd",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print("✅ ttyd instalado.")


def kill_previous():
    subprocess.run("pkill -f ttyd 2>/dev/null || true", shell=True)
    subprocess.run(f"pkill -f 'python3.*{WRAPPER_PORT}' 2>/dev/null || true", shell=True)
    time.sleep(0.5)


def start_ttyd():
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
  toast("✅ " + (d.message || "Sessão importada!"), "ok");

  setTimeout(() => {{
    if (window.confirm("Sessão restaurada com sucesso! Para acessar a sessão restaurada você deve acessar 'switch session' no menu Ctrl + p .  Você deseja atualizar página agora?")) {{
      window.location.reload();
    }}
  }}, 800);

}} else {{
  toast("❌ " + (d.error || "Erro ao importar"), "err");
}}

      }} catch(e) {{
        toast("❌ Falha na conexão: " + e.message, "err");
      }}
    }}
  </script>
</body>
</html>"""
    
    os.makedirs(WRAPPER_DIR, exist_ok=True)
    with open(os.path.join(WRAPPER_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(wrapper_html)


def start_wrapper_server():
    DRIVE_BACKUP_DIR = os.path.join(_folder_path, "backups")
    os.makedirs(DRIVE_BACKUP_DIR, exist_ok=True)
    
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
                        [f for f in os.listdir(DRIVE_BACKUP_DIR) if f.endswith(".json")],
                        reverse=True
                    )
                except Exception:
                    files = []
                self._json(200, {"backups": files})
                return
            
            self.send_error(404)
        
        def do_POST(self):
            p = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            
            if p == "/api/backup":
                session_id = body.get("session_id", "")
                ts = time.strftime("%Y%m%d_%H%M%S")
                
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
                
                r = _run([_opencode_bin, "import", fpath])
                if r.returncode != 0:
                    self._json(500, {"error": r.stderr or "Falha ao importar."})
                    return
                
                self._json(200, {"ok": True, "file": fname, "message": "Sessão importada com sucesso."})
                return
            
            self.send_error(404)
    
    threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", WRAPPER_PORT), Handler).serve_forever(),
        daemon=True,
    ).start()
    print(f"🚀 Servidor wrapper iniciado na porta {WRAPPER_PORT}")


def show_launch_button(banner_url):
    if not IN_COLAB or not display or not HTML:
        print(f"\n🎉 Acesse: {banner_url}")
        return
    
    display(HTML(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@500&display=swap');
  .pesquisai-launch {{
    display: inline-flex; align-items: center; gap: 12px;
    padding: 12px 26px; margin-top: 16px;
    font-family: "DM Mono", monospace; font-size: 13px;
    font-weight: 500; letter-spacing: .06em;
    color: #0d0f10; background: #4fc3f7;
    border: none; border-radius: 5px; cursor: pointer;
    text-decoration: none;
    transition: filter .18s, transform .12s, box-shadow .3s;
  }}
  .pesquisai-launch:hover {{
    filter: brightness(1.08); transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(79,195,247,.3);
  }}
  .pesquisai-launch .arrow {{ transition: transform .18s; }}
  .pesquisai-launch:hover .arrow {{ transform: translateX(3px); }}
</style>
<a href="{banner_url}" target="_blank" class="pesquisai-launch">
  Abrir o PesquisAI <span class="arrow">→</span>
</a>
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
    show_launch_button(banner_url)
    
    return banner_url


if __name__ == "__main__":
    launch()
