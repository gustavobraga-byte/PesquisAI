"""pesquisai/ocweb.py — v0.7.11-web: proxy da interface web do OpenCode.

O OpenCode V2 serve uma SPA em ``http://127.0.0.1:<porta>`` (a mesma do
``service.json``) protegida por HTTP Basic. Este módulo publica essa SPA em
``0.0.0.0:8002`` para o Colab (``proxyPort(8002)``) e para o wrapper,
**injetando a autenticação** e o **tema do UFVAI** (cores, tipografia e
assinatura), sem alterar o binário do motor.

Por que um proxy e não um iframe direto:

* o serviço escuta em ``127.0.0.1`` e exige Basic — o navegador não tem a
  senha (nem deve ter);
* a SPA usa caminhos absolutos (``/_assets/...``) e SSE em ``/api/event``;
  servir na própria origem (porta 8002) evita reescrever o bundle;
* o CSS injetado usa ``style-src 'unsafe-inline'`` do próprio CSP do motor,
  então não é preciso afrouxar a política de scripts.

Compatibilidade: HTTP/1.1, SSE (streaming em chunks) e WebSocket (túnel).
"""
from __future__ import annotations

import base64
import gzip
import http.client
import json
import os
import queue
import select
import socket
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .constants import (
    ACTIVE_SESSION_FILE,
    CURRENT_SESSION_FILE,
    FOCUS_FILE,
    WEB_FOCUS_FILE,
)

OCWEB_PORT: int = 8002
UPSTREAM_HOST: str = "127.0.0.1"

_THEME = """<style id="ufvai-ocweb-theme">
/* v0.7.11-web — paleta UFVAI (navy + dourado + creme) sobre os tokens do motor */
:root{
  --v2-background-bg-base:#f6f5f0!important;
  --v2-background-bg-deep:#efece4!important;
  --v2-background-bg-layer-01:#ffffff!important;
  --v2-background-bg-layer-02:#f4f2ec!important;
  --v2-background-bg-layer-03:#ebe7dd!important;
  --v2-text-text-base:#23282c!important;
  --v2-text-text-muted:#5f6468!important;
  --v2-text-text-faint:#8b8f92!important;
  --v2-border-border-base:#ddd8cc!important;
  --v2-border-border-muted:#e7e2d6!important;
  --v2-text-text-accent:#8a6d33!important;
  --v2-icon-icon-accent:#8a6d33!important;
  --v2-background-bg-accent:#8a6d33!important;
}
html{background-color:#f6f5f0!important}
html[data-color-scheme="dark"]{
  --v2-background-bg-base:#111518!important;
  --v2-background-bg-deep:#0d0f10!important;
  --v2-background-bg-layer-01:#161b1e!important;
  --v2-background-bg-layer-02:#1b2125!important;
  --v2-background-bg-layer-03:#222a2f!important;
  --v2-text-text-base:#f2f1ea!important;
  --v2-text-text-muted:#a8a49a!important;
  --v2-text-text-faint:#7d7a72!important;
  --v2-border-border-base:#2a3136!important;
  --v2-border-border-muted:#20262a!important;
  --v2-text-text-accent:#d9b45c!important;
  --v2-icon-icon-accent:#d9b45c!important;
  --v2-background-bg-accent:#b29149!important;
  background-color:#0d0f10!important;
}
html::before{content:"";position:fixed;top:0;left:0;right:0;height:3px;
  z-index:2147483647;pointer-events:none;
  background:linear-gradient(90deg,#1e2a34 0%,#1e2a34 58%,#b29149 58%,#b29149 100%)}
body{font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif!important}
.ufvai-oc-badge{position:fixed;left:12px;bottom:10px;z-index:2147483647;
  display:flex;align-items:center;gap:5px;padding:5px 9px;border-radius:999px;
  background:rgba(13,15,16,.82);border:1px solid rgba(178,145,73,.5);
  color:#f2f1ea;font:600 10px/1 "Segoe UI",system-ui,sans-serif;
  letter-spacing:.08em;opacity:.9;pointer-events:none;
  box-shadow:0 4px 14px rgba(0,0,0,.25);backdrop-filter:blur(6px)}
.ufvai-oc-badge b{color:#d9b45c;font-weight:800}
</style>"""

_BADGE = (
    '<div class="ufvai-oc-badge" title="UFVAI · OpenCode web">'
    "<span>UFV</span><b>AI</b></div>"
)

_BLOCKED_HEADERS = {
    "transfer-encoding", "content-length", "connection", "content-encoding",
    "proxy-connection", "keep-alive",
}
_SKIP_REQUEST_HEADERS = {
    "host", "authorization", "accept-encoding", "connection",
    "proxy-connection", "content-length",
}


# ── descoberta do serviço ─────────────────────────────────────

def service_file() -> Path:
    """Caminho do ``service.json`` do OpenCode (XDG, HOME ou /root)."""
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        candidate = Path(xdg) / "opencode" / "service.json"
        if candidate.exists():
            return candidate
    home = Path(os.path.expanduser("~")) / ".local" / "state" / "opencode" / "service.json"
    if home.exists():
        return home
    return Path("/root/.local/state/opencode/service.json")


