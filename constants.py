import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pesquisai")

REPO_URL = "https://github.com/gustavobraga-byte/PesquisAI.git"
AUTHOR_NAME = "Gustavo Bastos Braga"
AUTHOR_EMAIL = "gustavo.braga@ufv.br"
INSTITUTION = "Universidade Federal de Viçosa (UFV)"
VERSION = "1.0"

DRIVE_FOLDER = "PesquisAI"
MOUNT_PATH = "/content/drive"
DRIVE_PATH = os.path.join(MOUNT_PATH, "My Drive", DRIVE_FOLDER)
FALLBACK_URL = "https://drive.google.com/drive/my-drive"
WORK_DIR = "/tmp/pesquisai"
WRAPPER_DIR = "/tmp/pesquisai-wrapper"
SKILLS_DIR = os.path.expanduser("~/.agents/skills")
THEME_DIR = os.path.expanduser("~/.config/opencode/themes")
AGENT_DIR = os.path.expanduser("~/.config/opencode/agents")
OPENCODE_CFG = os.path.expanduser("~/.config/opencode/config.json")
TUI_JSON = os.path.expanduser("~/.config/opencode/tui.json")

TERMINAL_PORT = 8000
WRAPPER_PORT = 8001
