from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import re
import socket
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar
from urllib.parse import urlparse

import pika
import redis as redis_lib
import requests
from admin_auth import require_admin_auth
from auth import (
    AuthenticatedUser,
    AuthenticationError,
    PasswordPolicyError,
    UserExistsError,
    authenticate_user,
    change_password,
    clear_auth_cookie,
    create_access_token,
    create_user,
    decode_access_token,
    delete_user,
    get_token_from_sources,
    get_token_remember_me,
    get_user_by_id,
    init_auth_db,
    list_users,
    set_auth_cookie,
    update_user,
)
from circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from collections_models import (
    AddItemsRequest,
    CollectionDetailResponse,
    CollectionResponse,
    CreateCollectionRequest,
    ReorderItemsRequest,
    UpdateCollectionRequest,
    UpdateItemRequest,
)
from collections_service import (
    add_items as svc_add_items,
)
from collections_service import (
    create_collection as svc_create_collection,
)
from collections_service import (
    delete_collection as svc_delete_collection,
)
from collections_service import (
    get_collection as svc_get_collection,
)
from collections_service import (
    list_collections as svc_list_collections,
)
from collections_service import (
    remove_item as svc_remove_item,
)
from collections_service import (
    reorder_items as svc_reorder_items,
)
from collections_service import (
    update_collection as svc_update_collection,
)
from collections_service import (
    update_item as svc_update_item,
)
from config import settings
from correlation import CorrelationIdMiddleware, get_correlation_id
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from logging_config import setup_logging
from metrics import METRICS_CONTENT_TYPE, metrics_registry
from pydantic import BaseModel
from search_service import (
    build_filter_queries,
    build_inline_content_disposition,
    build_knn_params,
    build_pagination,
    build_solr_params,
    decode_document_token,
    encode_document_token,
    get_query_embedding,
    normalize_book,
    parse_facet_counts,
    parse_stats_response,
    reciprocal_rank_fusion,
    resolve_document_path,
    solr_escape,
)

setup_logging(service_name="solr-search")
logger = logging.getLogger(__name__)

T = TypeVar("T")

SortBy = Literal["score", "title", "author", "year", "category", "language"]
SortOrder = Literal["asc", "desc"]

VALID_SEARCH_MODES: frozenset[str] = frozenset({"keyword", "semantic", "hybrid"})
EMBEDDINGS_DEGRADED_MESSAGE = "Embeddings unavailable — showing keyword results"


_INSECURE_JWT_SECRETS = frozenset({"development-only-change-me", "", "changeme", "secret"})


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auth_jwt_secret in _INSECURE_JWT_SECRETS:
        logger.warning(
            "AUTH_JWT_SECRET is using an insecure default value. "
            "Set a strong random secret via the AUTH_JWT_SECRET environment variable."
        )
    init_auth_db(settings.auth_db_path)
    from collections_service import init_collections_db

    init_collections_db(settings.collections_db_path)
    logger.info("solr-search started", extra={"version": settings.version, "port": settings.port})
    yield
    logger.info("solr-search shutting down")


app = FastAPI(title=settings.title, version=settings.version, lifespan=lifespan)

# ---------------------------------------------------------------------------
# Circuit breakers — configured via CB_* environment variables (see config.py)
# ---------------------------------------------------------------------------

redis_circuit = CircuitBreaker(
    name="redis",
    failure_threshold=settings.cb_redis_failure_threshold,
    recovery_timeout=settings.cb_redis_recovery_timeout,
    expected_exceptions=(redis_lib.RedisError, OSError, ConnectionError),
)

solr_circuit = CircuitBreaker(
    name="solr",
    failure_threshold=settings.cb_solr_failure_threshold,
    recovery_timeout=settings.cb_solr_recovery_timeout,
    expected_exceptions=(requests.RequestException, ValueError),
)

embeddings_circuit = CircuitBreaker(
    name="embeddings",
    failure_threshold=settings.cb_embeddings_failure_threshold,
    recovery_timeout=settings.cb_embeddings_recovery_timeout,
    expected_exceptions=(requests.RequestException, ValueError, KeyError, TypeError, IndexError),
)

PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/v1/health",
        "/info",
        "/v1/info",
        "/version",
        "/status",
        "/v1/status",
        "/v1/status/",
        "/v1/auth/login",
        "/v1/auth/login/",
        "/v1/auth/validate",
        "/v1/auth/validate/",
        "/v1/metrics",
        "/v1/metrics/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)
PUBLIC_PATH_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UpdateUserRequest(BaseModel):
    username: str | None = None
    role: str | None = None


def require_role(*allowed_roles: str) -> Any:
    """FastAPI dependency that enforces role-based access control."""

    def _dependency(request: Request) -> AuthenticatedUser:
        user = _get_current_user(request)
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return Depends(_dependency)


class RateLimiter:
    """Simple in-memory rate limiter for upload endpoint."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is allowed to make a request."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self.lock:
            # Remove old requests outside the window
            while self.requests[client_ip] and self.requests[client_ip][0] < cutoff:
                self.requests[client_ip].popleft()

            # Check if under limit
            if len(self.requests[client_ip]) >= self.max_requests:
                return False

            # Add current request
            self.requests[client_ip].append(now)
            return True


upload_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


def get_client_ip(request: Request) -> str:
    """Extract the real client IP from a proxied request.

    Reads X-Forwarded-For set by nginx (configured as $remote_addr to prevent
    spoofing). Falls back to the direct connection IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    if request.client:
        return request.client.host
    return "unknown"


class RedisRateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, delegating to module-level helper."""
        return get_client_ip(request)

    def check_rate_limit(self, request: Request) -> tuple[bool, int]:
        """Check if request is within rate limit.

        Returns:
            tuple[bool, int]: (is_allowed, retry_after_seconds)
        """
        if self.requests_per_minute <= 0:
            return True, 0

        client_ip = self._get_client_ip(request)
        key = f"ratelimit:search:{client_ip}"
        now = time.time()
        window_start = now - self.window_seconds

        try:
            pool = _get_redis_pool()
            client = redis_lib.Redis(connection_pool=pool)

            # Clean old entries and count current requests
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zcard(key)
            results = pipe.execute()

            request_count = results[1]  # zcard result

            if request_count >= self.requests_per_minute:
                oldest = client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = oldest[0][1]
                    retry_after = int(oldest_timestamp + self.window_seconds - now) + 1
                    return False, max(retry_after, 1)
                return False, self.window_seconds

            # Only record request after confirming it's allowed
            member = f"{now}:{id(request)}"
            pipe2 = client.pipeline()
            pipe2.zadd(key, {member: now})
            pipe2.expire(key, self.window_seconds)
            pipe2.execute()

            return True, 0

        except (redis_lib.RedisError, OSError, ConnectionError) as exc:
            logger.warning(
                "rate_limit_redis_error",
                extra={
                    "error": str(exc),
                    "client_ip": client_ip,
                },
            )
            # Fail open: allow request if Redis is unavailable
            return True, 0


search_rate_limiter = RedisRateLimiter(requests_per_minute=settings.rate_limit_requests_per_minute)


def build_params_or_400(**kwargs: Any) -> dict[str, Any]:
    try:
        return build_solr_params(**kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def check_search_rate_limit(request: Request) -> None:
    """FastAPI dependency to check rate limit for search endpoint.

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded
    """
    allowed, retry_after = search_rate_limiter.check_rate_limit(request)
    if not allowed:
        logger.warning(
            "rate_limit_exceeded",
            extra={
                "client_ip": search_rate_limiter._get_client_ip(request),
                "path": request.url.path,
                "retry_after": retry_after,
            },
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )



if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Correlation ID middleware — extracts or generates a correlation ID per request,
# stores it in a ContextVar, and returns it in the X-Correlation-ID response header.
app.add_middleware(CorrelationIdMiddleware)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every HTTP request with method, path, status code, and duration."""
    start_time = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start_time) * 1000, 2)
    cid = get_correlation_id()
    logger.info(
        "%s %s %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={
            "http_method": request.method,
            "http_path": request.url.path,
            "http_status": response.status_code,
            "duration_ms": duration_ms,
            "correlation_id": cid,
        },
    )
    return response


def _raw_solr_query(params: dict[str, Any]) -> dict[str, Any]:
    """Execute a Solr HTTP request.  Raised exceptions feed the circuit breaker."""
    response = requests.post(settings.select_url, data=params, timeout=settings.request_timeout)
    response.raise_for_status()
    return response.json()


