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
import re
import select
import socket
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

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


_SERVICE_CACHE: dict = {"key": None, "value": (UPSTREAM_HOST, 0, "")}


def service_info() -> tuple[str, int, str]:
    """(host, porta, senha) do serviço em execução; ``(host, 0, '')`` se ausente.

    v0.7.11-web10: o ``service.json`` é lido em *toda* requisição do proxy
    (dezenas por navegação). O cache por ``mtime``/tamanho elimina esse I/O
    sem esconder a troca de porta quando o motor reinicia.
    """
    path = service_file()
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return UPSTREAM_HOST, 0, ""
    cached = _SERVICE_CACHE.get("value")
    if _SERVICE_CACHE.get("key") == key and cached:
        return cached
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UPSTREAM_HOST, 0, ""
    url = str(data.get("url") or "")
    port = 0
    if ":" in url:
        try:
            port = int(url.rsplit(":", 1)[1].strip("/"))
        except ValueError:
            port = 0
    info = (UPSTREAM_HOST, port, str(data.get("password") or ""))
    _SERVICE_CACHE["key"] = key
    _SERVICE_CACHE["value"] = info
    return info


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


_BOOT_JS = r"""(function(){
  try{var f=window.fetch;window.fetch=function(u,o){
    o=o||{};
    if(o.credentials===undefined||o.credentials==="omit")o.credentials="same-origin";
    try{
      var _u=(typeof u==="string")?u:((u&&u.url)||"");
      if(_u.indexOf("/interrupt")>=0)window.__ufvaiLastInterrupt=Date.now();
    }catch(e){}
    return f.call(this,u,o)
  }}catch(e){}
  function ufvaiTheme(t){
    t=(t==="light")?"light":"dark";
    try{localStorage.setItem("opencode-color-scheme",t);
      window.dispatchEvent(new StorageEvent("storage",{key:"opencode-color-scheme",newValue:t,storageArea:localStorage}));
    }catch(e){}
    try{document.documentElement.setAttribute("data-color-scheme",t);document.documentElement.style.colorScheme=t;}catch(e){}
  }
  try{var _qt=new URLSearchParams(location.search).get("theme");if(_qt)ufvaiTheme(_qt.indexOf("light")>=0?"light":"dark");}catch(e){}
  window.addEventListener("message",function(e){var d=e.data||{};if(d&&d.type==="ufvai-theme")ufvaiTheme(d.theme);});
  try{performance.setResourceTimingBufferSize(1000)}catch(e){}

  function b64(s){return btoa(unescape(encodeURIComponent(s))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"")}
  function key(){var a=document.querySelector('a[href*="/server/"][href*="/session/"]');if(!a)return "";var m=(a.getAttribute("href")||"").match(/\/server\/([^\/]+)\/session\//);return m?m[1]:""}
  function catalog(cb){fetch("/__ufvai/catalog",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(d){cb(d||{ready:true})}).catch(function(){cb({ready:true})})}
  function whenReady(cb,t){
    catalog(function(d){
      if(d&&d.ready)return cb(true);
      if(t<=0)return cb(false);
      setTimeout(function(){whenReady(cb,t-1)},600);
    });
  }

  // ── rota da SPA ────────────────────────────────────────────────────────
  // A chave da rota é o base64url da PRÓPRIA origem (é assim que a SPA monta
  // os links). Usar a URL do motor deixa a sessão em branco.
  function curSid(){var m=location.pathname.match(/^\/server\/[^\/]+\/session\/([^\/?#]+)/);return m?m[1]:""}
  function originKey(){try{return b64(location.origin)}catch(e){return ""}}
  function routeBase(){var m=location.pathname.match(/^(\/server\/[^\/]+)\/session\//);return m?m[1]:""}
  function canNav(){
    // Só não troca com rascunho no prompt: o texto digitado seria perdido.
    var ed=document.querySelector('[contenteditable="true"][aria-label="Prompt"]');
    return !(ed&&(ed.textContent||"").trim());
  }
  function mainText(){var m=document.querySelector("main");return m?(m.innerText||""):""}

  // ── foco: ordem total decidida pelo servidor (seq) ─────────────────────
  // Cada troca (TUI ou web) chega com um seq. Aplica-se só o que é mais novo
  // que o último visto e que não coincide com a sessão na tela. Batimentos e o
  // snapshot de conexão só servem de referência: nunca revertem uma escolha.
  var _lastSeq=-1,_seeded=false,_pendingSid="",_echoSid="",_echoUntil=0,_reportedSid="";
  function seedSeq(n){if(typeof n==="number"&&n>_lastSeq)_lastSeq=n;_seeded=true}
  function applyFocus(ev){
    if(!ev||!ev.sid)return;
    if(!_seeded){seedSeq(ev.seq);return}
    if(typeof ev.seq==="number"){if(ev.seq<=_lastSeq)return;_lastSeq=ev.seq}
    if(ev.sid===curSid()){_pendingSid="";return}
    if(!canNav()){_pendingSid=ev.sid;return}   // rascunho: aplica quando esvaziar
    navTo(ev.sid);
  }
  function navTo(sid){
    if(!sid||sid===curSid())return false;
    var base=routeBase()||("/server/"+originKey());
    if(!base||base==="/server/")return false;
    // A troca vem do terminal: a navegação resultante não volta como foco.
    _echoSid=sid;_echoUntil=Date.now()+2000;
    var path=base+"/session/"+sid;
    if(routeBase()){
      try{
        // Rota interna da SPA, sem recarregar. Se nenhum nó do DOM mudar em
        // 1,5 s, a SPA ignorou o evento: recarrega UMA vez por sessão.
        var reacted=false,mo=null;
        try{
          mo=new MutationObserver(function(){reacted=true});
          mo.observe(document.body,{childList:true,subtree:true,characterData:true});
        }catch(e){}
        history.pushState({},"",path);
        window.dispatchEvent(new PopStateEvent("popstate",{state:{}}));
        setTimeout(function(){
          try{if(mo)mo.disconnect()}catch(e){}
          if(reacted||curSid()!==sid)return;
          var k="ufvai.navfb."+sid;
          try{if(sessionStorage.getItem(k))return;sessionStorage.setItem(k,"1")}catch(e){}
          if(canNav()){try{location.replace(path)}catch(e){}}
        },1500);
        return true;
      }catch(e){}
    }
    // Fora de uma sessão (lista de projetos): o próprio link da SPA resolve a rota.
    try{var a=document.querySelector('a[href*="/session/'+sid+'"]');if(a){a.click();return true}}catch(e){}
    try{location.replace(path)}catch(e){}
    return true;
  }

  // ── canal ao vivo: /__ufvai/live (SSE) ─────────────────────────────────
  var _live=null,_lastLive=0;
  function startLive(){
    if(typeof window.EventSource!=="function")return false;
    try{
      if(_live){try{_live.close()}catch(e){}}
      _live=new window.EventSource("/__ufvai/live");
      _live.onopen=function(){_lastLive=Date.now()};
      _live.onmessage=function(ev){
        _lastLive=Date.now();   // qualquer dado (inclusive o ping) prova que o canal está vivo
        var d=null;try{d=JSON.parse(ev.data)}catch(e){return}
        if(!d||d.type==="ping")return;
        if(d.type==="snapshot"){
          if(!_seeded){seedSeq(d.seq);return}
          applyFocus(d);
          return;
        }
        if(d.type==="focus")applyFocus(d);
      };
    }catch(e){return false}
    return true;
  }
  startLive();
  if(window.addEventListener)window.addEventListener("pageshow",function(){startLive()});

  // Reserva: consulta a cada 1,5 s, SEMPRE. O SSE é o caminho rápido, mas o
  // proxy do Colab pode manter o stream "aberto" sem entregar eventos; nesse
  // caso o canal parece vivo e a página ficaria parada. O seq descarta o que
  // já foi aplicado, então a consulta é idempotente e barata.
  // Usa só o foco ordenado (nunca a sessão "active", que puxava a página para
  // longe da escolhida).
  setInterval(function(){
    if(_pendingSid&&_pendingSid!==curSid()&&canNav()){var s=_pendingSid;_pendingSid="";navTo(s);return}
    if(!_live||_live.readyState===2)startLive();
    fetch("/__ufvai/session?fallback=1",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(d){
      if(d&&d.focus){if(!_seeded)seedSeq(d.focus.seq);else applyFocus(d.focus)}
    }).catch(function(){});
  },1500);

  // ── web → terminal ─────────────────────────────────────────────────────
  // Toda troca feita aqui é publicada na hora (pushState, replaceState,
  // popstate) e, como rede de segurança, a cada 1,2 s.
  function reportFocus(){
    var sid=curSid();
    if(!sid||sid===_reportedSid)return;
    _reportedSid=sid;
    if(sid===_echoSid&&Date.now()<_echoUntil){_echoSid="";return}   // eco do terminal
    try{
      fetch("/__ufvai/focus",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({sid:sid,ts:Date.now(),source:"web"}),cache:"no-store",keepalive:true});
    }catch(e){}
  }
  setInterval(reportFocus,1200);
  try{
    var _ps=history.pushState,_rs=history.replaceState;
    history.pushState=function(){var r=_ps.apply(this,arguments);try{reportFocus()}catch(e){}return r};
    history.replaceState=function(){var r=_rs.apply(this,arguments);try{reportFocus()}catch(e){}return r};
    window.addEventListener("popstate",function(){try{reportFocus()}catch(e){}});
  }catch(e){}
  reportFocus();   // primeira leitura: publica o que está na tela

  // ── botão Parar: rede de segurança ─────────────────────────────────────
  // O botão da SPA faz POST /api/session/<id>/interrupt?resume=true. Se essa
  // chamada não sair, mandamos a interrupção 600 ms depois (idempotente).
  function _stopFallback(ev){
    try{
      var el=ev.target;
      var btn=(el&&el.closest)?el.closest('button[aria-label="Stop"],button[aria-label="Parar"]'):null;
      if(!btn)return;
      var sid=curSid(); if(!sid)return;
      setTimeout(function(){
        if(Date.now()-(window.__ufvaiLastInterrupt||0)<900)return;
        fetch("/__ufvai/run-state?sid="+encodeURIComponent(sid),{cache:"no-store"})
          .then(function(r){return r.ok?r.json():null})
          .then(function(js){
            if(js&&js.running){
              try{
                fetch("/api/session/"+sid+"/interrupt?resume=true",{
                  method:"POST",headers:{"Content-Type":"application/json"},body:"{}",cache:"no-store"
                });
              }catch(e){}
            }else if(js&&!js.running){
              // Turno já terminou no servidor: o "Working" é estado preso.
              _unstuckReload(sid);
            }
          }).catch(function(){});
      },600);
    }catch(e){}
  }
  try{document.addEventListener("click",_stopFallback,true);}catch(e){}

  // Recarrega no máximo 1× a cada 2 min por sessão (o estado está no servidor).
  function _unstuckReload(sid){
    var k="ufvai.unstuck."+sid;
    try{
      var last=Number(sessionStorage.getItem(k)||0);
      if(Date.now()-last<120000)return;
      sessionStorage.setItem(k,String(Date.now()));
    }catch(e){}
    try{location.reload();}catch(e){}
  }

  // "Working" preso: só age quando o MOTOR diz que a sessão não está rodando
  // (/__ufvai/run-state usa /api/session/active), três vezes seguidas (~18 s).
  var _stuck=0;
  setInterval(function(){
    window.__ufvaiWatch=(window.__ufvaiWatch||0)+1;
    var sid=curSid(); if(!sid){_stuck=0;return}
    if(!/(?:Working|Trabalhando)/.test(mainText())){_stuck=0;return}
    var ed=document.querySelector('[contenteditable="true"][aria-label="Prompt"]');
    if(ed&&(ed.textContent||"").trim())return;      // usuário digitando: não mexer
    fetch("/__ufvai/run-state?sid="+encodeURIComponent(sid),{cache:"no-store"})
      .then(function(r){return r.ok?r.json():null})
      .then(function(js){
        if(!js||js.running){_stuck=0;return}          // o motor diz que está rodando
        _stuck++;
        window.__ufvaiStuck=_stuck;
        try{window.dispatchEvent(new Event("focus"));}catch(e){}
        if(_stuck<3)return;
        _stuck=0;
        _unstuckReload(sid);
      }).catch(function(){});
  },6000);

  // ── modelos ────────────────────────────────────────────────────────────
  // A SPA busca /api/model ao abrir a sessão. Se a lista não chegou (motor
  // subindo, evento server.connected perdido), recarrega UMA vez a cada 10 min.
  // Só age quando o servidor já tem modelos (há chave configurada).
  function modelsOk(count){
    try{
      var es=performance.getEntriesByType("resource");
      for(var i=es.length-1;i>=0;i--){
        if((es[i].name||"").indexOf("/api/model")<0)continue;
        var st=es[i].responseStatus;
        if(!st)return true;              // sem dado de status: não mexe
        if(st!==200)return false;
        // v0.8.0 (web15): 200 com corpo mínimo = catálogo vazio/truncado.
        // O proxy sabe que há modelos (count > 0), então a SPA ficou com uma
        // lista em branco e precisa de uma recarga.
        var size=Number(es[i].decodedBodySize||es[i].transferSize||0);
        if(count>0&&size>0&&size<4096)return false;
        return true;
      }
    }catch(e){return true}
    return false;                        // a SPA nunca pediu /api/model
  }
  if(/^\/server\/[^\/]+\/session\//.test(location.pathname)){
    setTimeout(function(){
      catalog(function(d){
        if(!d||!d.ready)return;          // sem modelos no servidor (ex.: sem chave)
        if(modelsOk(Number(d.models)||0))return;
        try{
          // Chave versionada: tentativas feitas por web13/web14 não podem
          // impedir a primeira recuperação depois da atualização.
          var reloadKey="ufvai.modelreload.v15."+location.pathname;
          var last=Number(sessionStorage.getItem(reloadKey)||0);
          if(Date.now()-last<600000)return;
          sessionStorage.setItem(reloadKey,String(Date.now()));
        }catch(e){}
        if(canNav()){try{location.reload()}catch(e){}}
      });
    },12000);
  }

  // ── início: "/" abre a sessão atual (espera o catálogo, sem bloquear) ──
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
})();"""


