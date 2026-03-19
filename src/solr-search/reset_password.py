"""CLI tool to reset the admin password in the solr-search auth database.

Usage examples:
    # Set a specific password:
    python reset_password.py --password "my-new-secret"

    # Generate a secure random password and print it:
    python reset_password.py

    # Use a custom DB path:
    python reset_password.py --db-path /data/auth/users.db --password "new-pass"

    # Target a specific user (default: admin):
    python reset_password.py --username admin --password "new-pass"
"""

from __future__ import annotations

import argparse
import secrets
import sqlite3
import string
import sys
from pathlib import Path

# Allow running both inside the service directory and from an arbitrary location.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from auth import hash_password  # noqa: E402

DEFAULT_DB_PATH = Path("/data/auth/users.db")
GENERATED_PASSWORD_LENGTH = 32
_SAFE_ALPHABET = string.ascii_letters + string.digits + "-_"


def generate_password(length: int = GENERATED_PASSWORD_LENGTH) -> str:
    """Generate a cryptographically secure random password."""
    return "".join(secrets.choice(_SAFE_ALPHABET) for _ in range(length))


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open the auth SQLite database with validation."""
    if not db_path.exists():
        raise FileNotFoundError(f"Auth database not found: {db_path}")

    if not db_path.is_file():
        raise ValueError(f"Path is not a file: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Cannot open database (corrupt or not SQLite): {db_path}") from exc

    # Verify the users table exists with the expected schema
    try:
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
        table_info = cursor.fetchone()
        if table_info is None:
            conn.close()
            raise ValueError(f"Database does not contain a 'users' table: {db_path}")
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise ValueError(f"Cannot read database schema (corrupt?): {db_path}") from exc

    return conn


def reset_password(db_path: Path, username: str, new_password: str) -> bool:
    """Reset a user's password in the auth database.

    Returns True if the user was found and updated, False if the user doesn't exist.
    Raises FileNotFoundError if the database file is missing.
    Raises ValueError if the database is corrupt or missing the users table.
    """
    conn = _open_db(db_path)
    try:
        password_hash = hash_password(new_password)
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reset a user password in the solr-search auth database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python reset_password.py --password 'new-secret'\n"
            "  python reset_password.py  # generates a random password\n"
            "  python reset_password.py --db-path ./users.db --username admin\n"
        ),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help=f"Path to the auth SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Username whose password to reset (default: admin)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="New password/API key. If omitted, a secure random password is generated.",
    )
    return parser


def _resolve_db_path(cli_path: Path | None) -> Path:
    """Determine the DB path: CLI arg > AUTH_DB_PATH env > default."""
    if cli_path is not None:
        return cli_path.resolve()

    import os

    env_path = os.environ.get("AUTH_DB_PATH")
    if env_path:
        return Path(env_path).resolve()

    return DEFAULT_DB_PATH


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db_path = _resolve_db_path(args.db_path)
    username: str = args.username
    password: str | None = args.password
    generated = False

    if password is None:
        password = generate_password()
        generated = True

    try:
        updated = reset_password(db_path, username, password)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not updated:
        print(f"Error: user '{username}' not found in {db_path}", file=sys.stderr)
        return 1

    if generated:
        print(f"Password for '{username}' has been reset. New password:\n{password}")
    else:
        print(f"Password for '{username}' has been reset successfully.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