def query_solr(params: dict[str, Any]) -> dict[str, Any]:
    try:
        return solr_circuit.call(_raw_solr_query, params)
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=503,
            detail="Search service temporarily unavailable — Solr circuit breaker is open",
        ) from exc
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Timed out waiting for Solr") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Solr search request failed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Solr returned invalid JSON") from exc


def _fetch_embedding(text: str) -> list[float]:
    """Call the embeddings server through the circuit breaker; wrap errors as HTTP 502/503/504."""
    try:
        return embeddings_circuit.call(
            get_query_embedding, settings.embeddings_url, text, settings.embeddings_timeout
        )
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=503, detail="Embeddings service temporarily unavailable — circuit breaker is open"
        ) from exc
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Timed out waiting for embeddings server") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Embeddings server request failed") from exc
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(status_code=502, detail=f"Embeddings server returned invalid response: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error fetching embedding")
        raise HTTPException(status_code=502, detail="Unexpected error from embeddings server") from exc


def _should_degrade_to_keyword(exc: HTTPException) -> bool:
    return exc.status_code in {502, 503, 504}


def build_document_url(request: Request, file_path: str | None) -> str | None:
    if not file_path:
        return None

    document_id = encode_document_token(file_path)
    if settings.document_url_base:
        return f"{settings.document_url_base}/{document_id}"
    return str(request.url_for("get_document", document_id=document_id))


def resolve_page_size(limit: int | None, page_size: int) -> int:
    return limit or page_size


def collect_search_filters(**filters: str | None) -> dict[str, str]:
    return {name: value.strip() for name, value in filters.items() if value and value.strip()}


@contextlib.contextmanager
def _track_search_metrics(mode: str) -> Generator[None, None, None]:
    started = time.perf_counter()
    metrics_registry.increment_search_request(mode)
    try:
        yield
    finally:
        metrics_registry.observe_search_latency(mode, time.perf_counter() - started)


def _is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _unauthorized_response(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _unauthorized_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _request_uses_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return forwarded_proto.lower() == "https" or request.url.scheme == "https"


def _authenticate_request(request: Request) -> AuthenticatedUser:
    token = get_token_from_sources(
        request.headers.get("Authorization"),
        request.cookies.get(settings.auth_cookie_name),
    )
    if token is None:
        raise AuthenticationError("Not authenticated")
    return decode_access_token(token, settings.auth_jwt_secret)


def _authenticate_request_with_token(request: Request) -> tuple[AuthenticatedUser, str]:
    """Like ``_authenticate_request`` but also returns the raw token for cookie refresh."""
    token = get_token_from_sources(
        request.headers.get("Authorization"),
        request.cookies.get(settings.auth_cookie_name),
    )
    if token is None:
        raise AuthenticationError("Not authenticated")
    return decode_access_token(token, settings.auth_jwt_secret), token


def _get_current_user(request: Request) -> AuthenticatedUser:
    current_user = getattr(request.state, "auth_user", None)
    if isinstance(current_user, AuthenticatedUser):
        return current_user
    return _authenticate_request(request)


@app.middleware("http")
async def require_authentication(request: Request, call_next):
    if request.method == "OPTIONS" or _is_public_path(request.url.path):
        return await call_next(request)

    try:
        request.state.auth_user = _authenticate_request(request)
    except AuthenticationError as exc:
        return _unauthorized_response(str(exc))

    return await call_next(request)


@app.get("/v1/health", include_in_schema=False, name="health_v1")
@app.get("/health")
def health() -> dict[str, Any]:
    redis_cb = redis_circuit.get_status()
    solr_cb = solr_circuit.get_status()
    embeddings_cb = embeddings_circuit.get_status()

    if solr_cb["state"] == CircuitState.OPEN.value:
        overall = "unavailable"
    elif redis_cb["state"] == CircuitState.OPEN.value or embeddings_cb["state"] == CircuitState.OPEN.value:
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "status": overall,
        "service": settings.title,
        "version": settings.version,
        "circuit_breakers": {
            "redis": redis_cb,
            "solr": solr_cb,
            "embeddings": embeddings_cb,
        },
    }


@app.get("/v1/info", include_in_schema=False, name="info_v1")
@app.get("/info")
def info() -> dict[str, str]:
    return {"title": settings.title, "version": settings.version}


@app.get("/version", include_in_schema=False)
def version() -> dict[str, str]:
    return {
        "service": "solr-search",
        "version": settings.version,
        "commit": settings.commit,
        "built": settings.built,
    }


@app.post("/v1/auth/login/", include_in_schema=False, name="auth_login_v1_slash")
@app.post("/v1/auth/login", name="auth_login_v1")
def auth_login(credentials: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    client_ip = get_client_ip(request)
    if not login_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    user = authenticate_user(settings.auth_db_path, credentials.username, credentials.password)
    if user is None:
        raise _unauthorized_exception("Invalid username or password")

    token = create_access_token(
        user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds, remember_me=credentials.remember_me
    )
    cookie_max_age = settings.auth_jwt_ttl_seconds if credentials.remember_me else None
    set_auth_cookie(
        response,
        token,
        settings.auth_cookie_name,
        cookie_max_age,
        secure=_request_uses_https(request),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.auth_jwt_ttl_seconds,
        "user": user.to_dict(),
    }


@app.get("/v1/auth/validate/", include_in_schema=False, name="auth_validate_v1_slash")
@app.get("/v1/auth/validate", name="auth_validate_v1")
def auth_validate(request: Request, response: Response) -> dict[str, Any]:
    try:
        user, token = _authenticate_request_with_token(request)
    except AuthenticationError as exc:
        raise _unauthorized_exception(str(exc)) from exc
    # Refresh the auth cookie so nginx auth_request subrequests keep working.
    # Respect the original remember_me choice: only set max_age for persistent sessions.
    remember_me = get_token_remember_me(token, settings.auth_jwt_secret)
    cookie_max_age = settings.auth_jwt_ttl_seconds if remember_me else None
    set_auth_cookie(
        response,
        token,
        settings.auth_cookie_name,
        cookie_max_age,
        secure=_request_uses_https(request),
    )
    return {"authenticated": True, "user": user.to_dict()}


@app.post("/v1/auth/logout/", include_in_schema=False, name="auth_logout_v1_slash")
@app.post("/v1/auth/logout", name="auth_logout_v1")
def auth_logout(request: Request, response: Response) -> dict[str, str]:
    clear_auth_cookie(response, settings.auth_cookie_name, secure=_request_uses_https(request))
    return {"status": "logged_out"}


@app.get("/v1/auth/me/", include_in_schema=False, name="auth_me_v1_slash")
@app.get("/v1/auth/me", name="auth_me_v1")
def auth_me(request: Request) -> dict[str, Any]:
    return _get_current_user(request).to_dict()


@app.put("/v1/auth/change-password/", include_in_schema=False, name="auth_change_password_v1_slash")
@app.put("/v1/auth/change-password", name="auth_change_password_v1")
def auth_change_password(body: ChangePasswordRequest, request: Request) -> dict[str, str]:
    """Change the current user's password."""
    user = _get_current_user(request)

    try:
        change_password(settings.auth_db_path, user.id, body.current_password, body.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        status = 404 if "User not found" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    return {"status": "password_changed"}


# ---------------------------------------------------------------------------
# User CRUD endpoints (v1.9.0)
# ---------------------------------------------------------------------------


@app.post("/v1/auth/register/", include_in_schema=False, name="auth_register_v1_slash")
@app.post("/v1/auth/register", include_in_schema=False, name="auth_register_v1")
def auth_register(
    body: RegisterRequest,
    admin_user: Annotated[AuthenticatedUser, require_role("admin")],
) -> dict[str, Any]:
    try:
        return create_user(settings.auth_db_path, body.username, body.password, body.role)
    except UserExistsError as exc:
        raise HTTPException(status_code=409, detail="Username already exists") from exc
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/auth/users/", include_in_schema=False, name="auth_list_users_v1_slash")
@app.get("/v1/auth/users", include_in_schema=False, name="auth_list_users_v1")
def auth_list_users(
    admin_user: Annotated[AuthenticatedUser, require_role("admin")],
) -> list[dict[str, Any]]:
    return list_users(settings.auth_db_path)


@app.put("/v1/auth/users/{user_id}/", include_in_schema=False, name="auth_update_user_v1_slash")
@app.put("/v1/auth/users/{user_id}", include_in_schema=False, name="auth_update_user_v1")
def auth_update_user(
    user_id: int,
    body: UpdateUserRequest,
    request: Request,
) -> dict[str, Any]:
    current_user = _get_current_user(request)
    is_admin = current_user.role == "admin"

    if not is_admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if not is_admin and body.role is not None:
        raise HTTPException(status_code=403, detail="Only admins can change roles")

    target = get_user_by_id(settings.auth_db_path, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        updated = update_user(settings.auth_db_path, user_id, username=body.username, role=body.role)
    except UserExistsError as exc:
        raise HTTPException(status_code=409, detail="Username already taken") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")  # pragma: no cover
    return updated


@app.delete("/v1/auth/users/{user_id}/", include_in_schema=False, name="auth_delete_user_v1_slash")
@app.delete("/v1/auth/users/{user_id}", include_in_schema=False, name="auth_delete_user_v1")
def auth_delete_user(
    user_id: int,
    admin_user: Annotated[AuthenticatedUser, require_role("admin")],
) -> dict[str, str]:
    if admin_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    if not delete_user(settings.auth_db_path, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}


@app.get("/v1/search/", include_in_schema=False, name="search_v1")
@app.get("/v1/search", include_in_schema=False, name="search_v1_no_slash")
@app.get(
    "/search",
    responses={
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {"detail": "Rate limit exceeded. Please try again later."}
                }
            },
            "headers": {
                "Retry-After": {
                    "description": "Number of seconds to wait before retrying",
                    "schema": {"type": "integer"},
                }
            },
        }
    },
)
def search(
    request: Request,
    q: str = Query("", description="Keyword search. Empty values return all indexed books."),
    page: int = Query(1, ge=1),
    limit: int | None = Query(None, ge=1, le=settings.max_page_size),
    page_size: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
    sort: str | None = Query(None, description="Combined sort clause like `score desc` or `year_i asc`."),
    sort_by: Annotated[SortBy, Query()] = "score",
    sort_order: Annotated[SortOrder, Query()] = "desc",
    fq_author: str | None = Query(None),
    fq_category: str | None = Query(None),
    fq_language: str | None = Query(None),
    fq_year: str | None = Query(None),
    mode: str = Query(
        settings.default_search_mode,
        description="Search mode: keyword (BM25), semantic (Solr kNN), or hybrid (RRF fusion).",
        enum=list(VALID_SEARCH_MODES),
    ),
    _rate_limit: None = Depends(check_search_rate_limit),
) -> dict[str, Any]:
    """Search for books.

    - **keyword** (default): BM25 full-text search via Solr edismax.
    - **semantic**: Dense vector kNN search using Solr HNSW (``embedding_v`` field).
    - **hybrid**: Reciprocal Rank Fusion of the BM25 and kNN legs.

    Supports both the Phase 2 UI contract (`limit`, `sort`, `fq_*`) and the
    newer FastAPI query parameters (`page_size`, `sort_by`, `sort_order`).

    **Rate Limit:** Configurable via ``RATE_LIMIT_REQUESTS_PER_MINUTE`` (default: 100).
    Set to 0 to disable rate limiting (e.g., for E2E testing).
    """
    if mode not in VALID_SEARCH_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search mode: {mode!r}. Must be one of: keyword, semantic, hybrid.",
        )

    resolved_page_size = resolve_page_size(limit, page_size)
    filters = collect_search_filters(
        author=fq_author,
        category=fq_category,
        language=fq_language,
        year=fq_year,
    )

    with _track_search_metrics(mode):
        if mode == "keyword":
            return _search_keyword(request, q, page, resolved_page_size, sort_by, sort_order, sort, filters)
        if mode == "semantic":
            return _search_semantic(request, q, page, resolved_page_size, sort_by, sort_order, sort, filters)
        # hybrid
        return _search_hybrid(request, q, page, resolved_page_size, sort_by, sort_order, sort, filters)


