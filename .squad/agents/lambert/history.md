# Lambert — History

## Core Context

**Latest stable counts (v1.15.0, 2026-03):** 1,298+ collectable tests: solr-search 993 pytest; aithena-ui ~540+ Vitest / 54 files; document-indexer 83 pytest; document-lister 19 pytest; admin 116 pytest; embeddings-server 34 pytest; Playwright E2E 52 tests; E2E stress 5 suites. Growth: 452 (v1.2.0) → 690 (v1.10.0) → 1,298+ (v1.15.0). Some docs cite 1,944 because unit/integration/E2E/stress are counted differently. solr-search later reached 1,022 tests; coverage stayed ~91%.

**Stable quality context:** solr-search coverage ~91%+, document-indexer target >=80%, main has little/no reported flakiness. Admin tests are import-safe after PR #1091. Validated skill sets: pytest, Playwright E2E, Vitest, CI gates, PR integration gates, path metadata TDD, debugging discipline.

## Key Patterns

- **Audit first:** inspect existing coverage before new tests, especially during Parker/Dallas/Lambert waves, to avoid duplicate assertions.
- **Release validation:** record collectable count plus per-suite counts; keep unit/integration/E2E/stress distinct.
- **Verify after manifests:** after dependency lock/manifest conflicts, run `.squad/scripts/verify.sh`; `git checkout --theirs` can silently drop earlier bumps.
- **Cross-endpoint tests:** register→login, delete→login-fails, update→list-reflects catch more regressions than isolated mocks.
- **Pytest fixtures:** patch frozen settings with `object.__setattr__`; clear `login_rate_limiter.requests` around auth tests; guard real-corpus fixtures with `skipif`.
- **Env reload tests:** restore `os.environ` before final `importlib.reload(config)` so module-level `settings` is not stale while cleanup runs.
- **Solr readiness:** poll CLUSTERSTATUS until replicas ACTIVE; restore verification should test `/v1/search`, not only cluster status.
- **Auth/RBAC:** wrong role => 403, unauthenticated => 401; usernames are case-insensitive via `COLLATE NOCASE`.
- **Rate limits:** `RateLimiter(max_requests=0)` must allow repeated uploads; check `src/solr-search/tests/test_upload.py -k rate_limit` plus solr-search verify.
- **Circuit breaker:** `CircuitOpenError` needs `(name, remaining_seconds)`; endpoint tests can mock `query_solr` with `HTTPException(503)`.
- **Playwright discovery:** prefer read-only discovery through live `/v1/search/`; gracefully skip data-dependent PDF/similar-books/stats cases with annotations.
- **Playwright sequencing:** PDF viewer must open before similar-books panel; wait helpers should inspect request params such as `fq_author`.
- **Playwright tooling:** TS is transpiled at runtime; no standalone `tsc --noEmit`. CI should reuse `E2E_API_TOKEN` before password login; local fallback remains valid.
- **Local E2E:** QA work should validate against local docker + Playwright/integration stack before pushing when feasible; report local validation in PRs.
- **Naming:** E2E names/docstrings must describe exact assertions: URL metadata vs file retrieval, semantic-or-keyword vs strict semantic, delete-then-reindex, etc.
- **UI contracts:** `BookResult` lacks `is_chunk`/`chunk_text`; test page ranges and highlights, not chunk internals.
- **UI i18n:** `CollectionBadge` renders via i18n; avoid raw count text and prefer `.collection-badge`/accessible selectors.
- **Focus/error UI:** BookDetail uses `useId`, focuses close on mount, restores body overflow; PdfViewer trap includes iframe; thumbnail `onError` removes the image.
- **Chunk IDs:** format is `{parent_hash}_chunk_{index:04d}`. Similar-books chunk lookup uses `fl=parent_id_s, rows=1, wt=json`; bad chunks/missing parents return 404.
- **Metadata tests:** include new fields like `thumbnail_url` in expected-key sets; PIL dimension checks validate 200×280 thumbnail bounds.
- **Text chunking:** `.!?` sentence heuristic splits abbreviations like “Dr.”; document as known limitation.
- **Infra quirks:** embeddings-server may need manual `pytest`/`httpx`; `UV_NATIVE_TLS=1` can fix uv SSL UnknownIssuer.
- **Stress auth:** Locust uses JWT from `/v1/auth/login`; admin also needs `X-API-Key`. Env: `STRESS_TEST_USERNAME`, `STRESS_TEST_PASSWORD`, `STRESS_TEST_API_KEY`.
- **Restore/stress:** restore tiers are critical auth/secrets, high Solr/ZK, medium Redis/RabbitMQ; high-tier failures should be fatal. Stress venv is `tests/stress/.venv`.
- **Benchmarks:** single-collection e5 uses `books` with 768D embeddings; stale dual `books`/`books_e5base` A/B code was removed.
- **File generation:** large bash heredocs may silently fail here; use `python3` + `pathlib.Path.write_text()`.
- **Config parsing tests:** use YAML parsing for docker-compose embedded scripts and `tomllib` for pyproject/lock checks; installer tests use deterministic secret fixtures.

