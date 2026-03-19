from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt import DecodeError, ExpiredSignatureError, InvalidTokenError

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
        connection.commit()


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
MIN_PASSWORD_LENGTH = 8
VALID_ROLES = frozenset({"admin", "user", "viewer"})


class UserExistsError(ValueError):
    """Raised when a user with the given username already exists."""


class PasswordPolicyError(ValueError):
    """Raised when a password fails validation checks."""


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")


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
    validate_password(password)

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
    max_age: int,
    *,
    secure: bool,
) -> None:
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        max_age=max_age,
        expires=max_age,
        path="/",
        samesite="lax",
        secure=secure,
    )


def clear_auth_cookie(response, cookie_name: str, *, secure: bool) -> None:
    response.delete_cookie(key=cookie_name, path="/", samesite="lax", secure=secure)
