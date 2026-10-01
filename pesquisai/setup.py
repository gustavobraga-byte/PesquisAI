"""
setup.py — Setup do PesquisAI v0.6.0 (WEBCLI Mode).

Responsável por:
  1. Montar Google Drive (Colab)
  2. Instalar/configurar opencode CLI
  3. Configurar tema e agente PesquisAI
  4. Clonar skills (paralelo)
  5. Inicializar vault Obsidian (autopilot)

APÓS o setup, o main.py apenas executa `opencode web` que é o
webcli oficial do opencode.
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
    VERSION,
    logger,
    is_colab,
    is_drive_mounted,
)
from .jokes import next_joke
from .progress_bar import show as progress, finish as progress_finish
from .opencode_utils import find_opencode, opencode_installed, install_opencode


# ── Utilitários ──────────────────────────────────────────────

def _run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def _check_bin(name):
    if shutil.which(name):
        return True
    for d in ["~/.local/bin", "~/.npm-global/bin", "~/.opencode/bin", "/usr/local/bin"]:
        path = os.path.expanduser(os.path.join(d, name))
        if os.path.isfile(path):
            return True
    return False


# ── Etapa 1: Google Drive ───────────────────────────────────

def setup_drive() -> tuple[str, str]:
    """Monta o Google Drive (no Colab)."""
    progress(1, 4, "Montando Google Drive...")
    if not is_colab():
        os.makedirs("/tmp/pesquisai_work", exist_ok=True)
        print("⚠️  Fora do Colab — usando diretório local.")
        return "/tmp/pesquisai_work", "https://drive.google.com/drive/my-drive"

    try:
        from google.colab import drive
    except ImportError:
        os.makedirs("/tmp/pesquisai_work", exist_ok=True)
        return "/tmp/pesquisai_work", "https://drive.google.com/drive/my-drive"

    if not is_drive_mounted():
        print("📂 Montando Google Drive...")
        drive.mount("/content/drive", force_remount=False)
    os.makedirs(DRIVE_PATH, exist_ok=True)
    return DRIVE_PATH, "https://drive.google.com/drive/my-drive"


# ── Etapa 2: OpenCode e configuração ────────────────────────

def _install_opencode_if_missing() -> bool:
    if _check_bin("opencode"):
        print("✅ opencode já instalado — pulando.")
        return True
    print("📦 Instalando OpenCode...")
    return install_opencode()


def _setup_theme_and_agent() -> None:
    """Configura tema escuro/claro e agente PesquisAI no opencode."""
    import json

    os.makedirs(THEME_DIR, exist_ok=True)
    os.makedirs(AGENT_DIR, exist_ok=True)  # ~/.config/opencode/agent/ (singular!)
    os.makedirs(os.path.dirname(OPENCODE_CFG), exist_ok=True)

    # ── Tema escuro ─────────────────────────────────────────
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

    # ── Tema claro ──────────────────────────────────────────
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

    try:
        existing_tui = json.load(open(TUI_JSON))
    except Exception:
        existing_tui = {}
    tui_theme = existing_tui.get("theme", "pesquisai")
    with open(TUI_JSON, "w") as f:
        json.dump({"$schema": "https://opencode.ai/tui.json", "theme": tui_theme}, f, indent=2)
    print("✅ Temas configurados (escuro + claro).")

    # ── Agente PesquisAI (em ~/.config/opencode/agent/) ────
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agents_md = os.path.join(project_root, "AGENTS.md")
    if not os.path.exists(agents_md):
        # Tenta a pasta original
        original_agents = os.path.join(project_root, "..", "Pesquisai", "AGENTS.md")
        if os.path.exists(original_agents):
            agents_md = original_agents
    content = open(agents_md, encoding="utf-8").read() if os.path.exists(agents_md) else "# PesquisAI — Agente de pesquisa científica"

    agent_md = f"""---
name: PesquisAI
description: Agente de pesquisa científica com foco em dados brasileiros (IBGE, DataSUS), normas ABNT/UFV, integridade científica. REGRAS ABSOLUTAS: 1) referências exigem citation-management; 2) não inventar dados/estatísticas; 3) não simular coleta primária. v0.6.0: usa opencode web (webcli).
color: "#4fc3f7"
---
{content}
"""
    # ATENÇÃO: opencode procura em ~/.config/opencode/agent/ (singular)
    # Cria tanto em agent/ quanto em agents/ para compatibilidade
    for agent_dir in [
        os.path.expanduser("~/.config/opencode/agent"),  # v0.6.0+
        os.path.expanduser("~/.config/opencode/agents"),  # legacy
    ]:
        os.makedirs(agent_dir, exist_ok=True)
        with open(os.path.join(agent_dir, "pesquisai.md"), "w", encoding="utf-8") as f:
            f.write(agent_md)

    try:
        cfg = json.load(open(OPENCODE_CFG))
    except Exception:
        cfg = {}
    cfg["default_agent"] = "pesquisai"
    with open(OPENCODE_CFG, "w") as f:
        json.dump(cfg, f, indent=2)
    print("✅ Agente 'pesquisai' configurado em ~/.config/opencode/agent/ e agents/")


def setup_dependencies() -> None:
    """Instala/configura opencode e temas."""
    progress(2, 4, "Configurando opencode...")
    _install_opencode_if_missing()
    _setup_theme_and_agent()


# ── Etapa 3: Skills (paralelizadas) ──────────────────────────

def _clone_or_pull(repo_url: str, dest_name: str) -> bool:
    """Clone com cache: se já existe, faz git pull --depth 1."""
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
    """Clona/atualiza todas as skills em paralelo."""
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

    for skill_name in failed_skills:
        if skill_name in ESSENTIAL_SKILLS:
            logger.warning(
                "Skill essencial '%s' falhou ao clonar.",
                skill_name,
            )

    for src, dest_name in SKILL_MAPPINGS:
        dest = os.path.join(SKILLS_DIR, dest_name)
        if os.path.exists(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"📋 {dest_name} copiado.")

    print("✅ Skills instaladas.")


# ── Orquestrador ─────────────────────────────────────────────

def setup() -> tuple[str, str]:
    """Executa todo o setup do PesquisAI.

    Returns:
        (folder_path, drive_url) — para uso diagnóstico
    """
    t0 = time.time()
    progress(0, 4, "Preparando...")

    print("=" * 60)
    print(f"  🧑‍🔬  PESQUISAI v{VERSION} (WEBCLI MODE)")
    print(f"  Substituindo ttyd pelo opencode web")
    print("=" * 60)

    folder_path, drive_url = setup_drive()
    setup_dependencies()
    setup_skills()

    elapsed = time.time() - t0
    print(f"\n⚡ Setup concluído em {elapsed:.0f}s")
    print()

    return folder_path, drive_url


if __name__ == "__main__":
    setup()
