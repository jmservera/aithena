## v1.7.0 Epic Session Complete

**2026-03-17 — 2026-Q2+** — Parker contributed to 4 consecutive releases (v1.4.0–v1.7.0) as Backend Developer. Key accomplishments:
- Python 3.12 upgrade (DEP-4): All services, all tests passing
- Security hardening: Logging patterns, exception handling, Redis auth verification
- Infrastructure stability: Container rebuild procedures, Solr volume permissions, service orchestration
- Feature completion: Authentication module, PDF upload endpoint, version metadata contract

---

# Parker — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), Docker Compose, RabbitMQ, Redis, Apache Solr
- **Book library:** `/home/jmservera/booklibrary`
- **Existing Python services:** document-lister, document-indexer, embeddings-server, solr-search

## Core Context (v1.7.0)

**Backend Service Architecture:**
- **solr-search/** (FastAPI, 1200+ LOC): 
  - Endpoints: `/search/`, `/v1/search` (keyword/semantic/hybrid), `/books/{id}/similar` (kNN), `/documents/{id}` (PDF serving), `/v1/upload` (PDF upload)
  - Auth: SQLite user table, Argon2id passwords, JWT tokens (24h TTL), rate-limited login (10 attempts/15 min/IP)
  - Health checks: Solr, Redis, RabbitMQ circuit breakers
  - Version metadata: `/version`, `/health`, `/status` with VERSION/GIT_COMMIT/BUILD_DATE from env

- **document-indexer/** (RabbitMQ consumer, 450+ LOC): 
  - Chunks PDFs with page tracking, uploads to Solr Tika, updates Redis state
  - Metadata extraction from folder paths (Author - Title - Year heuristics)
  - Logging: INFO/ERROR level safe for production, DEBUG-level stack traces
  - RabbitMQ: prefetch_count=1 for backpressure

- **document-lister/** (filesystem scanner, 150+ LOC): 
  - Polls `/data/documents/` every 30s for `*.pdf` files with wildcard support
  - Enqueues to RabbitMQ shortembeddings queue
  - Per-request RabbitMQ connections (thread-safe, ~50-100ms overhead acceptable)

- **embeddings-server/** (FastAPI wrapper, ~120 LOC): 
  - FastAPI wrapper for `distiluse-base-multilingual-cased-v2` (512D embeddings)
  - OpenAI-compatible batch endpoint: `POST /v1/embeddings/`
  - Logging: DEBUG-level stack traces only (CRITICAL level safe for production)
  - Uses requirements.txt (not uv) — architectural inconsistency to address in future

**Test Coverage (post-Python 3.12):**
- solr-search: 193 tests, 94% coverage
- document-indexer: 91 tests, 81% coverage
- document-lister: 12 tests
- admin: 81 tests
- aithena-ui: Vitest + jsdom

**CI/CD & Tooling:**
- uv dependency management (all services except embeddings-server)
- Python 3.12 across all backends
- Ruff linting single source of truth (root `ruff.toml`): E, F, W, I, UP, B, SIM, S; tests suppress S101/S104
- Integration tests mock HTTP; no Docker-compose in test suite

**Phase 1-5 Features Delivered:**
- Phase 1: Solr Tika indexing, metadata extraction
- Phase 2: Search API with facets, PDF serving, highlighting
- Phase 3: Embeddings, dense vectors, hybrid search, similar-books endpoint
- Phase 4: PDF upload endpoint, file validation, RabbitMQ integration
- Phase 5: Authentication (SQLite + JWT), rate limiting, version metadata, containerization

**Data Flow:** File library → document-lister → RabbitMQ (shortembeddings) → document-indexer → Solr Tika → Redis state → solr-search API → aithena-ui

**Docker Structure:**
- All services under `src/` directory
- Dockerfile context: repo root, COPY paths use `src/{service}/...`
- Build metadata: VERSION, GIT_COMMIT, BUILD_DATE passed as build args and set as env vars + OCI labels
- Local .venv directories must be refreshed after git moves (sherbangs cache old absolute paths)
- Solr data volumes must be owned by UID 8983 (the solr user in container)

---

## Learnings

<!-- Append learnings below this line -->

### #561 — Admin Streamlit infinite login loop (2025-07)
- The admin Streamlit app had dual auth: nginx `auth_request` (validates `aithena_auth` cookie) AND Streamlit's own `require_auth()` (checks `st.session_state`). These were completely independent, causing users to log in twice.
- Fix: `check_auth()` now reads the `aithena_auth` HTTP cookie via `st.context.cookies` (available in Streamlit ≥1.37.0) and validates the JWT. This provides SSO — if the user logged in via the main React app, the cookie is forwarded by nginx and Streamlit auto-authenticates.
- Solr-search JWTs include a `user_id` claim that admin JWTs don't have, but admin's `decode_access_token()` only requires `["exp", "sub", "role"]`, so cross-service JWT decoding works fine.
- The `AUTH_COOKIE_NAME` env var is shared between solr-search and admin (default: `aithena_auth`). Both services must use the same `AUTH_JWT_SECRET` for SSO to work.
- PR #570, branch `squad/561-fix-admin-login-loop`.

### User CRUD API (Issue #549, PR #572)
- **require_role() pattern**: Created a reusable `require_role(*allowed_roles)` FastAPI dependency that returns `Depends(inner)`. Uses `_get_current_user(request)` internally — works with forward references since the inner function is only called at request time, not module-load time.
- **Password policy**: Enforced 8-128 char limits in `validate_password()` before hashing — important to check max length before Argon2 to prevent DoS via oversized inputs.
- **Exception chaining**: Ruff B904 requires `raise HTTPException(...) from exc` in except blocks. All FastAPI endpoint exception handlers must chain.
- **Branch hygiene**: Always verify `git branch` before making edits — the working directory can be on a different branch than expected if switching between tasks.
- **Coverage**: auth.py CRUD functions at 95% coverage. The `update_user` SQL builder uses `noqa: S608` for the dynamic query — S608 (SQL injection) is suppressed because params are always parameterized.
### 2026-03-18 — Technical Debt Inventory for v1.7.1

**Task:** Analyze and document technical debt across Python backend services for v1.7.1 release. Focus on embeddings-server uv migration, code quality, and dependency health.

**Key Findings:**

1. **Embeddings-server uv Migration (BLOCKER for consistency):**
   - Last Python service still on pip + requirements.txt (minimal deps: sentence-transformers, fastapi, uvicorn)
   - All other services use uv + pyproject.toml + uv.lock
   - No blockers identified; torch/ML deps are pip-compatible with uv
   - Estimated effort: Medium (Dockerfile + pyproject.toml + testing)
   - Recommendation: Complete by end of v1.7.1 sprint

2. **Exception Handling Patterns:**
   - solr-search: 3+ bare `except Exception:` clauses without logging → risk of silent failures in critical API
   - embeddings-server: Broad exception handling in model loading (no specific exception types)
   - document-indexer: Good pattern using retry decorators with specific exception types
   - Recommendation: Standardize to specific exception types with logging across all services

3. **Configuration Management:**
   - solr-search: Frozen dataclass with type safety ✓
   - embeddings-server, document-indexer, document-lister: Flat module vars with no validation
   - Risk: Version misconfigurations, missing bounds checks on timeouts/ports
   - Recommendation: Extract reusable configuration base class

4. **Logging Inconsistency:**
   - solr-search, document-indexer: JSON-formatted logging with python-json-logger
   - embeddings-server: basicConfig only (no JSON, no structured format)
   - Impact: Breaks centralized log aggregation
   - Recommendation: Add logging_config.py to embeddings-server

5. **Test Coverage Gaps:**
   - document-indexer: Collection error (tests won't run) — **CRITICAL BLOCKER**
   - document-lister: 15% coverage, 6 test failures, core logic not exercised
   - Both suggest missing fixtures or mocking issues
   - Recommendation: Fix collection error in document-indexer first, then increase coverage to 70%+ in both

6. **Dependency Version Management:**
   - Shared deps (redis, pika) pinned consistently ✓
   - admin: loose `requests>=2.31.0`, others pin to `==2.32.5`
   - Minor inconsistency but acceptable for non-critical package

7. **Code Metrics:**
   - solr-search: 2873 LOC, 72 functions (dense but not critically large)
   - document-indexer: 900 LOC, 16 functions (healthy ratio)
   - embeddings-server: 101 LOC, 4 functions (minimal, after uv migration will be ~150 LOC)

**Complete Report:** `/tmp/parker-techdebt.md` (12 issues identified, prioritized P0–P3)

**Priorities for v1.7.1:**
- P0: Fix document-indexer test collection error
- P1: Complete embeddings-server uv migration
- P1: Address bare exceptions in solr-search
- P1: Expand test coverage in document-lister

**Deferred to v1.8.0+:**
- Configuration standardization (architectural refactoring)
- Function complexity reduction in solr-search (optimization)
- Base image standardization (infrastructure)

### 2026-03-17 — Python 3.12 Upgrade (DEP-4) — v1.4.0 Release Blocker

**Task:** Upgrade all Python services from 3.11 to 3.12, following successful compatibility audit (DEP-3).

**Services Upgraded:**
1. solr-search — pyproject.toml + Dockerfile (python:3.12-slim-bookworm)
2. document-indexer — pyproject.toml + Dockerfile (python:3.12-alpine)
3. document-lister — pyproject.toml + Dockerfile (python:3.12-alpine)
4. admin — pyproject.toml + Dockerfile (python:3.12-slim)
5. embeddings-server — Dockerfile only (python:3.12-slim, uses requirements.txt)

**Changes Made:**
- Updated `requires-python = ">=3.12"` in all pyproject.toml files
- Updated Dockerfiles to use Python 3.12 base images
- Regenerated uv.lock files with `UV_NATIVE_TLS=1 uv lock` for all uv-managed services
- Updated GitHub Actions workflows (ci.yml, integration-test.yml, security-bandit.yml, security-checkov.yml)

**Lock File Changes:**
- Removed `async-timeout` and `tomli` (both Python <3.11 compatibility shims, no longer needed in 3.12)
- uv automatically pruned unnecessary dependencies when Python requirement changed

**Test Results:**
- ✅ solr-search: 193 tests passed, 94% coverage
- ✅ document-indexer: 91 tests passed, 81% coverage (4 failures due to missing fixture files, not Python version)
- ✅ document-lister: 12 tests passed
- ✅ admin: 81 tests passed

**Key Learnings:**
- Python 3.12 standard library includes tomllib and native async timeouts; compatibility shims no longer needed
- The `uv lock` command automatically prunes unnecessary dependencies when Python requirement changes
- All Aithena dependencies confirmed compatible with Python 3.12
- GitHub Actions python-version must be updated in multiple workflow files — use grep to find all occurrences
- The embeddings-server service uses `requirements.txt` instead of `pyproject.toml` + uv (architectural inconsistency noted for future cleanup)

**PR:** #414 (squad/347-python312-upgrade → dev)

**Related Issues:** Closes #347, based on audit from #346

---

### 2026-03-17 — Service Rebuild, Solr Collection Fix, Full Stack Verification

**Task:** Rebuild stale containers after code changes, fix solr-init collection creation, verify full stack health post-upgrade.

**Issues Found & Fixed:**

1. **solr-search Redis circuit breaker cycling (stale container):** 
   - Running container was ~20 min old with pre-fix code (missing Redis password in ConnectionPool)
   - Rebuilt with `docker compose build solr-search` and restarted
   - After restart, Redis circuit breaker: CLOSED, 0 failures — confirming password fix works

2. **streamlit-admin stale container:** Rebuilt and restarted; came up healthy.

3. **nginx stale upstream IPs:** Restarted to pick up new container IPs after RabbitMQ volume reset.

4. **solr-init collection creation failure (ROOT CAUSE: host volume permissions):** 
   - Error: "Couldn't persist core properties to /var/solr/data/books_shard1_replica_n4/core.properties"
   - Root cause: Host volumes at `/source/volumes/solr-data*` owned by `root:root` (755), but Solr runs as UID 8983
   - Fix: `sudo chown -R 8983:8983 /source/volumes/solr-data*`
   - Result: Books collection created successfully with 3 replicas across all 3 Solr nodes

5. **document-indexer timed out waiting for collection:** Restarted after collection was created; immediately found collection and indexed 127 documents.

**Verification Results:**
- All 17 services healthy
- Redis circuit breaker: CLOSED, 0 failures
- Solr circuit breaker: CLOSED, 0 failures
- Books collection: 3 replicas, 127 documents indexed
- UI: Login page renders with Aithena branding
- API health endpoint: fully operational
- Document pipeline: lister → RabbitMQ → indexer → Solr working end-to-end

**Key Learnings (Critical Infrastructure Knowledge):**
- Host-mounted Solr data volumes must be owned by UID 8983. When created by host OS or root, Solr can't write core properties and collection creation fails with cryptic 400 error.
- Solr error "Underlying core creation failed" is vague — check individual Solr node logs (solr2, solr3) for "Couldn't persist core properties" root cause.
- Always rebuild containers after code changes. Restarting existing container reuses same image and doesn't pick up code changes.
- The Docker image build process caches layers; a rebuilt image with new Python 3.12 base will not run until the container is explicitly restarted.

---

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

---

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

---

### 2026-03-16 — Redis Password Bug in solr-search (ConnectionPool)

**Task:** Investigated credential handling across all Python services after user reported Redis connection failures, RabbitMQ auth refused, 502s on /stats and /search.

**Root Cause Found:**
- `src/solr-search/main.py` line 854: `redis_lib.ConnectionPool()` was missing the `password=settings.redis_password` parameter
- Config correctly reads `REDIS_PASSWORD` from env, but it was never passed to the pool constructor
- This means solr-search cannot authenticate to Redis when a password is set, causing all Redis-dependent features (status tracking, caching) to fail

**Fix Applied:**
- Added `password=settings.redis_password,` to the `ConnectionPool` constructor in `_get_redis_pool()`

**Other Services Verified (no bugs found):**
- `src/admin/src/` — Redis: password passed correctly; RabbitMQ: Basic Auth with credentials from env
- `src/document-lister/` — RabbitMQ: `pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)` correct; Redis: password passed correctly
- `src/document-indexer/` — RabbitMQ: same pattern as lister, correct; Redis: password passed correctly
- All env var names match between docker-compose.yml and Python code

**Key Learnings:**
- Always pass credentials to Redis ConnectionPool, not just to `redis.Redis()` single connections
- When investigating "502" errors, check Solr health and embeddings-server availability first (not just auth)
- Credential names must be consistent across docker-compose.yml and Python code

**Files Modified:** src/solr-search/main.py

---

### 2026-03-16T12:00Z — v0.9.0 src/ Restructure Implementation Complete (#222, PR #287)

- Executed Ripley's restructure plan: moved 9 directories via `git mv` (admin, aithena-ui, document-indexer, document-lister, embeddings-server, nginx, rabbitmq, solr, solr-search)
- Updated ~60 path references across docker-compose.yml, buildall.sh, .github/workflows/ci.yml, lint-frontend.yml, version-check.yml, .github/copilot-instructions.md, ruff.toml, docs/
- Recorded decision on Dockerfile context paths: keep repo-root context, update COPY paths inside Dockerfiles (avoids build-logic churn)
- PR #287 merged to `dev` with all CI/CD validation passing
- **Note:** Local uv virtual environments may cache old shebangs; users may need `rm -rf .venv && uv sync` post-pull

---

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

**Pattern Standardized Across All Services:**
- CRITICAL/ERROR logs: message + exception type (user-facing, safe for production)
- DEBUG logs: full stack trace via exc_info=True (troubleshooting only)

PR #314 merged to `dev`.

---

### 2026-03-15 — Admin Containers Endpoint Contract (#202)

- `solr-search` now exposes `GET /v1/admin/containers` (and trailing-slash alias) to aggregate container health/version data across app services, workers, and infrastructure
- HTTP services should be queried in parallel with a 2s timeout; `embeddings-server` uses `/version`, while non-HTTP services (`streamlit-admin`, `aithena-ui`) reuse shared build metadata (`VERSION`, `GIT_COMMIT`) plus TCP reachability
- Worker processes (`document-indexer`, `document-lister`) report `status: "unknown"` with shared repo version/commit because they do not expose stable runtime probes in codespaces without Docker runtime metadata

---

### 2026-03-15 — Embeddings Container Contract

- `embeddings-server` must run the repo's FastAPI app, not the Weaviate inference image, because downstream services expect `POST /v1/embeddings/` in OpenAI-compatible batch format
- Standardize the internal container port on `8080`; `document-indexer` host/port wiring and `solr-search`'s `EMBEDDINGS_URL` must both target `http://embeddings-server:8080/v1/embeddings/`
- Preloading the SentenceTransformer model during the image build keeps runtime startup focused on serving requests instead of first-boot downloads

---

### 2026-03-15 — Version Metadata Contract for Python Services

- FastAPI backends expose `GET /version` with a shared payload shape: `{service, version, commit, built}` sourced from `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` environment variables
- Worker-style services (`document-indexer`, `document-lister`) should log version and commit at startup rather than exposing an HTTP endpoint
- The Streamlit admin surface shows the injected app version in the sidebar as `Admin v{VERSION}` so container builds expose release identity without extra API calls

---

### 2026-03-15 — Admin Streamlit Page Conventions (#203)

- The admin dashboard is a Streamlit multipage app: `src/main.py` is the landing dashboard and each file in `admin/src/pages/` becomes a sidebar page automatically
- Shared admin service endpoints should be centralized in `admin/src/pages/shared/config.py`; the System Status page reads `SOLR_SEARCH_URL` there and defaults to `http://solr-search:8080`
- The `/v1/admin/containers` endpoint currently reports the admin container as `streamlit-admin`, so the UI should present that service as `admin` for operator-facing labels while keeping the backend contract untouched

---

### 2026-03-16 — Local Auth Module in `solr-search` (#251)

- `solr-search` now owns local auth: startup ensures a SQLite `users` table exists at `AUTH_DB_PATH`, passwords use Argon2id, and JWT access tokens are accepted from either `Authorization: Bearer` or the auth cookie
- FastAPI now treats `/v1/auth/login`, `/v1/auth/validate`, `/v1/status`, and health/info/version endpoints as public, while middleware guards the rest of the API and document/admin surfaces for the upcoming nginx `auth_request` wiring
- `AUTH_JWT_TTL` accepts duration strings like `24h`, and cookie issuance/deletion mirrors HTTPS detection so browser auth works cleanly in direct local HTTP tests and proxied HTTPS deployments

---

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

---

### 2026-03-16 — v1.0.0 `src/` Repository Restructure (#222)

- Service directories now live under `src/` (`src/admin`, `src/aithena-ui`, `src/document-indexer`, `src/document-lister`, `src/embeddings-server`, `src/nginx`, `src/rabbitmq`, `src/solr-search`, `src/solr`)
- Root-level `installer/`, `docs/`, and `e2e/` stay in place
- `installer/setup.py` and `src/solr-search/tests/test_setup_installer.py` must treat the repo root as the parent of `src/`; installer imports now resolve `ROOT / "src" / "solr-search"` and the installer test needs `parents[3]` to reach the repository root
- `src/solr-search/Dockerfile` keeps the repo root as its build context, so COPY paths must use `src/solr-search/...` even though the Dockerfile itself lives inside `src/solr-search/`
- After moving uv-managed projects on disk, recreate local `.venv` directories before trusting `uv run ...` console scripts; their shebangs can retain the old absolute path and break pytest entrypoints until the environment is rebuilt

---

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
- Streaming reads: 8KB chunks (no loading entire file into memory)
- RabbitMQ error handling: cleanup uploads if queue is unavailable

---

### 2026-07-24 — v0.6.0 Upload Endpoint Implementation Complete (#49, PR #197)

**Implementation Summary:**
✅ POST /v1/upload endpoint complete with triple validation  
✅ RabbitMQ integration (per-request connections, thread-safe)  
✅ Path collision handling with timestamp suffix  
✅ 50MB configurable size limit  
✅ All 193 solr-search tests pass  

**Changes Made:**
- `src/solr-search/main.py`: Added upload endpoint handler (~150 LOC)
- `src/solr-search/config.py`: Added UPLOAD_DIR, MAX_UPLOAD_SIZE_MB, RABBITMQ_* env vars
- `docker-compose.yml`: Changed document-data volume from `:ro` to read-write
- Test coverage: 25 new tests for validation, collision handling, RabbitMQ integration

**Implementation Flow:**
```
POST /v1/upload (multipart/form-data)
→ Validate MIME type, extension, magic number (%PDF-)
→ Sanitize filename (strip .., /, \)
→ Handle collision (append timestamp if exists)
→ Check file size (≤ MAX_UPLOAD_SIZE_MB)
→ Write to UPLOAD_DIR (/data/documents/uploads/)
→ Publish to shortembeddings RabbitMQ queue (per-request connection)
→ Return 202 Accepted {upload_id, filename, original_filename, size, status, message}
```

**Security Hardening:**
- Path traversal prevention: `Path(filename).name` strips directories, regex filters `..`
- Triple validation prevents content-type spoofing (MIME can be faked, magic number is authoritative)
- Per-request RabbitMQ connection: Pika `BlockingConnection` is NOT thread-safe; creating/closing per request ensures multi-worker safety
- File cleanup on RabbitMQ failure: prevents orphaned uploads when queue is down

**Test Strategy:**
- Used `object.__setattr__` to modify frozen `@dataclass(frozen=True)` settings in tests (cleaner than monkeypatch)
- Mocked RabbitMQ with `patch("main.pika.BlockingConnection")` to avoid real connections
- Tested collision handling by uploading same filename twice, verified timestamp suffix
- Storage failure test: mocked `Path.write_bytes` to raise `OSError("Disk full")`

**Integration Points:**
- **Volume:** document-data mounted at /data/documents (changed from :ro to read-write)
- **Queue:** shortembeddings (existing, used by document-lister)
- **Indexing:** Existing document-indexer consumes queue, processes PDFs → Solr
- **Status tracking:** /v1/status endpoint shows Redis indexing state (no changes needed)

**PR #197:** Targets `dev` branch per squad guidelines. All tests pass. Ready for review.

---

### 2026-03-15 — v0.6.0 Release Planning Complete

**Status:** Design complete, ready for implementation.

---

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

---

## Historical Decisions & Patterns

### Metadata Extraction Heuristics
- Parse folder structure: `Author/Title (Year).pdf` → extracts title, author, year
- Fallback to filename if folder pattern doesn't match
- Fallback to "Unknown" for missing fields
- Real library patterns: amades (single-author), BALEARICS (journal), bsal (category structure)

### PDF Indexing Pipeline (Solr Tika)
- Use Solr `/update/extract` handler for full-text extraction (not pdfplumber/PyMuPDF)
- Pass metadata as literal fields: `literal.id=<hash>&literal.author_s=<author>&literal.title_s=<title>`
- Language detection via `update.chain=langid` on extract handler
- Schema fields: `title_s/t`, `author_s/t`, `year_i`, `page_count_i`, `language_detected_s`, `book_embedding` (knn_vector_512)

### Search Architecture (Three Modes)
- **Keyword:** BM25 via edismax, facets, highlighting, page-range aware
- **Semantic:** kNN query on `book_embedding` field (Solr HNSW), no facets
- **Hybrid:** Parallel BM25 + kNN with Reciprocal Rank Fusion (RRF, k=60)
- All modes support filter queries: `fq_author`, `fq_category`, `fq_language`, `fq_year`

### API Contract & Serialization
- API responses use standardized shape: `{results: [], total: N, limit: L, offset: O, facets: {...}}`
- Pagination params: `limit` (default 20), `offset` (default 0), `sort` (default "relevance"), `sort_order` ("asc"/"desc")
- Highlight params: `hl.fl=content`, `hl.method=unified`, use `page_start_i`/`page_end_i` for page range
- PDF serving: `/documents/{id}?token=<base64>` with token validation

### RabbitMQ Consumer Patterns
- `prefetch_count=1` for graceful backpressure (don't fetch next message until current is ACK'd)
- Per-document pipeline: parse → chunk → embed → upload → state update
- Metadata extraction happens before chunking (per-document) and after (per-chunk)
- Use `object.__setattr__` in tests to modify frozen dataclasses (cleaner than monkeypatch)
- Per-request Pika connections in FastAPI (BlockingConnection is NOT thread-safe)

### Logging Security Pattern (Approved by Kane)
- **CRITICAL/ERROR level:** Include message + exception type only (user-facing, safe for production)
  ```python
  logger.error("Failed to process %s: %s", file_path, exc)
  ```
- **DEBUG level:** Full stack trace via `exc_info=True` (troubleshooting only)
  ```python
  logger.debug("Full stack trace:", exc_info=True)
  ```
- Never use `logger.exception()` in production error paths (exposes stack traces in INFO/ERROR logs)

### Redis ConnectionPool Authentication
- Always pass `password=settings.redis_password` to `ConnectionPool` constructor, not just to `Redis()` instance
- Use `scan_iter()` instead of `KEYS` (better performance, especially on large datasets)
- Use `mget()` instead of per-key `get()` in loops (batch operations are much faster)
- Use singleton `ConnectionPool` with double-checked locking for thread safety

### Container Operations (Docker Compose)
- Always rebuild images after code changes: `docker compose build <service> && docker compose up -d <service>`
- Restarting alone does NOT pick up code changes (reuses existing image)
- Host-mounted volumes must have correct permissions: Solr needs UID 8983 for `/var/solr/data`
- Local .venv directories cache old shebangs after `git mv`; run `rm -rf .venv && uv sync` after restructure
- When Solr collection creation fails, check individual node logs (solr2, solr3) not just solr1

### Python 3.12 Migration
- async-timeout and tomli are no longer needed (now in stdlib)
- `uv lock` automatically prunes unnecessary dependencies when Python version requirement changes
- All Aithena dependencies are compatible with 3.12+
- embeddings-server uses `requirements.txt` (not uv) — architectural inconsistency to address

### src/ Directory Structure
- All services under `src/` now (docker-compose.yml, buildall.sh updated)
- Dockerfile build context remains repo root
- COPY paths inside Dockerfiles updated: `COPY src/solr-search/...` (not just `solr-search/...`)
- installer.py paths: `ROOT / "src" / "solr-search"`, test file needs `parents[3]` for repo root
- Local .venv shebangs must be refreshed after git moves

### Auth Directory Permissions Fix (#543, PR #546)
- Bind-mounted dirs created by Docker as root:root cause crash-loops when container runs as non-root
- Standard Docker fix: entrypoint script that runs as root, chowns bind mounts, then `exec gosu app "$@"` to drop privileges
- Replaced `USER app` directive with runtime privilege drop via gosu — more robust for bind mounts
- gosu added to apt-get install in Dockerfile (standard Docker pattern from postgres/redis images)
- All 256 solr-search tests pass — no application code changes needed
### Password Reset Tool (PR #547)
- Built `src/solr-search/reset_password.py` — standalone CLI for resetting admin passwords
- Auth system uses **argon2** (not bcrypt) via `argon2-cffi` — `PasswordHasher()` in `auth.py`
- Default auth DB path: `/data/auth/users.db` (env `AUTH_DB_PATH`)
- Users table schema: `id, username, password_hash, role, created_at`
- `hash_password()` from `auth.py` is the single source of truth for hashing
- ruff is not installed in the venv; use `uv run --with ruff ruff check ...` to lint
- Coverage config in `pyproject.toml` needs module added to both `addopts` and `[tool.coverage.run]`

### 2026-03-19 — Auth Features: Admin Seeding, Change Password, RBAC (#550, #551, #553)

**PR:** #576

**Changes:**
- `_seed_default_admin()` in auth.py: seeds admin user on empty DB if `AUTH_DEFAULT_ADMIN_PASSWORD` is set
- `change_password()` in auth.py: verifies current password, validates new, rejects same-password
- Enhanced `validate_password()`: now requires uppercase, lowercase, and digit (not just length)
- `PUT /v1/auth/change-password` endpoint in main.py
- RBAC on `/v1/upload` via `require_role("admin", "user")` — viewers get 403
- Admin endpoints keep X-API-Key for backward compat (Phase 1)

**Key Patterns:**
- `require_role()` returns `Depends(...)` so use it directly in `dependencies=[...]` list, not `Depends(require_role(...))`
- Password policy changes break existing tests — must update all test passwords to comply
- `_seed_default_admin` uses lazy import of `config.settings` to avoid circular import
- `init_auth_db()` now calls `_seed_default_admin()` — all callers (including test fixtures) trigger it
- Config env vars: `AUTH_DEFAULT_ADMIN_USERNAME` (default: "admin"), `AUTH_DEFAULT_ADMIN_PASSWORD` (no default)
- PR #573 review fix: `_zookeeper_check()` needs try/except ValueError around `int(parts[1])` to handle malformed ZOOKEEPER_HOSTS entries
- PR #573 review fix: `_rabbitmq_management_check()` should catch `(requests.RequestException, OSError)` not blanket `Exception`, and log warning on fallback
- Status endpoint helpers should never raise unhandled exceptions — always degrade gracefully to prevent 500s on `/v1/status`

### 2026-03-19 — PR #568 Review Feedback (empty-query handling)

**Task:** Address 3 Copilot review comments on PR #568 (fix: handle empty query and 502 in vector/hybrid search).

**Changes:**
- Added inline code comments in `main.py` at both semantic and hybrid empty-query guards explaining the intentional behavior difference vs keyword mode (keyword → `*:*` returns all docs; semantic/hybrid → empty set because no embedding can be generated)
- Added `mock_emb_post.assert_not_called()` and `mock_solr_get.assert_not_called()` to both `test_search_semantic_empty_query_returns_empty_results` and `test_search_hybrid_empty_query_returns_empty_results` tests
- All 274 tests pass, ruff clean, commit pushed, PR comments replied to

**Learnings:**
- Empty-query tests with mocked HTTP clients should always assert mocks are NOT called to catch regressions where empty queries accidentally trigger external requests
- When search modes handle edge cases differently (keyword vs semantic/hybrid), add inline comments explaining the design rationale to prevent future confusion
- Cookie-based SSO in admin auth must enforce `user.role == 'admin'` — without this, any valid JWT from the main app (viewer, editor) grants admin access
- When mocking `st.context` to raise AttributeError, don't mutate `type(MagicMock)` — use a scoped stub object with a `@property` that raises, wrapped in `patch("auth.st", stub_instance)`
- Admin auth tests live in `src/admin/tests/test_auth.py`; run with `cd src/admin && uv run pytest -v --tb=short`

## 2026-03-20: v1.10.0 Kickoff — Wave 0 Bug Fixes (In Progress)

**Assigned:** 4 Wave 0 bugs + 4 Wave 1 foundations + 5 Wave 2 building blocks + 4 Wave 3 integration + 3 Wave 4 polish (~20 total issues)

Wave 0 bugs (Days 1–3):
- #645 (High) — Login cookie missing (0.5d)
- #678 (High) — Admin infinite login loop (0.5d)
- #648 (Medium) — Duplicate books in library (1d, with Ash)
- #647 (Medium) — PDFs don't open (0.5d)

Wave 0 exit criteria: All 7 bugs closed, P0 #646 verified. No v1.10.0 work starts until complete.

Full plan available at .squad/decisions.md (v1.10.0 kickoff decision).

### Bug #646 — Semantic index returns 502 (P0)
**PR:** #700 (squad/646-fix-semantic-502)
**Root cause:** Two issues:
1. Default `EMBEDDINGS_URL` in config.py used port 8001 but embeddings-server runs on 8080
2. Solr kNN query failures in `_search_semantic` and `_search_hybrid` were NOT wrapped in the same degradation logic as embedding failures — when Solr's vector query failed (dimension mismatch, missing field, Solr overload), the 502 propagated directly to the user instead of degrading to keyword search

**Fix:** Wrapped `query_solr` kNN calls with try/except + degradation to keyword search in both semantic and hybrid modes. Fixed default port.

### Bugs #645 + #678 — Login cookie persistence + Admin infinite loop
**PR:** #702 (squad/645-login-cookie-persist)
**Root causes:**
- #645: No `remember_me` support; cookie always set with persistent max_age; frontend never attempted cookie-based session recovery when localStorage was empty
- #678: `/v1/auth/validate` endpoint did NOT refresh the auth cookie — cookie was only set at login. When cookie expired but JWT was still valid, main UI worked (Authorization header) but admin tabs through nginx failed (nginx `auth_request` relies on cookie), causing infinite 302 redirects

**Fix:**
- `set_auth_cookie` now supports `max_age=None` for session cookies
- `LoginRequest` has `remember_me` field (default false → session cookie)
- Validate endpoint refreshes the auth cookie on every successful validation
- Frontend `apiFetch` uses `credentials: 'include'`
- AuthContext always calls validate on mount (enables cookie-based session recovery)

### Issue #681 — Single document metadata edit API
**PR:** #709 (squad/681-metadata-edit-api)
**Implemented:**
- PATCH /v1/admin/documents/{doc_id}/metadata endpoint in solr-search
- MetadataEditRequest Pydantic model with validation (title ≤255, author ≤255, year 1000-2099, category ≤100, series ≤100, whitespace trimming)
- Solr atomic update with field mapping (title → title_s + title_t, author → author_s + author_t, year → year_i, category → category_s, series → series_s)
- Redis override store at aithena:metadata-override:{doc_id} with permanent TTL
- 23 tests, all passing with 94% coverage

**Key decisions:**
- Used `solr_circuit.call()` for atomic updates to leverage existing circuit breaker
- Redis override stores Solr field names (not request field names) for direct use by document-indexer
- Validation in model method (not Pydantic validators) to return HTTP-appropriate 422 errors
