import os
import subprocess
import time
import threading
import json
import gzip
import hashlib
import shutil
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import secrets
import re
import base64 as _b64

try:
    from google.colab import output
    from IPython.display import display, HTML, update_display
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
    output = None
    display = None
    HTML = None
    update_display = None

from .constants import (
    TERMINAL_PORT, WRAPPER_PORT, WRAPPER_DIR, VERSION, TUI_JSON, CLI_JSON,
    OPENCODE_DB_PATH, logger,
)
from .jokes import next_joke
from .opencode_config import (
    load_json_config,
    merge_cli_theme,
    mode_from_ui_theme,
    ui_theme_from_cli,
    write_json_atomic,
)

# v0.6.8 — POLÍTICA PAINEL ÚNICO (Colab): nenhum print verboso vai para stdout —
# todo feedback visual vem do painel de boot (_BootPanel). Em Colab o stdout é
# roteado para logger.debug; offline continua com prints normais.
if IN_COLAB:
    import builtins as _builtins
    import logging as _logging
    try:
        _logging.getLogger("google_auth_httplib2").setLevel(_logging.ERROR)
    except Exception:
        pass
    _orig_print = _builtins.print
    def _silent_print(*a, **k):
        try:
            # rotear para logger para não perder diagnóstico
            logger.debug(" ".join(str(x) for x in a))
        except Exception:
            pass
    _builtins.print = _silent_print

from .opencode_utils import (
    find_opencode,
    build_env,
    opencode_version_string,
    is_opencode_v2,
)
from .security import load_encrypted_keys, save_encrypted_keys, sanitize_command
from .run_fast import (
    ensure_ufvai_agent,
    preflight_ufvai_session,
    preflight_ufvai_session_info,
    remember_preflight_session,
    reset_preflight_cache,
    seed_ufvai_greeting,
)
from . import session_restore as _session_restore


_LAST_AGENT_ENSURE: float = 0.0
_AGENT_ENSURE_TTL_S: float = 30.0


def _ensure_ufvai_agent_before_spawn(where: str = "terminal") -> None:
    """Ajuste na v0.6.21 (14/10/2026 — SEM bump): terminal sempre inicia com UFVAI.

    Chamada ANTES de todo (re)spawn do terminal. A OpenCode V2 só usa o
    `default_agent` de opencode.json quando o agente existe, é visível e aceita
    `primary` — caso contrário inicia com `build` (doc oficial
    opencode.ai/v2/docs/agents, seção "Selection"). Reproduzido pelo autor:
    ao adicionar uma nova chave de API o motor iniciava em `build`, porque
    `agents/UFVAI.md`/`default_agent` só eram regrados no boot.

    Best-effort: JAMAIS impede o terminal de abrir — um terminal atrasado é
    pior que um aviso no log; a garantia roda de novo no próximo reinício.

    v0.7.5 (correção 23/10/2026 — SEM bump): memoização curta (30 s). A
    abertura normal chama esta função 2–3 vezes em poucos segundos
    (start_ttyd → troca de idioma → restore); regravar AGENTS.md (~30 KB) e
    opencode.json a cada chamada atrasava o terminal sem mudar nada.
    """
    global _LAST_AGENT_ENSURE
    now = time.monotonic()
    if (now - _LAST_AGENT_ENSURE) < _AGENT_ENSURE_TTL_S:
        return
    try:
        ok = ensure_ufvai_agent()
    except Exception as exc:  # noqa: BLE001 — spawn do terminal não pode falhar por isso
        logger.warning("ensure_ufvai_agent falhou (%s): %s", where, exc)
        return
    if not ok:
        logger.warning(
            "ensure_ufvai_agent NÃO gravou opencode.json (%s) — o motor pode "
            "iniciar com o agente `build` até o próximo reinício.", where,
        )
        return
    _LAST_AGENT_ENSURE = now


def _set_lang_only(lang: str, source: str = "browser") -> None:
    """Persiste o idioma SEM reiniciar o terminal (v0.7.5).

    Usado quando o navegador discorda do idioma detectado no boot. Antes,
    o frontend chamava o POST /api/lang normal, que matava o ttyd, criava
    OUTRA sessão e recarregava a página só para trocar a saudação.

    ``source="browser"`` grava a escolha no Drive: na próxima execução do
    Colab o boot já começa no idioma certo (antes, /root/.config sumia e
    tudo voltava para o inglês do locale do servidor).
    """
    global _current_lang
    _current_lang = lang
    _persist_lang(lang, source=source)
    _sync_terminal_locale(lang)


def _remember_ttyd_session(session_id: str | None) -> None:
    """Registra a sessão que o terminal passou a exibir (restore/comando).

    Um reinício posterior (idioma/chave/keepalive) reabre ESTA conversa.
    """
    global _current_ttyd_session
    sid = str(session_id or "").strip()
    _current_ttyd_session = sid or None
    if sid:
        remember_preflight_session(sid)


def _safe_isoformat(v):
    """Converte date/datetime/str para ISO string de forma segura (fix v0.6.10 cache BM25)."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    try:
        return v.isoformat()
    except Exception:
        return str(v)
try:
    from .telemetry import event as _tel_event, set_consent as _tel_set_consent
    from .telemetry import masked_state as _tel_masked_state, save_admin_config as _tel_save_admin
    from .telemetry import save_contact as _tel_save_contact, clear_contact as _tel_clear_contact, contact_status as _tel_contact_status
    from .telemetry import notify_active_user as _tel_notify_active_user
    from .telemetry import publish_backend_url as _tel_publish_backend_url
except Exception:  # pragma: no cover
    def _tel_event(*a, **k): pass
    def _tel_set_consent(*a, **k): pass
    def _tel_masked_state(*a, **k):
        return {"configured": False, "measurement_id": "", "api_secret_set": False,
                "source": "none", "consent_accepted": False, "consent_analytics": False,
                "kill_switch": False, "enabled": False}
    def _tel_save_admin(*a, **k):
        return False, "Telemetria indisponível."
    def _tel_save_contact(*a, **k):
        return False, "Contato indisponível."
    def _tel_clear_contact(*a, **k): pass
    def _tel_contact_status(*a, **k):
        return {"has_email": False, "email_masked": "", "contact_endpoint_set": False}
    def _tel_notify_active_user(*a, **k): pass
    def _tel_publish_backend_url(*a, **k): pass
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
# v0.6.15: inicia vazio para que _detect_system_lang() seja consultado na
# 1ª execução (antes caía sempre em "pt_BR" porque _current_lang era truthy).
_current_lang: str = ""
_LANG_COOKIE_FILE: str = os.path.expanduser("~/.config/pesquisai_lang")
# v0.6.0: token de sessão da UI + rate limit simples (segurança)
_SESSION_TOKEN: str | None = None
_RATE: dict[str, list[float]] = {}
# v0.6.5: handle do ttyd atual — permite matar a ÁRVORE do terminal
# (ttyd + bash + opencode) por grupo de processo, sem pkill -f global.
_TTYD_PROC: "subprocess.Popen | None" = None
# v0.7.5 (correção 23/10/2026 — SEM bump): sessão que o terminal está
# exibindo AGORA. Um reinício do ttyd (idioma/chave/keepalive) reabre esta
# mesma sessão em vez de pré-criar outra — era o que fazia o UFVAI abrir
# DUAS sessões na mesma entrada.
_current_ttyd_session: str | None = None

# v0.7.8: pasta de chaves efetivamente usada nesta execução (Drive ou
# `~/PesquisAI`). Definida em `start_wrapper_server()` e consumida por
# `_keys_backup_dir()` ao reiniciar o serviço com as chaves novas.
_KEYS_BACKUP_DIR: str | None = None

# v0.7.5+ (sem bump): saudação pendente por sessão. A mensagem padrão é
# semeada quando o CLIENTE informa o idioma (POST /api/lang), e não mais no
# spawn do ttyd — o servidor não sabe o idioma do navegador.
_PENDING_GREETING: dict[str, bool] = {}
_GREETING_LOCK = threading.Lock()

# v0.7.5+ (sem bump): auto-cura do terminal. O ttyd pode morrer (SIGKILL de
# uma execução anterior) e a porta 8000 fica fechada — a interface mostrava o
# splash "Iniciando terminal…" para sempre. Aqui ele é religado ANEXANDO à
# sessão tmux existente (`tmux new -A`), então a conversa continua a mesma.
_LAST_TTYD_REVIVE: float = 0.0
_TTYD_REVIVE_LOCK = threading.Lock()
_TTYD_REVIVE_MIN_S: float = 5.0



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
                    with open(bashrc) as _rf:
                        lines = _rf.readlines() if os.path.exists(bashrc) else []
                    lines = [l for l in lines if marker not in l and (env_var not in l or "export" not in l)]
                    lines.append(f"{export_line}  {marker}\n")
                    with open(bashrc, "w") as _wf:
                        _wf.writelines(lines)
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
    _ver = opencode_version_string()
    if _ver:
        print(f"🔧 OpenCode versão: {_ver}")
    return _opencode_bin, _env


def _workspace_dir() -> str:
    """Diretório de trabalho do UFVAI: a pasta PesquisAI (Drive no Colab).

    v0.7.7 (correção 27/10/2026 — SEM bump): o terminal abria em ``/root``
    porque cada ponto de spawn resolvia o projeto por conta própria e, quando
    ``DRIVE_PATH`` ainda não existia (Drive montando) ou quando o caminho era
    o do modo offline, caía em ``os.getcwd()`` — o cwd do kernel do Colab.
    Aqui a ordem é explícita e NUNCA devolve a raiz:

      1. ``DRIVE_PATH`` (``/content/drive/My Drive/PesquisAI``) se existir;
      2. ``~/PesquisAI`` (modo offline/.deb) se existir;
      3. ``DRIVE_PATH`` mesmo que precise ser criado (o chamador garante);
      4. ``~/PesquisAI`` como último recurso.
    """
    try:
        from .constants import DRIVE_PATH as _drive_path
    except Exception:  # noqa: BLE001
        _drive_path = os.path.join(os.environ.get("HOME", "/"), "PesquisAI")
    home_dir = os.path.join(os.environ.get("HOME", "/"), "PesquisAI")
    for candidate in (_drive_path, home_dir):
        try:
            if candidate and os.path.isdir(candidate):
                return candidate
        except OSError:
            continue
    target = _drive_path or home_dir
    try:
        os.makedirs(target, exist_ok=True)
    except OSError:
        return home_dir
    return target


# ── OpenCode V2 · tema do terminal (cli.json) ─────────────────
# Um só tema (pesquisai) cobre claro e escuro: o modo fica em theme.mode.
# A interface web continua usando os nomes 'pesquisai' / 'pesquisai-light'.

def _read_theme() -> str:
    """Tema da interface web conforme o modo do cli.json (dark → pesquisai)."""
    ok, cli = load_json_config(CLI_JSON)
    if ok and cli:
        return ui_theme_from_cli(cli)
    return "pesquisai"


def _write_theme(theme_name: str) -> None:
    """Grava o modo do tema UFVAI em cli.json (OpenCode V2).

    'pesquisai-light' → theme.mode 'light'; 'pesquisai' → 'dark'. O nome do
    tema do terminal passa a ser sempre 'pesquisai' porque o usuário escolheu
    explicitamente o tema UFVAI na interface.
    """
    ok, cli = load_json_config(CLI_JSON)
    if not ok:
        raise OSError("cli.json existe mas não pode ser interpretado; tema não alterado")
    write_json_atomic(CLI_JSON, merge_cli_theme(cli, "pesquisai", mode_from_ui_theme(theme_name)))


def install_ttyd() -> None:
    # v0.6.9-5: se ttyd já está bundle no .deb, não tenta apt (evita falha offline)
    import shutil as _shutil
    if _shutil.which("ttyd") or os.path.isfile("/usr/local/bin/ttyd"):
        print("✅ ttyd já instalado — pulando.")
        return
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
        # v0.6.9-5: tenta /usr/local/bin, fallback para ~/bin se sem permissão
        target = "/usr/local/bin/ttyd"
        rc = subprocess.run(
            ["curl", "-fsSL", url, "-o", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        if rc != 0 or not os.path.isfile(target):
            # fallback local
            import pathlib
            _local_bin = os.path.expanduser("~/bin/ttyd")
            os.makedirs(os.path.dirname(_local_bin), exist_ok=True)
            rc2 = subprocess.run(
                ["curl", "-fsSL", url, "-o", _local_bin],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            if rc2 == 0:
                subprocess.run(
                    ["chmod", "+x", _local_bin],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # garante no PATH desta sessão
                if os.path.dirname(_local_bin) not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{os.path.dirname(_local_bin)}:{os.environ['PATH']}"
                print(f"✅ ttyd baixado manualmente em {_local_bin}.")
                return
        if rc == 0:
            subprocess.run(
                ["chmod", "+x", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("✅ ttyd baixado manualmente.")
        else:
            print("⚠️  Download manual do ttyd também falhou. Continuando mesmo assim.")
    else:
        print("✅ ttyd instalado.")


def kill_previous():
    """Mata processos anteriores de ttyd e do wrapper.

    v0.6.5: pkill -x (COMM exato) em vez de -f — não casa processos cuja
    LINHA DE COMANDO meramente contém 'ttyd' (ex.: bash -i -c 'ttyd …',
    agente hospedeiro, editores). Mesmo efeito, sem danos colaterais.
    """
    subprocess.run(
        ["pkill", "-9", "-x", "ttyd"],
        capture_output=True,
        timeout=5,
    )
    _tmux_kill_session()  # boot começa de sessão limpa (a sessão tmux não morre com o ttyd)
    # v0.7.5: um BOOT novo começa com sessão NOVA. Sem isso, reexecutar a
    # célula de lançamento no mesmo kernel reabriria a conversa anterior
    # (o cache de preflight é por processo).
    global _current_ttyd_session
    _current_ttyd_session = None
    reset_preflight_cache()
    subprocess.run(
        ["pkill", "-f", f"python3.*{WRAPPER_PORT}"],
        capture_output=True,
        timeout=5,
    )
    time.sleep(0.5)


# ── v0.4.2.5: Touch scroll + pinch-zoom para ttyd/xterm.js em mobile ──
# O xterm.js nativamente só rola via wheel events (desktop). Em mobile,
# touch events não são convertidos para wheel — o scrollback fica inacessível.
# Estes helpers injetam JavaScript de touch handlers diretamente no HTML
# servido pelo ttyd (via flag --index), resolvendo scroll + zoom no mobile.

_TTYD_TOUCH_INDEX_PATH: str | None = None  # cache do caminho do HTML custom


def _get_touch_handler_script() -> str:
    """Retorna o script JS de touch scroll + seleção + zoom para injetar no ttyd.

    INJETADO NO <head> (antes do bundle do ttyd) para que o patch do
    WebSocket constructor capture o socket no momento da criação.

    Método primário de scroll: enviar escape sequences de mouse wheel (SGR)
    via WebSocket binário do ttyd (protocolo: opcode 48 + payload UTF-8).
    Reproduz o que o xterm.js faz no desktop ao receber wheel events.

    Recursos:
      1. 1 dedo arrastar → scroll (mouse wheel SGR via WebSocket)
      2. Long-press + arrastar → seleção de texto (MouseEvent sintético)
      3. 2 dedos pinçar → zoom (CSS zoom)
      4. Double-tap → reset zoom
    """
    return """<script>
(function(){'use strict';
// ====== PesquisAI — Touch Scroll + Seleção + Zoom para TUI no ttyd ======

var xtermElem=null, viewport=null, termContainer=null, zoomLevel=1, ready=false;
var term=null;

// --- CSS ---
var css=document.createElement('style');
css.textContent=[
  '.xterm,.xterm-viewport,.xterm-screen,.xterm-rows{touch-action:none!important}',
  '.xterm-viewport{overscroll-behavior:contain!important}',
  '#terminal{touch-action:none!important}',
  'body{overscroll-behavior:none!important;-webkit-touch-callout:none;margin:0;padding:0;overflow:hidden}',
  '.xterm{transform-origin:top left}'
].join('\\n');
(document.head||document.documentElement).appendChild(css);

// ====== CAPTURA DO WEBSOCKET (roda no <head>, antes do bundle do ttyd) ======
// Patch do CONSTRUCTOR: captura o socket no momento em que o ttyd o cria.
var capturedSocket=null;
var OrigWebSocket=window.WebSocket;
window.WebSocket=function(url,protocols){
  var ws=protocols?new OrigWebSocket(url,protocols):new OrigWebSocket(url);
  capturedSocket=ws;
  return ws;
};
window.WebSocket.prototype=OrigWebSocket.prototype;
window.WebSocket.OPEN=OrigWebSocket.OPEN;
window.WebSocket.CLOSED=OrigWebSocket.CLOSED;
window.WebSocket.CONNECTING=OrigWebSocket.CONNECTING;
window.WebSocket.CLOSING=OrigWebSocket.CLOSING;
// Backup: patch do prototype.send (captura em chamadas futuras)
var origSend=OrigWebSocket.prototype.send;
OrigWebSocket.prototype.send=function(data){
  if(!capturedSocket||capturedSocket.readyState!==1){capturedSocket=this}
  return origSend.call(this,data);
};

// ====== KEEPALIVE (v0.7.7, correção 27/10/2026 — SEM bump) ======
// O proxy do Colab derruba WebSocket ocioso (sem tráfego de APLICAÇÃO) em
// ~30–60 s; o ping do ttyd é controle de protocolo e não conta. Resultado:
// o terminal "desconectava" sozinho a cada minuto, mesmo sem ninguém tocar.
// A cada 20 s enviamos um RESIZE (protocolo do ttyd: '1' + JSON) com o
// tamanho ATUAL — é idempotente, não altera a tela e mantém o socket vivo.
setInterval(function(){
  var s=capturedSocket;
  if(!s||s.readyState!==1)return;
  try{
    var t=findTerminal();
    var rows=(t&&t.rows)||24, cols=(t&&t.cols)||80;
    s.send('1'+JSON.stringify({columns:cols,rows:rows}));
  }catch(e){}
},20000);

// ====== AUTO-RECONNECT (v0.7.5+; revisto em 27/10/2026) ======
// O cliente do ttyd só reconecta sozinho quando o close code != 1000; num
// reinício do servidor (troca de idioma, restore, auto-cura) ele fica em
// "Press ⏎ to Reconnect" / "Reconnecting..." esperando o usuário.
// v0.7.7: o reload antigo podia entrar em LAÇO (cada reload zerava o
// contador) e era ele próprio a causa das quedas de ~30 s. Agora:
//   1) Enter sintético no máximo 1×/5 s e só se o socket está fechado há >3 s;
//   2) reload só como último recurso, no máximo 2× por sessão de aba
//      (sessionStorage) e apenas se o terminal exibir "Reconnect"/"closed".
var _reconnectTries=0, _lastReconnectTry=0, _closedSince=0;
function _reloadBudget(){
  try{
    var k='ufvai_ttyd_reloads', now=Date.now();
    var v=JSON.parse(sessionStorage.getItem(k)||'{"n":0,"t":0}');
    if(now-v.t>600000){v={n:0,t:now}}
    if(v.n>=2)return false;
    v.n++;sessionStorage.setItem(k,JSON.stringify(v));return true;
  }catch(e){return false}
}
setInterval(function(){
  var s=capturedSocket;
  if(!s)return;
  if(s.readyState===1){_reconnectTries=0;_closedSince=0;return}
  var now=Date.now();
  if(!_closedSince)_closedSince=now;
  if(now-_closedSince<3000)return;
  if(now-_lastReconnectTry<5000)return;
  _lastReconnectTry=now;
  _reconnectTries++;
  var ta=document.querySelector('.xterm-helper-textarea');
  if(ta){
    try{ta.focus()}catch(e){}
    try{
      ta.dispatchEvent(new KeyboardEvent('keydown',{
        key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true
      }));
    }catch(e){}
  }
  if(_reconnectTries>=3){
    var txt=(document.body&&document.body.innerText)||'';
    if(/Reconnect|Connection closed|Desconect/i.test(txt) && _reloadBudget()){
      _reconnectTries=0;
      try{
        fetch('/health',{cache:'no-store'}).then(function(r){
          if(r&&r.ok){window.location.reload()}
        }).catch(function(){});
      }catch(e){}
    }
  }
},2500);

// --- Acessar window.term ---
function findTerminal(){
  if(term)return term;
  if(window.term){term=window.term;return term}
  return null;
}

// ====== ENVIAR DADOS AO TERMINAL (protocolo binário do ttyd) ======
// ttyd: Uint8Array[0]=48 (Command.INPUT) + dados UTF-8
function sendToPTY(data){
  var sock=capturedSocket;
  if(!sock||sock.readyState!==1)return false;
  try{
    var enc=new TextEncoder().encode(data);
    var payload=new Uint8Array(enc.length+1);
    payload[0]=48;
    payload.set(enc,1);
    origSend.call(sock,payload);
    return true;
  }catch(e){return false}
}

// ====== SCROLL: mouse wheel SGR via WebSocket ======
// Bubble Tea habilita mouse SGR (1006). Wheel up=button 64, down=button 65.
// ESC[<button;col;rowM
function sendWheel(direction){
  // direction: 1=scroll up, -1=scroll down
  var btn=direction>0?64:65;
  // Coordenadas: usar centro do terminal se disponível, senão 1;1
  var col=1,row=1;
  var t=findTerminal();
  if(t&&t.cols){col=Math.floor(t.cols/2)}
  if(t&&t.rows){row=Math.floor(t.rows/2)}
  var sgr='\\x1b[<'+btn+';'+col+';'+row+'M';
  return sendToPTY(sgr);
}

// Fallback via API interna do xterm.js (triggerDataEvent)
function sendWheelViaCore(direction){
  var t=findTerminal();
  if(!t)return false;
  try{
    var btn=direction>0?64:65;
    var seq='\\x1b[<'+btn+';1;1M';
    if(t._core&&t._core.coreService&&t._core.coreService.triggerDataEvent){
      t._core.coreService.triggerDataEvent(seq,true);return true;
    }
  }catch(e){}
  return false;
}

function doScroll(direction){
  // Primário: WebSocket binário (SGR mouse wheel)
  if(sendWheel(direction))return;
  // Fallback 1: API interna xterm.js
  if(sendWheelViaCore(direction))return;
  // Fallback 2: Page Up/Down via WebSocket
  sendToPTY(direction>0?'\\x1b[5~':'\\x1b[6~');
}

// ====== SCROLL (1 dedo arrastar) ======
var lastY=0,scrolling=false,startY=0,startT=0,startX=0,lastSendTime=0;
var isSelecting=false,longPressTimer=null,longPressTriggered=false;

function onTouchStart(e){
  if(e.touches.length===1){
    lastY=e.touches[0].clientY;startY=lastY;startT=Date.now();startX=e.touches[0].clientX;
    scrolling=false;longPressTriggered=false;isSelecting=false;
    findTerminal();
    longPressTimer=setTimeout(function(){
      longPressTriggered=true;isSelecting=true;scrolling=false;
      simulateMouseEvent('mousedown',e.touches[0].clientX,e.touches[0].clientY);
    },500);
  }
}

function onTouchMove(e){
  if(e.touches.length!==1)return;
  if(isSelecting){
    simulateMouseEvent('mousemove',e.touches[0].clientX,e.touches[0].clientY);
    e.preventDefault();return;
  }
  var cy=e.touches[0].clientY;
  var dy=lastY-cy;lastY=cy;
  if(!longPressTriggered&&Math.abs(cy-startY)>10){
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null}
    scrolling=true;
  }
  if(!scrolling)return;
  if(Math.abs(dy)<3)return;
  var cx=e.touches[0].clientX;
  if(Math.abs(cx-startX)>Math.abs(cy-startY)*2&&Math.abs(cy-startY)<30)return;
  var now=Date.now();
  if(now-lastSendTime<40)return;
  lastSendTime=now;
  var direction=dy>0?-1:1;
  doScroll(direction);
  e.preventDefault();e.stopPropagation();
}

function onTouchEnd(e){
  if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null}
  if(isSelecting){
    if(e.changedTouches.length>0){
      simulateMouseEvent('mouseup',e.changedTouches[0].clientX,e.changedTouches[0].clientY);
    }
    isSelecting=false;return;
  }
  if(scrolling&&e.changedTouches.length>0){
    var endY=e.changedTouches[0].clientY;
    var dt=Date.now()-startT;
    if(dt>0&&dt<400){
      var v=(startY-endY)/dt;
      if(Math.abs(v)>0.2){
        var direction=v>0?-1:1;
        var frames=Math.min(6,Math.ceil(Math.abs(v)*3));
        for(var i=0;i<frames;i++){
          (function(d,dir){setTimeout(function(){doScroll(dir)},d)})(i*60,direction);
        }
      }
    }
  }
  scrolling=false;
}

// ====== SELEÇÃO DE TEXTO (MouseEvent sintético) ======
function simulateMouseEvent(type,x,y){
  var target=viewport||xtermElem||document.querySelector('.xterm');
  if(!target)return;
  try{
    var ev=new MouseEvent(type,{
      bubbles:true,cancelable:true,view:window,button:0,
      buttons:type==='mousedown'?1:(type==='mousemove'?1:0),
      clientX:x,clientY:y,relatedTarget:null
    });
    target.dispatchEvent(ev);
  }catch(e){}
}

