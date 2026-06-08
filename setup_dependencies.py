import os
import json
import subprocess
import shutil

from constants import THEME_DIR, AGENT_DIR, TUI_JSON, OPENCODE_CFG, logger
from opencode_utils import find_opencode, ensure_opencode_in_path
from jokes import next_joke


def run(cmd, check=True, **kw):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result


def install_opencode():
    print(next_joke("fisica"))
    print("📦 Instalando OpenCode...")

    r1 = run("curl -fsSL https://opencode.ai/install | bash", check=False)
    if r1.returncode != 0:
        print("⚠️  Script oficial falhou. Tentando pip install opencode...")
        r2 = run("pip install opencode", check=False)
        if r2.returncode != 0:
            print("⚠️  pip falhou. Tentando npm install -g @opencode/cli...")
            r3 = run("npm install -g @opencode/cli", check=False)
            if r3.returncode != 0:
                print("❌ Todas as tentativas de instalação do opencode falharam.")
                return

    print(next_joke("fisica"))
    print("📦 Instalando uv...")
    run("curl -LsSf https://astral.sh/uv/install.sh | sh", check=False)

    print(next_joke("fisica"))
    print("📦 Instalando ferramentas de clipboard...")
    run("apt-get update -qq && apt-get install -y -qq xclip xsel", check=False)

    print(next_joke("fisica"))
    print("📦 Instalando dependências Python...")
    run("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib --quiet", check=False)

    try:
        ensure_opencode_in_path()
        print(next_joke("fisica"))
        print("✅ OpenCode instalado.")
    except FileNotFoundError as e:
        logger.error("opencode não encontrado após instalação: %s", e)


def create_directories():
    for d in [THEME_DIR, AGENT_DIR]:
        os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.dirname(OPENCODE_CFG), exist_ok=True)


def setup_theme():
    pesquisai_theme = {
        "$schema": "https://opencode.ai/theme.json",
        "defs": {
            "bg0": "#0b0d0f",
            "bg1": "#131618",
            "bg2": "#191e21",
            "bg3": "#1f262a",
            "bg4": "#263035",
            "fg0": "#dde4e8",
            "fg1": "#7e8f97",
            "fg2": "#4a5a62",
            "fg3": "#2e3d44",
            "blue": "#4fc3f7",
            "blueDim": "#1e6a8a",
            "blueGlow": "#2196b0",
            "green": "#5dba7e",
            "greenDark": "#1d4a2e",
            "amber": "#e8b84b",
            "amberDark": "#5a420d",
            "red": "#e07070",
            "redDark": "#5c1e1e",
            "cyan": "#56ccd8",
            "purple": "#a47de0",
            "synKeyword": "#56ccd8",
            "synString": "#5dba7e",
            "synComment": "#4a5a62",
            "synNumber": "#e8b84b",
            "synFunction": "#4fc3f7",
            "synType": "#a47de0",
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
        }
    }

    theme_path = os.path.join(THEME_DIR, "pesquisai.json")
    with open(theme_path, "w") as f:
        json.dump(pesquisai_theme, f, indent=2)

    tui = {"$schema": "https://opencode.ai/tui.json", "theme": "pesquisai"}
    with open(TUI_JSON, "w") as f:
        json.dump(tui, f, indent=2)

    print("✅ Tema configurado:", theme_path)


def setup_agent():
    agents_md_path = os.path.join(os.path.dirname(__file__), "AGENTS.md")
    if os.path.exists(agents_md_path):
        with open(agents_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        logger.warning("AGENTS.md não encontrado em %s", agents_md_path)
        content = "# PesquisAI\nAgente configurado manualmente."

    agent_md = f"""---
name: PesquisAI
description: Agente de pesquisa científica com foco em dados brasileiros (IBGE, DataSUS), normas ABNT/UFV e integridade científica.
color: "#4fc3f7"
---

{content}
"""

    agent_path = os.path.join(AGENT_DIR, "pesquisai.md")
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(agent_md)

    try:
        with open(OPENCODE_CFG) as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    cfg["default_agent"] = "pesquisai"

    with open(OPENCODE_CFG, "w") as f:
        json.dump(cfg, f, indent=2)

    print("✅ Agente configurado:", agent_path)
    print("✅ Config padrão:", OPENCODE_CFG)


def run_all():
    install_opencode()
    create_directories()
    setup_theme()
    setup_agent()
    print(next_joke("fisica"))
    print("\n🎉 Dependências e configurações concluídas!")


if __name__ == "__main__":
    run_all()
