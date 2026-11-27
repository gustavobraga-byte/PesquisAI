# 🎙️ UFVAI Voz — Assistente Local LFM3-Omni-2B

Este módulo adiciona capacidades de **voz** ao UFVAI usando o modelo omni-modal
[LiquidAI/LFM3-Omni-2B](https://huggingface.co/LiquidAI/LFM3-Omni-2B).
Ele roda **localmente** (CPU ou GPU), sem enviar seu áudio para APIs de nuvem.

## O que foi implementado

1. **Motor de Voz (`engine.py`)** — carrega o LFM3-Omni-2B via Hugging Face Transformers.
   Suporta ASR (transcrição), TTS (síntese 24 kHz) e chat local.
2. **Ponte UFVAI (`bridge.py`)** — conecta o assistente ao motor OpenCode do UFVAI,
   permitindo que comandos de voz acionem pesquisas reais (IBGE, DataSUS, papers).
3. **Servidor Web (`server.py`)** — API FastAPI na porta **8010**, com CORS habilitado
   para integração direta com a interface principal do UFVAI.
4. **Interface Integrada** — a web UI do UFVAI (`pesquisai/webui/`) ganhou um botão
   de microfone 🎤 na caixa de texto. O áudio é transcrito localmente e inserido no chat.
5. **Fine-tuning LoRA (`finetune/`)** — script de SFT para alinhar o modelo ao papel
   de assistente científico rigoroso (sem inventar dados ou referências).

## Como usar

### 1. Inicie o servidor de voz
```bash
cd agentes/lfm3-voz
python3 server.py
```
*Na primeira execução, o modelo (4 GB) é baixado automaticamente para `./model`.*

### 2. Abra a interface do UFVAI
Acesse a interface web normal do UFVAI (porta 8001/8002). Um ícone de **microfone**
aparecerá ao lado do campo de texto. Clique nele (ou pressione `Ctrl+M`), fale
sua pergunta e clique em parar. O texto será transcrito e preenchido no chat.

### 3. Interface dedicada (opcional)
Se preferir uma interface só de voz, acesse `http://127.0.0.1:8010`.

## Conversa ao vivo (grill-me)

A página `/voz/live` conduz uma entrevista falada: uma pergunta por vez, até
montar um **comando** completo para o UFVAI (nunca use a palavra "prompt").
Ao final, a assistente pergunta por voz qual modelo usar e se o comando está
aprovado; com a confirmação, ele é copiado e executado automaticamente.

Após o envio, a assistente **sempre** encerra dizendo em voz alta que o comando
já está em execução e que basta aguardar e conferir os resultados na pasta
**PesquisAI do Google Drive**. O mesmo aviso aparece na tela via evento
`final_status`, mesmo que a fala seja interrompida.

## Fine-tuning

O script `finetune/train.py` aplica adaptadores **LoRA** no backbone de linguagem.
O dataset (`finetune/dataset.jsonl`) ensina o modelo a:
- Identificar-se como assistente do UFVAI.
- Recusar a invenção de referências ou dados (política zero-fabricação).
- Explicar como acionar as skills do UFVAI.

Para retreinar:
```bash
cd finetune
python3 train.py --max-steps 16
```
O adaptador é salvo em `./adapter` e carregado automaticamente pelo `engine.py`
na próxima inicialização do servidor.

## Limitações técnicas

- **Hardware:** em CPU (float32), o modelo exige ~9 GB de RAM. Recomenda-se GPU
  para inferência em tempo real mais fluida.
- **Licença:** LFM Open License v1.0 (Liquid AI).
- **Integridade:** o assistente de voz **não substitui** a validação humana.
  Todas as respostas científicas devem ser conferidas na interface principal.
