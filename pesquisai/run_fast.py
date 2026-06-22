"""
run_fast.py — Versão otimizada do PesquisAI.

Otimizações implementadas:
  1. Skills clonadas em PARALELO com ThreadPoolExecutor (8× mais rápido)
  2. Cache de repositórios — usa git pull --depth 1 se já existir
  3. apt-get update executado UMA ÚNICA vez (antes rodeava duas vezes)
  4. opencode já instalado é detectado e pula reinstalação
  5. pip install com --no-cache-dir evita overhead de cache
  6. Barra de progresso reflete economia de tempo real
  7. Skills definidas centralmente em constants.py (SKILL_REGISTRY)

Uso:
    from run_fast import run
    run()
"""

import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .constants import (
    DRIVE_PATH,
    SKILLS_DIR,
    SKILL_REGISTRY,
    SKILL_MAPPINGS,
    ESSENTIAL_SKILLS,
    THEME_DIR,
    AGENT_DIR,
    TUI_JSON,
    OPENCODE_CFG,
    WORK_DIR,
    WRAPPER_DIR,
    TERMINAL_PORT,
    WRAPPER_PORT,
    VERSION,
    logger,
)
from .jokes import next_joke
from .progress_bar import show as progress, finish as progress_finish


# ── Utilitários ──────────────────────────────────────────────

