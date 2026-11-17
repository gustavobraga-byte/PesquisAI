#!/usr/bin/env python3
"""web18_runtime.py — aplica (nesta instância) a web18: terminal e web vivos.

O runtime do Colab é **efêmero**: a cada reinício a árvore em ``/tmp`` volta do
GitHub e o HTML do wrapper é regerado pelo boot (versão de uma moldura). Este
script deixa a instância pronta em um comando:

1. copia o módulo do wrapper com a **web18** (duas molduras) para ``/tmp``;
2. regenera o HTML do wrapper com o **token de sessão atual** (as APIs do
   wrapper continuam funcionando) e com a URL da web detectada;
3. informa o que foi feito.

Uso (a partir da pasta do Drive ``UFVAI-v0.7.11-web/``)::

    python3 scripts/web18_runtime.py            # aplica
    python3 scripts/web18_runtime.py --check    # só diagnostica

Nenhuma configuração é inventada: o token e as URLs são lidos do HTML que o
wrapper já está servindo.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

RUNTIME = Path("/tmp/pesquisai")
WRAPPER_DIR = Path("/tmp/pesquisai-wrapper")
WRAPPER_HTML = WRAPPER_DIR / "index.html"
DRIVE_TREE = Path(__file__).resolve().parent.parent


def _read(url: str, timeout: float = 4.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except Exception:  # noqa: BLE001
        return 0


def detect_web_port() -> int:
    """Porta onde a **web nova** está respondendo (8002 pelo boot; 8003 avulso).

    v0.7.11-web25: o teste usa ``/api/ufvai/about`` — rota que só existe na
    versão web25+ do gateway. Com ``/api/ufvai/commands`` (que também existe
    na web24) o script acabava apontando o wrapper para um servidor antigo
    que ainda respondia em 8002.
    """
    for port in (8003, 8002):
        if _read(f"http://127.0.0.1:{port}/api/ufvai/about") == 200:
            return port
    for port in (8003, 8002):
        if _read(f"http://127.0.0.1:{port}/api/ufvai/commands") == 200:
            return port
    return 8002


def proxy_url(html: str, old_port: int, new_port: int) -> str:
    """Troca a porta na URL do proxy do Colab (``https://8002-…`` → ``8003-…``)."""
    m = re.search(r'data-terminal-url="(https://[^"]+)"', html)
    if not m:
        return ""
    return m.group(1).replace(f"://{old_port}-", f"://{new_port}-", 1)


def main() -> int:
    check_only = "--check" in sys.argv

    if not WRAPPER_HTML.exists():
        print(f"✗ wrapper não encontrado: {WRAPPER_HTML}")
        return 1
    html = WRAPPER_HTML.read_text(encoding="utf-8", errors="replace")

    token = ""
    m = re.search(r'var __T = "([^"]+)"', html)
    if m:
        token = m.group(1)
    ttyd_url = ""
    m = re.search(r'var u = "(https://[^"]+)"', html)
    if m:
        ttyd_url = m.group(1)
    terminal_url = ""
    m = re.search(r'data-terminal-url="([^"]+)"', html)
    if m:
        terminal_url = m.group(1)
    drive_url = ""
    m = re.search(r'https://drive\.google\.com/drive/folders/[A-Za-z0-9_-]+', html)
    if m:
        drive_url = m.group(0)

    web_port = detect_web_port()
    web_url = proxy_url(html, 8002, web_port) if web_port != 8002 else terminal_url

    print("─ diagnóstico ─────────────────────────────")
    print(f"  token de sessão : {'ok' if token else 'AUSENTE'}")
    print(f"  url do terminal : {ttyd_url or '—'}")
    print(f"  url do proxy    : {terminal_url or '—'}")
    print(f"  url da web      : {web_url or '—'}  (porta {web_port})")
    print(f"  web18 no HTML   : {'sim' if 'web-frame' in html else 'NÃO (precisa regenerar)'}")
    print(f"  cliente novo    : {'ok' if _read('http://127.0.0.1:%d/api/ufvai/bootstrap' % web_port) == 200 else 'NÃO responde'}")
    if check_only:
        return 0

    if not token or not terminal_url:
        print("✗ não foi possível ler o token/URL do wrapper — o boot ainda está subindo?")
        return 1

    # 1) módulo web18 no runtime
    src = DRIVE_TREE / "pesquisai" / "launch_app_responsive_v041.py"
    dst = RUNTIME / "pesquisai" / "launch_app_responsive_v041.py"
    if src.exists():
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            shutil.copy2(src, dst)
            print(f"✓ módulo do wrapper (web18) copiado para {dst}")
        else:
            print(f"✓ módulo do wrapper (web18) já está no runtime")

    # 2) regenera o HTML do wrapper
    sys.path.insert(0, str(RUNTIME))
    try:
        from pesquisai.launch_app_responsive_v041 import create_wrapper_html  # type: ignore
    except ImportError:  # execução fora do pacote
        sys.path.insert(0, str(RUNTIME / "pesquisai"))
        from launch_app_responsive_v041 import create_wrapper_html  # type: ignore

    # v0.7.11-web22: o *fallback* da moldura da web (usado quando a URL da web
    # não responde) aponta para a MESMA porta da web nova — o proxy antigo
    # (8002 do boot) pode estar com o gateway de uma versão anterior.
    create_wrapper_html(
        terminal_url=web_url or terminal_url,
        drive_url=drive_url or "https://drive.google.com/drive/my-drive",
        session_token=token,
        web_mode=True,
        ttyd_url=ttyd_url,
        web_url=web_url,
    )
    new = WRAPPER_HTML.read_text(encoding="utf-8", errors="replace")
    print(f"✓ wrapper regenerado: {len(new):,} caracteres")
    print(f"  molduras: terminal={new.count('id=\"terminal-frame\"')} "
          f"web={new.count('id=\"web-frame\"')} "
          f"| ping/pong={'ufvai-ping' in new}")
    print("\nRecarregue a página da interface (Ctrl+Shift+R) e use o botão "
          "terminal ↔ web: nenhuma das duas visões recarrega.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
