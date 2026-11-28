"""Servidor do Assistente de Voz LFM3-Omni para UFVAI.

Sobe uma interface web local (porta 8010) com suporte a:
- Gravação de áudio pelo navegador (MediaRecorder)
- Transcrição local via LFM3-Omni-2B (ASR)
- Síntese de voz neural local via LFM3-Omni-2B (TTS)
- Integração com o motor UFVAI para pesquisa científica
"""
from __future__ import annotations

import os
import sys
import time
import uuid
import threading
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from engine import VoiceEngine
from bridge import UFVAIBridge
from live import LiveSession, DEFAULT_MODEL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("lfm3-voz")

BASE = Path(__file__).resolve().parent
TMP = BASE / "tmp"
TMP.mkdir(exist_ok=True)

app = FastAPI(title="UFVAI Voz — LFM3-Omni")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = VoiceEngine.get()
bridge = UFVAIBridge()

# Histórico de conversa local (para o modelo de voz)
history: list[dict] = []


def load_model_bg():
    # O modelo local (9 GB RAM) só é carregado sob demanda, para não derrubar
    # o servidor quando o usuário só quer a conversa ao vivo via Gemini.
    if os.environ.get("UFVAI_VOZ_PRELOAD", "0") == "1":
        engine.load()


@app.on_event("startup")
def startup():
    threading.Thread(target=load_model_bg, daemon=True).start()


@app.get("/ufvai.css")
def ufvai_css():
    """Identidade visual UFVAI (navy + ouro) compartilhada pelas páginas."""
    return Response(
        (BASE / "static" / "ufvai.css").read_text(encoding="utf-8"),
        media_type="text/css",
    )


