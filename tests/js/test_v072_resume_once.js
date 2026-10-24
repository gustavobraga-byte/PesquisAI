// Teste de regressão v0.7.2 — UFVAI
//   1) A pergunta de retomada do autosave é oferecida UMA VEZ por aba
//      (bug da v0.7.1: restore -> location.reload() -> a pergunta volta
//       -> loop infinito).
//   2) O calendário do "Restaurar" não esconde datas (dias marcados,
//      tooltip correto, chips dos meses com backup, item sem data
//      visível, alinhamento dos dias da semana).
//
// Node puro, sem dependencias:
//   node tests/js/test_v072_resume_once.js
const { execFileSync } = require("child_process");

const PKG = process.env.UFVAI_PKG || "/tmp/pesquisai/pesquisai";

// ── stubs de DOM/navegador ───────────────────────────────────────────────
const lstore = {};   // localStorage  (preferencia do autosave)
const sstore = {};   // sessionStorage (flag "retomada ja oferecida")
const sremoved = []; // chaves removidas do sessionStorage
global.localStorage = {
  getItem: (k) => (k in lstore ? lstore[k] : null),
  setItem: (k, v) => { lstore[k] = String(v); },
  removeItem: (k) => { delete lstore[k]; },
};
global.sessionStorage = {
  getItem: (k) => (k in sstore ? sstore[k] : null),
  setItem: (k, v) => { sstore[k] = String(v); },
  removeItem: (k) => { sremoved.push(k); delete sstore[k]; },
};

