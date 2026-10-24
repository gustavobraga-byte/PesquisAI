"""
tests/test_restore_free_tier.py — v0.7.3 (23/10/2026, sem bump)

Regressao do erro "OpenCode's free tier can only be used from within
OpenCode" ao restaurar o autosave.

CAUSA (reproduzida em 23/10/2026):
  uma sessao importada cujo id ficou no formato **legado**
  (``ses_`` + 16 hex) e recusada pelo gateway do free tier do OpenCode
  Zen em QUALQUER modelo free — a mensagem do usuario aparecia no
  terminal restaurado. Com o id **nativo** (``ses_`` + 12 hex + 14
  base62, 26 caracteres) a mesma sessao responde normalmente.

Estes testes nao tocam a rede: cobrem a geracao dos ids, o filtro dos
ids nativos e o ajuste ao contexto do modelo.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import session_restore as sr  # noqa: E402


# Ids reais do motor (formato nativo) e ids legados da retomada antiga.
NATIVE_1 = "ses_e99ced15dffe19WAaKxpEx3jcY"
NATIVE_2 = "ses_e99d67627ffeBkUqN270oQSixQ"
LEGACY_1 = "ses_566e0516e9af4acd"
LEGACY_2 = "ses_efb5b9a799a44b91"


class TestNativeIdShape:
    def test_reconhece_id_nativo(self):
        assert sr.is_native_id(NATIVE_1)
        assert sr.is_native_id(NATIVE_2)

    def test_reconhece_id_legado_como_nao_nativo(self):
        assert not sr.is_native_id(LEGACY_1)
        assert not sr.is_native_id(LEGACY_2)
        assert not sr.is_native_id("")

    def test_filtra_somente_nativos(self):
        ids = [NATIVE_1, LEGACY_1, NATIVE_2, LEGACY_2]
        assert sr.native_ids(ids) == [NATIVE_1, NATIVE_2]

    def test_legado_nao_e_aceito_como_amostra(self):
        """Ids legados nao podem servir de molde (reintroduziriam o bug)."""
        assert sr.native_ids([LEGACY_1, LEGACY_2]) == []


class TestMintId:
    def test_mint_usa_formato_nativo_mesmo_com_legados_no_meio(self):
        """Regressao principal: o filtro tem de ignorar os ids legados."""
        novo = sr.mint_id_like("ses_", [NATIVE_1, LEGACY_1, NATIVE_2, LEGACY_2])
        assert sr.is_native_id(novo), novo

    def test_mint_sem_amostra_ainda_e_nativo(self):
        novo = sr.mint_id_like("ses_", [])
        assert sr.is_native_id(novo), novo

    def test_mint_de_msg_usa_o_mesmo_formato(self):
        novo = sr.mint_id_like("msg_", ["msg_e99ced15dffe19WAaKxpEx3jcY"])
        assert novo.startswith("msg_")
        assert len(novo) == len("msg_") + 26
        assert all(c.isalnum() for c in novo[4:])

    def test_mint_preserva_o_componente_de_tempo(self):
        novo = sr.mint_id_like("ses_", [NATIVE_1])
        assert novo[:16] == NATIVE_1[:16]

    def test_mint_nao_repete_ids_ja_usados(self):
        usados = [sr.mint_id_like("ses_", [NATIVE_1]) for _ in range(5)]
        assert len(set(usados)) == len(usados)

    def test_ids_novos_sao_sempre_nativos(self):
        """100 ids seguidos, sempre no formato aceito pelo free tier."""
        for _ in range(100):
            assert sr.is_native_id(sr.mint_id_like("ses_", [NATIVE_1, LEGACY_1]))


class TestSanitizeIds:
    def _payload(self):
        return {
            "info": {"id": LEGACY_1, "title": "t", "time": {"created": 1}},
            "messages": [
                {"id": "msg_aaaa", "type": "user", "text": "oi", "files": []},
                {"id": "msg_bbbb", "type": "assistant", "content": "res"},
            ],
        }

    def test_sanitizar_renova_o_id_para_o_formato_nativo(self):
        out = sr.sanitize_v2(self._payload(), id_samples=[NATIVE_1, LEGACY_1])
        assert sr.is_native_id(out["info"]["id"]), out["info"]["id"]

    def test_sanitizar_renova_tambem_os_ids_de_mensagem(self):
        out = sr.sanitize_v2(self._payload(), id_samples=[NATIVE_1, LEGACY_1])
        for msg in out["messages"]:
            assert msg["id"].startswith("msg_")
            assert len(msg["id"]) == len("msg_") + 26


class TestContextFit:
    def _payload(self, n_chars):
        return {
            "info": {"id": NATIVE_1, "model": {"providerID": "opencode", "id": "beam-free"}},
            "messages": [
                {"id": f"msg_{i:016d}", "type": "user", "text": "x" * n_chars}
                for i in range(10)
            ],
        }

    def test_estimativa_de_tokens(self):
        payload = self._payload(3500)          # 10 x 3500 chars ≈ 10 000 tokens
        est = sr.estimate_tokens(payload)
        assert 5_000 < est < 15_000, est

    def test_aparar_descarta_as_mensagens_mais_antigas(self):
        payload = self._payload(3500)
        trimmed, dropped = sr.trim_payload(payload, 2_000)
        assert dropped > 0
        assert len(trimmed["messages"]) < len(payload["messages"])
        # a ultima mensagem (contexto imediato) e' sempre preservada
        assert trimmed["messages"][-1] == payload["messages"][-1]

    def test_aparar_nao_altera_quando_cabe(self):
        payload = self._payload(10)
        trimmed, dropped = sr.trim_payload(payload, 1_000_000)
        assert dropped == 0
        assert len(trimmed["messages"]) == len(payload["messages"])

    def test_orcamento_sem_modelo_conhecido(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 0)
        assert sr.context_budget("opencode", {}) == sr.FREE_TIER_SAFE_TOKENS

    def test_orcamento_usa_o_contexto_do_modelo(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 200_000)
        orc = sr.context_budget("opencode", {"providerID": "opencode", "id": "x"})
        assert 150_000 < orc <= 200_000

    def test_sessao_que_cabe_nao_e_ajustada(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 1_000_000)
        monkeypatch.setattr(sr, "compact_session", lambda *a, **k: True)
        payload = self._payload(10)
        out = sr.fit_to_context("opencode", NATIVE_1, payload)
        assert out["action"] == "none"
        assert out["session_id"] == NATIVE_1

    def test_sessao_grande_e_ajustada_por_compactacao(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 200_000)
        monkeypatch.setattr(sr, "compact_session", lambda *a, **k: True)
        payload = self._payload(70_000)
        out = sr.fit_to_context("opencode", NATIVE_1, payload)
        assert out["action"] == "compacted"
        assert out["tokens_before"] > out["budget"]

    def test_falha_na_compactacao_cai_para_o_aparar(self, monkeypatch):
        monkeypatch.setattr(sr, "model_context_limit", lambda *a, **k: 200_000)
        monkeypatch.setattr(sr, "compact_session", lambda *a, **k: False)
        monkeypatch.setattr(
            sr, "import_session",
            lambda binary, payload, env=None, timeout=180: "ses_" + "a" * 26)
        monkeypatch.setattr(sr, "delete_session", lambda *a, **k: True)
        payload = self._payload(70_000)
        out = sr.fit_to_context("opencode", NATIVE_1, payload)
        assert out["action"] == "trimmed"
        assert out["messages_dropped"] > 0
        assert sr.is_native_id(out["session_id"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-o", "addopts="]))
