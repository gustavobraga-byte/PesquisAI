"""Auto-cura do terminal (v0.7.5, sem bump).

Relato do autor (24/10/2026): "está carregando sempre". O ttyd havia sido
morto (SIGKILL) e a porta 8000 ficou fechada — a interface ficava no splash
"Iniciando terminal…" para sempre.

A correção religa o ttyd ANEXANDO à sessão tmux existente (`tmux new -A`),
sem matar o `opencode` que está rodando, e é acionada pelo próprio
`/api/ttyd_ready` (que a interface já consulta a cada 250 ms).

    pytest -o addopts="" tests/test_v075_ttyd_autorevive.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import launch_app as la  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_ttyd_log(tmp_path, monkeypatch):
    """Os testes não podem tocar no terminal real nem no log do runtime.

    `_build_ttyd_cmd` prepara o index do ttyd (subia um ttyd temporário e,
    antes da correção, rodava `pkill -9 -x ttyd` — matava o terminal vivo).
    """
    monkeypatch.setattr(la, "_ufvai_log_dir", lambda: str(tmp_path))
    monkeypatch.setattr(la, "_prepare_ttyd_touch_index", lambda env: None)
    yield


class _Alive:
    def poll(self):
        return None


class _Dead:
    def poll(self):
        return -9


@pytest.fixture(autouse=True)
def _reseta(monkeypatch):
    monkeypatch.setattr(la, "_LAST_TTYD_REVIVE", 0.0)
    monkeypatch.setattr(la, "_TTYD_PROC", _Dead())
    yield


def test_nao_duplica_ttyd_vivo(monkeypatch):
    monkeypatch.setattr(la, "_TTYD_PROC", _Alive())
    chamou = []
    monkeypatch.setattr(la, "_spawn_ttyd", lambda *a, **k: chamou.append(1))
    assert la._revive_ttyd() is False
    assert chamou == []


def test_religa_quando_o_processo_morreu(monkeypatch):
    capturado = {}

    def fake_spawn(args, env):
        capturado["args"] = args

    monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
    monkeypatch.setattr(la, "_spawn_ttyd", fake_spawn)
    monkeypatch.setattr(la, "_wait_port_open", lambda *a, **k: True)
    monkeypatch.setattr(la, "_remember_ttyd_session", lambda sid: capturado.update(sid=sid))
    monkeypatch.setattr(la, "_current_ttyd_session", "ses_viva")
    assert la._revive_ttyd() is True
    assert capturado["sid"] == "ses_viva"
    cmd = " ".join(capturado["args"])
    assert "tmux" in cmd and "-A" in cmd, "deve ANEXAR ao tmux (não recriar a sessão)"
    assert '--session "ses_viva"' in cmd


def test_nao_religa_em_rajada(monkeypatch):
    monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
    monkeypatch.setattr(la, "_spawn_ttyd", lambda *a, **k: None)
    monkeypatch.setattr(la, "_wait_port_open", lambda *a, **k: True)
    monkeypatch.setattr(la, "_remember_ttyd_session", lambda sid: None)
    assert la._revive_ttyd() is True
    # segunda chamada imediata: bloqueada pela janela mínima de 5 s
    assert la._revive_ttyd() is False


def test_forca_ignora_a_janela(monkeypatch):
    monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
    monkeypatch.setattr(la, "_spawn_ttyd", lambda *a, **k: None)
    monkeypatch.setattr(la, "_wait_port_open", lambda *a, **k: True)
    monkeypatch.setattr(la, "_remember_ttyd_session", lambda sid: None)
    assert la._revive_ttyd() is True
    assert la._revive_ttyd(force=True) is True


def test_falha_nao_propaga_excecao(monkeypatch):
    monkeypatch.setattr(la, "resolve_opencode", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert la._revive_ttyd() is False


def test_endpoint_aciona_a_auto_cura():
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "pesquisai", "launch_app.py"), encoding="utf-8") as fh:
        src = fh.read()
    bloco = src[src.find('if p == "/api/ttyd_ready":'):]
    bloco = bloco[:bloco.find("if p ==", 10)]
    assert "if not ready:" in bloco
    assert "ready = _revive_ttyd()" in bloco
