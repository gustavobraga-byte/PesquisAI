#!/usr/bin/env python3
"""test_web31.py — aceitação da rodada web31.

  1. o cabeçalho do **wrapper** mostra o estado REAL do agente (ativo/ocioso);
  2. o **boot** usa a árvore do Drive (com as correções) em vez do clone do
     GitHub — era a razão de o usuário continuar vendo a interface antiga;
  3. a rota de estado do agente no gateway responde e libera CORS.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

WRAPPER_HTML = Path("/tmp/pesquisai-wrapper/index.html")
TEST_DIR = Path("/tmp/test-wrapper")
REPO = Path(__file__).resolve().parent.parent
BOOT = REPO / "COLAB_BOOT_0.7.11.py"


def preparar_wrapper() -> str:
    src = WRAPPER_HTML.read_text(encoding="utf-8", errors="replace")
    # no teste local, a URL da web aponta para o gateway local
    src = re.sub(r"https://8003-[^\"'\s]+", "http://127.0.0.1:8003", src)
    TEST_DIR.mkdir(exist_ok=True)
    (TEST_DIR / "index.html").write_text(src, encoding="utf-8")
    return str(TEST_DIR / "index.html")


async def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []

    # ── 2) o boot prefere a árvore do Drive ──────────────────────────────
    boot_txt = BOOT.read_text(encoding="utf-8")
    drive_primeiro = (
        "_DAY_DRIVE" in boot_txt
        and boot_txt.index('os.path.join(_DAY_DRIVE, "pesquisai", "ocweb.py")')
        < boot_txt.index('os.path.join(_here, "pesquisai", "ocweb.py")')
    )
    checks.append(("boot: a árvore do Drive tem precedência sobre o clone do GitHub",
                   drive_primeiro))
    checks.append(("boot: imprime a árvore de origem",
                   "Árvore de origem" in boot_txt))
    checks.append(("boot: aceita UFVAI_BOOT_SRC (escolha explícita)",
                   "UFVAI_BOOT_SRC" in boot_txt))

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        html = preparar_wrapper()
        await page.goto(f"http://127.0.0.1:8099/{html.split('/')[-1]}",
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(9000)

        # ── 1) o wrapper mostra o estado real ────────────────────────────
        real = await page.evaluate("""() => {
            const dot = document.getElementById('agent-status-dot');
            const txt = document.getElementById('agent-status-text');
            return {classe: dot ? dot.className : '', texto: txt ? txt.textContent : '',
                    existe: !!dot && !!txt};
        }""")
        checks.append((f"wrapper tem o indicador de estado ({real.get('classe')!r})",
                       bool(real.get("existe"))))
        checks.append((f"wrapper reflete o estado do motor ({real.get('texto')!r})",
                       real.get("classe", "") in ("status-dot busy", "status-dot idle")
                       and bool(real.get("texto"))))

        # com busy=true forçado → o rótulo e o ponto mudam
        await page.route("**/api/ufvai/agent-state", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"busy": true, "sid": "ses_x", "sessions": 1}'))
        await page.wait_for_timeout(5200)
        forcado = await page.evaluate("""() => {
            const dot = document.getElementById('agent-status-dot');
            const txt = document.getElementById('agent-status-text');
            return {classe: dot ? dot.className : '', texto: txt ? txt.textContent : '',
                    cor: dot ? getComputedStyle(dot).backgroundColor : ''};
        }""")
        checks.append((f"com o agente ocupado: ponto âmbar + rótulo ({forcado.get('texto')!r})",
                       "busy" in forcado.get("classe", "")
                       and "209, 167, 5" in (forcado.get("cor") or "")))

        # ── 3) a rota do gateway responde e libera CORS ──────────────────
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:8003/api/ufvai/agent-state")
        with urllib.request.urlopen(req, timeout=20) as resp:
            corpo = resp.read().decode("utf-8")
            cors = resp.headers.get("Access-Control-Allow-Origin")
        checks.append((f"rota /agent-state do gateway responde (CORS={cors})",
                       '"busy"' in corpo and cors == "*"))

        await browser.close()

    print("═══ aceitação web31 ═══")
    for nome, ok in checks:
        print(f"  {'✓' if ok else '✗'} {nome}")
    falhas = [n for n, ok in checks if not ok]
    print(f"  erros de console: {errors if errors else 'nenhum'}")
    print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
    return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
