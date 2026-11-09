# ═══════════════════════════════════════════════════════════════════════
# UFVAI 0.7.11-web — BOOT LOCAL (própria pasta: clone do repositório ou Drive)
# ═══════════════════════════════════════════════════════════════════════
# Rode esta célula na MESMA pasta deste arquivo (clone do repositório ou
# `UFVAI-v0.7.11-web/` do Drive). Ela copia **essa pasta** para
# /tmp/pesquisai e inicia o UFVAI com a interface web do OpenCode.
#
# ⚠️ IMPORTANTE: rode depois de um **Runtime → Restart session** (ou
# "Desconectar e excluir ambiente"). Sem reiniciar, o wrapper antigo
# ainda ocupa a porta 8001 e a nova célula não consegue subir.
# ═══════════════════════════════════════════════════════════════════════
import os
import sys
import shutil
import socket
import subprocess

# 1) Drive montado
try:
    from google.colab import drive
    if not os.path.isdir("/content/drive/MyDrive"):
        drive.mount("/content/drive")
except Exception:
    pass

# 2) Descobre a árvore de origem: a pasta DESTE arquivo (funciona mesmo
#    que a pasta seja renomeada) e, sem __file__, a pasta atual se ela
#    contiver o pacote `pesquisai/`.
_here = ""
try:
    _here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _here = ""

if _here and os.path.isfile(os.path.join(_here, "pesquisai", "ocweb.py")):
    SRC = _here
elif os.path.isfile(os.path.join(os.getcwd(), "pesquisai", "ocweb.py")):
    SRC = os.getcwd()
else:
    SRC = "/content/drive/My Drive/PesquisAI/UFVAI-v0.7.11-web"

DST = "/tmp/pesquisai"

# 3) Se já existe um wrapper antigo na porta 8001 (sessão sem restart),
#    aborta com instrução clara. O bind acontece dentro de uma thread, então
#    sem esta checagem o boot "passaria" e a interface antiga continuaria
#    servindo (foi o que manteve o ttyd aparecendo).
def _porta_ocupada(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", porta)) == 0

if not os.path.isdir(SRC):
    raise SystemExit(f"Árvore não encontrada: {SRC}")

# 4) copia a árvore local (sem .git/debs/deliverable)
if os.path.exists(DST):
    shutil.rmtree(DST)
shutil.copytree(
    SRC, DST,
    ignore=shutil.ignore_patterns(
        ".git", "debs", "deliverable", "__pycache__",
        "*.pyc", ".pytest_cache", "*.egg-info",
    ),
)

os.chdir(DST)
sys.path.insert(0, DST)

# 5) instala o pacote `pesquisai` a partir da árvore copiada
for _cmd in (
    [sys.executable, "-m", "pip", "install", "-q", "--no-deps", "-e", DST],
    [sys.executable, "-m", "pip", "install", "-q", "-e", DST],
):
    try:
        subprocess.run(_cmd, check=False, timeout=900)
    except Exception:
        pass

# 6) confere a versão antes de subir
try:
    from pesquisai.__version__ import __version__
    print(f"UFVAI {__version__} — árvore {DST}")
except Exception as exc:
    print(f"[AVISO] não foi possível ler a versão: {exc}")

# 7) sobe o UFVAI — mas nunca por cima de uma interface antiga
if _porta_ocupada(8001):
    raise SystemExit(
        "\n⚠️  A porta 8001 já está em uso nesta sessão (interface antiga).\n"
        "   A árvore nova JÁ foi copiada para /tmp/pesquisai.\n"
        "   Faça **Ambiente de execução → Reiniciar sessão** e rode esta\n"
        "   célula novamente para subir a variante web.\n"
    )

from main import run
run()
