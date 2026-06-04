# Dallas — History

## Core Context

Dallas owns the React/TypeScript UI: search, library, upload, status/stats, auth/admin, collections, backup, PDF viewing, metadata editing, responsive UX, and a11y.

Stable stack:
- React 19 + TypeScript strict mode, Vite 8 ESM, React Router 7, react-intl 10.
- ESLint 10 flat config with jsx-a11y; Prettier 3; Vitest 4 + React Testing Library; basic Playwright E2E.
- Global CSS+BEM is primary; CSS Modules are emerging (Footer, LoadingSpinner). Dark theme: `#282c34` bg, `#7ec8e3` accent; tokens exist but no light toggle yet.
- Cookie auth uses `aithena_auth` HttpOnly/SameSite=lax, `AuthContext`, `ProtectedRoute`/`AdminRoute`, and `credentials: 'include'` on API calls.

Current layout:
```text
src/aithena-ui/src/
├── App.tsx, api.ts, main.tsx
├── Components/   BookCard, BookDetailView, PdfViewer, SimilarBooks, BatchEditPanel,
│                  MetadataEditModal, Collection*, FolderFacetTree, AdminRoute, etc.
├── hooks/        search, bookDetail, collections, useBatchMetadataEdit, admin, users
├── pages/        Search, Library, Upload, Status, Stats, Login, Admin, Profile,
│                  UserManagement, ChangePassword, Collections, CollectionDetail, BackupDashboard
├── contexts/     AuthContext, I18nContext
├── locales/      en/es/ca/fr JSON (~300+ keys)
└── __tests__/    600+ tests
```

Skills validated: `react-frontend-patterns`, `vitest-testing-patterns`, `accessibility-wcag-react`. Nginx context: `/` routes to Vite; `/v1` and `/documents` route to backend/proxied content.

## Key Patterns

- **Architecture:** Pages compose presentational components and hooks. Hooks own state/effects/API orchestration. `api.ts` is the only HTTP layer.
- **Data hooks:** Use `AbortController` plus a `cancelled` flag; treat `AbortError` as non-error. Poll with chained `setTimeout`, not `setInterval`.
- **Search state:** Reset pagination to page 1 whenever query/filters change. Use immutable updates and keep visible-page selection separate from query-wide selection.
- **API URLs:** `buildApiUrl()` centralizes `VITE_API_URL` handling (`.`, unset, or full URL). `resolveDocumentUrl()` strips internal Docker hosts and normalizes same-origin document paths to `/documents/`.
- **Vite:** ESM config needs `dirname(fileURLToPath(import.meta.url))`; dev proxy maps `/v1` and `/documents` to `localhost:8080`.
- **i18n:** Keys use `domain.featureKey`. Option arrays store `labelId`, resolved with `useIntl()`. Convert helpers to components when hooks are needed. `aithena.locale` is canonical localStorage.
- **Testing:** Use `IntlWrapper`. Avoid exact emoji matches; click labels for controlled checkboxes; dispatch `change` for upload accept filtering. Locale tests check key presence, not translated-value uniqueness.
- **Security:** Use `sanitizeHighlight()` before `dangerouslySetInnerHTML`; it strips all HTML except Solr `<em>` tags. Plain chunk text does not need HTML sanitization.
- **Accessibility:** Use skip link, route focus, `aria-modal`, table `scope`, health-dot `role="img"`, reduced-motion/contrast media, and rgba >=0.65 for AA. Browser audits still cover keyboard/focus/screen-reader gaps.
- **Responsive CSS:** Prefer `repeat(auto-fill, minmax(280px, 1fr))`; add `min-width: 0`, `overflow: hidden`, and `overflow-wrap: anywhere`. Mobile navigation needs a dedicated hamburger with i18n labels.
- **Modals/overlays:** PdfViewer and BookDetailView use focus trap, ESC dismiss, body scroll lock, `aria-modal`, and z-index discipline. If nested edit mode is active, ESC exits edit mode before closing the parent modal.
- **BookCard interactions:** Optional `onSelect` adds role/button semantics, `tabIndex`, keyboard handlers, `.book-card--selectable`, and child `stopPropagation` wrappers.
- **Zero-refetch detail:** Pass `initialData` to `useBookDetail`/BookDetailView when search already has a `BookResult`; add explicit `refresh()` to bypass the initial-data early return after edits.
- **Batch editing:** `BatchQueryContext` lets `useBatchMetadataEdit` call `/metadata-by-query` with query+filters for “select all N matching”; individual checkbox changes reset all-matching mode.
- **Toolbar pattern:** PDF toolbar uses left truncated title + grouped actions. Style `<button>` and `<a>` as `.pdf-viewer-toolbar__btn`; external links use `noopener`, download uses native `download`, hide missing-URL actions.

