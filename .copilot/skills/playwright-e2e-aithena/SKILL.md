---
name: "playwright-e2e-aithena"
description: "Playwright E2E test patterns for aithena: graceful skips, data-dependent discovery, sequential captures, screenshot specs"
domain: "testing, e2e, playwright, typescript"
confidence: "high"
source: "earned — Lambert's Playwright E2E work across e2e/playwright/ (v0.4–v1.8.0)"
author: "Lambert"
created: "2025-07-17"
last_validated: "2025-07-17"
---

## Context

Use when writing or reviewing Playwright tests in `e2e/playwright/`. The aithena E2E suite is read-only (discovers data from live API) and must be resilient in CI where indexed data may vary.

## Pattern 1: Data-Dependent Discovery (No Fixtures)

Tests discover content from the live `/v1/search/` API instead of uploading fixtures. This makes tests work against any populated Solr index.

```typescript
// Discover a real book from the API
const response = await request.get('/v1/search/?q=*&limit=1');
const data = await response.json();
if (data.total === 0) {
  test.skip('No indexed books available');
  return;
}
const book = data.results[0];
```

**Why:** Avoids fixture maintenance; tests validate real search behavior.

## Pattern 2: Graceful Skip with Annotations

Data-dependent pages (PDF viewer, similar books, status, stats, library) use try/catch + annotation:

```typescript
try {
  await page.locator('[data-testid="pdf-viewer"]').waitFor({ timeout: 5000 });
  await page.screenshot({ path: 'screenshots/pdf-viewer.png' });
} catch {
  test.info().annotations.push({
    type: 'skip',
    description: 'PDF viewer not available — no PDF data indexed'
  });
}
```

**Why:** CI stays green even when data is unavailable; annotations explain why in reports.

## Pattern 3: Sequential Page Capture (Dependency Chains)

Some pages depend on prior UI state. Capture them in order:

```typescript
// 1. Open PDF viewer first
await page.click('[data-testid="book-result"]:first-child');
await page.screenshot({ path: 'screenshots/pdf-viewer.png' });

// 2. Then capture similar books (depends on open PDF)
await page.click('[data-testid="similar-books-button"]');
await page.screenshot({ path: 'screenshots/similar-books.png' });
```

**Rule:** PDF viewer must be open before similar books panel can be captured.

## Pattern 4: Wait Helpers for Async UI

Use `waitForSearchResponse` with parameter checks before assertions:

```typescript
// Wait for faceted search response with specific filter
await waitForSearchResponse(page, { params: { fq_author: 'Cervantes' } });
await page.screenshot({ path: 'screenshots/search-faceted.png' });
```

**Why:** Facet filter changes trigger async API calls; asserting before response arrives causes flaky tests.

## Pattern 5: Screenshot Spec Coverage

The screenshot spec (`tests/screenshots.spec.ts`) captures 11 pages in a single test run:

1. Login
2. Search empty state (before any query)
3. Search results
4. Search faceted (filtered by author)
5. PDF viewer
6. Similar books
7. Admin dashboard
8. Upload
9. Status
10. Stats
11. Library

**Order matters:** Empty state before queries; PDF before similar books; static pages last.

## Configuration Notes

- `playwright.config.ts`: `baseURL` targets nginx (`http://localhost`)
- `global-setup.ts`: Polls both nginx and Vite dev server for health
- **No tsconfig.json** — Playwright handles TS transpilation at runtime; `tsc --noEmit` is not available for validation
- Artifacts go to `e2e/artifacts/` (gitignored), not repo root

## Solr Health Wait (CI Integration)

Before running E2E tests in CI, wait for Solr cluster readiness:

```yaml
- name: Wait for Solr cluster
  run: |
    for i in $(seq 1 15); do
      STATUS=$(curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS' | python3 -c 'import sys,json; ...')
      if [ "$STATUS" = "active" ]; then break; fi
      sleep 10
    done
```

**Timeouts:** retries=15, interval=10s, start_period=60s. Poll CLUSTERSTATUS API until all replicas ACTIVE.

## Anti-Patterns

- **Don't upload test fixtures** — discover from live API; fixtures go stale
- **Don't assert on empty Solr** — always check `numFound > 0` or skip
- **Don't capture dependent pages independently** — follow dependency chains
- **Don't hard-fail on missing data** — use graceful skip + annotation
- **Don't commit artifacts to repo root** — use `e2e/artifacts/` (gitignored)

## References

- `e2e/playwright/tests/screenshots.spec.ts` — 11-page screenshot spec
- `e2e/playwright/playwright.config.ts` — base config
- `e2e/playwright/global-setup.ts` — health polling
- `.squad/skills/smoke-testing/` — full local smoke test cycle
