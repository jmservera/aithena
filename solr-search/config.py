from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


TITLE = "Aithena Solr Search API"
VERSION = "0.1.0"


def _parse_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    title: str
    version: str
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
    # Phase 3 — hybrid search
    embeddings_url: str
    embeddings_timeout: float
    default_search_mode: str
    rrf_k: int
    knn_field: str

    @property
    def select_url(self) -> str:
        return f"{self.solr_url}/{self.solr_collection}/select"


raw_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
parsed_cors_origins = _parse_origins(raw_cors_origins)
allow_credentials = (
    os.environ.get("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    and "*" not in parsed_cors_origins
)

settings = Settings(
    title=os.environ.get("TITLE", TITLE),
    version=os.environ.get("VERSION", VERSION),
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
    # Phase 3 — hybrid search
    embeddings_url=os.environ.get(
        "EMBEDDINGS_URL", "http://embeddings-server:8001/v1/embeddings/"
    ).rstrip("/"),
    embeddings_timeout=float(os.environ.get("EMBEDDINGS_TIMEOUT", "120")),
    default_search_mode=os.environ.get("DEFAULT_SEARCH_MODE", "keyword"),
    rrf_k=int(os.environ.get("RRF_K", "60")),
    knn_field=os.environ.get("KNN_FIELD", "book_embedding"),
)
