from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from auth import parse_ttl_to_seconds

TITLE = "Aithena Solr Search API"
VERSION = "dev"
GIT_COMMIT = "unknown"
BUILD_DATE = "unknown"


def _parse_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def _parse_collection_set(raw_value: str) -> frozenset[str]:
    """Parse a comma-separated string into a frozenset of collection names."""
    return frozenset(name.strip() for name in raw_value.split(",") if name.strip())


def _parse_embeddings_url_overrides(allowed: frozenset[str]) -> tuple[tuple[str, str], ...]:
    """Build a collection→embeddings-URL map from per-collection env vars.

    For each collection in *allowed*, check for an env var named
    ``EMBEDDINGS_URL_{UPPER_NAME}`` (dots and hyphens replaced with underscores).
    """
    overrides: list[tuple[str, str]] = []
    for name in sorted(allowed):
        env_key = f"EMBEDDINGS_URL_{name.upper().replace('-', '_').replace('.', '_')}"
        url = os.environ.get(env_key)
        if url:
            overrides.append((name, url))
    return tuple(overrides)


@dataclass(frozen=True)
class Settings:
    title: str
    version: str
    commit: str
    built: str
    port: int
    solr_url: str
    solr_collection: str
    base_path: Path
    request_timeout: float
    default_page_size: int
    max_page_size: int
    facet_limit: int
    cors_origins: list[str]
    allow_credentials: bool
    document_url_base: str | None
    embeddings_url: str
    embeddings_timeout: float
    default_search_mode: str
    rrf_k: int
    knn_field: str
    book_embedding_field: str
    redis_host: str
    redis_port: int
    redis_key_pattern: str
    redis_queue_name: str
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_pass: str
    upload_dir: Path
    max_upload_size_mb: int
    rabbitmq_queue_name: str
    auth_db_path: Path
    auth_jwt_secret: str
    auth_jwt_ttl_seconds: int
    auth_cookie_name: str
    cb_redis_failure_threshold: int
    cb_redis_recovery_timeout: float
    cb_solr_failure_threshold: int
    cb_solr_recovery_timeout: float
    cb_embeddings_failure_threshold: int
    cb_embeddings_recovery_timeout: float
    admin_api_key: str | None
    rate_limit_requests_per_minute: int
    rabbitmq_management_port: int
    zookeeper_hosts: str
    auth_default_admin_username: str
    auth_default_admin_password: str | None
    collections_db_path: Path
    collections_note_max_length: int
    allowed_collections: frozenset[str]
    default_collection: str
    e5_collections: frozenset[str]
    collection_embeddings_urls: tuple[tuple[str, str], ...]
    comparison_baseline_collection: str
    comparison_candidate_collection: str
    search_architecture: str = "hnsw"
    docker_host: str = ""
    rabbitmq_management_path_prefix: str = "/admin/rabbitmq"
    log_tail_max: int = 5000
    solr_auth_user: str | None = None
    solr_auth_pass: str | None = None
    ascii_folding: bool = True

    @property
    def select_url(self) -> str:
        return f"{self.solr_url}/{self.solr_collection}/select"

    @property
    def solr_auth(self) -> tuple[str, str] | None:
        """Return (user, pass) tuple for HTTP Basic Auth, or None."""
        if self.solr_auth_user and self.solr_auth_pass:
            return (self.solr_auth_user, self.solr_auth_pass)
        return None

    def select_url_for(self, collection: str) -> str:
        """Return the Solr select URL for a specific collection."""
        return f"{self.solr_url}/{collection}/select"

    def embeddings_url_for(self, collection: str) -> str:
        """Return the embeddings URL for a collection (falls back to default)."""
        overrides = dict(self.collection_embeddings_urls)
        return overrides.get(collection, self.embeddings_url)

    def is_e5_collection(self, collection: str) -> bool:
        """Return True if the collection uses an e5 model (needs input_type)."""
        return collection in self.e5_collections


raw_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
parsed_cors_origins = _parse_origins(raw_cors_origins)
allow_credentials = (
    os.environ.get("CORS_ALLOW_CREDENTIALS", "true").lower() == "true" and "*" not in parsed_cors_origins
)

_allowed_collections = _parse_collection_set(os.environ.get("ALLOWED_COLLECTIONS", "books"))

