# Dallas — History

## Core Context

Dallas owns the React/TypeScript UI: search, detail/PDF flows, auth/admin routes, collections, upload/status/stats, metadata editing, responsiveness, and accessibility.

**Stable stack:** React + TypeScript strict mode, Vite ESM, React Router, react-intl, ESLint/Prettier, Vitest + Testing Library, and targeted Playwright coverage.

**UI architecture:** pages compose presentational components and hooks; hooks own async state/effects; `api.ts` is the single HTTP layer.

## Key Patterns

- **Hooks must be cancellation-safe.** Use `AbortController`, cancellation flags, and chained `setTimeout` polling rather than `setInterval`.
- **Search state changes reset pagination.** Keep visible-page selection separate from query-wide selection.
- **API/document URL handling is centralized.** `buildApiUrl()` and `resolveDocumentUrl()` should absorb same-origin, proxy, and Docker-host normalization issues.
- **i18n keys are structured contracts.** Prefer stable `domain.key` IDs, `labelId`-based option arrays, and localized components instead of raw strings.
- **Sanitize Solr highlights before HTML render.** Only safe `<em>` tags survive; plain chunk text stays plain text.
- **Accessibility is part of the component contract.** Focus management, skip links, `aria-modal`, table semantics, reduced-motion/contrast support, and keyboard behavior must ship with the feature.
- **Responsive layout defaults matter.** `repeat(auto-fill, minmax(...))`, `min-width: 0`, overflow containment, and mobile nav affordances prevent most UI breakage.
- **Modals need disciplined layering.** PDF/detail views use focus trap, ESC handling, body scroll lock, and nested-mode escape rules.
- **Selectable cards need explicit semantics.** If `onSelect` exists, add keyboard handlers, focusability, and stop-propagation wrappers for child controls.
- **Avoid unnecessary refetches, but keep a real refresh path.** `initialData` is fine for fast detail views only if edits can still force a server refresh.
- **Batch editing is query-aware.** “Select all matching” must preserve query/filter context and reset correctly on manual selection changes.
- **Version display follows the repo VERSION file.** Do not let UI-only env vars drift from the product version source of truth.
- **Iframe PDF rendering needs explicit SAMEORIGIN behavior.** Header inheritance and proxy/named-location interactions can break embedded PDFs.

## Testing Notes

- Use `IntlWrapper` and semantic selectors instead of brittle raw-text assertions.
- Test UI contracts such as page ranges, highlights, collection badges, and focus behavior rather than internal backend-only fields.
- Chunk-aware UI features should prefer `book.parent_id || book.id` when parent normalization matters.

## Skill References

- `.squad/skills/react-frontend-patterns/SKILL.md`
- `.squad/skills/vitest-testing-patterns/SKILL.md`
- `.squad/skills/accessibility-wcag-react/SKILL.md`
