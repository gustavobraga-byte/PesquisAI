"""PesquisAI - Agente de IA para Pesquisa Cientifica com foco em dados brasileiros.

Package principal do PesquisAI. Modulos:
    - constants:       constantes e configuracoes centralizadas
    - __version__:     versao unica (fonte de verdade)
    - jokes:           catalogo de piadas cientificas
    - progress_bar:    barra de progresso do setup
    - opencode_utils:  localizacao do binario opencode
    - security:        criptografia de chaves e sanitizacao de comandos
    - run_fast:        orquestrador otimizado do setup
    - launch_app:      servidor web wrapper + terminal ttyd
"""

from .__version__ import __version__  # noqa: F401

__all__ = ["__version__"]
