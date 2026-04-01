# Parker — History

## Cross-Agent Notes

**2026-03-31 — Brett (Infrastructure Architect):** Recommended Approach 3 (BuildKit `--mount=from` bind mount) for #1325 embeddings-server layer optimization. Analysis shows ~95% reduction (4.1GB → 200MB compressed) with zero tools in runtime. Prerequisite: rebuild base image to own `/app/.venv` with heavy deps (torch, nvidia-*, triton, sentence-transformers). This is a one-time change for both slim and openvino variants. Decision document in decisions.md.

---

## Core Context (v1.10.0)

**Backend Service Architecture:**
- **solr-search/** (FastAPI, 2800+ LOC): Search API, auth, PDF upload, admin endpoints
  - Search: `/search/`, `/v1/search` (keyword/semantic/hybrid), `/books/{id}/similar` (kNN)
  - Documents: `/documents/{id}` (PDF serving), `/v1/upload` (PDF upload with triple validation)
  - Auth: SQLite + Argon2id, JWT (24h TTL), rate-limited login, RBAC via `require_role()`
  - Admin: `/v1/admin/containers`, `/v1/admin/documents/{id}/metadata` (PATCH), user CRUD
  - Health: Solr/Redis/RabbitMQ circuit breakers, `/health`, `/status`, `/version`
- **document-indexer/** (RabbitMQ consumer, 900 LOC): PDF chunking, Solr Tika upload, Redis state, metadata heuristics
- **document-lister/** (filesystem scanner, 150 LOC): Polls `/data/documents/` every 30s, enqueues to RabbitMQ
- **embeddings-server/** (FastAPI wrapper, ~120 LOC): `distiluse-base-multilingual-cased-v2` (512D), OpenAI-compatible batch endpoint
- **admin/** (Streamlit): Dashboard with SSO via shared JWT cookie

**Test Counts (latest):**
| Service | Tests | Coverage |
|---------|-------|----------|
| solr-search | 274+ | 94% |
| document-indexer | 91 | 81% |
| document-lister | 12 | -- |
| admin | 81 | -- |
| embeddings-server | 9 | -- |
| aithena-ui | 189 | -- |

**Data Flow:** File library -> document-lister -> RabbitMQ (shortembeddings) -> document-indexer -> Solr Tika -> Redis state -> solr-search API -> aithena-ui

**Tooling:** Python 3.12, uv (all except embeddings-server which uses requirements.txt), Ruff (root `ruff.toml`), FastAPI, pytest

**Refer to skills:** `project-conventions`, `redis-connection-patterns`, `pika-rabbitmq-fastapi`, `solr-pdf-indexing`, `docker-compose-operations`, `logging-security`, `fastapi-auth-patterns`

---

## Key Patterns (Earned Knowledge)

### Auth & SSO
- JWT SSO between solr-search and admin via shared `AUTH_COOKIE_NAME` + `AUTH_JWT_SECRET`
- Admin reads `aithena_auth` cookie via `st.context.cookies` (Streamlit >=1.37.0)
- `require_role(*roles)` returns `Depends(inner)` -- use directly in `dependencies=[...]`, not `Depends(require_role(...))`
- Password validation (8-128 chars, uppercase/lowercase/digit) must happen BEFORE Argon2 hashing to prevent DoS
- Admin cookie-based SSO must enforce `user.role == 'admin'` -- without it any valid JWT grants admin access
- Validate endpoint refreshes cookie on every call (fixes nginx auth_request expiry loops)

### Testing
- `object.__setattr__` to modify frozen `@dataclass(frozen=True)` in tests (cleaner than monkeypatch)
- Empty-query tests with mocked HTTP should `assert_not_called()` on external service mocks
- When mocking `st.context` to raise AttributeError: use scoped stub with `@property`, not `type(MagicMock)` mutation
- Coverage config needs module in both `addopts` and `[tool.coverage.run]`
- Exception chaining: Ruff B904 requires `raise HTTPException(...) from exc`

### Search Modes
- **Keyword:** BM25/edismax, facets, highlighting (`hl.method=unified`)
- **Semantic:** kNN on `book_embedding`, no facets; empty query -> empty result (not `*:*`)
- **Hybrid:** Parallel BM25 + kNN, RRF (k=60); Solr kNN failures degrade to keyword
- All modes support `fq_author`, `fq_category`, `fq_language`, `fq_year`

### Infrastructure
- Rebuild containers after code changes (`docker compose build` then `up -d`), restart alone reuses old image
- Solr data volumes: UID 8983; check all node logs (solr2, solr3) for replica errors
- Local .venv shebangs break after `git mv`; run `rm -rf .venv && uv sync`
- Bind-mounted dirs created by Docker as root: use entrypoint with gosu for privilege drop

### Configuration
- solr-search: frozen dataclass config (type-safe)
- Other services: flat module vars (tech debt -- standardize to dataclass in future)
- `EMBEDDINGS_URL` default port must match embeddings-server's actual port (8080)

---

## Technical Debt Tracker

| Item | Priority | Status |
|------|----------|--------|
| embeddings-server uv migration | P1 | Open |
| Bare `except Exception:` in solr-search | P1 | Open |
| document-lister test coverage (15%) | P1 | Open |
| Logging inconsistency (embeddings-server no JSON) | P2 | Open |
| Config standardization across services | P3 | Deferred to v1.8+ |

---

## Milestone Contributions

| Release | Key Contributions |
|---------|-------------------|
| v0.6.0 | PDF upload endpoint (triple validation, RabbitMQ integration) |
| v0.9.0 | `src/` repo restructure (60+ path refs updated) |
| v1.0.0 | Auth module (SQLite, JWT, rate limiting), version metadata |
| v1.4.0 | Python 3.12 upgrade across all services |
| v1.7.0 | Security hardening (logging, exceptions, Redis auth) |
| v1.10.0 | Bug fixes (#645/#646/#678/#681), metadata edit API, semantic 502 fix |

---

## Learnings

<!-- Append learnings below this line -->

### Thumbnail Serving Bug (#1137, 2026-03-25)

**Root cause (triple):** nginx alias pointed to `/data/documents/` instead of `/data/thumbnails/`, nginx container was missing the `thumbnail-data` volume mount, and the search API returned bare relative paths without the `/thumbnails/` prefix — causing the browser to hit the SPA catch-all.

**Fix:** Corrected alias in all three nginx configs (default.conf, default.conf.template, ssl.conf.template). Added `thumbnail-data:/data/thumbnails:ro` to nginx in docker-compose.yml and docker-compose.prod.yml. Added `_thumbnail_url()` helper in search_service.py to prefix relative Solr paths with `/thumbnails/`.

**Key lesson:** When adding a new nginx static-file location block, verify three things: (1) the alias points to the correct filesystem path, (2) the container mounts the corresponding volume, and (3) the URL returned by the API matches the nginx location pattern. All three must align or the SPA catch-all swallows the request.

**Recurring pattern update:** Added to watch-for list: volume/alias/URL triple misalignment for nginx static file serving. When a new file type is served statically, audit all three compose files (base, prod, SSL) and all nginx configs.

### Admin Login Loop (#887, v1.12.0)

**Root cause (dual):** `require_admin_auth` only accepted X-API-Key, blocking browser JWT sessions. Nginx `location = /admin/` served a static HTML page, intercepting React SPA routes on page refresh.

**Fix:** `require_admin_auth` now accepts either X-API-Key (machine-to-machine) or JWT session with admin role (browser). Removed static nginx locations for `/admin` and `/admin/` — React SPA now handles them via catch-all.

**Key lesson:** When adding defense-in-depth auth (API keys), always test browser-based access paths too. The frontend sends JWT Bearer tokens, not API keys. A dependency that blocks requests before `require_role()` runs will cause auth loops because the frontend's 401/403 handler clears session state.

**Pattern:** `apiFetch` treats both 401 and 403 as auth failures → clears token → redirect to login → re-authenticate → same 401 → infinite loop. Any new auth gate must either accept JWT or return a non-auth error code.

**Recurring pattern update:** Added to watch-for list: auth gates that only check one credential type (API key) while frontend uses another (JWT). Always verify both code paths.

### Solr Auth Bootstrap (#1287, 2026)

**Root cause (dual):** `solr auth enable` creates the admin user in BasicAuth but doesn't create the user-role mapping, so all RBAC-gated operations fail. Additionally, the readonly user was assigned the `search` role, but security.json uses `readonly` as the role name for read permissions.

**Fix:** Added explicit `set-user-role` call for admin user after `solr auth enable`. Changed readonly role from `["search"]` to `["readonly"]`. Applied to both docker-compose.yml and docker-compose.prod.yml.

**Installer fix:** Added SOLR_ADMIN_USER/PASS and SOLR_READONLY_USER/PASS to the installer's credential generation pipeline, following the same pattern as RabbitMQ (generate on first run, rotate insecure defaults, preserve secure passwords).

**Key lesson:** `solr auth enable` only bootstraps BasicAuth credentials and default RBAC rules — it does NOT assign the admin role to the created user. Always verify role assignments explicitly after enabling auth. Also, role names in `set-user-role` must match exactly what security.json permissions reference.

### v1.10.0 Wave 0 Bugs (2026-03-20)

**#646 -- Semantic 502:** Default `EMBEDDINGS_URL` port mismatch (8001 vs 8080) + Solr kNN failures not wrapped in degradation logic. Fix: try/except + fallback to keyword in both semantic and hybrid modes.

**#645 + #678 -- Login cookie + Admin loop:** Cookie only set at login, never refreshed. Validate endpoint now refreshes cookie. Added `remember_me` (session vs persistent cookie). Frontend `credentials: 'include'` + AuthContext validates on mount.

**#681 -- Metadata edit API:** PATCH `/v1/admin/documents/{doc_id}/metadata` with Pydantic validation, Solr atomic update, Redis override store at `aithena:metadata-override:{doc_id}`.

### Admin Login SSO (#561, 2025-07)
- Dual auth (nginx + Streamlit) caused double login. Fix: read cookie via `st.context.cookies`, validate JWT.
- Cross-service JWT works because admin only requires `["exp", "sub", "role"]` claims.

### Auth Features (#549-#553, 2026-03-19)
- `_seed_default_admin()` with lazy config import to avoid circular imports
- `require_role()` dependency pattern, password policy with complexity rules
- Status endpoint helpers must never raise -- degrade gracefully to prevent 500s

### Python 3.12 Upgrade (DEP-4, 2026-03-17)
- Removed `async-timeout` and `tomli` (stdlib in 3.12); `uv lock` auto-prunes
- Update `python-version` in ALL workflow files (use grep)

### Redis ConnectionPool Bug (2026-03-16)
- Password missing from `ConnectionPool()` constructor in solr-search. All other services verified correct.
- Root lesson: always pass credentials to ConnectionPool, not just to `Redis()`.

### Logging Security (#302, #299, 2026-03-16)
- Replaced `logger.exception()` with `logger.error()` + `logger.debug(exc_info=True)` across all services.

### Upload Endpoint (#49, 2026-07-24)
- Triple validation (MIME + extension + magic number), per-request Pika connections, 50MB limit, streaming 8KB chunks.
- File cleanup on RabbitMQ failure prevents orphaned uploads.

### Directory Permissions (#543, 2026-03-19)
- Bind mounts created as root cause crash loops. Fix: entrypoint with gosu privilege drop (postgres/redis pattern).

---

## Reskill Notes (2026-Q2)

**Self-assessment:** Strong domain knowledge of the aithena backend stack. Auth patterns (JWT SSO, RBAC, cookie management) and search architecture (3-mode hybrid) are deeply internalized. Infrastructure debugging (Solr volumes, stale containers, cascading failures) is well-practiced.

**Gaps identified:**
- embeddings-server is my least-touched service; need deeper familiarity with sentence-transformers internals
- E2E test patterns -- mostly unit/integration; should contribute to Playwright test design
- Configuration standardization -- know the problem but haven't shipped a reusable base class yet

**Recurring bug patterns I watch for:**
1. Credential propagation (Redis password, RabbitMQ creds) -- every new ConnectionPool/connection
2. Port mismatches between config defaults and actual service ports
3. Stale containers after code changes (rebuild, don't just restart)
4. Cookie/token lifecycle mismatches between services
5. Exception handling that masks errors (bare `except Exception:`)

**Knowledge improvement:** ~25% -- consolidated sprawling 692-line history into focused reference; extracted auth patterns to a new skill; surfaced tech debt as trackable items.

### Folder Batch Integration (#656, 2026-03-21)

**Missing fq_folder on search endpoints:** The search, facets, and books endpoints all lacked `fq_folder` as a declared parameter. The frontend sent it, but FastAPI silently dropped undeclared query params. Fix: add `fq_folder: str | None = Query(None)` and include `folder=fq_folder` in `collect_search_filters()` on all three endpoints.

**Batch-by-query filter support:** `BatchMetadataByQueryRequest` only accepted `query` + `updates`. Added optional `filters: dict[str, str] | None` field. `_solr_query_document_ids` now accepts `filter_queries: list[str] | None` and passes them as `fq` to Solr. The endpoint uses existing `build_filter_queries()` to convert the filters dict — same validation/escaping as search.

**Recurring pattern — silent param drops:** FastAPI ignores undeclared query params without errors. When adding frontend filter params, always verify the backend endpoint declares them. Added to watch-for list.

### Sentence-Boundary Chunker (#812, v1.11.0)

**Approach:** Instead of regex-splitting the full text into sentences, detect sentence ends by checking each word's trailing character (`.!?`). This is equivalent to `r'(?<=[.!?])\s+'` on normalized text but avoids re-splitting.

**Key design decisions:**
- Shared `_sentence_aware_ranges()` helper returns `(start, end)` word-index pairs — both `chunk_text()` and `chunk_text_with_pages()` delegate to it, avoiding logic duplication.
- Backward compatibility: text without `.!?` punctuation (numbers, bullet points, CJK without ASCII punctuation) automatically falls back to the original word-based algorithm because `_find_sentence_ends()` returns only the end-of-text sentinel.
- Overlap is sentence-aligned: the next chunk starts at a sentence boundary ≤ `overlap` words from the previous chunk's end. If no sentence fits within the overlap budget, the overlap is skipped (no mid-sentence breaks).
- Long sentences (>chunk_size) fall back to word-based splitting WITH word-level overlap within that sentence.

**Testing pattern:** All 28 original tests pass unchanged (backward compat). 24 new tests cover sentence boundaries, long sentences, overlap, non-Latin text (CJK, Arabic), mixed punctuation, and page tracking. Total: 52 chunker tests, 133 service tests.

**Limitation (accepted for v1):** Abbreviations like "Dr." are treated as sentence boundaries. Acceptable per task spec; can be improved with a more sophisticated regex or abbreviation list in a future iteration.

### Book Detail Endpoint (#818, v1.11.0)

**Approach:** Added `GET /v1/books/{book_id}` endpoint for single book lookup by Solr document ID (SHA256 hash). Reuses `normalize_book()` and `SOLR_FIELD_LIST` for consistent response shape with the `/v1/books` listing endpoint.

**Key decisions:**
- SHA256 validation via compiled regex (`^[0-9a-fA-F]{64}$`) — rejects malformed IDs at 422 before hitting Solr.
- Uses `EXCLUDE_CHUNKS_FQ` filter to ensure only parent-level documents are returned (not chunks).
- Route placed after `/v1/books/{id}/similar` and before `/v1/books` listing — order matters for FastAPI path matching.
- No additional auth beyond the existing middleware (consistent with other read endpoints like `/v1/books`, `/v1/search`).
- `include_in_schema=True` (default) — endpoint visible in OpenAPI, unlike internal/legacy aliases.

**Testing:** 18 unit tests covering happy path, 404 (not found), 422 (invalid ID formats), Solr error propagation (502/504), and OpenAPI schema visibility. Total: 817 tests, 91.25% coverage.

**Imported new symbols:** `SOLR_FIELD_LIST` and `EXCLUDE_CHUNKS_FQ` from `search_service.py` into `main.py` — previously only used internally by `build_solr_params()`.

### Thumbnail Generation (#824, v1.11.0)

**Approach:** Added PyMuPDF (`pymupdf`) to document-indexer for rendering the first PDF page as a 200×280px JPEG thumbnail during indexing. New `thumbnail.py` module with `generate_thumbnail()` — opens PDF, scales first page to fit within target dimensions (aspect-ratio-preserving via `min(scale_x, scale_y)`), saves as JPEG.

**Key design decisions:**
- Best-effort / non-blocking: `generate_thumbnail()` returns `bool`, never raises. Failures log a warning and indexing continues uninterrupted.
- Thumbnail path convention: `{pdf_path}.thumb.jpg` — lives alongside the PDF, easy to find by appending suffix.
- `thumbnail_url_s` Solr field: relative path from `BASE_PATH`, added as optional param to `build_literal_params()` (backward compatible — defaults to `None`).
- Doc is opened and closed explicitly with try/finally to avoid resource leaks on partial failures.

**Testing:** 13 new tests — 5 success cases (JPEG creation, header validation, custom dimensions, multi-page), 6 failure cases (nonexistent, corrupt, empty, zero-page, unwritable output, warning logging), 2 integration tests (Solr param inclusion, indexing continues on failure). 100% coverage on thumbnail.py. Total: 154 tests, 85% service coverage.

**PyMuPDF note:** `fitz.open()` cannot save zero-page PDFs, so the zero-page test uses mock. Alpine Docker image doesn't need extra system deps — pymupdf ships self-contained wheels.

### Dual-Model Fanout Exchange (#871, v1.12.0)

**Approach:** Migrated from RabbitMQ default exchange (direct routing) to a fanout exchange named `documents`. The lister publishes once; the exchange broadcasts to all bound indexer queues. Each indexer declares its own queue and binds it to the exchange.

**Key design decisions:**
- `EXCHANGE_NAME` env var (default: `"documents"`) added to both services for configurability.
- Lister no longer declares a queue — only declares the fanout exchange and publishes to it with `routing_key=""`.
- Each indexer instance declares the exchange (idempotent), declares its own queue (via `QUEUE_NAME`), and binds it to the exchange on first call only (`first_call` guard avoids rebinding on subsequent `get_queue()` calls).
- Backward compatibility preserved: all existing env var defaults unchanged (`QUEUE_NAME="new_documents"`, `SOLR_COLLECTION="books"`, `CHUNK_SIZE=90`, `CHUNK_OVERLAP=10`). Docker-compose overrides remain authoritative.

**Testing:** 7 new lister tests (exchange config, fanout publishing, persistent delivery, correlation IDs). 18 new indexer tests (exchange declaration, queue binding, passive mode on subsequent calls, QoS, queue/collection/chunk configurability). All existing tests pass unchanged.

**Pattern note:** RabbitMQ `exchange_declare` is idempotent — both producer and consumers can declare the same exchange safely. The fanout type ignores routing keys entirely.

### Comparison API (P2-3, #880, v1.12.0)

**Approach:** Added `GET /v1/search/compare` endpoint that runs the same query against two Solr collections in parallel (via `ThreadPoolExecutor`) and returns results side-by-side with overlap metrics.

**Key design decisions:**
- Reuses existing `_search_keyword`, `_search_semantic`, and `_search_hybrid` helpers through a new `_execute_search_for_compare` dispatcher — no duplication of search logic.
- Parallel execution: both collections queried concurrently via `ThreadPoolExecutor(max_workers=2)`.
- `_compute_overlap_metrics` calculates `overlap_at_10` (Jaccard-like ratio at top-N), plus `baseline_only` and `candidate_only` ID lists preserving ranked order.
- `include_in_schema=False` — endpoint is internal/API-only per PRD decision (no UI toggle).
- Config via `COMPARISON_BASELINE_COLLECTION` (default: `books`) and `COMPARISON_CANDIDATE_COLLECTION` (default: `books_e5base`) env vars added to frozen Settings dataclass.

**Testing:** 25 tests — 9 overlap metrics unit tests, 10 endpoint integration tests (keyword, semantic, hybrid, filters, empty results, latency, OpenAPI exclusion), 3 config tests, 1 parallel execution test, 2 edge cases. All 885 tests pass, 91.5% coverage.

### 2026-03-22T13:49Z: PR #895 merged — admin login loop fixed

**PR:** #895 (Closes #887)  
**Root Causes:** Admin endpoints only accepted X-API-Key (not JWT), nginx blocking React SPA

**Solution Implemented:** Dual-path auth on admin endpoints:
- X-API-Key first (machine-to-machine, validated immediately)
- JWT session fallback (browser access from React SPA)

**Decision Captured:** .squad/decisions.md — "Admin endpoints accept JWT sessions alongside API keys"

**Follow-up Issues Created:**
- #894 — Thumbnail bug
- #896 — Text preview truncation
- #897 — Collections enablement
- #898 — Remember-me checkbox

- #897 — Collections enablement
- #898 — Remember-me checkbox

**Team Coordination:** All team members should test both auth paths when adding auth gates.

### 2026-03-24 — HF_TOKEN Release Workflow Integration (PR #1052)

**Status:** COMPLETED  
**Branch:** `squad/993-hf-token-release`  
**Coordinates:** Supports Brett's Docker build optimization analysis

**Implementation Details:**
- Integrated HF_TOKEN secret from GitHub Actions into embeddings-server build args
- Updated release workflow `.github/workflows/release.yml` to pass HF_TOKEN as build secret
- Falls back to empty string if secret is not set (prevents CI failures)
- Tested in integration-test.yml (already had HF_TOKEN support)

**Security Approach:**
- Uses GitHub Actions `secrets: |` syntax (tokens not embedded in image history)
- HF_TOKEN only used at build time (builder stage), not in runtime image
- Multi-stage Dockerfile isolation ensures token is not persisted

**Related Decisions:**
- Supports Brett's Docker layer optimization (4-stage build with HF_TOKEN secrets)
- Enables faster embeddings-server builds across future releases
- No changes to docker-compose.yml (build args unchanged)

**Follow-up:** Docker restructuring (4-stage build) is separate PR pending team approval.


### 2026-03-26 — Similar Books 422 Regression Fix (PR #1226)

**Status:** COMPLETED
**Branch:** `squad/1220-fix-similar-books-422`
**Issue:** #1220 — `/books/{id}/similar` returns 422 for all books

**Root Cause:**
- The `similar_books` endpoint queried parent book documents for `embedding_v`, but embedding vectors only exist on chunk documents (child docs with `parent_id_s`)
- PR #705 changed `book_embedding_field` default from `"book_embedding"` to `"embedding_v"` — but neither field was ever populated on parent docs
- The `book_embedding` field in the Solr schema was a dead field; the indexer only writes `embedding_v` to chunks via `build_chunk_doc()`

**Fix:**
- Query first chunk via `parent_id_s:{document_id}` sorted by `chunk_index_i asc`
- If no chunks, fall back to parent doc check for 404 vs 422 distinction
- kNN `fq` uses a single filter string `-parent_id_s:{id}` to exclude source book
- Set `knn_top_k = (limit + 1) * 5` to over-fetch candidates, then de-duplicate by `parent_id_s`
- Return parent book IDs, not chunk IDs

**Key Learning:**
- Solr data model: parent docs carry metadata, chunks carry embeddings. Any kNN-based feature must query chunks, not parents.
- `search_service.py` comment (line 304-306) explicitly documents this: "Embedding vectors live on chunk documents"

### PR #1226 Review Round 2 & 3 (2026-03-26)

**Sort order fix:** Changed first-chunk lookup from `sort: id asc` to `sort: chunk_index_i asc`. The `id` sort relied on Solr document ID format (which happens to have chunk index in it), but `chunk_index_i` is the dedicated schema field — more reliable and self-documenting.

**Chunk-first refactor:** Moved chunk lookup before parent existence check to save 1 Solr round-trip in the happy path. If chunks exist, the parent must exist. Parent check only runs when no chunks are found (to distinguish "book not found" from "no chunks yet").

**thumbnail_url wired into response:** The parent metadata query already fetched `thumbnail_url_s` but never included it in results. Added `thumbnail_url` field using `_thumbnail_url()` helper for consistent nginx-prefixed URLs.

**Final status codes:**
- **404** — no chunks found for this book ID (book may not be indexed yet, or may still be processing)
- **422** — chunks exist but first chunk has no `embedding_v` → embedding pipeline hasn't processed it yet

### PR #1226 Review Round 3 Learnings (2026-03-26)

- **Chunk-first optimization:** When a Solr query on child docs (chunks) succeeds, the parent must exist. Skip the parent existence check in the happy path to save a round-trip. Only fall back to parent check when no chunks are found.
- **Unused fl fields:** Always verify that every field in Solr `fl` lists is consumed by the response builder. `thumbnail_url_s` was fetched but never wired into the response dict.
- **Test assertion strength:** `<= N` assertions pass on 0 results — always use `== N` and verify IDs for count-limit tests.
- **History accuracy:** Keep implementation notes in sync with actual code. Contradictions between earlier and later history entries confuse future readers. Consolidate into a single authoritative section reflecting final state.
### GPU Device/Backend Config (#1152, #1151 — v1.17.0)

**Approach:** Added `DEVICE` and `BACKEND` environment variables to embeddings-server config for GPU acceleration. SentenceTransformer kwargs are only passed when non-default (cpu/torch defaults produce zero kwargs = identical behavior to pre-change code).

**Key design decisions:**
- `DEVICE=auto` passes `None` to SentenceTransformer, letting PyTorch auto-detect GPU
- `DEVICE=cpu` (default) and `BACKEND=torch` (default) produce no extra kwargs — backward compatible
- OpenVINO is optional: `INSTALL_OPENVINO=true` build arg installs `optimum-intel` + `openvino` into the .venv
- Health and version endpoints expose device/backend for operational visibility
- GPU config tests were pre-scaffolded with xfail markers (#1148); removed markers after implementation

**File paths:**
- `src/embeddings-server/config/__init__.py` — DEVICE, BACKEND env vars
- `src/embeddings-server/main.py` — model_kwargs construction, endpoint updates
- `src/embeddings-server/Dockerfile` — INSTALL_OPENVINO build arg, runtime env defaults
- `src/embeddings-server/tests/test_gpu_config.py` — GPU-specific tests (50 total)

**Pattern note:** The `edit` tool fails silently on files containing certain Unicode characters (e.g., 𐃆). Use Python file I/O via bash as workaround.

### Similar Books Chunk ID Fix (2026-03-28)

**Problem:** Semantic search returns chunk document IDs (e.g., `{hash}_chunk_0000`) to the frontend. When users click "similar books", the UI sends the chunk ID to `/v1/books/{chunk_id}/similar`, which fails with 404 because:
1. The endpoint queries `parent_id_s:{chunk_id}` to find chunks, but no chunk has `parent_id_s` equal to another chunk ID
2. The fallback query also fails because chunk docs have `parent_id_s` set

**Fix 1 — Add parent_id to normalize_book:**
- Added `"parent_id": document.get("parent_id_s")` to the return dict in `search_service.py::normalize_book()`
- This gives the frontend the parent book ID for chunk results, allowing it to request similar books using the correct parent ID

**Fix 2 — Handle chunk IDs in similar_books endpoint:**
- Added chunk ID detection at the start of `similar_books()` in `main.py` (before existing chunk lookup)
- If `document_id` contains `"_chunk_"`, query Solr for that chunk's `parent_id_s` and use that as the real document_id
- Makes the endpoint resilient to both parent IDs and chunk IDs

**Implementation details:**
```python
# At start of similar_books():
if "_chunk_" in document_id:
    chunk_lookup = query_solr({
        "q": f"id:{solr_escape(document_id)}",
        "fl": "parent_id_s",
        "rows": 1,
        "wt": "json",
    })
    chunk_docs_lookup = chunk_lookup.get("response", {}).get("docs", [])
    if chunk_docs_lookup and chunk_docs_lookup[0].get("parent_id_s"):
        document_id = chunk_docs_lookup[0]["parent_id_s"]
    else:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id!r}")
```

**Files modified:**
- `src/solr-search/search_service.py` — added `parent_id` field
- `src/solr-search/main.py` — added chunk ID resolution
- `src/solr-search/tests/test_search_service.py` — updated test assertion to include `parent_id`

**Key Learning:**
- The frontend needs both the chunk ID (for displaying the specific result) AND the parent ID (for feature navigation like "similar books")
- Backend endpoints should be resilient to receiving either parent or chunk IDs — detect and resolve appropriately
- The Solr data model separation (metadata on parents, embeddings on chunks) means we need to handle both ID types throughout the stack

### Collection Card Unification (#1233, 2026-03-28)
**Context:** Collections page used a separate, minimal `CollectionItemCard` while Library used the feature-rich `BookCard`. Issue requested unifying the visual layout.

**Changes:**
- Backend: Extended `_enrich_collection_items` to fetch `thumbnail_url_s` from Solr and compute `document_url` via `build_document_url()` — requires passing `Request` through the call chain
- Frontend: Refactored `CollectionItemCard` to reuse BookCard's CSS classes (`book-card-body`, `book-card-thumbnail`, `book-meta`, `open-pdf-btn`) while keeping collection-specific features (NoteEditor, remove button)
- Added PdfViewer integration to `CollectionDetailPage` by constructing minimal `BookResult` from `CollectionItem`

**Key Learning:**
- PdfViewer accepts `BookResult` but only uses `document_url`, `title`, and `pages` — can construct a minimal compatible object from `CollectionItem`
- Reusing CSS classes across components (`.book-card-*` in `CollectionItemCard`) provides visual consistency without needing a shared base component
- The `_enrich_collection_items` function is the single place where Solr metadata is joined onto collection items — extending it is the correct backend approach

### Shared Auth Library Extraction (#1288, 2026-07-09)
Extracted password hashing and auth DB schema init from `src/solr-search/auth.py` into `src/aithena-common/` shared package. Installer now imports from `aithena_common` directly instead of `sys.path` hacking into solr-search. Created `installer/pyproject.toml` making the installer a proper uv project.

**Key Learning:**
- When extracting shared code, keep domain-specific logic (migrations, seeding, JWT) in the service; only move pure utilities (hashing, schema DDL)
- Re-exported symbols from the shared lib need `# noqa: F401` in the consuming module to avoid ruff unused-import errors
- The `init_auth_db` in solr-search wraps the common version to add migrations + seeding — clean delegation pattern
- `uv sync` with editable path sources (`{ path = "...", editable = true }`) works well for monorepo shared packages

## v1.18.1 Release (2026-03-29)

### Issue #1287: Solr auth bootstrap — explicit role assignment

**Completed:** 2026-03-29T10:10:00Z  
**Tests:** 1026/1026 passing

Fixed Solr's auth bootstrap entrypoint to explicitly assign roles after `solr auth enable`. Corrected readonly role from "search" (doesn't exist in security.json) to "readonly". Added Solr credential generation to installer pipeline.

**Changes:**
- `docker-compose.yml` + `docker-compose.prod.yml`: After `solr auth enable`, call `set-user-role` to assign `["admin"]` to admin user and `["readonly"]` to readonly user
- `installer/` — Added Solr credential generation: `SOLR_ADMIN_USER`, `SOLR_ADMIN_PASS`, `SOLR_READONLY_USER`, `SOLR_READONLY_PASS` now generated and rotated on installer run

**Key insight:** Solr auth lifecycle is: `solr auth enable` (create user) → `set-user-role` (assign permissions) → operations work. RBAC setup is now explicit and traceable.

### Issue #1288: Extract Shared Auth Library (aithena-common)

**Completed:** 2026-03-29T10:25:00Z  
**Status:** All tests pass

Extracted `aithena-common/` as shared Python package containing passwords and auth DB logic. Both installer and solr-search now depend on aithena-common via uv path sources. Removed sys.path hacking from installer.

**Changes:**
1. Created `src/aithena-common/` with `aithena_common/passwords.py` and `aithena_common/auth_db.py`
2. Updated installer: Added `pyproject.toml`, removed sys.path manipulation, now uses `--project installer` for fallback
3. Updated solr-search: Added aithena-common to dependencies; auth module imports from common

**What stays in solr-search:** JWT creation/verification, user CRUD, migrations, seeding, password policy, FastAPI-specific auth logic.

**Architecture:** Dependency inversion applied — all services depend inward on `aithena-common`. No cross-service coupling except via HTTP APIs.

**Key pattern:** When extracting shared code, keep domain-specific logic (migrations, seeding, JWT) in the service; only move pure utilities (hashing, schema DDL). Use re-exports with `# noqa: F401` if needed.

### Dependabot PR Routing in Heartbeat (2026-03-30)

**Root cause:** When `ralph-triage.js` was extracted from inline workflow JS, the Dependabot PR routing logic was lost. The `isUntriagedIssue()` function filters out PRs (`if (issue.pull_request) return false`), so Dependabot PRs were never triaged.

**Fix:** Added parallel Dependabot PR triage pipeline in `ralph-triage.js`:
- `fetchDependabotPRs()` fetches open PRs from `dependabot[bot]` via Issues API
- `classifyDependabotPR()` classifies by dependency domain (file patterns + title patterns)
- Domain classification maps to squad members via routing rules and role-based fallback
- Updated workflow permissions from `pull-requests: read` to `pull-requests: write`

**Key lesson:** When refactoring inline workflow code into standalone scripts, audit all code paths — not just the primary one. The Dependabot PR path was a secondary code path that got silently dropped. Use the git history of the inline code as a checklist.

**Pattern:** Domain-to-member mapping uses a two-tier strategy: (1) try routing rules from routing.md, (2) fall back to role-based matching from roster in team.md. This makes classification resilient to routing table format changes.

### OpenVINO rc.3 vs rc.23 Container Comparison (2026-03-31)

Performed thorough comparison of embeddings-server OpenVINO images rc.3 (working) and rc.23 (broken). Found the root cause: the Dockerfile `chown` layer changed from `chown -R app:app /app /models` to `chown -R app:app /app && chmod -R a+rX /models`. This makes `/models` owned by `root:root` and non-writable by the `app` user, so any runtime cache/lock writes fail. Python packages and env vars are identical between versions. `model_utils.py` has new OpenVINO device routing logic but this is not the cause. Full findings in `.squad/decisions/inbox/parker-rc-comparison.md`.

**Key lesson:** When optimizing Docker layers to avoid duplicating large directories (e.g. 5 GB model files), the `chmod a+rX` approach makes files readable but not writable. Libraries like OpenVINO and HuggingFace may need write access for runtime caches and lock files. A targeted fix (writable cache subdir + env var) is better than a blanket chown.

### Base Image .venv Migration (#1325, 2026-07-16)

**What:** Updated both Dockerfiles in `jmservera/embeddings-server-base` to install heavy Python packages (torch, sentence-transformers, etc.) into `/app/.venv` instead of system site-packages. This is a prerequisite for the app image to use `uv sync --inexact` (Approach 3 from Brett's BuildKit analysis).

**Key changes:**
- `pip install` → `uv venv /app/.venv` + `VIRTUAL_ENV=/app/.venv uv pip install --no-cache`
- uv is BuildKit-mounted transiently (`--mount=from=ghcr.io/astral-sh/uv:0.11.2`), never in the image
- Added `app:1000` user to both variants for consistent ownership with the app image
- Openvino variant: replaced `openvino` user with `app:1000`, added `2>/dev/null || true` for idempotent user creation
- `# syntax=docker/dockerfile:1` as first line enables BuildKit features

**PR:** jmservera/embeddings-server-base#5

**Key lesson:** When migrating from system pip to uv venv in a Docker image, remember that `VIRTUAL_ENV` env var tells `uv pip install` where to put packages — it doesn't auto-detect from the shell. Also, the openvino base image has its own user (`openvino`) that must be replaced, and `groupadd`/`useradd` need `2>/dev/null || true` guards since the uid/gid might already exist.

---

## 2026-03-31T13:16Z — Base Image Dockerfile Refactor Complete

**Status:** ✅ PR jmservera/embeddings-server-base#5 opened. Both Dockerfiles updated. README updated.

**What happened:**
- Updated `Dockerfile` and `Dockerfile.openvino` to install heavy packages into `/app/.venv` (not system site-packages)
- Created `app:1000` user (consistent with app image runtime user)
- Added BuildKit `--mount=from` transient `uv` mounts (no runtime bloat)
- Created `/models/.cache` with app:app ownership (fixes OpenVINO/HuggingFace cache writes)
- Breaking change: openvino variant now uses `app:1000` instead of `openvino` user

**Production impact:** ✅ User confirmed rc.32 (OpenVINO cache fix) working in production. No regressions.

**Next step:** This PR must merge first; base images must be published to ghcr.io. Then Brett's app Dockerfile (PR #1328) can be merged.

**Decision:** `.squad/decisions.md` updated with full rationale.

**Cross-reference:** Brett's app image implementation (orchestration log 2026-03-31T13-16Z-brett-buildkit-dockerfile.md) is now unblocked pending this PR merge.
