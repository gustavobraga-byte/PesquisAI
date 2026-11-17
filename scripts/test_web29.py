#!/usr/bin/env python3
"""test_web29.py — aceitação da rodada web29.

  1. visualizador redimensionável (arrastar a altura);
  2. Word em **modo leitura** (formatação preservada);
  3. botão "voltar ao Colab e reexecutar" → notebook no Colab;
  4. links nas respostas **clicáveis** (markdown e URL solta);
  5. resposta que aponta um arquivo → clique abre o arquivo no explorador.
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8003/"


async def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await page.goto(BASE, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)

        # ── 4) links clicáveis (markdown + URL solta) ────────────────────
        links = await page.evaluate("""() => {
            const texto = 'Veja o [SIDRA](https://sidra.ibge.gov.br/tabela/1613) e '
                + 'também https://www.scielo.br/j/ para mais.';
            const box = document.createElement('div');
            box.className = 'answer';
            box.innerHTML = window.__ufvai.md(texto);
            document.getElementById('messages').appendChild(box);
            return [...box.querySelectorAll('a')].map(a => ({
                txt: a.textContent, href: a.href, target: a.target, rel: a.rel,
            }));
        }""")
        hrefs = [l["href"] for l in links]
        checks.append((f"link markdown clicável ({len(links)} links)", len(links) == 2))
        checks.append((f"URL solta virou link ({hrefs})",
                       any("scielo.br" in h for h in hrefs)))
        checks.append(("links abrem em nova aba com noopener",
                       all(l["target"] == "_blank" and l["rel"] == "noopener" for l in links)))

        # ── 5) referência de arquivo clicável ────────────────────────────
        ref = await page.evaluate("""() => {
            const box = document.createElement('div');
            box.className = 'answer';
            box.innerHTML = window.__ufvai.md('O relatório está em '
                + '**relatorio-final.pdf** e o comando é `npm run build`.');
            document.getElementById('messages').appendChild(box);
            const refs = [...box.querySelectorAll('a.file-ref')];
            return {quantos: refs.length, quais: refs.map(r => r.getAttribute('data-file'))};
        }""")
        checks.append((f"referência de arquivo vira link ({ref.get('quais')})",
                       ref.get("quantos") >= 1))
        checks.append(("código inline (que não é caminho) NÃO vira referência",
                       "npm run build" not in (ref.get("quais") or [])))

        # ── 3) botão do Colab ────────────────────────────────────────────
        colab = await page.evaluate("""() => {
            const a = document.getElementById('dead-action');
            return {tag: a.tagName, href: a.href, target: a.target};
        }""")
        checks.append((f"botão do Colab aponta para o notebook ({colab.get('href')})",
                       "colab.research.google.com/github/gustavobraga-byte/PesquisAI"
                       in colab.get("href", "") and "PesquisAI.ipynb" in colab.get("href", "")))

        # ── 1) e 2) explorador: visualizador redimensionável + Word ──────
        await page.evaluate("() => document.getElementById('explorer-btn').click()")
        await page.wait_for_timeout(2500)
        await page.fill("#exp-search", "Prova 2 - 2026-1 - Versao B.docx")
        await page.wait_for_timeout(6000)
        await page.evaluate("""() => {
            const it = [...document.querySelectorAll('#exp-list .exp-item')]
                .find(e => /\\.docx$/i.test((e.querySelector('.exp-name span')||{}).textContent || ''));
            if (it) it.click();
        }""")
        await page.wait_for_timeout(3500)
        doc = await page.evaluate("""() => {
            const p = document.getElementById('exp-preview');
            const d = p.querySelector('.exp-prev-doc');
            return {
                visivel: !p.hidden,
                doc: !!d,
                paragrafos: d ? d.querySelectorAll('p').length : 0,
                tabelas: d ? d.querySelectorAll('table').length : 0,
                negrito: d ? d.querySelectorAll('strong').length : 0,
                texto: d ? (d.textContent || '').trim().slice(0, 60) : '',
            };
        }""")
        checks.append((f"Word em modo leitura: {doc.get('paragrafos')} parágrafos, "
                       f"{doc.get('tabelas')} tabelas, {doc.get('negrito')} negritos",
                       bool(doc.get("doc")) and doc.get("paragrafos", 0) > 5
                       and doc.get("tabelas", 0) >= 1))

        # altura do visualizador
        antes = await page.evaluate(
            "() => Math.round(document.getElementById('exp-preview').getBoundingClientRect().height)")
        pos = await page.evaluate("""() => {
            const r = document.getElementById('exp-vresizer').getBoundingClientRect();
            return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)};
        }""")
        await page.mouse.move(pos["x"], pos["y"])
        await page.mouse.down()
        await page.mouse.move(pos["x"], pos["y"] - 140, steps=12)
        await page.mouse.up()
        await page.wait_for_timeout(800)
        depois = await page.evaluate(
            "() => Math.round(document.getElementById('exp-preview').getBoundingClientRect().height)")
        checks.append((f"arrastar redimensiona o visualizador ({antes} → {depois})",
                       antes != depois and depois > antes))

        # ── 5b) clique numa referência abre no explorador ─────────────────
        abriu = await page.evaluate("""async () => {
            const box = document.createElement('div');
            box.className = 'answer';
            box.innerHTML = window.__ufvai.md('Veja o arquivo SUMARIO_SES_1067.pdf');
            document.getElementById('messages').appendChild(box);
            const ref = box.querySelector('a.file-ref');
            if (!ref) return {semRef: true};
            ref.click();
            await new Promise(r => setTimeout(r, 3000));
            const p = document.getElementById('exp-preview');
            return {
                nome: (p.querySelector('.exp-prev-name')||{}).textContent || '',
                pdf: !!p.querySelector('iframe.exp-prev-pdf'),
                aberto: !document.getElementById('explorer').hidden,
            };
        }""")
        checks.append((f"clique no arquivo abre o explorador ({abriu.get('nome')!r})",
                       bool(abriu.get("pdf")) and "SUMARIO" in (abriu.get("nome") or "")))

        # ── 6) XLSX aparece como TABELA no explorador ────────────────────
        await page.fill("#exp-search", "Avaliacao_PPGER_2027-1_DOUTORADO.xlsx")
        # espera o resultado aparecer (a 1a busca monta o índice: ~3 s)
        achou = False
        for _ in range(30):
            achou = await page.evaluate("""() => [...document.querySelectorAll('#exp-list .exp-item')]
                .some(e => /[.]xlsx$/i.test((e.querySelector('.exp-name span')||{}).textContent || ''))""")
            if achou:
                break
            await page.wait_for_timeout(500)
        await page.evaluate("""() => {
            const it = [...document.querySelectorAll('#exp-list .exp-item')]
                .find(e => /[.]xlsx$/i.test((e.querySelector('.exp-name span')||{}).textContent || ''));
            if (it) it.click();
        }""")
        for _ in range(30):
            doc = await page.evaluate(
                "() => !!document.querySelector('#exp-preview .exp-prev-doc')")
            if doc:
                break
            await page.wait_for_timeout(500)
        xlsx = await page.evaluate("""() => {
            const d = document.querySelector('#exp-preview .exp-prev-doc');
            if (!d) return {doc: false};
            return {
                doc: true,
                abas: d.querySelectorAll('h3').length,
                tabelas: d.querySelectorAll('table').length,
                linhas: d.querySelectorAll('tbody tr').length,
                celulas: d.querySelectorAll('td').length,
            };
        }""")
        checks.append((f"XLSX vira tabela ({xlsx.get('abas')} abas, "
                       f"{xlsx.get('tabelas')} tabelas, {xlsx.get('linhas')} linhas)",
                       bool(xlsx.get("doc")) and xlsx.get("tabelas", 0) >= 1
                       and xlsx.get("linhas", 0) >= 5))

        # ── 7) indicador global de atividade (espiral + concluído) ───────
        busy = await page.evaluate("""async () => {
            window.__ufvai.setRunning(true);
            await new Promise(r => setTimeout(r, 400));
            const node = document.getElementById('agent-busy');
            const spin = node.querySelector('.spin');
            const cs = getComputedStyle(spin);
            const durante = {
                visivel: !node.hidden,
                animacao: cs.animationName,
                cor: cs.borderTopColor,
                texto: (node.querySelector('.busy-text')||{}).textContent || '',
                statusVisivel: !document.getElementById('status').hidden,
            };
            window.__ufvai.setRunning(false);
            await new Promise(r => setTimeout(r, 400));
            const depois = {
                visivel: !node.hidden,
                feito: node.classList.contains('done'),
                texto: (node.querySelector('.busy-text')||{}).textContent || '',
                check: getComputedStyle(node.querySelector('.busy-check')).display,
            };
            return {durante, depois};
        }""")
        d = busy.get("durante", {})
        dp = busy.get("depois", {})
        checks.append((f"espiral global enquanto o agente trabalha ({d.get('cor')}, "
                       f"{d.get('animacao')})",
                       bool(d.get("visivel")) and d.get("animacao") not in (None, "none")))
        checks.append((f"linha de status visível durante o turno ({d.get('statusVisivel')})",
                       bool(d.get("statusVisivel"))))
        checks.append((f"fim do turno mostra 'concluído' verde ({dp.get('texto')!r})",
                       bool(dp.get("visivel")) and bool(dp.get("feito"))
                       and dp.get("check") != "none"))

        await page.screenshot(path="/tmp/web29.png")
        print("═══ aceitação web29 ═══")
        for nome, ok in checks:
            print(f"  {'✓' if ok else '✗'} {nome}")
        falhas = [n for n, ok in checks if not ok]
        print(f"  erros de console: {errors if errors else 'nenhum'}")
        print(f"  resultado: {len(checks) - len(falhas)}/{len(checks)} ok")
        await browser.close()
        return 1 if falhas or errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
