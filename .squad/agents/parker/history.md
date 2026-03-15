# Parker — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), Docker Compose, RabbitMQ, Redis, Apache Solr
- **Book library:** `/home/jmservera/booklibrary`
- **Existing Python services:** document-lister, document-indexer, embeddings-server, solr-search

## Core Context

**Backend Service Architecture (v0.4-v0.5):**
- **solr-search/** (FastAPI, 1000 LOC): Dual `/search`, `/v1/search` endpoints; keyword/semantic/hybrid modes; `/books/{id}/similar` for kNN; `/documents/{id}` for PDF serving with token validation; health checks on Solr/Redis/RabbitMQ
- **document-indexer/** (RabbitMQ consumer, 391 LOC): Chunks PDFs with page tracking, uploads to Solr Tika, updates Redis state; metadata extraction from folder paths (Author - Title - Year heuristics)
- **document-lister/** (filesystem scanner, 144 LOC): Polls `/data/documents/` every 30s for `*.pdf` files, enqueues to RabbitMQ
- **embeddings-server/** (~80 LOC): FastAPI wrapper for `distiluse-base-multilingual-cased-v2` (512D embeddings)

**Test Coverage & CI:**
- pytest suites: 28 tests (solr-search), 15 (document-indexer), 5 (document-lister)
- CI workflow: uv dependency management, Python 3.11, unit + integration tests on dev/PR
- Ruff linting single source of truth (root `ruff.toml`), per-file `S101`/`S104` ignores in tests
- Integration tests mock HTTP; no Docker-compose in test suite

**Phase 1-3 Features Delivered:**
- Phase 1: Solr Tika indexing, metadata extraction, volume mounting fixed
- Phase 2: Search API with facets, PDF serving, page-range highlighting
- Phase 3: Embeddings indexing, dense vectors, hybrid search, similar-books endpoint
- v0.4 Release: 7 PRs merged (Search API, UI, Status/Stats tabs, PDF nav)
- v0.5 In Progress: Search mode selector, frontend tests, similar-books UI

**Known Issues:**
- #166: RabbitMQ cold-start timeout (Khepri projection registration race)
- #167: Document pipeline stalled (cascaded from #166 + depends_on condition mismatch)

## Learnings

<!-- Append learnings below -->

### 2026-03-15 — Embeddings Container Contract

- `embeddings-server` must run the repo's FastAPI app, not the Weaviate inference image, because downstream services expect `POST /v1/embeddings/` in OpenAI-compatible batch format.
- Standardize the internal container port on `8080`; `document-indexer` host/port wiring and `solr-search`'s `EMBEDDINGS_URL` must both target `http://embeddings-server:8080/v1/embeddings/`.
- Preloading the SentenceTransformer model during the image build keeps runtime startup focused on serving requests instead of first-boot downloads.


### 2026-03-14 — Backend Reskill: Current Service Architecture

**solr-search/** endpoints:
- `GET /search/` → keyword search + facets + highlight + pagination
- `GET /facets/` → author, category, year, language aggregations
- `GET /documents/{document_id}` → PDF serving (base64 token validation)
- `GET /books/{document_id}/similar` → kNN semantic search
- `GET /stats/`, `/health/`, `/info/`, `/status/` → monitoring

**Search contract:** `limit`, `sort`, `sort_order`, `fq_*` filter params; returns `results`, `total`, `limit`, `offset`, `facets`, `page_start_i`/`page_end_i` per hit.

**RabbitMQ consumer pattern:** `prefetch_count=1` for graceful backpressure; per-doc pipeline: metadata extraction → chunking (page-aware) → Solr upload → Redis state update.

**Metadata heuristics:** Real library patterns (amades single-author, BALEARICS journal, bsal category) feed folder-name parsing for author/title/year/category extraction.

**Integration:** embeddings-server called for query and document embeddings; Solr `/select` queries use BM25/kNN based on mode; Redis tracks `processed`/`failed` counts for stats endpoint.

**Recent work:** closed 9 stale copilot PRs, applied branch guardrails, fixed document-lister wildcard scanning, renamed `save_state()` param for Redis safety, added CI unit tests, uv migration across all 4 services.

### 2026-07-24 — v0.6.0 Upload Endpoint Design Review

**Task:** Reviewed Ripley's v0.6.0 release plan and designed PDF upload endpoint spec for #49.

**Key Architectural Decisions:**

1. **Reuse Existing Pipeline:** Upload endpoint writes to `/data/documents/uploads/` and publishes file paths to existing `shortembeddings` RabbitMQ queue. No duplicate indexing logic — `document-indexer` handles all PDF processing.

2. **Triple File Validation:** MIME type (`application/pdf`) + extension (`.pdf`) + magic number (`%PDF-` header) prevents content-type spoofing and ensures only valid PDFs enter the pipeline.

3. **Per-Request RabbitMQ Connection:** FastAPI runs multi-worker in production; Pika `BlockingConnection` is NOT thread-safe. Spec requires per-request connection creation/teardown (~50-100ms overhead, acceptable for async workflow).

4. **50 MB File Size Limit:** Configurable via `MAX_UPLOAD_SIZE_MB` env var. Prevents DoS attacks and disk exhaustion.

5. **Filename Collision Handling:** Append `_{YYYYMMDD}_{HHMMSS}` timestamp suffix if upload filename already exists. Preserves original name in response metadata.

**Integration Points:**
- **Volume:** Shared `document-data` volume between `solr-search` and `document-indexer` (already mounted for PDF serving)
- **Queue:** `shortembeddings` queue (existing, used by `document-lister`)
- **Redis State:** Indexing status tracked by existing `/v1/status` endpoint (no changes needed)

**API Contract:**
- `POST /v1/upload` with `multipart/form-data`
- Optional `category` parameter (deferred metadata override to future version)
- Returns 202 Accepted with `upload_id` (SHA256 hash of path, matches Solr `id`)
- Error codes: 400 (validation), 413 (size), 500 (storage), 502 (RabbitMQ)

**Security:**
- Path traversal prevention: sanitize filename to strip `..`, `/`, `\`
- Content spoofing: triple validation (MIME + extension + magic)
- Size limit: 50 MB cap

**Concerns Flagged:**
- RabbitMQ connection pooling required for thread safety (singleton pattern unsafe)
- Missing queue health check in `/v1/status` (recommend separate issue)
- Shared volume dependency (documented in spec, low risk)

**Deliverable:** Design brief saved to `.squad/decisions/inbox/parker-upload-endpoint-spec.md` with full API contract, validation rules, error handling, test requirements, and implementation checklist for @copilot.

### 2026-03-15 — v0.6.0 Release Planning Complete

**Summary:** Upload endpoint spec (#49) finalized and approved. Recorded in decisions.md. Ready for @copilot implementation after Ripley's release plan is approved.

**Key Specs Confirmed:**
- Endpoint: POST /v1/upload (202 Accepted)
- Validation: MIME type, extension, magic number (triple check)
- Size limit: 50 MB configurable
- Storage: /data/documents/uploads/ (shared volume)
- RabbitMQ: Per-request connections (thread-safe)
- Error handling: Comprehensive for validation, storage, queue failures
- Tests: ≥8 unit tests required
- Dependencies: pika, python-multipart, retry (all available)

**Next:** Awaiting Juanma approval of release plan → Issue #49 created + assigned → Implementation
