# PRD: v0.4.0 — Dashboard & Polish

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Status:** PROPOSED
**Milestone:** v0.4.0 — Dashboard & Polish

---

## Vision

Transform aithena from a single-page search app into a multi-tab application with Library browsing, Status monitoring, and Stats dashboards — while hardening the frontend with linting, formatting, and test coverage.

## User Stories

### US-1: Tab Navigation
**As a** user, **I want** tab navigation (Search / Library / Status / Stats) **so that** I can access different views without leaving the app.

### US-2: Library Browser
**As a** librarian, **I want** to browse the book collection by folder/author **so that** I can discover books without searching.

### US-3: Status Dashboard
**As an** operator, **I want** to see indexing progress and service health **so that** I know if the pipeline is working.

### US-4: Stats Dashboard
**As a** librarian, **I want** to see collection statistics (total books, by language, by author) **so that** I understand the library's composition.

### US-5: Frontend Test Coverage
**As a** developer, **I want** frontend tests for search, facets, and PDF viewing **so that** regressions are caught before merge.

### US-6: Frontend Code Quality
**As a** developer, **I want** eslint + prettier enforced in CI **so that** code style is consistent.

---

## Architecture

### Clean Architecture Layers

#### Backend (Python/FastAPI)

```
┌────────────────────────────┐
│  Presentation (main.py)    │  ← FastAPI routes, request/response models
├────────────────────────────┤
│  Application (services)    │  ← Business logic, orchestration
├────────────────────────────┤
│  Domain (models)           │  ← Data models, validation rules
├────────────────────────────┤
│  Infrastructure (clients)  │  ← Solr HTTP, RabbitMQ, Redis, filesystem
└────────────────────────────┘
```

- **Presentation:** `main.py` — HTTP routes, parameter validation, response formatting
- **Application:** `search_service.py`, `status_service.py`, `stats_service.py` — business logic
- **Domain:** Shared types (BookResult, StatusResponse, StatsResponse)
- **Infrastructure:** Solr client, RabbitMQ management API client, Redis client, filesystem reader

#### Frontend (React/TypeScript)

```
┌────────────────────────────┐
│  Pages (SearchPage, etc.)  │  ← Route-level components, layout
├────────────────────────────┤
│  Components (BookCard...)  │  ← Presentational, reusable UI
├────────────────────────────┤
│  Hooks (useSearch, etc.)   │  ← State management, side effects
├────────────────────────────┤
│  API (api.ts)              │  ← HTTP client, type-safe fetch wrappers
└────────────────────────────┘
```

- **Pages:** `SearchPage.tsx`, `LibraryPage.tsx`, `StatusPage.tsx`, `StatsPage.tsx`
- **Components:** `BookCard`, `FacetPanel`, `Pagination`, `PdfViewer`, `ServiceHealth`, `CollectionStats`, `FolderBrowser`
- **Hooks:** `useSearch()`, `useLibrary()`, `useStatus()`, `useStats()`
- **API:** `api.ts` — typed fetch functions for each endpoint

---

## Existing PRs (in progress)

| PR | Title | Status | Blocks |
|----|-------|--------|--------|
| #119 | `/v1/status/` endpoint | READY | — |
| #114 | `/v1/status/` issue | Open | #119 |
| #123 | Tab navigation (react-router-dom) | DRAFT | #119 |
| #127 | Stats tab (frontend) | DRAFT | #123 |
| #128 | Status tab (frontend) | DRAFT | #119, #123 |

**Note:** `/v1/stats/` endpoint already exists in `main.py` (merged in prior PR). `/v1/status/` is in PR #119.

---

## Implementation Tasks (TDD)

### Task 1: Status Endpoint — Backend Service Extraction
**Issue:** #114
**Agent:** Parker
**Layer:** Application + Infrastructure
**Effort:** S

