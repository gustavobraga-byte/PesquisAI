"""Testes v0.6.0 — telemetria anônima opt-in (UFVAI/PesquisAI)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import telemetry


class TestTelemetryDefaults:
    def test_disabled_sem_config(self):
        """Sem GA config no ambiente → desabilitada mesmo com consent."""
        os.environ.pop("UFVAI_GA_MEASUREMENT_ID", None)
        os.environ.pop("UFVAI_GA_API_SECRET", None)
        assert telemetry.configured() is False
        assert telemetry.enabled() is False

    def test_kill_switch(self):
        os.environ["UFVAI_TELEMETRY"] = "0"
        try:
            assert telemetry.kill_switch_active() is True
            assert telemetry.enabled() is False
        finally:
            os.environ.pop("UFVAI_TELEMETRY", None)

    def test_event_nunca_levanta(self):
        """event() deve ser no-op silencioso quando desabilitada."""
        os.environ.pop("UFVAI_GA_MEASUREMENT_ID", None)
        telemetry.event("teste_unitario", {"x": 1})  # não deve levantar

    def test_consent_read_write(self, tmp_path):
        """Gravação/leitura de consentimento em arquivo isolado."""
        cfile = tmp_path / "consent.json"
        old = telemetry._CONSENT_FILE
        telemetry._CONSENT_FILE = str(cfile)
        try:
            assert telemetry.consented() is False
            telemetry.set_consent(True)
            assert telemetry.consented() is True
            telemetry.set_consent(False)
            assert telemetry.consented() is False
        finally:
            telemetry._CONSENT_FILE = old