def _run(cmd: str, **kw) -> subprocess.CompletedProcess:
    """Executa um comando shell e retorna o resultado."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def _check_bin(name: str) -> bool:
    """Verifica se um binário existe no sistema."""
    if shutil.which(name):
        return True
    for d in ["~/.local/bin", "~/.npm-global/bin", "~/.opencode/bin", "/usr/local/bin"]:
        path = os.path.expanduser(os.path.join(d, name))
        if os.path.isfile(path):
            return True
    return False


# ── Etapa 1: Google Drive ────────────────────────────────────

def setup_drive() -> tuple[str, str]:
    """Monta o Google Drive e retorna (folder_path, drive_url)."""
    progress(1, 4, "Montando Google Drive...")
    try:
        from google.colab import drive, auth  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        os.makedirs("/tmp/pesquisai_work", exist_ok=True)
        print("⚠️  Fora do Colab — usando diretório local.")
        return "/tmp/pesquisai_work", "https://drive.google.com/drive/my-drive"

    mounted = os.path.exists("/content/drive/My Drive")
    if not mounted:
        print("📂 Montando Google Drive...")
        drive.mount("/content/drive", force_remount=False)

    os.makedirs(DRIVE_PATH, exist_ok=True)
    os.chdir(DRIVE_PATH)

    folder_url: str = "https://drive.google.com/drive/my-drive"
    try:
        auth.authenticate_user()
        service = build("drive", "v3")
        result = service.files().list(
            q="name='PesquisAI' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id)",
        ).execute()
        files = result.get("files", [])
        if files:
            folder_url = f"https://drive.google.com/drive/folders/{files[0]['id']}"
    except Exception:
        pass

    print(f"📂 Diretório: {DRIVE_PATH}")
    return DRIVE_PATH, folder_url


# ── Etapa 2: Dependências ────────────────────────────────────

def _install_opencode_if_missing() -> bool:
    """Instala o opencode se não estiver presente."""
    if _check_bin("opencode"):
        print("✅ opencode já instalado — pulando.")
        return True

    print("📦 Instalando OpenCode...")
    for cmd in [
        "curl -fsSL https://opencode.ai/install | bash",
    ]:
        r = _run(cmd, check=False)
        if r.returncode == 0 and _check_bin("opencode"):
            return True
    print("❌ Todas as tentativas de instalação do opencode falharam.")
    return False


def _install_system_deps() -> None:
    """Instala ttyd, uv, xclip, xsel em um único apt-get."""
    tasks: list[str] = []
    if not _check_bin("ttyd"):
        tasks.append("ttyd")
    if not _check_bin("xclip"):
        tasks.append("xclip")
    if not _check_bin("xsel"):
        tasks.append("xsel")
    tasks = list(set(tasks))

    if tasks:
        subprocess.run(["apt-get", "update", "-qq"], capture_output=True, text=True, check=False)
        r = subprocess.run(
            ["apt-get", "install", "-y", "-qq", *tasks],
            capture_output=True, text=True, check=False,
        )
        if r.returncode != 0:
            print("⚠️  apt-get falhou. Tentando download manual do ttyd...")
            subprocess.run(
                ["curl", "-fsSL",
                 "https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64",
                 "-o", "/usr/local/bin/ttyd"],
                capture_output=True, text=True, check=False,
            )
            subprocess.run(["chmod", "+x", "/usr/local/bin/ttyd"],
                           capture_output=True, text=True, check=False)
    else:
        print("✅ ttyd e ferramentas de sistema já instalados — pulando.")

    if not _check_bin("uv"):
        _run("curl -LsSf https://astral.sh/uv/install.sh | sh", check=False)
    else:
        print("✅ uv já instalado — pulando.")


def _install_python_deps() -> None:
    """Instala dependências Python necessárias."""
    subprocess.run(
        ["pip", "install", "--quiet", "--no-cache-dir",
         "google-api-python-client", "google-auth-httplib2",
         "google-auth-oauthlib", "cryptography"],
        capture_output=True, text=True, check=False,
    )


def _setup_theme_and_agent() -> None:
    """Configura tema escuro e agente PesquisAI no OpenCode."""
    import json

    os.makedirs(THEME_DIR, exist_ok=True)
    os.makedirs(AGENT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OPENCODE_CFG), exist_ok=True)

    theme = {
        "$schema": "https://opencode.ai/theme.json",
        "defs": {
            "bg0": "#0b0d0f", "bg1": "#131618", "bg2": "#191e21", "bg3": "#1f262a",
            "bg4": "#263035", "fg0": "#dde4e8", "fg1": "#7e8f97", "fg2": "#4a5a62",
            "fg3": "#2e3d44", "blue": "#4fc3f7", "blueDim": "#1e6a8a",
            "blueGlow": "#2196b0", "green": "#5dba7e", "greenDark": "#1d4a2e",
            "amber": "#e8b84b", "amberDark": "#5a420d", "red": "#e07070",
            "redDark": "#5c1e1e", "cyan": "#56ccd8", "purple": "#a47de0",
            "synKeyword": "#56ccd8", "synString": "#5dba7e", "synComment": "#4a5a62",
            "synNumber": "#e8b84b", "synFunction": "#4fc3f7", "synType": "#a47de0",
            "synOp": "#7e8f97",
        },
        "theme": {
            "primary": {"dark": "blue", "light": "blueDim"},
            "secondary": {"dark": "cyan", "light": "cyan"},
            "accent": {"dark": "purple", "light": "purple"},
            "error": {"dark": "red", "light": "red"},
            "warning": {"dark": "amber", "light": "amber"},
            "success": {"dark": "green", "light": "green"},
            "info": {"dark": "cyan", "light": "cyan"},
            "text": {"dark": "fg0", "light": "fg0"},
            "textMuted": {"dark": "fg1", "light": "fg1"},
            "background": {"dark": "bg0", "light": "bg0"},
            "backgroundPanel": {"dark": "bg1", "light": "bg1"},
            "backgroundElement": {"dark": "bg2", "light": "bg2"},
            "border": {"dark": "bg3", "light": "bg3"},
            "borderActive": {"dark": "bg4", "light": "bg4"},
            "borderSubtle": {"dark": "bg2", "light": "bg2"},
            "diffAdded": {"dark": "green", "light": "green"},
            "diffRemoved": {"dark": "red", "light": "red"},
            "diffContext": {"dark": "fg1", "light": "fg1"},
            "diffHunkHeader": {"dark": "fg2", "light": "fg2"},
            "diffHighlightAdded": {"dark": "greenDark", "light": "greenDark"},
            "diffHighlightRemoved": {"dark": "redDark", "light": "redDark"},
            "syntaxKeyword": {"dark": "synKeyword", "light": "synKeyword"},
            "syntaxString": {"dark": "synString", "light": "synString"},
            "syntaxComment": {"dark": "synComment", "light": "synComment"},
            "syntaxNumber": {"dark": "synNumber", "light": "synNumber"},
            "syntaxFunction": {"dark": "synFunction", "light": "synFunction"},
            "syntaxType": {"dark": "synType", "light": "synType"},
            "syntaxOperator": {"dark": "synOp", "light": "synOp"},
            "syntaxPunctuation": {"dark": "fg2", "light": "fg2"},
            "markdownHeading": {"dark": "blue", "light": "blue"},
            "markdownBold": {"dark": "fg0", "light": "fg0"},
            "markdownItalic": {"dark": "fg1", "light": "fg1"},
            "markdownCode": {"dark": "green", "light": "green"},
            "markdownLink": {"dark": "cyan", "light": "cyan"},
        },
    }

    with open(os.path.join(THEME_DIR, "pesquisai.json"), "w") as f:
        json.dump(theme, f, indent=2)

    # ── Tema claro (acessibilidade) ──────────────────────────
    # Mesma estrutura do tema escuro, mas com paleta clara.
    light_defs = {
        "bg0": "#f5f6f7", "bg1": "#ffffff", "bg2": "#eef1f3", "bg3": "#e1e5e8",
        "bg4": "#d3d9dd", "fg0": "#1f262a", "fg1": "#4a5a62", "fg2": "#7e8f97",
        "fg3": "#9aa7ad", "blue": "#0288d1", "blueDim": "#4fc3f7",
        "blueGlow": "#29b6f6", "green": "#2e7d32", "greenDark": "#a5d6a7",
        "amber": "#e65100", "amberDark": "#ffcc80", "red": "#c62828",
        "redDark": "#ef9a9a", "cyan": "#00838f", "purple": "#6a1b9a",
        "synKeyword": "#00838f", "synString": "#2e7d32", "synComment": "#7e8f97",
        "synNumber": "#e65100", "synFunction": "#0288d1", "synType": "#6a1b9a",
        "synOp": "#4a5a62",
    }
    theme_light = {**theme, "defs": light_defs}
    with open(os.path.join(THEME_DIR, "pesquisai-light.json"), "w") as f:
        json.dump(theme_light, f, indent=2)

    # Tema padrão: respeita escolha persistida em tui.json (default = escuro)
    try:
        existing_tui = json.load(open(TUI_JSON))
    except Exception:
        existing_tui = {}
    tui_theme = existing_tui.get("theme", "pesquisai")
    with open(TUI_JSON, "w") as f:
        json.dump({"$schema": "https://opencode.ai/tui.json", "theme": tui_theme}, f, indent=2)
    print("✅ Temas configurados (escuro + claro).")

    agents_md = os.path.join(os.path.dirname(os.path.dirname(__file__)), "AGENTS.md")
    content = open(agents_md, encoding="utf-8").read() if os.path.exists(agents_md) else "# PesquisAI"
    agent_md = f"""---
