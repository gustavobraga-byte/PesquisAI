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

from .constants import TERMINAL_PORT, WRAPPER_PORT, WRAPPER_DIR, VERSION, logger
from .jokes import next_joke
from .opencode_utils import find_opencode, build_env
from .security import load_encrypted_keys, save_encrypted_keys, sanitize_command


_opencode_bin: str | None = None
_env: dict | None = None
_drive_url: str = "https://drive.google.com/drive/my-drive"
_folder_path: str = "/content"


def set_drive_info(folder_path: str, drive_url: str) -> None:
    """Define as informações do Drive para uso no wrapper.

    Args:
        folder_path: Caminho absoluto para a pasta PesquisAI no Drive.
        drive_url: URL da web para a pasta no Google Drive.
    """
    global _drive_url, _folder_path
    _drive_url = drive_url
    _folder_path = folder_path


def load_keys_from_drive(
    backup_dir: str, env_dict: dict, write_bashrc: bool = True
) -> list[str]:
    """Carrega chaves de API CRIPTOGRAFADAS do Drive para o environment.

    As chaves são armazenadas criptografadas com AES-CBC + HMAC.
    A chave de criptografia fica em um arquivo SEPARADO no Drive.

    Args:
        backup_dir: Diretório onde os arquivos de chave estão.
        env_dict: Dicionário de environment para injetar as keys.
        write_bashrc: Se True, escreve export lines no ~/.bashrc.

    Returns:
        Lista de nomes de variáveis de ambiente carregadas.
    """
    saved_keys = load_encrypted_keys(backup_dir)
    if not saved_keys:
        return []

    loaded = []
    for k, v in saved_keys.items():
        if k.startswith("_env_") or not v:
            continue
        env_var = saved_keys.get(f"_env_{k}", "")
        if env_var and v:
            os.environ[env_var] = v
            env_dict[env_var] = v
            loaded.append(env_var)
            if write_bashrc:
                try:
                    bashrc = os.path.expanduser("~/.bashrc")
                    marker = f"# opencode-key-{k}"
                    export_line = f'export {env_var}="{v}"'
                    lines = open(bashrc).readlines() if os.path.exists(bashrc) else []
                    lines = [l for l in lines if marker not in l and (env_var not in l or "export" not in l)]
                    lines.append(f"{export_line}  {marker}\n")
                    open(bashrc, "w").writelines(lines)
                except Exception:
                    pass
    return loaded


def resolve_opencode() -> tuple[str, dict]:
    """Localiza o binário opencode e prepara o environment.

    Returns:
        Tupla (caminho_do_binario, dicionario_de_environment).
    """
    global _opencode_bin, _env
    try:
        _opencode_bin = find_opencode()
    except FileNotFoundError:
        logger.warning("opencode não encontrado, usando fallback 'opencode'")
        _opencode_bin = "opencode"
    _env = build_env()
    print(f"🔍 OpenCode binário: {_opencode_bin}")
    return _opencode_bin, _env


