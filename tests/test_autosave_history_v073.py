# -*- coding: utf-8 -*-
"""Testes da v0.7.3 — autosave: fallback de 3 interacoes + chave estavel.

Cobre:
  * `content_digest` estavel quando o motor RE-GERA o id da sessao
    (mesma conversa) e diferente quando o conteudo muda;
  * `preserve_autosave_history` (copia do ultimo backup da interacao que
    terminou, no maximo 3, sem duplicar a mesma interacao);
  * `list_autosaves` incluindo as copias preservadas (`history: True`);
  * `save_autosave` preservando a conversa anterior ao mudar de interacao;
  * resolucao da sessao ativa no backend (ttyd > mais recente).

Executar:  python3 -m pytest tests/test_autosave_history_v073.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

import pytest

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pesquisai")


def _load(name: str):
    path = os.path.join(PKG, name)
    spec = importlib.util.spec_from_file_location("ufvai_test_" + name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_pkg(name: str):
    """Importa como modulo do pacote (`launch_app.py` usa import relativo)."""
    parent = os.path.dirname(PKG)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import importlib
    return importlib.import_module("pesquisai." + name.replace(".py", ""))


sr = _load("session_restore.py")


def _export(session_id: str, created: int, msgs: int = 3, title: str = "Greeting"):
    return {
        "info": {
            "id": session_id,
            "title": title,
            "time": {"created": created, "updated": created + 1000},
        },
        "messages": [{"id": f"m{i}", "role": "user", "parts": [{"type": "text", "text": f"msg {i}"}]}
                     for i in range(msgs)],
    }


def _write(path: str, payload: dict, mtime: float | None = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


# ─────────────────────────────────────────────────────────────────────────
# 1. digest com chave estavel
# ─────────────────────────────────────────────────────────────────────────
def test_digest_estavel_quando_o_id_da_sessao_muda(tmp_path):
    """O motor re-gera o id a cada reinicio: a mesma conversa nao pode
    virar "versao distinta" (era o que duplicava os slots)."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(str(a), _export("ses_aaa", 1700000000000))
    _write(str(b), _export("ses_bbb", 1700000000000))   # MESMA conversa, id novo
    assert sr.content_digest(str(a)) == sr.content_digest(str(b))


