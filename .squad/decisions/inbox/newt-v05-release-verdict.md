# v0.5.0 Release Verdict

**Decision:** ✅ APPROVE  
**Author:** Newt (Product Manager)  
**Date:** 2026-03-15  
**Scope:** Release gate — v0.5.0 merge to main and tag

---

## Pre-checks

| Check | Result |
|-------|--------|
| Milestone v0.5.0 | **0 open / 9 closed** ✅ |
| Open issues with `release:v0.5.0` label | **None** ✅ |
| Local branch synced with origin/dev | **Yes** (pulled PRs #176, #177) ✅ |

## Build Validation

| Component | Command | Result |
|-----------|---------|--------|
| Frontend build | `npm run build` | ✅ 44 modules, 3 assets |
| Frontend tests | `npx vitest run` | ✅ **24/24 passed** (4 test files) |
| Backend tests | `uv run pytest` (solr-search) | ✅ **78/78 passed** |
| Indexer tests | `uv run pytest` (document-indexer) | ✅ **95/95 passed** |
| **Total** | | **197 tests, 0 failures** |

## Code Review — What Ships

### Features (Phase 3 — Embeddings)

1. **#163 — Search mode selector** ✅  
   Three modes (keyword/semantic/hybrid) with `aria-pressed` buttons, mode passed as query param, backend handles all three including RRF fusion for hybrid. Frontend shows "Embeddings unavailable" fallback.

2. **#47 — Similar Books panel** ✅  
   `useSimilarBooks` hook with AbortController, module-level cache, skeleton loading UI with `aria-live`. 4 dedicated tests covering loading, empty, click, and error states.

3. **#168 — Admin tab** ✅  
   Streamlit iframe at relative path `/admin/streamlit/` with nginx proxy. Sandbox attribute applied.

### Bug Fixes

4. **#166 — RabbitMQ startup** ✅  
   Image pinned to `rabbitmq:3.13-management`. Healthcheck: `rabbitmqctl ping`, interval 10s, timeout 30s, retries 12, `start_period: 30s`. Confirmed in docker-compose.yml after PR #176.

5. **#167 — Pipeline dependency** ✅  
   `document-lister`, `document-indexer`, and `streamlit-admin` all use `condition: service_healthy` for rabbitmq. Confirmed after PR #177.

6. **#171 — Document-lister state tracking** ✅  
   Test added for non-existent base path graceful handling.

7. **#172 — Language detection** ✅  
   langid field alignment + folder-path language extraction in indexer.

### Tooling

8. **#41 — Frontend test coverage** ✅  
   Vitest setup with 4 test files, 24 tests covering FacetPanel, PdfViewer, SearchPage, SimilarBooks.

## Follow-up Recommendations (Non-blocking)

These are not release blockers but should be considered for v0.5.1 or v0.6.0:

- **Admin iframe sandbox**: Consider removing `allow-popups` from sandbox attribute in `AdminPage.tsx` to tighten security.
- **Similar books cache**: `useSimilarBooks` module-level cache is unbounded. Consider LRU eviction for long-lived sessions.
- **Semantic mode facets**: Semantic search returns empty facet arrays. A UI hint ("Facets unavailable in semantic mode") would improve UX.
- **Invalid search mode**: No backend test for `?mode=invalid` query parameter. Minor edge case.

## Recommendation

**Ship it.** All 9 milestone issues are resolved and verified. 197 tests pass across 3 components. Infrastructure fixes (#166, #167) are confirmed in the codebase. The codebase is ready for merge to `main` and tagging as `v0.5.0`.

Ripley (Lead) or Juanma (Product Owner) may proceed with the merge.
