# Ripley — v0.5 PR Review Batch 1

**Date:** 2026-03-14
**Reviewer:** Ripley (Lead)

## PR #164 — feat(ui): add search mode selector (keyword/semantic/hybrid)

**Verdict: ✅ APPROVED**
**Branch:** `copilot/add-search-mode-selector` → `dev`
**Issue:** #163
**CI:** 4/4 checks pass

Summary: Adds `SearchMode` type, `mode` to SearchState (default: keyword), passes `?mode=` to API. Toggle button group below search bar with ARIA attributes. Mode badge in results area. Graceful error handling for empty queries in semantic/hybrid mode and HTTP 400 when embeddings unavailable. CSS follows existing App.css patterns. No regressions.

## PR #165 — feat(aithena-ui): add Vitest test coverage

**Verdict: ✅ APPROVED**
**Branch:** `copilot/add-frontend-test-coverage` → `dev`
**Issue:** #41
**CI:** 9/10 pass — 1 failure is pre-existing Python lint (SIM117 in solr-search/tests/test_integration.py:1115), NOT introduced by this PR

Summary: Sets up Vitest + React Testing Library + jsdom. 19 behavioral tests across 3 components:
- SearchPage (5 tests): query→results, empty state, API error
- FacetPanel (6 tests): rendering, checkbox interaction, filter state
- PdfViewer (8 tests): dialog open/close, Escape key, iframe src, page anchor, error state

All tests use proper mocking — no live backend. Tests are behavioral, not snapshots.

**Follow-up needed:** CI does not yet run `npm run test`. Suggest adding a frontend test job to the CI workflow.

## PR #170 — feat(ui): Add Admin tab embedding Streamlit dashboard

**Verdict: ✅ APPROVED**
**Branch:** `copilot/add-admin-tab-embed-streamlit` → `dev`
**Issue:** #168
**CI:** 4/4 checks pass

Summary: New AdminPage with iframe to `/admin/streamlit/` (relative path). Restrictive sandbox attribute. Route `/admin` + tab in TabNav. Flex layout, full height, no scrollbars. Graceful degradation if Streamlit unavailable. Clean stop-gap before v0.6 native migration.

## Action Items

1. **Pre-existing ruff failure:** `solr-search/tests/test_integration.py:1115` — SIM117 violation. Should be fixed independently (not a blocker for any of these PRs).
2. **CI gap:** Frontend tests (`npm run test`) not in CI pipeline. Should be added to prevent regressions.
3. **Merge order:** #165 (tests) first, then #164 (mode selector), then #170 (admin tab). No hard dependencies between them, but tests landing first gives a baseline.
