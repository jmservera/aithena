# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type aware lint rules:

- Configure the top-level `parserOptions` property like this:

```js
   parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: ['./tsconfig.json', './tsconfig.node.json'],
    tsconfigRootDir: __dirname,
   },
```

- Replace `plugin:@typescript-eslint/recommended` to `plugin:@typescript-eslint/recommended-type-checked` or `plugin:@typescript-eslint/strict-type-checked`
- Optionally add `plugin:@typescript-eslint/stylistic-type-checked`
- Install [eslint-plugin-react](https://github.com/jsx-eslint/eslint-plugin-react) and add `plugin:react/recommended` & `plugin:react/jsx-runtime` to the `extends` list

## Performance

### Route-based code splitting

Top-level pages are lazy-loaded in `src/App.tsx`, and each route is wrapped with `Suspense` plus a route-scoped error boundary:

```tsx
const SearchPage = lazy(() => import('./pages/SearchPage'));

function renderLazyRoute(element: ReactNode, title: string, message: string) {
  return (
    <RouteErrorBoundary>
      <Suspense fallback={<LoadingSpinner title={title} message={message} />}>{element}</Suspense>
    </RouteErrorBoundary>
  );
}
```

- Keep route components lazy by default; avoid pulling admin/upload/stats code into the initial path.
- Current `npm run build` output shows separate chunks for each route (`SearchPage` 16.92 kB / 5.26 kB gzip, `UploadPage` 6.47 kB / 2.23 kB gzip, `AdminPage` 7.06 kB / 1.80 kB gzip), while the entry bundle stays at `index` 141.66 kB / 46.24 kB gzip.
- Prefer splitting by page or large optional workflows. Do not lazy-load tiny shared components used on every screen.

### Memoization guidelines

We use `memo(...)` (`React.memo`) for UI that renders often and receives stable props: `BookCard`, `FilterChip`, `FacetPanel`, `Pagination`, and `ActiveFilters`.

```tsx
const BookCard = memo(function BookCard({ book, onOpenPdf, isSelected = false }: BookCardProps) {
  const foundPagesLabel = useMemo(
    () => (book.pages ? formatFoundPages(book.pages[0], book.pages[1]) : null),
    [book.pages]
  );
  const highlightMarkup = useMemo(
    () =>
      book.highlights?.map((snippet, index) => ({
        id: `${book.id}-highlight-${index}`,
        html: `…${sanitizeHighlight(snippet)}…`,
      })) ?? [],
    [book.highlights, book.id]
  );
  const handleOpenPdf = useCallback(() => {
    onOpenPdf?.(book);
  }, [book, onOpenPdf]);
```

Use memoization when:

- A component is expensive enough to notice during search result updates, filter changes, or pagination.
- Props can stay referentially stable between renders.
- You are protecting a list item or repeated chrome from parent rerenders.

Avoid memoization when:

- The component is cheap to render.
- Props are recreated every render anyway.
- `memo`, `useMemo`, or `useCallback` would only add noise without reducing rerenders.

Project patterns:

- `useMemo`: cache derived values with real work or identity value (`BookCard` highlight markup, `ActiveFilters` entries, `Pagination` page list, `AuthContext` provider value).
- `useCallback`: keep handler references stable when they are passed to memoized children or reused in effect dependencies (`useSearch` setters, `SearchPage` open/select handlers, `AuthContext` auth actions).
- Stabilize the parent data flow first. Do not wrap every function “just in case”.

### Error boundary architecture

- `src/main.tsx` wraps `<App />` in `RouteErrorBoundary` so uncaught route-level crashes show recovery UI instead of a blank screen.
- `RouteErrorBoundary` keys itself from the current location, so navigation resets the error state automatically.
- `SearchPage` and `UploadPage` add narrower `ErrorBoundary` wrappers around the results/upload panels so users can retry one section without losing the whole app.

Keep boundaries close to risky UI (lazy routes, async-heavy panels, upload/search result areas) and provide both `reset` and `reload` actions in the fallback.

### Profiling with React DevTools

1. Install the React DevTools browser extension.
2. Open the **Profiler** tab and record a real flow: search, toggle facets, paginate, open a PDF.
3. Check whether `BookCard`, `Pagination`, `ActiveFilters`, and `FacetPanel` rerender when their props did not change.
4. If a memoized component still rerenders, look for unstable arrays, objects, or callbacks before adding more memoization.
5. Re-run `npm run build` after performance work to confirm chunk sizes still make sense.