def _search_keyword(
    request: Request,
    q: str,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    sort: str | None,
    filters: dict[str, str],
    *,
    degraded: bool = False,
    message: str | None = None,
    requested_mode: str | None = None,
) -> dict[str, Any]:
    payload = query_solr(
        build_params_or_400(
            query=q,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            sort=sort,
            filters=filters,
            facet_limit=settings.facet_limit,
        )
    )

    response = payload.get("response", {})
    highlighting = payload.get("highlighting", {})
    results = [
        normalize_book(
            document,
            highlighting,
            build_document_url(request, document.get("file_path_s")),
        )
        for document in response.get("docs", [])
    ]

    search_response: dict[str, Any] = {
        "query": q,
        "mode": "keyword",
        "sort": {"by": sort_by, "order": sort_order},
        "degraded": degraded,
        **build_pagination(response.get("numFound", 0), page, page_size),
        "results": results,
        "facets": parse_facet_counts(payload),
    }
    if message is not None:
        search_response["message"] = message
    if requested_mode is not None and requested_mode != "keyword":
        search_response["requested_mode"] = requested_mode
    return search_response


def _search_semantic(
    request: Request,
    q: str,
    page: int,
    top_k: int,
    sort_by: str,
    sort_order: str,
    sort: str | None,
    filters: dict[str, str],
) -> dict[str, Any]:
    """Execute a Solr kNN semantic search using the ``embedding_v`` field.

    Facets and highlights degrade to empty because the kNN query path does not
    produce Solr facet counts or highlight snippets.
    """
    # Empty-query guard: semantic mode requires a non-empty string to generate
    # an embedding vector.  Return 400 rather than silently returning no results.
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty for semantic search")

    try:
        vector = _fetch_embedding(q)
    except HTTPException as exc:
        if _should_degrade_to_keyword(exc):
            return _search_keyword(
                request,
                q,
                page,
                top_k,
                sort_by,
                sort_order,
                sort,
                filters,
                degraded=True,
                message=EMBEDDINGS_DEGRADED_MESSAGE,
                requested_mode="semantic",
            )
        raise

    payload = query_solr(build_knn_params(vector, top_k, settings.knn_field, build_filter_queries(filters)))

    response = payload.get("response", {})
    results = [
        normalize_book(
            document,
            {},
            build_document_url(request, document.get("file_path_s")),
        )
        for document in response.get("docs", [])
    ]

    return {
        "query": q,
        "mode": "semantic",
        "sort": {"by": "score", "order": "desc"},
        "degraded": False,
        **build_pagination(response.get("numFound", len(results)), 1, top_k),
        "results": results,
        "facets": {"author": [], "category": [], "year": [], "language": []},
    }


def _search_hybrid(
    request: Request,
    q: str,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    sort: str | None,
    filters: dict[str, str],
) -> dict[str, Any]:
    """Execute BM25 and kNN searches in parallel, then fuse with RRF.

    Facets and highlights are sourced from the BM25 (keyword) leg.
    Documents that appear only in the kNN leg will have empty highlights.
    The RRF k constant is configurable via the ``RRF_K`` environment variable
    (default 60, per the original RRF paper).
    """
    # Empty-query guard: hybrid mode needs an embedding for the kNN leg.
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty for hybrid search")

    candidate_limit = max(page_size * 2, 20)

    kw_params = build_params_or_400(
        query=q,
        page=1,
        page_size=candidate_limit,
        sort_by=sort_by,
        sort_order=sort_order,
        sort=sort,
        filters=filters,
        facet_limit=settings.facet_limit,
    )

    # Run BM25 query and embedding fetch concurrently
    with ThreadPoolExecutor(max_workers=2) as pool:
        kw_future = pool.submit(query_solr, kw_params)
        emb_future = pool.submit(_fetch_embedding, q)

        kw_future_result = kw_future.result()
        try:
            vector = emb_future.result()
        except HTTPException as exc:
            if _should_degrade_to_keyword(exc):
                return _search_keyword(
                    request,
                    q,
                    page,
                    page_size,
                    sort_by,
                    sort_order,
                    sort,
                    filters,
                    degraded=True,
                    message=EMBEDDINGS_DEGRADED_MESSAGE,
                    requested_mode="hybrid",
                )
            raise

        kw_payload = kw_future_result

    knn_payload = query_solr(
        build_knn_params(vector, candidate_limit, settings.knn_field, build_filter_queries(filters))
    )

    kw_response = kw_payload.get("response", {})
    kw_highlighting = kw_payload.get("highlighting", {})

    kw_results = [
        normalize_book(
            document,
            kw_highlighting,
            build_document_url(request, document.get("file_path_s")),
        )
        for document in kw_response.get("docs", [])
    ]

    sem_results = [
        normalize_book(
            document,
            {},
            build_document_url(request, document.get("file_path_s")),
        )
        for document in knn_payload.get("response", {}).get("docs", [])
    ]

    fused = reciprocal_rank_fusion(kw_results, sem_results, k=settings.rrf_k)[:page_size]

    return {
        "query": q,
        "mode": "hybrid",
        "sort": {"by": "score", "order": "desc"},
        "degraded": False,
        **build_pagination(len(fused), 1, page_size),
        "results": fused,
        "facets": parse_facet_counts(kw_payload),
    }


