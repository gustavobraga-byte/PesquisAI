"""inspect_oc_spa4.py — mapeia a SPA do OpenCode dentro de uma sessão.

Entra (pareamento por senha), abre uma sessão e inspeciona:
composer + menu "/" + seletor de modelo + painel de Settings (abas).
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = "http://127.0.0.1:49374/"


async def buttons(page):
    return await page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('button,[role="button"],a[href],[role="menuitem"],[role="tab"],[role="option"],[role="dialog"]').forEach(e => {
                const label = e.getAttribute('aria-label') || e.getAttribute('title') || (e.textContent||'').trim().slice(0,44);
                if (label) out.push((e.getAttribute('role')||e.tagName.toLowerCase()) + ':' + label);
            });
            return [...new Set(out)];
        }"""
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1500, "height": 950})
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(2500)
        try:
            await page.get_by_text("Use password").first.click(timeout=5000)
            await page.wait_for_timeout(700)
            await page.locator("input[type='text']").first.fill("http://127.0.0.1:49374")
            await page.locator("input[type='password']").first.fill(PW)
            await page.get_by_text("Connect", exact=True).first.click(timeout=5000)
            await page.wait_for_timeout(4500)
        except Exception as exc:
            print("pareamento:", exc)

        # abre a primeira sessão da lista
        try:
            await page.get_by_text("UFVAI", exact=False).first.click(timeout=6000)
            await page.wait_for_timeout(4000)
        except Exception as exc:
            print("abrir sessão:", exc)

        print("=== TEXTO DA SESSÃO (2000) ===")
        print((await page.inner_text("body"))[:2000])
        await page.screenshot(path="/tmp/oc-spa-sessao.png")

        print("\n=== BOTÕES NA SESSÃO ===")
        for b in (await buttons(page))[:120]:
            print("   ", b)

        print("\n=== CAMPOS ===")
        for i in await page.evaluate(
            """() => [...document.querySelectorAll('input,textarea,[contenteditable="true"],[role="textbox"]')]
                    .map(e=>({tag:e.tagName,ph:e.getAttribute('placeholder'),aria:e.getAttribute('aria-label'),role:e.getAttribute('role'),ce:e.getAttribute('contenteditable'),type:e.type}))"""
        ):
            print("   ", json.dumps(i, ensure_ascii=False))

        # menu "/" no composer
        for sel in ["[contenteditable='true']", "textarea", "[role='textbox']"]:
            try:
                box = page.locator(sel).first
                if await box.count():
                    await box.click(timeout=4000)
                    await box.type("/")
                    await page.wait_for_timeout(1500)
                    await page.screenshot(path="/tmp/oc-spa-slash.png")
                    print(f"\n=== TEXTO APÓS DIGITAR '/' ({sel}) ===")
                    print((await page.inner_text("body"))[:1500])
                    break
            except Exception as exc:
                print(f"slash em {sel} falhou:", exc)

        # Settings
        try:
            await page.keyboard.press("Escape")
            await page.get_by_text("Settings", exact=True).first.click(timeout=6000)
            await page.wait_for_timeout(2500)
            await page.screenshot(path="/tmp/oc-spa-settings.png")
            print("\n=== TEXTO DO SETTINGS (2500) ===")
            print((await page.inner_text("body"))[:2500])
            print("\n=== BOTÕES DO SETTINGS ===")
            for b in (await buttons(page))[:140]:
                print("   ", b)
        except Exception as exc:
            print("settings:", exc)

        await browser.close()


asyncio.run(main())
