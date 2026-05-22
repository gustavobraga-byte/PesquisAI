import sys
import os

REPO_URL = "https://github.com/gustavobraga-byte/PesquisAI.git"
REPO_DIR = "/tmp/pesquisai_repo"

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
    padding: 40px;
    font-family: 'DM Mono', monospace;
}
.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(79, 195, 247, 0.2);
    border-top-color: #4fc3f7;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 20px;
}
.loading-text {
    color: #4fc3f7;
    font-size: 14px;
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


def run():
    show_loading_message()
    
    print("\n" + "="*50)
    print("  🚀 INICIANDO PESQUISAI")
    print("="*50 + "\n")
    
    print("📦 Configurando dependências...")
    from setup_dependencies import run_all as setup_deps
    setup_deps()
    
    print("\n🔧 Instalando skills...")
    from setup_skills import install_skills
    install_skills()
    
    print("\n📂 Configurando Google Drive...")
    from setup_drive import mount_drive, get_drive_info
    folder_path, drive_url = mount_drive()
    
    print("\n🚀 Iniciando aplicação...")
    from launch_app import launch, set_drive_info
    set_drive_info(folder_path, drive_url)
    launch()
    
    print("\n" + "="*50)
    print("  ✅ PESQUISAI PRONTO!")
    print("="*50)


if __name__ == "__main__":
    run()