@app.get("/v1/facets/", include_in_schema=False, name="facets_v1")
@app.get("/v1/facets", include_in_schema=False, name="facets_v1_no_slash")
@app.get("/facets")
def facets(
    q: str = Query("", description="Optional query to scope facet counts."),
    sort: str | None = Query(None),
    sort_by: Annotated[SortBy, Query()] = "score",
    sort_order: Annotated[SortOrder, Query()] = "desc",
    fq_author: str | None = Query(None),
    fq_category: str | None = Query(None),
    fq_language: str | None = Query(None),
    fq_year: str | None = Query(None),
) -> dict[str, Any]:
    payload = query_solr(
        build_params_or_400(
            query=q,
            page=1,
            page_size=1,
            sort_by=sort_by,
            sort_order=sort_order,
            sort=sort,
            filters=collect_search_filters(
                author=fq_author,
                category=fq_category,
                language=fq_language,
                year=fq_year,
            ),
            facet_limit=settings.facet_limit,
            rows=0,
        )
    )
    return {"query": q, "facets": parse_facet_counts(payload)}


@app.get("/v1/documents/{document_id}", include_in_schema=False, name="get_document_v1")
@app.get("/documents/{document_id}", name="get_document")
def get_document(document_id: str) -> FileResponse:
    try:
        file_path = decode_document_token(document_id)
        document_path = resolve_document_path(settings.base_path, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if document_path.suffix.lower() != ".pdf" or not document_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    return FileResponse(
        document_path,
        media_type="application/pdf",
        filename=document_path.name,
        headers={"Content-Disposition": build_inline_content_disposition(document_path.name)},
    )


@app.get("/v1/books/{document_id}/similar", include_in_schema=False, name="similar_books_v1")
@app.get("/books/{document_id}/similar")
def similar_books(
    request: Request,
    document_id: str,
    limit: int = Query(5, ge=1, le=50, description="Maximum number of similar books to return."),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum cosine similarity score threshold."),
) -> dict[str, Any]:
    """Return books semantically similar to the one identified by *document_id*.

    The source document is always excluded from results. Similarity is computed
    using Solr's kNN query against the ``embedding_v`` DenseVectorField.
    """
    embedding_field = settings.book_embedding_field

    source_payload = query_solr(
        {
            "q": f"id:{solr_escape(document_id)}",
            "fl": f"id,{embedding_field}",
            "rows": 1,
            "wt": "json",
        }
    )
    source_docs = source_payload.get("response", {}).get("docs", [])
    if not source_docs:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id!r}")

    vector = source_docs[0].get(embedding_field)
    if not vector:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Document {document_id!r} has no embedding yet. "
                "Embeddings are populated by the Phase 3 indexing pipeline."
            ),
        )

    knn_payload = query_solr(
        {
            "q": f"{{!knn f={embedding_field} topK={limit + 1}}}{json.dumps(vector)}",
            "fq": f"-id:{solr_escape(document_id)}",
            "fl": "id,title_s,author_s,year_i,category_s,file_path_s,score",
            "rows": limit,
            "wt": "json",
        }
    )
    docs = knn_payload.get("response", {}).get("docs", [])

    results = []
    for doc in docs:
        score = doc.get("score", 0.0)
        if min_score > 0.0 and score < min_score:
            continue
        file_path = doc.get("file_path_s")
        results.append(
            {
                "id": doc.get("id"),
                "title": doc.get("title_s") or Path(file_path or "").stem,
                "author": doc.get("author_s") or "Unknown",
                "year": doc.get("year_i"),
                "category": doc.get("category_s"),
                "document_url": build_document_url(request, file_path),
                "score": score,
            }
        )

    return {"results": results}


@app.get("/v1/books/", include_in_schema=False, name="books_v1")
@app.get("/v1/books", include_in_schema=False, name="books_v1_no_slash")
@app.get("/books")
def list_books(
    request: Request,
    page: int = Query(1, ge=1, description="Page number for pagination."),
    page_size: int = Query(
        settings.default_page_size, ge=1, le=settings.max_page_size, description="Results per page."
    ),
    sort_by: Annotated[SortBy, Query()] = "title",
    sort_order: Annotated[SortOrder, Query()] = "asc",
    fq_author: str | None = Query(None, description="Filter by author name."),
    fq_category: str | None = Query(None, description="Filter by category."),
    fq_language: str | None = Query(None, description="Filter by language."),
    fq_year: str | None = Query(None, description="Filter by publication year."),
) -> dict[str, Any]:
    """Browse the complete library of indexed books with pagination and filtering.

    Returns all books sorted by title (default) or other fields. Supports the same
    filter query parameters as the search endpoint (``fq_author``, ``fq_category``,
    ``fq_language``, ``fq_year``).

    This endpoint uses a wildcard ``*:*`` query to match all documents, making it
    suitable for library browsing and discovery.
    """
    filters = collect_search_filters(
        author=fq_author,
        category=fq_category,
        language=fq_language,
        year=fq_year,
    )

    payload = query_solr(
        build_params_or_400(
            query="*:*",
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            sort=None,
            filters=filters,
            facet_limit=settings.facet_limit,
        )
    )

    response = payload.get("response", {})
    highlighting = payload.get("highlighting", {})
    results = [
        normalize_book(
            document,
            highlighting,
            build_document_url(request, document.get("file_path_s")),
        )
        for document in response.get("docs", [])
    ]

    return {
        "sort": {"by": sort_by, "order": sort_order},
        **build_pagination(response.get("numFound", 0), page, page_size),
        "results": results,
        "facets": parse_facet_counts(payload),
    }


@app.get("/v1/stats/", include_in_schema=False, name="stats_v1")
@app.get("/v1/stats", include_in_schema=False, name="stats_v1_no_slash")
@app.get("/stats")
def stats() -> dict[str, Any]:
    """Return collection-level statistics from Solr.

    Queries Solr with the stats component and facets to produce an overview of
    the indexed book collection including totals, breakdowns by language,
    author, year, and category, and page-count statistics.

    Uses Solr grouping by parent_id_s to count distinct books instead of total
    chunks (Phase 1 quick win for issue #404).
    """
    params: dict[str, Any] = {
        "q": "*:*",
        "rows": 0,
        "wt": "json",
        "group": "true",
        "group.field": "parent_id_s",
        "group.ngroups": "true",
        "group.limit": 0,
        "stats": "true",
        "stats.field": "page_count_i",
        "facet": "true",
        "facet.field": ["author_s", "category_s", "year_i", "language_detected_s"],
        "facet.limit": settings.facet_limit,
        "facet.mincount": 1,
    }
    payload = query_solr(params)
    return parse_stats_response(payload)


# ---------------------------------------------------------------------------
# Phase 4 — /v1/status/ endpoint
# ---------------------------------------------------------------------------

_redis_pool: redis_lib.ConnectionPool | None = None
_redis_pool_lock = threading.Lock()


def _get_redis_pool() -> redis_lib.ConnectionPool:
    """Return a singleton Redis ConnectionPool (double-checked locking)."""
    global _redis_pool
    if _redis_pool is None:
        with _redis_pool_lock:
            if _redis_pool is None:
                _redis_pool = redis_lib.ConnectionPool(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=5,
                )
    return _redis_pool


