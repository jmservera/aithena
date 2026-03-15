# Playwright browser E2E tests

This suite exercises the React UI against a running local Aithena stack without mutating indexed data.

## What it covers

- Search flow with visible result cards, author metadata, and highlight snippets
- Author facet filtering and filter removal
- PDF viewer open flow and multi-page fragment navigation
- Tab navigation across Search, Library, Status, and Stats
- Search page empty state
- Search pagination
- File upload UI — entry point reachability, accept-attribute validation, and feedback
- Similar-books UI — trigger visibility, panel behavior, source-book exclusion, and dismiss

## Prerequisites

- The local stack is already running. These tests **do not** start Docker Compose for you.
- Preferred base URL: `http://localhost` (nginx)
- Fallback base URL: `http://localhost:5173` (Vite dev server)
- Search API reachable at `http://localhost:8080/v1/search/` when using Vite directly, or `/v1/search/` through nginx

If you want the isolated E2E stack described by the existing pytest suite:

```bash
export E2E_LIBRARY_PATH=/tmp/aithena-e2e-library
mkdir -p "$E2E_LIBRARY_PATH"
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d
```

## Install

```bash
cd e2e/playwright
npm install
npx playwright install chromium
```

## Run

```bash
cd e2e/playwright
npm run test:e2e
```

Run against the Vite dev server explicitly:

```bash
cd e2e/playwright
BASE_URL=http://localhost:5173 npm run test:e2e
```

Open the Playwright UI runner:

```bash
cd e2e/playwright
npm run test:e2e:ui
```

## Notes on repeatability

- Tests only read from the currently indexed catalog.
- Search-dependent scenarios discover a suitable query at runtime from the live `/v1/search/` API.
- If the stack has no indexed books, or no multi-page PDF is available, the data-dependent tests skip with an explicit reason instead of writing fixture data.
- `global-setup.ts` waits for either `http://localhost/search` or `http://localhost:5173/search` to return the Aithena app shell before tests begin.

## Deterministic vs data-gated tests

Tests in this suite fall into two categories:

| Category | Description | Requires |
|---|---|---|
| **Deterministic** | Always run; verify API contracts, error rejections, or UI structure that does not depend on indexed content | Running stack only |
| **Data-gated** | Skipped with an explicit reason when the required data or service is unavailable | Indexed documents, embeddings service, or specific field values |

### Deterministic tests (always run)

- Empty search state renders correctly
- Tab navigation across Search / Library / Status / Stats
- Upload accept-attribute restricts non-PDF file types
- Semantic / hybrid search rejects empty queries with HTTP 400
- Similar-books API returns 404 for an unknown document ID

### Data-gated tests (skip when data absent)

| Test | Gating condition |
|---|---|
| Search result cards show title, author, snippet | At least one indexed document |
| Author facet filtering and chip removal | Multiple documents from different authors |
| PDF viewer opens from search result | At least one result with a `document_url` |
| Search pagination | More than 10 indexed documents |
| Semantic search returns results | Embeddings service up + indexed data |
| Hybrid search returns results | Embeddings service up + indexed data |
| Similar-books trigger visible on result card | At least one indexed document |
| Similar-books panel loads related books | Embeddings service up + indexed data |
| Source book excluded from similar-books results | Embeddings service up + indexed data |
| Upload success/pending feedback | Backend upload + RabbitMQ configured |

## Files

- `playwright.config.ts` — Playwright configuration
- `global-setup.ts` — waits for the local app to be reachable
- `tests/navigation.spec.ts` — empty state and tab navigation coverage
- `tests/search.spec.ts` — search, facets, PDF viewer, and pagination coverage
- `tests/upload.spec.ts` — upload UI entry point, file-type validation, and feedback
- `tests/similar-books.spec.ts` — similar-books trigger, panel, exclusion, and dismiss
- `tests/helpers.ts` — runtime discovery helpers for indexed test data
