"""inspect_oc_spa.py — inspeciona a SPA do OpenCode (referência de recursos).

Uso: python3 scripts/inspect_oc_spa.py
Mostra o texto visível, os botões e os campos de entrada da interface oficial —
a referência para replicar menus, ajustes e atalhos no cliente do UFVAI.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
CREDS = {"username": "opencode", "password": SERVICE["password"]}
BASE = "http://127.0.0.1:49374/"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(http_credentials=CREDS, viewport={"width": 1500, "height": 950})
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(3500)
        await page.screenshot(path="/tmp/oc-spa-1.png")

        print("=== TEXTO VISÍVEL (OpenCode SPA) ===")
        print((await page.inner_text("body"))[:3000])

        print("\n=== BOTÕES / ICONES ===")
        els = await page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('button,[role="button"],a[href],[data-testid]').forEach(e => {
                    const label = e.getAttribute('aria-label') || e.getAttribute('title')
                        || e.getAttribute('data-testid') || (e.textContent||'').trim().slice(0,40);
                    if (label) out.push((e.tagName||'') + ':' + label);
                });
                return [...new Set(out)];
            }"""
        )
        for e in els[:140]:
            print("   ", e)

        print("\n=== CAMPOS DE ENTRADA ===")
        inputs = await page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('input,textarea,[contenteditable="true"],[role="textbox"]').forEach(e => {
                    out.push({tag: e.tagName, ph: e.getAttribute('placeholder'),
                              aria: e.getAttribute('aria-label'), role: e.getAttribute('role'),
                              ce: e.getAttribute('contenteditable')});
                });
                return out;
            }"""
        )
        for i in inputs:
            print("   ", json.dumps(i, ensure_ascii=False))

        await browser.close()


asyncio.run(main())
