"""Ponte entre o assistente de voz e o motor UFVAI (OpenCode).

Permite que o assistente de voz delegue perguntas científicas/complexas
para o UFVAI, criando sessões e recuperando respostas reais.
"""
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path

logger = logging.getLogger("lfm3-voz")

# Tenta localizar o pacote pesquisai no projeto UFVAI
ROOT = Path(__file__).resolve().parents[2]
UFVAI_SRC = ROOT / "UFVAI-v0.7.11-web46"
if UFVAI_SRC.exists() and str(UFVAI_SRC) not in sys.path:
    sys.path.insert(0, str(UFVAI_SRC))

try:
    from pesquisai import webapi
except ImportError:
    webapi = None
    logger.warning("Módulo pesquisai.webapi não encontrado. A ponte com o UFVAI estará indisponível.")


class UFVAIBridge:
    def __init__(self):
        self.session_id = None

    def available(self) -> bool:
        if not webapi:
            return False
        host, port, _ = webapi.engine()
        return bool(port)

    def ensure_session(self, sid: str | None = None) -> str | None:
        if not self.available():
            return None
        if sid:
            self.session_id = sid
            return sid
        if self.session_id:
            sess = webapi.session(self.session_id)
            if sess:
                return self.session_id
        
        # Cria nova sessão dedicada à voz
        sess = webapi.create_session(title="Assistente de Voz (LFM3-Omni)", agent="UFVAI")
        if sess:
            self.session_id = sess["id"]
            return self.session_id
        return None

    def list_models(self, limit: int = 24) -> list[dict]:
        """Modelos disponíveis no UFVAI (gratuitos primeiro) para a voz escolher."""
        if not self.available():
            return []
        try:
            data = webapi.catalog() if hasattr(webapi, "catalog") else None
            rows = (data or {}).get("models") if isinstance(data, dict) else None
            if not rows:
                import urllib.request, json
                req = urllib.request.Request("http://127.0.0.1:8002/api/ufvai/models")
                with urllib.request.urlopen(req, timeout=10) as r:
                    rows = json.load(r).get("models", [])
            free = [m for m in rows if (m.get("cost") or {}).get("free")]
            paid = [m for m in rows if not (m.get("cost") or {}).get("free")]
            picked = (free + paid)[:limit]
            return [
                {
                    "id": m.get("id"),
                    "providerID": m.get("providerID"),
                    "name": m.get("name") or m.get("id"),
                    "free": bool((m.get("cost") or {}).get("free")),
                    "context": m.get("context"),
                }
                for m in picked
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao listar modelos: %s", exc)
            return []

    def set_model(self, model: dict, sid: str | None = None) -> bool:
        """Troca o modelo da sessão antes de executar o comando."""
        sid = self.ensure_session(sid)
        if not sid or not model.get("id") or not model.get("providerID"):
            return False
        try:
            res = webapi.set_model(sid, model)
            if res.get("ok"):
                logger.info("Modelo da sessão alterado para %s/%s", model["providerID"], model["id"])
                return True
            logger.warning("Falha ao trocar modelo: %s", res.get("error"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erro ao trocar modelo: %s", exc)
        return False

    def ask(self, prompt: str, sid: str | None = None, model: dict | None = None,
            timeout: int = 180) -> str:
        sid = self.ensure_session(sid)
        if not sid:
            return "Desculpe, o motor UFVAI não está acessível no momento."
        if model:
            self.set_model(model, sid)

        # Envia o prompt
        res = webapi.send_prompt(sid, prompt)
        if not res.get("ok"):
            return f"Erro ao enviar para o UFVAI: {res.get('error')}"
        
        # Aguarda a resposta (polling simples e robusto)
        start = time.time()
        last_count = 0
        while time.time() - start < timeout:
            time.sleep(2)
            msgs = webapi.messages(sid)
            if len(msgs) > last_count:
                last_count = len(msgs)
                last = msgs[-1]
                if last["role"] == "assistant" and last.get("completed"):
                    return last["text"]
            
            # Verifica se a sessão ainda está ocupada
            sess = webapi.session(sid)
            if sess and not sess.get("busy") and last_count > 0:
                msgs = webapi.messages(sid)
                if msgs and msgs[-1]["role"] == "assistant":
                    return msgs[-1]["text"]
                    
        return "O UFVAI demorou muito para responder. Verifique a interface principal."
