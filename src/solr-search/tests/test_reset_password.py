# ruff: noqa: S106
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import hash_password, init_auth_db  # noqa: E402
from reset_password import (  # noqa: E402
    DEFAULT_DB_PATH,
    GENERATED_PASSWORD_LENGTH,
    _resolve_db_path,
    generate_password,
    main,
    reset_password,
)  # noqa: I001

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def auth_db(tmp_path: Path) -> Path:
    """Create a fresh auth DB with one admin user."""
    db_path = tmp_path / "users.db"
    init_auth_db(db_path)
    pw_hash = hash_password("OldPass123!")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", pw_hash, "admin"),
        )
        conn.commit()
    return db_path


# ── generate_password ─────────────────────────────────────────────────


def test_generate_password_default_length() -> None:
    pw = generate_password()
    assert len(pw) == GENERATED_PASSWORD_LENGTH


def test_generate_password_custom_length() -> None:
    pw = generate_password(64)
    assert len(pw) == 64


def test_generate_password_unique() -> None:
    passwords = {generate_password() for _ in range(20)}
    assert len(passwords) == 20


# ── reset_password (library function) ─────────────────────────────────


def test_reset_password_updates_hash(auth_db: Path) -> None:
    from argon2 import PasswordHasher

    ph = PasswordHasher()

    assert reset_password(auth_db, "admin", "NewPass456!") is True

    with sqlite3.connect(auth_db) as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()
    assert row is not None
    assert ph.verify(row[0], "NewPass456!") is True


def test_reset_password_returns_false_for_unknown_user(auth_db: Path) -> None:
    assert reset_password(auth_db, "nonexistent", "StrongPw99!") is False


def test_reset_password_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        reset_password(tmp_path / "missing.db", "admin", "StrongPw99!")


def test_reset_password_not_a_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a file"):
        reset_password(tmp_path, "admin", "StrongPw99!")


def test_reset_password_corrupt_db(tmp_path: Path) -> None:
    bad_db = tmp_path / "bad.db"
    bad_db.write_bytes(b"this is not a sqlite database at all!!!!")
    with pytest.raises(ValueError, match="corrupt|Cannot"):
        reset_password(bad_db, "admin", "StrongPw99!")


def test_reset_password_missing_users_table(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
        conn.commit()
    with pytest.raises(ValueError, match="users"):
        reset_password(db_path, "admin", "StrongPw99!")


# ── _resolve_db_path ──────────────────────────────────────────────────


def test_resolve_db_path_cli_arg(tmp_path: Path) -> None:
    p = tmp_path / "custom.db"
    assert _resolve_db_path(p) == p.resolve()


def test_resolve_db_path_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTH_DB_PATH", str(tmp_path / "env.db"))
    assert _resolve_db_path(None) == (tmp_path / "env.db").resolve()


def test_resolve_db_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_DB_PATH", raising=False)
    assert _resolve_db_path(None) == DEFAULT_DB_PATH


# ── CLI (main) ────────────────────────────────────────────────────────


def test_cli_with_explicit_password(auth_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--db-path", str(auth_db), "--password", "CliPass123!"])
    assert rc == 0
    assert "reset" in capsys.readouterr().err


def test_cli_generates_password_when_omitted(auth_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--db-path", str(auth_db)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "reset" in captured.err
    # Generated password written to stdout via buffer
    generated_pw = captured.out.strip()
    assert len(generated_pw) == GENERATED_PASSWORD_LENGTH


def test_cli_missing_db_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--db-path", str(tmp_path / "gone.db"), "--password", "StrongPw99!"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_cli_unknown_user_returns_error(auth_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--db-path", str(auth_db), "--username", "ghost", "--password", "StrongPw99!"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_cli_corrupt_db_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not-sqlite-at-all!!!!!!!!!!!!!!!!!!!!!!!")
    rc = main(["--db-path", str(bad), "--password", "StrongPw99!"])
    assert rc == 1
    assert "Error" in capsys.readouterr().err


def test_cli_password_actually_works(auth_db: Path) -> None:
    """After CLI reset, the user can authenticate with the new password."""
    from auth import authenticate_user

    main(["--db-path", str(auth_db), "--password", "RoundTrip99!"])
    user = authenticate_user(auth_db, "admin", "RoundTrip99!")
    assert user is not None
    assert user.username == "admin"


def test_reset_password_rejects_weak_password(auth_db: Path) -> None:
    """reset_password should reject passwords that violate the policy."""
    from auth import PasswordPolicyError

    with pytest.raises(PasswordPolicyError):
        reset_password(auth_db, "admin", "short")
