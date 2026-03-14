# v0.4.0 Task Decomposition — TDD Specs

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Milestone:** v0.4.0 — Dashboard & Polish
**Skill:** `.squad/skills/tdd-clean-code/SKILL.md`

---

## Task Summary

| # | Task | Agent | Layer | Effort | Depends On |
|---|------|-------|-------|--------|------------|
| T1 | Status endpoint — service extraction | Parker | App + Infra | S | — |
| T2 | Stats endpoint — service extraction | Parker | Application | S | — |
| T3 | Tab navigation — React Router | Dallas | Presentation | S | — |
| T4 | Stats tab — frontend | Dallas | Components + Hooks | S | T2, T3 |
| T5 | Status tab — frontend | Dallas | Components + Hooks | M | T1, T3 |
| T6 | Library endpoint — backend | Parker | App + Infra | M | — |
| T7 | Library browser — frontend | Dallas | Pages + Components | L | T3, T6 |
| T8 | Prettier + ESLint config | Dallas | Infrastructure | S | — |
| T9 | Frontend test coverage | Lambert | All frontend | L | T3–T7 |

**Total: 9 tasks (4S + 2M + 2L + 1S-config = ~3 sprints)**

---

## Detailed TDD Specs

### Task T1: Status Endpoint — Service Extraction
**Issue:** #114 / PR #119
**Agent:** Parker
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `solr-search/tests/test_status_service.py`
   - `test_get_status_all_healthy` — mock all 4 services responding 200, verify overall="healthy"
   - `test_get_status_solr_down` — mock Solr timeout, verify overall="degraded", solr.status="down"
   - `test_get_status_all_down` — mock all timeouts, verify overall="down"
   - `test_get_status_response_time` — verify response_time_ms populated per service
2. Verify test fails (red) — no `status_service.py` exists
3. Implement: `solr-search/status_service.py`
   - `check_service(name, url, timeout)` → `ServiceHealth`
   - `get_status(config)` → `StatusResponse`
   - Queries: Solr `/admin/collections`, RabbitMQ `/api/queues`, Redis `PING`, embeddings `/health`
4. Verify test passes (green)
5. Refactor: extract `HttpHealthChecker` class for reusable health probing

**Clean Architecture:**
- Layer: Application (status_service.py) + Infrastructure (HTTP health checks)
- Dependencies: `config.py` (URLs), `requests` (HTTP)
- Interface: `get_status(config: Settings) -> StatusResponse`

---

### Task T2: Stats Endpoint — Service Extraction
**Issue:** (existing `/v1/stats/` in main.py)
**Agent:** Parker
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `solr-search/tests/test_stats_service.py`
   - `test_parse_stats_total_books` — verify total count from Solr numFound
   - `test_parse_stats_by_language` — verify language facet aggregation
   - `test_parse_stats_by_author` — verify top-10 authors from facets
   - `test_parse_stats_empty_collection` — verify graceful handling of 0 docs
2. Verify test fails (red) — no `stats_service.py` exists
3. Implement: `solr-search/stats_service.py`
   - Extract stats logic from inline `/stats` route
   - `get_collection_stats(solr_response: dict) -> StatsResponse`
4. Verify test passes (green)
5. Refactor: ensure `main.py` `/stats` route is a thin wrapper calling `stats_service`

**Clean Architecture:**
- Layer: Application (stats_service.py)
- Dependencies: None (pure function on Solr response dict)
- Interface: `get_collection_stats(response: dict) -> StatsResponse`

---

### Task T3: Tab Navigation — React Router
**Issue:** #120 / PR #123
**Agent:** Dallas
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `aithena-ui/src/App.test.tsx`
   - `test_renders_four_tabs` — verify Search, Library, Status, Stats links exist
   - `test_search_tab_active_by_default` — verify `/` redirects to search, tab highlighted
   - `test_navigate_to_library` — click Library tab, verify LibraryPage rendered
   - `test_browser_back_works` — navigate to Library, press back, verify Search rendered
