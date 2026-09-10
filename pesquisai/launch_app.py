import os
import subprocess
import time
import threading
import json
import hashlib
import shutil
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

from .constants import TERMINAL_PORT, WRAPPER_PORT, WRAPPER_DIR, VERSION, logger
from .jokes import next_joke

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
from .opencode_utils import find_opencode, build_env
from .security import load_encrypted_keys, save_encrypted_keys, sanitize_command

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
    return _opencode_bin, _env


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

    import urllib.request as _urllib

    # 1. Iniciar ttyd temporário com comando dummy
    #    v0.6.5: nova sessão de processos + log em arquivo
    print("📱 Preparando HTML do ttyd com touch handlers...")
    tmp_proc = subprocess.Popen(
        ["ttyd", "-p", str(TERMINAL_PORT), "echo", "pesquisai_touch_tmp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
        start_new_session=True,
    )
    time.sleep(2)

    # 2. Buscar HTML padrão do ttyd
    html_content: str | None = None
    try:
        url = f"http://localhost:{TERMINAL_PORT}/"
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
    subprocess.run(["pkill", "-9", "-x", "ttyd"], capture_output=True, timeout=3)
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


def _persist_lang(lang: str) -> None:
    """Persiste o idioma atual em ~/.config/pesquisai_lang."""
    try:
        os.makedirs(os.path.dirname(_LANG_COOKIE_FILE), exist_ok=True)
        with open(_LANG_COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(lang)
    except Exception:
        pass


def _ensure_lang_initialized() -> str:
    """v0.6.15: garante que _current_lang esteja resolvido ANTES do 1º ttyd.

    Ordem: cookie file (≈ escolha explícita do usuário) > PESQUISAI_LANG env
    > detecção do sistema (_detect_system_lang). Persiste o resultado para
    tornar a próxima execução determinística. Idempotente — pode ser chamada
    em launch() e em start_wrapper_server() sem efeitos colaterais.
    """
    global _current_lang
    # Se já está válido, respeita (evita re-detectar após escolha do usuário)
    if _current_lang and _current_lang in _LANG_MAP.values():
        return _current_lang
    try:
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
                _persist_lang(_current_lang)
                return _current_lang
        if os.environ.get("PESQUISAI_LANG"):
            env_lang = str(os.environ["PESQUISAI_LANG"]).strip()
            short = env_lang.split("_")[0].lower()
            _current_lang = _LANG_MAP.get(short, env_lang if env_lang in _LANG_MAP.values() else "pt_BR")
            _persist_lang(_current_lang)
            return _current_lang
        # Nenhuma preferência salva → detecta do sistema
        _current_lang = _detect_system_lang()
        print(f"🌐 Idioma detectado do sistema: {_current_lang}")
        _persist_lang(_current_lang)
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


def _spawn_ttyd(ttyd_args: list, env: dict | None) -> "subprocess.Popen":
    """v0.6.5: Popen rastreado em NOVA SESSÃO de processos.

    start_new_session=True faz o ttyd ser líder do próprio grupo — assim
    _stop_terminal() consegue matar ttyd + bash + opencode (a árvore toda)
    com um único killpg, sem pkill -f global (que matava qualquer processo
    com 'opencode' na cmdline, inclusive o agente hospedeiro).
    """
    global _TTYD_PROC
    logf = _ttyd_log_file()
    proc = subprocess.Popen(
        ttyd_args,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    _TTYD_PROC = proc
    return proc


def _stop_terminal(wait_s: float = 0.8) -> None:
    """v0.6.5: encerra a ÁRVORE do terminal de forma cirúrgica.

    1. killpg no grupo rastreado (_TTYD_PROC) — mata ttyd + bash + opencode;
    2. Fallback determinístico: pkill -9 -x ttyd casa apenas o COMM exato
       'ttyd' (NUNCA casa python/host/bash com 'opencode' na cmdline).
    """
    global _TTYD_PROC
    import signal as _signal

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


def _build_ttyd_cmd(lang: str | None = None):
    """v0.6.5: constrói (args, env) do ttyd com saudação no idioma pedido.

    Extraído de start_ttyd para permitir retry determinístico em
    restart_ttyd_with_lang/_ensure_terminal_ready.
    """
    opencode_bin, env = resolve_opencode()

    # Resolve idioma (param > env > _current_lang > detecção do sistema)
    if lang is None:
        lang = os.environ.get("PESQUISAI_LANG") or _current_lang or _detect_system_lang()
    # Normaliza para o conjunto canônico
    short = (lang or "pt_BR").split("_")[0].lower()
    full_lang = _LANG_MAP.get(short, lang if lang in _LANG_MAP.values() else "pt_BR")

    greeting = get_greeting(full_lang)
    # Escapar aspas para o bash -c "..."
    safe_prompt = greeting.replace('"', '\\"').replace("'", "\\'")
    # v0.6.0: --yolo MANTIDO por padrão (decisão do usuário).
    # Para desligar: export PESQUISAI_YOLO=0
    _yolo = "" if os.environ.get("PESQUISAI_YOLO", "1").strip().lower() in ("0", "false", "off", "no") else " --yolo"
    bash_cmd = f'{opencode_bin} --prompt "{safe_prompt}" {_yolo} ; exec bash'

    # v0.4.2.5: construir args com --index (touch handlers)
    # v0.6.2: --writable restaurado (regressão v0.6.0 deixava o terminal read-only)
    base_args = ["ttyd", "-p", str(TERMINAL_PORT), "--writable", "bash", "-i", "-c", bash_cmd]
    return _build_ttyd_args(base_args, env), env, full_lang


def start_ttyd(lang: str | None = None):
    """Inicia o ttyd com saudação no idioma solicitado.

    Args:
        lang: Código do idioma (pt_BR, en_US, es_ES, fr_FR). Se None, usa
              o _current_lang global ou o env PESQUISAI_LANG.

    v0.4.2.2: ao invés de `--prompt 'oi'` genérico, usa saudação no idioma
              + instrução "(a partir de agora responda em X)".
    v0.4.2.5: injeta touch handlers (scroll + pinch-zoom) no HTML do ttyd
              via flag --index, habilitando rolagem e zoom em mobile.
    v0.6.5: spawn rastreado (_spawn_ttyd) + logs em arquivo; espera curta.
    """
    print(f"\n{next_joke('economia')}")
    ttyd_args, env, full_lang = _build_ttyd_cmd(lang)
    _spawn_ttyd(ttyd_args, env)
    print(f"🚀 Terminal iniciado (idioma: {full_lang}, touch: {'ON' if '--index' in ttyd_args else 'OFF'}).")
    time.sleep(0.8)


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
        _persist_lang(lang)

        def _spawn():
            ttyd_args, env, _full = _build_ttyd_cmd(lang)
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
        """Copy opencode auth/config to Drive backup folder.

        v0.6.0: grava CIFRADO com Fernet (o arquivo contém tokens de acesso!).
        Formato novo: {"_ufvai_enc": true, "data": "<fernet-b64>"}.
        Fallback: cópia plaintext apenas se a criptografia falhar (compat).
        """
        src = find_opencode_config()
        if src and os.path.exists(src):
            try:
                from .security import encrypt_data, _load_or_create_encryption_key
                raw = open(src, "rb").read()
                key = _load_or_create_encryption_key(DRIVE_BACKUP_DIR)
                enc = encrypt_data(key, _b64.b64encode(raw).decode("ascii"))
                with open(DRIVE_CONFIG_BACKUP, "w", encoding="utf-8") as fh:
                    json.dump({"_ufvai_enc": True, "data": enc}, fh)
                return src
            except Exception:
                shutil.copy2(src, DRIVE_CONFIG_BACKUP)
                return src
        return None

    def restore_opencode_config_from_drive():
        """Restore opencode auth/config from Drive backup if it exists.

        v0.6.0: aceita formato cifrado (_ufvai_enc=true) e legado plaintext.
        """
        if not os.path.exists(DRIVE_CONFIG_BACKUP):
            return False
        restored = False
        try:
            with open(DRIVE_CONFIG_BACKUP, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data.get("_ufvai_enc"):
                from .security import decrypt_data, _load_or_create_encryption_key
                key = _load_or_create_encryption_key(DRIVE_BACKUP_DIR)
                raw = _b64.b64decode(decrypt_data(key, data["data"]).encode("ascii"))
                src_path = os.path.join("/tmp", "ufvai_oc_auth_restore.json")
                with open(src_path, "wb") as fb:
                    fb.write(raw)
            else:
                src_path = DRIVE_CONFIG_BACKUP  # legado plaintext
        except Exception:
            src_path = DRIVE_CONFIG_BACKUP
        for dest in OPENCODE_CONFIG_CANDIDATES:
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src_path, dest)
                restored = True
            except Exception:
                pass
        return restored

    # Auto-restore opencode config from Drive on startup
    if restore_opencode_config_from_drive():
        print(f"🔑 Config do OpenCode restaurada do Drive.")
    
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
        
        def do_GET(self):
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
                content = open(idx, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Frame-Options", "SAMEORIGIN")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            
            if p == "/api/sessions":
                cmd = [_opencode_bin or "opencode", "session", "list", "--format", "json"]
                r = _run(cmd=cmd)
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

            if p == "/api/ttyd_ready":
                # v0.6.5: status do terminal para o splash de carregamento da UI.
                # O frontend faz polling aqui antes de apontar o iframe — assim
                # o usuário nunca vê ERR_CONNECTION_REFUSED dentro do terminal.
                try:
                    ready = _wait_port_open(TERMINAL_PORT, timeout_s=1.2)
                except Exception:
                    ready = False
                self._json(200, {"ready": bool(ready), "port": TERMINAL_PORT})
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
                # Retorna tema atual do tui.json
                try:
                    with open(os.path.expanduser("~/.config/opencode/tui.json")) as f:
                        tui = json.load(f)
                    current = tui.get("theme", "pesquisai")
                except Exception:
                    current = "pesquisai"
                self._json(200, {"theme": current})
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
                    cand_files.append(f"AGENTS.{_sh}.md")
                    cand_files.append(f"AGENTS.{_lg}.md")
                content = None
                served_file = None
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
                    "served_file": served_file or "",
                    "fallback_used": bool(served_file and short not in str(served_file)),
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

                # Build bash -c command string de forma segura
                # O comando do usuario (cmd) ja foi sanitizado acima.
                # O suffixo "; exec bash" e adicionado pelo codigo (nao pelo usuario),
                # entao nao precisa de segunda sanitizacao — isso causaria falso positivo
                # pois sanitize_command bloqueia ";" mesmo em comandos validos.
                if no_fallback:
                    bash_cmd = f"{cmd}; exec bash"
                else:
                    bash_cmd = f"{cmd}; {_opencode_bin}; exec bash"

                # v0.4.2.5: usar --index com touch handlers se disponível
                base_ttyd = ["ttyd", "--writable", "-p", str(TERMINAL_PORT),
                     "bash", "-i", "-c", bash_cmd]
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

                sid_safe = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id))[:12] or "sess"
                fname = f"backup_{sid_safe}_{ts}.json"
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

                try:
                    _tel_event("backup_created", {})
                except Exception:
                    pass
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
                fname_raw = str(body.get("file", "") or "").strip()
                fname = os.path.basename(fname_raw)
                if (not fname or fname != fname_raw or fname.startswith(".")
                        or ".." in fname
                        or not re.fullmatch(r"[A-Za-z0-9._-]+\.json", fname)):
                    self._json(400, {"error": "Nome de arquivo inválido."})
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
                
                # 3. v0.5.1.6 — REINICIAR ttyd com `opencode -s <session_id>`
                # Bug antigo: importava a sessão mas o ttyd continuava com --prompt,
                # então location.reload() mostrava a conversa ATUAL, não a importada.
                # v0.6.5: kill por árvore + espera a porta abrir + status real
                # (antes: respondia ok sem verificar → ERR_CONNECTION_REFUSED).
                ttyd_restarted = False
                ttyd_restart_error = ""
                if session_id:
                    try:
                        _stop_terminal()

                        def _spawn():
                            opencode_bin, env = resolve_opencode()
                            bash_cmd = f'{opencode_bin} -s "{session_id}" ; exec bash'
                            # v0.6.2: --writable restaurado (regressão v0.6.0 deixava o terminal read-only)
                            base_args = ["ttyd", "-p", str(TERMINAL_PORT), "--writable",
                                         "bash", "-i", "-c", bash_cmd]
                            _spawn_ttyd(_build_ttyd_args(base_args, env), env)

                        ttyd_restarted = _ensure_terminal_ready(_spawn, timeout_s=18.0)
                        if ttyd_restarted:
                            print(f"🔄 ttyd reiniciado com sessão {session_id}")
                        else:
                            ttyd_restart_error = (
                                f"Porta {TERMINAL_PORT} não respondeu após reinício "
                                "(veja logs/ttyd.log).")
                            logger.error(ttyd_restart_error)
                    except Exception as restart_err:
                        ttyd_restart_error = str(restart_err)[:200]
                        logger.error("Falha ao reiniciar ttyd com sessão %s: %s", session_id, restart_err)

                # 4. Respond
                try:
                    _tel_event("session_restored", {})
                except Exception:
                    pass
                self._json(200, {
                    "ok": True,
                    "file": fname,
                    "session_id": session_id,
                    "parse_error": parse_error,
                    "import_stdout": r.stdout.strip()[:300],
                    "ttyd_restarted": ttyd_restarted,
                    "ttyd_restart_error": ttyd_restart_error,
                    "message": (
                        "Sessão importada e ttyd reiniciado com opencode -s "
                        + session_id if ttyd_restarted else
                        "Sessão importada, mas ttyd NÃO foi reiniciado. "
                        "Faça reload manual após o import."
                    ),
                })
                return
            
            if p == "/api/theme":
                # Persiste escolha de tema (escuro/claro) em tui.json
                theme_name = body.get("theme", "").strip()
                # v0.6.0: aliases de marca mapeiam aos temas internos existentes
                _alias = {"ufvai": "pesquisai", "ufvai-light": "pesquisai-light"}
                theme_name = _alias.get(theme_name, theme_name)
                if theme_name not in ("pesquisai", "pesquisai-light"):
                    self._json(400, {"error": "Tema inválido. Use 'pesquisai' ou 'pesquisai-light'."})
                    return
                try:
                    tui_path = os.path.expanduser("~/.config/opencode/tui.json")
                    os.makedirs(os.path.dirname(tui_path), exist_ok=True)
                    with open(tui_path, "w") as f:
                        json.dump({"$schema": "https://opencode.ai/tui.json", "theme": theme_name}, f, indent=2)
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
                ok = restart_ttyd_with_lang(full_lang)
                if ok:
                    try:
                        _tel_event("lang_changed", {"lang": full_lang})
                    except Exception:
                        pass
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

    # v0.6.1: no modo offline (.deb/local) abre o navegador automaticamente
    # quando a UI estiver pronta — o launcher roda em background e antes
    # não havia nenhum feedback visível ("parecia não iniciar").
    if not IN_COLAB:
        _auto_open_browser(banner_url)
        print(f"\n🌐 Interface: {banner_url}  (terminal: http://localhost:{TERMINAL_PORT})")

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
