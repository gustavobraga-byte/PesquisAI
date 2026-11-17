"""Testes da VPN da UFV (v0.7.11).

Cobrem o que é determinístico e offline:
  * parsing/validação do perfil .ovpn;
  * máscara de CPF e redaction de logs;
  * reescrita do perfil com IP fixo;
  * decisão da tela inicial (should_ask / mark_decision);
  * armazenamento cifrado das credenciais;
  * handshake SOCKS5 + relay (com um servidor HTTP local).

O teste de conexão real com a UFV depende das credenciais do usuário e não
roda aqui (ver docs/VPN_UFV.md).
"""
from __future__ import annotations

import http.server
import socket
import socketserver
import threading
import time

import pytest

from pesquisai import vpn


# ── fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Cada teste roda com estado e credenciais isolados."""
    monkeypatch.setenv("UFVAI_VPN_DIR", str(tmp_path / "vpn"))
    monkeypatch.setenv("HOME", str(tmp_path))
    with vpn._LOCK:
        vpn._STATE.update(
            {
                "state": "disconnected",
                "mode": "",
                "progress": "",
                "last_error": "",
                "connected_at": 0.0,
                "tun_ip": "",
                "routes": [],
                "dns": [],
                "proxy": "",
                "pids": {},
                "forwards": [],
                "full_tunnel": False,
                "system_mode": False,
            }
        )
    yield
    vpn._cleanup_processes()


PROFILE = """client
dev tun
proto udp
remote vpn.ufvnet.ufv.br 1195
auth-user-pass
comp-lzo yes
<ca>
-----BEGIN CERTIFICATE-----
AAA
-----END CERTIFICATE-----
</ca>
<cert>
-----BEGIN CERTIFICATE-----
BBB
-----END CERTIFICATE-----
</cert>
<key>
-----BEGIN PRIVATE KEY-----
CCC
-----END PRIVATE KEY-----
</key>
"""


# ── perfil ────────────────────────────────────────────────────

def test_parse_profile_ok():
    meta = vpn.parse_profile(PROFILE)
    assert meta["valid"] is True
    assert meta["remote_host"] == "vpn.ufvnet.ufv.br"
    assert meta["remote_port"] == 1195
    assert meta["proto"] == "udp"
    assert meta["dev"] == "tun"
    assert meta["has_ca"] and meta["has_cert"] and meta["has_key"]


def test_parse_profile_invalid():
    meta = vpn.parse_profile("client\ndev tun\n")
    assert meta["valid"] is False
    assert meta["remote_host"] == ""


def test_runtime_profile_pins_ip_and_drops_auth_line():
    runtime = vpn._build_runtime_profile(PROFILE, "200.235.168.86", 1195)
    assert "remote 200.235.168.86 1195" in runtime
    assert "remote vpn.ufvnet.ufv.br" not in runtime
    # a linha nua de auth-user-pass sai; o arquivo é passado por CLI
    assert "auth-user-pass\n" not in runtime
    assert "proto udp" in runtime


def test_save_profile_text_roundtrip(tmp_path):
    meta = vpn.save_profile_text(PROFILE)
    assert meta["valid"] is True
    assert vpn.profile_path().exists()
    assert oct(vpn.profile_path().stat().st_mode & 0o777) == "0o600"
    assert vpn.parse_profile(vpn._read(vpn.profile_path()))["valid"] is True


def test_save_profile_text_rejects_garbage():
    with pytest.raises(ValueError):
        vpn.save_profile_text("nada aqui")


# ── segurança / apresentação ─────────────────────────────────

def test_mask_cpf():
    assert vpn._mask_cpf("123.456.789-01") == "***.***.***-01"
    assert vpn._mask_cpf("123") == ""


def test_redact_hides_cpf_and_password():
    text = "user 12345678901 password=segredo123"
    out = vpn._redact(text)
    assert "12345678901" not in out
    assert "segredo123" not in out
    assert "***.***.***-**" in out


# ── decisão da tela inicial ──────────────────────────────────

def test_should_ask_by_default():
    assert vpn.should_ask(str(vpn.state_dir())) is True


def test_mark_decision_stops_asking():
    vpn.mark_decision("no")
    assert vpn.load_prefs()["last_choice"] == "no"
    assert vpn.should_ask(str(vpn.state_dir())) is False


def test_mark_decision_ufv():
    vpn.mark_decision("ufv")
    assert vpn.load_prefs()["last_choice"] == "ufv"
    assert vpn.should_ask(str(vpn.state_dir())) is False


