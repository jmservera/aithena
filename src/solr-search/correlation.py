"""Correlation ID tracking for cross-service request tracing.

Provides a ContextVar-based correlation ID that:
- Is generated or extracted from X-Correlation-ID headers by middleware
- Is accessible anywhere in the async call chain via get_correlation_id()
- Is attached to log records via CorrelationIdFilter
- Can be propagated to downstream services via the CORRELATION_ID_HEADER constant
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Thread/task-safe storage for the current request's correlation ID.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

CORRELATION_ID_HEADER = "X-Correlation-ID"


def generate_correlation_id() -> str:
    """Return a new random UUID4 string."""
    return str(uuid.uuid4())


def get_correlation_id() -> str:
    """Return the correlation ID for the current context (empty string if unset)."""
    return correlation_id_var.get()


def set_correlation_id(cid: str) -> None:
    """Explicitly set the correlation ID for the current context."""
    correlation_id_var.set(cid)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that manages correlation IDs for every request.

    On each request:
    1. Reads X-Correlation-ID from the incoming headers (if present).
    2. Falls back to generating a new UUID4 if the header is missing or blank.
    3. Stores the value in the ContextVar so loggers and downstream code can access it.
    4. Adds X-Correlation-ID to the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = (request.headers.get(CORRELATION_ID_HEADER) or "").strip()
        cid = incoming if incoming else generate_correlation_id()
        correlation_id_var.set(cid)
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = cid
        return response


class CorrelationIdFilter:
    """Logging filter that injects the correlation ID into log records.

    Only sets the 'correlation_id' attribute when a non-empty value is
    available, preventing python-json-logger from serialising an empty
    string field.
    """

    def filter(self, record) -> bool:  # noqa: A003
        cid = correlation_id_var.get()
        if cid:
            record.correlation_id = cid
        return True
