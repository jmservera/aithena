"""Authentication module for the Aithena Admin Dashboard."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import streamlit as st

JWT_ALGORITHM = "HS256"
_TTL_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd]?)$")
_TTL_MULTIPLIERS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True)
class AuthSettings:
    """Authentication configuration loaded from environment variables."""

    jwt_secret: str
    jwt_ttl_seconds: int
    admin_username: str
    admin_password: str

    @classmethod
    def from_env(cls) -> AuthSettings:
        jwt_secret = os.environ.get("AUTH_JWT_SECRET", "")
        if not jwt_secret:
            raise ValueError("AUTH_JWT_SECRET environment variable is required.")
        raw_ttl = os.environ.get("AUTH_JWT_TTL", "24h")
        ttl_seconds = parse_ttl_to_seconds(raw_ttl)
        admin_username = os.environ.get("AUTH_ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("AUTH_ADMIN_PASSWORD", "")
        if not admin_password:
            raise ValueError("AUTH_ADMIN_PASSWORD environment variable is required.")
        return cls(
            jwt_secret=jwt_secret,
            jwt_ttl_seconds=ttl_seconds,
            admin_username=admin_username,
            admin_password=admin_password,
        )


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents a validated, authenticated user."""

    username: str
    role: str


def parse_ttl_to_seconds(raw_value: str) -> int:
    """Parse a TTL string like '24h', '30m', '3600s' into seconds."""
    match = _TTL_PATTERN.fullmatch(raw_value.strip().lower())
    if match is None:
        raise ValueError(f"Invalid AUTH_JWT_TTL value: {raw_value!r}")
    value = int(match.group("value"))
    unit = match.group("unit")
    ttl_seconds = value * _TTL_MULTIPLIERS[unit]
    if ttl_seconds <= 0:
        raise ValueError("AUTH_JWT_TTL must be greater than zero")
    return ttl_seconds


def authenticate_user(username: str, password: str, settings: AuthSettings) -> AuthenticatedUser | None:
    """Validate credentials. Uses constant-time comparison."""
    import hmac

    username_match = hmac.compare_digest(username, settings.admin_username)
    password_match = hmac.compare_digest(password, settings.admin_password)
    if username_match and password_match:
        return AuthenticatedUser(username=username, role="admin")
    return None


def create_access_token(
    user: AuthenticatedUser, secret: str, ttl_seconds: int, *, now: datetime | None = None
) -> str:
    """Create a JWT compatible with the Aithena auth system."""
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> AuthenticatedUser:
    """Decode and validate a JWT access token."""
    payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub", "role"]})
    username = str(payload["sub"])
    role = str(payload["role"])
    if not username or not role:
        raise ValueError("Token contains empty required claims")
    return AuthenticatedUser(username=username, role=role)


def check_auth(settings: AuthSettings) -> AuthenticatedUser | None:
    """Check if the current Streamlit session is authenticated."""
    token = st.session_state.get("auth_token")
    if not token:
        return None
    try:
        return decode_access_token(token, settings.jwt_secret)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        st.session_state.pop("auth_token", None)
        st.session_state.pop("auth_user", None)
        return None


def login(username: str, password: str, settings: AuthSettings) -> AuthenticatedUser | None:
    """Attempt to log in and store credentials in session state."""
    user = authenticate_user(username, password, settings)
    if user is None:
        return None
    token = create_access_token(user, settings.jwt_secret, settings.jwt_ttl_seconds)
    st.session_state["auth_token"] = token
    st.session_state["auth_user"] = user.username
    return user


def logout() -> None:
    """Clear authentication state from the Streamlit session."""
    st.session_state.pop("auth_token", None)
    st.session_state.pop("auth_user", None)


def require_auth(settings: AuthSettings) -> AuthenticatedUser:
    """Gate that blocks page rendering if not authenticated."""
    user = check_auth(settings)
    if user is not None:
        return user
    from login_page import render_login_page

    render_login_page(settings)
    st.stop()
    raise SystemExit  # pragma: no cover
