import sys
import os

from constants import logger
from jokes import next_joke


def ensure_in_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False


def show_loading_message():
    if ensure_in_colab():
        from IPython.display import display, HTML
        display(HTML("""
<style>
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
.loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
}
.spinner {
    width: 56px;
    height: 56px;
    border: 4px solid rgba(79, 195, 247, 0.12);
    border-top-color: #4fc3f7;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 24px;
}
.loading-text {
    color: #4fc3f7;
    font-family: monospace;
    font-size: 15px;
    animation: pulse 1.5s ease-in-out infinite;
}
</style>
<div class="loading-container">
    <div class="spinner"></div>
    <div class="loading-text">Carregando o PesquisAI...</div>
</div>
"""))
    else:
        print("⏳ Carregando o PesquisAI...")


def show_ready_message():
    if ensure_in_colab():
        from IPython.display import display, HTML
        display(HTML("""
<style>
@keyframes glow {
    0%, 100% { box-shadow: 0 0 20px rgba(93, 186, 126, 0.3); }
    50% { box-shadow: 0 0 40px rgba(93, 186, 126, 0.6); }
}
.ready-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 30px 20px 10px 20px;
}
.ready-badge {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    padding: 16px 32px;
    background: rgba(93, 186, 126, 0.12);
    border: 2px solid rgba(93, 186, 126, 0.4);
    border-radius: 12px;
    animation: glow 2s ease-in-out infinite;
}
.ready-icon {
    font-size: 28px;
}
.ready-text {
    font-family: 'DM Mono', monospace;
    font-size: 18px;
    font-weight: 600;
    color: #5dba7e;
}
</style>
<div class="ready-container">
    <div class="ready-badge">
        <span class="ready-icon">✨</span>
        <span class="ready-text">PesquisAI pronto!</span>
    </div>
</div>
"""))
    else:
        print("\n✨ PesquisAI pronto!\n")


def run():
    show_loading_message()

    print("\n" + "="*50)
    print("  🧑‍🔬  INICIANDO PESQUISAI")
    print("="*50)

    print(f"\n{next_joke('administracao')}")
    from setup_drive import mount_drive
    folder_path, drive_url = mount_drive()

    print(f"\n{next_joke('administracao')}")
    from setup_dependencies import run_all as setup_deps
    setup_deps()

    print(f"\n{next_joke('administracao')}")
    from setup_skills import install_skills
    install_skills()

    print(f"\n{next_joke('administracao')}")
    from launch_app import launch, set_drive_info
    set_drive_info(folder_path, drive_url)

    print(f"\n{next_joke('administracao')}")
    launch()

    print(f"\n ")


if __name__ == "__main__":
    run()
