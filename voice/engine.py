"""Motor de voz LFM3-Omni-2B para o UFVAI.

Carrega o modelo omni-modal da Liquid AI e expõe uma interface unificada
para transcrição (ASR), síntese (TTS) e conversação (texto/áudio).
"""
from __future__ import annotations

import os
import logging
import threading
from pathlib import Path

import torch
import numpy as np
import soundfile as sf

logger = logging.getLogger("lfm3-voz")

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE / "model"
ADAPTER_DIR = BASE / "adapter"


class VoiceEngine:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.model = None
        self.processor = None
        self.codec = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self.loaded = False
        self.loading = False
        self.error = None

    @classmethod
    def get(cls) -> "VoiceEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def load(self):
        if self.loaded or self.loading:
            return
        self.loading = True
        self.error = None
        try:
            from transformers import AutoModelForMultimodalLM, AutoProcessor

            model_id = str(MODEL_DIR) if MODEL_DIR.exists() else "LiquidAI/LFM3-Omni-2B"
            logger.info("Carregando %s em %s (%s)...", model_id, self.device, self.dtype)
            
            self.model = AutoModelForMultimodalLM.from_pretrained(
                model_id,
                dtype=self.dtype,
                device_map=self.device,
                trust_remote_code=True,
            ).eval()
            self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
            self.codec = self.processor.audio_tokenizer.to(device=self.device).eval()
            
            # Carrega o adaptador LoRA (fine-tuning UFVAI) se existir
            if (ADAPTER_DIR / "adapter_config.json").exists():
                try:
                    from peft import PeftModel
                    logger.info("Carregando adaptador LoRA UFVAI de %s", ADAPTER_DIR)
                    self.model = PeftModel.from_pretrained(self.model, str(ADAPTER_DIR))
                    logger.info("Adaptador LoRA aplicado com sucesso.")
                except Exception as e:
                    logger.error("Falha ao carregar adaptador LoRA: %s", e)
            
            self.loaded = True
            logger.info("Modelo carregado com sucesso.")
        except Exception as e:
            self.error = str(e)
            logger.exception("Falha ao carregar o modelo LFM3-Omni-2B")
        finally:
            self.loading = False

    def _ensure_loaded(self):
        if not self.loaded:
            if self.error:
                raise RuntimeError(f"Modelo indisponível: {self.error}")
            raise RuntimeError("Modelo ainda não carregado. Aguarde a inicialização.")

    def transcribe(self, audio_path: str, language: str = "Portuguese") -> str:
        self._ensure_loaded()
        conversation = [
            {"role": "system", "content": f"Perform ASR in {language}."},
            {"role": "user", "content": [{"type": "audio", "audio": audio_path}]},
        ]
        inputs = self.processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, max_new_tokens=1024, generation_mode="text"
            )
            text = self.processor.decode(
                outputs.sequences[0, inputs["input_ids"].shape[1] : outputs.sequence_lengths[0]],
                skip_special_tokens=True,
            )
        return text.strip()

    def synthesize(self, text: str, language: str = "Portuguese", gender: str = "female") -> bytes:
        self._ensure_loaded()
        conversation = [
            {"role": "system", "content": f"Perform TTS in {language} using a {gender} voice."},
            {"role": "user", "content": text},
        ]
        inputs = self.processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                generation_mode="audio",
                audio_temperature=0.4,
                audio_repetition_penalty=1.2,
            )
            waveform = self.codec.decode(
                outputs.audio_codes[:1, :, : outputs.audio_lengths[0]]
            ).audio_values[0]
            
        wav = waveform.squeeze(0).float().cpu().numpy()
        import io
        buf = io.BytesIO()
        sf.write(buf, wav, 24_000, format="WAV")
        return buf.getvalue()

    def chat(self, text: str, history: list[dict] | None = None, system_prompt: str | None = None) -> str:
        self._ensure_loaded()
        sys_text = system_prompt or "You are a helpful voice assistant. Respond in text in Brazilian Portuguese. Keep answers concise and natural for speech."
        conversation = [{"role": "system", "content": sys_text}]
        if history:
            conversation.extend(history)
        conversation.append({"role": "user", "content": text})
        
        inputs = self.processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, max_new_tokens=512, generation_mode="text"
            )
            response = self.processor.decode(
                outputs.sequences[0, inputs["input_ids"].shape[1] : outputs.sequence_lengths[0]],
                skip_special_tokens=True,
            )
        return response.strip()
