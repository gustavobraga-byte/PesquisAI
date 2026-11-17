"""inspect_oc_attach.py — descobre como a SPA envia arquivos anexados.

Abre a SPA do OpenCode (pareamento por senha), anexa um arquivo pelo botão
"Add images and files", escreve um texto e envia — capturando o corpo real do
POST /api/session/{id}/prompt.
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = "http://127.0.0.1:49374/"
SAMPLE = Path("/tmp/anexo-teste.txt")
SAMPLE.write_text("conteudo de teste do anexo\n", encoding="utf-8")


async def main():
    payloads = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1500, "height": 950})
        page = await ctx.new_page()

        def on_request(req):
            if "/prompt" in req.url and req.method == "POST":
                try:
                    payloads.append(json.loads(req.post_data or "{}"))
                except Exception:
                    payloads.append(req.post_data)

        page.on("request", on_request)
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(2500)
        try:
            await page.get_by_text("Use password").first.click(timeout=5000)
            await page.wait_for_timeout(700)
            await page.locator("input[type='text']").first.fill("http://127.0.0.1:49374")
            await page.locator("input[type='password']").first.fill(PW)
            await page.get_by_text("Connect", exact=True).first.click(timeout=5000)
            await page.wait_for_timeout(4500)
            await page.get_by_text("UFVAI", exact=False).first.click(timeout=6000)
            await page.wait_for_timeout(3500)
        except Exception as exc:
            print("setup:", exc)

        # menu "/": digita "/" num composer vazio e fotografa
        try:
            box = page.locator("[role='textbox']").first
            await box.click(timeout=5000)
            await page.wait_for_timeout(400)
            await box.type("/", delay=60)
            await page.wait_for_timeout(1800)
            await page.screenshot(path="/tmp/oc-slash.png")
            vis = await page.evaluate(
                """() => [...document.querySelectorAll('[role="menu"],[role="listbox"],[cmdk],[data-slot="command"]')]
                        .map(e=>e.innerText.slice(0,400))"""
            )
            print("=== menus com '/' ===")
            for v in vis:
                print(v[:400])
            if not vis:
                print("(nenhum elemento de menu; screenshot em /tmp/oc-slash.png)")
        except Exception as exc:
            print("slash:", exc)

        # anexa arquivo e envia
        try:
            await page.locator("input[type='file']").first.set_input_files(str(SAMPLE))
            await page.wait_for_timeout(1200)
            await page.screenshot(path="/tmp/oc-attach.png")
            box = page.locator("[role='textbox']").first
            await box.click(timeout=4000)
            await box.type("anexo de teste", delay=40)
            await page.wait_for_timeout(600)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(4000)
        except Exception as exc:
            print("anexo:", exc)

        print("\n=== payloads capturados ===")
        for pl in payloads:
            print(json.dumps(pl, ensure_ascii=False)[:2000])
        await browser.close()


asyncio.run(main())
