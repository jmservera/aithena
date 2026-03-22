# Dallas — Frontend Developer History

**Last Updated:** 2026-03-20 (post-reskill consolidation)  
**Status:** Shipped v1.4.0 → v1.7.0; v1.8.0–v1.10.0 in progress

---

## Core Context

**Project:** Aithena — Book library search engine with semantic + keyword search  
**Role:** Dallas, Frontend Developer (React/TypeScript specialist)  
**Team:** Squad (Ripley, Parker, Brett, Newt, Kane + others)  
**Releases Shipped:** v1.4.0 (Deps), v1.5.0 (Production), v1.6.0 (i18n), v1.7.0 (Quality), v1.8.0+ (UX)

### Frontend Codebase State (current)
- **Framework:** React 19 + TypeScript strict mode
- **Build:** Vite 8.x with TypeScript compilation
- **Linting/Formatting:** ESLint 10 (flat config) + Prettier 3.8 + eslint-plugin-jsx-a11y
- **Testing:** Vitest 4.1 + React Testing Library + jsdom + @vitest/coverage-v8
- **Routing:** React Router 7.13.1 (9 pages: Search, Library, Upload, Status, Stats, Login, Admin, Profile, UserManagement, ChangePassword)
- **Internationalization:** react-intl 10.0 with 4 locales (en, es, ca, fr), ~260 keys
- **Icons:** Lucide React (tree-shakeable, accessible SVG icons)
- **Styling:** Global CSS (BEM) + emerging CSS Modules (Footer, LoadingSpinner), dark theme #282c34
- **Auth:** Cookie-based auth with AuthContext, ProtectedRoute, AdminRoute
- **Components:** ~30 presentational components + error boundaries + skeletons
- **Tests:** 31 UI test files + backend tests across all services