// ====== PINCH ZOOM + double-tap ======
var pinchDist=0,pinchZoom=1,pinching=false;
function dist2(t){var dx=t[0].clientX-t[1].clientX,dy=t[0].clientY-t[1].clientY;return Math.sqrt(dx*dx+dy*dy)}
function onPinchStart(e){
  if(e.touches.length===2){pinchDist=dist2(e.touches);pinchZoom=zoomLevel;pinching=true;scrolling=false;
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null}}
}
function onPinchMove(e){
  if(!pinching||e.touches.length!==2)return;
  var d=dist2(e.touches);
  if(pinchDist>0){var s=d/pinchDist;zoomLevel=Math.max(0.5,Math.min(4,pinchZoom*s));if(xtermElem)xtermElem.style.zoom=zoomLevel}
  e.preventDefault();
}
function onPinchEnd(e){if(e.touches.length<2){pinching=false;pinchDist=0}}

var lastTap=0;
function onDoubleTap(e){
  var now=Date.now();
  if(now-lastTap<300&&e.changedTouches.length===1){zoomLevel=1;if(xtermElem)xtermElem.style.zoom='1'}
  lastTap=now;
}

// ====== INICIALIZAÇÃO ======
function init(){
  if(ready)return;
  xtermElem=document.querySelector('.xterm');
  viewport=document.querySelector('.xterm-viewport');
  termContainer=document.querySelector('#terminal')||xtermElem||document.body;
  if(!xtermElem){setTimeout(init,300);return}
  var target=termContainer;
  target.addEventListener('touchstart',function(e){if(e.touches.length===2){onPinchStart(e);return}onTouchStart(e)},{passive:true});
  target.addEventListener('touchmove',function(e){if(pinching){onPinchMove(e);return}onTouchMove(e)},{passive:false});
  target.addEventListener('touchend',function(e){onPinchEnd(e);onDoubleTap(e);if(!pinching)onTouchEnd(e)},{passive:true});
  document.addEventListener('touchstart',function(e){if(!scrolling&&!pinching&&!isSelecting){if(e.touches.length===1)onTouchStart(e);else if(e.touches.length===2)onPinchStart(e)}},{passive:true});
  document.addEventListener('touchmove',function(e){if(pinching)onPinchMove(e);else if(isSelecting||scrolling)onTouchMove(e)},{passive:false});
  document.addEventListener('touchend',function(e){if(pinching)onPinchEnd(e);if(isSelecting||scrolling)onTouchEnd(e);onDoubleTap(e)},{passive:true});
  ready=true;findTerminal();
  console.log('[PesquisAI] Touch scroll (WebSocket SGR) + seleção + zoom ativados');
}

if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init)}
else{init()}

