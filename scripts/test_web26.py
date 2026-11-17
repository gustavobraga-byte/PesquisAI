"""test_web26.py — aceitação do mini navegador de arquivos (web26).

  1. o botão abre o painel à direita (e fecha);
  2. navega pela pasta do agente (pastas e arquivos);
  3. visualizador mínimo: texto, imagem e suíte Office;
  4. download do arquivo;
  5. link para editar no Google Drive;
  6. segurança: nada fora da pasta do agente.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

WEB = "http://127.0.0.1:8003/"


async def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto(WEB, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)

        # ── 1) abrir / fechar ──────────────────────────────────────────────
        await page.click("#explorer-btn")
        await page.wait_for_timeout(2500)
        aberto = await page.evaluate("""() => ({
            visivel: !document.getElementById('explorer').hidden,
            colunas: getComputedStyle(document.querySelector('.app')).gridTemplateColumns,
            itens: document.querySelectorAll('.exp-item').length,
            caminho: (document.getElementById('exp-path')||{}).textContent,
        })""")
        checks.append((f"painel abre à direita ({aberto['colunas']})",
                       aberto["visivel"] and "360px" in aberto["colunas"]))
        checks.append((f"lista o conteúdo da pasta do agente ({aberto['itens']} itens)",
                       aberto["itens"] > 20 and aberto["caminho"] == "/"))

        # ── 2) navegar ─────────────────────────────────────────────────────
        await page.evaluate("""() => {
            const item = [...document.querySelectorAll('.exp-item')]
              .find(e => (e.querySelector('.exp-name')||{}).textContent === 'assets');
            if (item) item.click();
        }""")
        await page.wait_for_timeout(2000)
        nav = await page.evaluate("""() => ({
            caminho: (document.getElementById('exp-path')||{}).textContent,
            itens: document.querySelectorAll('.exp-item').length,
        })""")
        checks.append((f"navega para uma subpasta ({nav['caminho']}, {nav['itens']} itens)",
                       nav["caminho"].endswith("assets") and nav["itens"] > 0))

        # ── 3) prévia de imagem ────────────────────────────────────────────
        await page.evaluate("""() => {
            const item = [...document.querySelectorAll('.exp-item')]
              .find(e => (e.querySelector('.exp-name')||{}).textContent === 'logo.svg');
            if (item) item.click();
        }""")
        await page.wait_for_timeout(2500)
        prev = await page.evaluate("""() => {
            const img = document.querySelector('.exp-prev-image');
            return {
                imagem: !!img,
                src: img ? img.getAttribute('src') : '',
                nome: (document.querySelector('.exp-prev-name')||{}).textContent,
                acoes: [...document.querySelectorAll('.exp-prev-actions .mini-btn')]
                    .map(a => ({txt: a.textContent, href: a.getAttribute('href') || ''})),
            };
        }""")
        checks.append((f"prévia de imagem renderizada ({prev['nome']})",
                       prev["imagem"] and "inline=1" in prev["src"]))
        acoes = {a["txt"]: a["href"] for a in prev["acoes"]}
        checks.append((f"botão de download ({list(acoes)})",
                       any("download" in h for h in acoes.values())))
        checks.append(("link para o Google Drive",
                       any("drive.google.com" in h for h in acoes.values())))

        # ── 3b) prévia de texto ────────────────────────────────────────────
        await page.evaluate("""() => {
            const item = [...document.querySelectorAll('.exp-item')]
              .find(e => (e.querySelector('.exp-name')||{}).textContent === 'index.html');
            if (item) item.click();
        }""")
        await page.wait_for_timeout(2500)
        texto = await page.evaluate("""() => {
            const pre = document.querySelector('.exp-prev-text');
            return {tem: !!pre, chars: pre ? pre.textContent.length : 0};
        }""")
        checks.append((f"prévia de texto ({texto['chars']} caracteres)", texto["tem"] and texto["chars"] > 50))

        # ── 4) download responde ────────────────────────────────────────────
        dl = await page.evaluate("""async () => {
            const a = document.querySelector('.exp-prev-actions .mini-btn[download]');
            if (!a) return {ok: false};
            const r = await fetch(a.getAttribute('href'));
            return {ok: r.ok, status: r.status, tipo: r.headers.get('content-type')};
        }""")
        checks.append((f"download responde ({dl})", dl.get("ok") is True))

        # ── 5) fechar ───────────────────────────────────────────────────────
        await page.click("#exp-close")
        await page.wait_for_timeout(600)
        fechado = await page.evaluate("""() => ({
            visivel: !document.getElementById('explorer').hidden,
            corpo: document.body.classList.contains('explorer-open'),
        })""")
        checks.append((f"painel fecha ({fechado})",
                       not fechado["visivel"] and not fechado["corpo"]))

        # ── 6) segurança: nada fora da pasta do agente ────────────────────
        fora = await page.evaluate("""async () => {
            const r = await fetch('api/ufvai/explorer/preview?path=' +
                encodeURIComponent('../../etc/passwd'));
            const d = await r.json();
            return {erro: d.error || '', texto: d.text || ''};
        }""")
        checks.append((f"caminho fora da pasta é recusado ({fora.get('erro')!r})",
                       bool(fora.get("erro")) and "root" not in fora.get("texto", "")))

        await page.screenshot(path="/tmp/web26-final.png")
        print("═══ aceitação web26 ═══")
        for nome, ok in checks:
            print(f"  {'✓' if ok else '✗'} {nome}")
        falhas = [n for n, ok in checks if not ok]
        print(f"  erros de console: {errors if errors else 'nenhum'}")
        print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
        await browser.close()
        return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
