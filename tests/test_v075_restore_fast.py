"""Restauracao rapida (ajuste 23/10/2026, sem bump).

Cobre o que fazia o "Restaurar sessão" demorar dezenas de segundos:

1. ``prepare_payload_for_restore`` decide ANTES do import:
   - cabe ................. ``none``  (importa direto)
   - ate 25% acima ......... ``compact``
   - muito acima ........... ``trimmed`` (apara e importa UMA vez)
2. Caches em processo (contexto do modelo, amostras de id, listagem de
   autosaves) — antes cada restore/abertura disparava processos e relia
   ~20 MB de JSON no Drive.
3. A compactacao manual espera no maximo 30 s (era 120 s) e consulta a
   cada 1 s (era 3 s).

    pytest -o addopts="" tests/test_v075_restore_fast.py -v
"""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import session_restore as sr  # noqa: E402

NATIVE_1 = "ses_" + "0123456789ab" + "ABCDEFGHIJKLMN"


def _payload(n_msgs: int = 10, chars: int = 3500, model: dict | None = None) -> dict:
    return {
        "info": {
            "id": NATIVE_1,
            "title": "Conversa longa",
            "model": model or {"providerID": "opencode",
                               "id": "deepseek-v4.1-flash-free"},
        },
        "messages": [
            {"id": f"msg_{i:026d}", "type": "user", "text": "x" * chars}
            for i in range(n_msgs)
        ],
    }


@pytest.fixture(autouse=True)
def _clean_caches():
    sr.clear_restore_caches()
    yield
    sr.clear_restore_caches()


# ── 1. plano antes do import ────────────────────────────────────────────
class TestPlanoAntesDoImport:
    def test_sessao_que_cabe_nao_muda(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 1_000_000)
        payload = _payload(5, 100)
        out, plan = sr.prepare_payload_for_restore(payload, "opencode")
        assert plan["action"] == "none"
        assert out is payload
        assert "messages_dropped" not in plan

    def test_pouco_acima_do_orcamento_compacta(self, monkeypatch):
        # 10 x 70k chars ≈ 200k tokens; orcamento 170k (85% de 200k)
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 200_000)
        payload = _payload(10, 70_000)
        out, plan = sr.prepare_payload_for_restore(payload, "opencode")
        assert plan["action"] == "compact"
        assert out is payload            # importa inteiro e compacta depois
        assert plan["tokens_before"] > plan["budget"]

    def test_muito_acima_do_orcamento_apara_antes(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 200_000)
        payload = _payload(20, 200_000)  # ~1,1 milhao de tokens
        out, plan = sr.prepare_payload_for_restore(payload, "opencode")
        assert plan["action"] == "trimmed"
        assert plan["messages_dropped"] > 0
        assert plan["tokens_after"] <= plan["budget"] * 1.02
        assert len(out["messages"]) < len(payload["messages"])
        # o info (id/modelo/titulo) e' preservado
        assert out["info"]["id"] == NATIVE_1
        # a ultima mensagem (contexto imediato) fica
        assert out["messages"][-1] == payload["messages"][-1]

    def test_razao_de_compactacao_e_configuravel(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 200_000)
        payload = _payload(10, 70_000)          # ~200k tokens
        _, plan = sr.prepare_payload_for_restore(payload, "opencode", ratio=10.0)
        assert plan["action"] == "compact"

    def test_sem_modelo_usa_o_teto_gratuito(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 0)
        plan = sr.plan_restore(_payload(10, 100), "opencode")
        assert plan["budget"] == sr.FREE_TIER_SAFE_TOKENS
        assert plan["action"] == "none"


