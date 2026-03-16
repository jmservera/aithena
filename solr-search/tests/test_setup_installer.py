# ruff: noqa: I001, S105, S106, S108

from __future__ import annotations

import sqlite3
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

SOLR_SEARCH_DIR = ROOT / "solr-search"
if str(SOLR_SEARCH_DIR) not in sys.path:
    sys.path.append(str(SOLR_SEARCH_DIR))

from auth import authenticate_user  # noqa: E402
from installer.setup import (  # noqa: E402
    InstallerConfig,
    _reject_control_chars,
    load_env_file,
    normalize_username,
    resolve_auth_db_path,
    resolve_library_path,
    run_setup,
    write_env_file,
)


def fake_secret(_: int) -> str:
    return "generated-secret-value"


def test_run_setup_writes_env_and_hashes_password(tmp_path: Path) -> None:
    library_path = tmp_path / "library"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "state" / "users.db"

    result = run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="correct-horse-battery-staple",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=fake_secret,
    )

    env_values = load_env_file(env_path)
    assert result.generated_jwt_secret is True
    assert env_values["BOOKS_PATH"] == str(library_path.resolve())
    assert env_values["BOOK_LIBRARY_PATH"] == str(library_path.resolve())
    assert env_values["AUTH_DB_DIR"] == str(auth_db_path.resolve().parent)
    assert env_values["AUTH_DB_PATH"] == "/data/auth/users.db"
    assert env_values["AUTH_JWT_SECRET"] == "generated-secret-value"
    assert env_values["CORS_ORIGINS"] == "http://localhost"
    assert authenticate_user(auth_db_path, "admin", "correct-horse-battery-staple") is not None

    with sqlite3.connect(auth_db_path) as connection:
        row = connection.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            ("admin",),
        ).fetchone()

    assert row[0] == "admin"
    assert row[2] == "admin"
    assert row[1] != "correct-horse-battery-staple"
    assert row[1].startswith("$argon2id$")


def test_placeholder_secret_is_regenerated(tmp_path: Path) -> None:
    library_path = tmp_path / "library"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "state" / "users.db"
    env_path.write_text(
        "\n".join(
            [
                "BOOKS_PATH=/tmp/library",
                "PUBLIC_ORIGIN=http://localhost",
                "AUTH_DB_DIR=/tmp/auth",
                "AUTH_DB_PATH=/data/auth/users.db",
                "AUTH_JWT_SECRET=generate-with-installer",
                "AUTH_ADMIN_USERNAME=admin",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="replacement-password",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=lambda _: "fresh-generated-secret",
    )

    env_values = load_env_file(env_path)
    assert result.generated_jwt_secret is True
    assert env_values["AUTH_JWT_SECRET"] == "fresh-generated-secret"


def test_rerun_preserves_existing_secret_and_users(tmp_path: Path) -> None:
    library_path = tmp_path / "library"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "state" / "users.db"

    run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="first-password",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=fake_secret,
    )

    with sqlite3.connect(auth_db_path) as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("other-user", "$argon2id$preserved", "reader"),
        )
        connection.commit()

    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            "AUTH_JWT_SECRET=generated-secret-value",
            "AUTH_JWT_SECRET=keep-existing-secret",
        ),
        encoding="utf-8",
    )

    result = run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="second-password",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=lambda _: "new-secret-should-not-be-used",
    )

    env_values = load_env_file(env_path)
    assert result.generated_jwt_secret is False
    assert env_values["AUTH_JWT_SECRET"] == "keep-existing-secret"
    assert authenticate_user(auth_db_path, "admin", "second-password") is not None

    with sqlite3.connect(auth_db_path) as connection:
        usernames = [row[0] for row in connection.execute("SELECT username FROM users ORDER BY username")]

    assert usernames == ["admin", "other-user"]


