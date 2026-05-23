import sys
import os
import random

REPO_URL = "https://github.com/gustavobraga-byte/PesquisAI.git"

JOKES_EXTRA = [
    "👥 Recrutamento: você foi recrutado para a equipe da espera.",
    "📣 Posicionamento: esse download está no mercado da lentidão.",
    "🚚 Cadeia de suprimentos: a cadeia está completamente parada.",
    "⚖️ Prescrição: seu direito de reclamar já prescreveu.",
    "🏥 Diagnóstico: síndrome do download lento.",
    "👥 Treinamento: treinando a arte da paciência há muitos minutos.",
    "📣 Funil de vendas: você está no fundo do funil, esperando.",
    "🚚 Lead time: tempo de espera = indefinido.",
    "⚖️ Código Civil: artigo sobre espera rápida não existe.",
    "🏥 Pressão arterial: subindo a cada minuto.",
    "👥 Avaliação de desempenho: seu desempenho em esperar é excelente.",
    "📣 Branding: a marca é conhecida como 'O que não chega'.",
    "🚚 Just in Time: mais como Just Never.",
    "⚖️ Jurisprudência: todos os downloads lentos são iguais.",
    "🏥 Córtex cerebral: área da paciência sobrecarregada.",
    "👥 Clima organizacional: clima tenso de espera.",
    "📣 Valor percebido: cada minuto vale menos que o anterior.",
    "🚚 Estoque: seu estoque de paciência está acabando.",
    "⚖️ Indenização: você deveria ser indenizado por perda de paciência.",
    "🏥 Tratamento: café e mais café.",
    "👥 Motivação: baixo, mas a esperança ainda existe.",
    "📣 Growth: o único growth é o da sua frustração.",
    "🚚 KPI: Key Performance Indicator = Zero.",
    "⚖️ LGPD: seus dados de paciência estão sendo processados.",
    "🏥 Prognóstico: bom, se o download terminar hoje.",
]

_joke_index = 0

def next_joke_extra():
    global _joke_index
    if _joke_index < len(JOKES_EXTRA):
        joke = JOKES_EXTRA[_joke_index]
        _joke_index += 1
        return joke
    return JOKES_EXTRA[-1]


def ensure_in_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False


def setup_auth_first():
    print("  🔐 Solicitando permissões do Google Drive")
    print("-"*60)
    print("\n📋 Preciso dessa permissão para utilizar a pasta no google drive...")
    print("   (Dica, você pode inserir arquivos nessa pasta e o PesquisAI pode interagir com ele)\n")
    
    try:
        from google.colab import drive, auth
        from googleapiclient.discovery import build
        import os
    except ImportError:
        print("⚠️  Não está no Colab. Pulando autenticação.")
        return None, "https://drive.google.com/drive/my-drive"
    
    DRIVE_FOLDER = "PesquisAI"
    MOUNT_PATH = "/content/drive"
    FOLDER_PATH = os.path.join(MOUNT_PATH, "My Drive", DRIVE_FOLDER)
    FALLBACK_URL = "https://drive.google.com/drive/my-drive"
    url_direta = FALLBACK_URL
    
    if not os.path.exists(os.path.join(MOUNT_PATH, "My Drive")):
        print("📂 Montando Google Drive...")
        try:
            drive.mount(MOUNT_PATH, force_remount=False)
            print("✅ Drive montado!")
        except Exception as e:
            print(f"⚠️  Aviso ao montar: {e}")
            os.makedirs("/tmp/pesquisai_work", exist_ok=True)
            return "/tmp/pesquisai_work", FALLBACK_URL
    else:
        print("✅ Google Drive já está montado!")
    
    print("\n🔐 Autenticando usuário para API do Drive...")
    try:
        auth.authenticate_user()
        print("✅ Autenticação concluída!")
    except Exception as e:
        print(f"⚠️  Aviso na autenticação: {e}")
    
    os.makedirs(FOLDER_PATH, exist_ok=True)
    os.chdir(FOLDER_PATH)
    
    try:
        service = build("drive", "v3")
        query = (
            f"name = '{DRIVE_FOLDER}' "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        resultado = service.files().list(q=query, fields="files(id)").execute()
        arquivos = resultado.get("files", [])
        
        if arquivos:
            folder_id = arquivos[0]["id"]
            url_direta = f"https://drive.google.com/drive/folders/{folder_id}"
    except:
        pass
    
    return FOLDER_PATH, url_direta


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
    
    folder_path, drive_url = setup_auth_first()
    
    print(f"\n{next_joke_extra()}")
    from setup_dependencies import run_all as setup_deps
    setup_deps()
    
    print(f"\n{next_joke_extra()}")
    from setup_skills import install_skills
    install_skills()
    
    print(f"\n{next_joke_extra()}")
    from launch_app import launch, set_drive_info
    set_drive_info(folder_path, drive_url)
    
    print(f"\n{next_joke_extra()}")
    launch()
    
    print(f"\n ")


if __name__ == "__main__":
    run()