def service_info() -> tuple[str, int, str]:
    """(host, porta, senha) do serviço em execução; ``(host, 0, '')`` se ausente."""
    try:
        data = json.loads(service_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UPSTREAM_HOST, 0, ""
    url = str(data.get("url") or "")
    port = 0
    if ":" in url:
        try:
            port = int(url.rsplit(":", 1)[1].strip("/"))
        except ValueError:
            port = 0
    return UPSTREAM_HOST, port, str(data.get("password") or "")


def _basic(password: str) -> str:
    raw = f"opencode:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _inject_html(data: bytes, session_id: str = "") -> bytes:
    text = data.decode("utf-8", errors="replace")
    text = text.replace(
        "<title data-sm>OpenCode</title>",
        "<title data-sm>UFVAI · OpenCode</title>",
    )
    if "</head>" in text:
        text = text.replace("</head>", _THEME + "</head>", 1)
    if "</body>" in text:
        text = text.replace("</body>", _BOOT_TAG + _BADGE + "</body>", 1)
    return text.encode("utf-8")



_BOOT_JS = """(function(){
  try{var f=window.fetch;window.fetch=function(u,o){o=o||{};if(o.credentials===undefined||o.credentials==="omit")o.credentials="same-origin";return f.call(this,u,o)}}catch(e){}
  function ufvaiTheme(t){
    t=(t==="light")?"light":"dark";
    try{localStorage.setItem("opencode-color-scheme",t);
      window.dispatchEvent(new StorageEvent("storage",{key:"opencode-color-scheme",newValue:t,storageArea:localStorage}));
    }catch(e){}
    try{document.documentElement.setAttribute("data-color-scheme",t);document.documentElement.style.colorScheme=t;}catch(e){}
  }
  try{var _qt=new URLSearchParams(location.search).get("theme");if(_qt)ufvaiTheme(_qt.indexOf("light")>=0?"light":"dark");}catch(e){}
  window.addEventListener("message",function(e){var d=e.data||{};if(d&&d.type==="ufvai-theme")ufvaiTheme(d.theme);});
  function b64(s){return btoa(unescape(encodeURIComponent(s))).replace(/\\+/g,"-").replace(/\\//g,"_").replace(/=+$/,"")}
  function key(){var a=document.querySelector('a[href*="/server/"][href*="/session/"]');if(!a)return "";var m=(a.getAttribute("href")||"").match(/\\/server\\/([^\\/]+)\\/session\\//);return m?m[1]:""}
  function catalog(cb){fetch("/__ufvai/catalog",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(d){cb(d||{ready:true})}).catch(function(){cb({ready:true})})}
  function whenReady(cb,t){
    catalog(function(d){
      if(d&&d.ready)return cb(true);
      if(t<=0)return cb(false);
      setTimeout(function(){whenReady(cb,t-1)},600);
    });
  }
  // v0.7.11-web9: a TUI publica a sessão que está exibindo; o proxy faz
  // push por SSE (/__ufvai/live) e a web troca na hora — sem polling e sem
  // inferir a sessão: é exatamente o que o terminal mostra.
  function curSid(){
    var m=location.pathname.match(/^\\/server\\/[^\\/]+\\/session\\/([^\\/]+)/);
    return m?m[1]:"";
  }
  function canNav(){
    var ed=document.querySelector('[contenteditable="true"][aria-label="Prompt"]');
    if(ed&&(ed.textContent||"").trim())return false;
    var body=document.body.innerText||"";
    if(/\\b(Working|Trabalhando)\\b/.test(body))return false;
    return true;
  }
  function navTo(sid){
    var m=location.pathname.match(/^(\\/server\\/[^\\/]+)\\/session\\//);
    if(!m||!sid||sid===curSid())return;
    try{
      var a=document.querySelector('a[href*="/session/'+sid+'"]');
      if(a){a.click();return}
    }catch(e){}
    location.replace(m[1]+"/session/"+sid);
  }
  var _live=null;
  function startLive(){
    if(!curSid()||typeof window.EventSource!=="function")return false;
    try{
      if(_live){try{_live.close()}catch(e){}}
      _live=new window.EventSource("/__ufvai/live");
      var _first=true;
      _live.onmessage=function(ev){
        var d=null;try{d=JSON.parse(ev.data)}catch(e){return}
        // O 1º foco é o estado atual da TUI: ao ABRIR a página, a URL da web
        // é a intenção do usuário e ela reporta o foco ao terminal. Só os
        // focos seguintes (trocas reais na TUI) navegam a web.
        if(_first){_first=false;return}
        if(!d||!d.sid||d.sid===curSid()||!canNav())return;
        navTo(d.sid);
      };
    }catch(e){return false}
    return true;
  }
  function liveOk(){try{return !!_live&&_live.readyState===1}catch(e){return false}}
  startLive();
  if(window.addEventListener)window.addEventListener("pageshow",function(){startLive()});
  // Reserva: sem push (EventSource indisponível), consulta a cada 2,5 s.
  setInterval(function(){
    if(!curSid()||liveOk())return;
    if(!_live||_live.readyState===2)startLive();
    if(liveOk())return;
    fetch("/__ufvai/session?fallback=1",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(d){
      if(d&&d.active&&d.active!==curSid()&&d.active_age_ms<30000&&canNav())navTo(d.active);
    }).catch(function(){});
  },2500);
  // v0.7.11-web9: web → terminal — o plugin da TUI segue este foco.
  var _reported=location.pathname,_lastSid=curSid(),_forceReport=true;
  function reportFocus(){
    var sid=curSid();
    if(!sid||(!_forceReport&&location.pathname===_reported&&sid===_lastSid))return;
    _forceReport=false;_reported=location.pathname;_lastSid=sid;
    try{
      fetch("/__ufvai/focus",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({sid:sid,ts:Date.now(),source:"web"}),cache:"no-store"});
    }catch(e){}
  }
  setInterval(reportFocus,400);
  setTimeout(function(){_forceReport=true;reportFocus();},900);
  // Sessão: espera o catálogo de provedores/modelos antes de navegar.
  var n=0,t=setInterval(function(){
    n++;
    if(location.pathname!=="/"){clearInterval(t);return}
    var k=key();if(!k&&n>=6)k=b64(location.origin);
    if(!k){if(n>40)clearInterval(t);return}
    clearInterval(t);
    fetch("/__ufvai/session?fallback=1",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(d){
      var go=function(){ if(d&&d.sid)location.replace("/server/"+k+"/session/"+d.sid); };
      if(d&&d.sid)whenReady(go,20); else go();
    }).catch(function(){});
  },700);
  // Numa sessão aberta direto: se o catálogo NÃO estava pronto no load e
  // ficou pronto depois, recarrega UMA vez para a SPA buscar os modelos.
  if(/^\\/server\\/[^\\/]+\\/session\\//.test(location.pathname)){
    catalog(function(d0){
      if(d0&&d0.ready)return;
      whenReady(function(ok){
        if(!ok)return;
        try{
          var k="ufvai.catalog.reload."+location.pathname;
          if(sessionStorage.getItem(k))return;
          sessionStorage.setItem(k,"1");
          setTimeout(function(){location.reload()},400);
        }catch(e){}
      },20);
    });
  }
})();"""


_BOOT_TAG = '<script src="/__ufvai/boot.js"></script>'


def current_session() -> str:
    """Sessão que a interface deve abrir (gravada por launch_app)."""
    try:
        return Path(CURRENT_SESSION_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _session_exists(host: str, port: int, password: str, sid: str) -> bool:
    if not sid:
        return False
    conn = http.client.HTTPConnection(host, port, timeout=3)
    try:
        conn.request("GET", f"/api/session/{sid}",
                     headers={"Authorization": _basic(password)})
        resp = conn.getresponse()
        resp.read()
        return resp.status == 200
    except OSError:
        return False
    finally:
        conn.close()


def _api_json(path: str, timeout: float = 5.0):
    """GET JSON no serviço do OpenCode (``None`` em falha)."""
    host, port, password = service_info()
    if not port:
        return None
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(
            "GET",
            path,
            headers={"Authorization": _basic(password), "Accept": "application/json"},
        )
        resp = conn.getresponse()
        data = resp.read()
        if resp.status != 200:
            return None
        return json.loads(data.decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    finally:
        conn.close()


# v0.7.11-web8: fecha a 1ª conexão SSE uma vez para forçar um handshake
# real depois que o listener da SPA já está registrado.
_CLOSE_FIRST_SSE = float(os.environ.get("UFVAI_TEST_CLOSE_FIRST_SSE", "1.0") or 0)
_CLOSE_ONCE_LOCK = threading.Lock()
_CLOSE_ONCE_DONE = False
_RESP_CACHE: dict = {}
_RESP_LOCK = threading.Lock()
_LAST_SESSION_WRITTEN = {"sid": None}
_LAST_SESSION_LOCK = threading.Lock()


def _cache_key(path: str) -> str:
    """Chave estável por endpoint + diretório (``+`` e ``%20`` são iguais)."""
    parsed = urlparse(path)
    directory = parse_qs(parsed.query).get("location[directory]", [""])[0]
    return f"{parsed.path}|{directory}"


def _cache_get(key: str, port: int, ttl: float = 180.0):
    now = time.time()
    with _RESP_LOCK:
        item = _RESP_CACHE.get(key)
        if not item:
            return None
        ts, cached_port, data, ctype = item
        if cached_port != port or now - ts > ttl:
            return None
        return data, ctype


def _cache_put(key: str, port: int, data: bytes, ctype: str = "application/json") -> None:
    with _RESP_LOCK:
        if len(_RESP_CACHE) > 64:
            _RESP_CACHE.clear()
        _RESP_CACHE[key] = (time.time(), port, data, ctype)


def _api_bytes(path: str, timeout: float = 20.0) -> bytes:
    host, port, password = service_info()
    if not port:
        return b""
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(
            "GET", path,
            headers={"Authorization": _basic(password), "Accept": "application/json"},
        )
        resp = conn.getresponse()
        data = resp.read()
        return data if resp.status == 200 else b""
    except OSError:
        return b""
    finally:
        conn.close()


def prefetch_catalog(directory: str = "") -> None:
    """Pré-busca modelos/provedores (escopo do projeto + global) e cacheia.

    O *sync* da SPA tem timeout de 15 s. Servir do cache garante que o
    primeiro carregamento não dependa da latência do motor/Drive.
    """
    port = service_info()[1]
    if not port:
        return
    scoped = (
        "?location%5Bdirectory%5D=" + quote(directory, safe="")
        if directory else ""
    )
    for kind in ("model", "provider"):
        for query in (scoped, ""):
            raw = _api_bytes(f"/api/{kind}{query}")
            if not raw:
                continue
            try:
                json.loads(raw)
            except ValueError:
                continue
            _cache_put(f"/api/{kind}|{directory if query else ''}", port, raw)


_CATALOG_CACHE: dict = {"ts": 0.0, "data": {"ready": False, "models": 0, "providers": 0}}
_CATALOG_LOCK = threading.Lock()
_GLOBAL_ROWS: dict = {"ts": 0.0, "model": None, "provider": None}
_GLOBAL_LOCK = threading.Lock()


def _global_rows(kind: str, ttl: float = 30.0):
    """Lista global (sem ``location``) de modelos/provedores, com cache.

    A SPA consulta ``/api/model?location[directory]=...``. Em alguns
    ambientes o recorte do projeto volta vazio (config local), embora o
    catálogo global esteja cheio. Guardamos o global para o fallback.
    """
    if kind not in ("model", "provider"):
        return None
    now = time.time()
    with _GLOBAL_LOCK:
        cached = _GLOBAL_ROWS.get(kind)
        if cached is not None and now - float(_GLOBAL_ROWS["ts"]) < ttl:
            return cached
    payload = _api_json(f"/api/{kind}", timeout=15.0)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    with _GLOBAL_LOCK:
        _GLOBAL_ROWS[kind] = rows
        _GLOBAL_ROWS["ts"] = now
    return rows


def _catalog_response(kind: str, raw: bytes, status: int) -> tuple[bytes, int]:
    """Garante uma lista válida de modelos/provedores para a SPA.

    Se o recorte do projeto vier vazio, inválido ou com erro, devolve o
    catálogo global (a SPA não tem fallback próprio e deixaria o seletor e a
    lista de provedores em branco).
    """
    global_rows = None
    if status != 200:
        global_rows = _global_rows(kind)
        if global_rows:
            return json.dumps({"data": global_rows}).encode("utf-8"), 200
        return raw, status
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        global_rows = _global_rows(kind)
        if global_rows:
            return json.dumps({"data": global_rows}).encode("utf-8"), 200
        return raw, status
    if not isinstance(payload, dict):
        return raw, status
    rows = payload.get("data")
    if isinstance(rows, list) and rows:
        return raw, status
    global_rows = _global_rows(kind, ttl=15.0)
    if not global_rows:
        return raw, status
    payload["data"] = global_rows
    try:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8"), status
    except ValueError:
        return raw, status



def catalog(force: bool = False, ttl: float = 5.0) -> dict:
    """Estado do catálogo do motor: provedores e modelos já carregados.

    A SPA consulta ``/api/model`` e ``/api/provider`` ao abrir a sessão. Se o
    motor ainda estiver subindo, a resposta pode vir vazia e o seletor de
    modelos fica em branco até um recarregamento. O ``boot.js`` usa este
    endpoint para esperar o catálogo antes de navegar.
    """
    now = time.time()
    with _CATALOG_LOCK:
        if not force and now - float(_CATALOG_CACHE["ts"]) < ttl:
            return dict(_CATALOG_CACHE["data"])
    project = _api_json("/api/project")
    prows = project if isinstance(project, list) else (
        project.get("data") if isinstance(project, dict) else None
    )
    directory = ""
    if isinstance(prows, list) and prows and isinstance(prows[0], dict):
        directory = str(prows[0].get("canonical") or prows[0].get("worktree") or "")
    query = "?location%5Bdirectory%5D=" + quote(directory, safe="") if directory else ""
    models = _api_json(f"/api/model{query}", timeout=12) if query else None
    scoped_count = len((models.get("data") if isinstance(models, dict) else None) or [])
    if not models or not scoped_count:
        models = _api_json("/api/model", timeout=12)
    providers = _api_json(f"/api/provider{query}", timeout=8) if query else None
    if not providers:
        providers = _api_json("/api/provider", timeout=8)
    rows = models.get("data") if isinstance(models, dict) else None
    provs = providers.get("data") if isinstance(providers, dict) else None
    data = {
        "ready": bool(rows),
        "models": len(rows or []),
        "scoped_models": scoped_count,
        "providers": len(provs or []),
        "project": directory,
        "upstream": f"http://{service_info()[0]}:{service_info()[1]}",
    }
    with _CATALOG_LOCK:
        _CATALOG_CACHE.update(ts=now, data=data)
    try:
        port = service_info()[1]
        if isinstance(models, dict) and models.get("data"):
            key = _cache_key(f"/api/model{query}" if query else "/api/model")
            _cache_put(key, port, json.dumps(models, ensure_ascii=False).encode("utf-8"))
        if isinstance(providers, dict) and providers.get("data"):
            key = _cache_key(f"/api/provider{query}" if query else "/api/provider")
            _cache_put(key, port, json.dumps(providers, ensure_ascii=False).encode("utf-8"))
    except (OSError, ValueError):
        pass
    return dict(data)


def latest_session() -> str:
    """Sessão usada pelo terminal: ativa ou a mais recente."""
    active = _api_json("/api/session/active")
    data = active.get("data") if isinstance(active, dict) else None
    if isinstance(data, dict):
        for sid, info in data.items():
            if not isinstance(info, dict):
                continue
            if info.get("type") in ("running", "busy", "pending"):
                return str(sid)
    listing = _api_json("/api/session?limit=1&order=desc")
    rows = listing.get("data") if isinstance(listing, dict) else None
    if isinstance(rows, list) and rows:
        return str(rows[0].get("id") or "")
    return ""


# ── foco da TUI ↔ web (v0.7.11-web9) ─────────────────────────
# A TUI (plugin ufvai-sync) grava a sessão que está exibindo em
# ``FOCUS_FILE``. Um observador lê o arquivo e faz *push* imediato para as
# páginas abertas por ``/__ufvai/live`` — sem polling de 2,5 s e sem inferir
# a sessão por eventos: é o mesmo dado que a TUI mostra na tela.
_LIVE_SUBS: set = set()
_LIVE_LOCK = threading.Lock()
_FOCUS_STOP = threading.Event()


def read_focus() -> dict:
    """Foco publicado pela TUI (``{}`` se ausente/ inválido)."""
    try:
        raw = Path(FOCUS_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def write_web_focus(sid: str) -> bool:
    """Grava o foco escolhido na web (o plugin da TUI segue)."""
    sid = str(sid or "").strip()
    if not sid:
        return False
    try:
        tmp = f"{WEB_FOCUS_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"sid": sid, "ts": int(time.time() * 1000), "source": "web"}, fh)
        os.replace(tmp, WEB_FOCUS_FILE)
        return True
    except OSError:
        return False


def _publish_live(payload: dict) -> None:
    msg = json.dumps(payload, ensure_ascii=False)
    with _LIVE_LOCK:
        subs = list(_LIVE_SUBS)
    for sub in subs:
        try:
            sub.put_nowait(msg)
        except Exception:  # noqa: BLE001 — fila cheia: a próxima atualiza
            pass


def _watch_focus() -> None:
    """Observa ``FOCUS_FILE`` (0,25 s) e publica mudanças de sessão."""
    last = ""
    while not _FOCUS_STOP.is_set():
        data = read_focus()
        sid = str(data.get("sid") or "").strip()
        if sid and sid != last:
            last = sid
            _remember_session(sid)
            _publish_live(
                {
                    "sid": sid,
                    "ts": data.get("ts") or int(time.time() * 1000),
                    "source": data.get("source") or "tui",
                }
            )
        _FOCUS_STOP.wait(0.15)


_SYNC_EVENTS = {
    "session.created",
    "session.viewed",
    "session.execution.started",
    "session.model.selected",
}


def _remember_session(sid: str) -> None:
    sid = str(sid or "").strip()
    if not sid:
        return
    with _LAST_SESSION_LOCK:
        if _LAST_SESSION_WRITTEN["sid"] == sid:
            return
        _LAST_SESSION_WRITTEN["sid"] = sid
    try:
        tmp = f"{CURRENT_SESSION_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(sid)
        os.replace(tmp, CURRENT_SESSION_FILE)
    except OSError:
        pass


def _take_close_once() -> bool:
    global _CLOSE_ONCE_DONE
    with _CLOSE_ONCE_LOCK:
        if _CLOSE_ONCE_DONE:
            return False
        _CLOSE_ONCE_DONE = True
        return True


def _rearm_close_once() -> None:
    """Cada documento HTML (page load) rearma o reconnect do SSE."""
    global _CLOSE_ONCE_DONE
    with _CLOSE_ONCE_LOCK:
        _CLOSE_ONCE_DONE = False


def current_active() -> tuple[str, int]:
    """Sessão em execução ativa e idade (ms) do início."""
    try:
        data = json.loads(Path(ACTIVE_SESSION_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", 0
    if not isinstance(data, dict):
        return "", 0
    sid = str(data.get("sid") or "").strip()
    try:
        ts = float(data.get("ts") or 0)
    except (TypeError, ValueError):
        ts = 0.0
    age = int((time.time() - ts) * 1000) if ts else 0
    return sid, max(age, 0)


def _remember_active(sid: str) -> None:
    sid = str(sid or "").strip()
    if not sid:
        return
    try:
        tmp = f"{ACTIVE_SESSION_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"sid": sid, "ts": time.time()}, fh)
        os.replace(tmp, ACTIVE_SESSION_FILE)
    except OSError:
        pass


def _rename_session(sid: str, title: str = "UFVAI") -> bool:
    """Renomeia a sessão no motor (título exibido pela SPA)."""
    sid = str(sid or "").strip()
    if not sid:
        return False
    host, port, password = service_info()
    if not port:
        return False
    body = json.dumps({"title": title}).encode("utf-8")
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(
            "PATCH",
            f"/api/session/{sid}",
            body=body,
            headers={
                "Authorization": _basic(password),
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        resp.read()
        return resp.status < 300
    except OSError:
        return False
    finally:
        conn.close()


def _rename_new_session_soon(sid: str, delay: float = 1.2) -> None:
    """Confere o título de uma sessão recém-criada (inclusive pela TUI)."""
    time.sleep(delay)
    info = _api_json(f"/api/session/{sid}")
    data = info.get("data") if isinstance(info, dict) else None
    if not isinstance(data, dict):
        return
    title = str(data.get("title") or "").strip()
    if not title or title.lower() == "opencode":
        _rename_session(sid)


def _brand_new_session(raw: bytes) -> tuple[bytes, str]:
    """Troca título nulo/``opencode`` por ``UFVAI`` no POST /api/session.

    Devolve o corpo (possivelmente reescrito) e o id da sessão criada.
    """
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return raw, ""
    if not isinstance(payload, dict):
        return raw, ""
    info = payload.get("data")
    if not isinstance(info, dict):
        return raw, ""
    sid = str(info.get("id") or "")
    title = str(info.get("title") or "").strip()
    if sid and (not title or title.lower() == "opencode"):
        info["title"] = "UFVAI"
        try:
            return json.dumps(payload, ensure_ascii=False).encode("utf-8"), sid
        except ValueError:
            return raw, sid
    return raw, ""



def _sync_session_from_event(chunk: bytes) -> None:
    """Persiste a sessão ativa vista no SSE (terminal ↔ web).

    O terminal e a SPA usam o mesmo motor; quando o usuário cria/troca de
    sessão na TUI, o evento chega aqui e o próximo boot/reload da web abre
    a mesma conversa.
    """
    try:
        text = chunk.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return
    for block in text.split("\n\n"):
        if not any(ev in block for ev in _SYNC_EVENTS):
            continue
        line = next(
            (ln for ln in block.splitlines() if ln.startswith("data: ")), None
        )
        if not line:
            continue
        try:
            payload = json.loads(line[6:])
        except ValueError:
            continue
        if payload.get("type") not in _SYNC_EVENTS:
            continue
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            continue
        sid = data.get("sessionID")
        if not sid and isinstance(data.get("session"), dict):
            sid = data["session"].get("id")
        if sid:
            _remember_session(str(sid))
            if payload.get("type") == "session.execution.started":
                _remember_active(str(sid))
            if payload.get("type") == "session.created":
                threading.Thread(
                    target=_rename_new_session_soon, args=(str(sid),), daemon=True
                ).start()




# ── proxy HTTP/SSE/WebSocket ─────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "UFVAI-OCWeb/0.7.11"

    def log_message(self, *_args):  # silencioso (o wrapper já tem log)
        pass

    def _upstream(self) -> tuple[str, int, str]:
        host, port, password = service_info()
        if not port:
            raise ConnectionError(
                "serviço do OpenCode sem service.json — aguardando o motor subir"
            )
        return host, port, password

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        return self.rfile.read(length) if length > 0 else None

    def _forward_headers(self, password: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            if key.lower() in _SKIP_REQUEST_HEADERS:
                continue
            headers[key] = value
        headers["Authorization"] = _basic(password)
        headers["Accept-Encoding"] = "identity"
        headers["Connection"] = "close"
        return headers

    # WebSocket: túnel cru (a SPA usa SSE para o chat; o WS cobre o PTY)
    def _websocket(self, host: str, port: int, password: str) -> None:
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            self.send_error(502, "OpenCode indisponível")
            return
        lines = [f"GET {self.path} HTTP/1.1", f"Host: {host}:{port}"]
        for key, value in self.headers.items():
            if key.lower() in {"host", "authorization", "connection"}:
                continue
            lines.append(f"{key}: {value}")
        lines.append(f"Authorization: {_basic(password)}")
        lines.append("Connection: Upgrade")
        request = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1", "replace")
        try:
            upstream.sendall(request)
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 65536:
                chunk = upstream.recv(4096)
                if not chunk:
                    break
                head += chunk
            self.wfile.write(head)
            self.wfile.flush()
            sockets = [self.connection, upstream]
            while True:
                read, _, _ = select.select(sockets, [], [], 60)
                if not read:
                    continue
                for sock in read:
                    data = sock.recv(65536)
                    if not data:
                        return
                    (upstream if sock is self.connection else self.connection).sendall(data)
        except OSError:
            pass
        finally:
            upstream.close()

    def _health(self) -> None:
        """``/__ufvai_ready`` — estado do proxy e do motor, com CORS.

        Serve de health-check independente do wrapper (o boot pode consultar
        direto a porta 8002) e evita depender de uma rota ``/api/*`` que o
        motor possa reivindicar no futuro.
        """
        host, port, _ = service_info()
        body = json.dumps(
            {
                "ready": bool(port) and ready(self.server.server_address[1], timeout=0.25),
                "proxy": "ufvai-ocweb",
                "upstream": f"http://{host}:{port}" if port else "",
                "pid": os.getpid(),
            }
        ).encode("utf-8")
        self.send_response(200 if port else 503)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _boot_js(self) -> None:
        body = _BOOT_JS.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _catalog_info(self) -> None:
        body = json.dumps(catalog()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _diag(self) -> None:
        """Diagnóstico de provedores/modelos (escopo do projeto × global)."""
        project = _api_json("/api/project")
        rows = project if isinstance(project, list) else (
            project.get("data") if isinstance(project, dict) else None
        )
        directory = ""
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            directory = str(rows[0].get("canonical") or rows[0].get("worktree") or "")
        query = "?location%5Bdirectory%5D=" + quote(directory, safe="") if directory else ""
        model_scoped = _api_json(f"/api/model{query}", timeout=12)
        provider_scoped = _api_json(f"/api/provider{query}", timeout=8)
        model_global = _api_json("/api/model", timeout=12)
        provider_global = _api_json("/api/provider", timeout=8)

        def _count(payload):
            data = payload.get("data") if isinstance(payload, dict) else None
            return len(data) if isinstance(data, list) else -1

        body = json.dumps({
            "proxy": "ufvai-ocweb",
            "upstream": f"http://{service_info()[0]}:{service_info()[1]}",
            "project": directory,
            "model": {"scoped": _count(model_scoped), "global": _count(model_global)},
            "provider": {"scoped": _count(provider_scoped), "global": _count(provider_global)},
            "fallback": _count(model_scoped) in (0,) or _count(provider_scoped) in (0,),
            "focus": read_focus(),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _session_info(self) -> None:
        host, port, password = service_info()
        sid = current_session()
        source = "persisted"
        if not _session_exists(host, port, password, sid):
            sid = ""
        qs = parse_qs(urlparse(self.path).query)
        fallback = qs.get("fallback", ["0"])[0].lower() in ("1", "true", "yes")
        if not sid and fallback:
            # v0.7.11-web5: o terminal pode ter criado/trocado a sessão sem
            # reiniciar o ttyd. Cair para a sessão ativa/mais recente mantém
            # web e terminal na mesma conversa.
            sid = latest_session()
            source = "latest"
        active, active_age = current_active()
        body = json.dumps(
            {
                "sid": sid,
                "active": active,
                "active_age_ms": active_age,
                "source": source,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _live_stream(self) -> None:
        """SSE local: entrega o foco da TUI assim que ele muda."""
        sub: queue.Queue = queue.Queue(maxsize=64)
        with _LIVE_LOCK:
            _LIVE_SUBS.add(sub)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, no-transform")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def _send(payload: bytes) -> None:
            self.wfile.write(f"{len(payload):X}\r\n".encode() + payload + b"\r\n")
            self.wfile.flush()

        try:
            _send(b"retry: 1000\n\n")
            data = read_focus()
            sid = str(data.get("sid") or "").strip()
            if sid:
                _send(
                    b"data: "
                    + json.dumps(
                        {
                            "sid": sid,
                            "ts": data.get("ts") or 0,
                            "source": data.get("source") or "tui",
                        }
                    ).encode("utf-8")
                    + b"\n\n"
                )
            while True:
                try:
                    msg = sub.get(timeout=15)
                except queue.Empty:
                    _send(b": ping\n\n")
                    continue
                _send(b"data: " + str(msg).encode("utf-8") + b"\n\n")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _LIVE_LOCK:
                _LIVE_SUBS.discard(sub)

    def _web_focus(self) -> None:
        """A web informa a sessão que está exibindo (terminal segue)."""
        body = self._read_body() or b""
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            data = {}
        sid = str((data or {}).get("sid") or "").strip() if isinstance(data, dict) else ""
        ok = write_web_focus(sid)
        self.send_response(204 if ok else 400)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle(self, method: str) -> None:
        rota = self.path.split("?", 1)[0]
        if rota == "/__ufvai_ready":
            self._health()
            return
        if rota == "/__ufvai/boot.js":
            self._boot_js()
            return
        if rota == "/__ufvai/live":
            self._live_stream()
            return
        if rota == "/__ufvai/focus":
            self._web_focus()
            return
        if rota == "/__ufvai/session":
            self._session_info()
            return
        if rota == "/__ufvai/catalog":
            self._catalog_info()
            return
        if rota == "/__ufvai/diag":
            self._diag()
            return

        if self.headers.get("Upgrade", "").lower() == "websocket":
            host, port, password = self._upstream()
            self._websocket(host, port, password)
            return

        try:
            host, port, password = self._upstream()
        except ConnectionError as exc:
            body = (
                "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
                "<meta http-equiv=\"refresh\" content=\"3\">"
                "<title>UFVAI · OpenCode</title><style>"
                "body{margin:0;min-height:100vh;display:flex;align-items:center;"
                "justify-content:center;background:#0d0f10;color:#f2f1ea;"
                "font:14px/1.6 'Segoe UI',system-ui,sans-serif}"
                ".b{max-width:520px;padding:28px 32px;border:1px solid #2a3136;"
                "border-radius:16px;background:#111518}"
                "b{color:#d9b45c}small{color:#a8a49a;display:block;margin-top:8px}"
                "</style></head><body><div class=\"b\">"
                "<h2 style=\"margin:0 0 8px\">UFV<b>AI</b> · OpenCode</h2>"
                "<p>O motor do OpenCode ainda não está disponível.</p>"
                "<small>Esta página recarrega sozinha a cada 3 s. "
                "Se persistir, instale o motor com <b>ufvai --engine-install</b> "
                "(ou conclua o onboarding da chave).</small>"
                "</div></body></html>"
            ).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Retry-After", "3")
            self.end_headers()
            self.wfile.write(body)
            return

        body = self._read_body()
        rota_api = self.path.split("?", 1)[0]
        cache_key = _cache_key(self.path)
        if method in ("GET", "HEAD") and rota_api in ("/api/model", "/api/provider"):
            hit = _cache_get(cache_key, port)
            if hit:
                cached_data, cached_type = hit
                cached_gzip = False
                if (
                    len(cached_data) > 262144
                    and "gzip" in (self.headers.get("Accept-Encoding") or "").lower()
                ):
                    try:
                        cached_data = gzip.compress(cached_data, 6)
                        cached_gzip = True
                    except OSError:
                        cached_gzip = False
                self.send_response(200)
                self.send_header("Content-Type", cached_type or "application/json")
                self.send_header("Content-Length", str(len(cached_data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-UFVAI-Cache", "hit")
                if cached_gzip:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                self.end_headers()
                if method != "HEAD":
                    self.wfile.write(cached_data)
                return
        if method == "POST" and rota_api == "/api/session" and body:
            try:
                req = json.loads(body.decode("utf-8", "replace"))
            except ValueError:
                req = None
            if isinstance(req, dict):
                titulo = str(req.get("title") or "").strip()
                if not titulo or titulo.lower() == "opencode":
                    req["title"] = "UFVAI"
                    body = json.dumps(req, ensure_ascii=False).encode("utf-8")
        headers = self._forward_headers(password)
        conn = http.client.HTTPConnection(host, port, timeout=600)
        try:
            # v0.7.11-web5: uma tentativa extra cobre o reinício do motor
            # (service.json muda de porta) sem devolver 502 para a SPA.
            resp = None
            for attempt in range(2):
                try:
                    conn.request(method, self.path, body=body, headers=headers)
                    resp = conn.getresponse()
                    break
                except OSError:
                    try:
                        conn.close()
                    except OSError:
                        pass
                    if attempt == 0:
                        time.sleep(0.15)
                        conn = http.client.HTTPConnection(host, port, timeout=600)
                        continue
                    raise
            assert resp is not None
            ctype = (resp.getheader("Content-Type") or "").lower()

            if ctype.startswith("text/event-stream"):
                self.send_response(resp.status)
                for key, value in resp.getheaders():
                    if key.lower() in _BLOCKED_HEADERS:
                        continue
                    self.send_header(key, value)
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Cache-Control", "no-cache, no-store, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()
                self.close_connection = True
                tail = b""
                write_lock = threading.Lock()
                closed = False

                def _emit(payload: bytes) -> None:
                    nonlocal closed
                    with write_lock:
                        if closed:
                            return
                        self.wfile.write(
                            f"{len(payload):X}\r\n".encode() + payload + b"\r\n"
                        )
                        self.wfile.flush()
                        if not payload:
                            closed = True

                heartbeat_stop = threading.Event()

                def _heartbeat() -> None:
                    while not heartbeat_stop.wait(10.0):
                        try:
                            _emit(b": ufvai-ping\n\n")
                        except OSError:
                            return

                threading.Thread(
                    target=_heartbeat, name="ufvai-keepalive", daemon=True
                ).start()

                # v0.7.11-web8: no Colab o bundle da SPA pode carregar depois
                # do primeiro server.connected. Sem esse handshake a SPA não
                # dispara provider.sync/model.sync e o seletor/lista de
                # provedores ficam em branco até abrir as configurações.
                # Fechamos a PRIMEIRA conexão uma vez; a reconexão recebe um
                # handshake real quando o listener já existe.
                if _CLOSE_FIRST_SSE > 0 and _take_close_once():
                    def _force_reconnect() -> None:
                        nonlocal closed
                        time.sleep(_CLOSE_FIRST_SSE)
                        with write_lock:
                            if closed:
                                return
                            try:
                                self.wfile.write(b"0\r\n\r\n")
                                self.wfile.flush()
                            except OSError:
                                pass
                            closed = True
                        for obj in (self.connection, conn):
                            try:
                                obj.shutdown(socket.SHUT_RDWR)
                            except OSError:
                                pass
                            try:
                                obj.close()
                            except OSError:
                                pass

                    threading.Thread(
                        target=_force_reconnect, name="ufvai-reconnect", daemon=True
                    ).start()

                try:
                    while True:
                        chunk = resp.read1(4096)
                        if not chunk:
                            break
                        if tail or b'"type":"session.' in chunk:
                            buf = tail + chunk
                            if b"\n\n" in buf:
                                events, _, tail = buf.rpartition(b"\n\n")
                                _sync_session_from_event(events)
                                if len(tail) > 65536:
                                    tail = tail[-4096:]
                            else:
                                tail = buf[-65536:]
                        _emit(chunk)
                    _emit(b"")
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    heartbeat_stop.set()
                return

            data = resp.read()
            encoding = (resp.getheader("Content-Encoding") or "").lower().strip()
            if encoding in ("gzip", "x-gzip"):
                try:
                    data = gzip.decompress(data)
                except OSError:
                    pass
            elif encoding == "deflate":
                try:
                    data = zlib.decompress(data)
                except zlib.error:
                    try:
                        data = zlib.decompress(data, -zlib.MAX_WBITS)
                    except zlib.error:
                        pass
            created_sid = ""
            status_out = resp.status
            if method in ("GET", "HEAD") and rota_api in ("/api/model", "/api/provider"):
                data, status_out = _catalog_response(
                    rota_api.rsplit("/", 1)[-1], data, resp.status
                )
            if (
                method in ("GET", "HEAD")
                and rota_api in ("/api/model", "/api/provider")
                and status_out == 200
            ):
                _cache_put(cache_key, port, data)
            if method == "POST" and rota_api == "/api/session" and resp.status == 200:
                data, created_sid = _brand_new_session(data)
            if ctype.startswith("text/html") and resp.status == 200:
                _rearm_close_once()
                sid = current_session()
                if not _session_exists(host, port, password, sid):
                    sid = ""
                data = _inject_html(data, sid)

            # v0.7.11-web7: /api/model pode passar de 1 MB. Compactar reduz
            # o risco de o proxy do Colab truncar/estourar timeout.
            gzip_out = False
            if (
                rota_api in ("/api/model", "/api/provider")
                and len(data) > 262144
                and "gzip" in (self.headers.get("Accept-Encoding") or "").lower()
            ):
                try:
                    data = gzip.compress(data, 6)
                    gzip_out = True
                except OSError:
                    gzip_out = False

            self.send_response(status_out)
            for key, value in resp.getheaders():
                if key.lower() in _BLOCKED_HEADERS:
                    continue
                self.send_header(key, value)
            # v0.7.11-web5: API nunca deve vir do cache do navegador — um
            # /api/model vazio (motor subindo) ficaria "grudado" no reload.
            if self.path.startswith("/api/") or self.path.startswith("/__ufvai/"):
                self.send_header("Cache-Control", "no-store")
            if gzip_out:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(data)
            if created_sid:
                threading.Thread(
                    target=_rename_session, args=(created_sid,), daemon=True
                ).start()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError:
            try:
                self.send_error(502, "OpenCode indisponível")
            except OSError:
                pass
        finally:
            conn.close()

    do_GET = lambda self: self._handle("GET")  # type: ignore[assignment]
    do_POST = lambda self: self._handle("POST")  # type: ignore[assignment]
    do_PUT = lambda self: self._handle("PUT")  # type: ignore[assignment]
    do_PATCH = lambda self: self._handle("PATCH")  # type: ignore[assignment]
    do_DELETE = lambda self: self._handle("DELETE")  # type: ignore[assignment]
    do_HEAD = lambda self: self._handle("HEAD")  # type: ignore[assignment]
    do_OPTIONS = lambda self: self._handle("OPTIONS")  # type: ignore[assignment]


# ── ciclo de vida ────────────────────────────────────────────

_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()


class _Server(ThreadingHTTPServer):
    """Servidor do proxy com fila maior.

    A SPA dispara ~20 requisições em paralelo ao abrir uma sessão. O backlog
    padrão do ``socketserver`` (5) recusava conexões nesse pico — a SPA
    marcava "Can't reach this server" e algumas mensagens ficavam pendentes.
    """

    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def start(port: int = 8002) -> bool:
    """Sobe o proxy em ``0.0.0.0:<port>`` (idempotente)."""
    return _start(port)


def _start(port: int = 8002) -> bool:
    global _SERVER, _THREAD
    with _LOCK:
        if _SERVER is not None:
            return True
        try:
            server = _Server(("0.0.0.0", int(port)), _Handler)
            thread = threading.Thread(
                target=server.serve_forever,
                name="ufvai-ocweb",
                daemon=True,
            )
            thread.start()
            _SERVER, _THREAD = server, thread
            _FOCUS_STOP.clear()
            threading.Thread(
                target=_watch_focus, name="ufvai-focus", daemon=True
            ).start()
            return True
        except OSError:
            return False


def stop() -> None:
    global _SERVER, _THREAD
    with _LOCK:
        server, _SERVER = _SERVER, None
        _THREAD = None
    _FOCUS_STOP.set()
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except OSError:
            pass


def status() -> dict:
    host, port, _ = service_info()
    server = _SERVER
    return {
        "proxy_port": int(server.server_address[1]) if server else 0,
        "upstream": f"http://{host}:{port}" if port else "",
        "upstream_ready": bool(port),
        "running": bool(server),
    }


def ready(port: int = 8002, timeout: float = 0.4) -> bool:
    """Proxy no ar **e** serviço do OpenCode respondendo."""
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            pass
    except OSError:
        return False
    host, upstream, _ = service_info()
    if not upstream:
        return False
    try:
        with socket.create_connection((host, int(upstream)), timeout=timeout):
            return True
    except OSError:
        return False
