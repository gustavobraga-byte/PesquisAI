"""Inicialização automática do servidor de voz do UFVAI.

Para um **novo usuário**, o módulo `voice/` existe no Drive mas o servidor
FastAPI (porta 8010) ainda não está rodando. Este módulo detecta isso e sobe
o servidor automaticamente, sem exigir que o usuário digite comandos.

 Chamado pelo gateway `webui_server.py` quando uma rota `/voz/*` é acessada
e o servidor está offline.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import logging
from pathlib import Path

logger = logging.getLogger("ufvai.voice")

VOICE_PORT = 8010
_LOCK = __import__("threading").Lock()
_STARTED = False


def _port_open(port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _find_voice_dir() -> Path | None:
    """Localiza a pasta `voice/` no projeto (Drive ou offline)."""
    here = Path(__file__).resolve().parent.parent  # raiz do projeto pesquisai
    candidates = [
        here / "voice",
        Path("/content/drive/My Drive/PesquisAI/voice"),
        Path("/content/drive/My Drive/PesquisAI/agentes/lfm3-voz"),
        Path.home() / "PesquisAI" / "voice",
    ]
    for c in candidates:
        if (c / "server.py").is_file():
            return c
    return None


def ensure_server(wait_seconds: float = 45.0) -> bool:
    """Garante que o servidor de voz está no ar. True se online."""
    global _STARTED
    if _port_open(VOICE_PORT):
        return True
    with _LOCK:
        if _port_open(VOICE_PORT):
            return True
        voice_dir = _find_voice_dir()
        if not voice_dir:
            logger.warning("Pasta voice/ não encontrada — não é possível iniciar o servidor de voz.")
            return False
        # Não sob o modelo na memória: o download é sob demanda (usuário escolhe).
        env = dict(os.environ)
        env["UFVAI_VOZ_PRELOAD"] = "0"
        env["PYTHONPATH"] = str(voice_dir) + os.pathsep + env.get("PYTHONPATH", "")
        try:
            subprocess.Popen(
                [sys.executable, "server.py"],
                cwd=str(voice_dir),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
            )
            _STARTED = True
            logger.info("Servidor de voz iniciado automaticamente de %s", voice_dir)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao iniciar servidor de voz: %s", exc)
            return False

    # Aguarda o servidor subir (não carrega modelo, só sobe o FastAPI).
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _port_open(VOICE_PORT):
            return True
        time.sleep(0.5)
    return False
