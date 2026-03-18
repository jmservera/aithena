"""API-key authentication for admin endpoints (defense-in-depth).

If ``ADMIN_API_KEY`` is configured, requests to admin endpoints must include
a matching key via the ``X-API-Key`` header.
If the environment variable is **not** set, admin endpoints are disabled and
return *403 Forbidden* to prevent unauthenticated access.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


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


def require_admin_auth(request: Request) -> None:
    """FastAPI dependency that enforces API-key auth on admin endpoints.

    * Key not configured → *403 Forbidden* (admin endpoints disabled).
    * Key configured but missing/wrong in request → *401 Unauthorized*.
    * Key matches → request proceeds.
    """
    admin_api_key = _get_admin_api_key()
    if admin_api_key is None:
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints are disabled — ADMIN_API_KEY is not configured",
        )

    provided = _extract_api_key(request)
    if provided is None:
        raise HTTPException(
            status_code=401,
            detail="Admin API key required — provide via X-API-Key header",
        )

    if not hmac.compare_digest(provided, admin_api_key):
        raise HTTPException(status_code=401, detail="Invalid admin API key")