var obs=new MutationObserver(function(){if(!ready)init();else{viewport=viewport||document.querySelector('.xterm-viewport');if(!term)findTerminal()}});
obs.observe(document.documentElement,{childList:true,subtree:true});
setTimeout(function(){obs.disconnect()},30000);
setInterval(function(){if(!term)findTerminal();if(!viewport)viewport=document.querySelector('.xterm-viewport')},2000);
})();
</script>"""


def _prepare_ttyd_touch_index(env: dict) -> str | None:
    """Prepara um index.html custom com touch handlers para o ttyd.

    1. Inicia ttyd temporariamente com comando dummy
    2. Busca o HTML padrão em http://localhost:{TERMINAL_PORT}/
    3. Injeta o script de touch handlers antes de </body>
    4. Salva em /tmp/ttyd_touch.html
    5. Mata o ttyd temporário
    6. Retorna o caminho do arquivo (ou None se falhar)

    Usa cache: só busca o HTML uma vez por sessão.
    """
    global _TTYD_TOUCH_INDEX_PATH
    if _TTYD_TOUCH_INDEX_PATH and os.path.exists(_TTYD_TOUCH_INDEX_PATH):
        return _TTYD_TOUCH_INDEX_PATH

    import socket as _socket
    import urllib.request as _urllib

    # v0.7.5+ (sem bump): o ttyd temporário usa uma PORTA LIVRE. Antes ele
    # subia na TERMINAL_PORT — se o ttyd real já estivesse no ar, o dummy
    # não conseguia o bind e, no fim, um `pkill -9 -x ttyd` matava o ttyd
    # REAL (era uma das causas do "Reconnect": qualquer chamada que
    # regenerasse o index derrubava o terminal do usuário).
    _s = _socket.socket()
    try:
        _s.bind(("127.0.0.1", 0))
        _tmp_port = _s.getsockname()[1]
    finally:
        _s.close()

    # 1. Iniciar ttyd temporário com comando dummy
    #    v0.6.5: nova sessão de processos + log em arquivo
    print("📱 Preparando HTML do ttyd com touch handlers...")
    tmp_proc = subprocess.Popen(
        ["ttyd", "-p", str(_tmp_port), "echo", "pesquisai_touch_tmp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
        start_new_session=True,
    )
    time.sleep(2)

    # 2. Buscar HTML padrão do ttyd
    html_content: str | None = None
    try:
        url = f"http://localhost:{_tmp_port}/"
        req = _urllib.Request(url, headers={"User-Agent": "PesquisAI-Touch-Setup"})
        html_content = _urllib.urlopen(req, timeout=5).read().decode("utf-8")
    except Exception as e:
        logger.warning("Falha ao buscar HTML do ttyd para touch handlers: %s", e)

    # 3. Matar ttyd temporário
    #    v0.6.5: terminate/wait primeiro; fallback pkill -x (COMM exato) —
    #    NUNCA pkill -f ttyd, que mataria também o ttyd real de outra thread.
    try:
        tmp_proc.terminate()
        tmp_proc.wait(timeout=3)
    except Exception:
        pass
    try:
        import signal as _signal
        try:
            os.killpg(os.getpgid(tmp_proc.pid), _signal.SIGKILL)
        except Exception:
            pass
    except Exception:
        pass
    # v0.7.5+ (sem bump): NUNCA `pkill -9 -x ttyd` aqui. O temporário já foi
    # encerrado acima (terminate + killpg); um pkill global mataria o ttyd
    # real e derrubaria a sessão do usuário (sintoma "Reconnect").
    time.sleep(0.5)

    if not html_content:
        print("⚠️  Não foi possível obter HTML do ttyd — touch handlers não injetados.")
        return None

    # 4. Injetar script de touch handlers no <head> (ANTES do bundle do ttyd)
    # CRÍTICO: o patch do WebSocket constructor deve rodar antes do ttyd criar
    # seu socket. O bundle do ttyd fica no <body>, então injetar no <head>
    # garante que o constructor patch capture o socket na criação.
    touch_script = _get_touch_handler_script()
    if "<head>" in html_content:
        html_content = html_content.replace("<head>", "<head>" + touch_script, 1)
    elif "<head " in html_content:
        html_content = html_content.replace("<head ", "<head " + touch_script, 1)
    elif "</head>" in html_content:
        html_content = html_content.replace("</head>", touch_script + "</head>", 1)
    elif "</body>" in html_content:
        html_content = html_content.replace("</body>", touch_script + "</body>", 1)
    else:
        html_content = touch_script + html_content

    # 5. Salvar HTML custom — v0.6.9-5: caminho do usuário para evitar Permission denied
    # quando /tmp/ttyd_touch.html pertence a root (instalação via sudo)
    import tempfile as _tf
    candidates: list[str] = []
    try:
        _user_cache = os.path.join(os.path.expanduser("~"), ".cache", "ufvai")
        os.makedirs(_user_cache, exist_ok=True)
        candidates.append(os.path.join(_user_cache, f"ttyd_touch_{os.getuid()}.html"))
    except Exception:
        pass
    try:
        _pesquisai_tmp = os.path.join(os.path.expanduser("~"), "PesquisAI", "tmp")
        os.makedirs(_pesquisai_tmp, exist_ok=True)
        candidates.append(os.path.join(_pesquisai_tmp, "ttyd_touch.html"))
    except Exception:
        pass
    candidates.append(os.path.join(_tf.gettempdir(), f"ttyd_touch_{os.getuid()}.html"))
    candidates.append("/tmp/ttyd_touch.html")
    index_path = None
    for _cand in candidates:
        try:
            if os.path.exists(_cand) and not os.access(_cand, os.W_OK):
                try:
                    os.unlink(_cand)
                except Exception:
                    continue
            _dir = os.path.dirname(_cand)
            if _dir:
                os.makedirs(_dir, exist_ok=True)
            with open(_cand, "w", encoding="utf-8") as f:
                f.write(html_content)
            index_path = _cand
            break
        except Exception as e:
            logger.debug("Tentativa de salvar touch em %s falhou: %s", _cand, e)
            continue
    if index_path:
        _TTYD_TOUCH_INDEX_PATH = index_path
        print(f"✅ Touch handlers injetados no HTML do ttyd: {index_path}")
        return index_path
    logger.warning("Falha ao salvar HTML custom do ttyd em todos os candidatos")
    return None


def _build_ttyd_args(base_args: list, env: dict) -> list:
    """Constrói os argumentos do ttyd, adicionando --index se touch handlers estiverem prontos.

    Args:
        base_args: Argumentos base do ttyd (ex: ["ttyd", "-p", "8000", "--writable"])
        env: Dicionário de environment.

    Returns:
        Lista completa de argumentos incluindo --index se disponível.
    """
    touch_index = _prepare_ttyd_touch_index(env)
    if touch_index:
        # Inserir --index logo após "ttyd" (posição 1)
        # Flags podem aparecer em qualquer ordem antes do comando.
        result = [base_args[0], "--index", touch_index] + base_args[1:]
        return result
    return base_args


_LANG_MAP = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR", "zh": "zh_CN"}
# v0.6.24 (ajuste 18/10/2026): idioma da UI web → idioma da TUI do OpenCode.
# A troca no seletor da interface grava ``~/.config/opencode/ufvai-language.json``
# (fonte de verdade do plugin ``ufvai-pt``) ANTES de reiniciar o ttyd — assim,
# quando a interface recarrega, os comandos/menus do terminal já abrem no mesmo
# idioma. NÃO se faz patch no binário do motor (ver `tui_prompt.py`); os textos
# internos do OpenCode permanecem no idioma original.
_UI_TO_TUI_LOCALE = {
    "pt_BR": "pt-BR",
    "en_US": "en",
    "es_ES": "es",
    "fr_FR": "fr",
    # v0.6.25: sem esta entrada oIDIOMA CHINÊS era aceito pela UI mas
    # _sync_terminal_locale() devolvia False (silencioso) e o TERMINAL
    # continuava no idioma anterior. O tui_pt.PT_LOCALES já aceita "zh".
    "zh_CN": "zh",
}


def _detect_system_lang() -> str:
    """v0.6.1: detecta o idioma do sistema operacional/navegador.

    Ordem de consulta: $LANGUAGE → $LC_ALL → $LC_MESSAGES → $LANG
    → locale.getdefaultlocale(). Mapeia o prefixo para um dos idiomas
    suportados (pt/en/es/fr/zh); fallback pt_BR.
    """
    import locale as _locale
    for src in (
        os.environ.get("LANGUAGE"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ):
        if not src:
            continue
        # LANGUAGE pode ser uma lista "pt_BR:pt:en" — pegar o primeiro útil
        for part in src.split(":"):
            code = part.strip().split(".")[0].replace("-", "_").lower()
            if not code or code in ("c", "posix"):
                continue
            short = code.split("_")[0]
            if short in _LANG_MAP:
                return _LANG_MAP[short]
    try:
        loc = _locale.getdefaultlocale()[0]
        if loc:
            short = str(loc).split("_")[0].lower()
            if short in _LANG_MAP:
                return _LANG_MAP[short]
    except Exception:
        pass
    return "pt_BR"


def _prefs_path() -> str:
    """Arquivo de preferências que SOBREVIVE a reinícios do Colab.

    ``~/.config`` some quando o ambiente é reiniciado; o Drive não. Era por
    isso que, a cada execução nova, o backend voltava a detectar o idioma
    pelo locale do servidor (``en_US`` no Colab) e a saudação inicial saía
    em inglês, mesmo com o navegador do usuário em português.
    """
    drive = "/content/drive/My Drive/PesquisAI"
    base = drive if os.path.isdir(drive) else os.path.join(os.path.expanduser("~"), "PesquisAI")
    return os.path.join(base, "config", "prefs.json")


def _read_prefs() -> dict:
    """Lê ``config/prefs.json`` (best-effort; devolve ``{}`` se não existir)."""
    try:
        import json as _json
        with open(_prefs_path(), "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_prefs(**patch) -> None:
    """Funde ``patch`` no prefs.json de forma atômica (tmp + replace)."""
    try:
        import json as _json
        path = _prefs_path()
        data = _read_prefs()
        data.update(patch)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            _json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001 — preferência nunca derruba o boot
        try:
            logger.debug("prefs: não foi possível gravar (%s)", exc)
        except Exception:
            pass


def _persist_lang(lang: str, source: str = "user") -> None:
    """Persiste o idioma no cookie local e, se for escolha do usuário, no Drive.

    ``source``:
      - ``"user"``    — o usuário clicou no seletor; vale para sempre;
      - ``"browser"`` — adoção silenciosa do idioma do navegador; vale para as
        próximas execuções (é a melhor pista de idioma que existe no boot);
      - ``"auto"``    — detecção do sistema; grava só no arquivo local, jamais
        no Drive (senão o ``en_US`` do Colab viraria "escolha do usuário").
    """
    try:
        os.makedirs(os.path.dirname(_LANG_COOKIE_FILE), exist_ok=True)
        with open(_LANG_COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(lang)
    except Exception:
        pass
    if source in ("user", "browser"):
        _write_prefs(lang=lang, lang_source=source)


def _ensure_lang_initialized() -> str:
    """v0.6.15: garante que _current_lang esteja resolvido ANTES do 1º ttyd.

    Ordem: PESQUISAI_LANG (explícito) > prefs do Drive (escolha do usuário /
    idioma do navegador, sobrevive ao reinício do Colab) > cookie local >
    detecção do sistema. Persiste o resultado para tornar a próxima execução
    determinística. Idempotente — pode ser chamada em launch() e em
    start_wrapper_server() sem efeitos colaterais.
    """
    global _current_lang
    # Se já está válido, respeita (evita re-detectar após escolha do usuário)
    if _current_lang and _current_lang in _LANG_MAP.values():
        return _current_lang
    try:
        if os.environ.get("PESQUISAI_LANG"):
            env_lang = str(os.environ["PESQUISAI_LANG"]).strip()
            short = env_lang.split("_")[0].lower()
            _current_lang = _LANG_MAP.get(short, env_lang if env_lang in _LANG_MAP.values() else "pt_BR")
            _persist_lang(_current_lang)
            return _current_lang
        # v0.7.5+: idioma escolhido na interface (ou adotado do navegador)
        # gravado no Drive — o /root/.config não sobrevive ao reinício.
        pref_lang = str((_read_prefs() or {}).get("lang") or "").strip()
        if pref_lang:
            short = pref_lang.split("_")[0].lower()
            pref_full = _LANG_MAP.get(short, pref_lang if pref_lang in _LANG_MAP.values() else "")
            if pref_full:
                _current_lang = pref_full
                _persist_lang(_current_lang)
                print(f"🌐 Idioma das preferências (Drive): {_current_lang}")
                return _current_lang
        if os.path.exists(_LANG_COOKIE_FILE):
            with open(_LANG_COOKIE_FILE, "r", encoding="utf-8") as f:
                content = (f.read() or "").strip()
            if content:
                short = content.split("_")[0].lower()
                _current_lang = _LANG_MAP.get(short, content if content in _LANG_MAP.values() else "pt_BR")
                # normaliza e garante persistência
                try:
                    _short2 = (_current_lang or "pt").split("_")[0].lower()
                    _current_lang = _LANG_MAP.get(_short2, _current_lang if _current_lang in _LANG_MAP.values() else "pt_BR")
                except Exception:
                    _current_lang = "pt_BR"
                _persist_lang(_current_lang, source="browser")
                return _current_lang
        # Nenhuma preferência salva → detecta do sistema (não grava no Drive)
        _current_lang = _detect_system_lang()
        print(f"🌐 Idioma detectado do sistema: {_current_lang}")
        _persist_lang(_current_lang, source="auto")
        # normaliza
        try:
            _short = (_current_lang or "pt").split("_")[0].lower()
            _current_lang = _LANG_MAP.get(_short, _current_lang if _current_lang in _LANG_MAP.values() else "pt_BR")
        except Exception:
            _current_lang = "pt_BR"
        return _current_lang
    except Exception:
        _current_lang = "pt_BR"
        return _current_lang


def _wait_port_open(port: int, timeout_s: float = 10.0) -> bool:
    """v0.6.1: aguarda uma porta TCP local aceitar conexões.

    Usado após reiniciar o ttyd para garantir que a resposta do
    POST /api/lang só chega ao frontend quando o terminal já está
    pronto para aceitar conexões (evita iframe morto após reload).
    """
    import socket
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _consent_backup_file():
    """v0.6.9: arquivo PERSISTENTE de consentimento+contato do usuário.

    Colab: <Drive>/PesquisAI/backups/ufvai_consentimento.json — sobrevive à
    sessão (diferente de ~/.config, efêmero) e permite pré-preencher a tela de
    Termos nas reaberturas. Offline: ~/PesquisAI/backups/ufvai_consentimento.json.
    Retorna o caminho ou None em caso de falha.
    """
    try:
        base = ("/content/drive/My Drive/PesquisAI"
                if os.path.isdir("/content/drive/My Drive")
                else os.path.expanduser("~/PesquisAI"))
        bdir = os.path.join(base, "backups")
        os.makedirs(bdir, exist_ok=True)
        return os.path.join(bdir, "ufvai_consentimento.json")
    except Exception:
        return None


def _read_consent_profile() -> dict:
    """v0.6.9: lê o perfil persistente (backup do Drive → fallback local).
    v0.6.10: inclui ``name``/``nome`` e compatibilidade legada.
    """
    prof: dict = {}
    bpath = _consent_backup_file()
    if bpath and os.path.isfile(bpath):
        try:
            with open(bpath, encoding="utf-8") as fh:
                prof = json.load(fh) or {}
        except Exception:
            prof = {}
    if not prof.get("email"):
        try:
            with open(os.path.expanduser("~/.config/ufvai_profile.json"), encoding="utf-8") as fh:
                local = json.load(fh) or {}
            prof.setdefault("email", local.get("email", ""))
            prof.setdefault("email_sha256", local.get("email_sha256", ""))
            prof.setdefault("name", local.get("name", "") or local.get("nome", ""))
        except Exception:
            pass
    # normaliza nome legado
    if not prof.get("name") and prof.get("nome"):
        prof["name"] = prof.get("nome", "")
    return prof


_PRIVATE_IP_PREFIXES: tuple[str, ...] = (
    "0.", "10.", "100.64.", "127.", "169.254.",
    "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
    "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "192.0.0.", "192.0.2.", "192.168.", "198.18.", "198.19.",
    "198.51.100.", "203.0.113.",
)


def _is_private_ip(ip: str) -> bool:
    """True se o IP for loopback/privado/reservado (IPv4 ou IPv6).

    v0.6.13: usado para percorrer a cadeia X-Forwarded-For saltando os
    proxies internos (127.0.0.1, 10.x, 172.16-31.x, 192.168.x) e devolver
    o PRIMEIRO IP público = o endpoint real do navegador do usuário.
    """
    ip = (ip or "").strip().lower().rstrip(".")
    if not ip:
        return True
    if ":" in ip:  # IPv6
        return ip in ("::", "::1") or ip.startswith(("fe80:", "fc", "fd"))
    return ip.startswith(_PRIVATE_IP_PREFIXES)


def _normalize_ip_token(token: str) -> str:
    """Normaliza um item de cabeçalho IP para só o endereço.

    Trata: '1.2.3.4', '1.2.3.4:8080' (IPv4+porta), '[2804:431::1]',
    '[2804:431::1]:4567' (IPv6+porta) e '2804:431::1' (IPv6 puro).
    """
    t = (token or "").strip().strip("\"'\t ")
    if not t:
        return ""
    if t.startswith("["):  # IPv6 entre colchetes, com/sem porta
        end = t.find("]")
        return t[1:end] if end != -1 else t.strip("[]")
    if t.count(":") == 1:  # IPv4:porta (e não IPv6 puro, que tem 2+ ':')
        t = t.split(":")[0]
    return t.strip()


def _get_client_ip(handler, client_ip: str | None = None) -> str:
    """v0.6.14: extrai o IP REAL do usuário que está acessando.

    v0.6.14: prioriza IP enviado pelo cliente (via JS ipify) quando for
    público — corrige Colab onde o proxy NÃO injeta X-Forwarded-For e o
    servidor via só 127.0.0.1/localhost. Se o IP do cliente for privado/
    ausente, recorre à cadeia de headers.

    Cadeia de headers (fallback):
      1) X-Forwarded-For — "cliente, proxy1, proxy2" (direita→esquerda, pula privados)
      2) X-Real-IP / CF-Connecting-IP / True-Client-IP / X-Forwarded /
         X-Cluster-Client-IP / Forwarded (RFC 7239)
      3) client_address (no Colab costuma ser 127.0.0.1)

    Sempre devolve algo (nunca vazio).
    """
    # v0.6.14: IP enviado pelo frontend (ipify) tem prioridade quando público
    try:
        if client_ip:
            cip = _normalize_ip_token(str(client_ip))
            if cip and not _is_private_ip(cip):
                return cip
    except Exception:
        pass
    try:
        candidates: list[str] = []
        # 1) X-Forwarded-For: "1.2.3.4, 10.0.0.1, 127.0.0.1"
        for part in (handler.headers.get("X-Forwarded-For", "") or "").split(","):
            p = _normalize_ip_token(part)
            if p:
                candidates.append(p)
        # 2) headers de proxy/CDN de valor único
        for hname in ("X-Real-IP", "CF-Connecting-IP", "True-Client-IP",
                      "X-Forwarded", "X-Cluster-Client-IP"):
            v = handler.headers.get(hname, "") or ""
            if v:
                p = _normalize_ip_token(v.split(",")[0])
                if p:
                    candidates.append(p)
        # 3) Forwarded (RFC 7239): "for=1.2.3.4;proto=https"
        for seg in (handler.headers.get("Forwarded", "") or "").split(";"):
            seg = seg.strip()
            if seg.lower().startswith("for="):
                p = _normalize_ip_token(seg.split("=", 1)[1])
                if p:
                    candidates.append(p)
        # da direita para a esquerda (mais confiável primeiro), pulando privados
        for ip in reversed(candidates):
            if not _is_private_ip(ip):
                return ip
        if candidates:
            # tudo privado → devolve o primeiro da cadeia + log de diagnóstico
            try:
                # loga headers para debug do caso localhost (só quando ainda é privado)
                _hdr_debug = {k: handler.headers.get(k, "") for k in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP", "Forwarded")}
                logger.warning("IP debug: candidates=%s headers=%s client_address=%s", candidates, _hdr_debug, getattr(handler, "client_address", "?"))
            except Exception:
                pass
            return candidates[0]
        return handler.client_address[0] if hasattr(handler, "client_address") else ""
    except Exception:
        return ""


def _ttyd_log_file():
    """v0.6.5: arquivo de log do ttyd (antes: DEVNULL — falhas invisíveis).
    v0.6.9: NO COLAB o log NÃO vai mais para o Drive do usuário (poluição);
    vai para /tmp/ufvai-logs/ttyd.log (efêmero). Offline: ~/PesquisAI/logs/ttyd.log
    (máquina local, não é nuvem). Em caso de falha ao criar, retorna DEVNULL.
    """
    try:
        if os.path.isdir("/content/drive/My Drive"):
            log_dir = "/tmp/ufvai-logs"          # v0.6.9: fora do Drive do usuário
        else:
            log_dir = os.path.join(os.path.expanduser("~/PesquisAI"), "logs")
        os.makedirs(log_dir, exist_ok=True)
        return open(os.path.join(log_dir, "ttyd.log"), "ab")
    except Exception:
        return subprocess.DEVNULL


def _ufvai_log_dir() -> str:
    """Diretório de logs do runtime (mesmo critério do log do ttyd)."""
    if os.path.isdir("/content/drive/My Drive"):
        return "/tmp/ufvai-logs"          # Colab: fora do Drive do usuário
    return os.path.join(os.path.expanduser("~/PesquisAI"), "logs")


def _ttyd_event_log(evt: str, extra: str = "") -> None:
    """Registra QUEM reiniciou/parou o ttyd (diagnóstico do "Reconnect").

    v0.7.5+ (sem bump): o sintoma "o terminal pede Reconnect depois de um
    tempo" só se explica sabendo se o ttyd foi reiniciado — e por quem.
    Cada evento leva a pilha de chamadas resumida para wrapper.log.
    """
    try:
        os.makedirs(_ufvai_log_dir(), exist_ok=True)
        stack = "".join(traceback.format_stack(limit=7)[:-1]).strip()
        with open(os.path.join(_ufvai_log_dir(), "wrapper.log"), "a",
                  encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {evt} {extra}\n")
            if stack:
                fh.write(stack + "\n")
    except Exception:  # noqa: BLE001 — diagnóstico nunca derruba o runtime
        pass


def _spawn_ttyd(ttyd_args: list, env: dict | None, cwd: str | None = None) -> "subprocess.Popen":
    """v0.6.5: Popen rastreado em NOVA SESSÃO de processos.

    start_new_session=True faz o ttyd ser líder do próprio grupo — assim
    _stop_terminal() consegue matar ttyd + bash + opencode (a árvore toda)
    com um único killpg, sem pkill -f global (que matava qualquer processo
    com 'opencode' na cmdline, inclusive o agente hospedeiro).

    v0.7.7 (correção 27/10/2026 — SEM bump): o ttyd nasce com cwd na pasta
    PesquisAI. Antes, os caminhos que não faziam ``cd`` no bash_cmd
    (/api/run_terminal e /api/session-import) herdavam o cwd do processo
    servidor — ``/root`` no Colab — e a sessão do agente abria fora do Drive.
    """
    global _TTYD_PROC
    logf = _ttyd_log_file()
    proc = subprocess.Popen(
        ttyd_args,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=cwd or _workspace_dir(),
        start_new_session=True,
    )
    _TTYD_PROC = proc
    _ttyd_event_log("spawn", f"pid={proc.pid} sessao={_current_ttyd_session}")
    return proc


def _stop_terminal(wait_s: float = 0.8) -> None:
    """v0.6.5: encerra a ÁRVORE do terminal de forma cirúrgica.

    1. killpg no grupo rastreado (_TTYD_PROC) — mata ttyd + bash + opencode;
    2. Fallback determinístico: pkill -9 -x ttyd casa apenas o COMM exato
       'ttyd' (NUNCA casa python/host/bash com 'opencode' na cmdline).
    """
    global _TTYD_PROC
    _ttyd_event_log("stop", f"pid_atual={getattr(_TTYD_PROC, 'pid', None)}")
    import signal as _signal

    _tmux_kill_session()  # reinício explícito começa de sessão limpa
    proc, _TTYD_PROC = _TTYD_PROC, None
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), _signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=3)
        except Exception:
            pass
    # Fallback: mata qualquer OUTRO ttyd remanescente pelo nome exato do binário
    try:
        subprocess.run(["pkill", "-9", "-x", "ttyd"], capture_output=True, timeout=3)
    except Exception:
        pass
    # Órfãos típicos de versões antigas (bash -i -c … opencode …): mata só
    # bash INTERATIVO cujo -c contém opencode (padrão ancorado, sem falso
    # positivo com o agente hospedeiro, que não roda via 'bash -i -c').
    try:
        subprocess.run(["pkill", "-9", "-f", r"^-i -c .*opencode"],
                       capture_output=True, timeout=3)
    except Exception:
        pass
    time.sleep(wait_s)  # dá tempo do kernel liberar o socket da porta


def _ensure_terminal_ready(spawn_fn, timeout_s: float = 20.0,
                           retries: int = 1) -> bool:
    """v0.6.5: spawn + ESPERA a porta do terminal aceitar conexões.

    Retorna True somente se a TERMINAL_PORT estiver de fato atendendo.
    Se não abrir, reinicia (retry) antes de desistir — cobre corridas de
    rebind/TIME_WAIT que deixavam a porta morta (ERR_CONNECTION_REFUSED).
    """
    for attempt in range(1, retries + 2):
        spawn_fn()
        if _wait_port_open(TERMINAL_PORT, timeout_s=min(10.0, timeout_s)):
            return True
        print(f"⚠️  Terminal não abriu a porta {TERMINAL_PORT} "
              f"(tentativa {attempt}/{retries + 1}) — reiniciando…")
        if attempt <= retries:
            _stop_terminal(0.6)
    return False


# ── v0.6.22: sessão que sobrevive à queda do WebSocket ─────────────
# O ttyd cria UM processo por conexão WebSocket e envia SIGHUP a esse processo
# quando a conexão cai. Sem tmux, qualquer queda (ociosidade do proxy, aba em
# segundo plano) matava o opencode, e a reconexão recomeçava a sessão do zero.
# Com tmux, a queda derruba só o cliente: a sessão segue viva e a reconexão
# reanexa a ela (o comando e o --prompt não rodam de novo).
_TMUX_SOCKET = "ufvai"          # servidor tmux próprio: não mexe no tmux do usuário
_TMUX_SESSION = "ufvai"
_TMUX_CONF_PATH = "/tmp/ufvai-tmux.conf"
_TMUX_CONF_TEXT = (
    "set -g status off\n"                 # sem barra de status do tmux
    "set -g escape-time 10\n"             # ESC responde rápido no TUI do opencode
    "set -g default-terminal xterm-256color\n"
    "set -g mouse on\n"                   # roda do mouse vira copy-mode (rolagem)
)


def _tmux_conf_path() -> "str | None":
    """Grava o tmux.conf do UFVAI e devolve o caminho (None se não der)."""
    try:
        with open(_TMUX_CONF_PATH, "w", encoding="utf-8") as fh:
            fh.write(_TMUX_CONF_TEXT)
        return _TMUX_CONF_PATH
    except OSError:
        return None


def _ttyd_shell_argv(bash_cmd: str) -> list:
    """Argumentos do comando que o ttyd executa (depois das flags do ttyd).

    Com tmux, o ttyd só anexa à sessão do UFVAI. Sem tmux, mantém o
    comportamento anterior (bash -i -c), sem sessão persistente.
    """
    shell = ["bash", "-i", "-c", bash_cmd]
    conf = _tmux_conf_path()
    if conf is None or not shutil.which("tmux"):
        return shell
    return ["tmux", "-L", _TMUX_SOCKET, "-f", conf,
            "new", "-A", "-s", _TMUX_SESSION, *shell]


def _tmux_kill_session() -> None:
    """Encerra a sessão tmux do UFVAI. Usado só em reinício explícito e no boot,
    para que trocar idioma/chave/sessão comece de um estado limpo."""
    if not shutil.which("tmux"):
        return
    try:
        subprocess.run(["tmux", "-L", _TMUX_SOCKET, "kill-session", "-t", _TMUX_SESSION],
                       capture_output=True, timeout=3)
    except Exception:  # noqa: BLE001 — sessão inexistente é o caso normal
        pass


def _revive_ttyd(force: bool = False) -> bool:
    """Religa o ttyd ANEXANDO à sessão tmux existente (a conversa continua).

    Quando o processo morre (SIGKILL de uma execução anterior, troca de
    idioma interrompida), a porta do terminal fica fechada e a interface
    mostra "Iniciando terminal…" para sempre. `_ttyd_shell_argv` usa
    ``tmux new -A``: se a sessão já existe, ele apenas ANEXA — por isso é
    seguro religar sem derrubar o `opencode` que está rodando.
    """
    global _LAST_TTYD_REVIVE
    now = time.time()
    with _TTYD_REVIVE_LOCK:
        if not force and (now - _LAST_TTYD_REVIVE) < _TTYD_REVIVE_MIN_S:
            return False
        _LAST_TTYD_REVIVE = now
    if not force and _TTYD_PROC is not None and _TTYD_PROC.poll() is None:
        return False  # já existe um ttyd vivo: não duplica
    _ttyd_event_log("revive", f"force={force} pid_atual={getattr(_TTYD_PROC, 'pid', None)}")
    try:
        opencode_bin, env = resolve_opencode()
        project_dir = _workspace_dir()
        sid = _current_ttyd_session
        _yolo = "" if os.environ.get("PESQUISAI_YOLO", "1").strip().lower() in ("0", "false", "off", "no") else " --auto"
        if sid:
            bash_cmd = f'cd "{project_dir}" && {opencode_bin} --session "{sid}"{_yolo} ; exec bash'
        else:
            bash_cmd = f'cd "{project_dir}" && bash -i'
        base = ["ttyd", "-p", str(TERMINAL_PORT), "--writable",
                *_ttyd_shell_argv(bash_cmd)]
        _spawn_ttyd(_build_ttyd_args(base, env), env)
        ok = _wait_port_open(TERMINAL_PORT, timeout_s=8.0)
        if ok and sid:
            _remember_ttyd_session(sid)
        logger.info("ttyd religado (auto-cura): %s", ok)
        return ok
    except Exception as exc:  # noqa: BLE001 — auto-cura nunca derruba a UI
        logger.warning("auto-cura do ttyd falhou: %s", exc)
        return False


def _seed_greeting_async(session_id: str, lang: str, delay: float = 0.8) -> None:
    """Semeia a saudação padrão do idioma na sessão, em segundo plano.

    v0.7.5+ (sem bump): a saudação não é mais enviada "no escuro" com o
    idioma detectado pelo SERVIDOR (no Colab, ``en_US``) — era o que abria
    o terminal em inglês mesmo com o navegador em português. Quem decide o
    idioma é o CLIENTE:

      • se já existe preferência no Drive, o boot semeia direto no idioma
        certo (mensagem aparece rápido);
      • na primeira execução, a sessão fica pendente e a mensagem sai
        quando o frontend informa o idioma (POST /api/lang);
      • trocar o idioma reinjeta a mensagem no idioma novo.

    O processo é assíncrono: nenhum LLM disputa CPU/IO com o TUI na
    abertura (o boot fica mais leve).
    """
    sid = str(session_id or "").strip()
    if not sid:
        return
    try:
        from .__version__ import get_greeting as _get_greeting
    except Exception:  # noqa: BLE001
        def _get_greeting(_lang: str) -> str:
            return ""

    greeting = _get_greeting(lang)
    if not greeting:
        return

    def _run() -> None:
        try:
            opencode_bin, env = resolve_opencode()
            project_dir = _workspace_dir()
            # Usa o helper dedicado: ele escolhe o modelo gratuito do Zen
            # (`opencode/big-pickle`) quando existe. Sem isso, o `opencode run`
            # herda o modelo padrão do opencode.json — se ele estiver sem
            # quota, a saudação falhava em silêncio (DEVNULL).
            ok = seed_ufvai_greeting(
                sid, greeting, timeout_s=40.0,
                opencode_bin=opencode_bin, env=env, cwd=project_dir,
            )
            if ok:
                logger.info("Saudação semeada em %s (%s)", lang, sid)
            else:
                logger.debug("seed da saudação não concluiu (%s)", sid)
        except Exception as exc:  # noqa: BLE001
            logger.debug("seed da saudação falhou: %s", exc)

    threading.Timer(max(0.0, float(delay)), _run).start()


def _mark_greeting_pending(session_id: str, lang: str, fallback_s: float = 60.0) -> None:
    """Marca a sessão nova para receber a saudação quando o cliente falar.

    v0.7.7 (correção 27/10/2026 — SEM bump): o fallback NÃO usa mais o idioma
    detectado no servidor. No Colab o locale é ``en_US``; a interface leva
    alguns segundos para abrir e informar o idioma real, e o fallback de 8 s
    semeava "Hello! (Tip: ...)" antes do cliente falar — a interface aparecia
    em português com a saudação em inglês. Agora:
      • espera 60 s (tempo de sobra para o navegador se apresentar);
      • se ninguém falar, usa a preferência do Drive ou o padrão do produto
        (``pt_BR``) — nunca o locale do servidor.
    """
    sid = str(session_id or "").strip()
    if not sid:
        return
    with _GREETING_LOCK:
        _PENDING_GREETING[sid] = True

    def _fallback() -> None:
        with _GREETING_LOCK:
            still = _PENDING_GREETING.pop(sid, False)
        if still:
            pref = str((_read_prefs() or {}).get("lang") or "").strip()
            _seed_greeting_async(sid, pref or "pt_BR", delay=0.0)

    threading.Timer(max(1.0, float(fallback_s)), _fallback).start()


def _greeting_pending(session_id: str | None) -> bool:
    sid = str(session_id or "").strip()
    if not sid:
        return False
    with _GREETING_LOCK:
        return bool(_PENDING_GREETING.get(sid))


def _consume_greeting(session_id: str | None, lang: str) -> bool:
    """Se havia saudação pendente, semeia agora no idioma do cliente."""
    sid = str(session_id or "").strip()
    if not sid:
        return False
    with _GREETING_LOCK:
        pending = bool(_PENDING_GREETING.pop(sid, False))
    if pending:
        _seed_greeting_async(sid, lang, delay=0.2)
    return pending


def _build_ttyd_cmd(lang: str | None = None, session_id: str | None = None,
                    seed_greeting: bool = True):
    """v0.6.5: constrói (args, env) do ttyd com saudação no idioma pedido.

    Extraído de start_ttyd para permitir retry determinístico em
    restart_ttyd_with_lang/_ensure_terminal_ready.

    v0.7.5 (correção 23/10/2026 — SEM bump): ``session_id`` permite REABRIR a
    conversa atual num reinício (idioma/chave/keepalive) em vez de pré-criar
    uma segunda sessão. ``seed_greeting=False`` evita repetir a saudação numa
    sessão que já existe.
    """
    global _current_ttyd_session
    opencode_bin, env = resolve_opencode()

    # Resolve idioma (param > env > prefs do Drive > _current_lang > sistema).
    # v0.7.7 (correção 27/10/2026 — SEM bump): a preferência do Drive vem ANTES
    # de ``_current_lang``. Antes, um ``_current_lang`` herdado da detecção
    # automática (``en_US`` no servidor do Colab) vencia o idioma que o próprio
    # usuário já tinha escolhido — a saudação saía em inglês ("Hello! (Tip: ...)")
    # mesmo com a interface em português.
    _pref_lang = str((_read_prefs() or {}).get("lang") or "").strip()
    _env_lang = str(os.environ.get("PESQUISAI_LANG") or "").strip()
    if lang is None:
        lang = _env_lang or _pref_lang or _current_lang or _detect_system_lang()
    # Idioma CONFIRMADO = escolha explícita (env) ou preferência salva no Drive.
    # Sem confirmação, a saudação espera o cliente (/api/lang) — nunca o locale
    # do servidor.
    lang_confident = bool(_env_lang or _pref_lang)
    # Normaliza para o conjunto canônico
    short = (lang or "pt_BR").split("_")[0].lower()
    full_lang = _LANG_MAP.get(short, lang if lang in _LANG_MAP.values() else "pt_BR")

    # v0.7.5+ (sem bump): a TUI abre no MESMO idioma resolvido aqui (prefs do
    # Drive incluídas). Antes o arquivo de locale só era escrito ao TROCAR o
    # idioma — numa execução nova o terminal abria em inglês mesmo com a
    # interface em português.
    try:
        _sync_terminal_locale(full_lang)
    except Exception as exc:  # noqa: BLE001 — nunca impede o spawn
        logger.debug("sync do locale da TUI falhou: %s", exc)

    # Saudação só no idioma confirmado; sem confirmação usa o padrão do produto
    # (pt_BR) até o cliente informar o idioma — o /api/lang reescreve depois.
    greeting = get_greeting(full_lang if lang_confident else "pt_BR")
    # Escapar aspas para o bash -c "..."
    safe_prompt = greeting.replace('"', '\\"').replace("'", "\\'")
    # Auto-aprovação de permissões (flag do OpenCode V2 é --auto; antes --yolo).
    # Mantido ligado por padrão (decisão do usuário). Para desligar: PESQUISAI_YOLO=0
    _yolo = "" if os.environ.get("PESQUISAI_YOLO", "1").strip().lower() in ("0", "false", "off", "no") else " --auto"
    # v0.6.22b (ajuste 15/10/2026 — SEM bump): o TUI criava a sessão nova com o
    # agente `build` na primeira mensagem, mesmo com default_agent UFVAI válido
    # (defeito reproduzido: "switched agent from Build to UFVAI" após o clique).
    # Solução: pré-criar a sessão via API já com agent=UFVAI e abrir o TUI
    # nela (`--session`); best-effort — qualquer falha volta ao comportamento
    # anterior (default_agent + build/plan desabilitados continuam ativos).
    # O cwd bate com o do TUI que será spawnado (projeção de projeto do serviço).
    # Seed the initial greeting ALREADY in the UFVAI-pinned session, via the
    # headless `opencode run`, instead of passing `--prompt` to the
    # interactive TUI (which on V2 restarts/leaks into a `build` session and
    # leaves the saudação unanswered). Best-effort: any failure (key/model/quota)
    # leaves the pinned session available; later typed messages still target
    # the UFVAI (post-baseline session agent persiste).
    project_dir = _workspace_dir()

    session_id = str(session_id or "").strip() or None
    created = False
    if not session_id:
        try:
            session_id, created = preflight_ufvai_session_info(cwd=project_dir)
        except Exception as exc:  # noqa: BLE001
            logger.debug("preflight_ufvai_session falhou inesperadamente: %s", exc)
            session_id, created = None, False
    if session_id:
        # v0.7.5+ (sem bump): a saudação NÃO é mais enviada cegamente no
        # spawn com o idioma do SERVIDOR (no Colab, en_US). Duas situações:
        #   • já existe preferência de idioma no Drive (usuário conhecido) →
        #     semeia já, no idioma certo, para a mensagem aparecer rápido;
        #   • primeira execução → fica pendente e é semeada quando o cliente
        #     informa o idioma (POST /api/lang). Fallback de 8 s para quem
        #     abre o ttyd direto.
        # Em ambos os casos o boot fica mais leve: nenhum processo de LLM
        # disputa CPU/IO com o TUI na abertura.
        if created and seed_greeting:
            if lang_confident:
                _seed_greeting_async(str(session_id), full_lang, delay=1.2)
            else:
                _mark_greeting_pending(str(session_id), full_lang)
        _current_ttyd_session = str(session_id)
        bash_cmd = f"cd \"{project_dir}\" && {opencode_bin} --session \"{session_id}\" {_yolo} ; exec bash"
    else:
        _current_ttyd_session = None
        bash_cmd = f"cd \"{project_dir}\" && {opencode_bin} --prompt \"{safe_prompt}\" {_yolo} ; exec bash"

    # v0.4.2.5: construir args com --index (touch handlers)
    # v0.6.2: --writable restaurado (regressão v0.6.0 deixava o terminal read-only)
    base_args = ["ttyd", "-p", str(TERMINAL_PORT), "--writable", *_ttyd_shell_argv(bash_cmd)]
    return _build_ttyd_args(base_args, env), env, full_lang


def start_ttyd(lang: str | None = None):
    """Inicia o ttyd com saudação no idioma solicitado.

    Args:
        lang: Código do idioma (pt_BR, en_US, es_ES, fr_FR). Se None, usa
              o _current_lang global ou o env PESQUISAI_LANG.

    v0.6.21 (14/10/2026): garantia `ensure_ufvai_agent` antes do spawn — o agente
    carregado é sempre o UFVAI, nunca `build` (nem outro).

    v0.4.2.2: ao invés de `--prompt 'oi'` genérico, usa saudação no idioma
              + instrução "(a partir de agora responda em X)".
    v0.4.2.5: injeta touch handlers (scroll + pinch-zoom) no HTML do ttyd
              via flag --index, habilitando rolagem e zoom em mobile.
    v0.6.5: spawn rastreado (_spawn_ttyd) + logs em arquivo; espera curta.
    """
    print(f"\n{next_joke('economia')}")
    _ensure_ufvai_agent_before_spawn("start_ttyd")
    ttyd_args, env, full_lang = _build_ttyd_cmd(
        lang, session_id=_current_ttyd_session)
    _spawn_ttyd(ttyd_args, env)
    print(f"🚀 Terminal iniciado (idioma: {full_lang}, touch: {'ON' if '--index' in ttyd_args else 'OFF'}).")
    # v0.7.5: espera ATIVA (curta) em vez de sleep fixo de 0,8 s. A UI já
    # abre em seguida e faz polling em /api/ttyd_ready; quando o ttyd sobe
    # rápido, o boot ganha quase 1 s.
    _wait_port_open(TERMINAL_PORT, timeout_s=0.8)


def _sync_terminal_locale(full_lang: str) -> bool:
    """Alinha a TUI do OpenCode ao idioma escolhido na interface web (v0.6.24).

    Grava a escolha em ``~/.config/opencode/ufvai-language.json`` — fonte de
    verdade do plugin ``ufvai-pt`` — para que, ao recarregar a página, os
    comandos e menus da TUI abram no mesmo idioma da interface.

    NÃO se faz patch no binário do motor (decisão de 18/10/2026): textos
    internos (frases de exemplo, "Ask anything…", rodapé) permanecem no idioma
    original do OpenCode, evitando quebra em atualização.

    Fail-open: qualquer falha não impede o reinício do terminal.
    """
    locale = _UI_TO_TUI_LOCALE.get(full_lang)
    if not locale:
        return False
    try:
        from .tui_pt import save_locale as _save_tui_locale
        _save_tui_locale(locale)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Não foi possível gravar o idioma da TUI (%s): %s", locale, exc)
        return False


def restart_ttyd_with_lang(lang: str) -> bool:
    """Reinicia o ttyd com saudação no novo idioma.

    Usado pelo endpoint /api/lang quando o usuário troca o idioma.
    Retorna True APENAS se o terminal novo está de fato aceitando conexões.

    v0.6.1: além de persistir e reiniciar, AGUARDA a porta do ttyd abrir
    antes de responder — o frontend só recarrega a página quando o
    terminal novo está pronto, garantindo que a saudação inicial apareça
    no idioma selecionado.
    v0.6.5: kill cirúrgico por árvore (_stop_terminal), retry automático e
    retorno honesto (antes respondia ok mesmo se a porta nunca abrisse —
    causa do ERR_CONNECTION_REFUSED no iframe após trocar idioma).
    """
    global _current_lang
    try:
        # Encerra a árvore atual (ttyd + bash + opencode) sem pkill -f global
        _stop_terminal()
        # Persiste o idioma
        _current_lang = lang
        _persist_lang(lang, source="user")
        # v0.6.24: alinha a TUI (comandos, frases e rodapé) ao idioma da UI
        # ANTES de subir o terminal novo.
        _sync_terminal_locale(lang)

        # Ajuste 14/10/2026 (v0.6.21): troca de idioma E de chave de API passam
        # por aqui (via _apply_opencode_env_change_async) — é EXATAMENTE o fluxo
        # em que o autor viu o motor iniciar com `build` ao adicionar chave.
        _ensure_ufvai_agent_before_spawn("restart_ttyd_with_lang")

        def _spawn():
            # v0.7.5: reabre a sessão que o terminal já estava exibindo.
            # Antes, o preflight criava OUTRA sessão a cada troca de idioma.
            ttyd_args, env, _full = _build_ttyd_cmd(
                lang, session_id=_current_ttyd_session)
            _spawn_ttyd(ttyd_args, env)

        ready = _ensure_terminal_ready(_spawn, timeout_s=18.0)
        if not ready:
            logger.error("ttyd não abriu a porta %s após troca de idioma "
                         "(ver logs/ttyd.log).", TERMINAL_PORT)
        return ready
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
#   3. 🌐 Seletor de idioma na topbar (5 idiomas: pt_BR, en_US, es_ES, fr_FR, zh_CN)
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



# ═══════════════════════════════════════════════════════════════
# v0.6.17 — Singleton de memória p/ abertura instantânea via menu
# ═══════════════════════════════════════════════════════════════
# Problema: cada request /api/obsidian/* criava um ObsidianMemory novo
# → Searcher novo → revalidação mtime/size de todas as notas no Drive
# FUSE + re-parse do cache BM25 + re-iteração da árvore (inclusive
# 2× com include=tree) = segundos de espera a cada abertura do menu.
# Solução: 1 instância em RAM compartilhada entre requests (índice
# BM25/LinkIndex construídos 1×), warm-up em background no boot e
# revalidação stale-while-revalidate após _MEM_TTL s.
_MEM_SINGLETON = None
_MEM_LOCK = threading.Lock()
_MEM_BUILT_TS = 0.0
_MEM_REBUILDING = False
_MEM_TTL = 30.0  # s — janela antes de disparar revalidação em background


def _get_memory(*, refresh: bool = False):
    """Retorna a instância única de ObsidianMemory (v0.6.17).

    - 1ª chamada: cria a instância e constrói o índice sincronamente.
    - Chamadas seguintes: devolve o objeto em RAM (instantâneo, µs).
    - Após _MEM_TTL s: devolve os dados correntes (stale) imediatamente
      e dispara rebuild em background (stale-while-revalidate) — o menu
      NUNCA bloqueia esperando o Drive.
    - refresh=True: invalida e reconstrói sincronamente (uso pós-escrita
      crítica; o save de nota usa rebuild em background em vez disto).
    """
    global _MEM_SINGLETON, _MEM_BUILT_TS
    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
    with _MEM_LOCK:
        if _MEM_SINGLETON is None:
            _MEM_SINGLETON = ObsidianMemory.from_env()
        mem = _MEM_SINGLETON
    if mem.status != ObsidianMemoryStatus.READY:
        return mem
    now = time.time()
    if refresh or _MEM_BUILT_TS == 0.0:
        # Construção síncrona apenas na 1ª vez (ou refresh explícito).
        # Lock evita build duplo concorrente (warm-up thread + 1º request):
        # requests seguintes esperam a 1ª construção e depois são instantâneos.
        with _MEM_LOCK:
            if _MEM_BUILT_TS == 0.0 or refresh:
                try:
                    searcher = mem._searcher
                    if searcher is not None:
                        if refresh:
                            searcher.invalidate()
                        searcher._ensure_built()  # type: ignore[attr-defined]
                    _MEM_BUILT_TS = time.time()
                except Exception:  # noqa: BLE001
                    pass
    elif now - _MEM_BUILT_TS > _MEM_TTL:
        _kick_memory_rebuild()
    return mem


def _kick_memory_rebuild() -> None:
    """Dispara rebuild do índice BM25 em background (1 por vez)."""
    global _MEM_REBUILDING, _MEM_BUILT_TS
    with _MEM_LOCK:
        if _MEM_REBUILDING:
            return
        _MEM_REBUILDING = True

    def _worker() -> None:
        global _MEM_REBUILDING, _MEM_BUILT_TS
        try:
            mem = _MEM_SINGLETON
            if mem is not None and mem._searcher is not None:
                mem._searcher.invalidate()
                mem._searcher._ensure_built()  # type: ignore[attr-defined]
                _MEM_BUILT_TS = time.time()
        except Exception:  # noqa: BLE001
            pass
        finally:
            _MEM_REBUILDING = False

    threading.Thread(target=_worker, daemon=True, name="ufvai-memory-rebuild").start()


def _warm_memory_async() -> None:
    """v0.6.17: pré-aquece o índice da memória em background no boot.

    Quando o usuário abrir o menu da memória, o índice já está em RAM
    → abertura instantânea (sem esperar o Drive FUSE).
    """
    def _worker() -> None:
        try:
            _get_memory()
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_worker, daemon=True, name="ufvai-memory-warm").start()


def _iter_memory_notes(mem, *, subdir=None):
    """v0.6.17: itera notas em RAM (índice quente) em vez de reler o Drive.

    O Searcher mantém todas as notas carregadas (``_notes``); usar essa
    cópia evita re-ler ~250 arquivos via FUSE a cada renderização da
    árvore (era o gargalo restante mesmo com o singleton). Fallback:
    ``vault.iter_notes()`` (comportamento antigo) se o índice estiver frio.
    """
    searcher = getattr(mem, "_searcher", None)
    notes = getattr(searcher, "_notes", None) if searcher is not None else None
    if getattr(searcher, "_built", False) and notes:
        prefix = (subdir.rstrip("/") + "/") if subdir else ""
        for path in sorted(notes):
            if prefix and not path.startswith(prefix):
                continue
            yield notes[path]
        return
    vault = getattr(mem, "_vault", None)
    if vault is not None:
        yield from vault.iter_notes(subdir=subdir)


# ══════════════════════════════════════════════════════════════════
# OpenCode V2 (mudança não lançada) · credenciais e serviço em background
# ══════════════════════════════════════════════════════════════════
# O V2 guarda credenciais no SQLite (~/.local/share/opencode/opencode.db); o
# auth.json da V1 deixou de ser atualizado. O backup usa `opencode auth export`
# (JSON com segredos) e `opencode auth import`. O arquivo no Drive é CIFRADO
# (Fernet), como as demais chaves do UFVAI. Nunca copiamos o banco.
_DRIVE_PESQUISAI: str = "/content/drive/My Drive/PesquisAI"
_OC_AUTH_BACKUP_FILE: str = "opencode_auth.json"
_OC_AUTH_BACKUP_FORMAT: str = "opencode-auth-export-v2"


def _backup_dir() -> str:
    """Pasta de backups: Drive no Colab; ~/PesquisAI/backups fora dele."""
    base = _DRIVE_PESQUISAI if os.path.isdir(_DRIVE_PESQUISAI) else os.path.join(
        os.path.expanduser("~"), "PesquisAI")
    path = os.path.join(base, "backups")
    os.makedirs(path, exist_ok=True)
    return path


#: Cache curto da listagem de backups: o FUSE do Google Drive e lento
#: quando o arquivo ainda nao esta no cache local (a leitura de metadados
#: de 40+ arquivos pode levar ~15 s a frio).
_BACKUPS_CACHE: dict = {"ts": 0.0, "items": None}
_BACKUPS_CACHE_TTL = 45.0  # s


def _warm_autosave_lists(directory: str) -> None:
    """Aquece as listagens de autosave em segundo plano (v0.7.5+).

    A pergunta de retomada aparece ~1 s depois de a pagina carregar. Sem
    este aquecimento, a PRIMEIRA chamada de `/api/autosave` relia e
    reparseava ~20 MB de JSON no Drive (1,0 s; 6 ms com cache) e a
    pergunta chegava atrasada.
    """
    try:
        _session_restore.list_autosaves(directory)
        _session_restore.list_session_autosaves(directory)
    except Exception:  # noqa: BLE001 — aquecimento nunca derruba o boot
        pass


#: Cache (em processo) do index.html cru e comprimido. O HTML tem ~300 KB
#: (5 dicionários de idioma embutidos) e comprime para ~75 KB — 4x menos
#: bytes no proxy do Colab a cada abertura.
_INDEX_CACHE: dict = {"key": None, "raw": b"", "gz": b""}


def _index_payload(path: str) -> tuple[bytes, bytes]:
    """Devolve (cru, gzip) do index.html, com cache por (mtime, tamanho)."""
    try:
        st = os.stat(path)
        key = (path, int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        key = (path, 0, 0)
    if _INDEX_CACHE.get("key") != key:
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            raw = b""
        _INDEX_CACHE.update({
            "key": key,
            "raw": raw,
            "gz": gzip.compress(raw, 6) if raw else b"",
        })
    return _INDEX_CACHE["raw"], _INDEX_CACHE["gz"]


def _list_backups_cached(directory: str | None = None,
                         autosave_dir: str | None = None,
                         force: bool = False) -> list:
    """Backups de sessao do Drive (so backups), com cache curto.

    Filtra o que nao e backup (chaves, consentimentos) e traz data/hora,
    tamanho e integridade de cada arquivo — os dados que o calendario e o
    filtro por data da interface "Restaurar" precisam.
    """
    now = time.time()
    cached = _BACKUPS_CACHE.get("items")
    if (not force and cached is not None
            and (now - float(_BACKUPS_CACHE.get("ts") or 0)) < _BACKUPS_CACHE_TTL):
        return list(cached)
    base = directory or _backup_dir()
    auto = autosave_dir or os.path.join(base, "autosave")
    try:
        items = _session_restore.list_backups(base, auto)
    except Exception as exc:  # pragma: no cover — rede/FUSE
        logger.warning("Falha ao listar backups: %s", exc)
        items = []
    _BACKUPS_CACHE["ts"] = now
    _BACKUPS_CACHE["items"] = list(items)
    return list(items)


def _invalidate_backups_cache() -> None:
    """Chamado depois de gravar um backup/autosave novo."""
    _BACKUPS_CACHE["ts"] = 0.0
    _BACKUPS_CACHE["items"] = None


def _resolve_restore_path(fname_raw: str, backup_dir: str,
                           autosave_dir: str) -> "tuple[str | None, str]":
    """Resolve o arquivo a restaurar, recusando o que nao for backup.

    Devolve ``(caminho, "")`` em caso de sucesso ou ``(None, mensagem)``.
    Sao aceitos somente:

    * backups de sessao — ``backup_ses_<id>_<HH-MM-SS>_<DD-MM-YYYY>.json``
      (prefixo ``backup_``) na pasta de backups;
    * autosaves — ``autosave_<n>.json`` na pasta de autosaves.

    Qualquer outro ``.json`` da pasta (``keys_store.json``, ``keys.json``,
    ``ufvai_consentimento*.json`` …) e **recusado**: nao e backup e nao
    pode ser restaurado. O caminho tambem nao pode escapar das pastas
    (sem ``..``, sem separadores de diretorio).
    """
    raw = (fname_raw or "").strip()
    if not raw:
        return None, "Nome de arquivo inválido."
    # v0.7.4: autosave POR SESSAO — `autosave/sessions/<id>.json`
    # (uma pasta abaixo, com nome validado; sem traversal).
    if raw.startswith("autosave/sessions/"):
        sub = raw[len("autosave/sessions/"):]
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.json", sub or ""):
            return None, "Arquivo de autosave inválido."
        path = os.path.join(autosave_dir, "sessions", sub)
        if not os.path.exists(path):
            return None, f"Arquivo não encontrado: {sub}"
        return path, ""
    is_autosave = raw.startswith("autosave/")
    fname = raw[len("autosave/"):] if is_autosave else raw
    if (fname.startswith(".") or ".." in fname or "/" in fname or "\\" in fname
            or not fname.endswith(".json")):
        return None, "Nome de arquivo inválido."
    # v0.7.1: o nome do autosave pode chegar SEM o prefixo "autosave/".
    # Era exatamente o que a listagem devolvia e o que fazia a retomada na
    # ENTRADA falhar com "Este arquivo nao e um backup de sessao" (o
    # botao "Restaurar", que usa list_backups, traz o prefixo e funcionava).
    if not is_autosave and re.fullmatch(r"autosave_[1-9][0-9]*\.json", fname):
        is_autosave = True
    if is_autosave:
        if not re.fullmatch(r"autosave_[1-9][0-9]*\.json", fname):
            return None, "Arquivo de autosave inválido."
        path = os.path.join(autosave_dir, fname)
    else:
        if not re.fullmatch(r"backup_[A-Za-z0-9._-]+\.json", fname):
            return None, ("Este arquivo não é um backup de sessão (só arquivos "
                          "'backup_*.json' e autosaves podem ser restaurados).")
        path = os.path.join(backup_dir, fname)
    if not os.path.exists(path):
        return None, f"Arquivo não encontrado: {fname}"
    return path, ""


def _project_dir() -> str:
    """Pasta do projeto (onde as conversas do autor vivem).

    As conversas de outros diretorios (por exemplo `/root`, onde o motor
    cria as sessoes de preflight) nao entram no autosave por sessao.
    """
    try:
        return os.getcwd()
    except OSError:
        return ""


def _ttyd_session_id() -> str:
    """Id da sessao que o TERMINAL esta usando (v0.7.3).

    O ttyd e' iniciado com `opencode -s "<ses_id>"`; esse id e' a conversa
    que o usuario ve. Sem ele, o autosave caia em `sessions[0]` — a
    sessao mais recente do motor, que nem sempre e' a do terminal (com
    varias conversas abertas, os slots do autosave misturavam duas).
    """
    try:
        proc = subprocess.run(["ps", "-eo", "cmd"], capture_output=True,
                              text=True, timeout=10)
    except Exception:  # noqa: BLE001 — best effort
        return ""
    for line in (proc.stdout or "").splitlines():
        if "ttyd" not in line or "opencode" not in line:
            continue
        match = re.search(r"(?:--session|-s)\s+\"?(ses_[A-Za-z0-9_-]+)\"?", line)
        if match:
            return match.group(1)
    return ""


def _active_session_id(sessions: list) -> str:
    """Sessao mais recentemente atualizada do motor (v0.7.3)."""
    def _updated(session: dict) -> int:
        info = session.get("time") if isinstance(session, dict) else None
        if not isinstance(info, dict):
            return 0
        try:
            return int(info.get("updated") or 0)
        except (TypeError, ValueError):
            return 0

    ordered = sorted([s for s in (sessions or []) if isinstance(s, dict)],
                     key=_updated, reverse=True)
    return str(ordered[0].get("id") or "") if ordered else ""


def _opencode_bin_or_find() -> str:
    """Binário do OpenCode V2 (cache do boot ou busca)."""
    try:
        return _opencode_bin or find_opencode()
    except FileNotFoundError:
        return "opencode"


def _opencode_auth_export_text() -> "str | None":
    """Saída JSON de `opencode auth export` (None se o comando falhar)."""
    try:
        r = subprocess.run(
            [_opencode_bin_or_find(), "auth", "export"],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("opencode auth export: %s", exc)
        return None
    if r.returncode != 0:
        logger.warning("opencode auth export falhou (rc=%s): %s",
                       r.returncode, (r.stderr or "")[:200])
        return None
    return r.stdout


def _json_has_items(text: "str | None") -> bool:
    """True se o texto é um JSON não vazio (lista ou objeto)."""
    if not text:
        return False
    try:
        data = json.loads(text)
    except ValueError:
        return False
    return isinstance(data, (list, dict)) and len(data) > 0


def save_opencode_auth_to_drive(backup_dir: "str | None" = None) -> bool:
    """Grava as credenciais do OpenCode V2 CIFRADAS no backup.

    Nunca troca um backup existente por um vazio: só grava se a exportação
    trouxer ao menos uma credencial.
    """
    backup_dir = backup_dir or _backup_dir()
    text = _opencode_auth_export_text()
    if not _json_has_items(text):
        return False
    try:
        from .security import encrypt_data, _load_or_create_encryption_key
        key = _load_or_create_encryption_key(backup_dir)
        enc = encrypt_data(key, _b64.b64encode(text.encode("utf-8")).decode("ascii"))
        dest = os.path.join(backup_dir, _OC_AUTH_BACKUP_FILE)
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"_ufvai_enc": True, "format": _OC_AUTH_BACKUP_FORMAT, "data": enc}, fh)
        os.replace(tmp, dest)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao salvar credenciais do OpenCode: %s", exc)
        return False


def restore_opencode_auth_from_drive(backup_dir: "str | None" = None) -> bool:
    """Restaura as credenciais salvas no OpenCode V2 (antes do terminal iniciar)."""
    import tempfile
    backup_dir = backup_dir or _backup_dir()
    src = os.path.join(backup_dir, _OC_AUTH_BACKUP_FILE)
    if not os.path.exists(src):
        return False
    try:
        with open(src, "r", encoding="utf-8") as fh:
            wrapper = json.load(fh)
        if not (isinstance(wrapper, dict) and wrapper.get("_ufvai_enc")):
            return False
        from .security import decrypt_data, _load_or_create_encryption_key
        key = _load_or_create_encryption_key(backup_dir)
        raw = _b64.b64decode(decrypt_data(key, wrapper["data"]).encode("ascii")).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Backup de credenciais do OpenCode ilegível: %s", exc)
        return False

    if wrapper.get("format") != _OC_AUTH_BACKUP_FORMAT:
        # Backup legado (auth.json da V1): a V2 importa o auth.json legado na
        # migração do banco. Só se aplica enquanto o banco ainda não existe.
        if os.path.exists(OPENCODE_DB_PATH):
            return False
        legacy = os.path.expanduser("~/.local/share/opencode/auth.json")
        os.makedirs(os.path.dirname(legacy), exist_ok=True)
        with open(legacy, "w", encoding="utf-8") as fh:
            fh.write(raw)
        os.chmod(legacy, 0o600)
        return True

    if _json_has_items(_opencode_auth_export_text()):
        return False  # o motor já tem credenciais; não duplicar
    fd, tmp_path = tempfile.mkstemp(prefix="ufvai_oc_auth_", suffix=".json", dir="/tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(raw)
        r = subprocess.run(
            [_opencode_bin_or_find(), "auth", "import", tmp_path],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            logger.warning("opencode auth import falhou (rc=%s): %s",
                           r.returncode, (r.stderr or "")[:200])
            return False
        return True
    finally:
        try:
            os.remove(tmp_path)  # segredos não ficam em /tmp
        except OSError:
            pass


def _keys_backup_dir() -> str:
    """Pasta das chaves cifradas (``backups/``) em uso nesta execução.

    v0.7.8: o reinício do serviço após salvar/remover chave precisa usar o
    MESMO armazenamento que a interface usa. ``start_wrapper_server`` guarda
    o caminho resolvido em ``_KEYS_BACKUP_DIR``; sem ele, cai no Drive e
    depois no modo offline (``~/PesquisAI/backups``).
    """
    if _KEYS_BACKUP_DIR:
        return _KEYS_BACKUP_DIR
    drive = os.path.join("/content", "drive", "My Drive", "PesquisAI", "backups")
    if os.path.isdir(drive):
        return drive
    return os.path.join(os.path.expanduser("~"), "PesquisAI", "backups")


def _start_opencode_service_with_keys(timeout_s: float = 20.0) -> bool:
    """Sobe o serviço do motor já com as chaves decifradas do Drive.

    v0.7.8 (29/10/2026): o serviço guarda o ambiente de quando nasceu. Sem
    isto, uma chave salva/removida pela interface só valeria no próximo boot
    — o serviço antigo, sem a variável, continuava atendendo as sessões. Foi
    o que fez o OpenCode v2.2 "parar de carregar as chaves do Drive": na v2.2
    o catálogo de provedores é resolvido DENTRO do serviço.

    Returns:
        True se o serviço respondeu no prazo.
    """
    try:
        from .run_fast import ensure_service_project_dir
    except Exception as exc:  # noqa: BLE001
        logger.warning("Serviço com chaves: import indisponível (%s)", exc)
        return False
    project = _workspace_dir()
    return bool(
        ensure_service_project_dir(
            project, timeout_s=timeout_s, backup_dir=_keys_backup_dir()
        )
    )


def _apply_opencode_env_change_async() -> None:
    """Após salvar/remover chave: reergue o serviço com o ambiente novo.

    Paramos o serviço em background, subimos de novo JÁ com as chaves
    decifradas (v0.7.8) e reiniciamos o terminal. Roda em thread para não
    atrasar a resposta HTTP.
    """
    def _worker() -> None:
        try:
            _shutdown_stop_opencode_service()
        except Exception:  # noqa: BLE001
            pass
        try:
            _start_opencode_service_with_keys()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Serviço não voltou com as chaves novas: %s", exc)
        try:
            restart_ttyd_with_lang(_current_lang or "pt_BR")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reinício do terminal após troca de chave falhou: %s", exc)

    threading.Thread(target=_worker, daemon=True, name="ufvai-apply-keys").start()


def start_wrapper_server():
    # Determine correct backup dir — v0.6.9-6: offline usa local se Drive sem escrita
    _pesquisai_drive = "/content/drive/My Drive/PesquisAI"
    # Se Drive existe mas não tem escrita, usa local (fallback offline)
    _drive_writable = os.path.isdir(_pesquisai_drive) and os.access(_pesquisai_drive, os.W_OK)
    # Também respeita vault fallback: se vault é local, backup também é local
    try:
        _vault_is_local = "home" in str(os.environ.get("PESQUISAI_OBSIDIAN_VAULT","")) or "/home/" in str(_pesquisai_drive)
        # checa se discovery fallback ativou
        from .obsidian.discovery import get_default_vault_path as _gdv
        _vd = _gdv()
        if _vd and ("/home/" in _vd or str(_vd).startswith(str(os.path.expanduser("~")))):
            _drive_writable = False
    except Exception:
        pass
    if _drive_writable:
        _base = _pesquisai_drive
    elif os.path.isdir(_folder_path) and "drive" in _folder_path.lower() and os.access(_folder_path, os.W_OK):
        _base = _folder_path
    else:
        _base = os.path.join(os.path.expanduser("~"), "PesquisAI")
        os.makedirs(_base, exist_ok=True)
    DRIVE_BACKUP_DIR = os.path.join(_base, "backups")
    os.makedirs(DRIVE_BACKUP_DIR, exist_ok=True)
    # v0.7.8: guarda o caminho resolvido — o reinício do serviço após
    # salvar/remover chave precisa ler exatamente este armazenamento.
    global _KEYS_BACKUP_DIR
    _KEYS_BACKUP_DIR = DRIVE_BACKUP_DIR
    # v0.7.0: pasta dos autosaves (3 ultimos, rotacionados)
    AUTOSAVE_DIR = os.path.join(DRIVE_BACKUP_DIR, "autosave")
    os.makedirs(AUTOSAVE_DIR, exist_ok=True)
    # v0.7.5+: aquece a listagem em segundo plano (a pergunta de retomada
    # nao pode esperar a leitura de ~20 MB do Drive).
    try:
        threading.Thread(target=_warm_autosave_lists, args=(AUTOSAVE_DIR,),
                         daemon=True, name="ufvai-autosave-warm").start()
    except Exception:  # noqa: BLE001
        pass
    print(f"📁 Backup dir: {DRIVE_BACKUP_DIR}")
    print(f"💾 Autosave dir: {AUTOSAVE_DIR}")
    
    # v0.4.2.2: restaura idioma persistido (cookie/arquivo)
    # v0.6.15: helper garante detecção ANTES do ttyd (antes bug _current_lang="pt_BR" truthy)
    global _current_lang
    try:
        _ensure_lang_initialized()
        # Normaliza (aceita "pt", "en_US" etc.) e valida - garante mesmo se helper já normalizou
        try:
            _short = (_current_lang or "pt").split("_")[0].lower()
            _current_lang = _LANG_MAP.get(_short, _current_lang if _current_lang in _LANG_MAP.values() else "pt_BR")
        except Exception:
            _current_lang = "pt_BR"
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

        # ── v0.6.0 segurança ─────────────────────────────────────
        def _authorized(self) -> bool:
            """Exige o token de sessão injetado no HTML do wrapper."""
            if not _SESSION_TOKEN:
                return True  # uso standalone/script (sem HTML gerado)
            return self.headers.get("X-UFVAI-Token", "") == _SESSION_TOKEN

        def _reject_token(self):
            self._json(403, {
                "error": "Token de sessão ausente ou inválido.",
                "hint": "Recarregue a página do wrapper (F5).",
            })
        
        def _json(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            # v0.6.0: CORS '*' removido (a UI é same-origin). Headers seguros:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        
        def do_OPTIONS(self):
            # v0.6.0: preflight same-origin apenas (sem Access-Control-*)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        
        def _safe_error(self, exc: BaseException) -> None:
            """v0.7.0: transforma excecao inesperada em erro JSON claro.

            Sem esta rede, qualquer excecao no handler fechava a conexao
            sem resposta ("Empty reply from server") e a interface mostrava
            apenas "falha na conexao" — sem causa.
            """
            logger.exception("Excecao inesperada no handler %s", self.path)
            try:
                self._json(500, {
                    "error": f"Erro interno: {type(exc).__name__}: {exc}"[:300],
                    "traceback": traceback.format_exc()[-800:],
                })
            except Exception:
                pass

        def do_GET(self):
            try:
                self._do_GET_impl()
            except Exception as exc:
                self._safe_error(exc)

        def _do_GET_impl(self):
            p = urlparse(self.path).path
            if p.startswith("/api/") and not self._authorized():
                return self._reject_token()

            if p == "/vendor/marked.min.js":
                # v0.6.0: asset embutido para funcionamento offline
                try:
                    _vp = Path(__file__).resolve().parent / "vendor" / "marked.min.js"
                    content = open(_vp, "rb").read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/javascript; charset=utf-8")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Cache-Control", "max-age=86400")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception:
                    self.send_error(404)
                return

            if p == "/favicon.ico":
                # v0.6.6: favicon direto (browsers pedem /favicon.ico por padrão).
                # Serve o PNG 64 da marca via a mesma whitelist de assets.
                for _root in (
                    Path(__file__).resolve().parent.parent / "assets",
                    Path(__file__).resolve().parent / "assets",
                    Path("/opt/pesquisai/assets"),
                    Path.home() / "PesquisAI" / "assets",
                ):
                    try:
                        _cand = (_root / "ufvai-64.png").resolve()
                        if _cand.is_file():
                            _content = _cand.read_bytes()
                            self.send_response(200)
                            self.send_header("Content-Type", "image/png")
                            self.send_header("Cache-Control", "max-age=86400")
                            self.send_header("Content-Length", str(len(_content)))
                            self.end_headers()
                            self.wfile.write(_content)
                            return
                    except Exception:
                        continue
                self.send_error(404)
                return

            if p.startswith("/assets/"):
                # v0.6.4: assets locais (logomarca UFVAI etc.) — offline-safe.
                # Whitelist estrita + traversal guard (resolve() deve cair dentro
                # de um dos diretórios de assets conhecidos).
                _ASSET_TYPES = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".svg": "image/svg+xml",
                    ".ico": "image/x-icon",
                }
                _name = os.path.basename(urlparse(self.path).path)  # sem subdirs
                if _name in (
                    "logo-oficial-288.jpg", "logo.svg", "ico.svg",
                    "icon.png", "ufvai-256.png", "ufvai-128.png", "ufvai-64.png",
                ):
                    _roots = [
                        Path(__file__).resolve().parent.parent / "assets",
                        Path(__file__).resolve().parent / "assets",
                        Path("/opt/pesquisai/assets"),
                        Path.home() / "PesquisAI" / "assets",
                    ]
                    _content = None; _mime = _ASSET_TYPES.get(Path(_name).suffix.lower())
                    for _root in _roots:
                        try:
                            _cand = (_root / _name).resolve()
                            if _root.resolve() not in _cand.parents and _cand.parent != _root.resolve():
                                continue  # traversal guard
                            if _cand.is_file():
                                _content = _cand.read_bytes()
                                break
                        except Exception:
                            continue
                    if _content and _mime:
                        self.send_response(200)
                        self.send_header("Content-Type", _mime)
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Cache-Control", "max-age=86400")
                        self.send_header("Content-Length", str(len(_content)))
                        self.end_headers()
                        self.wfile.write(_content)
                        return
                self.send_error(404)
                return

            if p in ("/", "/index.html"):
                idx = os.path.join(WRAPPER_DIR, "index.html")
                raw, gz = _index_payload(idx)
                # v0.7.5+: o HTML tem ~300 KB (5 idiomas embutidos). Com
                # gzip vai para ~75 KB — bem menos bytes pelo proxy do
                # Colab no caminho crítico da abertura.
                use_gz = "gzip" in (self.headers.get("Accept-Encoding", "") or "").lower()
                content = gz if (use_gz and gz) else raw
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Frame-Options", "SAMEORIGIN")
                if use_gz and gz:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                # v0.7.5: o HTML carrega o JS das telas de abertura — NUNCA
                # deixar o navegador reusar uma versão antiga em cache
                # (era o que mantinha o comportamento velho após a correção).
                self.send_header("Cache-Control", "no-store, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            
            if p == "/api/sessions":
                # v0.6.25: a listagem vai para o SERVIDOR do motor
                # (`opencode api session.list`). A listagem por CLI
                # (`session list --format json`) e escopada por projeto e
                # resolvida pelo CWD do processo: o wrapper roda no diretorio
                # do Drive, mas as sessoes da TUI vivem no projeto `/root` ->
                # a lista voltava VAZIA (historico de sessoes quebrado).
                try:
                    sessions = _session_restore.list_sessions(_opencode_bin or "opencode", env=_env)
                except Exception as exc:
                    logger.warning("Falha ao listar sessoes: %s", exc)
                    sessions = []
                # Normaliza o formato: a interface le `date`/`created` (o
                # servidor devolve `time.created` em epoch ms).
                normalized = []
                for s in sessions:
                    item = dict(s)
                    created = (s.get("time") or {}).get("created")
                    if created:
                        item["created"] = created
                        item["date"] = time.strftime(
                            "%d/%m/%Y %H:%M", time.localtime(created / 1000)
                        )
                    item.setdefault("title", s.get("id", ""))
                    normalized.append(item)
                self._json(200, {"sessions": normalized})
                return

            if p == "/api/lang":
                # v0.4.2.2: retorna o idioma atual persistido
                # v0.7.5+: informa se a saudação ainda está pendente — o
                # frontend só precisa fazer o POST quando há divergência OU
                # saudação a semear (sem isso, sessão nova com o mesmo idioma
                # do servidor ficaria sem a mensagem padrão).
                _prefs_lang = _read_prefs() or {}
                self._json(200, {
                    "lang": _current_lang,
                    # v0.7.5+ (sem bump): "user" = escolha explícita no menu;
                    # "browser"/"auto" = detecção. O frontend usa isso para
                    # não deixar um cookie antigo vencer o navegador.
                    "lang_source": str(_prefs_lang.get("lang_source") or "auto"),
                    "greeting": get_greeting(_current_lang),
                    "greeting_pending": _greeting_pending(_current_ttyd_session),
                })
                return

            if p == "/api/ttyd_ready":
                # v0.6.5: status do terminal para o splash de carregamento da UI.
                # O frontend faz polling aqui antes de apontar o iframe — assim
                # o usuário nunca vê ERR_CONNECTION_REFUSED dentro do terminal.
                # v0.7.5: timeout curto (0,25 s). O polling é frequente e a
                # porta local responde na hora; 1,2 s por requisição segurava
                # o splash quando o ttyd ainda estava subindo.
                try:
                    ready = _wait_port_open(TERMINAL_PORT, timeout_s=0.25)
                except Exception:
                    ready = False
                # v0.7.5+ (sem bump): AUTO-CURA. Se o ttyd morreu (SIGKILL de
                # uma execução anterior), a porta nunca abria e a interface
                # ficava "carregando" para sempre. Religa anexando ao tmux —
                # a conversa continua a mesma.
                if not ready:
                    try:
                        ready = _revive_ttyd()
                    except Exception:
                        ready = False
                self._json(200, {
                    "ready": bool(ready),
                    "port": TERMINAL_PORT,
                    # v0.7.5+: pid do ttyd — o frontend usa para detectar
                    # reinício do servidor e recarregar o iframe sozinho.
                    "pid": getattr(_TTYD_PROC, "pid", None) if ready else None,
                })
                return

            if p == "/api/autosave":
                # v0.7.0 — listagem dos autosaves (usada pela pergunta de
                # retomada na abertura da interface). A GRAVACAO e' o POST.
                try:
                    items = _session_restore.list_autosaves(AUTOSAVE_DIR)
                except Exception as exc:
                    logger.warning("Falha ao listar autosaves: %s", exc)
                    items = []
                # v0.7.4: um autosave POR CONVERSA (quando ha varias sessoes
                # abertas, o autosave antigo so guardava uma).
                try:
                    per_session = _session_restore.list_session_autosaves(AUTOSAVE_DIR)
                except Exception as exc:
                    logger.warning("Falha ao listar autosaves por sessao: %s", exc)
                    per_session = []
                self._json(200, {
                    "autosaves": items,
                    "latest": items[0] if items else None,
                    "sessions": per_session,
                    "sessions_count": len(per_session),
                    "dir": AUTOSAVE_DIR,
                })
                return

            if p == "/api/backups":
                # v0.7.0 — lista SOMENTE backups de sessao, com data/hora,
                # tamanho e integridade, para o CALENDARIO e o FILTRO por data
                # do modal "Restaurar". Antes, a listacao devolvia todos os
                # .json da pasta (incluindo keys_store.json, keys.json e os
                # consentimentos), que nao sao backups e nao podem ser
                # restaurados.
                items = _list_backups_cached(DRIVE_BACKUP_DIR, AUTOSAVE_DIR)
                # v0.7.4: as conversas salvas individualmente entram na lista
                # do modal "Restaurar" (cada uma pode ser restaurada).
                try:
                    _per_session = _session_restore.list_session_autosaves(AUTOSAVE_DIR)
                except Exception:
                    _per_session = []
                _known = {item.get("file") for item in items}
                for _item in _per_session:
                    if _item.get("file") not in _known:
                        items.append(_item)
                dates = sorted({item["date"] for item in items}, reverse=True)
                self._json(200, {
                    "backups": items,
                    "files": [item["file"] for item in items],
                    "dates": dates,
                    "count": len(items),
                })
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
                        "env_keys_found_count": sum(
                            1 for k in os.environ
                            if any(x in k for x in ["KEY", "TOKEN", "SECRET", "API"])
                        ),
                    },
                    "drive_backup_dir": DRIVE_BACKUP_DIR,
                    "version": VERSION,
                })
                return
            
            if p == "/api/theme":
                # v0.6.20: tema ativo vem do cli.json (OpenCode V2) com
                # fallback para o tui.json (OpenCode V1).
                self._json(200, {"theme": _read_theme()})
                return

            if p == "/api/admin/telemetry":
                # v0.6.4: estado da telemetria para o painel Admin (nunca expõe o secret)
                self._json(200, _tel_masked_state())
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
                    "env_keys_found_count": sum(
                        1 for k in os.environ
                        if any(x in k for x in ["KEY", "TOKEN", "SECRET", "API"])
                    ),
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
                    "env_keys_count": sum(1 for k in _env if "KEY" in k or "TOKEN" in k or "SECRET" in k),
                })
                return
            
            if p == "/api/apikey":
                qs = parse_qs(urlparse(self.path).query)
                provider = qs.get("provider", [""])[0].strip()
                keys = load_encrypted_keys(DRIVE_BACKUP_DIR)
                if provider:
                    val = keys.get(provider, "")
                    masked = (val[:4] + "…") if val else ""
                    self._json(200, {"apikey": masked, "masked": True})
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
                # Suporta ?lang=pt_BR | en_US | es_ES | fr_FR | zh_CN (default pt_BR)
                qs = parse_qs(urlparse(self.path).query)
                lang = (qs.get("lang", ["pt_BR"])[0] or "pt_BR").strip()
                lang_code = lang.split("_")[0].lower() if "_" in lang else lang.lower()
                # Map pt_BR -> pt, en_US -> en, es_ES -> es, fr_FR -> fr, zh_CN -> zh
                if lang_code in _LANG_MAP:
                    full = _LANG_MAP[lang_code]
                elif lang in _LANG_MAP.values():
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
                # v0.6.0: cadeia de fallback (zh_CN → en_US → pt_BR)
                _lang_order = [full] + (["en_US"] if full == "zh_CN" else [])
                if "pt_BR" not in _lang_order:
                    _lang_order.append("pt_BR")
                cand_files: list[str] = []
                for _lg in _lang_order:
                    _sh = _lg.split("_")[0]
                    # NOTA: o pt-BR canônico vive na RAIZ (AGENTS.md) e é
                    # espelhado em agents/AGENTS.pt.md (cópia idêntica).
                    # Se o espelho existir, é ele que é servido primeiro;
                    # senão, o fallback canônico abaixo cobre o pt.
                    cand_files.append(f"AGENTS.{_sh}.md")
                    cand_files.append(f"AGENTS.{_lg}.md")
                content = None
                served_file = None
                served_lang = None
                tried_files = []
                if agents_dir:
                    for fname in cand_files:
                        fpath = os.path.join(agents_dir, fname)
                        tried_files.append(fpath)
                        if os.path.isfile(fpath):
                            try:
                                with open(fpath, "r", encoding="utf-8") as fh:
                                    content = fh.read()
                                served_file = fname
                                served_lang = fname[7:-3] if fname.startswith("AGENTS.") else ""
                                break
                            except Exception as e:
                                content = f"⚠️ Erro ao ler {fname}: {e}"
                                break
                if content is None:
                    # Fallback canônico: <raiz>/AGENTS.md (pt-BR, fonte única).
                    # Cobre o pt_BR (sem AGENTS.pt.md desde a remoção da
                    # duplicata) e serve de última instância p/ qualquer idioma.
                    _root_agents = os.path.join(parent, "AGENTS.md")
                    tried_files.append(_root_agents)
                    if os.path.isfile(_root_agents):
                        try:
                            with open(_root_agents, "r", encoding="utf-8") as fh:
                                content = fh.read()
                            served_file = "AGENTS.md"
                            served_lang = "pt"
                        except Exception as e:
                            content = f"⚠️ Erro ao ler AGENTS.md: {e}"
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
                    "served_file": served_file or "",
                    "served_lang": served_lang or short,
                    "fallback_used": bool(served_lang and served_lang not in (short, full)),
                    "filename": served_file or f"AGENTS.{short}.md",
                    "content": content,
                })
                return

            if p == "/api/obsidian":
                # v0.5.1.2: status da memória PesquisAI (segundo cérebro)
                # Lê o vault via pesquisai.obsidian (módulo oficial).
                # Retorna JSON com:
                #   - enabled / status / root
                #   - notes_count / tags_count / recent_notes / recent_daily
                #   - templates / templates_path
                #   - message (string amigável i18n pronta para toast)
                # v0.5.1.8: suporte a ?include=tree para unificar rotas
                q_obs = urlparse(self.path).query
                qp_obs = parse_qs(q_obs)
                incl_tree = "tree" in (qp_obs.get("include", [""])[0] or "")
                result = {
                    "ok": True,
                    "enabled": False,
                    "status": "disabled",
                    "root": None,
                    "writable": False,
                    "notes_count": 0,
                    "tags_count": 0,
                    "avg_note_length": 0,
                    "links": {"edges": 0, "nodes": 0},
                    "recent_notes": [],
                    "recent_daily": [],
                    "templates": [],
                    "templates_path": None,
                    "message": "Módulo Obsidian não instalado.",
                    "version": VERSION,
                }
                try:
                    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
                    mem = _get_memory()
                    if mem.status == ObsidianMemoryStatus.DISABLED:
                        result["status"] = "disabled"
                        result["message"] = (
                            "Memória desativada. Defina PESQUISAI_OBSIDIAN_VAULT "
                            "apontando para a pasta vault/ no Drive."
                        )
                    elif mem.status == ObsidianMemoryStatus.NO_VAULT:
                        result["status"] = "no_vault"
                        result["root"] = str(mem.root) if mem.root else None
                        result["message"] = (
                            "PESQUISAI_OBSIDIAN_VAULT definida, mas a pasta não existe. "
                            "Crie a pasta vault/ no Google Drive."
                        )
                    elif mem.status == ObsidianMemoryStatus.READ_ONLY:
                        result["status"] = "read_only"
                        result["root"] = str(mem.root) if mem.root else None
                        result["message"] = (
                            "Vault existe, mas sem permissão de escrita. "
                            f"Verifique as permissões de {mem.root}."
                        )
                    elif mem.status == ObsidianMemoryStatus.ERROR:
                        result["status"] = "error"
                        result["message"] = (
                            f"Erro ao abrir vault: {mem.last_error or 'desconhecido'}"
                        )
                    elif mem.status == ObsidianMemoryStatus.READY:
                        stats = mem.stats()
                        # Notas recentes (top 5)
                        recent = []
                        try:
                            for s in mem.search("", limit=5):
                                n = s.note
                                if n:
                                    recent.append({
                                        "path": n.path,
                                        "title": n.metadata.title if n.metadata else n.path,
                                        "tags": list(n.tags[:6]),
                                        "length": len(n.body or ""),
                                    })
                        except Exception:
                            pass
                        # Daily notes recentes (top 3)
                        recent_daily = []
                        try:
                            for n in mem.recent_daily_notes(limit=3):
                                recent_daily.append({
                                    "path": n.path,
                                    "title": n.metadata.title if n.metadata else n.path,
                                })
                        except Exception:
                            pass
                        # Templates oficiais
                        templates = []
                        templates_path = None
                        try:
                            from pathlib import Path as _P
                            # 1) skill instalada
                            skill_tpl = _P.home() / ".agents" / "skills" / "obsidian-memory" / "templates"
                            # 2) skills/obsidian-memory/templates (dev local)
                            here = _P(__file__).resolve().parent
                            dev_tpl = here.parent / "skills" / "obsidian-memory" / "templates"
                            for cand in (skill_tpl, dev_tpl):
                                if cand.is_dir():
                                    templates_path = str(cand)
                                    templates = sorted(
                                        f.stem for f in cand.glob("*.md")
                                    )
                                    break
                        except Exception:
                            pass
                        result.update({
                            "enabled": True,
                            "status": "ready",
                            "root": stats.get("root"),
                            "writable": True,
                            "notes_count": stats.get("notes", 0),
                            "tags_count": stats.get("tags", 0),
                            "avg_note_length": stats.get("avg_note_length", 0),
                            "links": stats.get("links", {"edges": 0, "nodes": 0}),
                            "recent_notes": recent,
                            "recent_daily": recent_daily,
                            "templates": templates,
                            "templates_path": templates_path,
                            "message": "Memória ativa.",
                        })
                        # v0.5.1.8: se ?include=tree, inclui árvore de notas
                        if incl_tree and mem._vault is not None:
                            try:
                                tree_data = []
                                folders_data: dict[str, list[dict]] = {}
                                for note in _iter_memory_notes(mem):  # v0.6.17: RAM
                                    rel = note.path
                                    folder = str(Path(rel).parent) if "/" in rel else ""
                                    folders_data.setdefault(folder, []).append({
                                        "path": note.path,
                                        "title": note.metadata.title,
                                        "tags": list(note.tags)[:6],
                                        "length": len(note.body or ""),
                                        "updated": _safe_isoformat(note.metadata.updated),
                                        "is_pesquisai_generated": note.is_pesquisai_generated,
                                    })
                                for folder in sorted(folders_data):
                                    tree_data.append({
                                        "folder": folder,
                                        "notes": sorted(folders_data[folder], key=lambda n: n["title"].lower()),
                                    })
                                result["tree"] = tree_data
                                result["tree_total"] = sum(len(t["notes"]) for t in tree_data)
                            except Exception:
                                result["tree"] = []
                                result["tree_total"] = 0
                    else:
                        result["status"] = str(mem.status.value)
                        result["message"] = f"Status desconhecido: {mem.status.value}"
                except ImportError:
                    result["status"] = "module_unavailable"
                    result["message"] = (
                        "Módulo pesquisai.obsidian não encontrado. "
                        "Verifique se o pacote foi instalado."
                    )
                except Exception as e:  # noqa: BLE001
                    result["ok"] = False
                    result["status"] = "error"
                    result["message"] = f"Erro inesperado: {e!r}"
                self._json(200, result)
                return

            # ════════════════════════════════════════════════════════════
            # v0.5.1.4 — Memória Obsidian: navegar, ler, buscar, tags
            # ════════════════════════════════════════════════════════════

            if p == "/api/obsidian/note":
                # GET /api/obsidian/note?path=foo/bar.md
                # Lê o conteúdo cru (markdown com frontmatter) de uma nota.
                q = urlparse(self.path).query
                qp = parse_qs(q)
                rel_path = (qp.get("path", [""])[0] or "").strip()
                if not rel_path:
                    self._json(400, {"error": "path obrigatório."})
                    return
                try:
                    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
                    mem = _get_memory()
                    if mem.status != ObsidianMemoryStatus.READY:
                        self._json(409, {
                            "ok": False,
                            "error": f"Memória não está pronta (status={mem.status.value}).",
                            "status": mem.status.value,
                        })
                        return
                    note = mem.get(rel_path)
                    if note is None:
                        self._json(404, {"error": f"Nota não encontrada: {rel_path}"})
                        return
                    raw = note.to_markdown()
                    self._json(200, {
                        "ok": True,
                        "path": note.path,
                        "title": note.metadata.title,
                        "tags": list(note.tags),
                        "wikilinks": list(note.wikilinks),
                        "is_pesquisai_generated": note.is_pesquisai_generated,
                        "created": _safe_isoformat(note.metadata.created),
                        "updated": _safe_isoformat(note.metadata.updated),
                        "body": note.body,
                        "raw": raw,
                        "metadata": note.metadata.to_dict(),
                    })
                except PermissionError as e:
                    self._json(403, {"ok": False, "error": str(e)})
                except FileNotFoundError as e:
                    self._json(404, {"ok": False, "error": str(e)})
                except Exception as e:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": f"Erro: {e!r}"})
                return

            if p == "/api/obsidian/tree":
                # GET /api/obsidian/tree?subdir=research
                # Retorna árvore de pastas com notas e metadados resumidos.
                q = urlparse(self.path).query
                qp = parse_qs(q)
                subdir = (qp.get("subdir", [""])[0] or "").strip() or None
                try:
                    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
                    mem = _get_memory()
                    if mem.status != ObsidianMemoryStatus.READY:
                        self._json(409, {"ok": False, "error": f"status={mem.status.value}"})
                        return
                    assert mem._vault is not None
                    tree: list[dict] = []
                    base = (mem._vault.root / subdir) if subdir else mem._vault.root
                    if not base.is_dir():
                        self._json(200, {"ok": True, "tree": [], "subdir": subdir or ""})
                        return
                    # Agrupa por pasta de primeiro nível
                    folders: dict[str, list[dict]] = {}
                    for note in _iter_memory_notes(mem, subdir=subdir):  # v0.6.17: RAM
                        rel = note.path
                        folder = str(Path(rel).parent) if "/" in rel else ""
                        folders.setdefault(folder, []).append({
                            "path": note.path,
                            "title": note.metadata.title,
                            "tags": list(note.tags)[:6],
                            "length": len(note.body or ""),
                            "updated": _safe_isoformat(note.metadata.updated),
                            "is_pesquisai_generated": note.is_pesquisai_generated,
                        })
                    # Ordena pastas e notas
                    for folder in sorted(folders):
                        tree.append({
                            "folder": folder,
                            "notes": sorted(folders[folder], key=lambda n: n["title"].lower()),
                        })
                    self._json(200, {
                        "ok": True,
                        "root": str(mem._vault.root),
                        "subdir": subdir or "",
                        "tree": tree,
                        "total": sum(len(t["notes"]) for t in tree),
                    })
                except Exception as e:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": f"Erro: {e!r}"})
                return

            if p == "/api/obsidian/search":
                # GET /api/obsidian/search?q=foo&limit=20
                q = urlparse(self.path).query
                qp = parse_qs(q)
                query = (qp.get("q", [""])[0] or "").strip()
                try:
                    limit = int(qp.get("limit", ["20"])[0])
                except ValueError:
                    limit = 20
                limit = max(1, min(limit, 100))
                try:
                    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
                    mem = _get_memory()
                    if mem.status != ObsidianMemoryStatus.READY:
                        self._json(409, {"ok": False, "error": f"status={mem.status.value}"})
                        return
                    # Se query vazia, lista todas (top N por path)
                    if not query:
                        results = []
                        for note in _iter_memory_notes(mem):  # v0.6.17: RAM
                            results.append({
                                "path": note.path,
                                "title": note.metadata.title,
                                "snippet": (note.body or "")[:160].replace("\n", " "),
                                "tags": list(note.tags)[:6],
                                "score": 0.0,
                                "matched_field": "all",
                            })
                        results.sort(key=lambda r: r["path"], reverse=True)
                        results = results[:limit]
                    else:
                        sr = mem.search(query, limit=limit)
                        results = [r.to_dict() for r in sr]
                    self._json(200, {
                        "ok": True,
                        "query": query,
                        "results": results,
                        "count": len(results),
                    })
                except Exception as e:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": f"Erro: {e!r}"})
                return

            if p == "/api/obsidian/tags":
                # GET /api/obsidian/tags — lista de tags com contagem
                try:
                    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
                    mem = _get_memory()
                    if mem.status != ObsidianMemoryStatus.READY:
                        self._json(409, {"ok": False, "error": f"status={mem.status.value}"})
                        return
                    summary = mem.tags_summary()
                    # Ordena por contagem desc
                    tags_list = sorted(
                        [{"tag": t, "count": c} for t, c in summary.items()],
                        key=lambda x: (-x["count"], x["tag"]),
                    )
                    self._json(200, {
                        "ok": True,
                        "tags": tags_list,
                        "count": len(tags_list),
                    })
                except Exception as e:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": f"Erro: {e!r}"})
                return

            if p == "/api/consent":
                # v0.6.0: estado do consentimento (Termos de Uso/telemetria)
                # v0.6.6: + estado do contato (e-mail mascarado, nunca exposto)
                # v0.6.9: + profile persistente (backups/ufvai_consentimento.json)
                #          p/ pré-preencher a tela de Termos nas reaberturas.
                #          O e-mail volta EM CLARO somente ao próprio usuário,
                #          na sessão autenticada dele (token obrigatório).
                state = {"accepted": False, "analytics": False}
                try:
                    with open(os.path.expanduser("~/.config/ufvai_consent.json"), encoding="utf-8") as fh:
                        state.update(json.load(fh))
                except Exception:
                    pass
                try:
                    state.update({"contact": _tel_contact_status()})
                except Exception:
                    pass
                try:
                    prof = _read_consent_profile()
                    state["profile"] = {
                        "email": str(prof.get("email", "")),
                        "name": str(prof.get("name", "") or prof.get("nome", "")),
                        "nome": str(prof.get("name", "") or prof.get("nome", "")),
                        "ip": str(prof.get("ip", "")),
                        "analytics": bool(prof.get("analytics", True)),
                        "accepted": bool(prof.get("accepted", False)),
                        "terms_version": str(prof.get("terms_version", "")),
                    }
                except Exception:
                    state["profile"] = {}
                self._json(200, {"ok": True, **state})
                return

            # v0.6.9: Manual do UFVAI — serve o MANUAL.md (botão 📘 da barra)
            if p == "/api/manual":
                _cands = []
                _here = os.path.dirname(os.path.abspath(__file__))
                _parent = os.path.dirname(_here)
                _cands.append(os.path.join(_parent, "MANUAL.md"))
                for _ in range(5):
                    _here = os.path.dirname(_here)
                    if _here and _here != os.path.dirname(_here):
                        _cands.append(os.path.join(_here, "MANUAL.md"))
                if _folder_path:
                    _cands.append(os.path.join(_folder_path, "MANUAL.md"))
                    _cands.append(os.path.join(os.path.dirname(_folder_path), "MANUAL.md"))
                _cands.append(os.path.join(os.getcwd(), "MANUAL.md"))
                _mcontent = None
                _mserved = None
                for _mf in _cands:
                    if os.path.isfile(_mf):
                        try:
                            with open(_mf, "r", encoding="utf-8") as fh:
                                _mcontent = fh.read()
                            _mserved = _mf
                            break
                        except Exception:
                            continue
                if _mcontent is None:
                    self._json(200, {
                        "ok": False,
                        "error": "MANUAL.md não encontrado localmente.",
                        "github": "https://github.com/gustavobraga-byte/PesquisAI/blob/main/MANUAL.md",
                        "tried": _cands[:6],
                    })
                    return
                self._json(200, {"ok": True, "source": _mserved, "content": _mcontent})
                return

            self.send_error(404)

        def do_POST(self):
            try:
                self._do_POST_impl()
            except Exception as exc:
                self._safe_error(exc)

        def _do_POST_impl(self):
            p = urlparse(self.path).path
            # v0.6.0: rate limit generoso nos mutantes (120/min/IP)
            ip = self.client_address[0] if self.client_address else "?"
            now = time.time()
            win = [t for t in _RATE.get(ip, []) if now - t < 60]
            if p.startswith("/api/") and len(win) >= 120:
                return self._json(429, {"error": "Muitas requisições. Aguarde alguns segundos."})
            if p.startswith("/api/"):
                win.append(now)
                _RATE[ip] = win[-240:]
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > 10 * 1024 * 1024:
                return self._json(413, {"error": "Corpo da requisição muito grande."})
            if p.startswith("/api/") and not self._authorized():
                return self._reject_token()
            body = json.loads(self.rfile.read(length)) if length else {}

            # ════════════════════════════════════════════════════════════
            # v0.5.1.4 — Memória Obsidian: salvar, criar, deletar nota
            # ════════════════════════════════════════════════════════════
            if p == "/api/obsidian/note":
                action = (body.get("action", "save") or "save").lower().strip()
                try:
                    from pesquisai.obsidian import ObsidianMemory, ObsidianMemoryStatus
                    from pesquisai.obsidian.models import Note, NoteMetadata
                    from pesquisai.obsidian.models import extract_wikilinks, extract_tags
                    import datetime as _dt
                    from dataclasses import replace as _dc_replace
                    mem = _get_memory()
                    if mem.status != ObsidianMemoryStatus.READY:
                        self._json(409, {"ok": False, "error": f"status={mem.status.value}"})
                        return
                    assert mem._vault is not None

                    if action == "save":
                        rel_path = (body.get("path", "") or "").strip()
                        if not rel_path:
                            self._json(400, {"ok": False, "error": "path obrigatório."})
                            return
                        force = bool(body.get("force", False))
                        new_body = body.get("body", "")
                        new_title = (body.get("title", "") or "").strip()
                        new_tags_in = body.get("tags", []) or []
                        new_tags = tuple(t.strip() for t in new_tags_in if t and str(t).strip())

                        existing = mem.get(rel_path)
                        today = _dt.date.today()
                        if existing is not None:
                            final_tags = new_tags or existing.metadata.tags
                            updated_meta = _dc_replace(
                                existing.metadata,
                                title=new_title or existing.metadata.title,
                                updated=today,
                                tags=final_tags,
                            )
                            body_wikilinks = extract_wikilinks(new_body)
                            body_tags = extract_tags(new_body)
                            merged_tags = tuple(sorted(set(updated_meta.tags) | set(body_tags)))
                            new_note = Note(
                                path=existing.path,
                                metadata=updated_meta,
                                body=new_body,
                                wikilinks=body_wikilinks,
                                tags=merged_tags,
                            )
                            try:
                                mem._vault.write(new_note, force=force)
                            except PermissionError as e:
                                self._json(403, {
                                    "ok": False, "error": str(e),
                                    "hint": "Nota humana: envie force=true para sobrescrever.",
                                })
                                return
                        else:
                            meta = NoteMetadata(
                                title=new_title or Path(rel_path).stem,
                                created=today,
                                updated=today,
                                tags=new_tags or ("pesquisai/draft",),
                                created_by="pesquisai",
                                status="draft",
                            )
                            body_wikilinks = extract_wikilinks(new_body)
                            body_tags = extract_tags(new_body)
                            merged_tags = tuple(sorted(set(meta.tags) | set(body_tags)))
                            new_note = Note(
                                path=rel_path,
                                metadata=meta,
                                body=new_body,
                                wikilinks=body_wikilinks,
                                tags=merged_tags,
                            )
                            mem._vault.write(new_note, force=force)
                        # v0.6.17: rebuild em background (não bloqueia a UI);
                        # leitura seguinte serve índice stale até convergir
                        _kick_memory_rebuild()
                        try:
                            _tel_event("memory_note_saved", {})
                        except Exception:
                            pass
                        self._json(200, {
                            "ok": True,
                            "action": "save",
                            "path": rel_path,
                            "message": f"Nota '{rel_path}' salva.",
                        })
                        return

                    if action == "create":
                        rel_path = (body.get("path", "") or "").strip()
                        if not rel_path:
                            self._json(400, {"ok": False, "error": "path obrigatório."})
                            return
                        if mem._vault.exists(rel_path):
                            self._json(409, {
                                "ok": False,
                                "error": f"Já existe: {rel_path}. Use action=save.",
                            })
                            return
                        title = (body.get("title", "") or "").strip() or Path(rel_path).stem
                        template = (body.get("template", "inbox") or "inbox").strip()
                        tags_in = body.get("tags", []) or []
                        tags = tuple(t.strip() for t in tags_in if t and str(t).strip())
                        context = dict(body.get("context", {}) or {})
                        context["title"] = title
                        note = mem.create_note(
                            rel_path, title=title, template=template,
                            tags=tags, context=context,
                        )
                        if note is None:
                            self._json(500, {"ok": False, "error": "Falha ao criar nota."})
                            return
                        # v0.6.17: rebuild em background (não bloqueia a UI)
                        _kick_memory_rebuild()
                        try:
                            _tel_event("memory_note_created", {})
                        except Exception:
                            pass
                        self._json(200, {
                            "ok": True,
                            "action": "create",
                            "path": note.path,
                            "title": note.metadata.title,
                            "message": f"Nota '{note.path}' criada a partir do template '{template}'.",
                        })
                        return

                    if action == "delete":
                        rel_path = (body.get("path", "") or "").strip()
                        if not rel_path:
                            self._json(400, {"ok": False, "error": "path obrigatório."})
                            return
                        force = bool(body.get("force", False))
                        try:
                            deleted = mem._vault.delete(rel_path, force=force)
                        except PermissionError as e:
                            self._json(403, {
                                "ok": False, "error": str(e),
                                "hint": "Nota humana: envie force=true para deletar.",
                            })
                            return
                        if not deleted:
                            self._json(404, {
                                "ok": False, "error": f"Nota não encontrada: {rel_path}",
                            })
                            return
                        if mem._searcher is not None:
                            mem._searcher.invalidate()
                        # v0.6.17: rebuild em background (não bloqueia a UI)
                        _kick_memory_rebuild()
                        try:
                            _tel_event("memory_note_deleted", {})
                        except Exception:
                            pass
                        self._json(200, {
                            "ok": True,
                            "action": "delete",
                            "path": rel_path,
                            "message": f"Nota '{rel_path}' movida para .trash/.",
                        })
                        return

                    self._json(400, {"ok": False, "error": f"action inválida: {action}"})
                    return
                except PermissionError as e:
                    self._json(403, {"ok": False, "error": str(e)})
                except FileNotFoundError as e:
                    self._json(404, {"ok": False, "error": str(e)})
                except Exception as e:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": f"Erro: {e!r}"})
                return

            if p == "/api/apikey":
                provider = body.get("provider", "").strip()
                action   = body.get("action", "save").strip().lower()
                env_var  = body.get("env", "").strip()
                key      = body.get("apikey", "").strip()

                if action == "delete":
                    if not provider:
                        self._json(400, {"error": "provider obrigatório para exclusão."})
                        return
                    existing = load_encrypted_keys(DRIVE_BACKUP_DIR)
                    # Verifica existência ANTES de dar pop, para não rejeitar chaves
                    # corrompidas/vazias (valor "" é falsy mas a entrada existe).
                    provider_exists = provider in existing
                    env_exists = f"_env_{provider}" in existing
                    if not provider_exists and not env_exists:
                        self._json(404, {"error": f"Chave não encontrada: {provider}"})
                        return
                    removed_key = existing.pop(provider, None)
                    removed_env = existing.pop(f"_env_{provider}", None)
                    if not save_encrypted_keys(DRIVE_BACKUP_DIR, existing):
                        self._json(500, {"error": "Falha ao salvar chaves após exclusão."})
                        return
                    # Remove do env atual (se houver)
                    env_name = removed_env or env_var
                    if env_name:
                        os.environ.pop(env_name, None)
                        _env.pop(env_name, None)
                    # Remove do ~/.bashrc
                    bashrc = os.path.expanduser("~/.bashrc")
                    try:
                        marker = f"# opencode-key-{provider}"
                        if os.path.exists(bashrc):
                            with open(bashrc, "r") as f:
                                lines = f.readlines()
                            lines = [l for l in lines if marker not in l]
                            with open(bashrc, "w") as f:
                                f.writelines(lines)
                    except Exception:
                        pass
                    try:
                        _tel_event("provider_deleted", {"provider": provider[:24]})
                    except Exception:
                        pass
                    _apply_opencode_env_change_async()
                    self._json(200, {"ok": True, "deleted": provider})
                    return

                # Ação padrão: salvar/atualizar chave
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
                try:
                    _tel_event("provider_saved", {"provider": provider[:24]})
                except Exception:
                    pass
                _apply_opencode_env_change_async()
                self._json(200, {"ok": True})
                return
            
            if p == "/api/apikey/apply":
                applied = load_keys_from_drive(DRIVE_BACKUP_DIR, _env, write_bashrc=False)
                self._json(200, {"ok": True, "applied": applied}) if applied else \
                    self._json(200, {"ok": False, "reason": "no keys stored"})
                return
            
            if p == "/api/run_terminal":
                raw_cmd = (body.get("command") or body.get("cmd") or "").strip()
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
                
                # v0.6.5: encerra a árvore do terminal de forma cirúrgica
                # (antes: pkill -9 -f opencode — matava qualquer processo com
                # 'opencode' na cmdline e deixava porta morta sem verificação)
                _stop_terminal()

                # Ajuste 14/10/2026 (v0.6.21): o fallback deste comando é o
                # próprio opencode (`; opencode; exec bash`) — sem a garantia,
                # ele poderia iniciar com `build` se o config tivesse mudado.
                _ensure_ufvai_agent_before_spawn("api/run_terminal")

                # Build bash -c command string de forma segura
                # O comando do usuario (cmd) ja foi sanitizado acima.
                # O suffixo "; exec bash" e adicionado pelo codigo (nao pelo usuario),
                # entao nao precisa de segunda sanitizacao — isso causaria falso positivo
                # pois sanitize_command bloqueia ";" mesmo em comandos validos.
                if no_fallback:
                    bash_cmd = f'cd "{_workspace_dir()}" && {cmd}; exec bash'
                else:
                    bash_cmd = f'cd "{_workspace_dir()}" && {cmd}; {_opencode_bin}; exec bash'

                # v0.4.2.5: usar --index com touch handlers se disponível
                base_ttyd = ["ttyd", "--writable", "-p", str(TERMINAL_PORT),
                     *_ttyd_shell_argv(bash_cmd)]
                ttyd_cmd = _build_ttyd_args(base_ttyd, _env)

                # v0.6.5: spawn rastreado + ESPERAR a porta abrir antes de
                # responder (antes respondia ok na hora; o reload do frontend
                # caía numa porta morta → ERR_CONNECTION_REFUSED).
                ready = _ensure_terminal_ready(
                    lambda: _spawn_ttyd(ttyd_cmd, _env), timeout_s=18.0)
                if not ready:
                    self._json(503, {
                        "ok": False,
                        "error": ("Terminal não respondeu após reinício "
                                  "(veja logs/ttyd.log). Tente novamente."),
                    })
                    return
                # v0.7.5: registra a sessão aberta por `opencode -s <id>` para
                # que trocar idioma/chave depois não abra outra conversa.
                try:
                    _sess = re.search(r"(?:^|\s)(?:-s|--session)\s+[\"']?(ses_[A-Za-z0-9]+)", cmd)
                    if _sess:
                        _remember_ttyd_session(_sess.group(1))
                    else:
                        _remember_ttyd_session(None)
                        reset_preflight_cache()
                except Exception:
                    pass
                self._json(200, {"ok": True})
                return
            
            if p == "/api/backup":
                os.makedirs(DRIVE_BACKUP_DIR, exist_ok=True)

                session_id = str(body.get("session_id", "") or "").strip()
                ts = time.strftime("%H-%M-%S_%d-%m-%Y")

                # ── Descoberta da sessao (v0.6.25) ──────────────────────
                # A busca anterior (`session list --format json`) e escopada
                # por projeto/CWD e voltava vazia — o "Salvar backup" falhava
                # com "Nenhuma sessao encontrada". Agora consulta o SERVIDOR.
                sessions = []
                try:
                    sessions = _session_restore.list_sessions(_opencode_bin or "opencode", env=_env)
                except Exception as exc:
                    logger.warning("Falha ao listar sessoes para backup: %s", exc)

                if session_id and not any(s.get("id") == session_id for s in sessions):
                    logger.info(
                        "Backup: sessao %s informada nao esta na lista do servidor; "
                        "tentando o export direto.", session_id,
                    )

                if not session_id and sessions:
                    # a mais recente (a lista vem do servidor, ja ordenada)
                    session_id = str(sessions[0].get("id") or "")

                if not session_id:
                    self._json(400, {
                        "error": (
                            "Nenhuma sessao encontrada para exportar. "
                            "O motor nao respondeu a listagem de sessoes."
                        )
                    })
                    return

                sid_safe = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id))[:12] or "sess"
                fname = f"backup_{sid_safe}_{ts}.json"
                # ── Etapa 1: exportar para /tmp/ (SSD local, sem FUSE) ─────────
                tmp_path = os.path.join("/tmp", fname)

                # v0.6.25: export DIRETO PARA ARQUIVO (sem pipe) + retentativa.
                # Capturar a saida do motor por pipe truncava o payload em
                # blocos de 64 KB (medido: 5 de 6 exports saiam com JSON
                # invalido — 196608/262144/393216 bytes) e o backup no Drive
                # ficava corrompido. Escrito direto no arquivo, o export sai
                # integro; a retentativa cobre o resto.
                try:
                    export_text, export_meta = _session_restore.export_session_verified(
                        _opencode_bin or "opencode", session_id, env=_env, attempts=3,
                        out_path=tmp_path,
                    )
                except _session_restore.SessionError as exc:
                    self._json(500, {
                        "error": (
                            f"Falha ao exportar a sessao apos 3 tentativas: {exc}. "
                            f"Nenhum arquivo foi gravado no Drive."
                        )
                    })
                    return

                if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        f.write(export_text)
                tmp_size = os.path.getsize(tmp_path)

                # ── Etapa 2: gravar no Drive de forma ATOMICA e verificada ──
                # Causa raiz dos backups quebrados: o Google Drive (FUSE)
                # trunca a escrita em limites de buffer interno (64KB/256KB/
                # 512KB) — o `stat` reporta o tamanho alvo, mas o conteudo
                # esta truncado. A correcao e gravar em arquivo temporario,
                # validar lendo de volta e so entao renomear (os.replace).
                outpath = os.path.join(DRIVE_BACKUP_DIR, fname)

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

                try:
                    write_info = _session_restore.write_backup_atomic(
                        tmp_path, outpath, attempts=3,
                    )
                except _session_restore.SessionError as exc:
                    self._json(500, {
                        "error": (
                            f"Exportado e validado em /tmp/ ({tmp_size} bytes, JSON valido), "
                            f"mas falhou ao gravar no Drive apos 3 tentativas. "
                            f"Causa provavel: truncamento FUSE em chunk de buffer. "
                            f"Ultimo erro: {exc}. "
                            f"Nenhum backup anterior foi sobrescrito. "
                            f"Arquivo temporario valido preservado em: {tmp_path}"
                        )
                    })
                    return
                finally:
                    if lock_ok and lock_fd:
                        try:
                            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                            lock_fd.close()
                        except Exception:
                            pass

                # ── Etapa 3: resposta ────────────────────────────────────────
                _invalidate_backups_cache()  # novo backup no Drive
                try:
                    _tel_event("backup_created", {})
                except Exception:
                    pass
                self._json(200, {
                    "ok": True,
                    "file": fname,
                    "session_id": session_id,
                    "path": outpath,
                    "size_bytes": write_info.get("size_bytes", tmp_size),
                    "tmp_path": tmp_path,
                    "validated": True,
                    "atomic": True,
                    "messages": export_meta.get("messages", 0),
                    "format": export_meta.get("format", "v2"),
                    "attempts": write_info.get("attempts", 1),
                    "title": export_meta.get("title", ""),
                })
                return
            
            if p == "/api/restore":
                fname_raw = str(body.get("file", "") or "").strip()
                # v0.7.0: aceita "autosave/autosave_1.json" (autosaves) ou
                # "backup_ses_*.json" (backups de sessao). Qualquer outro
                # .json da pasta (keys_store.json, keys.json, consentimentos)
                # e REJEITADO: nao e backup e nao pode ser restaurado.
                fpath, err = _resolve_restore_path(
                    fname_raw, DRIVE_BACKUP_DIR, AUTOSAVE_DIR)
                if fpath is None:
                    status = 404 if err.startswith("Arquivo não encontrado") else 400
                    self._json(status, {"error": err})
                    return
                fname = os.path.basename(fpath)

                # ── v0.6.25: restauracao com conversao e ids renovados ──
                # O import do motor v2 (a) rejeita o esquema legado v1 com
                # HTTP 400 e (b) devolve HTTP 500 quando os ids de mensagem
                # ja existem na base (caso comum: restaurar um backup cuja
                # sessao de origem continua viva). O modulo session_restore
                # converte o payload legado, remove o que o import nao
                # aceita e renova os ids antes de importar.
                file_size = os.path.getsize(fpath)
                if file_size < 100:
                    self._json(400, {
                        "error": f"Arquivo de backup corrompido ou vazio ({file_size} bytes)."
                    })
                    return

                # 1. Copiar para /tmp/ primeiro (Drive FUSE e lento para leitura grande)
                tmp_restore = os.path.join("/tmp", f"restore_{fname}")
                try:
                    shutil.copy2(fpath, tmp_restore)
                except Exception as e:
                    self._json(500, {"error": f"Falha ao copiar backup para /tmp/: {e}"})
                    return

                # 2. Preparar o payload (validacao + conversao v1->v2 + ids novos)
                #
                # Correcao 23/10/2026 (sem bump): o id importado precisa
                # nascer no formato NATIVO do motor (`ses_` + 12 hex + 14
                # base62). O gateway do free tier do OpenCode valida o
                # cabecalho `x-opencode-session` (issue #49433): um id fora do
                # padrao recebe HTTP 403 "OpenCode's free tier can only be
                # used from within OpenCode" — e a sessao restaurada nao anda
                # com modelos gratuitos (uma sessao NOVA funciona, porque o
                # proprio motor cria o id). Antes, a retomada gerava
                # `ses_` + 16 hex e quebrava TODA sessao restaurada.
                #
                # Ajuste 23/10/2026 (sem bump) — VELOCIDADE: as amostras de
                # id vem de cache em processo (antes: um `opencode session
                # list` a cada restore).
                _t0 = time.time()
                _timings: dict = {}
                try:
                    _id_samples = _session_restore.native_id_samples_cached(
                        _opencode_bin or "opencode", env=_env)
                except Exception as _exc:  # best-effort: sem amostras, padrao oficial
                    logger.warning("Restore: sem amostras de id nativas (%s)", _exc)
                    _id_samples = []
                try:
                    payload, src_format = _session_restore.prepare_import_payload(
                        tmp_restore,
                        project_id=str(body.get("project_id", "") or ""),
                        fallback_directory=str(body.get("directory", "") or ""),
                        id_samples=_id_samples,
                    )
                except _session_restore.SessionError as exc:
                    self._json(400, {"error": str(exc)})
                    return
                _timings["prepare_ms"] = int((time.time() - _t0) * 1000)

                # 2.0 Ajuste 23/10/2026 (sem bump) — PLANEJAR ANTES DE IMPORTAR.
                # Antes: importava o payload INTEIRO (os autosaves reais tem
                # 9,5 MB / ~2,6 milhoes de tokens), esperava a compactacao
                # manual (ate 120 s) e, se ela falhasse, importava de novo o
                # aparado. Agora:
                #   - cabe no orcamento ......... importa direto;
                #   - ate 25% acima ............. importa e compacta (rapido);
                #   - muito acima ............... APARA e importa UMA vez.
                _t_plan = time.time()
                try:
                    payload, plan = _session_restore.prepare_payload_for_restore(
                        payload, _opencode_bin or "opencode", env=_env)
                except Exception as _plan_err:  # fail-open: importa inteiro
                    logger.warning("Restore: plano de contexto falhou: %s", _plan_err)
                    plan = {"action": "none"}
                _timings["plan_ms"] = int((time.time() - _t_plan) * 1000)
                fit_info: dict = dict(plan)
                if plan.get("action") == "trimmed":
                    logger.info(
                        "Restore: payload aparado ANTES do import "
                        "(%s→%s tokens, %s mensagens descartadas, orcamento %s)",
                        plan.get("tokens_before"), plan.get("tokens_after"),
                        plan.get("messages_dropped"), plan.get("budget"),
                    )

                # 3. Importar (ids renovados evitam a colisao que dava HTTP 500)
                _t_imp = time.time()
                try:
                    session_id = _session_restore.import_session(
                        _opencode_bin or "opencode", payload, env=_env, timeout=180,
                    )
                except _session_restore.SessionError as exc:
                    self._json(500, {
                        "error": (
                            f"Falha ao importar a sessao: {exc}. "
                            f"O backup e valido e esta preservado em: {tmp_restore}"
                        )
                    })
                    return
                _timings["import_ms"] = int((time.time() - _t_imp) * 1000)

                parse_error = ""
                import_stdout = f"Imported session: {session_id}"
                # Correcao 23/10/2026: se o id importado nao seguir o formato
                # nativo, o free tier respondera 403 na 1a mensagem. Nao
                # bloqueia (o backup ja foi importado), mas deixa o rastro.
                try:
                    _native_shape = _session_restore.id_shape(_id_samples, "ses_")
                    if (_native_shape and session_id
                            and (len(session_id) - len("ses_")) != _native_shape[0]):
                        logger.warning(
                            "Sessao restaurada com id fora do formato nativo "
                            "(%s, %d chars; nativo=%d) — modelos gratuitos "
                            "podem falhar com FreeTierError.",
                            session_id, len(session_id) - len("ses_"),
                            _native_shape[0],
                        )
                except Exception:
                    pass

                # 2.1 Correcao 23/10/2026 (sem bump): AJUSTAR AO CONTEXTO.
                # Os autosaves reais tem ~300 mil tokens; os modelos free do
                # OpenCode Zen tem 200 mil de contexto. Ao abrir a sessao
                # importada o motor ve o contexto estourado e dispara a
                # compactacao AUTOMATICA — caminho que o gateway do free
                # tier recusa ("OpenCode's free tier can only be used from
                # within OpenCode"). Era o `✗ Compaction` de TODA sessao
                # restaurada, enquanto uma sessao nova funcionava.
                # Compactacao MANUAL (nao bloqueada) ou, em ultimo caso,
                # reimportar aparado.
                if plan.get("action") == "compact":
                    _t_fit = time.time()
                    try:
                        if _session_restore.compact_session(
                                _opencode_bin or "opencode", session_id, env=_env):
                            fit_info["action"] = "compacted"
                            fit_info["tokens_after"] = 0  # o motor nao informa
                        else:
                            # Compactacao nao terminou em 30 s: aparar e
                            # reimportar e' mais rapido do que esperar.
                            trimmed, dropped = _session_restore.trim_payload(
                                payload, int(fit_info.get("budget") or 0))
                            new_id = _session_restore.import_session(
                                _opencode_bin or "opencode", trimmed, env=_env,
                                timeout=180)
                            _session_restore.delete_session(
                                _opencode_bin or "opencode", session_id, env=_env)
                            fit_info.update({
                                "session_id": new_id,
                                "action": "trimmed",
                                "messages_dropped": dropped,
                                "tokens_after": _session_restore.estimate_tokens(trimmed),
                            })
                            session_id = new_id
                    except Exception as fit_err:  # fail-open: o import ja esta valido
                        logger.warning("Restore: ajuste ao contexto falhou: %s", fit_err)
                        fit_info["action"] = "error"
                        fit_info["error"] = str(fit_err)[:200]
                    _timings["fit_ms"] = int((time.time() - _t_fit) * 1000)

                # 3. v0.5.1.6 — REINICIAR ttyd com `opencode -s <session_id>`
                # Bug antigo: importava a sessão mas o ttyd continuava com --prompt,
                # então location.reload() mostrava a conversa ATUAL, não a importada.
                # v0.6.5: kill por árvore + espera a porta abrir + status real
                # (antes: respondia ok sem verificar → ERR_CONNECTION_REFUSED).
                ttyd_restarted = False
                ttyd_restart_error = ""
                if session_id:
                    _t_ttyd = time.time()
                    try:
                        _stop_terminal()

                        # Ajuste 14/10/2026 (v0.6.21): garantia antes do
                        # reinício pós-import. A V2 não troca o agente de uma
                        # sessão já gravada (doc agents/"Selection"); sessões
                        # exportadas do UFVAI já gravam UFVAI — e novas
                        # sessões, abertas depois, seguem com o default.
                        _ensure_ufvai_agent_before_spawn("api/session-import")

                        def _spawn():
                            opencode_bin, env = resolve_opencode()
                            _pd = _workspace_dir()
                            bash_cmd = f'cd "{_pd}" && {opencode_bin} -s "{session_id}" ; exec bash'
                            # v0.6.2: --writable restaurado (regressão v0.6.0 deixava o terminal read-only)
                            base_args = ["ttyd", "-p", str(TERMINAL_PORT), "--writable",
                                         *_ttyd_shell_argv(bash_cmd)]
                            _spawn_ttyd(_build_ttyd_args(base_args, env), env)

                        ttyd_restarted = _ensure_terminal_ready(_spawn, timeout_s=18.0)
                        if ttyd_restarted:
                            # v0.7.5: o terminal agora exibe a sessão importada.
                            # Fixa-a para que um reinício posterior (idioma/chave)
                            # reabra ESTA conversa, não a anterior.
                            _remember_ttyd_session(session_id)
                            print(f"🔄 ttyd reiniciado com sessão {session_id}")
                        else:
                            ttyd_restart_error = (
                                f"Porta {TERMINAL_PORT} não respondeu após reinício "
                                "(veja logs/ttyd.log).")
                            logger.error(ttyd_restart_error)
                    except Exception as restart_err:
                        ttyd_restart_error = str(restart_err)[:200]
                        logger.error("Falha ao reiniciar ttyd com sessão %s: %s", session_id, restart_err)
                    _timings["ttyd_ms"] = int((time.time() - _t_ttyd) * 1000)

                # 4. Respond
                try:
                    _tel_event("session_restored", {})
                except Exception:
                    pass
                _timings["total_ms"] = int((time.time() - _t0) * 1000)
                try:
                    logger.info(
                        "Restore concluido em %sms (%s) — %s",
                        _timings["total_ms"], fname, _timings,
                    )
                except Exception:
                    pass
                self._json(200, {
                    "ok": True,
                    "file": fname,
                    "session_id": session_id,
                    "fit": fit_info,
                    "parse_error": parse_error,
                    "import_stdout": import_stdout,
                    "source_format": src_format,
                    "ttyd_restarted": ttyd_restarted,
                    "ttyd_restart_error": ttyd_restart_error,
                    "timings": _timings,
                    "elapsed_ms": _timings["total_ms"],
                    "message": (
                        "Sessão importada e ttyd reiniciado com opencode -s "
                        + session_id if ttyd_restarted else
                        "Sessão importada, mas ttyd NÃO foi reiniciado. "
                        "Faça reload manual após o import."
                    ),
                })
                return
            
            if p == "/api/backup/delete":
                # v0.7.1 — APAGAR um backup/autosave do Drive (menu
                # "Restaurar"). Exige confirmacao explicita do usuario
                # ("confirm": true); o caminho passa pela mesma validacao
                # do /api/restore (so backup_*.json e autosave_<n>.json,
                # sem escape de diretorio).
                fname_raw = str(body.get("file", "") or "").strip()
                if not bool(body.get("confirm")):
                    self._json(400, {
                        "error": "Confirmação obrigatória para apagar o backup."
                    })
                    return
                fpath, err = _resolve_restore_path(
                    fname_raw, DRIVE_BACKUP_DIR, AUTOSAVE_DIR)
                if fpath is None:
                    status = 404 if err.startswith("Arquivo não encontrado") else 400
                    self._json(status, {"error": err})
                    return
                fname = os.path.basename(fpath)
                try:
                    os.remove(fpath)
                except FileNotFoundError:
                    self._json(404, {"error": f"Arquivo não encontrado: {fname}"})
                    return
                except OSError as exc:
                    self._json(500, {
                        "error": f"Não foi possível apagar o arquivo: {exc}"[:200]
                    })
                    return
                _invalidate_backups_cache()   # a lista do menu muda
                try:
                    _tel_event("backup_deleted", {})
                except Exception:
                    pass
                self._json(200, {"ok": True, "file": fname,
                                 "deleted_at": time.time()})
                return

            if p == "/api/autosave":
                # v0.7.0: autosave da sessao a cada 3 minutos (chave
                # liga/desliga na interface). Mantem os 3 ULTIMOS no Drive:
                # o mais recente e `autosave_1.json`; se ele estiver
                # corrompido (truncamento FUSE), o fallback assume.
                #
                # CORRECAO v0.7.0 (21/10): este bloco referenciava uma
                # variavel `method` que NUNCA foi definida no do_POST ->
                # NameError em TODA gravacao (a interface mostrava apenas
                # "falha na conexao" e nenhum arquivo era gravado). O
                # listing (GET) foi movido para o do_GET e aqui fica so
                # a gravacao (POST).
                os.makedirs(AUTOSAVE_DIR, exist_ok=True)
                session_id = str(body.get("session_id", "") or "").strip()
                if not session_id:
                    try:
                        sessions = _session_restore.list_sessions(
                            _opencode_bin or "opencode", env=_env,
                        )
                    except Exception:
                        sessions = []
                    # v0.7.3: prioriza a sessao do TERMINAL (o ttyd roda
                    # `opencode -s <id>`) — e' a conversa que o usuario
                    # esta usando; so depois a mais recentemente
                    # atualizada do motor.
                    session_id = _ttyd_session_id()
                    if not session_id and sessions:
                        session_id = _active_session_id(sessions)
                if not session_id:
                    self._json(400, {
                        "error": "Nenhuma sessao ativa para salvar automaticamente."
                    })
                    return
                try:
                    info = _session_restore.save_autosave(
                        _opencode_bin or "opencode", session_id, AUTOSAVE_DIR, env=_env,
                    )
                except _session_restore.SessionError as exc:
                    logger.warning("Autosave falhou: %s", exc)
                    self._json(500, {"error": str(exc)[:300]})
                    return
                except Exception as exc:
                    # v0.7.0: sem esta rede de seguranca, uma excecao
                    # inesperada fechava a conexao sem resposta ("Empty
                    # reply from server") e a interface mostrava apenas
                    # "falha na conexao" — sem dizer o que aconteceu.
                    logger.exception("Autosave falhou com excecao inesperada")
                    self._json(500, {
                        "error": f"Falha inesperada no autosave: {type(exc).__name__}: {exc}"[:300],
                        "traceback": traceback.format_exc()[-800:],
                    })
                    return
                # v0.7.4: SALVA TODAS AS CONVERSAS — com varias sessoes
                # abertas, o autosave antigo guardava SO a do terminal (a
                # conversa "que está ativa"). Agora cada conversa viva que
                # tenha conteudo novo recebe o seu proprio arquivo em
                # `backups/autosave/sessions/<id>.json`, e todas entram na
                # lista do modal "Restaurar".
                per_session: dict = {"ok": True, "saved": [], "skipped": [],
                                     "failed": [], "total": 0, "scope": "active"}
                # v0.7.4: por PADRAO salva SO a sessao ativa (e so quando ela
                # muda). O botao "Todas as conversas" no rodape liga o modo
                # completo (um arquivo por sessao).
                _want_all = bool(body.get("all_sessions") or body.get("all"))
                if _want_all:
                    try:
                        _sessions_all = _session_restore.list_sessions(
                            _opencode_bin or "opencode", env=_env,
                        )
                        per_session = _session_restore.save_all_sessions(
                            _opencode_bin or "opencode", _sessions_all,
                            AUTOSAVE_DIR, env=_env,
                            project_dir=_project_dir(),
                        )
                        per_session["scope"] = "all"
                    except Exception as exc:
                        logger.warning("Autosave por sessao falhou: %s", exc)
                        per_session = {"ok": False, "error": str(exc)[:200]}
                try:
                    _tel_event("autosave_created", {})
                except Exception:
                    pass
                _invalidate_backups_cache()  # autosave novo no Drive
                self._json(200, {"ok": True, **info, "sessions_saved": per_session})
                return

            if p == "/api/theme":
                # Persiste escolha de tema (escuro/claro) — v0.6.20 grava em
                # tui.json (OpenCode V1) E cli.json (OpenCode V2).
                theme_name = body.get("theme", "").strip()
                # v0.6.0: aliases de marca mapeiam aos temas internos existentes
                _alias = {"ufvai": "pesquisai", "ufvai-light": "pesquisai-light"}
                theme_name = _alias.get(theme_name, theme_name)
                if theme_name not in ("pesquisai", "pesquisai-light"):
                    self._json(400, {"error": "Tema inválido. Use 'pesquisai' ou 'pesquisai-light'."})
                    return
                try:
                    _write_theme(theme_name)
                    try:
                        _tel_event("theme_changed", {"theme": theme_name})
                    except Exception:
                        pass
                    self._json(200, {"ok": True, "theme": theme_name})
                except Exception as e:
                    self._json(500, {"error": str(e)})
                return

            if p == "/api/lang":
                # v0.4.2.2: persiste idioma e reinicia ttyd com saudação
                # no novo idioma ao invés de --prompt "oi" genérico.
                lang_in = (body.get("lang", "") or "").strip()
                if not lang_in:
                    self._json(400, {"error": "lang obrigatório (pt_BR/en_US/es_ES/fr_FR/zh_CN)"})
                    return
                short = lang_in.split("_")[0].lower() if "_" in lang_in else lang_in.lower()
                full_lang = _LANG_MAP.get(short, lang_in if lang_in in _LANG_MAP.values() else "pt_BR")
                changed = (full_lang != _current_lang)

                # v0.7.5 (correção 23/10/2026 — SEM bump): ``restart=False``
                # é a ADOÇÃO SILENCIOSA do idioma do navegador. O backend sobe
                # antes do navegador e detecta o idioma pelo locale do
                # servidor (no Colab, en_US); antes, a divergência fazia o
                # frontend chamar este endpoint e o ttyd era MORTO e recriado
                # (2ª sessão) + location.reload() — perdendo a conversa e,
                # às vezes, a pergunta de retomada. Aqui só persistimos.
                _restart = body.get("restart", True)
                if isinstance(_restart, str):
                    _restart = _restart.strip().lower() not in ("0", "false", "off", "no", "")
                if not _restart:
                    _source = str(body.get("source") or "browser").strip().lower()
                    if _source not in ("user", "browser", "auto"):
                        _source = "browser"
                    # v0.7.5+ (sem bump): dica do NAVEGADOR não sobrescreve
                    # escolha EXPLÍCITA do usuário (lang_source=user).
                    _prefs_now = _read_prefs() or {}
                    if (_source == "browser"
                            and str(_prefs_now.get("lang_source") or "") == "user"
                            and _prefs_now.get("lang")):
                        self._json(200, {
                            "ok": True, "lang": _current_lang, "changed": False,
                            "restarted": False, "ignored": True,
                            "greeting_seeded": False,
                        })
                        return
                    _set_lang_only(full_lang, source=_source)
                    seeded = _consume_greeting(_current_ttyd_session, full_lang)
                    self._json(200, {
                        "ok": True,
                        "lang": full_lang,
                        "changed": changed,
                        "restarted": False,
                        "greeting_seeded": seeded,
                    })
                    return

                # Nada mudou e o terminal está vivo: resposta imediata, sem
                # reiniciar (antes, um POST redundante criava outra sessão).
                if not changed and _wait_port_open(TERMINAL_PORT, timeout_s=0.3):
                    seeded = _consume_greeting(_current_ttyd_session, full_lang)
                    self._json(200, {
                        "ok": True,
                        "lang": full_lang,
                        "changed": False,
                        "restarted": False,
                        "greeting_seeded": seeded,
                    })
                    return

                ok = restart_ttyd_with_lang(full_lang)
                if ok:
                    try:
                        _tel_event("lang_changed", {"lang": full_lang})
                    except Exception:
                        pass
                    # v0.7.5+ (sem bump): trocar o idioma INJETA a mensagem
                    # padrão no idioma novo — antes a conversa continuava no
                    # idioma anterior e o usuário tinha de pedir a troca.
                    # Sessão recém-criada: a pendência é consumida aqui; sessão
                    # com histórico: injeta agora (uma única vez).
                    seeded = _consume_greeting(_current_ttyd_session, full_lang)
                    if not seeded and _current_ttyd_session:
                        _seed_greeting_async(_current_ttyd_session, full_lang, delay=1.0)
                        seeded = True
                    self._json(200, {
                        "ok": True,
                        "lang": full_lang,
                        "changed": changed,
                        "restarted": True,
                        "greeting": get_greeting(full_lang),
                        "greeting_seeded": seeded,
                        "message": f"ttyd reiniciado com saudação em {full_lang}",
                    })
                else:
                    self._json(500, {
                        "ok": False,
                        "error": "Falha ao reiniciar ttyd com o novo idioma.",
                    })
                return

            if p == "/api/admin/telemetry":
                # v0.6.4: salva credenciais GA4 configuradas pelo painel Admin da UI.
                # v0.6.7: também grava contact_endpoint (canal HTTPS que recebe o
                # e-mail de contato opt-in — ex.: Apps Script → Planilha Google).
                # Grava em ~/.config/ufvai_telemetry.json (chmod 600) e aplica no
                # processo imediatamente. O secret NUNCA é devolvido pela API.
                ok, msg = _tel_save_admin(
                    str(body.get("measurement_id", "")),
                    str(body.get("api_secret", "")),
                    str(body.get("contact_endpoint", "")) if "contact_endpoint" in body else None,
                )
                try:
                    if ok:
                        _tel_event("admin_telemetry_configured", {})
                except Exception:
                    pass
                self._json(200 if ok else 400, {"ok": ok, "message": msg,
                                                "state": _tel_masked_state()})
                return

            # v0.6.9: heartbeat de usuário ativo — chamado pela tela
            # "Bem-vindo de volta" a cada reabertura (e-mail + hora + flag
            # "usuario_ativo" → planilha de contatos do desenvolvedor).
            # v0.6.10: encaminha IP para a planilha.
            # v0.6.14: aceita IP enviado pelo cliente (ipify) e garante
            # que TODO acesso de usuário já registrado seja logado.
            # No primeiro acesso (sem perfil) a UI NÃO chama este endpoint.
            if p == "/api/access":
                try:
                    # v0.6.14: IP pode vir do body (cliente ipify) — preferido quando público
                    _body_ip = str(body.get("ip") or body.get("client_ip") or body.get("clientIp") or "").strip() if isinstance(body, dict) else ""
                    _cip = _get_client_ip(self, client_ip=_body_ip)
                    _tel_notify_active_user(_cip)
                except Exception:
                    pass
                self._json(200, {"ok": True})
                return

            if p == "/api/consent":
                # v0.6.0: grava aceite dos Termos + opt-in de telemetria
                # v0.6.6: e-mail de contato OPCIONAL (LGPD art. 7º I)
                # v0.6.9: (a) telemetria ATIVA POR PADRÃO — opt-out (art. 7º IX,
                #            sem cookie, oposição art. 18 §2º);
                #         (b) E-MAIL OBRIGATÓRIO para aceitar (art. 7º V —
                #            execução do serviço; eliminação art. 18 mantida);
                #         (c) perfil persistente em backups/ufvai_consentimento.json
                #            (sobrevive à sessão → pré-preenche a tela nas reaberturas).
                # v0.6.10: (d) NOME obrigatório ao lado do e-mail; (e) IP capturado.
                accepted = bool(body.get("accepted", False))
                analytics = bool(body.get("analytics", True))  # v0.6.9: opt-out (default ativo)
                terms_version = str(body.get("terms_version") or "6").strip()
                contact_msg = ""
                cemail = str(body.get("contact_email") or body.get("email") or "").strip()
                cname = str(body.get("contact_name") or body.get("name") or body.get("nome") or "").strip()
                # v0.6.14: IP pode vir do body (cliente ipify) — preferido quando público
                _body_ip2 = str(body.get("ip") or body.get("client_ip") or body.get("clientIp") or "").strip()
                cip = _get_client_ip(self, client_ip=_body_ip2)
                if accepted and not cemail:
                    return self._json(400, {
                        "ok": False,
                        "error": "E-mail obrigatório: informe um e-mail válido para ativar o UFVAI.",
                    })
                if accepted and not cname:
                    return self._json(400, {
                        "ok": False,
                        "error": "Nome obrigatório: informe seu nome para ativar o UFVAI.",
                    })
                if cemail or cname:
                    # valida nome quando vier
                    if cname and len(cname) < 2:
                        return self._json(400, {"ok": False, "error": "Nome inválido — use 2 a 100 letras."})
                    _ok, contact_msg = _tel_save_contact(cemail, cname, cip)
                    if not _ok:
                        return self._json(400, {"ok": False, "error": contact_msg})
                elif "contact_email" in body or "contact_name" in body:
                    _tel_clear_contact()  # campo esvaziado → eliminação (art. 18)
                cpath = os.path.expanduser("~/.config/ufvai_consent.json")
                try:
                    os.makedirs(os.path.dirname(cpath), exist_ok=True)
                    json.dump({
                        "accepted": accepted,
                        "analytics": analytics,
                        "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "version": VERSION,
                    }, open(cpath, "w", encoding="utf-8"))
                except Exception:
                    pass
                # v0.6.9: perfil persistente (Drive/offline) p/ pré-preenchimento
                # v0.6.10: inclui nome e ip (LGPD art. 7º V)
                try:
                    bpath = _consent_backup_file()
                    if bpath and accepted and cemail:
                        json.dump({
                            "email": cemail.lower(),
                            "email_sha256": hashlib.sha256(cemail.lower().encode("utf-8")).hexdigest(),
                            "name": cname.strip(),
                            "nome": cname.strip(),
                            "ip": cip,
                            "analytics": analytics,
                            "accepted": True,
                            "terms_version": terms_version,
                            "app_version": VERSION,
                            "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "purpose": "ativação/contato UFVAI (LGPD art. 7º V) · telemetria opt-out (art. 7º IX)",
                        }, open(bpath, "w", encoding="utf-8"))
                except Exception:
                    pass
                try:
                    _tel_set_consent(analytics)
                    if accepted:
                        _tel_event("terms_accepted", {"analytics": analytics})
                except Exception:
                    pass
                resp = {"ok": True, "accepted": accepted, "analytics": analytics}
                if contact_msg:
                    resp["contact_message"] = contact_msg
                self._json(200, resp)
                return

            # v0.6.6: estado do contato (mascarado) / eliminação (art. 18 VI)
            if p == "/api/contact":
                self._json(200, {"ok": True, **_tel_contact_status()})
                return

            if p == "/api/contact/delete":
                _tel_clear_contact()
                self._json(200, {"ok": True, "deleted": True})
                return

            # ══════════════════════════════════════════════════════════
            # v0.6.20 — Botão SAIR da interface (após confirmação no modal)
            # ══════════════════════════════════════════════════════════
            if p == "/api/shutdown":
                # Exigência de segurança: a UI só envia {"confirm": true}
                # após o usuário confirmar no modal. Sem isso, 400.
                if not bool(body.get("confirm", False)):
                    return self._json(400, {
                        "ok": False,
                        "error": "Confirmação ausente — o encerramento exige "
                                 "confirmação explícita do usuário.",
                    })
                # v0.6.20-fix: resposta IMEDIATA. O trabalho lento (nota de
                # fim de sessão no Drive/FUSE, kill do keep-alive e unassign)
                # roda em thread daemon. Antes era tudo síncrono e a rota só
                # respondia depois do write no Drive → o modal travava vários
                # segundos antes de desconectar.
                _shutdown_start()
                return self._json(200, {
                    "ok": True,
                    "message": "Encerrando o ambiente de execução…",
                })

            self.send_error(404)
    
    # v0.6.9-6: offline completo — bind 0.0.0.0 resolve "porta não funciona" quando localhost
    # resolve para 127.0.1.1 (Ubuntu /etc/hosts) ou quando o usuário tem proxy. Token + CORS
    # mantêm segurança mesmo em 0.0.0.0 (LAN precisaria do token). Override: UFVAI_BIND_HOST=127.0.0.1
    # para voltar ao modo localhost-only.
    _bind_host = os.environ.get("UFVAI_BIND_HOST") or "0.0.0.0"
    print(f"🛡️  Wrapper: bind {_bind_host}:{WRAPPER_PORT} · token {'ON' if _SESSION_TOKEN else 'OFF'} · CORS same-origin")

    # v0.6.3: servidor DUAL-STACK no loopback — o Chromium/Firefox preferem
    # ::1 (IPv6) ao resolver "localhost"; sem listener IPv6 a conexão cai
    # com ERR_CONNECTION_REFUSED (regressão v0.6.0; padrão herdado do
    # launcher 0.5.x). IPv4 principal + loopback IPv6 adicional (offline).
    _servers_started = 0
    try:
        threading.Thread(
            target=lambda: ThreadingHTTPServer((_bind_host, WRAPPER_PORT), Handler).serve_forever(),
            daemon=True,
            name="ufvai-wrapper",
        ).start()
        _servers_started += 1
    except OSError as e:
        logger.error("Falha ao bindar wrapper em %s:%s — %s", _bind_host, WRAPPER_PORT, e)

    # v0.6.9-6: tenta IPv6 também — 0.0.0.0 só cobre IPv4, localhost pode ser ::1
    try:
        import socket as _s

        class _LoopbackV6(ThreadingHTTPServer):
            address_family = _s.AF_INET6

        threading.Thread(
            target=lambda: _LoopbackV6(("::", WRAPPER_PORT), Handler).serve_forever(),
            daemon=True,
            name="ufvai-wrapper-v6",
        ).start()
        _servers_started += 1
    except OSError:
        pass  # sem IPv6 no host — segue só com IPv4
    if _servers_started == 0:
        raise RuntimeError(f"Nenhum servidor wrapper pôde ser iniciado na porta {WRAPPER_PORT}.")
    print(f"\n{next_joke('economia')}")
    print(f"🚀 Servidor wrapper iniciado na porta {WRAPPER_PORT} ({_servers_started} listener(s))")
    # v0.6.17: pré-aquece a memória em background — quando o usuário abrir
    # o menu da memória, o índice BM25 já estará em RAM (abertura instantânea)
    try:
        _warm_memory_async()
    except Exception:  # noqa: BLE001
        pass


def _auto_open_browser(url: str) -> None:
    """v0.6.1: abre o navegador automaticamente quando a UI estiver pronta.

    Modo offline/.deb (não-Colab): roda em thread daemon, espera a porta do
    wrapper responder (até 30 s) e abre o navegador padrão via webbrowser,
    com fallback para xdg-open/open.
    Desabilitar com: export UFVAI_NO_OPEN=1
    """
    if os.environ.get("UFVAI_NO_OPEN", "").strip().lower() in ("1", "true", "yes", "on"):
        print("ℹ️  UFVAI_NO_OPEN=1 — abertura automática do navegador desativada.")
        return

    def _worker():
        try:
            import socket as _socket
            deadline = time.time() + 30
            ready = False
            while time.time() < deadline:
                try:
                    with _socket.create_connection(("127.0.0.1", WRAPPER_PORT), timeout=0.5):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.5)
            if not ready:
                logger.warning("Porta %s não respondeu em 30s; navegador não aberto.", WRAPPER_PORT)
                return
            try:
                import webbrowser
                if webbrowser.open(url):
                    print(f"🌍 Navegador aberto em {url}")
                    return
            except Exception:
                pass
            # Fallbacks por plataforma
            for cmd in (["xdg-open", url], ["open", url]):
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=10)
                    if r.returncode == 0:
                        print(f"🌍 Navegador aberto em {url}")
                        return
                except Exception:
                    continue
            print(f"🌐 Abra manualmente: {url}")
        except Exception:
            try:
                print(f"🌐 Abra manualmente: {url}")
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True, name="ufvai-open-browser").start()


def show_ready_message():
    if not IN_COLAB or not display or not HTML:
        print("\n✨ UFVAI pronto!\n")
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
        <span class="ready-text">UFVAI pronto!</span>
    </div>
</div>
"""))


