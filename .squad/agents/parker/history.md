## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

---

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

### 2026-03-16 — Embeddings-Server Logging Security Fix (#299, PR #314)

**Task:** Fixed stack trace exposure vulnerability in embeddings-server model loading error handler.

**Changes Made:**
- Removed `exc_info=True` from CRITICAL-level log call at main.py:20
- Modified critical log to include error message and exception type: `logger.critical("Failed to load embedding model '%s': %s (%s)", MODEL_NAME, exc, type(exc).__name__)`
- Added DEBUG-level log with full stack trace: `logger.debug("Model loading stack trace:", exc_info=True)`

**Security Rationale:**
Production deployments typically run at INFO or WARNING level. Stack traces contain:
- Internal file paths and directory structure
- Library versions (dependency fingerprinting)
- Environment details
- Potentially sensitive variable values in frames

By moving `exc_info=True` to DEBUG level, we preserve debugging capability while preventing information disclosure in production logs.

**Testing Notes:**
- embeddings-server uses `requirements.txt` (not uv) — tested with venv-based pytest install
- Existing test `test_startup_fails_when_model_unavailable` validates sys.exit(1) behavior on model load failure
- Python syntax validated with `python3 -m py_compile`

**Pattern for Other Services:**
This pattern should be applied consistently:
- CRITICAL/ERROR logs: message + exception type (user-facing, safe for production)
- DEBUG logs: full stack trace via exc_info=True (troubleshooting only)

PR #314 merged to `dev`.

### 2026-03-16T12:00Z — v0.9.0 src/ Restructure Implementation Complete (#222, PR #287)

- Executed Ripley's restructure plan: moved 9 directories via `git mv` (admin, aithena-ui, document-indexer, document-lister, embeddings-server, nginx, rabbitmq, solr, solr-search).
- Updated ~60 path references across docker-compose.yml, buildall.sh, .github/workflows/ci.yml, lint-frontend.yml, version-check.yml, .github/copilot-instructions.md, ruff.toml, docs/.
- Recorded decision on Dockerfile context paths: keep repo-root context, update COPY paths inside Dockerfiles (avoids build-logic churn).
- PR #287 merged to `dev` with all CI/CD validation passing.
- Noted: local uv virtual environments may cache old shebangs; users may need `rm -rf .venv && uv sync` post-pull.

### 2026-03-15 — Admin Containers Endpoint Contract (#202)

- `solr-search` now exposes `GET /v1/admin/containers` (and trailing-slash alias) to aggregate container health/version data across app services, workers, and infrastructure.
- HTTP services should be queried in parallel with a 2s timeout; `embeddings-server` uses `/version`, while non-HTTP services (`streamlit-admin`, `aithena-ui`) reuse shared build metadata (`VERSION`, `GIT_COMMIT`) plus TCP reachability.
- Worker processes (`document-indexer`, `document-lister`) report `status: "unknown"` with shared repo version/commit because they do not expose stable runtime probes in codespaces without Docker runtime metadata.

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

### 2026-07-24 — v0.6.0 Upload Endpoint Implementation Complete (#49, PR #197)

**Task:** Implemented PDF upload endpoint for issue #49 as Copilot (Parker voice).

**Deliverables:**
- ✅ POST /v1/upload endpoint in solr-search/main.py (120 LOC)
- ✅ Triple validation: MIME type + .pdf extension + %PDF- magic number
- ✅ Filename sanitization (path traversal prevention, special char filtering, length limits)
- ✅ Per-request RabbitMQ connection (thread-safe for multi-worker FastAPI)
- ✅ Collision handling: timestamp suffix for duplicate filenames
- ✅ Comprehensive error handling: 400, 413, 500, 502 status codes
- ✅ 10 unit tests (100% edge case coverage), all 88 tests pass
- ✅ Docker Compose updates: env vars, volume mount :ro → read-write, health check deps
- ✅ Dependencies: pika>=1.3.2, python-multipart>=0.0.6

**Technical Implementation:**
```python
POST /v1/upload
→ Validate content_type=application/pdf
→ Validate .pdf extension
→ Read file content, check size ≤ MAX_UPLOAD_SIZE_MB
→ Validate %PDF- magic number
→ Sanitize filename (strip path traversal, limit chars, 255 char max)
→ Write to UPLOAD_DIR (/data/documents/uploads/)
→ Publish to shortembeddings RabbitMQ queue (per-request connection)
→ Return 202 Accepted {upload_id, filename, original_filename, size, status, message}
```

**Security Hardening:**
- Path traversal prevention: `Path(filename).name` strips directories, regex filters `..`
- Triple validation prevents content-type spoofing (MIME can be faked, magic number is authoritative)
- Per-request RabbitMQ connection: Pika `BlockingConnection` is NOT thread-safe; creating/closing per request ensures multi-worker safety (~50-100ms overhead, acceptable for async workflow)
- File cleanup on RabbitMQ failure: prevents orphaned uploads when queue is down

