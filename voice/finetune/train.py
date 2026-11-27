"""Fine-tuning LoRA do LFM3-Omni-2B para atuar como assistente de voz do UFVAI.

Este script aplica SFT (Supervised Fine-Tuning) com adaptadores LoRA no
backbone de linguagem do modelo omni-modal. O objetivo é alinhar o tom,
a identidade e as regras de integridade científica (zero fabricação)
do assistente de voz às diretrizes do UFVAI.

Uso:
    python3 train.py --epochs 1 --max-steps 20

O adaptador resultante é salvo em ../adapter e carregado pelo engine.py.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForMultimodalLM,
    AutoProcessor,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lfm3-finetune")

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE.parent / "model"
ADAPTER_DIR = BASE.parent / "adapter"


class VoiceDataset(Dataset):
    def __init__(self, path: Path, processor, max_length: int = 256):
        self.samples = []
        self.processor = processor
        self.max_length = max_length
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.samples.append(json.loads(line))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        messages = item["messages"]
        
        # Aplica o template de chat do LFM3-Omni
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        
        # Tokeniza
        inputs = self.processor.tokenizer(
            text,
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = inputs["input_ids"].squeeze(0)
        attention_mask = inputs["attention_mask"].squeeze(0)
        
        # Máscara de labels: treina apenas na resposta do assistente
        labels = input_ids.clone()
        labels[attention_mask == 0] = -100
        
        # Encontra o início da última resposta do assistente para mascarar o prompt
        # (Simplificação robusta: treina em tudo se o delimitador falhar, mas idealmente
        # focamos na resposta. O template LFM3 usa <|im_start|>assistant)
        try:
            assistant_token = self.processor.tokenizer.encode("<|im_start|>assistant", add_special_tokens=False)[-1]
            # Procura a última ocorrência do token de assistente
            indices = (input_ids == assistant_token).nonzero(as_tuple=True)[0]
            if len(indices) > 0:
                last_assistant = indices[-1].item()
                labels[:last_assistant] = -100
        except Exception:
            pass
            
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    args = ap.parse_args()

    logger.info("Carregando processador e modelo base...")
    processor = AutoProcessor.from_pretrained(str(MODEL_DIR), trust_remote_code=True)
    
    # Em CPU, float32 com gradient checkpointing é mais estável que bf16
    # (bf16 em CPU pode ser emulado e muito lento dependendo da build do PyTorch).
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    torch.set_num_threads(4)
    
    model = AutoModelForMultimodalLM.from_pretrained(
        str(MODEL_DIR),
        dtype=dtype,
        device_map=device,
        trust_remote_code=True,
    )
    model.config.use_cache = False
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
        logger.info("Gradient checkpointing ativado.")
    
    # Configuração LoRA: foca nas camadas de atenção do backbone de texto
    logger.info("Aplicando adaptadores LoRA...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    # O modelo omni encapsula o modelo de linguagem; o PEFT precisa encontrar os módulos
    try:
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()
    except Exception as e:
        logger.error("Falha ao aplicar LoRA automaticamente: %s", e)
        logger.info("Tentando aplicar no submódulo de linguagem...")
        # Fallback para arquiteturas compostas
        target = getattr(model, "language_model", getattr(model, "model", model))
        target = get_peft_model(target, lora_config)
        
    dataset = VoiceDataset(BASE / "dataset.jsonl", processor)
    logger.info("Dataset carregado: %d exemplos", len(dataset))
    
    training_args = TrainingArguments(
        output_dir=str(ADAPTER_DIR),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        logging_steps=1,
        save_strategy="no",
        report_to="none",
        remove_unused_columns=False,
        use_cpu=(device == "cpu"),
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )
    
    logger.info("Iniciando treinamento...")
    trainer.train()
    
    logger.info("Salvando adaptador em %s", ADAPTER_DIR)
    ADAPTER_DIR.mkdir(exist_ok=True)
    if hasattr(model, "save_pretrained"):
        model.save_pretrained(str(ADAPTER_DIR))
    else:
        torch.save(model.state_dict(), ADAPTER_DIR / "adapter_model.bin")
    
    logger.info("Fine-tuning concluído.")


if __name__ == "__main__":
    main()
