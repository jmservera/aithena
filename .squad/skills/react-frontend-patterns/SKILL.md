---
name: "react-frontend-patterns"
description: "React/TypeScript component and hook patterns for the aithena UI"
domain: "frontend, react, typescript"
confidence: "high"
source: "earned — verified from aithena-ui codebase (2026-03-15 reskill)"
author: "Dallas"
created: "2026-03-15"
last_validated: "2026-03-15"
---

## Overview

Aithena UI uses React 18 + TypeScript + Vite with a consistent pattern library: custom hooks manage state/data-fetching, presentational components consume hook results, and global CSS styles all interactions.

## Component Patterns

### Presentational Components (TSX)

Components are **primarily presentational** — state management and API calls live in hooks, not components.

**Template:**
```typescript
interface ComponentProps {
  data: TypeFromHook;
  onAction?: (payload: Type) => void;
  isSelected?: boolean;
}

function Component({ data, onAction, isSelected = false }: ComponentProps) {
  return (
    <div className={`component${isSelected ? ' component--active' : ''}`}>
      {/* JSX content */}
    </div>
  );
}

export default Component;
```

**Conventions:**
- Props interface at top: explicit, typed, includes optional handlers.
- CSS classes use BEM-like naming: `.component-name`, `.component-name--variant`, `.component-name__section`.
- Event handlers start with `on` (e.g., `onOpenPdf`, `onRemoveFilter`).
- Default props via destructuring (`isSelected = false`).

### Sanitization Pattern

When displaying user-generated or Solr-returned HTML (e.g., search highlights):

```typescript
function sanitizeHighlight(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/&lt;em&gt;/g, '<em>')
    .replace(/&lt;\/em&gt;/g, '</em>');
}

// In JSX:
<p dangerouslySetInnerHTML={{ __html: sanitizeHighlight(snippet) }} />
```

**Why:** Solr wraps matches in `<em>…</em>`; we strip all other HTML to prevent XSS.

## Hook Patterns

### Data-Fetching Hooks

Hooks manage state, API calls, and side-life cycles. Return a single object with all needed data/actions.

**Template:**
```typescript
export interface HookResult {
  data: DataType;
  loading: boolean;
  error: string | null;
  setField: (value: Type) => void;
}

export function useHookName(): HookResult {
  const [data, setData] = useState<DataType>(initialState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setField = useCallback((value: Type) => {
    setData(prev => ({ ...prev, field: value }));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Failed: ${response.status}`);
        const result = await response.json();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetch();
    return () => { cancelled = true; };
  }, [dependencies]);

  return { data, loading, error, setField };
}
```

**Key practices:**
- Use `cancelled` flag to prevent state updates after unmount.
- Always include `try/catch` with proper error messages.
- Reset `loading` in `finally` block.
- Return object; spread in components (`const { data, loading, error } = useHook()`).

### Polling Hooks

For continuous updates (e.g., indexing status):

```typescript
const REFRESH_INTERVAL_MS = 10_000;

export function useStatus(): StatusState {
  // ... state vars

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    async function fetchStatus() {
      controller = new AbortController();
      try {
        const response = await fetch(url, { signal: controller.signal });
        // ... handle response
      } catch (err) {
        if (!cancelled && !(err instanceof DOMException && err.name === 'AbortError')) {
          setError(err instanceof Error ? err.message : 'Error');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          timeoutId = setTimeout(fetchStatus, REFRESH_INTERVAL_MS);
        }
      }
    }

    fetchStatus();
    return () => {
      cancelled = true;
      controller?.abort();
      clearTimeout(timeoutId);
    };
  }, []);

  return { data, loading, error, lastUpdated };
}
```

**Key additions:**
- `AbortController` to cancel in-flight requests cleanly.
- `timeoutId` tracking to clear interval on unmount.
- Check for `AbortError` explicitly (don't treat cancellation as an error).

### State Management Hooks (Search)

For complex state with multiple fields and filters:

```typescript
export interface SearchState {
  query: string;
  filters: { author?: string; category?: string };
  page: number;
  limit: number;
  sort: string;
}

export function useSearch() {
  const [searchState, setSearchState] = useState<SearchState>(defaultState);

  const setQuery = useCallback((query: string) => {
    setSearchState(prev => ({ ...prev, query, page: 1 }));
  }, []);

  const setFilter = useCallback((key: keyof SearchFilters, value: string | undefined) => {
    setSearchState(prev => ({
      ...prev,
      page: 1,
      filters: { ...prev.filters, [key]: value },
    }));
  }, []);

  useEffect(() => {
    runSearch(searchState);
  }, [searchState, runSearch]);

  return { searchState, results, facets, total, loading, error, setQuery, setFilter };
}
```

**Conventions:**
- Immutable state updates (`{ ...prev }`).
- Reset pagination to page 1 when query/filters change.
- Auto-run search in separate `useEffect` watching searchState.

## Styling

### CSS Organization

- Single global stylesheet: `App.css` + `normal.css` (normalize).
- No CSS-in-JS or scoped styles.
- BEM-like naming: `.component-name`, `.component-name--variant`, `.component-name__subsection`.

**Example:**
```css
.book-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.book-card--active {
  background-color: rgba(126, 200, 227, 0.1);
  border-color: #7ec8e3;
}

