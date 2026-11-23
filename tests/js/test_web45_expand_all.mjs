/* web45 — smoke funcional do "expandir tudo" persistente (jsdom real).
   Valida que blocos de streaming e mensagens NOVAS após a ativação nascem
   abertos, e que o toggle do botão/atalho alterna o estado.
   Roda: NODE_PATH=<root>/node_modules node tests/js/test_web45_expand_all.mjs */
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP = fs.readFileSync(path.join(HERE, '../../pesquisai/webui/app.js'), 'utf8');
const HTML = fs.readFileSync(path.join(HERE, '../../pesquisai/webui/index.html'), 'utf8');
const I18N = JSON.parse(fs.readFileSync(path.join(HERE, '../../pesquisai/webui/i18n.json'), 'utf8'));

let pass = 0, fail = 0;
const check = (label, cond) => {
  if (cond) { pass++; console.log('  ok  ' + label); }
  else { fail++; console.log('  FAIL ' + label); }
};

const dom = new JSDOM(HTML, { url: 'http://localhost/', runScripts: 'outside-only' });
const { window: win } = dom;

const fetchMock = async (url) => {
  let body = {};
  if (url.includes('i18n.json')) body = I18N;
  else if (url.includes('/bootstrap')) body = {
    agents: [], models: [], sessions: [], active: {}, commands: [], skills: [],
    engine: {}, locale: 'pt-BR',
  };
  else if (url.includes('/explorer?')) body = { items: [], error: '' };
  else body = { ok: true };
  return { ok: true, status: 200, json: async () => body };
};
class EventSourceMock {
  constructor(url) { this.url = url; this.readyState = 1; setTimeout(() => this.onopen && this.onopen({}), 0); }
  close() { this.readyState = 2; }
}
win.EventSource = EventSourceMock;
win.fetch = fetchMock;
win.matchMedia = () => ({ matches: false, addEventListener(){}, addListener(){}, removeEventListener(){} });
win.requestAnimationFrame = () => 1;
const realSetTimeout = win.setTimeout.bind(win);
win.setTimeout = (fn, ms) => (ms >= 100 ? 1 : realSetTimeout(fn, ms));
win.setInterval = () => 1;

win.eval(APP);
const api = win.__ufvai;
console.log('\n[0] carregamento');
check('window.__ufvai disponível', !!api);
check('setAllExpanded exposto', typeof api.setAllExpanded === 'function');
check('shouldExpandBlock exposto', typeof api.shouldExpandBlock === 'function');
if (!api) process.exit(1);

const doc = win.document;
const box = doc.querySelector('#messages');

/* ---- helper respeita o estado persistente ------------------------------- */
console.log('\n[1] shouldExpandBlock');
api.state.prefs.expandReasoning = false;
api.state.prefs.expandTools = false;
api.state.allExpanded = false;
check('desligado + pref false => fechado', api.shouldExpandBlock('expandReasoning') === false);
api.state.prefs.expandTools = true;
check('desligado + pref true => aberto', api.shouldExpandBlock('expandTools') === true);
api.state.allExpanded = true;
api.state.prefs.expandReasoning = false;
api.state.prefs.expandTools = false;
check('LIGADO + pref false => ABERTO (reasoning)', api.shouldExpandBlock('expandReasoning') === true);
check('LIGADO + pref false => ABERTO (tools)', api.shouldExpandBlock('expandTools') === true);

/* ---- setAllExpanded cobre blocos vivos do streaming -------------------- */
console.log('\n[2] setAllExpanded — Streaming');
const reason = doc.createElement('details');
reason.className = 'block reasoning';
const tool1 = doc.createElement('details');
tool1.className = 'block tool';
api.state.stream = {
  m1: { wrap: doc.createElement('div'), reasoningBlock: reason, tools: { c1: tool1 },
        answer: doc.createElement('div'), text: '', reasoning: '', reasoningBlockSet: true },
};
api.setAllExpanded(true);
check('reasoning vivo ABERTO', reason.open === true);
check('tool vivo ABERTO', tool1.open === true);
check('state.allExpanded = true', api.state.allExpanded === true);
api.setAllExpanded(false);
check('reasoning vivo FECHADO', reason.open === false);
check('tool vivo FECHADO', tool1.open === false);

/* ---- novas mensagens (renderMessage) nascem abertas -------------------- */
console.log('\n[3] novas mensagens após ativação');
api.setAllExpanded(true);
const msg = {
  id: 'new-1', role: 'assistant', text: 'resposta',
  reasoning: 'raciocínio novo',
  tools: [{ name: 'bash', status: 'completed', input: {}, output: 'ok' }],
};
const wrap = api.renderMessage(msg);
const blocks = [...wrap.querySelectorAll('details.block')];
check('nova mensagem tem blocos', blocks.length >= 2);
check('todos os novos blocos ABERTOS', blocks.every(b => b.open === true));

// com o botão desligado, voltam a seguir as preferências (fechadas)
api.setAllExpanded(false);
api.state.prefs.expandReasoning = false;
api.state.prefs.expandTools = false;
const wrap2 = api.renderMessage({ ...msg, id: 'new-2' });
const blocks2 = [...wrap2.querySelectorAll('details.block')];
check('desligado: novos blocos FECHADOS', blocks2.every(b => b.open === false));

/* ---- botão alterna estado ---------------------------------------------- */
console.log('\n[4] botão alterna');
const btn = doc.querySelector('#expand-all-btn');
api.state.allExpanded = false;
btn.click();
check('clique 1 => expandido', api.state.allExpanded === true);
btn.click();
check('clique 2 => recolhido', api.state.allExpanded === false);

console.log(`\nRESULTADO: ${pass} passaram, ${fail} falharam`);
dom.window.close();
process.exit(fail === 0 ? 0 : 1);
