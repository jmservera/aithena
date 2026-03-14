# Dallas — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** TypeScript, React, Vite
- **Existing UI:** aithena-ui directory with React + Vite setup
- **UI package.json location:** aithena-ui/package.json

## Learnings

<!-- Append learnings below -->

### 2026-03-14T16:20 — Advanced Search Builder UI

- Added an opt-in advanced search composer to `aithena-ui` while keeping the default simple text search intact.
- Created `src/Pages/SearchPage.tsx` so the page shell can evolve independently from `App.tsx`.
- Implemented `src/Components/AdvancedSearch/` with row-based query building, year/language filters, disabled future semantic/hybrid tabs, and a live Solr preview.
- Added `buildQuery()` plus Vitest coverage for fuzzy terms, phrase queries, boolean composition, range filters, language filters, and invalid year sanitization.
- Imported Bootstrap CSS globally and layered dark-theme overrides in `App.css` so the new controls follow Bootstrap patterns without breaking the existing layout.
- `useSearch()` now tracks a `mode` field and submits it to the backend, preparing the UI for future semantic/hybrid enablement.
- Validation: `npm run test` ✅, targeted eslint on changed files ✅, `npm run build` ✅. Full `npm run lint` still fails on pre-existing chat/config files outside this feature.

### 2026-03-13T20:58 — Phase 2–4 GitHub Issues Assigned

- Ripley decomposed Phase 2–4 into issues #36–#53, all assigned to `@copilot` with squad labels and release milestones.
- **Your Phase 2 issues:** #42–#44 (Search UI component rewrite, PDF viewer, frontend tests)
- **Your Phase 3 issues:** #45–#47 (Similar books feature, semantic search integration)
- **Your Phase 4 issues:** #48–#51 (PDF upload UI, admin dashboard)
- Full dependency chain and rationale in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition".

**Your assignments (Phase 2–4):**
- **Phase 2:** Rewrite React UI from chat to search paradigm (keep Vite/TS scaffolding)
  - Replace `App.tsx` and components with search-oriented layout
  - Search bar with instant search, faceted sidebar (author, year range, language, category)
  - Result cards (title, author, year, language, snippet highlighting)
  - Pagination, click-to-view PDF
  - Add `react-router-dom` for routing
  - Remove old chat components (`ChatMessage.tsx`, `Configbar.tsx`, etc.)
- **Phase 3:** "Find Similar Books" feature (uses semantic search from backend)
- **Phase 4:** PDF upload UI (drag-and-drop) and upload endpoint integration

**UI dependencies:**
- Phase 2 blocked until Parker builds search API (2.1)
- PDF viewer component: use `react-pdf` or `pdf.js` via iframe with search term highlighting
- Search API endpoints: `GET /api/search?q=...&author=...&year_from=...`, `GET /api/facets`, `GET /api/books/{id}/pdf`

**Architecture context:**
- Paradigm shift from chat to search requires component rewrite, not refactor
- Full plan in `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

### 2026-03-14T15:50 — Fixed broken search UI after merged frontend changes

- The main runtime failure was API URL resolution: `aithena-ui/package.json` built with `VITE_API_URL="."`, which made search requests hit the wrong origin and return `404` in the browser.
- Added `aithena-ui/src/api.ts` to centralize API/document URL building, with localhost-aware fallback to `http://localhost:8080` during Vite dev and relative paths for proxied deployments.
- Updated `src/hooks/search.tsx` and `src/Components/PdfViewer.tsx` to use the shared URL helpers so both search requests and PDF iframe URLs resolve correctly.
- Added Vite dev-server proxy rules for `/v1` and `/documents`, and removed hardcoded `VITE_API_URL` values from package scripts so dev/build behave consistently.
- Cleaned leftover chat-era TypeScript issues by renaming non-JSX files from `.tsx` to `.ts` and fixing lint errors in old helper/components; `npm run build` and `npm run lint` now pass.
- Smoke tested at `http://localhost:5173`: search for `balearics` returned 22 results with facets/pagination, and the PDF viewer opened with an iframe-backed dialog.

