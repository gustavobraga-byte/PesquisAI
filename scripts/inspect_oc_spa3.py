"""inspect_oc_spa3.py — entra na SPA do OpenCode e mapeia a interface.

Preenche o formulário de pareamento (endereço + senha do service.json) e
inspeciona: textos, botões, campos, o menu "/" do composer, o seletor de
modelo e o painel de ajustes (abas).
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = "http://127.0.0.1:49374/"


async def dump(page, titulo):
    print(f"\n{'='*20} {titulo} {'='*20}")
    els = await page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('button,[role="button"],a[href],[role="menuitem"],[role="tab"],[role="option"]').forEach(e => {
                const label = e.getAttribute('aria-label') || e.getAttribute('title') || (e.textContent||'').trim().slice(0,44);
                if (label) out.push((e.getAttribute('role')||e.tagName.toLowerCase()) + ':' + label);
            });
            return [...new Set(out)];
        }"""
    )
    for e in els[:150]:
        print("   ", e)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1500, "height": 950})
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(2500)

        # 1) pareamento por senha
        try:
            await page.get_by_text("Use password").first.click(timeout=5000)
            await page.wait_for_timeout(800)
            await page.locator("input[type='text']").first.fill("http://127.0.0.1:49374")
            await page.locator("input[type='password']").first.fill(PW)
            await page.get_by_text("Connect", exact=True).first.click(timeout=5000)
            await page.wait_for_timeout(5000)
        except Exception as exc:
            print("pareamento falhou:", exc)

        txt = await page.inner_text("body")
        print("=== texto visível (2500) ===")
        print(txt[:2500])
        await page.screenshot(path="/tmp/oc-spa-main.png")

        await dump(page, "botões da tela principal")

        # 2) composer: digita "/" para ver o menu de comandos
        try:
            box = page.locator("[contenteditable='true'], textarea").first
            await box.click(timeout=5000)
            await box.type("/")
            await page.wait_for_timeout(1500)
            await page.screenshot(path="/tmp/oc-spa-slash.png")
            menu = await page.inner_text("body")
            print("\n=== trecho do menu de comandos ===")
            i = menu.find("/")
            print(menu[max(0, i-200): i+1200])
        except Exception as exc:
            print("slash falhou:", exc)

        await browser.close()


asyncio.run(main())
