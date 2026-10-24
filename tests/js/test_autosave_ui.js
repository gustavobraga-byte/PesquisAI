// Teste da interface do Autosave (v0.7.0) — default LIGADO.
// Node puro, sem dependencias: renderiza o HTML do wrapper em diretorio
// temporario e extrai o bloco JS do autosave.
//   node tests/js/test_autosave_ui.js
const { execFileSync } = require("child_process");

// ── stubs de DOM/navegador ───────────────────────────────────────────────
const store = {};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};
const els = {};
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
global.setTimeout = (fn, ms) => { global.__timeout = { fn, ms }; return 1; };
global.Blob = class { constructor() {} };
global.location = { reload: () => { global.__reloaded = true; } };
let calls = [];
global.__restoreFails = 0;   // v0.7.1: quantas falhas de restore simular
global.fetch = async (url, opts) => {
  calls.push({ url, opts });
  if (url.endsWith("/api/autosave") && opts && opts.method === "POST")
    return { json: async () => ({ ok: true, file: "autosave_1.json", saved_at_local: "21/10/2026 16:36:36" }) };
  if (url.endsWith("/api/autosave"))
    return { json: async () => ({
      latest: { file: "autosave_1.json", saved_at_local: "21/10/2026 16:36:36" },
      autosaves: [
        { file: "autosave_1.json", saved_at_local: "21/10/2026 16:36:36" },
        { file: "autosave_2.json", saved_at_local: "21/10/2026 16:30:00" },
        { file: "autosave_3.json", saved_at_local: "21/10/2026 16:20:00" },
      ],
    }) };
  if (url.endsWith("/api/restore")) {
    if (global.__restoreFails > 0) {
      global.__restoreFails -= 1;
      return { json: async () => ({ ok: false, error: "falha simulada" }) };
    }
    return { json: async () => ({ ok: true }) };
  }
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
    "ui.restore": "Restaurar",
  },
};
global._currentLang = "pt_BR";
global.BASE = "";
global.escapeHtml = (s) => String(s == null ? "" : s);

// ── renderiza o HTML do wrapper (em diretorio temporario) ───────────────
const py = `
import importlib.util, os, sys, tempfile
PKG = "/tmp/pesquisai/pesquisai"
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
let code = null;
for (const b of blocks) {
  if (b.includes("AUTOSAVE_INTERVAL_MS")) {
    const js = b.replace(/^<script[^>]*>/, "").replace(/<\/script>$/, "");
    const start = js.indexOf("const AUTOSAVE_INTERVAL_MS");
    const end = js.indexOf("// ── Inicialização");
    if (start >= 0 && end > start) code = js.slice(start, end);
    break;
  }
}
if (!code) {
  console.error("❌ bloco do autosave nao encontrado no HTML renderizado");
  process.exit(1);
}
eval(code);

let ok = 0, fail = 0;
function check(nome, cond) {
  if (cond) { ok++; console.log("  ✅", nome); }
  else { fail++; console.log("  ❌", nome); }
}

(async () => {
  console.log("=== 1. default: LIGADO (v0.7.0) ===");
  check("sem preferencia no localStorage => ligado", autosaveEnabled() === true);
  check("nenhum timer no ar ainda (so comecaria no load)", !global.__timer);
  setAutosaveUI(autosaveEnabled());
  check("interruptor marcado", mk("autosave-toggle").checked === true);
  check("classe 'on' aplicada", mk("autosave-switch").classList.contains("on"));

  console.log("\n=== 2. DESLIGAR explicitamente ===");
  toggleAutosave(false);
  check("preferencia persistida = 0", store["ufvai_autosave_enabled"] === "0");
  check("agora esta desligado", autosaveEnabled() === false);
  check("timer cancelado", !global.__timer);
  check("interruptor desmarcado", mk("autosave-toggle").checked === false);
  check("toast de desligado", global.__toast && global.__toast.msg.includes("desligado"));

  console.log("\n=== 3. religar ===");
  toggleAutosave(true);
  check("preferencia = 1", store["ufvai_autosave_enabled"] === "1");
  check("ligado de novo", autosaveEnabled() === true);
  // v0.7.3: o intervalo do autosave passou de 3 min para 1 min.
  check("timer de 1 min iniciado", global.__timer && global.__timer.ms === 60000);

  console.log("\n=== 4. tick grava no Drive ===");
  await new Promise((r) => setImmediate(r));
  calls = [];
  await autosaveTick(false);
  check("POST /api/autosave disparado", calls.length === 1 && calls[0].url.endsWith("/api/autosave"));
  check("metodo POST", calls[0].opts.method === "POST");
  check("toast de sucesso", global.__toast && global.__toast.kind === "ok");

  console.log("\n=== 5. tick NAO grava com o autosave desligado ===");
  toggleAutosave(false);
  await new Promise((r) => setImmediate(r));
  calls = [];
  await autosaveTick(false);
  check("nenhum POST com o autosave desligado", calls.length === 0);

  console.log("\n=== 6. pergunta de retomada ===");
  await new Promise((r) => setImmediate(r));
  calls = [];
  await checkAutosaveResume();
  check("GET /api/autosave disparado", calls.length === 1 && calls[0].url.endsWith("/api/autosave"));
  check("modal aberto", mk("autosave-overlay").classList.contains("open"));
  check("data/hora exibida", mk("autosave-when").textContent.includes("21/10/2026 16:36:36"));
  check("timeout nao bloqueante de 20s", global.__timeout && global.__timeout.ms === 20000);

  console.log("\n=== 7. continuar do ultimo autosave ===");
  calls = [];
  await autosaveResumeContinue();
  check("POST /api/restore com o arquivo do autosave (com prefixo)",
    calls.some((c) => c.url.endsWith("/api/restore") &&
      JSON.parse(c.opts.body).file === "autosave/autosave_1.json"));
  check("modal fechado", !mk("autosave-overlay").classList.contains("open"));

  console.log("\n=== 8. escolher nova sessao ===");
  await checkAutosaveResume();
  autosaveResumeNew();
  check("modal fechado sem restaurar", !mk("autosave-overlay").classList.contains("open"));

  console.log("\n=== 9. FALLBACK: o mais recente falha -> tenta o anterior ===");
  await checkAutosaveResume();
  calls = [];
  global.__restoreFails = 1;          // o slot 1 (mais recente) falha
  await autosaveResumeContinue();
  const restores = calls.filter((c) => c.url.endsWith("/api/restore"))
    .map((c) => JSON.parse(c.opts.body).file);
  check("primeira tentativa = autosave mais recente",
    restores[0] === "autosave/autosave_1.json");
  check("segunda tentativa = autosave anterior (fallback)",
    restores[1] === "autosave/autosave_2.json");
  check("restaurou no fallback (2 chamadas)", restores.length === 2);
  check("toast de sucesso no fallback",
    global.__toast && global.__toast.kind === "ok");
  global.__restoreFails = 0;

  console.log(`\n=== RESULTADO: ${ok} ok · ${fail} falhas ===`);
  process.exit(fail ? 1 : 0);
})();
