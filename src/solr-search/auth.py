from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import ExpiredSignatureError, JWTError, jwt

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
            token, secret, algorithms=[JWT_ALGORITHM], options={"require_exp": True}
        )
    except ExpiredSignatureError:
        raise TokenExpiredError("Token expired")
    except JWTError:
        raise AuthenticationError("Invalid authentication token")

    try:
        user_id = int(payload["user_id"])
        username = str(payload["sub"])
        role = str(payload["role"])
    except (KeyError, TypeError, ValueError):
        raise AuthenticationError("Invalid authentication token")

    if not username or not role:
        raise AuthenticationError("Invalid authentication token")

    return AuthenticatedUser(id=user_id, username=username, role=role)


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
