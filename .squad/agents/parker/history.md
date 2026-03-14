# Parker — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), Docker Compose, RabbitMQ, Redis, Apache Solr
- **Book library:** `/home/jmservera/booklibrary`
- **Existing Python services:** document-lister, document-indexer, embeddings-server, qdrant-search, qdrant-clean

## Learnings

<!-- Append learnings below -->

### 2026-03-14 — Copilot PR guardrails reset

- Closed 9 stale/bad-base Copilot PRs (#140, #128, #138, #127, #119, #143, #141, #145, #144) and re-opened their linked issues for fresh pickup instead of trying to salvage branches targeting the wrong base.
- Standardized reassignment guardrails on the linked issues: branch from `origin/dev`, target `dev`, stay inside the issue-specific scope fence, and do not touch files outside the stated scope.
- PR #137 (page ranges in search results) is still blocked by merge conflicts against `dev`; GitHub reports it is not cleanly mergeable and needs a local rebase/merge before it can land.
### 2026-03-14 — Ruff cleanup across Python services

- Root `ruff.toml` is the single source of truth for Python linting; Python service `pyproject.toml` files do not carry local `[tool.ruff]` overrides.
- Test suites rely on pytest-style `assert` usage, so Ruff needs per-file ignores for `S101` under `**/tests/*.py` and `e2e/*.py`; service entrypoints also keep targeted ignores for expected container/test patterns (`S104`, `S108`, `S603`).
- Post-cleanup validation passes for `solr-search`, `document-indexer`, and `document-lister` via `uv run pytest`, and `embeddings-server` passes in a clean temp venv with `huggingface_hub<0.26` plus `httpx<0.28`.

### 2026-03-14 — API contract + on-prem cleanup

- Added backward-compatible `/v1` aliases in `solr-search` for search, facets, similar-books, document serving, health, and info while keeping the legacy unversioned routes live.
- Restored the Phase 2 UI search contract on the backend by accepting `limit`, `sort`, and `fq_*` query params and returning `total` / `limit` aliases alongside the existing pagination fields.
- Removed dormant Azure dependencies from `document-lister` requirements, Dockerfile, and dead blob-storage code; import smoke is clean once the normal local runtime dependencies (`pika`, `redis`, `retry`) are available.

### 2026-03-13 — Metadata parser test fixes

- Fixed unknown-pattern fallback titles to preserve the original filename stem instead of replacing underscores with spaces.
- Stopped deep nested paths from inferring the second folder as an author; only two-level `category/author/title` paths now do that.
- Fixed real `bsal` year-range handling so `1885 - 1886` does not become a single-year value, and category acronyms like `bsal` are emitted as `BSAL`.

### 2026-03-13 — Phase 1 backend: Solr indexer rewrite

- Rewrote `document-indexer/document_indexer/__main__.py` into a RabbitMQ consumer that reads local PDFs from `/data/documents`, extracts path metadata, uploads binaries to Solr `/update/extract`, and updates Redis state with `processed` / `failed` outcomes.
- Added `document-indexer/document_indexer/metadata.py` with heuristics for the required folder patterns plus real library cases found under `/home/jmservera/booklibrary`.
- Updated `docker-compose.yml` so `document-data` bind-mounts `/home/jmservera/booklibrary`; `document-lister`, `document-indexer`, and all Solr nodes now mount that library path.
- Updated `document-indexer/document_indexer/__init__.py`, `document-indexer/requirements.txt`, and `document-indexer/Dockerfile` to remove Qdrant/Azure configuration and switch to Solr env vars (`SOLR_HOST`, `SOLR_PORT`, `SOLR_COLLECTION`, `BASE_PATH`).
- Real book library patterns observed during implementation:
  - `amades/<title> ... amades.pdf` behaves like a single-author folder; filename suffix repeats the author and should be stripped from the title.
  - `balearics/ESTUDIS_BALEARICS_01.pdf` behaves like a category/series folder; uppercase underscore filenames should keep title text and fall back to `author="Unknown"`.
  - `bsal/Bolletí ... 1885 - 1886.pdf` behaves like a category/journal folder; year ranges should not be mistaken for `Author - Title` splits, but the first year is still useful metadata.
- Validation completed with `python3 -m compileall` plus metadata smoke tests against required synthetic patterns and real sample paths from the mounted library.

### 2026-03-13T20:58 — Phase 2 GitHub Issues Assigned

- Ripley decomposed Phase 2 into issues #36–#41, all assigned to `@copilot` with squad labels and v0.4.0 milestone.
- **Your Phase 2 issues:**
  - #36: Solr FastAPI search service foundation (core `/search`, `/facets` endpoints)
  - #37–#39: Search API enhancement (filtering, PDF serving, error handling)
  - #40–#41: Integration & documentation
- Full dependency chain and rationale in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition".

**Your assignments (Phase 1–4):**
- **Phase 1:** Rewrite document-indexer for Solr Tika extraction (drop Qdrant), build metadata extraction module (path → author/title/year/category), fix docker-compose.yml volume mounting
- **Phase 2:** Build FastAPI search API with Solr `/select` wrapper (endpoints: search, facets, books/{id}, PDF serving)
- **Phase 3:** Implement embeddings indexing pipeline (post-Tika), hybrid search mode (keyword|semantic|hybrid), extend search API
- **Phase 4:** PDF upload endpoint, file watcher service (60s polling recommended over inotify for Docker reliability)

**Key technical decisions affecting your work:**
- Hybrid indexing: Solr Tika for full-text (Ph.1), app-side chunking for embeddings (Ph.3)
- Embeddings model: Standardize on `distiluse-base-multilingual-cased-v2` (fix Dockerfile/main.py mismatch)
- Search API: FastAPI (consistent Python stack)
- File watching: 60s polling over inotify

**Dependencies:** 
- Phase 1 blocked until Ash adds schema fields + you fix volume mount
- Phase 2 blocked on Phase 1 completion
- See full plan in `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

### 2026-03-13 — Cross-agent coordination (Phase 1.2–1.5)

**From Ash's schema work:**
- Ash confirmed all 11 fields in managed-schema.xml: title_s, title_t, author_s, author_t, year_i, page_count_i, file_path_s, folder_path_s, category_s, file_size_l, language_detected_s.
- copyField rules from title_t/author_t into _text_ are live. Your literal.* field population aligns with Ash's field definitions.

**From Lambert's test suite:**
- Lambert wrote 15 metadata extraction tests (11 passing, 4 failing). Review `document-indexer/tests/test_metadata.py` to validate your parser handles real library conventions (amades/ author, balearics/ category, bsal/ journal).
- Test expectations: `file_path` and `folder_path` relative to `base_path`, year ranges (1885 - 1886) must stay in title, unknown patterns conservatively fallback to title=filename, author=Unknown.

### 2026-03-13 — Phase 2 backend: Solr search service foundation

- Added `solr-search/` as a FastAPI wrapper for the `books` collection with `/search`, `/facets`, `/documents/{token}`, `/health`, and `/info` endpoints.
- Normalized Solr documents to UI-friendly JSON fields (`title`, `author`, `year`, `category`, `language`, `file_path`) and surfaced facet buckets plus highlight snippets from `content` / `_text_`.
- `document_url` now uses a URL-safe base64 token over `file_path_s`, and PDF serving validates the resolved path stays under `BASE_PATH` before streaming inline.
- Search requests run through `edismax`, reject Solr local-parameter syntax (`{!...}`), and fall back from `language_detected_s` to `language_s` so older indexed docs still facet and render correctly.
- Validation completed with `python3 -m pytest document-indexer/tests solr-search/tests -q`, `python3 -m compileall solr-search`, `docker compose config -q`, `docker compose build solr-search`, and a container smoke test against `/health`.

### 2026-03-14 — CI Workflows: Unit & Integration Tests

- Created `.github/workflows/ci.yml` with jobs for `document-indexer` and `solr-search` unit + integration tests.
- Added `solr-search/tests/test_integration.py` with 10 FastAPI endpoint tests using mocked Solr HTTP responses (no docker-compose, no real Solr).
- Integration tests cover: search results, empty queries, facets, pagination, sorting, error handling (timeout, connection errors, invalid JSON), and health/info endpoints.
- CI uses Python 3.11, pip caching, pytest with coverage reporting for unit tests.
- **Critical discovery:** FastAPI 0.99.1 + Starlette 0.27.0 requires `httpx<0.28` for TestClient compatibility. Added this constraint to the CI job installing test dependencies.
- Workflow triggers on push to `main` and `jmservera/solrstreamlitui` branches, and on PRs to `main`.
- Used concurrency groups to cancel in-progress runs on same PR.
- Validation: All 15 document-indexer tests pass, all 8 solr-search unit tests pass, all 10 solr-search integration tests pass locally.

### 2026-03-14 — Lister scan + save_state bugfixes

- Fixed `document-lister` to scan the local filesystem reliably for `*.pdf` files instead of inheriting the broken Docker default `DOCUMENT_WILDCARD=.pdf`, which matched nothing and made the service look idle after queue declaration.
- Simplified the lister scan loop to avoid redundant recursive rescans, log the active scan path/wildcard, and only enqueue PDFs.
- Made the lister Docker/Compose config explicit for `BASE_PATH=/data/documents/` and `DOCUMENT_WILDCARD=*.pdf`; `QUEUE_NAME` already matched `shortembeddings` on both lister and indexer.
- Renamed the indexer `save_state()` positional parameter so Redis state can safely include the metadata field `file_path` without raising `TypeError: multiple values for argument 'file_path'`.
- Added a regression test for `save_state(file_path=...)`, reran `document-lister/tests` and `document-indexer` pytest suites, and verified a direct local run indexed a blank PDF into Solr with Redis state updated successfully.

### 2026-03-14 — Backend Reskill: Current Service Architecture

**solr-search/ (FastAPI search API; 604 + 396 LOC)**
- Main endpoints (dual-routed for `/` and `/v1/` prefix compatibility):
  - `GET /search/` → keyword search (edismax, facets, highlight, pagination)
  - `GET /facets/` → facet aggregations (author, category, year, language)
  - `GET /documents/{document_id}` → PDF file serving with path token validation
  - `GET /books/{document_id}/similar` → kNN semantic similarity using `book_embedding` field
  - `GET /stats/` → aggregated indexing stats (processed/failed/pending counts from Redis)
  - `GET /health/` → liveness check
  - `GET /info/` → API version/title metadata
  - `GET /status/` → health aggregation for Solr, Redis, RabbitMQ with TCP probes
- Key modules: `config.py` (Settings dataclass, env-driven), `search_service.py` (Solr query builders, normalization, embedding calls)
- Search modes: `keyword` (BM25), `semantic` (embedding similarity), `hybrid` (RRF fusion)
- Embeddings integration: POST to embeddings-server `/v1/embeddings/`, expects `EmbeddingsInput.input` (string or list)
- Document token encoding: base64 URL-safe tokens for `/documents/{id}` to avoid path traversal
- CORS middleware enabled for frontend at `http://localhost:5173`

**document-indexer/ (RabbitMQ consumer; 391 LOC main)**
- Consumes from queue (default `shortembeddings`); graceful backpressure via `prefetch_count=1`
- Per document: extract metadata from path, chunk text with page tracking, upload to Solr `/update/extract`, update Redis state
- Key modules: `metadata.py` (heuristic parser for `Author - Title - Year` patterns), `chunker.py` (sliding window with page tracking), `embeddings.py` (batch calls to embeddings-server)
- Solr integration: multipart POST with literal.* metadata + PDF binary to `/update/extract`; Tika + langid chains auto-detect language
- Redis state keys: `doc:{hash_id}` with `{"file_path": "...", "status": "processed|failed", "page_count": N, "timestamp": ISO}`
- Page-aware chunking: each chunk includes `page_start_i` / `page_end_i` for highlighting in UI

**document-lister/ (filesystem scanner; 144 LOC main)**
- Polls `BASE_PATH` (default `/data/documents`) every `POLL_INTERVAL` (default 30s) for `*.pdf` files
- Per new/modified file: check Redis state, enqueue to RabbitMQ, or mark as unprocessed if modified
- Redis state keys: `/{QUEUE_NAME}/{file_path}` with `{"processed": bool, "last_modified": mtime, "timestamp": ISO}`

**embeddings-server/ (FastAPI FastText/SentenceTransformer; ~80 LOC)**
- Model: `distiluse-base-multilingual-cased-v2` (multilingual, ~512D embeddings)
- Endpoints: `POST /v1/embeddings/` (generates embeddings), `GET /v1/embeddings/model` (returns model name + dim)
- Used by both indexer (book-level embeddings during indexing) and solr-search (query embeddings for semantic search)

**Test Coverage & CI** 
- Backend tests use pytest (28 tests in solr-search, 15 in document-indexer, 5 in document-lister)
- CI workflow (`.github/workflows/ci.yml`): uses `uv` for dependency management, Python 3.11, runs unit + integration tests on dev/PR pushes
- Integration tests mock HTTP responses; no Docker-compose in test, only unit isolation
- Ruff linting runs across all Python services with per-file ignores for `S101` in tests (`assert` is allowed)

**Current API Contract (with Phase 1–3 additions)**
- `limit` / `sort` / `sort_order` query parameters
- `fq_*` filter parameters for faceted search (author, category, year, language)
- Response format: `{"results": [...], "total": N, "limit": M, "offset": O, "facets": {...}}`
- Returns `page_start_i` / `page_end_i` per hit for chunk-level search result localization

**Recent Commits & Activity**
- #159 (MERGED): Added `/v1/status/` endpoint with aggregated health probes
- #136 (STALE): Page ranges tracking — needs rebase to dev
- UV migration (#129–131): All services now use uv instead of pip for reproducible builds
- Ruff standardization (#100–105): Single root ruff.toml, auto-fix applied across services

