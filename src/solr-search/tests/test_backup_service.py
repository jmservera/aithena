"""Tests for backup/restore API endpoints and backup_service module."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import backup_service  # noqa: E402
import pytest  # noqa: E402
from backup_service import (  # noqa: E402
    BackupConfig,
    BackupConfigRequest,
    BackupTier,
    OperationRecord,
    OperationStatus,
    _reset_state,
    get_backup_by_id,
    get_config,
    get_tier_status,
    list_operations,
    scan_backups,
    update_config,
)

from tests.auth_helpers import create_authenticated_client  # noqa: E402

ADMIN_API_KEY = "test-backup-admin-key"


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset backup service state before each test."""
    _reset_state()
    yield
    _reset_state()


@pytest.fixture()
def client():
    """Return an authenticated TestClient with admin API key."""
    with patch("admin_auth._get_admin_api_key", return_value=ADMIN_API_KEY):
        c = create_authenticated_client()
        c.headers["x-api-key"] = ADMIN_API_KEY
        yield c


@pytest.fixture()
def backup_tree(tmp_path: Path):
    """Create a fake backup directory tree for scanning."""
    for tier in ("critical", "high", "medium"):
        tier_dir = tmp_path / tier
        tier_dir.mkdir()
        for i, ts in enumerate(["20240115-0200", "20240116-0200"]):
            entry = tier_dir / ts
            entry.mkdir()
            (entry / f"backup-{tier}-{i}.dat").write_text(f"data-{tier}-{i}")
    return tmp_path


class TestScanBackups:
    def test_empty_dir(self, tmp_path: Path):
        assert scan_backups(tmp_path) == []

    def test_scans_tiers(self, backup_tree: Path):
        backups = scan_backups(backup_tree)
        assert len(backups) == 6

    def test_backup_has_correct_fields(self, backup_tree: Path):
        backups = scan_backups(backup_tree)
        b = backups[0]
        assert b.tier in ("critical", "high", "medium")
        assert b.id.startswith(f"{b.tier}-")
        assert b.size_bytes > 0
        assert len(b.files) > 0

    def test_sorted_by_timestamp_descending(self, backup_tree: Path):
        backups = scan_backups(backup_tree)
        timestamps = [b.timestamp for b in backups]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_hidden_dirs_excluded(self, backup_tree: Path):
        (backup_tree / "critical" / ".hidden-backup").mkdir()
        backups = scan_backups(backup_tree)
        assert not any(".hidden" in b.id for b in backups)


class TestGetBackupById:
    def test_found(self, backup_tree: Path):
        backups = scan_backups(backup_tree)
        target = backups[0]
        result = get_backup_by_id(target.id, backup_tree)
        assert result is not None
        assert result.id == target.id

    def test_not_found(self, backup_tree: Path):
        assert get_backup_by_id("nonexistent-backup", backup_tree) is None


class TestTierStatus:
    def test_returns_all_tiers(self, backup_tree: Path):
        status = get_tier_status(backup_tree)
        assert set(status.keys()) == {"critical", "high", "medium"}

    def test_tier_counts(self, backup_tree: Path):
        status = get_tier_status(backup_tree)
        for tier_info in status.values():
            assert tier_info["backup_count"] == 2

    def test_empty_dir(self, tmp_path: Path):
        status = get_tier_status(tmp_path)
        for tier_info in status.values():
            assert tier_info["backup_count"] == 0
            assert tier_info["last_backup_timestamp"] is None


class TestOperationTracking:
    def test_list_operations_empty(self):
        assert list_operations() == []

    def test_record_and_list(self):
        record = OperationRecord(
            id="op-1",
            operation="backup",
            tier="critical",
            status=OperationStatus.completed,
            started_at="2024-01-15T02:00:00Z",
            finished_at="2024-01-15T02:01:00Z",
        )
        backup_service._record_operation(record)
        ops = list_operations()
        assert len(ops) == 1
        assert ops[0].id == "op-1"

    def test_filter_by_type(self):
        backup_service._record_operation(
            OperationRecord(
                id="op-b", operation="backup", tier="high",
                status=OperationStatus.completed, started_at="2024-01-15T02:00:00Z",
            )
        )
        backup_service._record_operation(
            OperationRecord(
                id="op-r", operation="restore", tier="high",
                status=OperationStatus.completed, started_at="2024-01-15T03:00:00Z",
            )
        )
        assert len(list_operations("backup")) == 1
        assert len(list_operations("restore")) == 1


class TestConfig:
    def test_default_config(self):
        config = get_config()
        assert config.retention_days == 7

    def test_update_retention(self):
        updated = update_config(BackupConfigRequest(retention_days=30))
        assert updated.retention_days == 30
        assert get_config().retention_days == 30

    def test_partial_update(self):
        update_config(BackupConfigRequest(retention_days=14))
        updated = update_config(BackupConfigRequest(tier=BackupTier.critical))
        assert updated.retention_days == 14


class TestListBackupsEndpoint:
    def test_returns_200(self, client, backup_tree):
        with patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(backup_tree))):
            resp = client.get("/v1/admin/backups")
        assert resp.status_code == 200
        data = resp.json()
        assert "backups" in data
        assert "total" in data
        assert data["total"] == 6

    def test_empty(self, client, tmp_path):
        with patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(tmp_path))):
            resp = client.get("/v1/admin/backups")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_requires_admin_api_key(self):
        with patch("admin_auth._get_admin_api_key", return_value=ADMIN_API_KEY):
            c = create_authenticated_client()
            resp = c.get("/v1/admin/backups")
        assert resp.status_code == 401