**TDD Spec:**
1. **Write test:** `test_status_service.py` — mock Solr/RabbitMQ/Redis HTTP calls, verify `get_status()` returns aggregated health with correct structure (`{services: [{name, status, details}], overall: "healthy"|"degraded"|"down"}`)
2. **Red:** Test fails (no `status_service.py` exists)
3. **Implement:** Extract status logic from PR #119's inline code into `status_service.py`. Query Solr `/admin/collections`, RabbitMQ management API `/api/queues`, Redis `PING`, embeddings-server `/health`.
4. **Green:** Test passes
5. **Refactor:** Extract HTTP client helpers into `infrastructure/` module for reuse

**Interface:**
```python
def get_status() -> StatusResponse:
    """Returns aggregated health of all services."""
```

**Acceptance Criteria:**
- Returns health for: solr, rabbitmq, redis, embeddings-server
- Each service has: name, status (up/down/degraded), response_time_ms, details
- Overall status: "healthy" (all up), "degraded" (some down), "down" (all down)
- Timeout per service check: 3s (configurable)

---

### Task 2: Stats Endpoint — Service Extraction
**Issue:** (part of existing stats)
**Agent:** Parker
**Layer:** Application
**Effort:** S

**TDD Spec:**
1. **Write test:** `test_stats_service.py` — mock Solr stats response, verify `get_stats()` returns `{total_books, by_language, by_author, by_category, index_size_mb}`
2. **Red:** Test fails (no `stats_service.py` exists)
3. **Implement:** Extract stats logic from `main.py` into `stats_service.py`. Use existing `parse_stats_response()` + add language/author/category facet aggregation.
4. **Green:** Test passes
5. **Refactor:** Ensure stats service has no direct HTTP dependency (inject Solr client)

**Interface:**
```python
def get_stats(solr_response: dict) -> StatsResponse:
    """Parses Solr stats + facets into structured stats."""
```

**Acceptance Criteria:**
- Total document count
- Top 10 authors by document count
- Language distribution
- Category distribution
- Collection size (from Solr admin API)

---

### Task 3: Tab Navigation — React Router Setup
**Issue:** #120
**Agent:** Dallas
**Layer:** Presentation (Pages)
**Effort:** S
**Depends on:** None (pure frontend scaffold)

**TDD Spec:**
1. **Write test:** `App.test.tsx` — render App, verify 4 tab links exist, verify clicking "Library" navigates to `/library`, verify `/search` renders SearchPage component
2. **Red:** Test fails (no router, no pages)
3. **Implement:** Install `react-router-dom`, refactor `App.tsx` into router shell with `<NavLink>` tabs. Extract current search UI into `SearchPage.tsx`. Create stub pages for Library/Status/Stats.
4. **Green:** Test passes
5. **Refactor:** Extract tab layout into `TabLayout.tsx` component. Ensure active tab styling.

**Interface:**
```typescript
// Routes
/search     → <SearchPage />
/library    → <LibraryPage />   (stub)
/status     → <StatusPage />    (stub)
/stats      → <StatsPage />     (stub)
/           → redirect to /search
```

**Acceptance Criteria:**
- 4 tabs visible: Search, Library, Status, Stats
- Active tab is visually highlighted
- Browser back/forward works
- Default route (`/`) redirects to `/search`
- Existing search functionality unchanged after extraction

---

### Task 4: Stats Tab — Frontend Component
**Issue:** #121
**Agent:** Dallas
**Layer:** Components + Hooks
**Effort:** S
**Depends on:** Task 2, Task 3

**TDD Spec:**
1. **Write test:** `StatsPage.test.tsx` — mock `useStats()` hook return, verify renders total count, language table, author table. Test loading state. Test error state.
2. **Red:** Test fails (no StatsPage)
3. **Implement:** `useStats()` hook fetching `/v1/stats/`. `StatsPage.tsx` rendering tables with stats data.
4. **Green:** Test passes
5. **Refactor:** Extract reusable `DataTable` component for stats tables

