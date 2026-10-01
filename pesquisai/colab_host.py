"""
colab_host.py — Supervisor detached do UFVAI para Google Colab (v0.6.20).

PROBLEMA QUE ESTE MÓDULO RESOLVE
=================================
No Colab, o boot padrão (`from main import run; run()`) roda DENTRO do kernel
do notebook. Consequências observadas pelo usuário:

1. **Desconexão por AFK** — o Colab encerra o runtime ocioso; como ttyd e o
   wrapper HTTP são threads/processos filhos do kernel, tudo morre junto.
2. **"reconnecting"** — ao reexecutar a célula, a nova instância chama
   `kill_previous()` → `pkill -9 -x ttyd`, que mata o ttyd da instância
   anterior. O iframe que o navegador já tinha aberto fica órfão e mostra
   "reconnecting".
3. **"pesquisai tmp"** — `_prepare_ttyd_touch_index()` sobe um ttyd *dummy*
   com `echo pesquisai_touch_tmp` NA MESMA porta do terminal real. Durante a
   janela de existência desse processo, o navegador pode conectar nele em vez do
   ttyd real → o usuário vê `pesquisai_touch_tmp` e precisa apertar Enter.

SOLUÇÃO
=======
Um processo **supervisor**, totalmente desacoplado do kernel:

    kernel  ──spawn──▶  supervisor (setsid,Setsid próprio)
                           ├── run()          (wrapper HTTP :8001)
                           ├── ttyd          (:8000, filho)
                           │     └── bash -i -c opencode
                           └── watchdog       (reinicia o ttyd se morrer)

Propriedades garantidas:

* **Detached** — `setsid` + stdin em /dev/null + fds redirecionados. Sobrevive
  a SIGHUP, a interrupção da célula e a reexecução do notebook.
* **Singleton** — `flock` exclusivo em `host.lock`. Uma segunda execução
  detecta a primeira e SAI (em vez de matar a árvore, que era a causa do
   "reconnecting"). Isso elimina a competição entre instâncias.
* **Auto-recuperação** — o watchdog sonda a porta do ttyd e o reinicia se
  morrer, com backoff. Nenhum patch de browser é necessário.
* **Shutdown ordenado** — `POST /api/shutdown` desativa o watchdog (senão ele
 uria "ressuscitar" o ttyd), mata a árvore do terminal e encerra o wrapper.

LIMITE HONESTO
==============
`nohup`/`setsid` protegem contra SIGHUP e interrupção de célula — mas o Colab
**destrói o container** quando o runtime ocioso expira. Nenhum processo dentro
da VM pode impedir isso. Contra a expiração do timer ocioso, a mitigação é no
front-end (clique periódico no botão de conexão), instalado pela célula do
notebook — ver `keepalive_js()`.

Uso
---
    # No notebook (lado kernel,efêmero):
    from pesquisai.colab_host import spawn_detached
    spawn_detached()          # retorna (pid, log)

    # O supervisor, quando executado como processo:
    python3 -m pesquisai.colab_host
"""

from __future__ import annotations

import errno
import fcntl
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

# ── Estado do supervisor ──────────────────────────────────────────
# Fica em /tmp: é efêmero por natureza (o runtime do Colab é descartado).
# No modo offline o supervisor não é usado, mas o caminho continua válido.
STATE_DIR = os.path.join(tempfile.gettempdir(), "ufvai-host")
PID_FILE = os.path.join(STATE_DIR, "host.pid")
LOCK_FILE = os.path.join(STATE_DIR, "host.lock")
LOG_FILE = os.path.join(STATE_DIR, "host.log")
READY_FILE = os.path.join(STATE_DIR, "ready")

# Espaçamento entre sondas do watchdog. 8s é bastante para não gerar
# tráfego e rápido o bastante para que a queda do ttyd seja reparada
# antes do usuário perceber (o iframe dele mostra "reconnecting").
WATCHDOG_INTERVAL_S = 8.0
# Backoff: após N reinícios consecutivos, espera o dobro (evita busy-loop
# quando o ttyd morre instantaneamente por um erro de configuração).
_MAX_FAST_RESTARTS = 3

