"""
keepalive.py — Anti-encerramento do runtime do Google Colab (v0.6.20).

O PROBLEMA QUE ESTE MÓDULO RESOLVE
==================================
O Colab encerra o runtime ocioso e o sintoma reportado pelo usuário era: *"o
Colab está constantemente encerrando o ambiente de execução — quero acabar com
a possibilidade de ele encerrar se eu minimizar a página"*.

Por que a v0.6.19 (e o keepalive JS da v0.6.20 anterior) NÃO resolvia
---------------------------------------------------------------------
A mitigação anterior morava **inteiramente no navegador**: um `setInterval` de
60 s que clicava no botão de conexão do Colab. Esse desenho é justamente
anulado pelo sintoma reportado. Ao minimizar a aba, o Chrome:

1. estrangula os timers de página oculta (1 s → 1 min, e *intensive
   throttling* → 1 disparo por minuto); e
2. pode **congelar** a página inteira (Page Freezing), caso em que nenhum
   JavaScript roda.

Ou seja: o relógio que se tentava driblar vivia no navegador, e o navegador era
justo o que desligava. Além disso, o Colab decide a ociosidade no **backend**,
não no front-end.

O QUE O GOOGLE DIZ HOJE (verificado, não suposição)
---------------------------------------------------
`googlecolab/google-colab-cli` (docs/01_session_management.md, log de
**2026-09-25**) removeu o próprio daemon de keep-alive e registra:

    "VM liveness is automatically maintained by the Colab backend based on
     kernel activity. The CLI runs no keep-alive daemon."

O ping HTTP no TFE que o CLI usava antes (`GET /tun/m/<endpoint>/keep-alive/`)
foi abandonado porque exige o *bearer token* Gaia do usuário. Testado neste
runtime em 2026-09-30 → **HTTP 401 Unauthorized** (o id do endpoint aparece em
`KMP_EXTRA_ARGS → --tunnel_background_save_url`, mas sem o token não há ping).

Ou seja: o sinal que importa é **atividade do kernel**, e ela precisa vir do
lado da VM — não do navegador.

A ARQUITETURA (três camadas, nesta ordem de força)
=================================================

    L0  keepalive.loop()     célula que fica EXECUTANDO
                              → o kernel está ativamente executando
                              → funciona COM a aba minimizada  ← principal
    L1  keepalive.start()    thread daemon no kernel
                              → ping `cell_javascript_eval` a cada 50 s
                              → sobrevive a Ctrl+C e ao fechamento da aba
    L2  colab_host.keepalive_js()
                              → clique no botão + diálogo "Runtime
                                disconnected"
                              → secundária: neutralizada por aba oculta

Decisões de implementação que evitam bugs reais
==============================================
* **`expect_reply=False`, sempre.** As respostas do Colab chegam pelo socket
  `stdin` — o **mesmo** por onde chega o que o usuário digita. Ler a resposta
  descartaria o `input()` do usuário. O próprio `google/colab/_system_commands.py`
  avisa em comentário: "If user input is provided while the blocking_request
  call is still waiting for a colab_reply, the input will be dropped". Portanto
  este módulo **nunca** lê o stdin: só envia.
* **Dois locks, ordem fixa.** `_send_lock` protege o socket iopub do ZMQ (que
  não é thread-safe); `_state_lock` protege o estado do módulo. Toda aquisição
  acontece na ordem **estado → envio**, nunca o inverso, o que elimina
  deadlock mesmo com L0 e L1 ativos ao mesmo tempo. `_state_lock` é um
  `RLock` porque `status()` é chamado de dentro de seções que já o seguram.
* **Sem reply ⇒ sem mentira no status.** Como não lemos resposta, `pings_ok`
  significa "mensagem entregue ao socket do kernel", não "o Colab confirmou".
  O próprio dicionário de status diz isso, para ninguém diagnosticar por
  cima de um número que não significa o que parece.

LIMITE HONESTO (leia antes de prometer qualquer coisa ao usuário)
================================================================
Nenhum código dentro da VM pode impedir o Colab de destruir o runtime. Ainda
existe, no nível do serviço:

* limite de ~12 h de execução contínua (teto do serviço, em qualquer plano);
* expiração por inatividade mesmo com keep-alive, se o backend decidir;
* esgotamento de cota do plano (free) e reclaims pré-emptivos;
* prompts de CAPTCHA ou verificação de conta.

Reiniciar o kernel (`Runtime → Reiniciar sessão`) também derruba a thread L1 e
a célula L0 — o supervisor detached sobrevive, mas o keepalive precisa ser
reiniciado (é só reexecutar a célula do notebook).

O que este módulo faz é **maximizar a chance de o runtime sobreviver** e, quando
ele cair mesmo assim, deixar a recuperação a um clique — porque toda a memória,
skills e configuração vivem no Drive, não na VM.

Uso
---
    # Na célula do notebook (lado kernel, efêmero):
    from pesquisai.keepalive import start, stop, status, loop
    start()        # L1 — não bloqueia
    loop()         # L0 — bloqueia; use numa célula própria, no fim do notebook

    # Desligar (scripts, testes, política):
    export UFVAI_NO_KEEPALIVE=1
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time

# ── Configuração ───────────────────────────────────────────────────

# 50 s: bem abaixo do timeout ocioso (~90 min) e abaixo de 60 s, que é o piso
# do *intensive throttling* do Chrome — acima de 1 minuto o navegador já
# estrangula tudo para 1 disparo/minuto de qualquer forma.
DEFAULT_INTERVAL_S = 50.0

# Mínimo e máximo aceitos: abaixo de 30 s é desperdício sem ganho; acima de
# 60 s o Chrome estrangula de todo modo, então aumentar não ajuda ninguém.
MIN_INTERVAL_S = 30.0
MAX_INTERVAL_S = 60.0

# O estado vive no kernel, mas a UI é servida pelo supervisor (outro processo).
# O arquivo é a ponte entre os dois. Sem ele, a UI não teria como saber se o
# keepalive está vivo.
try:  # pragma: no cover - import defensivo
    from .colab_host import STATE_DIR as _HOST_STATE_DIR
except Exception:  # pragma: no cover
    _HOST_STATE_DIR = os.path.join(tempfile.gettempdir(), "ufvai-host")

STATUS_FILE = os.path.join(_HOST_STATE_DIR, "keepalive.json")

# Variável de ambiente para desligar (mesma convenção de run_fast.py).
ENV_DISABLE = "UFVAI_NO_KEEPALIVE"

# Script enviado ao front-end. Idempotente e nunca lança: um erro aqui só
# apareceria no console do navegador, mas mesmo assim é melhor silenciar para
# não sujar a saída do usuário.
#
# `invokeFunction('keepAlive')` é o caminho histórico (colabtf). Fica como
# **complemento**: se a função não existir mais, o `typeof` evita o erro e o
# ping continua valendo pelo simples fato de a mensagem ter sido enviada.
_PING_SCRIPT = (
    "(function(){try{"
    "if(window.colab&&colab.kernel"
    "&&typeof colab.kernel.invokeFunction==='function'){"
    "colab.kernel.invokeFunction('keepAlive');}"
    "}catch(e){}"
    "if(window.__ufvaiKA){window.__ufvaiKA.lastPing=Date.now();}"
    "})();"
)

# ── Estado do processo (módulo) ────────────────────────────────────

# Ordem de aquisição SEMPRE estado → envio. Nunca o inverso.
_state_lock = threading.RLock()   # protege as globais abaixo
_send_lock = threading.Lock()     # protege o socket iopub do ZMQ

_stop = threading.Event()
_thread: "threading.Thread | None" = None
_started_at: "float | None" = None
_interval_s: float = DEFAULT_INTERVAL_S
_pings_ok = 0
_pings_fail = 0
_consecutive_failures = 0
_last_ping_at: "float | None" = None
_last_error = ""


# ── Detecção de ambiente ───────────────────────────────────────────

def disabled() -> bool:
    """True se `UFVAI_NO_KEEPALIVE` desligar o mecanismo."""
    return os.environ.get(ENV_DISABLE, "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def in_colab_kernel() -> bool:
    """True se este processo é um kernel real do Google Colab.

    Não basta o `/content/drive` existir: no modo offline a pasta é montada e o
    keepalive não tem sobre o que agir. O teste é o do próprio Colab
    (`google.colab._ipython.in_ipython()`) mais a presença do kernel app.
    """
    try:
        from google.colab import _ipython  # type: ignore
    except Exception:
        return False
    try:
        if not _ipython.in_ipython():
            return False
        _ipython.get_ipython()
        _ipython.get_kernelapp()
    except Exception:
        return False
    return True


def _clamp(interval_s: float) -> float:
    return max(MIN_INTERVAL_S, min(float(interval_s), MAX_INTERVAL_S))


# ── O ping ─────────────────────────────────────────────────────────

def ping() -> bool:
    """Envia **um** heartbeat de atividade do kernel. Não bloqueia.

    Returns:
        True se a mensagem foi entregue ao socket do kernel; False se não havia
        kernel do Colab ou se o envio falhou.

    Sobre o significado do True: o Colab **não** confirma o recebimento (ler a
    resposta exigiria consumir o stdin — ver docstring do módulo). True
    significa "a atividade foi emitida", não "o runtime foi salvo".
    """
    global _pings_ok, _consecutive_failures, _last_ping_at, _last_error

    try:
        from google.colab import _ipython, _message  # type: ignore
    except Exception as exc:
        _record_failure(f"google.colab indisponível: {exc}")
        return False

    try:
        shell = _ipython.get_ipython()
        # `_send_lock` é obrigatório: iopub_socket do ZMQ não é thread-safe e
        # L0 e L1 podem estar ativos ao mesmo tempo.
        with _send_lock:
            _message.send_request(
                "cell_javascript_eval",
                {"script": _PING_SCRIPT},
                parent=shell.parent_header,
                expect_reply=False,   # NUNCA True: roubaria o input() do usuário
            )
    except Exception as exc:
        _record_failure(f"{type(exc).__name__}: {exc}")
        return False

    with _state_lock:
        _pings_ok += 1
        _consecutive_failures = 0
        _last_ping_at = time.time()
    return True


def _record_failure(reason: str) -> None:
    global _pings_fail, _consecutive_failures, _last_error
    with _state_lock:
        _pings_fail += 1
        _consecutive_failures += 1
        _last_error = reason


# ── Status ─────────────────────────────────────────────────────────

def status() -> dict:
    """Estado atual. Seguro para `json.dumps` e para leitura de outro processo."""
    with _state_lock:
        started = _started_at
        alive = bool(_thread and _thread.is_alive())
        return {
            "enabled": not disabled(),
            "in_colab_kernel": in_colab_kernel(),
            "running": alive,
            "thread_alive": alive,
            "interval_s": _interval_s,
            "started_at": started,
            "uptime_s": (time.time() - started) if started else 0.0,
            "pings_ok": _pings_ok,
            "pings_fail": _pings_fail,
            "consecutive_failures": _consecutive_failures,
            "last_ping_at": _last_ping_at,
            "last_ping_age_s": (
                (time.time() - _last_ping_at) if _last_ping_at else None
            ),
            "last_error": _last_error,
            "transport": "colab_message" if in_colab_kernel() else "none",
            "note": (
                "pings_ok = mensagens emitidas pelo kernel, não confirmadas "
                "pelo Colab (este módulo nunca lê o stdin do usuário)."
            ),
            "pid": os.getpid(),
            "updated_at": time.time(),
        }


def _write_status_file() -> None:
    """Publica o status em disco para o supervisor/UI lerem.

    Escrita atômica (grava em .tmp e renomeia): se a leitura ocorrer no meio, o
    leitor vê a versão anterior inteira, nunca um JSON truncado.
    """
    try:
        os.makedirs(_HOST_STATE_DIR, exist_ok=True)
        tmp = f"{STATUS_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(status(), fh, ensure_ascii=False)
        os.replace(tmp, STATUS_FILE)
    except Exception:
        pass


def read_status_file() -> "dict | None":
    """Lê o status publicado no disco.

    Existe como função própria porque quem chama é **outro processo** (o
    wrapper HTTP dentro do supervisor), que não enxerga as globais deste módulo.
    """
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def format_status_line() -> str:
    """Linha curta para imprimir no notebook e nos logs."""
    st = status()
    if not st["enabled"]:
        return f"⏸️  keepalive desligado ({ENV_DISABLE})"
    if not st["in_colab_kernel"]:
        return "ℹ️  fora de um kernel do Colab — keepalive inativo (não se aplica)"
    age = st["last_ping_age_s"]
    age_txt = "nenhum ainda" if age is None else f"{age:.0f}s atrás"
    state = "ativo" if st["running"] else "parado"
    return (
        f"{'🟢' if st['running'] else '🟡'} keepalive {state} · "
        f"uptime {st['uptime_s'] / 60:.0f} min · "
        f"{st['pings_ok']} pings · último {age_txt} · "
        f"ciclo {st['interval_s']:.0f}s"
    )


# ── L1 — thread daemon ─────────────────────────────────────────────

def _run(interval_s: float) -> None:
    """Loop da thread. Publica o status a cada ciclo, mesmo sem pingar."""
    _write_status_file()
    while not _stop.is_set():
        if _stop.wait(interval_s):
            break
        ping()
        _write_status_file()
    _write_status_file()


def start(interval_s: "float | None" = None) -> dict:
    """Inicia a camada L1 (thread daemon). Idempotente. Não bloqueia.

    Returns:
        O dicionário de status resultante.
    """
    global _thread, _started_at, _interval_s

    st = status()
    if not st["enabled"] or not st["in_colab_kernel"]:
        # Fora do Colab (ou desligado por env) não há o que pingar. Registrar e
        # sair é melhor do que criar uma thread que gira sem propósito — o
        # pacote .deb, por exemplo, não precisa de keepalive nenhum.
        _write_status_file()
        return status()

    # Ping imediato antes de qualquer lock de estado: garante que o front-end
    # já registra atividade enquanto a thread ainda está nacendo.
    ping()

    with _state_lock:
        if _thread is not None and _thread.is_alive():
            _write_status_file()   # já está no ar
            return status()
        _interval_s = _clamp(interval_s or DEFAULT_INTERVAL_S)
        _stop.clear()
        _started_at = time.time()
        _thread = threading.Thread(
            target=_run, args=(_interval_s,),
            name="ufvai-keepalive", daemon=True,
        )
        _thread.start()

    _write_status_file()
    return status()


def stop() -> dict:
    """Para a camada L1. Idempotente. Não mexe na camada L0 (célula)."""
    global _thread, _started_at
    _stop.set()
    with _state_lock:
        th = _thread
    if th is not None and th.is_alive():
        th.join(timeout=3.0)
    with _state_lock:
        _thread = None
        _started_at = None
    _write_status_file()
    return status()


def ensure_started(interval_s: "float | None" = None) -> dict:
    """Atalho para a célula do notebook: `start()` que não duplica thread."""
    return start(interval_s)


# ── L0 — loop de célula (bloqueante) ───────────────────────────────

def loop(interval_s: "float | None" = None, print_every: float = 300.0) -> None:
    """Mantém o kernel **executando** até o usuário interromper (Ctrl+C / ■).

    Esta é a camada que sobrevive à aba minimizada: enquanto a célula está em
    execução, o backend vê o kernel ativo, sem depender de nenhum JavaScript no
    navegador.

    Não polui o output: imprime no máximo uma linha a cada `print_every`
    segundos (5 min por padrão). Cada iteração também emite o ping do L1, para
    que quem tem a aba aberta receba o sinal no front-end.

    Interromper a célula (■) **não** desliga o keepalive: a thread L1 continua
    sozinha. É intencional — a célula é a camada mais forte, mas o watchdog
    precisa sobreviver a um Ctrl+C acidental.
    """
    st = status()
    if not st["enabled"]:
        print(f"⏸️  keepalive desligado ({ENV_DISABLE}=1) — loop ignorado.")
        return
    if not st["in_colab_kernel"]:
        print(
            "ℹ️  Este loop só é útil dentro de um kernel do Google Colab. "
            "Fora dele (modo offline/.deb) não há runtime para manter vivo."
        )
        return

    period = _clamp(interval_s or DEFAULT_INTERVAL_S)
    print("🫀  Keepalive ATIVO — o runtime não deve ser encerrado por ociosidade.")
    print(f"    ciclo de {period:.0f}s · Ctrl+C (ou ■) para interromper esta célula")
    print(f"    a camada em segundo plano continua sozinha ({format_status_line()})")
    print()

    started = time.time()
    next_report = print_every
    elapsed = 0.0
    try:
        while True:
            time.sleep(period)
            ping()
            elapsed += period
            if elapsed >= next_report:
                next_report += print_every
                mins = (time.time() - started) / 60.0
                print(
                    f"🫀  {mins:.0f} min · {status()['pings_ok']} pings "
                    f"· {format_status_line()}"
                )
    except KeyboardInterrupt:
        print(
            "\n⏹️  Célula de keepalive interrompida. A camada em segundo plano "
            "(thread) continua ativa — o runtime segue protegido."
        )


__all__ = [
    "DEFAULT_INTERVAL_S", "ENV_DISABLE", "MAX_INTERVAL_S", "MIN_INTERVAL_S",
    "STATUS_FILE", "disabled", "ensure_started", "format_status_line",
    "in_colab_kernel", "loop", "ping", "read_status_file", "start", "status",
    "stop",
]