**Interface:**
```typescript
function useStats(): { stats: StatsData | null; loading: boolean; error: string | null; refresh: () => void }
```

**Acceptance Criteria:**
- Shows total book count prominently
- Language distribution table (language, count, percentage)
- Top 10 authors table (author, count)
- Category distribution table
- Loading spinner while fetching
- Error message on failure
- Manual refresh button

---

### Task 5: Status Tab — Frontend Component
**Issue:** #122
**Agent:** Dallas
**Layer:** Components + Hooks
**Effort:** M
**Depends on:** Task 1, Task 3

**TDD Spec:**
1. **Write test:** `StatusPage.test.tsx` — mock `useStatus()`, verify renders service list with health indicators (green/yellow/red). Test auto-refresh triggers. Test "all healthy" vs "degraded" states.
2. **Red:** Test fails (no StatusPage)
3. **Implement:** `useStatus()` hook polling `/v1/status/` every 10s. `StatusPage.tsx` with service health cards. Color-coded status (green=up, yellow=degraded, red=down).
4. **Green:** Test passes
5. **Refactor:** Extract `ServiceHealthCard` component. Add response time display.

**Interface:**
```typescript
function useStatus(pollInterval?: number): { status: StatusData | null; loading: boolean; error: string | null }
```

**Acceptance Criteria:**
- Shows each service: Solr, RabbitMQ, Redis, Embeddings Server
- Color-coded status indicator per service
- Overall system health banner
- Auto-refreshes every 10 seconds
- Response time per service
- Last checked timestamp
- Manual refresh button

---

### Task 6: Library Browser — Backend Endpoint
**Issue:** (new — create as part of v0.4.0)
**Agent:** Parker
**Layer:** Application + Infrastructure
**Effort:** M

**TDD Spec:**
1. **Write test:** `test_library_service.py` — mock filesystem + Solr, verify `list_directory("/")` returns folders and files with Solr metadata. Verify path traversal blocked. Verify non-existent path returns 404.
2. **Red:** Test fails (no library service)
3. **Implement:** `GET /v1/library/?path=` endpoint. Reads filesystem under `BASE_PATH`, enriches entries with Solr metadata (indexed status, page count, language). Path traversal protection (resolve + check prefix).
4. **Green:** Test passes
5. **Refactor:** Dependency-inject filesystem reader for testability

**Interface:**
```python
@app.get("/v1/library/")
def list_library(path: str = "") -> LibraryResponse:
    """List directory contents with Solr metadata enrichment."""
```

**Acceptance Criteria:**
- Lists folders and files at given path
- Each file shows: name, size, indexed (bool), page_count, language, author
- Folders show: name, file_count (recursive)
- Path traversal prevention (cannot escape BASE_PATH)
- Returns 404 for non-existent paths
- Supports root listing (path="")

---

### Task 7: Library Browser — Frontend Component
**Issue:** (new — create as part of v0.4.0)
**Agent:** Dallas
**Layer:** Pages + Components + Hooks
**Effort:** L
**Depends on:** Task 3, Task 6

**TDD Spec:**
1. **Write test:** `LibraryPage.test.tsx` — mock `useLibrary()`, verify renders folder tree and file list. Verify clicking folder navigates into it. Verify clicking file opens PdfViewer. Test breadcrumb navigation.
2. **Red:** Test fails (no LibraryPage)
3. **Implement:** `useLibrary()` hook fetching `/v1/library/?path=`. `LibraryPage.tsx` with breadcrumbs, folder list, file list. Click folder → navigate. Click file → PdfViewer.
4. **Green:** Test passes
5. **Refactor:** Extract `Breadcrumbs`, `FolderList`, `FileList` sub-components

**Interface:**
```typescript
function useLibrary(path: string): { entries: LibraryEntry[]; loading: boolean; error: string | null }
```