## Learnings

### 2026-06-03 — PR #1623
- Review cleanup: config reload tests must restore env before final reload; thumbnail tests should distinguish URL/stability metadata from actual image/header retrieval.
- Single-node upload failure was Python E2E semantic upload (`test_web_api_semantic.py`), not Playwright. The missing proof was endpoint-level disabled-rate-limit behavior for repeated uploads.
- E2E naming cleanup kept assertions precise and removed duplicate corrupt-PDF/oversized-upload recovery checks because `e2e/test_upload_api.py` owns upload API validation and avoids another 52MB upload.

### 2026-05-31 — Cross-Agent CI
- CI E2E should consume `E2E_API_TOKEN` before re-auth; documented in `.squad/skills/e2e-auth-reuse/SKILL.md`.
- Juanma’s local-test-first directive applies to QA: use local docker + Playwright/integration validation before pushing when feasible.
- Dependabot batch merges touching shared manifests can revert earlier bumps; verify locally after conflict resolution.

### 2026-03-29 — #1286 / #1287 Regression Guards
- Added 14 tests for Solr credential generation/preservation/rotation/reset, OpenVINO/IPEX extras and lock entries, and solr-init admin/readonly role wiring.
- Fixes were already applied, so tests act as guards. Failure messages should reference issue numbers for known regressions.

### 2026-03 — Chunk ID Handling
- Added 9 tests for `similar_books` chunk resolution and `normalize_book.parent_id`.
- Mock multi-call Solr flows with `@patch("main.requests.post")` + `side_effect`.
- Parent IDs still work; nonexistent chunks, missing `parent_id_s`, and missing parents return 404.

### 2026-03 — Benchmark Cleanup
- Migrated from dual-collection A/B to single `books` e5 benchmark; replaced comparison metrics with per-mode latency stats.
- Simplified health checks to documents, chunks, and 768D embedding dimension; rewrote tests and removed ~300 stale lines.

### 2026-03 — P2-4 Performance Metrics
- `perf_metrics.py` is an in-memory rolling-window store using `threading.Lock`, `defaultdict`, and `TimedSample`.
- `_timed_solr_query()` and `_timed_fetch_embedding()` attach internal latency keys that are stripped before client response.
- Admin metrics endpoints use `require_admin_auth`; tests cover auth, schema, reset, percentiles, and thread-safety.
- Structured search logging emits collection, mode, result count, and latency breakdown.

### 2026-03 — Wave Coverage
- Wave 1: 38 tests; confirmed UI chunks are normalized before display and should be tested via page ranges/highlights.
- Wave 2: 17 tests; confirmed circuit breaker constructor shape, i18n badge selectors, and BookDetail focus behavior.
- Wave 3: 12 tests; confirmed thumbnail dimensions, missing `thumbnail_url` expected-key gap, and image-error removal behavior.

### 2026-03 — v1.15 Reskill
- Admin import-safety, E2E stats/API field alignment, and admin logging allowlists improved CI reliability.
- Lambert strengths: pytest fixtures, resilient Playwright E2E, CI/release gates, coverage audits.
- Growth areas: deeper Vitest authoring, Locust/stress benchmarking, and documenting Solr auth requirements for E2E setup.