class TestTriggerBackupEndpoint:
    def test_returns_operation_record(self, client):
        with patch("main.run_backup", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = OperationRecord(
                id="op-123",
                operation="backup",
                tier="all",
                status=OperationStatus.in_progress,
                started_at="2024-01-15T02:00:00Z",
            )
            resp = client.post("/v1/admin/backups", json={"tier": "all"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "op-123"
        assert data["status"] == "in_progress"

    def test_invalid_tier(self, client):
        resp = client.post("/v1/admin/backups", json={"tier": "invalid"})
        assert resp.status_code == 422

    def test_dry_run(self, client):
        with patch("main.run_backup", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = OperationRecord(
                id="op-dry",
                operation="backup",
                tier="critical",
                status=OperationStatus.in_progress,
                started_at="2024-01-15T02:00:00Z",
                dry_run=True,
            )
            resp = client.post("/v1/admin/backups", json={"tier": "critical", "dry_run": True})
        assert resp.status_code == 200
        assert resp.json()["dry_run"] is True


class TestBackupStatusEndpoint:
    def test_returns_tier_status(self, client, backup_tree):
        with patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(backup_tree))):
            resp = client.get("/v1/admin/backups/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "tiers" in data
        assert set(data["tiers"].keys()) == {"critical", "high", "medium"}


class TestBackupDetailEndpoint:
    def test_found(self, client, backup_tree):
        with patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(backup_tree))):
            list_resp = client.get("/v1/admin/backups")
            backup_id = list_resp.json()["backups"][0]["id"]
            resp = client.get(f"/v1/admin/backups/{backup_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == backup_id

    def test_not_found(self, client, tmp_path):
        with patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(tmp_path))):
            resp = client.get("/v1/admin/backups/nonexistent-id")
        assert resp.status_code == 404


class TestRestoreEndpoint:
    def test_returns_operation_record(self, client, backup_tree):
        with (
            patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(backup_tree))),
            patch("main.run_restore", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = OperationRecord(
                id="op-restore-1",
                operation="restore",
                tier="critical",
                status=OperationStatus.in_progress,
                started_at="2024-01-15T03:00:00Z",
                backup_id="critical-20240116-0200",
            )
            resp = client.post(
                "/v1/admin/backups/critical-20240116-0200/restore",
                json={"backup_id": "critical-20240116-0200"},
            )
        assert resp.status_code == 200
        assert resp.json()["operation"] == "restore"

    def test_not_found(self, client, tmp_path):
        with (
            patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(tmp_path))),
            patch(
                "main.run_restore",
                new_callable=AsyncMock,
                side_effect=ValueError("Backup not found: bad-id"),
            ),
        ):
            resp = client.post(
                "/v1/admin/backups/bad-id/restore",
                json={"backup_id": "bad-id"},
            )
        assert resp.status_code == 404


class TestBackupConfigEndpoint:
    def test_get_config(self, client):
        resp = client.get("/v1/admin/backups/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "retention_days" in data

    def test_update_config(self, client):
        resp = client.put("/v1/admin/backups/config", json={"retention_days": 30})
        assert resp.status_code == 200
        assert resp.json()["retention_days"] == 30


class TestTestRestoreEndpoint:
    def test_returns_operation(self, client, backup_tree):
        with (
            patch.object(backup_service, "_config", BackupConfig(backup_base_dir=str(backup_tree))),
            patch("main.run_test_restore", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = OperationRecord(
                id="op-test-1",
                operation="test-restore",
                tier="critical",
                status=OperationStatus.in_progress,
                started_at="2024-01-15T04:00:00Z",
                dry_run=True,
            )
            resp = client.post("/v1/admin/backups/test-restore")
        assert resp.status_code == 200
        assert resp.json()["operation"] == "test-restore"

    def test_no_backups_returns_404(self, client, tmp_path):
        with patch(
            "main.run_test_restore",
            new_callable=AsyncMock,
            side_effect=ValueError("No backups available for test restore"),
        ):
            resp = client.post("/v1/admin/backups/test-restore")
        assert resp.status_code == 404


class TestAuthRequired:
    """All backup endpoints require admin API key auth."""

    ENDPOINTS = [
        ("GET", "/v1/admin/backups"),
        ("POST", "/v1/admin/backups"),
        ("GET", "/v1/admin/backups/status"),
        ("GET", "/v1/admin/backups/config"),
        ("PUT", "/v1/admin/backups/config"),
        ("POST", "/v1/admin/backups/test-restore"),
        ("GET", "/v1/admin/backups/some-id"),
        ("POST", "/v1/admin/backups/some-id/restore"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_returns_403_when_api_key_not_configured(self, method, path):
        with patch("admin_auth._get_admin_api_key", return_value=None):
            c = create_authenticated_client()
            resp = getattr(c, method.lower())(path)
        assert resp.status_code == 403

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_returns_401_without_api_key_header(self, method, path):
        with patch("admin_auth._get_admin_api_key", return_value=ADMIN_API_KEY):
            c = create_authenticated_client()
            resp = getattr(c, method.lower())(path)
        assert resp.status_code == 401
