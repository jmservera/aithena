# Decision: E2E emoji and checkbox assertion patterns

**Author:** Dallas (Frontend Dev)
**Date:** 2026-07-22
**PR:** #638

## Context

Two E2E Playwright tests were failing in CI (headless Chromium):
1. Emoji characters in page titles rendered as whitespace, breaking exact `toHaveText` assertions
2. `facetCheckbox.check()` failed due to React controlled component state management

## Decision

1. **Emoji text assertions:** Use `toContainText("Library")` instead of `toHaveText("📖 Library")` for all page title assertions in E2E tests. This tolerates missing emoji rendering in headless browsers.

2. **Facet interaction pattern:** Click the `.facet-label` element (not `.facet-checkbox` with `.check()`) when toggling facet filters. This matches the proven pattern in `search.spec.ts` and avoids Playwright's native checkbox toggle expectation conflicting with React's controlled state.

## Applies to

All E2E Playwright tests in `e2e/playwright/tests/`. Future tests should follow these patterns.
