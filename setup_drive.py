import os

DRIVE_FOLDER = "PesquisAI"
MOUNT_PATH = "/content/drive"
FOLDER_PATH = os.path.join(MOUNT_PATH, "My Drive", DRIVE_FOLDER)
FALLBACK_URL = "https://drive.google.com/drive/my-drive"

url_direta = FALLBACK_URL
folder_path = FOLDER_PATH


def mount_drive():
    global url_direta, folder_path
    
    try:
        from google.colab import drive, auth
        from googleapiclient.discovery import build
    except ImportError:
        print("⚠️  Não está rodando no Google Colab. Pulando montagem do Drive.")
        os.makedirs("/tmp/pesquisai_work", exist_ok=True)
        folder_path = "/tmp/pesquisai_work"
        return folder_path, FALLBACK_URL
    
    print("📂 Montando Google Drive...")
    drive.mount(MOUNT_PATH, force_remount=True)
    
    os.makedirs(FOLDER_PATH, exist_ok=True)
    os.chdir(FOLDER_PATH)
    folder_path = FOLDER_PATH
    print(f"📂 Diretório de trabalho: {os.getcwd()}")
    
    try:
        auth.authenticate_user()
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
            print(f"🔗 Link da pasta: {url_direta}")
        else:
            print("⚠️  Pasta não encontrada na API do Drive — usando link genérico.")
    except Exception as exc:
        print(f"⚠️  Erro na Drive API ({exc}) — usando link genérico.")
    
    return folder_path, url_direta


def get_drive_info():
    return folder_path, url_direta


if __name__ == "__main__":
    mount_drive()
