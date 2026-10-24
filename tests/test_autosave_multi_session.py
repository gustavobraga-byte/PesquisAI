# -*- coding: utf-8 -*-
"""Testes do autosave POR SESSAO (v0.7.4, 23/10/2026).

Pedido do autor: *"quando tem varias sessoes o autosave salva somente uma.
Queria que salvasse todas ou a que esta ativa."*

Antes, o `POST /api/autosave` exportava **uma** sessao (a do terminal) para
os slots rotativos (`autosave_1..3`). Agora:

  * os slots continuam sendo a **rotacao da interacao atual**;
  * **cada conversa viva** que tenha conteudo novo recebe o seu proprio
    arquivo em `backups/autosave/sessions/<id>.json`;
  * o modal "Restaurar" lista esses arquivos (e o `/api/restore` os aceita).

Cobre:
  * `session_restore.session_autosave_path` — nome seguro (sem traversal);
  * `session_restore.write_session_autosave` — grava e **nao reescreve**
    quando o conteudo e' identico;
  * `session_restore.list_session_autosaves` — itens no formato aceito pelo
    `/api/restore`;
  * `session_restore.infer_project_dir` — a pasta da conversa real (ignora
    as sessoes de preflight, que vivem em `/root` e nao tem mensagens);
  * `session_restore.save_all_sessions` — salva **todas** as conversas com
    conteudo novo, pula as que nao mudaram e respeita o limite por ciclo;
  * `launch_app._resolve_restore_path` — aceita `autosave/sessions/<id>.json`
    e barra path traversal.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "pesquisai"


def _load_pkg_module(name: str, filename: str):
    """Carrega um modulo do pacote `pesquisai/` sem depender do sys.path."""
    pkg_name = "ufvai_test_pkg_v074"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(_PKG)]
        sys.modules[pkg_name] = pkg
    spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.{name}", _PKG / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sr = _load_pkg_module("session_restore", "session_restore.py")


def _export_payload(session_id: str, n_messages: int = 3) -> dict:
    return {
        "info": {"id": session_id, "title": f"Sessão {session_id[-6:]}",
                 "time": {"created": 1, "updated": 2}},
        "messages": [{"id": f"msg_{i}", "type": "user", "text": f"m{i}",
                      "files": []} for i in range(n_messages)],
    }


class TestSessionAutosavePath(unittest.TestCase):
    def test_caminho_por_sessao(self):
        path = sr.session_autosave_path("/tmp/auto", "ses_abc123")
        self.assertTrue(path.endswith(os.path.join("sessions", "ses_abc123.json")))

    def test_nome_seguro_sem_traversal(self):
        path = sr.session_autosave_path("/tmp/auto", "../../etc/passwd")
        self.assertNotIn("..", path)
        self.assertTrue(path.startswith("/tmp/auto"))

    def test_id_vazio_nao_gera_caminho(self):
        self.assertEqual(sr.session_autosave_path("/tmp/auto", ""), "")


class TestWriteSessionAutosave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ufvai-sess-")
        self.src = os.path.join(self.tmp, "export.json")
        with open(self.src, "w", encoding="utf-8") as fh:
            json.dump(_export_payload("ses_aaa111"), fh)

    def test_grava_o_arquivo_da_sessao(self):
        res = sr.write_session_autosave(self.src, "ses_aaa111", self.tmp)
        self.assertTrue(res["ok"])
        self.assertFalse(res["skipped"])
        self.assertTrue(os.path.exists(
            sr.session_autosave_path(self.tmp, "ses_aaa111")))

    def test_nao_reescreve_conteudo_identico(self):
        sr.write_session_autosave(self.src, "ses_aaa111", self.tmp)
        res = sr.write_session_autosave(self.src, "ses_aaa111", self.tmp)
        self.assertTrue(res["ok"])
        self.assertTrue(res["skipped"])

    def test_reescreve_quando_o_conteudo_muda(self):
        sr.write_session_autosave(self.src, "ses_aaa111", self.tmp)
        with open(self.src, "w", encoding="utf-8") as fh:
            json.dump(_export_payload("ses_aaa111", 9), fh)
        res = sr.write_session_autosave(self.src, "ses_aaa111", self.tmp)
        self.assertTrue(res["ok"])
        self.assertFalse(res["skipped"])


class TestListSessionAutosaves(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ufvai-list-")
        os.makedirs(sr.session_autosave_dir(self.tmp), exist_ok=True)
        for sid in ("ses_aaa111", "ses_bbb222"):
            path = sr.session_autosave_path(self.tmp, sid)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(_export_payload(sid), fh)

    def test_lista_um_item_por_conversa(self):
        items = sr.list_session_autosaves(self.tmp)
        self.assertEqual(len(items), 2)
        ids = {item["session_id"] for item in items}
        self.assertEqual(ids, {"ses_aaa111", "ses_bbb222"})

    def test_formato_do_arquivo_aceito_pelo_restore(self):
        for item in sr.list_session_autosaves(self.tmp):
            self.assertTrue(item["file"].startswith("autosave/sessions/"))
            self.assertTrue(item["file"].endswith(".json"))
            self.assertEqual(item["kind"], "autosave-session")
            self.assertTrue(item["date"])
            self.assertTrue(item["time"])

    def test_pasta_inexistente_nao_quebra(self):
        self.assertEqual(sr.list_session_autosaves("/tmp/nao-existe-xyz"), [])


class TestInferProjectDir(unittest.TestCase):
    def test_ignora_sessao_vazia_de_preflight(self):
        sessions = [
            {"id": "ses_a", "location": {"directory": "/root"},
             "tokens": {"input": 0}, "time": {"updated": 999999}},
            {"id": "ses_b", "location": {"directory": "/content/drive"},
             "tokens": {"input": 120}, "time": {"updated": 1000}},
        ]
        self.assertEqual(sr.infer_project_dir(sessions), "/content/drive")

    def test_sem_conversa_com_conteudo_devolve_vazio(self):
        self.assertEqual(sr.infer_project_dir([]), "")


class TestSaveAllSessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ufvai-all-")
        self.exported = []

        def _fake_export(binary, session_id, path, env=None, timeout=120):
            self.exported.append(session_id)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(_export_payload(session_id, 4), fh)
            return _export_payload(session_id, 4), "v2"

        sr.export_session_to_file = _fake_export

    def _sessions(self):
        now_ms = int(time.time() * 1000)
        return [
            {"id": "ses_aaa111", "location": {"directory": "/content/drive"},
             "tokens": {"input": 10}, "time": {"updated": now_ms}},
            {"id": "ses_bbb222", "location": {"directory": "/content/drive"},
             "tokens": {"input": 20}, "time": {"updated": now_ms}},
            {"id": "ses_ccc333", "location": {"directory": "/root"},
             "tokens": {"input": 30}, "time": {"updated": now_ms}},
        ]

    def test_salva_todas_as_conversas_do_projeto(self):
        res = sr.save_all_sessions("opencode", self._sessions(), self.tmp,
                                   project_dir="/content/drive")
        self.assertEqual(sorted(res["saved"]), ["ses_aaa111", "ses_bbb222"])
        # a conversa de outro projeto (/root) ficou de fora
        self.assertNotIn("ses_ccc333", res["saved"])
        self.assertTrue(os.path.exists(
            sr.session_autosave_path(self.tmp, "ses_aaa111")))
        self.assertTrue(os.path.exists(
            sr.session_autosave_path(self.tmp, "ses_bbb222")))

    def test_conversa_sem_novidade_e_pulada(self):
        sessions = self._sessions()
        res = sr.save_all_sessions("opencode", sessions, self.tmp,
                                   project_dir="/content/drive")
        self.assertEqual(len(res["saved"]), 2)
        # 2o ciclo: nada mudou -> ninguem e' exportado de novo
        res2 = sr.save_all_sessions("opencode", sessions, self.tmp,
                                    project_dir="/content/drive")
        self.assertEqual(res2["saved"], [])
        self.assertEqual(len(res2["skipped"]), 2)

    def test_respeita_o_limite_por_ciclo(self):
        sessions = self._sessions()
        res = sr.save_all_sessions("opencode", sessions, self.tmp,
                                   project_dir="/content/drive", max_sessions=1)
        self.assertEqual(len(res["saved"]), 1)

    def test_conversa_antiga_e_ignorada(self):
        old = int((time.time() - 48 * 3600) * 1000)
        sessions = [{"id": "ses_old", "location": {"directory": "/content/drive"},
                     "tokens": {"input": 10}, "time": {"updated": old}}]
        res = sr.save_all_sessions("opencode", sessions, self.tmp,
                                   project_dir="/content/drive")
        self.assertEqual(res["saved"], [])


class TestResolveRestorePath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launch_app = _load_pkg_module("launch_app", "launch_app.py")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ufvai-resolve-")
        self.auto = os.path.join(self.tmp, "autosave")
        os.makedirs(os.path.join(self.auto, "sessions"), exist_ok=True)
        with open(os.path.join(self.auto, "sessions", "ses_aaa111.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(_export_payload("ses_aaa111"), fh)

    def test_aceita_autosave_por_sessao(self):
        path, err = self.launch_app._resolve_restore_path(
            "autosave/sessions/ses_aaa111.json", self.tmp, self.auto)
        self.assertEqual(err, "")
        self.assertTrue(path.endswith(os.path.join("sessions", "ses_aaa111.json")))

    def test_barrar_traversal(self):
        for nome in ("autosave/sessions/../../etc/passwd.json",
                     "autosave/sessions/..%2Fkeys_store.json",
                     "autosave/sessions/sub/ses_aaa111.json"):
            path, err = self.launch_app._resolve_restore_path(
                nome, self.tmp, self.auto)
            self.assertIsNone(path, nome)
            self.assertTrue(err)

    def test_arquivo_inexistente(self):
        path, err = self.launch_app._resolve_restore_path(
            "autosave/sessions/ses_nao_existe.json", self.tmp, self.auto)
        self.assertIsNone(path)
        self.assertIn("não encontrado", err)


if __name__ == "__main__":
    unittest.main()
