# Dallas — Frontend Developer History

**Last Updated:** 2026-03-25 (issue #1138)  
**Status:** v1.10.0+ in progress. Shipped: v1.4.0–v1.10.0. Collections API & UX (v1.11.0+) active.

---

## Recent

### #1138 — Admin dashboard pagination (v1.16.0)
- Added client-side pagination (page size 25) to all three admin tabs (queued/processed/failed)
- React: reused existing `Pagination` component, added per-tab page state to `AdminPage`
- Streamlit: added `paginate()` helper with `st.number_input` page controls
- No backend API changes needed — client-side slicing is sufficient for current scale
- Streamlit admin is deprecated in v2.0; kept fix minimal

---

## Core Context

**Project:** Aithena — Book library search engine with semantic + keyword search  
**Role:** Dallas, Frontend Developer (React/TypeScript specialist)  
**Team:** Squad (Ripley, Parker, Brett, Newt, Kane + others)

### Frontend Stack (Stable)
- **Framework:** React 19 + TypeScript strict mode
- **Build:** Vite 8.x with TypeScript
- **Linting:** ESLint 10 (flat config, jsx-a11y plugin)
- **Testing:** Vitest 4.1 + React Testing Library
- **Routing:** React Router 7.13.1 (14 pages: Search, Library, Upload, Status, Stats, Login, Admin, Profile, UserManagement, ChangePassword, Collections, CollectionDetail, BackupDashboard, StatsPage)
- **i18n:** react-intl 10.0 (4 locales: en, es, ca, fr; ~300+ keys)
- **Icons:** Lucide React
- **Styling:** Global CSS (BEM) + CSS Modules (Footer, LoadingSpinner)
- **Auth:** Cookie-based + AuthContext + ProtectedRoute/AdminRoute
- **Components:** 40+ presentational components

### File Organization
```
src/aithena-ui/src/
├── App.tsx, api.ts, main.tsx
├── Components/   (40+: BookCard, BookDetailView, PdfViewer, SimilarBooks, BatchEditPanel,
│                  MetadataEditModal, CollectionModal, FolderFacetTree, AdminRoute, etc.)
├── hooks/        (16: search, bookDetail, collections, useBatchMetadataEdit, etc.)
├── pages/        (14: SearchPage, LibraryPage, CollectionsPage, AdminPage, etc.)
├── contexts/     (AuthContext, I18nContext)
├── locales/      (en.json, es.json, ca.json, fr.json)
└── __tests__/    (600+ tests)
```

---

## Consolidated Learnings

### Architecture Patterns (proven across v1.4.0–v1.10.0)

1. **Separation of concerns:** Pages compose components + hooks. Components are presentational only. Hooks own state + API calls. `api.ts` is the only module making HTTP calls.
2. **Hook cleanup:** Always use `cancelled` flag + `AbortController` in data-fetching hooks to prevent memory leaks and race conditions.
3. **Polling hooks:** Use `setTimeout` chaining (not `setInterval`) for status polling. Explicitly handle `AbortError` as non-error.
4. **Search state reset:** Always reset pagination to page 1 when query/filters change. Use immutable state updates.
5. **Error boundaries:** Must be route-aware — reset on navigation via `useLocation()`. Nest boundaries to isolate sections (search results, upload panel).
6. **CSS:** Global CSS + BEM naming. CSS Modules emerging for isolated components (Footer, LoadingSpinner). Dark theme with `#282c34` bg, `#7ec8e3` accent.
7. **Auth:** Cookie-based (`aithena_auth`, HttpOnly, SameSite=lax). AuthContext wraps app. ProtectedRoute/AdminRoute for gating. `credentials: 'include'` on all API calls.

### i18n Patterns (established v1.6.0–v1.7.0)

1. **Key naming:** `domain.featureKey` (lowerCamelCase, dot-separated). Domains: search, filter, books, error, language, admin, upload, navigation, status, stats, app.
2. **Module-level arrays:** Use `labelId` pattern (not `label`), resolve at render time via `useIntl()`.
3. **Helpers → Components:** Convert helper functions to React components when they need hooks (e.g., `renderLazyRoute` → `LazyRoute` component).
4. **localStorage:** `aithena.locale` (dot-notation). Auto-migration from old keys on first load.
5. **Translation verification:** Locale completeness tests check keys exist but NOT that values differ from English. Consider adding "untranslated value" detection.

### Toolchain & Build (proven across migrations)

1. **ESLint migrations (v8→v9→v10):** Low-risk if tests are comprehensive and linting is strict (`--max-warnings 0`).
2. **API URL resolution:** Centralized `buildApiUrl()` in `api.ts`. Supports `VITE_API_URL` as ".", unset, or full URL. Localhost fallback for dev.
3. **Document URL normalization:** `resolveDocumentUrl()` strips internal Docker hostnames from backend-generated absolute URLs, keeping only the `/documents/` path.
4. **Vite ESM:** `vite.config.ts` needs `dirname(fileURLToPath(import.meta.url))` — no `__dirname` in ESM.
5. **Vite proxy:** Dev proxy rules for `/v1` and `/documents` route to `http://localhost:8080`.

### Accessibility (established v1.8.0+)

1. **Skip-to-content link** with CSS show-on-focus + i18n labels.
2. **Focus management** on route changes via `useEffect` + `useLocation` + mainRef.
3. **Contrast:** Minimum rgba opacity 0.65 for WCAG AA 4.5:1 ratio.
4. **Media queries:** `prefers-reduced-motion: reduce` disables animations. `prefers-contrast: more` enhances backgrounds.
5. **ARIA:** `aria-modal="true"` on dialogs, `role="img"` on health dots, `scope="col"` on table headers.
6. **Static analysis:** eslint-plugin-jsx-a11y catches redundant roles, missing keyboard handlers. Covers ~70% of WCAG; remaining 30% needs browser-based audit.

### E2E & Testing Patterns

1. **Emoji in headless Chromium:** Never use exact emoji matching. Use `toContainText` with text-only portion.
2. **React controlled checkboxes:** Playwright `.check()` may fail. Click the label element instead.
3. **File upload testing:** Manual `dispatchEvent` needed when testing accept-attribute filtering.
4. **IntlWrapper:** All component tests must wrap with `IntlWrapper` for react-intl compatibility.
5. **XSS sanitization:** `sanitizeHighlight()` strips all HTML except Solr's `<em>` tags. Always use for `dangerouslySetInnerHTML`.

### Responsive CSS (learned v1.10.0)

1. **Grid:** Use `repeat(auto-fill, minmax(280px, 1fr))` — never fixed column counts.
2. **Overflow prevention:** `min-width: 0` + `overflow: hidden` on grid items. `overflow-wrap: anywhere` on text.
3. **Mobile navigation:** Needs dedicated hamburger toggle + i18n labels.

---

## Release Summary

| Release | Key Frontend Work |
|---------|-------------------|
| v1.4.0 | Dependency upgrades, code formatting, ESLint/Prettier setup |
| v1.5.0 | PDF upload UI (drag-and-drop, progress tracking), Similar Books panel, API URL resolution |
| v1.6.0 | Full i18n (4 locales, 153+ keys), LanguageSwitcher, ESLint 10, contributor guide |
| v1.7.0 | Page-level i18n (260+ keys), localStorage standardization, error boundaries |
| v1.8.0 | UX roadmap (13 issues), Lucide icons, responsive audit, accessibility planning |
| v1.9.x | WCAG 2.1 AA fixes, E2E Playwright fixes, incomplete translation fix |
| v1.10.0 | CSS grid overlap fix, PDF viewer URL normalization, responsive improvements |

---

## Active Work (v1.10.0+)

**Wave 0 (bugs):** CSS overlap fix (#649 ✅), version display (#667 ✅), PDF URL normalization (#647 ✅)
**Wave 1 (CI):** Merge lint-frontend.yml into ci.yml (#692) with Brett
**Wave 2–4 (features):** Metadata modal (#688), batch panel (#691), folder facet tree (#652), collections UI (#661, #664), release pipeline (#687, #694)

**Parker handoff:** Cookie auth refresh (Decision 24 — add "Remember me" checkbox), Collections CRUD (Decision 25 — 9 endpoints ready for UI).

---

## Reskill Notes (2026-03-20)

### Self-Assessment
- **Strongest areas:** i18n architecture, hook patterns, component separation, test coverage, API integration
- **Growing areas:** Accessibility (WCAG 2.1 AA), responsive design, CSS Modules adoption, E2E Playwright
- **Knowledge gaps:** CSS Modules best practices (only 2 files use them), dark/light theme toggle, advanced Playwright patterns, Collections UI (backend API ready, no frontend yet)

### Stale Information Corrected
- React version: was listed as RC, now stable `^19.0.0`
- react-intl: was `6.8.1`, now `^10.0.0`
- Vitest: was `2.1.8`, now `^4.1.0`
- Vite: was `5.x`, now `^8.0.0`
- Prettier: was incorrectly listed as `10.1.8`, actually `^3.8.1`
- Component count: was ~20, now ~30 (added skeletons, auth, folder tree, error states)
- Page count: was 5, now 9 (added Login, Admin, Profile, UserManagement, ChangePassword)
- Hook count: was ~5, now 11 (added admin, library, users, useSearchState)
- CSS Modules emerging alongside global CSS (Footer, LoadingSpinner)
- Lucide React now in deps (replaced emoji icons)
- eslint-plugin-jsx-a11y added for a11y linting
- AuthContext + ProtectedRoute pattern established

### Patterns Extracted to Skills
- `vitest-testing-patterns` — Vitest + RTL testing patterns for aithena
- `accessibility-wcag-react` — WCAG 2.1 AA patterns for React apps
- Updated `react-frontend-patterns` — corrected versions, expanded component/hook inventory

### What Would Help Most
1. Collections UI skill (once frontend is built)
2. CSS Modules migration guide (transitioning from global CSS)
3. Dark/light theme implementation pattern
4. Advanced Playwright E2E patterns for React SPAs

**End of History — Dallas Frontend Developer**

### Folder Batch Integration (#656, 2026-03-21)

**Query-based batch editing:** Added `BatchQueryContext` type to `useBatchMetadataEdit` — when provided, the hook calls `/metadata-by-query` with query+filters instead of `/batch/metadata` with explicit IDs. The `save()` function branches based on `queryContext` presence, keeping backward compatibility.

**"Select all N matching" UX:** When total results exceed visible page size, a "Select all N matching results" button appears. This sets `allMatchingSelected` state, which passes `queryContext` (with current query + active filters including folder) to `BatchEditPanel`. Individual checkbox toggles reset `allMatchingSelected` to prevent mixed-mode confusion.

**i18n pattern:** Used `{count, plural, one {# matching result} other {# matching results}}` for the selectAllMatching key — follows established ICU MessageFormat pattern from existing batch keys.

### Version Display Fix (#810, 2026-07-17)

**Bug:** UI footer showed stale version (e.g. v1.0.0) instead of actual version from VERSION file.

**Root cause:** `getVersion()` in `vite.config.ts` checked `process.env.VERSION` before the VERSION file. A stale env var (from `.env`, Docker cache, or shell) would override the actual VERSION file.

**Fix:** Flipped resolution priority — VERSION file first, env var fallback. Also updated Dockerfile to write the VERSION build arg to a file so the file-based path works inside Docker builds.

**Learnings:**
- The VERSION file at repo root is the single source of truth; always prefer reading it over env vars.
- Docker build context for aithena-ui is `./src/aithena-ui/`, so the repo-root VERSION file is not in context. Must write it from the build arg in the Dockerfile.
- `.env.example` files contain stale VERSION values (0.8.0, 1.4.0) — operators copying these to `.env` get wrong versions. Flagged for infra team to fix.
### PDF Viewer Toolbar Redesign (#814, #815, #816 — PR #836)

**Toolbar pattern:** Replaced the old header/close-button layout with a horizontal toolbar: title on left (truncated), grouped action buttons on right. BEM naming: `.pdf-viewer-toolbar`, `.pdf-viewer-toolbar__title`, `.pdf-viewer-toolbar__actions`, `.pdf-viewer-toolbar__btn`. This pattern is reusable for future panel/modal headers.

**Fullscreen toggle:** Uses `useState(isFullscreen)` + `useCallback(toggleFullscreen)`. ESC key handler checks `isFullscreen` before calling `onClose` — exits fullscreen first, then closes on second ESC. The `isFullscreen` dependency was added to the keydown `useEffect` deps array.

**Toolbar buttons as links:** Download and external-link use `<a>` elements styled as toolbar buttons (`.pdf-viewer-toolbar__btn` class on both `<button>` and `<a>`). Download uses native `download` attribute. External link uses `target="_blank" rel="noopener noreferrer"`.

**Conditional rendering:** Download and external-link buttons only render when `pdfUrl` is truthy — avoids broken links when no document URL exists. Fullscreen and close always render.

**CSS fullscreen mode:** Separate modifier classes (`--fullscreen`) on both overlay and panel. Panel goes `width: 100vw; height: 100vh`, overlay background becomes transparent. No JS DOM manipulation needed — pure CSS class toggling.

### Decouple SimilarBooks from PDF Viewer (#820 — PR #841)

**State separation:** `focusedBookId` controls SimilarBooks panel. `selectedBook` controls PDF viewer. Independent rendering; panel persists after viewer closes.

**BookCard onSelect prop:** Added optional `onSelect?: (book: BookResult) => void`. When provided, `<article>` gets `role="button"`, `tabIndex={0}`, keyboard handlers, `.book-card--selectable` CSS. Children use `stopPropagation`.

**z-index layering:** `.similar-books-panel` at z-index 1001 sits above PDF overlay (z-index 1000).

**a11y:** eslint-disable justified for conditional role. Child stopPropagation wrappers need `role="presentation"` + `onKeyDown`.

### Chunk Text Display (#809, 2026-07-17)

**Feature:** Display vector search chunk text snippets in BookCard with left accent border, subtle blue background.

**Implementation:** Added `is_chunk`, `chunk_text`, `page_start`, `page_end` to `BookResult`. Page range shown when available (singular/plural).

**Key pattern:** Used `book.*` i18n prefix for consistency. Plain text, no sanitization needed (unlike keyword highlights with `<em>` tags).

### BookCard → BookDetailView Navigation (#821 — PR #843)

**Pattern:** Reused existing `onSelect` prop. No component changes needed — already wired with click, keyboard, role, and stopPropagation.

**State:** `detailBookId: string | null` + `detailInitialData: BookResult | undefined` cleanly separate "which book" from "what data we have." Avoids refetch for card clicks.

**Hook pattern:** `useBookDetail` with `initialData` prop — skips API fetch if already provided.

### BookDetailView Modal (#819, PR #842)

**Architecture:** Follows PdfViewer pattern (focus trap, ESC dismiss, body scroll lock, `aria-modal`). Adapted for centered overlay instead of side panel.

**initialData pattern:** When caller already has `BookResult` from search, skips `/v1/books/{id}` fetch entirely.

**Content:** Header (title/author/year), metadata grid, chunk text preview, action buttons, SimilarBooks integration.

**i18n:** Used `bookDetail.*` prefix for modal-specific labels (distinct from `book.*`).

**Type additions:** Added `file_size`, `folder_path`, `score` to `BookResult` interface.

### Inline Metadata Editing in BookDetailView (#822 — PR #844)

**Pattern:** Edit form renders inline within modal, toggled by `editMode` boolean. Avoids stacking two modals.

**Hook reuse:** `useMetadataEdit` reused directly inside `InlineEditForm`. Form fields duplicated locally since originals non-exported.

**useBookDetail refresh:** Added `refresh()` via `refreshCounter` state + `isInitialMount` ref. Increments counter to bypass `initialData` early-return and re-fetch.

**ESC key layering:** When `editMode` true, ESC exits edit mode (not closes modal). Added `editMode` to effect deps.

### BookCard Thumbnails (#827, PR #849)

**Feature:** Thumbnail image display with lazy loading and graceful fallback to FileText icon.

**Architecture:** Added `thumbnail_url?: string | null` to `BookResult`. BookThumbnail/DetailThumbnail components manage image error state internally.

**Layout:** BookCard flex row: thumbnail (80×112px) on left, content on right. BookDetailView shows larger thumbnail (200×280px).

**Lazy loading:** Used `loading="lazy"` on `<img>` tags. Simpler than intersection observer.

---

## Recent Shipments (Session 2026-03-22T14:41Z)

### Collections API Enablement (#897, PR #922)
- Removed 242 lines of hardcoded mock data
- Real API calls now default for all collection operations
- Frontend pulls live collections from backend

### Remember-me Checkbox (#898, PR #923)
- Added checkbox UI to LoginPage
- Updated AuthContext with `rememberMe` parameter
- Implemented sessionStorage/localStorage toggle
- i18n labels: English, Spanish, French, German
- All 600 tests pass

### Text Preview Truncation (#896, PR #924)
- Created `truncateChunkText` utility with smart truncation
- Keeps matched keywords centered and visible
- Proper em-tag handling for highlighting
- 13 new tests added and passing

---

## Skills Status

### Reviewed & Validated

1. **react-frontend-patterns** (SKILL.md)
   - ✅ Comprehensive. Component/hook patterns correct. Covers CSS, routing, API integration, TypeScript patterns.
   - Updated stats: 40+ components, 16 hooks, 14 pages (was 30, 11, 9).
   - Added: CSS Modules emerging, BatchEditPanel, BookDetailView, thumbnail patterns.
   - Added: `initialData` pattern for zero-refetch modal initialization.

2. **vitest-testing-patterns** (SKILL.md)
   - ✅ Comprehensive. IntlWrapper, component/hook testing, mocking patterns, i18n testing.
   - Added: File upload via dispatchEvent (needed for accept attribute testing).
   - Added: Error boundary + MemoryRouter for route-change testing.
   - Verified: All 31 test files follow patterns; 600+ tests passing.

3. **accessibility-wcag-react** (SKILL.md)
   - ✅ Comprehensive. Skip link, focus management, color contrast, media queries, ARIA, static linting.
   - Verified: eslint-plugin-jsx-a11y integrated and catching ~70% of issues.
   - Note: Remaining 30% requires browser audit (color contrast, focus visible, keyboard nav flow, screen reader announcements).
   - Patterns used: BookDetailView modal, PDF viewer toolbar, BookCard roles, SimilarBooks z-index layering.

4. **nginx-reverse-proxy** (SKILL.md)
   - ⚠️ Infrastructure, not frontend-specific. Reviewed for context.
   - Single port publisher pattern, health endpoint, upstream routing map, startup ordering.
   - Relevant to frontend: `/` routes to `aithena-ui:5173` (Vite), `/v1` routes to `solr-search:8080` (backend API).

### Created or Updated

**None new created this session.** All core frontend skills (react-frontend-patterns, vitest-testing-patterns, accessibility-wcag-react) were already in place and validated during reskill consolidation.

---

## Knowledge Gaps & Future Work

### Collections UI (v1.11.0+)
- **Status:** Backend 9 CRUD endpoints ready. Frontend API integration exists (collectionsApi.ts), real API calls enabled (#897). UI components partially in place (CollectionModal, CollectionPicker, CollectionsGrid, CollectionDetailView, CollectionDetailPage).
- **Gaps:** Comprehensive workflow documentation for collections CRUD (create, read, update, delete, add-to-collection, remove-from-collection). Test coverage gaps for collections UI.
- **Action:** Create `collections-ui-patterns` skill once full workflow is tested and stabilized.

### Folder Facet Tree & Query-Based Batch Editing
- **Status:** FolderFacetTree component implemented. Batch editing with query context (via `BatchQueryContext`) wired into `useBatchMetadataEdit` and batch panel.
- **Gaps:** Advanced filtering patterns (nested folder filtering, multi-select folder trees, dynamic folder expansion on API result).
- **Action:** Document advanced facet patterns once folder-based filtering is expanded.

### Dark/Light Theme Toggle
- **Status:** Currently dark theme only (`#282c34` bg, `#7ec8e3` accent). Design tokens exist in `design-tokens.css`.
- **Gaps:** No light theme implementation. No theme toggle UI. No localStorage persistence for theme preference.
- **Action:** Create `theming-react-patterns` skill with light theme color palette and toggle implementation once launched.

### CSS Modules Migration
- **Status:** Only 2 files use CSS Modules (Footer.module.css, LoadingSpinner.module.css). Global CSS still predominant.
- **Gaps:** Best practices for CSS Modules in large codebases. Handling of shared variables/utilities. Migration strategy from global CSS.
- **Action:** Document CSS Modules migration approach once rollout is planned.

### Advanced Playwright E2E Patterns
- **Status:** Basic E2E tests exist (e2e/ directory). Learnings from emoji, checkbox, file upload testing documented in vitest-testing-patterns.
- **Gaps:** Advanced patterns (visual regression, performance testing, accessibility testing in headless browsers, multi-tab workflows).
- **Action:** Create `playwright-advanced-patterns` skill once e2e suite is expanded significantly.

### v2.0 React Migration Readiness
- **Status:** Frontend already React 19. Streamlit admin dashboard still exists (separate service, not replaced by React frontend).
- **Gaps:** No consolidation of admin UI from Streamlit into React frontend. Unclear scope/timeline for v2.0.
- **Action:** Track v2.0 plan in squad decisions. Update history when consolidation begins.

---

## Self-Assessment Summary

### Strengths (Demonstrated)
- **i18n mastery:** 300+ keys across 4 locales. ICU MessageFormat patterns. localStorage migration.
- **Hook architecture:** Data-fetching patterns with cancellation, polling, state management, search state reset.
- **Component design:** Presentational components, prop interfaces, CSS class patterns, keyboard accessibility.
- **Test coverage:** 600+ tests. IntlWrapper, mocking, hook testing, i18n verification.
- **Modal/overlay patterns:** PDF viewer, BookDetailView, Collections modals. Focus management, ESC key, z-index layering.
- **API integration:** Zero-refetch `initialData` patterns, query-based batch editing, error handling.

### Growing Areas
- **Advanced CSS Modules:** Only 2 files use them. Need experience with larger-scale scoped CSS.
- **Theme switching:** Currently dark-only. Ready to learn light theme + toggle implementation.
- **E2E testing:** Basic patterns known. Advanced visual/perf/a11y E2E patterns need development.
- **Collections UI at scale:** API ready, basic UI in place. Full workflow documentation and test coverage expansion needed.

### Confidence Level
- **High:** React/TypeScript patterns, i18n, hook design, component architecture, accessibility, testing, API integration.
- **Medium:** CSS Modules scaling, advanced E2E, collections feature complete workflow.
- **Learning:** Theme implementation, advanced responsive patterns, performance optimization at scale.


## Work Item: Search UI Bug Fixes (#1221-#1224) - 2026-03-26

### Context
Four search result display regressions identified during v1.16.0 pre-release:
- #1221: Thumbnails missing in semantic search results
- #1222: Page numbers missing in keyword search results
- #1223: Snippet text truncated to 20 chars (far too short)
- #1224: Inconsistent styling between chunk text and keyword highlights

### Changes (PR #1225)
1. **Thumbnail derivation** (search.ts): Derive from file_path using /thumbnails/{path}.thumb.jpg convention.
2. **Chunk page enrichment** (search_service.py, main.py): Secondary Solr query for page ranges. Best-effort.
3. **Snippet length** (truncateChunkText.ts): Default 20->250 chars. Applied to keyword highlights too.
4. **Unified rendering** (BookCard.tsx, App.css): Merged chunk/highlight sections under .book-highlights.

### Learnings
- Keyword search EXCLUDE_CHUNKS_FQ returns parent docs (no page info). Semantic returns chunks (no thumbnail). Both need enrichment.
- Backend collaboration: traced bug to query structure, added backend functions for root cause fix.
- truncateChunkText handles <em> tags: strips HTML when measuring, centers around first match.

---

## End of History — Dallas Frontend Developer (Reskill #2, 2026-03-22)