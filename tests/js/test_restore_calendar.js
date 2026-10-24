// Teste da interface "Restaurar" (v0.7.0): calendario + filtro por data.
// Node puro, sem dependencias: stubs minimos de DOM/navegador.
//   node tests/js/test_restore_calendar.js
const fs = require("fs");
const path = require("path");

// ── stubs de DOM ────────────────────────────────────────────────────────
const els = {};
function mk(id) {
  return els[id] || (els[id] = {
    id, innerHTML: "", textContent: "", value: "", title: "", checked: false,
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      toggle(c, f) { f ? this._s.add(c) : this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    },
    addEventListener() {}, removeEventListener() {}, appendChild() {},
    setAttribute() {}, getAttribute() { return null; },
  });
}
global.document = {
  getElementById: (id) => mk(id),
  querySelectorAll: () => [],
  querySelector: () => null,
  addEventListener: () => {},
  createElement: () => mk("tmp"),
};
global.localStorage = { getItem: () => null, setItem: () => {} };
global.setTimeout = (fn) => 1;
global.setInterval = () => 1;
global.clearInterval = () => {};
global.navigator = { sendBeacon: () => true };
global.location = { reload: () => {} };

// ── contexto minimo ─────────────────────────────────────────────────────
global.I18N = {
  pt_BR: {
    "ui.loading": "Carregando…", "ui.restore": "Restaurar",
    "restore.count": "{total} backups",
    "restore.summary_filtered": "{shown} de {total} backups",
    "restore.all_dates": "Todas as datas", "restore.today": "Hoje",
    "restore.prev": "Mês anterior", "restore.next": "Próximo mês",
    "restore.filter": "Filtrar por data",
    "restore.dow.0": "S", "restore.dow.1": "T", "restore.dow.2": "Q",
    "restore.dow.3": "Q", "restore.dow.4": "S", "restore.dow.5": "S",
    "restore.dow.6": "D",
    "restore.empty": "Nenhum backup encontrado no Drive.",
    "restore.empty_date": "Nenhum backup nesta data.",
    "restore.error": "Erro ao carregar os backups.",
    "restore.autosave": "Autossave", "restore.invalid": "corrompido",
    "restore.confirm": "Restaurar o backup de {when}?",
    "restore.restoring": "Restaurando {when}…",
    "restore.delete": "apagar",
    "restore.delete_confirm": "Apagar o backup de {when}? Esta ação não pode ser desfeita.",
    "restore.deleting": "Apagando {when}…",
    "restore.deleted": "Backup apagado.",
    "restore.delete_failed": "Falha ao apagar o backup.",
  },
};
global._currentLang = "pt_BR";
global.BASE = "";
global.escapeHtml = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
global.toast = () => {};
global.IS_COLAB = false;      // v0.7.1: o bloco extraido chega ate "const PROVIDERS"
global.__confirmMsg = "";
global.pesquisaiConfirm = (msg, onYes) => { global.__confirmMsg = msg; if (onYes) onYes(); };

let fetchCalls = [];
global.fetch = async (url) => {
  fetchCalls.push(url);
  return {
    json: async () => ({
      backups: [
        { file: "backup_ses_aaa_10-00-00_21-10-2026.json", kind: "backup", session_id: "aaa",
          date: "2026-10-21", time: "10:00:00", datetime: "2026-10-21T10:00:00",
          timestamp: 1790000000, size: 1000, size_h: "1,0 KB", title: "Sessao A", valid: true },
        { file: "backup_ses_bbb_11-30-00_21-10-2026.json", kind: "backup", session_id: "bbb",
          date: "2026-10-21", time: "11:30:00", datetime: "2026-10-21T11:30:00",
          timestamp: 1790001000, size: 2000, size_h: "2,0 KB", title: "Sessao B", valid: true },
        { file: "backup_ses_ccc_09-15-00_09-10-2026.json", kind: "backup", session_id: "ccc",
          date: "2026-10-09", time: "09:15:00", datetime: "2026-10-09T09:15:00",
          timestamp: 1789000000, size: 3000, size_h: "3,0 KB", title: "Sessao C", valid: false },
        { file: "autosave/autosave_1.json", kind: "autosave", session_id: "ddd",
          date: "2026-10-21", time: "12:00:00", datetime: "2026-10-21T12:00:00",
          timestamp: 1790002000, size: 4000, size_h: "4,0 KB", title: "Sessao D", valid: true },
      ],
      count: 4, dates: ["2026-10-21", "2026-10-09"],
    }),
  };
};

