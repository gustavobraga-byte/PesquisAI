#!/usr/bin/env python3
"""Diagnóstico funcional — seleção/cópia no terminal com a TUI no comando.

Bug relatado em 29/10/2026: *"o Ctrl+C não está funcionando na TUI: aparece
'nada selecionado'"*. Causa medida no bundle do ttyd 1.7.4 (xterm.js):

  * a TUI do opencode liga a captura de mouse (DECSET 1000/1002/1006);
  * nesse estado o xterm **desativa o serviço de seleção**
    (``CoreMouseService.onProtocolChange`` → ``_selectionService.disable()``);
  * arrastar passa a ser evento de mouse para o aplicativo, a seleção fica
    vazia e ``term.getSelection()`` devolve ``''`` → o Ctrl+C não tem o que
    copiar (o aviso "Nada selecionado" estava correto);
  * e a cópia feita *dentro* da TUI vai por **OSC 52**, que o xterm.js não
    implementa.

Este script sobe um ttyd descartável (porta livre) com uma TUI falsa que
imita o comportamento do opencode e verifica, em Chromium real:

  1. a TUI captura o mouse (cenário do bug);
  2. arrastar seleciona e **copia** ("copiar ao selecionar");
  3. Ctrl+C copia e **não** envia ``^C``;
  4. Shift+arrastar + Ctrl+C (caminho nativo do xterm) também copia;
  5. clique continua chegando à TUI (mouse preservado);
  6. OSC 52 emitido pela TUI chega ao clipboard do navegador;
  7. com ``window.__ufvaiDragSelect=false`` o bug volta (o teste mede o
     comportamento certo).

Uso:
    python3 scripts/diag_selecao_tui.py
    python3 scripts/diag_selecao_tui.py -v     # mostra as mensagens do console

Requisitos: ``ttyd`` no PATH e Playwright + Chromium
(``pip install playwright && playwright install chromium``).

Códigos de saída: 0 = tudo certo · 1 = alguma verificação falhou ·
2 = ambiente sem ttyd/Playwright. Nada é escrito no Drive; o ttyd de teste
roda em porta livre e é encerrado no fim — o terminal real não é tocado.
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

TUI_PY = r'''
import base64
import os
import sys
import tty

OUT = 1

def w(s):
    os.write(OUT, s.encode("utf-8"))

def main():
    try:
        tty.setraw(0)
    except Exception:
        pass
    w("\x1b[?1000h\x1b[?1002h\x1b[?1006h")   # captura de mouse (como a TUI)
    w("\x1b[2J\x1b[H")
    for i in range(1, 11):
        w("linha %02d: texto de exemplo para selecionar com o mouse\r\n" % i)
    w("PRONTO\r\n\x1b[?25l")

    buf = b""
    while True:
        d = os.read(0, 1024)
        if not d:
            break
        buf += d
        while True:                        # descarta respostas de consulta OSC 52
            i = buf.find(b"\x1b]52;")
            if i < 0:
                break
            j = buf.find(b"\x07", i)
            if j < 0:
                break
            buf = buf[:i] + buf[j + 1:]
        while True:                        # cliques/arrastos -> MOUSE
            i = buf.find(b"\x1b[<")
            if i < 0:
                break
            fins = [x for x in (buf.find(b"M", i), buf.find(b"m", i)) if x >= 0]
            if not fins:
                break
            j = min(fins)
            buf = buf[:i] + buf[j + 1:]
            w("MOUSE\r\n")
        if b"o" in buf:                    # simula "Copied to clipboard"
            buf = buf.replace(b"o", b"", 1)
            w("\x1b]52;c;" + base64.b64encode(b"copiado pela TUI").decode() + "\x07")
        if b"\x03" in buf:
            buf = buf.replace(b"\x03", b"", 1)
            w("GOT_SIGINT\r\n")

main()
'''

BUF_JS = (
    "() => {const b=window.term.buffer.active;let s='';"
    "for(let i=0;i<b.length;i++){const l=b.getLine(i);if(l)s+=l.translateToString(true)+'|';}return s;}"
)


def _say(*p: object) -> None:
    """stdout REAL — o launch_app silencia ``builtins.print`` no Colab."""
    sys.stdout.write(" ".join(str(x) for x in p) + "\n")
    sys.stdout.flush()


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _espera_porta(porta: int, timeout: float = 15.0) -> bool:
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    if not _espera_porta(porta):
        raise RuntimeError(f"ttyd não subiu na porta {porta}")
    return proc


def _matar(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass


def _arrasto(pg, box: dict, shift: bool = False) -> None:
    x1, y1 = box["x"] + 20, box["y"] + 8
    x2 = box["x"] + min(box["width"] - 40, 340)
    if shift:
        pg.keyboard.down("Shift")
    pg.mouse.move(x1, y1)
    pg.mouse.down()
    pg.mouse.move(x2, y1, steps=12)
    pg.mouse.up()
    if shift:
        pg.keyboard.up("Shift")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="mostra o console da página")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        _say(f"[erro] Playwright indisponível: {exc}")
        return 2
    if subprocess.run(["which", "ttyd"], capture_output=True).returncode != 0:
        _say("[erro] ttyd não está no PATH.")
        return 2

    from pesquisai import launch_app as la

    tui = os.path.join(tempfile.gettempdir(), "ufvai_diag_tui_falsa.py")
    with open(tui, "w", encoding="utf-8") as fh:
        fh.write(TUI_PY)

    # 1) HTML base do ttyd + script real do UFVAI injetado no <head>
    p0 = _porta_livre()
    base = _spawn(p0, [], ["bash", "-c", "sleep 1"])
    try:
        html = urllib.request.urlopen(f"http://127.0.0.1:{p0}/", timeout=5).read().decode()
    finally:
        _matar(base)
    time.sleep(0.4)

    idx = os.path.join(tempfile.gettempdir(), "ufvai_diag_tui_index.html")
    with open(idx, "w", encoding="utf-8") as fh:
        fh.write(html.replace("<head>", "<head>" + la._get_terminal_inject_script(), 1))

    # 2) ttyd de teste com a TUI falsa
    porta = _porta_livre()
    ttyd = _spawn(porta, ["--index", idx], [sys.executable, "-u", tui])

    res: dict[str, object] = {}
    try:
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            ctx = nav.new_context(permissions=["clipboard-read", "clipboard-write"])

            pg = ctx.new_page()
            logs: list[str] = []
            pg.on("console", lambda m: logs.append(m.text))
            pg.goto(f"http://127.0.0.1:{porta}/")
            pg.wait_for_function("() => !!window.term", timeout=20000)
            time.sleep(1.5)
            pg.click(".xterm-screen")
            time.sleep(0.5)

            res["captura"] = pg.evaluate(
                "() => !!document.querySelector('.xterm').classList.contains('enable-mouse-events')"
            )
            box = pg.locator(".xterm-screen").bounding_box()

            pg.evaluate("() => navigator.clipboard.writeText('__limpo__')")
            _arrasto(pg, box)
            time.sleep(0.4)
            res["clip_arrasto"] = pg.evaluate("() => navigator.clipboard.readText()")

            pg.keyboard.press("Control+c")
            time.sleep(0.6)
            res["clip_ctrlc"] = pg.evaluate("() => navigator.clipboard.readText()")
            res["buffer"] = pg.evaluate(BUF_JS)

            pg.evaluate("() => navigator.clipboard.writeText('__limpo2__')")
            pg.evaluate("() => window.term.clearSelection()")
            _arrasto(pg, box, shift=True)
            time.sleep(0.3)
            pg.keyboard.press("Control+c")
            time.sleep(0.5)
            res["clip_shift"] = pg.evaluate("() => navigator.clipboard.readText()")

            pg.evaluate("() => window.term.clearSelection()")
            pg.mouse.move(box["x"] + 60, box["y"] + 30)
            pg.mouse.down()
            pg.mouse.up()
            time.sleep(0.7)
            res["clique"] = "MOUSE" in pg.evaluate(BUF_JS)

            pg.evaluate("() => navigator.clipboard.writeText('__antes__')")
            pg.keyboard.type("o")
            time.sleep(1.0)
            res["osc52"] = pg.evaluate("() => navigator.clipboard.readText()")

            # 3) kill-switch: reproduz o bug original
            ctx2 = nav.new_context(permissions=["clipboard-read", "clipboard-write"])
            ctx2.add_init_script("window.__ufvaiDragSelect=false")
            pg2 = ctx2.new_page()
            pg2.goto(f"http://127.0.0.1:{porta}/")
            pg2.wait_for_function("() => !!window.term", timeout=20000)
            time.sleep(1.5)
            pg2.click(".xterm-screen")
            time.sleep(0.5)
            pg2.evaluate("() => navigator.clipboard.writeText('__limpo3__')")
            _arrasto(pg2, pg2.locator(".xterm-screen").bounding_box())
            time.sleep(0.4)
            res["clip_sem_fix"] = pg2.evaluate("() => navigator.clipboard.readText()")

            if args.verbose:
                for ln in logs:
                    if "UFVAI" in ln:
                        _say("  console:", ln)
            nav.close()
    finally:
        _matar(ttyd)

    checks = [
        ("a TUI captura o mouse (cenário do bug)", res["captura"] is True),
        ("arrastar copia (copiar ao selecionar)", "texto de exemplo" in str(res["clip_arrasto"])),
        ("Ctrl+C copia a seleção", "texto de exemplo" in str(res["clip_ctrlc"])),
        ("Ctrl+C não envia ^C", "GOT_SIGINT" not in str(res["buffer"])),
        ("Shift+arrasto + Ctrl+C copia", "texto de exemplo" in str(res["clip_shift"])),
        ("clique continua indo para a TUI", res["clique"] is True),
        ("OSC 52 chega ao clipboard", str(res["osc52"]).strip() == "copiado pela TUI"),
        ("sem o fix nada é selecionado (bug reproduzido)", str(res["clip_sem_fix"]) == "__limpo3__"),
    ]
    for nome, ok in checks:
        _say(("  OK    " if ok else "  FALHA ") + nome)
    falhas = [n for n, ok in checks if not ok]
    _say("\nRESULTADO:", "PASS" if not falhas else "FAIL -> " + ", ".join(falhas))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
