"""
keepalive.py — Mantém a sessão do Colab ativa enquanto o UFVAI roda.

Por que uma célula bloqueante (e não um subprocesso)?
- O keep-alive antigo era um subprocesso que gravava uma linha por minuto. O
  Colab decide ociosidade pela atividade do notebook (execução de célula e
  interação com a página). Processo em segundo plano não conta como atividade.
- Uma célula em execução mantém o kernel ocupado. Enquanto ela roda, a sessão
  não é tratada como ociosa — até o teto do runtime (~12 h) ou a cota.

Limites honestos: nenhum código garante a sessão para sempre. Este módulo NÃO
simula cliques na interface do Colab (isso contraria os termos do serviço).

Recuperação: OPCIONAL (`on_unhealthy`). A célula do UFVAI NÃO a usa: reiniciar o
ttyd derruba a sessão do opencode em andamento. Se algum serviço cair, o painel
mostra e basta executar a célula de novo. A sessão do terminal sobrevive a quedas
do WebSocket graças ao tmux (launch_app._ttyd_shell_argv).
"""

from __future__ import annotations

import datetime
import os
import socket
import threading
import time
from typing import Callable, Iterable, Optional

from .constants import TERMINAL_PORT, WRAPPER_PORT, logger

DEFAULT_LOG = "/tmp/pesquisai/ufvai_keepalive.log"

_STOP = threading.Event()
_RUNNING = threading.Event()


def request_stop() -> None:
    """Pede a parada do laço (chamado pelo botão SAIR antes de desconectar)."""
    _STOP.set()


def is_running() -> bool:
    """True enquanto `run_keepalive` está bloqueando a célula."""
    return _RUNNING.is_set()


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """True se alguém aceita conexão em host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def health_snapshot(ports: Iterable[int] = (TERMINAL_PORT, WRAPPER_PORT)) -> dict:
    """Estado (aberta/fechada) de cada porta de serviço do UFVAI."""
    return {int(p): port_open(int(p)) for p in ports}


def recover_services(snapshot: dict) -> None:
    """Reinicia o que estiver fora do ar (terminal e/ou servidor da interface)."""
    from . import launch_app as la  # import tardio: evita ciclo na importação

    if not snapshot.get(TERMINAL_PORT, True):
        la.restart_ttyd_with_lang(la._current_lang or "pt_BR")
    if not snapshot.get(WRAPPER_PORT, True):
        la.start_wrapper_server()


def _log(path: Optional[str], message: str) -> None:
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"{stamp} {message}"
    logger.debug(line)
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def run_keepalive(
    interval_s: float = 60.0,
    log_path: Optional[str] = DEFAULT_LOG,
    on_unhealthy: Optional[Callable[[dict], None]] = None,
    ports: Iterable[int] = (TERMINAL_PORT, WRAPPER_PORT),
    max_hours: Optional[float] = None,
    clock: Callable[[], float] = time.monotonic,
    on_tick: Optional[Callable[[dict], None]] = None,
) -> str:
    """Bloqueia a célula, verificando as portas a cada `interval_s` segundos.

    Args:
        interval_s: intervalo entre verificações.
        log_path: arquivo local de log (fora do Drive, para não gerar tráfego).
        on_unhealthy: chamado após 2 verificações seguidas com falha.
        ports: portas de serviço a verificar.
        max_hours: teto opcional de duração do laço.
        clock: relógio (injetável para testes).
        on_tick: chamado a CADA ciclo (inclusive o primeiro) com
            {"healthy", "snap", "failures", "elapsed_s"}. O notebook usa para
            atualizar o painel da célula: essa saída é atividade do kernel, que
            é o que o Colab mede para decidir ociosidade. Laço silencioso não conta.

    Returns:
        Motivo da saída: 'parado' (request_stop) ou 'limite' (max_hours).
    """
    _STOP.clear()
    _RUNNING.set()
    started = clock()
    failures = 0
    ports = tuple(ports)
    try:
        _log(log_path, "keep-alive iniciado")
        while not _STOP.is_set():
            snap = health_snapshot(ports)
            healthy = all(snap.values())
            _log(log_path, f"ok={healthy} portas={snap}")
            if healthy:
                failures = 0
            else:
                failures += 1
                if on_unhealthy is not None and failures >= 2 and not _STOP.is_set():
                    try:
                        on_unhealthy(snap)
                        _log(log_path, "recuperação executada")
                    except Exception as exc:  # noqa: BLE001
                        _log(log_path, f"recuperação falhou: {exc}")
                    failures = 0
            if on_tick is not None:
                try:
                    on_tick({
                        "healthy": healthy,
                        "snap": snap,
                        "failures": failures,
                        "elapsed_s": clock() - started,
                    })
                except Exception as exc:  # noqa: BLE001
                    _log(log_path, f"heartbeat falhou: {exc}")
            if max_hours is not None and clock() - started >= max_hours * 3600:
                _log(log_path, "limite de duração atingido")
                return "limite"
            _STOP.wait(interval_s)
        _log(log_path, "keep-alive parado")
        return "parado"
    finally:
        _RUNNING.clear()
