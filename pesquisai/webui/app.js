/* ==========================================================================
   UFVAI · web (webui-v1) — cliente novo (sem build, sem dependências)
   --------------------------------------------------------------------------
   Contrato com o servidor: /api/ufvai/*  (ver pesquisai/webapi.py)
   Eventos: SSE em /api/ufvai/events?sid=<id>

   Recursos (paridade com a interface web do OpenCode):
     · sessões (busca, criar, renomear, duplicar, compactar)
     · conversa com streaming real (texto, raciocínio, ferramentas)
     · menu "/" com os comandos do agente · menu "@" com arquivos do projeto
     · anexos de arquivo (arrastar/selecionar) e menções de arquivo
     · seletor de modelo + variante · somente o agente UFVAI
     · painel de ajustes (geral, modelo, agente, comandos, habilidades,
       sessão, atalhos, sobre)
     · ações de sessão (segundo plano, contexto) e de mensagem (copiar)
   ========================================================================== */
(() => {
  'use strict';

  /* ── infraestrutura ───────────────────────────────────────────────── */

  const BASE = (() => {
    let p = location.pathname.replace(/[^/]*$/, '');
    if (!p.endsWith('/')) p += '/';
    return p;
  })();

  const api = (p) => `${BASE}api/ufvai${p}`;
  const $ = (sel) => document.querySelector(sel);
  const isVisible = () => !document.hidden;   // v0.7.11-web41
  function debounce(fn, ms) {
    let timer = 0;
    return function debounced(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  async function apiGet(path) {
    const res = await fetch(api(path), { headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(api(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* resposta sem corpo */ }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  const state = {
    sessionId: '',
    sessions: [],
    messages: [],
    active: {},
    agents: [],
    commands: [],
    skills: [],
    models: [],
    providers: [],
    model: { id: '', providerID: '', variant: '' },
    agent: 'UFVAI',
    running: false,
    runningSince: 0,        // v0.7.11-web30: início do turno (cronômetro)
    stopping: false,        // v0.7.11-web30: interrupção pedida pelo usuário
    runClosed: false,       // v0.7.11-web30: turno já encerrado (não religar)
    lastContentChange: 0,   // v0.7.11-web30: última vez que a resposta cresceu
    stream: {},
    manualSwitch: 0,
    source: null,
    attachments: [],
    pendingSkills: [],   // menções @skill ainda não enviadas
    palette: null,      // {kind:'command'|'mention', items, index, query}
    settingsTab: 'geral',
    locale: 'pt-BR',
    settingsOpen: false,
    allExpanded: false,
    view: 'web',            // 'web' | 'ttyd' — qual moldura está visível
    sseWaiters: [],          // promises à espera da abertura do SSE
    autoScroll: true,        // v0.7.11-web25: rolagem automática ativa
    about: {},               // ficha do UFVAI (aba "Sobre")
    autosave: null,          // configuração de autosave (vinda do wrapper)
    explorerPath: '',         // pasta atual do explorador de arquivos
    explorerQuery: '',        // filtro de busca do explorador (web28)
    explorerWidth: 360,       // largura do explorador (arrastável — web28)
    previewHeight: 320,       // altura do visualizador (arrastável — web28)
    pendingUsers: [],         // mensagens do usuário ainda provisórias (web28)
    usage: null,           // {used, limit, percent} — janela de contexto
    uploads: [],           // anexos já gravados em disco pelo gateway
    // v0.7.11-web39
    bulk: { active: false, selected: new Set() }, // seleção em massa de sessões
    find: { open: false, q: '', hits: [], idx: -1 }, // busca na conversa
    promptHistory: [],     // histórico de prompts (↑/↓)
    historyIdx: -1,
    promptFavorites: [],   // prompts favoritos (v0.7.11-web40)
    queue: [],             // fila de mensagens enquanto o agente trabalha
    queueFlushing: false,
    pinned: new Set(),     // sessões fixadas (v0.7.11-web41)
    forms: [],             // formulários pendentes (v0.7.11-web42)
    formsSig: '',          // assinatura para não re-renderizar à toa
    newSinceScroll: 0,     // mensagens novas fora da rolagem
    ctxDismissed: new Set(), // sessões em que o aviso de contexto foi fechado
    prefs: {
      expandReasoning: false,
      expandTools: false,
      autosaveEnabled: true,
      ctrlEnter: false,   // v0.7.11-web40: Enter envia (padrão); Ctrl+Enter = nova linha
    },
  };

  /* ── preferências persistentes ────────────────────────────────────── */

  const PREFS_KEY = 'ufvai_web_prefs';

  function loadPrefs() {
    try {
      const raw = localStorage.getItem(PREFS_KEY);
      if (raw) Object.assign(state.prefs, JSON.parse(raw));
    } catch (e) { /* ignora */ }
  }

  function savePrefs() {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(state.prefs)); } catch (e) { /* ignora */ }
  }

  /* ── idioma (i18n) ─────────────────────────────────────────────────── */

  // v0.7.11-web23: a web segue o idioma escolhido na interface principal.
  // O dicionário vive em `i18n.json` (servido junto com o cliente) e o
  // idioma chega por `postMessage {type:'ufvai-lang'}` do wrapper — trocar o
  // idioma lá troca aqui, sem recarregar nada.
  const I18N = { locales: {}, default: 'pt-BR' };

  function localeFromTag(tag) {
    const key = String(tag || '').trim().toLowerCase().replace('-', '_');
    const map = {
      pt: 'pt-BR', pt_br: 'pt-BR', br: 'pt-BR',
      en: 'en', en_us: 'en',
      es: 'es', es_es: 'es',
      fr: 'fr', fr_fr: 'fr',
      zh: 'zh', zh_cn: 'zh',
    };
    return map[key] || null;
  }

  /**
   * Idioma escolhido na interface principal, lido do cookie.
   *
   * O cookie não depende da porta: quando a web roda no mesmo host do
   * wrapper (implantação local), o cookie ``pesquisai_lang`` é visível aqui.
   * No proxy do Colab os hosts são diferentes — aí quem manda é o
   * ``postMessage`` ``ufvai-lang``.
   */
  function localeFromCookie() {
    try {
      const match = document.cookie.match(/(?:^| )pesquisai_lang=([^;]+)/);
      return match ? localeFromTag(decodeURIComponent(match[1])) : null;
    } catch (e) { return null; }
  }

  /** Texto traduzido; `vars` substitui marcadores ``{chave}``. */
  function t(key, vars) {
    const table = I18N.locales[state.locale] || I18N.locales[I18N.default] || {};
    let value = table[key];
    if (value === undefined) value = key;
    if (vars && typeof vars === 'object') {
      Object.keys(vars).forEach((name) => {
        value = String(value).split(`{${name}}`).join(String(vars[name]));
      });
    }
    return value;
  }

  /** Aplica o idioma: textos, placeholders, títulos e o `lang` do documento. */
  function applyLocale(lang) {
    const tag = localeFromTag(lang);
    if (!tag || !I18N.locales[tag]) return false;
    state.locale = tag;
    document.documentElement.setAttribute('lang', tag);
    document.querySelectorAll('[data-i18n]').forEach((node) => {
      const value = t(node.getAttribute('data-i18n'), '');
      if (value) node.textContent = value;
    });
    document.querySelectorAll('[data-i18n-title]').forEach((node) => {
      const value = t(node.getAttribute('data-i18n-title'), '');
      if (value) node.title = value;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((node) => {
      const value = t(node.getAttribute('data-i18n-placeholder'), '');
      if (value) node.placeholder = value;
    });
    applyPlaceholder();
    try { localStorage.setItem('ufvai_web_lang', tag); } catch (e) { /* ignora */ }
    renderSessions();
    renderAttachments();
    if (state.settingsOpen) renderSettings();
    return true;
  }

  /** Em tela estreita o placeholder longo é cortado: usa a versão curta. */
  function applyPlaceholder() {
    const input = $('#input');
    if (!input) return;
    const narrow = window.matchMedia('(max-width: 560px)').matches;
    input.placeholder = narrow
      ? t('composer.placeholderShort')
      : t('composer.placeholder');
  }

  async function loadI18n() {
    try {
      const res = await fetch(`${BASE}i18n.json`, { headers: { Accept: 'application/json' } });
      if (!res.ok) return;
      const data = await res.json();
      I18N.locales = data.locales || {};
      I18N.default = data.default || 'pt-BR';
    } catch (e) { /* sem i18n: segue em português */ }
  }

  /* ── markdown (leve, seguro: escapa tudo antes) ───────────────────── */

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);
  // v0.7.11-web41: só permite esquemas seguros em links (evita javascript:)
  const safeUrl = (u) => {
    const s = String(u || '').trim();
    return /^(https?:|mailto:|\/|\.\/|#)/i.test(s) ? s : '#';
  };

  // Extensões que, ao aparecerem como "nome.ext" ou "pasta/nome.ext", viram
  // referência clicável (abre o arquivo no explorador).
  const FILE_REFERENCE_EXT = 'pdf|docx?|xlsx?|pptx?|odt|ods|odp|csv|tsv|md|txt|rst|json|ya?ml|toml|ini|cfg|conf|log|py|js|mjs|cjs|ts|tsx|jsx|sh|bash|zsh|css|scss|html?|xml|sql|r|jl|tex|bib|ipynb|env|lock|png|jpe?g|gif|webp|svg|bmp|ico|mp3|mp4|wav|zip|tar|gz';

  // v0.7.11-web30: **caminhos** — de arquivo e de PASTA — citados na
  // resposta também viram clicáveis.
  //
  // Antes só era reconhecido "nome.ext" de uma lista fixa, e só fora de
  // crases. Ficavam como texto morto: `outputs-projeto/artigos` (pasta),
  // `` `vault/moc/last-state.md` `` (caminho entre crases) e
  // `/content/drive/My Drive/PesquisAI/vault` (caminho absoluto).
  const FILE_EXT_TEST = new RegExp(`\\.(?:${FILE_REFERENCE_EXT})$`, 'i');
  const PATH_SEGMENT = "[^\\s/\\\\:*?\"<>|,;\\[\\](){}]+";
  // caminho com pelo menos uma barra: "vault/moc", "outputs-x/artigos"
  const PATH_WITH_SLASH = `(?:${PATH_SEGMENT}\\/)+\\/?${PATH_SEGMENT}`;
  // caminho absoluto no Drive — o "My Drive" tem espaço
  const PATH_ABS_DRIVE = /\/content\/drive\/My Drive\/[^\s'"`<>)\]]+/g;
  // primeiras palavras que NÃO iniciam um caminho ("e/ou", "and/or"…)
  const PATH_STOP_FIRST = new Set([
    'e', 'ou', 'and', 'or', 'de', 'da', 'do', 'dos', 'das', 'em', 'no',
    'na', 'nos', 'nas', 'se', 'the', 'of', 'for', 'y', 'a', 'o',
  ]);

  /**
   * O texto é um caminho de arquivo ou de pasta?
   *
   * @param {string} text  texto puro (sem escape)
   * @returns {boolean}
   */
  function looksLikePath(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 400 || s.includes('\n')) return false;
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) return false;   // URL
    if (/^#/.test(s)) return false;                            // âncora
    if (/[<>|]/.test(s)) return false;
    if (s.startsWith('/content/drive/My Drive/')) return true;  // caminho absoluto
    if (/\s/.test(s)) return false;                            // com espaço: só o Drive
    if (!s.includes('/')) return FILE_EXT_TEST.test(s);        // "relatorio.md"
    const parts = s.replace(/\/+$/, '').split('/').filter(Boolean);
    if (parts.length < 2) return false;
    if (parts.every((p) => p.length <= 2)) return false;       // "e/ou"
    if (PATH_STOP_FIRST.has(parts[0].toLowerCase())) return false;
    return true;
  }

  function inline(text) {
    const codes = [];
    const bare = [];
    const anchors = [];
    const files = [];
    let out = escapeHtml(text);
    out = out.replace(/`([^`\n]+)`/g, (_, code) => {
      // v0.7.11-web30: caminho entre crases também é clicável
      if (looksLikePath(code)) {
        files.push(code.trim());
        return `\x04${files.length - 1}\x04`;
      }
      codes.push(code);
      return `\x01${codes.length - 1}\x01`;
    });
    // link markdown — ANTES da URL solta (senão o "https://..." dentro do
    // link seria tratado como URL avulsa e o link quebraria)
    out = out.replace(/\[([^\]\n]+)\]\(((?:https?:\/\/)[^\s)]*(?:\([^\s)]*\)[^\s)]*)*)\)/g,
      (_, label, url) => {
        anchors.push({ label, url });
        return `\x03${anchors.length - 1}\x03`;
      });
    // v0.7.11-web28: URL solta (sem markdown) tambem e clicavel
    out = out.replace(/(^|[\s(])((?:https?:\/\/)[^\s<>"'`)\]]+)/g, (_, pre, url) => {
      bare.push(url);
      return `${pre}\x02${bare.length - 1}\x02`;
    });
    // v0.7.11-web28: referencia a arquivo (nome ou caminho) -> clicavel
    out = out.replace(
      new RegExp(`(^|[\\s(]|\\*\\*)((?:[\\w.\\-]+[\\\\/])*[\\w.\\-]+\\.(?:${FILE_REFERENCE_EXT}))(?=[\\s).,;:!?*]|$)`, 'g'),
      (_, pre, path) => {
        files.push(path);
        return `${pre}\x04${files.length - 1}\x04`;
      },
    );
    // v0.7.11-web30: caminho ABSOLUTO no Drive — o "My Drive" tem espaço,
    // então a regra geral (que não aceita espaço) não pega.
    out = out.replace(PATH_ABS_DRIVE, (match) => {
      const limpo = match.replace(/[.,;:!?]+$/, '');
      if (!limpo) return match;
      files.push(limpo);
      return `\x04${files.length - 1}\x04` + match.slice(limpo.length);
    });
    // v0.7.11-web30: caminho com barra — de ARQUIVO ou de PASTA. É a regra
    // que faltava: "outputs-projeto/artigos" (pasta) e "vault/moc" viram
    // clicáveis e abrem no explorador.
    out = out.replace(
      new RegExp(`(^|[\\s(\\[>"'«]|\\*\\*)((?:${PATH_SEGMENT}\\/)+${PATH_SEGMENT}|(?:${PATH_SEGMENT}\\/)+)`, 'g'),
      (_, pre, path) => {
        const limpo = path.replace(/[.,;:!?]+$/, '');
        if (!limpo || !looksLikePath(limpo)) return pre + path;
        files.push(limpo);
        return `${pre}\x04${files.length - 1}\x04` + path.slice(limpo.length);
      },
    );
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, '$1<em>$2</em>');
    out = out.replace(/\x01(\d+)\x01/g, (_, i) => `<code>${escapeHtml(codes[Number(i)])}</code>`);
    out = out.replace(/\x02(\d+)\x02/g, (_, i) => {
      const url = bare[Number(i)];
      return `<a href="${escapeHtml(safeUrl(url))}" target="_blank" rel="noopener">${escapeHtml(url)}</a>`;
    });
    out = out.replace(/\x03(\d+)\x03/g, (_, i) => {
      const a = anchors[Number(i)];
      return `<a href="${escapeHtml(safeUrl(a.url))}" target="_blank" rel="noopener">${escapeHtml(a.label)}</a>`;
    });
    out = out.replace(/\x04(\d+)\x04/g, (_, i) => {
      const path = files[Number(i)];
      return `<a class="file-ref" data-file="${escapeHtml(path)}" href="#" `
        + `title="${t('answer.openFile')}">${escapeHtml(path)}</a>`;
    });
    // v0.7.11-web40: LaTeX inline — \( ... \) e $ ... $ (evita valores
    // puramente numéricos, que costumam ser moeda).
    out = out.replace(/\\\(([^\\\n]{1,200})\\\)/g,
      (_, tex) => `<span class="math">${escapeHtml(tex)}</span>`);
    out = out.replace(/\$([^$\n]{1,200})\$/g, (m, tex) => {
      if (/^\s*\d+([.,]\d+)?\s*$/.test(tex)) return m;
      return `<span class="math">${escapeHtml(tex)}</span>`;
    });
    return out;
  }

  /* ── tabelas markdown (v0.7.11-web28) ─────────────────────────────── */

  /**
   * Divide uma linha de tabela em células.
   *
   * O `|` **escapado** (`\|`) e o `|` dentro de código inline (`` `a|b` ``)
   * NÃO separam células. Era exatamente aí que as tabelas com links
   * quebravam: a coluna do link era cortada e o texto vazava para fora.
   */
  function splitTableRow(line) {
    const cells = [];
    let cur = '';
    let inCode = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === '\\' && line[i + 1] === '|') { cur += '|'; i += 1; continue; }
      if (ch === '`') { inCode = !inCode; cur += ch; continue; }
      if (ch === '|' && !inCode) { cells.push(cur); cur = ''; continue; }
      cur += ch;
    }
    cells.push(cur);
    // pipes das bordas (`| a | b |` → `a`, `b`)
    if (cells.length > 1 && cells[0].trim() === '') cells.shift();
    if (cells.length > 1 && cells[cells.length - 1].trim() === '') cells.pop();
    return cells.map((c) => c.trim());
  }

  /** A linha tem forma de linha de tabela? (tem `|` e não está vazia) */
  function isTableRow(line) {
    const s = String(line || '');
    return s.includes('|') && s.trim() !== '';
  }

  /** Linha separadora de cabeçalho? (`| --- | :---: |`) */
  function isTableSeparator(line) {
    const s = String(line || '').trim();
    if (!s || !s.includes('|') || !s.includes('-')) return false;
    const cells = splitTableRow(s);
    if (!cells.length) return false;
    return cells.every((c) => /^:?-+:?$/.test(c.trim()));
  }

  /** Alinhamento declarado no separador (left / center / right). */
  function tableAligns(separator) {
    return splitTableRow(separator).map((c) => {
      const s = c.trim();
      const left = s.startsWith(':');
      const right = s.endsWith(':');
      if (left && right) return 'center';
      if (right) return 'right';
      if (left) return 'left';
      return '';
    });
  }

  /**
   * Monta o ``<table>``. As células passam por ``inline()`` — é o que faz o
   * **link** dentro da tabela virar ``<a href>`` de verdade (antes o texto
   * do link era escapado e saía cru).
   *
   * v0.7.11-web33: a tabela vai dentro de um ``.table-scroll`` — no
   * telefone uma tabela larga estourava a largura da página (o campo de
   * escrita saía da tela junto). Agora ela rola na horizontal, sem
   * esmagar o layout.
   */
  function renderTable(head, aligns, body) {
    const alignAttr = (i) => (aligns[i] ? ` style="text-align:${aligns[i]}"` : '');
    const ths = head
      .map((cell, i) => `<th${alignAttr(i)}>${inline(cell)}</th>`)
      .join('');
    const rows = body
      .map((cells) => {
        const tds = head
          .map((_, i) => `<td${alignAttr(i)}>${inline(cells[i] === undefined ? '' : cells[i])}</td>`)
          .join('');
        return `<tr>${tds}</tr>`;
      })
      .join('');
    return `<div class="table-scroll"><table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  const __mdCache = new Map();   // v0.7.11-web41: cache de Markdown por mensagem
  function md(src) {
    const __key = String(src || '');
    const __hit = __mdCache.get(__key);
    if (__hit !== undefined) return __hit;
    const lines = __key.split('\n');
    const out = [];
    let para = [];
    let list = null;

    const flushPara = () => {
      if (para.length) { out.push(`<p>${inline(para.join('\n'))}</p>`); para = []; }
    };
    const flushList = () => { if (list) { out.push(`</${list}>`); list = null; } };

    for (let i = 0; i < lines.length; i++) {
      const raw = lines[i];

      if (/^```/.test(raw)) {
        flushPara(); flushList();
        const lang = raw.slice(3).trim().toLowerCase();
        const body = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { body.push(lines[i]); i++; }
        out.push(codeBlockHtml(body.join('\n'), lang));
        continue;
      }
      // v0.7.11-web40: LaTeX em bloco ($$ ... $$)
      if (/^\s*\$\$/.test(raw)) {
        flushPara(); flushList();
        const tex = [];
        let first = raw.replace(/^\s*\$\$/, '');
        if (/\$\$\s*$/.test(first)) {
          out.push(`<div class="math-block">${escapeHtml(first.replace(/\$\$\s*$/, ''))}</div>`);
          continue;
        }
        if (first.trim()) tex.push(first);
        i++;
        while (i < lines.length && !/\$\$/.test(lines[i])) { tex.push(lines[i]); i++; }
        if (i < lines.length) {
          const tail = lines[i].replace(/\$\$.*$/, '');
          if (tail.trim()) tex.push(tail);
        }
        out.push(`<div class="math-block">${escapeHtml(tex.join('\n').trim())}</div>`);
        continue;
      }
      if (/^\s*$/.test(raw)) { flushPara(); flushList(); continue; }

      const heading = raw.match(/^(#{1,4})\s+(.*)$/);
      if (heading) {
        flushPara(); flushList();
        const level = heading[1].length;
        out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        continue;
      }
      if (/^(-{3,}|\*{3,})$/.test(raw.trim())) {
        flushPara(); flushList();
        out.push('<hr>');
        continue;
      }
      // v0.7.11-web28: tabela markdown (cabeçalho + linha separadora).
      // Fica ANTES da regra do `<hr>` — sem isso a linha `|---|---|` era
      // tratada como texto e a tabela nunca virava uma tabela.
      if (isTableRow(raw) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
        flushPara(); flushList();
        const head = splitTableRow(raw);
        const aligns = tableAligns(lines[i + 1]);
        i += 2;
        const body = [];
        while (i < lines.length && isTableRow(lines[i])) {
          body.push(splitTableRow(lines[i]));
          i += 1;
        }
        i -= 1;
        out.push(renderTable(head, aligns, body));
        continue;
      }
      const quote = raw.match(/^>\s?(.*)$/);
      if (quote) {
        flushPara(); flushList();
        out.push(`<blockquote>${inline(quote[1])}</blockquote>`);
        continue;
      }
      const bullet = raw.match(/^\s*[-*+]\s+(.*)$/);
      const numbered = raw.match(/^\s*\d+[.)]\s+(.*)$/);
      if (bullet || numbered) {
        flushPara();
        const kind = bullet ? 'ul' : 'ol';
        if (list !== kind) { flushList(); out.push(`<${kind}>`); list = kind; }
        out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
        continue;
      }
      flushList();
      para.push(raw);
    }
    flushPara(); flushList();
    const __html = out.join('\n');
    if (__mdCache.size > 300) __mdCache.clear();
    __mdCache.set(__key, __html);
    return __html;
  }

  /* ── tema ─────────────────────────────────────────────────────────── */

  const THEME_KEY = 'pesquisai_theme';

  function applyTheme(theme) {
    // aceita o valor canônico do UFVAI ("pesquisai"/"pesquisai-light") e as
    // formas abreviadas ("light"/"dark") que a interface principal usava
    const light = theme === 'pesquisai-light' || theme === 'light';
    const value = light ? 'pesquisai-light' : 'pesquisai';
    document.documentElement.setAttribute('data-theme', value);
    document.documentElement.style.colorScheme = value === 'pesquisai-light' ? 'light' : 'dark';
    try { localStorage.setItem(THEME_KEY, value); } catch (e) { /* modo restrito */ }
    // O cookie é compartilhado com a interface principal (mesmo domínio,
    // porta diferente) — o botão de tema do cabeçalho do UFVAI e o da web
    // ficam em sincronia.
    try {
      document.cookie = `pesquisai_theme=${encodeURIComponent(value)}; path=/; max-age=31536000; SameSite=Lax`;
    } catch (e) { /* ignora */ }
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type: 'ufvai-theme', theme: value }, '*');
      }
    } catch (e) { /* cross-origin bloqueado */ }
    try {
      const meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', value === 'pesquisai-light' ? '#f5f6f7' : '#141c24');
    } catch (e) { /* ignora */ }
  }

  function currentTheme() {
    try {
      const cookie = document.cookie.match(/(?:^| )pesquisai_theme=([^;]+)/);
      if (cookie) return decodeURIComponent(cookie[1]);
    } catch (e) { /* ignora */ }
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored) return stored;
    } catch (e) { /* ignora */ }
    return 'pesquisai';
  }

  window.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data.type === 'ufvai-theme') applyTheme(data.theme);
    // v0.7.11-web24: qual vista está visível no wrapper (terminal ou web).
    // A web só segue o foco do terminal quando o terminal está à frente.
    if (data.type === 'ufvai-view') {
      state.view = data.view === 'ttyd' ? 'ttyd' : 'web';
    }
    // v0.7.11-web25: estado do autosave vindo do wrapper
    if (data.type === 'ufvai-autosave-state') {
      const payload = data.payload || {};
      state.autosave = {
        enabled: !!payload.enabled,
        intervalMin: payload.intervalMin || 10,
        scope: payload.scope || 'active',
        selectedIds: payload.selectedIds || [],
        sessions: payload.sessions || [],
        known: true,
      };
      state.prefs.autosaveEnabled = state.autosave.enabled;
      if (state.settingsOpen) renderSettings();
    }
    if (data.type === 'ufvai-autosave-saved') {
      toast(t('settings.autosaveSaved'));
    }
    // v0.7.11-web23: a interface principal propaga o idioma escolhido —
    // a web troca os textos na hora, sem recarregar.
    if (data.type === 'ufvai-lang') {
      if (applyLocale(data.lang)) {
        try { localStorage.setItem('ufvai_web_lang', state.locale); } catch (e) { /* ignora */ }
        toast(t('app.tagline'));
      }
    }
    // v0.7.11-web18: a interface principal confirma que a web respondeu; sem
    // este "pong" ela cai no proxy antigo (tela em branco).
    if (data.type === 'ufvai-ping') {
      try {
        if (event.source) {
          event.source.postMessage({ type: 'ufvai-pong', url: location.href }, '*');
        }
      } catch (e) { /* cross-origin bloqueado */ }
    }
  });

  /* ── toast ────────────────────────────────────────────────────────── */

  let toastTimer = null;
  function toast(message, kind) {
    const node = $('#toast');
    node.textContent = message;
    node.className = 'toast' + (kind ? ' ' + kind : '');
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 4200);
  }

  /** O foco está num campo de texto? (evita atalhos acidentais) */
  function isDigitando(alvo) {
    if (!alvo) return false;
    const tag = String(alvo.tagName || '').toLowerCase();
    return tag === 'input' || tag === 'textarea' || tag === 'select'
      || !!alvo.isContentEditable;
  }

  /* ── entrada de texto (prompt do navegador) ──────────────────────── */

  // v0.7.11-web24: `prompt()` é BLOQUEADO dentro de iframe sem
  // `allow="modals"` — por isso renomear a sessão não fazia nada na web.
  // Este modal resolve (e ainda funciona fora do iframe).
  let askResolve = null;
  let pendingConfirm = null;   // v0.7.11-web39: ação pendente do modal de confirmação

  function askText(title, value, hint, okLabel) {
    const modal = $('#prompt-modal');
    $('#prompt-title').textContent = title || '';
    $('#prompt-hint').textContent = hint || '';
    const input = $('#prompt-input');
    input.value = value || '';
    const ok = $('#prompt-ok');
    ok.textContent = okLabel || t('session.rename');
    modal.hidden = false;
    setTimeout(() => {
      input.focus();
      input.select();
    }, 30);
    return new Promise((resolve) => { askResolve = resolve; });
  }

  function closeAsk(value) {
    const modal = $('#prompt-modal');
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    const resolve = askResolve;
    askResolve = null;
    if (resolve) resolve(value);
  }

  /* ── confirmação genérica (v0.7.11-web40) ─────────────────────────── */

  let askConfirmResolve = null;

  function askConfirm(title, message, okLabel) {
    const modal = $('#ask-modal');
    if (!modal) return Promise.resolve(false);
    $('#ask-title').textContent = title || '';
    $('#ask-message').textContent = message || '';
    const ok = $('#ask-ok');
    ok.textContent = okLabel || t('key.ok');
    modal.hidden = false;
    setTimeout(() => ok.focus(), 30);
    return new Promise((resolve) => { askConfirmResolve = resolve; });
  }

  function closeAskConfirm(value) {
    const modal = $('#ask-modal');
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    const resolve = askConfirmResolve;
    askConfirmResolve = null;
    if (resolve) resolve(!!value);
  }

  /* ── permissões (decisões do motor) ───────────────────────────────── */

  // v0.7.11-web24: quando o motor pede licença para agir, a web ficava
  // esperando em silêncio — o turno travava e as opções não apareciam.
  // Agora o pedido vira um cartão com as três decisões.

  const PERMISSION_LABELS = {
    bash: 'command',
    edit: 'edição',
    write: 'escrita',
    read: 'leitura',
    webfetch: 'acesso à internet',
    websearch: 'busca na internet',
    patch: 'edição',
    external_directory: 'acesso ao disco',
  };

  function permissionLabel(action) {
    const key = String(action || '').toLowerCase();
    return PERMISSION_LABELS[key] || key || t('tool.other');
  }

  function renderPermission(request) {
    const box = $('#permissions');
    if (!box) return;
    const id = String(request.id || '');
    if (!id) return;
    const existing = box.querySelector(`[data-pid="${id}"]`);
    if (existing) existing.remove();
    const card = el('div', 'perm-card');
    card.dataset.pid = id;
    const head = el('div', 'perm-head');
    head.appendChild(el('span', 'perm-icon', '🔐'));
    const title = el('div', 'perm-title');
    title.appendChild(el('strong', null, t('permission.title')));
    title.appendChild(el('span', 'perm-action', permissionLabel(request.action)));
    head.appendChild(title);
    card.appendChild(head);
    const msg = request.message || (request.resources || []).join('\n');
    if (msg) card.appendChild(el('pre', 'perm-msg', msg));
    const actions = el('div', 'perm-actions');
    const once = el('button', 'btn primary', t('permission.once'));
    once.addEventListener('click', () => replyPermission(id, 'once'));
    const always = el('button', 'btn', t('permission.always'));
    always.addEventListener('click', () => replyPermission(id, 'always'));
    const reject = el('button', 'btn danger', t('permission.reject'));
    reject.addEventListener('click', () => replyPermission(id, 'reject'));
    actions.appendChild(once);
    actions.appendChild(always);
    actions.appendChild(reject);
    card.appendChild(actions);
    box.appendChild(card);
    box.hidden = false;
    scrollToEnd(false);
  }

  function clearPermission(id) {
    const box = $('#permissions');
    if (!box) return;
    const node = box.querySelector(`[data-pid="${id}"]`);
    if (node) node.remove();
    box.hidden = box.children.length === 0;
  }

  async function replyPermission(id, decision) {
    if (!state.sessionId) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/permission`, {
        requestID: id, decision,
      });
      clearPermission(id);
      toast(t('permission.done'));
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  /** Recarrega os pedidos de permissão em aberto (boot e reconexão). */
  async function loadPermissions() {
    if (!state.sessionId) return;
    try {
      const data = await apiGet(`/sessions/${encodeURIComponent(state.sessionId)}/permission`);
      const rows = data.permissions || [];
      const box = $('#permissions');
      if (box) box.innerHTML = '';
      rows.forEach(renderPermission);
      if (box) box.hidden = rows.length === 0;
    } catch (e) { /* sem permissões pendentes */ }
  }

  /* ── formulários do agente (ferramenta "question") ─────────────────── */

  /**
   * v0.7.11-web38: a ferramenta ``question`` cria um FORM no motor
   * (``/api/session/{sid}/form``) com as opções. Antes a interface web não
   * mostrava nada e o turno ficava parado esperando uma resposta que o
   * usuário não tinha como dar. Agora o formulário vira um cartão com as
   * opções clicáveis; ao enviar, o gateway repassa ``{answer}`` ao motor.
   */
  function formText(field) {
    return String(field.title || field.description || field.key || '');
  }

  function renderForm(form) {
    const box = $('#forms');
    if (!box) return;
    const id = String(form.id || '');
    if (!id) return;
    const old = box.querySelector(`[data-fid="${id}"]`);
    if (old) old.remove();

    const card = el('div', 'form-card');
    card.dataset.fid = id;
    const meta = form.metadata || {};
    if (meta.kind === 'question') card.classList.add('is-question');
    if (form.title) card.appendChild(el('div', 'form-title', form.title));

    const answers = {};
    const fields = Array.isArray(form.fields) ? form.fields : [];

    fields.forEach((field) => {
      const key = String(field.key || '');
      if (!key || field.hidden) return;
      const wrap = el('div', 'form-field');
      const label = formText(field);
      if (label) wrap.appendChild(el('div', 'form-label', label));
      if (field.description && field.description !== label) {
        wrap.appendChild(el('div', 'form-desc', field.description));
      }

      const type = String(field.type || '');
      const options = Array.isArray(field.options) ? field.options : [];

      if (type === 'multiselect') {
        const multiple = !(field.maxItems !== undefined && field.maxItems !== null
          && Number(field.maxItems) <= 1);
        const chosen = new Set(Array.isArray(field.default) ? field.default : []);
        const optsBox = el('div', 'form-options');
        options.forEach((opt) => {
          const value = String(opt.value !== undefined ? opt.value : (opt.label || ''));
          const btn = el('button', 'form-option', String(opt.label || value));
          btn.type = 'button';
          if (opt.description) btn.title = String(opt.description);
          if (chosen.has(value)) btn.classList.add('on');
          btn.addEventListener('click', () => {
            if (multiple) {
              if (chosen.has(value)) { chosen.delete(value); btn.classList.remove('on'); }
              else { chosen.add(value); btn.classList.add('on'); }
              answers[key] = Array.from(chosen);
            } else {
              // o motor exige ARRAY para campos multiselect, mesmo em
              // escolha única ("Expected string array for form field").
              chosen.clear(); chosen.add(value); answers[key] = [value];
              optsBox.querySelectorAll('.form-option').forEach((n) => n.classList.remove('on'));
              btn.classList.add('on');
            }
          });
          optsBox.appendChild(btn);
        });
        wrap.appendChild(optsBox);
        if (Array.isArray(field.default)) answers[key] = field.default.slice();
      } else if (type === 'string' && options.length) {
        const optsBox = el('div', 'form-options');
        options.forEach((opt) => {
          const value = String(opt.value !== undefined ? opt.value : (opt.label || ''));
          const btn = el('button', 'form-option', String(opt.label || value));
          btn.type = 'button';
          if (opt.description) btn.title = String(opt.description);
          if (field.default === value) { btn.classList.add('on'); answers[key] = value; }
          btn.addEventListener('click', () => {
            answers[key] = value;
            optsBox.querySelectorAll('.form-option').forEach((n) => n.classList.remove('on'));
            btn.classList.add('on');
          });
          optsBox.appendChild(btn);
        });
        wrap.appendChild(optsBox);
      } else if (type === 'boolean') {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = field.default === true;
        answers[key] = cb.checked;
        cb.addEventListener('change', () => { answers[key] = cb.checked; });
        wrap.appendChild(cb);
      } else {
        const input = document.createElement('input');
        input.type = (type === 'number' || type === 'integer') ? 'number' : 'text';
        if (field.placeholder) input.placeholder = String(field.placeholder);
        if (field.default !== undefined && field.default !== null) input.value = String(field.default);
        input.addEventListener('input', () => {
          answers[key] = (input.type === 'number') ? Number(input.value) : input.value;
        });
        wrap.appendChild(input);
      }

      if (field.custom) {
        const custom = document.createElement('input');
        custom.type = 'text';
        custom.className = 'form-custom';
        custom.placeholder = t('form.custom');
        custom.addEventListener('input', () => {
          const txt = String(custom.value || '');
          if (txt.trim()) answers[key] = (type === 'multiselect') ? [txt] : txt;
        });
        wrap.appendChild(custom);
      }

      card.appendChild(wrap);
    });

    const actions = el('div', 'form-actions');
    const submit = el('button', 'btn primary', t('form.submit'));
    submit.type = 'button';
    submit.addEventListener('click', () => replyForm(id, answers));
    actions.appendChild(submit);
    card.appendChild(actions);

    box.appendChild(card);
    box.hidden = false;
    scrollToEnd(false);
  }

  function clearForm(id) {
    const box = $('#forms');
    if (!box) return;
    const node = box.querySelector(`[data-fid="${id}"]`);
    if (node) node.remove();
    box.hidden = box.children.length === 0;
  }

  async function replyForm(id, answer) {
    if (!state.sessionId) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/form`, {
        formID: id, answer,
      });
      clearForm(id);
      toast(t('form.done'));
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  async function loadForms() {
    if (!state.sessionId) return;
    try {
      const data = await apiGet(`/sessions/${encodeURIComponent(state.sessionId)}/form`);
      const rows = data.forms || [];
      state.forms = rows;
      // v0.7.11-web42: só re-renderiza quando o conjunto de formulários muda
      // (o polling não pode apagar a seleção que o usuário está fazendo).
      const sig = rows
        .map((f) => `${f.id}:${(f.fields || []).map((x) => x.key).join(',')}`)
        .join('|');
      if (sig === state.formsSig) return;
      state.formsSig = sig;
      const box = $('#forms');
      if (box) box.innerHTML = '';
      rows.forEach(renderForm);
      if (box) box.hidden = rows.length === 0;
      if (rows.length) {
        console.info('[ufvai] formulário(s) pendente(s):', rows.length);
      }
    } catch (e) { /* sem formulários pendentes */ }
  }

  /* ── autosave (configuração do wrapper, via postMessage) ───────────── */

  /**
   * v0.7.11-web25: o autosave é agendado pelo WRAPPER (é o que mantém o
   * terminal vivo). A web não compartilha `localStorage` com ele (origens
   * diferentes no proxy do Colab), então a comunicação é por `postMessage`:
   *
   *   web → wrapper : ``ufvai-autosave-get`` / ``ufvai-autosave-set``
   *   wrapper → web : ``ufvai-autosave-state`` / ``ufvai-autosave-saved``
   */
  function askAutosave() {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type: 'ufvai-autosave-get' }, '*');
      }
    } catch (e) { /* cross-origin bloqueado */ }
  }

  async function pushAutosave() {
    const cfg = state.autosave || {};
    const payload = {
      enabled: !!cfg.enabled,
      intervalMin: parseInt(cfg.intervalMin, 10) || 10,
      scope: cfg.scope || 'active',
      selectedIds: cfg.selectedIds || [],
    };
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type: 'ufvai-autosave-set', payload }, '*');
        toast(t('settings.autosaveSaved'));
      } else {
        // fora do wrapper (web aberta direto): mostra o estado local
        toast(t('settings.autosaveStandalone'));
      }
    } catch (e) {
      toast(t('settings.autosaveStandalone'), 'err');
    }
  }

  /* ── explorador de arquivos (v0.7.11-web26) ──────────────────────── */

  // Mini navegador da pasta do agente (Google Drive). Leve: sem framework,
  // só DOM — lista de arquivos + prévia mínima (texto, imagem, Office),
  // download e o link para editar no Google Drive.

  const EXPLORER_ICON = {
    directory: '📁',
    image: '🖼️',
    office: '📄',
    pdf: '📕',
    text: '📄',
    binary: '🔒',
  };

  function explorerIcon(item) {
    if (item.type === 'directory') return EXPLORER_ICON.directory;
    return EXPLORER_ICON[item.kind] || '📄';
  }

  function humanSize(bytes) {
    const value = Number(bytes || 0);
    if (!value) return '';
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} kB`;
    return `${(value / 1048576).toFixed(1)} MB`;
  }

  async function openExplorer() {
    document.body.classList.add('explorer-open');
    $('#explorer').hidden = false;
    applyExplorerWidth();
    await loadExplorer(state.explorerPath || '', state.explorerQuery || '');
  }

  function closeExplorer() {
    document.body.classList.remove('explorer-open');
    $('#explorer').hidden = true;
  }

  /**
   * Carrega a lista do explorador.
   *
   * v0.7.11-web28: com ``query`` o gateway devolve a **busca recursiva**
   * (o filtro do usuário); sem ela, a listagem da pasta.
   */
  async function loadExplorer(path, query) {
    const list = $('#exp-list');
    const needle = String(query || '').trim();
    state.explorerPath = path || '';
    state.explorerQuery = needle;
    $('#exp-path').textContent = needle ? `⌕ ${needle}` : '/' + (path || '');
    const clear = $('#exp-search-clear');
    if (clear) clear.hidden = !needle;
    list.innerHTML = '';
    list.appendChild(el('div', 'exp-empty', t('explorer.loading')));
    try {
      const url = needle
        ? `/explorer?path=${encodeURIComponent(path || '')}&q=${encodeURIComponent(needle)}`
        : `/explorer?path=${encodeURIComponent(path || '')}`;
      const data = await apiGet(url);
      list.innerHTML = '';
      if (data.error) {
        list.appendChild(el('div', 'exp-empty', data.error));
        return;
      }
      const items = data.items || [];
      if (!items.length) {
        list.appendChild(el('div', 'exp-empty',
          needle ? t('explorer.noResults') : t('explorer.empty')));
        return;
      }
      if (needle) {
        // cabeçalho com o número de resultados
        list.appendChild(el('div', 'exp-count',
          t('explorer.results', { n: items.length })));
      }
      items.forEach((item) => {
        const row = el('button', 'exp-item');
        row.type = 'button';
        row.appendChild(el('span', 'exp-icon', explorerIcon(item)));
        const nameBox = el('span', 'exp-name');
        nameBox.appendChild(el('span', null, item.name));
        // v0.7.11-web28: na busca, o caminho do item aparece (o arquivo pode
        // estar em uma subpasta) — sem isso o usuário não sabia onde abrir.
        if (needle && item.parent) {
          nameBox.appendChild(el('span', 'exp-where', `/${item.parent}`));
        }
        row.appendChild(nameBox);
        if (item.type !== 'directory') {
          row.appendChild(el('span', 'exp-size', humanSize(item.size)));
        }
        row.addEventListener('click', () => {
          if (item.type === 'directory') {
            loadExplorer(item.path, '');
          } else {
            document.querySelectorAll('#exp-list .exp-item').forEach((n) => n.classList.remove('on'));
            row.classList.add('on');
            previewExplorerFile(item);
          }
        });
        list.appendChild(row);
      });
      if (data.truncated) {
        list.appendChild(el('div', 'exp-empty', t('explorer.truncated')));
      }
    } catch (e) {
      list.innerHTML = '';
      list.appendChild(el('div', 'exp-empty', String(e.message || e)));
    }
  }

  /**
   * v0.7.11-web28: uma referência a arquivo citada na resposta (nome ou
   * caminho) abre o **arquivo no explorador** — o gateway resolve a
   * referência (`/explorer/resolve`) e a web navega até ela.
   */
  async function openFileInExplorer(reference) {
    const name = String(reference || '').trim();
    if (!name) return;
    try {
      const data = await apiGet(`/explorer/resolve?name=${encodeURIComponent(name)}`);
      if (!data || !data.ok) {
        toast((data && data.error) || t('explorer.notFound'), 'err');
        return;
      }
      document.body.classList.add('explorer-open');
      $('#explorer').hidden = false;
      applyExplorerWidth();
      if (data.dir) {
        await loadExplorer(data.path || '', '');
        // v0.7.11-web30: confirma que a PASTA foi aberta (antes não havia
        // nenhuma pista de que o clique tinha funcionado).
        toast(`${t('answer.openFolder')}: ${data.path || data.name}`);
      } else {
        const parent = String(data.path || '').includes('/')
          ? String(data.path).slice(0, String(data.path).lastIndexOf('/'))
          : '';
        await loadExplorer(parent, '');
        previewExplorerFile({ path: data.path, name: data.name });
      }
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  /**
   * Arrastar a borda entre a lista e a visualização para mudar a **altura**
   * do visualizador (v0.7.11-web28).
   */
  const PREVIEW_H_KEY = 'ufvai_explorer_preview_h';

  function applyPreviewHeight() {
    const box = $('#exp-preview');
    if (!box) return;
    const h = Math.max(120, Number(state.previewHeight || 320));
    box.style.height = `${h}px`;
    box.style.maxHeight = 'none';
    const handle = $('#exp-vresizer');
    if (handle) handle.setAttribute('aria-valuenow', String(h));
  }

  function setPreviewHeight(height) {
    state.previewHeight = Math.max(120, Math.min(900, Math.round(height)));
    applyPreviewHeight();
    try { localStorage.setItem(PREVIEW_H_KEY, String(state.previewHeight)); } catch (e) { /* ignora */ }
  }

  function loadPreviewHeight() {
    try {
      const saved = parseInt(localStorage.getItem(PREVIEW_H_KEY) || '', 10);
      if (saved) state.previewHeight = saved;
    } catch (e) { /* ignora */ }
    applyPreviewHeight();
  }

  function bindPreviewResizer() {
    const handle = $('#exp-vresizer');
    if (!handle) return;
    let arrastando = false;
    let inicioY = 0;
    let inicioAltura = 0;

    const mover = (event) => {
      if (!arrastando) return;
      const y = (event.touches && event.touches[0] ? event.touches[0].clientY : event.clientY);
      // a alça fica ACIMA do visualizador: arrastar para baixo encolhe
      setPreviewHeight(inicioAltura + (inicioY - y));
    };
    const soltar = () => {
      if (!arrastando) return;
      arrastando = false;
      document.body.classList.remove('resizing');
    };

    handle.addEventListener('pointerdown', (event) => {
      arrastando = true;
      inicioY = (event.touches && event.touches[0] ? event.touches[0].clientY : event.clientY);
      inicioAltura = Number(state.previewHeight || 320);
      document.body.classList.add('resizing');
      try { handle.setPointerCapture(event.pointerId); } catch (e) { /* ignora */ }
      event.preventDefault();
    });
    handle.addEventListener('pointermove', mover);
    handle.addEventListener('pointerup', soltar);
    handle.addEventListener('pointercancel', soltar);
    handle.addEventListener('dblclick', () => setPreviewHeight(320));
    handle.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowUp') { setPreviewHeight(state.previewHeight + 24); event.preventDefault(); }
      if (event.key === 'ArrowDown') { setPreviewHeight(state.previewHeight - 24); event.preventDefault(); }
    });
  }

  /* ── filtro de busca do explorador (v0.7.11-web28) ────────────────── */

  let searchTimer = null;

  function onExplorerSearch(value) {
    const needle = String(value || '');
    clearTimeout(searchTimer);
    // v0.7.11-web28: enquanto o usuário digita, a lista da pasta atual é
    // filtrada na hora (resposta instantânea); a busca recursiva do
    // servidor entra 350 ms depois (sem travar a digitação).
    searchTimer = setTimeout(() => {
      loadExplorer(state.explorerPath || '', needle);
    }, 350);
  }

  function clearExplorerSearch() {
    const input = $('#exp-search');
    if (input) input.value = '';
    loadExplorer(state.explorerPath || '', '');
    if (input) input.focus();
  }

  /* ── largura do explorador (arrastável — v0.7.11-web28) ──────────── */

  const EXPLORER_W_KEY = 'ufvai_explorer_width';
  const EXPLORER_MIN_W = 240;
  const EXPLORER_MAX_W = 720;

  function applyExplorerWidth() {
    const width = Math.max(EXPLORER_MIN_W, Math.min(EXPLORER_MAX_W, Number(state.explorerWidth || 360)));
    document.documentElement.style.setProperty('--explorer-w', `${width}px`);
    const resizer = $('#exp-resizer');
    if (resizer) resizer.setAttribute('aria-valuenow', String(width));
  }

  function setExplorerWidth(width) {
    state.explorerWidth = Math.max(EXPLORER_MIN_W, Math.min(EXPLORER_MAX_W, Math.round(width)));
    applyExplorerWidth();
    try { localStorage.setItem(EXPLORER_W_KEY, String(state.explorerWidth)); } catch (e) { /* ignora */ }
  }

  function loadExplorerWidth() {
    try {
      const saved = parseInt(localStorage.getItem(EXPLORER_W_KEY) || '', 10);
      if (saved) state.explorerWidth = saved;
    } catch (e) { /* ignora */ }
    applyExplorerWidth();
  }

  /**
   * Arrastar a borda esquerda do explorador para mudar a largura.
   *
   * O explorador fica à **direita**: a largura é a distância entre o
   * cursor e a borda direita da janela.
   */
  function bindExplorerResizer() {
    const resizer = $('#exp-resizer');
    if (!resizer) return;
    let arrastando = false;

    const mover = (event) => {
      if (!arrastando) return;
      const x = (event.touches && event.touches[0] ? event.touches[0].clientX : event.clientX);
      setExplorerWidth(window.innerWidth - x);
    };
    const soltar = () => {
      if (!arrastando) return;
      arrastando = false;
      document.body.classList.remove('resizing');
    };

    resizer.addEventListener('pointerdown', (event) => {
      arrastando = true;
      document.body.classList.add('resizing');
      try { resizer.setPointerCapture(event.pointerId); } catch (e) { /* ignora */ }
      event.preventDefault();
    });
    resizer.addEventListener('pointermove', mover);
    resizer.addEventListener('pointerup', soltar);
    resizer.addEventListener('pointercancel', soltar);
    resizer.addEventListener('dblclick', () => setExplorerWidth(360));
    // teclado: as setas redimensionam em passos de 24 px
    resizer.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowLeft') { setExplorerWidth(state.explorerWidth + 24); event.preventDefault(); }
      if (event.key === 'ArrowRight') { setExplorerWidth(state.explorerWidth - 24); event.preventDefault(); }
    });
  }

  /* ── prévisualização formatada (leve) ──────────────────────────────── */

  // v0.7.11-web26: a prévia é **formatada**, mas leve — sem biblioteca:
  // markdown renderizado com o `md()` já existente, CSV como tabela, JSON
  // identado e código com uma coloração mínima (escape ANTES das regex,
  // então nada de injeção de HTML).

  const HL_KEYWORDS = {
    py: 'def class return if elif else import from as with try except finally for while in not and or None True False self lambda yield pass raise async await',
    js: 'function const let var return if else for while class new this import export from async await try catch finally null undefined true false',
    ts: 'interface type enum function const let var return if else for while class new this import export from async await try catch null undefined true false',
    sh: 'if then else fi for while do done case esac function return export local echo cd ls set source',
    css: 'important media supports keyframes from to inherit initial unset auto none flex grid block inline',
    html: 'html head body div span a img script style link meta title p ul li table tr td th',
    json: 'true false null',
    yaml: 'true false null',
    toml: 'true false',
    sql: 'select from where join left right inner outer on group by order having limit offset insert into values update set delete create table drop alter index primary key foreign references not null default and or in like between is as distinct union all case when then else end count sum avg min max',
    r: 'function if else for while repeat in next break return library require true false null na inf list data frame ggplot',
    jl: 'function end if else elseif for while in return using import export struct mutable module begin let try catch finally true false nothing',
    c: 'include define if else elif endif for while do return break continue struct typedef enum union switch case default sizeof static const void int char float double long short unsigned signed',
    cpp: 'include using namespace class struct public private protected virtual override template typename return if else for while do switch case break continue new delete const static void int char float double bool auto nullptr true false',
    java: 'class interface extends implements public private protected static final void int long double float boolean char String new return if else for while do switch case break continue try catch finally throw throws import package null true false',
    go: 'package import func type struct interface map chan go defer select case switch default if else for range return var const nil true false',
    rust: 'fn let mut struct enum trait impl pub use mod match if else for while loop return break continue self Self true false None Some Ok Err where as',
    md: 'true false null',
  };

  const HL_EXT = {
    py: 'py', js: 'js', mjs: 'js', cjs: 'js', ts: 'ts', tsx: 'ts', jsx: 'js',
    sh: 'sh', bash: 'sh', zsh: 'sh', css: 'css', scss: 'css', html: 'html',
    htm: 'html', xml: 'html', json: 'json', yaml: 'yaml', yml: 'yaml', toml: 'toml',
    sql: 'sql', r: 'r', jl: 'jl', c: 'c', h: 'c', cpp: 'cpp', cc: 'cpp',
    cxx: 'cpp', hpp: 'cpp', java: 'java', go: 'go', rs: 'rust',
    md: 'md', markdown: 'md',
  };

  function highlightCode(text, lang) {
    let out = escapeHtml(text);
    const words = (HL_KEYWORDS[lang] || '').split(' ').filter(Boolean);
    if (words.length) {
      const pattern = new RegExp(`\\b(${words.join('|')})\\b`, 'g');
      out = out.replace(pattern, '<span class="hl-kw">$1</span>');
    }
    if (lang === 'py' || lang === 'sh') {
      out = out.replace(/(#[^\n]*)/g, '<span class="hl-com">$1</span>');
    } else {
      out = out.replace(/(\/\/[^\n]*)/g, '<span class="hl-com">$1</span>');
    }
    out = out.replace(/(&quot;[^&\n]*?&quot;|&#39;[^&\n]*?&#39;)/g, '<span class="hl-str">$1</span>');
    out = out.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="hl-num">$1</span>');
    return out;
  }

  /** v0.7.11-web40: bloco de código com linguagem e números de linha. */
  function codeBlockHtml(code, lang) {
    const l = String(lang || '').toLowerCase();
    if (l === 'mermaid') {
      return `<div class="mermaid">${escapeHtml(code)}</div>`;
    }
    const lines = String(code).split('\n');
    const rows = lines.map((line, idx) => {
      const html = highlightCode(line, HL_EXT[l] || l);
      return `<span class="cl"><span class="ln">${idx + 1}</span>`
        + `<span class="lc">${html || ' '}</span></span>`;
    }).join('');
    return `<pre class="code" data-lang="${escapeHtml(l)}"><code>${rows}</code></pre>`;
  }

  /* ── KaTeX/Mermaid sob demanda (CDN, com fallback offline) ─────────── */

  let katexPromise = null;
  let mermaidPromise = null;

  function ensureKatex() {
    if (window.katex) return Promise.resolve(window.katex);
    if (katexPromise) return katexPromise;
    katexPromise = new Promise((resolve, reject) => {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css';
      document.head.appendChild(css);
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js';
      s.onload = () => resolve(window.katex);
      s.onerror = () => { katexPromise = null; reject(new Error('katex')); };
      document.head.appendChild(s);
    });
    return katexPromise;
  }

  function ensureMermaid() {
    if (window.mermaid) return Promise.resolve(window.mermaid);
    if (mermaidPromise) return mermaidPromise;
    mermaidPromise = import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs')
      .then((mod) => {
        const mermaid = mod.default || mod;
        mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
        window.mermaid = mermaid;
        return mermaid;
      })
      .catch((e) => { mermaidPromise = null; throw e; });
    return mermaidPromise;
  }

  /** Renderiza LaTeX/Mermaid dentro de um nó já desenhado. */
  function decorateRich(root, isFinal) {
    if (!root || !isFinal) return;
    const maths = root.querySelectorAll('.math, .math-block');
    if (maths.length) {
      ensureKatex().then(() => {
        maths.forEach((node) => {
          if (node.dataset.texDone) return;
          node.dataset.texDone = '1';
          try {
            window.katex.render(node.textContent || '', node, {
              throwOnError: false,
              displayMode: node.classList.contains('math-block'),
            });
          } catch (e) { /* mantém o texto */ }
        });
      }).catch(() => { /* offline: mostra o LaTeX cru */ });
    }
    const diagrams = root.querySelectorAll('.mermaid');
    if (diagrams.length) {
      ensureMermaid().then((mermaid) => {
        mermaid.run({ nodes: [...diagrams] }).catch(() => {});
      }).catch(() => { /* offline: mostra o código */ });
    }
  }

  function csvToTable(text) {
    const rows = [];
    let row = [];
    let cell = '';
    let quoted = false;
    const source = String(text || '').slice(0, 120_000);
    for (let i = 0; i < source.length && rows.length < 120; i += 1) {
      const ch = source[i];
      if (quoted) {
        if (ch === '"' && source[i + 1] === '"') { cell += '"'; i += 1; }
        else if (ch === '"') quoted = false;
        else cell += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ',' || ch === ';' || ch === '\t') { row.push(cell); cell = ''; }
      else if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
      else if (ch !== '\r') cell += ch;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    if (!rows.length) return null;
    const head = rows[0].map((c) => c.trim());
    const body = rows.slice(1).filter((r) => r.some((c) => c.trim()));
    const table = el('table', 'exp-table');
    const thead = el('thead');
    const trh = el('tr');
    head.forEach((cell) => trh.appendChild(el('th', null, cell)));
    thead.appendChild(trh);
    table.appendChild(thead);
    const tbody = el('tbody');
    body.forEach((r) => {
      const tr = el('tr');
      for (let i = 0; i < head.length; i += 1) tr.appendChild(el('td', null, (r[i] || '').trim()));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  /** Conteúdo formatado da prévia, conforme o tipo do arquivo. */
  function renderPreviewContent(box, data) {
    const name = String(data.name || '');
    const suffix = name.includes('.') ? name.slice(name.lastIndexOf('.') + 1).toLowerCase() : '';
    const text = data.text || '';

    if (suffix === 'md' || suffix === 'markdown') {
      const boxMd = el('div', 'exp-prev-md');
      boxMd.innerHTML = md(text);
      box.appendChild(boxMd);
      return;
    }
    if (suffix === 'csv' || suffix === 'tsv') {
      const table = csvToTable(text);
      if (table) { box.appendChild(table); return; }
    }
    if (suffix === 'json') {
      try {
        const pretty = JSON.stringify(JSON.parse(text), null, 2);
        const pre = el('pre', 'exp-prev-text');
        pre.innerHTML = highlightCode(pretty, 'json');
        box.appendChild(pre);
        return;
      } catch (e) { /* não é JSON válido: cai no texto simples */ }
    }
    const pre = el('pre', 'exp-prev-text');
    pre.innerHTML = highlightCode(text, HL_EXT[suffix] || '');
    box.appendChild(pre);
  }

  /** v0.7.11-web28: fecha a visualização (a prévia) do arquivo. */
  function closePreview() {
    const box = $('#exp-preview');
    if (!box) return;
    box.hidden = true;
    box.innerHTML = '';
    document.querySelectorAll('#exp-list .exp-item.on').forEach((n) => n.classList.remove('on'));
  }

  async function previewExplorerFile(item) {
    const box = $('#exp-preview');
    box.hidden = false;
    box.innerHTML = '';
    box.appendChild(el('div', 'exp-empty', t('explorer.loading')));
    try {
      const data = await apiGet(`/explorer/preview?path=${encodeURIComponent(item.path)}`);
      box.innerHTML = '';
      const head = el('div', 'exp-prev-head');
      head.appendChild(el('span', 'exp-prev-name', data.name || item.name));
      const actions = el('div', 'exp-prev-actions');
      const dl = el('a', 'mini-btn', t('explorer.download'));
      dl.href = data.downloadUrl || '';
      dl.setAttribute('download', data.name || item.name);
      actions.appendChild(dl);
      const drive = el('a', 'mini-btn', t('explorer.drive'));
      drive.href = data.driveUrl || item.driveUrl || '';
      drive.target = '_blank';
      drive.rel = 'noopener';
      actions.appendChild(drive);
      // v0.7.11-web28: botão de fechar a visualização
      const close = el('button', 'mini-btn exp-prev-close', '✕');
      close.type = 'button';
      close.title = t('explorer.closePreview');
      close.setAttribute('aria-label', t('explorer.closePreview'));
      close.addEventListener('click', closePreview);
      actions.appendChild(close);
      head.appendChild(actions);
      box.appendChild(head);

      const body = el('div', 'exp-prev-body');
      if (data.error) body.appendChild(el('p', 'exp-prev-note', data.error));
      if (data.kind === 'image' && data.inlineUrl) {
        const img = document.createElement('img');
        img.className = 'exp-prev-image';
        img.alt = data.name || '';
        img.src = data.inlineUrl;
        body.appendChild(img);
      } else if (data.kind === 'pdf' && data.inlineUrl) {
        // v0.7.11-web28: o PDF é renderizado pelo navegador dentro da web
        const frame = document.createElement('iframe');
        frame.className = 'exp-prev-pdf';
        frame.src = data.inlineUrl;
        frame.title = data.name || 'PDF';
        frame.setAttribute('loading', 'lazy');
        body.appendChild(frame);
      } else if (data.html) {
        // v0.7.11-web28: Word em MODO LEITURA — o HTML vem do próprio
        // pacote .docx (títulos, negrito, listas, tabelas, links, imagens).
        const doc = el('div', 'exp-prev-doc');
        doc.innerHTML = data.html;
        body.appendChild(doc);
      } else if (data.text) {
        renderPreviewContent(body, data);
      }
      if (data.truncated) {
        body.appendChild(el('p', 'exp-prev-note', t('explorer.truncated')));
      }
      box.appendChild(body);
    } catch (e) {
      box.innerHTML = '';
      box.appendChild(el('div', 'exp-empty', String(e.message || e)));
    }
  }

  /* ── finalizar sessão (com confirmação) ───────────────────────────── */

  // v0.7.11-web26: encerrar o trabalho com a sessão. Sempre pergunta antes
  // — e oferece as duas saídas reais: arquivar (a conversa continua na lista,
  // marcada com ✔) ou excluir do histórico (o autosave no Drive é o
  // arquivo de segurança).

  function askFinalize() {
    const modal = $('#confirm-modal');
    const row = currentSession();
    $('#confirm-title').textContent = t('session.finalize');
    $('#confirm-message').textContent = t('session.finalizeAsk')
      .replace('{title}', row ? sessionTitle(row) : '');
    pendingConfirm = {
      archive: () => finalizeSession('archive'),
      delete: () => finalizeSession('delete'),
    };
    modal.hidden = false;
  }

  function runConfirm(mode) {
    const action = pendingConfirm ? pendingConfirm[mode] : null;
    pendingConfirm = null;
    if (action) action();
    else $('#confirm-modal').hidden = true;
  }

  function closeConfirm() {
    pendingConfirm = null;
    $('#confirm-modal').hidden = true;
  }

  async function finalizeSession(mode) {
    const sid = state.sessionId;
    if (!sid) { closeConfirm(); return; }
    try {
      const result = await apiPost(`/sessions/${encodeURIComponent(sid)}/finalize`, { mode });
      closeConfirm();
      toast(t('session.finalizeDone'));
      await refreshSessions();
      if (mode === 'delete') {
        const next = state.sessions.find((s) => s.id !== sid);
        if (next) await openSession(next.id);
        else await newSession();
      } else if (result && result.title) {
        // a sessão foi arquivada: o título no topo acompanha
        const row = state.sessions.find((s) => s.id === sid);
        if (row) row.title = result.title;
        $('#session-title').textContent = result.title;
        renderSessions();
      }
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  /* ── sobrecarga do servidor / retry (v0.7.11-web27) ──────────────── */

  // Quando o provedor está saturado (429/503/“overloaded”/cota), o motor
  // agenda uma nova tentativa e emite `session.retry.scheduled`. A interface
  // mostra isso de forma **distinta** (âmbar, com contagem regressiva): não é
  // falha — é o servidor sobrecarregado e o retry está em curso. Os outros
  // erros aparecem em **vermelho**, com o detalhe técnico.

  let retryTimer = null;
  let retryEndsAt = 0;

  function showRetryNotice(info) {
    const banner = $('#retry-banner');
    if (!banner) return;
    const delay = Math.max(0, Number(info.delayMs || 0));
    const attempt = Number(info.attempt || 0);
    $('#retry-title').textContent = t('retry.overloaded');
    const detail = String(info.message || '').trim();
    $('#retry-detail').textContent = detail || t('retry.detail');
    banner.hidden = false;
    retryEndsAt = Date.now() + delay;
    updateRetryCount();
    if (retryTimer) clearInterval(retryTimer);
    retryTimer = setInterval(updateRetryCount, 1000);
  }

  function updateRetryCount() {
    const box = $('#retry-banner');
    if (!box || box.hidden) return;
    const restante = Math.max(0, retryEndsAt - Date.now());
    const seg = Math.ceil(restante / 1000);
    const count = $('#retry-count');
    if (count) count.textContent = seg > 0 ? `${seg}s` : '…';
    if (restante <= 0) {
      if (retryTimer) { clearInterval(retryTimer); retryTimer = null; }
      const detail = $('#retry-detail');
      if (detail) detail.textContent = t('retry.waiting');
    }
  }

  function hideRetryNotice() {
    const banner = $('#retry-banner');
    if (banner) banner.hidden = true;
    if (retryTimer) { clearInterval(retryTimer); retryTimer = null; }
    retryEndsAt = 0;
  }

  /** Erro comum (vermelho) — diferente da sobrecarga. */
  function showErrorNotice(info) {
    const box = $('#errors');
    if (!box) return;
    const card = el('div', 'error-card');
    card.appendChild(el('span', 'ec-title', t('error.title')));
    const detail = String(info.error || '').trim();
    if (detail) card.appendChild(el('span', 'ec-detail', detail));
    const status = Number(info.status || 0);
    if (status) card.appendChild(el('span', 'ec-detail', `HTTP ${status}`));
    box.appendChild(card);
    box.hidden = false;
    scrollToEnd(false);
  }

  function clearErrorNotices() {
    const box = $('#errors');
    if (box) { box.innerHTML = ''; box.hidden = true; }
  }

  /* ── sessões ──────────────────────────────────────────────────────── */

  function relativeTime(ms) {
    if (!ms) return '';
    const diff = Math.max(0, Date.now() - ms);
    const min = Math.floor(diff / 60000);
    if (min < 1) return 'agora';
    if (min < 60) return `${min} min`;
    const hours = Math.floor(min / 60);
    if (hours < 24) return `${hours} h`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days} d`;
    return new Date(ms).toLocaleDateString('pt-BR');
  }

  function sessionTitle(row) {
    if (row.title && row.title.trim()) return row.title.trim();
    return row.id.slice(0, 10);
  }

  function currentSession() {
    return state.sessions.find((s) => s.id === state.sessionId) || null;
  }

  function renderSessions() {
    const list = $('#sessions');
    const filter = ($('#session-search').value || '').trim().toLowerCase();
    list.innerHTML = '';
    const rows = state.sessions.filter((row) => {
      if (!row || !row.id) return false;   // v0.7.11-web39: nunca quebra com item inválido
      if (!filter) return true;
      return (row.title || '').toLowerCase().includes(filter) || row.id.toLowerCase().includes(filter);
    });
    if (!rows.length) {
      list.appendChild(el('div', 'model-group', 'sem sessões'));
      return;
    }
    // v0.7.11-web41: fixadas primeiro, depois por atualização
    rows.sort((a, b) => {
      const pa = state.pinned.has(a.id) ? 1 : 0;
      const pb = state.pinned.has(b.id) ? 1 : 0;
      if (pa !== pb) return pb - pa;
      return Number(b.updated || b.created || 0) - Number(a.updated || a.created || 0);
    });
    let lastGroup = '';
    rows.forEach((row) => {
      const inBulk = state.bulk.active;
      if (!inBulk) {
        const g = sessionGroup(row.updated || row.created);
        if (g !== lastGroup) {
          list.appendChild(el('div', 'session-group', t(`sessions.${g}`)));
          lastGroup = g;
        }
      }
      const selected = state.bulk.selected.has(row.id);
      const pinned = state.pinned.has(row.id);
      let cls = 'session-item' + (row.id === state.sessionId ? ' active' : '');
      if (inBulk) cls += ' bulk-mode';
      if (selected) cls += ' bulk-on';
      if (pinned) cls += ' pinned';
      const item = el('button', cls);
      item.type = 'button';
      if (inBulk) item.appendChild(el('span', 's-check', selected ? '☑' : '☐'));
      if (state.active[row.id]) item.appendChild(el('span', 's-dot'));
      item.appendChild(el('span', 's-title', sessionTitle(row)));
      item.appendChild(el('span', 's-time', relativeTime(row.updated || row.created)));
      if (!inBulk) {
        const pin = el('span', 's-pin', pinned ? '📌' : '📍');
        pin.title = pinned ? t('sessions.unpin') : t('sessions.pin');
        pin.setAttribute('role', 'button');
        pin.addEventListener('click', (event) => {
          event.preventDefault();
          event.stopPropagation();
          togglePin(row.id);
        });
        item.appendChild(pin);
      }
      item.addEventListener('click', () => {
        if (state.bulk.active) { toggleBulk(row.id); return; }
        openSession(row.id, { focus: true });
      });
      // v0.7.11-web20: duplo clique no nome renomeia a sessão
      if (!inBulk) {
        item.addEventListener('dblclick', (event) => {
          event.preventDefault();
          event.stopPropagation();
          renameSession(row.id);
        });
      }
      list.appendChild(item);
    });
    updateBulkBar();
  }

  /* ── agrupamento e fixação de sessões (v0.7.11-web41) ─────────────── */

  function sessionGroup(ms) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const t = Number(ms) || 0;
    if (t >= today) return 'today';
    if (t >= today - 86400000) return 'yesterday';
    if (t >= today - 6 * 86400000) return 'week';
    return 'older';
  }

  function loadPinned() {
    try {
      const raw = localStorage.getItem('ufvai_pinned_sessions');
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          state.pinned = new Set(arr.filter((x) => typeof x === 'string'));
        }
      }
    } catch (e) { /* sem fixadas */ }
  }

  function togglePin(id) {
    if (!id) return;
    if (state.pinned.has(id)) state.pinned.delete(id);
    else state.pinned.add(id);
    try {
      localStorage.setItem('ufvai_pinned_sessions', JSON.stringify([...state.pinned]));
    } catch (e) { /* storage cheio */ }
    renderSessions();
  }

  /* ── seleção em massa de sessões (v0.7.11-web39) ──────────────────── */

  function toggleBulkMode(force) {
    state.bulk.active = force !== undefined ? !!force : !state.bulk.active;
    if (!state.bulk.active) state.bulk.selected.clear();
    const bar = $('#bulk-bar');
    if (bar) bar.hidden = !state.bulk.active;
    const btn = $('#bulk-toggle');
    if (btn) btn.classList.toggle('on', state.bulk.active);
    renderSessions();
  }

  function toggleBulk(id) {
    const set = state.bulk.selected;
    if (set.has(id)) set.delete(id); else set.add(id);
    renderSessions();
  }

  function updateBulkBar() {
    const bar = $('#bulk-bar');
    if (!bar) return;
    const n = state.bulk.selected.size;
    const count = $('#bulk-count');
    if (count) count.textContent = String(n);
    const arch = $('#bulk-archive');
    const del = $('#bulk-delete');
    if (arch) arch.disabled = n === 0;
    if (del) del.disabled = n === 0;
  }

  function askBulk() {
    const n = state.bulk.selected.size;
    if (!n) return;
    $('#confirm-title').textContent = t('bulk.title');
    $('#confirm-message').textContent = t('bulk.confirm').replace('{n}', String(n));
    pendingConfirm = {
      archive: () => bulkFinalize('archive'),
      delete: () => bulkFinalize('delete'),
    };
    $('#confirm-modal').hidden = false;
  }

  async function bulkFinalize(mode) {
    const ids = [...state.bulk.selected];
    if (!ids.length) { closeConfirm(); return; }
    const activeWas = ids.includes(state.sessionId);
    closeConfirm();
    let done = 0;
    for (const id of ids) {
      try {
        await apiPost(`/sessions/${encodeURIComponent(id)}/finalize`, { mode });
        done += 1;
      } catch (e) { /* segue com os demais */ }
    }
    toggleBulkMode(false);
    await refreshSessions();
    toast(t('bulk.done').replace('{n}', String(done)));
    if (activeWas) {
      if (mode === 'delete') {
        const next = state.sessions.find((s) => !ids.includes(s.id));
        if (next) await openSession(next.id);
        else await newSession();
      } else {
        await openSession(state.sessionId);
      }
    }
  }

  function renderUsage() {
    const row = currentSession();
    const pill = $('#usage-pill');
    if (!row) { pill.hidden = true; return; }
    const tokens = (row.tokens || {});
    const parts = [];
    const total = (tokens.input || 0) + (tokens.output || 0) + (tokens.reasoning || 0);
    if (total) parts.push(`${Math.round(total / 1000)}k tokens`);
    if (row.cost) parts.push(`$${Number(row.cost).toFixed(2)}`);
    // v0.7.11-web23: percentual da janela de contexto
    const usage = state.usage;
    if (usage && usage.limit) {
      const pct = Math.max(0, Math.min(100, Number(usage.percent) || 0));
      parts.push(`${pct.toFixed(pct < 10 ? 1 : 0)}% ${t('top.context')}`);
      pill.title = `${Math.round(usage.used / 1000)}k / ${Math.round(usage.limit / 1000)}k ${t('top.context')}`;
    }
    if (!parts.length) { pill.hidden = true; return; }
    pill.hidden = false;
    pill.textContent = parts.join(' · ');
  }

  /** Atualiza o uso da janela de contexto da sessão aberta. */
  async function refreshUsage() {
    if (!state.sessionId) return;
    try {
      const data = await apiGet(`/sessions/${encodeURIComponent(state.sessionId)}/usage`);
      state.usage = data || null;
      renderUsage();
      maybeWarnContext();
    } catch (e) { /* motor fora do ar: mantém o último valor */ }
  }

  /** v0.7.11-web39: avisa quando a janela de contexto passa de 80%. */
  function maybeWarnContext() {
    const box = $('#context-warning');
    if (!box) return;
    const usage = state.usage;
    const sid = state.sessionId;
    const pct = usage && usage.limit ? Number(usage.percent) || 0 : 0;
    if (pct >= 80 && !state.ctxDismissed.has(sid)) {
      const text = $('#context-warning-text');
      if (text) text.textContent = t('ctx.warning').replace('{pct}', pct.toFixed(0));
      box.hidden = false;
    } else {
      box.hidden = true;
    }
  }

  /* ── mensagens ────────────────────────────────────────────────────── */

  const TOOL_LIMITS = { input: 2500, output: 6000 };

  function truncate(text, limit) {
    const value = String(text ?? '');
    if (value.length <= limit) return value;
    return `${value.slice(0, limit)}
… (${value.length - limit} caracteres omitidos)`;
  }

  /** Rótulo curto da ferramenta (nomes próprios do motor). */
  function toolLabel(name) {
    const raw = String(name || '');
    const key = raw.toLowerCase().replace(/[^a-z]/g, '');
    const map = {
      shell: 'toolname.shell', bash: 'toolname.shell', write: 'toolname.write',
      edit: 'toolname.edit', read: 'toolname.read', list: 'toolname.list',
      grep: 'toolname.grep', glob: 'toolname.glob', patch: 'toolname.patch',
      todowrite: 'toolname.todo', webfetch: 'toolname.web', websearch: 'toolname.web',
      task: 'toolname.task', skill: 'toolname.skill',
    };
    const id = map[key];
    if (id) return t(id);
    return raw || t('toolname.other');
  }

  /** Diff por linhas: devolve {kind:'add'|'del'|'ctx', text}. */
  function diffRows(oldText, newText) {
    const a = String(oldText ?? '').split('\n');
    const b = String(newText ?? '').split('\n');
    let start = 0;
    while (start < a.length && start < b.length && a[start] === b[start]) start += 1;
    let endA = a.length;
    let endB = b.length;
    while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
      endA -= 1; endB -= 1;
    }
    const rows = [];
    a.slice(0, start).forEach((text) => rows.push({ kind: 'ctx', text }));
    a.slice(start, endA).forEach((text) => rows.push({ kind: 'del', text }));
    b.slice(start, endB).forEach((text) => rows.push({ kind: 'add', text }));
    a.slice(endA).forEach((text) => rows.push({ kind: 'ctx', text }));
    return rows;
  }

  /** Desenha o diff: adições em verde, supressões em vermelho. */
  function renderDiff(container, rows) {
    const box = el('div', 'diff');
    rows.forEach((row) => {
      const line = el('div', 'diff-row ' + row.kind);
      line.appendChild(el('span', 'diff-sign', row.kind === 'add' ? '+' : (row.kind === 'del' ? '−' : ' ')));
      line.appendChild(el('span', 'diff-text', row.text || ' '));
      box.appendChild(line);
    });
    container.appendChild(box);
    return box;
  }

  /** Bloco de diff a partir do payload do gateway ({added, removed}). */
  function diffFromPayload(payload) {
    if (!payload) return [];
    const rows = [];
    (payload.removed || []).forEach((text) => rows.push({ kind: 'del', text }));
    (payload.added || []).forEach((text) => rows.push({ kind: 'add', text }));
    return rows;
  }

  /** Entrada da ferramenta em formato legível (nada de JSON em uma linha). */
  function formatToolInput(name, input) {
    if (input === undefined || input === null) return '';
    const key = String(name || '').toLowerCase();
    if (typeof input === 'string') return `$ ${input}`;
    if (key.includes('shell') || key.includes('bash')) {
      const cmd = input.command || input.cmd || input.script || '';
      const extra = Object.entries(input)
        .filter(([k]) => !['command', 'cmd', 'script'].includes(k))
        .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join(' · ');
      return `$ ${cmd}${extra ? `\n${extra}` : ''}`;
    }
    if (key.includes('write') || key.includes('edit') || key.includes('patch')) {
      const path = input.filePath || input.path || input.file || '';
      const head = path ? `${t('tool.file')}: ${path}` : '';
      return head;
    }
    try {
      return truncate(JSON.stringify(input, null, 2), TOOL_LIMITS.input);
    } catch (e) {
      return truncate(String(input), TOOL_LIMITS.input);
    }
  }

  /** Tela de entrada da ferramenta: cabeçalho + diff/preview + saída. */
  function toolContent(name, input, output, diff) {
    const wrap = el('div', 'tool-content');
    const key = String(name || '').toLowerCase();
    const path = (input && typeof input === 'object')
      ? (input.filePath || input.path || input.file || '')
      : '';

    if (path) {
      wrap.appendChild(el('div', 'tool-path', path));
    }

    // diff: do gateway (write/edit) ou calculado do próprio `edit`
    let rows = diffFromPayload(diff);
    if (!rows.length && input && typeof input === 'object'
        && typeof input.oldString === 'string' && typeof input.newString === 'string') {
      rows = diffRows(input.oldString, input.newString);
    }
    if (rows.length) {
      const added = rows.filter((r) => r.kind === 'add').length;
      const removed = rows.filter((r) => r.kind === 'del').length;
      const legend = el('div', 'diff-legend');
      legend.appendChild(el('span', 'dl-add', `+${added} ${t('tool.added')}`));
      legend.appendChild(el('span', 'dl-del', `−${removed} ${t('tool.removed')}`));
      wrap.appendChild(legend);
      renderDiff(wrap, rows);
    } else if (input && typeof input === 'object' && typeof input.content === 'string') {
      // `write` sem foto anterior: mostra a prévia do conteúdo gravado
      const preview = el('pre', 'tool-preview', truncate(input.content, 1200));
      wrap.appendChild(preview);
    } else {
      const text = formatToolInput(name, input);
      if (text) wrap.appendChild(el('pre', 'tool-preview', text));
    }

    if (output) {
      wrap.appendChild(el('pre', 'tool-output', truncate(output, TOOL_LIMITS.output)));
    }
    return wrap;
  }

  /** Resumo compacto do uso de ferramentas (estilo "Used 39 · Write, Shell"). */
  function toolSummary(tools) {
    if (!tools || !tools.length) return null;
    const names = [];
    tools.forEach((tool) => {
      const label = toolLabel(tool.name);
      if (!names.includes(label)) names.push(label);
    });
    const count = tools.length;
    const node = el('button', 'tool-summary');
    node.type = 'button';
    node.appendChild(el('span', 'ts-count', `${count}`));
    node.appendChild(el('span', 'ts-label', count === 1 ? t('tool.call') : t('tool.calls')));
    node.appendChild(el('span', 'ts-names', names.join(' · ')));
    return node;
  }

  /** Botão de copiar — usado na resposta, no raciocínio e nas ferramentas. */
  function miniCopy(getText, label) {
    const btn = el('button', 'mini-btn copy', label || t('tool.copy'));
    btn.type = 'button';
    btn.addEventListener('click', async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const text = getText();
      if (!text) { toast(t('warn.copyFailed'), 'err'); return; }
      try {
        await navigator.clipboard.writeText(text);
        toast(t('tool.copied'));
      } catch (e) {
        toast(t('tool.copyFail'), 'err');
      }
    });
    return btn;
  }

  /**
   * Indicador de atividade de um bloco (raciocínio ou ferramenta).
   *
   * v0.7.11-web28: enquanto o bloco está **em execução**, aparece uma
   * **espiral amarela girando**; quando **conclui**, o rótulo fica **verde**;
   * quando **falha**, **vermelho**.
   *
   * ``kind``: ``running`` | ``done`` | ``error``.
   */
  function setBlockStatus(details, kind, label) {
    if (!details) return;
    const wrap = details.__statusWrap || details.__status;
    const spin = details.__spin;
    const labelNode = details.__label;
    const state = kind === 'done' ? 'done' : (kind === 'error' ? 'error' : 'busy');
    if (spin) spin.hidden = state !== 'busy';
    if (labelNode) {
      labelNode.textContent = (label === undefined || label === null) ? (
        state === 'error' ? t('tool.error')
          : state === 'done' ? t('tool.done')
            : t('tool.running')
      ) : label;
    }
    if (wrap) {
      wrap.className = `status-run status-${state}`;
      wrap.hidden = false;
    }
  }

  function textBlock(label, body, cls, state) {
    const details = el('details', 'block' + (cls ? ' ' + cls : ''));
    const summary = el('summary');
    summary.appendChild(el('span', 'block-label', label));
    // v0.7.11-web28: indicador de raciocínio em andamento (espiral
    // amarela) — vira verde quando o raciocínio termina.
    const running = state === 'running';
    const statusWrap = el('span', 'status-run ' + (running ? 'status-busy' : 'status-done'));
    const spin = el('span', 'spin');
    spin.setAttribute('aria-hidden', 'true');
    spin.hidden = !running;
    const labelNode = el('span', 'status-label', running ? t('tool.running') : t('tool.done'));
    statusWrap.appendChild(spin);
    statusWrap.appendChild(labelNode);
    summary.appendChild(statusWrap);
    details.appendChild(summary);
    const bodyNode = el('div', 'block-body', body || '');
    details.appendChild(bodyNode);
    details.__body = bodyNode;
    details.__status = statusWrap;
    details.__statusWrap = statusWrap;
    details.__spin = spin;
    details.__label = labelNode;
    // v0.7.11-web23: copiar o raciocínio
    summary.appendChild(miniCopy(() => bodyNode.textContent || ''));
    return details;
  }

  function toolBlock(name, status) {
    const details = el('details', 'block tool');
    const summary = el('summary');
    const head = el('span', 'tool-head');
    head.appendChild(el('span', 'tool-name', toolLabel(name)));
    // v0.7.11-web28: espiral amarela enquanto a ferramenta roda; verde quando
    // conclui; vermelho quando dá erro.
    const statusNode = el('span', 'status-run status-busy');
    const spin = el('span', 'spin');
    spin.setAttribute('aria-hidden', 'true');
    const labelNode = el('span', 'status-label', status || t('tool.running'));
    statusNode.appendChild(spin);
    statusNode.appendChild(labelNode);
    head.appendChild(statusNode);
    summary.appendChild(head);
    details.appendChild(summary);
    const body = el('div', 'block-body');
    details.appendChild(body);
    details.__body = body;
    details.__status = statusNode;
    details.__statusWrap = statusNode;
    details.__spin = spin;
    details.__label = labelNode;
    // v0.7.11-web23: copiar a ferramenta (entrada + saída)
    summary.appendChild(miniCopy(() => body.textContent || ''));
    return details;
  }

  function assistantShell(message) {
    const wrap = el('div', 'msg msg-assistant');
    const who = el('div', 'who');
    who.appendChild(el('b', null, message.agent || 'UFVAI'));
    if (message.model && message.model.id) {
      who.appendChild(el('span', 'tag', message.model.id));
    }
    wrap.appendChild(who);
    return wrap;
  }

  function copyButton(getText, label) {
    const actions = el('div', 'msg-actions');
    actions.appendChild(miniCopy(getText, label || t('tool.copy')));
    return actions;
  }

  /* ── ações por mensagem, metadados e editar/regenerar (web40) ────── */

  function actionButton(label, title, handler) {
    const b = el('button', 'mini-btn', label);
    b.type = 'button';
    if (title) b.title = title;
    b.addEventListener('click', handler);
    return b;
  }

  function insertIntoComposer(text) {
    const input = $('#input');
    if (!input) return;
    const current = input.value || '';
    input.value = current ? `${current}\n${text}` : text;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    autoGrow();
  }

  function quoteMessage(text) {
    const sel = window.getSelection ? String(window.getSelection() || '').trim() : '';
    const base = sel || String(text || '');
    if (!base) return;
    insertIntoComposer(base.split('\n').map((l) => `> ${l}`).join('\n') + '\n\n');
    toast(t('msg.quoted'));
  }

  function useAsPrompt(text) {
    const input = $('#input');
    if (!input || !text) return;
    input.value = text;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    autoGrow();
  }

  /* ── favoritos de prompts (v0.7.11-web40) ─────────────────────────── */

  function loadFavorites() {
    try {
      const raw = localStorage.getItem('ufvai_prompt_favorites');
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          state.promptFavorites = arr.filter((x) => typeof x === 'string').slice(0, 50);
        }
      }
    } catch (e) { /* sem favoritos */ }
  }

  function saveFavorites() {
    try {
      localStorage.setItem('ufvai_prompt_favorites', JSON.stringify(state.promptFavorites));
    } catch (e) { /* storage cheio */ }
  }

  function renderFavMenu() {
    const menu = $('#fav-menu');
    if (!menu) return;
    menu.innerHTML = '';
    const current = ($('#input').value || '').trim();
    if (current) {
      const add = el('button', 'fav-item fav-add', `＋ ${t('fav.save')}`);
      add.type = 'button';
      add.addEventListener('click', () => {
        if (!state.promptFavorites.includes(current)) state.promptFavorites.unshift(current);
        state.promptFavorites = state.promptFavorites.slice(0, 50);
        saveFavorites();
        renderFavMenu();
        toast(t('fav.saved'));
      });
      menu.appendChild(add);
    }
    if (!state.promptFavorites.length) {
      menu.appendChild(el('div', 'fav-empty', t('fav.empty')));
    } else {
      state.promptFavorites.forEach((text, idx) => {
        const row = el('div', 'fav-row');
        const use = el('button', 'fav-item', text.length > 80 ? `${text.slice(0, 80)}…` : text);
        use.type = 'button';
        use.title = text;
        use.addEventListener('click', () => { useAsPrompt(text); menu.hidden = true; });
        row.appendChild(use);
        const del = el('button', 'fav-del', '×');
        del.type = 'button';
        del.title = t('fav.remove');
        del.addEventListener('click', () => {
          state.promptFavorites.splice(idx, 1);
          saveFavorites();
          renderFavMenu();
        });
        row.appendChild(del);
        menu.appendChild(row);
      });
    }
    menu.hidden = false;
  }

  async function saveMessageToMemory(text) {
    if (!text || !state.sessionId) return;
    try {
      const res = await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/memory`, {
        text,
        title: String(text).split('\n')[0].slice(0, 120),
      });
      toast(res && res.path
        ? `${t('msg.savedMemory')}: ${res.path}`
        : t('msg.savedMemory'));
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  function messageMeta(message) {
    const meta = el('div', 'msg-meta');
    const created = Number(message.created || 0);
    if (created) {
      try {
        meta.appendChild(el('span', 'meta-time',
          new Date(created).toLocaleTimeString(state.locale || 'pt-BR',
            { hour: '2-digit', minute: '2-digit' })));
      } catch (e) { /* locale inválido */ }
    }
    const first = Number(message.firstToken || 0);
    const done = Number(message.completed || 0);
    if (created && done) {
      const total = (done - created) / 1000;
      let txt = `${total.toFixed(1)} s`;
      if (first && first >= created) {
        txt += ` · TTFT ${((first - created) / 1000).toFixed(1)} s`;
      }
      meta.appendChild(el('span', 'meta-dur', txt));
    }
    return meta;
  }

  function messageActions(message, isUser) {
    const actions = el('div', 'msg-actions');
    actions.appendChild(miniCopy(() => message.text || '', t('tool.copy')));
    actions.appendChild(actionButton(t('msg.copyMd'), t('msg.copyMd'), () => {
      navigator.clipboard.writeText(message.text || '').then(
        () => toast(t('msg.copied')),
        () => toast(t('warn.copyFailed'), 'err'),
      );
    }));
    actions.appendChild(actionButton('❝', t('msg.quote'), () => quoteMessage(message.text)));
    actions.appendChild(actionButton(t('msg.usePrompt'), t('msg.usePrompt'),
      () => useAsPrompt(message.text)));
    actions.appendChild(actionButton('🧠', t('msg.saveMemory'),
      () => saveMessageToMemory(message.text)));
    if (isUser) {
      actions.appendChild(actionButton(t('msg.edit'), t('msg.edit'),
        () => editMessage(message)));
    } else {
      actions.appendChild(actionButton(t('msg.regenerate'), t('msg.regenerate'),
        () => regenerate(message)));
    }
    return actions;
  }

  async function editMessage(message) {
    if (!message || !message.id) return;
    const edited = await askText(t('msg.edit'), message.text || '',
      t('msg.editHint'), t('msg.resend'));
    if (edited === null || edited === undefined) return;
    const trimmed = String(edited).trim();
    if (!trimmed || trimmed === String(message.text || '').trim()) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/revert`, {
        messageID: message.id, files: false,
      });
      await syncMessages({ force: true });
      const input = $('#input');
      input.value = trimmed;
      autoGrow();
      await send();
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  async function regenerate(message) {
    if (!message || !message.id) return;
    const msgs = state.messages || [];
    const idx = msgs.findIndex((m) => m.id === message.id);
    let user = null;
    for (let i = idx - 1; i >= 0; i -= 1) {
      if (msgs[i] && msgs[i].role === 'user') { user = msgs[i]; break; }
    }
    if (!user) { toast(t('msg.noUser'), 'err'); return; }
    const ok = await askConfirm(t('msg.regenerate'), t('msg.regenerateAsk'),
      t('msg.regenerate'));
    if (!ok) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/revert`, {
        messageID: user.id, files: false,
      });
      await syncMessages({ force: true });
      const input = $('#input');
      input.value = user.text || '';
      autoGrow();
      await send();
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  /** Abre/fecha TODOS os blocos (raciocínio e ferramentas) da conversa. */
  function setAllExpanded(open) {
    document.querySelectorAll('#messages details.block').forEach((block) => {
      block.open = open;
    });
    const btn = $('#expand-all-btn');
    if (btn) {
      btn.classList.toggle('on', open);
      const label = btn.querySelector('.lb-text');
      if (label) label.textContent = open ? t('tool.collapseAll') : t('tool.expandAll');
      btn.title = open ? t('tool.collapseAll') : t('tool.expandAll');
    }
    state.allExpanded = open;
  }

  function renderMessage(message) {
    if (message.role === 'user') {
      const wrap = el('div', 'msg msg-user');
      if (message.id) wrap.dataset.mid = message.id;
      wrap.appendChild(el('div', 'bubble', message.text || ''));
      wrap.appendChild(messageMeta(message));
      wrap.appendChild(messageActions(message, true));
      return wrap;
    }

    const wrap = assistantShell(message);
    if (message.id) wrap.dataset.mid = message.id;
    const answer = el('div', 'answer');
    answer.innerHTML = md(message.text || '');
    decorateRich(answer, true);
    wrap.appendChild(answer);
    wrap.appendChild(messageMeta(message));

    if (message.reasoning) {
      const block = textBlock(t('tool.reasoning'), message.reasoning, 'reasoning');
      block.open = !!state.prefs.expandReasoning;
      wrap.appendChild(block);
    }
    const tools = message.tools || [];
    if (tools.length) {
      const summary = toolSummary(tools);
      if (summary) {
        summary.addEventListener('click', () => {
          const blocks = wrap.querySelectorAll('details.block.tool');
          const shouldOpen = ![...blocks].every((b) => b.open);
          blocks.forEach((b) => { b.open = shouldOpen; });
        });
        wrap.appendChild(summary);
      }
      tools.forEach((tool) => {
        const block = toolBlock(tool.name, tool.status);
        block.__body.innerHTML = '';
        block.__body.appendChild(
          toolContent(tool.name, tool.input, tool.output, tool.diff),
        );
        setBlockStatus(block, tool.status === 'error' ? 'error'
          : (tool.status === 'completed' ? 'done' : 'running'));
        block.open = !!state.prefs.expandTools;
        wrap.appendChild(block);
      });
    }
    if (message.retry && message.retry.attempt) {
      // v0.7.11-web27: a mensagem carrega a tentativa — servidor saturado
      const info = el('div', 'retry-inline');
      info.appendChild(el('span', 'ri-icon', '⚠️'));
      const txt = el('div', 'ri-text');
      txt.appendChild(el('strong', null, t('retry.overloaded')));
      const delay = Number(message.retry.delayMs || 0);
      txt.appendChild(el('span', null, delay
        ? t('retry.attempt', { attempt: message.retry.attempt, seconds: Math.round(delay / 1000) })
        : t('retry.attemptNoDelay', { attempt: message.retry.attempt })));
      info.appendChild(txt);
      wrap.appendChild(info);
    }
    if (message.error) {
      // erro comum: VERMELHO, distinto da sobrecarga
      const card = el('div', 'error-card');
      card.appendChild(el('span', 'ec-title', t('error.title')));
      if (message.errorStatus) {
        card.appendChild(el('span', 'ec-detail', `HTTP ${message.errorStatus}`
          + (message.errorType ? ` · ${message.errorType}` : '')));
      }
      card.appendChild(el('span', 'ec-detail', message.error));
      wrap.appendChild(card);
    }
    wrap.appendChild(messageActions(message, false));
    return wrap;
  }

  function renderMessages() {
    const box = $('#messages');
    const thread = $('#thread');
    // v0.7.11-web28: um re-render não pode levar a conversa de volta para
    // o fim se o usuário está lendo uma mensagem antiga.
    const coladoNoFim = !thread || state.autoScroll;
    const posicaoAntes = thread ? thread.scrollTop : 0;
    box.innerHTML = '';
    $('#empty-state').hidden = state.messages.length > 0;
    state.messages.forEach((message) => {
      const slot = state.stream[message.id];
      if (slot && slot.wrap) {
        // v0.7.11-web28: a mensagem em streaming é um nó VIVO — preservá-lo
        // evita que o texto que está chegando "suma" no re-render.
        if (message.id) slot.wrap.dataset.mid = message.id;
        box.appendChild(slot.wrap);
        return;
      }
      box.appendChild(renderMessage(message));
    });
    if (coladoNoFim) scrollToEnd(true);
    else if (thread) thread.scrollTop = posicaoAntes;
  }

  /**
   * Rolagem automática: a conversa **segue** o conteúdo novo.
   *
   * v0.7.11-web25: antes a rolagem só acontecia se o usuário já estivesse
   * perto do fim — as mensagens novas "apareciam fora da tela". Agora ela
   * acompanha sempre; se o usuário rolar para cima, a rolagem automática é
   * pausada e aparece o botão "ir para o fim".
   */
  function scrollToEnd(force) {
    const thread = $('#thread');
    if (!thread) return;
    if (!force && !state.autoScroll) { showJump(true); return; }
    // v0.7.11-web25: sem animação — a rolagem automática acontece a cada
    // fragmento de texto e a animação a deixava sempre "a caminho".
    thread.scrollTop = thread.scrollHeight;
    state.newSinceScroll = 0;
    showJump(false);
  }

  function showJump(visible) {
    const btn = $('#jump-btn');
    if (!btn) return;
    btn.hidden = !visible;
    btn.textContent = (visible && state.newSinceScroll > 0)
      ? `↓ ${state.newSinceScroll}`
      : '↓';
  }

  /* ── busca na conversa (v0.7.11-web39) ─────────────────────────────── */

  function clearFindMarks() {
    document.querySelectorAll('#messages mark.find-hit').forEach((m) => {
      const parent = m.parentNode;
      if (!parent) return;
      parent.replaceChild(document.createTextNode(m.textContent || ''), m);
      parent.normalize();
    });
    state.find.hits = [];
    state.find.idx = -1;
  }

  function openFind() {
    const bar = $('#find-bar');
    if (!bar) return;
    state.find.open = true;
    bar.hidden = false;
    const input = $('#find-input');
    if (input) { input.focus(); input.select(); }
  }

  function closeFind() {
    state.find.open = false;
    const bar = $('#find-bar');
    if (bar) bar.hidden = true;
    clearFindMarks();
    const count = $('#find-count');
    if (count) count.textContent = '';
  }

  function highlightTextNode(node, q, hits) {
    const text = node.nodeValue || '';
    const lower = text.toLowerCase();
    let idx = 0;
    let last = 0;
    const frag = document.createDocumentFragment();
    while ((idx = lower.indexOf(q, last)) !== -1) {
      if (idx > last) frag.appendChild(document.createTextNode(text.slice(last, idx)));
      const mark = document.createElement('mark');
      mark.className = 'find-hit';
      mark.textContent = text.slice(idx, idx + q.length);
      frag.appendChild(mark);
      hits.push(mark);
      last = idx + q.length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    if (frag.childNodes.length) node.parentNode.replaceChild(frag, node);
  }

  function runFind(q) {
    clearFindMarks();
    const box = $('#messages');
    const needle = String(q || '').trim().toLowerCase();
    state.find.q = needle;
    const count = $('#find-count');
    if (!box || needle.length < 2) {
      if (count) count.textContent = '';
      return;
    }
    const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT, {
      acceptNode(t) {
        if (!t.nodeValue || !t.nodeValue.toLowerCase().includes(needle)) {
          return NodeFilter.FILTER_REJECT;
        }
        const p = t.parentElement;
        if (p && p.closest('script,style,mark.find-hit')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    const hits = [];
    nodes.forEach((n) => highlightTextNode(n, needle, hits));
    state.find.hits = hits;
    state.find.idx = hits.length ? 0 : -1;
    if (hits.length) hits[0].classList.add('current');
    if (count) count.textContent = hits.length ? `1/${hits.length}` : '0';
    if (hits.length) hits[0].scrollIntoView({ block: 'center' });
  }

  function stepFind(dir) {
    const hits = state.find.hits;
    if (!hits.length) return;
    if (state.find.idx >= 0 && hits[state.find.idx]) {
      hits[state.find.idx].classList.remove('current');
    }
    state.find.idx = (state.find.idx + dir + hits.length) % hits.length;
    const hit = hits[state.find.idx];
    if (hit) { hit.classList.add('current'); hit.scrollIntoView({ block: 'center' }); }
    const count = $('#find-count');
    if (count) count.textContent = `${state.find.idx + 1}/${hits.length}`;
  }

  function onThreadScroll() {
    const thread = $('#thread');
    if (!thread) return;
    const dist = thread.scrollHeight - thread.scrollTop - thread.clientHeight;
    // rolagem para CIMA (ação do usuário) → pausa a rolagem automática.
    // Mas se o CONTEÚDO mudou (nova conversa, nova mensagem renderizada), o
    // salto para 0 é do re-render, não do usuário — nesse caso a conversa
    // deve continuar acompanhando.
    const subiu = thread.scrollTop < lastScrollTop - 4;
    const conteudoMudou = Math.abs(thread.scrollHeight - lastScrollHeight) > 40;
    lastScrollTop = thread.scrollTop;
    lastScrollHeight = thread.scrollHeight;
    if (subiu && !conteudoMudou) {
      lastUserScrollUp = Date.now();
      state.autoScroll = false;
      showJump(true);
      return;
    }
    state.autoScroll = dist < 120;
    showJump(!state.autoScroll);
  }

  let lastScrollTop = 0;
  let lastScrollHeight = 0;
  let lastUserScrollUp = 0;
  let lastTouchY = 0;

  /**
   * Intenção de rolagem para CIMA — detectada em ``wheel``/``touchmove``,
   * que disparam **antes** do evento ``scroll``. Sem isso havia uma corrida:
   * o `ResizeObserver` (que acompanha o conteúdo) puxava a conversa de volta
   * ao fim antes de o evento `scroll` ser processado, e o usuário nunca
   * conseguia ler uma mensagem antiga.
   */
  function onScrollIntent(event) {
    let delta = 0;
    if (event.deltaY !== undefined) {
      delta = event.deltaY;
    } else if (event.touches && event.touches.length) {
      const y = event.touches[0].clientY;
      delta = lastTouchY - y;
      lastTouchY = y;
    }
    if (delta > 0) return;             // rolando para baixo
    lastUserScrollUp = Date.now();
    state.autoScroll = false;
    showJump(true);
  }

  /* ── streaming ────────────────────────────────────────────────────── */

  function streamSlot(messageID) {
    if (!state.stream[messageID]) {
      const wrap = el('div', 'msg msg-assistant');
      if (messageID) wrap.dataset.mid = messageID;
      const who = el('div', 'who');
      who.appendChild(el('b', null, 'UFVAI'));
      wrap.appendChild(who);
      const answer = el('div', 'answer');
      wrap.appendChild(answer);
      const slot = {
        wrap, answer, text: '', reasoning: '', tools: {}, toolInputs: {},
        reasoningBlock: null, __tools: '',
        startedAt: Date.now(), firstTokenAt: 0, meta: null,   // v0.7.11-web40
      };
      // v0.7.11-web24: as mensagens em streaming também precisam do botão
      // de copiar (antes ele só existia nas mensagens do histórico).
      wrap.appendChild(copyButton(() => slot.text || '', t('session.copyResponse')));
      const meta = el('div', 'msg-meta');
      wrap.appendChild(meta);
      slot.meta = meta;
      state.stream[messageID] = slot;
      $('#messages').appendChild(wrap);
      $('#empty-state').hidden = true;
    }
    return state.stream[messageID];
  }

  function scheduleRender(slot) {
    if (slot.__pending) return;
    slot.__pending = true;
    requestAnimationFrame(() => {
      slot.__pending = false;
      slot.answer.innerHTML = md(slot.text);
      decorateRich(slot.answer, false);
      if (slot.reasoningBlock) slot.reasoningBlock.__body.textContent = slot.reasoning;
      if (slot.meta) {
        const now = Date.now();
        const elapsed = (now - slot.startedAt) / 1000;
        let txt = `${elapsed.toFixed(1)} s`;
        if (slot.firstTokenAt) {
          txt += ` · TTFT ${((slot.firstTokenAt - slot.startedAt) / 1000).toFixed(1)} s`;
        }
        slot.meta.textContent = txt;
      }
      scrollToEnd(false);
    });
  }

  function handleEvent(ev) {
    if (!ev || !ev.type) return;
    if (ev.sid && state.sessionId && ev.sid !== state.sessionId) return;

    switch (ev.type) {
      case 'run.started':
        setRunning(true);
        setTimeout(loadForms, 600);   // v0.7.11-web42: pega o form cedo
        break;
      case 'run.finished':
      case 'run.failed':
        state.runClosed = true;
        setRunning(false);
        refreshSessions();
        refreshUsage();
        // v0.7.11-web24: completa o texto que possa ter ficado faltando
        syncMessages({ force: true });
        break;
      case 'step.started': {
        const slot = streamSlot(ev.messageID);
        const who = slot.wrap.querySelector('.who');
        if (who && ev.agent) who.querySelector('b').textContent = ev.agent;
        break;
      }
      case 'text.started':
        streamSlot(ev.messageID);
        // v0.7.11-web27: a resposta voltou — a sobrecarga acabou
        hideRetryNotice();
        break;
      case 'text.delta': {
        const slot = streamSlot(ev.messageID);
        if (!slot.firstTokenAt) slot.firstTokenAt = Date.now();
        slot.text += ev.delta || '';
        hideRetryNotice();
        scheduleRender(slot);
        break;
      }
      case 'text.ended': {
        const slot = streamSlot(ev.messageID);
        if (typeof ev.text === 'string' && ev.text.length >= slot.text.length) slot.text = ev.text;
        scheduleRender(slot);
        break;
      }
      case 'reasoning.started':
        streamSlot(ev.messageID);
        break;
      case 'reasoning.delta': {
        const slot = streamSlot(ev.messageID);
        slot.reasoning += ev.delta || '';
        if (!slot.reasoningBlock) {
          // v0.7.11-web28: o raciocínio mostra a espiral amarela enquanto
          // está em curso.
          slot.reasoningBlock = textBlock(t('tool.reasoning'), '', 'reasoning', 'running');
          slot.reasoningBlock.open = !!state.prefs.expandReasoning;
          slot.wrap.appendChild(slot.reasoningBlock);
        } else {
          setBlockStatus(slot.reasoningBlock, 'running');
        }
        scheduleRender(slot);
        break;
      }
      case 'reasoning.ended': {
        const slot = streamSlot(ev.messageID);
        if (ev.text) slot.reasoning = ev.text;
        if (!slot.reasoningBlock) {
          slot.reasoningBlock = textBlock(t('tool.reasoning'), slot.reasoning, 'reasoning', 'done');
          slot.reasoningBlock.open = !!state.prefs.expandReasoning;
          slot.wrap.appendChild(slot.reasoningBlock);
        }
        // v0.7.11-web28: terminou — a espiral some e o rótulo fica verde.
        setBlockStatus(slot.reasoningBlock, 'done');
        scheduleRender(slot);
        break;
      }
      case 'tool.started': {
        const slot = streamSlot(ev.messageID);
        const block = toolBlock(ev.name, t('tool.running'));
        if (!slot.toolStarted) slot.toolStarted = {};
        slot.toolStarted[ev.callID] = Date.now();
        slot.toolInputs[ev.callID] = ev.input;
        // v0.7.11-web42: a ferramenta "question" cria um form no motor
        if (ev.name === 'question') setTimeout(loadForms, 400);
        block.__body.innerHTML = '';
        block.__body.appendChild(toolContent(ev.name, ev.input, null, null));
        slot.tools[ev.callID] = block;
        slot.wrap.appendChild(block);
        scrollToEnd(false);
        break;
      }
      case 'tool.finished': {
        const slot = streamSlot(ev.messageID);
        const block = slot.tools[ev.callID];
        if (block) {
          // v0.7.11-web40: duração real da ferramenta (início → fim)
          const started = slot.toolStarted && slot.toolStarted[ev.callID];
          const ms = started ? (Date.now() - started) : 0;
          const base = ev.status === 'error' ? t('tool.error') : t('tool.done');
          const label = ms ? `${base} · ${(ms / 1000).toFixed(1)} s` : base;
          setBlockStatus(block, ev.status === 'error' ? 'error' : 'done', label);
          // v0.7.11-web23: o diff do arquivo alterado chega no fim da chamada
          const input = slot.toolInputs && slot.toolInputs[ev.callID];
          block.__body.innerHTML = '';
          block.__body.appendChild(toolContent(ev.name, input, ev.output, ev.diff));
        }
        scrollToEnd(false);
        break;
      }
      case 'inbox.enqueued':
        if (ev.text) {
          const wrap = el('div', 'msg msg-user');
          wrap.appendChild(el('div', 'bubble', ev.text));
          wrap.style.opacity = '0.65';
          $('#messages').appendChild(wrap);
          scrollToEnd(false);
        }
        break;
      case 'retry.scheduled':
        // v0.7.11-web27: servidor sobrecarregado — o retry está em curso
        showRetryNotice(ev);
        break;
      case 'permission.asked':
        renderPermission(ev);
        break;
      case 'permission.replied':
        clearPermission(ev.id);
        break;
      case 'form.created':
        // v0.7.11-web38: ferramenta "question" — busca e mostra as opções
        console.info('[ufvai] form.created', ev);
        loadForms();
        break;
      case 'form.replied':
      case 'form.cancelled':
        clearForm(ev.id);
        break;
      case 'error':
        // v0.7.11-web27: sobrecarga → avisa com retry; demais erros → vermelho
        if (ev.reason === 'overloaded') {
          showRetryNotice({
            delayMs: ev.retryAfterMs || 0,
            attempt: 0,
            message: ev.error || '',
          });
          toast(t('retry.overloaded'), 'warn');
        } else {
          showErrorNotice(ev);
          toast(String(ev.error || t('error.title')), 'err');
        }
        break;
      default:
        break;
    }
  }

  /**
   * v0.7.11-web30: estado de execução — **sem depender só do SSE**.
   *
   * O indicador anterior só acendia com o evento ``run.started``. Se esse
   * evento se perdesse (queda do SSE, proxy que bufferiza, reconexão), o
   * usuário ficava **sem nenhuma pista** de o modelo estar trabalhando —
   * e sem botão de parar. Agora há três fontes independentes:
   *
   * 1. o SSE (``run.started`` / ``run.finished``);
   * 2. o estado ``active`` do motor (``GET /sessions`` → ``active``);
   * 3. a própria resposta **crescendo** (a sincronização de 3 s).
   *
   * E o envio é **otimista**: ao publicar, o turno já está começando.
   */
  function setRunning(running, opts) {
    const opcoes = opts || {};
    const estavaRodando = state.running;
    state.running = !!running;
    const agora = Date.now();
    if (state.running) {
      if (!estavaRodando && !opcoes.keepStopping) state.runningSince = agora;
      $('#status').hidden = false;
      const botao = $('#stop-btn');
      if (botao) { botao.classList.add('live'); botao.disabled = false; }
    } else {
      $('#status').hidden = true;
      const botao = $('#stop-btn');
      if (botao) { botao.classList.remove('live'); }
    }
    atualizaTextoAtividade();
    setAgentBusy(state.running, estavaRodando);
    if (state.running) { watchRun(); startElapsed(); } else { stopElapsed(); }
    // v0.7.11-web40: turno terminou → envia a próxima mensagem da fila
    if (!state.running && !state.stopping) setTimeout(flushQueue, 0);
  }

  /**
   * v0.7.11-web35: formata segundos decorridos como HH:MM:SS
   * (horas:minutos:segundos), com zero à esquerda. Ex.: 3725 → "01:02:05".
   * Horas e minutos aparecem mesmo quando zero, para leitura inequívoca.
   */
  function formataCronometro(totalSeg) {
    const s = Math.max(0, Math.floor(totalSeg || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const seg = s % 60;
    return [h, m, seg].map(n => String(n).padStart(2, '0')).join(':');
  }

  /** Texto do indicador: "Trabalhando… · 00:01:23" / "interrompendo…". */
  function atualizaTextoAtividade() {
    const seg = state.runningSince ? Math.floor((Date.now() - state.runningSince) / 1000) : 0;
    const base = state.stopping ? t('status.interrupting') : t('status.working');
    const texto = seg > 0 ? `${base} · ${formataCronometro(seg)}` : base;
    const status = $('#status-text');
    if (status) status.textContent = state.running ? texto : '';
    const busy = $('#agent-busy');
    // só mexe no texto do indicador enquanto ele gira — senão o texto do
    // flash ("concluído" / "interrompido") seria sobrescrito.
    if (busy && state.running) {
      const alvo = busy.querySelector('.busy-text');
      if (alvo) alvo.textContent = texto;
    }
  }

  let elapsedTimer = null;

  function startElapsed() {
    if (elapsedTimer) return;
    elapsedTimer = setInterval(() => { if (isVisible()) atualizaTextoAtividade(); }, 1000);
  }

  function stopElapsed() {
    if (!elapsedTimer) return;
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }

  /**
   * v0.7.11-web29: indicador **global** de atividade.
   *
   * Enquanto o agente trabalha, uma **espiral amarela** gira no cabeçalho
   * (e na linha de status do compositor). Quando o turno termina, a espiral
   * é trocada por um **✓ verde** com "concluído" por alguns segundos — sem
   * isso não dá para saber se o agente acabou ou se travou.
   *
   * v0.7.11-web30: ganhou o estado **interrompido** (quadrado vermelho),
   * quando a parada foi pedida pelo usuário.
   */
  let busyFlashTimer = null;

  function setAgentBusy(busy, veioDeExecucao) {
    const node = $('#agent-busy');
    if (!node) return;
    const text = node.querySelector('.busy-text');
    clearTimeout(busyFlashTimer);
    node.classList.remove('done', 'stopped');
    if (busy) {
      node.hidden = false;
      node.classList.toggle('stopping', !!state.stopping);
      if (text) text.textContent = state.stopping ? t('status.interrupting') : t('status.working');
      return;
    }
    if (!veioDeExecucao) { node.hidden = true; return; }
    // fim do turno: "concluído" (verde) ou "interrompido" (vermelho)
    if (state.stopping) {
      node.classList.add('stopped');
      if (text) text.textContent = t('status.stopped');
    } else {
      node.classList.add('done');
      if (text) text.textContent = t('tool.done');
    }
    node.hidden = false;
    busyFlashTimer = setTimeout(() => {
      node.hidden = true;
      node.classList.remove('done', 'stopped');
      state.stopping = false;
    }, 2800);
  }

  /**
   * v0.7.11-web30: sondagem do estado do motor.
   *
   * ``GET /api/ufvai/sessions`` devolve ``active``: o próprio motor dice
   * quais sessões estão **em execução**. É uma chamada normal (funciona
   * por qualquer proxy, ao contrário do SSE) — então serve de segunda
   * fonte para o indicador e para habilitar o botão de parar.
   */
  const ATIVIDADE_POLL_MS = 2500;
  let atividadeTimer = null;

  function iniciaSondaAtividade() {
    if (atividadeTimer) return;
    atividadeTimer = setInterval(() => { if (isVisible()) sondaAtividade(); }, ATIVIDADE_POLL_MS);
    sondaAtividade();
  }

  async function sondaAtividade() {
    if (!state.sessionId) return;
    let ativo = null;
    try {
      const data = await apiGet('/sessions');
      const mapa = (data && data.active) || null;
      if (mapa && typeof mapa === 'object') ativo = mapa;
    } catch (e) { return; }
    if (!ativo) return;
    // v0.7.11-web30: "não deu para perguntar" ≠ "não está rodando"
    if (ativo.error) return;
    state.active = ativo;
    const ids = Object.keys(ativo);
    const emExecucao = ids.includes(state.sessionId);
    const agora = Date.now();
    if (emExecucao) {
      // v0.7.11-web30: o turno **já encerrado** não é religado pela
      // sondagem — o motor pode continuar listando a sessão como ativa
      // por alguns instantes depois do fim (e o "concluído" sumiria).
      if (!state.running && !state.runClosed) setRunning(true);
      return;
    }
    // o motor diz que esta sessão está parada: só encerra o indicador se
    // também houve silêncio (nada novo na resposta) — evita apagar o
    // "trabalhando" por causa de uma leitura atrasada do motor.
    const silencio = agora - (state.lastContentChange || state.runningSince || agora);
    if (state.running && silencio > 7000 && agora - (state.runningSince || 0) > 9000) {
      setRunning(false);
      await syncMessages({ force: true });
    }
  }

  /**
   * v0.7.11-web24: o aviso "Trabalhando…" ficava na tela para sempre quando
   * o evento ``run.finished`` se perdia (queda do SSE no fim do turno).
   * O watchdog relê a conversa — mas **não** decide mais se o turno ended:
   * v0.7.11-web30, a heurística ``busy < updated`` estava **errada**
   * (``updated`` também avança DURANTE o turno) e apagava o indicador
   * "trabalhando" bem no meio da execução. Quem decide agora é a
   * sondagem do motor (:func:`sondaAtividade`), com a lista ``active``.
   */
  let runWatchTimer = null;

  function watchRun() {
    if (runWatchTimer) return;
    runWatchTimer = setInterval(async () => {
      if (!isVisible()) return;
      if (!state.running || !state.sessionId) return;
      try {
        await syncMessages();
      } catch (e) { /* motor fora do ar: o watchdog de reconexão trata */ }
    }, 4000);
  }

  /**
   * v0.7.11-web24: as vezes a mensagem parava no meio (evento de streaming
   * perdido). Ao fim do turno — e a cada reconexão do SSE — a web relê as
   * últimas mensagens do motor e completa o que ficou faltando.
   *
   * v0.7.11-web28: a sincronização foi refeita.
   *
   * **O que estava errado**
   *
   * 1. Só a **última** mensagem era conferida — se duas respostas se
   *    dessincronizassem, a anterior continuava errada na tela;
   * 2. uma diferença de texto chamava ``renderMessages()``, que **apagava
   *    o texto que estava chegando por streaming** (a resposta "voltava" ao
   *    estado antigo e ficava truncada);
   * 3. não havia **fallback**: se o SSE caía, a tela ficava congelada até
   *    a reconexão.
   *
   * **O que passa a valer**
   *
   * * todas as mensagens da cauda são reconciliadas;
   * * mensagem em streaming é atualizada **no lugar** (o nó vivo nunca é
   *   recriado);
   * * mensagem do histórico é corrigida no próprio nó da tela (preserva o
   *   que o usuário expandiu);
   * * há **sondagem** periódica — a tela se conserta mesmo sem SSE.
   */
  let syncInFlight = false;

  async function syncMessages(options) {
    const opts = options || {};
    if (!state.sessionId) return;
    if (syncInFlight && !opts.force) return;
    syncInFlight = true;
    const sid = state.sessionId;
    try {
      const limit = opts.limit || 80;
      const data = await apiGet(`/sessions/${encodeURIComponent(sid)}/messages?limit=${limit}`);
      // trocou de sessão no meio da requisição: o resultado é de outra
      // conversa e não pode ser aplicado aqui.
      if (state.sessionId !== sid) return;
      const rows = data.messages || [];
      if (!rows.length) return;
      applySyncedMessages(rows);
    } catch (e) { /* mantém o que já está na tela */ }
    finally {
      syncInFlight = false;
    }
  }

  // compatibilidade: chamadores antigos
  const syncTail = syncMessages;

  /**
   * Reconcilia a lista da tela com a do motor.
   */
  function applySyncedMessages(rows) {
    let estruturaMudou = false;
    let conteudoMudou = false;

    rows.forEach((row) => {
      if (!row || !row.id) return;
      if (row.role === 'system' && !row.outcome) return;

      const slot = state.stream[row.id];
      const known = state.messages.find((m) => m.id === row.id);

      // ── mensagem viva (streaming): atualiza no lugar ────────────────
      if (slot) {
        const texto = row.text || '';
        if (slot.text !== texto) {
          slot.text = texto;
          slot.answer.innerHTML = md(texto);
          conteudoMudou = true;
        }
        if (row.reasoning) {
          slot.reasoning = row.reasoning;
          if (slot.reasoningBlock) {
            slot.reasoningBlock.__body.textContent = row.reasoning;
            // v0.7.11-web28: se o turno já acabou, o raciocínio está verde.
            if (!state.running) setBlockStatus(slot.reasoningBlock, 'done');
          }
        }
        const ferramentas = JSON.stringify(row.tools || []);
        if (slot.__tools !== ferramentas) {
          slot.__tools = ferramentas;
          renderStreamTools(slot, row.tools || []);
        }
        if (!known) {
          state.messages.push(row);
          estruturaMudou = true;
        }
        return;
      }

      // ── mensagem do histórico ────────────────────────────────────────
      if (!known) {
        // a mensagem do usuário pode já estar na tela (envio otimista):
        // troca o nó provisório pelo oficial, sem duplicar.
        const pending = (state.pendingUsers || [])
          .find((p) => p.text === (row.text || ''));
        if (pending) {
          const node = document.querySelector(
            `#messages .msg[data-mid="${pending.key}"]`,
          );
          if (node) node.replaceWith(renderMessage(row));
          state.pendingUsers = state.pendingUsers.filter((p) => p !== pending);
        }
        state.messages.push(row);
        estruturaMudou = true;
        return;
      }

      if ((known.text || '') !== (row.text || '')
        || (known.reasoning || '') !== (row.reasoning || '')
        || JSON.stringify(known.tools || []) !== JSON.stringify(row.tools || [])
        || (known.error || '') !== (row.error || '')) {
        known.text = row.text;
        known.reasoning = row.reasoning;
        known.tools = row.tools;
        known.error = row.error;
        known.errorStatus = row.errorStatus;
        known.errorType = row.errorType;
        known.retry = row.retry;
        updateMessageNode(known);
        conteudoMudou = true;
      }
    });

    // ordem cronológica (a do motor)
    state.messages.sort((a, b) => {
      const ta = Number(a.created || 0);
      const tb = Number(b.created || 0);
      if (ta && tb && ta !== tb) return ta - tb;
      return String(a.id).localeCompare(String(b.id));
    });

    pruneStream();
    if (estruturaMudou) renderMessages();
    else if (conteudoMudou) { /* os nós já foram corrigidos no lugar */ }
    // v0.7.11-web30: a resposta **cresceu** → o modelo está trabalhando.
    // É a 3ª fonte do indicador de atividade (independente do SSE).
    // E o turno volta a estar "aberto": houve output novo.
    if (conteudoMudou) {
      state.lastContentChange = Date.now();
      state.runClosed = false;
    }
  }

  /**
   * Atualiza **um** nó da tela (sem recriar a conversa inteira — o que
   * preserva o que o usuário expandiu e a posição da rolagem).
   */
  function updateMessageNode(message) {
    const id = String(message.id || '');
    const node = document.querySelector(`#messages .msg[data-mid="${id}"]`);
    if (!node) {
      renderMessages();
      return;
    }
    node.replaceWith(renderMessage(message));
  }

  /**
   * Libera os slots de streaming que já foram incorporados ao histórico
   * (o texto confere com o do motor) — a partir daí a mensagem passa a ser
   * desenhada a partir da lista, como as outras.
   */
  function pruneStream() {
    if (state.running) return;
    Object.keys(state.stream).forEach((id) => {
      const slot = state.stream[id];
      const known = state.messages.find((m) => m.id === id);
      if (known && (known.text || '') === (slot.text || '')) {
        delete state.stream[id];
      }
    });
  }

  /** Reconstrói os blocos de ferramentas de uma mensagem em streaming. */
  function renderStreamTools(slot, tools) {
    if (!slot) return;
    const existentes = slot.wrap.querySelectorAll('details.block.tool');
    existentes.forEach((node) => node.remove());
    (tools || []).forEach((tool) => {
      const block = toolBlock(tool.name, tool.status);
      block.__body.innerHTML = '';
      block.__body.appendChild(toolContent(tool.name, tool.input, tool.output, tool.diff));
      setBlockStatus(block, tool.status === 'error' ? 'error'
        : (tool.status === 'completed' ? 'done' : 'running'));
      block.open = !!state.prefs.expandTools;
      slot.wrap.appendChild(block);
    });
  }

  /* ── eventos (SSE) ────────────────────────────────────────────────── */

  // v0.7.11-web23: se a conexão ficar caída por mais de 10 minutos, o
  // ambiente do Colab provavelmente foi encerrado (inatividade). O aviso
  // explica o que houve e lembra que o Drive está intacto.
  const DEAD_AFTER_MS = 10 * 60 * 1000;
  let downSince = 0;

  /**
   * Detecta a queda do ambiente (Colab encerrado).
   *
   * v0.7.11-web25: dois sinais independentes — o SSE (que só cai se o
   * gateway ou o motor morrem) e um **heartbeat** em ``/health`` (que cobre o
   * caso do servidor inteiro ter ido). Depois de 10 minutos sem resposta,
   * o aviso explica o que houve.
   */
  function markEngineDown() {
    const dot = $('#engine-dot');
    const text = $('#engine-text');
    if (dot) dot.className = 'dot bad';
    if (text) text.textContent = t('sidebar.reconnecting');
    if (!downSince) {
      downSince = Date.now();
      setTimeout(() => {
        if (downSince && Date.now() - downSince >= DEAD_AFTER_MS) showEngineDead();
      }, DEAD_AFTER_MS + 500);
    }
  }

  function showEngineDead() {
    const banner = $('#engine-dead');
    if (banner) banner.hidden = false;
    const text = $('#engine-text');
    if (text) text.textContent = t('sidebar.engineDead');
  }

  function markEngineUp() {
    downSince = 0;
    const banner = $('#engine-dead');
    if (banner) banner.hidden = true;
  }

  /** Heartbeat: sonda o gateway (não depende do SSE). */
  async function heartbeat() {
    try {
      const res = await fetch(`${BASE}health`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      markEngineUp();
    } catch (e) {
      markEngineDown();
    }
  }

  function connectEvents() {
    if (state.source) { state.source.close(); state.source = null; }
    const url = api(`/events${state.sessionId ? `?sid=${encodeURIComponent(state.sessionId)}` : ''}`);
    const source = new EventSource(url);
    state.source = source;
    source.onmessage = (event) => {
      try { handleEvent(JSON.parse(event.data)); } catch (e) { /* frame inválido */ }
    };
    source.onerror = () => {
      markEngineDown();
    };
    source.onopen = () => {
      markEngineUp();
      const dot = $('#engine-dot');
      const text = $('#engine-text');
      if (dot) dot.className = 'dot ok';
      if (text) text.textContent = t('sidebar.connected');
      // v0.7.11-web24: ao reconectar, o que chegou durante a queda se perdeu
      // — relê a cauda da conversa e reidrata as permissões pendentes.
      syncMessages({ force: true });
      loadPermissions();
      loadForms();
      const waiters = state.sseWaiters.splice(0, state.sseWaiters.length);
      waiters.forEach((fn) => fn());
    };
  }

  /**
   * v0.7.11-web24: o prompt precisa sair **depois** que o SSE está aberto.
   * Antes, a mensagem era publicada logo após trocar de sessão e os eventos
   * (``run.started``, ``text.delta``) se perdiam — a resposta aparecia
   * vazia ou truncada.
   */
  function ensureEvents() {
    if (state.source && state.source.readyState === 1) return Promise.resolve();
    return new Promise((resolve) => {
      state.sseWaiters.push(resolve);
      connectEvents();
      // não bloqueia o envio se o motor estiver fora do ar
      setTimeout(() => {
        const waiters = state.sseWaiters.splice(0, state.sseWaiters.length);
        waiters.forEach((fn) => fn());
      }, 2500);
    });
  }

  /* ── sessão ───────────────────────────────────────────────────────── */

  function applyModel(model) {
    state.model = {
      id: model.id || '',
      providerID: model.providerID || '',
      variant: model.variant || '',
    };
    const label = state.model.id ? `${state.model.id} · ${state.model.providerID}` : 'modelo…';
    $('#model-label').textContent = label;
    renderVariant();
  }

  function currentModelEntry() {
    return state.models.find(
      (m) => m.id === state.model.id && m.providerID === state.model.providerID,
    ) || null;
  }

  function renderVariant() {
    const entry = currentModelEntry();
    const variants = (entry && entry.variants) || [];
    const box = $('#variant-chip');
    if (!box) return;
    if (!variants.length) { box.hidden = true; return; }
    box.hidden = false;
    box.textContent = state.model.variant ? `variante: ${state.model.variant}` : 'variante: padrão';
  }

  async function openSession(sid, opts) {
    if (!sid) return;
    const options = opts || {};
    state.sessionId = sid;
    state.manualSwitch = Date.now();
    state.stream = {};
    state.attachments = [];
    renderAttachments();
    closePalette();
    $('#session-title').textContent = 'carregando…';

    try {
      const data = await apiGet(`/sessions/${encodeURIComponent(sid)}/messages`);
      state.messages = data.messages || [];
    } catch (e) {
      state.messages = [];
      toast('não foi possível carregar a sessão', 'err');
    }

    const row = state.sessions.find((s) => s.id === sid);
    $('#session-title').textContent = row ? sessionTitle(row) : sid.slice(0, 12);
    if (row) applyModel(row.model || {});
    if (row && row.agent) {
      state.agent = row.agent;
      $('#agent-label').textContent = row.agent;
    }
    renderMessages();
    renderSessions();
    renderUsage();
    refreshUsage();
    connectEvents();
    // Só uma escolha explícita do usuário move o terminal: abrir a página não
    // deve arrastar a TUI para outra sessão.
    if (options.focus) {
      apiPost('/focus', { sid }).catch(() => {});
    }
  }

  async function refreshSessions() {
    try {
      const data = await apiGet('/sessions');
      state.sessions = data.sessions || [];
      state.active = data.active || {};
      renderSessions();
      renderUsage();
    } catch (e) { /* mantém a lista anterior */ }
  }

  async function newSession() {
    try {
      const body = {};
      if (state.agent) body.agent = state.agent;
      if (state.model.id && state.model.providerID) body.model = state.model;
      const data = await apiPost('/sessions', body);
      const row = data.session;
      if (!row || !row.id) {
        // v0.7.11-web39: o motor pode devolver corpo vazio/erro — não insere
        // um item inválido na lista (isso quebrava a renderização).
        toast(String(data.error || 'não foi possível criar a sessão'), 'err');
        return;
      }
      state.sessions.unshift(row);
      renderSessions();
      await openSession(row.id, { focus: true });
      $('#input').focus();
    } catch (e) {
      toast('não foi possível criar a sessão', 'err');
    }
  }

  /* ── envio ────────────────────────────────────────────────────────── */

  async function send(opts) {
    const input = $('#input');
    const text = input.value.trim();
    if (!text && !state.attachments.length) return;

    // v0.7.11-web39: histórico de prompts (↑/↓)
    if (text) {
      const h = state.promptHistory;
      if (h[h.length - 1] !== text) h.push(text);
      while (h.length > 50) h.shift();
      state.historyIdx = -1;
      try { localStorage.setItem('ufvai_prompt_history', JSON.stringify(h)); } catch (e) {}
    }

    // v0.7.11-web40: fila — se o agente está trabalhando, guarda a mensagem
    if (state.running && !(opts && opts.force) && !state.stopping) {
      queueMessage(text);
      return;
    }

    if (!state.sessionId) { await newSession(); }

    // v0.7.11-web27: novo turno → limpa os avisos do anterior
    clearErrorNotices();
    hideRetryNotice();

    input.value = '';
    input.style.height = 'auto';

    const wrap = el('div', 'msg msg-user');
    // v0.7.11-web28: a mensagem do usuário entra na tela na hora (envio
    // otimista) — mas fica marcada como provisória: quando o motor devolve
    // a mensagem oficial, o nó é trocado (sem duplicar).
    const pendingKey = `pending-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    wrap.dataset.mid = pendingKey;
    state.pendingUsers = state.pendingUsers || [];
    state.pendingUsers.push({ key: pendingKey, text: text || '' });
    wrap.appendChild(el('div', 'bubble', text || `(${t('composer.attached')})`));
    if (state.attachments.length) {
      const names = state.attachments
        .map((a) => `📎 ${a.name}${a.path ? `\n${a.path}` : ''}`)
        .join('\n');
      wrap.appendChild(el('div', 'bubble-attach', names));
    }
    $('#messages').appendChild(wrap);
    $('#empty-state').hidden = true;
    scrollToEnd(true);

    // v0.7.11-web23: o anexo vai inline (o modelo lê) E o gateway recebe o
    // caminho em disco (o agente abre).
    const files = state.attachments
      .filter((a) => a.uri)
      .map((a) => ({ uri: a.uri, source: { type: 'inline' }, name: a.name }));
    const uploads = state.attachments
      .filter((a) => a.path)
      .map((a) => ({ name: a.name, path: a.path, size: a.size }));
    const skills = state.pendingSkills.slice();
    state.attachments = [];
    state.pendingSkills = [];
    renderAttachments();

    // v0.7.11-web30: o turno começa AGORA — o indicador acende no instante
    // do envio, sem esperar o evento do motor (que às vezes se perde).
    state.stopping = false;
    state.runClosed = false;
    setRunning(true);

    try {
      // v0.7.11-web24: garante o SSE aberto antes de publicar (evita perder
      // os eventos do turno).
      await ensureEvents();
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/message`, {
        text, files, skills: skills.length ? skills : undefined,
        uploads: uploads.length ? uploads : undefined,
      });
    } catch (e) {
      toast(String(e.message || e), 'err');
      setRunning(false);
    }
  }

  /* ── fila de mensagens (v0.7.11-web40) ────────────────────────────── */

  function queueMessage(text) {
    const files = state.attachments.slice();
    const skills = state.pendingSkills.slice();
    if (!text && !files.length) return;
    const node = el('div', 'msg msg-user queued');
    node.appendChild(el('div', 'bubble', text || `(${t('composer.attached')})`));
    node.appendChild(el('span', 'q-badge', `${t('queue.badge')} ${state.queue.length + 1}`));
    $('#messages').appendChild(node);
    state.queue.push({ text, attachments: files, skills, node });
    state.attachments = [];
    state.pendingSkills = [];
    renderAttachments();
    const input = $('#input');
    input.value = '';
    input.style.height = 'auto';
    toast(t('queue.added'));
    scrollToEnd(true);
  }

  async function flushQueue() {
    if (state.queueFlushing || state.running || !state.queue.length) return;
    state.queueFlushing = true;
    const item = state.queue.shift();
    try {
      if (item.node && item.node.parentNode) item.node.remove();
      const input = $('#input');
      input.value = item.text || '';
      state.attachments = item.attachments || [];
      state.pendingSkills = item.skills || [];
      renderAttachments();
      await send({ force: true });
    } finally {
      state.queueFlushing = false;
    }
  }

  async function stop() {
    if (!state.sessionId) return;
    // v0.7.11-web30: o botão de parar é SEMPRE visível — se o indicador
    // falhar, o usuário ainda tem como interromper. E o estado "interrompido"
    // fica visível depois da parada (não é só um flash).
    if (!state.running) {
      toast(t('status.noneRunning'));
      return;
    }
    state.stopping = true;
    atualizaTextoAtividade();
    const node = $('#agent-busy');
    if (node) {
      node.classList.remove('done');
      node.classList.add('stopping');
      node.hidden = false;
    }
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/interrupt`, {});
      toast(t('status.interrupting'));
    } catch (e) {
      state.stopping = false;
      toast(String(e.message || e), 'err');
    }
  }

  /* ── anexos ───────────────────────────────────────────────────────── */

  // v0.7.11-web23: 25 MB (limite do gateway; o motor aceita inline grande,
  // mas o upload em disco é o que o agente realmente consegue abrir).
  const MAX_ATTACHMENT = 25 * 1024 * 1024;

  function humanSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function renderAttachments() {
    const box = $('#attachments');
    box.innerHTML = '';
    state.attachments.forEach((item, index) => {
      const chip = el('span', 'chip' + (item.mime && item.mime.startsWith('image/') ? ' image' : ''));
      chip.appendChild(el('span', 'c-name', item.name));
      if (item.size) chip.appendChild(el('span', 'c-size', humanSize(item.size)));
      if (item.path) chip.appendChild(el('span', 'c-path', item.path));
      if (item.pending) chip.appendChild(el('span', 'c-path', t('composer.uploading')));
      const rm = el('button', null, '✕');
      rm.type = 'button';
      rm.title = t('composer.remove');
      rm.addEventListener('click', () => {
        state.attachments.splice(index, 1);
        renderAttachments();
      });
      chip.appendChild(rm);
      box.appendChild(chip);
    });
    box.hidden = state.attachments.length === 0;
  }

  function readFileAsDataUri(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('falha ao ler o arquivo'));
      reader.onload = () => resolve(String(reader.result || ''));
      reader.readAsDataURL(file);
    });
  }

  /**
   * Anexa arquivos do dispositivo.
   *
   * Duas vias: (1) o arquivo vai **inline** no prompt (data URI) para o
   * modelo enxergar o conteúdo; (2) o gateway o grava em ``/tmp`` e devolve
   * o caminho absoluto, que é injetado no prompt — sem isso o agente
   * recebe o arquivo "no vácuo" e não consegue abrir.
   */
  async function attachLocalFiles(files) {
    for (const file of files) {
      if (file.size > MAX_ATTACHMENT) {
        toast(`${file.name} ${t('composer.tooBig')}`, 'err');
        continue;
      }
      const item = {
        name: file.name, size: file.size, mime: file.type || '', uri: '', path: '', pending: true,
      };
      state.attachments.push(item);
      renderAttachments();
      try {
        const uri = await readFileAsDataUri(file);
        item.uri = uri;
        const base64 = uri.includes(',') ? uri.split(',')[1] : '';
        const res = await apiPost('/upload', {
          sid: state.sessionId || '',
          name: file.name,
          mime: file.type || '',
          data: base64,
        });
        if (res && res.ok) {
          item.path = res.path || '';
          item.name = res.name || file.name;
          item.size = res.size || file.size;
        } else {
          toast(`${file.name}: ${t('composer.uploadFail')}`, 'err');
        }
      } catch (e) {
        toast(`${file.name}: ${t('composer.uploadFail')}`, 'err');
      } finally {
        item.pending = false;
        renderAttachments();
      }
    }
  }

  /* ── paletas: "/" (comandos) e "@" (arquivos) ────────────────────── */

  function triggerAtCaret() {
    const input = $('#input');
    const pos = input.selectionStart ?? input.value.length;
    const before = input.value.slice(0, pos);
    const command = before.match(/(^|\s)\/([^\s/]*)$/);
    if (command) {
      return { kind: 'command', query: command[2], start: pos - command[2].length - 1, end: pos };
    }
    const mention = before.match(/(^|\s)@([^\s@]*)$/);
    if (mention) {
      const query = mention[2] || '';
      return { kind: 'mention', query, start: pos - query.length - 1, end: pos };
    }
    return null;
  }

  function closePalette() {
    state.palette = null;
    $('#palette').hidden = true;
  }

  function basename(path) {
    const clean = String(path || '').replace(/\/+$/, '');
    const parts = clean.split('/');
    return parts[parts.length - 1] || clean || path;
  }

  function rebuildMentionItems(pal) {
    const q = (pal.query || '').toLowerCase();
    const skills = state.skills
      .filter((s) => !q || s.id.toLowerCase().includes(q) || (s.name || '').toLowerCase().includes(q))
      .map((s) => ({
        group: t('palette.skills'),
        type: 'skill',
        id: s.id,
        name: '@' + s.id,
        desc: s.description || s.name || '',
      }));
    const files = (pal.files || []).map((f) => ({
      group: t('palette.files'),
      type: 'file',
      path: f.path,
      name: '@' + basename(f.path),
      desc: f.path,
    }));
    pal.items = skills.concat(files);
  }

  function openPalette(kind, query, start, end) {
    const pal = {
      kind, query, index: 0,
      start: start ?? 0, end: end ?? 0,
      items: [], files: [],
    };
    if (kind === 'command') {
      // v0.7.11-web23: o menu "/" lista TODOS os comandos do OpenCode —
      // os do agente (motor) e os nativos da barra da TUI, traduzidos pelo
      // plugin ``ufvai.pt`` e agrupados pela categoria.
      const q = String(query || '').toLowerCase();
      // v0.7.11-web30: comando **da web** — parar a execução. Não existe
      // no motor: era o que faltava ("não tem comando para parar").
      const locais = [{
        group: t('palette.commands'),
        type: 'command',
        name: t('palette.stopCommand'),
        desc: t('palette.stopDesc'),
        action: 'stop',
        scope: 'web',
        native: 'stop',
      }].filter((c) => !q
        || c.name.toLowerCase().includes(q)
        || String(c.desc).toLowerCase().includes(q));
      const doMotor = state.commands
        .filter((c) => {
          if (!q) return true;
          return [c.name, c.title, c.native, ...(c.aliases || [])]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(q));
        })
        .map((c) => ({
          group: c.group || t('palette.commands'),
          type: 'command',
          name: '/' + c.name,
          desc: c.description || c.title || '',
          action: c.action || '',
          scope: c.scope || 'motor',
          native: c.native || c.name,
        }));
      pal.items = locais.concat(doMotor);
    } else {
      rebuildMentionItems(pal);
    }
    state.palette = pal;
    $('#palette').hidden = false;
    $('#palette-head').textContent = kind === 'command'
      ? `${t('palette.commands')} — “/${query}”`
      : `${t('palette.skills')} · ${t('palette.files')} — “@${query}”`;
    renderPalette();
    if (kind !== 'command') searchFiles(query);
  }

  function renderPalette() {
    const box = $('#palette-list');
    box.innerHTML = '';
    const pal = state.palette;
    if (!pal) return;
    if (!pal.items.length) {
      box.appendChild(el('div', 'palette-group', pal.loading ? '…' : t('palette.noResults')));
      return;
    }
    const groups = new Map();
    pal.items.forEach((item, index) => {
      if (!groups.has(item.group)) groups.set(item.group, []);
      groups.get(item.group).push({ item, index });
    });
    groups.forEach((entries, group) => {
      box.appendChild(el('div', 'palette-group', String(group).toUpperCase()));
      entries.forEach(({ item, index }) => {
        const node = el('button', 'palette-item' + (index === pal.index ? ' active' : ''));
        node.type = 'button';
        node.appendChild(el('span', 'p-name', item.name));
        if (item.scope === 'tui') {
          // v0.7.11-web23: sinaliza os comandos que só existem no terminal
          node.appendChild(el('span', 'p-badge', 'TUI'));
        }
        node.appendChild(el('span', 'p-desc', item.desc || ''));
        node.addEventListener('click', () => { pal.index = index; choosePalette(); });
        box.appendChild(node);
      });
    });
  }

  async function searchFiles(query) {
    const pal = state.palette;
    if (!pal || pal.kind === 'command') return;
    pal.loading = true;
    renderPalette();
    try {
      const dir = (state.sessions[0] || {}).directory || '';
      const data = await apiGet(`/files?query=${encodeURIComponent(query)}&directory=${encodeURIComponent(dir)}`);
      if (!state.palette || state.palette.kind === 'command') return;
      state.palette.files = data.files || [];
      state.palette.loading = false;
      rebuildMentionItems(state.palette);
      renderPalette();
    } catch (e) {
      if (state.palette) {
        state.palette.loading = false;
        state.palette.files = [];
        rebuildMentionItems(state.palette);
        renderPalette();
      }
    }
  }

  function replaceRange(start, end, text) {
    const input = $('#input');
    input.value = input.value.slice(0, start) + text + input.value.slice(end);
    const pos = start + text.length;
    input.setSelectionRange(pos, pos);
    input.focus();
    autoGrow();
  }

  async function choosePalette() {
    const pal = state.palette;
    if (!pal) return;
    const item = pal.items[pal.index];
    if (!item) return;

    if (item.type === 'command') {
      // v0.7.11-web23: comando nativo com ação na web → executa; comando
      // só do terminal → pede a troca para a interface do terminal (que
      // roda na moldura ao lado); comando de agente → insere o texto.
      if (item.action) {
        closePalette();
        runCommandAction(item.action);
        return;
      }
      if (item.scope === 'tui') {
        closePalette();
        showTerminalForCommand(item.native);
        return;
      }
      replaceRange(pal.start, pal.end, `${item.name} `);
      closePalette();
      return;
    }

    if (item.type === 'skill') {
      // menção de habilidade: "@id" no texto + anexo em `skills` do prompt
      const text = `@${item.id}`;
      replaceRange(pal.start, pal.end, `${text} `);
      state.pendingSkills = state.pendingSkills.filter((s) => s.id !== item.id);
      state.pendingSkills.push({
        id: item.id,
        mention: { start: pal.start, end: pal.start + text.length, text },
      });
      closePalette();
      return;
    }

    // arquivo do projeto: anexa (o servidor lê e devolve o data URI)
    const dir = (state.sessions[0] || {}).directory || '';
    closePalette();
    replaceRange(pal.start, pal.end, `@${basename(item.path)} `);
    try {
      const data = await apiPost('/file', { path: item.path, directory: dir });
      const file = data.file || {};
      state.attachments.push({ name: file.name || basename(item.path), uri: file.uri, mime: '' });
      renderAttachments();
    } catch (e) {
      toast(`não foi possível anexar ${item.path}`, 'err');
    }
  }

  function movePalette(delta) {
    const pal = state.palette;
    if (!pal || !pal.items.length) return;
    pal.index = (pal.index + delta + pal.items.length) % pal.items.length;
    renderPalette();
  }

  /* ── ações dos comandos nativos ────────────────────────────────────── */

  /** Executa no web o equivalente de um comando nativo da TUI. */
  async function runCommandAction(action) {
    switch (action) {
      case 'new-session': await newSession(); return;
      case 'rename-session': renameSession(); return;
      case 'fork-session': await forkSession(); return;
      case 'compact-session': await compactSession(); return;
      case 'background-session': await backgroundSession(); return;
      case 'copy-session-link': await copySessionLink(); return;
      case 'open-models': openModels(); return;
      case 'open-variants': openVariants(); return;
      case 'open-agents': openAgents(); return;
      case 'open-skills': openSkillPalette(); return;
      case 'open-settings': openSettings('geral'); return;
      case 'open-shortcuts': openSettings('atalhos'); return;
      case 'toggle-theme':
        applyTheme(currentTheme() === 'pesquisai-light' ? 'pesquisai' : 'pesquisai-light');
        return;
      case 'toggle-terminal': showTerminalForCommand(''); return;
      // v0.7.11-web30: parar a execução (também pelo atalho Esc)
      case 'stop': await stop(); return;
      default: return;
    }
  }

  /** Abre a paleta de habilidades (``@``). */
  function openSkillPalette() {
    const input = $('#input');
    input.focus();
    const pos = input.selectionStart ?? input.value.length;
    input.value = `${input.value.slice(0, pos)}@${input.value.slice(pos)}`;
    input.setSelectionRange(pos + 1, pos + 1);
    const trig = triggerAtCaret();
    if (trig) openPalette(trig.kind, trig.query, trig.start, trig.end);
    autoGrow();
  }

  /** Copia o link da sessão atual. */
  async function copySessionLink() {
    const url = `${location.origin}${location.pathname}#${state.sessionId}`;
    try {
      await navigator.clipboard.writeText(url);
      toast(t('session.copy'));
    } catch (e) {
      toast(t('tool.copyFail'), 'err');
    }
  }

  /**
   * Comando que só existe no terminal (TUI): pede ao wrapper que mostre a
   * moldura do terminal — ele fica ao lado da web, no mesmo ambiente.
   */
  function showTerminalForCommand(command) {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({
          type: 'ufvai-show-terminal',
          command: command ? `/${command}` : '',
        }, '*');
      }
    } catch (e) { /* cross-origin bloqueado */ }
    toast(t('palette.terminalOnly'));
  }

  /* ── seletor de modelo ────────────────────────────────────────────── */

  function modelMeta(model) {
    return model.context ? `${Math.round(model.context / 1000)}k` : '';
  }

  function renderModelList(filter) {
    const list = $('#model-list');
    list.innerHTML = '';
    const needle = (filter || '').trim().toLowerCase();
    const groups = new Map();
    state.models.forEach((model) => {
      if (needle) {
        const hay = `${model.name} ${model.id} ${model.providerID}`.toLowerCase();
        if (!hay.includes(needle)) return;
      }
      if (!groups.has(model.providerID)) groups.set(model.providerID, []);
      groups.get(model.providerID).push(model);
    });

    const providerMeta = new Map((state.providers || []).map((p) => [p.id, p]));
    let shown = 0;
    groups.forEach((models, providerID) => {
      const meta = providerMeta.get(providerID) || {};
      const head = el('div', 'model-group');
      head.textContent = `${meta.name || providerID} · ${models.length}`;
      list.appendChild(head);
      models.sort((a, b) => (b.available - a.available) || a.name.localeCompare(b.name));
      models.forEach((model) => {
        const item = el('button', 'model-item' + (model.id === state.model.id && model.providerID === state.model.providerID ? ' current' : ''));
        item.type = 'button';
        if (!model.available) item.classList.add('unavailable');
        const name = el('div', 'm-name');
        name.appendChild(document.createTextNode(model.name));
        const sub = el('small');
        sub.textContent = model.id;
        name.appendChild(sub);
        item.appendChild(name);
        if (model.cost && model.cost.free) item.appendChild(el('span', 'badge free', 'grátis'));
        if (!model.available) item.appendChild(el('span', 'badge nokey', 'sem chave'));
        item.appendChild(el('span', 'm-meta', modelMeta(model)));
        item.addEventListener('click', () => pickModel(model));
        list.appendChild(item);
        shown++;
      });
    });

    if (!shown) list.appendChild(el('div', 'model-group', 'nenhum modelo encontrado'));
    $('#model-foot').textContent = state.models.length
      ? `${state.models.length} modelos · ${state.models.filter((m) => m.available).length} com provedor configurado`
      : 'catálogo vazio — o motor ainda está subindo';
  }

  function openModels() {
    $('#model-modal').hidden = false;
    $('#model-search').value = '';
    renderModelList('');
    $('#model-search').focus();
  }

  async function pickModel(model) {
    if (!state.sessionId) { await newSession(); }
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/model`, {
        model: { id: model.id, providerID: model.providerID },
      });
      applyModel({ id: model.id, providerID: model.providerID, variant: '' });
      const row = currentSession();
      if (row) { row.model = { ...state.model }; renderSessions(); }
      $('#model-modal').hidden = true;
      toast(`modelo: ${model.name}`);
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  async function pickVariant(variant) {
    if (!state.sessionId || !state.model.id) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/model`, {
        model: {
          id: state.model.id,
          providerID: state.model.providerID,
          ...(variant ? { variant } : {}),
        },
      });
      applyModel({ ...state.model, variant });
      toast(variant ? `variante: ${variant}` : 'variante: padrão');
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  function openVariants() {
    const entry = currentModelEntry();
    const variants = (entry && entry.variants) || [];
    if (!variants.length) {
      toast('este modelo não tem variantes');
      return;
    }
    const list = $('#session-actions');
    list.innerHTML = '';
    $('#session-modal-title').textContent = 'Variante do modelo';
    const head = el('div', 'model-group', `variantes de ${entry.name}`);
    list.appendChild(head);
    const make = (label, value) => {
      const item = el('button', 'model-item' + (state.model.variant === value ? ' current' : ''));
      item.type = 'button';
      item.appendChild(el('div', 'm-name', label));
      item.addEventListener('click', async () => {
        $('#session-modal').hidden = true;
        await pickVariant(value);
      });
      list.appendChild(item);
    };
    make('padrão', '');
    variants.forEach((v) => make(v, v));
    $('#session-modal').hidden = false;
  }

  /* ── agente (somente UFVAI) ───────────────────────────────────────── */

  function openAgents() {
    // O motor expõe rotinas internas (general, explore, compaction…); a
    // interface do UFVAI mostra **apenas o UFVAI** — abrir aqui leva aos
    // ajustes do agente.
    openSettings('agente');
  }

  /* ── ajustes ──────────────────────────────────────────────────────── */

  function switchRow(label, key, onChange) {
    const r = el('div', 'setting-row');
    r.appendChild(el('div', 's-label', label));
    const sw = el('button', 'switch' + (state.prefs[key] ? ' on' : ''));
    sw.type = 'button';
    sw.setAttribute('role', 'switch');
    sw.setAttribute('aria-checked', state.prefs[key] ? 'true' : 'false');
    sw.setAttribute('aria-label', label);
    sw.addEventListener('click', () => {
      state.prefs[key] = !state.prefs[key];
      sw.classList.toggle('on', state.prefs[key]);
      sw.setAttribute('aria-checked', state.prefs[key] ? 'true' : 'false');
      savePrefs();
      if (onChange) onChange();
    });
    r.appendChild(sw);
    return r;
  }

  function row(label, value) {
    const r = el('div', 'setting-row');
    r.appendChild(el('div', 's-label', label));
    r.appendChild(el('div', 's-value', value));
    return r;
  }

  function renderSettings() {
    const pane = $('#settings-pane');
    pane.innerHTML = '';
    const tab = state.settingsTab;

    if (tab === 'geral') {
      pane.appendChild(el('h3', null, t('settings.appearance')));
      pane.appendChild(row(t('settings.theme'), currentTheme() === 'pesquisai-light' ? 'claro' : 'escuro'));
      pane.appendChild(el('p', null, t('settings.themeNote')));
      pane.appendChild(row(t('settings.language'), (state.locale || 'pt-BR').toUpperCase()));
      pane.appendChild(el('p', null, t('settings.languageNote')));

      pane.appendChild(el('h3', null, t('settings.display')));
      pane.appendChild(el('p', null, t('settings.displayNote')));
      pane.appendChild(switchRow(t('settings.expandReasoning'), 'expandReasoning',
        () => { renderMessages(); }));
      pane.appendChild(switchRow(t('settings.expandTools'), 'expandTools',
        () => { renderMessages(); }));
      // v0.7.11-web40: Enter envia (desligado) ou Ctrl+Enter envia (ligado)
      pane.appendChild(switchRow(t('settings.ctrlEnter'), 'ctrlEnter'));
      pane.appendChild(el('p', null, t('settings.ctrlEnterNote')));
      pane.appendChild(el('p', null, t('settings.expandAllNote')));
      const actions = el('div', 'setting-actions');
      const bAll = el('button', 'btn', t('tool.expandAll'));
      bAll.addEventListener('click', () => {
        setAllExpanded(true);
        renderSettings();
      });
      const bNone = el('button', 'btn', t('tool.collapseAll'));
      bNone.addEventListener('click', () => {
        setAllExpanded(false);
        renderSettings();
      });
      actions.appendChild(bAll);
      actions.appendChild(bNone);
      pane.appendChild(actions);

      pane.appendChild(el('h3', null, t('settings.engine')));
      pane.appendChild(row(t('settings.version'), (state.engine && state.engine.version) || '—'));
      pane.appendChild(row(t('settings.directory'), state.directory || '—'));
      pane.appendChild(row(t('settings.modelsCount'), String(state.models.length)));
      pane.appendChild(row(t('settings.providers'), String((state.providers || []).length)));
    }

    if (tab === 'modelo') {
      pane.appendChild(el('h3', null, t('settings.modelSession')));
      pane.appendChild(row(t('settings.current'), state.model.id ? `${state.model.id} · ${state.model.providerID}` : '—'));
      pane.appendChild(row(t('settings.variantRow'), state.model.variant || t('settings.default')));
      const actions = el('div', 'setting-actions');
      const b = el('button', 'btn primary', t('settings.chooseModel'));
      b.addEventListener('click', () => { $('#settings-modal').hidden = true; openModels(); });
      actions.appendChild(b);
      pane.appendChild(actions);
      pane.appendChild(el('h3', null, t('settings.providersTitle')));
      const list = el('div', 'setting-list');
      (state.providers || []).forEach((p) => {
        const item = el('div', 'setting-item');
        item.appendChild(el('b', null, p.name || p.id));
        item.appendChild(el('span', null,
          `${p.models} modelos · ${p.available ? t('settings.providerOk') : t('settings.providerNoKey')}`));
        list.appendChild(item);
      });
      pane.appendChild(list);
    }

    if (tab === 'agente') {
      pane.appendChild(el('h3', null, t('settings.agent')));
      pane.appendChild(el('p', null, t('settings.agentNote')));
      const list = el('div', 'setting-list');
      state.agents.forEach((a) => {
        const item = el('div', 'setting-item');
        item.appendChild(el('b', null, a.name || a.id));
        item.appendChild(el('span', null,
          [a.description, a.model && a.model.id ? `modelo: ${a.model.id}` : ''].filter(Boolean).join(' · ')));
        list.appendChild(item);
      });
      pane.appendChild(list);
    }

    if (tab === 'comandos') {
      pane.appendChild(el('h3', null, t('palette.commands')));
      pane.appendChild(el('p', null, t('settings.commandsNote')));
      const list = el('div', 'setting-list');
      state.commands.forEach((c) => {
        const item = el('div', 'setting-item');
        item.appendChild(el('b', null, '/' + c.name));
        item.appendChild(el('span', null, [c.title, c.description].filter(Boolean).join(' — ')));
        list.appendChild(item);
      });
      pane.appendChild(list);
    }

    if (tab === 'habilidades') {
      pane.appendChild(el('h3', null, t('palette.skills')));
      const list = el('div', 'setting-list');
      if (!state.skills.length) {
        list.appendChild(el('div', 'setting-item', t('settings.skillsNone')));
      }
      state.skills.forEach((s) => {
        const item = el('div', 'setting-item');
        item.appendChild(el('b', null, s.name || s.id));
        item.appendChild(el('span', null, s.description || ''));
        list.appendChild(item);
      });
      pane.appendChild(list);
    }

    if (tab === 'sessao') {
      const s = currentSession();
      pane.appendChild(el('h3', null, t('settings.sessionCurrent')));
      if (!s) {
        pane.appendChild(el('p', null, t('warn.noSession')));
      } else {
        pane.appendChild(row(t('settings.title'), s.title || s.id));
        pane.appendChild(row(t('settings.id'), s.id));
        pane.appendChild(row(t('settings.agent'), s.agent || 'UFVAI'));
        pane.appendChild(row(t('settings.modelRow'), s.model && s.model.id ? `${s.model.id} · ${s.model.providerID}` : '—'));
        pane.appendChild(row(t('settings.created'), new Date(s.created).toLocaleString('pt-BR')));
        pane.appendChild(row(t('settings.updated'), new Date(s.updated).toLocaleString('pt-BR')));
        const tokens = s.tokens || {};
        pane.appendChild(row(t('settings.tokens'), `${tokens.input || 0} entrada · ${tokens.output || 0} saída · ${tokens.reasoning || 0} raciocínio`));
        pane.appendChild(row(t('settings.cost'), `$${Number(s.cost || 0).toFixed(4)}`));
        if (state.usage && state.usage.limit) {
          pane.appendChild(row(t('top.context'),
            `${Math.round(state.usage.used / 1000)}k / ${Math.round(state.usage.limit / 1000)}k (${state.usage.percent}%)`));
        }
        pane.appendChild(row(t('settings.directory'), s.directory || '—'));
      }
      const actions = el('div', 'setting-actions');
      const b1 = el('button', 'btn', t('settings.showContext'));
      b1.addEventListener('click', showContext);
      const b2 = el('button', 'btn', t('settings.duplicateSession'));
      b2.addEventListener('click', forkSession);
      const b3 = el('button', 'btn', t('settings.compact'));
      b3.addEventListener('click', compactSession);
      actions.appendChild(b1); actions.appendChild(b2); actions.appendChild(b3);
      pane.appendChild(actions);
    }

    if (tab === 'autosave') {
      // v0.7.11-web25: a configuração de autosave vive no WRAPPER (é o que
      // agenda o salvamento). A web lê e escreve por `postMessage`.
      const cfg = state.autosave || {};
      pane.appendChild(el('h3', null, t('settings.tab.autosave')));
      pane.appendChild(el('p', null, t('settings.autosaveNote')));
      pane.appendChild(switchRow(t('settings.autosaveEnabled'), 'autosaveEnabled', async () => {
        await pushAutosave();
      }));
      const interval = el('div', 'setting-row');
      interval.appendChild(el('span', 's-label', t('settings.autosaveInterval')));
      const number = document.createElement('input');
      number.type = 'number';
      number.min = '1';
      number.max = '240';
      number.className = 'num-input';
      number.value = String(cfg.intervalMin || 10);
      number.addEventListener('change', async () => {
        const min = Math.max(1, parseInt(number.value, 10) || 10);
        number.value = String(min);
        if (state.autosave) state.autosave.intervalMin = min;
        await pushAutosave();
      });
      interval.appendChild(number);
      interval.appendChild(el('span', 's-value', t('settings.minutes')));
      pane.appendChild(interval);

      pane.appendChild(el('h3', null, t('settings.autosaveScope')));
      const scopeList = el('div', 'scope-list');
      [['active', t('settings.scopeActive')], ['all', t('settings.scopeAll')],
       ['selected', t('settings.scopeSelected')]].forEach(([value, label]) => {
        const opt = el('button', 'scope-opt' + ((cfg.scope || 'active') === value ? ' on' : ''),
          label);
        opt.type = 'button';
        opt.addEventListener('click', async () => {
          state.autosave.scope = value;
          renderSettings();
          await pushAutosave();
        });
        scopeList.appendChild(opt);
      });
      pane.appendChild(scopeList);

      if ((cfg.scope || 'active') === 'selected') {
        pane.appendChild(el('h3', null, t('settings.autosaveSessions')));
        const list = el('div', 'setting-list');
        const selected = new Set(cfg.selectedIds || []);
        (cfg.sessions || []).forEach((s) => {
          const item = el('label', 'setting-item');
          const box = document.createElement('input');
          box.type = 'checkbox';
          box.checked = selected.has(s.id);
          box.addEventListener('change', async () => {
            const set = new Set(state.autosave.selectedIds || []);
            if (box.checked) set.add(s.id); else set.delete(s.id);
            state.autosave.selectedIds = [...set];
            await pushAutosave();
          });
          item.appendChild(box);
          item.appendChild(el('span', null, s.title || s.id));
          list.appendChild(item);
        });
        if (!state.autosave.sessions || !state.autosave.sessions.length) {
          list.appendChild(el('div', 'setting-item', t('warn.noSession')));
        }
        pane.appendChild(list);
      }
      pane.appendChild(row(t('settings.autosaveState'), cfg.known
        ? t('settings.autosaveConnected') : t('settings.autosaveStandalone')));
    }

    if (tab === 'atalhos') {
      pane.appendChild(el('h3', null, t('settings.shortcuts')));
      pane.appendChild(el('p', null, t('settings.shortcutHint')));
      const atalhos = [
        ['Enter', t('key.send')],
        ['Shift+Enter', t('key.newline')],
        ['/', t('key.commands')],
        ['@', t('key.mention')],
        ['Ctrl+Shift+A', t('key.expandAll')],
        ['Ctrl+B', t('key.background')],
        ['Ctrl+\\', t('key.toggleSidebar')],
        ['Ctrl+U', t('key.attach')],
        ['Esc', t('key.interrupt')],
        ['Ctrl+Shift+R', t('key.close')],
      ];
      atalhos.forEach(([k, d]) => {
        const r = el('div', 'shortcut-row');
        r.appendChild(el('span', null, d));
        const kbd = el('kbd', null, k);
        r.appendChild(kbd);
        pane.appendChild(r);
      });
    }

    if (tab === 'sobre') {
      // v0.7.11-web25: ficha real do UFVAI (fonte: /api/ufvai/about →
      // pesquisai/__version__.py), no lugar do texto genérico.
      const about = state.about || {};
      const card = el('div', 'about');
      const logo = el('div', 'about-logo');
      const img = document.createElement('img');
      img.src = 'assets/logo.svg';
      img.alt = 'UFVAI';
      logo.appendChild(img);
      card.appendChild(logo);
      card.appendChild(el('h3', 'about-name', 'UFVAI — Universidade Federal de Viçosa'));
      card.appendChild(el('p', 'about-tag', t('app.tagline')));
      card.appendChild(el('p', 'about-desc', t('app.description')));
      const rows = el('div', 'about-rows');
      const put = (label, value) => {
        if (!value) return;
        const r = el('div', 'about-row');
        r.appendChild(el('span', 'ar-label', label));
        r.appendChild(el('span', 'ar-value', value));
        rows.appendChild(r);
      };
      put(t('about.version'), about.version || '');
      put(t('about.codename'), about.codename || '');
      put(t('about.release'), about.release_date || '');
      put(t('about.author'), about.author || '');
      put(t('about.email'), about.email || '');
      put(t('about.institution'), about.institution || '');
      put(t('about.registry'), about.registry || '');
      put(t('about.license'), about.license ? `MIT — ${about.license}` : '');
      put(t('about.languages'), (about.languages || '').replace(/_/g, '-'));
      put(t('about.agencies'), about.agencies || '');
      card.appendChild(rows);
      const links = el('div', 'about-links');
      const gh = el('a', 'about-link', 'GitHub — gustavobraga-byte/PesquisAI');
      gh.href = 'https://github.com/gustavobraga-byte/PesquisAI';
      gh.target = '_blank';
      gh.rel = 'noopener';
      links.appendChild(gh);
      const mail = el('a', 'about-link', about.email || '');
      if (about.email) {
        mail.href = `mailto:${about.email}`;
        links.appendChild(mail);
      }
      card.appendChild(links);
      pane.appendChild(card);
    }
  }

  function openSettings(tab) {
    state.settingsTab = tab || state.settingsTab;
    state.settingsOpen = true;
    document.querySelectorAll('#settings-tabs .tab').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.tab === state.settingsTab);
    });
    renderSettings();
    $('#settings-modal').hidden = false;
    // v0.7.11-web33: no telefone as abas ficam numa faixa rolável — a aba
    // ativa precisa aparecer (centralizada), senão "Sobre" ficava fora da
    // tela e o menu parecia não funcionar.
    try {
      const active = document.querySelector('#settings-tabs .tab.active');
      if (active && active.scrollIntoView) {
        active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
      }
    } catch (e) {}
  }

  async function showContext() {
    if (!state.sessionId) return;
    try {
      const data = await apiGet(`/sessions/${encodeURIComponent(state.sessionId)}/context`);
      const list = $('#session-actions');
      list.innerHTML = '';
      const head = el('div', 'model-group', 'contexto da sessão');
      list.appendChild(head);
      const info = data.data || data;
      const item = el('div', 'setting-item');
      item.appendChild(el('b', null, 'Resumo'));
      item.appendChild(el('span', null, JSON.stringify(info).slice(0, 900)));
      list.appendChild(item);
      $('#session-modal').hidden = false;
    } catch (e) {
      toast('não foi possível ler o contexto', 'err');
    }
  }

  async function forkSession() {
    if (!state.sessionId) return;
    try {
      const data = await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/fork`, {});
      await refreshSessions();
      const row = data.session || {};
      if (row.id) {
        state.sessions.unshift(row);
        renderSessions();
        await openSession(row.id, { focus: true });
      }
      $('#session-modal').hidden = true;
      $('#settings-modal').hidden = true;
      toast('sessão duplicada');
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  async function compactSession() {
    if (!state.sessionId) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/compact`, {});
      $('#session-modal').hidden = true;
      $('#settings-modal').hidden = true;
      await openSession(state.sessionId);
      toast('histórico compactado');
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  async function renameSession(sid) {
    const target = sid || state.sessionId;
    if (!target) return;
    const row = state.sessions.find((s) => s.id === target) || currentSession();
    const title = await askText(
      t('session.rename'),
      row ? sessionTitle(row) : '',
      t('session.renamePrompt'),
      t('session.rename'),
    );
    if (!title || !title.trim()) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(target)}/rename`, { title: title.trim() });
      const item = state.sessions.find((s) => s.id === target);
      if (item) item.title = title.trim();
      if (target === state.sessionId) $('#session-title').textContent = title.trim();
      renderSessions();
      toast(t('session.done'));
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  async function backgroundSession() {
    if (!state.sessionId) return;
    try {
      await apiPost(`/sessions/${encodeURIComponent(state.sessionId)}/background`, {});
      toast('execução movida para segundo plano');
      $('#session-modal').hidden = true;
    } catch (e) {
      toast(String(e.message || e), 'err');
    }
  }

  /* ── exportar/copiar a conversa (v0.7.11-web41) ───────────────────── */

  function conversationMarkdown() {
    const row = currentSession();
    const title = row ? sessionTitle(row) : 'UFVAI';
    const lines = [`# ${title}`, ''];
    (state.messages || []).forEach((m) => {
      if (!m || !m.text) return;
      const who = m.role === 'user' ? 'Usuário' : (m.agent || 'UFVAI');
      const when = m.created
        ? new Date(m.created).toLocaleString(state.locale || 'pt-BR')
        : '';
      lines.push(`## ${who}${when ? ` — ${when}` : ''}`, '', m.text, '');
    });
    return lines.join('\n');
  }

  function downloadText(name, text) {
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }

  function exportConversation() {
    const row = currentSession();
    const base = (row ? sessionTitle(row) : 'ufvai')
      .replace(/[^\w.-]+/g, '-').slice(0, 60) || 'ufvai';
    downloadText(`${base}.md`, conversationMarkdown());
    toast(t('session.exported'));
  }

  function copyConversation() {
    navigator.clipboard.writeText(conversationMarkdown()).then(
      () => toast(t('session.copied')),
      () => toast(t('warn.copyFailed'), 'err'),
    );
  }

  function openSessionMenu() {
    const list = $('#session-actions');
    list.innerHTML = '';
    $('#session-modal-title').textContent = t('modal.session');
    const head = el('div', 'model-group', t('sidebar.sessions'));
    list.appendChild(head);
    const actions = [
      [t('session.rename'), renameSession],
      [t('session.fork'), forkSession],
      [t('session.compact'), compactSession],
      [t('session.context'), showContext],
      [t('session.exportMd'), exportConversation],
      [t('session.copyAll'), copyConversation],
      [t('session.background'), backgroundSession],
      [t('session.finalize'), askFinalize],
    ];
    actions.forEach(([label, fn]) => {
      const item = el('button', 'model-item');
      item.type = 'button';
      item.appendChild(el('div', 'm-name', label));
      item.addEventListener('click', () => { $('#session-modal').hidden = true; fn(); });
      list.appendChild(item);
    });
    $('#session-modal').hidden = false;
  }

  /* ── foco TUI → web ───────────────────────────────────────────────── */

  /**
   * v0.7.11-web24: a web seguia a sessão do TERMINAL a cada 2,5 s — e como o
   * ttyd fica em outra sessão, a web **puxava o usuário para outra conversa**
   * no meio do turno (aí a mensagem "parava" e o aviso de execução sumia).
   *
   * Agora a web só segue o foco do terminal quando o **terminal é a vista
   * visível** (o wrapper avisa por `postMessage {type:'ufvai-view'}`) e nunca
   * durante uma execução.
   */
  function pollFocus() {
    if (state.view === 'web') return;
    if (state.running) return;
    apiGet('/focus')
      .then((focus) => {
        if (!focus || !focus.sid) return;
        if (focus.source !== 'tui') return;
        if (focus.sid === state.sessionId) return;
        if (Date.now() - state.manualSwitch < 4000) return;
        openSession(focus.sid);
      })
      .catch(() => {});
  }

  /* ── inicialização ────────────────────────────────────────────────── */

  /**
   * URL da versão atualizada da web, quando ela está em OUTRA porta.
   *
   * v0.7.11-web26: o servidor que o **boot** sobe (8002) carrega o gateway
   * antigo em memória, enquanto o HTML do cliente é lido do disco a cada
   * requisição — ou seja: o cliente novo aparecia, mas as rotas novas
   * (`/api/ufvai/explorer`, `…/finalize`) respondiam 404. Se o gateway
   * Servido não tem a rota, o cliente redireciona para a porta que tem
   * (8003, mantida pelo supervisor).
   */
  function newerWebUrl() {
    try {
      const url = new URL(location.href);
      if (/^8002-/.test(url.host)) {
        url.host = url.host.replace(/^8002-/, '8003-');
      } else if (url.port === '8002') {
        url.port = '8003';
      } else {
        return null;
      }
      return url.toString();
    } catch (e) {
      return null;
    }
  }

  /** Confere se o gateway desta origem tem as rotas da versão atual.

   * Tenta **3 vezes**: logo após o boot o servidor pode estar reiniciando
   * (o supervisor da web nova) e responder 404 por um instante — um 404
   * isolado não significa “gateway antigo”.
   */
  async function gatewayIsCurrent() {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const res = await fetch(api('/explorer?path='), { cache: 'no-store' });
        if (res.ok) return true;
        if (res.status !== 404) return true;   // outro erro: não é falta de rota
      } catch (e) {
        return true; // erro de rede: não redireciona (pode ser o Colab morrendo)
      }
      await new Promise((resolve) => setTimeout(resolve, 600));
    }
    return false;
  }

  /**
   * Aviso de gateway antigo: a página servida por um servidor com o
   * *gateway* antigo (mas com o HTML novo, lido do disco) não tem as rotas
   * novas. No proxy do Colab a porta 8003 é o supervisor da versão
   * atualizada → redireciona; fora dele, mostra o aviso com o link.
   */
  function showGatewayOldNotice(target) {
    const box = $('#gateway-old');
    if (!box) return;
    box.hidden = false;
    const link = $('#gateway-old-link');
    if (link && target) {
      link.href = target;
      link.textContent = target;
    }
  }

  async function boot() {
    loadPrefs();
    applyTheme(currentTheme());
    // v0.7.11-web26: se o gateway desta origem for antigo, vai para a
    // porta que serve a versão completa.
    if (!(await gatewayIsCurrent())) {
      const target = newerWebUrl();
      let isProxy = false;
      try {
        isProxy = /^8002-/.test(new URL(location.href).host);
      } catch (e) { isProxy = false; }
      if (target && isProxy) {
        // no proxy do Colab a 8003 é o supervisor da versão nova
        location.replace(target);
        return;
      }
      // fora do proxy: sonda a outra porta em `no-cors` — uma resposta opaca
      // (status 0) prova que o servidor existe; se a porta estiver fechada
      // o fetch é rejeitado e o aviso é mostrado.
      if (target) {
        try {
          await fetch(target, { mode: 'no-cors', cache: 'no-store' });
          location.replace(target);
          return;
        } catch (e) { /* porta fechada: mostra o aviso */ }
      }
      showGatewayOldNotice(target);
    }
    // v0.7.11-web23: i18n — dicionário local + idioma do wrapper/motor
    await loadI18n();
    const cookieLang = localeFromCookie();
    if (cookieLang) applyLocale(cookieLang);
    let saved = null;
    try { saved = localStorage.getItem('ufvai_web_lang'); } catch (e) { /* ignora */ }
    if (saved && !cookieLang) applyLocale(saved);
    try {
      const loc = await apiGet('/locale');
      if (loc && loc.lang && !cookieLang) applyLocale(loc.lang);
    } catch (e) { /* segue com o idioma salvo */ }
    try {
      if (localStorage.getItem('ufvai_side_hidden') === '1') {
        document.body.classList.add('side-hidden');
        $('#menu-btn').classList.add('on');
      }
    } catch (e) { /* ignora */ }

    let data;
    try {
      data = await apiGet('/bootstrap');
    } catch (e) {
      $('#engine-dot').className = 'dot bad';
      $('#engine-text').textContent = 'sem conexão';
      toast('não foi possível falar com o motor', 'err');
      return;
    }

    state.engine = data.engine || {};
    state.directory = data.directory || '';
    state.agents = data.agents || [];
    state.sessions = data.sessions || [];
    state.active = data.active || {};
    state.models = (data.models && data.models.models) || [];
    state.providers = (data.models && data.models.providers) || [];

    $('#engine-sub').textContent = state.engine.version
      ? `motor ${state.engine.version} · ${state.models.length} modelos`
      : '';
    $('#engine-dot').className = 'dot ok';
    $('#engine-text').textContent = 'motor conectado';

    const preferred = state.agents.find((a) => a.id.toUpperCase() === 'UFVAI');
    state.agent = (preferred || state.agents[0] || {}).id || 'UFVAI';
    $('#agent-label').textContent = state.agent;

    // comandos e habilidades (menus "/" e "@")
    try {
      const extra = await apiGet(`/commands?lang=${encodeURIComponent(state.locale)}`);
      state.commands = extra.commands || [];
      state.skills = extra.skills || [];
    } catch (e) { /* segue sem os menus */ }

    renderSessions();
    renderModelList('');
    renderAttachments();

    const hash = (location.hash || '').replace(/^#/, '');
    const target = (data.current && data.current.id) || (hash || (state.sessions[0] || {}).id);
    if (target) {
      await openSession(target);
    } else {
      await newSession();
    }

    // v0.7.11-web25: rolagem automática — o `ResizeObserver` garante que a
    // conversa **acompanhe** o conteúdo: texto que chega em pedaços, blocos
    // de ferramenta, anexos e o rodapé das mensagens mudam a altura depois do
    // último render (a rolagem ficava alguns pixels acima do fim).
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        if (!state.autoScroll) return;
        // logo após o usuário rolar para cima, não puxa a conversa de volta
        if (Date.now() - lastUserScrollUp < 1500) return;
        scrollToEnd(false);
      });
      observer.observe($('#messages'));
    }

    connectEvents();
    // v0.7.11-web41: nenhum poll roda com a aba oculta (economiza CPU/bateria)
    setInterval(() => { if (isVisible()) refreshSessions(); }, 20000);
    setInterval(() => { if (isVisible()) pollFocus(); }, 2500);
    setInterval(() => { if (isVisible()) refreshUsage(); }, 30000);
    // v0.7.11-web42: formulários da ferramenta "question" — busca periódica
    // (não depende do evento form.created chegar).
    setInterval(() => { if (isVisible() && state.sessionId) loadForms(); }, 3000);
    // v0.7.11-web30: sondagem do estado do motor — o indicador de atividade
    // e o botão de parar não podem depender só do SSE.
    iniciaSondaAtividade();
    // v0.7.11-web25: heartbeat — detecta a queda do ambiente mesmo sem SSE
    setInterval(() => { if (isVisible()) heartbeat(); }, 10000);
    // v0.7.11-web28: FALLBACK de sincronização — a tela não pode depender
    // só do SSE. Enquanto o motor trabalha (ou enquanto o SSE está caído),
    // a web sonda a cauda da conversa e corrige o que ficou para trás.
    setInterval(() => {
      if (!isVisible()) return;
      if (!state.sessionId) return;
      if (state.running || downSince) syncMessages();
    }, 3000);
    // v0.7.11-web28: ao voltar para a aba (ou recuperar o foco), a
    // conversa é reconciliada — nada se perde enquanto a aba estava em
    // segundo plano.
    window.addEventListener('focus', () => syncMessages({ force: true }));
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) syncMessages({ force: true });
    });
    // v0.7.11-web25: ficha do UFVAI e configuração de autosave
    try {
      const about = await apiGet('/about');
      state.about = about || {};
    } catch (e) { /* segue sem a ficha */ }
    askAutosave();
  }

  /* ── eventos da interface ─────────────────────────────────────────── */

  /* v0.7.11-web33: mede a área realmente visível da tela (viewport
     visual) e publica em --app-h. É o que garante que o compositor
     (com o campo de escrita) fique SEMPRE à vista no telefone — com a
     barra de endereço aberta ou com o teclado na tela. */
  function syncViewport() {
    try {
      const vv = window.visualViewport;
      const h = vv && vv.height ? vv.height : window.innerHeight;
      if (!h || h < 120) return;
      document.documentElement.style.setProperty('--app-h', Math.round(h) + 'px');
    } catch (e) {}
  }

  function autoGrow() {
    const input = $('#input');
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 220) + 'px';
  }

  function bind() {
    try {
      const raw = localStorage.getItem('ufvai_prompt_history');
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          state.promptHistory = arr.filter((x) => typeof x === 'string').slice(-50);
        }
      }
    } catch (e) { /* sem histórico */ }
    loadFavorites();
    loadPinned();
    const input = $('#input');
    input.addEventListener('input', () => {
      autoGrow();
      state.historyIdx = -1;
      const trig = triggerAtCaret();
      if (!trig) { closePalette(); return; }
      if (state.palette && state.palette.kind === trig.kind && state.palette.query === trig.query) {
        // mesma consulta: só atualiza o intervalo de substituição
        state.palette.start = trig.start;
        state.palette.end = trig.end;
        return;
      }
      openPalette(trig.kind, trig.query, trig.start, trig.end);
    });
    input.addEventListener('blur', () => setTimeout(() => { if (!state.palette) closePalette(); }, 150));
    input.addEventListener('keydown', (event) => {
      if (state.palette) {
        if (event.key === 'ArrowDown') { event.preventDefault(); movePalette(1); return; }
        if (event.key === 'ArrowUp') { event.preventDefault(); movePalette(-1); return; }
        if (event.key === 'Enter' || event.key === 'Tab') { event.preventDefault(); choosePalette(); return; }
        if (event.key === 'Escape') { event.preventDefault(); closePalette(); return; }
      }
      // v0.7.11-web39: histórico de prompts (↑/↓) quando o campo está vazio
      if (!state.palette && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
        const h = state.promptHistory;
        if (h.length) {
          const editing = input.value.length > 0 && state.historyIdx < 0;
          if (event.key === 'ArrowUp' && !editing) {
            event.preventDefault();
            state.historyIdx = Math.min(state.historyIdx + 1, h.length - 1);
            input.value = h[h.length - 1 - state.historyIdx] || '';
            input.setSelectionRange(input.value.length, input.value.length);
            autoGrow();
            return;
          }
          if (event.key === 'ArrowDown' && state.historyIdx >= 0) {
            event.preventDefault();
            state.historyIdx -= 1;
            input.value = state.historyIdx >= 0
              ? (h[h.length - 1 - state.historyIdx] || '')
              : '';
            input.setSelectionRange(input.value.length, input.value.length);
            autoGrow();
            return;
          }
        }
      }
      // v0.7.11-web40: Enter envia (padrão) ou Ctrl+Enter envia (preferência)
      const sendOnCtrl = !!state.prefs.ctrlEnter;
      const wantsSend = sendOnCtrl
        ? (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.isComposing)
        : (event.key === 'Enter' && !event.shiftKey && !event.isComposing);
      if (wantsSend) {
        event.preventDefault();
        send();
      }
    });

    $('#send-btn').addEventListener('click', send);
    $('#stop-btn').addEventListener('click', stop);
    $('#new-session').addEventListener('click', newSession);
    $('#refresh-btn').addEventListener('click', async () => {
      await refreshSessions();
      toast('atualizado');
    });
    $('#session-search').addEventListener('input', debounce(renderSessions, 150));

    // v0.7.11-web39: seleção em massa de sessões
    $('#bulk-toggle').addEventListener('click', () => toggleBulkMode());
    $('#bulk-all').addEventListener('click', () => {
      const filter = ($('#session-search').value || '').trim().toLowerCase();
      const rows = state.sessions.filter((row) => !filter
        || (row.title || '').toLowerCase().includes(filter)
        || row.id.toLowerCase().includes(filter));
      const all = rows.length && rows.every((r) => state.bulk.selected.has(r.id));
      rows.forEach((r) => {
        if (all) state.bulk.selected.delete(r.id);
        else state.bulk.selected.add(r.id);
      });
      renderSessions();
    });
    $('#bulk-archive').addEventListener('click', askBulk);
    $('#bulk-delete').addEventListener('click', askBulk);
    $('#bulk-cancel').addEventListener('click', () => toggleBulkMode(false));

    $('#fav-btn').addEventListener('click', () => {
      const menu = $('#fav-menu');
      if (!menu) return;
      if (menu.hidden) renderFavMenu(); else menu.hidden = true;
    });
    document.addEventListener('click', (event) => {
      const menu = $('#fav-menu');
      if (!menu || menu.hidden) return;
      if (event.target.closest && (event.target.closest('#fav-menu')
          || event.target.closest('#fav-btn'))) return;
      menu.hidden = true;
    });

    $('#attach-btn').addEventListener('click', () => $('#file-input').click());
    $('#file-input').addEventListener('change', (event) => {
      attachLocalFiles([...event.target.files]);
      event.target.value = '';
    });

    // v0.7.11-web39: busca na conversa (Ctrl+F)
    const findInput = $('#find-input');
    if (findInput) {
      findInput.addEventListener('input', debounce(() => runFind(findInput.value), 150));
      findInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') { event.preventDefault(); stepFind(event.shiftKey ? -1 : 1); }
        if (event.key === 'Escape') { event.preventDefault(); closeFind(); }
      });
    }
    $('#find-prev').addEventListener('click', () => stepFind(-1));
    $('#find-next').addEventListener('click', () => stepFind(1));
    $('#find-close').addEventListener('click', closeFind);

    // v0.7.11-web39: aviso de contexto
    $('#context-compact').addEventListener('click', compactSession);
    $('#context-dismiss').addEventListener('click', () => {
      state.ctxDismissed.add(state.sessionId);
      const box = $('#context-warning');
      if (box) box.hidden = true;
    });

    $('#model-pill').addEventListener('click', openModels);
    $('#model-close').addEventListener('click', () => { $('#model-modal').hidden = true; });
    $('#model-search').addEventListener('input', debounce((e) => renderModelList(e.target.value), 150));

    $('#agent-pill').addEventListener('click', openAgents);
    $('#variant-chip').addEventListener('click', openVariants);

    $('#settings-btn').addEventListener('click', () => openSettings('geral'));
    $('#settings-close').addEventListener('click', () => { $('#settings-modal').hidden = true; });
    document.querySelectorAll('#settings-tabs .tab').forEach((btn) => {
      btn.addEventListener('click', () => openSettings(btn.dataset.tab));
    });

    $('#session-title').addEventListener('dblclick', () => renameSession());
    $('#session-menu-btn').addEventListener('click', openSessionMenu);
    $('#session-close').addEventListener('click', () => { $('#session-modal').hidden = true; });

    // v0.7.11-web23: "expandir tudo" — abre/fecha todos os blocos já
    // renderizados (raciocínio e ferramentas).
    $('#expand-all-btn').addEventListener('click', () => {
      const anyClosed = [...document.querySelectorAll('#messages details.block')]
        .some((b) => !b.open);
      setAllExpanded(anyClosed);
    });

    // v0.7.11-web23: o botão claro/escuro foi removido da web (o do
    // cabeçalho do wrapper é a fonte da verdade).

    $('#thread').addEventListener('scroll', onThreadScroll, { passive: true });
    $('#thread').addEventListener('wheel', onScrollIntent, { passive: true });

    // v0.7.11-web39: arrastar/soltar e colar arquivos no compositor
    const threadBox = $('#thread');
    ['dragenter', 'dragover'].forEach((ev) => {
      threadBox.addEventListener(ev, (event) => {
        const types = event.dataTransfer && event.dataTransfer.types;
        if (!types || ![...types].includes('Files')) return;
        event.preventDefault();
        document.body.classList.add('dragging');
      });
    });
    ['dragleave', 'dragend', 'drop'].forEach((ev) => {
      threadBox.addEventListener(ev, () => document.body.classList.remove('dragging'));
    });
    threadBox.addEventListener('drop', (event) => {
      const files = [...((event.dataTransfer && event.dataTransfer.files) || [])];
      if (!files.length) return;
      event.preventDefault();
      document.body.classList.remove('dragging');
      attachLocalFiles(files);
    });
    document.addEventListener('paste', (event) => {
      const items = [...((event.clipboardData && event.clipboardData.items) || [])];
      const files = items
        .filter((it) => it.kind === 'file')
        .map((it) => it.getAsFile())
        .filter(Boolean);
      if (files.length) { event.preventDefault(); attachLocalFiles(files); }
    });

    // v0.7.11-web39: contador de mensagens novas quando o usuário lê o histórico
    const messagesBox = $('#messages');
    if (messagesBox && window.MutationObserver) {
      new MutationObserver((mutations) => {
        if (state.autoScroll) return;
        let added = 0;
        mutations.forEach((m) => { added += m.addedNodes ? m.addedNodes.length : 0; });
        if (added > 0) {
          state.newSinceScroll += added;
          showJump(true);
        }
      }).observe(messagesBox, { childList: true });
    }
    // v0.7.11-web28: referência a arquivo citada na resposta → abre no
    // explorador (delegado: vale para qualquer mensagem já renderizada).
    document.addEventListener('click', (event) => {
      const ref = event.target && event.target.closest
        ? event.target.closest('.file-ref')
        : null;
      if (!ref) return;
      event.preventDefault();
      openFileInExplorer(ref.getAttribute('data-file'));
    });

    $('#thread').addEventListener('touchmove', onScrollIntent, { passive: true });

    // v0.7.11-web26: explorador de arquivos
    $('#explorer-btn').addEventListener('click', () => {
      if (document.body.classList.contains('explorer-open')) closeExplorer();
      else openExplorer();
    });
    $('#exp-close').addEventListener('click', closeExplorer);
    $('#exp-refresh').addEventListener('click', () => loadExplorer(state.explorerPath, state.explorerQuery));
    $('#exp-up').addEventListener('click', () => {
      const path = String(state.explorerPath || '');
      const parent = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
      loadExplorer(parent, '');
    });
    // v0.7.11-web28: filtro de busca + largura arrastável
    const expSearch = $('#exp-search');
    if (expSearch) {
      expSearch.addEventListener('input', () => onExplorerSearch(expSearch.value));
      expSearch.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') { clearExplorerSearch(); event.preventDefault(); }
      });
    }
    $('#exp-search-clear').addEventListener('click', clearExplorerSearch);
    bindExplorerResizer();
    bindPreviewResizer();
    loadExplorerWidth();
    loadPreviewHeight();
    $('#jump-btn').addEventListener('click', () => {
      state.autoScroll = true;
      state.newSinceScroll = 0;
      const thread = $('#thread');
      if (thread && thread.scrollTo) {
        thread.scrollTo({ top: thread.scrollHeight, behavior: 'smooth' });
      } else {
        scrollToEnd(true);
      }
      setTimeout(() => scrollToEnd(true), 500);
    });
    $('#dead-action').addEventListener('click', () => {
      // v0.7.11-web28: é um link para o notebook no Colab (abre em nova aba)
      toast(t('warn.deadAction'));
    });

    // v0.7.11-web26: confirmação de finalização da sessão
    $('#confirm-close').addEventListener('click', closeConfirm);
    $('#confirm-cancel').addEventListener('click', closeConfirm);
    $('#confirm-archive').addEventListener('click', () => runConfirm('archive'));
    $('#confirm-delete').addEventListener('click', () => runConfirm('delete'));

    $('#menu-btn').addEventListener('click', () => {
      // v0.7.11-web21: no desktop o botão OCULTA as sessões (a coluna
      // colapsa); no responsivo abre a gaveta.
      const mobile = window.matchMedia('(max-width: 900px)').matches;
      if (mobile) {
        document.body.classList.toggle('side-open');
        $('#scrim').hidden = !document.body.classList.contains('side-open');
      } else {
        const hidden = document.body.classList.toggle('side-hidden');
        try { localStorage.setItem('ufvai_side_hidden', hidden ? '1' : '0'); } catch (e) {}
        $('#menu-btn').classList.toggle('on', hidden);
        $('#menu-btn').title = hidden ? t('top.sessions') : t('top.sessions');
      }
    });
    // v0.7.11-web24: o "✕" do quadrado de sessões foi removido (não
    // funcionava); a gaveta fecha pelo botão ☰ ou tocando fora.
    $('#scrim').addEventListener('click', () => {
      document.body.classList.remove('side-open');
      $('#scrim').hidden = true;
    });

    // v0.7.11-web24: modal de entrada (substitui prompt(), bloqueado em iframe)
    $('#prompt-ok').addEventListener('click', () => {
      closeAsk($('#prompt-input').value);
    });
    $('#prompt-cancel').addEventListener('click', () => closeAsk(null));
    $('#prompt-close').addEventListener('click', () => closeAsk(null));
    $('#prompt-input').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') { event.preventDefault(); closeAsk($('#prompt-input').value); }
      if (event.key === 'Escape') { event.preventDefault(); closeAsk(null); }
    });

    // v0.7.11-web40: modal de confirmação genérico
    $('#ask-ok').addEventListener('click', () => closeAskConfirm(true));
    $('#ask-cancel').addEventListener('click', () => closeAskConfirm(false));
    $('#ask-close').addEventListener('click', () => closeAskConfirm(false));

    document.addEventListener('keydown', (event) => {
      // v0.7.11-web39: Esc fecha a busca na conversa
      if (event.key === 'Escape' && state.find.open) {
        event.preventDefault();
        closeFind();
        return;
      }
      // v0.7.11-web30: **Esc** interrompe a execução quando ela está em
      // curso (e nada mais está aberto). As outras camadas de Esc
      // (paleta, modais) marcam `defaultPrevented` — por isso o guarda.
      if (event.key === 'Escape' && !event.defaultPrevented && state.running
          && !isDigitando(event.target)) {
        event.preventDefault();
        stop();
        return;
      }
      if (event.key === 'Escape') {
        closePalette();
        $('#model-modal').hidden = true;
        $('#settings-modal').hidden = true;
        $('#session-modal').hidden = true;
        const fav = $('#fav-menu');
        if (fav) fav.hidden = true;
        closeAskConfirm(false);
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        $('#session-search').focus();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
        event.preventDefault();
        openFind();
      }
      if (event.key === '?' && !isDigitando(event.target)
          && !document.querySelector('.modal:not([hidden])')) {
        event.preventDefault();
        openSettings('atalhos');
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'l') {
        event.preventDefault();
        $('#input').focus();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'b') {
        event.preventDefault();
        backgroundSession();
      }
      // v0.7.11-web23: expandir/recolher tudo
      if ((event.ctrlKey || event.metaKey) && event.shiftKey
          && (event.key === 'A' || event.key === 'a')) {
        event.preventDefault();
        const anyClosed = [...document.querySelectorAll('#messages details.block')]
          .some((b) => !b.open);
        setAllExpanded(anyClosed);
      }
      // v0.7.11-web23: ocultar/mostrar as sessões
      if ((event.ctrlKey || event.metaKey) && event.key === '\\') {
        event.preventDefault();
        $('#menu-btn').click();
      }
      // v0.7.11-web23: anexar arquivo
      if ((event.ctrlKey || event.metaKey) && event.key === 'u') {
        event.preventDefault();
        $('#file-input').click();
      }
    });

    // v0.7.11-web39: prende o foco no modal visível (acessibilidade)
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Tab') return;
      const modals = [...document.querySelectorAll('.modal')].filter((m) => !m.hidden);
      if (!modals.length) return;
      const modal = modals[modals.length - 1];
      const focusables = [...modal.querySelectorAll(
        'a[href],button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'
      )].filter((n) => n.offsetParent !== null);
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    window.addEventListener('beforeunload', () => {
      if (state.source) state.source.close();
    });
    // v0.7.11-web23: o placeholder muda com a largura da tela
    window.addEventListener('resize', () => {
      applyPlaceholder();
      syncViewport();
    });
    // v0.7.11-web33: a altura do app segue o VIEWPORT VISUAL — a área
    // realmente visível da tela. No telefone isso significa:
    //   · com a barra de endereço aberta, o app ocupa só o que se vê
    //     (o campo de escrita não fica atrás do rodapé);
    //   · com o TECLADO aberto, o app encolhe e o campo sobe junto com
    //     o teclado — antes ele ficava escondido atrás dele.
    try {
      if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', syncViewport);
        window.visualViewport.addEventListener('scroll', syncViewport);
      }
    } catch (e) {}
    syncViewport();
  }

  bind();
  boot();

  // Handle de diagnóstico (usado pelos testes de aceitação e pelo autor
  // para depurar no console do navegador). Não expõe nada sensível.
  window.__ufvai = {
    state,
    handleEvent,
    gatewayIsCurrent,
    setRunning,
    showRetryNotice,
    showErrorNotice,
    syncTail,
    syncMessages,
    md,
    loadExplorer,
    renderPermission,
    replyPermission,
    loadPermissions,
    watchRun,
    // v0.7.11-web30: parada e sondagem de atividade (usadas na aceitação)
    stop,
    sondaAtividade,
    iniciaSondaAtividade,
    // v0.7.11-web39: seleção em massa, busca na conversa e aviso de contexto
    toggleBulkMode,
    openFind,
    closeFind,
    runFind,
    maybeWarnContext,
    // v0.7.11-web40: mensagens, fila, favoritos e confirmação
    renderMessage,
    renderMessages,
    send,
    queueMessage,
    flushQueue,
    askConfirm,
    renderFavMenu,
    loadFavorites,
    loadForms,   // v0.7.11-web42: diagnóstico/recarga manual de formulários
    // v0.7.11-web41: sessões (grupo/fixar) e exportação
    renderSessions,
    togglePin,
    sessionGroup,
    conversationMarkdown,
    exportConversation,
  };
})();
