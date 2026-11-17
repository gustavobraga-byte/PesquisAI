"""test_status_running.py — o status "Trabalhando…" some ao final do turno?

Cria uma sessão nova pela própria interface, envia uma mensagem e acompanha o
estado do indicador de execução (visível → oculto) e o fim do turno no motor.
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"


async def main():
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # sessão nova (idle) — evita o enfileiramento no meio de outro turno
        await page.evaluate("() => document.getElementById('new-session').click()")
        await page.wait_for_timeout(2500)
        sid = await page.evaluate("() => (window.__sid || '')")
        print("sessão:", await page.inner_text("#session-title"))

        await page.fill("#input", "Responda apenas com a palavra: FIM")
        await page.evaluate("() => document.getElementById('send-btn').click()")

        # amostra o estado do indicador a cada 500 ms
        amostras = []
        for i in range(60):
            visivel = await page.locator("#status").is_visible()
            estado = await page.evaluate(
                """() => {
                    const s = document.getElementById('status-text');
                    return s ? s.textContent : '';
                }"""
            )
            amostras.append((round(i * 0.5, 1), visivel, estado))
            if not visivel and i > 3:
                break
            await page.wait_for_timeout(500)

        mudou = [a for a in amostras if a[1]]
        print(f"1) 'Trabalhando…' visível em: {[a[0] for a in mudou][:20]} s")
        print(f"   último estado: {amostras[-1]}")
        print(f"2) estado final: visível={amostras[-1][1]} | texto={amostras[-1][2]!r}")

        # o motor terminou o turno?
        sessoes = await page.evaluate(
            """async () => {
                const r = await fetch('api/ufvai/sessions');
                const d = await r.json();
                return d.sessions.map(s => ({id: s.id, busy: s.busy, updated: s.updated}));
            }"""
        )
        print("3) sessões (busy/updated):", sessoes[:3])

        await page.screenshot(path="/tmp/status-final.png")
        print("4) erros:", errors if errors else "nenhum")
        await browser.close()


asyncio.run(main())
