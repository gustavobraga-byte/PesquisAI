"""test_webui_web20b.py — tema pelo cabeçalho do UFVAI + menção de habilidade.

  1) o botão de tema do cabeçalho (wrapper) muda o tema da web (postMessage)
  2) a menção @habilidade vai no prompt como `skills` (chega ao motor)
"""

import asyncio, json, re, urllib.request, base64
from pathlib import Path
from playwright.async_api import async_playwright

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())


def engine(path):
    req = urllib.request.Request("http://127.0.0.1:49374" + path)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"opencode:{SERVICE['password']}".encode()).decode())
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


async def main():
    src = Path('/tmp/pesquisai-wrapper/index.html').read_text(encoding='utf-8', errors='replace')
    src = re.sub(r'https://8002-[^"\'\s]+', 'http://127.0.0.1:8002', src)
    src = re.sub(r'https://8003-[^"\'\s]+', 'http://127.0.0.1:8003', src)
    src = re.sub(r'https://8000-[^"\'\s]+', 'http://127.0.0.1:8000', src)
    Path('/tmp/test-wrapper').mkdir(exist_ok=True)
    Path('/tmp/test-wrapper/index.html').write_text(src, encoding='utf-8')

    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto("http://127.0.0.1:8099/index.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # alterna para a web
        await page.evaluate("() => { const b=document.getElementById('console-toggle'); if(b) b.click(); }")
        await page.wait_for_timeout(7000)
        web = next((f for f in page.frames if ":8003" in f.url), None)
        print("frame da web:", web.url if web else "(ausente)")
        if not web:
            return

        # 1) tema pelo cabeçalho do UFVAI
        tema_antes = await web.evaluate("() => document.documentElement.getAttribute('data-theme')")
        await page.evaluate("""() => {
            const btns = [...document.querySelectorAll('#topbar button, .tb-btn, [data-i18n="theme.toggle"]')];
            const b = btns.find(x => /tema|theme/i.test(x.getAttribute('aria-label') || x.title || x.textContent || ''));
            if (b) b.click();
        }""")
        await page.wait_for_timeout(1500)
        tema_depois = await web.evaluate("() => document.documentElement.getAttribute('data-theme')")
        print(f"1) tema: web antes={tema_antes!r} → depois do clique no cabeçalho={tema_depois!r} "
              f"(mudou={tema_antes != tema_depois})")

        # 2) menção de habilidade no prompt
        await web.evaluate("""() => {
            const i = document.getElementById('input');
            i.focus(); i.value = '@ibge-br';
            i.dispatchEvent(new Event('input'));
        }""")
        await page.wait_for_timeout(1600)
        await web.evaluate("() => document.querySelector('.palette-item').click()")
        await page.wait_for_timeout(900)
        await web.evaluate(
            "() => { const i = document.getElementById('input'); i.focus();"
            " i.value = '@ibge-br qual a populacao de Vicosa?';"
            " i.dispatchEvent(new Event('input')); }"
        )
        await page.wait_for_timeout(700)
        await web.evaluate("() => document.getElementById('send-btn').click()")
        await page.wait_for_timeout(7000)

        sid = await web.evaluate("() => (window.location.hash || '').replace('#','')")
        sessoes = engine("/api/session")["data"]
        alvo = sessoes[0]
        msgs = engine(f"/api/session/{alvo['id']}/message")["data"]
        ultimo = [m for m in msgs if m.get("type") == "user"][-1]
        payload = ultimo.get("payload") or {}
        print(f"2) prompt enviado: {json.dumps(payload, ensure_ascii=False)[:400]}")
        print(f"   skills no payload: {json.dumps(payload.get('skills'), ensure_ascii=False)}")
        print("3) erros:", errors if errors else "nenhum")
        await browser.close()


asyncio.run(main())
