"""
main.py — Ponto de entrada principal do PesquisAI.

Delega para run_fast.py (versão otimizada).

Uso:
    python main.py
    # ou
    from main import run
"""

from pesquisai.run_fast import run

if __name__ == "__main__":
    run()
