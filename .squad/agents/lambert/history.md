# Lambert — History

## Core Context — Latest Verified Test Counts (v1.10.0-dev)

**690 Tests Passing** as of v1.10.0 development (2026-03-20):

| Service | Tests | Coverage | Notes |
|---------|-------|----------|-------|
| **solr-search** | ~219 | 94.83% | Core search, auth, facets, PDF, folder facets, chunk embedding |
| **aithena-ui** | ~189 | — | Vitest + React Testing Library |
| **document-indexer** | 91 + 4 skipped | ~81% | 4 tests skip if env vars misconfigured |
| **admin** | 81 | — | 19 InsecureKeyLengthWarning (test-only HMAC keys, not prod) |
| **document-lister** | 12 | — | File watcher + RabbitMQ publisher |
| **embeddings-server** | 9 | — | Requires manual pip install pytest httpx |

**Growth:** 452 (v1.2.0) -> 469 (v1.3.0) -> 690 (v1.10.0-dev)

**Coverage thresholds:** solr-search >=90%, document-indexer >=80%

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

## Reskill Notes (2025-07-17)

**Self-assessment:**
- **Strongest areas:** Release validation workflow, pytest fixture patterns, Playwright E2E resilience, CI gap analysis
- **Growth areas:** Stress testing (assigned #675 — first time), Locust load testing patterns, performance benchmarking
- **Knowledge gaps:** No hands-on experience with Vitest coverage configuration; frontend test authoring has been light compared to backend
- **Stale knowledge removed:** v0.4-v0.5 test counts (superseded), duplicate screenshot entries, redundant release validation details

**Patterns extracted to skills:**
- pytest-aithena-patterns — Fixture strategies, mock patterns, service-specific quirks
- playwright-e2e-aithena — Graceful skip, sequential capture, data-dependent discovery

**Consolidation metrics:**
- History reduced from ~15.6KB to ~5.5KB (~65% reduction)
- 2 duplicate entries removed (screenshot spec)
- 2 redundant release validations collapsed into deliverables table
- Outdated v0.4-v0.5 test counts removed (superseded by latest)