## Learnings

- **2026-03-20 reskill:** Versions corrected to React 19, react-intl 10, Vite 8, Vitest 4, Prettier 3.8. Inventory: 40+ components, 16 hooks, 14 pages. Lucide, AuthContext routes, CSS Modules, jsx-a11y established.
- **2026-03-21 folder batch (#656):** Query-based batch save branches on `queryContext` presence while keeping explicit-ID mode. ICU plural syntax (`{count, plural,...}`) fits “select all matching” labels.
- **2026-03-22 collections/remember/text preview:** Collections now use real backend API calls instead of mocks. Remember-me toggles sessionStorage/localStorage through `AuthContext`. `truncateChunkText` keeps matched terms centered and handles `<em>` tags while measuring plain text.
- **2026-03-25 admin pagination (#1138):** React admin tabs use the shared `Pagination` component and per-tab page state; Streamlit admin used a small `paginate()` helper. No API change was needed for current scale; Streamlit admin remains deprecated for v2.0.
- **2026-03-26 search UI fixes (#1221-#1225):** Semantic search returns chunks needing thumbnail derivation; keyword search returns parent docs needing page enrichment. Unified chunk/highlight rendering under `.book-highlights`; default snippet length is 250 chars.
- **2026-03-26 PR #1225 reviews:** Gate thumbnail derivation on `is_chunk`; parent docs get backend thumbnails. Chunk-page enrichment adds one mock call; verify `parent_id_s` filter. Avoid escaped digit regex mistakes; use `/Page \d+/`. Run ESLint and Prettier separately.
- **2026-05-31 dependabot sweep:** Batch dependency updates by cherry-picking and regenerating the lockfile. React/DOM, Vite, Vitest, ESLint, and TypeScript chain merged without breaking changes.
- **2026-07-09 Solr escape:** Apply `solr_escape()` to parent IDs in `build_chunk_page_params` to avoid Lucene query injection. `FACET_FIELDS` keys are logical names (`language`), not Solr fields (`language_s`), for `build_filter_queries`. PR comment replies use `in_reply_to` on `pulls/{pr}/comments`.
- **2026-07-09 similar books:** Chunk result IDs are not parent book IDs. Add/use `parent_id` on `BookResult` and prefer `book.parent_id || book.id` for SimilarBooks and PDF focus paths.
- **2026-07-17 version display (#810):** VERSION file is the single source of truth. `vite.config.ts` should prefer the file over env vars; Docker UI builds must write the VERSION build arg into a file because repo-root VERSION is outside `src/aithena-ui` build context.
- **2026-07-17 chunk display (#809):** Add `is_chunk`, `chunk_text`, `page_start`, and `page_end` to `BookResult`; show page range singular/plural via `book.*` i18n. Chunk text is plain text with a subtle accent style.
- **2026-07 PDF/detail work (#814-#827):** Fullscreen is pure CSS via `--fullscreen` classes; ESC exits fullscreen before closing. SimilarBooks state (`focusedBookId`) is independent from PDF/detail selection. BookDetailView uses `bookDetail.*` i18n, inline edit mode, metadata refresh, and larger thumbnails; BookCard thumbnails use `loading="lazy"` with fallback icons.
- **2026-07 X-Frame fix (#1234):** Iframe-served PDFs need SAMEORIGIN even on nginx named `@auth_error` locations; named locations inherit server-level headers. Use `proxy_hide_header X-Frame-Options` plus `add_header` to avoid duplicate conflicts, and normalize same-origin document URLs to `/documents/`.

Open growth: collections tests/skill, advanced folder facets, CSS Modules migration, light theme toggle, advanced Playwright visual/perf/a11y, and React consolidation for deprecated Streamlit admin.
