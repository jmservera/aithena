"""Authentication for admin endpoints (defense-in-depth).

Admin endpoints accept **either** of two authentication methods:

1. **API key** — ``X-API-Key`` header matching ``ADMIN_API_KEY`` env var.
   Intended for machine-to-machine / scripted access.
2. **JWT session** — a valid JWT (via ``Authorization: Bearer`` header or the
   auth cookie) whose ``role`` claim is ``"admin"``.
   Intended for browser-based access from the React admin UI.

If neither method succeeds the request is rejected with *401 Unauthorized*.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException, Request

_logger = logging.getLogger(__name__)


def _get_admin_api_key() -> str | None:
    """Retrieve admin API key from settings (single source of truth)."""
    from config import settings

    return settings.admin_api_key


def _extract_api_key(request: Request) -> str | None:
    """Extract an API key from the ``X-API-Key`` header."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()
    return None


def _is_authenticated_admin(request: Request) -> bool:
    """Return ``True`` if the middleware already authenticated an admin user."""
    from main import AuthenticatedUser

    user = getattr(request.state, "auth_user", None)
    return isinstance(user, AuthenticatedUser) and user.role == "admin"


def require_admin_auth(request: Request) -> None:
    """FastAPI dependency that enforces auth on admin endpoints.

    Accepts either a valid ``X-API-Key`` header **or** a JWT session with
    admin role (set by the authentication middleware).
    """
    # Path 1: API-key authentication (machine-to-machine).
    admin_api_key = _get_admin_api_key()
    provided_key = _extract_api_key(request)

    if provided_key is not None and admin_api_key is not None:
        if hmac.compare_digest(provided_key, admin_api_key):
            return  # valid API key
        raise HTTPException(
            status_code=401,
            detail="Invalid admin API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Path 2: JWT session — the auth middleware has already validated the
    # token and stored the user on request.state.auth_user.
    if _is_authenticated_admin(request):
        return

    # Neither method succeeded.
    if provided_key is not None:
        # An API key was provided but ADMIN_API_KEY is not configured.
        _logger.warning("X-API-Key provided but ADMIN_API_KEY is not configured")

    raise HTTPException(
        status_code=401,
        detail="Admin access required — authenticate via API key or admin session",
        headers={"WWW-Authenticate": "Bearer"},
    )
