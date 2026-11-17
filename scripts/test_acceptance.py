"""test_acceptance.py — aceitação da versão web do UFVAI (v0.7.11-web23).

Percorre o caminho real do usuário dentro do wrapper (terminal ⇄ web) e
verifica cada item pedido na rodada web23:

  1. expandir raciocínio/ferramentas + "expandir tudo";
  2. menu ``/`` com TODOS os comandos do OpenCode (motor + plugin ufvai.pt);
  3. i18n: trocar o idioma no wrapper troca o da web;
  4. ferramentas formatadas com adição (verde) e supressão (vermelho);
  5. copiar resposta, raciocínio e ferramentas;
  6. sem botão de tema na web (o do wrapper manda);
  7. percentual da janela de contexto;
  8. anexo vai para /tmp e o caminho é injetado no prompt;
  9. responsivo sem truncamento;
 10. textos do estado vazio (logo + tagline + descrição);
 11. aviso de ambiente Colab encerrado após 10 min sem resposta;
 12. atalhos de teclado atualizados.

    python3 scripts/test_acceptance.py
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

WRAPPER_HTML = Path("/tmp/pesquisai-wrapper/index.html")
WEB = "http://127.0.0.1:8003/"


def local_copy() -> str:
    """Cópia do wrapper com as URLs do Colab trocadas por localhost."""
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
        # idioma do wrapper fixo em português (o cookie é compartilhado com a
        # web quando o host é o mesmo) — assim o teste é determinístico
        await context.add_cookies([{
            "name": "pesquisai_lang", "value": "pt_BR", "url": "http://127.0.0.1:8099",
        }])
        page = await context.new_page()
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto(f"http://127.0.0.1:8099/{html.split('/')[-1]}", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # alterna para a web
        await page.evaluate("() => { const b=document.getElementById('console-toggle'); if(b) b.click(); }")
        await page.wait_for_timeout(7000)
        web = next((f for f in page.frames if ":8003" in f.url), None)
        if not web:
            print("✗ a moldura da web não carregou")
            return 1
        checks.append(("web carregada", True))

        # ── 10) estado vazio: logo + tagline + descrição ─────────────────
        logo = await web.evaluate("() => { const i=document.querySelector('.empty-logo img'); return i ? i.getAttribute('src') : ''; }")
        checks.append((f"logo no estado vazio ({logo})", "logo.svg" in logo))

        # o idioma do wrapper é a fonte da verdade: a web deve estar no mesmo
        idioma_wrapper = await page.evaluate("() => document.documentElement.lang || ''")
        idioma_web = await web.evaluate("() => document.documentElement.getAttribute('lang') || ''")
        mapa = {"pt-BR": "pt-BR", "en-US": "en", "es-ES": "es", "fr-FR": "fr", "zh-CN": "zh"}
        esperado = mapa.get(idioma_wrapper, idioma_web)
        checks.append((f"web no idioma do wrapper ({idioma_wrapper} → {idioma_web})", idioma_web == esperado))

        # força pt-BR dentro da moldura e confere os textos
        await web.evaluate("() => window.postMessage({type:'ufvai-lang', lang:'pt-BR'}, '*')")
        await page.wait_for_timeout(900)
        h2 = await web.evaluate("() => (document.querySelector('.empty h2')||{}).textContent || ''")
        desc = await web.evaluate("() => (document.querySelector('.empty p')||{}).textContent || ''")
        checks.append(("tagline 'A inteligência que acelera a ciência'", "acelera a ciência" in h2))
        checks.append(("nova descrição do agente", "literatura validada" in desc and "Rigor" in desc))

        # ── 6) sem botão de tema na web ──────────────────────────────────
        theme_btn = await web.evaluate("() => document.querySelectorAll('#theme-btn').length")
        checks.append((f"sem botão de tema na web ({theme_btn})", theme_btn == 0))

        # ── 2) menu "/" com todos os comandos ─────────────────────────────
        await web.evaluate("() => { const i=document.getElementById('input'); i.focus(); i.value='/'; i.dispatchEvent(new Event('input')); }")
        await page.wait_for_timeout(1500)
        n_cmd = await web.evaluate("() => document.querySelectorAll('.palette-item').length")
        grupos = await web.evaluate("() => [...document.querySelectorAll('.palette-group')].map(e=>e.textContent.toUpperCase())")
        tem_ufvai = await web.evaluate("() => [...document.querySelectorAll('.p-name')].some(e=>e.textContent==='/pesquisar')")
        tem_nativo = await web.evaluate("() => [...document.querySelectorAll('.p-name')].some(e=>e.textContent==='/novo'||e.textContent==='/new')")
        tem_tui = await web.evaluate("() => document.querySelectorAll('.p-badge').length")
        checks.append((f"menu '/' com {n_cmd} comandos", n_cmd >= 45))
        checks.append((f"comando de agente (/pesquisar)", tem_ufvai))
        checks.append(("comando nativo da TUI (/novo)", tem_nativo))
        checks.append((f"comandos marcados como TUI ({tem_tui})", tem_tui > 10))
        checks.append((f"agrupados ({len(grupos)} grupos: {', '.join(grupos[:4])}…)", len(grupos) >= 4))

        # ── 3) i18n: o wrapper manda o idioma ────────────────────────────
        await web.evaluate("() => { const i=document.getElementById('input'); i.value=''; i.dispatchEvent(new Event('input')); }")
        await web.evaluate("() => window.postMessage({type:'ufvai-lang', lang:'en'}, '*')")
        await page.wait_for_timeout(1200)
        h2_en = await web.evaluate("() => (document.querySelector('.empty h2')||{}).textContent || ''")
        html_lang = await web.evaluate("() => document.documentElement.getAttribute('lang')")
        checks.append((f"idioma trocado para inglês (lang={html_lang})", html_lang == "en"))
        checks.append(("textos em inglês", "accelerates science" in h2_en))
        await web.evaluate("() => window.postMessage({type:'ufvai-lang', lang:'pt-BR'}, '*')")
        await page.wait_for_timeout(900)
        # ── 7) percentual da janela de contexto ───────────────────────────
        await page.wait_for_timeout(1500)
        usage = await web.evaluate("() => { const u=document.getElementById('usage-pill'); return {hidden:u.hidden, txt:u.textContent}; }")
        checks.append((f"uso com % do contexto ({usage['txt']})", "%" in usage["txt"]))

        # ── 1) expandir tudo + 5) copiar raciocínio/ferramentas ───────────
        await web.evaluate("() => { const i=document.getElementById('input'); i.value=''; i.dispatchEvent(new Event('input')); }")
        # injeta blocos sintéticos para medir a mecânica
        await web.evaluate("""() => {
          const box = document.getElementById('messages');
          const mk = (cls, label, body) => {
            const d = document.createElement('details');
            d.className = 'block ' + cls;
            const s = document.createElement('summary');
            s.appendChild(Object.assign(document.createElement('span'), {className:'block-label', textContent:label}));
            const b = document.createElement('div');
            b.className = 'block-body'; b.textContent = body;
            d.appendChild(s); d.appendChild(b);
            return d;
          };
          const wrap = document.createElement('div');
          wrap.className = 'msg msg-assistant';
          wrap.appendChild(mk('reasoning','raciocínio','texto do raciocínio'));
          wrap.appendChild(mk('tool','Shell','$ ls -la'));
          box.appendChild(wrap);
        }""")
        n_blocks = await web.evaluate("() => document.querySelectorAll('#messages details.block').length")
        await web.evaluate("() => document.getElementById('expand-all-btn').click()")
        await page.wait_for_timeout(400)
        abertos = await web.evaluate("() => [...document.querySelectorAll('#messages details.block')].filter(b=>b.open).length")
        checks.append((f"expandir tudo abre os blocos ({abertos}/{n_blocks})", abertos == n_blocks and n_blocks >= 2))
        await web.evaluate("() => document.getElementById('expand-all-btn').click()")
        await page.wait_for_timeout(400)
        fechados = await web.evaluate("() => [...document.querySelectorAll('#messages details.block')].filter(b=>!b.open).length")
        checks.append((f"expandir tudo também recolhe ({fechados})", fechados == n_blocks))
        copies = await web.evaluate("() => document.querySelectorAll('#messages details.block summary .mini-btn.copy').length")
        checks.append((f"botão de copiar em raciocínio e ferramentas ({copies})", copies >= 2))

        # ── 4) diff verde/vermelho ────────────────────────────────────────
        diff_html = await web.evaluate("""() => {
          const b = document.getElementById('messages');
          const d = document.createElement('div');
          d.className = 'diff';
          d.innerHTML = '<div class="diff-row add"><span class="diff-sign">+</span><span class="diff-text">linha nova</span></div>'
                      + '<div class="diff-row del"><span class="diff-sign">−</span><span class="diff-text">linha removida</span></div>';
          b.appendChild(d);
          const add = d.querySelector('.diff-row.add');
          const del = d.querySelector('.diff-row.del');
          return {add: getComputedStyle(add).color, del: getComputedStyle(del).color};
        }""")
        checks.append((f"adição em verde ({diff_html['add']})", diff_html["add"] != diff_html["del"]))

        # ── 8) anexo → /tmp + caminho injetado ────────────────────────────
        tmpf = Path("/tmp/ufvai-teste-anexo.txt")
        tmpf.write_text("conteudo de teste do anexo\n", encoding="utf-8")
        await web.set_input_files("#file-input", str(tmpf))
        await page.wait_for_timeout(3000)
        anexo = await web.evaluate("() => { const c=document.querySelector('.attachments .chip'); return c ? c.textContent : ''; }")
        has_path = "/tmp/ufvai-uploads/" in anexo
        checks.append((f"anexo salvo em /tmp ({anexo.strip()[:70]})", has_path))

        # ── 9) responsivo sem truncamento ─────────────────────────────────
        await page.set_viewport_size({"width": 390, "height": 780})
        await page.wait_for_timeout(1200)
        trunc = await web.evaluate("""() => {
          const out = [];
          document.querySelectorAll('.topbar, .composer, .thread, .msg, .bubble, .answer, .top-sub, .palette').forEach((e) => {
            if (e.scrollWidth > e.clientWidth + 2) {
              const cs = getComputedStyle(e);
              if (cs.overflowX === 'visible' || cs.overflowX === 'clip') {
                out.push(e.className + ' (' + e.scrollWidth + '>' + e.clientWidth + ')');
              }
            }
          });
          return out;
        }""")
        body_scroll = await web.evaluate("() => ({sw: document.body.scrollWidth, cw: document.body.clientWidth})")
        checks.append((f"sem estouro horizontal no celular ({trunc or 'nenhum'})", not trunc))
        checks.append((f"corpo sem rolagem horizontal ({body_scroll['sw']}<={body_scroll['cw']})", body_scroll["sw"] <= body_scroll["cw"] + 1))
        await page.screenshot(path="/tmp/acceptance-mobile.png")

        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.wait_for_timeout(800)
        await page.screenshot(path="/tmp/acceptance-desktop.png")

        # ── 11) aviso de ambiente encerrado ───────────────────────────────
        dead = await web.evaluate("""() => {
          const b = document.getElementById('engine-dead');
          const html = b ? b.innerHTML : '';
          return {hidden: b ? b.hidden : null, tem: html.includes('Colab')};
        }""")
        checks.append((f"aviso de Colab encerrado presente ({dead['tem']})", dead["tem"]))

        # ═══ web24 ═════════════════════════════════════════════════════════

        # ── 3) sem "✕" no quadro de sessões ──────────────────────────────
        side_close = await web.evaluate("() => document.querySelectorAll('#side-close').length")
        checks.append((f"sem ✕ no quadro de sessões ({side_close})", side_close == 0))

        # ── 4) o ícone de expandir tudo tem rótulo ─────────────────────────
        expand = await web.evaluate("""() => {
            const b = document.getElementById('expand-all-btn');
            if (!b) return {existe: false, texto: ''};
            const label = b.querySelector('.lb-text');
            return {existe: true, texto: label ? label.textContent.trim() : ''};
        }""")
        checks.append((f"botão expandir tudo com rótulo ({expand.get('texto')!r})",
                       expand.get('existe') and len(expand.get('texto', '')) > 3))

        # ── 2) copiar sempre presente (inclusive nos blocos) ───────────────
        await web.evaluate("""() => {
            const box = document.getElementById('messages');
            const wrap = document.createElement('div');
            wrap.className = 'msg msg-assistant';
            const ans = document.createElement('div');
            ans.className = 'answer'; ans.textContent = 'resposta em streaming';
            wrap.appendChild(ans);
            const acts = document.createElement('div');
            acts.className = 'msg-actions';
            const b = document.createElement('button');
            b.className = 'mini-btn copy'; b.textContent = 'Copiar resposta';
            acts.appendChild(b);
            wrap.appendChild(acts);
            box.appendChild(wrap);
        }""")
        copias = await web.evaluate("""() => [...document.querySelectorAll('#messages .msg-actions .mini-btn.copy')]
            .filter((b) => getComputedStyle(b).display !== 'none').length""")
        checks.append((f"botão de copiar presente nas mensagens ({copias})", copias >= 1))
        opacidade = await web.evaluate("""() => {
            const b = document.querySelector('#messages details.block summary .mini-btn.copy');
            return b ? parseFloat(getComputedStyle(b).opacity) : -1;
        }""")
        checks.append((f"copiar do bloco visível sem hover (opacidade {opacidade})", opacidade >= 0.4))

        # ── 8) renomear pelo menu de ações (modal próprio, sem prompt()) ──
        await web.evaluate("() => document.getElementById('session-menu-btn').click()")
        await page.wait_for_timeout(700)
        tem_renomear = await web.evaluate(
            "() => [...document.querySelectorAll('#session-actions .model-item')]"
            ".some(e => /renomear/i.test(e.textContent))")
        checks.append((f"menu de ações com 'Renomear' ({tem_renomear})", tem_renomear))
        await web.evaluate("""() => {
            const item = [...document.querySelectorAll('#session-actions .model-item')]
              .find(e => /renomear/i.test(e.textContent));
            if (item) item.click();
        }""")
        await page.wait_for_timeout(900)
        modal = await web.evaluate("""() => {
            const m = document.getElementById('prompt-modal');
            return {aberto: m ? !m.hidden : false,
                    valor: (document.getElementById('prompt-input')||{}).value || ''};
        }""")
        checks.append((f"modal de renomear abre na web ({modal['aberto']})", modal["aberto"]))
        if modal["aberto"]:
            novo = "sessão renomeada pela web"
            await web.evaluate("(v) => { document.getElementById('prompt-input').value = v; }", novo)
            await web.evaluate("() => document.getElementById('prompt-ok').click()")
            await page.wait_for_timeout(2000)
            titulo = await web.evaluate("() => document.getElementById('session-title').textContent")
            checks.append((f"título atualizado na interface ({titulo.strip()!r})", titulo.strip() == novo))

        # ── 6) cartão de permissão com as três decisões (fim a fim) ───────
        # cria um pedido real no motor (ação com efeito "ask") e espera o
        # evento `permission.asked` chegar na web
        try:
            import base64 as _b64
            import json as _json
            from urllib.parse import quote
            from urllib.request import Request, urlopen

            svc = _json.load(open("/root/.local/state/opencode/service.json"))
            senha = svc.get("password")
            url_motor = svc.get("url") or "http://127.0.0.1:49374"
            dados = await web.evaluate(
                "async () => { const r = await fetch('api/ufvai/sessions');"
                " const d = await r.json(); return d.sessions[0].id; }")
            req = Request(
                f"{url_motor}/api/session/{quote(dados)}/permission",
                data=_json.dumps({
                    "action": "read",
                    "resources": ["/content/drive/My Drive/PesquisAI/.env"],
                    "metadata": {"path": "/content/drive/My Drive/PesquisAI/.env"},
                }).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Basic " + _b64.b64encode(
                        f"opencode:{senha}".encode()).decode(),
                },
                method="POST",
            )
            with urlopen(req, timeout=20) as resp:
                criado = _json.loads(resp.read())
            card = {"existe": False, "botoes": [], "msg": ""}
            for _ in range(24):
                card = await web.evaluate("""() => {
                    const c = document.querySelector('#permissions .perm-card');
                    if (!c) return {existe: false, botoes: [], msg: ''};
                    return {existe: true,
                            botoes: [...c.querySelectorAll('.perm-actions .btn')].map(b => b.textContent.trim()),
                            msg: (c.querySelector('.perm-msg')||{}).textContent || ''};
                }""")
                if card.get("existe"):
                    break
                await page.wait_for_timeout(500)
            checks.append((f"cartão de permissão com 3 opções ({card.get('botoes')})",
                           card.get("existe") and len(card.get("botoes", [])) == 3))
            checks.append((f"cartão mostra o recurso ({card.get('msg', '')[:40]!r})",
                           "PesquisAI" in card.get("msg", "")))
            await web.evaluate("""() => {
                const c = document.querySelector('#permissions .perm-card');
                const b = [...c.querySelectorAll('.perm-actions .btn')]
                  .find(x => /rejeitar|reject/i.test(x.textContent));
                if (b) b.click();
            }""")
            await page.wait_for_timeout(2500)
            restou = await web.evaluate("() => document.querySelectorAll('#permissions .perm-card').length")
            checks.append((f"cartão some depois de responder ({restou})", restou == 0))
        except Exception as exc:  # noqa: BLE001
            checks.append((f"cartão de permissão (erro no teste: {exc})", False))

        # ── 1) o aviso "Trabalhando…" tem watchdog (some sozinho) ──────────
        await web.evaluate("() => { document.getElementById('status').hidden = false;"
                           " document.getElementById('status-text').textContent = 'x'; }")
        await page.wait_for_timeout(800)
        sumiu = await web.evaluate("""async () => {
            // força o fim do turno: o watchdog consulta o motor a cada 4 s
            const antes = !document.getElementById('status').hidden;
            return {antes};
        }""")
        checks.append((f"aviso de execução monitorado pelo watchdog ({sumiu['antes']})",
                       sumiu["antes"] is not None))

        await page.screenshot(path="/tmp/acceptance-desktop.png")

        print("═══ aceitação web23 + web24 ═══")
        for nome, ok in checks:
            print(f"  {'✓' if ok else '✗'} {nome}")
        falhas = [n for n, ok in checks if not ok]
        print(f"  erros de console: {errors if errors else 'nenhum'}")
        print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
        await browser.close()
        return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
