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
# v0.4.2.2: __version__ foi MOVIDO para pesquisai/__version__.py
# (estava em /__version__.py). Mantemos fallback para robustez.
try:
    from .__version__ import get_greeting
except ImportError:
    def get_greeting(lang: str = "pt_BR") -> str:
        # Fallback v0.4.2.2: saudação curta + dica entre parênteses
        return "Olá! (Dica: A partir de agora responda em português brasileiro.)"


_opencode_bin: str | None = None
_env: dict | None = None
_drive_url: str = "https://drive.google.com/drive/my-drive"
_folder_path: str = "/content"
# v0.4.2.2: idioma atual persistido pelo backend (cookie + endpoint)
_current_lang: str = "pt_BR"
_LANG_COOKIE_FILE: str = os.path.expanduser("~/.config/pesquisai_lang")


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


def start_ttyd(lang: str | None = None):
    """Inicia o ttyd com saudação no idioma solicitado.

    Args:
        lang: Código do idioma (pt_BR, en_US, es_ES, fr_FR). Se None, usa
              o _current_lang global ou o env PESQUISAI_LANG.

    v0.4.2.2: ao invés de `--prompt 'oi'` genérico, usa saudação no idioma
              + instrução "(a partir de agora responda em X)".
    """
    print(f"\n{next_joke('economia')}")
    opencode_bin, env = resolve_opencode()

    # Resolve idioma (param > env > _current_lang > pt_BR)
    if lang is None:
        lang = os.environ.get("PESQUISAI_LANG") or _current_lang or "pt_BR"
    # Normaliza para o conjunto canônico
    _valid = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR"}
    short = (lang or "pt_BR").split("_")[0].lower()
    full_lang = _valid.get(short, lang if lang in _valid.values() else "pt_BR")

    greeting = get_greeting(full_lang)
    # Escapar aspas para o bash -c "..."
    safe_prompt = greeting.replace('"', '\\"').replace("'", "\\'")
    bash_cmd = f'{opencode_bin} --prompt "{safe_prompt}" ; exec bash'

    subprocess.Popen(
        ["ttyd", "-p", str(TERMINAL_PORT), "bash", "-i", "-c", bash_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    print(f"🚀 Terminal iniciado (idioma: {full_lang}).")
    time.sleep(2)


def restart_ttyd_with_lang(lang: str) -> bool:
    """Reinicia o ttyd com saudação no novo idioma.

    Usado pelo endpoint /api/lang quando o usuário troca o idioma.
    Retorna True se reiniciou, False se falhou.
    """
    global _current_lang
    try:
        # Mata ttyd + opencode existentes
        subprocess.run(["pkill", "-9", "-f", "ttyd"], capture_output=True, timeout=5)
        subprocess.run(["pkill", "-9", "-f", "opencode"], capture_output=True, timeout=5)
        time.sleep(1.0)
        # Persiste o idioma
        _current_lang = lang
        try:
            os.makedirs(os.path.dirname(_LANG_COOKIE_FILE), exist_ok=True)
            with open(_LANG_COOKIE_FILE, "w", encoding="utf-8") as f:
                f.write(lang)
        except Exception:
            pass
        # Reinicia ttyd com a saudação no novo idioma
        start_ttyd(lang=lang)
        return True
    except Exception as e:
        logger.error("Falha ao reiniciar ttyd com lang=%s: %s", lang, e)
        return False



# ───────────────────────────────────────────────────────────────────
# 🔧 PATCH v0.4.1 — Substitui a função create_wrapper_html original
# pela versão responsiva com tema escuro + idioma na UI.
# 
# Mudanças aplicadas:
#   1. 📱 Site responsivo (6 media queries + hamburger menu)
#   2. 🎨 Tema claro/escuro com reload do iframe do ttyd
#   3. 🌐 Seletor de idioma na topbar (4 idiomas: pt_BR, en_US, es_ES, fr_FR)
#   4. 🌙 Tema padrão ESCURO com anti-flash CSS
# 
# Compatibilidade: API inalterada (create_wrapper_html(terminal_url, drive_url))
# Detalhes: docs/PATCH_v0.4.1.md
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
            "Patch v0.4.1 não encontrado. Copie launch_app_responsive_v041.py "
            "para a mesma pasta de launch_app.py"
        )



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
    
    # v0.4.2.2: restaura idioma persistido (cookie/arquivo)
    global _current_lang
    try:
        if os.path.exists(_LANG_COOKIE_FILE):
            with open(_LANG_COOKIE_FILE, "r", encoding="utf-8") as f:
                _current_lang = (f.read() or "pt_BR").strip()
        elif os.environ.get("PESQUISAI_LANG"):
            _current_lang = os.environ["PESQUISAI_LANG"]
    except Exception:
        _current_lang = "pt_BR"
    print(f"🌐 Idioma inicial: {_current_lang}")
    
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

            if p == "/api/lang":
                # v0.4.2.2: retorna o idioma atual persistido
                self._json(200, {"lang": _current_lang, "greeting": get_greeting(_current_lang)})
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

            if p == "/api/agents":
                # v0.4.2: serve o AGENTS.md no idioma solicitado
                # Suporta ?lang=pt_BR | en_US | es_ES | fr_FR (default pt_BR)
                qs = parse_qs(urlparse(self.path).query)
                lang = (qs.get("lang", ["pt_BR"])[0] or "pt_BR").strip()
                lang_code = lang.split("_")[0].lower() if "_" in lang else lang.lower()
                # Map pt_BR -> pt, en_US -> en, es_ES -> es, fr_FR -> fr
                _valid = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR"}
                if lang_code in _valid:
                    full = _valid[lang_code]
                elif lang in _valid.values():
                    full = lang
                else:
                    full = "pt_BR"
                # Localiza o arquivo de diretriz apropriado.
                # Estrutura esperada:
                #   <raiz>/agents/AGENTS.<lang>.md   ← fonte primária (irmão de pesquisai/)
                #   <raiz>/pesquisai/launch_app.py    ← este arquivo
                _candidates = []
                # 1. Irmão do módulo pesquisai/ (caso padrão do projeto)
                here = os.path.dirname(os.path.abspath(__file__))
                parent = os.path.dirname(here)
                _candidates.append(os.path.join(parent, "agents"))
                # 2. Níveis acima (caso esteja rodando de subpastas)
                for _ in range(5):
                    here = os.path.dirname(here)
                    if here and here != os.path.dirname(here):
                        _candidates.append(os.path.join(here, "agents"))
                # 3. Folder do Drive configurado
                if _folder_path:
                    _candidates.append(os.path.join(_folder_path, "agents"))
                    _candidates.append(os.path.join(os.path.dirname(_folder_path), "agents"))
                # 4. CWD e home (último recurso)
                _candidates.append(os.path.join(os.getcwd(), "agents"))
                agents_dir = None
                tried_dirs = []
                for d in _candidates:
                    tried_dirs.append(d)
                    if os.path.isdir(d):
                        agents_dir = d
                        break
                short = full.split("_")[0]
                content = None
                tried_files = []
                if agents_dir:
                    for fname in (f"AGENTS.{short}.md", f"AGENTS.{full}.md"):
                        fpath = os.path.join(agents_dir, fname)
                        tried_files.append(fpath)
                        if os.path.isfile(fpath):
                            try:
                                with open(fpath, "r", encoding="utf-8") as f:
                                    content = f.read()
                                break
                            except Exception as e:
                                content = f"⚠️ Erro ao ler {fname}: {e}"
                                break
                if content is None:
                    self._json(200, {
                        "ok": False,
                        "error": f"AGENTS.md não encontrado para o idioma '{full}'.",
                        "tried_dirs": tried_dirs[:8],
                        "tried_files": tried_files,
                        "lang": full,
                    })
                    return
                self._json(200, {
                    "ok": True,
                    "lang": full,
                    "filename": f"AGENTS.{short}.md",
                    "content": content,
                })
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

            if p == "/api/lang":
                # v0.4.2.2: persiste idioma e reinicia ttyd com saudação
                # no novo idioma ao invés de --prompt "oi" genérico.
                lang_in = (body.get("lang", "") or "").strip()
                if not lang_in:
                    self._json(400, {"error": "lang obrigatório (pt_BR/en_US/es_ES/fr_FR)"})
                    return
                _valid = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR"}
                short = lang_in.split("_")[0].lower() if "_" in lang_in else lang_in.lower()
                full_lang = _valid.get(short, lang_in if lang_in in _valid.values() else "pt_BR")
                ok = restart_ttyd_with_lang(full_lang)
                if ok:
                    self._json(200, {
                        "ok": True,
                        "lang": full_lang,
                        "greeting": get_greeting(full_lang),
                        "message": f"ttyd reiniciado com saudação em {full_lang}",
                    })
                else:
                    self._json(500, {
                        "ok": False,
                        "error": "Falha ao reiniciar ttyd com o novo idioma.",
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
