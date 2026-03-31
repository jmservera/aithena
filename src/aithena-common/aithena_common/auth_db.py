"""SQLite auth database schema management and user lookup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1


def _ensure_schema_version_table(connection: sqlite3.Connection) -> None:
    """Create the schema_version tracking table if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
        """
    )


def get_schema_version(db_path: Path) -> int:
    """Return the current schema version, or 0 if unversioned."""
    with sqlite3.connect(db_path) as connection:
        try:
            row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0


def init_auth_db(db_path: Path) -> None:
    """Initialise the auth SQLite database (users + schema_version tables).

    NOTE: This does NOT run migrations or seed the default admin user.
    Those are solr-search domain concerns. Callers that need migrations
    should invoke the migrations framework separately.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_schema_version_table(connection)
        row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
        if row is None or row[0] is None:
            connection.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (SCHEMA_VERSION, "Initial schema: users table"),
            )
        connection.commit()


def find_user(db_path: Path, username: str) -> dict[str, str | int] | None:
    """Look up a user by username. Returns a dict or None if not found."""
    normalized = username.strip()
    if not normalized:
        return None

    if not db_path.exists():
        return None

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, username, role FROM users WHERE username = ?",
            (normalized,),
        ).fetchone()
        if row is None:
            return None
        return {"id": int(row["id"]), "username": str(row["username"]), "role": str(row["role"])}