# ── 2. caches ───────────────────────────────────────────────────────────
class TestCaches:
    def test_contexto_do_modelo_vem_do_cache(self, monkeypatch):
        calls = {"n": 0}
        payload_models = {
            "data": [
                {"providerID": "opencode", "id": "m1", "limit": {"context": 200_000}},
            ]
        }

        def fake_run(cmd, env=None, timeout=60):
            calls["n"] += 1

            class R:
                returncode = 0
                stdout = json.dumps(payload_models)
                stderr = ""

            return R()

        monkeypatch.setattr(sr, "_run", fake_run)
        model = {"providerID": "opencode", "id": "m1"}
        assert sr.model_context_limit("opencode", model) == 200_000
        assert sr.model_context_limit("opencode", model) == 200_000
        assert calls["n"] == 1

    def test_amostras_de_id_vem_do_cache(self, monkeypatch):
        calls = {"n": 0}

        def fake_list(binary, env=None):
            calls["n"] += 1
            return [{"id": NATIVE_1}]

        monkeypatch.setattr(sr, "list_sessions", fake_list)
        assert sr.native_id_samples_cached("opencode") == [NATIVE_1]
        assert sr.native_id_samples_cached("opencode") == [NATIVE_1]
        assert calls["n"] == 1
        # limpar o cache forca nova consulta
        sr.clear_restore_caches()
        sr.native_id_samples_cached("opencode")
        assert calls["n"] == 2

    def test_listagem_de_autosaves_vem_do_cache(self, monkeypatch, tmp_path):
        auto = tmp_path / "autosave"
        auto.mkdir()
        for slot in range(1, 4):
            (auto / f"autosave_{slot}.json").write_text(json.dumps({
                "info": {"id": NATIVE_1, "title": "T"},
                "messages": [{"id": "msg_1", "type": "user", "text": "oi"}],
            }), encoding="utf-8")
        loads = {"n": 0}
        real_load = json.load

        def counting_load(*a, **k):
            loads["n"] += 1
            return real_load(*a, **k)

        monkeypatch.setattr(sr.json, "load", counting_load)
        first = sr.list_autosaves(str(auto))
        second = sr.list_autosaves(str(auto))
        assert len(first) == 3 and len(second) == 3
        assert loads["n"] == 3          # 3 arquivos lidos UMA vez
        # devolve copias: alterar o resultado nao corrompe o cache
        second[0]["title"] = "mutado"
        assert sr.list_autosaves(str(auto))[0]["title"] == "T"

    def test_so_o_arquivo_que_mudou_e_reparseado(self, monkeypatch, tmp_path):
        """Um slot pequeno muda a cada minuto; os grandes nao sao relidos.

        Antes, a assinatura da PASTA invalidava tudo e a listagem reparseava
        os 21 MB do Drive — era o resto do atraso da pergunta de retomada.
        """
        auto = tmp_path / "autosave"
        auto.mkdir()
        big = "x" * 200_000
        (auto / "autosave_1.json").write_text(json.dumps({
            "info": {"id": NATIVE_1, "title": "grande"},
            "messages": [{"id": "msg_1", "type": "user", "text": big}],
        }), encoding="utf-8")
        (auto / "autosave_3.json").write_text(json.dumps({
            "info": {"id": NATIVE_1, "title": "pequeno"},
            "messages": [{"id": "msg_2", "type": "user", "text": "oi"}],
        }), encoding="utf-8")

        real_load = json.load
        seen: list[str] = []

        def counting_load(fh, *a, **k):
            seen.append(getattr(fh, "name", "?"))
            return real_load(fh, *a, **k)

        monkeypatch.setattr(sr.json, "load", counting_load)
        assert len(sr.list_autosaves(str(auto))) == 2
        assert len(seen) == 2

        # o slot pequeno e' reescrito (rotacao normal do autosave)
        time.sleep(0.01)
        (auto / "autosave_3.json").write_text(json.dumps({
            "info": {"id": NATIVE_1, "title": "pequeno 2"},
            "messages": [{"id": "msg_3", "type": "user", "text": "oi"}],
        }), encoding="utf-8")

        seen.clear()
        items = sr.list_autosaves(str(auto))
        assert len(items) == 2
        assert len(seen) == 1, seen                      # so o slot 3
        assert seen[0].endswith("autosave_3.json")
        assert items[0]["title"] == "pequeno 2"          # valor novo, nao cache


# ── 3. tempos da compactacao ────────────────────────────────────────────
class TestCompactacaoRapida:
    def test_limites(self):
        assert sr.COMPACT_MAX_RATIO == pytest.approx(1.25)
        assert sr.COMPACT_WAIT_S <= 30
        assert sr.COMPACT_POLL_S <= 1.0

    def test_espera_curta_e_consulta_frequente(self, monkeypatch):
        """`compact_session` desiste em <= 30 s consultando a cada 1 s."""
        sleeps: list[float] = []

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        monkeypatch.setattr(sr, "_run", lambda *a, **k: R())
        monkeypatch.setattr(sr, "_compaction_status", lambda *a, **k: "running")
        monkeypatch.setattr(sr.time, "sleep", lambda s: sleeps.append(s))
        # relogio falso: cada consulta "gasta" 1 s
        clock = {"t": 0.0}
        monkeypatch.setattr(sr.time, "time", lambda: clock["t"])

        def sleeper(s):
            sleeps.append(s)
            clock["t"] += s

        monkeypatch.setattr(sr.time, "sleep", sleeper)
        assert sr.compact_session("opencode", NATIVE_1, wait_s=5, interval=1.0) is False
        assert sleeps and max(sleeps) <= 1.0
        assert sum(sleeps) <= 6


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-o", "addopts="]))
