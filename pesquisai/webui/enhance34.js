/* ==========================================================================
   UFVAI · web34 — melhorias ADITIVAS de produtividade (2026-11-16)
   --------------------------------------------------------------------------
   Carregado DEPOIS de app.js. Não altera, não substitui e não remove
   nenhuma função existente — apenas ACRESCENTA:
     1. Chips de início rápido no estado vazio (preenchem o compositor);
     2. Alternador de densidade (confortável ⇄ compacta), persistido;
     3. Linha de dicas de atalhos sob o compositor (oculta no celular).
   Strings nos 5 idiomas da interface; acompanha o <html lang> que o
   app.js atualiza via postMessage do wrapper.
   ========================================================================== */
(function () {
  'use strict';

  var DENS_KEY = 'ufvai_w34_density';

  var L = {
    'pt-BR': {
      density: 'Densidade da conversa',
      densityCompact: 'Alternar para densidade compacta',
      densityComfy: 'Alternar para densidade confortável',
      chips: [
        ['📚', 'Revisão de literatura sobre: '],
        ['📊', 'Consultar dados do IBGE sobre: '],
        ['🏥', 'Consultar dados do DataSUS sobre: '],
        ['📝', 'Normalizar referências em ABNT: '],
        ['🔍', 'Analisar qualitativamente o texto: '],
        ['📁', 'Abrir o explorador de arquivos']
      ],
      hints: [
        ['Enter', 'enviar'], ['Shift+Enter', 'nova linha'], ['/', 'comandos'],
        ['@', 'habilidades e arquivos'], ['Esc', 'parar'], ['Ctrl+L', 'focar o campo']
      ]
    },
    'en': {
      density: 'Conversation density',
      densityCompact: 'Switch to compact density',
      densityComfy: 'Switch to comfortable density',
      chips: [
        ['📚', 'Literature review on: '],
        ['📊', 'Query IBGE data on: '],
        ['🏥', 'Query DataSUS data on: '],
        ['📝', 'Format references in ABNT: '],
        ['🔍', 'Qualitatively analyze the text: '],
        ['📁', 'Open the file explorer']
      ],
      hints: [
        ['Enter', 'send'], ['Shift+Enter', 'new line'], ['/', 'commands'],
        ['@', 'skills & files'], ['Esc', 'stop'], ['Ctrl+L', 'focus input']
      ]
    },
    'es': {
      density: 'Densidad de la conversación',
      densityCompact: 'Cambiar a densidad compacta',
      densityComfy: 'Cambiar a densidad cómoda',
      chips: [
        ['📚', 'Revisión de literatura sobre: '],
        ['📊', 'Consultar datos del IBGE sobre: '],
        ['🏥', 'Consultar datos del DataSUS sobre: '],
        ['📝', 'Normalizar referencias en ABNT: '],
        ['🔍', 'Analizar cualitativamente el texto: '],
        ['📁', 'Abrir el explorador de archivos']
      ],
      hints: [
        ['Enter', 'enviar'], ['Shift+Enter', 'nueva línea'], ['/', 'comandos'],
        ['@', 'habilidades y archivos'], ['Esc', 'detener'], ['Ctrl+L', 'enfocar el campo']
      ]
    },
    'fr': {
      density: 'Densité de la conversation',
      densityCompact: 'Passer en densité compacte',
      densityComfy: 'Passer en densité confortable',
      chips: [
        ['📚', 'Revue de littérature sur : '],
        ['📊', 'Consulter les données IBGE sur : '],
        ['🏥', 'Consulter les données DataSUS sur : '],
        ['📝', 'Normaliser les références en ABNT : '],
        ['🔍', 'Analyser qualitativement le texte : '],
        ['📁', 'Ouvrir l’explorateur de fichiers']
      ],
      hints: [
        ['Enter', 'envoyer'], ['Shift+Enter', 'nouvelle ligne'], ['/', 'commandes'],
        ['@', 'compétences et fichiers'], ['Esc', 'arrêter'], ['Ctrl+L', 'cibler le champ']
      ]
    },
    'zh': {
      density: '对话密度',
      densityCompact: '切换到紧凑密度',
      densityComfy: '切换到舒适密度',
      chips: [
        ['📚', '文献综述：'],
        ['📊', '查询 IBGE 数据：'],
        ['🏥', '查询 DataSUS 数据：'],
        ['📝', '按 ABNT 规范整理参考文献：'],
        ['🔍', '对文本进行定性分析：'],
        ['📁', '打开文件浏览器']
      ],
      hints: [
        ['Enter', '发送'], ['Shift+Enter', '换行'], ['/', '命令'],
        ['@', '技能与文件'], ['Esc', '停止'], ['Ctrl+L', '聚焦输入框']
      ]
    }
  };

  function dict() {
    var lang = (document.documentElement.getAttribute('lang') || 'pt-BR');
    return L[lang] || L['pt-BR'];
  }

  /* ── 1. chips de início rápido ─────────────────────────────────────── */
  var chipsBox = null;

  function fillInput(text) {
    var input = document.getElementById('input');
    if (!input) return;
    input.value = text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
    try { input.setSelectionRange(text.length, text.length); } catch (e) {}
  }

  function chipAction(index) {
    var d = dict();
    if (index === 5) {
      var btn = document.getElementById('explorer-btn');
      if (btn) btn.click();
      return;
    }
    fillInput(d.chips[index][1]);
  }

  function buildChips() {
    var empty = document.getElementById('empty-state');
    if (!empty || chipsBox) return;
    chipsBox = document.createElement('div');
    chipsBox.className = 'w34-chips';
    chipsBox.setAttribute('role', 'group');
    var d = dict();
    d.chips.forEach(function (c, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'w34-chip';
      b.innerHTML = '<span class="w34-chip-ico" aria-hidden="true"></span><span class="w34-chip-txt"></span>';
      b.querySelector('.w34-chip-ico').textContent = c[0];
      b.querySelector('.w34-chip-txt').textContent = c[1].replace(/:\s*$/, '');
      b.addEventListener('click', function () { chipAction(i); });
      chipsBox.appendChild(b);
    });
    empty.appendChild(chipsBox);
  }

  function refreshChips() {
    if (!chipsBox) return;
    var d = dict();
    var txts = chipsBox.querySelectorAll('.w34-chip-txt');
    d.chips.forEach(function (c, i) {
      if (txts[i]) txts[i].textContent = c[1].replace(/:\s*$/, '');
    });
  }

  /* ── 2. densidade confortável ⇄ compacta ───────────────────────────── */
  var densBtn = null;

  function isCompact() { return document.body.classList.contains('w34-compact'); }

  function applyDensity(compact, persist) {
    document.body.classList.toggle('w34-compact', compact);
    if (densBtn) {
      var d = dict();
      densBtn.title = (compact ? d.densityComfy : d.densityCompact) + ' · ' + d.density;
      densBtn.setAttribute('aria-label', densBtn.title);
      densBtn.setAttribute('aria-pressed', compact ? 'true' : 'false');
      densBtn.classList.toggle('on', compact);
      densBtn.textContent = compact ? '⇱' : '⇲';
    }
    if (persist) {
      try { localStorage.setItem(DENS_KEY, compact ? 'compact' : 'comfy'); } catch (e) {}
    }
  }

  function buildDensityButton() {
    var actions = document.querySelector('.top-actions');
    if (!actions || densBtn) return;
    densBtn = document.createElement('button');
    densBtn.type = 'button';
    densBtn.id = 'w34-density-btn';
    densBtn.className = 'icon-btn';
    var settings = document.getElementById('settings-btn');
    actions.insertBefore(densBtn, settings || null);
    densBtn.addEventListener('click', function () { applyDensity(!isCompact(), true); });
    var saved = null;
    try { saved = localStorage.getItem(DENS_KEY); } catch (e) {}
    applyDensity(saved === 'compact', false);
  }

  /* ── 3. dicas de atalhos sob o compositor ──────────────────────────── */
  var hintsBox = null;

  function buildHints() {
    var composer = document.querySelector('.composer');
    var inner = document.querySelector('.composer-inner');
    if (!composer || !inner || hintsBox) return;
    hintsBox = document.createElement('div');
    hintsBox.className = 'w34-hints';
    hintsBox.setAttribute('aria-hidden', 'true');
    composer.insertBefore(hintsBox, inner.nextSibling);
    refreshHints();
  }

  function refreshHints() {
    if (!hintsBox) return;
    hintsBox.textContent = '';
    dict().hints.forEach(function (h) {
      var s = document.createElement('span');
      var k = document.createElement('kbd');
      k.textContent = h[0];
      s.appendChild(k);
      s.appendChild(document.createTextNode(' ' + h[1]));
      hintsBox.appendChild(s);
    });
  }

  /* ── idioma: acompanha o <html lang> que o app.js atualiza ─────────── */
  function watchLang() {
    try {
      var mo = new MutationObserver(function () {
        refreshChips(); refreshHints();
        if (densBtn) applyDensity(isCompact(), false);
      });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    } catch (e) {}
  }

  function init() {
    try { buildChips(); } catch (e) {}
    try { buildDensityButton(); } catch (e) {}
    try { buildHints(); } catch (e) {}
    try { watchLang(); } catch (e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
