"""
opencode_utils.py — Utilitários para localizar e configurar o binário OpenCode.

Fornece funções para encontrar o executável opencode no sistema,
garantir que ele está no PATH, e construir o environment para execução.

v0.6.20 · OpenCode V2: ganha detecção de versão (`opencode_major`,
`is_opencode_v2`) para o boot decidir instalar/atualizar o motor 2.x.

OpenCode V2 (não lançado): a busca PREFERE o binário 2.x. Antes, o primeiro
`opencode` do PATH vencia, e um V1 instalado antes (ex.: via npm) fazia o
boot tentar atualizar a cada inicialização. Agora a ordem testa todos os
candidatos e escolhe o primeiro 2.x; sem 2.x, usa o primeiro encontrado.
"""

import os
import re
import shutil
import subprocess
from typing import Optional

from .constants import OPENCODE_MIN_MAJOR, logger

OPENCODE_BIN: Optional[str] = None

CANDIDATES: list[str] = [
    os.path.expanduser("~/.local/bin/opencode"),
    os.path.expanduser("~/bin/opencode"),
    # Instalador oficial (V2 substitui o binário no mesmo path)
    os.path.expanduser("~/.opencode/bin/opencode"),
    "/root/.local/bin/opencode",
    "/root/.opencode/bin/opencode",
    "/root/bin/opencode",
    "/usr/local/bin/opencode",
    "/usr/bin/opencode",
]


def _search() -> Optional[str]:
    """Busca recursivamente o binário opencode no sistema (último recurso)."""
    result = subprocess.run(
        ["find", "/root", "/home", "/usr/local", "-name", "opencode", "-type", "f"],
        capture_output=True, text=True, timeout=10,
    )
    hits = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return hits[0] if hits else None


def _which_all() -> list[str]:
    """Todos os `opencode` do PATH, na ordem em que aparecem."""
    found: list[str] = []
    try:
        result = subprocess.run(
            ["which", "-a", "opencode"], capture_output=True, text=True, timeout=5,
        )
        found = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001 — `which -a` ausente não é fatal
        found = []
    if not found:
        w = shutil.which("opencode")
        if w:
            found = [w]
    return found


