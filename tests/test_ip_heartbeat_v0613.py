"""Testes v0.6.13 — IP real do cliente + heartbeat "usuario_ativo" na revisita.

Cobre:
  - _normalize_ip_token / _is_private_ip (IPv4/IPv6, portas, colchetes)
  - _get_client_ip: cadeia X-Forwarded-For da direita p/ esquerda pulando
    IPs privados; headers X-Real-IP/CF-Connecting-IP/Forwarded; fallback
  - telemetry._read_profile: fallback no backup persistente quando o
    ~/.config efêmero perdeu o e-mail (revisita em sessão nova do Colab)
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import launch_app
from pesquisai import telemetry


class _FakeHeaders:
    def __init__(self, data):
        self._d = {k.lower(): v for k, v in (data or {}).items()}

    def get(self, name, default=None):
        return self._d.get(name.lower(), default or "")


class _FakeHandler:
    def __init__(self, headers=None, addr=("127.0.0.1", 8001)):
        self.headers = _FakeHeaders(headers or {})
        self.client_address = addr


# ═══════════════════════════════════════════════════════════════
# IP REAL (Bug 1)
# ═══════════════════════════════════════════════════════════════

class TestIsPrivateIP:
    def test_privados_loopback(self):
        assert launch_app._is_private_ip("127.0.0.1")
        assert launch_app._is_private_ip("10.1.2.3")
        assert launch_app._is_private_ip("172.16.0.1")
        assert launch_app._is_private_ip("172.31.255.255")
        assert launch_app._is_private_ip("192.168.1.1")
        assert launch_app._is_private_ip("169.254.10.10")
        assert launch_app._is_private_ip("100.64.0.1")     # CGNAT
        assert launch_app._is_private_ip("::1")
        assert launch_app._is_private_ip("fe80::1")
        assert launch_app._is_private_ip("fc00::1")

    def test_publicos(self):
        assert not launch_app._is_private_ip("8.8.8.8")
        assert not launch_app._is_private_ip("189.90.5.6")
        assert not launch_app._is_private_ip("2804:431::1")

    def test_vazio(self):
        assert launch_app._is_private_ip("") is True
        assert launch_app._is_private_ip(None) is True


class TestNormalizeIPToken:
    def test_ipv4(self):
        assert launch_app._normalize_ip_token("  1.2.3.4  ") == "1.2.3.4"

    def test_ipv4_com_porta(self):
        assert launch_app._normalize_ip_token("189.90.5.6:8080") == "189.90.5.6"

    def test_ipv6_colchetes(self):
        assert launch_app._normalize_ip_token("[2804:431::1]:4567") == "2804:431::1"
        assert launch_app._normalize_ip_token("[2804:431::1]") == "2804:431::1"

    def test_ipv6_puro(self):
        assert launch_app._normalize_ip_token("2804:431::1") == "2804:431::1"

    def test_nulo(self):
        assert launch_app._normalize_ip_token("") == ""


class TestGetClientIP:
    def test_colab_xff_cadeia_privada_publica(self):
        h = _FakeHandler({"X-Forwarded-For": "200.155.10.9, 10.0.0.1, 127.0.0.1"})
        assert launch_app._get_client_ip(h) == "200.155.10.9"

    def test_xff_publico_no_fim(self):
        h = _FakeHandler({"X-Forwarded-For": "127.0.0.1, 172.16.1.1, 189.90.5.6"})
        assert launch_app._get_client_ip(h) == "189.90.5.6"

    def test_xff_so_privados_retorna_primeiro(self):
        h = _FakeHandler({"X-Forwarded-For": "10.0.0.5, 127.0.0.1"})
        assert launch_app._get_client_ip(h) == "10.0.0.5"

    def test_xff_ipv4_porta(self):
        h = _FakeHandler({"X-Forwarded-For": "189.90.5.6:8080, 172.16.0.1"})
        assert launch_app._get_client_ip(h) == "189.90.5.6"

    def test_xff_ipv6_colchetes(self):
        h = _FakeHandler({"X-Forwarded-For": "[2804:431::1]:4567, 10.0.0.1"})
        assert launch_app._get_client_ip(h) == "2804:431::1"

    def test_x_real_ip(self):
        h = _FakeHandler({"X-Real-IP": "200.155.7.7"})
        assert launch_app._get_client_ip(h) == "200.155.7.7"

    def test_cf_connecting_ip(self):
        h = _FakeHandler({"CF-Connecting-IP": "8.8.8.8"})
        assert launch_app._get_client_ip(h) == "8.8.8.8"

    def test_forwarded_rfc7239(self):
        h = _FakeHandler({"Forwarded": "for=201.42.33.1;proto=https"})
        assert launch_app._get_client_ip(h) == "201.42.33.1"

    def test_sem_headers_fallback_client_address(self):
        h = _FakeHandler({}, ("127.0.0.1", 8001))
        assert launch_app._get_client_ip(h) == "127.0.0.1"

    def test_sem_nada(self):
        h = _FakeHandler({}, None)
        assert launch_app._get_client_ip(h) == ""

    def test_espacos_e_virgulas(self):
        h = _FakeHandler({"X-Forwarded-For": "  200.155.3.3  ,  10.0.0.1  "})
        assert launch_app._get_client_ip(h) == "200.155.3.3"


# ═══════════════════════════════════════════════════════════════
# HEARTBEAT REVISITA (Bug 2)
# ═══════════════════════════════════════════════════════════════

class TestReadProfileFallback:
    def test_persisted_profile_path_colab(self, monkeypatch, tmp_path):
        """Colab → backup em /content/drive/My Drive/PesquisAI/backups/."""
        def _fake_isdir(p):
            return p == "/content/drive/My Drive"
        monkeypatch.setattr(launch_app.os.path, "isdir", _fake_isdir)
        monkeypatch.setattr(telemetry.os.path, "isdir", _fake_isdir)
        path = telemetry._persisted_profile_path()
        assert path and path.endswith(
            "My Drive/PesquisAI/backups/ufvai_consentimento.json")

    def test_sem_perfil_local_cai_no_backup(self, monkeypatch, tmp_path):
        """Revisita em VM nova: ~/.config efêmero sem e-mail → backup."""
        monkeypatch.setattr(
            telemetry, "_PROFILE_FILE",
            os.path.join(str(tmp_path), "no_such_profile.json"))
        backup_dir = os.path.join(str(tmp_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(backup_dir, "ufvai_consentimento.json")
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump({"email": "revisita@teste.ufv.br",
                       "email_sha256": "abc123",
                       "name": "Revisita"}, f)
        monkeypatch.setattr(telemetry, "_persisted_profile_path",
                            lambda: backup_file)
        prof = telemetry._read_profile()
        assert prof.get("email") == "revisita@teste.ufv.br"
        assert prof.get("email_sha256") == "abc123"
        assert prof.get("name") == "Revisita"

    def test_perfil_local_tem_precedencia(self, monkeypatch, tmp_path):
        """Com e-mail no ~/.config, NÃO sobrescreve com o backup."""
        local_file = os.path.join(str(tmp_path), "local.json")
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump({"email": "local@ufv.br"}, f)
        monkeypatch.setattr(telemetry, "_PROFILE_FILE", local_file)
        # backup EXISTE com outro e-mail — local deve vencer
        backup_file = os.path.join(str(tmp_path), "backups", "ufvai_consentimento.json")
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump({"email": "backup@ufv.br", "email_sha256": "zzz",
                       "name": "Backup"}, f)
        monkeypatch.setattr(telemetry, "_persisted_profile_path",
                            lambda: backup_file)
        prof = telemetry._read_profile()
        assert prof.get("email") == "local@ufv.br"      # e-mail local vence
        # fallback do backup NAO rodou (email local presente) → nome não vem
        # do backup ("Backup") e sha do backup não vaza para o perfil local
        assert prof.get("name") != "Backup"
        assert prof.get("email_sha256", "") == ""