/* UFVAI Voz — componentes compartilhados: header, tema, ícones, base path. */
(function () {
  const BASE = location.pathname.startsWith('/voz') ? '/voz' : '';
  window.ufvaiVoiceBase = BASE;

  // ── Tema (claro/escuro) ─────────────────────────────────────────────
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('ufvai_voice_theme', t); } catch (e) {}
    const btn = document.getElementById('themeBtn');
    if (btn) btn.setAttribute('aria-label', t === 'light' ? 'Ativar tema escuro' : 'Ativar tema claro');
  }
  let saved = null;
  try { saved = localStorage.getItem('ufvai_voice_theme'); } catch (e) {}
  if (!saved) saved = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  applyTheme(saved);

  window.ufvaiToggleTheme = function () {
    const cur = document.documentElement.getAttribute('data-theme');
    applyTheme(cur === 'light' ? 'dark' : 'light');
  };

  // ── Ícones SVG ──────────────────────────────────────────────────────
  const ICONS = {
    // Ondas sonoras (mesmo gesto visual das ondas do microfone)
    wavesLogo: `<svg viewBox="0 0 34 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <g stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
        <path d="M4 11v6"/><path d="M10 6v16"/><path d="M16 2v24"/>
        <path d="M22 7v14"/><path d="M28 11v6"/>
      </g></svg>`,
    spark: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M24 5c1.6 9.8 5.2 13.4 15 15-9.8 1.6-13.4 5.2-15 15-1.6-9.8-5.2-13.4-15-15 9.8-1.6 13.4-5.2 15-15Z"
        fill="currentColor" opacity=".9"/>
      <path d="M38 30c.6 3.4 1.8 4.6 5.2 5.2-3.4.6-4.6 1.8-5.2 5.2-.6-3.4-1.8-4.6-5.2-5.2 3.4-.6 4.6-1.8 5.2-5.2Z"
        fill="currentColor" opacity=".55"/></svg>`,
    chip: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="11" y="11" width="26" height="26" rx="5" stroke="currentColor" stroke-width="2.2"/>
      <rect x="19" y="19" width="10" height="10" rx="2" stroke="currentColor" stroke-width="2"/>
      <path d="M17 11V6M24 11V6M31 11V6M17 42v-5M24 42v-5M31 42v-5M11 17H6M11 24H6M11 31H6M42 17h-5M42 24h-5M42 31h-5"
        stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
    mic: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="18" y="7" width="12" height="24" rx="6" fill="currentColor"/>
      <path d="M12 23a12 12 0 0 0 24 0M24 35v6M18 41h12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>`,
    sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
      <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`,
    moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>`,
    arrow: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M15 18l-6-6 6-6"/></svg>`,
    check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20 6 9 17l-5-5"/></svg>`,
    warn: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>
      <path d="M12 9v4M12 17h.01"/></svg>`
  };
  window.ufvaiIcon = name => ICONS[name] || '';

  // ── Header: ondas sonoras + texto "ufvai" ──────────────────────────
  window.ufvaiHeader = function (section) {
    return `<header class="ufvai-head">
      <span class="logo-waves">${ICONS.wavesLogo}</span>
      <span class="wordmark">ufvai</span>
      <span class="sep">·</span>
      <span class="section">${section}</span>
      <span class="spacer"></span>
      <button class="link theme-btn" id="themeBtn" onclick="ufvaiToggleTheme()" title="Alternar tema">${ICONS.moon}</button>
      <a href="${BASE}/start">Trocar motor</a>
    </header>`;
  };
})();