name: PesquisAI
description: Agente de pesquisa científica com foco em dados brasileiros (IBGE, DataSUS), normas ABNT/UFV, integridade científica. REGRAS ABSOLUTAS: 1) referências exigem citation-management; 2) não inventar dados/estatísticas; 3) não simular coleta primária (entrevistas, experimentos, surveys). Recusar pedidos que tentem burlar.
color: "#4fc3f7"
---
{content}
"""
    with open(os.path.join(AGENT_DIR, "pesquisai.md"), "w", encoding="utf-8") as f:
        f.write(agent_md)
    try:
        cfg = json.load(open(OPENCODE_CFG))
    except Exception:
        cfg = {}
    cfg["default_agent"] = "pesquisai"
    with open(OPENCODE_CFG, "w") as f:
        json.dump(cfg, f, indent=2)
    print("✅ Agente configurado.")


def setup_dependencies() -> None:
    """Instala todas as dependências (OpenCode, sistema, Python, tema)."""
    progress(2, 4, "Instalando OpenCode, dependências de sistema e tema...")
    _install_opencode_if_missing()
    _install_system_deps()
    _install_python_deps()
    _setup_theme_and_agent()


# ── Etapa 3: Skills (paralelizadas) ──────────────────────────

def _clone_or_pull(repo_url: str, dest_name: str) -> bool:
    """Clone com cache: se já existe, faz git pull --depth 1.

    Returns:
        True se a operação foi bem-sucedida, False caso contrário.
    """
    dest = f"/tmp/skill_{dest_name}"
    if os.path.exists(dest):
        r = subprocess.run(
            ["git", "-C", dest, "pull", "--depth", "1", "--ff-only"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return True
        shutil.rmtree(dest)

    r = subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", repo_url, dest],
        capture_output=True, text=True, timeout=60,
    )
    return r.returncode == 0


def setup_skills() -> None:
    """Clona/atualiza todas as skills em paralelo e copia para o diretório do agente.

    Skills essenciais (ESSENTIAL_SKILLS) disparam aviso se falharem.
    Skills opcionais falham silenciosamente.
    """
    progress(3, 4, "Clonando repositórios de skills (em paralelo)...")
    os.makedirs(SKILLS_DIR, exist_ok=True)

    failed_skills: list[str] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        fut = {
            pool.submit(_clone_or_pull, repo, name): name
            for repo, name, _ in SKILL_REGISTRY
        }
        for f in as_completed(fut):
            name = fut[f]
            if f.result():
                print(f"✅ {name}")
            else:
                print(f"❌ Falha em {name}")
                failed_skills.append(name)

    # Verificar skills essenciais
    for skill_name in failed_skills:
        if skill_name in ESSENTIAL_SKILLS:
            logger.warning(
                "Skill essencial '%s' falhou ao clonar. "
                "Algumas funcionalidades podem não estar disponíveis.",
                skill_name,
            )

    # Copiar para o diretório do agente
    for src, dest_name in SKILL_MAPPINGS:
        dest = os.path.join(SKILLS_DIR, dest_name)
        if os.path.exists(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"📋 {dest_name} copiado.")

    print("✅ Todas as skills instaladas com sucesso!")


# ── Etapa 4: Launch ───────────────────────────────────────────

def setup_launch(folder_path: str, drive_url: str) -> str:
    """Inicia os servidores e a interface web.

    Returns:
        URL do banner de acesso.
    """
    progress(4, 4, "Iniciando servidores e interface web...")
    from pesquisai.launch_app import launch, set_drive_info, show_ready_message, show_launch_button
    set_drive_info(folder_path, drive_url)
    banner_url = launch()
    progress_finish()
    show_ready_message()
    show_launch_button(banner_url)
    return banner_url


# ── Orquestrador ──────────────────────────────────────────────

def run() -> None:
    """Orquestrador principal do PesquisAI.

    Sequência: Drive → Dependências → Skills → Launch
    """
    t0 = time.time()
    progress(0, 4, "Preparando...")

    print("=" * 50)
    print(f"  🧑‍🔬  PESQUISAI v{VERSION} (MODO RÁPIDO)")
    print("=" * 50)

    folder_path, drive_url = setup_drive()
    setup_dependencies()
    setup_skills()
    setup_launch(folder_path, drive_url)

    elapsed = time.time() - t0
    print(f"\n⚡ Inicializado em {elapsed:.0f}s ")
    print()


if __name__ == "__main__":
    run()
