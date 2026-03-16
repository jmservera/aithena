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
    redis_key_pattern: str
    redis_queue_name: str
    rabbitmq_host: str
    rabbitmq_port: int
    upload_dir: Path
    max_upload_size_mb: int
    rabbitmq_queue_name: str
    auth_db_path: Path
    auth_jwt_secret: str
    auth_jwt_ttl_seconds: int
    auth_cookie_name: str

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
    embeddings_url=os.environ.get("EMBEDDINGS_URL", "http://embeddings-server:8001/v1/embeddings/").rstrip("/"),
    embeddings_timeout=float(os.environ.get("EMBEDDINGS_TIMEOUT", "120")),
    default_search_mode=os.environ.get("DEFAULT_SEARCH_MODE", "keyword"),
    rrf_k=int(os.environ.get("RRF_K", "60")),
    knn_field=os.environ.get("KNN_FIELD", "book_embedding"),
    book_embedding_field=os.environ.get("BOOK_EMBEDDING_FIELD", "book_embedding"),
    redis_host=os.environ.get("REDIS_HOST", "redis"),
    redis_port=int(os.environ.get("REDIS_PORT", "6379")),
    redis_key_pattern=os.environ.get("REDIS_KEY_PATTERN", "doc:*"),
    redis_queue_name=os.environ.get("REDIS_QUEUE_NAME", os.environ.get("QUEUE_NAME", "shortembeddings")),
    rabbitmq_host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
    rabbitmq_port=int(os.environ.get("RABBITMQ_PORT", "5672")),
    upload_dir=Path(os.environ.get("UPLOAD_DIR", "/data/documents/uploads")).resolve(),
    max_upload_size_mb=int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50")),
    rabbitmq_queue_name=os.environ.get("RABBITMQ_QUEUE_NAME", "shortembeddings"),
    auth_db_path=Path(os.environ.get("AUTH_DB_PATH", "/data/auth/users.db")).resolve(),
    auth_jwt_secret=os.environ.get("AUTH_JWT_SECRET", ""),
    auth_jwt_ttl_seconds=parse_ttl_to_seconds(os.environ.get("AUTH_JWT_TTL", "24h")),
    auth_cookie_name=os.environ.get("AUTH_COOKIE_NAME", "aithena_auth"),
)
