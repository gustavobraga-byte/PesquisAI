#!/usr/bin/env python3
"""test_web32.py — aceitação da rodada web32.

  1. a VERSÃO WEB é a visão padrão ao abrir a interface;
  2. o TERMINAL continua RODANDO em segundo plano (moldura carregada,
     ttyd conectado, vigia RELIGANDO-o se morrer) — mesmo com a web à
     frente e mesmo sem navegador aberto (vigia no servidor);
  3. `?view=terminal` abre no terminal, sob demanda, sem quebrar o padrão.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

WRAPPER_HTML = Path("/tmp/pesquisai-wrapper/index.html")
TEST_DIR = Path("/tmp/test-wrapper")
REPO = Path(__file__).resolve().parent.parent
BOOT = REPO / "COLAB_BOOT_0.7.11.py"
LAUNCH_APP = REPO / "pesquisai" / "launch_app.py"
WRAPPER_SRC = REPO / "pesquisai" / "launch_app_responsive_v041.py"


def preparar_wrapper() -> str:
    """Copia o wrapper gerado, apontando as URLs para o ambiente local."""
    src = WRAPPER_HTML.read_text(encoding="utf-8", errors="replace")
    src = re.sub(r"https://8003-[^\"'\s]+", "http://127.0.0.1:8003", src)
    src = re.sub(r"https://8000-[^\"'\s]+", "http://127.0.0.1:8000", src)
    TEST_DIR.mkdir(exist_ok=True)
    (TEST_DIR / "index.html").write_text(src, encoding="utf-8")
    return str(TEST_DIR / "index.html")


async def _prontidao(page, contador: dict) -> None:
    """Simula os endpoints de prontidão (o servidor real está em outra porta)."""
    await page.route(
        "**/api/ocweb_ready",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"ready": true, "port": 8002}'),
    )

    async def _ttyd(route):
        contador["ttyd_ready"] = contador.get("ttyd_ready", 0) + 1
        await route.fulfill(
            status=200, content_type="application/json",
            body='{"ready": true, "port": 8000, "pid": 4242}',
        )

    await page.route("**/api/ttyd_ready", _ttyd)


async def _testar_vigia_terminal() -> tuple[bool, str]:
    """Teste FUNCIONAL da vigia: derruba o 'terminal' e espera o religamento.

    Usa uma porta de mentira (o alvo é um servidor HTTP qualquer) — o que
    está em teste é a lógica da vigia: detectar a porta caída e religar o
    processo com o mesmo comando e o mesmo ambiente.
    """
    import json
    import os
    import subprocess as sp

    porta = 8097
    argv_file = Path("/tmp/test-watchdog-argv.json")
    log = Path("/tmp/test-watchdog.log")
    argv_file.write_text(
        json.dumps({
            "argv": ["python3", "-m", "http.server", str(porta),
                     "--directory", "/tmp/test-wrapper"],
            "env": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "UFVAI_TTYD_PORT": str(porta),
        "UFVAI_TTYD_WATCHDOG_INTERVAL": "3",
        "UFVAI_TTYD_ARGV_FILE": str(argv_file),
        "UFVAI_TTYD_WATCHDOG_LOG": str(log),
    }
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(REPO / "scripts" / "ttyd_watchdog.py"),
        env=env, stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    def _aberta() -> bool:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
                return True
        except OSError:
            return False

    try:
        for _ in range(40):          # espera a vigia subir o alvo
            await asyncio.sleep(0.5)
            if _aberta():
                break
        if not _aberta():
            return False, "a vigia não subiu o alvo"
        sp.run(["pkill", "-f", f"http.server {porta}"], capture_output=True)
        await asyncio.sleep(1.5)
        caiu = not _aberta()
        for _ in range(30):          # espera o religamento
            await asyncio.sleep(0.5)
            if _aberta():
                return caiu, "religado"
        return False, "não religou em 15 s"
    finally:
        try:
            proc.terminate()
            await asyncio.sleep(0.3)
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        sp.run(["pkill", "-f", f"http.server {porta}"], capture_output=True)


async def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []
    contador: dict = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        reqs: list[str] = []
        page.on("request", lambda r: reqs.append(r.url))
        await _prontidao(page, contador)

        html = preparar_wrapper()
        await page.goto(f"http://127.0.0.1:8099/{html.split('/')[-1]}",
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(9000)

        # ── 1) a WEB é a visão padrão ──────────────────────────────
        visao = await page.evaluate("""() => {
            const web = document.getElementById('web-frame');
            const term = document.getElementById('terminal-frame');
            const visivel = (el) => el && !el.classList.contains('ufvai-hidden')
                && getComputedStyle(el).display !== 'none';
            return {
                webVisivel: visivel(web),
                termVisivel: visivel(term),
                termCarregado: term ? term.dataset.loaded === '1' : false,
                termSrc: term ? term.src : '',
                webSrc: web ? web.src : '',
            };
        }""")
        checks.append(("a web é a visão padrão ao abrir",
                       visao["webVisivel"] and not visao["termVisivel"]))
        checks.append((f"o terminal fica carregado em segundo plano ({visao['termSrc'][:48]}…)",
                       visao["termCarregado"] and ":8000" in visao["termSrc"]))
        checks.append(("a moldura do terminal NÃO mostra a web",
                       "8003" not in visao["termSrc"]))

        # ── 2) o terminal realmente conectou (pedido ao ttyd) ──────
        checks.append(("o navegador abriu o ttyd (terminal rodando)",
                       any(u.startswith("http://127.0.0.1:8000") for u in reqs)))

        # ── 3) a vigia consulta o ttyd mesmo com a web à frente ────
        await page.wait_for_timeout(22000)
        checks.append((f"a vigia do terminal consulta /api/ttyd_ready com a web à frente "
                       f"({contador.get('ttyd_ready', 0)}×)",
                       contador.get("ttyd_ready", 0) >= 1))

        # ── 4) o botão alterna SEM recarregar as molduras ──────────
        # (force=True: na primeira visita a tela de Termos de Uso fica por
        #  cima e interceptaria o clique — não é o que estamos testando)
        await page.evaluate("""() => {
            const o = document.getElementById('terms-overlay');
            if (o) o.style.display = 'none';
        }""")
        antes = await page.evaluate("""() => {
            const t = document.getElementById('terminal-frame');
            const w = document.getElementById('web-frame');
            return {t: t.src, w: w.src};
        }""")
        await page.click("#console-toggle", force=True)
        await page.wait_for_timeout(2500)
        depois = await page.evaluate("""() => {
            const t = document.getElementById('terminal-frame');
            const w = document.getElementById('web-frame');
            const visivel = (el) => el && !el.classList.contains('ufvai-hidden');
            return {t: t.src, w: w.src, termVisivel: visivel(t),
                    webVisivel: visivel(w)};
        }""")
        checks.append(("o botão alterna para o terminal",
                       depois["termVisivel"] and not depois["webVisivel"]))
        checks.append(("a alternância NÃO recarrega as molduras "
                       "(a sessão do agente continua viva)",
                       antes["t"] == depois["t"] and antes["w"] == depois["w"]))

        # ── 5) ?view=terminal abre no terminal ─────────────────────
        page2 = await ctx.new_page()
        page2.on("pageerror", lambda e: errors.append(f"[pageerror-2] {e}"))
        await _prontidao(page2, contador)
        await page2.goto(f"http://127.0.0.1:8099/{html.split('/')[-1]}?view=terminal",
                         wait_until="domcontentloaded")
        await page2.wait_for_timeout(9000)
        vis2 = await page2.evaluate("""() => {
            const t = document.getElementById('terminal-frame');
            const w = document.getElementById('web-frame');
            const visivel = (el) => el && !el.classList.contains('ufvai-hidden');
            return {term: visivel(t), web: visivel(w)};
        }""")
        checks.append(("?view=terminal abre no terminal", vis2["term"] and not vis2["web"]))
        await page2.close()

        await browser.close()

    # ── 6) a vigia do terminal existe no SERVIDOR ──────────────────
    txt = LAUNCH_APP.read_text(encoding="utf-8")
    checks.append(("servidor: vigia do terminal (thread) presente",
                   "ufvai-ttyd-watchdog" in txt and "_start_ttyd_watchdog" in txt))
    checks.append(("servidor: a vigia religa o ttyd se a porta cair",
                   "_revive_ttyd(force=True)" in txt))
    checks.append(("servidor: a vigia externa (script) é iniciada no boot",
                   "_start_ttyd_watchdog_process" in txt
                   and "ttyd_watchdog.py" in txt))

    # ── 6b) teste FUNCIONAL da vigia: derruba e espera religar ────
    ok_vigia, det = await _testar_vigia_terminal()
    checks.append((f"a vigia religa o terminal depois da queda ({det})", ok_vigia))

    # ── 7) o wrapper tem o splash da web nos 5 idiomas ─────────────
    wtxt = WRAPPER_SRC.read_text(encoding="utf-8")
    for lang, txt_splash in (("pt", "Carregando a interface"),
                             ("en", "Loading the interface"),
                             ("es", "Cargando la interfaz"),
                             ("fr", "Chargement de l’interface"),
                             ("zh", "正在加载界面")):
        checks.append((f"splash da web em {lang}", txt_splash in wtxt))

    # ── 8) o padrão é a web — a preferência antiga não manda mais ───
    checks.append(("a chave antiga (ufvai.console.v2) é ignorada/limpa",
                   'localStorage.removeItem("ufvai.console.v2")' in wtxt))
    checks.append(("?view=terminal é o escape hatch documentado",
                   '_VIEW_PARAM === "terminal"' in wtxt))

    print("═══ aceitação web32 ═══")
    for nome, ok in checks:
        print(f"  {'✓' if ok else '✗'} {nome}")
    falhas = [n for n, ok in checks if not ok]
    print(f"  erros de console: {errors if errors else 'nenhum'}")
    print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
    return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
