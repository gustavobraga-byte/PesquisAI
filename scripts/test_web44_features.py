#!/usr/bin/env python3
"""test_web44_features.py — valida os recursos da v0.7.11-web44.

Cobre os 9 pontos pedidos pelo autor:

1. fila de mensagens entregue ao motor na hora (inbox), não no fim do turno;
2. fallback para o raciocínio não ficar "carregando";
3. raciocínio antes da resposta (streaming e histórico);
4. explorador: excluir + ordenar (nome/data);
5. auto-scroll com botão "jump to last" e contador;
6. remoção de mensagens vazias;
7. sugestões de performance do motor (documento — não testável aqui);
8. filtros no seletor de modelos (grátis / provedor / com chave);
9. aviso vermelho para modelos com janela < 50k.

Roda: python3 scripts/test_web44_features.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP = (ROOT / "pesquisai" / "webui" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "pesquisai" / "webui" / "theme34.css").read_text(encoding="utf-8")
HTML = (ROOT / "pesquisai" / "webui" / "index.html").read_text(encoding="utf-8")
I18N = json.loads((ROOT / "pesquisai" / "webui" / "i18n.json").read_text(encoding="utf-8"))

from pesquisai import explorer, webui_server  # noqa: E402

ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


# ── 1. fila entregue imediatamente ──────────────────────────────────────────
check("1 fila: postQueuedItem existe", "async function postQueuedItem(" in APP)
check("1 fila: queueMessage publica no motor",
      "postQueuedItem(item).then((accepted)" in APP)
check("1 fila: fallback local mantido", "async function flushQueue()" in APP)
check("1 fila: motor enfileira na inbox", "case 'inbox.enqueued':" in APP)
check("1 fila: limpa bolha duplicada", "function clearQueuedBubble(" in APP)
check("1 fila: inbox.delivered tratado", "case 'inbox.delivered':" in APP)
check("1 fila: rebadge da fila", "function rebadgeQueue(" in APP)

# ── 2. raciocínio não fica carregando ───────────────────────────────────────
check("2 reasoning: fallback existe", "function finishReasoningBlocks(" in APP)
check("2 reasoning: chamado no fim do turno (run)",
      "finishReasoningBlocks();" in APP.split("case 'run.finished':")[1][:400])
check("2 reasoning: chamado em setRunning(false)",
      "if (!state.running) {\n      finishReasoningBlocks();" in APP)
check("2 reasoning: só conclui status-busy", "classList.contains('status-busy')" in APP)
check("2 reasoning: setBlockStatus done", "setBlockStatus(block, 'done')" in APP)

# ── 3. raciocínio antes da resposta ─────────────────────────────────────────
check("3 reasoning: streaming insertBefore",
      "slot.wrap.insertBefore(slot.reasoningBlock, slot.answer)" in APP)
check("3 reasoning: histórico antes do answer",
      "wrap.appendChild(block);\n    }\n    wrap.appendChild(answer);" in APP)
check("3 reasoning: reasoning.ended também insere antes",
      APP.count("insertBefore(slot.reasoningBlock, slot.answer)") >= 2)

# ── 4. explorador: excluir + ordenar ────────────────────────────────────────
check("4 explorer: backend delete", callable(getattr(explorer, "delete", None)))
check("4 explorer: listing aceita sort", "def listing(" in Path(
      ROOT / "pesquisai" / "explorer.py").read_text(encoding="utf-8")
      and "sort: str = \"name\"" in Path(
      ROOT / "pesquisai" / "explorer.py").read_text(encoding="utf-8"))
check("4 explorer: ordenação por mtime", "\"mtime\"" in Path(
      ROOT / "pesquisai" / "explorer.py").read_text(encoding="utf-8"))
check("4 explorer: rota POST delete", "parts[3] == \"delete\"" in Path(
      ROOT / "pesquisai" / "webui_server.py").read_text(encoding="utf-8"))
check("4 explorer: frontend delete", "async function deleteExplorerItem(" in APP)
check("4 explorer: botão 🗑", "exp-act exp-del" in APP)
check("4 explorer: confirmação", "explorer.deleteConfirm" in APP)
check("4 explorer: select de ordem no HTML", 'id="exp-sort"' in HTML)
check("4 explorer: sort na URL", "&sort=${encodeURIComponent(ordem)}" in APP)
check("4 explorer: estado explorerSort", "explorerSort: 'name'" in APP)

# ── 5. auto-scroll / jump to last ───────────────────────────────────────────
check("5 scroll: botão jump existe", 'id="jump-btn"' in HTML)
check("5 scroll: contador no texto", "btn.textContent = n > 0 ? `↓ ${n}`" in APP)
check("5 scroll: classe has-new", "classList.toggle('has-new', n > 0)" in APP)
check("5 scroll: aria-label com contador", "jump.newMessages" in APP)
check("5 scroll: some no clique", "showJump(false);   // v0.7.11-web44" in APP)
check("5 scroll: MutationObserver conta novas", "state.newSinceScroll += added" in APP)
check("5 scroll: CSS has-new", ".jump-btn.has-new" in CSS)

# ── 6. mensagens vazias ─────────────────────────────────────────────────────
check("6 vazias: prune existe", "function pruneEmptyStreamSlots(" in APP)
check("6 vazias: chamado no fim do turno", "setTimeout(pruneEmptyStreamSlots, 400)" in APP)
check("6 vazias: respeita histórico", "const persisted = (state.messages || []).some(" in APP)

# ── 8. filtros de modelos ───────────────────────────────────────────────────
check("8 modelos: estado modelFilters", "modelFilters: { free: false, available: false" in APP)
check("8 modelos: renderProviderFilter", "function renderProviderFilter(" in APP)
check("8 modelos: chip grátis", 'id="mf-free"' in HTML)
check("8 modelos: chip com chave", 'id="mf-available"' in HTML)
check("8 modelos: select provedor", 'id="model-provider"' in HTML)
check("8 modelos: filtro por custo", "if (filtros.free && !(model.cost && model.cost.free)) return;" in APP)
check("8 modelos: filtro por provedor", "if (filtros.provider && model.providerID !== filtros.provider) return;" in APP)
check("8 modelos: sync chips", "function syncFilterChips(" in APP)
check("8 modelos: CSS chips", ".mf-chip.on" in CSS)

# ── 9. contexto < 50k ───────────────────────────────────────────────────────
check("9 contexto: mínimo 50k", "minContext: 50000" in APP)
check("9 contexto: checagem", "ctx < (state.minContext || 50000)" in APP)
check("9 contexto: badge incompatível", "badge incompatible" in APP)
check("9 contexto: classe no item", "item.classList.add('incompatible')" in APP)
check("9 contexto: CSS vermelho", ".badge.incompatible" in CSS)
check("9 contexto: contador no rodapé", "incompativeis} incompatíveis" in APP)

# ── i18n (5 idiomas) ────────────────────────────────────────────────────────
need = [
    "jump.toLast", "jump.newMessages",
    "explorer.delete", "explorer.deleteConfirm", "explorer.deleteDirConfirm",
    "explorer.deleteFail", "explorer.deleted", "explorer.sort",
    "explorer.sortName", "explorer.sortNameDesc", "explorer.sortNewest", "explorer.sortOldest",
    "model.freeOnly", "model.availableOnly", "model.allProviders", "model.byProvider",
    "model.incompatible", "model.incompatibleTip", "model.none",
]
locales = I18N.get("locales", {})
check("i18n: versão web44+", str(I18N.get("version", "")).startswith("0.7.11-web4")
      and int(str(I18N.get("version")).split("web4")[-1]) >= 4)
check("i18n: 5 idiomas", set(locales) == {"pt-BR", "en", "es", "fr", "zh"})
for loc, bucket in locales.items():
    faltando = [k for k in need if k not in bucket]
    check(f"i18n: {loc} tem as 19 chaves", not faltando)
    if faltando:
        print("     faltando:", ", ".join(faltando))

# ── backend funcional (explorer) ────────────────────────────────────────────
print("\n[backend funcional]")
with tempfile.TemporaryDirectory() as td:
    base = Path(td).resolve()
    (base / "b.txt").write_text("b", encoding="utf-8")
    (base / "a.txt").write_text("a", encoding="utf-8")
    (base / "pasta").mkdir()
    (base / "pasta" / "c.md").write_text("c", encoding="utf-8")
    explorer.allowed_roots = lambda: [base]

    nomes_az = [i["name"] for i in explorer.listing("", "name")["items"]]
    check("backend: name → pastas primeiro A-Z", nomes_az == ["pasta", "a.txt", "b.txt"])
    nomes_za = [i["name"] for i in explorer.listing("", "name-desc")["items"]]
    check("backend: name-desc → pastas primeiro", nomes_za[0] == "pasta")
    check("backend: mtime → retorna lista", len(explorer.listing("", "mtime")["items"]) == 3)
    check("backend: mtime-asc → retorna lista", len(explorer.listing("", "mtime-asc")["items"]) == 3)

    check("backend: delete arquivo", explorer.delete("a.txt").get("ok") is True)
    check("backend: arquivo sumiu", not (base / "a.txt").exists())
    check("backend: delete raiz negado", explorer.delete("").get("ok") is False)
    check("backend: delete absoluto negado", explorer.delete(str(base / "b.txt")).get("ok") is False)
    check("backend: arquivo intacto após falha", (base / "b.txt").exists())
    check("backend: delete pasta", explorer.delete("pasta").get("ok") is True)
    check("backend: pasta sumiu", not (base / "pasta").exists())

    status, payload = webui_server._handle_api(
        "POST", "/api/ufvai/explorer/delete", {}, {"path": "b.txt"}
    )
    check("backend: rota POST delete 200", status == 200)
    check("backend: rota delete aplicou", not (base / "b.txt").exists())

print(f"\nRESULTADO: {ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
