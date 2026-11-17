"""inspect_oc_attach2.py — como a SPA envia anexos + o que o "/" abre.

Usa foco via JS (o clique do Playwright é interceptado por sobreposições) e
captura o POST /api/session/{id}/prompt.
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = "http://127.0.0.1:49374/"
SAMPLE = Path("/tmp/anexo-teste.txt")
SAMPLE.write_text("conteudo de teste do anexo\n", encoding="utf-8")


async def focus_composer(page):
    await page.evaluate(
        """() => {
            const el = document.querySelector('[role="textbox"],[contenteditable="true"]');
            if (el) { el.focus(); const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
                      const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
        }"""
    )


async def main():
    payloads = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1500, "height": 950})
        page = await ctx.new_page()

        def on_request(req):
            if req.method == "POST" and "/prompt" in req.url:
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

        # ---- menu "/" ----
        await focus_composer(page)
        await page.keyboard.type("/", delay=80)
        await page.wait_for_timeout(1800)
        await page.screenshot(path="/tmp/oc-slash.png")
        print("=== popover/menu após '/' ===")
        pops = await page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('[role="menu"],[role="listbox"],[data-slot],[cmdk]').forEach(e => {
                    const t = (e.innerText||'').trim();
                    if (t && t.length < 2000) out.push(t);
                });
                return [...new Set(out)];
            }"""
        )
        for p_ in pops[:6]:
            print("---"); print(p_[:900])
        if not pops:
            print("(sem popover; ver /tmp/oc-slash.png)")

        # limpa o composer
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        await page.wait_for_timeout(300)

        # ---- anexo de arquivo ----
        try:
            await page.locator("input[type='file']").first.set_input_files(str(SAMPLE))
            await page.wait_for_timeout(1500)
            await page.screenshot(path="/tmp/oc-attach.png")
            print("\n=== composer após anexar ===")
            print(await page.evaluate("""() => document.querySelector('[role="textbox"]').innerText"""))
        except Exception as exc:
            print("anexo:", exc)

        await focus_composer(page)
        await page.keyboard.type("anexo de teste", delay=40)
        await page.wait_for_timeout(600)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/oc-sent.png")

        print("\n=== payloads capturados ===")
        for pl in payloads:
            print(json.dumps(pl, ensure_ascii=False)[:3000])
        await browser.close()


asyncio.run(main())