### File Organization (current)
```
src/aithena-ui/src/
├── App.tsx, App.css, main.tsx, api.ts
├── Components/     (~30: BookCard, FacetPanel, PdfViewer, ErrorBoundary, SimilarBooks,
│                    LanguageSwitcher, FolderFacetTree, SkeletonCard, SkeletonFacetPanel,
│                    EmptyState, ErrorState, LoadingSpinner, Footer, AdminRoute, ProtectedRoute,
│                    FilterChip, ActiveFilters, Pagination, TabNav, CollectionStats, IndexingStatus, List)
├── hooks/          (11: search, status, stats, library, upload, admin, users, similarBooks,
│                    useSearchState, chat, input)
├── pages/          (9: Search, Library, Upload, Status, Stats, Login, Admin, Profile,
│                    UserManagement, ChangePassword)
├── contexts/       (AuthContext, I18nContext)
├── locales/        (en.json, es.json, ca.json, fr.json — ~260 keys each)
└── __tests__/      (31 test files)
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

**State separation pattern:** Introduced `focusedBookId` state alongside `selectedBook` in SearchPage and LibraryPage. `selectedBook` controls the PDF viewer; `focusedBookId` controls the SimilarBooks panel. This allows similar books to render independently of the PDF viewer state and persist after closing the viewer.

**BookCard onSelect prop:** Added `onSelect?: (book: BookResult) => void` to BookCard. When provided, the `<article>` element gets `role="button"`, `tabIndex={0}`, keyboard handlers (Enter/Space), and a `.book-card--selectable` CSS class with cursor/hover states. Interactive children (checkbox, menu, Open PDF button) use `stopPropagation` to prevent double-triggering.

**z-index layering:** `.similar-books-panel` gets `position: relative; z-index: 1001` to sit above the PDF viewer overlay (`z-index: 1000`). This ensures the panel is never obscured by the dark overlay when both are visible.

**a11y lint with conditional roles:** ESLint's `jsx-a11y/no-noninteractive-element-interactions` fires on `<article>` with event handlers. Since we conditionally apply `role="button"`, an inline `eslint-disable` comment is appropriate. The `stopPropagation` wrapper divs need `role="presentation"` + `onKeyDown` handler to satisfy `jsx-a11y/click-events-have-key-events` and `jsx-a11y/no-static-element-interactions`.

**Testing decoupled components:** When a parent element has `role="button"` and contains child buttons, `getByRole('button', { name: ... })` may match multiple elements. Use `getByLabelText` for specific child buttons instead.

### Chunk Text Display (#809, 2026-07-17)

**Feature:** Display vector search chunk text snippets in BookCard.

**Implementation:** Added `is_chunk`, `chunk_text`, `page_start`, `page_end` to `BookResult` type. When `is_chunk=true` and `chunk_text` is present, a visually distinct panel renders above keyword highlights with a left accent border and subtle blue background (`.book-chunk-text` CSS class). Page range shown when available (singular/plural).

**Learnings:**
- Used `book.*` i18n key prefix to stay consistent with existing BookCard keys rather than introducing a new `bookCard.*` domain prefix.
- Chunk text is plain text (no HTML sanitization needed) — unlike keyword highlights which come with `<em>` tags from Solr.
- Added `book.chunkPage` (singular) and `book.chunkPages` (plural) for page display — follows existing `book.foundOnPage`/`book.foundOnPages` pattern.
- 8 tests cover all edge cases: presence/absence of chunk, single vs. multi page, empty string, missing page range, coexistence with keyword highlights.

### BookCard → BookDetailView Navigation (#821 — PR #843)

**Pattern:** Repurposed the existing `onSelect` prop on BookCard (from #820's SimilarBooks decoupling) to open BookDetailView instead of just setting `focusedBookId`. No changes to BookCard.tsx were needed — all click, keyboard (Enter/Space), role="button", tabIndex, and stopPropagation on Open PDF were already wired from #820.

**State pattern:** Two state variables — `detailBookId: string | null` and `detailInitialData: BookResult | undefined` — cleanly separate "which book to show" from "what data we already have." Passing full BookResult as `initialData` to `useBookDetail` avoids a refetch for card clicks. For similar book navigation within the detail view, `getCachedSimilarBook()` provides cached data when available.

**Learnings:**
- When `onSelect` infrastructure already exists on a component, wiring a new feature is a page-level state change only — no component modifications needed.
- Two-variable state (`detailBookId` + `detailInitialData`) is cleaner than a single `BookResult | null` when the hook (`useBookDetail`) needs to distinguish "has initial data, skip fetch" vs. "no initial data, fetch by ID."
- BookDetailView embeds SimilarBooks, so the standalone SimilarBooks panel (from #820) and the detail view coexist — `focusedBookId` drives the standalone panel, `detailBookId` drives the modal.
- Shared environment risk: another session switched branches mid-work. Always verify `git branch --show-current` after any pause.
### Inline Metadata Editing in BookDetailView (#822 — PR #844)

**Inline edit pattern:** Instead of opening a separate MetadataEditModal on top of BookDetailView, the edit form renders inline within the modal body. An `editMode` boolean state toggles between read-only metadata display and the editable form. This avoids stacking two modals and provides a smoother UX.

**Hook reuse:** The `useMetadataEdit` hook (from v1.10.0) is reused directly inside `InlineEditForm` — no changes needed. Form fields (TextInput, YearInput, ComboboxField) are duplicated locally since the originals are non-exported internal components of `MetadataEditModal.tsx`. If a third usage appears, extract to shared `Components/fields/`.

**useBookDetail refresh pattern:** Added `refresh()` to `useBookDetail` using a `refreshCounter` state + `isInitialMount` ref. When `refresh()` is called, the counter increments and the effect re-runs, bypassing the `initialData` early-return. This pattern avoids exposing `setBook` and keeps the hook's API clean.

**ESC key layering:** When `editMode` is true, pressing ESC exits edit mode instead of closing the modal. The keydown handler checks `editMode` first. This required adding `editMode` to the effect's dependency array alongside `onClose`.

**Timer cleanup in InlineEditForm:** The 600ms toast delay (`setTimeout → onSaved`) can leak between tests (or after unmount). Added `mountedRef` guard to prevent `onSaved` from firing after the component unmounts.

**Learnings:**
- Reusing `meta-edit-*` CSS classes from `MetadataEditModal.css` inside BookDetailView works because the CSS is globally scoped. No duplicate import needed.
- The `as keyof MetadataFormValues` cast on `setField` calls is needed because the `onChange` callback type is `(value: string) => void` but `setField` expects the field name as a typed key.
- When BookDetailView's parent branch (squad/819) is already merged to dev, branch from dev directly — don't branch from the feature branch.
- 12 new tests cover: edit mode entry, field population, Save/Cancel toggle, ESC layering, Save disabled state, API error display, auth gating, and action button persistence in edit mode.

### BookDetailView Modal (#819, PR #842)

**Feature:** Modal overlay component showing full book metadata, similar books, and action buttons.

**Architecture:** Followed the established PdfViewer modal pattern — focus trap, ESC dismiss, body scroll lock, `aria-modal` — but adapted for a centered overlay (vs PdfViewer's side panel). Created `useBookDetail` hook with `initialData` prop pattern: when the caller already has `BookResult` from search results, it skips the API fetch entirely, avoiding a redundant `GET /v1/books/{book_id}` call.

**Content sections:** Header (title/author/year), metadata grid (category, language, series, page count, file size, folder path), chunk text preview (reuses existing `book.matchingText`/`book.chunkPage`/`book.chunkPages` i18n keys), action buttons (Open PDF, Open external, Edit metadata for admins), and SimilarBooks component integration.

**Learnings:**
- Used `bookDetail.*` i18n key prefix for modal-specific labels (close, loading, error, fileSize, folderPath, openExternal, untitled) — keeps them distinct from `book.*` keys used by BookCard.
- Added `file_size`, `folder_path`, `score` to `BookResult` interface — these fields exist in the backend `normalize_book()` response but were missing from the frontend type.
- Admin gating uses `useAuth().user?.role === 'admin'` — straightforward role check via AuthContext.
- Title appears in both toolbar and body header — test queries must use `getAllByText` or role-based selectors to avoid ambiguity.
- `SimilarBooks` heading text ("Similar Books") overlaps with loading text ("Loading similar books…") for `/similar books/i` regex — use `getByRole('region', { name: /similar books/i })` for the section.
- Backdrop click handler on `role="dialog"` triggers `jsx-a11y/click-events-have-key-events` — suppressed with eslint-disable since ESC is the keyboard equivalent.
- CSS: centered modal with `max-width: 800px`, responsive at 600px breakpoint (full-width, stacked layout). BEM naming `.book-detail-*`.


### BookCard Thumbnails (#827, PR #849)

**Feature:** Thumbnail image display in BookCard and BookDetailView with lazy loading and graceful fallback.

**Architecture:** Added `thumbnail_url?: string | null` to `BookResult` type. Created small `BookThumbnail` and `DetailThumbnail` components that manage image error state internally — on load error they swap to a FileText placeholder icon. Used `loading="lazy"` on `<img>` tags for performance.

**Layout:** BookCard body is now a flex row: thumbnail (80×112px) on the left, content on the right. Wrapped existing card content in `book-card-body > book-card-thumbnail + book-card-content` divs. BookDetailView header similarly shows a larger thumbnail (200×280px) beside the title/author info.

**Learnings:**
- When wrapping existing JSX in new container divs, carefully count opening/closing tags — prettier will catch syntax errors but the nesting must be correct.
- Placeholder thumbnails use `aria-hidden="true"` since they're decorative; actual images use book title as alt text.
- The `onError` handler on `<img>` is the cleanest way to handle broken image URLs — simpler than intersection observer approaches.
- BEM naming: `book-card-body`, `book-card-thumbnail`, `book-card-thumbnail--placeholder`, `book-card-content`, `book-detail-header__thumbnail`, `book-detail-header__thumbnail--placeholder`, `book-detail-header__info`.
- `fireEvent.error(img)` in tests simulates image load failure for fallback testing.
- 7 new tests added; all 581 tests pass.