# ═══════════════════════════════════════════════════════════════════
# v0.6.7: Painel de boot do Colab — barra de progresso + checkpoints
# ═══════════════════════════════════════════════════════════════════

# Lupa UFVAI (assets/ico.svg) embutida inline — offline-safe, sem request.
_UFVAI_ICO_SVG: str = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" '
    'width="100%" height="100%" role="img" aria-label="UFVAI">'
    '<defs><linearGradient id="ufl-lens" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#d4b56a"/>'
    '<stop offset="100%" stop-color="#8f7536"/>'
    '</linearGradient></defs>'
    '<circle cx="92" cy="92" r="48" fill="#1f2831"/>'
    '<circle cx="92" cy="92" r="48" fill="none" stroke="url(#ufl-lens)" stroke-width="6"/>'
    '<line x1="127" y1="127" x2="166" y2="166" stroke="url(#ufl-lens)" '
    'stroke-width="10" stroke-linecap="round"/>'
    '<g stroke="#b29149" stroke-width="1.6" opacity="0.85">'
    '<line x1="76" y1="78" x2="96" y2="74"/><line x1="76" y1="78" x2="90" y2="92"/>'
    '<line x1="76" y1="78" x2="70" y2="96"/><line x1="96" y1="74" x2="110" y2="88"/>'
    '<line x1="96" y1="74" x2="90" y2="92"/><line x1="110" y1="88" x2="106" y2="106"/>'
    '<line x1="110" y1="88" x2="90" y2="92"/><line x1="106" y1="106" x2="88" y2="110"/>'
    '<line x1="106" y1="106" x2="90" y2="92"/><line x1="88" y1="110" x2="70" y2="96"/>'
    '<line x1="88" y1="110" x2="90" y2="92"/><line x1="70" y1="96" x2="90" y2="92"/>'
    '</g>'
    '<circle cx="90" cy="92" r="5.5" fill="#d4b56a"/>'
    '<circle cx="76" cy="78" r="4.5" fill="#b29149"/>'
    '<circle cx="96" cy="74" r="4.5" fill="#b29149"/>'
    '<circle cx="110" cy="88" r="4.5" fill="#b29149"/>'
    '<circle cx="106" cy="106" r="4.5" fill="#b29149"/>'
    '<circle cx="88" cy="110" r="4.5" fill="#b29149"/>'
    '<circle cx="70" cy="96" r="4.5" fill="#b29149"/>'
    '</svg>'
)

