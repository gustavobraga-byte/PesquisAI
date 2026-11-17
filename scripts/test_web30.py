#!/usr/bin/env python3
"""test_web30.py — aceitação da rodada web30.

  1. **caminho clicável** — arquivo, PASTA, caminho entre crases e caminho
     absoluto do Drive viram link e abrem no explorador;
  2. **botão de parar** sempre visível + atalho **Esc**;
  3. **indicador de atividade** — acende no envio, mostra o cronômetro,
     termina em "concluído" (verde) ou "interrompido" (vermelho);
  4. **sondagem do motor** — o indicador não depende só do SSE.
"""

from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"


async def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}")
                if m.type == "error" else None)
        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)

        # v0.7.11-web30: a teste roda numa sessão **factícia** — assim o
        # estado "active" do motor (que inclui a sessão real do agente que
        # executa este teste) não interfere no indicador.
        await page.evaluate("""() => {
            window.__ufvai.state.__sidReal = window.__ufvai.state.sessionId;
            window.__ufvai.state.sessionId = 'ses_teste_web30';
            window.__ufvai.setRunning(false);
        }""")
        await page.wait_for_timeout(500)

        # ── 1) caminhos viram link ───────────────────────────────────────
        caminhos = await page.evaluate("""() => {
            const box = document.createElement('div');
            box.className = 'answer';
            box.innerHTML = window.__ufvai.md(
                'Salvei em outputs-processo-seletivo/artigos e em '
                + '`vault/moc/last-state.md`. Também em '
                + '/content/drive/My Drive/PesquisAI/vault. Use e/ou e `npm run build`.');
            document.getElementById('messages').appendChild(box);
            const refs = [...box.querySelectorAll('a.file-ref')];
            return {
                quais: refs.map(r => r.getAttribute('data-file')),
                texto: box.textContent,
            };
        }""")
        quais = caminhos.get("quais") or []
        checks.append((f"caminho de PASTA vira link ({quais})",
                       "outputs-processo-seletivo/artigos" in quais))
        checks.append((f"caminho entre crases vira link ({quais})",
                       "vault/moc/last-state.md" in quais))
        checks.append((f"caminho absoluto do Drive vira link ({quais})",
                       any("/content/drive/My Drive/PesquisAI/vault" in q for q in quais)))
        checks.append(("'e/ou' NÃO vira link (falso positivo)",
                       not any("e/ou" in q for q in quais)))
        checks.append(("código que não é caminho NÃO vira link",
                       not any("npm run build" in q for q in quais)))

        # ── 1b) clique num caminho de PASTA abre a pasta no explorador ───
        await page.evaluate("""() => {
            const box = document.createElement('div');
            box.className = 'answer';
            box.innerHTML = window.__ufvai.md('Veja a pasta vault/moc do projeto.');
            document.getElementById('messages').appendChild(box);
            const ref = box.querySelector('a.file-ref');
            if (ref) ref.click();
        }""")
        await page.wait_for_timeout(4000)
        abriu = await page.evaluate("""() => ({
            aberto: !document.getElementById('explorer').hidden,
            caminho: (document.getElementById('exp-path')||{}).textContent || '',
            itens: document.querySelectorAll('#exp-list .exp-item').length,
        })""")
        checks.append((f"clique na PASTA abre o explorador ({abriu.get('caminho')!r})",
                       bool(abriu.get("aberto")) and "moc" in (abriu.get("caminho") or "")))
        checks.append((f"a pasta listou itens ({abriu.get('itens')})",
                       int(abriu.get("itens") or 0) > 0))

        # ── 2) botão de parar sempre visível ────────────────────────────
        botao = await page.evaluate("""() => {
            const b = document.getElementById('stop-btn');
            return {
                hidden: b.hidden,
                display: getComputedStyle(b).display,
                live: b.classList.contains('live'),
                titulo: b.getAttribute('title'),
            };
        }""")
        checks.append((f"botão de parar sempre visível (hidden={botao.get('hidden')})",
                       not botao.get("hidden") and botao.get("display") != "none"))
        checks.append(("botão de parar apagado quando não há execução",
                       not botao.get("live")))

        # ── 3) indicador de atividade ───────────────────────────────────
        ativo = await page.evaluate("""async () => {
            window.__ufvai.setRunning(true);
            await new Promise(r => setTimeout(r, 1400));
            const node = document.getElementById('agent-busy');
            const spin = node.querySelector('.spin');
            const cs = getComputedStyle(spin);
            const out = {
                visivel: !node.hidden,
                animacao: cs.animationName,
                cor: cs.borderTopColor,
                texto: (node.querySelector('.busy-text')||{}).textContent || '',
                statusVisivel: !document.getElementById('status').hidden,
                statusTexto: (document.getElementById('status-text')||{}).textContent || '',
                stopLive: document.getElementById('stop-btn').classList.contains('live'),
            };
            return out;
        }""")
        checks.append((f"espiral global enquanto o agente trabalha ({ativo.get('cor')})",
                       bool(ativo.get("visivel")) and ativo.get("animacao") not in (None, "none")))
        checks.append((f"linha de status visível ({ativo.get('statusVisivel')})",
                       bool(ativo.get("statusVisivel"))))
        checks.append((f"cronômetro no indicador ({ativo.get('texto')!r})",
                       "s" in (ativo.get("texto") or "") and "·" in (ativo.get("texto") or "")))
        checks.append(("botão de parar acende durante a execução",
                       bool(ativo.get("stopLive"))))

        # ── 3b) fim do turno: "concluído" verde ─────────────────────────
        fim = await page.evaluate("""async () => {
            window.__ufvai.setRunning(false);
            await new Promise(r => setTimeout(r, 500));
            const node = document.getElementById('agent-busy');
            return {
                visivel: !node.hidden,
                feito: node.classList.contains('done'),
                texto: (node.querySelector('.busy-text')||{}).textContent || '',
            };
        }""")
        checks.append((f"fim do turno mostra 'concluído' ({fim.get('texto')!r})",
                       bool(fim.get("visivel")) and bool(fim.get("feito"))
                       and bool(fim.get("texto"))))

        # ── 3c) interrupção: "interrompido" vermelho ────────────────────
        parar = await page.evaluate("""async () => {
            const node = document.getElementById('agent-busy');
            window.__ufvai.setRunning(true);
            await new Promise(r => setTimeout(r, 300));
            window.__ufvai.state.stopping = true;
            window.__ufvai.setRunning(false);
            await new Promise(r => setTimeout(r, 400));
            const out = {
                visivel: !node.hidden,
                parou: node.classList.contains('stopped'),
                texto: (node.querySelector('.busy-text')||{}).textContent || '',
            };
            window.__ufvai.state.stopping = false;
            return out;
        }""")
        checks.append((f"parada mostra 'interrompido' ({parar.get('texto')!r})",
                       bool(parar.get("visivel")) and bool(parar.get("parou"))
                       and bool(parar.get("texto"))))

        # ── 4) Esc interrompe (chama /interrupt) ────────────────────────
        interceptadas: list[str] = []

        async def rota_interrupt(route):
            interceptadas.append(route.request.url)
            await route.fulfill(status=200, content_type="application/json",
                                body='{"ok": true, "interrupted": true}')

        await page.route("**/api/ufvai/sessions/*/interrupt", rota_interrupt)
        await page.evaluate("""async () => {
            window.__ufvai.setRunning(true);
            await new Promise(r => setTimeout(r, 300));
        }""")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1500)
        checks.append((f"Esc interrompe a execução ({len(interceptadas)} chamada(s))",
                       len(interceptadas) >= 1))
        estado = await page.evaluate("""() => ({
            parando: window.__ufvai.state.stopping,
            texto: (document.querySelector('#agent-busy .busy-text')||{}).textContent || '',
        })""")
        checks.append((f"estado 'interrompendo' na tela ({estado.get('texto')!r})",
                       bool(estado.get("parando")) or "interrompendo" in (estado.get("texto") or "")))

        # ── 5) a sondagem do motor acende o indicador (sem SSE) ─────────
        sid = await page.evaluate("() => window.__ufvai.state.sessionId || ''")
        if sid:
            async def rota_sessions(route):
                corpo = route.request.post_data
                if corpo:
                    await route.fulfill(status=200, content_type="application/json",
                                        body=corpo.decode("utf-8"))
                else:
                    await route.fulfill(
                        status=200, content_type="application/json",
                        body='{"sessions": [], "active": {"%s": {"type": "running"}}}' % sid)

            await page.route("**/api/ufvai/sessions", rota_sessions)
            await page.evaluate("""async () => {
                window.__ufvai.setRunning(false);
                await new Promise(r => setTimeout(r, 300));
                await window.__ufvai.sondaAtividade();
            }""")
            await page.wait_for_timeout(600)
            sondou = await page.evaluate("""() => ({
                rodando: window.__ufvai.state.running,
                visivel: !document.getElementById('agent-busy').hidden,
            })""")
            checks.append((f"sondagem do motor acende o indicador ({sondou.get('rodando')})",
                           bool(sondou.get("rodando")) and bool(sondou.get("visivel"))))
            await page.unroute("**/api/ufvai/sessions")
        else:
            checks.append(("sondagem do motor acende o indicator (sem sessão)", False))

        # ── 6) comando "/parar" na paleta ───────────────────────────────
        paleta = await page.evaluate("""() => {
            const inp = document.getElementById('input');
            inp.focus();
            inp.value = '/par';
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            return new Promise(resolve => setTimeout(() => {
                const itens = [...document.querySelectorAll('#palette-list .palette-item')]
                    .map(n => n.textContent || '');
                resolve({itens, visivel: !document.getElementById('palette').hidden});
            }, 900));
        }""")
        itens = paleta.get("itens") or []
        checks.append((f"paleta traz o comando de parar ({len(itens)} item(ns))",
                       any("parar" in (i or "").lower() or "stop" in (i or "").lower()
                           or "arrêter" in (i or "").lower() for i in itens)))
        # o comando da web executa a parada
        antes = len(interceptadas)
        executar = await page.evaluate("""async () => {
            const inp = document.getElementById('input');
            inp.value = '/parar';
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            await new Promise(r => setTimeout(r, 800));
            const item = [...document.querySelectorAll('#palette-list .palette-item')]
                .find(n => (n.textContent || '').includes('parar'));
            if (!item) return {achou: false};
            item.click();
            await new Promise(r => setTimeout(r, 800));
            return {
                achou: true,
                toast: (document.getElementById('toast')||{}).textContent || '',
            };
        }""")
        checks.append((f"o comando '/parar' aciona a parada "
                       f"({len(interceptadas) - antes} chamada(s))",
                       bool(executar.get("achou")) and len(interceptadas) > antes))
        await page.unroute("**/api/ufvai/sessions/*/interrupt")

        # restaura a sessão real
        await page.evaluate("""() => {
            if (window.__ufvai.state.__sidReal) {
                window.__ufvai.state.sessionId = window.__ufvai.state.__sidReal;
            }
        }""")

        await browser.close()

    print("═══ aceitação web30 ═══")
    for nome, ok in checks:
        print(f"  {'✓' if ok else '✗'} {nome}")
    if errors:
        print("  erros de console:")
        for e in errors[:10]:
            print("   ", e)
    else:
        print("  erros de console: nenhum")
    ok = sum(1 for _, o in checks if o)
    print(f"  resultado: {ok}/{len(checks)} ok")
    return 0 if ok == len(checks) and not errors else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