def install_ttyd() -> None:
    print(f"\n{next_joke('economia')}")
    print("📦 Instalando ttyd...")
    subprocess.run(
        ["apt-get", "update", "-qq"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    r1 = subprocess.run(
        ["apt-get", "install", "-y", "-qq", "ttyd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if r1.returncode != 0:
        print("⚠️  apt-get falhou. Tentando download manual do ttyd...")
        url = "https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64"
        rc = subprocess.run(
            ["curl", "-fsSL", url, "-o", "/usr/local/bin/ttyd"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        if rc == 0:
            subprocess.run(
                ["chmod", "+x", "/usr/local/bin/ttyd"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("✅ ttyd baixado manualmente.")
        else:
            print("⚠️  Download manual do ttyd também falhou. Continuando mesmo assim.")
    else:
        print("✅ ttyd instalado.")


def kill_previous():
    """Mata processos anteriores de ttyd e do wrapper."""
    subprocess.run(
        ["pkill", "-f", "ttyd"],
        capture_output=True,
        timeout=5,
    )
    subprocess.run(
        ["pkill", "-f", f"python3.*{WRAPPER_PORT}"],
        capture_output=True,
        timeout=5,
    )
    time.sleep(0.5)


def start_ttyd():
    print(f"\n{next_joke('economia')}")
    opencode_bin, env = resolve_opencode()
    
    subprocess.Popen(
        ["ttyd", "-p", str(TERMINAL_PORT), "bash", "-i", "-c", f"{opencode_bin} --prompt 'oi' ; exec bash"],
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
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css">
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

    .tb-icons {{ display:flex; align-items:center; gap:4px; margin-left:6px; }}
    .tb-icon {{
      display:inline-flex; align-items:center; justify-content:center;
      width:30px; height:30px; padding:0;
      background:transparent; border:1px solid var(--line);
      border-radius:var(--radius); cursor:pointer;
      color:var(--ink-muted); transition:background .15s,color .15s,border-color .15s;
    }}
    .tb-icon:hover {{
      background:var(--accent-dim); color:var(--accent);
      border-color:rgba(79,195,247,.4);
    }}
    .tb-icon:active {{ transform: scale(.94); }}
    .tb-icon svg {{ width:15px; height:15px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0; }}

    .health-row {{
      display:flex; align-items:center; justify-content:space-between;
      padding:9px 12px; font-size:11.5px; color:var(--ink);
      border-bottom:1px solid var(--line);
    }}
    .health-row:last-child {{ border-bottom:none; }}
    .health-status {{
      font-size:13px; font-weight:700; padding:2px 8px; border-radius:3px;
    }}
    .health-ok {{ background:var(--green-dim); color:var(--green); }}
    .health-warn {{ background:var(--amber-dim); color:var(--amber); }}
    .health-fail {{ background:var(--red-dim); color:var(--red); }}

    .session-search {{
      display:block; width:100%; padding:8px 10px; margin-bottom:10px;
      box-sizing:border-box; background:rgba(255,255,255,.04);
      border:1px solid var(--line); border-radius:var(--radius);
      color:var(--ink); font-family:'DM Mono',monospace; font-size:11px;
      outline:none; transition:border-color .15s;
    }}
    .session-search:focus {{ border-color:rgba(79,195,247,.4); }}
    .session-item {{
      display:flex; align-items:center; justify-content:space-between;
      padding:9px 12px; font-size:11.5px; color:var(--ink-muted);
      border-bottom:1px solid var(--line); cursor:pointer;
      transition:background .12s;
    }}
    .session-item:last-child {{ border-bottom:none; }}
    .session-item:hover {{ background:rgba(255,255,255,.04); color:var(--ink); }}
    .session-item .ses-meta {{ font-size:10px; color:var(--ink-muted); opacity:.7; }}

    .shortcut-row {{
      display:flex; align-items:center; justify-content:space-between;
      padding:8px 12px; font-size:11.5px; color:var(--ink);
      border-bottom:1px solid var(--line);
    }}
    .shortcut-row:last-child {{ border-bottom:none; }}
    .shortcut-key {{
      font-family:'DM Mono',monospace; font-size:10.5px; font-weight:600;
      padding:2px 8px; background:var(--accent-dim); color:var(--accent);
      border:1px solid rgba(79,195,247,.25); border-radius:3px;
    }}
   </style>
</head>
<body>

  <div id="topbar">
    <div class="logo">
      <span class="logo-p">Pesquis</span><span class="logo-ai">AI</span>
      <span>  <a href="https://github.com/gustavobraga-byte/PesquisAI/blob/main/CHANGELOG.md" target="_blank" class="logo-tag"> v{VERSION} </a> </span>
    </div>

    <div class="status">
      <span class="status-dot"></span>
      agente ativo
    </div>

    <div class="tb-icons">
      <button class="tb-icon" onclick="openHealth()" title="Dashboard de Saúde">
        <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </button>
      <button class="tb-icon" onclick="openSessions()" title="Histórico de Sessões">
        <svg viewBox="0 0 24 24"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/></svg>
      </button>
      <button class="tb-icon" onclick="openShortcuts()" title="Atalhos de Teclado">
        <svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10"/></svg>
      </button>
      <button class="tb-icon" onclick="toggleTheme()" id="theme-toggle" title="Alternar tema claro/escuro">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
      </button>
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
    <span style="color:var(--ink-muted)">UFV · Viçosa, MG - Brasil</span>

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

  <!-- Modal: Dashboard de Saúde -->
  <div id="health-overlay" onclick="if(event.target===this)closeHealth()" style="
    position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);
    display:flex;align-items:center;justify-content:center;
    z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:440px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">🩺 Dashboard de Saúde</div>
      <div id="health-list" style="max-height:340px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty">Carregando diagnóstico…</div>
      </div>
      <button onclick="closeHealth()" class="modal-close">Fechar</button>
    </div>
  </div>

  <!-- Modal: Histórico de Sessões -->
  <div id="sessions-overlay" onclick="if(event.target===this)closeSessions()" style="
    position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);
    display:flex;align-items:center;justify-content:center;
    z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:520px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">📜 Histórico de Sessões</div>
      <input id="session-search" class="session-search" placeholder="🔍 Buscar por id ou conteúdo…" oninput="filterSessions()">
      <div id="session-list" style="max-height:300px;overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="modal-empty">Carregando sessões…</div>
      </div>
      <button onclick="closeSessions()" class="modal-close">Fechar</button>
    </div>
  </div>

  <!-- Modal: Atalhos de Teclado -->
  <div id="shortcuts-overlay" onclick="if(event.target===this)closeShortcuts()" style="
    position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);
    display:flex;align-items:center;justify-content:center;
    z-index:99999;opacity:0;pointer-events:none;transition:opacity .2s;">
    <div style="background:#181b1e;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:24px;width:420px;max-width:94vw;box-shadow:0 28px 72px rgba(0,0,0,.7);">
      <div class="modal-title">⌨️ Atalhos de Teclado</div>
      <div style="border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px;">
        <div class="shortcut-row"><span>Copiar seleção</span><span class="shortcut-key">Segure o Shift e selecione</span></div>
        <div class="shortcut-row"><span>Interromper comando</span><span class="shortcut-key">Ctrl+C</span></div>
        <div class="shortcut-row"><span>Colar (Chrome)</span><span class="shortcut-key">Ctrl+Shift+V</span></div>
        <div class="shortcut-row"><span>Menu e opções</span><span class="shortcut-key">Ctrl+P</span></div>
        <div class="shortcut-row"><span>Alterar modelo</span><span class="shortcut-key">Ctrl+X m</span></div>
        <div class="shortcut-row"><span>Histórico anterior</span><span class="shortcut-key">↑</span></div>
        <div class="shortcut-row"><span>Histórico seguinte</span><span class="shortcut-key">↓</span></div>
      </div>
      <button onclick="closeShortcuts()" class="modal-close">Fechar</button>
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
      {{ id:"anthropic",    name:"Anthropic",             env:"ANTHROPIC_API_KEY",          hint:"sk-ant-…"    }},
      {{ id:"bedrock",      name:"AWS Bedrock",           env:"AWS_ACCESS_KEY_ID",          hint:"AKIA…"       }},
      {{ id:"azure",        name:"Azure OpenAI",          env:"AZURE_OPENAI_API_KEY",       hint:"…"           }},
      {{ id:"deepseek",     name:"DeepSeek",              env:"DEEPSEEK_API_KEY",           hint:"sk-…"        }},
      {{ id:"google",       name:"Google Gemini",         env:"GOOGLE_GENERATIVE_AI_API_KEY",         hint:"AIza…"       }},
      {{ id:"groq",         name:"Groq",                  env:"GROQ_API_KEY",               hint:"gsk_…"       }},
      {{ id:"mistral",      name:"Mistral",               env:"MISTRAL_API_KEY",            hint:"…"           }},
      {{ id:"nvidia",       name:"Nvidia NIM",            env:"NVIDIA_API_KEY",             hint:"nvapi-…"     }},
      {{ id:"openai",       name:"OpenAI",                env:"OPENAI_API_KEY",             hint:"sk-…"        }},
      {{ id:"opencode_go",  name:"OpenCode Go",           env:"OPENCODE_API_KEY",        hint:"sk-…"        }},
      {{ id:"opencode_zen", name:"OpenCode Zen",          env:"OPENCODE_API_KEY",       hint:"sk-…"        }},
      {{ id:"openrouter",   name:"OpenRouter",            env:"OPENROUTER_API_KEY",         hint:"sk-or-…"     }},
      {{ id:"together",     name:"Together AI",           env:"TOGETHER_API_KEY",           hint:"…"           }},
      {{ id:"vertex",       name:"Vertex AI",             env:"VERTEX_API_KEY",             hint:"…"           }},
      {{ id:"xai",          name:"xAI (Grok)",            env:"XAI_API_KEY",                hint:"xai-…"       }},
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

    /* ── 3.2 Dashboard de Saúde ──────────────────────────────── */
    async function openHealth() {{
      const overlay = document.getElementById("health-overlay");
      overlay.style.opacity = "1"; overlay.style.pointerEvents = "all";
      const list = document.getElementById("health-list");
      list.innerHTML = '<div class="modal-empty">Carregando diagnóstico…</div>';
      try {{
        const r = await fetch(BASE + "/api/health");
        const d = await r.json();
        if (!d.ok) {{ list.innerHTML = '<div class="modal-empty">Erro ao carregar.</div>'; return; }}
        const c = d.checks;
        const row = (label, ok, okText="OK", failText="Falha", warn=false) =>
          `<div class="health-row"><span>${{label}}</span>` +
          `<span class="health-status ${{warn ? 'health-warn' : (ok ? 'health-ok' : 'health-fail')}}">${{warn ? '⚠️' : (ok ? '✅ ' + okText : '❌ ' + failText)}}</span></div>`;
        const skillsList = c.skills_loaded && c.skills_loaded.length
          ? c.skills_loaded.join(", ") : "(nenhuma)";
        list.innerHTML =
          row("Google Drive montado", c.drive_mounted) +
          row("Diretório de backup existe", c.backup_dir_exists) +
          row("ttyd ativo", c.ttyd_alive) +
          row("OpenCode binário encontrado", c.opencode_found, "encontrado", "ausente") +
          row("Arquivo de keys existe", c.keys_store_exists, "sim", "não", !c.keys_store_exists && c.keys_loaded_count === 0 ? false : !c.keys_store_exists) +
          row("Chave de criptografia existe", c.encryption_key_exists, "sim", "não") +
          row(`Keys carregadas (${{c.keys_loaded_count}})`, c.keys_loaded_count > 0, "ativas", "0 keys", c.keys_loaded_count === 0) +
          row(`Skills instaladas (${{c.skills_count}})`, c.skills_count > 0, "OK", "0 skills", c.skills_count === 0) +
          `<div class="health-row"><span>Skills: ${{skillsList}}</span></div>` +
          row("ffmpeg disponível", c.ffmpeg_ok, "sim", "não", !c.ffmpeg_ok) +
          row(`Espaço livre (${{c.disk_free_mb}} / ${{c.disk_total_mb}} MB)`, c.disk_free_mb > 100, "suficiente", "baixo", c.disk_free_mb >= 0 && c.disk_free_mb < 100) +
          `<div class="health-row"><span>PesquisAI v${{d.version}}</span></div>`;
      }} catch(e) {{
        list.innerHTML = '<div class="modal-empty">Falha: ' + e.message + '</div>';
      }}
    }}
    function closeHealth() {{
      const o = document.getElementById("health-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }}

    /* ── 3.3 Histórico de Sessões ────────────────────────────── */
    let _allSessions = [];
    async function openSessions() {{
      const overlay = document.getElementById("sessions-overlay");
      overlay.style.opacity = "1"; overlay.style.pointerEvents = "all";
      const list = document.getElementById("session-list");
      list.innerHTML = '<div class="modal-empty">Carregando sessões…</div>';
      document.getElementById("session-search").value = "";
      try {{
        const r = await fetch(BASE + "/api/sessions");
        const d = await r.json();
        _allSessions = d.sessions || [];
        renderSessions(_allSessions);
      }} catch(e) {{
        list.innerHTML = '<div class="modal-empty">Falha: ' + e.message + '</div>';
      }}
    }}
    function renderSessions(sessions) {{
      const list = document.getElementById("session-list");
      if (!sessions || sessions.length === 0) {{
        list.innerHTML = '<div class="modal-empty">Nenhuma sessão encontrada.</div>';
        return;
      }}
      list.innerHTML = sessions.map(s => {{
        const id = typeof s === "string" ? s : (s.id || JSON.stringify(s).slice(0, 40));
        const meta = typeof s === "object" && s !== null
          ? Object.keys(s).filter(k => k !== "id").slice(0, 2).map(k => k + "=" + String(s[k]).slice(0,20)).join(" · ")
          : "";
        return `<div class="session-item" onclick="restoreSession('${{id}}')">` +
          `<span>${{id.length > 32 ? id.slice(0,32) + "…" : id}}<br><span class="ses-meta">${{meta || "sem metadados"}}</span></span>` +
          `<span class="restore-lbl">abrir</span></div>`;
      }}).join("");
    }}
    function filterSessions() {{
      const q = document.getElementById("session-search").value.toLowerCase().trim();
      if (!q) {{ renderSessions(_allSessions); return; }}
      const filtered = _allSessions.filter(s => {{
        const txt = typeof s === "string" ? s : JSON.stringify(s);
        return txt.toLowerCase().includes(q);
      }});
      renderSessions(filtered);
    }}
    async function restoreSession(id) {{
      closeSessions();
      const cmd = "opencode -s " + id;
      toast("🔄 Abrindo sessão " + id.slice(0,12) + "…", "info");
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
          toast("✅ Sessão aberta!", "ok");
        }}, 3500);
      }} catch(e) {{ toast("❌ Erro: " + e.message, "err"); }}
    }}
    function closeSessions() {{
      const o = document.getElementById("sessions-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }}

    /* ── 3.6 Atalhos de Teclado ──────────────────────────────── */
    function openShortcuts() {{
      const o = document.getElementById("shortcuts-overlay");
      o.style.opacity = "1"; o.style.pointerEvents = "all";
    }}
    function closeShortcuts() {{
      const o = document.getElementById("shortcuts-overlay");
      o.style.opacity = "0"; o.style.pointerEvents = "none";
    }}

    /* ── 3.8 Tema Claro/Escuro ────────────────────────────────── */
    async function toggleTheme() {{
      const btn = document.getElementById("theme-toggle");
      const cur = btn.dataset.theme || "pesquisai";
      const next = cur === "pesquisai" ? "pesquisai-light" : "pesquisai";
      try {{
        const r = await fetch(BASE + "/api/theme", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ theme: next }})
        }});
        const d = await r.json();
        if (d.ok) {{
          btn.dataset.theme = next;
          applyWrapperTheme(next);
          toast(next === "pesquisai-light" ? "☀️ Tema claro (UI + terminal)" : "🌙 Tema escuro (UI + terminal)", "info");
        }}
      }} catch(e) {{ toast("❌ Erro ao trocar tema: " + e.message, "err"); }}
    }}
    function applyWrapperTheme(theme) {{
      const root = document.documentElement;
      if (theme === "pesquisai-light") {{
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
      }} else {{
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
      }}
    }}
    async function loadInitialTheme() {{
      try {{
        const r = await fetch(BASE + "/api/theme");
        const d = await r.json();
        if (d.theme === "pesquisai-light") {{
          document.getElementById("theme-toggle").dataset.theme = "pesquisai-light";
          applyWrapperTheme("pesquisai-light");
        }}
      }} catch(e) {{}}
    }}

    /* ── Listener tecla '?' abre atalhos ─────────────────────── */
    document.addEventListener("keydown", (e) => {{
      if (e.key === "?" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {{
        e.preventDefault();
        openShortcuts();
      }}
      if (e.key === "Escape") {{
        closeHealth(); closeSessions(); closeShortcuts(); closeProvider(); closeModal();
      }}
    }});

    /* ── Load saved keys on startup ─────────────────────────────── */
    window.addEventListener("load", () => {{
      fetch(BASE + "/api/apikey/apply", {{ method: "POST" }}).catch(() => {{}});
      loadInitialTheme();
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
    
    _loaded_keys = load_keys_from_drive(DRIVE_BACKUP_DIR, _env)
    if _loaded_keys:
        print(f"🔑 Keys carregadas do Drive: {', '.join(_loaded_keys)}")
    
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
            
            if p == "/api/health":
                # Dashboard de Saude — consolida /api/diagnose + /api/debug
                import shutil as _shutil
                keys_file_new = os.path.join(DRIVE_BACKUP_DIR, "keys_store.json")
                keyfile_new = os.path.join(DRIVE_BACKUP_DIR, "keys_encryption_key.bin")
                # ttyd vivo?
                ttyd_alive = False
                try:
                    r = subprocess.run(
                        ["pgrep", "-f", "ttyd"], capture_output=True, text=True, timeout=2
                    )
                    ttyd_alive = r.returncode == 0 and bool(r.stdout.strip())
                except Exception:
                    ttyd_alive = False
                # skills carregadas
                skills_loaded = []
                try:
                    skills_loaded = sorted(
                        d for d in os.listdir(os.path.expanduser("~/.agents/skills"))
                        if os.path.isdir(os.path.join(os.path.expanduser("~/.agents/skills"), d))
                        and not d.startswith(".")
                    )
                except Exception:
                    pass
                # espaco em disco (MB)
                try:
                    du = _shutil.disk_usage("/content/drive/My Drive" if os.path.isdir("/content/drive/My Drive") else "/")
                    disk_free_mb = du.free // (1024 * 1024)
                    disk_total_mb = du.total // (1024 * 1024)
                except Exception:
                    disk_free_mb = disk_total_mb = -1
                # ffmpeg?
                ffmpeg_ok = _shutil.which("ffmpeg") is not None
                self._json(200, {
                    "ok": True,
                    "checks": {
                        "drive_mounted": os.path.ismount("/content/drive"),
                        "backup_dir_exists": os.path.isdir(DRIVE_BACKUP_DIR),
                        "ttyd_alive": ttyd_alive,
                        "opencode_bin": _opencode_bin or "",
                        "opencode_found": bool(_opencode_bin),
                        "keys_store_exists": os.path.exists(keys_file_new),
                        "encryption_key_exists": os.path.exists(keyfile_new),
                        "keys_loaded_count": len(_loaded_keys),
                        "keys_loaded": _loaded_keys,
                        "skills_loaded": skills_loaded,
                        "skills_count": len(skills_loaded),
                        "ffmpeg_ok": ffmpeg_ok,
                        "disk_free_mb": disk_free_mb,
                        "disk_total_mb": disk_total_mb,
                        "env_keys_found": [
                            k for k in sorted(os.environ)
                            if any(x in k for x in ["KEY", "TOKEN", "SECRET", "API"])
                        ],
                    },
                    "drive_backup_dir": DRIVE_BACKUP_DIR,
                    "version": VERSION,
                })
                return
            
            if p == "/api/theme":
                # Retorna tema atual do tui.json
                try:
                    with open(os.path.expanduser("~/.config/opencode/tui.json")) as f:
                        tui = json.load(f)
                    current = tui.get("theme", "pesquisai")
                except Exception:
                    current = "pesquisai"
                self._json(200, {"theme": current})
                return
            
            if p == "/api/diagnose":
                # Endpoint de diagnóstico completo
                keys_file_new = os.path.join(DRIVE_BACKUP_DIR, "keys_store.json")
                keys_file_old = os.path.join(DRIVE_BACKUP_DIR, ".keys.json")
                keyfile_new = os.path.join(DRIVE_BACKUP_DIR, "keys_encryption_key.bin")
                keyfile_old = os.path.join(DRIVE_BACKUP_DIR, ".keys_encryption_key")
                
                diag = {
                    "drive_backup_dir": DRIVE_BACKUP_DIR,
                    "drive_mounted": os.path.ismount("/content/drive"),
                    "backup_dir_exists": os.path.isdir(DRIVE_BACKUP_DIR),
                    "keys_store_new_exists": os.path.exists(keys_file_new),
                    "keys_store_old_exists": os.path.exists(keys_file_old),
                    "encryption_key_new_exists": os.path.exists(keyfile_new),
                    "encryption_key_old_exists": os.path.exists(keyfile_old),
                    "keys_loaded_count": len(_loaded_keys),
                    "keys_loaded": _loaded_keys,
                    "opencode_bin": _opencode_bin,
                    "env_keys_found": [
                        k for k in sorted(os.environ)
                        if any(x in k for x in ["KEY", "TOKEN", "SECRET", "API"])
                    ],
                    "bashrc_has_keys": False,
                }
                # Verifica se .bashrc tem exports de keys
                bashrc = os.path.expanduser("~/.bashrc")
                if os.path.exists(bashrc):
                    with open(bashrc) as f:
                        content = f.read()
                    diag["bashrc_has_keys"] = "opencode-key-" in content
                    diag["bashrc_key_count"] = content.count("opencode-key-")
                
                self._json(200, diag)
                return
            
            if p == "/api/debug":
                keys_file = os.path.join(DRIVE_BACKUP_DIR, "keys_store.json")
                key_file = os.path.join(DRIVE_BACKUP_DIR, "keys_encryption_key.bin")
                keys_exist = os.path.exists(keys_file)
                keyfile_exists = os.path.exists(key_file)
                keys_data = {}
                if keys_exist:
                    try:
                        raw = load_encrypted_keys(DRIVE_BACKUP_DIR)
                        keys_data = {k: (v[:4]+"…" if not k.startswith("_env_") and v else v) for k, v in raw.items()}
                    except Exception as e:
                        keys_data = {"error": str(e)}
                self._json(200, {
                    "drive_backup_dir": DRIVE_BACKUP_DIR,
                    "drive_dir_exists": os.path.isdir(DRIVE_BACKUP_DIR),
                    "keys_file_exists": keys_exist,
                    "encryption_keyfile_exists": keyfile_exists,
                    "keys_encrypted": keys_exist,
                    "keys_data_masked": keys_data,
                    "opencode_bin": _opencode_bin,
                    "env_keys": [k for k in _env if "KEY" in k or "TOKEN" in k or "SECRET" in k],
                })
                return
            
            if p == "/api/apikey":
                qs = parse_qs(urlparse(self.path).query)
                provider = qs.get("provider", [""])[0].strip()
                keys = load_encrypted_keys(DRIVE_BACKUP_DIR)
                if provider:
                    self._json(200, {"apikey": keys.get(provider, "")})
                else:
                    # Mascarar valores por segurança (mostrar só primeiros 4 chars)
                    masked = {
                        k: (v[:4] + "…" if not k.startswith("_env_") and v else v)
                        for k, v in keys.items()
                    }
                    self._json(200, {"keys": masked})
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
                # 1. Carregar chaves existentes e adicionar a nova
                existing = load_encrypted_keys(DRIVE_BACKUP_DIR)
                existing[provider] = key
                if env_var:
                    existing[f"_env_{provider}"] = env_var
                # 2. Salvar CRIPTOGRAFADO no Drive
                if not save_encrypted_keys(DRIVE_BACKUP_DIR, existing):
                    self._json(500, {"error": "Falha ao salvar chaves criptografadas no Drive."})
                    return
                # 3. Inject into current process env
                if env_var:
                    os.environ[env_var] = key
                    _env[env_var] = key
                # 4. Write into ~/.bashrc for persistence across restarts
                bashrc = os.path.expanduser("~/.bashrc")
                try:
                    marker = f"# opencode-key-{provider}"
                    export_line = f'export {env_var}="{key}"'
                    lines = []
                    if os.path.exists(bashrc):
                        with open(bashrc, "r") as f:
                            lines = f.readlines()
                    lines = [l for l in lines if marker not in l and (env_var not in l or "export" not in l)]
                    lines.append(f"{export_line}  {marker}\n")
                    with open(bashrc, "w") as f:
                        f.writelines(lines)
                except Exception:
                    pass
                self._json(200, {"ok": True})
                return
            
            if p == "/api/apikey/apply":
                applied = load_keys_from_drive(DRIVE_BACKUP_DIR, _env, write_bashrc=False)
                self._json(200, {"ok": True, "applied": applied}) if applied else \
                    self._json(200, {"ok": False, "reason": "no keys stored"})
                return
            
            if p == "/api/run_terminal":
                raw_cmd = body.get("command", "").strip()
                no_fallback = body.get("no_fallback", False)
                if not raw_cmd:
                    self._json(400, {"error": "Comando vazio."})
                    return
                
                # ── SANITIZAÇÃO OBRIGATÓRIA ─────────────────────
                # Impede command injection: ; & | ` $() ${} etc.
                valid, cmd_or_error = sanitize_command(raw_cmd)
                if not valid:
                    logger.warning("Comando rejeitado pela sanitização: %s", cmd_or_error)
                    self._json(403, {
                        "error": f"Comando não permitido por razões de segurança.",
                        "detail": cmd_or_error,
                    })
                    return
                
                cmd = cmd_or_error  # comando já sanitizado
                load_keys_from_drive(DRIVE_BACKUP_DIR, _env, write_bashrc=False)
                
                # Hard kill ttyd + opencode (shell=True é seguro aqui pois o comando é fixo)
                subprocess.run(
                    ["pkill", "-9", "-f", "ttyd"],
                    capture_output=True,
                    timeout=5,
                )
                subprocess.run(
                    ["pkill", "-9", "-f", "opencode"],
                    capture_output=True,
                    timeout=5,
                )
                time.sleep(1.5)
                
                # Build bash -c command string de forma segura
                # O comando do usuario (cmd) ja foi sanitizado acima.
                # O suffixo "; exec bash" e adicionado pelo codigo (nao pelo usuario),
                # entao nao precisa de segunda sanitizacao — isso causaria falso positivo
                # pois sanitize_command bloqueia ";" mesmo em comandos validos.
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
                self._json(200, {"ok": True})
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
                # ── Etapa 1: exportar para /tmp/ (SSD local, sem FUSE) ─────────
                tmp_path = os.path.join("/tmp", fname)

                r = _run(
                    [_opencode_bin, "export", session_id, "--format", tmp_path],
                    timeout=120,
                )
                export_ok = r.returncode == 0 and os.path.exists(tmp_path)

                # Fallback via stdout se o --format falhar
                if not export_ok:
                    r2 = _run(
                        [_opencode_bin, "export", session_id],
                        timeout=120,
                    )
                    if r2.returncode == 0 and len(r2.stdout) > 0:
                        with open(tmp_path, "w", encoding="utf-8") as f:
                            f.write(r2.stdout)
                        export_ok = os.path.exists(tmp_path)

                if not export_ok:
                    self._json(500, {
                        "error": (
                            r.stderr[:500] if r.stderr
                            else "Falha ao exportar sessão. Arquivo não foi criado."
                        )
                    })
                    return

                # ── Etapa 1.5: validar JSON do /tmp/ ANTES de copiar ─────────
                # Evita copiar arquivo truncado/invalido para o Drive
                tmp_size = os.path.getsize(tmp_path)
                tmp_json_valid = False
                try:
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        json.load(f)
                    tmp_json_valid = True
                except Exception as je:
                    logger.error(
                        "JSON exportado para /tmp/ e invalido (%s, %d bytes): %s. "
                        "Possivel truncamento no opencode export. Arquivo: %s",
                        fname, tmp_size, str(je)[:200], tmp_path,
                    )
                    self._json(500, {
                        "error": (
                            f"Sessao exportada mas JSON invalido ({tmp_size} bytes). "
                            f"Possivel truncamento no opencode export. "
                            f"Arquivo temporario preservado em: {tmp_path}"
                        )
                    })
                    return

                # ── Etapa 2: copiar para o Drive com validacao robusta ────────
                # Causa raiz de backups quebrados: Google Drive FUSE trunca
                # a escrita em limites de buffer interno (64KB/256KB/512KB),
                # mas getsize() reporta o tamanho alvo (metadata cache).
                # Solucao: validar JSON lendo de VOLTA do Drive apos copy.
                outpath = os.path.join(DRIVE_BACKUP_DIR, fname)

                # Remove arquivo anterior corrompido se existir
                if os.path.exists(outpath):
                    os.remove(outpath)

                # Lock para evitar concorrencia entre cliques rapidos
                import fcntl
                lock_path = os.path.join(DRIVE_BACKUP_DIR, ".backup.lock")
                lock_ok = False
                lock_fd = None
                try:
                    os.makedirs(DRIVE_BACKUP_DIR, exist_ok=True)
                    lock_fd = open(lock_path, "w")
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_ok = True
                except (ImportError, OSError, IOError):
                    # fcntl ausente (Windows) ou lock ocupado — prossegue sem lock
                    pass

                copy_ok = False
                copy_error = ""
                try:
                    for attempt in range(3):
                        try:
                            # Remove parcial de tentativa anterior
                            if os.path.exists(outpath):
                                os.remove(outpath)
                            shutil.copy2(tmp_path, outpath)
                            # Forcar sincronizacao FUSE: fsync + sleep + sync
                            try:
                                with open(outpath, "rb") as fsf:
                                    os.fsync(fsf.fileno())
                            except Exception:
                                pass
                            time.sleep(0.8 + attempt * 0.5)  # backoff
                            os.sync()  # flush global
                            time.sleep(0.3)
                            # Validacao 1: tamanho
                            dest_size = os.path.getsize(outpath)
                            if dest_size != tmp_size:
                                copy_error = f"tamanho divergente (tmp={tmp_size}, drive={dest_size})"
                                logger.warning("Backup %s: tentativa %d - %s", fname, attempt+1, copy_error)
                                continue
                            # Validacao 2: JSON valido (ler de volta do Drive)
                            try:
                                with open(outpath, "r", encoding="utf-8") as vf:
                                    json.load(vf)
                            except Exception as je:
                                copy_error = f"JSON invalido no Drive: {str(je)[:150]}"
                                logger.warning("Backup %s: tentativa %d - %s", fname, attempt+1, copy_error)
                                continue
                            # Validacao 3: heuristica potência-de-2 (FUSE chunk)
                            # Tamanhos exatos de 64KB/256KB/512KB/1MB sao suspeitos
                            if dest_size > 1023 and (dest_size & (dest_size - 1)) == 0:
                                logger.warning(
                                    "Backup %s: tamanho %d e potencia exata de 2 "
                                    "(possivel truncamento FUSE) — revalidando",
                                    fname, dest_size,
                                )
                                # Ja validamos JSON acima; se passou, esta ok
                                # mas logamos para diagnostico
                            copy_ok = True
                            break
                        except Exception as e:
                            copy_error = str(e)[:200]
                            time.sleep(1 + attempt)
                finally:
                    if lock_ok and lock_fd:
                        try:
                            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                            lock_fd.close()
                        except Exception:
                            pass

                # ── Etapa 3: resposta ────────────────────────────────────────
                if not copy_ok:
                    self._json(500, {
                        "error": (
                            f"Exportado e validado em /tmp/ ({tmp_size} bytes, JSON valido), "
                            f"mas falhou ao copiar para o Drive apos 3 tentativas. "
                            f"Causa provavel: truncamento FUSE em chunk de buffer. "
                            f"Ultimo erro: {copy_error}. "
                            f"Arquivo temporario valido preservado em: {tmp_path}"
                        )
                    })
                    return

                self._json(200, {
                    "ok": True,
                    "file": fname,
                    "session_id": session_id,
                    "path": outpath,
                    "size_bytes": tmp_size,
                    "tmp_path": tmp_path,
                    "validated": True,
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

                # Verificar integridade: arquivo truncado é rejeitado
                file_size = os.path.getsize(fpath)
                if file_size < 100:
                    self._json(400, {
                        "error": f"Arquivo de backup corrompido ou vazio ({file_size} bytes)."
                    })
                    return

                # Validar JSON antes de copiar (FUSE pode ter truncado)
                try:
                    with open(fpath, "r", encoding="utf-8") as jf:
                        json.load(jf)
                except Exception as je:
                    import math as _math
                    is_pow2 = file_size > 0 and (file_size & (file_size - 1)) == 0
                    hint = (
                        " (tamanho e potencia exata de 2 — truncamento FUSE classico)"
                        if is_pow2 else ""
                    )
                    self._json(400, {
                        "error": (
                            f"Arquivo de backup corrompido: JSON invalido ({file_size} bytes{hint}). "
                            f"Causa: {str(je)[:150]}. "
                            f"Remova este backup e gere um novo via 'Salvar backup'."
                        )
                    })
                    return

                # 1. Copiar para /tmp/ primeiro (Drive FUSE é lento para leitura grande)
                tmp_restore = os.path.join("/tmp", f"restore_{fname}")
                try:
                    shutil.copy2(fpath, tmp_restore)
                except Exception as e:
                    self._json(500, {"error": f"Falha ao copiar backup para /tmp/: {e}"})
                    return

                # 2. Importar do /tmp/ (rápido e confiável)
                r = _run([_opencode_bin, "import", tmp_restore], timeout=120)
                if r.returncode != 0:
                    self._json(500, {
                        "error": r.stderr.strip()[:500] or "Falha ao importar."
                    })
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
            
            if p == "/api/theme":
                # Persiste escolha de tema (escuro/claro) em tui.json
                theme_name = body.get("theme", "").strip()
                if theme_name not in ("pesquisai", "pesquisai-light"):
                    self._json(400, {"error": "Tema inválido. Use 'pesquisai' ou 'pesquisai-light'."})
                    return
                try:
                    tui_path = os.path.expanduser("~/.config/opencode/tui.json")
                    os.makedirs(os.path.dirname(tui_path), exist_ok=True)
                    with open(tui_path, "w") as f:
                        json.dump({"$schema": "https://opencode.ai/tui.json", "theme": theme_name}, f, indent=2)
                    self._json(200, {"ok": True, "theme": theme_name})
                except Exception as e:
                    self._json(500, {"error": str(e)})
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
    
    # ═══ CARREGAR CHAVES ANTES DE INICIAR O TERMINAL ═══
    # Determina o diretório de backup para carregar as chaves
    _pesquisai_drive = "/content/drive/My Drive/PesquisAI"
    if os.path.isdir(_pesquisai_drive):
        _base = _pesquisai_drive
    elif os.path.isdir(_folder_path) and "drive" in _folder_path.lower():
        _base = _folder_path
    else:
        _base = _folder_path
    _pre_backup_dir = os.path.join(_base, "backups")
    os.makedirs(_pre_backup_dir, exist_ok=True)
    
    # Carrega chaves criptografadas do Drive ANTES do terminal
    _pre_loaded = load_keys_from_drive(_pre_backup_dir, _env, write_bashrc=True)
    if _pre_loaded:
        print(f"🔑 Keys carregadas do Drive: {', '.join(_pre_loaded)}")
    else:
        # Verifica se os arquivos existem para dar diagnóstico
        _keys_file = os.path.join(_pre_backup_dir, "keys_store.json")
        _old_keys_file = os.path.join(_pre_backup_dir, ".keys.json")
        _keyfile = os.path.join(_pre_backup_dir, "keys_encryption_key.bin")
        _old_keyfile = os.path.join(_pre_backup_dir, ".keys_encryption_key")
        
        if os.path.exists(_keys_file) or os.path.exists(_old_keys_file):
            print(
                "⚠️  Arquivo de chaves encontrado, mas não foi possível "
                "descriptografar. A chave de criptografia pode estar corrompida. "
                "Use '+ provedor' para reconfigurar."
            )
        else:
            print(
                "ℹ️  Nenhuma API key configurada. "
                "Use o botão '+ provedor' na interface para adicionar."
            )
    # ═══════════════════════════════════════════════════
    
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
