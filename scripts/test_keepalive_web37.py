#!/usr/bin/env python3
"""test_keepalive_web37.py — valida o keep-alive local do UFVAI (v0.7.11-web37).

Motivo: em máquina LOCAL com o Drive montado em /content/drive, o keep-alive
era pulado (a condição era `if not os.path.isdir("/content/drive")`), o processo
encerrava e a porta 8001 caía (ERR_CONNECTION_REFUSED).

Roda: python3 scripts/test_keepalive_web37.py
"""
import re
import sys
from pathlib import Path

src = (Path(__file__).resolve().parent.parent / "pesquisai" / "run_fast.py").read_text(encoding="utf-8")
ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


# 1) O bloco do keep-alive não depende mais da existência de /content/drive.
_idx = src.find("_offline_keep_alive(banner_url)")
_janela = src[max(0, _idx - 500):_idx]
check('keep-alive não usa os.path.isdir("/content/drive")',
      _idx != -1 and 'os.path.isdir("/content/drive")' not in _janela)

# 2) A nova condição existe.
check("usa _em_kernel", "_em_kernel" in src)
check("considera IN_COLAB", "_in_colab" in src)
check("considera ipykernel", 'ipykernel' in src)
check("chama _offline_keep_alive(banner_url)", "_offline_keep_alive(banner_url)" in src)

# 3) Simula a decisão em três ambientes.
def keep_alive(in_colab, em_jupyter):
    _in_colab = in_colab
    _em_kernel = _in_colab or (em_jupyter)
    return not _em_kernel

check("máquina local (sem kernel, Drive montado) → keep-alive ON",
      keep_alive(False, False) is True)
check("Colab (in_colab=True) → keep-alive OFF",
      keep_alive(True, False) is False)
check("Jupyter local (ipykernel) → keep-alive OFF",
      keep_alive(False, True) is False)

print(f"\n{ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