.book-card__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.book-card__meta-item {
  font-size: 0.9em;
  color: rgba(255, 255, 255, 0.7);
}
```

### Color Scheme

- **Background:** `#282c34` (main), `#202123` (header/secondary)
- **Text:** `white` (primary), `rgba(255, 255, 255, 0.7)` (secondary), `rgba(255, 255, 255, 0.5)` (tertiary)
- **Accent:** `#7ec8e3` (blue, for active states/highlights)
- **Borders:** `rgba(255, 255, 255, 0.1)` (subtle dividers)

### Responsive Design

- Flexbox throughout.
- Mobile-first approach not heavily emphasized (project focuses on desktop/library use).
- Use `flex-wrap`, `gap`, and `min-width: 0` for flex children to prevent overflow.

## File Organization

```
aithena-ui/src/
├── App.tsx
├── App.css
├── main.tsx
├── api.ts
├── Components/
│   ├── BookCard.tsx
│   ├── FacetPanel.tsx
│   ├── ActiveFilters.tsx
│   ├── Pagination.tsx
│   ├── PdfViewer.tsx
│   ├── TabNav.tsx
│   ├── IndexingStatus.tsx
│   ├── CollectionStats.tsx
│   └── types/
├── hooks/
│   ├── search.ts
│   ├── status.ts
│   ├── stats.ts
│   └── chat.ts, input.ts (legacy)
└── pages/
    ├── SearchPage.tsx
    ├── LibraryPage.tsx
    ├── StatusPage.tsx
    └── StatsPage.tsx
```

## Routing

Uses `react-router-dom` v7.13.1:

```typescript
<BrowserRouter>
  <Routes>
    <Route path="/" element={<Navigate to="/search" />} />
    <Route path="/search" element={<SearchPage />} />
    <Route path="/status" element={<StatusPage />} />
  </Routes>
</BrowserRouter>
```

**Conventions:**
- Tab navigation lives in app header (component: `TabNav`).
- Active tab indicator via CSS class.
- Route components are pages in `src/pages/`.

## API Integration

### URL Builders (`api.ts`)

```typescript
const baseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL);

export function buildApiUrl(path: string): string {
  return `${baseUrl}${path}`;
}

export function resolveDocumentUrl(documentUrl?: string | null): string | null {
  return documentUrl ? buildApiUrl(documentUrl) : null;
}
```

**Conventions:**
- All fetch calls use `buildApiUrl()`.
- Environment variable `VITE_API_URL` can be ".", unset, or a full URL.
- Fallback: localhost dev detects port and routes to `http://localhost:8080`.

### URL Parameters

```typescript
const params = new URLSearchParams();
params.set('q', query);
params.set('limit', limit.toString());
params.set('fq_author', author);
params.set('fq_category', category);
fetch(`${baseUrl}?${params.toString()}`)
```

**Conventions:**
- Query: `q`
- Facet filters: `fq_*`
- Pagination: `page`, `limit`
- Sort: `sort`

## TypeScript Patterns

### Response Types

```typescript
export interface SearchResponse {
  results: BookResult[];
  total: number;
  query: string;
  facets: FacetGroups;
  page: number;
  limit: number;
}

const data: SearchResponse = await response.json();
```

### Optional Props

```typescript
const pageCount = book.page_count ?? 'unknown';
const url = book.document_url?.trim() ?? null;
```

## Development Workflow

### Scripts

```json
{
  "dev": "vite",
  "build": "tsc && vite build",
  "lint": "eslint . --max-warnings 0",
  "format": "prettier --write ."
}
```

### Running Locally

```bash
cd aithena-ui
npm install
npm run dev
npm run lint
```

### Testing

- **Framework:** Vitest + React Testing Library
- **Test files:** `*.test.ts` / `*.test.tsx`
- **Status:** No test script yet; to be added in Phase 3+

## Anti-Patterns

- **Don't hardcode API URLs in components** — use `api.ts` helpers
- **Don't fetch in components** — use hooks
- **Don't ignore cancellation flags** — prevents memory leaks
- **Don't use dangerouslySetInnerHTML without sanitization** — XSS risk
- **Don't add CSS-in-JS libraries** — keep global CSS
- **Don't forget to reset pagination when query/filters change**
- **Don't rely on Bootstrap classes** — installed but unused
- **Don't mix state management strategies** — use hooks for all state

## References

- `aithena-ui/src/api.ts` — URL building
- `aithena-ui/src/hooks/*.ts` — hook implementations
- `aithena-ui/src/Components/*.tsx` — component examples
- `aithena-ui/src/pages/*.tsx` — page layouts
- `aithena-ui/src/App.css` — styling
- Skill `api-contract-alignment` — backend API conventions
