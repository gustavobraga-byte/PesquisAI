// Teste de regressão v0.7.5 — UFVAI
//   Tela de e-mail/"Bem-vindo" e pergunta de retomada: UMA VEZ por EXECUÇÃO.
//
// Bug relatado (23/10/2026): as telas reapareciam "inúmeras vezes na mesma
// sessão" (sessionStorage particionado no iframe do Colab) e, com a correção
// anterior, deixavam de aparecer em entradas NOVAS: a marca ficava 12 h no
// localStorage — inclusive a da pergunta de retomada.
//
// Correção: a marca é escopada por UFVAI_BOOT_ID (injetado no HTML a cada
// execução). Recargas da mesma execução não repetem; uma nova execução tem
// outro ID e volta a mostrar.
//
// Node puro, sem dependências:
//   node tests/js/test_v075_opening_once.js
const { execFileSync } = require("child_process");

const PKG = process.env.UFVAI_PKG || "/tmp/pesquisai/pesquisai";

// ── storages simulados ──────────────────────────────────────────────────
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

// cookie jar mínimo (document.cookie get/set)
let cookies = {};
global.document = {
  get cookie() {
    return Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join("; ");
  },
  set cookie(str) {
    const [pair, ...attrs] = String(str).split(";");
    const eq = pair.indexOf("=");
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    if (/expires=Thu, 01 Jan 1970/i.test(attrs.join(";"))) delete cookies[name];
    else cookies[name] = value;
  },
  getElementById: () => null,
};

// ── extrai o bloco de abertura do HTML renderizado ──────────────────────
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

