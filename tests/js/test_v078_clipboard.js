// Teste de comportamento v0.7.8 (sem bump) — Ctrl+C copia · Ctrl+V cola no ttyd
//
// Bug relatado (29/10/2026): no terminal do UFVAI (ttyd + xterm.js) o Ctrl+C
// chegava ao PTY como ^C e a TUI do opencode ENCERRAVA a conversa; o Ctrl+V
// mandava ^V (0x16) além de colar.
//
// Este teste executa o script injetado de verdade (o mesmo que vai no
// `ttyd --index`), num DOM mínimo simulado — sem navegador:
//
//   node tests/js/test_v078_clipboard.js
//
// Contrato verificado:
//   • Ctrl+C copia a seleção e NUNCA envia ^C ao PTY;
//   • Ctrl+C sem seleção: nada é enviado (só a dica);
//   • Ctrl+Shift+C envia \x03 (saída de emergência);
//   • Ctrl+V não é interceptado (quem cola é o evento `paste`);
//   • `paste` fora do terminal é entregue ao PTY uma vez;
//   • campo de formulário fica intocado;
//   • attachCustomKeyEventHandler barra ^C/^V no xterm.
"use strict";

const { execFileSync } = require("child_process");
const path = require("path");

const RAIZ = process.env.UFVAI_ROOT || path.resolve(__dirname, "..", "..");

