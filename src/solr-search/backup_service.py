"""Backup/Restore management service for Aithena BCDR.

Provides in-memory state tracking for backup and restore operations,
backup inventory scanning, and subprocess execution for backup scripts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("aithena.backup")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TIERS = frozenset({"critical", "high", "medium", "all"})
BACKUP_BASE_DIR = Path(os.environ.get("BACKUP_DEST", "/source/backups"))
SCRIPTS_DIR = Path(os.environ.get("BACKUP_SCRIPTS_DIR", "/source/aithena/scripts"))


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class BackupTier(Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    all = "all"


class OperationStatus(Enum):
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class BackupRequest(BaseModel):
    tier: BackupTier = BackupTier.all
    dry_run: bool = False


class RestoreRequest(BaseModel):
    backup_id: str
    dry_run: bool = False


class BackupInfo(BaseModel):
    id: str
    tier: str
    timestamp: str
    path: str
    size_bytes: int = 0
    files: list[str] = Field(default_factory=list)


class OperationRecord(BaseModel):
    id: str
    operation: str  # "backup" or "restore"
    tier: str
    status: OperationStatus
    started_at: str
    finished_at: str | None = None
    dry_run: bool = False
    error: str | None = None
    backup_id: str | None = None


class BackupStatusResponse(BaseModel):
    tiers: dict[str, dict[str, Any]]


class BackupListResponse(BaseModel):
    backups: list[BackupInfo]
    total: int


class BackupConfigRequest(BaseModel):
    retention_days: int | None = None
    tier: BackupTier | None = None


class BackupConfig(BaseModel):
    retention_days: int = 7
    backup_base_dir: str = str(BACKUP_BASE_DIR)
    scripts_dir: str = str(SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# In-memory operation tracking
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_operations: dict[str, OperationRecord] = {}
_config = BackupConfig()


def _record_operation(record: OperationRecord) -> None:
    with _lock:
        _operations[record.id] = record


def get_operation(operation_id: str) -> OperationRecord | None:
    with _lock:
        return _operations.get(operation_id)


def list_operations(
    operation_type: str | None = None,
    limit: int = 50,
) -> list[OperationRecord]:
    with _lock:
        ops = list(_operations.values())
    if operation_type:
        ops = [o for o in ops if o.operation == operation_type]
    ops.sort(key=lambda o: o.started_at, reverse=True)
    return ops[:limit]


def get_config() -> BackupConfig:
    with _lock:
        return _config.model_copy()


def update_config(updates: BackupConfigRequest) -> BackupConfig:
    global _config  # noqa: PLW0603
    with _lock:
        data = _config.model_dump()
        if updates.retention_days is not None:
            data["retention_days"] = updates.retention_days
        _config = BackupConfig(**data)
        return _config.model_copy()


# ---------------------------------------------------------------------------
# Backup directory scanning
# ---------------------------------------------------------------------------

_TIMESTAMP_PATTERN = re.compile(r"(\d{8}-\d{4})")


def _dir_size(path: Path) -> int:
    """Return total size in bytes of all files under *path*."""
    total = 0
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def _list_files(path: Path) -> list[str]:
    """Return relative file paths under *path*."""
    if path.is_file():
        return [path.name]
    if path.is_dir():
        return sorted(str(f.relative_to(path)) for f in path.rglob("*") if f.is_file())
    return []


def scan_backups(base_dir: Path | None = None) -> list[BackupInfo]:
    """Scan backup directories and return inventory of available backups."""
    base = base_dir or Path(get_config().backup_base_dir)
    backups: list[BackupInfo] = []

    for tier in ("critical", "high", "medium"):
        tier_dir = base / tier
        if not tier_dir.is_dir():
            continue

        for entry in sorted(tier_dir.iterdir(), reverse=True):
            if entry.name.startswith("."):
                continue
            match = _TIMESTAMP_PATTERN.search(entry.name)
            timestamp = match.group(1) if match else entry.name
            backup_id = f"{tier}-{entry.name}"
            backups.append(
                BackupInfo(
                    id=backup_id,
                    tier=tier,
                    timestamp=timestamp,
                    path=str(entry),
                    size_bytes=_dir_size(entry),
                    files=_list_files(entry),
                )
            )

    backups.sort(key=lambda b: b.timestamp, reverse=True)
    return backups


def get_backup_by_id(backup_id: str, base_dir: Path | None = None) -> BackupInfo | None:
    """Find a specific backup by its ID."""
    for backup in scan_backups(base_dir):
        if backup.id == backup_id:
            return backup
    return None


def get_tier_status(base_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return per-tier status summary: last backup, count, total size."""
    all_backups = scan_backups(base_dir)
    result: dict[str, dict[str, Any]] = {}

    for tier in ("critical", "high", "medium"):
        tier_backups = [b for b in all_backups if b.tier == tier]
        last = tier_backups[0] if tier_backups else None

        last_op = None
        with _lock:
            for op in sorted(_operations.values(), key=lambda o: o.started_at, reverse=True):
                if op.tier == tier and op.operation == "backup":
                    last_op = op
                    break

        result[tier] = {
            "backup_count": len(tier_backups),
            "total_size_bytes": sum(b.size_bytes for b in tier_backups),
            "last_backup_timestamp": last.timestamp if last else None,
            "last_operation_status": last_op.status.value if last_op else None,
            "last_operation_id": last_op.id if last_op else None,
        }

    return result