**Acceptance Criteria:**
- Breadcrumb navigation showing current path
- Folders displayed with folder icon, name, file count
- Files displayed with book icon, name, indexed status badge, metadata
- Click folder → navigates into subfolder (URL updates)
- Click file → opens PDF viewer
- Back button works (browser history)
- Empty folder shows message

---

### Task 8: Frontend Linting — Prettier + ESLint Config
**Issue:** #93, #94
**Agent:** Dallas
**Layer:** Infrastructure (tooling)
**Effort:** S

**TDD Spec:**
1. **Write test:** N/A (config task, not code). Validation: `npx prettier --check "src/**/*.{ts,tsx}"` exits 0. `npx eslint src/` exits 0.
2. **Implement:** Add `.prettierrc`, update `.eslintrc` / `eslint.config.js`. Add CI job in `.github/workflows/ci.yml`.
3. **Validate:** `npm run lint` and `npm run format:check` pass
4. **Refactor:** Auto-fix existing files with `prettier --write` and `eslint --fix`

**Acceptance Criteria:**
- `.prettierrc` with consistent settings (2-space indent, single quotes, trailing commas)
- ESLint config with React + TypeScript rules
- `npm run lint` script in `package.json`
- `npm run format:check` script in `package.json`
- CI job fails PR if lint/format checks fail
- All existing files pass after auto-fix

---

### Task 9: Frontend Test Coverage
**Issue:** #41
**Agent:** Lambert
**Layer:** All frontend layers
**Effort:** L
**Depends on:** Tasks 3-7

**TDD Spec:**
1. **Write tests for existing components:**
   - `BookCard.test.tsx` — renders title, author, year; sanitizes HTML snippets; click opens PDF
   - `FacetPanel.test.tsx` — renders facet categories; click selects filter
   - `Pagination.test.tsx` — renders page numbers; click changes page
   - `PdfViewer.test.tsx` — renders iframe with correct URL; escape closes viewer
   - `useSearch.test.ts` — hook returns correct state shape; setQuery triggers fetch
2. **Write tests for new components (from Tasks 4-7):**
   - `StatsPage.test.tsx`, `StatusPage.test.tsx`, `LibraryPage.test.tsx`
3. **Validate:** `npm run test` passes with ≥70% line coverage on components/

**Acceptance Criteria:**
- Every component has at least one test file
- Every hook has at least one test file
- Tests cover: rendering, user interaction, error states, loading states
- `npm run test` script works in CI
- Coverage target: ≥70% lines on `src/Components/` and `src/hooks/`

---

## Implementation Order

```
Phase A (parallel — no dependencies):
  Task 1: Status endpoint (Parker)
  Task 2: Stats extraction (Parker)
  Task 3: Tab navigation (Dallas)
  Task 8: Prettier + ESLint (Dallas)

Phase B (depends on Phase A):
  Task 4: Stats tab UI (Dallas) — needs Task 2 + 3
  Task 5: Status tab UI (Dallas) — needs Task 1 + 3
  Task 6: Library endpoint (Parker) — needs nothing, but sequenced

Phase C (depends on Phase B):
  Task 7: Library browser UI (Dallas) — needs Task 3 + 6
  Task 9: Test coverage (Lambert) — needs Tasks 3-7

Merge order: 1,2 → 3,8 → 4,5 → 6 → 7 → 9
```

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| react-router-dom conflicts with existing search state | M | SearchPage extraction preserves all hook state |
| Library endpoint path traversal vulnerability | H | Reuse existing `resolve_document_path()` pattern |
| Status polling overwhelms services | L | 10s interval, short timeout, circuit breaker |
| `--legacy-peer-deps` still required | L | Document in README, plan upgrade in v0.5.0 |

## Success Criteria

1. All 4 tabs render and navigate correctly
2. Status page shows real service health
3. Stats page shows collection statistics
4. Library page browses real filesystem with metadata
5. `npm run lint` and `npm run format:check` pass in CI
6. `npm run test` passes with ≥70% component coverage
7. All existing search functionality preserved (no regressions)
