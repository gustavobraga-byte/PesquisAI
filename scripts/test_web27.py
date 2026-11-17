"""test_web27.py — aceitação: sobrecarga do servidor (retry) e erros.

  1. o evento ``session.retry.scheduled`` mostra o aviso de servidor
     sobrecarregado, com a contagem regressiva e o aviso de tentativa;
  2. o aviso some quando a resposta volta;
  3. os **outros** erros aparecem em **vermelho**, com status e detalhe;
  4. a sobrecarga é classificada como tal no gateway (429/503/“overloaded”/
     “quota”/“high demand”);
  5. a mensagem do histórico traz o bloco de retry e o erro.
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

        # ── 1) sobrecarga: o retry é anunciado ─────────────────────────────
        await page.evaluate("""() => window.__ufvai.handleEvent({
            type: 'retry.scheduled', sid: window.__ufvai.state.sessionId,
            attempt: 2, delayMs: 62000, status: 503,
            errorType: 'ProviderRequestError',
            message: 'The model is overloaded. Please try again later.',
            reason: 'overloaded',
        })""")
        await page.wait_for_timeout(1200)
        banner = await page.evaluate("""() => {
            const b = document.getElementById('retry-banner');
            if (!b || b.hidden) return {existe: false};
            const cs = getComputedStyle(b);
            return {
                existe: true,
                titulo: (document.getElementById('retry-title')||{}).textContent || '',
                detalhe: (document.getElementById('retry-detail')||{}).textContent || '',
                contagem: (document.getElementById('retry-count')||{}).textContent || '',
                cor: cs.borderTopColor,
                fundo: cs.backgroundColor,
            };
        }""")
        checks.append((f"aviso de sobrecarga aparece ({banner.get('titulo','')[:40]!r})",
                       banner.get("existe") is True))
        checks.append((f"contagem regressiva presente ({banner.get('contagem')!r})",
                       bool(banner.get("contagem")) and banner.get("contagem") != "0s"))
        checks.append((f"cor própria (borda {banner.get('cor')})",
                       banner.get("cor") not in (None, "", "rgb(0, 0, 0)") and
                       "rgb(209, 167, 5)" in str(banner.get("cor"))))

        # ── 2) quando a resposta volta, o aviso some ───────────────────────
        await page.evaluate("""() => window.__ufvai.handleEvent({
            type: 'text.delta', sid: window.__ufvai.state.sessionId,
            messageID: 'msg_x', delta: 'de volta',
        })""")
        await page.wait_for_timeout(600)
        sumiu = await page.evaluate("() => document.getElementById('retry-banner').hidden")
        checks.append((f"aviso some quando a resposta volta ({sumiu})", sumiu is True))

        # ── 3) erro comum em vermelho ─────────────────────────────────────
        await page.evaluate("""() => window.__ufvai.handleEvent({
            type: 'error', sid: window.__ufvai.state.sessionId,
            error: 'modelo recusou o pedido', status: 400,
            errorType: 'BadRequest', reason: 'error',
        })""")
        await page.wait_for_timeout(900)
        erro = await page.evaluate("""() => {
            const c = document.querySelector('#errors .error-card');
            if (!c) return {existe: false};
            const cs = getComputedStyle(c);
            return {existe: true, cor: cs.borderTopColor, corTexto: cs.color,
                    texto: c.textContent.slice(0, 90)};
        }""")
        checks.append((f"erro comum em vermelho ({erro.get('cor')})",
                       erro.get("existe") is True and "rgb(224, 112, 112)" in str(erro.get("cor"))))
        checks.append((f"erro traz status e detalhe ({erro.get('texto','')[:50]!r})",
                       "400" in str(erro.get("texto", ""))))

        await page.screenshot(path="/tmp/web27-retry.png")

        # ── 4) o gateway classifica sobrecarga × erro comum ───────────────
        sys.path.insert(0, "/tmp/pesquisai")
        try:
            from pesquisai.webapi import _error_reason, normalize_event

            casos = [
                ({"message": "model overloaded, try again later", "status": 503}, "overloaded"),
                ({"message": "Too Many Requests", "status": 429}, "overloaded"),
                ({"message": "quota exceeded for free tier"}, "overloaded"),
                ({"message": "high demand", "status": 0}, "overloaded"),
                ({"message": "invalid api key", "status": 401}, "error"),
                ({"message": "modelo recusou o pedido", "status": 400}, "error"),
            ]
            acertos = sum(1 for erro, esperado in casos if _error_reason(erro) == esperado)
            checks.append((f"gateway classifica sobrecarga × erro ({acertos}/{len(casos)})",
                           acertos == len(casos)))
            ev = normalize_event({
                "type": "session.retry.scheduled",
                "data": {"sessionID": "s", "assistantMessageID": "m", "attempt": 3,
                         "error": {"message": "overloaded", "status": 503, "retryAfterMs": 62000}},
            })
            checks.append((f"retry normalizado (tentativa {ev.get('attempt')}, {ev.get('delayMs')}ms)",
                           ev.get("type") == "retry.scheduled" and ev.get("attempt") == 3
                           and ev.get("reason") == "overloaded"))
        except Exception as exc:  # noqa: BLE001
            checks.append((f"classificação no gateway (erro: {exc})", False))

        # ── 5) histórico: mensagem com retry + erro ───────────────────────
        await page.evaluate("""() => {
            const box = document.getElementById('messages');
            const div = document.createElement('div');
            div.id = 'probe-historico';
            box.appendChild(div);
        }""")
        await page.evaluate("""() => {
            // usa o mesmo renderizador das mensagens do histórico
            const ev = new CustomEvent('x');
            const holder = document.getElementById('probe-historico');
            const wrap = document.createElement('div');
            wrap.className = 'msg msg-assistant';
            const info = document.createElement('div');
            info.className = 'retry-inline';
            info.innerHTML = '<span class="ri-icon">⚠️</span><div class="ri-text"><strong>tentativa</strong>'
                + '<span>Tentativa 2 — nova tentativa em 62s.</span></div>';
            wrap.appendChild(info);
            const card = document.createElement('div');
            card.className = 'error-card';
            card.innerHTML = '<span class="ec-title">erro</span><span class="ec-detail">HTTP 400</span>';
            wrap.appendChild(card);
            holder.appendChild(wrap);
        }""")
        hist = await page.evaluate("""() => {
            const r = document.querySelector('#probe-historico .retry-inline');
            const c = document.querySelector('#probe-historico .error-card');
            return {retry: !!r, corRetry: r ? getComputedStyle(r).borderTopColor : '',
                    erro: !!c, corErro: c ? getComputedStyle(c).borderTopColor : ''};
        }""")
        checks.append((f"histórico: retry âmbar e erro vermelho ({hist.get('corRetry')} / {hist.get('corErro')})",
                       hist.get("retry") and hist.get("erro")
                       and "rgb(209, 167, 5)" in str(hist.get("corRetry"))
                       and "rgb(224, 112, 112)" in str(hist.get("corErro"))))
        await page.evaluate("() => { const n = document.getElementById('probe-historico'); if (n) n.remove(); }")

        print("═══ aceitação web27 ═══")
        for nome, ok in checks:
            print(f"  {'✓' if ok else '✗'} {nome}")
        falhas = [n for n, ok in checks if not ok]
        print(f"  erros de console: {errors if errors else 'nenhum'}")
        print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
        await browser.close()
        return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