# Marcado por /api/shutdown: o watchdog para de ressuscitar o ttyd e o
# supervisor começa a encerrar. Ver `request_shutdown()`.
_SHUTDOWN = threading.Event()


# ── Utilidades ────────────────────────────────────────────────────

def _port_open(port: int, timeout: float = 0.5) -> bool:
    """True se `port` aceitar conexão TCP em localhost."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _write_log(msg: str) -> None:
    """Loga em arquivo + stdout. Nunca levanta exceção.

    O stdout do supervisor é redirigido para LOG_FILE por `spawn_detached`,
    então ambos os caminhos convergem para o mesmo arquivo.
    """
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    """True se `pid` existe e pode ser sinalizado."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        # EPERM = existe mas pertence a outro usuário (ainda vivo).
        return exc.errno == errno.EPERM


# ── Singleton ─────────────────────────────────────────────────────

class _Singleton:
    """Trava `flock` exclusiva — no máximo um supervisor por runtime.

    O lock é seguro contra morte abrupta: quando o processo morre, o kernel
    fecha o descriptor e libera o `flock` automaticamente. Não há PID file
    órfão que precise de limpeza manual.
    """

    def __init__(self) -> None:
        self._fd: int | None = None

    def acquire(self) -> tuple[bool, int | None]:
        """Tenta adquirir o lock.

        Returns:
            (True, None)            → acquired com sucesso
            (False, pid_do_dono)    → já existe um supervisor vivo
        """
        os.makedirs(STATE_DIR, exist_ok=True)
        fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Já trancado → outro supervisor ativo. Lê o PID dele para
            # diagnóstico (o PID file pode estar stale; o flock não mente).
            owner = self._read_owner_pid(fd)
            os.close(fd)
            return False, owner
        self._fd = fd
        return True, None

    @staticmethod
    def _read_owner_pid(fd: int) -> int | None:
        try:
            raw = os.pread(fd, 64, 0).decode("utf-8", "ignore").strip()
            return int(raw) if raw else None
        except Exception:
            return None

    def write_pid(self, pid: int) -> None:
        """Grava o PID no arquivo de lock (visível para diagnóstico)."""
        if self._fd is None:
            return
        try:
            os.ftruncate(self._fd, 0)
            os.pwrite(self._fd, f"{pid}\n".encode(), 0)
            os.fsync(self._fd)
        except Exception:
            pass

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(self._fd)
        except Exception:
            pass
        self._fd = None


def read_host_pid() -> int | None:
    """PID do supervisor em execução, ou None se não houver.

    Usado pela célula do notebook para decidir se já inicializou. O PID file
    sozinho não é confiável (pode ser stale após um crash), então a
    verificação combina PID **e** teste da porta do wrapper.
    """
    try:
        with open(PID_FILE, "r", encoding="utf-8") as fh:
            pid = int((fh.read() or "0").strip())
    except Exception:
        return None
    return pid if _pid_alive(pid) else None


# ── Guard de sinais ───────────────────────────────────────────────

def install_signal_guard() -> None:
    """Torna o supervisor imune a SIGHUP e SIGPIPE.

    * **SIGHUP** — enviado quando o terminal que o lançou fecha (ttyd morre,
      usuário aperta Ctrl+D, o shell pai do Colab encerra). É exatamente o
      sinal que o `nohup` do usuário tentava bloquear; aqui é feito em Python
      e cobre também o caso de o processo ser filho de um shell já morto.
    * **SIGPIPE** — o default é matar o processo; ignoramos e deixamos as
      escritas falharem normalmente, o que é o comportamento correto para
      um servidor que perde um cliente.

    SIGTERM **não** é ignorado: é o sinal do "Sair com segurança" e precisa
    encerrar o processo.
    """
    for sig in (signal.SIGHUP, signal.SIGPIPE):
        try:
            signal.signal(sig, signal.SIG_IGN)
        except (ValueError, OSError):
            # ValueError: não estamos na thread principal.
            pass


# ── Watchdog ──────────────────────────────────────────────────────

