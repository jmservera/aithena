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
    redis_password: str | None
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

    @property
    def select_url(self) -> str:
        return f"{self.solr_url}/{self.solr_collection}/select"


raw_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
parsed_cors_origins = _parse_origins(raw_cors_origins)
allow_credentials = (
    os.environ.get("CORS_ALLOW_CREDENTIALS", "true").lower() == "true" and "*" not in parsed_cors_origins
)

settings = Settings(
    title=os.environ.get("TITLE", TITLE),
    version=os.environ.get("VERSION", VERSION),
    commit=os.environ.get("GIT_COMMIT", GIT_COMMIT),
    built=os.environ.get("BUILD_DATE", BUILD_DATE),
    port=int(os.environ.get("PORT", "8080")),
    solr_url=os.environ.get("SOLR_URL", "http://solr:8983/solr").rstrip("/"),
    solr_collection=os.environ.get("SOLR_COLLECTION", "books"),
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
    redis_password=os.environ.get("REDIS_PASSWORD") or None,
    redis_key_pattern=os.environ.get("REDIS_KEY_PATTERN", "doc:*"),
    redis_queue_name=os.environ.get("REDIS_QUEUE_NAME", os.environ.get("QUEUE_NAME", "shortembeddings")),
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
)
