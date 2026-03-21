# Parker — History

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