def test_digest_muda_quando_o_conteudo_muda(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(str(a), _export("ses_aaa", 1700000000000, msgs=3))
    _write(str(b), _export("ses_aaa", 1700000000000, msgs=9))
    assert sr.content_digest(str(a)) != sr.content_digest(str(b))


def test_digest_muda_entre_conversas_diferentes(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(str(a), _export("ses_aaa", 1700000000000))
    _write(str(b), _export("ses_bbb", 1700000100000))   # conversa outra
    assert sr.content_digest(str(a)) != sr.content_digest(str(b))


# ─────────────────────────────────────────────────────────────────────────
# 2. preservacao do historico
# ─────────────────────────────────────────────────────────────────────────
def test_slots_de_historico_sao_4_a_6(tmp_path):
    paths = sr.autosave_history_paths(str(tmp_path))
    assert [os.path.basename(p) for p in paths] == [
        "autosave_4.json", "autosave_5.json", "autosave_6.json"]


def test_preserve_copia_o_ultimo_backup_da_interacao_anterior(tmp_path):
    d = str(tmp_path)
    slot1 = sr.autosave_paths(d)[0]
    _write(slot1, _export("ses_aaa", 1700000000000), mtime=time.time() - 600)
    out = sr.preserve_autosave_history(d)
    assert out is not None
    hist = sr.autosave_history_paths(d)[0]
    assert os.path.exists(hist)
    assert sr.logical_session_key(hist) == "1700000000000"
    # o mtime original e' preservado (o calendario mostra a data real)
    assert abs(os.path.getmtime(hist) - (time.time() - 600)) < 5


def test_preserve_nao_duplica_a_mesma_interacao(tmp_path):
    d = str(tmp_path)
    slot1 = sr.autosave_paths(d)[0]
    _write(slot1, _export("ses_aaa", 1700000000000))
    assert sr.preserve_autosave_history(d) is not None
    assert sr.preserve_autosave_history(d) is None   # ja preservada


def test_historico_guarda_no_maximo_3_interacoes(tmp_path):
    d = str(tmp_path)
    slot1 = sr.autosave_paths(d)[0]
    for i in range(6):
        _write(slot1, _export(f"ses_{i}", 1700000000000 + i * 1000))
        sr.preserve_autosave_history(d)
    history = sr.autosave_history_paths(d)
    existing = [p for p in history if os.path.exists(p)]
    assert len(existing) == sr.AUTOSAVE_HISTORY_SLOTS == 3


def test_list_autosaves_inclui_as_copias_preservadas(tmp_path):
    d = str(tmp_path)
    slot1 = sr.autosave_paths(d)[0]
    _write(slot1, _export("ses_aaa", 1700000000000))
    sr.preserve_autosave_history(d)
    items = sr.list_autosaves(d)
    assert len(items) == 2
    assert any(item["history"] for item in items)
    assert any(not item["history"] for item in items)
    # o nome continua no formato aceito pelo POST /api/restore
    for item in items:
        assert item["file"].startswith("autosave/autosave_")
        assert item["file"].split("/")[-1].replace("autosave_", "").replace(".json", "").isdigit()


# ─────────────────────────────────────────────────────────────────────────
# 3. save_autosave preserva a conversa anterior
# ─────────────────────────────────────────────────────────────────────────
def test_save_autosave_preserva_a_conversa_anterior(tmp_path, monkeypatch):
    d = str(tmp_path)
    slot1 = sr.autosave_paths(d)[0]
    _write(slot1, _export("ses_antiga", 1700000000000), mtime=time.time() - 900)

    def fake_export(binary, session_id, out_path, env=None, timeout=180):
        payload = _export("ses_nova", 1700009999999)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return payload, "v2"

    monkeypatch.setattr(sr, "export_session_to_file", fake_export)
    meta = sr.save_autosave("opencode", "ses_nova", d)
    assert meta["ok"] is True
    # a conversa anterior foi preservada no historico
    hist = [p for p in sr.autosave_history_paths(d) if os.path.exists(p)]
    assert len(hist) == 1
    assert sr.logical_session_key(hist[0]) == "1700000000000"
    # e o slot 1 passou a ser a conversa nova
    assert sr.logical_session_key(slot1) == "1700009999999"


def test_save_autosave_nao_grava_copia_identica(tmp_path, monkeypatch):
    """Mesmo conteudo, id re-gerado: nao grava de novo (v0.7.1 mantido)."""
    d = str(tmp_path)
    slot1 = sr.autosave_paths(d)[0]
    payload = _export("ses_aaa", 1700000000000)

    def fake_export(binary, session_id, out_path, env=None, timeout=180):
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return payload, "v2"

    monkeypatch.setattr(sr, "export_session_to_file", fake_export)
    sr.save_autosave("opencode", "ses_aaa", d)
    first = os.path.getsize(slot1)
    meta = sr.save_autosave("opencode", "ses_aaa", d)
    assert meta.get("skipped") is True
    assert os.path.getsize(slot1) == first


# ─────────────────────────────────────────────────────────────────────────
# 4. resolucao da sessao ativa no backend
# ─────────────────────────────────────────────────────────────────────────
def test_backend_tem_resolucao_de_sessao_ativa():
    with open(os.path.join(PKG, "launch_app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "def _ttyd_session_id()" in src
    assert "def _active_session_id(" in src
    # o POST (gravacao) e' a 2a ocorrencia do caminho
    branches = src.split('if p == "/api/autosave"')
    assert len(branches) >= 3, "esperado GET + POST do /api/autosave"
    assert "_ttyd_session_id()" in branches[2][:4000]


def test_active_session_id_usa_o_updated_mais_recente():
    la = _load_pkg("launch_app.py")
    sessions = [
        {"id": "ses_antigo", "time": {"updated": 100}},
        {"id": "ses_novo", "time": {"updated": 900}},
        {"id": "ses_meio", "time": {"updated": 500}},
    ]
    assert la._active_session_id(sessions) == "ses_novo"


def test_ttyd_session_id_nao_quebra():
    la = _load_pkg("launch_app.py")
    value = la._ttyd_session_id()
    assert isinstance(value, str)
    assert value == "" or value.startswith("ses_")