let ok = 0, fail = 0;
function check(nome, cond) {
  if (cond) { ok++; console.log("  ✅", nome); }
  else { fail++; console.log("  ❌", nome); }
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
if (!codeOpening) {
  console.error("❌ bloco de abertura (v0.7.5) não encontrado no HTML");
  process.exit(1);
}
eval(codeOpening);
if (typeof ufvaiOpeningGet !== "function" || typeof ufvaiOpeningMark !== "function") {
  console.error("❌ helpers de abertura não definidos");
  process.exit(1);
}
const BOOT = (html.match(/const UFVAI_BOOT_ID = "([^"]+)"/) || [])[1] || "";
check("boot id injetado pelo servidor", /^[0-9a-f]{8,}$/.test(String(BOOT)));

console.log("=== 1. marca em TRÊS camadas (sessionStorage + localStorage + cookie) ===");
check("sem marca: não visto", ufvaiOpeningGet("welcome") === false);
ufvaiOpeningMark("welcome");
check("após marcar: visto (sessionStorage)", sstore["ufvai_seen_welcome"] === BOOT);
check("após marcar: visto (localStorage)", lstore["ufvai_seen_welcome"] === BOOT);
check("após marcar: visto (cookie)", document.cookie.indexOf("ufvai_seen_welcome=") >= 0);
check("get() confirma", ufvaiOpeningGet("welcome") === true);

console.log("\n=== 2. sessionStorage perdido (iframe particionado): NÃO reabre ===");
delete sstore["ufvai_seen_welcome"];
cookies = {};
check("localStorage sozinho segura a marca", ufvaiOpeningGet("welcome") === true);

console.log("\n=== 3. marca de OUTRA execução: volta a aparecer (BUG CORRIGIDO) ===");
delete sstore["ufvai_seen_welcome"];
lstore["ufvai_seen_welcome"] = "deadbeefdeadbeef";   // execução anterior
check("marca de execução anterior NÃO conta", ufvaiOpeningGet("welcome") === false);
ufvaiOpeningMark("welcome");
check("nova marca usa o ID atual", lstore["ufvai_seen_welcome"] === BOOT);

console.log("\n=== 4. cookie de sessão sozinho também segura a marca ===");
delete sstore["ufvai_seen_resume"];
delete lstore["ufvai_seen_resume"];
document.cookie = "ufvai_seen_resume=" + BOOT + "; path=/; SameSite=Lax";
check("cookie sozinho: visto", ufvaiOpeningGet("resume") === true);

console.log("\n=== 5. botão ↻ limpa a marca em TODAS as camadas ===");
ufvaiOpeningMark("resume");
ufvaiOpeningClear("resume");
check("sessionStorage limpo", !("ufvai_seen_resume" in sstore));
check("localStorage limpo", !("ufvai_seen_resume" in lstore));
check("cookie limpo", !/ufvai_seen_resume=/.test(document.cookie));
check("get() volta a false", ufvaiOpeningGet("resume") === false);

console.log("\n=== 6. contrato nas telas (código do HTML) ===");
const mTerms = html.match(/function _openTerms\(\)\{[\s\S]*?\n    \}/);
check("_openTerms existe", !!mTerms);
check("_openTerms consulta ufvaiOpeningGet('terms')",
  !!mTerms && /ufvaiOpeningGet\(\s*["']terms["']\s*\)/.test(mTerms[0]));
check("_openTerms marca ufvaiOpeningMark('terms')",
  !!mTerms && /ufvaiOpeningMark\(\s*["']terms["']\s*\)/.test(mTerms[0]));
const mWelcome = html.match(/function _showWelcome\(email, name\)\{[\s\S]*?return true;\n      \}/);
check("_showWelcome existe", !!mWelcome);
check("_showWelcome consulta ufvaiOpeningGet('welcome')",
  !!mWelcome && /ufvaiOpeningGet\(\s*["']welcome["']\s*\)/.test(mWelcome[0]));
check("_showWelcome marca ufvaiOpeningMark('welcome')",
  !!mWelcome && /ufvaiOpeningMark\(\s*["']welcome["']\s*\)/.test(mWelcome[0]));
if (mWelcome) {
  const iMark = mWelcome[0].indexOf("ufvaiOpeningMark");
  const iShow = mWelcome[0].indexOf('style.display="flex"');
  check("_showWelcome marca ANTES de exibir", iMark >= 0 && iShow > iMark);
}
const mResume = html.match(/function showAutosaveResume\(item\)\s*\{[\s\S]*?classList\.add\("open"\);/);
check("showAutosaveResume existe", !!mResume);
check("showAutosaveResume marca 'resume' antes de abrir",
  !!mResume && mResume[0].indexOf("markAutosaveResumeOffered") >= 0 &&
  mResume[0].indexOf("markAutosaveResumeOffered") < mResume[0].indexOf('classList.add("open")'));

console.log("\n=== 7. pergunta de retomada: guarda por execução (não consome) ===");
const mCheck = html.match(/async function checkAutosaveResume\(\)\s*\{[\s\S]*?catch \(e\) \{ \/\* silencioso/);
check("checkAutosaveResume existe", !!mCheck);
check("consulta a marca ANTES do fetch",
  !!mCheck && mCheck[0].indexOf("ufvaiOpeningGet") >= 0 &&
  mCheck[0].indexOf("ufvaiOpeningGet") < mCheck[0].indexOf("fetch("));
check("NÃO consome a marca (não remove)",
  !!mCheck && !/ufvaiOpeningClear|removeItem\(AUTOSAVE_RESUME_STATE\)/.test(mCheck[0]));
check("define markAutosaveResumeOffered (chamada pelo menu Restaurar)",
  /function markAutosaveResumeOffered\(\)/.test(html));

console.log("\n=== 8. idioma NÃO reinicia o terminal na abertura (sem 2ª sessão/reload) ===");
const iSync = html.indexOf("// v0.6.15 — ADOÇÃO SILENCIOSA");
const iTry = iSync >= 0 ? html.indexOf("try {", iSync) : -1;
const iEnd = iTry >= 0 ? html.indexOf("// 2. Carrega tema", iTry) : -1;
const syncCode = (iTry >= 0 && iEnd > iTry) ? html.slice(iTry, iEnd) : "";
check("bloco de adoção silenciosa existe", !!syncCode);
check("envia restart:false", /restart:\s*false/.test(syncCode));
check("NÃO chama setLang()", syncCode.indexOf("setLang(") < 0);
check("NÃO recarrega a página", syncCode.indexOf("location.reload") < 0);

console.log("\n=== 9. HTML não pode ser cacheado (JS novo sempre carrega) ===");
const py2 = `
import io, os, re
p = os.path.join(${JSON.stringify(PKG)}, "launch_app.py")
src = io.open(p, encoding="utf-8").read()
i = src.find('if p in ("/", "/index.html")')
chunk = src[i:i+1200]
print("NO_STORE" if "no-store" in chunk else "SEM_NO_STORE")
`;
let noStore = "";
try { noStore = execFileSync("python3", ["-c", py2]).toString("utf8").trim(); } catch (e) {}
check("resposta do HTML tem Cache-Control: no-store", noStore === "NO_STORE");

console.log(`\n──── ${ok}/${ok + fail} verificações verdes ────`);
process.exit(fail ? 1 : 0);