// ── carrega o bloco de código do "Restaurar" ────────────────────────────
// O bloco e extraido do HTML JA RENDERIZADO (o mesmo que o navegador
// recebe): assim os escapes do template Python ficam resolvidos.
const { execFileSync } = require("child_process");
const SRC = "/tmp/pesquisai/pesquisai/launch_app_responsive_v041.py";
const py = `
import importlib.util, os, sys, tempfile, types
PKG = "/tmp/pesquisai/pesquisai"
spec = importlib.util.spec_from_file_location("ufvai_resp", os.path.join(PKG, "launch_app_responsive_v041.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["ufvai_resp"] = mod
spec.loader.exec_module(mod)
tmp = tempfile.mkdtemp(prefix="ufvai-render-")
mod.WRAPPER_DIR = tmp          # NAO sobrescrever o index.html do wrapper vivo
html = mod.create_wrapper_html("http://localhost:8000", "https://drive.google.com")
sys.stdout.write(html)
`;
let html;
try {
  html = execFileSync("python3", ["-c", py], { maxBuffer: 64 * 1024 * 1024 }).toString("utf8");
} catch (e) {
  console.error("❌ falha ao renderizar o HTML do wrapper:", e.stderr ? e.stderr.toString() : e);
  process.exit(1);
}
const blocks = html.match(/<script(?![^>]*\bsrc=)[^>]*>[\s\S]*?<\/script>/g) || [];
let code = null;
for (const b of blocks) {
  if (b.includes("restoreBuildGrid")) {
    const js = b.replace(/^<script[^>]*>/, "").replace(/<\/script>$/, "");
    // recorta apenas o bloco do "Restaurar" (o script inteiro depende do
    // DOM completo da pagina)
    const start = js.indexOf("let _restoreItems = [];");
    const end = js.indexOf("const PROVIDERS");
    if (start >= 0 && end > start) code = js.slice(start, end);
    break;
  }
}
if (!code) {
  console.error("❌ bloco 'Restaurar' nao encontrado no HTML renderizado");
  process.exit(1);
}
eval(code);

// ── testes ───────────────────────────────────────────────────────────────
let ok = 0, fail = 0;
function check(nome, cond) {
  if (cond) { ok++; console.log("  ✅", nome); }
  else { fail++; console.log("  ❌", nome); }
}

