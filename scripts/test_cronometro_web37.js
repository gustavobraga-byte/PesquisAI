#!/usr/bin/env node
/**
 * test_cronometro_web37.js — validação do cronômetro HH:MM:SS (v0.7.11-web37).
 *
 * Roda SEM dependências: node scripts/test_cronometro_web37.js
 * Verifica que:
 *   1. app.js define formataCronometro() e a usa no texto do indicador;
 *   2. a função formata 0/1/59/60/3599/3600/3725/86399/90061 s corretamente;
 *   3. o antigo formato "${seg}s" não está mais no indicador de atividade.
 */
const fs = require('fs');
const path = require('path');

const appPath = path.join(__dirname, '..', 'pesquisai', 'webui', 'app.js');
const src = fs.readFileSync(appPath, 'utf8');
let ok = 0, total = 0;
function check(name, cond) {
  total++;
  console.log((cond ? '✓' : '✗') + '  ' + name);
  if (cond) ok++;
}

check('app.js define formataCronometro()', /function\s+formataCronometro\s*\(/.test(src));
check('atualizaTextoAtividade usa formataCronometro(seg)',
      /atualizaTextoAtividade[\s\S]{0,600}formataCronometro\(seg\)/.test(src));
check('indicador NÃO usa mais `${seg}s`',
      !/\$\{base\} · \$\{seg\}s/.test(src));

// Extrai e executa a função real do arquivo (sem duplicar a implementação).
const m = src.match(/function\s+formataCronometro\s*\([^)]*\)\s*\{[\s\S]*?\n  \}/);
if (!m) {
  console.log('✗  não foi possível extrair formataCronometro() do app.js');
  process.exit(1);
}
const formataCronometro = new Function('return (' + m[0] + ')')();

const casos = [
  [0, '00:00:00'], [1, '00:00:01'], [59, '00:00:59'], [60, '00:01:00'],
  [65, '00:01:05'], [3599, '00:59:59'], [3600, '01:00:00'], [3725, '01:02:05'],
  [86399, '23:59:59'], [90061, '25:01:01'],
];
for (const [entrada, esperado] of casos) {
  check(`${entrada}s -> ${esperado}`, formataCronometro(entrada) === esperado);
}

console.log(`\n${ok}/${total} verificações passaram`);
process.exit(ok === total ? 0 : 1);