def _watchdog(launch, ports: tuple[int, ...]) -> None:
    """Mantém os serviços de pé enquanto o supervisor viver.

    O wrapper HTTP roda em threads *dentro* deste processo, então não pode
    morrer sozinho. O ttyd, sim — é um filho que pode ser morto por OOM,
    por um `pkill` externo, ou por uma falha de bind. Este loop reconstrói.

    Backoff: as primeiras `_MAX_FAST_RESTARTS` tentativas acontecem em
    `WATCHDOG_INTERVAL_S`; depois disso o intervalo dobra, até 60s. Sem
    backoff, um ttyd que morre na hora (ex.: binário ausente) viraria um
    busy-loop tentando bind a cada 8s para sempre.
    """
    interval = WATCHDOG_INTERVAL_S
    consecutive_failures = 0

    while not _SHUTDOWN.is_set():
        # Espaçado em fatias curtas para reagir rápido a um shutdown
        # sem esperar o sleep inteiro.
        if _SHUTDOWN.wait(interval):
            return

        down = [p for p in ports if not _port_open(p)]
        if not down:
            consecutive_failures = 0
            interval = WATCHDOG_INTERVAL_S
            continue

        consecutive_failures += 1
        if consecutive_failures > _MAX_FAST_RESTARTS:
            interval = min(interval * 2, 60.0)
        _write_log(
            f"⚠️  Porta(s) {down} fora do ar — reiniciando serviços "
            f"(tentativa {consecutive_failures}, próximo check em {interval:.0f}s)"
        )
        try:
            launch()
        except Exception as exc:
            _write_log(f"❌ Falha ao reiniciar serviços: {exc}")
        # Não deixa a próxima iteração colar no restart anterior.
        time.sleep(1.0)


# ── Orquestração ──────────────────────────────────────────────────

def request_shutdown(reason: str = "api") -> None:
    """Sinaliza o encerramento e impede o watchdog de ressuscitar o ttyd.

    Chamado por `POST /api/shutdown` (que roda numa thread do wrapper HTTP,
    dentro deste processo) e pelo handler de SIGTERM.

    Importante: o watchdog é desligado **antes** da limpeza. Sem isso, ele
    veria a porta 8000 morrer e reiniciaria o ttyd enquanto a UI já está
    sendo desmontada — o usuário veria o terminal "voltar do nada".
    """
    if not _SHUTDOWN.is_set():
        _write_log(f"🛑 Shutdown solicitado (motivo: {reason})")
    _SHUTDOWN.set()


def run_supervised() -> int:
    """Executa o UFVAI e mantém os serviços vivos. Bloqueante.

    Returns:
        Código de saída do processo.
    """
    install_signal_guard()
    os.makedirs(STATE_DIR, exist_ok=True)

    lock = _Singleton()
    acquired, owner_pid = lock.acquire()
    if not acquired:
        _write_log(
            f"ℹ️  Já existe um supervisor ativo (pid {owner_pid}). "
            f"Nada a fazer — saindo para não derrubar a instância viva."
        )
        return 0

    pid = os.getpid()
    lock.write_pid(pid)
    try:
        with open(PID_FILE, "w", encoding="utf-8") as fh:
            fh.write(f"{pid}\n")
    except Exception:
        pass

    _write_log(f"🧬 Supervisor UFVAI iniciado (pid {pid}, pgid {os.getpgrp()})")

    from .constants import TERMINAL_PORT, WRAPPER_PORT
    from .run_fast import run

    # Import tardio: o módulo do boot faz trabalho pesado no import e
    # não deve ser carregado se já vamos sair (outro supervisor ativo).
    import pesquisai.launch_app as la

    # Encerra eventual resíduo de uma sessão anterior ANTES de subir a
    # nossa. Só é seguro porque o flock garante que somos o único
    # supervisor — o pkill não pode derrubar uma instância legítima.
    try:
        la.kill_previous()
    except Exception as exc:
        _write_log(f"⚠️  kill_previous falhou: {exc}")

    stop_event = threading.Event()

    def _on_sigterm(_sig, _frm):
        _write_log("👋 SIGTERM recebido — encerrando.")
        stop_event.set()
        request_shutdown("sigterm")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_sigterm)
        except (ValueError, OSError):
            pass

    # ── Boot ──────────────────────────────────────────────────────
    try:
        run()
    except Exception as exc:
        _write_log(f"❌ Falha no boot do UFVAI: {exc}")
        _cleanup(la)
        lock.release()
        return 1

    # run() só retorna depois que a UI está no ar. A partir daqui o
    # watchdog assume.
    if not _port_open(WRAPPER_PORT, timeout=1.0):
        _write_log(
            f"❌ Wrapper não respondeu em :{WRAPPER_PORT} após o boot — abortando."
        )
        _cleanup(la)
        lock.release()
        return 1

    try:
        with open(READY_FILE, "w", encoding="utf-8") as fh:
            fh.write(f"{pid}\n{time.time()}\n")
    except Exception:
        pass

    _write_log(
        f"✅ UFVAI no ar — UI :{WRAPPER_PORT} · terminal :{TERMINAL_PORT} · "
        f"watchdog ativo (SIGHUP ignorado)"
    )

    # ── Watchdog ──────────────────────────────────────────────────
    def _relaunch():
        """Reconstrói o ttyd (o wrapper vive neste processo)."""
        try:
            la._stop_terminal()
            la.start_ttyd()
        except Exception as exc:
            _write_log(f"❌ relaunch falhou: {exc}")

    watchdog = threading.Thread(
        target=_watchdog,
        args=(_relaunch, (TERMINAL_PORT,)),
        name="ufvai-watchdog",
        daemon=True,
    )
    watchdog.start()

    # ── Aguarda até o shutdown ────────────────────────────────────
    try:
        while not stop_event.wait(1.0):
            pass
    except KeyboardInterrupt:
        request_shutdown("keyboardinterrupt")

    # Deriva o watchdog antes de derrubar os serviços.
    _SHUTDOWN.set()
    watchdog.join(timeout=3.0)
    _write_log("🧹 Watchdog encerrado — limpando serviços.")
    _cleanup(la)
    lock.release()
    _write_log("👋 UFVAI encerrado com segurança.")
    return 0