let els = {};
function mk(id) {
  return els[id] || (els[id] = {
    id, checked: false, textContent: "", title: "", innerHTML: "", value: "",
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
/** Simula o reload da pagina: DOM novo, sessionStorage preservado. */
function reloadDom() { els = {}; }

let __cookies = {};
global.document = {
  get cookie() {
    return Object.entries(__cookies).map(([k, v]) => `${k}=${v}`).join("; ");
  },
  set cookie(str) {
    const [pair, ...attrs] = String(str).split(";");
    const eq = pair.indexOf("=");
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    if (/expires=Thu, 01 Jan 1970/i.test(attrs.join(";"))) delete __cookies[name];
    else __cookies[name] = value;
  },
  getElementById: (id) => mk(id),
  querySelectorAll: () => [],
  querySelector: () => null,
  addEventListener: () => {},
  visibilityState: "visible",
  createElement: () => mk("tmp"),
};
global.navigator = { sendBeacon: () => true };
global.setInterval = (fn, ms) => { global.__timer = { fn, ms }; return 1; };
global.clearInterval = () => { global.__timer = null; };
global.__timeouts = [];
global.setTimeout = (fn, ms) => { global.__timeouts.push({ fn, ms }); return global.__timeouts.length; };
global.Blob = class { constructor() {} };
global.location = { reload: () => { global.__reloaded = true; } };
global.__reloaded = false;

let calls = [];
global.__restoreFails = 0;
global.fetch = async (url, opts) => {
  calls.push({ url, opts });
  if (url.endsWith("/api/autosave") && opts && opts.method === "POST")
    return { json: async () => ({ ok: true, file: "autosave_1.json", saved_at_local: "22/10/2026 00:15:00" }) };
  if (url.endsWith("/api/autosave"))
    return { json: async () => ({
      latest: { file: "autosave/autosave_1.json", saved_at_local: "22/10/2026 00:15:00" },
      autosaves: [
        { file: "autosave/autosave_1.json", saved_at_local: "22/10/2026 00:15:00" },
        { file: "autosave/autosave_2.json", saved_at_local: "22/10/2026 00:12:00" },
        { file: "autosave/autosave_3.json", saved_at_local: "22/10/2026 00:05:00" },
      ],
    }) };
  if (url.endsWith("/api/restore")) {
    if (global.__restoreFails > 0) {
      global.__restoreFails -= 1;
      return { json: async () => ({ ok: false, error: "falha simulada" }) };
    }
    return { json: async () => ({ ok: true }) };
  }
  if (url.endsWith("/api/backups"))
    return { json: async () => ({ ok: true, backups: global.__backups || [] }) };
  return { json: async () => ({ ok: true }) };
};
global.toast = (msg, kind) => { global.__toast = { msg, kind }; };

// ── contexto minimo ─────────────────────────────────────────────────────
global.I18N = {
  pt_BR: {
    "autosave.title": "Autosave", "autosave.saved": "Sessão salva no Drive",
    "autosave.off_msg": "Autosave desligado",
    "autosave.resume.when": "Autosave de",
    "autosave.resume.restoring": "Restaurando o último autosave…",
    "autosave.resume.done": "Sessão restaurada",
    "autosave.resume.none": "Nenhum autosave válido",
    "autosave.resume.again": "Retomar",
    "ui.restore": "Restaurar",
    "restore.count": "{total} backups",
    "restore.summary_filtered": "{shown} de {total} backups",
    "restore.day_tip": "{n} backups",
    "restore.month_tip": "{n} backups em {m}",
    "restore.nodate": "sem data",
    "restore.newest": "Mais recente",
    "restore.autosave": "Autossave",
    "restore.invalid": "corrompido",
    "restore.dow.0": "S", "restore.dow.1": "T", "restore.dow.2": "Q",
    "restore.dow.3": "Q", "restore.dow.4": "S", "restore.dow.5": "S",
    "restore.dow.6": "D",
  },
};
global._currentLang = "pt_BR";
global.BASE = "";
global.escapeHtml = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// ── renderiza o HTML do wrapper (em diretorio temporario) ───────────────
const py = `
import importlib.util, os, sys, tempfile
PKG = ${JSON.stringify(PKG)}
spec = importlib.util.spec_from_file_location("ufvai_resp", os.path.join(PKG, "launch_app_responsive_v041.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["ufvai_resp"] = mod
spec.loader.exec_module(mod)
mod.WRAPPER_DIR = tempfile.mkdtemp(prefix="ufvai-render-")   # NAO tocar no wrapper vivo
sys.stdout.write(mod.create_wrapper_html("http://localhost:8000", "https://drive.google.com"))
`;
let html;
try {
  html = execFileSync("python3", ["-c", py], { maxBuffer: 64 * 1024 * 1024 }).toString("utf8");
} catch (e) {
  console.error("❌ falha ao renderizar o HTML:", e.stderr ? e.stderr.toString() : e);
  process.exit(1);
}
const blocks = html.match(/<script(?![^>]*\bsrc=)[^>]*>[\s\S]*?<\/script>/g) || [];

function sliceBlock(startMark, endMark) {
  for (const b of blocks) {
    const js = b.replace(/^<script[^>]*>/, "").replace(/<\/script>$/, "");
    const s = js.indexOf(startMark);
    const e = js.indexOf(endMark);
    if (s >= 0 && e > s) return js.slice(s, e);
  }
  return null;
}

const codeOpening = sliceBlock("const UFVAI_BOOT_ID", "// ── Detecção de idioma");
const codeAutosave = sliceBlock("const AUTOSAVE_INTERVAL_MS", "// ── Inicialização");
const codeRestore = sliceBlock("let _restoreItems = []", "function closeModal()");
if (!codeOpening) { console.error("❌ bloco de abertura (v0.7.5) não encontrado"); process.exit(1); }
if (!codeAutosave) { console.error("❌ bloco do autosave não encontrado"); process.exit(1); }
if (!codeRestore) { console.error("❌ bloco do 'Restaurar' não encontrado"); process.exit(1); }
eval(codeOpening);
eval(codeAutosave);
eval(codeRestore);

let ok = 0, fail = 0;
function check(nome, cond) {
  if (cond) { ok++; console.log("  ✅", nome); }
  else { fail++; console.log("  ❌", nome); }
}

(async () => {
  // ══════════════════════════════════════════════════════════════════
  console.log("=== 1. RETOMADA: a pergunta aparece na ENTRADA (1ª vez) ===");
  reloadDom();
  calls = [];
  await checkAutosaveResume();
  check("1ª chamada abre o modal", mk("autosave-overlay").classList.contains("open"));
  check("consultou /api/autosave", calls.length === 1 && calls[0].url.endsWith("/api/autosave"));
  check("gravou a marca 'resume' no sessionStorage (v0.7.5)",
    sstore["ufvai_seen_resume"] === (html.match(/const UFVAI_BOOT_ID = "([^"]+)"/) || [])[1]);
  check("gravou a marca 'resume' no localStorage (v0.7.5)",
    typeof lstore["ufvai_seen_resume"] === "string");

  console.log("\n=== 2. RECARGA na MESMA sessão: NÃO pergunta de novo (v0.7.5) ===");
  reloadDom();
  calls = [];
  await checkAutosaveResume();
  check("modal NÃO reabre na recarga", !mk("autosave-overlay").classList.contains("open"));
  check("nem consulta o backend de novo", calls.length === 0);

  console.log("\n=== 3. RESTORE -> reload -> NÃO pergunta de novo (sem loop) ===");
  reloadDom();
  await checkAutosaveResume();
  calls = [];
  await autosaveResumeContinue();
  check("POST /api/restore disparado",
    calls.some((c) => c.url.endsWith("/api/restore")));
  // v0.7.5+: o backend já espera a porta do ttyd abrir — o reload é
  // agendado em 1,2 s (antes: 3,5 s fixos).
  const reloadCall = global.__timeouts.find((t) => t.ms === 1200);
  check("reload agendado após o restore (1,2 s)", !!reloadCall);
  reloadDom();
  global.__reloaded = false;
  calls = [];
  await checkAutosaveResume();
  check("SEM LOOP: o modal NÃO volta após o reload",
    !mk("autosave-overlay").classList.contains("open"));
  check("SEM LOOP: nenhuma requisição disparada", calls.length === 0);

  console.log("\n=== 4. botão ↻ reoferece a pergunta (sob demanda) ===");
  reloadDom();
  calls = [];
  sremoved.length = 0;
  await reofferAutosaveResume();
  check("a marca 'resume' foi limpa antes de reoferecer (v0.7.5)",
    sremoved.includes("ufvai_seen_resume"));
  check("a pergunta volta a ser oferecida", mk("autosave-overlay").classList.contains("open"));

  console.log("\n=== 5. 'Nova sessão' também encerra a oferta ===");
  reloadDom();
  await checkAutosaveResume();
  autosaveResumeNew();
  check("modal fechado", !mk("autosave-overlay").classList.contains("open"));
  reloadDom();
  await checkAutosaveResume();
  check("não reaparece depois de 'Nova sessão'",
    !mk("autosave-overlay").classList.contains("open"));

  console.log("\n=== 5b. storage do navegador bloqueado: a marca sobrevive num deles ===");
  reloadDom();
  try { sessionStorage.removeItem("ufvai_seen_resume"); } catch (e) {}
  // localStorage ainda tem a marca (é o fallback quando o sessionStorage
  // é particionado/bloqueado no iframe do Colab)
  calls = [];
  await checkAutosaveResume();
  check("com sessionStorage vazio e localStorage marcado, NÃO reabre",
    !mk("autosave-overlay").classList.contains("open"));
  check("e nem consulta o backend", calls.length === 0);

  console.log("\n=== 5c. sessão NOVA (tudo limpo): volta a perguntar ===");
  reloadDom();
  delete sstore["ufvai_seen_resume"];
  delete lstore["ufvai_seen_resume"];
  __cookies = {};   // cookie de sessão também é novo
  calls = [];
  await checkAutosaveResume();
  check("sessão nova pergunta (comportamento desejado)",
    mk("autosave-overlay").classList.contains("open"));
  check("consultou o backend", calls.length === 1);

  // ══════════════════════════════════════════════════════════════════
  console.log("\n=== 6. CALENDÁRIO: os dias com backup aparecem ===");
  global.__backups = [
    // mais recente (vira o mes inicial do calendario)
    { file: "backup_ses_aaa_10-00-00_22-10-2026.json", kind: "backup", session_id: "aaa",
      date: "2026-10-22", time: "10:00:00", datetime: "2026-10-22T10:00:00",
      timestamp: 1792893600, size: 100, size_h: "100 B", title: "S1", valid: true },
    { file: "backup_ses_aaa_11-00-00_22-10-2026.json", kind: "backup", session_id: "aaa",
      date: "2026-10-22", time: "11:00:00", datetime: "2026-10-22T11:00:00",
      timestamp: 1792897200, size: 100, size_h: "100 B", title: "S2", valid: true },
    { file: "backup_ses_bbb_09-00-00_22-10-2026.json", kind: "backup", session_id: "bbb",
      date: "2026-10-22", time: "09:00:00", datetime: "2026-10-22T09:00:00",
      timestamp: 1792890000, size: 100, size_h: "100 B", title: "S3", valid: true },
    // mes anterior
    { file: "backup_ses_ccc_09-00-00_18-06-2026.json", kind: "backup", session_id: "ccc",
      date: "2026-06-18", time: "09:00:00", datetime: "2026-06-18T09:00:00",
      timestamp: 1781763600, size: 100, size_h: "100 B", title: "S4", valid: true },
    // item SEM "date", mas com "datetime" -> a data tem de ser deduzida
    { file: "backup_ses_ddd_09-00-00_05-07-2026.json", kind: "backup", session_id: "ddd",
      datetime: "2026-07-05T09:00:00", timestamp: 1783242000, size: 100, size_h: "100 B",
      title: "S5", valid: true },
    // item SEM data nenhuma -> continua visivel, em "sem data"
    { file: "backup_ses_eee.json", kind: "backup", session_id: "eee",
      size: 100, size_h: "100 B", title: "S6", valid: true },
    // autosave (vem com "date" do backend)
    { file: "autosave/autosave_1.json", kind: "autosave", session_id: "",
      date: "2026-10-22", time: "12:00:00", datetime: "2026-10-22T12:00:00",
      timestamp: 1792900800, size: 100, size_h: "100 B", title: "AS", valid: true },
  ];
  reloadDom();
  await openRestore();
  const grid = mk("restore-grid").innerHTML;
  const chips = mk("restore-months").innerHTML;
  check("abriu no mês do backup mais recente (out/2026)",
    mk("restore-month-label").textContent.includes("2026"));
  check("dias com backup têm a classe 'has'", grid.includes('restore-day has'));
  check("o dia 22 de outubro está marcado", grid.includes(">22"));
  check("contagem exibida no dia (rd-n)", grid.includes('class="rd-n"'));
  check("tooltip corrigido ('4 backups', não '4)')", grid.includes('title="4 backups"'));
  check("tooltip NÃO tem mais o texto quebrado '4)'", !grid.includes('title="4)"'));
  check("chips dos meses com backup (3 meses)", (chips.match(/rmonth-chip/g) || []).length === 3);
  check("chip de junho/2026 presente", /jun|06/i.test(chips));
  check("chip de julho/2026 presente", /jul|07/i.test(chips));

  console.log("\n=== 7. CALENDÁRIO: filtro por data não esconde o item sem data ===");
  reloadDom();
  await openRestore();
  restorePickDate("2026-10-22");
  const listOct = mk("backup-list").innerHTML;
  check("itens de 22/10 listados (S1/S2/S3 + autosave)",
    listOct.includes("S1") && listOct.includes("S2") && listOct.includes("S3"));
  check("item SEM data continua visível no filtro (S6)", listOct.includes("S6"));
  check("item de outra data (junho) NÃO aparece", !listOct.includes("S4"));
  check("grupo 'sem data' rotulado", listOct.includes("sem data"));

  console.log("\n=== 8. CALENDÁRIO: deduz a data de quem não tem 'date' ===");
  reloadDom();
  await openRestore();
  const norm = restoreNormalizeItems([
    { file: "x.json", datetime: "2026-07-05T09:00:00" },
    { file: "y.json", timestamp: 1783242000 },
    { file: "z.json" },
  ]);
  check("data deduzida de 'datetime'", norm[0].date === "2026-07-05");
  check("hora deduzida de 'datetime'", norm[0].time === "09:00:00");
  check("data deduzida de 'timestamp'", !!norm[1].date);
  check("sem data continua sem data (vai p/ grupo 'sem data')", !norm[2].date);

  console.log("\n=== 9. CALENDÁRIO: alinhamento dos dias da semana ===");
  // outubro/2026: dia 1 = quinta-feira (coluna 3, 0 = segunda)
  const weeks = restoreBuildGrid(2026, 9);
  const firstRow = weeks[0];
  const idx = firstRow.indexOf(1);
  check("01/10/2026 cai na coluna 3 (quinta)", idx === 3);
  check("células vazias antes do dia 1", firstRow.slice(0, idx).every((c) => c === null));
  const feb = restoreBuildGrid(2026, 1);   // 01/02/2026 = domingo (coluna 6)
  check("01/02/2026 cai na coluna 6 (domingo)", feb[0].indexOf(1) === 6);

  console.log("\n=== 10. CALENDÁRIO: 'Hoje' e o estado vazio são acionáveis ===");
  reloadDom();
  await openRestore();
  restoreToday();
  check("'Hoje' seleciona a data de hoje",
    mk("restore-date").value === restoreDateKey(new Date()));

  // data SEM backup, numa lista que NAO tem item sem data (senao o item
  // sem data continua visivel e a lista nao fica vazia — comportamento
  // correto da v0.7.2, ja coberto no teste 7).
  const todosBackups = global.__backups;
  global.__backups = todosBackups.filter((b) => b.file !== "backup_ses_eee.json");
  reloadDom();
  await openRestore();
  restoreSetDate("2026-10-21");
  const htmlVazio = mk("backup-list").innerHTML;
  check("data sem backup mostra o estado vazio",
    htmlVazio.includes("Nenhum backup nesta data"));
  check("estado vazio oferece 'Todas as datas' (sem beco sem saída)",
    htmlVazio.includes("restoreClearDate()"));
  restoreClearDate();
  check("'Todas as datas' devolve todos os 6 itens",
    (mk("backup-list").innerHTML.match(/class="backup-item"/g) || []).length === 6);
  global.__backups = todosBackups;

  console.log("\n=== 11. CALENDÁRIO: 'Mais recente' volta ao mês do topo ===");
  reloadDom();
  await openRestore();
  restoreGoMonth(2020, 0);
  restoreGoNewest();
  check("voltou para outubro/2026",
    mk("restore-month-label").textContent.includes("2026"));

  console.log(`\n=== RESULTADO: ${ok} ok · ${fail} falhas ===`);
  process.exit(fail ? 1 : 0);
})();