2. Verify test fails (red) — no router exists
3. Implement:
   - `npm install react-router-dom`
   - Refactor `App.tsx` → router shell with `<NavLink>` tabs
   - Extract current search into `pages/SearchPage.tsx`
   - Create stub `pages/LibraryPage.tsx`, `pages/StatusPage.tsx`, `pages/StatsPage.tsx`
4. Verify test passes (green)
5. Refactor: extract `TabLayout.tsx` for consistent tab chrome

**Clean Architecture:**
- Layer: Presentation (Pages)
- Dependencies: react-router-dom, existing hooks/components
- Interface: Routes `/search`, `/library`, `/status`, `/stats`

---

### Task T4: Stats Tab — Frontend
**Issue:** #121 / PR #127
**Agent:** Dallas
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `aithena-ui/src/pages/StatsPage.test.tsx`
   - `test_renders_total_book_count` — mock useStats, verify "169 books" displayed
   - `test_renders_language_table` — verify language rows with counts
   - `test_renders_loading_state` — verify spinner when loading=true
   - `test_renders_error_state` — verify error message when error is set
   - `test_refresh_button_calls_refresh` — verify click triggers refetch
2. Verify test fails (red)
3. Implement:
   - `hooks/useStats.ts` — fetches `/v1/stats/`, returns `{ stats, loading, error, refresh }`
   - `pages/StatsPage.tsx` — renders tables from stats data
   - Add `fetchStats()` to `api.ts`
4. Verify test passes (green)
5. Refactor: extract `DataTable` component for reusable tabular display

**Clean Architecture:**
- Layer: Pages (StatsPage) → Components (DataTable) → Hooks (useStats) → API (fetchStats)
- Dependencies: Task T2 (backend), Task T3 (router)
- Interface: `useStats(): { stats: StatsData | null, loading: boolean, error: string | null, refresh: () => void }`

---

### Task T5: Status Tab — Frontend
**Issue:** #122 / PR #128
**Agent:** Dallas
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `aithena-ui/src/pages/StatusPage.test.tsx`
   - `test_renders_service_list` — mock useStatus, verify 4 service cards rendered
   - `test_healthy_service_shows_green` — verify green indicator for status="up"
   - `test_degraded_shows_yellow_banner` — verify overall="degraded" banner
   - `test_auto_refresh_calls_api` — verify polling triggers after interval
   - `test_shows_response_time` — verify "45ms" displayed for each service
2. Verify test fails (red)
3. Implement:
   - `hooks/useStatus.ts` — polls `/v1/status/` every 10s, returns `{ status, loading, error }`
   - `pages/StatusPage.tsx` — renders service health cards
   - `Components/ServiceHealthCard.tsx` — single service card with indicator
   - Add `fetchStatus()` to `api.ts`
4. Verify test passes (green)
5. Refactor: extract polling logic into `usePolling()` generic hook

**Clean Architecture:**
- Layer: Pages (StatusPage) → Components (ServiceHealthCard) → Hooks (useStatus) → API (fetchStatus)
- Dependencies: Task T1 (backend), Task T3 (router)
- Interface: `useStatus(pollInterval?: number): { status: StatusData | null, loading: boolean, error: string | null }`

---

### Task T6: Library Endpoint — Backend
**Issue:** new (create under v0.4.0)
**Agent:** Parker
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `solr-search/tests/test_library_service.py`
   - `test_list_root_returns_folders` — mock filesystem, verify folder listing
   - `test_list_folder_returns_files_with_metadata` — mock fs + Solr, verify enriched entries
   - `test_path_traversal_blocked` — verify `../` in path returns 400
   - `test_nonexistent_path_returns_404` — verify missing path returns 404
   - `test_file_shows_indexed_status` — mock Solr query, verify `indexed: true` for indexed file
2. Verify test fails (red) — no library endpoint exists
3. Implement: `solr-search/library_service.py`
   - `list_directory(base_path, relative_path, solr_client)` → `LibraryResponse`
   - `GET /v1/library/?path=` route in `main.py`
   - Path traversal protection using `resolve_document_path()` pattern
4. Verify test passes (green)
5. Refactor: extract `FileSystemReader` protocol for testability