@app.get("/common.js")
def common_js():
    """Header, tema e ícones SVG compartilhados."""
    return Response(
        (BASE / "static" / "common.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


# ── Cofre de chaves do UFVAI ────────────────────────────────────────────────
# v0.7.12-fix: a chave da conversa ao vivo é salva EXATAMENTE como no fluxo
# "Conectar provedor de IA" (pesquisai.security -> <base>/backups, cifrado).
# Antes ficava em voice/.gemini_key (texto puro) e não sobrevivia às sessões.
_PROJECT_ROOT = BASE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from pesquisai.security import load_encrypted_keys, save_encrypted_keys
    from pesquisai.onboarding import PROVIDERS, normalize_key, validate_key_format

    _GOOGLE_ENV = PROVIDERS["google"]["env"]  # GOOGLE_GENERATIVE_AI_API_KEY
except Exception as exc:  # pragma: no cover — voice/ rodando isolado
    logger.warning("Cofre cifrado indisponível (%s); persistência desabilitada.", exc)
    load_encrypted_keys = lambda _d: {}          # type: ignore
    save_encrypted_keys = lambda _d, _k: False   # type: ignore
    normalize_key = lambda raw: str(raw or "").strip()  # type: ignore
    validate_key_format = lambda _p, k: (bool(k), "")   # type: ignore
    _GOOGLE_ENV = "GOOGLE_GENERATIVE_AI_API_KEY"

_LEGACY_KEY_FILE = BASE / ".gemini_key"  # apenas para migrar instalações antigas


def _backup_dir() -> Path:
    """Mesmo diretório de backup do app principal (DRIVE_BACKUP_DIR)."""
    override = os.environ.get("PESQUISAI_BACKUP_DIR", "").strip()
    if override:
        return Path(override)
    drive_base = Path("/content/drive/My Drive/PesquisAI")
    if drive_base.is_dir() and os.access(drive_base, os.W_OK):
        return drive_base / "backups"
    return Path.home() / "PesquisAI" / "backups"


def _stored_google_key() -> str:
    """Lê a chave Google do cofre cifrado (igual ao Conectar provedor)."""
    try:
        return str(load_encrypted_keys(str(_backup_dir())).get("google", "") or "").strip()
    except Exception:
        return ""


def _mirror_to_bashrc(key: str) -> None:
    """Idêntico ao fluxo do provedor: export no ~/.bashrc, com marcador."""
    try:
        bashrc = os.path.expanduser("~/.bashrc")
        marker = "# opencode-key-google"
        lines: list[str] = []
        if os.path.exists(bashrc):
            with open(bashrc) as fh:
                lines = fh.readlines()
        lines = [
            line for line in lines
            if marker not in line and (_GOOGLE_ENV not in line or "export" not in line)
        ]
        lines.append(f'export {_GOOGLE_ENV}="{key}"  {marker}\n')
        with open(bashrc, "w") as fh:
            fh.writelines(lines)
    except Exception:
        pass


def _store_google_key(key: str) -> bool:
    """Grava no cofre cifrado e aplica no ambiente do processo de voz."""
    store = load_encrypted_keys(str(_backup_dir()))
    store["google"] = key
    store["_env_google"] = _GOOGLE_ENV
    if not save_encrypted_keys(str(_backup_dir()), store):
        return False
    os.environ[_GOOGLE_ENV] = key
    # Compatibilidade com o cliente Gemini Live.
    os.environ["GEMINI_API_KEY"] = key
    os.environ["GOOGLE_API_KEY"] = key
    _mirror_to_bashrc(key)
    return True


def _migrate_legacy_key() -> None:
    """Move chave antiga de voice/.gemini_key para o cofre e apaga o arquivo."""
    try:
        if not _LEGACY_KEY_FILE.is_file() or _stored_google_key():
            return
        key = normalize_key(_LEGACY_KEY_FILE.read_text(encoding="utf-8"))
        if key:
            _store_google_key(key)
        _LEGACY_KEY_FILE.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Falha ao migrar chave legada: %s", exc)


def _saved_gemini_key() -> str:
    """Chave persistida no cofre (mantém compatibilidade com código antigo)."""
    _migrate_legacy_key()
    return _stored_google_key()


@app.get("/api/gemini/key")
def gemini_key_status():
    """Informa se há chave Gemini (valor nunca é devolvido ao navegador)."""
    in_env = bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get(_GOOGLE_ENV)
    )
    configured = in_env or bool(_saved_gemini_key())
    source = "ambiente" if in_env else ("cofre" if _saved_gemini_key() else "nenhuma")
    return {"configured": configured, "source": source}


@app.post("/api/gemini/key")
def gemini_key_save(payload: dict):
    """Salva a chave no MESMO cofre cifrado do 'Conectar provedor de IA'."""
    key = normalize_key(payload.get("key", ""))
    ok, msg = validate_key_format("google", key)
    if not ok:
        return {"ok": False, "error": msg or "Cole uma chave da Gemini API para continuar."}
    try:
        if not _store_google_key(key):
            return {"ok": False, "error": "Falha ao salvar a chave no cofre cifrado do UFVAI."}
    except Exception as exc:
        return {"ok": False, "error": f"Não foi possível salvar a chave: {exc}"}
    return {"ok": True, "configured": True, "source": "cofre"}


@app.get("/start", response_class=HTMLResponse)
def start_page():
    """Página inicial: usuário escolhe Google Live ou LFM local."""
    return (BASE / "static" / "start.html").read_text(encoding="utf-8")


@app.get("/local", response_class=HTMLResponse)
def local_page():
    """Página do LFM local — download do modelo é sob demanda."""
    return (BASE / "static" / "local.html").read_text(encoding="utf-8")


@app.get("/key", response_class=HTMLResponse)
def key_page():
    """Pedido da chave Gemini (mesmo padrão do onboarding do UFVAI)."""
    return (BASE / "static" / "key.html").read_text(encoding="utf-8")


def _model_weights_present() -> bool:
    """Detecta os pesos em MODEL_DIR **ou** no cache do Hugging Face.

    O download falhava (CLI antiga) mas o engine carregava do cache — a UI
    dizia "não baixado" mesmo com 4,3 GB em disco. A checagem agora cobre
    os dois lugares (v0.7.11-web47-fix).
    """
    from engine import MODEL_DIR

    local = MODEL_DIR / "model.safetensors"
    try:
        if local.exists() and local.stat().st_size > 1_000_000_000:
            return True
    except OSError:
        pass
    try:
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache("LiquidAI/LFM3-Omni-2B", "model.safetensors")
        if cached:
            return Path(cached).stat().st_size > 1_000_000_000
    except Exception:  # noqa: BLE001 — cache é otimização, nunca derruba o status
        pass
    return False


@app.get("/api/local/status")
def local_status():
    """Estado do modelo local para a UI: baixado / carregando / pronto."""
    return {
        "downloaded": _model_weights_present(),
        "loaded": engine.loaded,
        "loading": engine.loading,
        "downloading": _DL_STATE["running"],
        "percent": _DL_STATE["percent"],
        "progress": _DL_STATE["message"],
        "error": engine.error or _DL_STATE.get("error") or None,
    }


@app.post("/api/local/download")
def local_download():
    """Baixa o modelo LFM3-Omni-2B apenas quando o usuário pede."""
    if _DL_STATE["running"]:
        return {"ok": False, "error": "download já em andamento"}
    threading.Thread(target=_download_model_bg, daemon=True).start()
    return {"ok": True, "started": True}


@app.post("/api/local/load")
def local_load():
    """Carrega o modelo na memória quando o usuário pede."""
    if not engine.loaded and not engine.loading:
        threading.Thread(target=engine.load, daemon=True).start()
    return {"ok": True}


_DL_STATE = {"running": False, "percent": 0, "message": "", "error": None}


def _hf_download_cmd(model_dir: Path) -> list[str]:
    """Comando de download compatível com a CLI HF instalada.

    huggingface_hub >= 1.x removeu ``python -m huggingface_hub``; o comando
    antigo falhava com ``No module named huggingface_hub.__main__`` e o
    código marcava 100% de qualquer forma (v0.7.11-web47-fix).
    """
    import shutil

    repo = "LiquidAI/LFM3-Omni-2B"
    for exe in ("hf", "huggingface-cli"):
        path = shutil.which(exe)
        if path:
            return [path, "download", repo, "--local-dir", str(model_dir)]
    # Último recurso: API Python (sem depender de executável na PATH).
    return [
        sys.executable, "-c",
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download({repo!r}, local_dir={str(model_dir)!r})",
    ]


def _download_model_bg():
    import re
    import subprocess
    from engine import MODEL_DIR

    _DL_STATE.update(running=True, percent=0, message="Iniciando download de ~4,1 GB…", error=None)
    try:
        cmd = _hf_download_cmd(MODEL_DIR)
        logger.info("Download do modelo local: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        # tqdm escreve com \r; o `for` só separa por \n — normalizar para
        # extrair cada atualização de porcentagem (barra de progresso real).
        for raw in proc.stdout or []:
            for line in raw.replace("\r", "\n").split("\n"):
                line = line.strip()
                if not line:
                    continue
                m = re.search(r"(\d{1,3})\s*%", line)
                if m:
                    pct = min(100, max(0, int(m.group(1))))
                    if pct >= _DL_STATE["percent"]:
                        _DL_STATE["percent"] = pct
                _DL_STATE["message"] = line[-160:]
        proc.wait()
        if proc.returncode != 0:
            detail = _DL_STATE["message"] or f"código de saída {proc.returncode}"
            _DL_STATE.update(
                error=f"Falha no download (código {proc.returncode}): {detail}"
            )
            logger.error("Download falhou: %s", _DL_STATE["error"])
            return  # nunca fingir sucesso; finally limpa o estado "running"
        _DL_STATE.update(percent=100, message="Download concluído. Carregando modelo…")
        engine.load()
        if engine.error:
            _DL_STATE["error"] = engine.error
    except Exception as exc:  # noqa: BLE001
        _DL_STATE["error"] = str(exc)
        _DL_STATE["message"] = f"Erro: {exc}"
        logger.exception("Falha no download do modelo local")
    finally:
        _DL_STATE["running"] = False


@app.get("/live", response_class=HTMLResponse)
def live_page():
    return (BASE / "static" / "live.html").read_text(encoding="utf-8")


@app.websocket("/ws/live")
async def live_ws(ws: WebSocket):
    await ws.accept()
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
        or ws.query_params.get("key", "")
        or _saved_gemini_key()
    )
    if not api_key:
        await ws.send_json({
            "type": "error",
            "message": "Configure GEMINI_API_KEY (gratuita em aistudio.google.com/apikey) para usar a conversa ao vivo.",
        })
        await ws.close()
        return
    session = LiveSession(ws, api_key=api_key)
    await session.run()


@app.get("/", response_class=HTMLResponse)
def index():
    """Raiz = seletor de motor (Google Live ou LFM local)."""
    return (BASE / "static" / "start.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    return {
        "loaded": engine.loaded,
        "loading": engine.loading,
        "error": engine.error,
        "device": engine.device,
        "ufvai_available": bridge.available(),
        "live_model": DEFAULT_MODEL,
        "live_key_configured": bool(
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
            or _saved_gemini_key()
        ),
    }


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not engine.loaded:
        return JSONResponse({"error": "Modelo não carregado"}, status_code=503)
    
    ext = Path(file.filename).suffix or ".webm"
    path = TMP / f"rec_{uuid.uuid4().hex}{ext}"
    content = await file.read()
    path.write_bytes(content)
    
    # Converte para WAV 16kHz mono se necessário (via ffmpeg ou librosa)
    wav_path = path.with_suffix(".wav")
    try:
        import librosa
        import soundfile as sf
        y, sr = librosa.load(str(path), sr=16000, mono=True)
        sf.write(str(wav_path), y, 16000)
    except Exception as e:
        logger.error("Erro na conversão de áudio: %s", e)
        return JSONResponse({"error": f"Falha ao processar áudio: {e}"}, status_code=400)
    
    try:
        text = engine.transcribe(str(wav_path))
        return {"text": text}
    except Exception as e:
        logger.exception("Erro no ASR")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


@app.post("/api/chat")
async def chat(payload: dict):
    if not engine.loaded:
        return JSONResponse({"error": "Modelo não carregado"}, status_code=503)
    
    user_text = payload.get("text", "").strip()
    use_ufvai = payload.get("use_ufvai", False)
    sid = payload.get("sid")
    grillme = payload.get("grillme", False)
    is_research = False
    if not user_text:
        return {"text": "", "audio": None}
    
    # Modo grill-me (LFM local): entrevista para montar o prompt do UFVAI.
    # Nunca delega ao UFVAI nesse modo — o objetivo é esclarecer a intenção.
    if grillme:
        logger.info("Grill-me local: %s", user_text[:60])
        sys = (
            "Você é o assistente de voz do UFVAI e está entrevistando o usuário "
            "para montar o melhor COMANDO para o UFVAI. Use sempre a palavra "
            "'comando', nunca 'prompt'. Fale em português brasileiro, frases curtas "
            "e naturais. Faça UMA pergunta por vez, em no máximo 6 rodadas, "
            "esclarecendo: tema/objetivo, tipo de entrega, dados disponíveis, recorte e "
            "normas (ABNT/APA/Vancouver). Quando tiver informação suficiente, apresente "
            "o comando final completo entre <<<COMANDO_UFVAI>>> e <<<FIM_COMANDO>>>, "
            "incluindo a exigência de não inventar dados nem referências. "
            "SEMPRE pergunte por voz se o comando está aprovado. Se o usuário confirmar "
            "(sim, pode executar, está bom), responda apenas: 'Comando aprovado. "
            "Executando agora.' Se não concordar, continue a entrevista e apresente um "
            "novo bloco <<<COMANDO_UFVAI>>> atualizado. Não invente dados."
        )
        reply_text = engine.chat(user_text, history=history[-8:], system_prompt=sys)
        speech_text = reply_text.replace("<<<COMANDO_UFVAI>>>", "").replace("<<<FIM_COMANDO>>>", "")[:600]
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
    else:
        # Roteamento: se estiver integrado à sessão do UFVAI, sempre delega.
        ufvai_keywords = ["pesquise", "ufvai", "artigo", "paper", "dados", "ibge", "datasus", "referência", "citação"]
        is_research = bool(sid) or use_ufvai or any(k in user_text.lower() for k in ufvai_keywords)
        if is_research and bridge.available():
            logger.info("Delegando ao UFVAI (sid=%s): %s", sid, user_text)
            reply_text = bridge.ask(user_text, sid=sid)
            speech_text = reply_text.replace("*", "").replace("#", "").replace("`", "")
            if len(speech_text) > 600:
                speech_text = speech_text[:600] + "... O restante está na tela."
        else:
            logger.info("Respondendo localmente: %s", user_text)
            system_prompt = (
                "Você é o assistente de voz do UFVAI, um agente de pesquisa científica da UFV. "
                "Responda em português brasileiro, de forma clara, concisa e adequada para síntese de voz. "
                "Não invente dados nem referências."
            )
            reply_text = engine.chat(user_text, history=history[-6:], system_prompt=system_prompt)
            speech_text = reply_text
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply_text})
    
    # Sintetiza a resposta
    audio_b64 = None
    try:
        wav_bytes = engine.synthesize(speech_text)
        import base64
        audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    except Exception as e:
        logger.error("Erro no TTS: %s", e)
    
    source = "grillme" if grillme else ("ufvai" if is_research and bridge.available() else "local")
    return {
        "text": reply_text,
        "audio": audio_b64,
        "source": source
    }


@app.post("/api/tts")
async def tts(payload: dict):
    if not engine.loaded:
        return JSONResponse({"error": "Modelo não carregado"}, status_code=503)
    text = payload.get("text", "")
    try:
        wav_bytes = engine.synthesize(text)
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    port = int(os.environ.get("LFM3_VOZ_PORT", 8010))
    print(f"\n🎙️  UFVAI Voz (LFM3-Omni-2B) rodando em http://127.0.0.1:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
