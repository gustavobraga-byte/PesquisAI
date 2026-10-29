#!/usr/bin/env python3
"""Diagnóstico funcional do teclado no terminal (ttyd + xterm.js) — v0.7.8.

Sobe um ttyd descartável com o HTML injetado por ``launch_app`` (o mesmo
``--index`` usado pelo UFVAI), abre no Chromium via Playwright e verifica o
contrato do ajuste "Ctrl+C copia / Ctrl+V cola":

  1. digitação chega ao PTY;
  2. **Ctrl+V** cola (evento ``paste`` nativo) uma única vez e **não** deixa
     ``^V`` no terminal;
  3. **Ctrl+V** sem evento ``paste`` (navegador que não entrega o evento)
     ainda cola via Clipboard API (rede de segurança);
  4. ``paste`` com o foco fora do terminal chega ao PTY (fallback);
  5. **Ctrl+C** copia a seleção e **não envia** ``^C``;
  6. **Ctrl+Shift+C** envia ``^C`` de verdade (saída de emergência).

Uso:
    python3 scripts/diag_clipboard_ttyd.py          # roda tudo
    python3 scripts/diag_clipboard_ttyd.py -v       # mostra o buffer final

Requisitos: ``ttyd`` no PATH e ``playwright`` + Chromium instalados
(``pip install playwright && playwright install chromium``).

Códigos de saída: 0 = tudo certo · 1 = alguma verificação falhou ·
2 = ambiente sem ttyd/Playwright. Nada é escrito no Drive; o ttyd de teste
roda numa porta livre e é encerrado no fim.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def _say(*partes: object) -> None:
    """Escreve no stdout REAL — o launch_app silencia ``builtins.print`` no Colab."""
    sys.stdout.write(" ".join(str(p) for p in partes) + "\n")
    sys.stdout.flush()

ECHO_PY = r'''
import os, signal
def _h(s, f):
    os.write(1, b"GOT_SIGINT\r\n")
signal.signal(signal.SIGINT, _h)
os.write(1, b"READY\r\n")
while True:
    d = os.read(0, 1024)
    if not d:
        break
    os.write(1, d)
'''

BUF_JS = """() => {const b=window.term.buffer.active;let L=[];
  for(let i=0;i<b.length;i++){const l=b.getLine(i);if(l){const s=l.translateToString(true);
    if(s.trim())L.push(s);}}
  return L.join('');}"""

PASTE_JS = """(arg) => {const txt=arg[0], alvoBody=arg[1];
  const dt=new DataTransfer(); dt.setData('text/plain', txt);
  const alvo=alvoBody?document.body:document.querySelector('.xterm-helper-textarea');
  alvo.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));}"""


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _espera_porta(porta: int, timeout: float = 10.0) -> bool:
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            socket.create_connection(("127.0.0.1", porta), 0.3).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


def _spawn(porta: int, args: list[str], cmd: list[str]) -> subprocess.Popen:
    proc = subprocess.Popen(
        ["ttyd", "-p", str(porta), "--writable", *args, *cmd],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True,
    )
    if not _espera_porta(porta):
        raise RuntimeError(f"ttyd não subiu na porta {porta}")
    return proc


def _matar(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass


def _mata_por_pid(pid: int) -> None:
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="imprime o buffer final do terminal")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        _say(f"[erro] Playwright indisponível: {exc}")
        return 2
    if not (subprocess.run(["which", "ttyd"], capture_output=True).returncode == 0):
        _say("[erro] ttyd não está no PATH.")
        return 2

    from pesquisai import launch_app as la

    echo_py = os.path.join(tempfile.gettempdir(), "ufvai_echo_sigint.py")
    with open(echo_py, "w", encoding="utf-8") as fh:
        fh.write(ECHO_PY)

    # 1) HTML base (ttyd sem --index) + injeção do script real do UFVAI
    porta_base = _porta_livre()
    p0 = _spawn(porta_base, [], ["bash", "-c", "sleep 1"])
    try:
        html = urllib.request.urlopen(f"http://127.0.0.1:{porta_base}/", timeout=5).read().decode()
    finally:
        _matar(p0)
    time.sleep(0.4)

    idx = os.path.join(tempfile.gettempdir(), "ufvai_idx_diag.html")
    with open(idx, "w", encoding="utf-8") as fh:
        fh.write(html.replace("<head>", "<head>" + la._get_terminal_inject_script(), 1))

    # 2) ttyd de teste com o index injetado
    porta = _porta_livre()
    ttyd = _spawn(porta, ["--index", idx], [sys.executable, "-u", echo_py])

    res: dict[str, str] = {}
    try:
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            ctx = nav.new_context(permissions=["clipboard-read", "clipboard-write"])
            pg = ctx.new_page()
            pg.goto(f"http://127.0.0.1:{porta}/")
            pg.wait_for_function("() => !!window.term", timeout=15000)
            time.sleep(1.2)
            pg.click(".xterm-screen")
            time.sleep(0.4)

            pg.keyboard.type("ola mundo")
            time.sleep(0.5)
            res["digita"] = pg.evaluate(BUF_JS)

            # A) Ctrl+V com o evento paste que o navegador entrega ao xterm
            pg.keyboard.press("Control+v")
            pg.evaluate(PASTE_JS, ["PASTENATIVO", False])
            time.sleep(0.9)
            res["buf_nativo"] = pg.evaluate(BUF_JS)

            # B) Ctrl+V sem evento paste -> rede de segurança da Clipboard API
            pg.evaluate("navigator.clipboard.writeText('PASTEAPI')")
            pg.keyboard.press("Control+v")
            time.sleep(1.1)
            res["buf_api"] = pg.evaluate(BUF_JS)

            # C) paste com o foco fora do terminal (target = body)
            pg.evaluate(PASTE_JS, ["PASTEBODY", True])
            time.sleep(0.6)
            res["buf_body"] = pg.evaluate(BUF_JS)

            # D) Ctrl+C com seleção
            pg.evaluate("window.term.selectAll()")
            time.sleep(0.4)
            pg.keyboard.press("Control+c")
            time.sleep(0.8)
            res["clip"] = pg.evaluate("navigator.clipboard.readText()")
            res["buf_ctrlc"] = pg.evaluate(BUF_JS)

            # E) Ctrl+Shift+C
            pg.keyboard.press("Control+Shift+C")
            time.sleep(1.2)
            res["buf_shiftc"] = pg.evaluate(BUF_JS)
            nav.close()
    finally:
        _matar(ttyd)

    checks = [
        ("digitação chega ao PTY", "ola mundo" in res["digita"]),
        ("Ctrl+V (paste nativo) cola 1x", res["buf_nativo"].count("PASTENATIVO") == 1),
        ("Ctrl+V nativo não deixa ^V", "^V" not in res["buf_nativo"]),
        ("Ctrl+V sem evento: Clipboard API cola", "PASTEAPI" in res["buf_api"]),
        ("paste fora do terminal chega ao PTY", res["buf_body"].count("PASTEBODY") == 1),
        ("Ctrl+C copia a seleção", "ola mundo" in (res["clip"] or "")),
        ("Ctrl+C NÃO envia ^C", "GOT_SIGINT" not in res["buf_ctrlc"]),
        ("Ctrl+C não suja o terminal com ^C", "^C" not in res["buf_ctrlc"]),
        ("Ctrl+Shift+C envia ^C", "GOT_SIGINT" in res["buf_shiftc"]),
    ]
    if args.verbose:
        _say(f"clipboard: {res['clip'][:60]!r}")
        _say(f"buffer final: {res['buf_shiftc'][-200:]}")
    for nome, ok in checks:
        _say(("  OK    " if ok else "  FALHA ") + nome)
    falhas = [n for n, ok in checks if not ok]
    _say("\nRESULTADO:", "PASS" if not falhas else "FAIL -> " + ", ".join(falhas))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
