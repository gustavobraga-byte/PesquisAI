# tests/test_consent_dedupe.py — v0.6.20-fix
#
# Planilha de contatos recebe EXATAMENTE UMA linha por ativação/retorno
# (v0.6.20, contrato final): o kind "usuario_ativo" (e-mail · nome · IP),
# disparado pelo clique do botão Continuar/ABRIR (/api/access →
# notify_active_user()). save_contact() NÃO envia mais forward algum —
# o primeiro aceite grava apenas o perfil local + backup do Drive:
#   1. primeiro aceite (sem perfil) → SEM webhook; GA4 contact_optin ok;
#   2. mesmo e-mail do perfil persistente (Drive) → re-consentimento:
#      sem webhook, sem GA4, perfil local atualizado (ok=True);
#   3. e-mail DIFERENTE do perfil persistente → contato novo: sem webhook,
#      GA4 contact_optin ok (a linha única virá do clique do botão);
#   4. clear_contact() elimina TAMBÉM o backup persistente (LGPD art. 18 VI);
#   5. notify_active_user() → ÚNICO forward, kind "usuario_ativo", com IP.

import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pesquisai import telemetry as tel  # noqa: E402


class _SyncThread:
    """Executa o target sincronamente — torna os asserts determinísticos."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self._t, self._a, self._k = target, args, (kwargs or {})

    def start(self):
        if self._t is not None:
            self._t(*self._a, **self._k)


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """Ambiente isolado: perfil local + backup persistente + sem rede/GA4."""
    monkeypatch.setattr(tel.threading, "Thread", _SyncThread)
    monkeypatch.setattr(tel, "_email_domain_valid", lambda a: True)
    local_file = tmp_path / "ufvai_profile.json"
    backup_file = tmp_path / "ufvai_consentimento.json"
    monkeypatch.setattr(tel, "_PROFILE_FILE", str(local_file))
    monkeypatch.setattr(tel, "_persisted_profile_path", lambda: str(backup_file))
    forwards: list = []
    events: list = []
    monkeypatch.setattr(
        tel, "_forward_contact",
        lambda addr, sha, kind="novo_contato", name="", ip="": forwards.append((kind, addr, ip)),
    )
    monkeypatch.setattr(tel, "event", lambda n, p=None: events.append(n))
    return {"local": local_file, "backup": backup_file,
            "forwards": forwards, "events": events}


def test_primeiro_aceite_nao_envia_webhook(isolated):
    """v0.6.20: save_contact NÃO faz forward — a planilha aguarda o clique."""
    ok, _ = tel.save_contact("novo@exemplo.com", "Novo", "1.2.3.4")
    assert ok is True
    assert isolated["forwards"] == []          # NENHUMA linha "novo_contato"
    assert "contact_optin" in isolated["events"]  # contador anônimo GA4 mantido
    # perfil local é gravado normalmente
    prof = json.loads(isolated["local"].read_text(encoding="utf-8"))
    assert prof["email"] == "novo@exemplo.com"
    assert prof["name"] == "Novo"


def test_re_consentimento_mesmo_email_nao_registra(isolated):
    # Perfil persistente (backup do Drive) já tem este e-mail
    isolated["backup"].write_text(
        json.dumps({"email": "gustavo@ufv.br", "accepted": True}), encoding="utf-8")
    ok, _ = tel.save_contact("Gustavo@UFV.br", "Gustavo", "")
    assert ok is True
    assert isolated["forwards"] == []  # NENHUMA linha "novo_contato"
    assert "contact_optin" not in isolated["events"]
    # perfil local é atualizado mesmo assim (consent_at/termos em dia)
    prof = json.loads(isolated["local"].read_text(encoding="utf-8"))
    assert prof["email"] == "gustavo@ufv.br"
    assert prof["name"] == "Gustavo"


def test_email_diferente_registra_como_novo(isolated):
    isolated["backup"].write_text(
        json.dumps({"email": "antigo@ufv.br"}), encoding="utf-8")
    ok, _ = tel.save_contact("outro@exemplo.com", "Outro", "")
    assert ok is True
    # v0.6.20: contato novo também NÃO envia webhook — linha única vem do
    # clique do botão (notify_active_user), sempre kind "usuario_ativo"
    assert isolated["forwards"] == []
    assert "contact_optin" in isolated["events"]


def test_clear_contact_remove_backup_persistente(isolated):
    isolated["local"].write_text(json.dumps({"email": "x@y.com"}), encoding="utf-8")
    isolated["backup"].write_text(json.dumps({"email": "x@y.com"}), encoding="utf-8")
    tel.clear_contact()
    assert not isolated["local"].exists()
    assert not isolated["backup"].exists()


def test_notify_active_user_eh_a_unica_linha_da_planilha(isolated):
    """v0.6.20: notify_active_user é a ÚNICA fonte de linhas na planilha —
    1 linha "usuario_ativo" por clique do botão, com e-mail + nome + IP."""
    isolated["local"].write_text(json.dumps({
        "email": "gustavo@ufv.br",
        "email_sha256": "abc123",
        "name": "Gustavo",
    }), encoding="utf-8")
    tel.notify_active_user("177.128.109.197")
    assert isolated["forwards"] == [("usuario_ativo", "gustavo@ufv.br", "177.128.109.197")]


def test_notify_active_user_sem_perfil_eh_noop(isolated):
    tel.notify_active_user("1.2.3.4")
    assert isolated["forwards"] == []
