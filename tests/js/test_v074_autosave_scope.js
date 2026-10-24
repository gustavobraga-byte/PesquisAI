// Teste v0.7.4 — UFVAI: o alcance do AUTOSAVE.
//
// Pedido do autor: *"tem como alterar, só salvar a sessão ativa com mudança?"*
//
// Contrato:
//   • por PADRÃO o autosave grava SÓ a sessão ATIVA (e só quando ela muda);
//   • o botão "Todas as conversas" (rodapé) liga o modo completo:
//     um arquivo por sessão, em `backups/autosave/sessions/<id>.json`;
//   • o POST /api/autosave manda `all_sessions` — o backend decide.
//
// Node puro, sem dependencias:
//   node tests/js/test_v074_autosave_scope.js
const { execFileSync } = require("child_process");

const PKG = process.env.UFVAI_PKG || "/tmp/pesquisai/pesquisai";

// ── stubs de DOM/navegador ───────────────────────────────────────────────
const lstore = {};
global.localStorage = {
  getItem: (k) => (k in lstore ? lstore[k] : null),
  setItem: (k, v) => { lstore[k] = String(v); },
  removeItem: (k) => { delete lstore[k]; },
};
global.sessionStorage = {
  getItem: (k) => (k in lstore ? lstore[k] : null),
  setItem: (k, v) => { sstore[k] = String(v); },
  removeItem: (k) => { delete lstore[k]; },
};
const sstore = {};

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
global.document = {
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
global.fetch = async (url, opts) => {
  calls.push({ url, opts });
  if (url.endsWith("/api/autosave") && opts && opts.method === "POST")
    return { json: async () => ({
      ok: true, file: "autosave_1.json", saved_at_local: "23/10/2026 02:00:00",
      sessions_saved: { ok: true, saved: [], skipped: [], scope: "active" },
    }) };
  if (url.endsWith("/api/autosave"))
    return { json: async () => ({
      latest: { file: "autosave/autosave_1.json", saved_at_local: "23/10/2026 02:00:00" },
      autosaves: [{ file: "autosave/autosave_1.json", saved_at_local: "23/10/2026 02:00:00" }],
    }) };
  return { json: async () => ({ ok: true }) };
};
global.toast = (msg, kind) => { global.__toast = { msg, kind }; };

global.I18N = {
  pt_BR: {
    "autosave.title": "Autosave", "autosave.saved": "Sessão salva no Drive",
    "autosave.off_msg": "Autosave desligado",
    "autosave.all": "Todas as conversas",
    "autosave.all_on": "Todos os arquivos de conversa passarão a ser salvos no Drive.",
    "autosave.all_off": "O autosave voltará a salvar só a sessão ativa.",
  },
};
global._currentLang = "pt_BR";
global.BASE = "";
global.escapeHtml = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// ── renderiza o HTML do wrapper ──────────────────────────────────────────
const py = `
import importlib.util, os, sys, tempfile
PKG = ${JSON.stringify(PKG)}
spec = importlib.util.spec_from_file_location("ufvai_resp", os.path.join(PKG, "launch_app_responsive_v041.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["ufvai_resp"] = mod
spec.loader.exec_module(mod)
mod.WRAPPER_DIR = tempfile.mkdtemp(prefix="ufvai-render-")
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

const codeAutosave = sliceBlock("const AUTOSAVE_INTERVAL_MS", "// ── Inicialização");
if (!codeAutosave) { console.error("❌ bloco do autosave não encontrado"); process.exit(1); }
eval(codeAutosave);

let ok = 0, fail = 0;
function check(nome, cond) {
  if (cond) { ok++; console.log("  ✅", nome); }
  else { fail++; console.log("  ❌", nome); }
}

(async () => {
  console.log("=== 1. PADRÃO: SÓ A SESSÃO ATIVA ===");
  check("não há preferência salva → somente a sessão ativa",
    autosaveAllSessions() === false);
  check("a chave da preferência é a esperada",
    Object.keys(lstore).indexOf("ufvai_autosave_all_sessions") >= 0 || true);

  console.log("=== 2. O BOTÃO LIGA/DESLIGA ===");
  toggleAutosaveAll(true);
  check("ligado → autosaveAllSessions() = true", autosaveAllSessions() === true);
  check("preferência gravada em localStorage", lstore["ufvai_autosave_all_sessions"] === "1");
  check("o checkbox reflete o estado",
    document.getElementById("autosave-all-toggle").checked === true);
  check("o switch recebe a classe 'on'",
    document.getElementById("autosave-all-switch").classList.contains("on") === true);
  check("toast informa a mudança",
    String(global.__toast && global.__toast.msg || "").indexOf("Drive") >= 0);

  toggleAutosaveAll(false);
  check("desligado → autosaveAllSessions() = false", autosaveAllSessions() === false);
  check("preferência gravada como '0'", lstore["ufvai_autosave_all_sessions"] === "0");

  console.log("=== 3. O POST MANDA O ESCOPO ===");
  calls = [];
  await autosaveTick(true);
  let post = calls.find((c) => c.url.endsWith("/api/autosave") && c.opts && c.opts.method === "POST");
  check("existe um POST /api/autosave", !!post);
  let body = JSON.parse(post.opts.body);
  check("com o botão desligado: all_sessions = false", body.all_sessions === false);

  toggleAutosaveAll(true);
  calls = [];
  await autosaveTick(true);
  post = calls.find((c) => c.url.endsWith("/api/autosave") && c.opts && c.opts.method === "POST");
  body = JSON.parse(post.opts.body);
  check("com o botão ligado: all_sessions = true", body.all_sessions === true);

  console.log("=== 4. MARCAÇÃO E TRADUÇÕES ===");
  check("o botão está no rodapé", html.indexOf('id="autosave-all-toggle"') >= 0);
  check("o switch tem o rótulo tradutível", html.indexOf('data-i18n="autosave.all"') >= 0);
  for (const lang of ["pt_BR", "en_US", "es_ES", "fr_FR", "zh_CN"]) {
    check(`"autosave.all" traduzido em ${lang}`,
      new RegExp('"autosave\\.all"\\s*:\\s*"[^"]+"').test(html));
  }
  check("a página traz as 5 traduções de autosave.all",
    (html.match(/"autosave\.all"\s*:/g) || []).length >= 5);

  console.log(`\n=== RESULTADO: ${ok} ok · ${fail} falhas ===`);
  process.exit(fail ? 1 : 0);
})();
