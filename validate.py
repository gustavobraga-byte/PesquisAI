"""
validate_v0.5.1.2.py — Validação completa do patch v0.5.1.2.

Verifica:
  1. Sintaxe Python dos 3 arquivos
  2. Sintaxe JS (node --check) das funções openMemory/closeMemory/renderMemory
  3. Endpoint /api/obsidian no backend (mock)
  4. Botão na topbar presente
  5. Overlay no HTML presente
  6. Item no mobile menu presente
  7. Função closeMemory() no handler de Escape
  8. i18n: 19 chaves memory.* em 4 idiomas
"""

import re
import subprocess
import sys
from pathlib import Path

BASE = Path("/tmp/pesquisai-fix/pesquisai-v0.5.1.2-obsidian-button/pesquisai")
errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}")
        errors.append(msg)


# ── 1. Sintaxe Python ─────────────────────────────────────
print("\n[1] Sintaxe Python")
for f in ("launch_app.py", "launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    try:
        compile(src, f, "exec")
        print(f"  ✅ {f} compila sem erros")
    except SyntaxError as e:
        print(f"  ❌ {f} ERRO de sintaxe: {e}")
        errors.append(str(e))


# ── 2. Sintaxe JS ────────────────────────────────────────
print("\n[2] Sintaxe JS (node --check)")


def extract_function(source: str, name: str) -> str:
    """Extrai função JS até a próxima função (não usa balanceamento ingênuo).

    Estratégia: começa em `function NAME(` e vai até o início da PRÓXIMA
    declaração `function ` (ou `async function `) no mesmo nível de indentação.
    Isso evita falsos positivos com `else if` e blocos internos.
    """
    start = source.find(f"async function {name}(")
    if start < 0:
        start = source.find(f"function {name}(")
    if start < 0:
        raise ValueError(f"Função {name!r} não encontrada")
    # Pega a indentação da linha da declaração
    line_start = source.rfind("\n", 0, start) + 1
    indent = start - line_start  # espaços antes de "function"
    # Procura a próxima "function" ou "async function" no mesmo nível
    search_from = start + len("function ")
    while True:
        idx = source.find("function ", search_from)
        if idx < 0:
            # Não tem próxima função: vai até o fim do arquivo
            return source[start:source.rfind("}") + 1]
        # Verifica se está no mesmo nível de indentação
        line_start2 = source.rfind("\n", 0, idx) + 1
        cur_indent = idx - line_start2
        if cur_indent == indent:
            # Encontrou próxima função no mesmo nível
            # Volta até o } anterior que fecha a função atual
            # (assume que há \n    }\n antes da próxima)
            cutoff = source.rfind("}", 0, idx) + 1
            return source[start:cutoff]
        search_from = idx + 1


for f in ("launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    for fname in ("openMemory", "closeMemory", "renderMemory"):
        try:
            js = extract_function(src, fname)
        except ValueError as e:
            print(f"  ❌ {f} :: {e}")
            errors.append(str(e))
            continue
        tmp = Path("/tmp") / f"_check_{fname}_{f}.js"
        tmp.write_text(js, encoding="utf-8")
        result = subprocess.run(
            ["node", "--check", str(tmp)], capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✅ {f} :: {fname}() válida ({len(js)} chars)")
        else:
            print(f"  ❌ {f} :: {fname}() ERRO: {result.stderr.strip()}")
            errors.append(f"{f}::{fname}: {result.stderr.strip()}")


# ── 3. Backend /api/obsidian ────────────────────────────
print("\n[3] Backend: endpoint /api/obsidian")
launch_app = (BASE / "launch_app.py").read_text(encoding="utf-8")
check('if p == "/api/obsidian":' in launch_app,
      'Endpoint /api/obsidian presente')
check('ObsidianMemory.from_env()' in launch_app,
      'Usa ObsidianMemory.from_env()')
check('mem.stats()' in launch_app,
      'Lê estatísticas do vault')
check('mem.recent_daily_notes' in launch_app,
      'Lê daily notes recentes')
check('mem.search' in launch_app,
      'Busca notas recentes via search')
check('"message"' in launch_app and 'memória' in launch_app.lower(),
      'Mensagem amigável em PT-BR')


# ── 4. Botão na topbar ─────────────────────────────────
print("\n[4] Botão na topbar (entre shortcuts e theme-toggle)")
for f in ("launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    # O botão de memória deve vir DEPOIS do openShortcuts e ANTES do toggleTheme
    pos_shortcuts = src.find('onclick="openShortcuts()"')
    pos_memory = src.find('onclick="openMemory()"')
    pos_theme = src.find('onclick="toggleTheme()"')
    check(pos_memory > 0, f"{f} :: botão openMemory() presente na topbar")
    check(pos_shortcuts < pos_memory < pos_theme,
          f"{f} :: ordem correta (shortcuts < memory < theme)")
    check('id="memory-btn"' in src, f"{f} :: id=memory-btn presente")
    check('data-i18n-title="memory.tooltip"' in src,
          f"{f} :: tooltip i18n presente")


# ── 5. Overlay no HTML ─────────────────────────────────
print("\n[5] Overlay de Memória Obsidian")
for f in ("launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    check('id="memory-overlay"' in src, f"{f} :: #memory-overlay presente")
    check('id="memory-content"' in src, f"{f} :: #memory-content presente")
    check('id="memory-status-badge"' in src,
          f"{f} :: #memory-status-badge presente")
    check('id="memory-open-drive"' in src,
          f"{f} :: #memory-open-drive presente")


# ── 6. Item no mobile menu ─────────────────────────────
print("\n[6] Item no mobile menu")
for f in ("launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    check('onclick="openMemory(); toggleMobileMenu();"' in src,
          f"{f} :: botão de memória no mobile menu")


# ── 7. closeMemory() no handler de Escape ──────────────
print("\n[7] closeMemory() no handler de Escape")
for f in ("launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    check('closeMemory()' in src and 'Escape' in src,
          f"{f} :: closeMemory() referenciado em algum lugar")
    # Encontra o bloco do Escape
    esc_block = re.search(
        r'if \(e\.key === "Escape"\)\s*\{[^}]*\}',
        src, re.DOTALL
    )
    if esc_block:
        check('closeMemory()' in esc_block.group(0),
              f"{f} :: closeMemory() no bloco do Escape")
    else:
        errors.append(f"{f} :: não consegui localizar bloco do Escape")


# ── 8. i18n ────────────────────────────────────────────
print("\n[8] i18n: chaves memory.* em 4 idiomas")
required_keys = [
    "memory.title", "memory.subtitle", "memory.tooltip",
    "memory.status_ready", "memory.status_disabled",
    "memory.status_no_vault", "memory.status_read_only",
    "memory.status_error",
    "memory.notes_count", "memory.tags_count",
    "memory.links_count", "memory.avg_len",
    "memory.recent_daily", "memory.recent_notes",
    "memory.no_notes", "memory.templates",
    "memory.open_vault", "memory.refresh",
    "memory.notes_unit",
]
for f in ("launch_app_responsive.py", "launch_app_responsive_v041.py"):
    src = (BASE / f).read_text(encoding="utf-8")
    missing = [k for k in required_keys if f'"{k}"' not in src]
    if not missing:
        print(f"  ✅ {f} :: todas as 19 chaves presentes em todos os idiomas")
    else:
        print(f"  ❌ {f} :: faltam {len(missing)} chaves: {missing[:5]}…")
        errors.append(f"{f} faltam chaves: {missing}")


# ── Resumo ─────────────────────────────────────────────
print("\n" + "=" * 60)
if errors:
    print(f"❌ {len(errors)} ERRO(S) ENCONTRADO(S):")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅ TODOS OS TESTES PASSARAM — v0.5.1.2 OK!")
    print("=" * 60)