_UFVAI_LOGO_B64: str | None = None  # cache; "" = asset ausente (fallback)


def _load_logo_b64() -> str | None:
    """Logomarca oficial (assets/logo-oficial-288.jpg) em base64, com cache.

    Offline-safe: lê o arquivo do repositório, sem qualquer request de rede.
    Retorna None se o asset não existir (o chamador usa o fallback em CSS).
    """
    global _UFVAI_LOGO_B64
    if _UFVAI_LOGO_B64 is not None:
        return _UFVAI_LOGO_B64 or None
    try:
        p = Path(__file__).resolve().parent.parent / "assets" / "logo-oficial-288.jpg"
        if p.is_file():
            _UFVAI_LOGO_B64 = _b64.b64encode(p.read_bytes()).decode("ascii")
            return _UFVAI_LOGO_B64
    except Exception:
        pass
    _UFVAI_LOGO_B64 = ""
    return None


def _launch_logo_markup() -> str:
    """Logo real (<img> base64) ou wordmark CSS como fallback — tema da marca."""
    b64 = _load_logo_b64()
    if b64:
        return (
            '<img class="ufb-logo" src="data:image/jpeg;base64,' + b64 + '" '
            'alt="UFVAI — Inteligência Artificial" width="230" height="230" />'
        )
    return (
        '<div class="ufb-logo-fallback">'
        '<div class="ufb-wm"><span>UFV</span><span class="ufl-ai">AI</span></div>'
        '<div class="ufb-rule"></div>'
        '<div class="ufb-tag">INTELIGÊNCIA ARTIFICIAL</div>'
        "</div>"
    )


