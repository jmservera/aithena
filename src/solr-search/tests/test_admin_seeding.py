"""Tests for default admin user seeding on first startup (#550)."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")  # noqa: S105
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import hash_password, init_auth_db  # noqa: E402
from config import settings  # noqa: E402


@pytest.fixture
def seed_db(tmp_path: Path):
    """Provide a temp DB path and restore settings afterwards."""
    original_db = settings.auth_db_path
    original_username = settings.auth_default_admin_username
    original_password = settings.auth_default_admin_password
    db_path = tmp_path / "seed-test.db"
    object.__setattr__(settings, "auth_db_path", db_path)
    yield db_path
    object.__setattr__(settings, "auth_db_path", original_db)
    object.__setattr__(settings, "auth_default_admin_username", original_username)
    object.__setattr__(settings, "auth_default_admin_password", original_password)


def test_seeds_admin_when_password_set_and_table_empty(seed_db: Path) -> None:
    object.__setattr__(settings, "auth_default_admin_password", "Str0ngPass")
    object.__setattr__(settings, "auth_default_admin_username", "admin")

    init_auth_db(seed_db)

    with sqlite3.connect(seed_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT username, role FROM users").fetchone()
    assert row is not None
    assert row["username"] == "admin"
    assert row["role"] == "admin"


def test_seeds_with_custom_username(seed_db: Path) -> None:
    object.__setattr__(settings, "auth_default_admin_password", "Custom1Pass")
    object.__setattr__(settings, "auth_default_admin_username", "superadmin")

    init_auth_db(seed_db)

    with sqlite3.connect(seed_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT username FROM users").fetchone()
    assert row is not None
    assert row["username"] == "superadmin"


def test_skips_seeding_when_no_password_set(seed_db: Path) -> None:
    object.__setattr__(settings, "auth_default_admin_password", None)

    init_auth_db(seed_db)

    with sqlite3.connect(seed_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 0


def test_idempotent_skips_if_users_exist(seed_db: Path) -> None:
    object.__setattr__(settings, "auth_default_admin_password", "Str0ngPass")

    init_auth_db(seed_db)

    # Insert another user manually
    with sqlite3.connect(seed_db) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("extra", hash_password("Extra1Pass"), "viewer"),
        )
        conn.commit()

    # Re-init should not add another admin
    init_auth_db(seed_db)

    with sqlite3.connect(seed_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 2  # original admin + extra, no duplicate


def test_logs_warning_when_no_password(caplog, seed_db: Path) -> None:
    object.__setattr__(settings, "auth_default_admin_password", None)

    with caplog.at_level("WARNING"):
        init_auth_db(seed_db)

    assert any("AUTH_DEFAULT_ADMIN_PASSWORD" in record.message for record in caplog.records)


def test_logs_info_when_seeding(caplog, seed_db: Path) -> None:
    object.__setattr__(settings, "auth_default_admin_password", "Info1Test!")

    with caplog.at_level("INFO"):
        init_auth_db(seed_db)

    assert any("Default admin user" in record.message for record in caplog.records)