def _redis_call(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute *func* through the Redis circuit breaker."""
    return redis_circuit.call(func, *args, **kwargs)


def _tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to *host*:*port* succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _rabbitmq_management_check(
    host: str,
    management_port: int,
    user: str,
    password: str,
    path_prefix: str = "/admin/rabbitmq",
    timeout: float = 2.0,
) -> bool:
    """Check RabbitMQ via management HTTP API, falling back to AMQP TCP check."""
    url = f"http://{host}:{management_port}{path_prefix}/api/health/checks/alarms"
    try:
        resp = requests.get(url, auth=(user, password), timeout=timeout)
        return resp.status_code == 200
    except (requests.RequestException, OSError) as exc:
        logger.warning("RabbitMQ management check failed (%s), falling back to TCP probe", exc)
        return _tcp_check(host, settings.rabbitmq_port)


def _zookeeper_check(hosts_csv: str, timeout: float = 2.0) -> bool:
    """Return True if at least one ZooKeeper node is reachable."""
    for entry in hosts_csv.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.rsplit(":", 1)
        host = parts[0]
        try:
            port = int(parts[1]) if len(parts) > 1 else 2181
        except ValueError:
            logger.warning("Skipping malformed ZooKeeper entry %r: invalid port", entry)
            continue
        if _tcp_check(host, port, timeout=timeout):
            return True
    return False


def _get_solr_status(solr_url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Query Solr CLUSTERSTATUS and return aggregated node/doc information."""
    cluster_url = f"{solr_url}/admin/collections"
    try:
        resp = requests.get(
            cluster_url,
            params={"action": "CLUSTERSTATUS", "wt": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {"status": "error", "nodes": 0, "docs_indexed": 0}

    cluster = data.get("cluster", {})
    live_nodes = cluster.get("live_nodes", [])
    node_count = len(live_nodes)

    docs_indexed = 0
    collections = cluster.get("collections", {})
    for col_data in collections.values():
        for shard_data in col_data.get("shards", {}).values():
            replicas = shard_data.get("replicas", {})
            if replicas:
                first_replica = next(iter(replicas.values()))
                docs_indexed += first_replica.get("index", {}).get("numDocs", 0)

    if node_count == 0:
        solr_status = "error"
    elif node_count < 3:
        solr_status = "degraded"
    else:
        solr_status = "ok"

    return {"status": solr_status, "nodes": node_count, "docs_indexed": docs_indexed}


def _raw_indexing_status(key_pattern: str) -> tuple[dict[str, int], set[str]]:
    """Inner Redis scan — raised exceptions feed the circuit breaker."""
    pool = _get_redis_pool()
    client = redis_lib.Redis(connection_pool=pool)
    keys = list(client.scan_iter(match=key_pattern, count=100))
    empty: dict[str, int] = {"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}
    if not keys:
        return empty, set()

    values = client.mget(keys)
    indexed = 0
    failed = 0
    pending = 0
    failed_keys: set[str] = set()
    for key, val in zip(keys, values, strict=False):
        if val is None:
            pending += 1
        elif val == "text_indexed":
            indexed += 1
        elif val == "failed":
            failed += 1
            failed_keys.add(str(key))
        else:
            pending += 1

    total = len(keys)
    return {
        "total_discovered": total,
        "indexed": indexed,
        "failed": failed,
        "pending": pending,
    }, failed_keys


def _get_indexing_status_details(key_pattern: str) -> tuple[dict[str, int], set[str] | None]:
    """Scan Redis for *key_pattern* keys — routes through Redis circuit breaker."""
    empty: dict[str, int] = {"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}
    try:
        return _redis_call(_raw_indexing_status, key_pattern)
    except CircuitOpenError:
        logger.warning("redis_circuit_open: skipping indexing status check")
        return empty, None
    except Exception:
        return empty, None


def _get_indexing_status(key_pattern: str) -> dict[str, int]:
    counts, _failed_keys = _get_indexing_status_details(key_pattern)
    return counts


@app.get("/v1/status/", include_in_schema=False, name="status_v1_slash")
@app.get("/v1/status", name="status_v1")
def service_status() -> dict[str, Any]:
    """Return aggregated indexing and service health status.

    Aggregates:
    - Solr CLUSTERSTATUS (node health + doc count)
    - Redis ``doc:*`` key scan (indexing state breakdown)
    - TCP reachability checks for Solr, Redis, and ZooKeeper
    - RabbitMQ management HTTP API health check
    - Embeddings `/version` probe for semantic-search readiness
    """
    parsed = urlparse(settings.solr_url)
    solr_host = parsed.hostname or settings.solr_url
    solr_port = parsed.port or 8983

    solr_info = _get_solr_status(settings.solr_url, timeout=settings.request_timeout)
    indexing_info = _get_indexing_status(settings.redis_key_pattern)

    solr_up = _tcp_check(solr_host, solr_port)
    redis_up = _tcp_check(settings.redis_host, settings.redis_port)
    rabbitmq_up = _rabbitmq_management_check(
        settings.rabbitmq_host,
        settings.rabbitmq_management_port,
        settings.rabbitmq_user,
        settings.rabbitmq_pass,
    )
    zookeeper_up = _zookeeper_check(settings.zookeeper_hosts)
    embeddings_available = _embeddings_available(timeout=CONTAINER_VERSION_TIMEOUT)

    return {
        "solr": solr_info,
        "indexing": indexing_info,
        "embeddings_available": embeddings_available,
        "services": {
            "solr": "up" if solr_up else "down",
            "redis": "up" if redis_up else "down",
            "rabbitmq": "up" if rabbitmq_up else "down",
            "zookeeper": "up" if zookeeper_up else "down",
            "embeddings": "up" if embeddings_available else "down",
        },
    }


CONTAINER_VERSION_TIMEOUT = 2.0


def _build_container_entry(
    name: str,
    status: str,
    container_type: str,
    version: str = "unknown",
    commit: str = "unknown",
) -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "type": container_type,
        "version": version,
        "commit": commit,
    }


def _get_embeddings_version_url() -> str:
    embeddings_url = settings.embeddings_url
    if not embeddings_url.startswith(("http://", "https://")):
        embeddings_url = f"http://{embeddings_url}"

    parsed = urlparse(embeddings_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "embeddings-server"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{scheme}://{host}{port}/version"


def _get_http_container_status(
    name: str,
    version_url: str,
    container_type: str = "service",
    timeout: float = CONTAINER_VERSION_TIMEOUT,
) -> dict[str, str]:
    try:
        response = requests.get(version_url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return _build_container_entry(
            name=name,
            status="up",
            container_type=container_type,
            version=str(payload.get("version") or "unknown"),
            commit=str(payload.get("commit") or "unknown"),
        )
    except Exception:
        return _build_container_entry(name=name, status="down", container_type=container_type)


def _embeddings_available(timeout: float = CONTAINER_VERSION_TIMEOUT) -> bool:
    return (
        _get_http_container_status(
            "embeddings-server",
            _get_embeddings_version_url(),
            timeout=timeout,
        )["status"]
        == "up"
    )


def _get_indexing_queue_depth() -> int:
    try:
        client = _get_admin_redis_client()
        return sum(1 for _key, _state, doc_status in _iter_admin_docs(client) if doc_status == "queued")
    except HTTPException:
        return 0


def _refresh_metrics() -> None:
    solr_info = _get_solr_status(settings.solr_url, timeout=settings.request_timeout)
    metrics_registry.set_solr_live_nodes(int(solr_info.get("nodes", 0)))
    metrics_registry.set_indexing_queue_depth(_get_indexing_queue_depth())

    _indexing_counts, failed_keys = _get_indexing_status_details(settings.redis_key_pattern)
    if failed_keys is not None:
        metrics_registry.sync_indexing_failures(failed_keys)

    metrics_registry.set_embeddings_available(1 if _embeddings_available() else 0)


@app.get("/v1/metrics/", include_in_schema=False, name="metrics_v1_slash")
@app.get("/v1/metrics", name="metrics_v1")
def prometheus_metrics() -> Response:
    _refresh_metrics()
    return Response(content=metrics_registry.render(), headers={"Content-Type": METRICS_CONTENT_TYPE})


def _get_tcp_container_status(
    name: str,
    host: str,
    port: int,
    container_type: str,
    version: str = "unknown",
    commit: str = "unknown",
) -> dict[str, str]:
    status = "up" if _tcp_check(host, port) else "down"
    return _build_container_entry(name, status, container_type, version, commit)


def _get_worker_container_status(name: str) -> dict[str, str]:
    return _build_container_entry(
        name=name,
        status="unknown",
        container_type="worker",
        version=settings.version,
        commit=settings.commit,
    )


def _get_solr_container_status() -> dict[str, str]:
    parsed = urlparse(settings.solr_url)
    solr_host = parsed.hostname or settings.solr_url
    solr_port = parsed.port or 8983
    solr_info = _get_solr_status(settings.solr_url, timeout=CONTAINER_VERSION_TIMEOUT)
    status = "up" if _tcp_check(solr_host, solr_port) and solr_info["status"] != "error" else "down"
    return _build_container_entry("solr", status, "infrastructure")


@app.get(
    "/v1/admin/containers/",
    include_in_schema=False,
    name="admin_containers_v1_slash",
    dependencies=[Depends(require_admin_auth)],
)
@app.get("/v1/admin/containers", name="admin_containers_v1", dependencies=[Depends(require_admin_auth)])
def admin_containers() -> dict[str, Any]:
    """Return a combined version/health snapshot for app and infrastructure containers."""
    checks = [
        lambda: _build_container_entry(
            "solr-search",
            "up",
            "service",
            settings.version,
            settings.commit,
        ),
        lambda: _get_http_container_status("embeddings-server", _get_embeddings_version_url()),
        lambda: _get_tcp_container_status(
            "aithena-ui",
            "aithena-ui",
            80,
            "service",
            settings.version,
            settings.commit,
        ),
        lambda: _get_worker_container_status("document-indexer"),
        lambda: _get_worker_container_status("document-lister"),
        _get_solr_container_status,
        lambda: _get_tcp_container_status("redis", settings.redis_host, settings.redis_port, "infrastructure"),
        lambda: _get_tcp_container_status(
            "rabbitmq",
            settings.rabbitmq_host,
            settings.rabbitmq_port,
            "infrastructure",
        ),
        lambda: _get_tcp_container_status("nginx", "nginx", 80, "infrastructure"),
    ]

    with ThreadPoolExecutor(max_workers=len(checks)) as pool:
        containers = [future.result() for future in [pool.submit(check) for check in checks]]

    healthy = sum(1 for container in containers if container["status"] == "up")
    return {
        "containers": containers,
        "last_updated": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "total": len(containers),
        "healthy": healthy,
    }


# ---------------------------------------------------------------------------
# Admin — /v1/admin/documents endpoints (document triage and recovery)
# ---------------------------------------------------------------------------

DocumentStatus = Literal["queued", "processed", "failed"]

# Column sets per status — mirrors the Streamlit admin dashboard schema.
# Canonical field names are defined by document-lister (__main__.py) and
# document-indexer, which write these JSON fields to Redis.
_ADMIN_DOC_COLUMNS: dict[str, tuple[str, ...]] = {
    "queued": ("path", "timestamp", "last_modified"),
    "processed": ("path", "title", "author", "year", "category", "page_count", "timestamp"),
    "failed": ("path", "error", "timestamp", "last_modified"),
}


def _get_admin_redis_client() -> redis_lib.Redis:
    """Return a Redis client using the shared pool."""
    pool = _get_redis_pool()
    return redis_lib.Redis(connection_pool=pool)


def _admin_key_pattern() -> str:
    """Return the Redis key scan pattern for document-lister state entries."""
    return f"/{settings.redis_queue_name}/*"


def _encode_admin_key(redis_key: str) -> str:
    """Base64url-encode a Redis key for use as a URL path segment."""
    return encode_document_token(redis_key)


def _decode_admin_key(token: str) -> str:
    """Decode a base64url-encoded Redis key.  Raises ValueError on invalid input."""
    return decode_document_token(token)


def _classify_doc_state(state: dict[str, Any]) -> DocumentStatus:
    """Return the status category for a parsed document state dict."""
    if state.get("failed"):
        return "failed"
    if state.get("processed"):
        return "processed"
    return "queued"


def _iter_admin_docs(
    client: redis_lib.Redis,
) -> Generator[tuple[str, dict[str, Any], DocumentStatus], None, None]:
    """Yield ``(redis_key, state_dict, status)`` for every valid admin doc entry.

    Silently skips keys whose value is missing or cannot be decoded as JSON.
    Raises HTTPException 503 if the Redis scan itself fails.
    """
    try:
        keys: list[str] = _redis_call(
            lambda: list(client.scan_iter(match=_admin_key_pattern(), count=100)),
        )
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=503,
            detail="Redis circuit breaker is open — admin operations temporarily unavailable",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cannot connect to Redis") from exc

    for key in keys:
        raw = client.get(key)
        if raw is None:
            continue
        try:
            state: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            continue
        yield key, state, _classify_doc_state(state)


def _load_admin_documents(
    status_filter: DocumentStatus | None = None,
) -> dict[str, Any]:
    """Scan Redis and return documents categorised by indexing status.

    Args:
        status_filter: When set, only documents with that status are included
            in the ``documents`` list; counts always reflect the full dataset.

    Returns:
        A dict with summary counts and a ``documents`` list suitable for a
        React data-table.  Each entry carries an opaque ``id`` token that can
        be passed back to the requeue endpoint.
    """
    client = _get_admin_redis_client()
    counts: dict[DocumentStatus, int] = {"queued": 0, "processed": 0, "failed": 0}
    documents: list[dict[str, Any]] = []

    for key, state, doc_status in _iter_admin_docs(client):
        counts[doc_status] += 1

        if status_filter is not None and doc_status != status_filter:
            continue

        entry: dict[str, Any] = {"id": _encode_admin_key(key), "status": doc_status}
        for col in _ADMIN_DOC_COLUMNS[doc_status]:
            entry[col] = state.get(col)
        documents.append(entry)

    return {
        "total": sum(counts.values()),
        **counts,
        "documents": documents,
    }


def _delete_admin_key(redis_key: str) -> bool:
    """Delete *redis_key* from Redis.  Returns True if the key existed."""
    try:
        client = _get_admin_redis_client()
        return bool(_redis_call(client.delete, redis_key))
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=503,
            detail="Redis circuit breaker is open — admin operations temporarily unavailable",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cannot connect to Redis") from exc


@app.get(
    "/v1/admin/documents/",
    include_in_schema=False,
    name="admin_documents_v1_slash",
    dependencies=[Depends(require_admin_auth)],
)
@app.get("/v1/admin/documents", name="admin_documents_v1", dependencies=[Depends(require_admin_auth)])
def admin_list_documents(
    status: Annotated[
        DocumentStatus | None,
        Query(description="Filter documents by indexing status (queued, processed, or failed)."),
    ] = None,
) -> dict[str, Any]:
    """List documents tracked in Redis with their indexing status.

    Returns summary counts for all statuses plus a ``documents`` list for the
    React admin table.  Use the optional ``status`` query parameter to limit
    the ``documents`` list to a single status while still receiving full
    counts.

    Each document entry includes an opaque ``id`` token that can be passed to
    the ``POST /v1/admin/documents/{doc_id}/requeue`` endpoint.
    """
    return _load_admin_documents(status_filter=status)


@app.post(
    "/v1/admin/documents/requeue-failed",
    name="admin_requeue_failed_v1",
    dependencies=[Depends(require_admin_auth)],
)
def admin_requeue_failed() -> dict[str, Any]:
    """Requeue all failed documents by deleting their Redis tracking entries.

    Deleting the Redis key causes the document-lister to re-discover and
    re-enqueue the document on its next scan.  The operation is idempotent —
    calling it when there are no failed documents returns ``requeued: 0``.
    """
    client = _get_admin_redis_client()
    requeued_ids: list[str] = []
    for key, _state, doc_status in _iter_admin_docs(client):
        if doc_status == "failed":
            _delete_admin_key(key)
            requeued_ids.append(_encode_admin_key(key))

    return {"requeued": len(requeued_ids), "ids": requeued_ids}


@app.delete(
    "/v1/admin/documents/processed",
    name="admin_clear_processed_v1",
    dependencies=[Depends(require_admin_auth)],
)
def admin_clear_processed() -> dict[str, Any]:
    """Clear all processed document entries from Redis.

    Removing the Redis key causes the document-lister to re-index the document
    on its next scan.  The operation is idempotent — calling it when there are
    no processed documents returns ``cleared: 0``.
    """
    client = _get_admin_redis_client()
    cleared = 0
    for key, _state, doc_status in _iter_admin_docs(client):
        if doc_status == "processed":
            _delete_admin_key(key)
            cleared += 1

    return {"cleared": cleared}


@app.post(
    "/v1/admin/documents/{doc_id}/requeue",
    name="admin_requeue_document_v1",
    dependencies=[Depends(require_admin_auth)],
)
def admin_requeue_document(doc_id: str) -> dict[str, Any]:
    """Requeue a single document identified by its opaque ``doc_id`` token.

    The ``doc_id`` is the base64url-encoded Redis key returned by
    ``GET /v1/admin/documents``.  Deleting the key causes the document-lister
    to re-discover and re-enqueue the document on its next scan.

    The operation is idempotent — requeueing a document that no longer exists
    in Redis (e.g. because it was already requeued) returns a 404.
    """
    try:
        redis_key = _decode_admin_key(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document id") from exc

    if not redis_key.startswith(f"/{settings.redis_queue_name}/"):
        raise HTTPException(status_code=400, detail="Invalid document id")

    deleted = _delete_admin_key(redis_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found in queue state")

    return {"requeued": 1, "id": doc_id}



# ---------------------------------------------------------------------------
# Metadata edit — PATCH /v1/admin/documents/{doc_id}/metadata
# ---------------------------------------------------------------------------

# Field mapping: request field → list of Solr fields to update atomically
_METADATA_FIELD_MAP: dict[str, list[str]] = {
    "title": ["title_s", "title_t"],
    "author": ["author_s", "author_t"],
    "year": ["year_i"],
    "category": ["category_s"],
    "series": ["series_s"],
}


class MetadataEditRequest(BaseModel):
    """Pydantic model for single-document metadata edit."""

    title: str | None = None
    author: str | None = None
    year: int | None = None
    category: str | None = None
    series: str | None = None

    model_config = {"str_strip_whitespace": True}

    def non_empty_fields(self) -> dict[str, str | int]:
        """Return only supplied, non-empty fields."""
        result: dict[str, str | int] = {}
        for field_name in _METADATA_FIELD_MAP:
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            result[field_name] = value
        return result

    def validate_non_empty(self) -> dict[str, str | int]:
        """Return non-empty fields or raise HTTPException(422) if none."""
        fields = self.non_empty_fields()
        if not fields:
            raise HTTPException(status_code=422, detail="At least one metadata field must be provided")
        if "title" in fields and len(str(fields["title"])) > 255:
            raise HTTPException(status_code=422, detail="title must be 255 characters or fewer")
        if "author" in fields and len(str(fields["author"])) > 255:
            raise HTTPException(status_code=422, detail="author must be 255 characters or fewer")
        if "category" in fields and len(str(fields["category"])) > 100:
            raise HTTPException(status_code=422, detail="category must be 100 characters or fewer")
        if "series" in fields and len(str(fields["series"])) > 100:
            raise HTTPException(status_code=422, detail="series must be 100 characters or fewer")
        if "year" in fields:
            year_val = int(fields["year"])
            if year_val < 1000 or year_val > 2099:
                raise HTTPException(status_code=422, detail="year must be between 1000 and 2099")
        return fields


def _solr_document_exists(doc_id: str) -> bool:
    """Check if a document exists in Solr by its ID."""
    params = {
        "q": f"id:{solr_escape(doc_id)}",
        "rows": 0,
        "wt": "json",
    }
    result = query_solr(params)
    return result.get("response", {}).get("numFound", 0) > 0


def _solr_atomic_update(doc_id: str, fields: dict[str, str | int]) -> None:
    """Send an atomic update to Solr for the given fields."""
    update_doc: dict[str, Any] = {"id": doc_id}
    for field_name, value in fields.items():
        for solr_field in _METADATA_FIELD_MAP[field_name]:
            update_doc[solr_field] = {"set": value}

    update_url = f"{settings.solr_url}/{settings.solr_collection}/update/json"
    try:
        response = solr_circuit.call(
            requests.post,
            update_url,
            json=[update_doc],
            params={"commit": "true"},
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=503,
            detail="Search service temporarily unavailable — Solr circuit breaker is open",
        ) from exc
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Timed out waiting for Solr update") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Solr update request failed: {exc}") from exc


def _store_metadata_override(doc_id: str, fields: dict[str, str | int], edited_by: str) -> None:
    """Persist metadata override in Redis so re-indexing preserves manual edits."""
    override_key = f"aithena:metadata-override:{doc_id}"
    override_data: dict[str, Any] = {}
    for field_name, value in fields.items():
        for sf in _METADATA_FIELD_MAP[field_name]:
            override_data[sf] = value
    override_data["edited_by"] = edited_by
    override_data["edited_at"] = datetime.now(UTC).isoformat()

    try:
        client = _get_admin_redis_client()
        _redis_call(client.set, override_key, json.dumps(override_data))
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=503,
            detail="Redis circuit breaker is open — override store temporarily unavailable",
        ) from exc
    except Exception as exc:
        logger.warning("metadata_override_store_failed", extra={"doc_id": doc_id, "error": str(exc)})
        raise HTTPException(status_code=503, detail="Cannot store metadata override in Redis") from exc


# ---------------------------------------------------------------------------
# Phase 2: Batch metadata edit endpoints (defined before single-doc route
# so that FastAPI does not match "/batch/metadata" as {doc_id}="batch")
# ---------------------------------------------------------------------------

_BATCH_MAX_DOCUMENT_IDS = 1000
_BATCH_PAGE_SIZE = 100
_BATCH_MAX_QUERY_RESULTS = 5000


class BatchMetadataEditRequest(BaseModel):
    """Batch metadata edit by explicit document IDs."""

    document_ids: list[str]
    updates: MetadataEditRequest

    model_config = {"str_strip_whitespace": True}


class BatchMetadataByQueryRequest(BaseModel):
    """Batch metadata edit by Solr query."""

    query: str
    updates: MetadataEditRequest

    model_config = {"str_strip_whitespace": True}


def _batch_apply_updates(
    doc_ids: list[str],
    fields: dict[str, str | int],
) -> dict[str, Any]:
    """Apply metadata updates to a list of document IDs.

    Returns a batch result dict with matched/updated/failed/errors counts.
    Continues on individual document failures (partial failure handling).
    """
    matched = len(doc_ids)
    updated = 0
    failed = 0
    errors: list[dict[str, str]] = []

    for doc_id in doc_ids:
        try:
            if not _solr_document_exists(doc_id):
                failed += 1
                errors.append({"document_id": doc_id, "error": "Document does not exist"})
                continue
            _solr_atomic_update(doc_id, fields)
            _store_metadata_override(doc_id, fields, edited_by="admin")
            updated += 1
        except HTTPException as exc:
            failed += 1
            errors.append({"document_id": doc_id, "error": exc.detail})
        except Exception as exc:
            failed += 1
            logger.error("batch_update_error", extra={"doc_id": doc_id, "error": str(exc)})
            errors.append({"document_id": doc_id, "error": "Internal error updating document"})

    return {
        "matched": matched,
        "updated": updated,
        "failed": failed,
        "errors": errors,
    }


def _solr_query_document_ids(query: str, page_size: int | None = None) -> list[str]:
    """Execute a Solr query and return all matching document IDs, paginated."""
    if page_size is None:
        page_size = _BATCH_PAGE_SIZE
    all_ids: list[str] = []
    start = 0

    while True:
        params: dict[str, Any] = {
            "q": query,
            "fl": "id",
            "rows": page_size,
            "start": start,
            "wt": "json",
        }
        result = query_solr(params)
        docs = result.get("response", {}).get("docs", [])
        if not docs:
            break
        all_ids.extend(doc["id"] for doc in docs if "id" in doc)
        num_found = result.get("response", {}).get("numFound", 0)
        start += page_size
        if start >= num_found:
            break

    return all_ids


@app.patch(
    "/v1/admin/documents/batch/metadata",
    name="admin_batch_edit_metadata_v1",
    dependencies=[Depends(require_admin_auth), require_role("admin")],
)
def admin_batch_edit_metadata(body: BatchMetadataEditRequest) -> dict[str, Any]:
    """Edit metadata for multiple documents by ID.

    Applies the same field updates to every document in the list.
    Continues on individual failures and reports partial results.
    Requires both admin API key and admin JWT role (defense-in-depth).
    """
    if not body.document_ids:
        raise HTTPException(status_code=422, detail="document_ids must not be empty")
    if len(body.document_ids) > _BATCH_MAX_DOCUMENT_IDS:
        raise HTTPException(
            status_code=422,
            detail=f"Too many document IDs — maximum is {_BATCH_MAX_DOCUMENT_IDS}",
        )

    fields = body.updates.validate_non_empty()
    return _batch_apply_updates(body.document_ids, fields)


@app.patch(
    "/v1/admin/documents/batch/metadata-by-query",
    name="admin_batch_edit_metadata_by_query_v1",
    dependencies=[Depends(require_admin_auth), require_role("admin")],
)
def admin_batch_edit_metadata_by_query(body: BatchMetadataByQueryRequest) -> dict[str, Any]:
    """Edit metadata for documents matching a Solr query.

    Resolves matching document IDs via Solr search, then applies updates
    in pages.  Requires both admin API key and admin JWT role (defense-in-depth).
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")

    fields = body.updates.validate_non_empty()
    doc_ids = _solr_query_document_ids(query)

    if not doc_ids:
        return {"matched": 0, "updated": 0, "failed": 0, "errors": []}

    if len(doc_ids) > _BATCH_MAX_QUERY_RESULTS:
        raise HTTPException(
            status_code=422,
            detail=f"Query matched {len(doc_ids)} documents — maximum is {_BATCH_MAX_QUERY_RESULTS}. "
            "Use a more specific query.",
        )

    return _batch_apply_updates(doc_ids, fields)


@app.patch(
    "/v1/admin/documents/{doc_id}/metadata",
    name="admin_edit_document_metadata_v1",
    dependencies=[Depends(require_admin_auth), require_role("admin")],
)
def admin_edit_document_metadata(doc_id: str, body: MetadataEditRequest) -> dict[str, Any]:
    """Edit metadata for a single document.

    Performs a Solr atomic update and stores the override in Redis so that
    manual edits survive re-indexing.  Requires both admin API key and
    admin JWT role (defense-in-depth).
    """
    fields = body.validate_non_empty()

    if not _solr_document_exists(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")

    _solr_atomic_update(doc_id, fields)
    _store_metadata_override(doc_id, fields, edited_by="admin")

    return {
        "id": doc_id,
        "updated_fields": sorted(fields.keys()),
        "status": "ok",
        "message": "Metadata updated in Solr and override store",
    }



# ---------------------------------------------------------------------------
# Phase 4 — /v1/upload endpoint
# ---------------------------------------------------------------------------


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and limit to safe characters."""
    # Remove any directory components
    filename = Path(filename).name
    # Remove or replace unsafe characters, keep alphanumeric, dots, dashes, underscores
    filename = re.sub(r"[^\w\s\-\.]", "_", filename)
    # Remove any leading/trailing dots or spaces
    filename = filename.strip(". ")
    # Limit length
    if len(filename) > 255:
        name_part = filename.rsplit(".", 1)[0][:240]
        ext = filename.rsplit(".", 1)[1] if "." in filename else ""
        filename = f"{name_part}.{ext}" if ext else name_part
    return filename if filename else "upload.pdf"


def _validate_pdf_content(content: bytes) -> bool:
    """Validate that content starts with PDF magic number."""
    return content.startswith(b"%PDF-")


def _compute_upload_id(file_path: Path) -> str:
    """Compute upload_id as SHA256 hash of the file path (matches Solr document ID)."""
    return hashlib.sha256(str(file_path).encode()).hexdigest()


def _publish_to_queue(file_path: Path) -> None:
    """Publish file path to RabbitMQ queue for indexing (per-request connection)."""
    connection = None
    try:
        credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_pass)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.rabbitmq_host, port=settings.rabbitmq_port, credentials=credentials
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue=settings.rabbitmq_queue_name, durable=True, auto_delete=False)
        channel.basic_publish(
            exchange="",
            routing_key=settings.rabbitmq_queue_name,
            body=str(file_path),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    except pika.exceptions.AMQPError as exc:
        raise HTTPException(status_code=502, detail="Failed to enqueue document for indexing") from exc
    finally:
        if connection and not connection.is_closed:
            connection.close()


@app.post("/v1/upload", name="upload_pdf", dependencies=[require_role("admin", "user")])
async def upload_pdf(file: UploadFile, request: Request) -> dict[str, Any]:
    """Upload a PDF document for indexing.

    Accepts multipart/form-data with a PDF file, validates it, writes to the
    upload directory, and enqueues for indexing via RabbitMQ.

    Returns:
        - 202 Accepted with upload_id, filename, size
        - 400 Bad Request: invalid file type or validation failure
        - 413 Payload Too Large: file exceeds size limit
        - 429 Too Many Requests: rate limit exceeded
        - 500 Internal Server Error: storage failure
        - 502 Bad Gateway: RabbitMQ failure
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not upload_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many uploads. Please try again later.")

    # Validate content type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are accepted.")

    # Validate filename extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid filename. Must have .pdf extension.")

    # Stream file content with size limit enforcement
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    chunk_size = 8192
    content = bytearray()

    try:
        while chunk := await file.read(chunk_size):
            content.extend(chunk)
            if len(content) > max_size_bytes:
                raise HTTPException(
                    status_code=413, detail=f"File size exceeds {settings.max_upload_size_mb}MB limit"
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file") from exc

    file_size = len(content)

    # Validate PDF magic number
    if not _validate_pdf_content(content):
        raise HTTPException(status_code=400, detail="Invalid PDF file. File does not contain PDF header.")

    # Sanitize filename
    safe_filename = _sanitize_filename(file.filename)

    # Ensure upload directory exists
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # Handle filename collision with timestamp
    target_path = settings.upload_dir / safe_filename
    if target_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_stem = target_path.stem
        target_path = settings.upload_dir / f"{name_stem}_{timestamp}.pdf"

    # Write file to disk
    try:
        target_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from exc

    # Publish to RabbitMQ
    try:
        _publish_to_queue(target_path)
    except HTTPException:
        # Clean up file if RabbitMQ publish fails
        with contextlib.suppress(Exception):
            target_path.unlink(missing_ok=True)
        raise

    # Compute upload_id (matches Solr document ID for status tracking)
    upload_id = _compute_upload_id(target_path)

    return {
        "upload_id": upload_id,
        "filename": target_path.name,
        "original_filename": file.filename,
        "size": file_size,
        "status": "accepted",
        "message": "File uploaded and queued for indexing",
    }


# ---------------------------------------------------------------------------
# Collections CRUD endpoints
# ---------------------------------------------------------------------------


@app.post("/v1/collections", response_model=CollectionResponse, status_code=201)
def create_collection(body: CreateCollectionRequest, request: Request):
    user = _get_current_user(request)
    result = svc_create_collection(settings.collections_db_path, str(user.id), body.name, body.description)
    return result


@app.get("/v1/collections", response_model=list[CollectionResponse])
def list_collections(request: Request):
    user = _get_current_user(request)
    return svc_list_collections(settings.collections_db_path, str(user.id))


@app.get("/v1/collections/{collection_id}", response_model=CollectionDetailResponse)
def get_collection(collection_id: str, request: Request):
    user = _get_current_user(request)
    result = svc_get_collection(settings.collections_db_path, collection_id, str(user.id))
    if result is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return result


@app.put("/v1/collections/{collection_id}", response_model=CollectionDetailResponse)
def update_collection(collection_id: str, body: UpdateCollectionRequest, request: Request):
    user = _get_current_user(request)
    if body.name is None and body.description is None:
        raise HTTPException(status_code=422, detail="At least one of name or description must be provided")
    result = svc_update_collection(
        settings.collections_db_path, collection_id, str(user.id), name=body.name, description=body.description
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return result


@app.delete("/v1/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: str, request: Request):
    user = _get_current_user(request)
    deleted = svc_delete_collection(settings.collections_db_path, collection_id, str(user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return Response(status_code=204)


@app.post("/v1/collections/{collection_id}/items", status_code=201)
def add_collection_items(collection_id: str, body: AddItemsRequest, request: Request):
    user = _get_current_user(request)
    # Verify the collection exists and is owned by user
    col = svc_get_collection(settings.collections_db_path, collection_id, str(user.id))
    if col is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    added = svc_add_items(settings.collections_db_path, collection_id, str(user.id), body.document_ids)
    return {"added": added, "added_count": len(added)}


@app.put("/v1/collections/{collection_id}/items/reorder")
def reorder_collection_items(collection_id: str, body: ReorderItemsRequest, request: Request):
    user = _get_current_user(request)
    col = svc_get_collection(settings.collections_db_path, collection_id, str(user.id))
    if col is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    svc_reorder_items(settings.collections_db_path, collection_id, str(user.id), body.item_ids)
    return {"status": "reordered"}


@app.put("/v1/collections/{collection_id}/items/{item_id}")
def update_collection_item(collection_id: str, item_id: str, body: UpdateItemRequest, request: Request):
    user = _get_current_user(request)
    if body.note is not None and len(body.note) > settings.collections_note_max_length:
        raise HTTPException(
            status_code=422,
            detail=f"Note exceeds maximum length of {settings.collections_note_max_length} characters",
        )
    result = svc_update_item(
        settings.collections_db_path,
        collection_id,
        str(user.id),
        item_id,
        note=body.note,
        position=body.position,
        note_max_length=settings.collections_note_max_length,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return result


@app.delete("/v1/collections/{collection_id}/items/{item_id}", status_code=204)
def delete_collection_item(collection_id: str, item_id: str, request: Request):
    user = _get_current_user(request)
    removed = svc_remove_item(settings.collections_db_path, collection_id, str(user.id), item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
