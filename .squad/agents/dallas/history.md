# Dallas — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** TypeScript, React, Vite
- **Existing UI:** aithena-ui directory with React + Vite setup
- **UI package.json location:** aithena-ui/package.json

## Learnings

<!-- Append learnings below -->

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

### 2026-03-14T18:55 — LINT-6 prettier + eslint autofix on aithena-ui

- Added `aithena-ui/.prettierrc` plus Prettier integration in `.eslintrc.cjs`, and installed `prettier`, `eslint-config-prettier`, and `eslint-plugin-prettier` as dev dependencies.
- Ran `npx prettier --write` and `npx eslint --fix` across the UI, including `vite.config.ts`, keeping the diff formatting-only.
- Renamed non-JSX hooks from `.tsx` to `.ts` (`src/hooks/chat`, `input`, `search`) so file extensions match content without changing imports.
- Verified `npm run lint` and `npm run build` pass; `npm test` currently fails because `aithena-ui/package.json` has no `test` script yet.

### 2026-03-15T08:30 — Reskill: Current Frontend Codebase & Architecture

**Component Inventory:**
- `BookCard.tsx` — Renders a single search result with title, metadata (author, year, category, language, page count), Solr highlights (snippet with <em> wrapping), and "Open PDF" button.
  - Sanitizes highlights to prevent XSS (keeps only `<em>` tags, escapes all other HTML).
  - Uses `formatFoundPages()` helper to display page ranges where search term was found.
- `FacetPanel.tsx` — Sidebar for filtering by author, category, language, year (facet counts from search API).
- `ActiveFilters.tsx` — Displays active filters as removable badges, with "Clear All" button.
- `Pagination.tsx` — Next/prev buttons with page indicators; controls `searchState.page`.
- `PdfViewer.tsx` — Modal dialog using iframe to embed PDF via `document_url` (hosted on backend).
  - Converts search `page_count` to viewer page number (1-based indexing).
- `TabNav.tsx` — Sticky header nav with React Router links: Search, Library, Status, Stats.
- `CollectionStats.tsx` — Dashboard showing total_books, language/author/year/category distributions, page statistics.
- `IndexingStatus.tsx` — Real-time display of Solr health, indexing progress (total_discovered, indexed, failed, pending).
- Deprecated/chat-era: `ChatMessage.ts`, `Configbar.tsx` (not actively used in current UI).

**Hook Patterns (`src/hooks/`):**
1. **`search.ts` (`useSearch()`)** — State management for search interaction:
   - Tracks: query, filters (author/category/language/year), page, limit (10), sort (score/year/title/author).
   - API calls to `{apiBase}/v1/search?q=...&fq_*=...&page=...&limit=...&sort=...`.
   - Returns: { searchState, results[], facets, total, loading, error, setQuery(), setFilter(), clearFilters(), setPage(), setSort(), setLimit() }.
   - Auto-executes search when state changes (useEffect dependency).
   - Resets page to 1 when query or filters change.

2. **`status.ts` (`useStatus()`)** — Polling hook for system health (10s intervals):
   - Fetches from `{apiBase}/v1/status/` → { solr: {status, nodes, docs_indexed}, indexing: {total_discovered, indexed, failed, pending}, services: {solr/redis/rabbitmq status} }.
   - Returns: { data, loading, error, lastUpdated }.
   - Uses AbortController to cancel in-flight requests on unmount.
   - Doesn't fetch until component mounts (initial loading=true).

3. **`stats.ts` (`useStats()`)** — One-shot stats fetch for Stats tab:
   - Fetches from `{apiBase}/v1/stats/` → { total_books, by_language[], by_author[], by_year[], by_category[], page_stats: {total, avg, min, max} }.
   - Returns: { stats, loading, error }.
   - Uses cancellation flag to avoid state updates after unmount.

4. **Other hooks:** `chat.ts`, `input.ts` (legacy, minimal usage).

