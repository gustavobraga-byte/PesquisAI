import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = f"http://opencode:{PW}@127.0.0.1:49374/"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1500, "height": 950})
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(4000)
        await page.screenshot(path="/tmp/oc-spa-2.png")
        txt = await page.inner_text("body")
        print("=== texto (600) ===")
        print(txt[:600])

        # se a tela de pareamento aparecer, tenta o link local
        if "Connect to a server" in txt or "Pairing" in txt:
            print("→ tela de pareamento")
            for sel in ["text=Use password", "button:has-text('Use password')"]:
                try:
                    el = page.locator(sel).first
                    if await el.count():
                        await el.click()
                        await page.wait_for_timeout(1200)
                        await page.screenshot(path="/tmp/oc-spa-3.png")
                        print("   clicou em", sel)
                        inputs = await page.evaluate("""() => [...document.querySelectorAll('input')].map(i=>({ph:i.placeholder,type:i.type}))""")
                        print("   inputs:", inputs)
                        break
                except Exception as e:
                    print("   falhou:", sel, e)
            txt = await page.inner_text("body")
            print("=== texto após (800) ===")
            print(txt[:800])
        await browser.close()


asyncio.run(main())
