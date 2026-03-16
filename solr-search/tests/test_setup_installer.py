# ruff: noqa: I001, S105, S106

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

SOLR_SEARCH_DIR = ROOT / "solr-search"
if str(SOLR_SEARCH_DIR) not in sys.path:
    sys.path.append(str(SOLR_SEARCH_DIR))

from auth import authenticate_user  # noqa: E402
from installer.setup import InstallerConfig, load_env_file, run_setup  # noqa: E402


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


def test_env_injection_via_newline_in_username(tmp_path: Path) -> None:
    import pytest
    from installer.setup import normalize_username

    with pytest.raises(ValueError, match="invalid characters"):
        normalize_username("admin\nMALICIOUS_KEY=evil")


def test_env_file_strips_newlines_from_values(tmp_path: Path) -> None:
    from installer.setup import write_env_file, load_env_file

    env_path = tmp_path / ".env"
    values = {key: "normal" for key, _ in __import__("installer.setup", fromlist=["ENV_COMMENTS"]).ENV_COMMENTS}
    values["AUTH_JWT_SECRET"] = "secret\nINJECTED=bad"

    write_env_file(env_path, values)
    reloaded = load_env_file(env_path)

    assert "\n" not in reloaded["AUTH_JWT_SECRET"]
    assert "INJECTED" not in reloaded.get("INJECTED", "")


def test_env_file_has_restricted_permissions(tmp_path: Path) -> None:
    library_path = tmp_path / "lib"
    env_path = tmp_path / ".env"
    auth_db_path = tmp_path / "auth.db"

    run_setup(
        InstallerConfig(
            library_path=str(library_path),
            admin_user="admin",
            admin_password="test-pass-123",
            origin="http://localhost",
            auth_db_path=auth_db_path,
            env_path=env_path,
        ),
        interactive=False,
        secret_factory=fake_secret,
    )

    assert env_path.stat().st_mode & 0o077 == 0, ".env should be owner-only (0600)"
    assert auth_db_path.stat().st_mode & 0o077 == 0, "auth DB should be owner-only (0600)"
