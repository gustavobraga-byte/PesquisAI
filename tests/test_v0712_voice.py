"""Testes offline da v0.7.12 — voz ao vivo, download e proxy /voz.

Não exigem GPU, chave de API nem rede: verificam contratos de código.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_versao_0712():
    import sys

    sys.path.insert(0, str(ROOT))
    from pesquisai import __version__ as v

    assert v.__version__ == "0.7.12"
    assert "voice_live" in v.__components__
    assert "voice_download_progress" in v.__components__
    assert any("/voz/api/chat" in e for e in v.__api_endpoints__)


def test_voice_presente_no_repositorio():
    for rel in (
        "voice/server.py",
        "voice/live.py",
        "voice/engine.py",
        "voice/bridge.py",
        "voice/static/local.html",
        "voice/static/live.html",
        "voice/adapter/adapter_config.json",
        "pesquisai/voice_autostart.py",
    ):
        assert (ROOT / rel).is_file(), rel


def test_download_usa_cli_hf_moderna():
    src = (ROOT / "voice/server.py").read_text(encoding="utf-8")
    assert "def _hf_download_cmd" in src
    assert '"hf", "huggingface-cli"' in src
    assert 'python3", "-m", "huggingface_hub' not in src
    assert "proc.returncode" in src
    assert "try_to_load_from_cache" in src


def test_barra_de_progresso_na_ui():
    html = (ROOT / "voice/static/local.html").read_text(encoding="utf-8")
    assert "progPct" in html
    assert "Tentar novamente" in html
    assert "scheduleCheck(1200)" in html


def test_proxy_voz_post_sem_dupla_leitura():
    src = (ROOT / "pesquisai/webui_server.py").read_text(encoding="utf-8")
    assert "def _voice_ws_tunnel" in src
    assert "def _voice_proxy" in src
    # o despacho /voz deve vir ANTES da leitura do corpo
    import re

    m = re.search(r'if path\.startswith\("/voz"\):.*?self\._voice_proxy\(path, "POST"\)',
                  src, re.S)
    assert m, "despacho /voz não encontrado"
    read_at = src.index("body = self._read_body()", m.end())
    assert m.start() < read_at


def test_deb_inclui_voice():
    src = (ROOT / "build-deb.sh").read_text(encoding="utf-8")
    assert "pesquisai voice agents i18n" in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
