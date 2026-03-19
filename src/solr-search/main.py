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
    clear_auth_cookie,
    create_access_token,
    create_user,
    decode_access_token,
    delete_user,
    get_token_from_sources,
    get_user_by_id,
    init_auth_db,
    list_users,
    set_auth_cookie,
    update_user,
)
from circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
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


class RedisRateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, checking X-Forwarded-For then X-Real-IP."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"

    def check_rate_limit(self, request: Request) -> tuple[bool, int]:
        """Check if request is within rate limit.

        Returns:
            tuple[bool, int]: (is_allowed, retry_after_seconds)
        """
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
    response = requests.get(settings.select_url, params=params, timeout=settings.request_timeout)
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
    """Call the embeddings server; wrap errors as HTTP 502."""
    try:
        return get_query_embedding(settings.embeddings_url, text, settings.embeddings_timeout)
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Timed out waiting for embeddings server") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Embeddings server request failed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _should_degrade_to_keyword(exc: HTTPException) -> bool:
    return exc.status_code in {502, 504}


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

    if solr_cb["state"] == CircuitState.OPEN.value:
        overall = "unavailable"
    elif redis_cb["state"] == CircuitState.OPEN.value:
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
    client_ip = request.client.host if request.client else "unknown"
    if not login_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    user = authenticate_user(settings.auth_db_path, credentials.username, credentials.password)
    if user is None:
        raise _unauthorized_exception("Invalid username or password")

    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    set_auth_cookie(
        response,
        token,
        settings.auth_cookie_name,
        settings.auth_jwt_ttl_seconds,
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
def auth_validate(request: Request) -> dict[str, Any]:
    try:
        user = _authenticate_request(request)
    except AuthenticationError as exc:
        raise _unauthorized_exception(str(exc)) from exc
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
    - **semantic**: Dense vector kNN search using Solr HNSW (``book_embedding`` field).
    - **hybrid**: Reciprocal Rank Fusion of the BM25 and kNN legs.

    Supports both the Phase 2 UI contract (`limit`, `sort`, `fq_*`) and the
    newer FastAPI query parameters (`page_size`, `sort_by`, `sort_order`).

    **Rate Limit:** Configurable via ``RATE_LIMIT_REQUESTS_PER_MINUTE`` (default: 100).
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
    """Execute a Solr kNN semantic search using the ``book_embedding`` field.

    Facets and highlights degrade to empty because the kNN query path does not
    produce Solr facet counts or highlight snippets.
    """
    # Empty-query handling: semantic/hybrid modes return an empty result set
    # immediately, skipping embeddings and Solr calls entirely.  This differs
    # from keyword mode, which normalizes "" to "*:*" and returns all indexed
    # documents with facets.  The distinction exists because generating a
    # meaningful embedding from an empty string is not possible.
    if not q.strip():
        return {
            "query": q,
            "mode": "semantic",
            "sort": {"by": "score", "order": "desc"},
            "degraded": False,
            **build_pagination(0, 1, top_k),
            "results": [],
            "facets": {"author": [], "category": [], "year": [], "language": []},
        }

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
    # See semantic mode comment — same rationale: no embedding possible for "".
    if not q.strip():
        return {
            "query": q,
            "mode": "hybrid",
            "sort": {"by": "score", "order": "desc"},
            "degraded": False,
            **build_pagination(0, 1, page_size),
            "results": [],
            "facets": {"author": [], "category": [], "year": [], "language": []},
        }

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
    using Solr's kNN query against the ``book_embedding`` DenseVectorField.
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
            "streamlit-admin",
            "streamlit-admin",
            8501,
            "service",
            settings.version,
            settings.commit,
        ),
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
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.rabbitmq_host, port=settings.rabbitmq_port)
        )
        channel = connection.channel()
        channel.queue_declare(queue=settings.rabbitmq_queue_name, durable=True, auto_delete=False)
        channel.basic_publish(
            exchange="",
            routing_key=settings.rabbitmq_queue_name,
            body=str(file_path),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
    except pika.exceptions.AMQPError as exc:
        raise HTTPException(status_code=502, detail="Failed to enqueue document for indexing") from exc


@app.post("/v1/upload", name="upload_pdf")
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