**Routing Structure (`react-router-dom` v7.13.1):**
- `App.tsx` defines BrowserRouter + Routes.
- Routes: `/` → redirect to `/search`, `/search` (SearchPage), `/library` (LibraryPage), `/status` (StatusPage), `/stats` (StatsPage).
- TabNav displays active tab via route-aware styling (activeClassName or custom logic).

**CSS/Styling Approach:**
- **File:** `App.css` + `normal.css` (global reset/normalize).
- **No CSS-in-JS or component-scoped styles** — all BEM-like classes in global CSS.
- **Colors:** Dark theme (#282c34 background, #202123 header, white text, accent blue #7ec8e3).
- **Layout:** CSS Flexbox throughout (app header + content area, tab nav, search layout with sidebar + results).
- **Classes follow pattern:** `.book-card`, `.book-title`, `.book-meta`, `.book-highlights`, `.facet-panel`, `.active-filters`, etc.
- **Interactive states:** `:hover`, `--active` suffix on elements (e.g., `.book-card--active`).
- **Bootstrap 5.3.0 installed** but largely unused; appears to be a legacy dependency.

**API Integration (`src/api.ts`):**
- `buildApiUrl(path)` — Helper that normalizes `VITE_API_URL` env var.
  - If env is "." or unset and UI runs on localhost dev ports (5173, 4173, etc.), defaults to `http://localhost:8080`.
  - Otherwise uses env or relative paths for proxied deployments.
- `resolveDocumentUrl(documentUrl)` — Resolves PDF URLs (relative or absolute).
- Vite proxy rules in `vite.config.ts` route `/v1/*` and `/documents/*` to backend API.

**Key File Paths:**
- `aithena-ui/src/Components/` — React components (mostly .tsx, some legacy .ts).
- `aithena-ui/src/hooks/` — Custom hooks (.ts files).
- `aithena-ui/src/pages/` — Page components (SearchPage, LibraryPage, StatusPage, StatsPage).
- `aithena-ui/src/Components/types/` — TypeScript type definitions.
- `aithena-ui/src/App.tsx` — Root component.
- `aithena-ui/src/App.css` — Main stylesheet.
- `aithena-ui/src/main.tsx` — Entry point.
- `aithena-ui/vite.config.ts` — Vite configuration.
- `aithena-ui/package.json` — Dependencies: React 18, react-router-dom 7.13.1, Bootstrap 5.3.0, dev tools.

**Recent Changes (last 20 commits):**
- Latest: Added CollectionStats component + useStats hook for Stats tab.
- Fixes to IndexingStatus component and useStatus hook API alignment (AbortController, pages array contract).
- PDF viewer page navigation support.
- Tab navigation with React Router.
- Prettier + ESLint formatting pass.
- Overall trajectory: Phase 2 → Phase 3 (faceted search UI mature, adding system status/stats dashboards).

**Testing Status:**
- No test script in package.json yet.
- Vitest + React Testing Library are available as dev deps but no test files exist.
- `npm run lint` and `npm run build` pass cleanly.

### 2026-03-15T09:05 — Added Similar Books panel to SearchPage

- Created `src/hooks/similarBooks.ts` with `useSimilarBooks(documentId)` to call `/v1/books/{documentId}/similar?limit=5&min_score=0.0`, using `buildApiUrl` and `AbortController` cleanup.
- Added `src/Components/SimilarBooks.tsx` as a horizontal recommendation strip with title, author, score badge, loading skeletons, empty state, and friendly error handling.
- Integrated the panel into `SearchPage.tsx` so selecting a book for PDF viewing also loads similar titles; clicking a similar book swaps the selected PDF and refreshes recommendations.
- Added dark-theme styles in `App.css` for `.similar-books-panel`, `.similar-book-card`, and `.similarity-score`.
- Added Vitest coverage for the new panel and SearchPage interaction; verified `npm run lint`, `npm run build`, and `npm test` all pass.

