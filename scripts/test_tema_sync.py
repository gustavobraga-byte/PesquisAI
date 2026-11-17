"""test_tema_sync.py — o botão de tema do cabeçalho do UFVAI altera o tema da web.

Abre a interface (wrapper com duas molduras), clica no botão de tema do
cabeçalho e confere o `data-theme` da moldura da web antes e depois.
"""

import asyncio, re
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    src = Path('/tmp/pesquisai-wrapper/index.html').read_text(encoding='utf-8', errors='replace')
    src = re.sub(r'https://8002-[^"\'\s]+', 'http://127.0.0.1:8002', src)
    src = re.sub(r'https://8003-[^"\'\s]+', 'http://127.0.0.1:8003', src)
    src = re.sub(r'https://8000-[^"\'\s]+', 'http://127.0.0.1:8000', src)
    Path('/tmp/test-wrapper').mkdir(exist_ok=True)
    Path('/tmp/test-wrapper/index.html').write_text(src, encoding='utf-8')

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # a cópia de teste do wrapper não tem a API do UFVAI: responde ao
        # POST /api/theme para que o toggleTheme() siga adiante
        async def tema_route(route):
            await route.fulfill(
                status=200,
                content_type="application/json",
                body='{"ok": true, "theme": "pesquisai-light"}',
            )

        await page.route("**/api/theme", tema_route)
        await page.goto("http://127.0.0.1:8099/index.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await page.evaluate("() => { const b=document.getElementById('console-toggle'); if(b) b.click(); }")
        await page.wait_for_timeout(7000)

        web = next((f for f in page.frames if ":8003" in f.url), None)
        print("frame da web:", web.url if web else "(ausente)")
        if not web:
            return

        antes = await web.evaluate("() => document.documentElement.getAttribute('data-theme')")
        wrapper_antes = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        # botão de tema do cabeçalho do UFVAI (wrapper): #theme-toggle
        achou = await page.evaluate(
            """() => {
                const b = document.getElementById('theme-toggle');
                if (b) { b.click(); return true; }
                return false;
            }"""
        )
        await page.wait_for_timeout(1800)
        depois = await web.evaluate("() => document.documentElement.getAttribute('data-theme')")
        wrapper_depois = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        print(f"botão de tema do cabeçalho encontrado={achou}")
        print(f"tema da web: {antes!r} → {depois!r} (mudou={antes != depois})")
        print(f"tema do wrapper: {wrapper_antes!r} → {wrapper_depois!r}")

        # e o inverso: o botão da web também muda o cabeçalho (cookie compartilhado)
        await web.evaluate("() => document.getElementById('theme-btn').click()")
        await page.wait_for_timeout(1200)
        print("tema do wrapper após o botão da web:",
              await page.evaluate("() => document.documentElement.getAttribute('data-theme')"),
              "| cookie:", await page.evaluate("() => document.cookie"))
        await browser.close()


asyncio.run(main())
