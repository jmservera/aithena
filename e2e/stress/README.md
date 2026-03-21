# Playwright UI Stress Tests

Stress tests that validate Aithena's frontend behaviour under load: simultaneous
uploads, rapid search, admin workflows under pressure, deep pagination, and
concurrent browser sessions.

## Prerequisites

- Node.js 18+
- The main E2E setup must have run first (`cd ../playwright && npm install`)
- A running Aithena stack (or access to `BASE_URL`)

## Setup

```bash
# Install the parent Playwright package first
cd e2e/playwright && npm install && npx playwright install chromium

# Create the symlink (scripts do this automatically via npm install)
cd ../stress
npm install
```

## Running Tests

```bash
# Run all stress tests
npm test

# List available tests (syntax validation)
npm run test:list

# Run a specific suite
npm run test:upload
npm run test:search
npm run test:admin
npm run test:pagination
npm run test:concurrent

# Custom base URL
BASE_URL=http://localhost:5173 npm test
```

## Configuration

All stress parameters are tuneable via environment variables. Defaults are
designed for local development — increase values for CI or production-like runs.

| Variable | Default | Description |
|----------|---------|-------------|
| `STRESS_UPLOAD_FILES` | 10 | Number of simultaneous file uploads |
| `STRESS_UPLOAD_TIMEOUT_MS` | 30000 | Timeout for upload feedback |
| `STRESS_SEARCH_QUERIES` | 20 | Number of rapid-fire search queries |
| `STRESS_SEARCH_DELAY_MS` | 200 | Delay between rapid queries (ms) |
| `STRESS_SEARCH_MAX_RESPONSE_MS` | 15000 | Max acceptable response time per query |
| `STRESS_ADMIN_REPETITIONS` | 10 | Repeat count for admin actions |
| `STRESS_ADMIN_DELAY_MS` | 500 | Delay between admin actions (ms) |
| `STRESS_PAGINATION_MAX_PAGES` | 50 | Maximum pages to traverse |
| `STRESS_PAGINATION_PAGE_TIMEOUT_MS` | 20000 | Timeout per page load |
| `STRESS_CONCURRENT_CONTEXTS` | 5 | Number of parallel browser sessions |
| `STRESS_CONCURRENT_ACTIONS` | 10 | Actions per session in long-run test |

## Test Suites

| File | Scenario |
|------|----------|
| `upload-stress.spec.ts` | Upload N files simultaneously; verify queue appearance |
| `search-stress.spec.ts` | Rapid searches, facet clicking, search during indexing |
| `admin-stress.spec.ts` | Status monitoring, requeue, clear — under rapid repetition |
| `pagination-stress.spec.ts` | Deep pagination through 1,000+ results |
| `concurrent-sessions.spec.ts` | Multiple browser contexts, mixed workloads, memory leak detection |

## Data Gating

Tests skip gracefully when required data or features are unavailable,
following the same `discoverCatalogScenario()` pattern as the main E2E tests.
No test will fail solely because the index is empty.

## Architecture

The stress test suite shares the Playwright installation and helpers from
`e2e/playwright/` (global-setup, auth, helpers). A `node_modules` symlink
points to the parent playwright `node_modules/` to avoid duplicate
`@playwright/test` installations. The `stress.config.ts` file provides a
single place to tune all stress parameters via environment variables.
