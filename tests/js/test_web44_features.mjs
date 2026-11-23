/* web44 — smoke funcional dos 9 pontos (jsdom real).
   Roda: node tests/js/test_web44_features.mjs                          */
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP = fs.readFileSync(path.join(HERE, '../../pesquisai/webui/app.js'), 'utf8');
const I18N = JSON.parse(fs.readFileSync(path.join(HERE, '../../pesquisai/webui/i18n.json'), 'utf8'));

let pass = 0, fail = 0;
const check = (label, cond) => {
  if (cond) { pass++; console.log('  ok  ' + label); }
  else { fail++; console.log('  FAIL ' + label); }
};

const HTML = fs.readFileSync(path.join(HERE, '../../pesquisai/webui/index.html'), 'utf8');
const dom = new JSDOM(HTML, { url: 'http://localhost/', runScripts: 'outside-only' });
const { window: win } = dom;

const calls = [];
let aceitaMensagem = true;
const fetchMock = async (url, opts = {}) => {
  calls.push({ url, opts });
  let body = {};
  if (url.includes('i18n.json')) body = I18N;
  else if (url.includes('/explorer?')) body = { items: [], error: '' };
  else if (url.includes('/bootstrap')) body = {
    agents: [], models: [], sessions: [], active: {}, commands: [], skills: [],
    engine: {}, locale: 'pt-BR',
  };
  else body = { ok: true };
  if (url.includes('/message') && opts.method === 'POST' && !aceitaMensagem) {
    return { ok: false, status: 500, json: async () => ({ error: 'falha' }) };
  }
  return { ok: true, status: 200, json: async () => body };
};

// SSE pronto para ensureEvents() resolver sem abrir conexão real.
class EventSourceMock {
  constructor(url) {
    this.url = url;
    this.readyState = 1;
    setTimeout(() => { if (this.onopen) this.onopen({}); }, 0);
  }
  close() { this.readyState = 2; }
}
win.EventSource = EventSourceMock;
win.fetch = fetchMock;
win.confirm = () => true;
win.matchMedia = () => ({ matches: false, addEventListener(){}, addListener(){}, removeEventListener(){} });
win.requestAnimationFrame = () => 1;
// callbacks de boot não devem disparar (evita polls e timeouts infinitos)
const realSetTimeout = win.setTimeout.bind(win);
win.setTimeout = (fn, ms) => (ms >= 100 ? 1 : realSetTimeout(fn, ms));
win.setInterval = () => 1;

win.eval(APP);
const api = win.__ufvai;
console.log('\n[0] carregamento');
check('window.__ufvai disponível', !!api);
if (!api) process.exit(1);

/* ---- 1. fila entregue ao motor ----------------------------------------- */
console.log('\n[1] fila imediata (inbox)');
api.state.sessionId = 's1';
api.state.messages = [];
api.state.stream = {};
api.state.queue = [];
const item = { text: 'pergunta na fila', attachments: [], skills: [], node: win.document.createElement('div') };
const antes = calls.length;
await api.postQueuedItem(item);
const post = calls.slice(antes).find(c => c.url.includes('/sessions/s1/message') && c.opts.method === 'POST');
check('postQueuedItem chamou POST /message', !!post);
check('texto enviado ao motor', !!post && JSON.parse(post.opts.body).text === 'pergunta na fila');
aceitaMensagem = false;
check('falha devolve false (fica na fila local)', (await api.postQueuedItem(item)) === false);
aceitaMensagem = true;

const msgBox = win.document.querySelector('#messages');
const bolha = win.document.createElement('div');
bolha.className = 'msg msg-user queued';
const bcontent = win.document.createElement('div');
bcontent.className = 'bubble';
bcontent.textContent = 'pergunta na fila';
bolha.appendChild(bcontent);
msgBox.appendChild(bolha);
api.clearQueuedBubble('pergunta na fila');
check('clearQueuedBubble removeu a bolha', !msgBox.contains(bolha));

/* ---- 2/3. reasoning ----------------------------------------------------- */
console.log('\n[2/3] raciocínio: fallback e ordem');
const answer = win.document.createElement('div'); answer.className = 'answer';
const reason = win.document.createElement('details'); reason.className = 'block reasoning';
const status = win.document.createElement('span'); status.className = 'status-run status-busy';
reason.__statusWrap = status;
api.state.stream = { m1: { wrap: win.document.createElement('div'), answer, reasoningBlock: reason,
  text: 'resposta', reasoning: 'pensei', tools: {} } };
