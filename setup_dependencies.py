import os
import json
import subprocess
import shutil

THEME_DIR = os.path.expanduser("~/.config/opencode/themes")
AGENT_DIR = os.path.expanduser("~/.config/opencode/agents")
TUI_JSON = os.path.expanduser("~/.config/opencode/tui.json")
OPENCODE_CFG = os.path.expanduser("~/.config/opencode/config.json")

OPENCODE_BIN = None

JOKES_INSTALL = [
    "⚛️ Relatividade geral: o tempo passa mais devagar quando você olha para o progresso.",
    "⚗️ Catalisador: o café que você tomou deveria acelerar isso.",
    "⚛️ Primeira lei de Newton: download em repouso tende a permanecer em repouso.",
    "⚗️ Se esse progresso fosse um elemento, seria o Gás Nobre: não reage com nada.",
    "⚛️ Schrödinger já desistiu: esse download está e não está terminando.",
    "⚗️ Estado de oxidação da paciência: -1000",
    "⚛️ Entropia: a bagunça do seu progresso só aumenta.",
    "⚗️ Reação: Paciência(lenta) → Paciência + Cansaço",
    "⚛️ Princípio da incerteza: não sabemos quando termina nem se termina.",
    "⚗️ Entalpia desse processo: ΔH = +muito",
]

_joke_index = 0

def next_joke():
    global _joke_index
    if _joke_index < len(JOKES_INSTALL):
        joke = JOKES_INSTALL[_joke_index]
        _joke_index += 1
        return joke
    return JOKES_INSTALL[-1]


def run(cmd, check=True, **kw):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result


def find_opencode_binary():
    global OPENCODE_BIN
    
    _candidates = [
        os.path.expanduser("~/.local/bin/opencode"),
        os.path.expanduser("~/bin/opencode"),
        "/root/.local/bin/opencode",
        "/root/bin/opencode",
        "/usr/local/bin/opencode",
        "/usr/bin/opencode",
    ]
    _found = next((p for p in _candidates if os.path.isfile(p)), None)
    
    if _found is None:
        result = subprocess.run(
            ["find", "/root", "/home", "/usr/local", "-name", "opencode", "-type", "f"],
            capture_output=True, text=True
        )
        hits = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        _found = hits[0] if hits else None
    
    if _found:
        OPENCODE_BIN = _found
        _bin_dir = os.path.dirname(_found)
        if _bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _bin_dir + ":" + os.environ["PATH"]
        os.environ["OPENCODE_BIN"] = _found
        print(f"\n{next_joke()}")
        print(f"✅ opencode encontrado: {_found}")
        try:
            subprocess.run([_found, "--version"])
        except:
            pass
    else:
        print("\n❌ opencode NÃO encontrado.")
    
    return _found


def install_opencode():
    print("📦 Instalando OpenCode...")
    print(f"\n{next_joke()}")
    run("curl -fsSL https://opencode.ai/install | bash", check=True)
    
    print(f"\n{next_joke()}")
    print("📦 Instalando uv...")
    run("curl -LsSf https://astral.sh/uv/install.sh | sh", check=False)
    
    print(f"\n{next_joke()}")
    print("📦 Instalando ferramentas de clipboard...")
    run("apt-get update -qq && apt-get install -y -qq xclip xsel", check=False)
    
    print(f"\n{next_joke()}")
    print("📦 Instalando dependências Python...")
    run("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib --quiet", check=False)
    
    find_opencode_binary()
    print(f"\n{next_joke()}")
    print("✅ OpenCode instalado.")


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
    agent_md = """\
---
name: PesquisAI
description: Agente de pesquisa científica com foco em dados brasileiros (IBGE, DataSUS) e revisão bibliográfica.
color: "#4fc3f7"
---

Você é o **PesquisAI**, um assistente de pesquisa científica especializado em:

- Revisão bibliográfica e síntese de literatura acadêmica
- Consulta e análise de dados públicos brasileiros (IBGE, DataSUS, SINAN)
- Formatação de referências e citações no padrão ABNT
- Apoio na redação e estruturação de artigos científicos

## Diretrizes

- Cite as fontes consultadas ao final de cada resposta.
- Para dados quantitativos, informe sempre o ano de referência e a fonte.
- Quando não tiver certeza de uma informação, sinalize explicitamente.
- Não realize coleta primária de dados — opere sobre bases públicas disponíveis pelas skills.
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
    print(f"\n{next_joke()}")
    print("\n🎉 Dependências e configurações concluídas!")


if __name__ == "__main__":
    run_all()
