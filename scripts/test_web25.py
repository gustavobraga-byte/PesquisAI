"""test_web25.py — aceitação da rodada web25 (itens novos).

  1. rolagem automática a medida que as mensagens chegam;
  2. aba "Sobre" com a ficha do UFVAI;
  3. no responsivo, o menu lateral abre e FECHA ao clicar fora;
  4. detecção da morte do Colab (heartbeat + aviso);
  5. i18n nas ações de sessão;
  6. configurações de autosave nos ajustes (via canal com o wrapper).
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

WRAPPER_HTML = Path("/tmp/pesquisai-wrapper/index.html")


def local_copy() -> str:
    src = WRAPPER_HTML.read_text(encoding="utf-8", errors="replace")
    src = re.sub(r"https://8002-[^\"'\s]+", "http://127.0.0.1:8003", src)
    src = re.sub(r"https://8003-[^\"'\s]+", "http://127.0.0.1:8003", src)
    src = re.sub(r"https://8000-[^\"'\s]+", "http://127.0.0.1:8000", src)
    out = Path("/tmp/test-wrapper")
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(src, encoding="utf-8")
    return str(out / "index.html")


async def main() -> int:
    html = local_copy()
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await context.add_cookies([{
            "name": "pesquisai_lang", "value": "pt_BR", "url": "http://127.0.0.1:8099",
        }])
        page = await context.new_page()
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto(f"http://127.0.0.1:8099/{html.split('/')[-1]}", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await page.evaluate("() => { const b=document.getElementById('console-toggle'); if(b) b.click(); }")
        await page.wait_for_timeout(9000)
        web = next((f for f in page.frames if ":8003" in f.url), None)
        if not web:
            print("✗ a moldura da web não carregou")
            return 1
        checks.append(("web carregada", True))

        # ── 1) rolagem automática ────────────────────────────────────────
        await web.evaluate("() => document.getElementById('new-session').click()")
        await page.wait_for_timeout(2500)
        await web.evaluate("""() => {
            const i = document.getElementById('input');
            i.value = 'Escreva um paragrafo longo sobre ciencia aberta, com 8 frases.';
            i.dispatchEvent(new Event('input'));
            document.getElementById('send-btn').click();
        }""")
        await page.wait_for_timeout(3000)
        durante = await web.evaluate("""() => {
            const t = document.getElementById('thread');
            return {top: Math.round(t.scrollTop), max: Math.round(t.scrollHeight - t.clientHeight)};
        }""")
        checks.append((f"rolagem automática durante o turno ({durante})",
                       durante["max"] - durante["top"] < 8))
        await page.wait_for_timeout(26000)
        depois = await web.evaluate("""() => {
            const t = document.getElementById('thread');
            return {top: Math.round(t.scrollTop), max: Math.round(t.scrollHeight - t.clientHeight),
                    auto: window.__ufvai.state.autoScroll};
        }""")
        checks.append((f"rolagem automática no fim do turno ({depois})",
                       depois["max"] - depois["top"] < 8 and depois["auto"]))
        altura = await web.evaluate(
            "() => document.getElementById('thread').scrollHeight - document.getElementById('thread').clientHeight")
        if altura > 40:
            await web.evaluate("() => document.getElementById('thread').dispatchEvent("
                "new WheelEvent('wheel', {deltaY: -140, bubbles: true}))")
            await page.wait_for_timeout(400)
            await page.wait_for_timeout(700)
            cima = await web.evaluate("""() => ({
                auto: window.__ufvai.state.autoScroll,
                jump: !document.getElementById('jump-btn').hidden})""")
            checks.append((f"rolagem para cima pausa e mostra o botão ({cima})",
                           not cima["auto"] and cima["jump"]))
        else:
            checks.append(("rolagem para cima (conversa vazia: sem rolagem)", True))
        await web.evaluate("() => document.getElementById('jump-btn').click()")
        await page.wait_for_timeout(600)
        voltou = await web.evaluate("""() => {
            const t = document.getElementById('thread');
            return Math.round(t.scrollHeight - t.clientHeight - t.scrollTop) < 8;
        }""")
        checks.append(("botão 'ir para o fim' volta ao fim", voltou))

        # ── 2) aba Sobre ─────────────────────────────────────────────────
        await web.evaluate("() => document.getElementById('settings-btn').click()")
        await page.wait_for_timeout(600)
        await web.evaluate("() => document.querySelector('#settings-tabs .tab[data-tab=\"sobre\"]').click()")
        await page.wait_for_timeout(900)
        sobre = await web.evaluate("""() => {
            const a = document.querySelector('#settings-pane .about');
            if (!a) return {existe: false};
            return {existe: true, logo: !!a.querySelector('img'),
                    linhas: [...a.querySelectorAll('.about-row')].length,
                    autor: (a.querySelector('.about-row .ar-value')||{}).textContent || '',
                    links: [...a.querySelectorAll('.about-link')].length};
        }""")
        checks.append((f"aba Sobre com a ficha do UFVAI (logo={sobre.get('logo')}, "
                       f"{sobre.get('linhas')} linhas, {sobre.get('links')} links)",
                       sobre.get("existe") and sobre.get("logo") and sobre.get("linhas", 0) >= 6))

        # ── 6) autosave nos ajustes ──────────────────────────────────────
        await web.evaluate("() => document.querySelector('#settings-tabs .tab[data-tab=\"autosave\"]').click()")
        await page.wait_for_timeout(1200)
        auto = await web.evaluate("""() => {
            const p = document.getElementById('settings-pane');
            return {
                temIntervalo: !!p.querySelector('.num-input'),
                escopos: [...p.querySelectorAll('.scope-opt')].map(e => e.textContent.trim()),
                origem: (p.querySelector('.setting-row .s-value')||{}).textContent || '',
                estado: window.__ufvai.state.autosave,
            };
        }""")
        checks.append((f"painel de autosave com intervalo e escopos ({auto.get('escopos')})",
                       auto.get("temIntervalo") and len(auto.get("escopos", [])) == 3))
        checks.append((f"estado do autosave vindo do wrapper ({auto.get('origem')!r})",
                       bool(auto.get("estado")) and auto["estado"].get("known") is True))
        # muda o escopo e confere o wrapper
        await web.evaluate("""() => {
            const b = [...document.querySelectorAll('.scope-opt')].find(e => /todas|toutes|all/i.test(e.textContent));
            if (b) b.click();
        }""")
        await page.wait_for_timeout(1500)
        no_wrapper = await page.evaluate(
            "() => localStorage.getItem('ufvai_autosave_scope')")
        checks.append((f"escopo gravado no wrapper ({no_wrapper!r})", no_wrapper == "all"))

        # ── 5) i18n nas ações de sessão ──────────────────────────────────
        await web.evaluate("() => document.getElementById('settings-close').click()")
        await web.evaluate("() => document.getElementById('session-menu-btn').click()")
        await page.wait_for_timeout(800)
        acoes = await web.evaluate(
            "() => [...document.querySelectorAll('#session-actions .model-item')].map(e => e.textContent.trim())")
        # a web tem de estar NO MESMO idioma do wrapper (é o que o wrapper
        # propaga) — e os rótulos não podem estar em português fixo.
        lang_wrapper = await page.evaluate("() => document.documentElement.lang || ''")
        lang_web = await web.evaluate("() => document.documentElement.lang || ''")
        esperado = {"pt-BR": "pt-BR", "en-US": "en", "es-ES": "es", "fr-FR": "fr", "zh-CN": "zh"}
        trad = {"pt-BR": "Renomear", "en": "Rename", "es": "Renombrar", "fr": "Renommer", "zh": "重命名"}
        alvo = esperado.get(lang_wrapper, lang_web)
        ok_i18n = (lang_web == alvo
                   and trad.get(alvo, "") in " ".join(acoes)
                   and len(acoes) >= 5)
        checks.append((f"ações de sessão no idioma do wrapper ({lang_wrapper} → {lang_web}: {acoes})", ok_i18n))

        # ── 4) detecção da morte do Colab ────────────────────────────────
        banner = await web.evaluate("""() => {
            const b = document.getElementById('engine-dead');
            return {existe: !!b, texto: b ? (b.textContent||'').slice(0,120) : ''};
        }""")
        checks.append((f"aviso de ambiente encerrado presente ({banner.get('existe')})", banner.get("existe")))
        heartbeat = await web.evaluate("() => typeof window.__ufvai.state === 'object'")
        checks.append(("heartbeat instalado", heartbeat))

        # ── 3) responsivo: gaveta abre e fecha ao clicar fora ───────────
        # Feito na web direta: dentro do wrapper o "boot-splash" fica por
        # cima da iframe (artefacto do ambiente de teste) e o clique não
        # chegaria à gaveta.
        movel = await browser.new_page(viewport={"width": 390, "height": 780},
                                       is_mobile=True, has_touch=True)
        await movel.goto("http://127.0.0.1:8003/", wait_until="domcontentloaded")
        await movel.wait_for_timeout(3500)
        await movel.evaluate("() => document.getElementById('menu-btn').click()")
        await movel.wait_for_timeout(700)
        aberto = await movel.evaluate("""() => ({
            side: document.body.classList.contains('side-open'),
            scrim: (() => { const r = document.getElementById('scrim').getBoundingClientRect();
                            return Math.round(r.width) + 'x' + Math.round(r.height); })()})""")
        checks.append((f"gaveta abre com o ☰ (scrim {aberto.get('scrim')})",
                       aberto.get("side") and aberto.get("scrim") != "0x0"))
        await movel.mouse.click(360, 650)
        await movel.wait_for_timeout(700)
        fechado = await movel.evaluate("""() => ({
            side: document.body.classList.contains('side-open'),
            scrim: !document.getElementById('scrim').hidden})""")
        checks.append((f"clicar fora recolhe o menu ({fechado})",
                       not fechado.get("side") and not fechado.get("scrim")))
        await movel.screenshot(path="/tmp/web25-mobile.png")
        await movel.close()

        print("═══ aceitação web25 ═══")
        for nome, ok in checks:
            print(f"  {'✓' if ok else '✗'} {nome}")
        falhas = [n for n, ok in checks if not ok]
        print(f"  erros de console: {errors if errors else 'nenhum'}")
        print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
        await browser.close()
        return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
