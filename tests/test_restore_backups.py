# -*- coding: utf-8 -*-
"""Testes do "Restaurar" da v0.7.0 — lista SOMENTE backups, com data/hora.

Cobre:
  * `session_restore.parse_backup_filename` — nome -> data/hora/id;
  * `session_restore.list_backups` — filtra o que NAO e backup (chaves,
    consentimentos), ordena por data, detecta truncamento (FUSE) e inclui
    os autosaves;
  * `launch_app._resolve_restore_path` — recusa arquivos que nao sao backup
    e barrar path traversal.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "pesquisai"


def _load_pkg_module(name: str, filename: str):
    """Carrega um modulo do pacote `pesquisai/` sem depender do sys.path.

    O repositorio tem um `__init__.py` na raiz (layout plano legado) que
    sombreia o pacote `pesquisai/` quando o pytest insere o diretorio
    pai no sys.path — problema de ambiente pre-existente. O carregamento
    por caminho evita o conflito.
    """
    pkg_name = "ufvai_test_pkg"
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


def _write(path: str, payload: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload)


class TestParseBackupFilename(unittest.TestCase):
    def test_nome_padrao(self):
        meta = sr.parse_backup_filename(
            "backup_ses_08fe0c7d_15-18-34_20-07-2026.json")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["session_id"], "08fe0c7d")
        self.assertEqual(meta["date"], "2026-07-20")
        self.assertEqual(meta["time"], "15:18:34")
        self.assertEqual(meta["datetime"].year, 2026)
        self.assertEqual(meta["datetime"].month, 7)
        self.assertEqual(meta["datetime"].day, 20)

    def test_arquivos_que_nao_sao_backup(self):
        for nome in ("keys_store.json", "keys.json", "aakeys.json",
                     "ufvai_consentimento.json", "ufvai_consentimento001.json",
                     "autosave_1.json", "backup.json", "notebook.json"):
            self.assertIsNone(sr.parse_backup_filename(nome), nome)

    def test_data_impossivel(self):
        self.assertIsNone(
            sr.parse_backup_filename("backup_ses_abc_00-00-00_31-02-2026.json"))

    def test_nome_vazio(self):
        self.assertIsNone(sr.parse_backup_filename(""))


class TestHumanSize(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(sr.human_size(0), "0 B")
        self.assertEqual(sr.human_size(512), "512 B")
        self.assertIn("KB", sr.human_size(33622))
        self.assertIn("MB", sr.human_size(1927728))
        # separador pt-BR
        self.assertIn(",", sr.human_size(33622))


class TestListBackups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.auto = os.path.join(self.dir, "autosave")
        os.makedirs(self.auto, exist_ok=True)

        # backups reais
        _write(os.path.join(self.dir, "backup_ses_aaa_10-00-00_21-10-2026.json"),
               json.dumps({"info": {"id": "ses_aaa", "title": "Sessao A"},
                           "messages": [{"id": "m1"}]}))
        _write(os.path.join(self.dir, "backup_ses_bbb_11-30-00_21-10-2026.json"),
               json.dumps({"info": {"id": "ses_bbb", "title": "Sessao B"},
                           "messages": [{"id": "m2"}]}))
        _write(os.path.join(self.dir, "backup_ses_ccc_09-15-00_09-10-2026.json"),
               json.dumps({"info": {"id": "ses_ccc", "title": "Sessao C"},
                           "messages": [{"id": "m3"}]}))
        # backup truncado pelo FUSE (sem chave de fechamento)
        _write(os.path.join(self.dir, "backup_ses_ddd_01-13-56_18-06-2026.json"),
               "{\"info\": {\"id\": \"ses_ddd\", \"trunc")

        # arquivos que NAO sao backup (ficam na mesma pasta)
        _write(os.path.join(self.dir, "keys_store.json"), "{\"k\": \"v\"}")
        _write(os.path.join(self.dir, "keys.json"), "{\"k\": \"v\"}")
        _write(os.path.join(self.dir, "aakeys.json"), "{\"k\": \"v\"}")
        _write(os.path.join(self.dir, "ufvai_consentimento.json"), "{\"c\": 1}")
        _write(os.path.join(self.dir, "ufvai_consentimento001.json"), "{\"c\": 1}")
        _write(os.path.join(self.dir, ".oculto.json"), "{\"c\": 1}")
        _write(os.path.join(self.dir, "notebook.txt"), "texto")

        # autosaves
        _write(os.path.join(self.auto, "autosave_1.json"),
               json.dumps({"info": {"id": "ses_as", "title": "Auto"},
                           "messages": [{"id": "m4"}]}))
        _write(os.path.join(self.auto, "autosave_2.json"),
               json.dumps({"info": {"id": "ses_as", "title": "Auto"},
                           "messages": [{"id": "m5"}]}))
        # v0.7.2 — mtime FIXO dos autosaves. Sem isso o mtime era "agora"
        # e o teste dependia da DATA DO DIA (quebrava ao virar o dia:
        # items[0] passava a ser o autosave de "hoje", nao o backup de
        # 21/10). Agora a ordenacao e deterministica.
        _ts_fixo = datetime.datetime(2026, 10, 20, 12, 0, 0).timestamp()
        for _n in ("autosave_1.json", "autosave_2.json"):
            os.utime(os.path.join(self.auto, _n), (_ts_fixo, _ts_fixo))

    def tearDown(self):
        self.tmp.cleanup()

    def test_lista_somente_backups(self):
        items = sr.list_backups(self.dir, self.auto)
        nomes = {i["file"] for i in items}
        self.assertNotIn("keys_store.json", nomes)
        self.assertNotIn("keys.json", nomes)
        self.assertNotIn("aakeys.json", nomes)
        self.assertNotIn("ufvai_consentimento.json", nomes)
        self.assertNotIn("ufvai_consentimento001.json", nomes)
        self.assertNotIn(".oculto.json", nomes)
        self.assertNotIn("notebook.txt", nomes)
        # 4 backups + 2 autosaves
        self.assertEqual(len(items), 6)

    def test_metadados(self):
        items = sr.list_backups(self.dir, self.auto)
        alvo = next(i for i in items if i["file"].endswith("aaa_10-00-00_21-10-2026.json"))
        self.assertEqual(alvo["date"], "2026-10-21")
        self.assertEqual(alvo["time"], "10:00:00")
        self.assertEqual(alvo["session_id"], "aaa")
        self.assertEqual(alvo["kind"], "backup")
        self.assertTrue(alvo["valid"])
        self.assertEqual(alvo["title"], "Sessao A")
        self.assertGreater(alvo["size"], 0)
        self.assertIn("B", alvo["size_h"])

    def test_ordenacao_decrescente_por_data(self):
        items = sr.list_backups(self.dir, self.auto)
        marcas = [i["timestamp"] for i in items]
        self.assertEqual(marcas, sorted(marcas, reverse=True))
        self.assertEqual(items[0]["date"], "2026-10-21")

    def test_truncamento_detectado(self):
        items = sr.list_backups(self.dir, self.auto)
        truncado = next(i for i in items if "ddd" in i["file"])
        self.assertFalse(truncado["valid"])
        # o truncado continua listado (o usuario pode ver que existe),
        # mas sinalizado como corrompido
        validos = [i for i in items if i["valid"]]
        self.assertEqual(len(validos), 5)

    def test_autosaves_incluidos(self):
        items = sr.list_backups(self.dir, self.auto)
        autos = [i for i in items if i["kind"] == "autosave"]
        self.assertEqual(len(autos), 2)
        self.assertTrue(all(i["file"].startswith("autosave/") for i in autos))

    def test_pasta_inexistente(self):
        self.assertEqual(sr.list_backups("/tmp/nao-existe-xyz", "/tmp/nao-existe-xyz"), [])


class TestSaveAutosaveRotation(unittest.TestCase):
    """Regressao da v0.7.0: o slot 1 (mais recente) ficava VAZIO.

    A rotacao vinha DEPOIS da gravacao e levava o arquivo recem-gravado do
    slot 1 para o slot 2 — o "mais recente" ficava fora do lugar
    documentado e o slot 1 nunca existia. Agora a rotacao vem ANTES.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "autosave")
        os.makedirs(self.dir, exist_ok=True)
        self._orig_export = sr.export_session_to_file

        def fake_export(binary, session_id, out_path, env=None, **kw):
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump({"info": {"id": session_id, "title": "T"},
                           "messages": [{"id": "m1"}]}, fh)
            return {"info": {"id": session_id, "title": "T"},
                    "messages": [{"id": "m1"}]}, "v2"

        sr.export_session_to_file = fake_export

    def tearDown(self):
        sr.export_session_to_file = self._orig_export
        self.tmp.cleanup()

    def test_slot1_fica_com_o_mais_recente(self):
        sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        p1 = sr.autosave_paths(self.dir)[0]
        self.assertTrue(os.path.exists(p1), "slot 1 deve existir apos o autosave")
        self.assertEqual(os.path.getsize(p1) > 0, True)

        sr.save_autosave("opencode", "ses_2", self.dir, attempts=1)
        sr.save_autosave("opencode", "ses_3", self.dir, attempts=1)
        paths = sr.autosave_paths(self.dir)
        for path in paths:
            self.assertTrue(os.path.exists(path), f"slot ausente: {path}")

    def test_list_autosaves_ordena_por_data(self):
        for sid in ("ses_1", "ses_2", "ses_3"):
            sr.save_autosave("opencode", sid, self.dir, attempts=1)
        items = sr.list_autosaves(self.dir)
        # v0.7.3: alem dos 3 slots VIVOS, a listagem inclui as COPIAS
        # PRESERVADAS das interacoes anteriores (slots 4..6) — e' o que
        # garante que o backup da sessao anterior nao seja destruido.
        self.assertGreaterEqual(len(items), 3)
        marcas = [i["saved_at"] for i in items]
        self.assertEqual(marcas, sorted(marcas, reverse=True))
        # o mais recente e' o slot 1
        self.assertTrue(items[0]["file"].endswith("autosave_1.json"))
        vivos = [i for i in items if not i["history"]]
        preservados = [i for i in items if i["history"]]
        self.assertEqual(len(vivos), 3)
        self.assertTrue(preservados, "a interacao anterior deve estar preservada")
        for item in preservados:
            self.assertRegex(item["file"], r"autosave/autosave_\d+\.json")

    def test_fallback_quando_o_mais_recente_esta_corrompido(self):
        sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        sr.save_autosave("opencode", "ses_2", self.dir, attempts=1)
        # corrompe o slot 1 (truncamento do FUSE)
        with open(sr.autosave_paths(self.dir)[0], "w", encoding="utf-8") as fh:
            fh.write("{ truncado")
        items = sr.list_autosaves(self.dir)
        # v0.7.3: o fallback assume (slot 2) e a copia preservada da
        # interacao anterior continua restauravel.
        self.assertGreaterEqual(len(items), 1)
        self.assertTrue(items[0]["file"].endswith("autosave_2.json"))
        self.assertTrue(any(i["history"] for i in items),
                        "a interacao anterior deve continuar restauravel")