(async () => {
  console.log("=== 1. grade do calendario ===");
  // 01/10/2026 e' uma quinta-feira -> 3 celulas vazias antes do dia 1
  const weeks = restoreBuildGrid(2026, 9);
  check("4 ou 5 semanas geradas", weeks.length >= 4 && weeks.length <= 6);
  check("primeira semana comeca na segunda", weeks[0].length === 7);
  check("celulas vazias no inicio (quinta-feira)",
    weeks[0][0] === null && weeks[0][1] === null && weeks[0][2] === null);
  check("dia 1 na posicao 3 da primeira semana", weeks[0][3] === 1);
  const lastWeek = weeks[weeks.length - 1];
  const flat = weeks.flat();
  check("31 dias em outubro", flat.filter((d) => d !== null).length === 31);
  check("semultiplas de 7 no total", flat.length % 7 === 0);
  check("ultima celula nao nula (31)", lastWeek[6] === 31 || lastWeek[5] === 31);

  console.log("\n=== 2. contagem por data ===");
  const items = [
    { date: "2026-10-21" }, { date: "2026-10-21" }, { date: "2026-10-21" },
    { date: "2026-10-09" },
  ];
  const counts = restoreDayCounts(items);
  check("21/10 com 3 backups", counts["2026-10-21"] === 3);
  check("09/10 com 1 backup", counts["2026-10-09"] === 1);
  check("data sem backup = 0", (counts["2026-01-01"] || 0) === 0);

  console.log("\n=== 3. filtro por data ===");
  const all = restoreFilterByDate(items, "");
  check("sem filtro devolve todos", all.length === 4);
  const one = restoreFilterByDate(items, "2026-10-21");
  check("filtro devolve so a data", one.length === 3);
  check("filtro de data sem backup devolve vazio",
    restoreFilterByDate(items, "2026-01-01").length === 0);

  console.log("\n=== 4. render (calendario + lista) ===");
  await openRestore();
  const grid = mk("restore-grid").innerHTML;
  const list = mk("backup-list").innerHTML;
  check("GET /api/backups disparado", fetchCalls.some((u) => u.endsWith("/api/backups")));
  check("grade com 31 dias", (grid.match(/restore-day/g) || []).length >= 31);
  check("dia 21 marcado como 'has'", grid.includes("2026-10-21"));
  check("dia com backup tem classe 'has'", grid.includes("restore-day has"));
  check("lista traz as 4 entradas", (list.match(/class="backup-item"/g) || []).length === 4);
  check("lista agrupada por data", list.includes("restore-daygroup"));
  check("titulo do backup aparece", list.includes("Sessao A"));
  check("autosave com badge proprio", list.includes("b-badge auto"));
  check("backup corrompido com badge", list.includes("b-badge bad"));
  check("resumo mostra o total", mk("restore-summary").textContent.includes("4"));

  console.log("\n=== 5. filtro por data (clique no dia) ===");
  restorePickDate("2026-10-09");
  const list2 = mk("backup-list").innerHTML;
  check("lista filtrada tem 1 item", (list2.match(/class="backup-item"/g) || []).length === 1);
  check("item filtrado e o de 09/10", list2.includes("Sessao C"));
  check("input de data sincronizado", mk("restore-date").value === "2026-10-09");
  check("resumo filtrado", mk("restore-summary").textContent.includes("1"));

  console.log("\n=== 6. limpar filtro / selecao de hoje ===");
  restoreClearDate();
  check("filtro limpo -> 4 itens",
    (mk("backup-list").innerHTML.match(/class="backup-item"/g) || []).length === 4);
  check("input de data vazio", mk("restore-date").value === "");
  restoreToday();
  const today = new Date();
  const key = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0") +
              "-" + String(today.getDate()).padStart(2, "0");
  check("'Hoje' seleciona a data de hoje", mk("restore-date").value === key);

  console.log("\n=== 7. navegacao entre meses ===");
  restorePrevMonth();
  const mesAntigo = mk("restore-month-label").textContent;
  restoreNextMonth();
  const mesNovo = mk("restore-month-label").textContent;
  check("rotulo do mes muda ao navegar", mesAntigo !== mesNovo);
  check("rotulo do mes preenchido", mesNovo.length > 0);

  console.log("\n=== 8. clique de novo no mesmo dia desmarca ===");
  restoreClearDate();
  restorePickDate("2026-10-21");
  check("dia selecionado", mk("restore-date").value === "2026-10-21");
  restorePickDate("2026-10-21");
  check("segundo clique desmarca", mk("restore-date").value === "");

  console.log("\n=== 9. compatibilidade com o formato antigo (so o nome) ===");
  const legado = restoreItemFromName("backup_ses_08fe0c7d_15-18-34_20-07-2026.json");
  check("data extraida do nome", legado.date === "2026-07-20");
  check("hora extraida do nome", legado.time === "15:18:34");
  check("id da sessao extraido do nome", legado.session_id === "08fe0c7d");
  check("normaliza lista de strings", Array.isArray(restoreNormalizeItems(["backup_ses_08fe0c7d_15-18-34_20-07-2026.json"])));
  check("item normalizado e objeto", typeof restoreNormalizeItems(["backup_ses_08fe0c7d_15-18-34_20-07-2026.json"])[0] === "object");
  const auto = restoreItemFromName("autosave/autosave_1.json");
  check("autosave reconhecido pelo nome", auto.kind === "autosave");

  console.log("\n=== 10. botao de APAGAR (v0.7.1) ===");
  await openRestore();
  const lista = mk("backup-list").innerHTML;
  check("botao de apagar em cada item",
    (lista.match(/class="b-del"/g) || []).length === 4);
  check("botao com o nome do arquivo em data-file",
    lista.includes('data-file="backup_ses_aaa_10-00-00_21-10-2026.json"'));
  check("botao nao dispara o restaurar (stopPropagation)",
    lista.includes("event.stopPropagation(); doDeleteBackup(this.dataset.file)"));
  // confirmacao + POST /api/backup/delete
  let deletes = [];
  const fetchOriginal = global.fetch;
  global.fetch = async (url, opts) => {
    if (url.endsWith("/api/backup/delete")) {
      deletes.push(JSON.parse(opts.body));
      return { json: async () => ({ ok: true }) };
    }
    return fetchOriginal(url, opts);
  };
  await doDeleteBackup("backup_ses_aaa_10-00-00_21-10-2026.json");
  check("confirmacao exibida antes de apagar",
    global.__confirmMsg.includes("Apagar o backup de"));
  check("POST /api/backup/delete disparado", deletes.length === 1);
  check("confirm: true no corpo da requisicao", deletes[0].confirm === true);
  check("arquivo correto no corpo",
    deletes[0].file === "backup_ses_aaa_10-00-00_21-10-2026.json");
  global.fetch = fetchOriginal;

  console.log(`\n=== RESULTADO: ${ok} ok · ${fail} falhas ===`);
  process.exit(fail ? 1 : 0);
})();