settings = Settings(
    title=os.environ.get("TITLE", TITLE),
    version=os.environ.get("VERSION", VERSION),
    commit=os.environ.get("GIT_COMMIT", GIT_COMMIT),
    built=os.environ.get("BUILD_DATE", BUILD_DATE),
    port=int(os.environ.get("PORT", "8080")),
    solr_url=os.environ.get("SOLR_URL", "http://solr:8983/solr").rstrip("/"),
    solr_collection=os.environ.get("SOLR_COLLECTION", "books"),
    solr_auth_user=os.environ.get("SOLR_AUTH_USER") or None,
    solr_auth_pass=os.environ.get("SOLR_AUTH_PASS") or None,
    base_path=Path(os.environ.get("BASE_PATH", "/data/documents")).resolve(),
    request_timeout=float(os.environ.get("SOLR_TIMEOUT", "30")),
    default_page_size=int(os.environ.get("DEFAULT_PAGE_SIZE", "20")),
    max_page_size=int(os.environ.get("MAX_PAGE_SIZE", "100")),
    facet_limit=int(os.environ.get("FACET_LIMIT", "25")),
    cors_origins=parsed_cors_origins,
    allow_credentials=allow_credentials,
    document_url_base=os.environ.get("DOCUMENT_URL_BASE", "").rstrip("/") or None,
    embeddings_url=os.environ.get("EMBEDDINGS_URL", "http://embeddings-server:8080/v1/embeddings/"),
    embeddings_timeout=float(os.environ.get("EMBEDDINGS_TIMEOUT", "120")),
    default_search_mode=os.environ.get("DEFAULT_SEARCH_MODE", "keyword"),
    rrf_k=int(os.environ.get("RRF_K", "60")),
    knn_field=os.environ.get("KNN_FIELD", "embedding_v"),
    book_embedding_field=os.environ.get("BOOK_EMBEDDING_FIELD", "embedding_v"),
    redis_host=os.environ.get("REDIS_HOST", "redis"),
    redis_port=int(os.environ.get("REDIS_PORT", "6379")),
    redis_queue_name=os.environ.get("REDIS_QUEUE_NAME", os.environ.get("QUEUE_NAME", "shortembeddings")),
    redis_key_pattern=os.environ.get(
        "REDIS_KEY_PATTERN",
        f"/{os.environ.get('REDIS_QUEUE_NAME', os.environ.get('QUEUE_NAME', 'shortembeddings'))}/*",
    ),
    rabbitmq_host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
    rabbitmq_port=int(os.environ.get("RABBITMQ_PORT", "5672")),
    rabbitmq_user=os.environ.get("RABBITMQ_USER", ""),
    rabbitmq_pass=os.environ.get("RABBITMQ_PASS", ""),
    upload_dir=Path(os.environ.get("UPLOAD_DIR", "/data/documents/uploads")).resolve(),
    max_upload_size_mb=int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50")),
    rabbitmq_queue_name=os.environ.get("RABBITMQ_QUEUE_NAME", "shortembeddings"),
    auth_db_path=Path(os.environ.get("AUTH_DB_PATH", "/data/auth/users.db")).resolve(),
    auth_jwt_secret=os.environ.get("AUTH_JWT_SECRET", "development-only-change-me"),
    auth_jwt_ttl_seconds=parse_ttl_to_seconds(os.environ.get("AUTH_JWT_TTL", "24h")),
    auth_cookie_name=os.environ.get("AUTH_COOKIE_NAME", "aithena_auth"),
    cb_redis_failure_threshold=int(os.environ.get("CB_REDIS_FAILURE_THRESHOLD", "5")),
    cb_redis_recovery_timeout=float(os.environ.get("CB_REDIS_RECOVERY_TIMEOUT", "30")),
    cb_solr_failure_threshold=int(os.environ.get("CB_SOLR_FAILURE_THRESHOLD", "5")),
    cb_solr_recovery_timeout=float(os.environ.get("CB_SOLR_RECOVERY_TIMEOUT", "30")),
    cb_embeddings_failure_threshold=int(os.environ.get("CB_EMBEDDINGS_FAILURE_THRESHOLD", "3")),
    cb_embeddings_recovery_timeout=float(os.environ.get("CB_EMBEDDINGS_RECOVERY_TIMEOUT", "30")),
    admin_api_key=os.environ.get("ADMIN_API_KEY") or None,
    rate_limit_requests_per_minute=int(os.environ.get("RATE_LIMIT_REQUESTS_PER_MINUTE", "100")),
    rabbitmq_management_port=int(os.environ.get("RABBITMQ_MANAGEMENT_PORT", "15672")),
    zookeeper_hosts=os.environ.get("ZOOKEEPER_HOSTS", "zoo1:2181"),
    auth_default_admin_username=os.environ.get("AUTH_DEFAULT_ADMIN_USERNAME", "admin").strip() or "admin",
    auth_default_admin_password=os.environ.get("AUTH_DEFAULT_ADMIN_PASSWORD") or None,
    collections_db_path=Path(os.environ.get("COLLECTIONS_DB_PATH", "/data/collections/collections.db")).resolve(),
    collections_note_max_length=int(os.environ.get("COLLECTIONS_NOTE_MAX_LENGTH", "1000")),
    allowed_collections=_allowed_collections,
    default_collection=os.environ.get("DEFAULT_COLLECTION", "books"),
    e5_collections=_parse_collection_set(os.environ.get("E5_COLLECTIONS", "books")),
    collection_embeddings_urls=_parse_embeddings_url_overrides(_allowed_collections),
    comparison_baseline_collection=os.environ.get("COMPARISON_BASELINE_COLLECTION", "books"),
    comparison_candidate_collection=os.environ.get("COMPARISON_CANDIDATE_COLLECTION", "books"),
    docker_host=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"),
    search_architecture=os.environ.get("SEARCH_ARCHITECTURE", "hnsw"),
    rabbitmq_management_path_prefix=os.environ.get("RABBITMQ_MANAGEMENT_PATH_PREFIX", "/admin/rabbitmq"),
    log_tail_max=int(os.environ.get("LOG_TAIL_MAX", "5000")),
    ascii_folding=os.environ.get("SOLR_ASCII_FOLDING", "true").lower() == "true",
)
