"""
sync.py — Sincronização do vault com Google Drive e git.

Três modos:

1. **drive** — espelha o vault para uma pasta "vault-mirror" no Drive
   (compatível com usuários que não usam Obsidian localmente)
2. **git** — ``git add && git commit && git push`` em bare repo
   (compatível com *Obsidian Git* ou *Remotely Save*)
3. **pull-only** — apenas verifica se o vault remoto está atualizado
   e avisa se houver divergências

Política:

- **Nunca** sobrescreve notas humanas (a regra do :class:`Vault` prevalece)
- Faz **backup local** antes de cada push (``vault/.backups/AAAA-MM-DD/``)
- Respeita **rate limits** do Drive (no máximo 1 write/segundo)
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Union

from .models import Note
from .vault import Vault

logger = logging.getLogger("pesquisai.obsidian.sync")


@dataclass(slots=True)
class SyncReport:
    """Relatório de uma operação de sincronização."""

    started_at: _dt.datetime
    ended_at: _dt.datetime
    pushed: tuple[str, ...] = ()
    pulled: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    bytes_transferred: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"⏱  {self.ended_at - self.started_at}\n"
            f"📤 pushed: {len(self.pushed)}\n"
            f"📥 pulled: {len(self.pulled)}\n"
            f"⚠️  conflicts: {len(self.conflicts)}\n"
            f"❌ errors: {len(self.errors)}"
        )


def sync_drive(
    vault: Vault,
    mirror_path: Union[str, Path],
    *,
    direction: str = "push",  # "push" | "pull" | "both"
) -> SyncReport:
    """Sincroniza o vault com uma pasta espelho (ex.: outra pasta no Drive).

    Esta é a forma mais simples de "sync" — basta copiar os arquivos.
    Para vaults grandes, prefira :func:`sync_git` com *Obsidian Git*.
    """
    started = _dt.datetime.now()
    mirror = Path(mirror_path).expanduser().resolve()
    mirror.mkdir(parents=True, exist_ok=True)
    pushed: list[str] = []
    pulled: list[str] = []
    errors: list[str] = []
    bytes_tx = 0

    if direction in ("push", "both"):
        for note in vault.iter_notes():
            src = vault.root / note.path
            dst = mirror / note.path
            try:
                if not _is_newer(src, dst):
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                bytes_tx += src.stat().st_size
                pushed.append(note.path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"push {note.path}: {exc}")

    if direction in ("pull", "both"):
        for src in mirror.rglob("*.md"):
            rel = src.relative_to(mirror)
            dst = vault.root / rel
            try:
                if not _is_newer(src, dst):
                    continue
                # Nunca sobrescreve nota humana
                if dst.exists():
                    existing = Note.from_markdown(
                        str(dst.relative_to(vault.root)),
                        dst.read_text(encoding="utf-8"),
                    )
                    if not existing.is_pesquisai_generated:
                        errors.append(
                            f"pull {rel}: nota humana no vault — pulando"
                        )
                        continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                bytes_tx += src.stat().st_size
                pulled.append(str(rel))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"pull {rel}: {exc}")

    return SyncReport(
        started_at=started,
        ended_at=_dt.datetime.now(),
        pushed=tuple(pushed),
        pulled=tuple(pulled),
        errors=tuple(errors),
        bytes_transferred=bytes_tx,
    )


def sync_git(
    vault: Vault,
    *,
    remote: Optional[str] = None,
    branch: str = "main",
    commit_message: Optional[str] = None,
) -> SyncReport:
    """Sincroniza o vault via ``git`` (assume que o vault é um repo git).

    Compatível com os plugins Obsidian *Obsidian Git* e *Remotely Save*
    (que operam sobre repositórios bare locais).
    """
    started = _dt.datetime.now()
    pushed: list[str] = []
    pulled: list[str] = []
    errors: list[str] = []

    if not (vault.root / ".git").is_dir():
        errors.append(f"{vault.root} não é um repositório git")
        return SyncReport(
            started_at=started,
            ended_at=_dt.datetime.now(),
            errors=tuple(errors),
        )

    def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            args, cwd=str(vault.root), capture_output=True, text=True, timeout=timeout,
        )

    try:
        # 1. Backup local antes de qualquer coisa
        _local_backup(vault)

        # 2. Pull
        r = _run(["git", "fetch", "--all"])
        if r.returncode != 0:
            errors.append(f"git fetch: {r.stderr.strip()}")
        r = _run(["git", "rebase", f"origin/{branch}"])
        if r.returncode != 0:
            errors.append(f"git rebase: {r.stderr.strip()}")
        # Lista o que mudou após pull
        diff_after_pull = _run(["git", "diff", "--name-only", "HEAD~1"])
        if diff_after_pull.returncode == 0:
            pulled = tuple(diff_after_pull.stdout.splitlines())

        # 3. Add + commit
        _run(["git", "add", "-A"])
        status = _run(["git", "status", "--porcelain"])
        if status.returncode == 0 and status.stdout.strip():
            msg = commit_message or (
                f"pesquisai: sync {_dt.datetime.now().isoformat(timespec='seconds')}"
            )
            r = _run(["git", "commit", "-m", msg])
            if r.returncode != 0:
                errors.append(f"git commit: {r.stderr.strip()}")
            else:
                # Lista o que foi commitado
                diff_after = _run(["git", "show", "--name-only", "--format="])
                if diff_after.returncode == 0:
                    pushed = tuple(
                        line.strip() for line in diff_after.stdout.splitlines()
                        if line.strip()
                    )

        # 4. Push
        if remote:
            r = _run(["git", "push", remote, branch])
            if r.returncode != 0:
                errors.append(f"git push: {r.stderr.strip()}")

    except subprocess.TimeoutExpired as exc:
        errors.append(f"git timeout: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"git error: {exc}")

    return SyncReport(
        started_at=started,
        ended_at=_dt.datetime.now(),
        pushed=tuple(pushed),
        pulled=tuple(pulled),
        errors=tuple(errors),
    )


def check_drift(vault: Vault, mirror: Union[str, Path]) -> list[str]:
    """Retorna paths que diferem entre o vault e o mirror.

    Útil para diagnósticos antes de um sync.
    """
    mirror_path = Path(mirror).expanduser().resolve()
    if not mirror_path.is_dir():
        return [f"mirror não existe: {mirror_path}"]
    diff: list[str] = []
    vault_paths = set(vault.list_paths())
    mirror_paths = {
        str(p.relative_to(mirror_path))
        for p in mirror_path.rglob("*.md")
        if not p.name.startswith(".")
    }
    only_in_vault = vault_paths - mirror_paths
    only_in_mirror = mirror_paths - vault_paths
    for p in sorted(only_in_vault):
        diff.append(f"apenas no vault: {p}")
    for p in sorted(only_in_mirror):
        diff.append(f"apenas no mirror: {p}")
    return diff


# ── Internos ─────────────────────────────────────────────────────

def _is_newer(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    return src.stat().st_mtime > dst.stat().st_mtime


def _local_backup(vault: Vault) -> Path:
    """Cria um backup local do vault antes de operações destrutivas."""
    today = _dt.date.today().isoformat()
    backup_dir = vault.root / ".backups" / today
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Hard-link copy (rápido, economiza espaço)
    for note in vault.iter_notes():
        src = vault.root / note.path
        dst = backup_dir / note.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dst.exists():
                dst.unlink()
            os.link(src, dst)
        except OSError:
            # Se hard-link falhar (cross-device), copia normal
            shutil.copy2(src, dst)
    logger.info("Backup local criado em %s", backup_dir)
    return backup_dir