_BOOT_TAG = '<script src="/__ufvai/boot.js"></script>'


def current_session() -> str:
    """Sessão que a interface deve abrir (gravada por launch_app)."""
    try:
        return Path(CURRENT_SESSION_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


_EXISTS_CACHE: dict = {}
_EXISTS_LOCK = threading.Lock()
_EXISTS_TTL = 15.0


def _session_exists(host: str, port: int, password: str, sid: str) -> bool:
    """Existência da sessão (cache de 15 s).

    Chamada a cada HTML servido; sem cache virava uma ida ao motor dentro do
    caminho crítico do primeiro paint.
    """
    if not sid:
        return False
    key = (port, sid)
    now = time.time()
    with _EXISTS_LOCK:
        item = _EXISTS_CACHE.get(key)
        if item and now - item[0] < _EXISTS_TTL:
            return item[1]
    conn = http.client.HTTPConnection(host, port, timeout=3)
    ok = False
    try:
        conn.request("GET", f"/api/session/{sid}",
                     headers={"Authorization": _basic(password)})
        resp = conn.getresponse()
        resp.read()
        ok = resp.status == 200
    except OSError:
        ok = False
    finally:
        conn.close()
    with _EXISTS_LOCK:
        if len(_EXISTS_CACHE) > 256:
            _EXISTS_CACHE.clear()
        _EXISTS_CACHE[key] = (now, ok)
    return ok


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


def _catalog_json(path: str, timeout: float = 12.0, wait: float = 6.0):
    """Lê catálogo repetindo 503/lista vazia durante o aquecimento.

    O motor pode publicar ``service.json`` antes de terminar a descoberta de
    provedores/modelos. A SPA não repete uma resposta vazia, portanto o
    endpoint interno também precisa aguardar o catálogo real.
    """
    deadline = time.time() + wait
    last = None
    while True:
        last = _api_json(path, timeout=timeout)
        rows = last.get("data") if isinstance(last, dict) else None
        if isinstance(rows, list) and rows:
            return last
        if time.time() >= deadline:
            return last
        time.sleep(0.2)


# ── v0.7.11-web16: reparo de sessão ──────────────────────────────────────────
# Dois defeitos apareciam em conversas já carregadas:
#
# 1. a sessão ficava apontando para um modelo que ESTE ambiente não oferece
#    (provedor desconectado, modelo renomeado/retirado). A SPA mostrava
#    "modelo (unavailable)" e o envio morria em ``provider.no-route``;
# 2. a execução morria no meio (cota/erro do provedor) deixando
#    ``time.busy > time.idle``. A SPA continuava em "Trabalhando" e as
#    mensagens novas entravam na fila sem nunca serem entregues.
#
# O proxy corrige os dois sem tocar no binário do motor: repara o modelo na
# leitura da sessão e interrompe execuções que o próprio motor já não lista
# como ativas em ``/api/session/active``.
_SESSION_GET_RE = re.compile(r"^/api/session/(ses_[A-Za-z0-9]+)$")
_MODEL_KEYS_CACHE: dict = {"at": 0.0, "keys": frozenset()}
_MODEL_KEYS_LOCK = threading.Lock()
_MODEL_REPAIR_TRIED: dict[str, float] = {}
_MODEL_REPAIR_LOCK = threading.Lock()
_MODEL_REPAIR_TTL_S = 300.0
_MODEL_KEYS_TTL_S = 120.0
_SEEN_SESSIONS: dict[str, float] = {}
_SESSION_DIR: dict[str, str] = {}
_SEEN_LOCK = threading.Lock()
_RUNS_STOP = threading.Event()
_RUNS_LAST: dict[str, float] = {}
_RUNS_LOCK = threading.Lock()
_STUCK_RUN_S = 90.0
_STUCK_RUN_TTL_S = 120.0


def _model_keys() -> set[str]:
    """``{"provedor/modelo", ...}`` do catálogo atual (cache de 2 min)."""
    now = time.time()
    with _MODEL_KEYS_LOCK:
        if _MODEL_KEYS_CACHE["keys"] and now - float(_MODEL_KEYS_CACHE["at"]) < _MODEL_KEYS_TTL_S:
            return set(_MODEL_KEYS_CACHE["keys"])
    payload = _catalog_json("/api/model", timeout=8.0, wait=2.0)
    rows = payload.get("data") if isinstance(payload, dict) else None
    keys = {
        f"{row.get('providerID')}/{row.get('id')}"
        for row in (rows or [])
        if isinstance(row, dict) and row.get("providerID") and row.get("id")
    }
    if keys:
        with _MODEL_KEYS_LOCK:
            _MODEL_KEYS_CACHE["keys"] = frozenset(keys)
            _MODEL_KEYS_CACHE["at"] = now
    return keys


def _config_model_ref() -> dict | None:
    """Modelo padrão do ``/api/config`` como ``{providerID, id}``."""
    cfg = _api_json("/api/config", timeout=5.0)
    data = cfg.get("data") if isinstance(cfg, dict) else None
    model = str((data or {}).get("model") or "").strip()
    if "/" not in model:
        return None
    provider, _, model_id = model.partition("/")
    provider, model_id = provider.strip(), model_id.split("#")[0].strip()
    if not provider or not model_id:
        return None
    return {"providerID": provider, "id": model_id}


def _replacement_ref(provider_id: str, keys: set[str]) -> dict | None:
    """Melhor modelo substituto: mesmo provedor → padrão da config → 1º livre."""
    same = sorted(key for key in keys if key.startswith(f"{provider_id}/"))
    if same:
        return {"providerID": provider_id, "id": same[0].split("/", 1)[1]}
    default = _config_model_ref()
    if default and f"{default['providerID']}/{default['id']}" in keys:
        return default
    for key in sorted(keys):
        provider, _, model_id = key.partition("/")
        if provider and model_id:
            return {"providerID": provider, "id": model_id}
    return None


def _post_session_model(session_id: str, ref: dict) -> bool:
    """``POST /api/session/<id>/model`` no motor (``True`` se aceitou)."""
    host, port, password = service_info()
    if not port or not session_id or not ref:
        return False
    conn = http.client.HTTPConnection(host, port, timeout=6.0)
    try:
        body = json.dumps({"model": ref}).encode("utf-8")
        conn.request(
            "POST",
            f"/api/session/{session_id}/model{_location_query(session_id)}",
            body=body,
            headers={
                "Authorization": _basic(password),
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        resp.read()
        return 200 <= resp.status < 300
    except OSError:
        return False
    finally:
        conn.close()


def repair_session_model(data: bytes) -> bytes:
    """Troca o modelo da sessão quando ele não existe neste ambiente.

    Sessão com ``model: null`` fica como está: a SPA resolve o padrão da
    configuração (comportamento do motor). Só corrige o que está quebrado.
    """
    try:
        payload = json.loads(data.decode("utf-8", "replace"))
    except ValueError:
        return data
    row = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(row, dict):
        return data
    model = row.get("model") if isinstance(row.get("model"), dict) else {}
    provider = str(model.get("providerID") or "").strip()
    model_id = str(model.get("id") or "").strip()
    if not provider or not model_id:
        return data
    keys = _model_keys()
    if not keys or f"{provider}/{model_id}" in keys:
        return data
    session_id = str(row.get("id") or "").strip()
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    remember_session_dir(session_id, str(location.get("directory") or ""))
    now = time.time()
    with _MODEL_REPAIR_LOCK:
        if now - _MODEL_REPAIR_TRIED.get(session_id, 0.0) < _MODEL_REPAIR_TTL_S:
            return data
        _MODEL_REPAIR_TRIED[session_id] = now
        if len(_MODEL_REPAIR_TRIED) > 200:
            for key in sorted(_MODEL_REPAIR_TRIED, key=_MODEL_REPAIR_TRIED.get)[:100]:
                _MODEL_REPAIR_TRIED.pop(key, None)
    ref = _replacement_ref(provider, keys)
    if not ref or not _post_session_model(session_id, ref):
        return data
    row["model"] = dict(model)
    row["model"]["providerID"] = ref["providerID"]
    row["model"]["id"] = ref["id"]
    row["model"].pop("variant", None)
    try:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return data


def remember_seen_session(session_id: str) -> None:
    """Guarda as sessões que o navegador abriu (vigia de execução travada)."""
    sid = str(session_id or "").strip()
    if not sid.startswith("ses_"):
        return
    with _SEEN_LOCK:
        _SEEN_SESSIONS[sid] = time.time()
        if len(_SEEN_SESSIONS) > 60:
            for key in sorted(_SEEN_SESSIONS, key=_SEEN_SESSIONS.get)[:30]:
                _SEEN_SESSIONS.pop(key, None)
                _SESSION_DIR.pop(key, None)


def remember_session_dir(session_id: str, directory: str) -> None:
    """Diretório de trabalho da sessão (o motor exige ``location`` fora do cwd)."""
    sid = str(session_id or "").strip()
    directory = str(directory or "").strip()
    if not sid.startswith("ses_") or not directory:
        return
    with _SEEN_LOCK:
        _SESSION_DIR[sid] = directory


def _location_query(session_id: str) -> str:
    """``?location[directory]=…`` quando a sessão está fora do cwd do motor."""
    with _SEEN_LOCK:
        directory = _SESSION_DIR.get(str(session_id or ""))
    if not directory:
        return ""
    return "?location%5Bdirectory%5D=" + quote(directory, safe="")


def _active_session_ids() -> set[str]:
    active = _api_json("/api/session/active", timeout=6.0)
    rows = active.get("data") if isinstance(active, dict) else None
    if not isinstance(rows, dict):
        return set()
    return {str(key) for key in rows}


def _session_info(session_id: str) -> dict:
    info = _api_json(f"/api/session/{session_id}{_location_query(session_id)}", timeout=6.0)
    row = info.get("data") if isinstance(info, dict) else None
    return row if isinstance(row, dict) else {}


def _interrupt_session(session_id: str) -> bool:
    host, port, password = service_info()
    if not port:
        return False
    conn = http.client.HTTPConnection(host, port, timeout=6.0)
    try:
        conn.request(
            "POST",
            f"/api/session/{session_id}/interrupt{_location_query(session_id)}",
            body=b"{}",
            headers={
                "Authorization": _basic(password),
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        resp.read()
        return 200 <= resp.status < 300
    except OSError:
        return False
    finally:
        conn.close()


def unstick_sessions(now_ms: int | None = None) -> int:
    """Interrompe execuções que o motor não reconhece mais como ativas.

    ``busy > idle`` + ausente de ``/api/session/active`` = execução morta: a
    SPA fica em "Trabalhando" para sempre e as mensagens novas nunca saem da
    fila. Só age nesse caso (nunca numa execução real) e no máximo 1×/2 min
    por sessão.
    """
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    active = _active_session_ids()
    with _SEEN_LOCK:
        # Só conversas abertas nos últimos 30 min e, no máximo, 10 por ciclo.
        recentes = [
            sid
            for sid, visto in sorted(_SEEN_SESSIONS.items(), key=lambda kv: -kv[1])
            if now_ms / 1000.0 - visto < 1800.0
        ][:10]
    fixed = 0
    for session_id in recentes:
        if session_id in active:
            continue
        row = _session_info(session_id)
        if not row:
            continue
        times = row.get("time") if isinstance(row.get("time"), dict) else {}
        busy = int(times.get("busy") or 0)
        idle = int(times.get("idle") or 0)
        if not busy or busy <= idle:
            continue
        if now_ms - busy < _STUCK_RUN_S * 1000:
            continue
        with _RUNS_LOCK:
            if now_ms / 1000.0 - _RUNS_LAST.get(session_id, 0.0) < _STUCK_RUN_TTL_S:
                continue
            _RUNS_LAST[session_id] = now_ms / 1000.0
        if _interrupt_session(session_id):
            fixed += 1
    return fixed


def _watch_stuck_runs() -> None:
    """Vigia contínuo (15 s) das execuções mortas — ver ``unstick_sessions``."""
    while not _RUNS_STOP.is_set():
        try:
            unstick_sessions()
        except Exception:  # noqa: BLE001 — o vigia nunca derruba o proxy
            pass
        _RUNS_STOP.wait(15.0)


# v0.8.0 (web14b): atrasa a 1ª conexão SSE de cada documento HTML (~1,2 s)
# para o ``server.connected`` chegar depois de o listener da SPA existir.
# A versão anterior FECHAVA essa conexão logo na abertura: além de derrubar o
# stream, o evento que dispara provider.sync/model.sync se perdia e o seletor
# de modelos ficava vazio justamente no primeiro acesso (motor recém-iniciado).
_SSE_HANDSHAKE_DELAY_S = float(
    os.environ.get("UFVAI_SSE_HANDSHAKE_DELAY", "1.2") or 0
)
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


# v0.8.0 (web14): o catálogo (modelos/provedores) muda quando uma chave é salva
# ou o motor reinicia. O TTL antigo (180 s) servia listas velhas por 3 minutos;
# agora o cache também é invalidado pela identidade do motor (porta + mtime do
# service.json), que muda a cada reinício.
_CACHE_TTL_S: float = float(os.environ.get("UFVAI_CATALOG_TTL", "60") or 60)


def _engine_stamp() -> tuple:
    """Identidade do motor atual: (porta, mtime_ns do service.json)."""
    try:
        return (service_info()[1], service_file().stat().st_mtime_ns)
    except OSError:
        return (0, 0)


def _has_rows(raw: bytes) -> bool:
    """True se a resposta traz ``data`` com ao menos um item (lista vazia não é cacheada)."""
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return False
    rows = payload.get("data") if isinstance(payload, dict) else None
    return isinstance(rows, list) and len(rows) > 0


def _cache_get(key: str, port: int, ttl: float | None = None):
    now = time.time()
    ttl = _CACHE_TTL_S if ttl is None else ttl
    with _RESP_LOCK:
        item = _RESP_CACHE.get(key)
        if not item:
            return None
        ts, cached_port, data, ctype, stamp = item
        if cached_port != port or now - ts > ttl or stamp != _engine_stamp():
            return None
        return data, ctype


def _cache_put(key: str, port: int, data: bytes, ctype: str = "application/json") -> None:
    with _RESP_LOCK:
        if len(_RESP_CACHE) > 64:
            _RESP_CACHE.clear()
        _RESP_CACHE[key] = (time.time(), port, data, ctype, _engine_stamp())


def invalidate_catalog_cache() -> None:
    """Descarta modelos/provedores em cache (chave salva ou motor reiniciado)."""
    with _RESP_LOCK:
        for key in [k for k in _RESP_CACHE if k.startswith(("/api/model", "/api/provider"))]:
            _RESP_CACHE.pop(key, None)
    with _CATALOG_LOCK:
        _CATALOG_CACHE.update(ts=0.0)
    with _GLOBAL_LOCK:
        _GLOBAL_ROWS.clear()
        _GLOBAL_ROWS.update({"ts": 0.0, "model": None, "provider": None})


def compute_run_state(
    data: dict,
    rows: list,
    now_ms: int,
    stale_ms: int = 120_000,
    engine_running: bool | None = None,
) -> dict:
    """Decide se o turno está rodando a partir da última mensagem.

    ``session.time.busy > idle`` não serve sozinho: quando um turno morre no
    meio, o motor mantém ``outcome`` do turno anterior e ``idle`` velho, e a
    UI fica "Working" para sempre. A mensagem do assistente é o sinal direto:
    ``time.completed`` presente = terminou; ausente e recente = rodando;
    ausente e parada há muito tempo = turno órfão (``stale``).
    """
    last_assistant = next(
        (
            m
            for m in (rows or [])
            if isinstance(m, dict) and m.get("type") == "assistant"
        ),
        None,
    )
    running = False
    stale = False
    last_ms = 0
    completed = None
    if last_assistant:
        t = last_assistant.get("time") or {}
        created = int(t.get("created") or 0)
        streamed = int(t.get("streamed") or 0)
        completed = t.get("completed")
        last_ms = max(created, streamed)
        if not completed and last_ms:
            age = now_ms - last_ms
            running = age < stale_ms
            stale = not running
    if engine_running is not None:
        # v0.8.0 (web14): o motor é a fonte da verdade. Entre dois passos do
        # turno a última mensagem já está fechada, mas a sessão segue em
        # execução — a heurística acima dava falso "parado" e recarregava a
        # página a cada ~30 s.
        running = bool(engine_running)
        stale = bool(not running and not completed and last_ms and now_ms - last_ms >= stale_ms)
    return {
        "running": bool(running),
        "stale": bool(stale),
        "completed": completed is not None,
        "last_activity_ms": last_ms,
        "age_ms": (now_ms - last_ms) if last_ms else None,
        "outcome": (data or {}).get("outcome"),
        "busy": ((data or {}).get("time") or {}).get("busy", 0),
        "idle": ((data or {}).get("time") or {}).get("idle", 0),
    }


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
        if cached and now - float(_GLOBAL_ROWS.get(f"{kind}_ts", 0.0)) < ttl:
            return cached
    payload = _catalog_json(f"/api/{kind}", timeout=15.0, wait=6.0)
    rows = payload.get("data") if isinstance(payload, dict) else None
    # v0.8.0 (web14): lista vazia não é guardada — ela pode ser só o motor
    # ainda subindo, e cacheá-la deixava o seletor vazio por 30 s.
    if not isinstance(rows, list) or not rows:
        return None
    with _GLOBAL_LOCK:
        _GLOBAL_ROWS[kind] = rows
        _GLOBAL_ROWS[f"{kind}_ts"] = now
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
    models = _catalog_json(f"/api/model{query}", timeout=12, wait=6.0) if query else None
    scoped_count = len((models.get("data") if isinstance(models, dict) else None) or [])
    if not models or not scoped_count:
        models = _catalog_json("/api/model", timeout=12, wait=6.0)
    providers = _catalog_json(f"/api/provider{query}", timeout=8, wait=6.0) if query else None
    if not providers:
        providers = _catalog_json("/api/provider", timeout=8, wait=6.0)
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


# ── páginas de mensagens: agregação e pré-busca (v0.7.11-web10) ─────
# A SPA carrega a conversa inteira ao abrir uma sessão:
#   message.list({limit:200, order:"asc"}) e depois
#   message.list({limit:200, cursor:...}) até `cursor.next` ser nulo.
# Em conversa longa isso são várias idas sequenciais e ~3,5 MB de JSON
# (medido: 779 mensagens). Aqui o proxy busca as páginas seguintes no
# motor (loopback, ~30 ms cada), devolve UMA resposta e ainda a mantém
# comprimida. O número de idas pelo túnel do Colab cai a 1.
_MESSAGE_PATH = re.compile(r"^/api/session/[^/]+/message$")
_AGG_MAX_PAGES = int(os.environ.get("UFVAI_AGG_MAX_PAGES", "12") or 12)
_AGG_MIN_LIMIT = 100
_PREFETCH: dict = {}
_PREFETCH_READY: dict = {}
_PREFETCH_LAST: dict = {}
_PREFETCH_LOCK = threading.Lock()
_PREFETCH_TTL = float(os.environ.get("UFVAI_PREFETCH_TTL", "8") or 0)
_LAST_DIRECTORY: dict = {"value": "", "header": ""}


def _directory_of(path: str) -> str:
    qs = parse_qs(urlparse(path).query)
    for key in ("location[directory]", "directory"):
        value = qs.get(key)
        if value:
            return value[0]
    return ""


def _session_of(path: str) -> str:
    m = re.match(r"^/api/session/([^/]+)(?:/|$)", urlparse(path).path)
    return m.group(1) if m else ""


def _is_message_first_page(path: str) -> bool:
    parsed = urlparse(path)
    if not _MESSAGE_PATH.match(parsed.path):
        return False
    qs = parse_qs(parsed.query)
    if qs.get("cursor"):
        return False
    if (qs.get("order") or [""])[0] != "asc":
        return False
    try:
        limit = int((qs.get("limit") or ["0"])[0])
    except ValueError:
        limit = 0
    return limit >= _AGG_MIN_LIMIT


def _get_upstream(
    path: str,
    timeout: float = 30.0,
    extra_headers: dict | None = None,
) -> tuple[int, bytes]:
    host, port, password = service_info()
    if not port:
        return 0, b""
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        headers = {
            "Authorization": _basic(password),
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }
        if extra_headers:
            headers.update(extra_headers)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        if raw[:2] == b"\x1f\x8b" or (resp.getheader("Content-Encoding") or "") == "gzip":
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        return resp.status, raw
    except OSError:
        return 0, b""
    finally:
        conn.close()


def aggregate_message_pages(
    path: str, first: bytes, extra_headers: dict | None = None
) -> bytes:
    """Junta as páginas seguintes de ``message.list`` numa única resposta.

    O cursor do motor é opaco e não pode ser combinado com ``order`` — por
    isso a primeira página usa ``order=asc`` e as seguintes apenas
    ``limit``+``cursor``, exatamente como a SPA faz. Se algo falhar, devolve
    a primeira página intacta (o cursor original continua no JSON).
    """
    try:
        payload = json.loads(first.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return first
    if not isinstance(payload, dict):
        return first
    items = payload.get("data")
    cursor = ((payload.get("cursor") or {}).get("next") or "")
    if not isinstance(items, list) or not cursor:
        return first
    parsed = urlparse(path)
    qs = parse_qs(parsed.query)
    base = {k: v[0] for k, v in qs.items() if k != "cursor"}
    base.pop("order", None)
    pages = 1
    while cursor and pages < _AGG_MAX_PAGES:
        status, raw = _get_upstream(
            parsed.path + "?" + urlencode({**base, "cursor": cursor}),
            extra_headers=extra_headers,
        )
        if status != 200 or not raw:
            break
        try:
            page = json.loads(raw.decode("utf-8", "replace"))
        except (ValueError, UnicodeDecodeError):
            break
        chunk = page.get("data") if isinstance(page, dict) else None
        if not isinstance(chunk, list):
            break
        cursor = ((page.get("cursor") or {}).get("next") or "")
        if not chunk:
            break
        items.extend(chunk)
        pages += 1
    payload["data"] = items
    current = payload.get("cursor")
    current = current if isinstance(current, dict) else {}
    current["next"] = cursor or None
    payload["cursor"] = current
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def prefetch_session(sid: str, ready: threading.Event | None = None) -> None:
    """Pré-busca a conversa que a TUI acabou de exibir (uso único).

    Roda em paralelo com o push do SSE. Se a requisição da SPA chegar antes
    de terminar, ela espera em ``wait_prefetch`` — o resultado é o primeiro
    paint da conversa já com os bytes na mão, sem ida extra ao motor.
    """
    sid = str(sid or "").strip()
    directory = _LAST_DIRECTORY.get("value") or ""
    header = _LAST_DIRECTORY.get("header") or ""
    try:
        if not sid or _PREFETCH_TTL <= 0:
            return
        with _PREFETCH_LOCK:
            last = _PREFETCH_LAST.get(sid, 0.0)
            if time.time() - last < 30.0:
                return
            _PREFETCH_LAST[sid] = time.time()
            if len(_PREFETCH_LAST) > 64:
                _PREFETCH_LAST.clear()
        query = {"limit": "200", "order": "asc"}
        extra: dict = {}
        if header:
            extra["x-opencode-directory"] = header
        elif directory:
            extra["x-opencode-directory"] = quote(directory, safe="")
        else:
            return
        path = f"/api/session/{quote(sid, safe='')}/message?" + urlencode(query)
        status, raw = _get_upstream(path, extra_headers=extra)
        if status != 200 or not raw:
            return
        raw = aggregate_message_pages(path, raw, extra_headers=extra)
        gz = b""
        if len(raw) > 131072:
            try:
                gz = gzip.compress(raw, 6)
            except OSError:
                gz = b""
        with _PREFETCH_LOCK:
            if len(_PREFETCH) > 8:
                _PREFETCH.clear()
            _PREFETCH[sid] = (
                time.time(),
                unquote(header) if header else directory,
                raw,
                gz,
            )
    finally:
        if ready is not None:
            ready.set()


def _prefetch_state() -> dict:
    now = time.time()
    with _PREFETCH_LOCK:
        return {
            sid: {"age_s": round(now - ts, 2), "bytes": len(raw)}
            for sid, (ts, _dir, raw, _gz) in _PREFETCH.items()
        }


def wait_prefetch(path: str, timeout: float = 2.5) -> None:
    """Espera (curto) a pré-busca em andamento da sessão pedida."""
    if not _is_message_first_page(path):
        return
    sid = _session_of(path)
    with _PREFETCH_LOCK:
        event = _PREFETCH_READY.get(sid)
    if event is not None:
        event.wait(timeout)


def take_prefetch(path: str, directory: str = "") -> tuple[bytes, bytes] | None:
    """Consome (uma vez) a pré-busca se o pedido casa com ela."""
    if not _is_message_first_page(path):
        return None
    sid = _session_of(path)
    if not sid:
        return None
    directory = directory or _directory_of(path)
    now = time.time()
    with _PREFETCH_LOCK:
        item = _PREFETCH.pop(sid, None)
        _PREFETCH_READY.pop(sid, None)
    if not item:
        return None
    ts, saved_dir, raw, gz = item
    if now - ts > _PREFETCH_TTL:
        return None
    if directory and saved_dir and directory != saved_dir:
        return None
    return raw, gz


def drop_prefetch(path: str) -> None:
    sid = _session_of(path)
    if not sid:
        return
    with _PREFETCH_LOCK:
        _PREFETCH.pop(sid, None)
        _PREFETCH_READY.pop(sid, None)


# ── foco da TUI ↔ web (v0.7.11-web9) ─────────────────────────
# A TUI (plugin ufvai-sync) grava a sessão que está exibindo em
# ``FOCUS_FILE``. Um observador lê o arquivo e faz *push* imediato para as
# páginas abertas por ``/__ufvai/live`` — sem polling de 2,5 s e sem inferir
# a sessão por eventos: é o mesmo dado que a TUI mostra na tela.
_LIVE_SUBS: set = set()
_LIVE_LOCK = threading.Lock()
_FOCUS_STOP = threading.Event()


# A TUI reescreve o foco a cada 5 s (heartbeat). Passados 15 s sem
# atualização, o arquivo é resíduo de uma TUI encerrada e não deve arrastar a
# web para uma sessão antiga.
FOCUS_MAX_AGE_MS = 15000


def read_focus(max_age_ms: int = FOCUS_MAX_AGE_MS) -> dict:
    """Foco publicado pela TUI (``{}`` se ausente, inválido ou vencido)."""
    try:
        raw = Path(FOCUS_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    try:
        ts = int(data.get("ts") or 0)
    except (TypeError, ValueError):
        ts = 0
    if max_age_ms > 0 and (not ts or int(time.time() * 1000) - ts > max_age_ms):
        return {}
    return data


def write_focus(sid: str, route: str = "session") -> bool:
    """Grava o foco publicado pela TUI (mesmo formato do plugin).

    Usado quando o plugin entrega o foco por HTTP (``POST /__ufvai/focus`` com
    ``source: "tui"``) — o arquivo continua sendo escrito para que o polling e
    o ``/__ufvai/session`` enxerguem o mesmo estado.
    """
    sid = str(sid or "").strip()
    if not sid:
        return False
    payload = {
        "sid": sid,
        "ts": int(time.time() * 1000),
        "route": str(route or "session"),
        "source": "tui",
    }
    try:
        tmp = f"{FOCUS_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, FOCUS_FILE)
        return True
    except OSError:
        return False


# v0.8.0 (web14): o foco tem UMA ordem, decidida pelo servidor. Cada TROCA de
# sessão — vinda da TUI ou da web — recebe um ``seq`` crescente. Batimentos da
# TUI (mesma sessão) não geram evento: nunca revertem uma escolha recente.
#   TUI → web : /__ufvai/live          (SSE; eventos das duas origens)
#   web → TUI : /__ufvai/focus/stream  (SSE; só eventos da web)
#   arquivos  : FOCUS_FILE / WEB_FOCUS_FILE (reserva e compatibilidade)
_TUI_SUBS: set = set()
_FOCUS_LOCK = threading.Lock()
_FOCUS: dict = {
    # v0.8.0 (web14b): o seq nasce do relógio (ms). Se o proxy reiniciar, os
    # clientes que guardaram um seq alto não ignoram os eventos novos.
    "seq": int(time.time() * 1000), "sid": "", "source": "", "ts": 0,
    "tui_sid": "", "web_sid": "",
}


def _focus_next(sid: str, source: str) -> int:
    """Registra uma troca de sessão. Chamar com ``_FOCUS_LOCK`` adquirido."""
    _FOCUS["seq"] = int(_FOCUS["seq"]) + 1
    _FOCUS["sid"] = sid
    _FOCUS["source"] = source
    _FOCUS["ts"] = int(time.time() * 1000)
    return int(_FOCUS["seq"])


def _focus_snapshot() -> dict:
    """Foco atual para quem acabou de conectar (referência; não navega)."""
    with _FOCUS_LOCK:
        sid = str(_FOCUS.get("sid") or "")
        seq = int(_FOCUS.get("seq") or 0)
        source = str(_FOCUS.get("source") or "")
    if not sid:
        data = read_focus()
        sid = str(data.get("sid") or "").strip()
        source = str(data.get("source") or "tui")
    return {"sid": sid, "seq": seq, "source": source}


def _write_web_file(sid: str, seq: int) -> bool:
    try:
        tmp = f"{WEB_FOCUS_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"sid": sid, "seq": seq, "ts": int(time.time() * 1000), "source": "web"},
                fh,
            )
        os.replace(tmp, WEB_FOCUS_FILE)
        return True
    except OSError:
        return False


def _start_prefetch(sid: str) -> None:
    ready = threading.Event()
    with _PREFETCH_LOCK:
        _PREFETCH_READY[sid] = ready
    threading.Thread(
        target=prefetch_session,
        args=(sid, ready),
        name="ufvai-prefetch",
        daemon=True,
    ).start()


def apply_tui_focus(sid: str, route: str = "session") -> bool:
    """Foco publicado pela TUI (``POST /__ufvai/focus``, ``source: "tui"``).

    Grava o arquivo de reserva sempre, mas só publica quando a sessão mudou em
    relação à última que a TUI reportou (batimentos não publicam).
    """
    sid = str(sid or "").strip()
    if not sid:
        return False
    write_focus(sid, route)
    with _FOCUS_LOCK:
        if _FOCUS.get("tui_sid") == sid:
            return True
        _FOCUS["tui_sid"] = sid
        seq = _focus_next(sid, "tui")
        ts = int(_FOCUS["ts"])
    _remember_session(sid)
    with _LIVE_LOCK:
        has_pages = bool(_LIVE_SUBS)
    if has_pages:
        _start_prefetch(sid)
    _publish_live({"type": "focus", "sid": sid, "seq": seq, "source": "tui", "ts": ts})
    return True


def write_web_focus(sid: str) -> bool:
    """Foco escolhido na web (``POST /__ufvai/focus``, ``source: "web"``).

    Publica para o terminal (``/__ufvai/focus/stream``) e para as outras abas
    da web (``/__ufvai/live``). A ``CURRENT_SESSION_FILE`` só é atualizada
    quando a TUI segue a escolha (``apply_tui_focus``).
    """
    sid = str(sid or "").strip()
    if not sid:
        return False
    with _FOCUS_LOCK:
        changed = _FOCUS.get("web_sid") != sid
        if changed:
            _FOCUS["web_sid"] = sid
            seq = _focus_next(sid, "web")
        else:
            seq = int(_FOCUS.get("seq") or 0)
        ts = int(_FOCUS.get("ts") or 0)
    ok = _write_web_file(sid, seq)
    if changed:
        msg = {"type": "focus", "sid": sid, "seq": seq, "source": "web", "ts": ts}
        _publish_live(msg)
        _publish_tui(msg)
    return ok


def _publish_live(payload: dict) -> None:
    msg = json.dumps(payload, ensure_ascii=False)
    with _LIVE_LOCK:
        subs = list(_LIVE_SUBS)
    for sub in subs:
        try:
            sub.put_nowait(msg)
        except Exception:  # noqa: BLE001 — fila cheia: a próxima atualiza
            pass


def _publish_tui(payload: dict) -> None:
    msg = json.dumps(payload, ensure_ascii=False)
    with _LIVE_LOCK:
        subs = list(_TUI_SUBS)
    for sub in subs:
        try:
            sub.put_nowait(msg)
        except Exception:  # noqa: BLE001
            pass


def _watch_focus() -> None:
    """Rede de segurança: observa ``FOCUS_FILE`` (50 ms).

    Cobre plugins antigos, quem escreve o arquivo à mão e o caso em que o POST
    da TUI falha. Só age quando a sessão no arquivo é diferente da última que a
    TUI reportou, então não duplica o que já chegou por HTTP.
    """
    last_ts = 0
    while not _FOCUS_STOP.is_set():
        data = read_focus()
        sid = str(data.get("sid") or "").strip()
        ts = int(data.get("ts") or 0)
        if sid and ts != last_ts:
            last_ts = ts
            with _FOCUS_LOCK:
                known = _FOCUS.get("tui_sid")
            if sid != known:
                apply_tui_focus(sid, str(data.get("route") or "session"))
        _FOCUS_STOP.wait(0.05)


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
    """Cada documento HTML (page load) rearma o atraso do 1º SSE."""
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

# v0.8.0 (web14): tempo máximo que o proxy espera o motor subir antes de
# devolver erro à SPA. O motor V2 reseta conexões e responde 503
# (``service_starting``) por ~5-10 s após iniciar; a SPA não repete
# requisições falhas, então sem essa espera o seletor de modelos ficava vazio.
_UPSTREAM_WAIT_S: float = float(os.environ.get("UFVAI_UPSTREAM_WAIT_S", "12") or 12)

# v0.8.0 (web14b): logo após o motor (re)iniciar, ``/api/model`` e
# ``/api/provider`` podem responder 200 com ``data: []`` antes de o catálogo
# terminar de carregar. A SPA aceita esse vazio e não repete — o seletor de
# modelos fica em branco para quem abre a interface nessa janela. Enquanto a
# janela estiver aberta, o proxy repete a leitura por até ``_EMPTY_RETRY_S``.
_WARM_LOCK = threading.Lock()
_WARM: dict = {"stamp": None, "until": 0.0}
_WARM_GRACE_S: float = float(os.environ.get("UFVAI_WARM_GRACE_S", "25") or 25)
_EMPTY_RETRY_S: float = float(os.environ.get("UFVAI_EMPTY_RETRY_S", "6") or 6)


def _engine_warm() -> bool:
    """True durante a janela de carregamento após um (re)início do motor.

    A identidade vem do ``service.json`` (porta + mtime): qualquer reinício
    abre a janela. Fora dela, lista vazia é resposta legítima (ex.: sem chave)
    e não deve atrasar a SPA.
    """
    stamp = _engine_stamp()
    now = time.time()
    with _WARM_LOCK:
        if _WARM["stamp"] != stamp:
            _WARM["stamp"] = stamp
            _WARM["until"] = now + _WARM_GRACE_S
        return now < float(_WARM["until"])


def _payload_has_rows(raw: bytes, encoding: str = "") -> bool:
    """``data`` com ao menos um item, mesmo quando o corpo veio comprimido."""
    enc = (encoding or "").lower().strip()
    data = raw
    if enc in ("gzip", "x-gzip"):
        try:
            data = gzip.decompress(raw)
        except OSError:
            return False
    elif enc == "deflate":
        try:
            data = zlib.decompress(raw)
        except zlib.error:
            try:
                data = zlib.decompress(data, -zlib.MAX_WBITS)
            except zlib.error:
                return False
    return _has_rows(data)



class _Buffered:
    """Resposta do motor já lida (corpo em memória), com a interface usada pelo proxy."""

    def __init__(self, status: int, reason: str, headers: list, body: bytes) -> None:
        self.status = status
        self.reason = reason
        self._headers = headers
        self._body = body

    def getheader(self, name: str, default=None):
        for key, value in self._headers:
            if key.lower() == name.lower():
                return value
        return default

    def getheaders(self) -> list:
        return list(self._headers)

    def read(self, amt=None) -> bytes:
        body, self._body = self._body, b""
        return body


def _open_upstream(method: str, path: str, body, headers: dict, host: str, port: int):
    """Abre a requisição ao motor, repetindo enquanto ele está subindo.

    GET/HEAD são repetidos em qualquer falha de conexão e em 503 (corpo curto,
    antes do SSE). POST só é repetido quando a conexão é recusada — nesse caso
    nada chegou ao motor, então não há risco de executar duas vezes.
    Devolve ``(resposta, conexão)``; a conexão é ``None`` quando a resposta
    já foi lida e está em memória (``_Buffered``).
    """
    deadline = time.time() + _UPSTREAM_WAIT_S
    idempotent = method in ("GET", "HEAD")
    route = path.split("?", 1)[0]
    # Só GET de catálogo, e só na janela de carregamento do motor.
    catalog_get = method == "GET" and route in ("/api/model", "/api/provider") and _engine_warm()
    empty_deadline = min(deadline, time.time() + _EMPTY_RETRY_S)
    delay = 0.15
    while True:
        conn = http.client.HTTPConnection(host, port, timeout=600)
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            conn.close()
            retry_ok = idempotent or isinstance(exc, ConnectionRefusedError)
            if not retry_ok or time.time() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 1.6, 1.0)
            continue
        ctype = (resp.getheader("Content-Type") or "").lower()
        if idempotent and resp.status == 503 and not ctype.startswith("text/event-stream"):
            raw = resp.read(65536)
            headers_out = resp.getheaders()
            conn.close()
            if time.time() < deadline:
                time.sleep(delay)
                delay = min(delay * 1.6, 1.0)
                continue
            return _Buffered(503, resp.reason, headers_out, raw), None
        if catalog_get and resp.status == 200:
            # v0.8.0 (web14b): 200 com lista vazia durante o aquecimento é
            # transitório. Repetir aqui evita que a SPA "grude" no vazio.
            raw = resp.read()
            headers_out = resp.getheaders()
            encoding = resp.getheader("Content-Encoding") or ""
            conn.close()
            if _payload_has_rows(raw, encoding) or time.time() >= empty_deadline:
                return _Buffered(200, resp.reason or "OK", headers_out, raw), None
            time.sleep(delay)
            delay = min(delay * 1.6, 1.0)
            continue
        return resp, conn


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

    def _accept_encoding(self) -> str:
        """Codificações que o navegador aceita (só as que o proxy entende).

        v0.7.11-web10: antes o proxy pedia ``identity`` ao motor e servia
        **tudo sem compressão**. Só o bundle da SPA passa de 3,3 MB (0,9 MB
        em gzip) e uma página de mensagens longas chega a ~350 kB (89 kB em
        gzip). No proxy do Colab isso é a diferença entre "instantâneo" e
        "dezenas de segundos". ``br``/``zstd`` ficam de fora porque o proxy
        precisa inspecionar algumas respostas (HTML, /api/model, /api/provider).
        """
        raw = (self.headers.get("Accept-Encoding") or "").lower()
        if "gzip" in raw:
            return "gzip, deflate"
        if "deflate" in raw:
            return "deflate"
        return "identity"

    def _accepts(self, encoding: str) -> bool:
        raw = (self.headers.get("Accept-Encoding") or "").lower()
        if encoding == "deflate":
            return "deflate" in raw
        return "gzip" in raw

    def _forward_headers(self, password: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            if key.lower() in _SKIP_REQUEST_HEADERS:
                continue
            headers[key] = value
        headers["Authorization"] = _basic(password)
        headers["Accept-Encoding"] = self._accept_encoding()
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

    def _run_state(self) -> None:
        """Estado **real** de execução de uma sessão (para destravar a UI).

        ``session.time.busy > idle`` não é confiável quando um turno morre no
        meio (o motor mantém ``outcome`` do turno anterior e ``idle`` velho).
        Aqui olhamos a última mensagem do assistente: se ela tem
        ``time.completed``, o turno terminou; se não tem, ainda está rodando —
        a menos que esteja parada há mais de ``STALE_MS`` (turno órfão).
        """
        qs = parse_qs(urlparse(self.path).query)
        sid = str(qs.get("sid", [""])[0] or "").strip()
        if not sid:
            self._json_error(400, "sid obrigatório")
            return
        sess = _api_json(f"/api/session/{quote(sid, safe='')}")
        data = sess.get("data") if isinstance(sess, dict) else None
        if not isinstance(data, dict):
            self._json_error(404, "sessão não encontrada")
            return
        msgs = _api_json(
            f"/api/session/{quote(sid, safe='')}/message?limit=3&order=desc"
        )
        rows = msgs.get("data") if isinstance(msgs, dict) else None
        # Sinal autoritativo do motor: sessões em execução (``type``: running,
        # busy ou pending). ``None`` se o motor não respondeu → heurística.
        active = _api_json("/api/session/active")
        act_map = active.get("data") if isinstance(active, dict) else None
        engine_running = None
        if isinstance(act_map, dict):
            status = act_map.get(sid)
            engine_running = bool(
                isinstance(status, dict)
                and status.get("type") in ("running", "busy", "pending")
            )
        info = compute_run_state(
            data, rows or [], int(time.time() * 1000), engine_running=engine_running
        )
        info["sid"] = sid
        body = json.dumps(info).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
            "focus": read_focus(0),
            "prefetch": _prefetch_state(),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
        # v0.8.0 (web14): ``focus`` traz a ordem (seq) do último foco. A web usa
        # só isso no reserva; ``active`` (sessão que começou a executar) não
        # serve para navegar — puxava a página para longe da sessão escolhida.
        body = json.dumps(
            {
                "sid": sid,
                "active": active,
                "active_age_ms": active_age,
                "source": source,
                "focus": _focus_snapshot(),
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _live_stream(self, kind: str = "web") -> None:
        """SSE de foco: ``web`` (páginas, eventos das duas origens) ou ``tui``
        (plugin do terminal, só eventos da web).

        Primeiro envia um ``snapshot`` (referência, sem navegar). Depois, cada
        troca como ``data:``. O ping também vai em ``data:`` — o navegador só
        marca o canal como vivo quando recebe mensagem com dados.
        """
        subs = _TUI_SUBS if kind == "tui" else _LIVE_SUBS
        sub: queue.Queue = queue.Queue(maxsize=64)
        with _LIVE_LOCK:
            subs.add(sub)
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
            snap = {"type": "snapshot", **_focus_snapshot()}
            _send(b"data: " + json.dumps(snap, ensure_ascii=False).encode("utf-8") + b"\n\n")
            while True:
                try:
                    msg = sub.get(timeout=15)
                except queue.Empty:
                    ping = json.dumps({"type": "ping", "seq": int(_FOCUS.get("seq") or 0)})
                    _send(b"data: " + ping.encode("utf-8") + b"\n\n")
                    continue
                _send(b"data: " + str(msg).encode("utf-8") + b"\n\n")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _LIVE_LOCK:
                subs.discard(sub)

    def _web_focus(self) -> None:
        """A web informa a sessão que está exibindo (terminal segue)."""
        body = self._read_body() or b""
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            data = {}
        sid = str((data or {}).get("sid") or "").strip() if isinstance(data, dict) else ""
        source = str((data or {}).get("source") or "web") if isinstance(data, dict) else "web"
        if source == "tui":
            # v0.7.11-web12: a TUI entrega o foco por HTTP → o proxy publica no
            # SSE na hora (~1 ms), sem esperar o polling do arquivo.
            ok = apply_tui_focus(sid, str((data or {}).get("route") or "session"))
        else:
            ok = write_web_focus(sid)
        self.send_response(204 if ok else 400)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle(self, method: str) -> None:
        rota = self.path.split("?", 1)[0]
        # Escopo do projeto (a pré-busca precisa dele para consultar o motor).
        # A SPA manda `x-opencode-directory` (encodeURIComponent) nas rotas
        # de sessão; algumas rotas usam `location[directory]` na query.
        dir_header = self.headers.get("x-opencode-directory") or ""
        _dir = _directory_of(self.path)
        if dir_header:
            _LAST_DIRECTORY["header"] = dir_header
            _LAST_DIRECTORY["value"] = unquote(dir_header)
        elif _dir:
            _LAST_DIRECTORY["value"] = _dir
            _LAST_DIRECTORY["header"] = quote(_dir, safe="")
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            # Qualquer escrita invalida a conversa pré-buscada da sessão.
            drop_prefetch(self.path)
        if rota == "/__ufvai_ready":
            self._health()
            return
        if rota == "/__ufvai/boot.js":
            self._boot_js()
            return
        if rota == "/__ufvai/live":
            self._live_stream("web")
            return
        if rota == "/__ufvai/focus/stream":
            self._live_stream("tui")
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
        if rota == "/__ufvai/run-state":
            self._run_state()
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
        if method == "GET" and _is_message_first_page(self.path):
            # v0.7.11-web10: a conversa que a TUI acabou de exibir já está
            # aqui (a SPA espera no máximo 2,5 s por ela).
            wait_prefetch(self.path)
            hit = take_prefetch(
                self.path, unquote(dir_header) if dir_header else _dir
            )
            if hit:
                raw, gz = hit
                accept = (self.headers.get("Accept-Encoding") or "").lower()
                use_gz = bool(gz) and "gzip" in accept
                payload = gz if use_gz else raw
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-UFVAI-Prefetch", "hit")
                if use_gz:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                self.end_headers()
                self.wfile.write(payload)
                return

        headers = self._forward_headers(password)
        conn = None
        try:
            # v0.8.0 (web14b): uma vez por documento, espera o listener da SPA
            # existir antes de abrir o SSE — sem fechar a conexão depois.
            if (
                _SSE_HANDSHAKE_DELAY_S > 0
                and self.path.split("?", 1)[0] == "/api/event"
                and _take_close_once()
            ):
                time.sleep(_SSE_HANDSHAKE_DELAY_S)
            # v0.8.0 (web14): repete enquanto o motor sobe (ver _open_upstream).
            # Substitui a tentativa única da v0.7.11-web5, que não cobria a
            # janela de ~5-10 s do reinício e devolvia 502 para a SPA.
            resp, conn = _open_upstream(method, self.path, body, headers, host, port)
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

                # v0.8.0 (web14b): o handshake já foi atrasado antes de abrir
                # o stream (ver _SSE_HANDSHAKE_DELAY_S). Não fechamos mais a
                # primeira conexão: derrubá-la perdia o server.connected e
                # deixava o seletor de modelos vazio no primeiro acesso.

                try:
                    while True:
                        chunk = resp.read1(65536)
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
            # Só estas rotas precisam ser abertas pelo proxy (título/tema no
            # HTML, catálogo reparado, título da sessão recém-criada). Todo o
            # resto segue comprimido de ponta a ponta: menos bytes no túnel do
            # Colab e zero custo de descompressão/recompressão.
            aggregate = method == "GET" and _is_message_first_page(self.path)
            transform = (
                ctype.startswith("text/html")
                or rota_api in ("/api/model", "/api/provider")
                or aggregate
                or bool(_SESSION_GET_RE.match(rota_api))
                or (method == "POST" and rota_api == "/api/session")
            )
            passthrough = ""
            if encoding in ("gzip", "x-gzip", "deflate"):
                normalized = "deflate" if encoding == "deflate" else "gzip"
                if not transform and self._accepts(normalized):
                    passthrough = normalized
                elif normalized == "gzip":
                    try:
                        data = gzip.decompress(data)
                    except OSError:
                        pass
                else:
                    try:
                        data = zlib.decompress(data)
                    except zlib.error:
                        try:
                            data = zlib.decompress(data, -zlib.MAX_WBITS)
                        except zlib.error:
                            pass
            if aggregate and resp.status == 200:
                # Uma resposta só, com todas as páginas que a SPA pediria
                # em sequência (cursor oculto até o limite de segurança).
                extra = (
                    {"x-opencode-directory": dir_header} if dir_header else None
                )
                data = aggregate_message_pages(self.path, data, extra_headers=extra)
            created_sid = ""
            status_out = resp.status
            if (
                method in ("GET", "HEAD")
                and resp.status == 200
                and _SESSION_GET_RE.match(rota_api)
            ):
                # v0.7.11-web16: conversa presa a modelo que este ambiente não
                # oferece → troca pelo substituto válido antes de a SPA pintar.
                sid_visto = _SESSION_GET_RE.match(rota_api).group(1)  # type: ignore[union-attr]
                remember_seen_session(sid_visto)
                data = repair_session_model(data)
            if method in ("GET", "HEAD") and rota_api in ("/api/model", "/api/provider"):
                data, status_out = _catalog_response(
                    rota_api.rsplit("/", 1)[-1], data, resp.status
                )
            if (
                method in ("GET", "HEAD")
                and rota_api in ("/api/model", "/api/provider")
                and status_out == 200
                and _has_rows(data)
            ):
                _cache_put(cache_key, port, data)
            if method == "POST" and rota_api == "/api/session" and resp.status == 200:
                data, created_sid = _brand_new_session(data)
                if created_sid:
                    remember_seen_session(created_sid)
            if ctype.startswith("text/html") and resp.status == 200:
                _rearm_close_once()
                sid = current_session()
                if not _session_exists(host, port, password, sid):
                    sid = ""
                data = _inject_html(data, sid)

            # v0.7.11-web7: /api/model pode passar de 1 MB. Compactar reduz
            # o risco de o proxy do Colab truncar/estourar timeout.
            gzip_out = False
            _accepts_gzip = "gzip" in (
                self.headers.get("Accept-Encoding") or ""
            ).lower()
            if (
                (rota_api in ("/api/model", "/api/provider") or aggregate)
                and len(data) > 262144
                and _accepts_gzip
            ) or (
                ctype.startswith("text/html") and len(data) > 4096 and _accepts_gzip
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
            if passthrough:
                self.send_header("Content-Encoding", passthrough)
                self.send_header("Vary", "Accept-Encoding")
            elif gzip_out:
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
            if conn is not None:
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
            _RUNS_STOP.clear()
            threading.Thread(
                target=_watch_stuck_runs, name="ufvai-runs", daemon=True
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
    _RUNS_STOP.set()
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
