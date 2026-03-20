from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt import DecodeError, ExpiredSignatureError, InvalidTokenError

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
_PASSWORD_HASHER = PasswordHasher()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("aithena-dummy-password")
_TTL_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd]?)$")
_TTL_MULTIPLIERS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


class AuthenticationError(ValueError):
    """Raised when an auth token is missing or invalid."""


class TokenExpiredError(AuthenticationError):
    """Raised when an auth token is expired."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: str

    def to_dict(self) -> dict[str, int | str]:
        return {"id": self.id, "username": self.username, "role": self.role}


@dataclass(frozen=True)
class StoredUser:
    id: int
    username: str
    password_hash: str
    role: str


def parse_ttl_to_seconds(raw_value: str) -> int:
    match = _TTL_PATTERN.fullmatch(raw_value.strip().lower())
    if match is None:
        raise ValueError(f"Invalid AUTH_JWT_TTL value: {raw_value!r}")

    value = int(match.group("value"))
    unit = match.group("unit")
    ttl_seconds = value * _TTL_MULTIPLIERS[unit]
    if ttl_seconds <= 0:
        raise ValueError("AUTH_JWT_TTL must be greater than zero")
    return ttl_seconds


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

    from migrations import apply_pending_migrations

    apply_pending_migrations(db_path)
    _seed_default_admin(db_path)


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _load_user_by_username(db_path: Path, username: str) -> StoredUser | None:
    normalized_username = username.strip()
    if not normalized_username:
        return None

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if row is None:
            return None
        return StoredUser(
            id=int(row["id"]),
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            role=str(row["role"]),
        )


def _verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError, VerificationError):
        return False


def authenticate_user(db_path: Path, username: str, password: str) -> AuthenticatedUser | None:
    user = _load_user_by_username(db_path, username)
    if user is None:
        _verify_password(_DUMMY_PASSWORD_HASH, password)
        return None

    password_valid = _verify_password(user.password_hash, password)
    if not password_valid:
        return None

    if _PASSWORD_HASHER.check_needs_rehash(user.password_hash):
        with _connect(db_path) as connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), user.id),
            )
            connection.commit()

    return AuthenticatedUser(id=user.id, username=user.username, role=user.role)


def create_access_token(
    user: AuthenticatedUser,
    secret: str,
    ttl_seconds: int,
    *,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> AuthenticatedUser:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp"]}
        )
    except ExpiredSignatureError as err:
        raise TokenExpiredError("Token expired") from err
    except (DecodeError, InvalidTokenError) as err:
        raise AuthenticationError("Invalid authentication token") from err

    try:
        user_id = int(payload["user_id"])
        username = str(payload["sub"])
        role = str(payload["role"])
    except (KeyError, TypeError, ValueError) as err:
        raise AuthenticationError("Invalid authentication token") from err

    if not username or not role:
        raise AuthenticationError("Invalid authentication token")

    return AuthenticatedUser(id=user_id, username=username, role=role)


MAX_PASSWORD_LENGTH = 128
VALID_ROLES = frozenset({"admin", "user", "viewer"})


class UserExistsError(ValueError):
    """Raised when a user with the given username already exists."""


class PasswordPolicyError(ValueError):
    """Raised when a password fails validation checks."""


def validate_password(password: str, username: str = "") -> None:
    """Validate password against policy using the standalone password_policy module."""
    from password_policy import validate_password as _check_policy

    violations = _check_policy(password, username)
    if violations:
        raise PasswordPolicyError("; ".join(violations))


def validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of: {', '.join(sorted(VALID_ROLES))}")
    return normalized


def create_user(db_path: Path, username: str, password: str, role: str) -> dict:
    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Username must not be empty")
    validated_role = validate_role(role)
    validate_password(password, normalized_username)

    password_hash = hash_password(password)
    with _connect(db_path) as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (normalized_username, password_hash, validated_role),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise UserExistsError(f"User {normalized_username!r} already exists") from exc
        row = connection.execute(
            "SELECT created_at FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return {
            "id": cursor.lastrowid,
            "username": normalized_username,
            "role": validated_role,
            "created_at": row["created_at"],
        }


def list_users(db_path: Path) -> list[dict]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
    return [
        {"id": row["id"], "username": row["username"], "role": row["role"], "created_at": row["created_at"]}
        for row in rows
    ]


def get_user_by_id(db_path: Path, user_id: int) -> dict | None:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT id, username, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"], "created_at": row["created_at"]}


def update_user(db_path: Path, user_id: int, *, username: str | None = None, role: str | None = None) -> dict | None:
    normalized_username: str | None = None
    validated_role: str | None = None

    if username is not None:
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError("Username must not be empty")

    if role is not None:
        validated_role = validate_role(role)

    if normalized_username is None and validated_role is None:
        return get_user_by_id(db_path, user_id)

    with _connect(db_path) as connection:
        try:
            if normalized_username is not None and validated_role is not None:
                connection.execute(
                    "UPDATE users SET username = ?, role = ? WHERE id = ?",
                    (normalized_username, validated_role, user_id),
                )
            elif normalized_username is not None:
                connection.execute(
                    "UPDATE users SET username = ? WHERE id = ?",
                    (normalized_username, user_id),
                )
            else:
                connection.execute(
                    "UPDATE users SET role = ? WHERE id = ?",
                    (validated_role, user_id),
                )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise UserExistsError("Username already taken") from exc
    return get_user_by_id(db_path, user_id)


def delete_user(db_path: Path, user_id: int) -> bool:
    with _connect(db_path) as connection:
        cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
        return cursor.rowcount > 0


def _seed_default_admin(db_path: Path) -> None:
    """Seed a default admin user if the users table is empty and AUTH_DEFAULT_ADMIN_PASSWORD is set."""
    from config import settings

    with _connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        user_count = row[0] if row else 0

    if user_count > 0:
        return

    password = settings.auth_default_admin_password
    if not password:
        logger.warning(
            "No users in the database and AUTH_DEFAULT_ADMIN_PASSWORD is not set. "
            "No default admin user created. Use reset_password.py or set the env var to bootstrap."
        )
        return

    username = settings.auth_default_admin_username
    try:
        validate_password(password, username)
    except PasswordPolicyError:
        logger.warning(
            "Default admin password does not meet password policy. "
            "Seeding anyway to avoid blocking startup — please change the password promptly."
        )
    password_hash = hash_password(password)
    created_at = datetime.now(UTC).isoformat()

    with _connect(db_path) as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, "admin", created_at),
        )
        connection.commit()

    logger.info("Default admin user '%s' created on first startup", username)


def change_password(db_path: Path, user_id: int, current_password: str, new_password: str) -> None:
    """Change a user's password after verifying the current one.

    Raises:
        ValueError: current password wrong, or same password.
        PasswordPolicyError: new password doesn't meet policy.
    """
    # Validate lengths before expensive Argon2 operations to prevent DoS
    if len(current_password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Current password is incorrect")

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT username, password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    if row is None:
        raise ValueError("User not found")

    validate_password(new_password, str(row["username"]))

    stored_hash = str(row["password_hash"])

    if not _verify_password(stored_hash, current_password):
        raise ValueError("Current password is incorrect")

    if _verify_password(stored_hash, new_password):
        raise ValueError("New password must be different from the current password")

    new_hash = hash_password(new_password)
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )
        connection.commit()


def get_token_from_sources(authorization_header: str | None, cookie_token: str | None) -> str | None:
    if authorization_header:
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token.strip()
    if cookie_token:
        return cookie_token.strip() or None
    return None


def set_auth_cookie(
    response,
    token: str,
    cookie_name: str,
    max_age: int | None,
    *,
    secure: bool,
) -> None:
    """Set the auth cookie on the response.

    When *max_age* is ``None`` the cookie becomes a session cookie that is
    deleted when the browser closes.
    """
    kwargs: dict[str, Any] = {
        "key": cookie_name,
        "value": token,
        "httponly": True,
        "path": "/",
        "samesite": "lax",
        "secure": secure,
    }
    if max_age is not None:
        kwargs["max_age"] = max_age
        kwargs["expires"] = max_age
    response.set_cookie(**kwargs)


def clear_auth_cookie(response, cookie_name: str, *, secure: bool) -> None:
    response.delete_cookie(key=cookie_name, path="/", samesite="lax", secure=secure)