def test_reset_recreates_auth_db(tmp_path: Path) -> None:
    library_path = tmp_path / "library"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "state" / "users.db"

    run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="first-password",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=lambda _: "first-secret",
    )

    with sqlite3.connect(auth_db_path) as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("legacy-user", "$argon2id$legacy", "reader"),
        )
        connection.commit()

    result = run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="fresh-password",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
            reset=True,
        ),
        interactive=False,
        secret_factory=lambda _: "second-secret",
    )

    env_values = load_env_file(env_path)
    assert result.admin_action == "created"
    assert result.generated_jwt_secret is True
    assert env_values["AUTH_JWT_SECRET"] == "second-secret"
    assert authenticate_user(auth_db_path, "admin", "fresh-password") is not None

    with sqlite3.connect(auth_db_path) as connection:
        usernames = [row[0] for row in connection.execute("SELECT username FROM users ORDER BY username")]

    assert usernames == ["admin"]


# ---------------------------------------------------------------------------
# Security regression tests — blocker #1: control-character injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_input",
    [
        "path/with\nnewline",
        "path/with\rcarriage-return",
        "path/with\r\nboth",
        "path/with\x00nul",
        "path/with\x1besc",
    ],
)
def test_reject_control_chars_helper(bad_input: str) -> None:
    with pytest.raises(ValueError, match="control characters"):
        _reject_control_chars(bad_input, "field")


@pytest.mark.parametrize(
    "bad_input",
    [
        "/srv/library\nINJECTED=1",
        "/srv/library\rINJECTED=1",
    ],
)
def test_resolve_library_path_rejects_control_chars(bad_input: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="control characters"):
        resolve_library_path(bad_input)


@pytest.mark.parametrize(
    "bad_input",
    [
        "/srv/auth/users.db\nINJECTED=1",
        "/srv/auth/users.db\rINJECTED=1",
    ],
)
def test_resolve_auth_db_path_rejects_control_chars(bad_input: str) -> None:
    with pytest.raises(ValueError, match="control characters"):
        resolve_auth_db_path(bad_input)


@pytest.mark.parametrize(
    "bad_input",
    [
        "admin\nINJECTED=1",
        "admin\rINJECTED=1",
    ],
)
def test_normalize_username_rejects_control_chars(bad_input: str) -> None:
    with pytest.raises(ValueError, match="control characters"):
        normalize_username(bad_input)


def test_write_env_file_rejects_newline_in_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    values = {
        "BOOKS_PATH": "/srv/library\nINJECTED=evil",
        "BOOK_LIBRARY_PATH": "/srv/library",
        "PUBLIC_ORIGIN": "http://localhost",
        "CORS_ORIGINS": "http://localhost",
        "AUTH_DB_DIR": "/srv/auth",
        "AUTH_DB_PATH": "/data/auth/users.db",
        "AUTH_JWT_SECRET": "some-secret",
        "AUTH_JWT_TTL": "24h",
        "AUTH_COOKIE_NAME": "aithena_auth",
        "AUTH_ADMIN_USERNAME": "admin",
        "VERSION": "dev",
        "GIT_COMMIT": "abc123",
        "BUILD_DATE": "2026-01-01T00:00:00Z",
    }
    with pytest.raises(ValueError, match="newline"):
        write_env_file(env_path, values)


# ---------------------------------------------------------------------------
# Security regression tests — blocker #2: file permissions
# ---------------------------------------------------------------------------


def test_env_file_has_restricted_permissions(tmp_path: Path) -> None:
    library_path = tmp_path / "library"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "state" / "users.db"

    run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="correct-horse-battery-staple",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=lambda _: "test-secret",
    )

    env_perms = stat.S_IMODE(env_path.stat().st_mode)
    assert env_perms == 0o600, f".env has mode {oct(env_perms)}, expected 0o600"


def test_auth_dir_and_db_have_restricted_permissions(tmp_path: Path) -> None:
    library_path = tmp_path / "library"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "state" / "users.db"

    run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="correct-horse-battery-staple",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=lambda _: "test-secret",
    )

    dir_perms = stat.S_IMODE(auth_db_path.parent.stat().st_mode)
    db_perms = stat.S_IMODE(auth_db_path.stat().st_mode)
    assert dir_perms == 0o700, f"auth dir has mode {oct(dir_perms)}, expected 0o700"
    assert db_perms == 0o600, f"users.db has mode {oct(db_perms)}, expected 0o600"