# ── credenciais cifradas ─────────────────────────────────────

def test_save_load_forget_credentials(tmp_path):
    backup = str(tmp_path / "backups")
    assert vpn.save_credentials("12345678901", "senha", backup) is True
    assert vpn.load_saved_credentials(backup) == ("12345678901", "senha")
    assert vpn.has_saved_credentials(backup) is True
    assert vpn.forget_credentials(backup) is True
    assert vpn.load_saved_credentials(backup) == ("", "")


def test_credentials_never_in_status(tmp_path):
    backup = str(tmp_path / "backups")
    vpn.save_credentials("12345678901", "senha-secreta", backup)
    st = vpn.status(backup)
    blob = repr(st)
    assert "senha-secreta" not in blob
    assert "12345678901" not in blob
    assert st["has_saved_credentials"] is True


# ── SOCKS5 + relay ───────────────────────────────────────────

class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"ola-do-http-local"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_socks5_handshake_and_relay():
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    http_port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    socks_port = vpn._free_port(19080, 19120)
    threading.Thread(
        target=vpn.run_socks_server,
        args=("127.0.0.1", socks_port, []),
        daemon=True,
    ).start()
    time.sleep(0.6)

    client = socket.create_connection(("127.0.0.1", socks_port), timeout=5)
    try:
        client.sendall(b"\x05\x01\x00")
        assert client.recv(2) == b"\x05\x00"
        host = b"127.0.0.1"
        req = b"\x05\x01\x00\x03" + bytes([len(host)]) + host + http_port.to_bytes(2, "big")
        client.sendall(req)
        reply = client.recv(10)
        assert reply[:2] == b"\x05\x00"
        client.sendall(b"GET / HTTP/1.1\r\nHost: local\r\nConnection: close\r\n\r\n")
        data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk
        assert b"ola-do-http-local" in data
    finally:
        client.close()
        httpd.shutdown()
        httpd.server_close()


# ── estado / capacidades ─────────────────────────────────────

def test_capabilities_shape():
    caps = vpn.capabilities()
    for key in (
        "has_tun",
        "has_net_admin",
        "has_unshare",
        "has_slirp4netns",
        "has_openvpn",
        "mode",
        "can_install",
    ):
        assert key in caps
    assert caps["mode"] in ("direct", "netns", "unavailable")


def test_status_shape_without_connection(tmp_path):
    st = vpn.status(str(tmp_path / "backups"))
    assert st["ok"] is True
    assert st["state"] == "disconnected"
    assert "capabilities" in st
    assert "should_ask" in st
    assert st["proxy"] == ""
    assert isinstance(st["log_tail"], list)

# ── modo total / encaminhamento de portas ────────────────────

def test_runtime_profile_full_tunnel():
    runtime = vpn._build_runtime_profile(PROFILE, "1.2.3.4", 1195, full_tunnel=True)
    assert "redirect-gateway def1" in runtime
    split = vpn._build_runtime_profile(PROFILE, "1.2.3.4", 1195, full_tunnel=False)
    assert "redirect-gateway" not in split


def test_status_has_forward_and_system_fields(tmp_path):
    st = vpn.status(str(tmp_path / "backups"))
    assert st["forwards"] == []
    assert st["full_tunnel"] is False
    assert st["system_mode"] is False


def test_set_system_mode():
    vpn.set_system_mode(True)
    assert vpn.status()["system_mode"] is True
    vpn.set_system_mode(False)
    assert vpn.status()["system_mode"] is False


def test_publish_port_requires_connection():
    with pytest.raises(vpn.VPNError):
        vpn.publish_port(8000, 8000)


def test_add_forward_requires_connection():
    with pytest.raises(vpn.VPNError):
        vpn.add_forward("10.0.0.1", 11434)


def test_remove_unknown_forward():
    assert vpn.remove_forward("nao-existe") is False

def test_test_without_proxy_is_no_proxy():
    res = vpn.test(proxy="")
    assert res["ok"] is False
    assert res["verdict"] == "no_proxy"
    assert res["proxy_ip"] == ""
    assert res["direct_ip"] == ""


def test_parse_pushed_reads_dns_from_any_line():
    log = (
        "PUSH: Received control message: 'PUSH_REPLY,route 100.65.0.0 255.255.128.0,"
        "dhcp-option DNS 200.235.168.10,route 200.235.168.0 255.255.255.0'\n"
        "dhcp-option DNS 10.255.0.1\n"
    )
    routes, dns = vpn._parse_pushed(log)
    assert "200.235.168.10" in dns
    assert "10.255.0.1" in dns
    assert any("100.65.0.0" in route for route in routes)


