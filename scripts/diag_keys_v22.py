#!/usr/bin/env python3
"""diag_keys_v22.py — diagnóstico das chaves de API do UFVAI × OpenCode v2.2.

Responde, em uma tela, por que um provedor configurado no Drive não aparece
no motor:

  * quantas chaves o ``keys_store.json`` tem e quais VARIÁVEIS elas pedem;
  * se essas variáveis existem no processo atual, no ``~/.bashrc`` e — o
    ponto crítico — no processo do serviço ``opencode serve --service``;
  * quais provedores o motor enxerga hoje (``opencode models``).

Nunca imprime segredo: só nomes de variáveis, contagens e existência.

Uso:
    python3 scripts/diag_keys_v22.py [--backup-dir CAMINHO] [--json]

Código de saída:
    0  chaves presentes no store E visíveis no serviço
    1  store com chaves mas serviço sem elas (falha de injeção)
    2  nenhuma chave utilizável no store
    3  serviço não está rodando ou erro inesperado
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _backup_candidates(explicit: str | None) -> list[str]:
    if explicit:
        return [explicit]
    home = os.path.expanduser("~")
    return [
        "/content/drive/My Drive/PesquisAI/backups",
        os.path.join(home, "PesquisAI", "backups"),
    ]


def _pick_backup_dir(explicit: str | None) -> str | None:
    for candidate in _backup_candidates(explicit):
        if os.path.exists(os.path.join(candidate, "keys_store.json")):
            return candidate
    return None


def _bashrc_key_count() -> int:
    path = os.path.expanduser("~/.bashrc")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return sum(1 for line in fh if "# opencode-key-" in line)
    except OSError:
        return 0


def _models_by_provider(timeout: int = 90) -> dict[str, int]:
    try:
        out = subprocess.run(
            ["opencode", "models"], capture_output=True, text=True,
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    counts: dict[str, int] = {}
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if not line or "/" not in line:
            continue
        provider = line.split("/", 1)[0]
        counts[provider] = counts.get(provider, 0) + 1
    return counts


def collect(backup_dir: str | None = None) -> dict[str, Any]:
    """Monta o retrato do estado (sem segredos)."""
    from pesquisai.opencode_utils import (
        keys_env_from_store,
        service_env,
        service_pids,
    )

    picked = _pick_backup_dir(backup_dir)
    report: dict[str, Any] = {
        "backup_dir": picked or (backup_dir or ""),
        "keys_store_found": picked is not None,
        "encryption_key_found": False,
        "providers_in_store": [],
        "keys_readable": 0,
        "keys_unreadable": 0,
        "env_vars_expected": [],
        "env_vars_in_process": [],
        "env_vars_in_bashrc_count": _bashrc_key_count(),
        "service_pids": [],
        "env_vars_in_service": [],
        "missing_in_service": [],
        "models_by_provider": {},
    }

    keys_env: dict[str, str] = {}
    if picked:
        report["encryption_key_found"] = os.path.exists(
            os.path.join(picked, "keys_encryption_key.bin")
        ) or os.path.exists(os.path.join(picked, ".keys_encryption_key"))
        keys_env = keys_env_from_store(picked)
        try:
            from pesquisai.security import load_encrypted_keys
            store = load_encrypted_keys(picked)
            report["providers_in_store"] = sorted(
                k for k in store if not k.startswith("_env_")
            )
            report["keys_readable"] = sum(
                1 for k, v in store.items()
                if not k.startswith("_env_") and isinstance(v, str) and v
            )
            report["keys_unreadable"] = sum(
                1 for k, v in store.items()
                if not k.startswith("_env_") and v == ""
            )
        except Exception as exc:  # noqa: BLE001
            report["store_error"] = str(exc)

    report["env_vars_expected"] = sorted(keys_env)
    report["env_vars_in_process"] = sorted(v for v in keys_env if v in os.environ)

    pids = service_pids()
    report["service_pids"] = pids
    have: set[str] = set()
    for pid in pids:
        have |= set(service_env(pid))
    report["env_vars_in_service"] = sorted(v for v in keys_env if v in have)
    report["missing_in_service"] = sorted(v for v in keys_env if v not in have)

    report["models_by_provider"] = _models_by_provider()
    return report


def _verdict(report: dict[str, Any]) -> tuple[int, str]:
    expected = report.get("env_vars_expected") or []
    if not report.get("keys_store_found") or not expected:
        return 2, "Nenhuma chave utilizável no store — configure pela interface (+ provedor)."
    missing = report.get("missing_in_service") or []
    if missing:
        return 1, (
            f"FALHA: {len(missing)} variável(is) existem no Drive e NÃO chegaram ao "
            f"serviço do motor ({', '.join(missing)}). É o defeito corrigido na v0.7.8."
        )
    if not report.get("service_pids"):
        return 3, "Serviço do motor não está em execução (nada a comparar)."
    return 0, "OK: as chaves do Drive estão no ambiente do serviço."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico de chaves UFVAI × OpenCode v2.2"
    )
    parser.add_argument("--backup-dir", default=None,
                        help="pasta backups/ (padrão: Drive, depois ~/PesquisAI)")
    parser.add_argument("--json", action="store_true", help="saída JSON")
    args = parser.parse_args(argv)

    try:
        report = collect(args.backup_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"ERRO: {exc!r}", file=sys.stderr)
        return 3

    code, message = _verdict(report)
    report["verdict"] = message
    report["exit_code"] = code

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return code

    print("═" * 62)
    print("  DIAGNÓSTICO DE CHAVES — UFVAI × OpenCode v2.2")
    print("═" * 62)
    print(f"  Pasta do store ......... {report['backup_dir'] or '(não encontrada)'}")
    print(f"  Chave de criptografia .. {'sim' if report['encryption_key_found'] else 'NÃO'}")
    print(f"  Provedores no store .... {', '.join(report['providers_in_store']) or '(nenhum)'}")
    print(f"  Chaves legíveis ........ {report.get('keys_readable', 0)}"
          f" (ilegíveis: {report.get('keys_unreadable', 0)})")
    print(f"  Variáveis esperadas .... {', '.join(report['env_vars_expected']) or '(nenhuma)'}")
    print(f"  No processo atual ...... {', '.join(report['env_vars_in_process']) or '(nenhuma)'}")
    print(f"  No ~/.bashrc ........... {report['env_vars_in_bashrc_count']} export(s)")
    print(f"  Serviço (PID) .......... {', '.join(report['service_pids']) or '(não está rodando)'}")
    print(f"  No serviço ............. {', '.join(report['env_vars_in_service']) or '(nenhuma)'}")
    print(f"  Faltando no serviço .... {', '.join(report['missing_in_service']) or '(nenhuma)'}")
    models = report["models_by_provider"]
    print(f"  Provedores no motor .... "
          f"{', '.join(f'{k} ({v})' for k, v in sorted(models.items())) or '(nenhum)'}")
    print("-" * 62)
    print(f"  {message}")
    print("═" * 62)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
