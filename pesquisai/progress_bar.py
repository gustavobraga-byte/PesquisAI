"""
progress_bar.py — v0.6.7: painel de boot do UFVAI desde o INÍCIO do carregamento.

A antiga barra escura (#0d0f10, spinner colorido) foi APOSENTADA. Agora os
estágios iniciais do run() — Preparando → Google Drive → Dependências →
Skills → Interface — alimentam o MESMO painel leve no tema da logomarca
oficial usado pelo _BootPanel de launch_app.py:

  · mesma linguagem visual (papel off-white, wordmark "UFV" navy + "AI" dourado);
  · MESMO display_id ("ufvai_boot_panel") → a barra nunca reinicia nem duplica;
  · mensagens/checkpoints SEMPRE abaixo da barra de progresso.

O PesquisAI.ipynb embute uma réplica mínima deste painel ainda na fase de
clone do repositório (antes do pacote existir em /tmp), então a barra nasce
no primeiro segundo e é continuada aqui sem solução de continuidade.

API pública preservada: show(step, total, message) / finish().
Fora do Colab (sem IPython) mantém o fallback ASCII legado.
"""

# ── Detecção de ambiente IPython/Colab ──────────────────────
IN_COLAB: bool = False

try:
    from IPython.display import clear_output as _clear_func

    IN_COLAB = True
except ImportError:  # terminal puro (.deb/offline)
    _clear_func = None

# Percentuais dos estágios do setup dentro da jornada completa de boot.
# O launch() continua EXATAMENTE de onde este mapa termina (82 → 99 → 100),
# garantindo barra monotônica (nunca regressiva) de ponta a ponta.
_STAGE_PCT: dict[int, int] = {0: 6, 1: 20, 2: 48, 3: 72, 4: 80}


def show(step: int = 0, total: int = 4, message: str = "Iniciando...") -> None:
    """Atualiza o painel de boot com o estágio atual do setup.

    Delega ao painel compartilhado (launch_app.get_boot_panel()): cada
    chamada conclui a linha anterior com ✓ e revela a nova mensagem como
    linha ativa (spinner) ABAIXO da barra dourada. Erros de renderização
    NUNCA interrompem o setup.
    """
    if total <= 0:
        total = 1
    pct = _STAGE_PCT.get(int(step))
    if pct is None:
        pct = min(max(int(round(100 * step / total)), 2), 99)

    try:
        from pesquisai.launch_app import get_boot_panel

        get_boot_panel().active(message.rstrip(".").strip() + "...", pct)
        return
    except Exception:
        pass

    # ── Fallback ASCII (terminal/offline sem painel disponível) ──
    if IN_COLAB:
        return
    bar = "█" * (pct // 4) + "░" * (25 - pct // 4)
    print(f"\r  {message:<42} {bar} {pct:>3}%", end="", flush=True)


def finish() -> None:
    """Encerra a fase de setup: limpa a saída antes da mensagem final/botão.

    Mantém o contrato legado — logs de instalação e o próprio painel saem
    de cena para o card final (logomarca + botão) aparecer limpo.
    """
    if IN_COLAB and _clear_func is not None:
        try:
            _clear_func(wait=True)
        except Exception:
            pass
    else:
        print()
