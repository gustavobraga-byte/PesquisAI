"""inspect_slash_menu.py — o que o menu "/" da SPA do OpenCode mostra.

Entra na SPA (pareamento por senha), digita "/" no composer e despeja o
conteúdo do popover — a referência para o menu "/" do cliente UFVAI.
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = "http://127.0.0.1:49374/"


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
            await page.get_by_text("UFVAI", exact=False).first.click(timeout=6000)
            await page.wait_for_timeout(3500)
        except Exception as exc:
            print("setup:", exc)

        await page.evaluate(
            """() => {
                const el = document.querySelector('[role="textbox"],[contenteditable="true"]');
                if (el) { el.focus(); const r=document.createRange(); r.selectNodeContents(el); r.collapse(false);
                          const s=getSelection(); s.removeAllRanges(); s.addRange(r); }
            }"""
        )
        await page.keyboard.type("/", delay=90)
        await page.wait_for_timeout(2000)
        await page.screenshot(path="/tmp/oc-slash-menu.png")

        print("=== elementos do popover (/) ===")
        pops = await page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('[role="menu"],[role="listbox"],[data-slot],[cmdk],[data-radix-popper-content-wrapper] *').forEach(e => {
                    const t = (e.innerText||'').trim();
                    if (t && t.length < 3000 && !out.includes(t)) out.push(t);
                });
                return out;
            }"""
        )
        for p_ in pops[:10]:
            print("---")
            print(p_[:1200])

        # menu "@"
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        await page.keyboard.type("@", delay=90)
        await page.wait_for_timeout(2000)
        await page.screenshot(path="/tmp/oc-at-menu.png")
        print("\n=== elementos do popover (@) ===")
        pops = await page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('[role="menu"],[role="listbox"],[data-slot],[cmdk]').forEach(e => {
                    const t = (e.innerText||'').trim();
                    if (t && t.length < 3000 && !out.includes(t)) out.push(t);
                });
                return out;
            }"""
        )
        for p_ in pops[:10]:
            print("---")
            print(p_[:1200])

        await browser.close()


asyncio.run(main())