# ---------------------------------------------------------------------------
# Subprocess execution
# ---------------------------------------------------------------------------


async def run_backup(tier: BackupTier, dry_run: bool = False) -> OperationRecord:
    """Trigger a backup subprocess and track its progress."""
    operation_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    record = OperationRecord(
        id=operation_id,
        operation="backup",
        tier=tier.value,
        status=OperationStatus.in_progress,
        started_at=now,
        dry_run=dry_run,
    )
    _record_operation(record)

    asyncio.create_task(_execute_backup(operation_id, tier, dry_run))
    return record


async def _execute_backup(operation_id: str, tier: BackupTier, dry_run: bool) -> None:
    """Execute the backup script as a subprocess."""
    config = get_config()
    script = Path(config.scripts_dir) / "backup.sh"

    cmd = [str(script), "--tier", tier.value]
    if dry_run:
        cmd.append("--dry-run")

    env = {**os.environ, "BACKUP_DEST": config.backup_base_dir}

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        now = datetime.now(UTC).isoformat()
        with _lock:
            record = _operations[operation_id]
            if process.returncode == 0:
                updated = record.model_copy(
                    update={"status": OperationStatus.completed, "finished_at": now}
                )
            else:
                error_msg = stderr.decode(errors="replace").strip() or f"Exit code {process.returncode}"
                updated = record.model_copy(
                    update={
                        "status": OperationStatus.failed,
                        "finished_at": now,
                        "error": error_msg[:500],
                    }
                )
            _operations[operation_id] = updated

        logger.info("Backup %s finished: %s", operation_id, updated.status.value)

    except Exception as exc:
        now = datetime.now(UTC).isoformat()
        with _lock:
            record = _operations[operation_id]
            _operations[operation_id] = record.model_copy(
                update={
                    "status": OperationStatus.failed,
                    "finished_at": now,
                    "error": str(exc)[:500],
                }
            )
        logger.exception("Backup %s failed with exception", operation_id)


async def run_restore(backup_id: str, dry_run: bool = False) -> OperationRecord:
    """Trigger a restore subprocess and track its progress."""
    backup = get_backup_by_id(backup_id)
    if backup is None:
        raise ValueError(f"Backup not found: {backup_id}")

    operation_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    record = OperationRecord(
        id=operation_id,
        operation="restore",
        tier=backup.tier,
        status=OperationStatus.in_progress,
        started_at=now,
        dry_run=dry_run,
        backup_id=backup_id,
    )
    _record_operation(record)

    asyncio.create_task(_execute_restore(operation_id, backup, dry_run))
    return record


async def _execute_restore(operation_id: str, backup: BackupInfo, dry_run: bool) -> None:
    """Execute the appropriate restore script as a subprocess."""
    config = get_config()
    script_name = f"restore-{backup.tier}.sh"
    script = Path(config.scripts_dir) / script_name

    if not script.exists():
        script = Path(config.scripts_dir) / "restore.sh"

    env = {
        **os.environ,
        "BACKUP_DEST": config.backup_base_dir,
        "RESTORE_SOURCE": backup.path,
    }
    if dry_run:
        env["DRY_RUN"] = "1"

    cmd = [str(script)]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        now = datetime.now(UTC).isoformat()
        with _lock:
            record = _operations[operation_id]
            if process.returncode == 0:
                updated = record.model_copy(
                    update={"status": OperationStatus.completed, "finished_at": now}
                )
            else:
                error_msg = stderr.decode(errors="replace").strip() or f"Exit code {process.returncode}"
                updated = record.model_copy(
                    update={
                        "status": OperationStatus.failed,
                        "finished_at": now,
                        "error": error_msg[:500],
                    }
                )
            _operations[operation_id] = updated

        logger.info("Restore %s finished: %s", operation_id, updated.status.value)

    except Exception as exc:
        now = datetime.now(UTC).isoformat()
        with _lock:
            record = _operations[operation_id]
            _operations[operation_id] = record.model_copy(
                update={
                    "status": OperationStatus.failed,
                    "finished_at": now,
                    "error": str(exc)[:500],
                }
            )
        logger.exception("Restore %s failed with exception", operation_id)


async def run_test_restore(dry_run: bool = True) -> OperationRecord:
    """Run an automated restore drill using the most recent backup."""
    backups = scan_backups()
    if not backups:
        raise ValueError("No backups available for test restore")

    latest = backups[0]
    operation_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    record = OperationRecord(
        id=operation_id,
        operation="test-restore",
        tier=latest.tier,
        status=OperationStatus.in_progress,
        started_at=now,
        dry_run=dry_run,
        backup_id=latest.id,
    )
    _record_operation(record)

    asyncio.create_task(_execute_restore(operation_id, latest, dry_run=dry_run))
    return record


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Clear all in-memory state. Only for testing."""
    global _config  # noqa: PLW0603
    with _lock:
        _operations.clear()
        _config = BackupConfig()
