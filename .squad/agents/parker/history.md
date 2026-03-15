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
