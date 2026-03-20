# Decision: Lambert Reskill — Testing Knowledge Consolidation

**Author:** Lambert (Tester)
**Date:** 2025-07-17
**Status:** COMPLETED

## What Changed

### History Consolidated
- Reduced `history.md` from 15.6KB to 5.0KB (68% reduction)
- Removed: duplicate screenshot spec entries, redundant v1.2.0/v1.3.0 release validation details, outdated v0.4-v0.5 test counts (superseded by v1.10.0 data)
- Added: Core Context table with latest 690-test baseline, consolidated patterns section, deliverables log, reskill self-assessment

### New Skills Extracted

1. **`pytest-aithena-patterns`** — Aithena-specific pytest patterns:
   - Frozen dataclass patching with `object.__setattr__()`
   - Rate limiter autouse cleanup fixtures
   - Environment-dependent test skipping
   - Real-library corpus fixtures with skipif guards
   - FastAPI TestClient + mocked service boundaries
   - Per-service quirks table (embeddings-server, document-indexer, admin)

2. **`playwright-e2e-aithena`** — Playwright E2E patterns for aithena:
   - Data-dependent discovery (no fixtures, live API)
   - Graceful skip with annotations for CI resilience
   - Sequential page capture for dependency chains
   - Wait helpers for async UI (facet filters)
   - 11-page screenshot spec coverage map
   - Solr cluster health wait for CI integration

### Existing Skills Reviewed (No Changes Needed)
- `path-metadata-tdd` — Still accurate and relevant
- `tdd-clean-code` — General TDD principles, no updates needed
- `smoke-testing` — Local smoke test cycle, still valid
- `ci-coverage-setup` — Coverage config patterns, comprehensive
- `project-conventions` — Test counts section updated elsewhere

## Impact

- **Lambert:** Faster context loading at spawn (~2600 fewer tokens from history alone)
- **All agents:** Two new reusable skills for pytest and Playwright patterns
- **New contributors:** Clear per-service quirks table reduces onboarding friction

## Self-Assessment

- **Knowledge improvement:** ~30% — primarily from consolidating scattered learnings into structured, reusable skills. Core knowledge was already strong but poorly organized.
- **Biggest gap identified:** Frontend test authoring (Vitest) — backend pytest is well-covered but Vitest patterns need more hands-on work
- **Next growth area:** Stress testing with Playwright and Locust (v1.10.0 #675)
