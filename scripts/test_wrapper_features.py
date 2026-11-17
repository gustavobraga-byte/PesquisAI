"""test_wrapper_features.py — recursos novos através da interface (web18).

Testa a página do wrapper (duas molduras) com URLs locais: alterna para a web,
abre o menu "/", o menu "@", anexa um arquivo e confere os ajustes.
"""

import asyncio, re
from pathlib import Path
from playwright.async_api import async_playwright

SAMPLE = Path("/tmp/anexo-wrapper.txt")
SAMPLE.write_text("linha do anexo pelo wrapper\n", encoding="utf-8")


async def main():
    src = Path('/tmp/pesquisai-wrapper/index.html').read_text(encoding='utf-8', errors='replace')
    src = re.sub(r'https://8002-[^"\'\s]+', 'http://127.0.0.1:8002', src)
    src = re.sub(r'https://8003-[^"\'\s]+', 'http://127.0.0.1:8003', src)
    src = re.sub(r'https://8000-[^"\'\s]+', 'http://127.0.0.1:8000', src)
    Path('/tmp/test-wrapper').mkdir(exist_ok=True)
    Path('/tmp/test-wrapper/index.html').write_text(src, encoding='utf-8')

    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1500, "height": 950})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto("http://127.0.0.1:8099/index.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        await page.evaluate("() => { const b=document.getElementById('console-toggle'); if(b) b.click(); }")
        await page.wait_for_timeout(7000)
        web = next((f for f in page.frames if ":8003" in f.url), None)
        print("frame da web:", web.url if web else "(ausente)")
        if not web:
            return

        print("título:", await web.evaluate("() => (document.getElementById('session-title')||{}).textContent"))
        print("modelos:", await web.evaluate(
            "() => { document.getElementById('model-pill').click(); return document.querySelectorAll('.model-item').length; }"))
        await web.evaluate("() => document.getElementById('model-close').click()")

        # menu "/"
        await web.evaluate("() => { const i=document.getElementById('input'); i.focus(); i.value='/'; i.dispatchEvent(new Event('input')); }")
        await page.wait_for_timeout(1200)
        cmds = await web.evaluate("() => document.querySelectorAll('.palette-item').length")
        print("menu '/':", cmds, "itens")
        await page.screenshot(path="/tmp/ui-wrapper-slash.png")

        # menu "@"
        await web.evaluate("() => { const i=document.getElementById('input'); i.focus(); i.value='@MANUAL'; i.dispatchEvent(new Event('input')); }")
        await page.wait_for_timeout(2200)
        files = await web.evaluate("() => document.querySelectorAll('.palette-item').length")
        print("menu '@':", files, "arquivos")

        # anexo local
        await web.evaluate("() => { const i=document.getElementById('input'); i.focus(); i.value='anexo pelo wrapper'; i.dispatchEvent(new Event('input')); }")
        await web.locator("#file-input").set_input_files(str(SAMPLE))
        await page.wait_for_timeout(1200)
        chips = await web.evaluate("() => [...document.querySelectorAll('.chip .c-name')].map(e=>e.textContent)")
        print("anexos:", chips)

        # ajustes
        await web.evaluate("() => document.getElementById('settings-btn').click()")
        await page.wait_for_timeout(900)
        tabs = await web.evaluate("() => [...document.querySelectorAll('#settings-tabs .tab')].map(e=>e.textContent)")
        print("ajustes:", tabs)
        await page.screenshot(path="/tmp/ui-wrapper-settings.png")
        print("erros:", errors if errors else "nenhum")
        await browser.close()


asyncio.run(main())