**Test Strategy:**
- Used `object.__setattr__` to modify frozen `@dataclass(frozen=True)` settings in tests (cleaner than monkeypatch for isolated per-test changes)
- Mocked RabbitMQ with `patch("main.pika.BlockingConnection")` to avoid real connections
- Tested collision handling by uploading same filename twice, verified timestamp suffix
- Storage failure test: mocked `Path.write_bytes` to raise `OSError("Disk full")`

**Integration Points:**
- **Volume:** document-data mounted at /data/documents (changed from :ro to read-write in docker-compose.yml)
- **Queue:** shortembeddings (existing, used by document-lister)
- **Indexing:** Existing document-indexer consumes queue, processes PDFs → Solr
- **Status tracking:** /v1/status endpoint shows Redis indexing state (no changes needed)

**Config Added to solr-search:**
```
UPLOAD_DIR=/data/documents/uploads
MAX_UPLOAD_SIZE_MB=50
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_QUEUE_NAME=shortembeddings
REDIS_HOST=redis
REDIS_PORT=6379
```

**PR #197:** Targets `dev` branch per squad guidelines. All tests pass. Ready for review.

**Follow-up Recommendations:**
1. UI integration (issue #50): Build upload form in aithena-ui that POSTs to /v1/upload
2. Status polling: UI should poll /v1/status with upload_id to show indexing progress
3. E2E test: Add full pipeline test (upload → queue → indexing → search) in e2e/
4. Monitoring: Consider logging upload metrics (file count, size distribution, RabbitMQ latency)

### 2026-03-15 — Version Metadata Contract for Python Services

- FastAPI backends expose `GET /version` with a shared payload shape: `{service, version, commit, built}` sourced from `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` environment variables.
- Worker-style services (`document-indexer`, `document-lister`) should log version and commit at startup rather than exposing an HTTP endpoint.
- The Streamlit admin surface shows the injected app version in the sidebar as `Admin v{VERSION}` so container builds expose release identity without extra API calls.

### 2026-03-15 — Admin Streamlit Page Conventions (#203)

- The admin dashboard is a Streamlit multipage app: `src/main.py` is the landing dashboard and each file in `admin/src/pages/` becomes a sidebar page automatically.
- Shared admin service endpoints should be centralized in `admin/src/pages/shared/config.py`; the System Status page reads `SOLR_SEARCH_URL` there and defaults to `http://solr-search:8080`.
- The `/v1/admin/containers` endpoint currently reports the admin container as `streamlit-admin`, so the UI should present that service as `admin` for operator-facing labels while keeping the backend contract untouched.


### 2026-03-16 — Local Auth Module in `solr-search` (#251)

- `solr-search` now owns local auth: startup ensures a SQLite `users` table exists at `AUTH_DB_PATH`, passwords use Argon2id, and JWT access tokens are accepted from either `Authorization: Bearer` or the auth cookie.
- FastAPI now treats `/v1/auth/login`, `/v1/auth/validate`, `/v1/status`, and health/info/version endpoints as public, while middleware guards the rest of the API and document/admin surfaces for the upcoming nginx `auth_request` wiring.
- `AUTH_JWT_TTL` accepts duration strings like `24h`, and cookie issuance/deletion mirrors HTTPS detection so browser auth works cleanly in direct local HTTP tests and proxied HTTPS deployments.

### 2026-03-16 — PR #263: Auth Module HTTP Endpoints Merged

**Status:** ✅ Merged to `dev`  
**Tests:** 129 pass (unit + integration)  
**Security Review:** Approved by Kane; 3 blockers fixed:
1. Hardcoded JWT secret fallback → now mandatory env var
2. Missing JWT exp enforcement → added explicit check in decode
3. No login rate limiting → Redis-backed 10 attempts/15 min per IP

**API Contract:**
- `POST /auth/login` — username/password → JWT token + secure cookie
- `POST /auth/logout` — clears auth cookie
- `GET /auth/validate` — returns current user or 401 if expired
- Rate limiting (429) on excessive failed attempts

**Next:** Ready for #252 (Login UI) and #253 (nginx auth_request gating)

### 2026-03-16 — v1.0.0 `src/` Repository Restructure (#222)

- Service directories now live under `src/` (`src/admin`, `src/aithena-ui`, `src/document-indexer`, `src/document-lister`, `src/embeddings-server`, `src/nginx`, `src/rabbitmq`, `src/solr-search`, `src/solr`). Root-level `installer/`, `docs/`, and `e2e/` stay in place.
- `installer/setup.py` and `src/solr-search/tests/test_setup_installer.py` must treat the repo root as the parent of `src/`; installer imports now resolve `ROOT / "src" / "solr-search"` and the installer test needs `parents[3]` to reach the repository root.
- `src/solr-search/Dockerfile` keeps the repo root as its build context, so COPY paths must use `src/solr-search/...` even though the Dockerfile itself lives inside `src/solr-search/`.
- After moving uv-managed projects on disk, recreate local `.venv` directories before trusting `uv run ...` console scripts; their shebangs can retain the old absolute path and break pytest entrypoints until the environment is rebuilt.

### 2026-03-16 — Issue #302: Document-Indexer Logging Security Fix (PR #310)

**Task:** Replace `logger.exception()` with `logger.error()` in production error paths to prevent information disclosure in container logs.

**Changes Made:**
- Line 379: `logger.exception("Failed to process %s", file_path)` → `logger.error("Failed to process %s: %s", file_path, exc)` + `logger.debug()` with `exc_info=True`
- Line 383: `logger.exception("Unable to persist failed state for %s", file_path)` → `logger.error("Unable to persist failed state for %s: %s", file_path, persist_exc)` + `logger.debug()` with `exc_info=True`

**Security Impact:**
- `logger.exception()` includes full stack traces with internal paths and library versions in container logs at INFO/ERROR level
- `logger.error()` logs only the error message and exception type
- `logger.debug()` with `exc_info=True` preserves full stack traces for troubleshooting when DEBUG logging is enabled

**Testing:**
- ✅ All 91 tests pass (`cd src/document-indexer && uv run pytest -v --tb=short`)
- No behavior changes, only logging output format

**Decision:** Standard practice for production error logging should be `logger.error()` for user-facing messages and `logger.debug()` with `exc_info=True` for full stack traces. Reserved `logger.exception()` for unexpected internal errors where stack traces are always needed.

### 2026-03-16 — Redis Password Bug in solr-search (ConnectionPool)

**Task:** Investigated credential handling across all Python services after user reported Redis connection failures, RabbitMQ auth refused, 502s on /stats and /search.

**Root Cause Found:**
- `src/solr-search/main.py` line 854: `redis_lib.ConnectionPool()` was missing the `password=settings.redis_password` parameter. The config correctly reads `REDIS_PASSWORD` from env, but it was never passed to the pool constructor. This means solr-search cannot authenticate to Redis when a password is set, causing all Redis-dependent features (status tracking, caching) to fail.

**Fix Applied:**
- Added `password=settings.redis_password,` to the `ConnectionPool` constructor in `_get_redis_pool()`.

**Other Services Verified (no bugs found):**
- `src/admin/src/` — Redis: password passed correctly. RabbitMQ: uses Management HTTP API with Basic Auth, credentials from env correctly.
- `src/document-lister/` — RabbitMQ: `pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)` correct. Redis: password passed correctly.
- `src/document-indexer/` — RabbitMQ: same pattern as lister, correct. Redis: password passed correctly.
- All env var names (`RABBITMQ_USER`, `RABBITMQ_PASS`, `REDIS_PASSWORD`) match between docker-compose.yml and Python code.

**502 Root Causes:**
- `/stats` 502: depends on Solr `query_solr()`. If books collection doesn't exist → Solr error → 503/502 through nginx.
- `/search` 502: same Solr dependency. Semantic/hybrid modes also need embeddings-server.
- RabbitMQ `ACCESS_REFUSED`: likely stale Docker volume with old guest credentials. Code-level credential names are correct.

**Key File Paths:**
- `src/solr-search/main.py:854` — Redis ConnectionPool (fixed)
- `src/solr-search/config.py:98` — redis_password from env
- `src/document-lister/__init__.py:5-8` — RabbitMQ env vars
- `src/document-indexer/__init__.py:3-6` — RabbitMQ env vars
- `src/admin/src/pages/shared/config.py:8-17` — All admin env vars

### 2026-03-17 — Redis auth wiring audit coordinated with Brett

**Status:** Orchestrated background agent diagnosis of service authentication wiring + systematic audit of credential propagation.

**Outcomes:**
- Found and fixed missing Redis password in solr-search ConnectionPool (main.py:854)
- Audited all other services — admin, document-lister, document-indexer all correct
- All 193 solr-search tests pass after fix
- RabbitMQ and Solr failures confirmed as non-code issues (documented in Brett's infrastructure diagnosis)

**Files Modified:** src/solr-search/main.py

**Decisions:** 2 merged to decisions.md
- `.squad/decisions.md#solr-search-Redis-ConnectionPool-Authentication`
- `.squad/decisions.md#Infrastructure-Cascading-Failures`

**Orchestration Log:** `.squad/orchestration-log/2026-03-17T08-13-parker.md`

**Cross-Coordination:** Brett diagnosed infrastructure issues independently; merged into single coordinated decision set showing full system health.
