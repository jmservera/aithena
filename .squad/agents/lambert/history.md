# Lambert — History

## Core Context — Latest Verified Test Counts (v1.15.0)

**1,298+ Tests Collectable** as of v1.15.0 (2026-03-22):

| Service | Tests Collected | Type | Status | Notes |
|---------|-----------------|------|--------|-------|
| **solr-search** | 993 | pytest | ✓ | Comprehensive suite: search, auth, facets, PDF, chunking, semantic |
| **aithena-ui** | ~540+ | vitest | ✓ | 54 test files, React Testing Library + i18n coverage |
| **document-indexer** | 83 | pytest | ✓ | File import pipeline with 3 collection errors (env-dependent) |
| **document-lister** | 19 | pytest | ✓ | File watcher + RabbitMQ integration tests |
| **admin** | 116 | pytest | ✓ | Streamlit security, logging, auth—now import-safe for testing |
| **embeddings-server** | 34 | pytest | ✓ | E5 768D embeddings, in-memory store |
| **E2E Playwright** | 52 | playwright | ✓ | 10 test files covering login, search, PDF, upload, stats |
| **E2E Stress** | 5 suites | playwright | ✓ | Concurrent sessions, upload, search, admin, pagination stress tests |

**Growth trajectory:** 452 (v1.2.0) → 690 (v1.10.0) → 1,298 (v1.15.0) [+88% growth in v1.15.0]

**Quality metrics:** solr-search coverage >=91%, document-indexer >=80%, zero test flakiness in main

---

## Patterns & Conventions (Consolidated)

### Service-Specific Quirks
- **embeddings-server:** requirements.txt lacks test deps; install pytest httpx manually before running
- **document-indexer:** 4 env-dependent tests skip gracefully (RabbitMQ/Solr hosts); affects CI counts
- **admin (Streamlit):** HMAC warnings are test-only — use 256-bit keys in production
- **UV_NATIVE_TLS=1** needed for uv sync when SSL certs cause UnknownIssuer errors in codespace

### Pytest Patterns
- **Frozen dataclass patching:** object.__setattr__(settings, "field", value) in fixtures
- **Rate limiter cleanup:** autouse fixture that clears login_rate_limiter.requests before/after each test
- **Real-library fixtures:** Guard with skipif so local corpus knowledge is preserved without breaking CI
- **Arrange/Act/Assert** structure; AAA comments only when test is complex

### Playwright E2E Patterns
- **Read-only discovery:** Tests discover queries from live /v1/search/ API — no uploaded fixtures
- **Graceful skip:** try/catch + test.info().annotations for data-dependent pages (PDF, similar books, stats)
- **Sequential capture:** PDF viewer must be open before similar books panel (dependency chain)
- **Wait helpers:** waitForSearchResponse with param checks (e.g., fq_author) before assertions
- **No TypeScript compiler:** Playwright handles TS transpilation at runtime; no tsc --noEmit available

### Integration Test Patterns
- **Cross-endpoint flows** are highest-value: register->login, delete->login-fails, update->list-reflects
- **Solr health waits:** Poll CLUSTERSTATUS API until all replicas ACTIVE before running tests
- **RBAC testing:** require_role() returns 403 (wrong role) vs 401 (unauthenticated)
- **Username uniqueness:** Case-insensitive via COLLATE NOCASE

### CI Strategy (5-Tier Fast Test Suite)
- **Tier 1 (P0):** 219 existing tests added to ci.yml — zero new test code, CI config only
- **Tier 2-5:** API contracts, smoke tests, config validators, mock integrations (future)
- **Goal:** <2 min fast feedback; full E2E reserved for release gates on main

---

## Key Deliverables Log

### v1.10.0 (2026-03-20) — Current
- **PR #724:** 26 new tests (20 folder facet edge cases + 6 chunk embedding/semantic search)
- **CI reliability:** Solr health retries 10->15, timeout 5->10s, start_period 30->60s; CLUSTERSTATUS polling
- **PRD decomposition:** Stress Testing PRD -> 9 issues across 4 team members
- **Bug investigation lead:** P0 #646 (semantic index 502)

### v1.8.0 (2026-03-19)
- **PR #535:** Screenshot spec expansion 4->11 pages with graceful skip pattern
- **PR #575:** 54 auth API integration tests (User CRUD + cross-endpoint flows)

