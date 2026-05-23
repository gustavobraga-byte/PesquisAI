import os

DRIVE_FOLDER = "PesquisAI"
MOUNT_PATH = "/content/drive"
FOLDER_PATH = os.path.join(MOUNT_PATH, "My Drive", DRIVE_FOLDER)
FALLBACK_URL = "https://drive.google.com/drive/my-drive"

url_direta = FALLBACK_URL
folder_path = FOLDER_PATH
_already_mounted = False
_already_authenticated = False

JOKES_DRIVE = [
    "🌌 O universo tem 13.8 bilhões de anos. Esse processo parece mais velho.",
    "🧮 A soma da sua paciência já ultrapassou o número de Pi.",
    "🌌 A luz do sol chega à Terra em 8 minutos. Esse processo...",
    "🧮 Esse progresso é uma série convergente para o infinito.",
    "🌌 Buraco negro: suga toda a sua paciência.",
    "🧮 Complexidade Big O: O(muito devagar)",
    "🌌 Constelação: Ursa Maior da Paciência",
    "🧮 A probabilidade de terminar logo é tendendo a zero.",
    "🌌 Gravidade: está puxando sua paciência para baixo.",
    "🧮 Assíntota: chega perto mas nunca chega.",
]

_joke_index = 0

def next_joke():
    global _joke_index
    if _joke_index < len(JOKES_DRIVE):
        joke = JOKES_DRIVE[_joke_index]
        _joke_index += 1
        return joke
    return JOKES_DRIVE[-1]


def is_drive_mounted():
    return os.path.exists(os.path.join(MOUNT_PATH, "My Drive"))


def mount_drive():
    global url_direta, folder_path, _already_mounted, _already_authenticated
    
    print(f"\n{next_joke()}")
    print("📂 Configurando Google Drive...")
    
    try:
        from google.colab import drive, auth
        from googleapiclient.discovery import build
    except ImportError:
        print("⚠️  Não está rodando no Google Colab. Pulando montagem do Drive.")
        os.makedirs("/tmp/pesquisai_work", exist_ok=True)
        folder_path = "/tmp/pesquisai_work"
        return folder_path, FALLBACK_URL
    
    if is_drive_mounted() and _already_mounted:
        print(f"\n{next_joke()}")
        print("✅ Google Drive já está montado! Pulando autorização.")
    else:
        print(f"\n{next_joke()}")
        print("📂 Montando Google Drive (pedindo autorização apenas uma vez)...")
        try:
            drive.mount(MOUNT_PATH, force_remount=False)
            _already_mounted = True
            print("✅ Drive montado com sucesso!")
        except Exception as e:
            print(f"⚠️  Aviso ao montar Drive: {e}")
            if not is_drive_mounted():
                os.makedirs("/tmp/pesquisai_work", exist_ok=True)
                folder_path = "/tmp/pesquisai_work"
                return folder_path, FALLBACK_URL
    
    os.makedirs(FOLDER_PATH, exist_ok=True)
    os.chdir(FOLDER_PATH)
    folder_path = FOLDER_PATH
    print(f"📂 Diretório de trabalho: {os.getcwd()}")
    
    try:
        print(f"\n{next_joke()}")
        if not _already_authenticated:
            auth.authenticate_user()
            _already_authenticated = True
            print("✅ Autenticação concluída!")
        else:
            print("✅ Já autenticado!")
        
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
    
    print(f"\n{next_joke()}")
    return folder_path, url_direta


def get_drive_info():
    return folder_path, url_direta


if __name__ == "__main__":
    mount_drive()