function codigoDoScript() {
  const py = [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(RAIZ)})`,
    "from pesquisai import launch_app as la",
    "sys.stdout.write(la._get_clipboard_script())",
  ].join("; ");
  const bruto = execFileSync("python3", ["-c", py], { encoding: "utf-8" });
  return bruto.replace(/^\s*<script>/, "").replace(/<\/script>\s*$/, "");
}

// ── DOM mínimo ──────────────────────────────────────────────────────────
function criarAmbiente() {
  const env = {
    selecao: "",
    clipboard: [],
    enviado: [], // bytes crus ao PTY (__pesquisaiSendToPTY)
    colado: [], // term.paste()
    handlers: { keydown: [], paste: [] },
    keyHandler: null,
  };

  const xtermEl = { closest: (sel) => (sel === ".xterm" ? xtermEl : null) };

  const term = {
    getSelection: () => env.selecao,
    paste: (txt) => env.colado.push(txt),
    attachCustomKeyEventHandler: (fn) => (env.keyHandler = fn),
    cols: 80,
    rows: 24,
  };

  const corpo = {
    appendChild: () => {},
    innerText: "",
  };

  const doc = {
    addEventListener: (tipo, fn) => (env.handlers[tipo] = env.handlers[tipo] || []).push(fn),
    querySelector: (sel) => (sel === ".xterm" ? xtermEl : null),
    createElement: () => ({
      style: {},
      setAttribute: () => {},
      select: () => {},
      value: "",
      textContent: "",
    }),
    execCommand: () => true,
    documentElement: { appendChild: () => {} },
    body: corpo,
  };

  const nav = {
    clipboard: {
      writeText: (txt) => {
        env.clipboard.push(txt);
        return Promise.resolve();
      },
      readText: () => Promise.resolve(""),
    },
  };

  const win = {
    term,
    getSelection: () => env.selecao,
    __pesquisaiSendToPTY: (txt) => {
      env.enviado.push(txt);
      return true;
    },
  };

  const fn = new Function(
    "window",
    "document",
    "navigator",
    "setInterval",
    "setTimeout",
    "clearTimeout",
    "console",
    codigoDoScript()
  );
  // setTimeout/setInterval inertes: a rede de segurança de 400 ms do Ctrl+V
  // não deve rodar neste teste (quem cola aqui é o evento `paste`).
  fn(win, doc, nav, () => 0, () => 0, () => 0, { log: () => {} });

  env.alvoTerminal = {
    tagName: "TEXTAREA",
    classList: { contains: (c) => c === "xterm-helper-textarea" },
    closest: (sel) => (sel === ".xterm" ? xtermEl : null),
  };
  env.alvoCorpo = {
    tagName: "BODY",
    classList: { contains: () => false },
    closest: () => null,
  };
  return env;
}

function tecla(env, props) {
  const ev = Object.assign(
    {
      ctrlKey: true,
      metaKey: false,
      altKey: false,
      shiftKey: false,
      key: "",
      target: env.alvoTerminal,
      prevented: false,
      stopped: false,
      preventDefault() {
        this.prevented = true;
      },
      stopImmediatePropagation() {
        this.stopped = true;
      },
    },
    props
  );
  env.handlers.keydown.forEach((fn) => fn(ev));
  return ev;
}

function colar(env, texto, alvo) {
  const ev = {
    clipboardData: { getData: () => texto },
    target: alvo,
    prevented: false,
    stopped: false,
    preventDefault() {
      this.prevented = true;
    },
    stopImmediatePropagation() {
      this.stopped = true;
    },
  };
  env.handlers.paste.forEach((fn) => fn(ev));
  return ev;
}

// ── runner ──────────────────────────────────────────────────────────────
let ok = 0;
const falhas = [];

function teste(nome, fn) {
  const env = criarAmbiente();
  try {
    fn(env);
    ok++;
    console.log("  ✅ " + nome);
  } catch (e) {
    falhas.push(nome + " — " + e.message);
    console.log("  ❌ " + nome + " — " + e.message);
  }
}

function igual(a, b, msg) {
  const sa = JSON.stringify(a);
  const sb = JSON.stringify(b);
  if (sa !== sb) throw new Error((msg ? msg + ": " : "") + "esperado " + sb + ", obtido " + sa);
}

function verdade(v, msg) {
  if (!v) throw new Error(msg || "esperado verdadeiro");
}

console.log("\n[UFVAI v0.7.8] Ctrl+C copia · Ctrl+V cola (ttyd + xterm.js)\n");

teste("Ctrl+C com seleção copia e NÃO envia ^C ao PTY", (env) => {
  env.selecao = "linha copiada";
  const ev = tecla(env, { key: "c" });
  igual(env.clipboard, ["linha copiada"], "clipboard");
  igual(env.enviado, [], "bytes ao PTY");
  verdade(ev.prevented, "o evento deve ser cancelado (não deixa o xterm copiar de novo)");
});

teste("Ctrl+C sem seleção não copia e não envia ^C (só dica)", (env) => {
  env.selecao = "";
  const ev = tecla(env, { key: "c" });
  igual(env.clipboard, [], "clipboard");
  igual(env.enviado, [], "bytes ao PTY");
  verdade(ev.prevented, "evento cancelado");
});

teste("Ctrl+Shift+C envia \\x03 de verdade", (env) => {
  env.selecao = "algo";
  tecla(env, { key: "C", shiftKey: true });
  igual(env.enviado, ["\x03"], "bytes ao PTY");
  igual(env.clipboard, [], "não deve copiar");
});

teste("Ctrl+V não intercepta o atalho do navegador", (env) => {
  const ev = tecla(env, { key: "v" });
  verdade(!ev.prevented, "Ctrl+V não pode ser cancelado (quebraria o paste)");
  igual(env.enviado, [], "nada vai ao PTY no keydown");
});

teste("paste fora do terminal entrega o texto ao PTY uma vez", (env) => {
  const ev = colar(env, "linha1\nlinha2", env.alvoCorpo);
  igual(env.colado, ["linha1\nlinha2"], "term.paste");
  verdade(ev.prevented, "entrega manual → cancela o default");
});

teste("paste dentro do terminal passa direto para o xterm", (env) => {
  const ev = colar(env, "abc", env.alvoTerminal);
  igual(env.colado, [], "o xterm trata (bracketed paste)");
  verdade(!ev.prevented, "não intercepta");
});

teste("campo de formulário fica intocado", (env) => {
  const ev = tecla(env, {
    key: "c",
    target: { tagName: "INPUT", classList: { contains: () => false } },
  });
  verdade(!ev.prevented, "atalho não pode ser sequestrado num input");
  igual(env.clipboard, [], "não copia");
});

teste("attachCustomKeyEventHandler barra ^C e ^V no xterm", (env) => {
  verdade(typeof env.keyHandler === "function", "handler instalado no window.term");
  igual(env.keyHandler({ ctrlKey: true, altKey: false, shiftKey: false, key: "c" }), false, "Ctrl+C");
  igual(env.keyHandler({ ctrlKey: true, altKey: false, shiftKey: false, key: "v" }), false, "Ctrl+V");
  igual(env.keyHandler({ ctrlKey: true, altKey: false, shiftKey: true, key: "v" }), true, "Ctrl+Shift+V");
  igual(env.keyHandler({ ctrlKey: true, altKey: false, shiftKey: false, key: "x" }), true, "outras teclas");
  igual(env.keyHandler({ ctrlKey: false, altKey: false, shiftKey: false, key: "c" }), true, "c sem Ctrl");
});

console.log("\n" + (falhas.length ? "❌ " : "✅ ") + ok + " passaram, " + falhas.length + " falharam\n");
if (falhas.length) {
  falhas.forEach((f) => console.log("   · " + f));
  process.exit(1);
}
