"""Conversa ao vivo em linguagem natural — Gemini Live API (free tier).

Proxy WebSocket navegador ↔ Gemini Live ↔ UFVAI, com dois objetivos:

1. **Fluidez** — a sessão NÃO morre após o primeiro turno: o downstream
   permanece em loop, exceções de um lado não derrubam o outro e o
   microfone continua ativo entre as falas.
2. **Grill-me** — o assistente conduz uma entrevista curta para esclarecer
   a intenção do usuário e, ao final, propõe um PROMPT COMPLETO para ser
   colado no UFVAI (exibido em destaque na tela).

- Entrada do navegador: PCM 16-bit, 16 kHz, mono, little-endian.
- Saída para o navegador: PCM 16-bit, 24 kHz, mono, little-endian.
- Sem custo no free tier do Gemini Developer API (sujeito a rate limits;
  o conteúdo pode ser usado pelo Google para melhorar produtos).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os

from google import genai
from google.genai import types

from bridge import UFVAIBridge

logger = logging.getLogger("lfm3-voz.live")

DEFAULT_MODEL = os.environ.get("UFVAI_LIVE_MODEL", "gemini-3.8-live")

# ── Protocolo grill-me ───────────────────────────────────────────────
SYSTEM_INSTRUCTION = (
    "Você é o assistente de voz do UFVAI, agente de pesquisa científica da "
    "Universidade Federal de Viçosa. Sua missão nesta conversa é ENTREVISTAR "
    "o usuário para entender exatamente o que ele precisa e, ao final, "
    "escrever o MELHOR COMANDO possível para ele executar no UFVAI.\n\n"
    "USE SEMPRE A PALAVRA 'COMANDO' — nunca diga 'prompt'.\n\n"
    "REGRAS DA ENTREVISTA (modo grill-me):\n"
    "1. Fale SEMPRE em português brasileiro, com voz natural, cordial e "
    "frases curtas (é uma conversa falada, não um texto).\n"
    "2. Faça UMA pergunta por vez e espere a resposta. Nunca empilhe "
    "perguntas.\n"
    "3. Esclareça estes eixos, em no máximo 6 rodadas: (a) tema e objetivo "
    "do trabalho; (b) tipo de entrega desejada (artigo, revisão, TCC, "
    "planilha, slides, análise de dados etc.); (c) dados ou arquivos que a "
    "pessoa já tem; (d) recorte (período, local, população); (e) formato e "
    "normas exigidos (ABNT, APA, Vancouver).\n"
    "4. Se a resposta for vaga, peça UM detalhe concreto. Se já estiver "
    "clara, avance para o próximo eixo sem repetir.\n"
    "5. Quando tiver informação suficiente, chame a ferramenta apresentar_comando "
    "com o texto completo do comando (isso mostra o comando na tela de forma "
    "confiável). Depois pergunte em VOZ: 'Montei seu comando. Está aprovado? Quer "
    "que eu execute?'. NUNCA chame executar_comando antes de o usuário responder "
    "SIM. O sistema BLOQUEIA qualquer execução sem a confirmação do usuário.\n"
    "6. O COMANDO FINAL deve ser completo e autossuficiente: contexto, "
    "objetivo, recorte, dados disponíveis, formato de saída, exigências de "
    "integridade (não inventar dados nem referências, validar citações) e "
    "o passo a passo esperado. Escreva-o em português.\n"
    "7. Apresente o comando final EXATAMENTE entre as marcas "
    "<<<COMANDO_UFVAI>>> e <<<FIM_COMANDO>>>. Esse bloco aparece na tela.\n"
    "8. ANTES de finalizar, pergunte por VOZ qual modelo o usuário quer que "
    "execute o comando. Cite as opções que a ferramenta listar_modelos "
    "retornar (sugira os GRATUITOS primeiro, dizendo quais são grátis). "
    "Espere a resposta e registre o modelo escolhido. Se ele dissimular ou "
    "não entender, sugira o primeiro modelo gratuito da lista.\n"
    "9. SEMPRE pergunte por VOZ se o comando está aprovado. A resposta do "
    "usuário virá como texto do próprio microfone. Se ele CONFIRMAR (sim, "
    "pode executar, está bom, aprovado), chame a ferramenta executar_comando "
    "passando o comando completo e o modelo escolhido (id e providerID) — "
    "o sistema vai copiá-lo e executá-lo no UFVAI com ESSE modelo "
    "automaticamente; o usuário NÃO precisa copiar nada. Se ele NÃO "
    "concordar (quero mudar, não, ajuste tal parte), continue a entrevista: "
    "pergunte o que ajustar, revisite o eixo citado e apresente um NOVO "
    "bloco <<<COMANDO_UFVAI>>> ... <<<FIM_COMANDO>>> atualizado, tornando a "
    "pergunta de confirmação novamente por voz.\n"
    "10. NÃO invente dados, estatísticas nem referências. Se o usuário pedir "
    "para EXECUTAR a pesquisa antes de montar o comando, use a ferramenta "
    "consultar_ufvai.\n"
    "11. DEPOIS que a ferramenta executar_comando confirmar o envio, você DEVE "
    "dizer ao usuário em VOZ, como última fala da entrevista, exatamente esta "
    "mensagem (com suas próprias palavras, mas com o mesmo sentido): 'Pronto — "
    "seu comando já está em execução no UFVAI. É só aguardar e conferir os "
    "resultados na pasta PesquisAI do seu Google Drive.' Fale com cordialidade, "
    "sem termos técnicos, sem citar o conteúdo devolvido pela ferramenta e sem "
    "dizer que o trabalho já terminou. Depois disso, encerre a conversa.\n"
)

UFVAI_TOOL = {
    "name": "consultar_ufvai",
    "description": (
        "Consulta o agente de pesquisa científica UFVAI, que tem acesso a "
        "bases oficiais brasileiras (IBGE, DataSUS), busca de artigos e "
        "validação de referências. Use SOMENTE se o usuário pedir para "
        "executar a pesquisa agora, e não apenas para montar o comando."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pergunta": {
                "type": "string",
                "description": "Pedido completo do usuário, em português.",
            }
        },
        "required": ["pergunta"],
    },
}

APRESENTAR_COMANDO_TOOL = {
    "name": "apresentar_comando",
    "description": (
        "Mostra o comando final na tela do usuário de forma confiável. "
        "Chame SEMPRE que terminar de montar o comando, ANTES de pedir "
        "aprovação e antes de executar."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "comando": {
                "type": "string",
                "description": "O texto completo do comando final, em português.",
            }
        },
        "required": ["comando"],
    },
}

LISTAR_MODELOS_TOOL = {
    "name": "listar_modelos",
    "description": (
        "Lista os modelos disponíveis no UFVAI (gratuitos primeiro) para "
        "perguntar ao usuário qual deve executar o comando. Chame ANTES da "
        "pergunta sobre o modelo."
    ),
    "parameters": {"type": "object", "properties": {}},
}

EXECutar_COMANDO_TOOL = {
    "name": "executar_comando",
    "description": (
        "Executa o comando final aprovado pelo usuário: copia o texto para a "
        "área de transferência do navegador e envia para o motor UFVAI rodar "
        "em uma sessão, usando o modelo escolhido pelo usuário. Chame SOMENTE "
        "após o usuário confirmar por voz/fala que o comando está aprovado. "
        "Depois do retorno, fale a mensagem final de 'já em execução — confira "
        "os resultados na pasta PesquisAI do Google Drive' (regra 11)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "comando": {
                "type": "string",
                "description": "O comando completo entre <<<COMANDO_UFVAI>>> e <<<FIM_COMANDO>>>.",
            },
            "modelo": {
                "type": "object",
                "description": "Modelo escolhido pelo usuário (id e providerID).",
                "properties": {
                    "id": {"type": "string", "description": "ID do modelo."},
                    "providerID": {"type": "string", "description": "Provedor do modelo."},
                    "name": {"type": "string", "description": "Nome legível do modelo."},
                },
                "required": ["id", "providerID"],
            },
        },
        "required": ["comando", "modelo"],
    },
}


class LiveSession:
    """Uma sessão de conversa ao vivo navegador ↔ Gemini ↔ UFVAI."""

    def __init__(self, websocket, api_key: str, model: str | None = None):
        self.ws = websocket
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.bridge = UFVAIBridge()
        self.client = genai.Client(
            api_key=api_key, http_options={"api_version": "v1beta"}
        )
        self._closed = False
        # Controle de estado do fluxo: o comando só pode ser executado depois
        # de apresentado ao usuário e de ele ter confirmado por voz/fala.
        self.cmd_presented = False
        self.current_command = ""
        self.approval_asked = False
        self.user_approved = False

    async def run(self):
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(
                parts=[types.Part(text=SYSTEM_INSTRUCTION)]
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=os.environ.get("UFVAI_LIVE_VOICE", "Kore")
                    )
                )
            ),
            tools=[
                types.Tool(function_declarations=[
                    UFVAI_TOOL, LISTAR_MODELOS_TOOL,
                    APRESENTAR_COMANDO_TOOL, EXECutar_COMANDO_TOOL
                ])
            ],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        try:
            logger.info("Abrindo sessão Gemini Live (%s)...", self.model)
            async with self.client.aio.live.connect(
                model=self.model, config=config
            ) as session:
                logger.info("Sessão Gemini aberta.")
                await self._send_json({"type": "ready", "model": self.model})
                # return_exceptions=True: se um lado cair, o outro continua;
                # quem encerra de fato é o disconnect do navegador.
                results = await asyncio.gather(
                    self._upstream(session),
                    self._downstream(session),
                    return_exceptions=True,
                )
                for r in results:
                    if isinstance(r, Exception):
                        logger.warning("Task da sessão terminou com: %s", r)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Sessão Live encerrada com erro")
            await self._send_json({"type": "error", "message": str(exc)})
        finally:
            await self.close()

    async def _upstream(self, session):
        """Áudio/texto do navegador → Gemini (loop até o cliente desconectar)."""
        audio_frames = 0
        try:
            while not self._closed:
                frame = await self.ws.receive()
                if frame.get("type") == "websocket.disconnect":
                    logger.info("Cliente desconectou (upstream).")
                    break
                raw = frame.get("bytes")
                if raw is None:
                    raw = frame.get("text")
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    audio_frames += 1
                    if audio_frames % 100 == 1:
                        logger.info("Áudio do microfone fluindo (%d frames).", audio_frames)
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=raw, mime_type="audio/pcm;rate=16000"
                        )
                    )
                    continue
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                kind = msg.get("type")
                if kind == "text":
                    user_txt = msg.get("text", "")
                    logger.info("Texto do usuário: %s", user_txt[:80])
                    # Detecta confirmação por voz/fala do usuário.
                    confirmacoes = ("sim", "aprovado", "pode executar", "está bom",
                                    "concordo", "pode ir", "pode sim", "executa",
                                    "executar", "ok", "certo", "fechado", "vai")
                    baixo = user_txt.lower()
                    if any(p in baixo for p in confirmacoes):
                        self.user_approved = True
                        logger.info("Usuário APROVOU o comando por voz.")
                        await self._send_json({
                            "type": "user_approved", "message": "Aprovação recebida."
                        })
                    # send_client_content(turn_complete=True) força a resposta;
                    # send_realtime_input(text=...) ficaria aguardando VAD.
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=user_txt)],
                        ),
                        turn_complete=True,
                    )
                elif kind == "audio":
                    chunk = base64.b64decode(msg.get("data", ""))
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=chunk, mime_type="audio/pcm;rate=16000"
                        )
                    )
                elif kind == "close":
                    break
        except Exception as exc:  # noqa: BLE001
            logger.info("Upstream encerrado: %s", exc)

    async def _downstream(self, session):
        """Gemini → navegador, em loop contínuo de turnos.

        IMPORTANTE: o async generator de ``session.receive()`` TERMINA ao fim
        de cada turno. Por isso ele precisa ser recriado em um ``while`` —
        caso contrário a conversa morre depois da primeira resposta.
        """
        while not self._closed:
            try:
                async for response in session.receive():
                    if self._closed:
                        return
                    content = response.server_content
                    if content:
                        if content.model_turn:
                            for part in content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    await self._send_json(
                                        {
                                            "type": "audio",
                                            "data": base64.b64encode(
                                                part.inline_data.data
                                            ).decode("ascii"),
                                            "rate": 24000,
                                        }
                                    )
                        if content.input_transcription and content.input_transcription.text:
                            await self._send_json(
                                {
                                    "type": "transcript",
                                    "role": "user",
                                    "text": content.input_transcription.text,
                                }
                            )
                        if content.output_transcription and content.output_transcription.text:
                            txt = content.output_transcription.text
                            await self._send_json(
                                {
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": txt,
                                }
                            )
                            # Marca que o comando foi apresentado (mesmo que a
                            # marca tenha vido em pedaços ao longo do stream).
                            if "<<<COMANDO_UFVAI>>>" in txt:
                                self.cmd_presented = True
                                logger.info("Comando apresentado ao usuário na tela.")
                        if content.interrupted:
                            await self._send_json({"type": "interrupted"})
                        if content.turn_complete:
                            logger.info("Turno concluído — aguardando o próximo.")
                            await self._send_json({"type": "turn_complete"})

                    if response.tool_call:
                        await self._handle_tool_call(session, response.tool_call)
                # Fim do generator (turno encerrado): reabre o receive().
                logger.info("receive() encerrado; reabrindo para o próximo turno.")
            except Exception as exc:  # noqa: BLE001
                logger.info("Downstream encerrado: %s", exc)
                return

    async def _handle_tool_call(self, session, tool_call):
        responses = []
        for fc in tool_call.function_calls:
            args = fc.args or {}
            if fc.name == "apresentar_comando":
                comando = args.get("comando", "")
                self.current_command = comando
                self.cmd_presented = True
                logger.info("Comando apresentado via tool (tamanho %d).", len(comando))
                await self._send_json({
                    "type": "show_command", "command": comando,
                })
                responses.append(
                    types.FunctionResponse(
                        name=fc.name, id=fc.id,
                        response={"ok": True, "message": "Comando exibido na tela do usuário. Agora pergunte por voz se está aprovado."},
                    )
                )
            elif fc.name == "listar_modelos":
                loop = asyncio.get_running_loop()
                modelos = await loop.run_in_executor(None, self.bridge.list_models)
                await self._send_json({
                    "type": "models", "models": modelos,
                })
                resposta = {
                    "modelos": modelos,
                    "instrucao": "Pergunte por voz ao usuário qual modelo usar. "
                                 "Cite os gratuitos primeiro e diga quais são grátis.",
                }
                responses.append(
                    types.FunctionResponse(
                        name=fc.name, id=fc.id, response=resposta
                    )
                )
            elif fc.name == "executar_comando":
                comando = args.get("comando", "")
                modelo = args.get("modelo") or {}
                # BLOQUEIO: exige que o comando tenha sido apresentado e que o
                # usuário tenha confirmado por voz antes de executar.
                if not self.cmd_presented or not self.user_approved:
                    logger.warning(
                        "executar_comando bloqueado (apresentado=%s, aprovado=%s)",
                        self.cmd_presented, self.user_approved,
                    )
                    await self._send_json({
                        "type": "tool", "name": fc.name, "status": "blocked",
                        "message": "Aguardando sua aprovação: apresente o comando e pergunte ao usuário antes de executar.",
                    })
                    responses.append(
                        types.FunctionResponse(
                            name=fc.name, id=fc.id,
                            response={
                                "erro": "Execução BLOQUEADA. Você DEVE primeiro apresentar o comando entre <<<COMANDO_UFVAI>>> e <<<FIM_COMANDO>>> e perguntar por voz se está aprovado. Só chame esta ferramenta DEPOIS que o usuário responder SIM. Não chame novamente agora."
                            },
                        )
                    )
                    continue
                # 1) Manda o navegador copiar o comando automaticamente.
                await self._send_json({
                    "type": "execute_command",
                    "command": comando,
                    "model": modelo,
                })
                # 2) Envia para o motor UFVAI rodar com o modelo escolhido.
                nome_modelo = modelo.get("name") or modelo.get("id") or "padrão"
                await self._send_json({
                    "type": "tool", "name": fc.name, "status": "running",
                    "message": f"Executando no UFVAI com o modelo {nome_modelo}…",
                })
                # Feedback imediato e independente do modelo: a entrevista
                # termina aqui com a orientação de aguardar e conferir no Drive.
                await self._send_json({
                    "type": "final_status",
                    "message": (
                        "Pronto — seu comando já está em execução no UFVAI. "
                        "É só aguardar e conferir os resultados na pasta "
                        "PesquisAI do seu Google Drive."
                    ),
                })
                loop = asyncio.get_running_loop()
                resultado = await loop.run_in_executor(
                    None, self.bridge.ask, comando, None, modelo or None
                )
                await self._send_json({
                    "type": "command_result",
                    "result": resultado,
                })
                await self._send_json({
                    "type": "tool", "name": fc.name, "status": "done",
                    "message": "Comando enviado ao UFVAI. Confira os resultados na pasta PesquisAI do seu Google Drive.",
                })
                responses.append(
                    types.FunctionResponse(
                        name=fc.name, id=fc.id,
                        response={
                            "result": (
                                "Comando copiado e enviado ao UFVAI. "
                                "DIGA ao usuário em VOZ, agora, a mensagem final: "
                                "'Pronto — seu comando já está em execução no UFVAI. "
                                "É só aguardar e conferir os resultados na pasta "
                                "PesquisAI do seu Google Drive.' "
                                "Não leia este texto técnico em voz alta."
                            ),
                            "detalhe_interno": resultado[:400],
                        },
                    )
                )
            elif fc.name == "consultar_ufvai":
                pergunta = args.get("pergunta", "")
                await self._send_json(
                    {"type": "tool", "name": fc.name, "status": "running"}
                )
                loop = asyncio.get_running_loop()
                resultado = await loop.run_in_executor(
                    None, self.bridge.ask, pergunta
                )
                responses.append(
                    types.FunctionResponse(
                        name=fc.name, id=fc.id, response={"result": resultado}
                    )
                )
                await self._send_json(
                    {"type": "tool", "name": fc.name, "status": "done"}
                )
        if responses:
            await session.send_tool_response(function_responses=responses)

    async def _send_json(self, payload: dict):
        if self._closed:
            return
        try:
            await self.ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao enviar ao cliente: %s", exc)
            self._closed = True

    async def close(self):
        self._closed = True
        try:
            await self.ws.close()
        except Exception:  # noqa: BLE001
            pass