class TestResolveRestorePath(unittest.TestCase):
    """`launch_app._resolve_restore_path` — recusa o que nao e backup."""

    @classmethod
    def setUpClass(cls):
        cls.launch_app = _load_pkg_module("launch_app", "launch_app.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.auto = os.path.join(self.dir, "autosave")
        os.makedirs(self.auto, exist_ok=True)
        _write(os.path.join(self.dir, "backup_ses_aaa_10-00-00_21-10-2026.json"), "{}")
        _write(os.path.join(self.dir, "keys_store.json"), "{}")
        _write(os.path.join(self.auto, "autosave_1.json"), "{}")

    def tearDown(self):
        self.tmp.cleanup()

    def _resolve(self, name):
        return self.launch_app._resolve_restore_path(name, self.dir, self.auto)

    def test_backup_aceito(self):
        path, err = self._resolve("backup_ses_aaa_10-00-00_21-10-2026.json")
        self.assertTrue(path)
        self.assertEqual(err, "")

    def test_autosave_aceito(self):
        path, err = self._resolve("autosave/autosave_1.json")
        self.assertTrue(path)
        self.assertTrue(path.endswith(os.path.join("autosave", "autosave_1.json")))

    def test_arquivos_que_nao_sao_backup_recusados(self):
        for nome in ("keys_store.json", "keys.json", "ufvai_consentimento.json",
                     "aakeys.json", "backup.json"):
            path, err = self._resolve(nome)
            self.assertIsNone(path, nome)
            self.assertTrue(err)

    def test_path_traversal_recusado(self):
        for nome in ("../keys_store.json", "autosave/../keys_store.json",
                     "/etc/passwd", "..%2fkeys_store.json"):
            path, err = self._resolve(nome)
            self.assertIsNone(path, nome)

    def test_inexistente(self):
        path, err = self._resolve("backup_ses_zzz_00-00-00_01-01-2026.json")
        self.assertIsNone(path)
        self.assertIn("não encontrado", err)


class TestRetomadaNaEntrada(unittest.TestCase):
    """v0.7.1 — a retomada na ENTRADA falhava com "nao e um backup".

    Causa: `list_autosaves()` devolvia o nome do autosave SEM o prefixo
    "autosave/" (ao contrario de `list_backups()`), e o `/api/restore`
    tratava o nome como backup de sessao -> HTTP 400 "Este arquivo nao e
    um backup de sessao". O botao "Restaurar" funcionava porque usa
    `list_backups()` (que traz o prefixo).
    """

    @classmethod
    def setUpClass(cls):
        cls.launch_app = _load_pkg_module("launch_app", "launch_app.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "autosave")
        os.makedirs(self.dir, exist_ok=True)
        payload = {"info": {"id": "ses_x", "title": "T"},
                   "messages": [{"id": "m1", "text": "oi"}]}
        for slot in (1, 2, 3):
            _write(os.path.join(self.dir, f"autosave_{slot}.json"),
                   json.dumps(payload))

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_autosaves_traz_o_prefixo(self):
        items = sr.list_autosaves(self.dir)
        self.assertEqual(len(items), 3)
        for item in items:
            self.assertTrue(item["file"].startswith("autosave/"),
                            f"sem prefixo: {item['file']}")
            self.assertTrue(item["file"].endswith(".json"))
            self.assertTrue(item["name"].endswith(".json"))

    def test_nome_sem_prefixo_e_aceito(self):
        path, err = self.launch_app._resolve_restore_path(
            "autosave_1.json", os.path.dirname(self.dir), self.dir)
        self.assertTrue(path, err)
        self.assertTrue(path.endswith(os.path.join("autosave", "autosave_1.json")))

    def test_nome_com_prefixo_continua_aceito(self):
        path, err = self.launch_app._resolve_restore_path(
            "autosave/autosave_2.json", os.path.dirname(self.dir), self.dir)
        self.assertTrue(path, err)

    def test_arquivo_que_nao_e_backup_continua_recusado(self):
        for nome in ("keys_store.json", "backup.json", "autosave_0.json",
                     "autosave_x.json"):
            path, err = self.launch_app._resolve_restore_path(
                nome, os.path.dirname(self.dir), self.dir)
            self.assertIsNone(path, nome)


class TestAutosaveSemDuplicata(unittest.TestCase):
    """v0.7.1 — o autosave nao pode gravar 3 copias do MESMO arquivo.

    A gravacao so acontece quando o conteudo (id da sessao + mensagens)
    muda; caso contrario, o slot 1 continua como esta e nada e' rotacionado.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "autosave")
        os.makedirs(self.dir, exist_ok=True)
        self._orig_export = sr.export_session_to_file
        self.payload = {"info": {"id": "ses_1", "title": "T"},
                        "messages": [{"id": "m1"}]}

        def fake_export(binary, session_id, out_path, env=None, **kw):
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(self.payload, fh)
            return self.payload, "v2"

        sr.export_session_to_file = fake_export

    def tearDown(self):
        sr.export_session_to_file = self._orig_export
        self.tmp.cleanup()

    def test_conteudo_identico_nao_grava_novo_arquivo(self):
        info = sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        self.assertTrue(info["ok"])
        self.assertFalse(info.get("skipped"))
        slot1 = sr.autosave_paths(self.dir)[0]
        mtime1 = os.path.getmtime(slot1)

        info2 = sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        self.assertTrue(info2.get("skipped"), "deveria pular (conteudo identico)")
        self.assertEqual(info2.get("reason"), "conteudo_identico")
        # o slot 1 NAO foi reescrito e o slot 2 NAO foi criado
        self.assertEqual(os.path.getmtime(slot1), mtime1)
        self.assertFalse(os.path.exists(sr.autosave_paths(self.dir)[1]))

    def test_conteudo_novo_rotaciona(self):
        sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        self.payload = {"info": {"id": "ses_1", "title": "T"},
                        "messages": [{"id": "m1"}, {"id": "m2"}]}
        info = sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        self.assertFalse(info.get("skipped"))
        paths = sr.autosave_paths(self.dir)
        self.assertTrue(os.path.exists(paths[0]))
        self.assertTrue(os.path.exists(paths[1]))
        # o slot 2 e' a versao anterior
        with open(paths[1], "r", encoding="utf-8") as fh:
            antigo = json.load(fh)
        self.assertEqual(len(antigo["messages"]), 1)

    def test_sessao_diferente_grava(self):
        sr.save_autosave("opencode", "ses_1", self.dir, attempts=1)
        self.payload = {"info": {"id": "ses_2", "title": "T"},
                        "messages": [{"id": "m1"}]}
        info = sr.save_autosave("opencode", "ses_2", self.dir, attempts=1)
        self.assertFalse(info.get("skipped"), "sessao diferente = arquivo diferente")
        self.assertTrue(os.path.exists(sr.autosave_paths(self.dir)[1]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
