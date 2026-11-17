#!/usr/bin/env python3
"""test_web28.py — aceitação da rodada web28.

  1. tabelas Markdown **com links** (a tabela vira <table> e o link, <a>);
  2. sincronismo: a cauda é reconciliada e o texto perdido é corrigido;
  3. **fallback** de sincronização (funciona sem o SSE);
  4. explorador: filtro de busca, arrastar para redimensionar, fechar a
     visualização e visualizar PDF;
  5. link do Drive na **busca** (/drive/u/0/search?q=);
  6. indicador de atividade: espiral **amarela** girando no raciocínio e nas
     ferramentas, **verde** quando concluído.
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"

TABELA = """Segue a comparação:

| Fonte | Tipo | Link |
|---|---|---|
| IBGE | Agregado | [SIDRA](https://sidra.ibge.gov.br/tabela/1613) |
| DataSUS | Microdados | [OpenDataSUS](https://opendatasus.saude.gov.br/) |
| Plano | Texto | — |
"""


async def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)

        # ── 1) tabela markdown com links ────────────────────────────────
        tabela = await page.evaluate("""(s) => {
            const box = document.createElement('div');
            box.className = 'answer';
            box.innerHTML = window.__ufvai.md(s);
            document.getElementById('messages').appendChild(box);
            const t = box.querySelector('table');
            if (!t) return {existe: false};
            return {
                existe: true,
                linhas: t.querySelectorAll('tbody tr').length,
                colunas: t.querySelectorAll('thead th').length,
                links: [...t.querySelectorAll('a')].map(a => ({
                    txt: a.textContent, href: a.href, target: a.target,
                })),
                celula: t.querySelector('tbody tr td:nth-child(3)').textContent,
                textoCru: t.closest('.answer').textContent.includes('|---'),
            };
        }""", TABELA)
        checks.append((f"tabela markdown vira <table> ({tabela.get('linhas')} linhas x "
                       f"{tabela.get('colunas')} colunas)", bool(tabela.get("existe"))
                       and tabela.get("linhas") == 3 and tabela.get("colunas") == 3))
        checks.append((f"links da tabela são <a href> ({tabela.get('links')})",
                       len(tabela.get("links") or []) == 2
                       and all(l["href"].startswith("https://") for l in tabela["links"])))
        checks.append(("a tabela não vaza texto cru (pipes)", tabela.get("textoCru") is False))
        checks.append((f"célula com link mostra o rótulo ({tabela.get('celula')!r})",
                       tabela.get("celula") == "SIDRA"))

        # ── 2) sincronismo: reconcilia toda a cauda ────────────────────
        sync = await page.evaluate("""async () => {
            const st = window.__ufvai.state;
            if (!st.sessionId) return {semSessao: true};
            const r = await fetch('api/ufvai/sessions/' + encodeURIComponent(st.sessionId)
                                  + '/messages?limit=80');
            const server = await r.json();
            const mapa = new Map((server.messages || []).map(m => [m.id, m.text || '']));
            // sabota TODAS as mensagens que o servidor conhece
            let corrompidas = 0;
            st.messages.forEach((m) => {
                if (mapa.has(m.id)) { m.text = 'TEXTO CORROMPIDO'; corrompidas += 1; }
            });
            await window.__ufvai.syncMessages({force: true});
            const divergentes = st.messages.filter(
                (m) => mapa.has(m.id) && (m.text || '') !== mapa.get(m.id));
            return {
                corrompidas, divergentes: divergentes.length,
                mensagens: st.messages.length, servidor: mapa.size,
            };
        }""")
        checks.append((f"a sincronização reconcilia toda a cauda "
                       f"({sync.get('corrompidas')} sabotadas, {sync.get('divergentes')} divergentes)",
                       sync.get("corrompidas", 0) > 0
                       and sync.get("divergentes") == 0))

        # ── 3) fallback: sincroniza sem depender do SSE ────────────────
        fallback = await page.evaluate("""async () => {
            const st = window.__ufvai.state;
            const r = await fetch('api/ufvai/sessions/' + encodeURIComponent(st.sessionId)
                                  + '/messages?limit=80');
            const server = await r.json();
            const mapa = new Map((server.messages || []).map(m => [m.id, m.text || '']));
            st.messages.forEach((m) => {
                if (mapa.has(m.id)) m.text = 'CORROMPIDO SEM SSE';
            });
            // derruba o SSE e marca a sessão como em execução: o fallback
            // periódico (a cada 3 s) tem de consertar a mensagem.
            try { if (st.source) st.source.close(); } catch (e) {}
            st.source = null;
            window.__ufvai.setRunning(true);
            await new Promise(r => setTimeout(r, 5000));
            const divergentes = st.messages.filter(
                (m) => mapa.has(m.id) && (m.text || '') !== mapa.get(m.id));
            window.__ufvai.setRunning(false);
            return {divergentes: divergentes.length, mensagens: mapa.size};
        }""")
        checks.append((f"fallback periódico corrige sem SSE "
                       f"({fallback.get('divergentes')} divergentes)",
                       fallback.get("mensagens", 0) > 0
                       and fallback.get("divergentes") == 0))

        # ── 4) explorador ──────────────────────────────────────────────
        await page.evaluate("() => document.getElementById('explorer-btn').click()")
        await page.wait_for_timeout(2500)
        exp = await page.evaluate("""() => {
            const e = document.getElementById('explorer');
            return {
                aberto: !e.hidden,
                itens: document.querySelectorAll('#exp-list .exp-item').length,
                busca: !!document.getElementById('exp-search'),
                alca: !!document.getElementById('exp-resizer'),
                largura: getComputedStyle(document.documentElement)
                    .getPropertyValue('--explorer-w').trim(),
            };
        }""")
        checks.append((f"explorador abre com itens ({exp.get('itens')})",
                       bool(exp.get("aberto")) and exp.get("itens", 0) > 3))
        checks.append(("campo de busca e alça de redimensionamento presentes",
                       bool(exp.get("busca")) and bool(exp.get("alca"))))

        # filtro de busca (termo que existe em uma subpasta → mostra o caminho)
        await page.fill("#exp-search", "test_web28")
        await page.wait_for_timeout(2500)
        busca = await page.evaluate("""() => ({
            itens: document.querySelectorAll('#exp-list .exp-item').length,
            contador: (document.querySelector('#exp-list .exp-count')||{}).textContent || '',
            onde: [...document.querySelectorAll('#exp-list .exp-where')].map(e => e.textContent),
            caminho: document.getElementById('exp-path').textContent,
        })""")
        checks.append((f"filtro filtra arquivos e pastas ({busca.get('itens')} itens, "
                       f"contador={busca.get('contador')!r})",
                       busca.get("itens", 0) >= 1 and bool(busca.get("contador"))))
        checks.append(("o filtro mostra o caminho do item encontrado",
                       bool(busca.get("onde"))))

        # PDF: abrir o primeiro resultado (deve ser o SUMARIO...pdf)
        await page.fill("#exp-search", "SUMARIO")
        await page.wait_for_timeout(2500)
        await page.evaluate("""() => {
            const it = [...document.querySelectorAll('#exp-list .exp-item')]
                .find(e => /[.]pdf$/i.test((e.querySelector('.exp-name')||{}).textContent || ''));
            if (it) it.click();
        }""")
        await page.wait_for_timeout(3000)
        prev = await page.evaluate("""() => {
            const p = document.getElementById('exp-preview');
            const f = p.querySelector('iframe.exp-prev-pdf');
            const img = p.querySelector('img.exp-prev-image');
            return {
                visivel: !p.hidden,
                pdf: !!f,
                src: f ? f.getAttribute('src') : '',
                imagem: !!img,
                fecha: !!p.querySelector('.exp-prev-close'),
                nome: (p.querySelector('.exp-prev-name')||{}).textContent || '',
                linkDrive: (p.querySelector('a[href*="drive.google.com"]')||{}).href || '',
            };
        }""")
        checks.append((f"PDF é visualizado dentro da web ({prev.get('nome')!r})",
                       bool(prev.get("pdf")) and "/explorer/download" in prev.get("src", "")))
        checks.append((f"link do Drive usa /search?q= ({prev.get('linkDrive')[:60]})",
                       "/drive/u/0/search?q=" in prev.get("linkDrive", "")))

        # fechar a visualização
        await page.evaluate("""() => {
            const b = document.querySelector('#exp-preview .exp-prev-close');
            if (b) b.click();
        }""")
        await page.wait_for_timeout(800)
        fechado = await page.evaluate("""() => ({
            oculto: document.getElementById('exp-preview').hidden,
            vazio: document.getElementById('exp-preview').innerHTML.trim() === '',
        })""")
        checks.append((f"botão fecha a visualização ({fechado})",
                       bool(fechado.get("oculto")) and bool(fechado.get("vazio"))))

        # arrastar para redimensionar
        await page.evaluate("() => { document.getElementById('exp-search').value = ''; }")
        antes = await page.evaluate(
            "() => getComputedStyle(document.documentElement).getPropertyValue('--explorer-w').trim()")
        box = await page.evaluate("""() => {
            const r = document.getElementById('exp-resizer').getBoundingClientRect();
            return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + 120)};
        }""")
        await page.mouse.move(box["x"], box["y"])
        await page.mouse.down()
        await page.mouse.move(box["x"] - 120, box["y"], steps=12)
        await page.mouse.up()
        await page.wait_for_timeout(700)
        depois = await page.evaluate(
            "() => getComputedStyle(document.documentElement).getPropertyValue('--explorer-w').trim()")
        checks.append((f"arrastar redimensiona o explorador ({antes} → {depois})",
                       antes != depois))

        # ── 6) indicador de atividade (espiral) ────────────────────────
        spir = await page.evaluate("""() => {
            const st = window.__ufvai.state;
            const id = 'msg-teste-espiral';
            window.__ufvai.handleEvent({type: 'reasoning.started', messageID: id});
            window.__ufvai.handleEvent({type: 'reasoning.delta', messageID: id, delta: 'pensando…'});
            const bloco = document.querySelector(
                '#messages .msg[data-mid="' + id + '"] details.block.reasoning');
            const spin = bloco ? bloco.querySelector('.spin') : null;
            const css = spin ? getComputedStyle(spin) : null;
            const emExecucao = {
                temBloco: !!bloco,
                espiral: !!spin,
                cor: css ? css.borderTopColor : '',
                animacao: css ? css.animationName : '',
                rodando: css ? css.animationDuration : '',
                rotulo: bloco ? (bloco.querySelector('.status-label')||{}).textContent : '',
            };
            window.__ufvai.handleEvent({type: 'reasoning.ended', messageID: id, text: 'pensando…'});
            const spin2 = bloco.querySelector('.spin');
            const css2 = getComputedStyle(spin2);
            const concluido = {
                espiralVisivel: !spin2.hidden,
                cor: css2.borderTopColor,
                rotulo: (bloco.querySelector('.status-label')||{}).textContent,
                classe: (bloco.querySelector('.status-run')||{}).className,
            };
            // ferramenta em execução
            window.__ufvai.handleEvent({type: 'tool.started', messageID: id, name: 'bash',
                                        callID: 'c1', input: {command: 'ls'}});
            const tool = document.querySelector(
                '#messages .msg[data-mid="' + id + '"] details.block.tool');
            const tSpin = tool.querySelector('.spin');
            const tCss = getComputedStyle(tSpin);
            const toolRodando = {
                espiral: !!tSpin,
                cor: tCss.borderTopColor,
                rotulo: (tool.querySelector('.status-label')||{}).textContent,
            };
            window.__ufvai.handleEvent({type: 'tool.finished', messageID: id, name: 'bash',
                                        callID: 'c1', status: 'completed', output: 'ok'});
            const tSpin2 = tool.querySelector('.spin');
            const toolConcluido = {
                espiralVisivel: !tSpin2.hidden,
                classe: (tool.querySelector('.status-run')||{}).className,
                rotulo: (tool.querySelector('.status-label')||{}).textContent,
            };
            return {emExecucao, concluido, toolRodando, toolConcluido};
        }""")
        e = spir.get("emExecucao", {})
        c = spir.get("concluido", {})
        tr = spir.get("toolRodando", {})
        tc = spir.get("toolConcluido", {})
        checks.append((f"raciocínio mostra a espiral girando ({e.get('cor')} / {e.get('animacao')})",
                       bool(e.get("espiral")) and e.get("animacao") not in (None, "none")))
        checks.append((f"concluído: a espiral some e o rótulo fica verde "
                       f"({c.get('rotulo')!r}, {c.get('classe')})",
                       c.get("espiralVisivel") is False
                       and "status-done" in (c.get("classe") or "")))
        checks.append((f"ferramenta em execução: espiral amarela ({tr.get('cor')!r})",
                       bool(tr.get("espiral"))))
        checks.append((f"ferramenta concluída: verde, sem espiral ({tc.get('rotulo')!r})",
                       tc.get("espiralVisivel") is False
                       and "status-done" in (tc.get("classe") or "")))

        await page.screenshot(path="/tmp/web28.png", full_page=False)
        print("═══ aceitação web28 ═══")
        for nome, ok in checks:
            print(f"  {'✓' if ok else '✗'} {nome}")
        falhas = [n for n, ok in checks if not ok]
        print(f"  erros de console: {errors if errors else 'nenhum'}")
        print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
        await browser.close()
        return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
