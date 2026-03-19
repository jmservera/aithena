"""Tests for auth DB migration framework and schema versioning."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import SCHEMA_VERSION, get_schema_version, init_auth_db  # noqa: E402
from migrations import _discover_migrations, apply_pending_migrations  # noqa: E402


def test_init_auth_db_creates_schema_version_table(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.db"
    init_auth_db(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "schema_version" in tables
    assert "users" in tables


def test_init_auth_db_sets_initial_version(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.db"
    init_auth_db(db_path)

    assert get_schema_version(db_path) == SCHEMA_VERSION


def test_init_auth_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.db"
    init_auth_db(db_path)
    init_auth_db(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert rows == 1


def test_get_schema_version_returns_zero_for_unversioned_db(tmp_path: Path) -> None:
    db_path = tmp_path / "does_not_exist.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE dummy (id INTEGER)")
    assert get_schema_version(db_path) == 0


def test_discover_migrations_returns_sorted_list() -> None:
    migrations = _discover_migrations()
    if migrations:
        versions = [m.VERSION for m in migrations]
        assert versions == sorted(versions)


def test_apply_pending_migrations_with_no_migrations(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.db"
    init_auth_db(db_path)
    applied = apply_pending_migrations(db_path)
    assert applied == 0


def test_migration_applies_correctly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a migration by creating a temporary module."""
    db_path = tmp_path / "auth.db"
    init_auth_db(db_path)

    import types

    fake_migration = types.ModuleType("migrations.m0002_test")
    fake_migration.VERSION = 2
    fake_migration.DESCRIPTION = "Test migration"
    fake_migration.upgrade = lambda conn: conn.execute(  # noqa: ARG005
        "ALTER TABLE users ADD COLUMN email TEXT DEFAULT NULL"
    )

    import migrations

    original_discover = migrations._discover_migrations
    monkeypatch.setattr(migrations, "_discover_migrations", lambda: [fake_migration])

    applied = apply_pending_migrations(db_path)

    assert applied == 1
    assert get_schema_version(db_path) == 2

    with sqlite3.connect(db_path) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    assert "email" in cols

    monkeypatch.setattr(migrations, "_discover_migrations", original_discover)


def test_migration_skips_already_applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "auth.db"
    init_auth_db(db_path)

    import types

    fake_migration = types.ModuleType("migrations.m0002_test")
    fake_migration.VERSION = 2
    fake_migration.DESCRIPTION = "Test migration"
    call_count = 0

    def counted_upgrade(conn):
        nonlocal call_count
        call_count += 1
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT NULL")

    fake_migration.upgrade = counted_upgrade

    import migrations

    original_discover = migrations._discover_migrations
    monkeypatch.setattr(migrations, "_discover_migrations", lambda: [fake_migration])

    apply_pending_migrations(db_path)
    apply_pending_migrations(db_path)

    assert call_count == 1

    monkeypatch.setattr(migrations, "_discover_migrations", original_discover)