def _candidate_paths() -> list[str]:
    """Caminhos existentes, sem duplicatas, em ordem de preferência."""
    raw: list[str] = []
    env_bin = os.environ.get("OPENCODE_BIN")
    if env_bin:
        raw.append(env_bin)
    raw.append(os.path.expanduser("~/.opencode/bin/opencode"))  # instalador V2
    raw.extend(_which_all())
    raw.extend(CANDIDATES)

    seen: set[str] = set()
    ordered: list[str] = []
    for path in raw:
        if not path or not os.path.isfile(path):
            continue
        key = os.path.realpath(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def reset_opencode_cache() -> None:
    """Limpa o cache do binário (use após instalar/atualizar o opencode)."""
    global OPENCODE_BIN
    OPENCODE_BIN = None


def find_opencode() -> str:
    """Localiza o binário do opencode, preferindo o motor 2.x.

    Ordem de busca:
    1. Cache global OPENCODE_BIN (somente se ainda existir)
    2. Variável de ambiente OPENCODE_BIN
    3. Instalador V2 (~/.opencode/bin), `which -a` e candidatos conhecidos —
       o primeiro com versão MAJOR >= OPENCODE_MIN_MAJOR vence
    4. Sem 2.x: primeiro candidato encontrado (o boot tenta atualizar)
    5. Busca recursiva com find (último recurso)

    Raises:
        FileNotFoundError: se o binário não for encontrado em lugar nenhum.
    """
    global OPENCODE_BIN
    if OPENCODE_BIN and os.path.isfile(OPENCODE_BIN):
        return OPENCODE_BIN

    candidates = _candidate_paths()
    if not candidates:
        found = _search()
        if found:
            candidates = [found]
    if not candidates:
        raise FileNotFoundError(
            "opencode binary not found. Install it from https://opencode.ai"
        )

    for path in candidates:
        major = opencode_major(path)
        if major is not None and major >= OPENCODE_MIN_MAJOR:
            OPENCODE_BIN = path
            return path

    # Nenhum 2.x: segue com o primeiro (o boot tenta instalar/atualizar).
    OPENCODE_BIN = candidates[0]
    return candidates[0]


def ensure_opencode_in_path() -> None:
    """Garante que o diretório do opencode está no PATH (na frente)."""
    bin_path = find_opencode()
    bin_dir = os.path.dirname(bin_path)
    current = os.environ.get("PATH", "")
    if bin_dir not in current.split(":"):
        os.environ["PATH"] = bin_dir + ":" + current
    os.environ["OPENCODE_BIN"] = bin_path
    logger.info("opencode encontrado: %s", bin_path)


def build_env(extra_vars: Optional[dict] = None) -> dict:
    """Constrói o dicionário de environment para executar o opencode.

    Args:
        extra_vars: Variáveis adicionais para injetar no environment.

    Returns:
        Dict com todas as variáveis de ambiente necessárias.
    """
    env: dict = {**os.environ}
    env["OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT"] = "1"
    bin_path = find_opencode()
    bin_dir = (
        os.path.dirname(bin_path)
        if os.path.isfile(bin_path)
        else os.path.expanduser("~/.local/bin")
    )
    # OpenCode V2 (mudança não lançada): o diretório do binário escolhido vai
    # NA FRENTE do PATH, para que nenhum opencode antigo seja resolvido primeiro.
    current = env.get("PATH", "")
    if bin_dir not in current.split(":"):
        env["PATH"] = bin_dir + ":" + current
    if extra_vars:
        env.update(extra_vars)
    return env


# ── v0.6.20 · detecção de versão (OpenCode V2) ─────────────────

def opencode_version_string(bin_path: Optional[str] = None) -> Optional[str]:
    """Retorna a primeira linha de `opencode --version` (ou None).

    Formatos observados: ``1.18.34`` (V1) e ``opencode v2.0.28`` (V2).

    Returns:
        String bruta da versão, ou None se o binário não responder.
    """
    try:
        target = bin_path or find_opencode()
        r = subprocess.run(
            [target, "--version"],
            capture_output=True, text=True, timeout=20,
            stdin=subprocess.DEVNULL,
        )
        out = (r.stdout or "").strip() or (r.stderr or "").strip()
        return out.splitlines()[0].strip() if out else None
    except Exception as exc:  # noqa: BLE001 — versão é diagnóstico, nunca fatal
        logger.debug("Não foi possível ler a versão do opencode: %s", exc)
        return None


def opencode_major(bin_path: Optional[str] = None) -> Optional[int]:
    """Retorna o número da versão MAJOR do opencode (1, 2, …) ou None."""
    raw = opencode_version_string(bin_path)
    if not raw:
        return None
    m = re.search(r"\bv?(\d+)\.\d+", raw)
    if m:
        return int(m.group(1))
    m = re.match(r"v?(\d+)", raw)
    return int(m.group(1)) if m else None


def is_opencode_v2(bin_path: Optional[str] = None) -> bool:
    """True se o binário detectado for OpenCode 2.x ou superior."""
    major = opencode_major(bin_path)
    return major is not None and major >= OPENCODE_MIN_MAJOR


# ── v0.7.8 · chaves do Drive no ambiente do SERVIÇO ─────────────
#
# O serviço de background (`opencode serve --service`) resolve catálogo de
# provedores e credenciais NO PRÓPRIO PROCESSO, a partir do ambiente com que
# nasceu. No OpenCode v2.2 a TUI/CLI apenas consulta esse serviço — logo, se
# ele nascer sem as variáveis de chave, nenhum provedor além do nativo
# (`opencode`/`opencode-go`) aparece, mesmo com as chaves certas no Drive.
#
# As funções abaixo só LEEM nomes de variáveis e valores já decifrados em
# memória; nunca gravam, nunca logam segredo.

def keys_env_from_store(backup_dir: str) -> dict[str, str]:
    """Traduz o ``keys_store.json`` (cifrado) em ``{VAR_DE_AMBIENTE: valor}``.

    Args:
        backup_dir: pasta ``backups/`` do PesquisAI (Drive ou ``~/PesquisAI``).

    Returns:
        Dicionário de variáveis prontas para o ambiente do serviço. Vazio se
        o armazenamento não existir, estiver ilegível ou não tiver metadados
        ``_env_<provedor>`` (nunca inventa nome de variável).
    """
    try:
        from .security import load_encrypted_keys
    except Exception:  # noqa: BLE001 — sem módulo de segurança não há chaves
        return {}
    try:
        store = load_encrypted_keys(backup_dir)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(store, dict):
        return {}

    env: dict[str, str] = {}
    for name, value in store.items():
        if name.startswith("_env_") or not isinstance(value, str) or not value:
            continue
        var = store.get(f"_env_{name}") or ""
        if isinstance(var, str) and var.strip():
            env[var.strip()] = value
    return env


def service_pids() -> list[str]:
    """PIDs dos processos ``opencode serve --service`` em execução."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", "opencode serve --service"],
            capture_output=True, text=True, timeout=3,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [p for p in (out.stdout or "").split() if p.isdigit()]


def service_env(pid: str) -> dict[str, str]:
    """Ambiente de um processo lido de ``/proc/<pid>/environ``.

    Returns:
        Dicionário de variáveis; vazio se o ``/proc`` não estiver acessível.
    """
    try:
        with open(f"/proc/{pid}/environ", "rb") as fh:
            raw = fh.read()
    except (OSError, ValueError):
        return {}
    env: dict[str, str] = {}
    for chunk in raw.split(b"\0"):
        if b"=" in chunk:
            key, _, value = chunk.partition(b"=")
            env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return env


def service_missing_key_envs(backup_dir: str) -> list[str]:
    """Variáveis de chave do Drive que FALTAM no serviço em execução.

    Serve de gatilho de auto-cura: se o serviço já está no diretório certo mas
    nasceu sem as chaves (caso do boot anterior à v0.7.8), ele precisa ser
    reiniciado — senão a TUI conversa com um motor sem credenciais.

    Returns:
        Lista de NOMES de variáveis ausentes. Vazia quando não há serviço em
        execução (nada a corrigir) ou quando ele já tem todas as chaves.
    """
    expected = keys_env_from_store(backup_dir)
    if not expected:
        return []
    pids = service_pids()
    if not pids:
        return []
    have: set[str] = set()
    for pid in pids:
        have |= set(service_env(pid))
    return sorted(var for var in expected if var not in have)
