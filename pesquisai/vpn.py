"""vpn.py — VPN da UFV dentro do Colab (OpenVPN em namespace isolado).

Por que este módulo existe
==========================
O runtime do Google Colab é um contêiner **sem** ``/dev/net/tun`` e **sem**
``CAP_NET_ADMIN`` no namespace de rede principal. Isso impede o caminho
"clássico" do OpenVPN (``--dev tun``) e também o WireGuard de kernel.

A solução implementada aqui é a mesma usada por projetos de "VPN sandbox":

1. cria-se um **user + network namespace** com ``unshare -Urn`` (dentro dele
   somos root e temos ``CAP_NET_ADMIN``);
2. o ``slirp4netns`` liga esse namespace à internet por NAT em espaço de
   usuário (``tap0`` = 10.0.2.100, gateway 10.0.2.2);
3. o **OpenVPN** roda dentro do namespace, cria ``tun0`` e recebe as rotas
   empurradas pelo servidor da UFV (split tunnel — só a rede da UFV);
4. um **proxy SOCKS5** roda dentro do namespace e é exposto ao Colab por
   ``slirp4netns add_hostfwd`` em ``127.0.0.1:1081``.

Assim, qualquer processo do Colab pode acessar a rede da UFV com
``curl --socks5-hostname 127.0.0.1:1081 ...`` (ou ``ALL_PROXY``), sem
precisar de privilégio no namespace principal e sem derrubar o Colab.

O que este módulo **não** faz
=============================
* Não torna o túnel transparente para todo o contêiner: sem
  ``CAP_NET_ADMIN`` no namespace raiz isso é impossível. O tráfego só passa
  pela VPN quando o processo usa o proxy (ou quando o SO tem TUN/NET_ADMIN e
  o modo direto é usado).
* Não contorna a regra da UFV de **1 dispositivo por CPF**. Conectar o Colab
  conta como um dispositivo e pode desconectar o computador do usuário.
* Não valida a senha online antes de conectar (a validação é a própria VPN).

Segurança
=========
* A senha nunca é escrita em log, estado ou linha de comando: vai por um
  arquivo temporário ``0600`` que é apagado ao desconectar.
* Se o usuário marcar "lembrar", CPF e senha são gravados **cifrados** no
  mesmo ``keys_store.json`` do UFVAI (Fernet), com prefixo reservado
  ``vpn_ufv_`` — e nunca aparecem em ``/api/apikey``.
* O perfil ``.ovpn`` é público (baixado de vpn.ufvnet.ufv.br), mas é gravado
  com permissão ``0600``.

Autor: UFVAI · v0.7.11
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import random
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger("pesquisai.vpn")

# ── Constantes públicas ────────────────────────────────────────
VPN_NAME = "UFV"
PROFILE_URL = "https://vpn.ufvnet.ufv.br/configs/UFV-linux.ovpn"
PROFILE_HOST = "vpn.ufvnet.ufv.br"
PROFILE_PORT = 1195
PROFILE_PROTO = "udp"
DEFAULT_REMOTE_HOST = "vpn.ufvnet.ufv.br"
DEFAULT_REMOTE_PORT = 1195

GUEST_IP = "10.0.2.100"          # IP do namespace no slirp4netns
GUEST_GW = "10.0.2.2"
SOCKS_GUEST_PORT = 1080
SOCKS_HOST_PORT = 1081
TEST_INTERNAL_URL = "https://sistemas.ufv.br/"
TEST_PUBLIC_URL = "https://www.ufv.br/"

CRED_CPF = "vpn_ufv_cpf"
CRED_PASSWORD = "vpn_ufv_password"
RESERVED_PREFIX = "vpn_ufv_"

NET_ADMIN_BIT = 1 << 12

_LOCK = threading.RLock()
_CONNECT_THREAD: Optional[threading.Thread] = None
_CANCEL = threading.Event()

_STATE: dict = {
    "state": "disconnected",      # disconnected | connecting | connected | error
    "mode": "",                   # netns | direct
    "progress": "",
    "last_error": "",
    "connected_at": 0.0,
    "tun_ip": "",
    "routes": [],
    "dns": [],
    "proxy": "",
    "host_port": 0,
    "guest_port": 0,
    "pids": {},
    "profile": {},
    "cpf_masked": "",
    "log_tail": [],
}


# ═══════════════════════════════════════════════════════════════
# Caminhos e utilidades
# ═══════════════════════════════════════════════════════════════

def state_dir() -> Path:
    """Diretório de estado (efêmero, fora do Drive).

    O perfil e os logs não precisam sobreviver ao boot; as credenciais, se
    lembradas, ficam no ``keys_store.json`` cifrado do Drive.
    """
    custom = os.environ.get("UFVAI_VPN_DIR", "").strip()
    base = Path(custom) if custom else Path.home() / ".config" / "ufvai" / "vpn"
    base.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    return base


def default_backup_dir() -> str:
    """Pasta de backups do UFVAI (onde vive o ``keys_store.json``)."""
    drive = Path("/content/drive/My Drive/PesquisAI")
    if drive.is_dir():
        return str(drive / "backups")
    return str(Path.home() / "PesquisAI" / "backups")


def profile_path() -> Path:
    return state_dir() / "UFV-linux.ovpn"


def runtime_profile_path() -> Path:
    return state_dir() / "runtime.ovpn"


def log_path() -> Path:
    return state_dir() / "vpn.log"


def openvpn_log_path() -> Path:
    return state_dir() / "openvpn.log"


def state_path() -> Path:
    return state_dir() / "state.json"


def prefs_path() -> Path:
    return state_dir() / "prefs.json"


def persistent_prefs_path() -> Path | None:
    """Espelho persistente das preferências da VPN (Drive ou ``~/PesquisAI``).

    ``state_dir()`` vive em ``~/.config`` — no Colab isso é **efêmero**: cada
    runtime novo (ou "Reiniciar sessão") perde a decisão e a pergunta "você é
    aluno(a) da UFV?" voltava a aparecer. O espelho no Drive resolve isso:
    a resposta é dada **uma vez** por Drive, não por sessão.
    """
    custom = os.environ.get("UFVAI_VPN_PREFS_FILE", "").strip()
    if custom:
        # testes e instalações com Drive em outro lugar
        target = Path(custom)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    try:
        drive_root = Path("/content/drive") / "My Drive"
        base = (
            drive_root / "PesquisAI"
            if drive_root.is_dir()
            else Path.home() / "PesquisAI"
        )
        if not base.is_dir():
            return None
        bdir = base / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        return bdir / "ufvai_vpn_prefs.json"
    except OSError:
        return None


# O espelho vive no Drive: ler a cada chamada de ``status()`` (a UI consulta a
# cada 1,5 s durante a conexão) custaria centenas de ms. Cache curto resolve.
_PREFS_CACHE: dict = {"path": None, "at": 0.0, "value": {}}
_PREFS_TTL = 2.0


def _read_json_file(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _read_prefs_mirror(path: Path | None) -> dict:
    if path is None:
        return {}
    now = time.time()
    if (
        _PREFS_CACHE.get("path") == str(path)
        and now - float(_PREFS_CACHE.get("at") or 0) < _PREFS_TTL
    ):
        return dict(_PREFS_CACHE.get("value") or {})
    value = _read_json_file(path)
    _PREFS_CACHE.update({"path": str(path), "at": now, "value": value})
    return dict(value)


def load_prefs() -> dict:
    """Preferências locais + espelho do Drive (a decisão vale para os dois).

    ``ask_dismissed`` e ``auto_connect`` são OU lógicos: se qualquer um dos
    arquivos já registrou a decisão, ela não é desfeita por um ``/tmp`` novo.
    ``last_choice``/``answered_at`` seguem a cópia local (mais recente).
    """
    local = _read_json_file(prefs_path())
    remote = _read_prefs_mirror(persistent_prefs_path())
    if not local:
        return dict(remote)
    if not remote:
        return dict(local)
    merged = dict(remote)
    merged.update(
        {k: v for k, v in local.items() if k not in ("ask_dismissed", "auto_connect")}
    )
    merged["ask_dismissed"] = bool(local.get("ask_dismissed") or remote.get("ask_dismissed"))
    merged["auto_connect"] = bool(local.get("auto_connect") or remote.get("auto_connect"))
    return merged


def save_prefs(data: dict) -> None:
    """Grava as preferências no local e no espelho do Drive.

    Mescla com o que já existe (``{**anterior, **data}``) para que uma escrita
    parcial — de uma versão antiga ou de outro caminho — não "esqueça" a
    decisão já registrada e faça a pergunta voltar.
    """
    payload = dict(_read_json_file(prefs_path()))
    payload.update(data)
    try:
        _write_json(prefs_path(), payload)
        os.chmod(prefs_path(), 0o600)
    except OSError:
        pass
    mirror = persistent_prefs_path()
    if mirror is not None:
        try:
            merged = dict(_read_json_file(mirror))
            merged.update(payload)
            _write_json(mirror, merged)
            os.chmod(mirror, 0o600)
            _PREFS_CACHE.update({"path": str(mirror), "at": time.time(), "value": merged})
        except OSError:
            pass


def mark_decision(choice: str) -> dict:
    """Registra a resposta da tela inicial ("ufv" ou "no").

    ``ask_dismissed`` evita repetir a pergunta — e agora é gravado também no
    Drive (``backups/ufvai_vpn_prefs.json``), então **novos acessos não
    perguntam de novo**. ``auto_connect`` guarda a intenção de reconectar
    sozinho quando houver credenciais salvas. O botão 🛡 da topbar continua
    disponível para abrir o painel a qualquer momento.
    """
    choice = "ufv" if str(choice).lower() in ("ufv", "yes", "sim", "aluno") else "no"
    prefs = load_prefs()
    prefs.update(
        {
            "ask_dismissed": True,
            "last_choice": choice,
            "auto_connect": choice == "ufv",
            "answered_at": _iso(_now()),
        }
    )
    save_prefs(prefs)
    return prefs


def set_auto_connect(enabled: bool) -> dict:
    """Liga/desliga a reconexão automática no próximo boot (persistente)."""
    prefs = load_prefs()
    prefs["auto_connect"] = bool(enabled)
    prefs["auto_connect_at"] = _iso(_now())
    save_prefs(prefs)
    return prefs


def should_auto_connect(backup_dir: str | None = None) -> bool:
    """Só reconecta sozinho quem já conectou **e** salvou as credenciais."""
    if not load_prefs().get("auto_connect"):
        return False
    if not has_saved_credentials(backup_dir):
        return False
    with _LOCK:
        return _STATE.get("state") not in ("connected", "connecting")


def should_ask(backup_dir: str | None = None) -> bool:
    """A pergunta inicial só aparece para quem ainda não decidiu (uma vez)."""
    if has_saved_credentials(backup_dir):
        return False
    if load_prefs().get("ask_dismissed"):
        return False
    with _LOCK:
        if _STATE.get("state") in ("connected", "connecting"):
            return False
    return True


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    if not ts:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _read(path: Path, limit: int = 200_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def _tail(path: Path, lines: int = 40) -> list[str]:
    text = _read(path, 400_000)
    if not text:
        return []
    return text.splitlines()[-lines:]


def _redact(text: str) -> str:
    """Remove CPF e possíveis segredos de qualquer texto de log."""
    text = re.sub(r"\b\d{11}\b", "***.***.***-**", text)
    text = re.sub(r"(?i)(password|senha|passwd)\s*[:=]\s*\S+", r"\1=<oculto>", text)
    return text


def _mask_cpf(cpf: str) -> str:
    digits = re.sub(r"\D", "", cpf or "")
    if len(digits) != 11:
        return ""
    return f"***.***.***-{digits[-2:]}"


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _pid_alive(pid: int) -> bool:
    if not pid or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid(pid: int) -> None:
    if not _pid_alive(pid):
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(pid), sig)
            return
        except OSError:
            try:
                os.kill(pid, sig)
                return
            except OSError:
                return


_EXTRA_BIN_DIRS = (
    "/usr/sbin",
    "/sbin",
    "/usr/bin",
    "/usr/local/sbin",
    "/usr/local/bin",
    "/bin",
)


def _which(name: str) -> str:
    """``shutil.which`` + caminhos usuais de root (o PATH do wrapper pode
    não incluir ``/usr/sbin``, onde ficam ``openvpn`` e ``slirp4netns``)."""
    found = shutil.which(name)
    if found:
        return found
    for directory in _EXTRA_BIN_DIRS:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _cap_eff() -> int:
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("CapEff:"):
                    return int(line.split()[1], 16)
    except (OSError, ValueError):
        pass
    return 0


def capabilities() -> dict:
    """Diagnóstico do que o ambiente permite."""
    is_colab = os.path.isdir("/content/drive") or os.path.isdir("/content")
    has_tun = os.path.exists("/dev/net/tun")
    has_net_admin = bool(_cap_eff() & NET_ADMIN_BIT)
    has_unshare = bool(_which("unshare"))
    has_nsenter = bool(_which("nsenter"))
    has_slirp = bool(_which("slirp4netns"))
    has_openvpn = bool(_which("openvpn"))
    euid = os.geteuid()

    if has_openvpn and has_tun and has_net_admin:
        mode = "direct"
    elif has_openvpn and has_unshare and has_slirp and has_nsenter:
        mode = "netns"
    elif not has_openvpn or (not has_slirp and not (has_tun and has_net_admin)):
        mode = "unavailable"
    else:
        mode = "unavailable"

    return {
        "is_colab": is_colab,
        "euid": euid,
        "has_tun": has_tun,
        "has_net_admin": has_net_admin,
        "has_unshare": has_unshare,
        "has_nsenter": has_nsenter,
        "has_slirp4netns": has_slirp,
        "has_openvpn": has_openvpn,
        "openvpn": _which("openvpn"),
        "slirp4netns": _which("slirp4netns"),
        "mode": mode,
        "can_install": bool(_which("apt-get")) and euid == 0,
    }


def ensure_tun() -> tuple[bool, str]:
    """Garante ``/dev/net/tun`` quando somos root (Colab não traz o device)."""
    if os.path.exists("/dev/net/tun"):
        return True, "ok"
    if os.geteuid() != 0:
        return False, (
            "/dev/net/tun não existe e não somos root. Rode o UFVAI como root "
            "ou habilite o dispositivo TUN no sistema."
        )
    try:
        os.makedirs("/dev/net", exist_ok=True)
        os.system("mknod /dev/net/tun c 10 200 2>/dev/null")
        os.chmod("/dev/net/tun", 0o600)
        if os.path.exists("/dev/net/tun"):
            return True, "criado"
        return False, "não foi possível criar /dev/net/tun (mknod falhou)."
    except Exception as exc:  # noqa: BLE001
        return False, f"falha ao criar /dev/net/tun: {exc}"


def ensure_dependencies() -> tuple[bool, str]:
    """Instala openvpn/slirp4netns quando faltam (somente root + apt)."""
    caps = capabilities()
    need = []
    if not caps["has_openvpn"]:
        need.append("openvpn")
    if caps["mode"] != "direct" and not caps["has_slirp4netns"]:
        need.append("slirp4netns")
    if not caps["has_unshare"] or not caps["has_nsenter"]:
        need.append("util-linux")
    if not need:
        return True, "dependências presentes"

    if not caps["can_install"]:
        return False, (
            "Faltam pacotes (%s) e não é possível instalar automaticamente. "
            "Instale com: sudo apt-get install -y %s"
            % (", ".join(need), " ".join(need))
        )

    cmd = "apt-get update -qq && apt-get install -y -qq " + " ".join(need)
    try:
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        msg = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[-6:]
        return ok, " | ".join(msg) if msg else ("ok" if ok else "apt falhou")
    except Exception as exc:  # noqa: BLE001
        return False, f"falha ao instalar dependências: {exc}"


# ═══════════════════════════════════════════════════════════════
# Perfil .ovpn
# ═══════════════════════════════════════════════════════════════

def parse_profile(text: str) -> dict:
    """Extrai metadados e valida o perfil OpenVPN da UFV."""
    text = text or ""
    remote = re.search(r"^\s*remote\s+(\S+)\s+(\d+)", text, re.MULTILINE)
    proto = re.search(r"^\s*proto\s+(\S+)", text, re.MULTILINE)
    dev = re.search(r"^\s*dev\s+(\S+)", text, re.MULTILINE)
    meta = {
        "valid": False,
        "remote_host": remote.group(1) if remote else "",
        "remote_port": int(remote.group(2)) if remote else 0,
        "proto": proto.group(1).lower() if proto else "",
        "dev": dev.group(1) if dev else "",
        "has_ca": "<ca>" in text.lower(),
        "has_cert": "<cert>" in text.lower(),
        "has_key": "<key>" in text.lower(),
        "has_auth_user_pass": "auth-user-pass" in text.lower(),
        "bytes": len(text.encode("utf-8")),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    meta["valid"] = bool(
        meta["remote_host"]
        and meta["has_ca"]
        and meta["has_cert"]
        and meta["dev"]
    )
    return meta


def fetch_profile(force: bool = False, timeout: int = 25) -> dict:
    """Baixa o perfil oficial da UFV e grava em ``state_dir`` (0600)."""
    path = profile_path()
    if path.exists() and not force:
        meta = parse_profile(_read(path))
        if meta["valid"]:
            meta["source"] = "cache"
            meta["path"] = str(path)
            return meta

    req = urllib.request.Request(
        PROFILE_URL,
        headers={"User-Agent": "UFVAI/0.7.11 (+https://github.com/gustavobraga-byte/PesquisAI)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(300_000)
    text = raw.decode("utf-8", errors="replace")
    meta = parse_profile(text)
    if not meta["valid"]:
        raise ValueError(
            "O arquivo baixado não parece um perfil OpenVPN válido "
            "(faltam remote/<ca>/<cert>/dev)."
        )
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    meta["source"] = "download"
    meta["path"] = str(path)
    return meta


def save_profile_text(text: str) -> dict:
    """Salva um perfil colado/enviado pelo usuário (modo offline)."""
    meta = parse_profile(text)
    if not meta["valid"]:
        raise ValueError(
            "Perfil inválido: são obrigatórios 'remote host porta', 'dev tun', "
            "'<ca>' e '<cert>'."
        )
    path = profile_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    meta["source"] = "upload"
    meta["path"] = str(path)
    return meta


def _build_runtime_profile(
    profile_text: str, remote_ip: str, remote_port: int, full_tunnel: bool = False
) -> str:
    """Cria uma cópia com ``remote`` fixado no IP resolvido.

    Dentro do namespace o DNS do slirp não resolve ``vpn.ufvnet.ufv.br``;
    resolver no host e fixar o IP evita a dependência de DNS no túnel.
    """
    lines = []
    for line in profile_text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("remote "):
            continue
        if stripped.startswith("auth-user-pass"):
            continue
        lines.append(line)
    lines.append("")
    lines.append(f"remote {remote_ip} {remote_port}")
    lines.append(f"proto {PROFILE_PROTO}")
    if full_tunnel:
        # Túnel total: duas rotas /1 vencem a default do slirp; todo o
        # tráfego do namespace (OpenCode, terminal, ferramentas) vai pela UFV.
        lines.append("redirect-gateway def1")
    return "\n".join(lines) + "\n"


def _resolve_remote(host: str, port: int) -> str:
    """Resolve o servidor no namespace do host (IPv4)."""
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)
    if not infos:
        raise OSError(f"não foi possível resolver {host}")
    return infos[0][4][0]


# ═══════════════════════════════════════════════════════════════
# Credenciais (cifradas no keys_store do UFVAI)
# ═══════════════════════════════════════════════════════════════

def _keys_module():
    try:
        from . import security as _sec  # type: ignore
        return _sec
    except Exception:  # noqa: BLE001
        try:
            import security as _sec  # type: ignore
            return _sec
        except Exception:  # noqa: BLE001
            return None


def load_saved_credentials(backup_dir: str | None = None) -> tuple[str, str]:
    sec = _keys_module()
    if sec is None:
        return "", ""
    try:
        store = sec.load_encrypted_keys(backup_dir or default_backup_dir())
    except Exception:  # noqa: BLE001
        return "", ""
    return str(store.get(CRED_CPF, "") or ""), str(store.get(CRED_PASSWORD, "") or "")


def save_credentials(cpf: str, password: str, backup_dir: str | None = None) -> bool:
    sec = _keys_module()
    if sec is None:
        return False
    path = backup_dir or default_backup_dir()
    try:
        store = sec.load_encrypted_keys(path)
        store[CRED_CPF] = cpf
        store[CRED_PASSWORD] = password
        return bool(sec.save_encrypted_keys(path, store))
    except Exception:  # noqa: BLE001
        logger.warning("não foi possível salvar as credenciais da VPN", exc_info=True)
        return False


def forget_credentials(backup_dir: str | None = None) -> bool:
    sec = _keys_module()
    if sec is None:
        return False
    path = backup_dir or default_backup_dir()
    try:
        store = sec.load_encrypted_keys(path)
        changed = False
        for key in (CRED_CPF, CRED_PASSWORD):
            if key in store:
                store.pop(key, None)
                changed = True
        if changed:
            ok = bool(sec.save_encrypted_keys(path, store))
            if ok:
                try:
                    set_auto_connect(False)
                except Exception:  # noqa: BLE001
                    pass
            return ok
        return True
    except Exception:  # noqa: BLE001
        return False


def has_saved_credentials(backup_dir: str | None = None) -> bool:
    cpf, password = load_saved_credentials(backup_dir)
    return bool(cpf and password)


# ═══════════════════════════════════════════════════════════════
# SOCKS5 (stdlib) — roda DENTRO do namespace
# ═══════════════════════════════════════════════════════════════

def _encode_dns_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        raw = label.encode("idna")
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def _dns_query(host: str, server: str, timeout: float = 3.0) -> list[str]:
    """Consulta A via UDP no DNS empurrado pela VPN (sem dependências)."""
    tid = random.randint(0, 65535)
    packet = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    packet += _encode_dns_name(host) + struct.pack("!HH", 1, 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (server, 53))
        data, _ = sock.recvfrom(2048)
    finally:
        sock.close()
    if len(data) < 12:
        return []
    _tid, _flags, qd, an, _ns, _ar = struct.unpack("!HHHHHH", data[:12])
    offset = 12
    for _ in range(qd):
        while offset < len(data) and data[offset] != 0:
            offset += data[offset] + 1
        offset += 5
    addresses = []
    for _ in range(an):
        if offset >= len(data):
            break
        # nome (com compressão)
        if data[offset] & 0xC0 == 0xC0:
            offset += 2
        else:
            while offset < len(data) and data[offset] != 0:
                offset += data[offset] + 1
            offset += 1
        if offset + 10 > len(data):
            break
        rtype, rclass, _ttl, rdlen = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlen]
        offset += rdlen
        if rtype == 1 and rclass == 1 and len(rdata) == 4:
            addresses.append(socket.inet_ntoa(rdata))
    return addresses


def _resolve_for_proxy(host: str, dns_servers: Iterable[str]) -> list[tuple[int, tuple]]:
    """Resolve um nome: DNS da VPN → DNS públicos → resolver do sistema.

    Dentro do namespace o ``/etc/resolv.conf`` do Colab aponta para um
    resolver que não existe naquele namespace (127.0.0.53). Por isso os DNS
    públicos são tentados diretamente via UDP, que o slirp encaminha.
    """
    servers = [s for s in (dns_servers or []) if s]
    for fallback in ("10.0.2.3", "1.1.1.1", "8.8.8.8"):
        if fallback not in servers:
            servers.append(fallback)
    for server in servers:
        try:
            ips = _dns_query(host, server)
            if ips:
                return [(socket.AF_INET, (ip, 0)) for ip in ips]
        except Exception:  # noqa: BLE001
            continue
    try:
        infos = socket.getaddrinfo(host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return [(fam, (sockaddr[0], 0)) for fam, _t, _p, _c, sockaddr in infos]
    except OSError:
        return []


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("conexão encerrada")
        buf += chunk
    return buf


def _socks_reply(conn: socket.socket, code: int, addr: str = "0.0.0.0", port: int = 0) -> None:
    try:
        packed = socket.inet_aton(addr)
        conn.sendall(bytes([5, code, 0, 1]) + packed + struct.pack("!H", port))
    except OSError:
        pass


def _socks_handle(conn: socket.socket, dns_servers: list[str]) -> None:
    target: Optional[socket.socket] = None
    try:
        conn.settimeout(20)
        ver, nmethods = _recv_exact(conn, 2)
        if ver != 5:
            return
        _recv_exact(conn, nmethods)
        conn.sendall(b"\x05\x00")
        ver, cmd, _rsv, atyp = _recv_exact(conn, 4)
        if ver != 5 or cmd != 1:
            _socks_reply(conn, 7)
            return
        if atyp == 1:
            host = socket.inet_ntoa(_recv_exact(conn, 4))
        elif atyp == 4:
            host = socket.inet_ntop(socket.AF_INET6, _recv_exact(conn, 16))
        elif atyp == 3:
            length = _recv_exact(conn, 1)[0]
            host = _recv_exact(conn, length).decode("utf-8", errors="replace")
        else:
            _socks_reply(conn, 8)
            return
        port = struct.unpack("!H", _recv_exact(conn, 2))[0]

        target = None
        if atyp == 3:
            for family, sockaddr in _resolve_for_proxy(host, dns_servers):
                try:
                    cand = socket.socket(family, socket.SOCK_STREAM)
                    cand.settimeout(12)
                    cand.connect((sockaddr[0], port))
                    target = cand
                    break
                except OSError:
                    try:
                        cand.close()
                    except OSError:
                        pass
                    continue
        else:
            try:
                target = socket.create_connection((host, port), timeout=12)
            except OSError:
                target = None

        if target is None:
            _socks_reply(conn, 5)
            return

        try:
            bound = target.getsockname()
            _socks_reply(conn, 0, bound[0] if bound else "0.0.0.0", bound[1] if bound else 0)
        except OSError:
            _socks_reply(conn, 0)

        conn.settimeout(None)
        target.settimeout(None)
        sockets = [conn, target]
        while True:
            readable, _, errored = select.select(sockets, [], sockets, 60)
            if errored or not readable:
                break
            for src in readable:
                dst = target if src is conn else conn
                try:
                    data = src.recv(65536)
                except OSError:
                    data = b""
                if not data:
                    return
                try:
                    dst.sendall(data)
                except OSError:
                    return
    except Exception:  # noqa: BLE001
        logger.debug("erro no SOCKS", exc_info=True)
    finally:
        try:
            conn.close()
        except OSError:
            pass
        try:
            if target is not None:
                target.close()
        except OSError:
            pass


def run_socks_server(bind: str, port: int, dns_servers: list[str]) -> None:
    """Loop do servidor SOCKS5 (executado dentro do namespace)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(64)
    print(
        f"[ufvai-vpn] SOCKS5 em {bind}:{port} dns={','.join(dns_servers) or 'sistema'}",
        flush=True,
    )
    while True:
        try:
            conn, _addr = srv.accept()
        except OSError:
            break
        threading.Thread(
            target=_socks_handle, args=(conn, list(dns_servers)), daemon=True
        ).start()


