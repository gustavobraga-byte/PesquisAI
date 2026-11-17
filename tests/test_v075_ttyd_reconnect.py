"""Reconnect do terminal: vigia no iframe + diagnóstico de reinícios.

Relato do autor (24/10/2026): "o terminal está pedindo 'reconnect' depois de
um tempo, mesmo com o opencode rodando".

Causa: o cliente do ttyd só reconecta sozinho quando o close code != 1000.
Num reinício do servidor (troca de idioma, restore, auto-cura) ele fica em
"Press ⏎ to Reconnect" / "Reconnecting..." esperando o usuário — enquanto o
`opencode` (tmux) continua vivo.

Cobre:
  * vigia injetado no <head> do index do ttyd (Enter sintético + reload);
  * /api/ttyd_ready devolve o pid (o frontend detecta reinício);
  * o iframe é recarregado quando o pid muda;
  * wrapper.log registra quem parou/subiu o ttyd.

    pytest -o addopts="" tests/test_v075_ttyd_reconnect.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import launch_app as la  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class TestVigiaNoIframe:
    def test_script_injeta_auto_reconnect(self):
        js = la._get_touch_handler_script()
        assert "AUTO-RECONNECT" in js
        assert "xterm-helper-textarea" in js
        assert "keyCode:13" in js or "keyCode: 13" in js

    def test_reload_so_com_servidor_vivo(self):
        js = la._get_touch_handler_script()
        # não pode recarregar em laço quando o ttyd está fora
        assert "fetch('/health'" in js
        assert "_reloads<3" in js

    def test_injetado_no_head_antes_do_bundle(self):
        src = _read("pesquisai/launch_app.py")
        bloco = src[src.find("def _prepare_ttyd_touch_index"):]
        bloco = bloco[:bloco.find("def ", 10)]
        assert 'html_content.replace("<head>", "<head>" + touch_script' in bloco
        # o patch do WebSocket precisa rodar antes do bundle do ttyd
        assert "ANTES do bundle" in bloco


class TestPidDoTtyd:
    def test_ttyd_ready_devolve_pid(self):
        src = _read("pesquisai/launch_app.py")
        bloco = src[src.find('if p == "/api/ttyd_ready"'):]
        bloco = bloco[:bloco.find("if p ==", 10)]
        assert '"pid": getattr(_TTYD_PROC, "pid", None) if ready else None' in bloco

    def test_frontend_recarrega_quando_pid_muda(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert "_ttydPid" in src
        assert "d.pid === _ttydPid" in src
        assert "contentWindow.location.reload()" in src


class TestDiagnostico:
    def test_event_log_grava_com_pilha(self, tmp_path, monkeypatch):
        monkeypatch.setattr(la, "_ufvai_log_dir", lambda: str(tmp_path))
        la._ttyd_event_log("spawn", "pid=123")
        txt = (tmp_path / "wrapper.log").read_text(encoding="utf-8")
        assert "spawn pid=123" in txt
        assert "test_v075_ttyd_reconnect.py" in txt  # pilha de chamadas

    def test_spawn_e_stop_registram_evento(self):
        src = _read("pesquisai/launch_app.py")
        assert '_ttyd_event_log("spawn", f"pid={proc.pid}' in src
        assert '_ttyd_event_log("stop"' in src
        assert '_ttyd_event_log("revive"' in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-o", "addopts="]))
