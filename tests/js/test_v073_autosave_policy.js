// Teste de regressão v0.7.5 — UFVAI
//   1) O autosave passa de 3 para 1 MINUTO.
//   2) A pergunta de retomada e' feita UMA VEZ POR SESSÃO (v0.7.5):
//        - sessão nova        -> PERGUNTA
//        - recarga na sessão  -> NÃO pergunta (marca não é consumida)
//        - restore -> reload  -> NÃO pergunta (sem loop)
//        - "new"              -> NÃO pergunta de novo nesta aba
//        - botão ↻            -> limpa a marca e reoferece
//   3) A marca vai para sessionStorage + localStorage + cookie.
//
// Node puro, sem dependencias:
//   node tests/js/test_v073_autosave_policy.js
const { execFileSync } = require("child_process");

const PKG = process.env.UFVAI_PKG || "/tmp/pesquisai/pesquisai";

// ── stubs de DOM/navegador ───────────────────────────────────────────────
const lstore = {};
const sstore = {};
global.localStorage = {
  getItem: (k) => (k in lstore ? lstore[k] : null),
  setItem: (k, v) => { lstore[k] = String(v); },
  removeItem: (k) => { delete lstore[k]; },
};
global.sessionStorage = {
  getItem: (k) => (k in sstore ? sstore[k] : null),
  setItem: (k, v) => { sstore[k] = String(v); },
  removeItem: (k) => { delete sstore[k]; },
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
global.fetch = async (url, opts) => {
  calls.push({ url, opts });
  if (url.endsWith("/api/autosave") && opts && opts.method === "POST")
    return { json: async () => ({ ok: true, file: "autosave_1.json", saved_at_local: "22/10/2026 12:00:00" }) };
  if (url.endsWith("/api/autosave"))
    return { json: async () => ({
      latest: { file: "autosave/autosave_1.json", saved_at_local: "22/10/2026 12:00:00" },
      autosaves: [
        { file: "autosave/autosave_1.json", saved_at_local: "22/10/2026 12:00:00" },
        { file: "autosave/autosave_2.json", saved_at_local: "22/10/2026 11:58:00" },
      ],
    }) };
  if (url.endsWith("/api/restore"))
    return { json: async () => ({ ok: true }) };
  return { json: async () => ({ ok: true }) };
};
global.toast = (msg, kind) => { global.__toast = { msg, kind }; };

global.I18N = {
  pt_BR: {
    "autosave.title": "Autosave", "autosave.saved": "Sessão salva no Drive",
    "autosave.off_msg": "Autosave desligado",
    "autosave.resume.when": "Autosave de",
    "autosave.resume.restoring": "Restaurando o último autosave…",
    "autosave.resume.done": "Sessão restaurada",
    "autosave.resume.none": "Nenhum autosave válido",
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

const codeOpening = sliceBlock("const UFVAI_BOOT_ID", "// ── Detecção de idioma");
const codeAutosave = sliceBlock("const AUTOSAVE_INTERVAL_MS", "// ── Inicialização");
if (!codeAutosave) { console.error("❌ bloco do autosave não encontrado"); process.exit(1); }
eval(codeOpening);
eval(codeAutosave);

let ok = 0, fail = 0;
function check(nome, cond) {
  if (cond) { ok++; console.log("  ✅", nome); }
  else { fail++; console.log("  ❌", nome); }
}

(async () => {
  console.log("=== 1. INTERVALO DO AUTOSAVE = 1 MINUTO ===");
  check("AUTOSAVE_INTERVAL_MS = 60000 (1 min)",
    /const AUTOSAVE_INTERVAL_MS\s*=\s*60000/.test(codeAutosave));
  check("não há mais o intervalo de 3 min (180000)",
    !/AUTOSAVE_INTERVAL_MS\s*=\s*180000/.test(codeAutosave));
  startAutosaveTimer();
  check("o timer criado usa 60000 ms",
    global.__timer && global.__timer.ms === 60000);

  console.log("\n=== 2. ENTRADA: a pergunta É feita (1ª vez na sessão) ===");
  reloadDom();
  calls = [];
  await checkAutosaveResume();
  check("modal abre na entrada",
    mk("autosave-overlay").classList.contains("open"));
  check("consultou /api/autosave", calls.length === 1 && calls[0].url.endsWith("/api/autosave"));

  console.log("\n=== 3. A marca vai para as TRÊS camadas ===");
  const BOOT = (html.match(/const UFVAI_BOOT_ID = "([^"]+)"/) || [])[1] || "";
  check("sessionStorage: ufvai_seen_resume = boot id", sstore["ufvai_seen_resume"] === BOOT);
  check("localStorage: ufvai_seen_resume = boot id", lstore["ufvai_seen_resume"] === BOOT);
  check("cookie: ufvai_seen_resume = boot id",
    document.cookie.indexOf("ufvai_seen_resume=" + encodeURIComponent(BOOT)) >= 0);
  check("NENHUMA flag 'offered' (bug da v0.7.2)",
    Object.keys(sstore).filter((k) => k.includes("offered")).length === 0);

  console.log("\n=== 4. RECARGA na mesma sessão: NÃO pergunta de novo ===");
  reloadDom();
  calls = [];
  await checkAutosaveResume();
  check("modal NÃO reabre", !mk("autosave-overlay").classList.contains("open"));
  check("nem consulta o backend", calls.length === 0);

  console.log("\n=== 5. RESTORE -> reload: SEM LOOP ===");
  reloadDom();
  await checkAutosaveResume();              // já marcado: não abre
  // limpa para simular a sessão em que a pergunta foi exibida
  for (const k of ["ufvai_seen_resume"]) { delete sstore[k]; delete lstore[k]; }
  __cookies = {};
  await checkAutosaveResume();              // abre
  calls = [];
  await autosaveResumeContinue();           // restaura -> agenda reload
  check("POST /api/restore disparado",
    calls.some((c) => c.url.endsWith("/api/restore")));
  // v0.7.5+: reload em 1,2 s (o backend já espera o ttyd subir).
  check("reload agendado após o restore (1,2 s)",
    !!global.__timeouts.find((t) => t.ms === 1200));
  reloadDom();                              // o reload recria o DOM
  calls = [];
  await checkAutosaveResume();              // carga apos o reload
  check("SEM LOOP: o modal NÃO volta após o reload",
    !mk("autosave-overlay").classList.contains("open"));
  check("SEM LOOP: nenhuma requisição disparada", calls.length === 0);

  console.log("\n=== 6. NOVA SESSÃO (storage limpo): pergunta de novo ===");
  reloadDom();
  delete sstore["ufvai_seen_resume"];
  delete lstore["ufvai_seen_resume"];
  __cookies = {};
  calls = [];
  await checkAutosaveResume();
  check("modal abre na sessão nova",
    mk("autosave-overlay").classList.contains("open"));
  check("consultou o backend", calls.length === 1);

  console.log("\n=== 7. 'NOVA SESSÃO' encerra a oferta nesta execução ===");
  autosaveResumeNew();
  check("marca 'resume' gravada (boot id)", sstore["ufvai_seen_resume"] === BOOT);
  reloadDom();
  calls = [];
  await checkAutosaveResume();
  check("modal NÃO abre", !mk("autosave-overlay").classList.contains("open"));
  check("nem consulta o backend", calls.length === 0);

  console.log("\n=== 8. BOTÃO ↻ reoferece sob demanda ===");
  reloadDom();
  calls = [];
  await reofferAutosaveResume();
  check("modal abre pelo ↻", mk("autosave-overlay").classList.contains("open"));

  console.log(`\n=== RESULTADO: ${ok} ok · ${fail} falhas ===`);
  process.exit(fail ? 1 : 0);
})();