# ── Encaminhador TCP (porta local → serviço na rede da UFV) ───
# É o que permite usar um modelo local (Ollama/vLLM) que só existe na
# intranet da UFV: o OpenCode fala com 127.0.0.1:<porta> e o tráfego
# atravessa o tun0 do namespace.

def _forward_handle(
    conn: socket.socket,
    target_host: str,
    target_port: int,
    dns_servers: list[str],
) -> None:
    target: Optional[socket.socket] = None
    try:
        conn.settimeout(20)
        for family, (ip, _p) in _resolve_for_proxy(target_host, dns_servers):
            try:
                cand = socket.socket(family, socket.SOCK_STREAM)
                cand.settimeout(15)
                cand.connect((ip, target_port))
                target = cand
                break
            except OSError:
                try:
                    cand.close()
                except OSError:
                    pass
        if target is None:
            return
        conn.settimeout(None)
        target.settimeout(None)
        sockets = [conn, target]
        while True:
            readable, _, errored = select.select(sockets, [], sockets, 60)
            if errored or not readable:
                break
            for src in readable:
                dst = target if src is conn else conn
                try:
                    data = src.recv(65536)
                except OSError:
                    data = b""
                if not data:
                    return
                try:
                    dst.sendall(data)
                except OSError:
                    return
    except Exception:  # noqa: BLE001
        logger.debug("forward: erro no relay", exc_info=True)
    finally:
        for sock in (conn, target):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def run_forward_server(
    bind: str,
    port: int,
    target_host: str,
    target_port: int,
    dns_servers: list[str],
) -> None:
    """Loop do encaminhador TCP (executado dentro do namespace)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(64)
    actual = srv.getsockname()[1]
    print(
        f"[ufvai-vpn] FORWARD em {bind}:{actual} -> {target_host}:{target_port}",
        flush=True,
    )
    while True:
        try:
            conn, _addr = srv.accept()
        except OSError:
            break
        threading.Thread(
            target=_forward_handle,
            args=(conn, target_host, target_port, list(dns_servers)),
            daemon=True,
        ).start()


# ═══════════════════════════════════════════════════════════════
# slirp4netns API
# ═══════════════════════════════════════════════════════════════

def _slirp_api(sock_path: Path, payload: dict, timeout: float = 5.0) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(sock_path))
        client.sendall(json.dumps(payload).encode() + b"\n")
        data = client.recv(8192)
        return json.loads(data.decode("utf-8", errors="replace") or "{}")
    finally:
        client.close()


def _slirp_add_hostfwd(
    sock_path: Path, host_port: int, guest_port: int, guest_addr: str = GUEST_IP
) -> bool:
    try:
        resp = _slirp_api(
            sock_path,
            {
                "execute": "add_hostfwd",
                "arguments": {
                    "proto": "tcp",
                    "host_addr": "127.0.0.1",
                    "host_port": host_port,
                    "guest_addr": guest_addr,
                    "guest_port": guest_port,
                },
            },
        )
        return "error" not in resp
    except Exception:  # noqa: BLE001
        logger.debug("add_hostfwd falhou", exc_info=True)
        return False


# ═══════════════════════════════════════════════════════════════
# Estado / API pública
# ═══════════════════════════════════════════════════════════════

def _set_state(**kwargs) -> None:
    with _LOCK:
        _STATE.update(kwargs)
        try:
            _write_json(state_path(), _public_state())
        except OSError:
            pass


def _public_state() -> dict:
    """Estado sem segredos (nunca inclui CPF completo nem senha)."""
    return {
        "state": _STATE.get("state", "disconnected"),
        "mode": _STATE.get("mode", ""),
        "progress": _STATE.get("progress", ""),
        "last_error": _STATE.get("last_error", ""),
        "connected_at": _iso(float(_STATE.get("connected_at") or 0)),
        "tun_ip": _STATE.get("tun_ip", ""),
        "routes": _STATE.get("routes", []),
        "dns": _STATE.get("dns", []),
        "dns_internal": bool(_STATE.get("dns_internal", False)),
        "dns_detail": _STATE.get("dns_detail", {}),
        "proxy": _STATE.get("proxy", ""),
        "host_port": _STATE.get("host_port", 0),
        "guest_port": _STATE.get("guest_port", 0),
        "forwards": _STATE.get("forwards", []),
        "full_tunnel": bool(_STATE.get("full_tunnel", False)),
        "system_mode": bool(_STATE.get("system_mode", False)),
        "pids": _STATE.get("pids", {}),
        "profile": _STATE.get("profile", {}),
        "cpf_masked": _STATE.get("cpf_masked", ""),
        "log_tail": _tail(log_path(), 25),
    }


def status(backup_dir: str | None = None) -> dict:
    """Status completo para a UI (inclui capacidades e perfil)."""
    caps = capabilities()
    with _LOCK:
        state = _public_state()
        state["capabilities"] = caps

    # Detecta estado "fantasma" (processo morreu / boot novo).
    if state["state"] in ("connected", "connecting"):
        pids = state.get("pids") or {}
        if pids and not all(_pid_alive(int(p)) for p in pids.values() if p):
            with _LOCK:
                _STATE["state"] = "error"
                _STATE["last_error"] = "A conexão caiu (processo da VPN não está mais ativo)."
                _STATE["progress"] = ""
                _STATE["proxy"] = ""
                _STATE["tun_ip"] = ""
                _STATE["pids"] = {}
                _write_json(state_path(), _public_state())
            state = _public_state()
            state["capabilities"] = caps

    prof = profile_path()
    if prof.exists():
        meta = parse_profile(_read(prof))
        meta["path"] = str(prof)
        meta["source"] = "cache"
        state["profile"] = meta
    else:
        state["profile"] = {"valid": False}

    state["has_saved_credentials"] = has_saved_credentials(backup_dir)
    if state["has_saved_credentials"]:
        cpf, _pw = load_saved_credentials(backup_dir)
        state["saved_cpf_masked"] = _mask_cpf(cpf)
    else:
        state["saved_cpf_masked"] = ""
    state["should_ask"] = should_ask(backup_dir)
    state["prefs"] = load_prefs()
    # v0.7.11-web12: a decisão ("sou aluno" / "continuar sem VPN") fica no
    # Drive; a UI usa estes campos para não repetir a pergunta e para mostrar
    # que a reconexão automática está armada.
    state["auto_connect"] = bool(state["prefs"].get("auto_connect"))
    state["auto_connect_ready"] = bool(
        state["auto_connect"] and state["has_saved_credentials"]
    )
    state["prefs_persistent"] = persistent_prefs_path() is not None
    state["guide_url"] = "https://vpn.ufvnet.ufv.br/linux_ubuntu.html"
    state["profile_url"] = PROFILE_URL
    state["ok"] = True
    return state


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def add_forward(
    host: str,
    port: int,
    local_port: int = 0,
    backup_dir: str | None = None,
) -> dict:
    """Publica um serviço da rede da UFV em ``127.0.0.1:<local_port>``.

    Exemplo (modelo Ollama na intranet):
        add_forward("10.0.0.10", 11434, 11435)
        # OpenCode → http://127.0.0.1:11435/v1
    """
    host = (host or "").strip()
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise VPNError("Porta remota inválida.")
    if not host:
        raise VPNError("Informe o host interno (IP ou nome na rede da UFV).")
    if not (1 <= port <= 65535):
        raise VPNError("Porta remota fora do intervalo 1–65535.")

    with _LOCK:
        if _STATE.get("state") != "connected":
            raise VPNError("Conecte a VPN da UFV antes de encaminhar a porta.")
        ns_pid = (_STATE.get("pids") or {}).get("ns")
        dns = list(_STATE.get("dns") or [])
    if not ns_pid or not _pid_alive(int(ns_pid)):
        raise VPNError("O namespace da VPN não está ativo. Reconecte.")

    if local_port:
        local_port = int(local_port)
        if not (1 <= local_port <= 65535):
            raise VPNError("Porta local fora do intervalo 1–65535.")
        if not _port_is_free("127.0.0.1", local_port):
            raise VPNError(f"A porta local {local_port} já está em uso.")
    else:
        local_port = _free_port(11435, 11535)

    stamp = int(_now() * 1000)
    log = state_dir() / f"forward-{stamp}.log"
    root = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [
            "nsenter", "-t", str(ns_pid), "-m", "-n",
            sys.executable, "-m", "pesquisai.vpn", "--forward-server",
            "--bind", "0.0.0.0:0",
            "--target", f"{host}:{port}",
            "--dns", ",".join(dns),
        ],
        stdout=open(log, "wb"),
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )

    guest_port = 0
    deadline = _now() + 12
    while _now() < deadline:
        match = re.search(r"FORWARD em [^:]+:(\d+)", _read(log, 4000))
        if match:
            guest_port = int(match.group(1))
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    if not guest_port:
        _kill_pid(proc.pid)
        tail = _read(log, 4000)[-400:]
        raise VPNError(
            "O encaminhador não conseguiu abrir a porta dentro do namespace. "
            + (tail or "Veja " + str(log))
        )

    api = state_dir() / "slirp.sock"
    if not _slirp_add_hostfwd(api, local_port, guest_port, GUEST_IP):
        _kill_pid(proc.pid)
        raise VPNError("Não foi possível publicar a porta no Colab (add_hostfwd).")
    if not _wait_for(lambda: _port_open("127.0.0.1", local_port), timeout=6):
        _kill_pid(proc.pid)
        raise VPNError("A porta foi publicada, mas não respondeu em 127.0.0.1.")

    fwd = {
        "id": f"fwd{stamp}",
        "local_port": local_port,
        "local_url": f"http://127.0.0.1:{local_port}",
        "openai_base": f"http://127.0.0.1:{local_port}/v1",
        "remote_host": host,
        "remote_port": port,
        "guest_port": guest_port,
        "pid": proc.pid,
        "created": _iso(_now()),
    }
    with _LOCK:
        _STATE.setdefault("forwards", []).append(fwd)
        _STATE.setdefault("pids", {})[f"forward_{fwd['id']}"] = proc.pid
        _write_json(state_path(), _public_state())
    logger.info("VPN forward %s -> %s:%s", local_port, host, port)
    return fwd


def remove_forward(forward_id: str, backup_dir: str | None = None) -> bool:
    """Encerra um encaminhamento e libera a porta local."""
    with _LOCK:
        forwards = list(_STATE.get("forwards") or [])
        fwd = next((f for f in forwards if f.get("id") == forward_id), None)
        if not fwd:
            return False
        _STATE["forwards"] = [f for f in forwards if f.get("id") != forward_id]
        pid = (_STATE.get("pids") or {}).pop(f"forward_{forward_id}", None)
        _write_json(state_path(), _public_state())
    if pid:
        _kill_pid(int(pid))
    # Melhor esforço: remove o hostfwd (versões novas do slirp4netns).
    try:
        _slirp_api(
            state_dir() / "slirp.sock",
            {
                "execute": "remove_hostfwd",
                "arguments": {
                    "proto": "tcp",
                    "host_addr": "127.0.0.1",
                    "host_port": int(fwd.get("local_port") or 0),
                },
            },
        )
    except Exception:  # noqa: BLE001
        pass
    return True


def publish_port(
    local_port: int,
    guest_port: int,
    guest_addr: str = GUEST_IP,
) -> dict:
    """Publica uma porta que já está aberta DENTRO do namespace.

    Usado pelo modo "todo o UFVAI na VPN": o ttyd escuta 8000 no namespace
    e o host publica 127.0.0.1:8000 → 10.0.2.100:8000.
    """
    with _LOCK:
        if _STATE.get("state") != "connected":
            raise VPNError("Conecte a VPN antes de publicar a porta.")
    ok = _slirp_add_hostfwd(
        state_dir() / "slirp.sock", int(local_port), int(guest_port), guest_addr
    )
    if not ok:
        raise VPNError(f"Não foi possível publicar 127.0.0.1:{local_port}.")
    return {
        "local_port": int(local_port),
        "guest_port": int(guest_port),
        "guest_addr": guest_addr,
    }


def unpublish_port(local_port: int, host_addr: str = "127.0.0.1") -> None:
    """Remove um hostfwd publicado (melhor esforço)."""
    try:
        _slirp_api(
            state_dir() / "slirp.sock",
            {
                "execute": "remove_hostfwd",
                "arguments": {
                    "proto": "tcp",
                    "host_addr": host_addr,
                    "host_port": int(local_port),
                },
            },
        )
    except Exception:  # noqa: BLE001
        pass


def set_system_mode(enabled: bool) -> None:
    with _LOCK:
        _STATE["system_mode"] = bool(enabled)
        try:
            _write_json(state_path(), _public_state())
        except OSError:
            pass


def _cleanup_processes() -> None:
    with _LOCK:
        pids = dict(_STATE.get("pids") or {})
        _STATE["pids"] = {}
        _STATE["forwards"] = []
    # Primeiro os encaminhamentos, depois OpenVPN/SOCKS/slirp/namespace.
    for key, pid in pids.items():
        if key.startswith("forward_") and pid:
            _kill_pid(int(pid))
    for key in ("openvpn", "socks", "slirp", "ns"):
        pid = pids.get(key)
        if pid:
            _kill_pid(int(pid))
    auth = state_dir() / "run" / "auth"
    try:
        auth.unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_stale() -> None:
    """Chamado no boot: encerra restos de uma sessão anterior."""
    try:
        if not state_path().exists():
            return
        data = json.loads(_read(state_path()) or "{}")
        pids = data.get("pids") or {}
        alive = [int(p) for p in pids.values() if p and _pid_alive(int(p))]
        if alive:
            for pid in alive:
                _kill_pid(pid)
        with _LOCK:
            _STATE.update(
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
                }
            )
            _write_json(state_path(), _public_state())
    except Exception:  # noqa: BLE001
        logger.debug("cleanup_stale da VPN falhou", exc_info=True)


def _wait_for(predicate, timeout: float, interval: float = 0.3) -> bool:
    end = _now() + timeout
    while _now() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _log_contains(path: Path, needles: Iterable[str]) -> str:
    text = _read(path)
    for needle in needles:
        if needle in text:
            return needle
    return ""


def _parse_pushed(text: str) -> tuple[list[str], list[str]]:
    """Extrai rotas e DNS do log do OpenVPN.

    O ``PUSH_REPLY`` pode vir fatiado em várias linhas e o ``dhcp-option
    DNS`` também aparece na diretiva do perfil — por isso o DNS é varrido
    no log inteiro, não apenas na linha do PUSH.
    """
    routes: list[str] = []
    dns: list[str] = []
    for line in text.splitlines():
        if "PUSH: Received control message" not in line:
            continue
        if "route " in line:
            for chunk in re.findall(r"route\s+([0-9./]+\s+[0-9.]+(?:\s+\S+)?)", line):
                chunk = chunk.strip()
                if chunk and chunk not in routes:
                    routes.append(chunk)
    for server in re.findall(r"dhcp-option\s+DNS6?\s+([0-9a-fA-F:.]+)", text):
        server = server.strip()
        if server and server not in dns:
            dns.append(server)
    return routes, dns


def _dns_probe(ns_pid: int, server: str, host: str, timeout: float = 4.0) -> list[str]:
    """Consulta um DNS específico **dentro** do namespace."""
    dig = _which("dig")
    if dig:
        proc = _ns(
            [dig, "+short", "+time=2", "+tries=1", f"@{server}", host],
            ns_pid, timeout=timeout + 2,
        )
        return [
            line.strip() for line in (proc.stdout or "").splitlines()
            if line.strip() and not line.startswith(";")
        ]
    proc = _ns(["getent", "hosts", host], ns_pid, timeout=timeout + 2)
    ips = []
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if parts:
            ips.append(parts[0])
    return ips


def _discover_dns(ns_pid: int, pushed: Iterable[str]) -> dict:
    """Descobre qual DNS resolve os nomes internos da UFV.

    O perfil oficial não traz ``dhcp-option DNS`` e o servidor pode não
    empurrar um. Nesse caso o único resolver que enxerga ``*.ufv.br``
    interno é o da própria rede da UFV — testamos o gateway do túnel
    (``10.255.0.1``) e o DNS do slirp, nessa ordem, e registramos o que
    realmente respondeu.
    """
    candidates: list[str] = []
    for server in list(pushed or []):
        if server and server not in candidates:
            candidates.append(server)
    # 200.235.128.2 / .129.2 = ns1/ns2.cpd.ufv.br (delegação pública de
    # ufv.br). De fora eles respondem só a visão externa; dentro da rede da
    # UFV (pelo túnel) respondem a visão interna, onde sistemas.ufv.br existe.
    for server in (
        "10.255.0.1",
        "200.235.128.2",
        "200.235.129.2",
        "10.0.2.3",
        "1.1.1.1",
    ):
        if server not in candidates:
            candidates.append(server)

    detail: dict[str, dict] = {}
    internal: list[str] = []
    public: list[str] = []
    for server in candidates:
        internal_ips = _dns_probe(ns_pid, server, "sistemas.ufv.br")
        public_ips = _dns_probe(ns_pid, server, "www.ufv.br")
        detail[server] = {"internal": internal_ips[:3], "public": public_ips[:3]}
        if internal_ips:
            internal.append(server)
        if public_ips:
            public.append(server)

    ordered = list(internal)
    for server in public:
        if server not in ordered:
            ordered.append(server)
    for server in candidates:
        if server not in ordered and (
            detail[server]["internal"] or detail[server]["public"]
        ):
            ordered.append(server)
    return {
        "servers": ordered,
        "internal": internal,
        "public": public,
        "detail": detail,
    }


def _tun_counters(ns_pid: int) -> dict:
    """Bytes que passaram pela interface ``tun0`` (prova de uso do túnel)."""
    out = {"tx": 0, "rx": 0}
    for key, stat in (("tx", "tx_bytes"), ("rx", "rx_bytes")):
        proc = _ns(
            ["cat", f"/sys/class/net/tun0/statistics/{stat}"],
            ns_pid, timeout=5,
        )
        try:
            out[key] = int((proc.stdout or "").strip())
        except ValueError:
            out[key] = 0
    return out


def _ns(args: list[str], ns_pid: int, timeout: float = 10) -> subprocess.CompletedProcess:
    # -m: o namespace tem um /etc/resolv.conf próprio (bind mount), essencial
    # para o OpenCode/terminal resolverem nomes internos da UFV.
    return subprocess.run(
        ["nsenter", "-t", str(ns_pid), "-m", "-n"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _tun_ip(ns_pid: int) -> str:
    try:
        proc = _ns(["ip", "-4", "-o", "addr", "show", "dev", "tun0"], ns_pid)
        match = re.search(r"inet\s+([0-9.]+)", proc.stdout)
        return match.group(1) if match else ""
    except Exception:  # noqa: BLE001
        return ""


def _ns_routes(ns_pid: int) -> list[str]:
    try:
        proc = _ns(["ip", "-4", "route", "show"], ns_pid)
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:  # noqa: BLE001
        return []


def _free_port(start: int, end: int = 0) -> int:
    end = end or start + 20
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise OSError(f"nenhuma porta livre entre {start} e {end}")


def _connect_worker(
    cpf: str, password: str, remember: bool, backup_dir: str | None,
    full_tunnel: bool = False,
) -> None:
    try:
        _connect_impl(cpf, password, remember, backup_dir, full_tunnel)
    except VPNError as exc:
        if _CANCEL.is_set():
            return  # o disconnect() já limpou e definiu o estado
        _fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        if _CANCEL.is_set():
            return
        logger.exception("erro inesperado na VPN")
        _fail(f"Erro inesperado: {type(exc).__name__}: {exc}")


def _check_cancel() -> None:
    if _CANCEL.is_set():
        raise VPNError("Conexão cancelada.")


class VPNError(RuntimeError):
    """Erro de conexão com mensagem pronta para o usuário."""


def _fail(message: str) -> None:
    _cleanup_processes()
    with _LOCK:
        _STATE.update(
            {
                "state": "error",
                "progress": "",
                "last_error": _redact(message)[:600],
                "proxy": "",
                "tun_ip": "",
                "connected_at": 0.0,
            }
        )
        try:
            _write_json(state_path(), _public_state())
        except OSError:
            pass


def _connect_impl(
    cpf: str, password: str, remember: bool, backup_dir: str | None,
    full_tunnel: bool = False,
) -> None:
    caps = capabilities()
    if caps["mode"] == "unavailable":
        ok, msg = ensure_dependencies()
        if not ok:
            raise VPNError(msg)
        caps = capabilities()
        if caps["mode"] == "unavailable":
            raise VPNError(
                "Este ambiente não permite VPN: faltam TUN/NET_ADMIN e não há "
                "unshare + slirp4netns. No Colab isso normalmente funciona; "
                "verifique se o runtime é o padrão."
            )

    _CANCEL.clear()
    _set_state(
        state="connecting",
        mode=caps["mode"],
        progress="Preparando o perfil da UFV…",
        last_error="",
        connected_at=0.0,
        tun_ip="",
        routes=[],
        dns=[],
        proxy="",
    )

    # 1) Perfil
    prof = profile_path()
    if not prof.exists():
        _set_state(progress="Baixando o perfil oficial da UFV…")
        try:
            meta = fetch_profile()
        except Exception as exc:  # noqa: BLE001
            raise VPNError(
                "Não foi possível baixar o perfil da VPN da UFV "
                f"({exc}). Baixe manualmente em {PROFILE_URL} e cole no campo "
                "'Perfil .ovpn' do painel."
            ) from exc
    else:
        meta = parse_profile(_read(prof))
        if not meta["valid"]:
            raise VPNError(
                "O perfil .ovpn salvo está inválido. Baixe novamente em "
                f"{PROFILE_URL}."
            )

    host = meta["remote_host"] or DEFAULT_REMOTE_HOST
    port = meta["remote_port"] or DEFAULT_REMOTE_PORT
    _set_state(progress=f"Resolvendo {host}…")
    try:
        remote_ip = _resolve_remote(host, port)
    except OSError as exc:
        raise VPNError(f"Não foi possível resolver {host}: {exc}") from exc

    _check_cancel()
    _set_state(progress="Preparando o OpenVPN…")
    ok, msg = ensure_dependencies()
    _check_cancel()
    if not ok:
        raise VPNError(msg)
    ok_tun, msg_tun = ensure_tun()
    if not ok_tun and caps["mode"] == "netns":
        raise VPNError(msg_tun)

    run_dir = state_dir() / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(run_dir, 0o700)
    auth_file = run_dir / "auth"
    auth_file.write_text(f"{cpf}\n{password}\n", encoding="utf-8")
    os.chmod(auth_file, 0o600)

    runtime = runtime_profile_path()
    runtime.write_text(
        _build_runtime_profile(_read(prof), remote_ip, port, full_tunnel),
        encoding="utf-8",
    )
    os.chmod(runtime, 0o600)

    if caps["mode"] == "direct":
        _connect_direct(runtime, auth_file, cpf, password, remember, backup_dir, full_tunnel)
    else:
        _connect_netns(runtime, auth_file, cpf, password, remember, backup_dir, full_tunnel)


def _connect_direct(
    runtime: Path,
    auth_file: Path,
    cpf: str,
    password: str,
    remember: bool,
    backup_dir: str | None,
    full_tunnel: bool = False,
) -> None:
    _set_state(progress="Iniciando o OpenVPN (modo direto)…")
    log = openvpn_log_path()
    log.write_text("", encoding="utf-8")
    ovpn = subprocess.Popen(
        [
            _which("openvpn"),
            "--config", str(runtime),
            "--auth-user-pass", str(auth_file),
            "--auth-nocache",
            "--script-security", "0",
            "--verb", "4",
            "--log", str(log),
            "--writepid", str(state_dir() / "run" / "openvpn.pid"),
            "--connect-retry-max", "2",
            "--ping", "10",
            "--ping-restart", "60",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    with _LOCK:
        _STATE["pids"] = {"openvpn": ovpn.pid}

    _wait_openvpn(log, timeout=60)
    text = _read(log)
    routes, dns = _parse_pushed(text)
    tun_ip = ""
    match = re.search(r"ifconfig\s+([0-9.]+)\s+([0-9.]+)", text)
    if match:
        tun_ip = match.group(1)
    _finish_connect(
        tun_ip, routes, dns, cpf, password, remember, backup_dir,
        "direct", full_tunnel=full_tunnel,
    )


def _connect_netns(
    runtime: Path,
    auth_file: Path,
    cpf: str,
    password: str,
    remember: bool,
    backup_dir: str | None,
    full_tunnel: bool = False,
) -> None:
    _set_state(progress="Criando o namespace isolado…")
    # v0.7.11: mount namespace + resolv.conf próprio. Sem isso, o OpenCode
    # (e qualquer processo do namespace) herdaria o resolver do Colab, que
    # não existe lá dentro — e nomes internos da UFV não resolveriam.
    resolv = state_dir() / "resolv.conf"
    # 10.0.2.3 = DNS do slirp4netns (sai por tap0, NÃO entra no túnel).
    # Resolve nomes públicos mesmo em túnel total; o DNS da VPN, quando
    # empurrado, entra na frente para resolver os nomes internos.
    resolv.write_text(
        "nameserver 10.0.2.3\nnameserver 1.1.1.1\n", encoding="utf-8"
    )
    ns_proc = subprocess.Popen(
        [
            "unshare", "-Urnm", "sh", "-c",
            'mount --bind "$1" /etc/resolv.conf && exec sleep 2147483647',
            "sh", str(resolv),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    time.sleep(0.4)
    if ns_proc.poll() is not None:
        err = (ns_proc.stderr.read() if ns_proc.stderr else "") or "unshare falhou"
        raise VPNError(
            "Não foi possível criar o namespace de rede (unshare). "
            f"Detalhe: {err.strip()[:300]}"
        )

    api_sock = state_dir() / "slirp.sock"
    try:
        api_sock.unlink(missing_ok=True)
    except OSError:
        pass

    _set_state(progress="Ligando o namespace à internet (slirp4netns)…")
    slirp_log = state_dir() / "slirp.log"
    slirp = subprocess.Popen(
        [
            _which("slirp4netns"),
            "--configure",
            "--mtu=65520",
            "--api-socket", str(api_sock),
            str(ns_proc.pid),
            "tap0",
        ],
        stdout=open(slirp_log, "wb"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    with _LOCK:
        _STATE["pids"] = {"ns": ns_proc.pid, "slirp": slirp.pid}

    if not _wait_for(lambda: api_sock.exists(), timeout=8):
        raise VPNError(
            "O slirp4netns não subiu (API socket ausente). "
            "Veja o log em " + str(slirp_log)
        )
    if not _wait_for(
        lambda: "tap0" in (_ns(["ip", "link", "show", "tap0"], ns_proc.pid).stdout or ""),
        timeout=8,
    ):
        raise VPNError("A interface tap0 não apareceu no namespace.")

    _set_state(progress="Iniciando o OpenVPN no namespace…")
    log = openvpn_log_path()
    log.write_text("", encoding="utf-8")
    ovpn = subprocess.Popen(
        [
            "nsenter", "-t", str(ns_proc.pid), "-m", "-n",
            _which("openvpn"),
            "--config", str(runtime),
            "--auth-user-pass", str(auth_file),
            "--auth-nocache",
            "--script-security", "0",
            "--verb", "4",
            "--log", str(log),
            "--writepid", str(state_dir() / "run" / "openvpn.pid"),
            "--connect-retry-max", "2",
            "--ping", "10",
            "--ping-restart", "60",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    with _LOCK:
        _STATE["pids"] = {"ns": ns_proc.pid, "slirp": slirp.pid, "openvpn": ovpn.pid}

    _wait_openvpn(log, timeout=75)
    text = _read(log)
    routes, pushed_dns = _parse_pushed(text)

    _set_state(progress="Verificando o DNS da UFV…")
    dns_probe = _discover_dns(ns_proc.pid, pushed_dns)
    dns = list(dns_probe["servers"]) or list(pushed_dns)
    # 10.0.2.3 resolve nomes públicos mesmo em túnel total; os DNS da UFV
    # ficam como alternativa para a visão interna; 1.1.1.1 é o último
    # recurso (pode ser bloqueado pela UFV).
    for fallback in ("10.0.2.3", "200.235.128.2", "200.235.129.2", "1.1.1.1"):
        if fallback not in dns:
            dns.append(fallback)

    _set_state(progress="Lendo a interface do túnel…")
    try:
        resolv.write_text(
            "\n".join(f"nameserver {s}" for s in dns) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    tun_ip = ""
    if _wait_for(lambda: bool(_tun_ip(ns_proc.pid)), timeout=10):
        tun_ip = _tun_ip(ns_proc.pid)
    ns_routes = _ns_routes(ns_proc.pid)
    if ns_routes:
        routes = ns_routes

    # 2) SOCKS5 dentro do namespace
    _set_state(progress="Iniciando o proxy SOCKS5…")
    host_port = _free_port(SOCKS_HOST_PORT)
    guest_port = SOCKS_GUEST_PORT
    socks_env = dict(os.environ)
    root = str(Path(__file__).resolve().parent.parent)
    socks_env["PYTHONPATH"] = root + os.pathsep + socks_env.get("PYTHONPATH", "")
    socks = subprocess.Popen(
        [
            "nsenter", "-t", str(ns_proc.pid), "-m", "-n",
            sys.executable, "-m", "pesquisai.vpn", "--socks-server",
            "--bind", f"0.0.0.0:{guest_port}",
            "--dns", ",".join(dns),
        ],
        stdout=open(state_dir() / "socks.log", "wb"),
        stderr=subprocess.STDOUT,
        env=socks_env,
        start_new_session=True,
    )
    with _LOCK:
        _STATE["pids"] = {
            "ns": ns_proc.pid,
            "slirp": slirp.pid,
            "openvpn": ovpn.pid,
            "socks": socks.pid,
        }

    if not _wait_for(
        lambda: "SOCKS5 em" in _read(state_dir() / "socks.log", 4000), timeout=12
    ):
        raise VPNError(
            "O proxy SOCKS5 não abriu dentro do namespace. Veja "
            + str(state_dir() / "socks.log")
        )

    _set_state(progress="Publicando o proxy no Colab…")
    if not _slirp_add_hostfwd(api_sock, host_port, guest_port, GUEST_IP):
        raise VPNError("Não foi possível publicar o proxy SOCKS5 (add_hostfwd).")
    if not _wait_for(lambda: _port_open("127.0.0.1", host_port), timeout=8):
        raise VPNError(
            "O proxy foi publicado, mas a porta 127.0.0.1:%d não respondeu. "
            "Veja %s" % (host_port, state_dir() / "socks.log")
        )

    _finish_connect(
        tun_ip, routes, dns, cpf, password, remember, backup_dir,
        "netns", proxy=f"socks5h://127.0.0.1:{host_port}",
        host_port=host_port, guest_port=guest_port,
        full_tunnel=full_tunnel,
        dns_internal=bool(dns_probe["internal"]),
        dns_detail=dns_probe["detail"],
    )


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_openvpn(log: Path, timeout: float = 70) -> None:
    """Aguarda o handshake terminar e traduz os erros mais comuns."""
    end = _now() + timeout
    while _now() < end:
        _check_cancel()
        text = _read(log)
        if "Initialization Sequence Completed" in text:
            return
        if "AUTH_FAILED" in text:
            raise VPNError(
                "CPF ou senha recusados pela VPN da UFV. Confira as credenciais "
                "do portal vpn.ufvnet.ufv.br (a senha é a mesma da VPN, não a do "
                "e-mail)."
            )
        if "Cannot open TUN/TAP" in text or "TUNSETIFF" in text:
            raise VPNError(
                "O OpenVPN não conseguiu abrir o dispositivo TUN. No Colab isso "
                "é resolvido pelo namespace isolado; verifique se o runtime tem "
                "unshare + slirp4netns."
            )
        if "Options error" in text:
            line = next(
                (ln for ln in text.splitlines() if "Options error" in ln), ""
            )
            raise VPNError(f"Erro de opção no perfil: {line[:300]}")
        if "TLS Error" in text and "handshake failed" in text:
            raise VPNError(
                "O servidor da UFV não completou o handshake TLS. Verifique se "
                "a rede do Colab alcança vpn.ufvnet.ufv.br:1195 (UDP)."
            )
        time.sleep(0.4)
    tail = "\n".join(_tail(log, 12))
    raise VPNError(
        "Tempo esgotado aguardando a VPN. Últimas linhas do OpenVPN:\n"
        + _redact(tail)[-800:]
    )


def _finish_connect(
    tun_ip: str,
    routes: list[str],
    dns: list[str],
    cpf: str,
    password: str,
    remember: bool,
    backup_dir: str | None,
    mode: str,
    proxy: str = "",
    host_port: int = 0,
    guest_port: int = 0,
    full_tunnel: bool = False,
    dns_internal: bool = False,
    dns_detail: dict | None = None,
) -> None:
    if remember:
        save_credentials(cpf, password, backup_dir)
    # v0.7.11-web12: conexão bem-sucedida com credenciais salvas = o próximo
    # boot reconecta sozinho (sem repetir a pergunta inicial).
    try:
        if remember:
            set_auto_connect(True)
    except Exception:  # noqa: BLE001 — preferência não pode derrubar a conexão
        pass
    with _LOCK:
        _STATE.update(
            {
                "state": "connected",
                "mode": mode,
                "progress": "Conectado à VPN da UFV",
                "last_error": "",
                "connected_at": _now(),
                "tun_ip": tun_ip,
                "routes": routes[:40],
                "dns": dns[:6],
                "dns_internal": bool(dns_internal),
                "dns_detail": dns_detail or {},
                "proxy": proxy,
                "host_port": host_port,
                "guest_port": guest_port,
                "forwards": [],
                "full_tunnel": bool(full_tunnel),
                "cpf_masked": _mask_cpf(cpf),
            }
        )
        _write_json(state_path(), _public_state())


def connect(
    cpf: str = "",
    password: str = "",
    remember: bool = False,
    use_saved: bool = False,
    backup_dir: str | None = None,
    full_tunnel: bool = False,
) -> dict:
    """Conecta à VPN da UFV.

    v0.7.11: o PADRÃO é **split tunnel** (``full_tunnel=False``) com o
    serviço do OpenCode DENTRO do namespace: a rede da UFV
    (``100.65.0.0/17``…, ``200.235.128.0/17``) sai por ``tun0`` e a internet
    comum (LLM, GitHub, PyPI) continua pelo Colab via ``tap0``.

    ``full_tunnel=True`` (``redirect-gateway def1``) manda TODO o tráfego
    para a UFV — medido em 07/11/2026: a UFV **bloqueia a saída externa**
    (OpenRouter, Google, OpenAI, GitHub e PyPI dão timeout; só hosts da UFV
    respondem). Serve para modelos/serviços internos da UFV, não para LLM
    em nuvem.
    """
    """Inicia a conexão em segundo plano e devolve o estado imediatamente."""
    global _CONNECT_THREAD

    cpf = re.sub(r"\D", "", cpf or "")
    password = (password or "").strip()

    # v0.7.11: completa o que faltou com o que está salvo (o usuário pode
    # digitar só a senha nova, ou só confirmar o CPF, sem redigitar tudo).
    if use_saved or not cpf or not password:
        saved_cpf, saved_pw = load_saved_credentials(backup_dir)
        cpf = cpf or saved_cpf
        password = password or saved_pw

    if len(cpf) != 11:
        raise VPNError("Informe o CPF (11 dígitos) usado no portal da VPN da UFV.")
    if not password:
        raise VPNError("Informe a senha da VPN da UFV.")

    with _LOCK:
        if _STATE.get("state") == "connected":
            return status(backup_dir)
        if _CONNECT_THREAD and _CONNECT_THREAD.is_alive():
            return status(backup_dir)
        _STATE.update(
            {
                "state": "connecting",
                "progress": "Iniciando…",
                "last_error": "",
                "cpf_masked": _mask_cpf(cpf),
            }
        )
        _CONNECT_THREAD = threading.Thread(
            target=_connect_worker,
            args=(cpf, password, remember, backup_dir, full_tunnel),
            daemon=True,
            name="ufvai-vpn-connect",
        )
        _CONNECT_THREAD.start()
    return status(backup_dir)


def disconnect(backup_dir: str | None = None) -> dict:
    """Encerra a VPN e o proxy, apagando o arquivo de credenciais.

    Também desliga a reconexão automática: se o usuário desconectou de
    propósito, o próximo boot não deve reconectar sem ele pedir.
    """
    _CANCEL.set()
    try:
        set_auto_connect(False)
    except Exception:  # noqa: BLE001
        pass
    _cleanup_processes()
    with _LOCK:
        _STATE.update(
            {
                "state": "disconnected",
                "mode": "",
                "progress": "",
                "last_error": "",
                "connected_at": 0.0,
                "tun_ip": "",
                "routes": [],
                "dns": [],
                "dns_internal": False,
                "dns_detail": {},
                "proxy": "",
                "host_port": 0,
                "guest_port": 0,
                "forwards": [],
                "full_tunnel": False,
                "system_mode": False,
                "cpf_masked": "",
            }
        )
        try:
            _write_json(state_path(), _public_state())
        except OSError:
            pass
    return status(backup_dir)


# ═══════════════════════════════════════════════════════════════
# Teste de acesso através do proxy
# ═══════════════════════════════════════════════════════════════

def _curl_raw(
    proxy: str, url: str, timeout: int = 15, want_body: bool = False
) -> dict:
    """GET via curl (opcionalmente por SOCKS5) devolvendo status e corpo."""
    curl = _which("curl")
    if not curl:
        return {"ok": False, "error": "curl não encontrado", "url": url, "http": "", "body": ""}
    cmd = [curl, "-sS", "--max-time", str(timeout), "-w", "\n%{http_code}"]
    clean = (proxy or "").replace("socks5h://", "").replace("socks5://", "")
    if clean:
        cmd += ["--socks5-hostname", clean]
    cmd.append(url)
    started = _now()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        out = proc.stdout or ""
        body, _, code = out.rpartition("\n")
        code = code.strip()
        return {
            "ok": proc.returncode == 0 and code not in ("", "000"),
            "url": url,
            "http": code,
            "body": body if want_body else "",
            "seconds": round(_now() - started, 2),
            "error": (proc.stderr or "").strip()[:300] if proc.returncode else "",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": url, "http": "", "body": "", "error": str(exc)}


def _curl_through_proxy(proxy: str, url: str, timeout: int = 15) -> dict:
    return _curl_raw(proxy, url, timeout=timeout, want_body=False)


def _curl_in_ns(
    ns_pid: int, url: str, timeout: int = 15, want_body: bool = False
) -> dict:
    """GET **dentro** do namespace da VPN (é o caminho real do OpenCode).

    Não depende do proxy SOCKS5: usa as rotas/DNS do próprio namespace. No
    modo total, é a única forma honesta de saber se o túnel está roteando.
    """
    curl = _which("curl")
    if not curl:
        return {"ok": False, "error": "curl não encontrado", "url": url, "http": "", "body": ""}
    cmd = [
        "nsenter", "-t", str(ns_pid), "-m", "-n",
        curl, "-sS", "--max-time", str(timeout), "-w", "\n%{http_code}",
    ]
    cmd.append(url)
    started = _now()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        out = proc.stdout or ""
        body, _, code = out.rpartition("\n")
        code = code.strip()
        return {
            "ok": proc.returncode == 0 and code not in ("", "000"),
            "url": url,
            "http": code,
            "body": body if want_body else "",
            "seconds": round(_now() - started, 2),
            "error": (proc.stderr or "").strip()[:300] if proc.returncode else "",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": url, "http": "", "body": "", "error": str(exc)}


def _ip_via_ns(ns_pid: int, timeout: int = 10) -> tuple[str, str]:
    for url in (
        "https://api.ipify.org?format=json",
        "https://icanhazip.com",
        "https://ifconfig.me/ip",
    ):
        res = _curl_in_ns(ns_pid, url, timeout=timeout, want_body=True)
        if not res.get("ok"):
            continue
        body = (res.get("body") or "").strip()
        ip = ""
        try:
            data = json.loads(body)
            ip = str(data.get("ip") or "")
        except (ValueError, TypeError):
            ip = body.split()[0] if body else ""
        if ip:
            return ip, url
    return "", ""


def _ns_diag(ns_pid: int, host: str) -> dict:
    """DNS + rota do host dentro do namespace (diagnóstico do teste)."""
    out = {"host": host, "ip": "", "route": ""}
    try:
        p = _ns(["getent", "hosts", host], ns_pid, timeout=6)
        line = (p.stdout or "").strip().splitlines()
        if line:
            parts = line[0].split()
            out["ip"] = parts[0] if parts else ""
        if out["ip"]:
            r = _ns(["ip", "route", "get", out["ip"]], ns_pid, timeout=6)
            out["route"] = (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        pass
    return out


def _ip_via(proxy: str, timeout: int = 10) -> tuple[str, str]:
    """Descobre o IP público visto por um caminho (proxy vazio = direto)."""
    for url in (
        "https://api.ipify.org?format=json",
        "https://icanhazip.com",
        "https://ifconfig.me/ip",
    ):
        res = _curl_raw(proxy, url, timeout=timeout, want_body=True)
        if not res.get("ok"):
            continue
        body = (res.get("body") or "").strip()
        ip = ""
        try:
            data = json.loads(body)
            ip = str(data.get("ip") or "")
        except (ValueError, TypeError):
            ip = body.split()[0] if body else ""
        if ip:
            return ip, url
    return "", ""


def test(proxy: str = "", timeout: int = 15, url: str = "") -> dict:
    """Testa se o tráfego está realmente saindo pela VPN.

    No modo ``netns`` o teste roda **dentro do namespace** (o mesmo caminho
    do OpenCode/terminal), sem depender do proxy SOCKS5. No modo ``direct``
    usa o host. A prova mais forte é comparar o **IP público direto** com o
    **IP público do túnel**: se forem diferentes, o tráfego passa pela UFV.
    """
    with _LOCK:
        proxy = proxy or _STATE.get("proxy", "")
        mode = _STATE.get("mode", "")
        ns_pid = (_STATE.get("pids") or {}).get("ns")
        full = bool(_STATE.get("full_tunnel", False))
        tun = _STATE.get("tun_ip", "")
        routes = list(_STATE.get("routes") or [])
        dns = list(_STATE.get("dns") or [])
        dns_internal = bool(_STATE.get("dns_internal", False))
    use_ns = bool(mode == "netns" and ns_pid and _pid_alive(int(ns_pid)))
    if not proxy and not use_ns:
        return {
            "ok": False,
            "verdict": "no_proxy",
            "error": "A VPN não está conectada (sem proxy/namespace ativo).",
            "proxy": "",
            "proxy_ip": "",
            "direct_ip": "",
            "exit_ip_differs": False,
            "full_tunnel": full,
            "tun_ip": tun,
            "routes": routes[:12],
            "dns": dns[:6],
            "dns_internal": dns_internal,
            "path": "none",
            "internal": None,
            "public": None,
            "tun_tx": 0,
            "tun_rx": 0,
            "tunnel_active": False,
            "route_default": "",
        }
    clean = proxy.replace("socks5h://", "").replace("socks5://", "")
    if url:
        only = (
            _curl_in_ns(int(ns_pid), url, timeout) if use_ns
            else _curl_through_proxy(clean, url, timeout)
        )
        return {
            "ok": bool(only.get("ok")),
            "verdict": "vpn" if only.get("ok") else "proxy_only",
            "proxy": proxy,
            "proxy_ip": "",
            "direct_ip": "",
            "exit_ip_differs": False,
            "full_tunnel": full,
            "tun_ip": tun,
            "routes": routes[:12],
            "dns": dns[:6],
            "dns_internal": dns_internal,
            "path": "netns" if use_ns else "proxy",
            "internal": only,
            "public": None,
            "url": url,
            "tun_tx": 0,
            "tun_rx": 0,
            "tunnel_active": bool(only.get("ok")),
            "route_default": "",
        }

    direct_ip, _ = _ip_via("", timeout=min(timeout, 12))
    tun_tx = tun_rx = 0
    tunnel_active = False
    route_default = ""
    if use_ns:
        before = _tun_counters(int(ns_pid))
        public = _curl_in_ns(int(ns_pid), TEST_PUBLIC_URL, timeout)
        after = _tun_counters(int(ns_pid))
        tun_tx = max(0, after["tx"] - before["tx"])
        tun_rx = max(0, after["rx"] - before["rx"])
        # Bytes no tun0 durante o GET = o tráfego realmente passou pelo túnel.
        # Keepalives do OpenVPN são ~100 B a cada 10 s; o GET rende KBs.
        tunnel_active = bool(public.get("ok") and (tun_tx + tun_rx) >= 2048)
        try:
            route_proc = _ns(["ip", "route", "get", "1.1.1.1"], int(ns_pid), timeout=6)
            route_default = " ".join((route_proc.stdout or "").split())
        except Exception:  # noqa: BLE001
            route_default = ""
        proxy_ip, ip_source = _ip_via_ns(int(ns_pid), timeout=min(timeout, 12))
        internal = _curl_in_ns(int(ns_pid), TEST_INTERNAL_URL, timeout)
        diag_internal = _ns_diag(int(ns_pid), "sistemas.ufv.br")
        diag_public = _ns_diag(int(ns_pid), "www.ufv.br")
        path = "netns"
    else:
        # modo direto: o host já está roteado pela VPN (split ou total)
        proxy_ip, ip_source = _ip_via("", timeout=min(timeout, 12))
        internal = _curl_raw("", TEST_INTERNAL_URL, timeout)
        public = _curl_raw("", TEST_PUBLIC_URL, timeout)
        diag_internal = {"host": "sistemas.ufv.br", "ip": "", "route": ""}
        diag_public = {"host": "www.ufv.br", "ip": "", "route": ""}
        path = "direct"

    differs = bool(proxy_ip and direct_ip and proxy_ip != direct_ip)
    if differs or internal.get("ok") or tunnel_active:
        verdict = "vpn"
    elif proxy_ip or public.get("ok"):
        verdict = "proxy_only"
    else:
        verdict = "no_proxy"

    return {
        "ok": bool(
            proxy_ip or internal.get("ok") or public.get("ok") or tunnel_active
        ),
        "verdict": verdict,
        "proxy": proxy,
        "proxy_ip": proxy_ip,
        "direct_ip": direct_ip,
        "exit_ip_differs": differs,
        "ip_source": ip_source,
        "full_tunnel": full,
        "tun_ip": tun,
        "routes": routes[:12],
        "dns": dns[:6],
        "dns_internal": dns_internal,
        "tun_tx": tun_tx,
        "tun_rx": tun_rx,
        "tunnel_active": tunnel_active,
        "route_default": route_default,
        "path": path,
        "internal": internal,
        "public": public,
        "diag_internal": diag_internal,
        "diag_public": diag_public,
    }


# ═══════════════════════════════════════════════════════════════
# CLI (offline / diagnóstico)
# ═══════════════════════════════════════════════════════════════

def _main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="ufvai-vpn", description="VPN da UFV no UFVAI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="mostra o estado")
    sub.add_parser("disconnect", help="desconecta")
    sub.add_parser("forget", help="apaga as credenciais salvas")
    p_conn = sub.add_parser("connect", help="conecta")
    p_conn.add_argument("--cpf", default="")
    p_conn.add_argument("--password", default="")
    p_conn.add_argument("--remember", action="store_true")
    p_conn.add_argument("--saved", action="store_true")
    p_prof = sub.add_parser("profile", help="baixa/valida o perfil")
    p_prof.add_argument("--force", action="store_true")
    p_test = sub.add_parser("test", help="testa o acesso pelo proxy")
    p_test.add_argument("--url", default=TEST_INTERNAL_URL)

    p_socks = sub.add_parser("socks", help=argparse.SUPPRESS)
    p_socks.add_argument("--bind", default=f"0.0.0.0:{SOCKS_GUEST_PORT}")
    p_socks.add_argument("--dns", default="")

    p_fwd = sub.add_parser("forward", help="encaminha uma porta da rede da UFV")
    p_fwd.add_argument("--host", required=True)
    p_fwd.add_argument("--port", type=int, required=True)
    p_fwd.add_argument("--local", type=int, default=0)
    p_unfwd = sub.add_parser("unforward", help="remove um encaminhamento")
    p_unfwd.add_argument("--id", required=True)
    sub.add_parser("forwards", help="lista os encaminhamentos ativos")

    p_fs = sub.add_parser("forward-server", help=argparse.SUPPRESS)
    p_fs.add_argument("--bind", default="0.0.0.0:0")
    p_fs.add_argument("--target", required=True)
    p_fs.add_argument("--dns", default="")

    args = parser.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "disconnect":
        print(json.dumps(disconnect(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "forget":
        print("ok" if forget_credentials() else "falhou")
        return 0
    if args.cmd == "profile":
        try:
            print(json.dumps(fetch_profile(force=args.force), ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    if args.cmd == "test":
        print(json.dumps(
            _curl_through_proxy(
                _STATE.get("proxy", "").replace("socks5h://", ""), args.url
            ),
            ensure_ascii=False, indent=2,
        ))
        return 0
    if args.cmd == "connect":
        try:
            print(json.dumps(
                connect(args.cpf, args.password, args.remember, args.saved),
                ensure_ascii=False, indent=2,
            ))
        except VPNError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
        # aguarda até 90 s e imprime o estado final
        for _ in range(180):
            time.sleep(0.5)
            st = status()
            if st["state"] != "connecting":
                print(json.dumps(st, ensure_ascii=False, indent=2))
                return 0 if st["state"] == "connected" else 1
        return 2
    if args.cmd == "socks":
        host, _, port = args.bind.rpartition(":")
        dns = [d for d in (args.dns or "").split(",") if d]
        run_socks_server(host or "0.0.0.0", int(port), dns)
        return 0
    if args.cmd == "forward":
        try:
            print(json.dumps(
                add_forward(args.host, args.port, args.local),
                ensure_ascii=False, indent=2,
            ))
            return 0
        except VPNError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    if args.cmd == "unforward":
        print("ok" if remove_forward(args.id) else "não encontrado")
        return 0
    if args.cmd == "forwards":
        print(json.dumps(status().get("forwards", []), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "forward-server":
        target_host, _, target_port = args.target.rpartition(":")
        bind_host, _, bind_port = args.bind.rpartition(":")
        dns = [d for d in (args.dns or "").split(",") if d]
        run_forward_server(
            bind_host or "0.0.0.0", int(bind_port),
            target_host, int(target_port), dns,
        )
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    # Compatibilidade: o servidor SOCKS é iniciado como
    # ``python -m pesquisai.vpn --socks-server ...``
    argv = sys.argv[1:]
    if argv and argv[0] == "--socks-server":
        argv = ["socks"] + argv[1:]
    if argv and argv[0] == "--forward-server":
        argv = ["forward-server"] + argv[1:]
    raise SystemExit(_main(argv))