def test_discover_dns_prefers_the_server_that_resolves_internal(monkeypatch):
    def fake_probe(ns_pid, server, host, timeout=4.0):
        if server == "10.255.0.1" and host == "sistemas.ufv.br":
            return ["200.235.168.50"]
        if host == "www.ufv.br":
            return ["200.235.168.227"]
        return []

    monkeypatch.setattr(vpn, "_dns_probe", fake_probe)
    res = vpn._discover_dns(123, ["200.235.168.10"])
    assert res["internal"] == ["10.255.0.1"]
    assert res["servers"][0] == "10.255.0.1"
    assert "200.235.168.10" in res["detail"]


def test_tun_counters_read_sysfs_inside_namespace(monkeypatch):
    class _Proc:
        def __init__(self, out):
            self.stdout = out

    def fake_ns(args, ns_pid, timeout=10):
        return _Proc("1234\n" if "tx_bytes" in args[-1] else "5678\n")

    monkeypatch.setattr(vpn, "_ns", fake_ns)
    assert vpn._tun_counters(1) == {"tx": 1234, "rx": 5678}


def test_verdict_is_vpn_when_tun_counters_grow(monkeypatch):
    with vpn._LOCK:
        vpn._STATE.update(
            {
                "state": "connected",
                "mode": "netns",
                "pids": {"ns": 99999},
                "proxy": "socks5h://127.0.0.1:1081",
                "full_tunnel": True,
                "tun_ip": "10.255.0.228",
                "routes": [],
                "dns": ["10.0.2.3"],
            }
        )
    monkeypatch.setattr(vpn, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(vpn, "_ip_via", lambda *a, **k: ("34.1.1.1", "ipify"))
    monkeypatch.setattr(vpn, "_ip_via_ns", lambda *a, **k: ("", ""))

    def fake_curl(ns_pid, url, timeout=15, want_body=False):
        return {
            "ok": url.startswith("https://www.ufv.br"),
            "url": url,
            "http": "200" if url.startswith("https://www.ufv.br") else "000",
            "body": "",
            "error": "",
        }

    monkeypatch.setattr(vpn, "_curl_in_ns", fake_curl)
    counters = iter([{"tx": 100, "rx": 100}, {"tx": 5000, "rx": 6000}])
    monkeypatch.setattr(vpn, "_tun_counters", lambda pid: next(counters))
    monkeypatch.setattr(
        vpn, "_ns_diag", lambda pid, host: {"host": host, "ip": "", "route": ""}
    )
    monkeypatch.setattr(
        vpn, "_ns",
        lambda *a, **k: type("_P", (), {"stdout": "1.1.1.1 via 10.255.0.1 dev tun0\n"})(),
    )
    res = vpn.test()
    assert res["verdict"] == "vpn"
    assert res["tunnel_active"] is True
    assert res["tun_tx"] == 4900
    assert res["tun_rx"] == 5900
    assert "dev tun0" in res["route_default"]


# ── v0.7.11: OpenCode SEMPRE pela VPN (padrão) ───────────────

def test_connect_defaults_to_split_tunnel():
    """O padrão do conector é split tunnel (serviço no netns; LLM continua no Colab).

    full_tunnel=True manda TODO o tráfego para a UFV, que bloqueia a saída
    externa (medido em 07/11/2026: OpenRouter/GitHub/GitHub timeout).
    """
    import inspect

    assert inspect.signature(vpn.connect).parameters["full_tunnel"].default is False


def test_system_enable_accepts_split_tunnel(monkeypatch):
    """O modo total aceita split tunnel (não exige mais redirect-gateway)."""
    from pesquisai import launch_app as la
    from pesquisai import vpn as _vpn

    monkeypatch.setattr(
        _vpn,
        "status",
        lambda *a, **k: {
            "state": "connected",
            "system_mode": False,
            "full_tunnel": False,
            "pids": {"ns": 4242},
        },
    )
    monkeypatch.setattr(la, "_stop_terminal", lambda: None)
    monkeypatch.setattr(la, "_port_accepts", lambda *a, **k: False)
    monkeypatch.setattr(_vpn, "unpublish_port", lambda *a, **k: None)
    monkeypatch.setattr(_vpn, "publish_port", lambda *a, **k: None)
    monkeypatch.setattr(la, "_system_enable_steps", lambda *a, **k: None)
    out = la._vpn_system_enable("")
    assert out["state"] == "connected"
    assert out["full_tunnel"] is False


def test_service_endpoint_reads_xdg_state(tmp_path, monkeypatch):
    """A porta do serviço é lida do service.json para ser republicada."""
    from pesquisai import launch_app

    state = tmp_path / "opencode"
    state.mkdir()
    (state / "service.json").write_text(
        '{"url": "http://127.0.0.1:49374", "pid": 123}', encoding="utf-8"
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert launch_app._opencode_service_endpoint() == ("127.0.0.1", 49374)


def test_ensure_service_in_netns_binds_and_strips_proxies(monkeypatch):
    """No namespace o serviço escuta 0.0.0.0:<porta> e não herda proxy."""
    import subprocess as _sp
    from unittest.mock import MagicMock

    from pesquisai import run_fast

    captured: dict = {}

    class FakePopen:
        def __init__(self, cmd, **kw):
            captured["cmd"] = list(cmd)
            captured["env"] = dict(kw.get("env") or {})
            self.pid = 4242

    monkeypatch.setenv("HTTPS_PROXY", "socks5h://127.0.0.1:1081")
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1081")
    monkeypatch.setattr(run_fast, "_service_cwd", lambda: None)
    monkeypatch.setattr(
        "pesquisai.opencode_utils.keys_env_from_store", lambda *_: {}
    )
    monkeypatch.setattr(
        "pesquisai.opencode_utils.service_missing_key_envs", lambda *_: []
    )
    monkeypatch.setattr("pesquisai.opencode_utils.find_opencode", lambda: "/bin/true")
    monkeypatch.setattr(
        "pesquisai.opencode_utils.build_env", lambda extra=None: {"PATH": "/usr/bin"}
    )
    monkeypatch.setattr(
        _sp, "run",
        lambda *a, **k: _sp.CompletedProcess(args=a[0] if a else [], returncode=0,
                                            stdout="", stderr=""),
    )
    monkeypatch.setattr(_sp, "Popen", FakePopen)

    ok = run_fast.ensure_service_project_dir(
        "/tmp", timeout_s=0.05, netns_pid=777,
        service_host="0.0.0.0", service_port=4567,
    )

    assert ok is False  # /bin/true não responde "service status"
    cmd = captured["cmd"]
    assert cmd[:5] == ["nsenter", "-t", "777", "-m", "-n"]
    assert cmd[cmd.index("--hostname") + 1] == "0.0.0.0"
    assert cmd[cmd.index("--port") + 1] == "4567"
    assert "--service" in cmd
    assert "ALL_PROXY" not in captured["env"]
    assert "HTTPS_PROXY" not in captured["env"]


def test_system_enable_publishes_opencode_service_port(monkeypatch):
    """O modo total publica a porta do serviço no host (senão o CLI não o vê)."""
    from pesquisai import launch_app as la
    from pesquisai import run_fast, vpn

    calls: dict = {}

    monkeypatch.setattr(la, "find_opencode", lambda: "/bin/true")
    monkeypatch.setattr(la, "_workspace_dir", lambda: "/tmp")
    monkeypatch.setattr(la, "_opencode_service_endpoint", lambda: ("127.0.0.1", 4567))
    monkeypatch.setattr(la, "_wait_service_on_host", lambda *a, **k: True)
    monkeypatch.setattr(la.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        la, "start_ttyd", lambda **kw: calls.setdefault("ttyd", kw)
    )

    def fake_ensure(*args, **kwargs):
        calls["ensure"] = kwargs
        return True

    monkeypatch.setattr(run_fast, "ensure_service_project_dir", fake_ensure)
    monkeypatch.setattr(vpn, "publish_port", lambda *a, **k: calls.setdefault("publish", a))
    monkeypatch.setattr(vpn, "unpublish_port", lambda *a, **k: None)
    monkeypatch.setattr(vpn, "set_system_mode", lambda *a, **k: None)

    la._SYSTEM_MODE_NETNS_PID = None
    la._SYSTEM_MODE_SERVICE_PORT = None
    la._system_enable_steps("", 999)

    assert calls["ensure"]["service_host"] == "0.0.0.0"
    assert calls["ensure"]["service_port"] == 4567
    assert calls["publish"] == (4567, 4567)
    assert calls["ttyd"]["netns_pid"] == 999
    assert la._SYSTEM_MODE_NETNS_PID == 999
    assert la._SYSTEM_MODE_SERVICE_PORT == 4567

    # restaura os globais para não vazar entre testes
    la._SYSTEM_MODE_NETNS_PID = None
    la._SYSTEM_MODE_SERVICE_PORT = None
