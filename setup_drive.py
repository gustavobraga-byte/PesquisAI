import os

from constants import DRIVE_PATH, MOUNT_PATH, FALLBACK_URL, logger
from jokes import next_joke

url_direta = FALLBACK_URL
folder_path = DRIVE_PATH
_already_mounted = False
_already_authenticated = False


def is_drive_mounted():
    return os.path.exists(os.path.join(MOUNT_PATH, "My Drive"))


def mount_drive():
    global url_direta, folder_path, _already_mounted, _already_authenticated

    print(next_joke("astronomia"))
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
        print(next_joke("astronomia"))
        print("✅ Google Drive já está montado! Pulando autorização.")
    else:
        print(next_joke("astronomia"))
        print("📂 Montando Google Drive (pedindo autorização apenas uma vez)...")
        try:
            drive.mount(MOUNT_PATH, force_remount=False)
            _already_mounted = True
            print("✅ Drive montado com sucesso!")
        except Exception as e:
            logger.warning("Aviso ao montar Drive: %s", e)
            if not is_drive_mounted():
                os.makedirs("/tmp/pesquisai_work", exist_ok=True)
                folder_path = "/tmp/pesquisai_work"
                return folder_path, FALLBACK_URL

    os.makedirs(DRIVE_PATH, exist_ok=True)
    os.chdir(DRIVE_PATH)
    folder_path = DRIVE_PATH
    print(f"📂 Diretório de trabalho: {os.getcwd()}")

    try:
        print(next_joke("astronomia"))
        if not _already_authenticated:
            auth.authenticate_user()
            _already_authenticated = True
            print("✅ Autenticação concluída!")
        else:
            print("✅ Já autenticado!")

        service = build("drive", "v3")
        query = (
            f"name = 'PesquisAI' "
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
        logger.warning("Erro na Drive API (%s) — usando link genérico.", exc)

    print(next_joke("astronomia"))
    return folder_path, url_direta


def get_drive_info():
    return folder_path, url_direta


if __name__ == "__main__":
    mount_drive()