api.finishReasoningBlocks();
check('finishReasoningBlocks concluiu', status.classList.contains('status-done') && !status.classList.contains('status-busy'));
check('insertBefore usado no streaming', APP.includes('insertBefore(slot.reasoningBlock, slot.answer)'));

/* ---- 5. jump to last ---------------------------------------------------- */
console.log('\n[5] jump to last');
const jump = win.document.querySelector('#jump-btn');
api.state.newSinceScroll = 3;
api.showJump(true);
check('botão visível', jump.hidden === false);
check('contador ↓ 3', jump.textContent === '↓ 3');
check('classe has-new', jump.classList.contains('has-new'));
const label = jump.getAttribute('aria-label') || '';
check('aria-label com número', label.includes('3'), label);
api.state.newSinceScroll = 0;
api.showJump(false);
check('botão some', jump.hidden === true && !jump.classList.contains('has-new'));

/* ---- 6. mensagens vazias ------------------------------------------------ */
console.log('\n[6] prune de mensagens vazias');
const wrapVazio = win.document.createElement('div');
msgBox.appendChild(wrapVazio);
api.state.stream = { vazio: { wrap: wrapVazio, text: '', reasoning: '', tools: {} } };
api.state.messages = [];
api.pruneEmptyStreamSlots();
check('slot vazio removido', !msgBox.contains(wrapVazio));
check('slot removido do state', !api.state.stream.vazio);

const wrapReal = win.document.createElement('div');
msgBox.appendChild(wrapReal);
api.state.stream = { real: { wrap: wrapReal, text: 'tem texto', reasoning: '', tools: {} } };
api.pruneEmptyStreamSlots();
check('slot com texto preservado', msgBox.contains(wrapReal) && !!api.state.stream.real);

/* ---- 8/9. filtros e contexto ------------------------------------------- */
console.log('\n[8/9] filtros de modelos + aviso <50k');
api.state.locale = 'pt-BR';
api.state.models = [
  { id: 'free-8k', name: 'Modelo Curto', providerID: 'google', context: 8000,
    available: true, cost: { free: true } },
  { id: 'paid-128k', name: 'Modelo Longo', providerID: 'openrouter', context: 128000,
    available: true, cost: { free: false } },
  { id: 'free-200k', name: 'Modelo Grátis Grande', providerID: 'google', context: 200000,
    available: true, cost: { free: true } },
];
api.state.providers = [{ id: 'google', name: 'Google' }, { id: 'openrouter', name: 'OpenRouter' }];
api.state.modelFilters = { free: false, available: false, provider: '' };
const list = win.document.querySelector('#model-list');
const itens = () => [...list.querySelectorAll('.model-item')];
api.renderModelList('');
check('3 modelos listados', itens().length === 3);
check('1 incompatível (8k)', itens().filter(n => n.classList.contains('incompatible')).length === 1);
check('badge incompatível escrito', itens().some(n => [...n.querySelectorAll('.badge')]
  .some(b => b.textContent.includes('incompatível'))));

api.state.modelFilters.free = true;
api.renderModelList('');
check('filtro grátis → 2 modelos', itens().length === 2);

api.state.modelFilters.free = false;
api.state.modelFilters.provider = 'google';
api.renderModelList('');
check('filtro provedor google → 2', itens().length === 2);

api.state.modelFilters = { free: false, available: false, provider: '' };
api.renderProviderFilter();
check('select de provedor preenchido', win.document.querySelector('#model-provider').options.length >= 3);
check('i18n do aviso existe', !!I18N.locales['pt-BR']['model.incompatible']);

/* ---- 4. explorador: contratos ------------------------------------------ */
console.log('\n[4] explorador: contratos');
check('rota delete no código', APP.includes("apiPost('/explorer/delete'"));
check('ordenação na URL', APP.includes('&sort=${encodeURIComponent(ordem)}'));
check('botão de excluir na lista', APP.includes('exp-act exp-del'));

console.log(`\nRESULTADO: ${pass} passaram, ${fail} falharam`);
dom.window.close();
process.exit(fail === 0 ? 0 : 1);
