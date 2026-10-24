"""Testes de sessoes: listagem, exportacao e restauracao (pesquisai/session_restore.py).

Cobre as correcoes da v0.6.25 (diagnostico de 21/10/2026 no motor v2.1.2):

- `detect_format` distingue o esquema legado v1 (motor 1.15-1.18) do v2;
- `convert_v1_to_v2` converte `{info, parts}` -> mensagens planas, `tokens` sem a
  chave extra `total` (que sozinha fazia o import devolver HTTP 400) e
  `info` com `location` no lugar de `directory`/`path`/`slug`/`summary`;
- `sanitize_v2` remove o que o import nao aceita (`outcome`, tipos de mensagem
  como `agent-switched`) e RENOVA os ids — a colisao de ids com a base era a
  causa do HTTP 500;
- `prepare_import_payload` le um arquivo truncado e devolve erro claro;
- `write_backup_atomic` grava num diretorio temporario, valida e so entao
  renomeia (o nome definitivo nunca fica com arquivo corrompido).
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "pesquisai" / "session_restore.py"
_spec = importlib.util.spec_from_file_location("ufvai_session_restore", _MODULE)
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)


# ── fixtures ─────────────────────────────────────────────────────────────

V1_PAYLOAD = {
    "info": {
        "id": "ses_legado123",
        "title": "Sessao antiga",
        "directory": "/content/drive/My Drive/PesquisAI",
        "path": "/content/drive/My Drive/PesquisAI",
        "slug": "sessao-antiga",
        "summary": "resumo",
        "version": "1.17.18",
        "projectID": "global",
        "agent": "PesquisAI",
        "model": {"id": "qwen3.7-plus", "providerID": "opencode-go"},
        "cost": 0,
        "tokens": {
            "total": 41010, "input": 40839, "output": 53,
            "reasoning": 118, "cache": {"read": 0, "write": 0},
        },
        "time": {"created": 1783693730036, "updated": 1783693730747},
    },
    "messages": [
        {
            "info": {"id": "msg_user1", "role": "user", "time": {"created": 1783693730036}},
            "parts": [
                {"type": "text", "id": "prt_1", "text": "Ola! (Dica: responda em portugues.)"}
            ],
        },
        {
            "info": {"id": "msg_asst1", "role": "assistant", "time": {"created": 1783693730050}},
            "parts": [
                {"type": "reasoning", "text": "pensando...", "time": {"created": 1783693730051}},
                {
                    "type": "tool", "callID": "call_00_abc", "tool": "shell",
                    "state": {
                        "status": "completed",
                        "input": {"command": "ls"},
                        "output": "arquivo.txt",
                        "title": "ls",
                        "metadata": {"count": 1, "truncated": False},
                        "time": {"start": 1, "end": 2},
                    },
                },
                {
                    "type": "step-finish", "reason": "tool-calls", "cost": 0,
                    "tokens": {"total": 10, "input": 8, "output": 2, "reasoning": 0,
                               "cache": {"read": 0, "write": 0}},
                },
            ],
        },
    ],
}

V2_PAYLOAD = {
    "info": {
        "id": "ses_atual12345",
        "projectID": "abc123",
        "agent": "UFVAI",
        "title": "Sessao nova",
        "outcome": "interrupted",
        "cost": 0.1,
        "tokens": {"input": 10, "output": 5, "reasoning": 1, "cache": {"read": 0, "write": 0}},
        "time": {"created": 1792578899692, "updated": 1792578929003},
        "location": {"directory": "/content/drive/My Drive/PesquisAI"},
    },
    "messages": [
        {"id": "msg_u1", "time": {"created": 1}, "text": "oi", "files": [], "agents": [],
         "type": "user"},
        {"id": "msg_a1", "time": {"created": 2}, "type": "assistant", "agent": "UFVAI",
         "content": [{"type": "text", "text": "ola"}]},
        {"id": "msg_x1", "time": {"created": 3}, "type": "agent-switched", "agent": "UFVAI"},
    ],
}


# ── deteccao de formato ──────────────────────────────────────────────────

def test_detect_format_v1_e_v2():
    assert sr.detect_format(V1_PAYLOAD) == "v1"
    assert sr.detect_format(V2_PAYLOAD) == "v2"
    assert sr.detect_format({"info": {}, "messages": []}) == "v2"
    assert sr.detect_format("lixo") == "desconhecido"


def test_is_legacy_v1():
    assert sr.detect_format(V1_PAYLOAD) == "v1"
    assert sr.detect_format(V2_PAYLOAD) != "v1"


# ── conversao v1 -> v2 ───────────────────────────────────────────────────

def test_convert_v1_mensagens_planas():
    out = sr.convert_v1_to_v2(V1_PAYLOAD, "/tmp")
    tipos = [m["type"] for m in out["messages"]]
    assert tipos == ["user", "assistant"]
    assert out["messages"][0]["text"].startswith("Ola!")
    assert out["messages"][0]["files"] == [] and out["messages"][0]["agents"] == []


def test_convert_v1_tokens_sem_total():
    """A chave `total` do v1 nao existe no esquema v2 — sozinha causa HTTP 400."""
    out = sr.convert_v1_to_v2(V1_PAYLOAD, "/tmp")
    assert "total" not in out["info"]["tokens"]
    assert "total" not in out["messages"][1]["tokens"]
    assert out["messages"][1]["tokens"]["input"] == 8


def test_convert_v1_info_com_location():
    out = sr.convert_v1_to_v2(V1_PAYLOAD, "/tmp")
    info = out["info"]
    assert info["location"] == {"directory": "/content/drive/My Drive/PesquisAI"}
    for chave in ("slug", "summary", "version", "directory", "path"):
        assert chave not in info


def test_convert_v1_ferramenta_vira_texto():
    """No v1 a ferramenta nao e aceita pelo import: vira texto, sem perder a saida."""
    out = sr.convert_v1_to_v2(V1_PAYLOAD, "/tmp")
    content = out["messages"][1]["content"]
    tipos = [c["type"] for c in content]
    assert "tool" not in tipos
    texto = " ".join(c.get("text", "") for c in content)
    assert "shell" in texto and "arquivo.txt" in texto


def test_convert_v1_ferramenta_preservada_quando_pedido():
    out = sr.convert_v1_to_v2(V1_PAYLOAD, "/tmp", tools_as_text=False)
    content = out["messages"][1]["content"]
    assert any(c["type"] == "tool" for c in content)


def test_convert_v1_step_finish_vira_campos_da_mensagem():
    out = sr.convert_v1_to_v2(V1_PAYLOAD, "/tmp")
    msg = out["messages"][1]
    assert msg["finish"] == "tool-calls"
    assert msg["rawFinish"] == "tool_calls"
    assert msg["cost"] == 0


# ── saneamento ───────────────────────────────────────────────────────────

def test_sanitize_remove_outcome_e_tipos_nao_suportados():
    out = sr.sanitize_v2(V2_PAYLOAD, "proj", "/tmp")
    assert "outcome" not in out["info"]
    assert [m["type"] for m in out["messages"]] == ["user", "assistant"]


def test_sanitize_renova_ids():
    """Sem ids novos o import colide com a base e devolve HTTP 500."""
    out = sr.sanitize_v2(V2_PAYLOAD, "proj", "/tmp")
    assert out["info"]["id"] != V2_PAYLOAD["info"]["id"]
    assert out["info"]["id"].startswith("ses_")
    for original, novo in zip(V2_PAYLOAD["messages"], out["messages"]):
        if "id" in original:
            assert novo["id"] != original["id"]
            assert novo["id"].startswith("msg_")


def test_sanitize_preserva_conteudo():
    out = sr.sanitize_v2(V2_PAYLOAD, "proj", "/tmp")
    assert out["messages"][0]["text"] == "oi"
    assert out["messages"][1]["content"][0]["text"] == "ola"


# ── payload de import ────────────────────────────────────────────────────

def test_prepare_import_de_arquivo_v1(tmp_path):
    arquivo = tmp_path / "backup.json"
    arquivo.write_text(json.dumps(V1_PAYLOAD), encoding="utf-8")
    payload, fmt = sr.prepare_import_payload(str(arquivo), "proj", "/tmp")
    assert fmt == "v1"
    assert payload["info"]["id"] != "ses_legado123"
    assert len(payload["messages"]) == 2


def test_prepare_import_de_arquivo_v2(tmp_path):
    arquivo = tmp_path / "backup.json"
    arquivo.write_text(json.dumps(V2_PAYLOAD), encoding="utf-8")
    payload, fmt = sr.prepare_import_payload(str(arquivo), "proj", "/tmp")
    assert fmt == "v2"
    assert "outcome" not in payload["info"]


def test_prepare_import_de_arquivo_truncado(tmp_path):
    arquivo = tmp_path / "backup.json"
    arquivo.write_text('{"info": {"id": "ses_x"}, "messages": [', encoding="utf-8")
    with pytest.raises(sr.SessionError) as exc:
        sr.prepare_import_payload(str(arquivo), "proj", "/tmp")
    assert "corrompido" in str(exc.value).lower()


def test_prepare_import_de_arquivo_inexistente(tmp_path):
    with pytest.raises(sr.SessionError):
        sr.prepare_import_payload(str(tmp_path / "nao_existe.json"), "proj", "/tmp")


# ── gravacao atomica ─────────────────────────────────────────────────────

def test_write_backup_atomic_grava_e_valida(tmp_path):
    origem = tmp_path / "origem.json"
    origem.write_text(json.dumps(V2_PAYLOAD), encoding="utf-8")
    destino = tmp_path / "backup_ses_x.json"
    info = sr.write_backup_atomic(str(origemem := origem), str(destino))
    assert info["ok"] is True
    assert destino.exists()
    with open(destino, encoding="utf-8") as fh:
        json.load(fh)


def test_write_backup_atomic_rejeita_json_invalido(tmp_path):
    origem = tmp_path / "origem.json"
    origem.write_text('{"info": {}, "messages": [', encoding="utf-8")
    destino = tmp_path / "backup_ses_y.json"
    with pytest.raises(sr.SessionError):
        sr.write_backup_atomic(str(origem), str(destino))
    assert not destino.exists()


def test_write_backup_atomic_nao_sobrescreve_arquivo_ruim(tmp_path):
    """Se a gravacao falhar, o backup anterior (com nome final) permanece."""
    destino = tmp_path / "backup_ses_z.json"
    destino.write_text("conteudo anterior", encoding="utf-8")
    origem = tmp_path / "origem.json"
    origem.write_text("nao e json", encoding="utf-8")
    with pytest.raises(sr.SessionError):
        sr.write_backup_atomic(str(origem), str(destino))
    assert destino.read_text(encoding="utf-8") == "conteudo anterior"
    # nenhum temporario orfao
    assert not [p for p in os.listdir(tmp_path) if p.startswith(".tmp-backup-")]


# ── validacao de export ──────────────────────────────────────────────────

def test_validate_export_aceita_payload_valido():
    data, fmt = sr.validate_export(json.dumps(V2_PAYLOAD))
    assert fmt == "v2"
    assert len(data["messages"]) == 3


def test_validate_export_rejeita_json_truncado():
    with pytest.raises(sr.SessionError):
        sr.validate_export('{"info": {"id": "ses_x"}, "messages": [')


def test_validate_export_rejeita_sem_mensagens():
    with pytest.raises(sr.SessionError):
        sr.validate_export(json.dumps({"info": {"id": "ses_x"}, "messages": []}))


def test_validate_export_rejeita_vazio():
    with pytest.raises(sr.SessionError):
        sr.validate_export("")