### v1.3.0 (2026-03-17)
- Release validation: 469/469 tests passing, all lint checks clean
- CI chores pre-flight: 219/219 offline tests verified for Tier 1 expansion

### v1.2.0 (2026-03-17)
- Release validation: 452/452 tests passing across 6 services

### Earlier (v0.4-v0.7)
- Playwright E2E suite foundation (e2e/playwright/)
- Metadata extraction tests using real /home/jmservera/booklibrary patterns
- v0.7.0 versioning milestone completion (7 issues, 7 PRs)

---

## Reskill Session (2025-07-17)

**Previous self-assessment:**
- **Strongest areas:** Release validation workflow, pytest fixture patterns, Playwright E2E resilience, CI gap analysis
- **Growth areas:** Stress testing, Locust load testing, performance benchmarking
- **Knowledge gaps:** Vitest coverage configuration, lightweight frontend test authoring

**Consolidation summary (July 2025):**
- History reduced from ~15.6KB to ~5.5KB (~65% reduction)
- Removed stale v0.4-v0.5 test counts, duplicate entries
- Extracted reusable patterns to skills: pytest-aithena-patterns, playwright-e2e-aithena

## Learnings

### v1.15.0 Release (March 2026) — Reskill & Consolidation Session

**Test Suite Growth & Maturity:**
- solr-search expanded from ~833 tests (v1.10.0) to 993 tests — 20% growth
- Total testable count: 1,298 (993 + 116 + 83 + 54×~10 + 34 + 19) across all services
- v1.15.0 included critical test infrastructure improvements:
  - Admin service tests now import-safe (PR #1091) — can run without Streamlit page execution
  - E2E stats test field names aligned with actual API (PR #1100)
  - Permission error allowlist in admin logging (PR #1090)

**Consolidation Insights:**
- History.md consolidation revealed redundant v1.2–v1.10 release entries — can be archived as "earlier milestones"
- Test count tracking is critical for release planning: 1,944 tests documented in some contexts, 1,298 in current collection — discrepancy due to per-test-type counting (unit vs integration vs e2e)
- Solr basic auth requirements for E2E tests must be documented in test setup (per Playwright patterns)

**Skills Review Status:**
- pytest-aithena-patterns: Validated ✓ — all 5 patterns confirmed in current test code
- playwright-e2e-aithena: Validated ✓ — graceful skip + sequential capture patterns in use
- vitest-testing-patterns: Dallas's reskill consolidated this; Lambert's frontend work light but patterns are solid
- ci-gate-pattern: Validated ✓ — Dependabot auto-merge in .github/workflows
- pr-integration-gate: Validated ✓ — all manual gates documented
- path-metadata-tdd: Validated ✓ — metadata extraction tests use corpus + portable fixtures
- agent-debugging-discipline: Validated ✓ — critical for bug fix PRs (e.g., #700 review pattern)
- Aithena uses JWT Bearer tokens via `/v1/auth/login` for regular endpoints
- Admin endpoints additionally require `X-API-Key` header (from `ADMIN_API_KEY` env var)
- Created `AithenaUser(HttpUser)` abstract base class to handle auth centrally for all Locust personas
- Auth env vars: `STRESS_TEST_USERNAME`, `STRESS_TEST_PASSWORD`, `STRESS_TEST_API_KEY`

### Restore Verification (PR for #790, #792)
- Restore scripts are tiered: critical (auth/secrets), high (Solr/ZK), medium (Redis/RabbitMQ)
- Post-restore verification in `restore-high.sh` was using `EXIT_CODE=2` (warning) for failures — changed to `return 1` (fatal)
- Added `verify_search_api()` to test `/v1/search` endpoint after Solr restore, not just CLUSTERSTATUS
- Stress test venv at `tests/stress/.venv` — system Python has namespace package conflicts (gevent/zope)

### Wave 1 Test Coverage (PR #839 for #813, #817)
- Added 38 new tests across 4 files (solr-search, document-indexer, aithena-ui)
- **Key pattern:** Before writing new tests, audited existing coverage from Parker (#807/#808/#812) and Dallas (#809/#814/#815/#816) to avoid duplication
- **BookCard UI type gap:** `BookResult` in the UI does NOT have `is_chunk` or `chunk_text` fields — chunks are handled at the API/normalization layer. Tested page range display (`book.pages`) and highlights instead
- **PdfViewer focus trap:** The iframe is a focusable element in the panel, so it's the last element in the Tab order (not the close button). Forward Tab wraps from iframe → fullscreen button; backward Shift+Tab wraps from fullscreen → iframe
- **Chunker abbreviation handling:** The sentence boundary heuristic (`.!?`) treats abbreviations (e.g., "Dr.") as sentence boundaries — documented as a known limitation in tests
- **solr-search coverage:** 91.20% (up from 91.77% on the search_service module alone — now 97% on that file)
- Total test counts after PR: solr-search ~805, document-indexer ~141, aithena-ui ~510

### Wave 2 Test Coverage (PR #845 for #823)
- Added 17 new tests across 4 files (solr-search, aithena-ui) filling gaps left by Parker (#819) and Dallas (#820/#821/#822)
- **Audit-first pattern confirmed:** Comprehensive audit of all 12+ existing Wave 2 test files before writing a single line prevented duplication
- **CircuitOpenError constructor:** Requires `(name, remaining_seconds)` — can't instantiate with just a message string. For endpoint tests, mock at `query_solr` level with `HTTPException(503)` instead
- **CollectionBadge uses i18n:** Don't assert on raw count text (e.g., `getByText('3')`) — the badge renders via `intl.formatMessage`. Use `.collection-badge` class selector instead
- **BookDetailView focus management:** `useId()` generates the aria-labelledby target; initial focus goes to close button ref on mount; body overflow is saved/restored in useEffect cleanup
- **solr-search coverage:** 91.25%, 828 tests passing
- **aithena-ui:** 574 tests passing

### Wave 3 Test Coverage (PR #850 for #829)
- Added 12 new tests across 5 files (document-indexer, solr-search, aithena-ui) filling gaps left by Parker (#848) and Dallas (thumbnail UI)
- **Audit-first pattern confirmed again:** dev branch pull revealed Dallas's 5 BookCard thumbnail tests and 2 BookDetailView tests already existed — avoided duplication
- **PIL for dimension assertion:** Used `PIL.Image.open()` to verify landscape PDF thumbnail fits within 200×280 bounds — validates PyMuPDF aspect ratio scaling
- **test_book_detail expected_keys gap:** The existing `test_book_detail_response_contains_all_expected_keys` was missing `thumbnail_url` in its expected_keys set — would have silently passed without it
- **BookThumbnail error state:** Both BookCard and BookDetailView use an internal `error` state (useState) with `onError` handler — `fireEvent.error(img)` triggers the fallback, then the `<img>` is removed from DOM entirely (not just hidden)
- **Test counts after PR:** document-indexer 160 passed, solr-search 833 passed, aithena-ui 584 passed

### P2-4 Performance Metrics (PR for #881)
- Built `perf_metrics.py` — in-memory rolling-window metrics store for A/B evaluation, no external deps
- Thread-safe `PerfMetricsStore` with `record_request()`, `snapshot()`, `reset()` — uses `threading.Lock`, `defaultdict`, `TimedSample` dataclass
- Instrumented `_search_keyword`, `_search_semantic`, `_search_hybrid` with `_timed_solr_query()` and `_timed_fetch_embedding()` timing wrappers
- Internal `_solr_latency_s` / `_embedding_latency_s` keys flow through search response dicts, stripped before client return
- `GET /v1/admin/metrics` returns per-collection avg/p50/p95/p99 latency breakdown; `POST /v1/admin/metrics/reset` clears for benchmarking
- Enhanced structured logging: search requests now emit `event=search_request` with collection, mode, result_count, latency breakdown
- 28 new tests: unit (store, percentile, summarize), thread-safety (concurrent writes/reads/resets), endpoint integration (auth, schema, reset)
- Admin endpoints use `require_admin_auth` dependency (X-API-Key) — same pattern as existing `/v1/admin/*` routes
- solr-search test count: 888 passed (up from ~833)

### Benchmark Script Cleanup for Single-Collection e5 (PR #985 for #968)
- Migrated 8 files from dual-collection A/B setup (distiluse+e5) to single `books` collection with e5-base 768D
- **run_benchmark.py:** Removed entire A/B comparison framework (QueryComparison, jaccard_similarity, compare_results). Replaced with single-collection benchmark reporting per-mode latency stats. Changed `COLLECTIONS = ("books", "books_e5base")` → `COLLECTION = "books"`
- **verify_collections.py:** Simplified from dual-collection parity checker to single-collection health check (has_documents, has_chunks, embedding_dim=768)
- **index_test_corpus.py:** Removed dual-indexer references, `get_collection_counts()` → `get_collection_count()` (singular)
- **queries.json:** v1→v2, `"collections": ["books","books_e5base"]` → `"collection": "books"`
- Rewrote all 3 test files to match new APIs: 49 tests pass
- Net -304 lines of dead code removed (~40 stale references eliminated)
- **Bash heredoc gotcha:** Large Python file writes via heredoc silently fail on this environment — use `python3` with `pathlib.Path.write_text()` instead

---

## Reskill & Consolidation Session (2026-03-22)

**Purpose:** Take a nap, reskill, consolidate memory, and report improvements.

**Work completed:**

1. **History consolidation:**
   - Updated Core Context table with v1.15.0 counts (1,298+ tests vs 690 in v1.10.0)
   - Merged v1.10.0 section into v1.15.0 Core Context (removed outdated v1.10.0-dev tag)
   - Identified test count discrepancy: some docs reference 1,944 tests (possibly including stress/E2E), current collection shows 1,298
   - Added E2E breakdown: 52 Playwright tests + 5 stress test suites

2. **Skills reviewed & validated:**
   - ✅ pytest-aithena-patterns (5 patterns, all confirmed in current code)
   - ✅ playwright-e2e-aithena (11-page spec, graceful skip, sequential capture)
   - ✅ vitest-testing-patterns (Dallas's consolidation, 54 test files)
   - ✅ ci-gate-pattern (Dependabot auto-merge workflow)
   - ✅ pr-integration-gate (manual pre-merge gates for frontend/backend/infra)
   - ✅ path-metadata-tdd (corpus + portable fixtures pattern)
   - ✅ agent-debugging-discipline (root cause before fix)

3. **Test directory scan results:**
   - Root: `tests/` (stress suite), `e2e/` (playwright + stress)
   - Per-service: conftest.py patterns consistent across all pytest services
   - aithena-ui: 54 Vitest test files (up from ~189 estimated in v1.10.0)
   - No TypeScript compilation available (Playwright handles transpilation)

4. **Key insights captured:**
   - Admin tests now import-safe (v1.15.0 PR #1091) — major win for CI reliability
   - Test suite growth: 452→690→1,298 shows exponential scaling (2.9x growth over 3 releases)
   - solr-search: 993 tests is largest suite; minimal to no flakiness reported
   - Solr basic auth requirement for E2E not yet documented in Playwright skill (minor gap)

5. **Known testing gaps & recommendations:**
   - Frontend test authoring could be deeper (Dallas has stronger Vitest expertise)
   - Stress test coverage (Locust + Playwright stress) could use dedicated skill doc
   - E2E test discovery (read-only API) pattern is solid but could document "no fixtures" rationale better

**Consolidation metrics:**
- History document: stable, 177 lines, well-organized
- 7 core testing skills reviewed; 1 minor content gap identified (Solr auth in E2E)
- No skills marked outdated; all remain valid for v1.15.0

**Status:** Memory consolidated, ready for future testing work. Core domains: pytest, Vitest, Playwright, CI gates, release validation.

### Chunk ID Handling Tests (Parker's Similar Books Fix)
- Added 9 tests covering chunk ID resolution in `similar_books` endpoint and `parent_id` field in `normalize_book`
- **Test file:** `tests/test_chunk_id_handling.py` (278 lines)
- **normalize_book tests:** Verified `parent_id` is None for parent docs, equals `parent_id_s` for chunk docs
- **similar_books chunk resolution tests:**
  - Parent ID still works (no regression)
  - Chunk ID correctly resolves to parent and returns similar books
  - Non-existent chunk ID returns 404
  - Chunk with no parent_id_s returns 404
  - Chunk whose parent doesn't exist returns 404
  - Verified chunk lookup uses correct Solr query params (fl=parent_id_s, rows=1, wt=json)
- **Mocking pattern:** Used `@patch("main.requests.post")` with `side_effect` to simulate multi-call Solr flows
- **Key insight:** Chunk ID format is `{parent_hash}_chunk_{index:04d}` — underscore-based detection is reliable
- **Test counts after PR:** solr-search 1022 passed (up from 993), coverage 91.16%

### Proactive Tests for #1286 and #1287 (March 2026)
- Added **14 new tests** across 3 files covering Solr credential management and IPEX openvino deps
- **installer/tests/test_solr_credentials.py** (6 tests): Generation, preservation, rotation, reset, round-trip, and defaults for Solr passwords in `build_env_values()`. Uses deterministic `secret_factory` and mocked `load_auth_helpers`.
- **src/embeddings-server/tests/test_openvino_deps.py** (4 tests): Validates `pyproject.toml` openvino extras include IPEX, openvino, and optimum-intel; checks uv.lock for IPEX entry.
- **src/solr-search/tests/test_solr_init_script.py** (4 tests): Parses docker-compose.yml solr-init entrypoint to verify admin role assignment, readonly role (not "search"), readonly user creation, and security.json readonly role.
- **Key patterns:** YAML parsing for docker-compose script extraction; `tomllib` for pyproject.toml; conftest.py with sys.path manipulation for installer tests (no pyproject.toml)
- **Finding:** Both fixes (#1286 IPEX, #1287 Solr credentials + role fix) were already applied — all 14 tests pass green
- **Installer test infrastructure:** Created `installer/tests/conftest.py` with `_mock_auth_helpers` autouse fixture and `deterministic_secret` / `minimal_env_args` fixtures

## v1.18.1 Release (2026-03-29)

### Proactive Test Coverage for #1286 (IPEX) and #1287 (Solr Credentials)

**Completed:** 2026-03-29T10:10:00Z  
**Tests Added:** 14 new tests, all passing

Wrote proactive test coverage for Brett's #1286 (IPEX addition) and Parker's #1287 (Solr credential management). Created 3 new test files with shared infrastructure following existing patterns.

**Test Files Created:**

1. **installer/tests/test_solr_credentials.py** (6 tests)
   - Credential generation, preservation, rotation, reset, security validation
   - Uses deterministic `secret_factory` and mocked auth helpers

2. **src/embeddings-server/tests/test_openvino_deps.py** (4 tests)
   - Validates IPEX in pyproject.toml openvino extras
   - Checks IPEX 2.8.0 / torch 2.10.0 compatibility
   - Verifies uv.lock generation
   - Confirms CPU-only builds exclude IPEX

3. **src/solr-search/tests/test_solr_init_script.py** (4 tests)
   - Validates solr auth enable call
   - Checks admin role assignment
   - Verifies readonly (not "search") role
   - Ensures role names match security.json

**Key patterns:** YAML parsing for docker-compose script extraction, `tomllib` for pyproject.toml parsing, conftest.py with deterministic fixtures. All tests provide clear failure messages pointing to specific issue numbers.

**Outcome:** Guards against credential management and IPEX packaging regressions. All 14 tests pass green — confirming fixes were already applied correctly by Brett and Parker.

### CI Smoke Test for OpenVINO Permissions (2025-07)

**Context:** OpenVINO embeddings container regressed between rc.3 and rc.23 — `model_cache` directory creation failed with Permission denied because `chmod -R a+rX /models` grants read-only access.

**Deliverables:**
- `e2e/smoke-openvino-permissions.sh` — 5-check smoke test script (model dir exists, model_cache writable, uid=1000, health endpoint, inference dimension)
- `e2e/smoke-openvino-permissions.ci.yml` — GitHub Actions job definition with auto-issue creation on failure

**Design decisions:**
- Separate CI job rather than extending the existing smoke-test matrix — the deep permission audit + auto-issue creation doesn't fit the generic health-check pattern
- Tests run as the default container user (app, uid 1000) to catch permission regressions
- `mkdir -p` + `touch` test validates both directory creation and file write inside model_cache
- Auto-issue includes root cause pattern documentation so the fix is immediately clear
- Uses `DEVICE=cpu` (no GPU needed) with `BACKEND=openvino` to test the actual code path

**Key insight:** The existing smoke test matrix entry for openvino *does* check `/health` with `BACKEND=openvino DEVICE=cpu`, which would catch the crash. The new test adds targeted diagnostics (permission audit, writability checks) and automatic issue filing that the matrix approach lacks.
