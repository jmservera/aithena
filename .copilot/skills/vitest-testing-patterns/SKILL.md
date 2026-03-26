---
name: "vitest-testing-patterns"
description: "Vitest + React Testing Library patterns for aithena-ui"
domain: "frontend, testing, vitest, react-testing-library"
confidence: "high"
source: "earned — consolidated from 31 test files in aithena-ui (Dallas reskill 2026-03-20)"
author: "Dallas"
created: "2026-03-20"
last_validated: "2026-03-20"
---

## Overview

Testing patterns for the aithena React frontend. Uses Vitest 4.x + React Testing Library + jsdom. Tests live in `src/__tests__/` and follow Given/When/Then structure.

## Setup

```bash
cd src/aithena-ui
npm test            # vitest run (non-watch)
npx vitest run      # alternative
npx vitest --watch  # dev mode
```

## IntlWrapper (Required for All Component Tests)

All components use react-intl. Tests MUST wrap renders with IntlWrapper:

```typescript
import { IntlProvider } from 'react-intl';
import enMessages from '../locales/en.json';

function IntlWrapper({ children, locale = 'en' }: { children: React.ReactNode; locale?: string }) {
  const messages = locale === 'en' ? enMessages : /* import other locale */;
  return (
    <IntlProvider locale={locale} messages={messages}>
      {children}
    </IntlProvider>
  );
}

// Usage:
render(<IntlWrapper><BookCard book={mockBook} /></IntlWrapper>);
```

**Without IntlWrapper:** Tests will throw "Could not find required `intl` object" errors.

## Component Testing Pattern

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

test('BookCard renders title and author', () => {
  // Given
  const book = { title: 'Don Quixote', author: 'Cervantes', year: 1605 };

  // When
  render(<IntlWrapper><BookCard book={book} /></IntlWrapper>);

  // Then
  expect(screen.getByText('Don Quixote')).toBeInTheDocument();
  expect(screen.getByText('Cervantes')).toBeInTheDocument();
});
```

**Selectors (prefer in order):** `getByRole` > `getByText` > `getByLabelText` > `getByTestId`

## Hook Testing Pattern

```typescript
import { renderHook, waitFor } from '@testing-library/react';

test('useSearch returns results for query', async () => {
  // Given
  vi.spyOn(global, 'fetch').mockResolvedValueOnce(
    new Response(JSON.stringify({ results: [mockBook], total: 1 }))
  );

  // When
  const { result } = renderHook(() => useSearch(), { wrapper: IntlWrapper });

  // Then
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.results).toHaveLength(1);
});
```

## Mocking Patterns

### Fetch Mocking
```typescript
beforeEach(() => {
  vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(mockData), { status: 200 })
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});
```

### File Upload Mocking
```typescript
// Mock file input via dispatchEvent (needed for accept attribute testing)
const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
const input = screen.getByLabelText('Upload');
await userEvent.upload(input, file);
```

### LocalStorage Mocking
```typescript
beforeEach(() => {
  localStorage.clear();
});

test('language preference persists', () => {
  render(<IntlWrapper><LanguageSwitcher /></IntlWrapper>);
  fireEvent.click(screen.getByRole('button', { name: 'Español' }));
  expect(localStorage.getItem('aithena.locale')).toBe('es');
});
```

## i18n Test Patterns

### Locale Completeness
```typescript
import en from '../locales/en.json';
import es from '../locales/es.json';

test('all locales have identical keys', () => {
  const keys = (obj: Record<string, string>) => Object.keys(obj).sort();
  expect(keys(es)).toEqual(keys(en));
});
```

### Language Switching
```typescript
test('switching language updates UI', async () => {
  render(<IntlWrapper initialLocale="en"><Component /></IntlWrapper>);
  // trigger language change
  expect(screen.getByText('Spanish text')).toBeInTheDocument();
});
```

## Error Boundary Testing

```typescript
import { MemoryRouter } from 'react-router-dom';

function ThrowingComponent() {
  throw new Error('Test error');
  return null;
}

test('error boundary shows fallback', () => {
  render(
    <MemoryRouter>
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    </MemoryRouter>
  );
  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
});

test('error boundary resets on route change', () => {
  // Use MemoryRouter with initialEntries for route-change testing
});
```

## Anti-Patterns

- ❌ **Forgetting IntlWrapper** — all components need it
- ❌ **Testing implementation details** — test behavior, not internal state
- ❌ **Exact emoji matching** — headless Chromium lacks emoji fonts; use `toContainText`
- ❌ **Using `.check()` on React controlled checkboxes** — click the label instead
- ❌ **Brittle selectors** — prefer `getByRole`, `getByText` over `getByTestId`
- ❌ **Missing cleanup** — always `vi.restoreAllMocks()` in `afterEach`

## References

- **Test files:** `src/aithena-ui/src/__tests__/`
- **Setup:** `src/aithena-ui/vitest.setup.ts`
- **Config:** `src/aithena-ui/vite.config.ts` (vitest section)