# Paleta da logomarca oficial (logo_8x8cm_300dpi.jpg): papel off-white,
# azul-marinho "UFV", dourado "AI"; vermelho das constelações p/ falhas.
_UFL_CSS: str = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@500&family=Montserrat:wght@600;700;800&display=swap');
.ufl-panel{max-width:560px;margin:10px auto;padding:26px 30px 22px;background:#f6f5f0;border:1px solid rgba(43,45,58,.14);border-radius:18px;box-shadow:0 14px 34px rgba(43,45,58,.12);font-family:'DM Mono',monospace}
.ufl-head{text-align:center;margin-bottom:16px}
.ufl-wordmark{font-family:'Montserrat','Syne',system-ui,sans-serif;font-size:34px;font-weight:800;letter-spacing:.04em;line-height:1;color:#2b2d3a}
.ufl-wordmark .ufl-ai{color:#b8912f}
.ufl-rule{height:1px;background:rgba(43,45,58,.22);margin:10px auto 7px;width:78%}
.ufl-tagline{font-family:'Montserrat',system-ui,sans-serif;font-size:11px;font-weight:600;color:#8f8d86;letter-spacing:.42em;text-indent:.42em}
.ufl-barwrap{position:relative;height:12px;background:#e9e6df;border:1px solid rgba(43,45,58,.15);border-radius:999px;overflow:hidden}
.ufl-fill{position:absolute;top:0;left:0;bottom:0;width:PERCENT%;background:linear-gradient(90deg,#caa53f,#b8912f 45%,#8f7536);border-radius:999px;transition:width .45s ease;overflow:hidden}
.ufl-fill::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.5),transparent);animation:ufl-shim 1.4s linear infinite}
@keyframes ufl-shim{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.ufl-pct{text-align:right;font-size:11px;color:#8f7536;margin-top:6px;letter-spacing:.08em}
/* Mensagens SEMPRE abaixo da barra — ordem garantida em _html() */
.ufl-list{list-style:none;margin:14px 0 0;padding:0;display:flex;flex-direction:column;gap:8px}
.ufl-row{display:flex;align-items:center;gap:9px;font-size:13px;color:#3c3f4e;text-align:left}
.ufl-mark{color:#b8912f;font-weight:700;flex:0 0 auto}
.ufl-row.bad .ufl-mark,.ufl-row.bad{color:#a94442}
.ufl-spin{width:12px;height:12px;border:2px solid rgba(184,145,47,.30);border-top-color:#b8912f;border-radius:50%;animation:ufl-rot .8s linear infinite;flex:0 0 12px}
@keyframes ufl-rot{to{transform:rotate(360deg)}}
.ufl-ready{margin-top:16px;font-family:'Montserrat','Syne',sans-serif;font-weight:700;color:#2b2d3a;font-size:15px;text-align:center;letter-spacing:.04em}
@media (prefers-reduced-motion: reduce){.ufl-fill::after,.ufl-spin{animation:none}}
</style>
"""


class _BootPanel:
    """Painel visual de inicialização do Colab (v0.6.7).

    Tela LEVE no tema da logomarca oficial (papel off-white #f6f5f0 +
    azul-marinho "UFV" #2b2d3a + dourado "AI" #b8912f) com barra de
    progresso e checklist de checkpoints que aparece linha a linha
    SEMPRE ABAIXO da barra, conforme as etapas reais de launch()
    concluem.

    Fora do Colab todas as operações são no-op (o fluxo de prints
    legado permanece). Erros de renderização NUNCA derrubam o boot.
    """

    _DISPLAY_ID = "ufvai_boot_panel"

    def __init__(self) -> None:
        self._pct: int = 0
        self._rows: list[tuple[str, bool]] = []  # (label, ok)
        self._active: str | None = None
        self._created: bool = False
        self._finished: bool = False

    # ── API de estado ────────────────────────────────────────────
    def begin(self) -> None:
        """Cria o painel vazio (barra em 0%) — idempotente.

        Se o painel já foi criado nesta sessão (ex.: pelo progress_bar
        no início do run(), ou por um begin() anterior), NÃO reinicia:
        preserva % e histórico das linhas para a barra ser CONTÍNUA
        desde o início do carregamento.
        """
        if self._created:
            return
        self._render(create=True)

    def active(self, label: str, pct: int) -> None:
        """Inicia um checkpoint: revela a linha com spinner e avança a barra.

        Se houver checkpoint ativo pendente (troca direta de etapa,
        caminho do progress_bar → launch()), ele é concluído com ✓
        antes — nunca ficam dois spinners simultâneos.
        """
        if self._active and self._active != label:
            self._rows.append((self._active, True))
        self._pct = max(self._pct, min(int(pct), 99))
        self._active = label
        self._render()

    def done(self, pct: int | None = None) -> None:
        """Conclui o checkpoint ativo (linha fica ✓ verde-dourado)."""
        if self._active:
            self._rows.append((self._active, True))
            self._active = None
        if pct is not None:
            self._pct = max(self._pct, min(int(pct), 99))
        self._render()

    def fail(self, note: str = "") -> None:
        """Marca o checkpoint ativo como falho (✕) sem interromper o boot."""
        if self._active:
            label = self._active + (f" — {note}" if note else "")
            self._rows.append((label, False))
            self._active = None
            self._render()

    def finish(self) -> None:
        """100% + linha '✨ UFVAI pronto!'."""
        if self._active:
            self._rows.append((self._active, True))
            self._active = None
        self._pct = 100
        self._finished = True
        self._render()

    # ── Render ───────────────────────────────────────────────────
    def _supported(self) -> bool:
        return bool(
            IN_COLAB and display is not None and HTML is not None
            and update_display is not None
        )

    def _render(self, create: bool = False) -> None:
        if not self._supported():
            return
        try:
            html = HTML(self._html())
            if create or not self._created:
                display(html, display_id=self._DISPLAY_ID)
                self._created = True
            else:
                update_display(html, display_id=self._DISPLAY_ID)
        except Exception:
            pass  # painel nunca derruba o boot

    def _html(self) -> str:
        rows = []
        for label, ok in self._rows:
            mark = "✓" if ok else "✕"
            cls = "ok" if ok else "bad"
            rows.append(
                f'<li class="ufl-row {cls}"><span class="ufl-mark">{mark}</span>'
                f"<span>{label}</span></li>"
            )
        if self._active:
            rows.append(
                f'<li class="ufl-row act"><span class="ufl-spin"></span>'
                f"<span>{self._active}…</span></li>"
            )
        ready_line = (
            '\n<div class="ufl-ready">✨ UFVAI pronto!</div>' if self._finished else ""
        )
        css = _UFL_CSS.replace("PERCENT", str(self._pct))
        return (
            css
            + '<div class="ufl-panel">'
            + '<div class="ufl-head">'
            + '<div class="ufl-wordmark"><span>UFV</span>'
            + '<span class="ufl-ai">AI</span></div>'
            + '<div class="ufl-rule"></div>'
            + '<div class="ufl-tagline">INTELIGÊNCIA ARTIFICIAL</div>'
            + "</div>"
            + '<div class="ufl-barwrap"><div class="ufl-fill"></div></div>'
            + f'<div class="ufl-pct">{self._pct}%</div>'
            + ('<ul class="ufl-list">' + "".join(rows) + "</ul>" if rows else "")
            + ready_line
            + "</div>"
        )


# ── Painel único da sessão ───────────────────────────────────────
_BOOT_SINGLETON: "_BootPanel | None" = None


def get_boot_panel() -> "_BootPanel":
    """Retorna o painel de boot ÚNICO desta sessão (singleton).

    v0.6.7 — a barra começa no INÍCIO do carregamento: o notebook cria
    o painel ainda na fase de clone, progress_bar.show() alimenta os
    estágios do run() (Drive → dependências → skills) e launch()
    continua no mesmo display ("ufvai_boot_panel") até os 100%.
    Uma única barra contínua, mensagens sempre abaixo dela, sem cards
    duplicados nem reinicializações.
    """
    global _BOOT_SINGLETON
    if _BOOT_SINGLETON is None:
        _BOOT_SINGLETON = _BootPanel()
    return _BOOT_SINGLETON


def show_launch_button(banner_url):
    if not IN_COLAB or not display or not HTML:
        print(f"\n🎉 Acesse: {banner_url}")
        return

    # v0.6.7 (revisão): tela LEVE no tema da logomarca oficial — papel
    # off-white, azul-marinho "UFV" + dourado "AI". A LOGO REAL (base64,
    # offline-safe) aparece acima do botão NO LUGAR do antigo texto
    # "✨ UFVAI pronto"; botão em pílula dourada com tipografia navy.
    logo_html = _launch_logo_markup()
    display(HTML(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@500&family=Montserrat:wght@600;700;800&display=swap');
  @keyframes ufb-pulse {{
    0%, 100% {{ box-shadow: 0 6px 18px rgba(143,117,54,.35); }}
    50% {{ box-shadow: 0 10px 34px rgba(184,145,47,.55); }}
  }}
  .ufb-card {{
    max-width: 560px;
    margin: 12px auto;
    padding: 28px 24px 26px;
    background: #f6f5f0;
    border: 1px solid rgba(43,45,58,.14);
    border-radius: 18px;
    box-shadow: 0 14px 34px rgba(43,45,58,.12);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
  }}
  .ufb-logo {{
    width: 210px;
    height: auto;
    border-radius: 10px;
  }}
  /* Fallback sem asset: wordmark CSS no tema da marca */
  .ufb-logo-fallback {{
    font-family: 'Montserrat', 'Syne', system-ui, sans-serif;
    text-align: center;
    color: #2b2d3a;
    padding: 8px 0 2px;
  }}
  .ufb-wm {{
    font-size: 40px;
    font-weight: 800;
    letter-spacing: .04em;
    line-height: 1;
  }}
  .ufb-wm .ufl-ai {{ color: #b8912f; }}
  .ufb-rule {{
    height: 1px;
    background: rgba(43,45,58,.22);
    margin: 10px auto 7px;
    width: 220px;
  }}
  .ufb-tag {{
    font-size: 11px;
    font-weight: 600;
    color: #8f8d86;
    letter-spacing: .38em;
    text-indent: .38em;
  }}
  .ufb-btn, .pesquisai-launch {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    padding: 17px 46px;
    font-family: 'Montserrat', 'Syne', sans-serif;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: .08em;
    color: #2b2d3a;
    background: linear-gradient(135deg, #d3b054 0%, #b8912f 45%, #8f7536 100%);
    border: none;
    border-radius: 999px;
    cursor: pointer;
    text-decoration: none;
    box-shadow: 0 6px 18px rgba(143,117,54,.35);
    transition: transform 0.2s ease, filter 0.2s ease, box-shadow 0.2s ease;
    animation: ufb-pulse 2.5s ease-in-out infinite;
    position: relative;
    overflow: hidden;
  }}
  .ufb-btn::before {{
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.35), transparent);
    transition: left 0.5s;
  }}
  .ufb-btn:hover::before {{ left: 100%; }}
  .ufb-btn:hover {{
    transform: translateY(-4px) scale(1.02);
    filter: brightness(1.08);
    box-shadow: 0 12px 40px rgba(184,145,47,.5), 0 8px 24px rgba(43,45,58,.18);
  }}
  .ufb-btn:active {{ transform: translateY(-1px) scale(0.99); }}
  .ufb-btn:focus-visible {{
    outline: 3px solid rgba(43,45,58,.45);
    outline-offset: 3px;
  }}
  .ufb-text {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 3px;
  }}
  .ufb-main {{ line-height: 1; }}
  .ufb-sub {{
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    opacity: 0.75;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }}
  .ufb-arrow {{
    font-size: 26px;
    font-weight: 500;
    transition: transform 0.2s ease;
  }}
  .ufb-btn:hover .ufb-arrow {{ transform: translateX(8px); }}
  @media (prefers-reduced-motion: reduce) {{
    .ufb-btn {{ animation: none; transition: none; }}
  }}
</style>
<div class="ufb-card">
  {logo_html}
  <a href="{banner_url}" target="_blank" class="ufb-btn pesquisai-launch">
    <span class="ufb-text">
      <span class="ufb-main">ABRIR O UFVAI</span>
      <span class="ufb-sub">clique para começar</span>
    </span>
    <span class="ufb-arrow">→</span>
  </a>
</div>
"""))


# ══════════════════════════════════════════════════════════════════
# v0.6.20 — Botão SAIR da interface: encerramento seguro do runtime
# ══════════════════════════════════════════════════════════════════
# Fluxo acionado pela UI (modal com confirmação → POST /api/shutdown):
#   0. A rota responde IMEDIATAMENTE (v0.6.20-fix) — todo o trabalho vai para
#      uma thread daemon via _shutdown_start(), para a UI não travar no Drive;
#   1. Salvar nota de fim de sessão na memória (best-effort, teto de 1 s);
#   2. Encerrar o keep-alive do notebook (PID em /tmp/pesquisai/ufvai_keepalive.pid,
#      escrito pela célula de boot; fallback pkill pelo marcador de cmdline);
#   3. Desconectar e excluir o runtime do Colab (runtime.unassign) — executado
#      em thread daemon APÓS a resposta HTTP chegar ao frontend, para que a
#      UI possa mostrar o estado "encerrando/encerrado" antes da queda.
_KEEPALIVE_PID_FILE = "/tmp/pesquisai/ufvai_keepalive.pid"
_KEEPALIVE_CMD_MARKER = "ufvai-keepalive-v0620"


def _shutdown_save_memory_note() -> bool:
    """Grava nota de fim de sessão na memória (best-effort, fail-open)."""
    try:
        from pesquisai.obsidian import ObsidianMemoryStatus
        from pesquisai.obsidian.models import Note, NoteMetadata
        from pesquisai.obsidian.models import extract_wikilinks, extract_tags
        import datetime as _dt

        mem = _get_memory()
        if mem.status != ObsidianMemoryStatus.READY or mem._vault is None:
            return False
        today = _dt.date.today()
        rel_path = f"sessions/ses_{today.isoformat()}-encerrado-via-interface.md"
        body = (
            f"# Sessão encerrada via interface — {today.isoformat()}\n\n"
            "- **Evento:** usuário acionou o botão **SAIR** da interface do app "
            "(confirmação explícita no modal) e o ambiente de execução foi "
            "desconectado/excluído (`runtime.unassign`).\n"
            f"- **Registrado automaticamente** pela rota `/api/shutdown` (v0.6.20) "
            "para preservar o rastro da sessão na memória.\n"
            "- Próxima sessão: recall em [[moc/last-state]].\n"
        )
        existing = mem.get(rel_path)
        if existing is not None:
            body = existing.body + "\n" + body
        note = Note(
            path=rel_path,
            metadata=NoteMetadata(
                title=f"Sessão encerrada via interface — {today.isoformat()}",
                created=existing.metadata.created if existing else today,
                updated=today,
                tags=("pesquisai/session", "pesquisai/archived"),
                created_by="pesquisai",
                status="archived",
            ),
            body=body,
            wikilinks=extract_wikilinks(body),
            tags=extract_tags(body),
        )
        if existing is not None:
            note.tags = tuple(sorted(set(note.tags) | set(existing.metadata.tags) | set(note.wikilinks and [])))
        mem._vault.write(note, force=False)
        return True
    except Exception:
        return False


def _shutdown_kill_keepalive() -> bool:
    """Encerra o subprocesso keep-alive do notebook (best-effort)."""
    # Keep-alive em célula bloqueante (kernel): pedimos a parada por evento.
    try:
        from . import keepalive as _ka
        _ka.request_stop()
    except Exception:  # noqa: BLE001
        pass
    import signal  # import local: módulo não depende de signal no topo

    pid: int | None = None
    try:
        with open(_KEEPALIVE_PID_FILE, "r", encoding="utf-8") as fh:
            pid = int(fh.read().strip())
    except Exception:
        pid = None

    if pid is not None and pid > 0 and pid != os.getpid():
        try:
            os.kill(pid, signal.SIGTERM)
            # v0.6.20-fix: espera curta (≤0,3 s) pelo TERM antes do KILL —
            # o botão SAIR não pode ficar preso num processo teimoso.
            for _ in range(15):
                time.sleep(0.02)
                try:
                    os.kill(pid, 0)
                except OSError:
                    return True
            os.kill(pid, signal.SIGKILL)
            return True
        except OSError:
            pass

    # Fallback: marcador na cmdline (PID file ausente/inválido)
    try:
        subprocess.run(
            ["pkill", "-f", _KEEPALIVE_CMD_MARKER],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def _shutdown_stop_opencode_service() -> bool:
    """v0.6.20 · OpenCode V2: encerra o serviço de fundo compartilhado.

    O V2 sobe um `opencode serve --service` **desanexado** (fora do grupo de
    processos do ttyd), então ele sobreviveria ao kill da árvore do terminal
    e continuaria consumindo memória depois do SAIR. Best-effort: com o
    motor V1 (sem o subcomando `service`) esta função é um no-op.
    """
    try:
        if not is_opencode_v2():
            return False
        bin_path = find_opencode()
    except Exception:
        return False
    try:
        r = subprocess.run(
            [bin_path, "service", "stop"],
            capture_output=True, timeout=8,
        )
        return r.returncode == 0
    except Exception:
        return False


def _shutdown_schedule_unassign(delay_s: float = 0.4) -> None:
    """Desconecta/exclui o runtime do Colab após a resposta HTTP ser entregue.

    O servidor wrapper roda em thread DENTRO do processo do kernel do Colab;
    `google.colab.runtime.unassign()` age pelo canal do kernel e é o mesmo
    mecanismo de *Runtime ▸ Desconectar e excluir ambiente* (colabtools).
    Fora do Colab (offline/.deb), nada é feito.
    """
    def _worker():
        try:
            time.sleep(delay_s)
            if not IN_COLAB:
                return
            from google.colab import runtime as _colab_runtime  # noqa: PLC0415
            _colab_runtime.unassign()
        except Exception:
            # Fallback honesto: o usuário pode usar o menu Runtime.
            pass

    threading.Thread(target=_worker, daemon=True, name="ufvai-sair-unassign").start()


def _shutdown_start(
    *,
    memory_timeout_s: float = 1.0,
    flush_s: float = 0.4,
) -> None:
    """Dispara o encerramento SEM bloquear a resposta HTTP (v0.6.20-fix).

    Todo o trabalho lento — gravar a nota de fim de sessão na memória
    (Drive/FUSE), encerrar o keep-alive e desligar o runtime — roda em
    thread daemon. A rota ``/api/shutdown`` responde na hora e a UI fecha o
    modal imediatamente, sem os segundos de espera do write no Drive.

    A gravação da nota tem um **teto** (``memory_timeout_s``): desconectar
    não pode depender de uma escrita lenta no Drive. A nota é *best-effort*
    e o progresso real já é salvo continuamente pelo agente.
    """
    def _worker() -> None:
        # 1. Nota de fim de sessão em paralelo (não bloqueia o kill).
        note_done = threading.Event()

        def _save() -> None:
            try:
                _shutdown_save_memory_note()
            except Exception:  # noqa: BLE001
                pass
            finally:
                note_done.set()

        threading.Thread(
            target=_save, daemon=True, name="ufvai-sair-memoria",
        ).start()

        # 2. Encerra o keep-alive (rápido) enquanto a nota é gravada.
        try:
            _shutdown_kill_keepalive()
        except Exception:  # noqa: BLE001
            pass

        # 2b. v0.6.20 · OpenCode V2: derruba também o serviço de fundo
        #     (desanexado do ttyd — sobreviveria ao kill da árvore).
        try:
            _shutdown_stop_opencode_service()
        except Exception:  # noqa: BLE001
            pass

        # 2c. Credenciais do OpenCode V2 (cifradas no Drive), teto de 6 s.
        auth_done = threading.Event()

        def _save_auth() -> None:
            try:
                save_opencode_auth_to_drive(_backup_dir())
            except Exception:  # noqa: BLE001
                pass
            finally:
                auth_done.set()

        threading.Thread(target=_save_auth, daemon=True, name="ufvai-sair-auth").start()
        auth_done.wait(timeout=6.0)

        # 3. Espera a nota apenas até o teto — nunca além disso.
        note_done.wait(timeout=memory_timeout_s)

        # 4. Só então derruba o kernel, garantindo o flush da resposta HTTP.
        _shutdown_schedule_unassign(delay_s=flush_s)

    threading.Thread(target=_worker, daemon=True, name="ufvai-sair").start()


def launch():
    global _drive_url
    
    # v0.6.7: painel de boot ÚNICO e contínuo — reutiliza a instância que
    # já exibe os estágios do setup (progress_bar) desde o início do
    # carregamento; begin() é idempotente e NÃO zera a barra.
    boot = get_boot_panel()
    boot.begin()
    # v0.6.15: idioma do prompt inicial deve respeitar detecção do sistema
    # (antes _current_lang="pt_BR" truthy impedia _detect_system_lang(); ttyd
    # sempre iniciava em pt). Garante detecção ANTES do 1º start_ttyd.
    try:
        _ensure_lang_initialized()
    except Exception:
        pass
    
    try:
        boot.active("Localizando o núcleo opencode", 82)
        resolve_opencode()
        boot.done(85)
        
        # ═══ CARREGAR CHAVES ANTES DE INICIAR O TERMINAL ═══
        boot.active("Carregando chaves de API do Drive", 87)
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
        boot.done(89)
        
        boot.active("Restaurando credenciais do OpenCode", 90)
        try:
            restore_opencode_auth_from_drive(_pre_backup_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Restauração de credenciais do OpenCode falhou: %s", exc)
        boot.done(90)
        boot.active("Instalando o terminal (ttyd)", 91)
        install_ttyd()
        boot.done(93)
        
        boot.active("Encerrando sessões anteriores", 94)
        kill_previous()
        boot.done(95)
        
        boot.active("Iniciando terminal interativo", 96)
        start_ttyd()
        boot.done(97)
        
        if IN_COLAB and output:
            terminal_url = output.eval_js(f"google.colab.kernel.proxyPort({TERMINAL_PORT})")
            banner_url = output.eval_js(f"google.colab.kernel.proxyPort({WRAPPER_PORT})")
        else:
            terminal_url = f"http://localhost:{TERMINAL_PORT}"
            banner_url = f"http://localhost:{WRAPPER_PORT}"
        
        boot.active("Preparando a interface web", 98)
        global _SESSION_TOKEN
        _SESSION_TOKEN = secrets.token_urlsafe(32)
        create_wrapper_html(terminal_url, _drive_url, session_token=_SESSION_TOKEN)
        start_wrapper_server()
        try:
            _tel_event("app_started", {"version": VERSION, "lang": _current_lang, "colab": bool(IN_COLAB)})
        except Exception:
            pass
        boot.done(99)
    except Exception as exc:
        boot.fail(str(exc)[:80])
        raise
    
    time.sleep(1)
    boot.finish()  # 100% + "✨ UFVAI pronto!"

    show_launch_button(banner_url)

    # v0.6.21: cookies de terceiros — ÚLTIMO item do fluxo. O botão "ABRIR O
    # UFVAI" já está na tela e o diagnóstico fecha a sequência com o veredito
    # real (✅ liberados / ❌ bloqueados). O proxy do Colab (*.prod.colab.dev)
    # não abre sem permissão de cookie de 3ª parte. ensure_cookie_check() é
    # idempotente: se outro caminho já mostrou o bloco (run_fast ou notebook),
    # aqui devolve 'done' sem repetir. Fora do Colab devolve 'skipped'.
    try:
        from .colab_cookies import ensure_cookie_check
        _cookie_state = ensure_cookie_check()
        if _cookie_state.get("state") == "error":
            logger.warning(
                "Teste de cookies indisponível: %s", _cookie_state.get("error")
            )
    except Exception as exc:  # noqa: BLE001 — o aviso é acessório, nunca fatal
        logger.warning("Verificação de cookies não pôde ser executada: %s", exc)

    # v0.6.1: no modo offline (.deb/local) abre o navegador automaticamente
    # quando a UI estiver pronta — o launcher roda em background e antes
    # não havia nenhum feedback visível ("parecia não iniciar").
    if not IN_COLAB:
        _auto_open_browser(banner_url)
        print(f"\n🌐 Interface: {banner_url}  (terminal: http://localhost:{TERMINAL_PORT})")

    # v0.6.11: anuncia a URL pública p/ o app Android descobrir sozinho (sem colar URL)
    if IN_COLAB and banner_url and str(banner_url).startswith("http"):
        try:
            _tel_publish_backend_url(str(banner_url))
        except Exception:
            pass

    return banner_url


if __name__ == "__main__":
    _url = launch()
    # v0.6.3: execução direta fora do Colab também precisa manter o processo vivo
    if not IN_COLAB:
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n👋 Encerrando UFVAI…")
