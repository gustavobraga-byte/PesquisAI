"""
progress_bar.py — Barra de progresso visual para o setup do PesquisAI.

Funciona tanto no Google Colab (HTML interativo) quanto em terminal (ASCII).
"""

import time
from typing import Optional

# ── Detecção de ambiente Colab ──────────────────────────────
IN_COLAB: bool = False
_handle = None
_clear = None

try:
    from IPython.display import display, HTML, clear_output as _clear_func
    _clear = _clear_func
    IN_COLAB = True
except ImportError:
    display = None
    HTML = None

STAGES: list[str] = [
    "Configurando Google Drive",
    "Instalando dependências",
    "Instalando skills",
    "Iniciando interface",
]

COLORS: list[str] = ["#4fc3f7", "#5dba7e", "#e8b84b", "#a47de0"]


def _html(step: int, total: int, message: str, percent: int) -> str:
    """Gera o HTML da barra de progresso para exibição no Colab."""
    if total <= 0:
        total = 1
    idx = min(step, total - 1)
    stage = STAGES[idx] if idx < len(STAGES) else "Finalizando"
    color = COLORS[idx % len(COLORS)]
    return f"""<div id="ppbar" style="
    max-width:680px; margin:20px auto 16px; padding:16px 22px;
    background:#0d0f10; border:1px solid rgba(255,255,255,.07);
    border-radius:10px; font-family:system-ui,-apple-system,sans-serif;
">
    <div style="display:flex; align-items:center; gap:11px; margin-bottom:12px;">
        <div style="
            width:24px; height:24px; border-radius:50%;
            border:3px solid {color}; border-top-color:transparent;
            animation:ppsp 0.85s linear infinite;
        "></div>
        <div>
            <div style="color:#e8e6e0; font-size:14px; font-weight:600;">
                {stage}
            </div>
            <div style="color:#8a8780; font-size:11.5px; margin-top:1px;">
                {message}
            </div>
        </div>
        <div style="margin-left:auto; color:{color}; font-size:13px; font-weight:700;">
            {percent}%
        </div>
    </div>
    <div style="
        width:100%; height:5px; background:rgba(255,255,255,.05);
        border-radius:3px; overflow:hidden;
    ">
        <div style="
            width:{percent}%; height:100%;
            background:linear-gradient(90deg, {color}, {color}cc);
            border-radius:3px; transition:width .35s ease;
        "></div>
    </div>
    <style>
        @keyframes ppsp{{to{{transform:rotate(360deg)}}}}
    </style>
</div>"""


def show(step: int = 0, total: int = 4, message: str = "Iniciando...") -> None:
    """Atualiza a barra de progresso com o passo atual."""
    global _handle
    if total <= 0:
        total = 1
    percent = min(int((step / total) * 100), 100)
    html = _html(step, total, message, percent)

    if IN_COLAB and display and HTML:
        if _handle is None:
            _handle = display(HTML(html), display_id=True)
        else:
            _handle.update(HTML(html))
    else:
        bar = "█" * (percent // 4) + "░" * (25 - percent // 4)
        idx = min(step, total - 1)
        stage = STAGES[idx] if idx < len(STAGES) else "Finalizando"
        print(f"\r  {stage:<38} {bar} {percent:>3}%  {message}", end="", flush=True)


def finish() -> None:
    """Limpa a barra de progresso ao finalizar."""
    global _handle
    if IN_COLAB and _clear:
        _clear(wait=True)
        _handle = None
    else:
        print()