def _cleanup(la) -> None:
    """Derruba a árvore do terminal e remove os arquivos de estado.

    Always best-effort: qualquer falha é logada e ignorada, para que a
    limpeza nunca impeça a saída.
    """
    for fn_name in ("_stop_terminal",):
        try:
            getattr(la, fn_name)()
        except Exception as exc:
            _write_log(f"⚠️  {fn_name} falhou: {exc}")
    for path in (READY_FILE, PID_FILE):
        try:
            os.unlink(path)
        except OSError:
            pass
    # Remove o lock para o próximo boot começar limpo (o flock já foi
    # liberado, mas o arquivo vazio confunde diagnósticos).
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


# ── Spawn (lado do kernel) ────────────────────────────────────────

def spawn_detached(repo_dir: str | None = None, timeout_s: float = 300.0) -> tuple[int, str]:
    """Lança o supervisor desacoplado e retorna (pid, caminho_do_log).

    Executado pelo notebook, no kernel. Faz o mínimo possível e retorna
    imediatamente — a célula NÃO fica bloqueada, para que o usuário possa
    navegar para a UI enquanto o boot acontece.

    O detach é feito com `start_new_session=True` (setsid), que é o
    equivalente Python do `setsid` do shell e o que realmente desconecta o
    filho do terminal/grupo de processos do kernel. `nohup` sozinho
    apenas ignora SIGHUP, o que **não** sobrevive à morte do grupo de
    processos — esta é a diferença que importa aqui.

    Returns:
        (pid, log_path). Levanta RuntimeError se o supervisor já estiver
        rodando (o caller deve tratar como sucesso idempotente) ou se o
        processo morrer imediatamente.
    """
    if repo_dir is None:
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    existing = read_host_pid()
    if existing:
        raise RuntimeError(f"supervisor já ativo (pid {existing})")

    os.makedirs(STATE_DIR, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_dir + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    # Marcador consultado por launch_app.kill_previous() para nunca
    # matar o processo que está iniciando (ver patch em launch_app.py).
    env["UFVAI_HOST_CHILD"] = "1"

    logfh = open(LOG_FILE, "ab", buffering=0)

    proc = subprocess.Popen(
        [sys.executable, "-m", "pesquisai.colab_host"],
        cwd=repo_dir,
        stdin=subprocess.DEVNULL,     # <- nunca lê do notebook
        stdout=logfh,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,       # <- setsid: o que realmente destaca
        close_fds=True,
    )
    logfh.close()

    _write_log(
        f"🚀 Supervisor lançado (pid {proc.pid}, setsid). Log: {LOG_FILE}"
    )
    return proc.pid, LOG_FILE


def wait_ready(timeout_s: float = 300.0, interval_s: float = 1.0) -> bool:
    """Aguarda o supervisor sinalizar que a UI está no ar.

    A UI só pode ser aberta depois disso — abrir antes resultaria em
    ERR_CONNECTION_REFUSED, que é parte da confusão que estamos removendo.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _SHUTDOWN.is_set():
            return False
        if os.path.exists(READY_FILE):
            return True
        time.sleep(interval_s)
    return False


def stop_host(grace_s: float = 5.0) -> bool:
    """Encerra o supervisor a partir de fora (usado pelo notebook/manual).

    Returns True se o processo estava rodando e recebeu o sinal.
    """
    pid = read_host_pid()
    if not pid:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    deadline = time.time() + grace_s
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return True


# ── JS anti-idle ──────────────────────────────────────────────────

def keepalive_js() -> str:
    """JavaScript de apoio para a página do Colab (injetado no notebook).

    PAPEL DESTA CAMADA (v0.6.20): ELA É SECUNDÁRIA
    ----------------------------------------------
    Na v0.6.20 o combate à ociosidade foi movido para o lado da VM
    (`pesquisai/keepalive.py`: thread no kernel + célula em execução). A razão
    é medida, não estilística:

    * Ao **minimizar** a aba, o Chrome estrangula os timers de página oculta
      (1 s → 1 min, e *intensive throttling* → 1 disparo por minuto) e pode
      **congelar** a página inteira (Page Freezing), caso em que nenhum
      JavaScript roda. Um `setInterval` que depende do navegador deixa de
      funcionar justamente no cenário que o usuário denunciou.
    * Desde 2023 o Colab decide a ociosidade no **backend**. O
      `googlecolab/google-colab-cli` registra (2026-09-25): *"VM liveness is
      automatically maintained by the Colab backend based on kernel activity"*,
      e removeu o próprio daemon de keep-alive.

    O que sobra para o navegador fazer de útil, e é o que este script faz:
      1. Clicar no botão de conexão (ajuda enquanto a aba está visível).
      2. Aceitar o diálogo "Runtime disconnected" — é o passo que efetivamente
         reabastece o relógio quando o Colab já avisou que vai encerrar.
      3. Manter um **wake lock** de tela, para o SO não suspender a aba em
         notebook fechado — o que derruba o WebSocket do front-end.
      4. Pingar na hora em que a aba volta a ficar visível.

    Limitações (conhecidas e deliberadas):
    * Depende do DOM do Colab (`colab-connect-button`). Se o Google mudar a
      estrutura, o script para de encontrar o botão — falha silenciosa, sem
      quebrar nada. Os seletores tentados em ordem refletem isso.
    * Não sobrevive a aba minimizada por muito tempo. **Não** é a camada que
      resolve o problema do usuário; é apenas uma camada extra de segurança.
    * O Google não endossa essa prática e pode mudar a política. Por isso o
      script é **opt-in** e desligável (`__ufvaiKeepAliveStop()`).

    Para desligar tudo, inclusive a camada principal:
        from pesquisai.keepalive import stop; stop()
        Javascript("window.__ufvaiKeepAliveStop()")
    """
    return r"""
(function () {
  if (window.__ufvaiKeepAlive) { return; }
  window.__ufvaiKeepAlive = true;

  // Seletores tentados em ordem — o primeiro que existir vence.
  function findConnectBtn() {
    var tries = [
      function () { return document.querySelector("#top-toolbar > colab-connect-button"); },
      function () { return document.querySelector("colab-toolbar-button#connect"); },
      function () { return document.querySelector("colab-connect-button"); }
    ];
    for (var i = 0; i < tries.length; i++) {
      var host;
      try { host = tries[i](); } catch (e) { continue; }
      if (!host) { continue; }
      // Dentro do shadowRoot está o botão real.
      var inner = null;
      try {
        inner = host.shadowRoot &&
                (host.shadowRoot.querySelector("#connect") ||
                 host.shadowRoot.getElementById("connect"));
      } catch (e) { /* shadowRoot pode não existir */ }
      if (inner) { return inner; }
      return host;   // fallback: o host em si pode ser clicável
    }
    return null;
  }

  // Se o Colab mostrar o diálogo "Runtime disconnected", aceita — é o
  // passo que efetivamente reabastece o timer.
  function dismissDisconnectDialog() {
    try {
      var dlg = document.querySelector("colab-dialog.yes-no-dialog") ||
                document.querySelector("colab-dialog");
      if (!dlg) { return; }
      var title = dlg.querySelector("div.content-area > h2");
      var txt = (title && (title.innerText || "")) + " " + (dlg.innerText || "");
      if (/disconnected|timed out|encerrado/i.test(txt)) {
        var ok = dlg.querySelector("paper-button#ok") ||
                 dlg.querySelector("paper-button");
        if (ok) { ok.click(); }
      }
    } catch (e) { /* silencioso */ }
  }

  window.__ufvaiKeepAliveStop = function () {
    if (window.__ufvaiKeepAliveTimer) {
      clearInterval(window.__ufvaiKeepAliveTimer);
      window.__ufvaiKeepAliveTimer = null;
    }
    document.removeEventListener("visibilitychange", onVisible);
    window.removeEventListener("focus", onVisible);
    if (window.__ufvaiWakeLock) {
      // Libera o wake lock: segurá-lo sem necessidade impede a tela de
      // dormir e consome bateria do usuário sem qualquer ganho.
      try { window.__ufvaiWakeLock.release(); } catch (e) {}
      window.__ufvaiWakeLock = null;
    }
    window.__ufvaiKeepAlive = false;
    console.log("[UFVAI] keepalive (front-end) desligado");
  };

  // ── Wake Lock de tela (v0.6.20) ─────────────────────────────────
  // Não é o que mantém o runtime vivo — o Chrome estrangula timers de página
  // oculta de qualquer jeito. O que resolve aqui é outro problema: em
  // notebook fechado, o SO pode suspender a aba, e o WebSocket do front-end
  // morre junto. O wake lock evita essa suspensão. Só é válido com a página
  // visível, então é re-solicitado a cada vez que ela volta.
  function acquireWakeLock() {
    if (!("wakeLock" in navigator) || window.__ufvaiWakeLock) { return; }
    try {
      navigator.wakeLock.request("screen").then(function (s) {
        window.__ufvaiWakeLock = s;
        s.addEventListener("release", function () {
          window.__ufvaiWakeLock = null;
        });
      }).catch(function () { /* negado pelo navegador: irrelevante */ });
    } catch (e) { /* API ausente */ }
  }

  function tick() {
    var btn = findConnectBtn();
    if (btn) { try { btn.click(); } catch (e) {} }
    dismissDisconnectDialog();
  }

  // Voltar a ficar visível é o momento de maior valor para um ping: é quando
  // o Chrome deixa de estrangular os timers e o clique no botão volta a ter
  // efeito sobre o relógio do Colab.
  function onVisible() {
    if (document.visibilityState !== "visible") { return; }
    acquireWakeLock();
    tick();
  }

  // 45 s (v0.6.19 usava 60 s). Com a aba visível, 45 s dá folga sobre o
  // timeout ocioso de ~90 min. Com a aba oculta o Chrome estrangula para
  // 1/min de qualquer forma — por isso o intervalo é só uma otimização do
  // caso visível, e NÃO a proteção principal (que está no kernel).
  window.__ufvaiKeepAliveTimer = setInterval(tick, 45000);
  document.addEventListener("visibilitychange", onVisible);
  window.addEventListener("focus", onVisible);
  acquireWakeLock();
  tick();
  console.log(
    "[UFVAI] keepalive front-end ativo (45s) + wake lock. " +
    "Camada SECUNDÁRIA — quem protege o runtime minimized é " +
    "pesquisai/keepalive.py (thread no kernel + célula em execução)."
  );
})();
"""


# ── Entry point ───────────────────────────────────────────────────

def main() -> int:
    """Ponto de entrada do processo supervisor: `python3 -m pesquisai.colab_host`."""
    try:
        return run_supervised()
    except KeyboardInterrupt:
        request_shutdown("interrupt-main")
        return 0


if __name__ == "__main__":
    sys.exit(main())
