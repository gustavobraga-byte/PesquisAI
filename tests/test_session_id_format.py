# -*- coding: utf-8 -*-
"""Regressão 23/10/2026 — formato dos ids da sessão restaurada.

Contexto (issue #49433 do OpenCode): o gateway do *free tier* valida o
cabeçalho ``x-opencode-session``. O valor precisa ser
``ses_`` + 12 hex (tempo) + 14 base62. Qualquer outro formato recebe
``403 FreeTierError`` — "OpenCode's free tier can only be used from
within OpenCode".

A retomada do UFVAI importava a sessão com ``ses_`` + 16 hex
(``secrets.token_hex(8)``), então **toda sessão restaurada** quebrava com
modelos gratuitos, enquanto uma sessão NOVA (id criado pelo motor)
funcionava. Estes testes travam o contrato:

1. ``id_shape`` infere o formato dos ids vivos e ignora a minoria atípica
   (os ``ses_`` + 16 hex legados — copiá-los perpetuaria o bug).
2. ``mint_id_like`` gera no formato inferido, preservando o componente de
   tempo da amostra mais recente.
3. ``sanitize_v2``/``prepare_import_payload`` renovam TODOS os ids no
   formato nativo.
4. Sem amostras, cai no padrão oficial (12 hex + 14 base62) — nunca em
   16 hex.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import session_restore as sr  # noqa: E402

HEX12 = re.compile(r"^[0-9a-f]{12}$")
B62_14 = re.compile(r"^[A-Za-z0-9]{14}$")


def _tail(value: str, prefix: str) -> str:
    assert value.startswith(prefix)
    return value[len(prefix):]


# Ids no formato NATIVO do motor (12 hex + 14 base62) — do mais novo ao
# mais antigo, como `list_sessions()` devolve.
NATIVE = [
    "ses_e99e78d15ffeofnzARKrxit83W",
    "ses_e99e9414effe5ngxndp5Fqofvy",
    "ses_e99e9b259ffe4B4ZnEtnqbuzR0",
]
# Id legado gerado pela retomada antiga (16 hex) — NÃO pode ser copiado.
LEGACY_16HEX = "ses_efb5b9a799a44b91"


def test_id_shape_majoritario_ignora_legado():
    """3 nativos + 1 legado -> formato de 26 (12 hex + 14 base62)."""
    length, pattern, sample = sr.id_shape(NATIVE + [LEGACY_16HEX], "ses_")
    assert length == 26
    assert pattern == "h" * 12 + "b" * 14
    assert sample == _tail(NATIVE[0], "ses_")


def test_id_shape_sem_amostras():
    assert sr.id_shape([], "ses_") is None
    assert sr.id_shape([LEGACY_16HEX], "ses_")[0] == 16  # só há legado


def test_mint_formato_nativo_e_prefixo_de_tempo():
    novo = sr.mint_id_like("ses_", NATIVE)
    tail = _tail(novo, "ses_")
    assert len(tail) == 26
    assert HEX12.match(tail[:12]), "os 12 primeiros precisam ser hex"
    assert B62_14.match(tail[12:]), "os 14 últimos precisam ser base62"
    # componente de tempo: reaproveita o da amostra mais recente
    assert tail[:12] == NATIVE[0][4:16]
    # sufixo aleatório de verdade
    assert tail[12:] != NATIVE[0][16:]


def test_mint_sem_amostras_usa_padrao_oficial():
    ids = {sr.mint_id_like("ses_") for _ in range(20)}
    assert len(ids) == 20  # unicidade
    for value in ids:
        tail = _tail(value, "ses_")
        assert len(tail) == 26
        assert HEX12.match(tail[:12]) and B62_14.match(tail[12:])


def test_mint_respeita_taken():
    taken = {sr.mint_id_like("ses_", NATIVE) for _ in range(3)}
    novo = sr.mint_id_like("ses_", NATIVE, taken=taken)
    assert novo not in taken


def _payload():
    """Payload v2 mínimo (2 mensagens, 1 usuário + 1 assistente)."""
    return {
        "info": {
            "id": LEGACY_16HEX,
            "title": "Teste",
            "time": {"created": 1792629132595, "updated": 1792629132595},
            "projectID": "proj",
            "agent": "UFVAI",
            "model": {"id": "deepseek-v4.1-flash-free", "providerID": "opencode"},
            "location": {"directory": "/root"},
            "outcome": "ok",  # chave que o import rejeita -> deve sumir
        },
        "messages": [
            {"type": "user", "id": "msg_1", "text": "oi"},
            {"type": "assistant", "id": "msg_2", "content": "olá"},
            {"type": "synthetic", "id": "msg_3", "content": "x"},  # filtrada
        ],
    }


def test_sanitize_v2_renova_ids_no_formato_nativo():
    out = sr.sanitize_v2(_payload(), id_samples=NATIVE)
    sid = out["info"]["id"]
    tail = _tail(sid, "ses_")
    assert len(tail) == 26 and HEX12.match(tail[:12]) and B62_14.match(tail[12:])
    assert sid != LEGACY_16HEX
    assert "outcome" not in out["info"]

    assert len(out["messages"]) == 2  # 'synthetic' removida
    for msg in out["messages"]:
        mtail = _tail(msg["id"], "msg_")
        assert len(mtail) == 26, msg["id"]
        assert HEX12.match(mtail[:12]) and B62_14.match(mtail[12:]), msg["id"]
        assert msg["id"] not in ("msg_1", "msg_2")
    # o componente de tempo da mensagem acompanha o da sessão
    assert out["messages"][0]["id"][4:16] == sid[4:16]


def test_prepare_import_payload_aceita_amostras(tmp_path):
    path = tmp_path / "backup.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")
    payload, fmt = sr.prepare_import_payload(str(path), id_samples=NATIVE)
    assert fmt == "v2"
    assert len(_tail(payload["info"]["id"], "ses_")) == 26


def test_prepare_import_payload_sem_amostras_nao_usa_16hex(tmp_path):
    """Sem amostras, o padrão é o oficial — nunca o legado de 16 hex."""
    path = tmp_path / "backup.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")
    payload, _ = sr.prepare_import_payload(str(path))
    assert len(_tail(payload["info"]["id"], "ses_")) == 26


def test_ids_unicos_entre_duas_restauracoes():
    a = sr.sanitize_v2(_payload(), id_samples=NATIVE)["info"]["id"]
    b = sr.sanitize_v2(_payload(), id_samples=NATIVE)["info"]["id"]
    assert a != b