**Clean Architecture:**
- Layer: Application (library_service.py) + Infrastructure (filesystem + Solr enrichment)
- Dependencies: `config.py` (BASE_PATH), `requests` (Solr), `pathlib` (filesystem)
- Interface: `list_directory(base: Path, path: str) -> LibraryResponse`

---

### Task T7: Library Browser — Frontend
**Issue:** new (create under v0.4.0)
**Agent:** Dallas
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: `aithena-ui/src/pages/LibraryPage.test.tsx`
   - `test_renders_folder_list` — mock useLibrary, verify folder names displayed
   - `test_click_folder_navigates` — verify clicking folder updates URL path
   - `test_renders_breadcrumbs` — verify breadcrumb shows "Root > amades > subfolder"
   - `test_click_file_opens_pdf` — verify PdfViewer opens on file click
   - `test_empty_folder_message` — verify "No files found" for empty directory
2. Verify test fails (red)
3. Implement:
   - `hooks/useLibrary.ts` — fetches `/v1/library/?path=`, returns `{ entries, loading, error }`
   - `pages/LibraryPage.tsx` — breadcrumbs + folder/file list
   - `Components/Breadcrumbs.tsx` — path navigation
   - `Components/FolderList.tsx` — folder entries
   - `Components/FileList.tsx` — file entries with metadata badges
   - Add `fetchLibrary()` to `api.ts`
4. Verify test passes (green)
5. Refactor: memoize directory listings, add virtualization if >100 entries

**Clean Architecture:**
- Layer: Pages (LibraryPage) → Components (Breadcrumbs, FolderList, FileList) → Hooks (useLibrary) → API (fetchLibrary)
- Dependencies: Task T3 (router), Task T6 (backend)
- Interface: `useLibrary(path: string): { entries: LibraryEntry[], loading: boolean, error: string | null }`

---

### Task T8: Prettier + ESLint Config
**Issue:** #93, #94
**Agent:** Dallas
**Milestone:** v0.4.0

**TDD Spec:**
1. Write test: N/A (tooling config). Validation:
   - `npx prettier --check "src/**/*.{ts,tsx}"` exits 0
   - `npx eslint src/` exits 0
2. Implement:
   - Add `.prettierrc` to `aithena-ui/`
   - Add/update ESLint config (flat config or `.eslintrc`)
   - Add `"lint": "eslint src/"` and `"format:check": "prettier --check src/"` to `package.json`
   - Add CI job in `.github/workflows/ci.yml`
3. Validate: run `npm run lint && npm run format:check`
4. Refactor: auto-fix all existing files with `prettier --write` and `eslint --fix`

**Clean Architecture:**
- Layer: Infrastructure (tooling)
- Dependencies: None
- Interface: `npm run lint`, `npm run format:check`

---

### Task T9: Frontend Test Coverage
**Issue:** #41
**Agent:** Lambert
**Milestone:** v0.4.0

**TDD Spec:**
1. Write tests for all existing + new components:

   **Existing components:**
   - `BookCard.test.tsx` — renders title/author/year, sanitizes HTML, click opens PDF
   - `FacetPanel.test.tsx` — renders categories, click selects filter, shows counts
   - `Pagination.test.tsx` — renders pages, click changes page, disables at bounds
   - `PdfViewer.test.tsx` — renders iframe, escape closes, error state
   - `ActiveFilters.test.tsx` — renders active filters, click removes filter

   **Existing hooks:**
   - `useSearch.test.ts` — returns state shape, setQuery triggers fetch, handles errors

   **New components (from T4-T7):**
   - `StatsPage.test.tsx` — already defined in T4
   - `StatusPage.test.tsx` — already defined in T5
   - `LibraryPage.test.tsx` — already defined in T7
   - `ServiceHealthCard.test.tsx` — renders indicator, shows response time
   - `Breadcrumbs.test.tsx` — renders path segments, click navigates

2. Coverage validation: `npm run test -- --coverage`
   - Target: ≥70% lines on `src/Components/` and `src/hooks/`

**Clean Architecture:**
- Layer: All frontend layers (tests validate contracts between layers)
- Dependencies: Tasks T3–T7 (components must exist)
- Interface: `npm run test`, `npm run test -- --coverage`
