"""test_webui_final.py — validação final dos recursos novos do cliente UFVAI.

  · apenas o agente UFVAI (ajustes → Agente)
  · menu "/" com comandos (inserção correta)
  · menu "@" com arquivos do projeto (anexo + inserção)
  · anexo local enviado ao motor (chegou como "Attached file")
  · painel de ajustes e menu de sessão
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"
SAMPLE = Path("/tmp/anexo-final.txt")
SAMPLE.write_text("conteúdo do anexo final\n", encoding="utf-8")


async def js_click(page, selector, index=0):
    await page.evaluate(
        """([sel, i]) => {
            const nodes = [...document.querySelectorAll(sel)];
            if (nodes[i]) nodes[i].click();
        }""", [selector, index])


async def main():
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(1800)

        # 1) agente — só UFVAI
        await js_click(page, "#agent-pill")
        await page.wait_for_timeout(700)
        pane = await page.inner_text("#settings-pane")
        agentes = [l for l in pane.split("\n") if l.strip()][:6]
        print(f"1) aba Agente: {agentes}")
        await js_click(page, "#settings-close")

        # 2) menu "/"
        await page.fill("#input", "/")
        await page.wait_for_timeout(800)
        items = await page.locator(".palette-item .p-name").all_inner_texts()
        print(f"2) comandos no menu '/': {len(items)} → {items[:6]}")
        await page.fill("#input", "/dados")
        await page.wait_for_timeout(700)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(400)
        valor = await page.input_value("#input")
        print(f"   inserção: {valor!r}")
        await page.keyboard.type("IBGE no VF")
        print(f"   final: {(await page.input_value('#input'))!r}")
        await page.fill("#input", "")

        # 3) menu "@" + anexo de arquivo do projeto
        await page.fill("#input", "@MANUAL")
        await page.wait_for_timeout(1800)
        arquivos = await page.locator(".palette-item .p-name").all_inner_texts()
        print(f"3) menu '@' (busca MANUAL): {len(arquivos)} → {arquivos[:4]}")
        if arquivos:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2500)
            chips = await page.locator(".chip .c-name").all_inner_texts()
            print(f"   chips de anexo: {chips} | composer: {(await page.input_value('#input'))!r}")

        # 4) anexo local + envio
        await page.fill("#input", "resuma o anexo")
        await page.set_input_files("#file-input", str(SAMPLE))
        await page.wait_for_timeout(800)
        print(f"4) barra de anexos: {await page.locator('.chip .c-name').all_inner_texts()}")
        await js_click(page, "#send-btn")
        await page.wait_for_timeout(7000)
        print(f"   enviada; mensagens na conversa: {await page.locator('.msg').count()}")
        await page.screenshot(path="/tmp/ui-final.png")

        print("5) erros:", errors if errors else "nenhum")
        await browser.close()


asyncio.run(main())
