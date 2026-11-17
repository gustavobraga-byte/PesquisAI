"""test_webui_features.py — valida os recursos novos do cliente UFVAI.

  · menu "/" (comandos do agente)
  · menu "@" (arquivos do projeto) + anexo
  · anexar arquivo local e enviar (o motor recebe o anexo)
  · painel de ajustes (abas) e菜单 de sessão
  · apenas o agente UFVAI na lista
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"
SAMPLE = Path("/tmp/anexo-ui.txt")
SAMPLE.write_text("primeira linha do anexo\nsegunda linha\n", encoding="utf-8")


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

        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(1800)

        # 1) agente: apenas UFVAI
        agent = await page.inner_text("#agent-label")
        print(f"1) agente exibido: {agent!r}")

        # 2) menu "/"
        await page.fill("#input", "/")
        await page.wait_for_timeout(900)
        vis = await page.locator("#palette").is_visible()
        items = await page.locator(".palette-item").all_inner_texts()
        print(f"2) menu '/': visível={vis} | itens={len(items)} | ex.: {items[:3]}")
        await page.screenshot(path="/tmp/ui-slash.png")

        # 2b) filtra "/pesq"
        await page.fill("#input", "/pesq")
        await page.wait_for_timeout(700)
        items = await page.locator(".palette-item").all_inner_texts()
        print(f"   busca '/pesq' → {items}")
        # escolhe o primeiro
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(600)
        print(f"   composer após escolher: {await page.input_value('#input')!r}")

        # 3) menu "@"
        await page.fill("#input", "@")
        await page.wait_for_timeout(1500)
        vis = await page.locator("#palette").is_visible()
        files = await page.locator(".palette-item").all_inner_texts()
        print(f"3) menu '@': visível={vis} | arquivos={len(files)} | ex.: {files[:3]}")
        await page.screenshot(path="/tmp/ui-at.png")

        # 4) anexo local + envio
        await page.fill("#input", "analyze o anexo")
        await page.set_input_files("#file-input", str(SAMPLE))
        await page.wait_for_timeout(900)
        chips = await page.locator(".chip .c-name").all_inner_texts()
        print(f"4) anexos na barra: {chips}")
        await page.screenshot(path="/tmp/ui-attach.png")

        await js_click(page, "#send-btn")
        await page.wait_for_timeout(6000)
        msgs = await page.locator(".msg-user .bubble").all_inner_texts()
        attach_txt = await page.locator(".bubble-attach").all_inner_texts()
        print(f"   enviada: {msgs[-1][:40]!r} | marca de anexo: {attach_txt[-1:]!r}")

        # 5) ajustes: abas
        await js_click(page, "#settings-btn")
        await page.wait_for_timeout(700)
        tabs = await page.locator("#settings-tabs .tab").all_inner_texts()
        print(f"5) abas dos ajustes: {tabs}")
        await page.screenshot(path="/tmp/ui-settings.png")
        for tab in ["comandos", "habilidades", "sessao", "atalhos"]:
            await js_click(page, f'.tab[data-tab="{tab}"]')
            await page.wait_for_timeout(500)
            txt = (await page.inner_text("#settings-pane"))[:110].replace("\n", " | ")
            print(f"   aba {tab}: {txt}")
        await js_click(page, "#settings-close")

        # 6) menu da sessão
        await js_click(page, "#session-menu-btn")
        await page.wait_for_timeout(600)
        acts = await page.locator("#session-actions .m-name").all_inner_texts()
        print(f"6) ações da sessão: {acts}")
        await js_click(page, "#session-close")

        print("7) erros:", errors if errors else "nenhum")
        await browser.close()


asyncio.run(main())
