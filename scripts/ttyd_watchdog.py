#!/usr/bin/env python3
"""ttyd_watchdog.py — mantém o TERMINAL (ttyd) SEMPRE rodando.

Por que isto existe (v0.7.11-web32): a versão web passou a ser a visão
padrão da interface, mas o terminal é peça essencial — é ele que mantém
viva a sessão do agente (tmux). Se o ttyd cair, o terminal deixa de
existir para o usuário e a conversa pode ser perdida.

O que esta vigia faz, a cada INTERVAL segundos:

  1. confere se a porta do terminal responde;
  2. se ela caiu, religa o ttyd com **exatamente** o mesmo comando e o
     mesmo ambiente que estavam rodando (que usa ``tmux new -A``: ANEXA à
     sessão existente — a conversa continua, não é recriada).

É redundante de propósito: já existem a vigia do processo (em
``launch_app.py``) e a vigia do navegador (no wrapper). Esta sobrevive à
queda do próprio processo do UFVAI.

Uso (o boot já faz isso):
    setsid nohup python3 scripts/ttyd_watchdog.py >/dev/null 2>&1 </dev/null &

Variáveis de ambiente: UFVAI_TTYD_PORT (8000), UFVAI_TTYD_WATCHDOG_INTERVAL
(25 s), UFVAI_TTYD_WATCHDOG_LOG (/tmp/ufvai-ttyd-watchdog.log),
UFVAI_TTYD_ARGV_FILE (/tmp/ufvai-ttyd-argv.json).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

PORT = int(os.environ.get("UFVAI_TTYD_PORT", "8000") or 8000)
INTERVAL = float(os.environ.get("UFVAI_TTYD_WATCHDOG_INTERVAL", "25") or 25)
LOG = Path(os.environ.get("UFVAI_TTYD_WATCHDOG_LOG", "/tmp/ufvai-ttyd-watchdog.log"))
ARGV_FILE = Path(os.environ.get("UFVAI_TTYD_ARGV_FILE", "/tmp/ufvai-ttyd-argv.json"))


def _log(msg: str) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:  # noqa: BLE001 — a vigia nunca deve morrer por um log
        pass


def porta_aberta(porta: int = PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
            return True
    except OSError:
        return False


def _proc_ttyd() -> tuple[list[str], dict[str, str]] | None:
    """Localiza o ttyd vivo e devolve (argv, env) exatamente como estão."""
    for entrada in os.listdir("/proc"):
        if not entrada.isdigit():
            continue
        try:
            bruto = Path(f"/proc/{entrada}/cmdline").read_bytes()
            argv = [p.decode("utf-8", "replace") for p in bruto.split(b"\0") if p]
            if len(argv) < 2:
                continue
            if "ttyd" not in os.path.basename(argv[0]):
                continue
            # confirma a porta: o ttyd é chamado com "-p <porta>"
            if str(PORT) not in argv:
                continue
            env_bruto = Path(f"/proc/{entrada}/environ").read_bytes()
            env = {}
            for par in env_bruto.split(b"\0"):
                if not par:
                    continue
                chave, _, valor = par.decode("utf-8", "replace").partition("=")
                if chave:
                    env[chave] = valor
            return argv, env
        except Exception:  # noqa: BLE001 — /proc pode sumir no meio da leitura
            continue
    return None


def capturar() -> bool:
    achado = _proc_ttyd()
    if not achado:
        return False
    argv, env = achado
    try:
        ARGV_FILE.write_text(
            json.dumps({"argv": argv, "env": env}, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def religar() -> bool:
    if not ARGV_FILE.exists() and not capturar():
        return False
    try:
        dados = json.loads(ARGV_FILE.read_text(encoding="utf-8"))
        argv = [str(a) for a in dados.get("argv") or []]
        env = {str(k): str(v) for k, v in (dados.get("env") or {}).items()}
    except Exception as exc:  # noqa: BLE001
        _log(f"argv do ttyd ilegível: {exc}")
        return False
    if not argv:
        return False
    env.setdefault("PATH", os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"))
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("ab") as saida:
            subprocess.Popen(
                argv, env=env, stdout=saida, stderr=saida,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        _log(f"ttyd religado na porta {PORT}")
        return True
    except Exception as exc:  # noqa: BLE001
        _log(f"falha ao religar o ttyd: {exc}")
        return False


def main() -> int:
    _log(f"vigia do terminal iniciada (porta {PORT}, a cada {int(INTERVAL)}s)")
    capturar()
    while True:
        time.sleep(INTERVAL)
        if porta_aberta():
            capturar()      # mantém o comando/ambiente atualizados
            continue
        _log(f"porta {PORT} fechada — religando o terminal")
        religar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
