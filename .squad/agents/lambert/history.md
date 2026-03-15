## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

---

# Lambert — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (pytest), TypeScript (Vitest), Docker Compose, Playwright for E2E
- **Key test concerns:** PDF processing edge cases, multilingual search quality, metadata extraction, file watcher reliability

## Core Context

**Test Infrastructure (v0.4-v0.5):**
- **E2E Playwright suite** (`e2e/playwright/`): Read-only browser tests discovering live `/v1/search/` API results; works against nginx or Vite dev server
- **Metadata extraction tests** (pytest): 11 passing + 4 intentional failures; real patterns from `/home/jmservera/booklibrary` (amades author folder, BALEARICS category, bsal year-range edge case)
- **Backend test suites:** 28 tests (solr-search), 15 (document-indexer), 5 (document-lister) using pytest + mocking

**Real Library Patterns Discovered:**
- `amades/` → author folder; strip author suffixes from titles when duplicated
- `balearics/ESTUDIS_BALEARICS_*.pdf` → category/series folder; preserve uppercase underscore stems
- `bsal/Bolletí...1885 - 1886.pdf` → critical edge case; year ranges must stay in title, not misread as author-title split

**Test Data Source:**
- `/home/jmservera/booklibrary` (actual user library with old texts, OCR issues)
- Test discovery: skip gracefully when no indexed books, no meaningful facets, or no multi-page PDF

## Learnings

<!-- Append learnings below -->

### 2026-03-14 — Playwright browser E2E suite for the local stack

- Browser suite (`e2e/playwright/`) is read-only: discovers queries from live `/v1/search/` API instead of uploading fixtures
- `playwright.config.ts`: `baseURL` aligns with nginx (`http://localhost`); `global-setup.ts` polls both nginx and Vite dev server
- Search, facet, pagination, PDF tests are data-aware: skip gracefully when no indexed books, no meaningful facets, or no multi-page PDF
- PDF viewer is iframe wrapper; page navigation via fragment `#page=2` after modal open

**v0.5 Test Queue:**
- #41 (frontend tests): Vitest setup + search/facets/PDF component coverage (🟢 good fit)
- #47 (similar-books UI): React component for `/books/{id}/similar` endpoint (🟡 needs review)
- #165 (merged): Frontend test coverage for search/facets/PDF

**Known test blockers:**
- #166: RabbitMQ cold-start prevents document indexing in CI
- #167: Document pipeline stalled; affects E2E test data population
