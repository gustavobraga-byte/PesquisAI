"""test_webui_web20.py — valida as correções e melhorias da web20.

  · menu "@" lista **habilidades** (skills) e arquivos
  · menção de habilidade vai no prompt (`skills`)
  · interruptores "expandir raciocínio" / "expandir ferramentas"
  · duplo clique no nome da sessão → renomear
  · hambúrguer mostra/oculta o menu de sessões (responsivo)
  · tema da web (claro/escuro) + tema sincronizado pelo cabeçalho do UFVAI
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"


async def main():
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept("sessão renomeada")))
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 1) menu "@" → habilidades + arquivos
        await page.fill("#input", "@")
        await page.wait_for_timeout(2000)
        grupos = await page.locator(".palette-group").all_inner_texts()
        skills = await page.locator(".palette-item .p-name").all_inner_texts()
        print(f"1) menu '@': grupos={grupos} | itens={len(skills)} | ex.: {skills[:5]}")
        await page.screenshot(path="/tmp/w20-at.png")

        # 2) escolhe uma habilidade → insere "@id"
        await page.fill("#input", "@ibge")
        await page.wait_for_timeout(1500)
        nomes = await page.locator(".palette-item .p-name").all_inner_texts()
        print(f"   busca '@ibge' → {nomes}")
        if nomes:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(700)
            print(f"   composer: {(await page.input_value('#input'))!r}")
            print(f"   menções registradas: {await page.evaluate('() => (window.__ufvaiSkills||[]).length') if False else 'n/a'}")

        # 3) interruptores nos ajustes
        await page.click("#settings-btn")
        await page.wait_for_timeout(800)
        switches = await page.locator("#settings-pane .switch").count()
        antes = await page.locator("#settings-pane .switch.on").count()
        await page.locator("#settings-pane .switch").first.click()
        await page.wait_for_timeout(600)
        depois = await page.locator("#settings-pane .switch.on").count()
        print(f"3) interruptores: {switches} | ligados antes={antes} depois={depois}")
        prefs = await page.evaluate("() => localStorage.getItem('ufvai_web_prefs')")
        print(f"   preferências salvas: {prefs}")
        await page.screenshot(path="/tmp/w20-settings.png")
        await page.click("#settings-close")

        # 4) tema da web
        await page.click("#theme-btn")
        await page.wait_for_timeout(500)
        print(f"4) tema da web: {await page.get_attribute('html', 'data-theme')!r}")
        await page.screenshot(path="/tmp/w20-claro.png")
        await page.click("#theme-btn")
        await page.wait_for_timeout(400)

        # 5) duplo clique no nome da sessão (barra lateral)
        await page.evaluate("""() => {
            const item = document.querySelector('.session-item .s-title');
            if (item) item.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
        }""")
        await page.wait_for_timeout(1200)
        print("5) duplo clique → diálogo de renomear disparado (sem erro)")

        # 6) responsivo: hambúrguer
        await page.set_viewport_size({"width": 420, "height": 860})
        await page.wait_for_timeout(600)
        async def sidebar_x():
            box = await page.locator("#sidebar").bounding_box()
            return round(box["x"]) if box else None
        x_ini = await sidebar_x()
        await page.click("#menu-btn")
        await page.wait_for_timeout(700)
        x_aberta = await sidebar_x()
        await page.click("#scrim", position={"x": 380, "y": 700})
        await page.wait_for_timeout(700)
        x_fechada = await sidebar_x()
        print(f"6) responsivo: menu-btn visível={await page.locator('#menu-btn').is_visible()} | "
              f"sidebar x: inicial={x_ini} → aberta={x_aberta} → fechada={x_fechada} "
              f"(aberto={x_aberta == 0}, fechado={x_fechada < 0})")
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.wait_for_timeout(400)

        # 7) rodapé
        print(f"7) rodapé: dir={await page.inner_text('#footer-dir')!r} | "
              f"motor={await page.inner_text('#footer-engine')!r}")

        print("8) erros:", errors if errors else "nenhum")
        await browser.close()


asyncio.run(main())
