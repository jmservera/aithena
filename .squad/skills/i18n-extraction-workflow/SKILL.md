---
name: "i18n-extraction-workflow"
description: "Workflow for extracting hardcoded UI strings to react-intl locale files"
domain: "frontend, internationalization, react-intl"
confidence: "high"
source: "earned — v1.6.0 & v1.7.0 i18n extraction cycle (Dallas 2026-03-17/18)"
author: "Dallas"
created: "2026-03-18"
last_validated: "2026-03-18"
---

## Overview

The i18n extraction workflow converts hardcoded English strings in React components to `react-intl` calls with locale IDs, enabling translation across multiple languages. This skill captures the proven process from Aithena v1.6.0 & v1.7.0 releases.

## Quick Reference

**Key Pattern:**
```typescript
// Before: hardcoded string
<button>Open PDF</button>

// After: i18n with formatMessage
const intl = useIntl();
<button>{intl.formatMessage({ id: 'books.openPdf' })}</button>
```

**Locale File Structure:**
```json
{
  "domain.featureKey": "English value",
  "books.pages": "{count, number} pages",
  "search.resultCount": "{total, plural, one {result} other {results}}"
}
```

**Key Naming:** `domain.featureKey` (lowerCamelCase, dot-separated domain)

**Domains:** `search`, `filter`, `books`, `error`, `language`, `admin`, `upload`, `navigation`, `status`, `stats`, `app`

## Process Summary

1. **Identify extraction scope** — Which components/pages contain hardcoded strings?
2. **Design locale keys** — Define key naming convention and structure
3. **Extract to locale files** — Move strings to JSON locale files (en baseline)
4. **Update components** — Replace hardcoded strings with `useIntl()` + `formatMessage()`
5. **Create locale files** — Translate to es, ca, fr, etc.
6. **Register locales** — Update I18nContext with new locale imports
7. **Test completeness** — Verify all locales have identical key sets
8. **Test switching** — Verify UI updates when language changes
9. **Test persistence** — Verify localStorage preserves language choice

## Phase 1: Component Extraction (v1.6.0)

### Step 1: Identify Hardcoded Strings

Search components for literal strings:
```bash
grep -r "label\|placeholder\|title\|error" src/aithena-ui/src/Components/ | grep "\"" | head -50
```

**Scope:** UI components (BookCard, FacetPanel, etc.), excludes pages initially

### Step 2: Design Locale Key Naming

**Convention:** `domain.featureName` (lowerCamelCase with dot-separated domain)

**Examples:**
```json
{
  "search.placeholder": "Search books by title, author, or content…",
  "filter.author": "Author",
  "books.pages": "{count, number} pages",
  "error.loadFailed": "Failed to load results",
  "language.english": "English"
}
```

**ICU Syntax (for plurals/variables):**
```json
{
  "books.pageCount": "{count, number} {count, plural, one {page} other {pages}}",
  "search.resultCount": "{total, plural, one {result} other {results}} for \"{query}\""
}
```

### Step 3: Create English Baseline (en.json)

Create `src/aithena-ui/src/locales/en.json` with all extracted strings.

### Step 4: Update Components to Use useIntl()

**Pattern 1: Simple strings**
```typescript
import { useIntl } from 'react-intl';

const intl = useIntl();
<button>{intl.formatMessage({ id: 'books.openPdf' })}</button>
```

**Pattern 2: With variables**
```typescript
<FormattedMessage
  id="books.pages"
  values={{ count: book.page_count }}
/>
```

**Pattern 3: Placeholders & aria-labels**
```typescript
placeholder={intl.formatMessage({ id: 'search.placeholder' })}
aria-label={intl.formatMessage({ id: 'navigation.search' })}
```

### Step 5: Create Locale Files (es, ca, fr)

Copy `en.json` → `es.json`, `ca.json`, `fr.json` and translate all values.

**Critical Rules:**
- ✅ Preserve ICU syntax: `{count, plural, ...}` must not change
- ✅ Preserve placeholders: `{total}`, `{query}`, `{count}` are NOT translated
- ✅ Preserve key names: JSON keys identical across all files
- ✅ Test completeness: Automated tests verify all locales have same keys

### Step 6: Register Locales in I18nContext

Update `src/aithena-ui/src/contexts/I18nContext.tsx`:

```typescript
import enMessages from '../locales/en.json';
import esMessages from '../locales/es.json';
import caMessages from '../locales/ca.json';
import frMessages from '../locales/fr.json';

export type Locale = 'en' | 'es' | 'ca' | 'fr';

const MESSAGES: Record<Locale, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
};

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    const browserLang = navigator.language.split('-')[0];
    if (['es', 'ca', 'fr'].includes(browserLang)) {
      localStorage.setItem('aithena.locale', browserLang);
      return browserLang as Locale;
    }
    return 'en';
  });

  return (
    <IntlProvider locale={locale} messages={MESSAGES[locale]}>
      {children}
    </IntlProvider>
  );
}
```

## Phase 2: Page-Level Extraction (v1.7.0)

### Extended Scope

Pages contain additional strings in:
- Module-level constants (SORT_OPTIONS, MODE_OPTIONS arrays)
- Helper functions (renderLazyRoute)
- Page-specific error messages

### Pattern: Convert Static Arrays to labelId

**Before:**
```typescript
const SORT_OPTIONS = [
  { label: 'Relevance', value: 'score' },
  { label: 'Year (Newest)', value: 'year_desc' }
];

{SORT_OPTIONS.map(opt => (
  <option value={opt.value}>{opt.label}</option>
))}
```

**After:**
```typescript
interface SortOption {
  labelId: string;
  value: string;
}

const SORT_OPTIONS: SortOption[] = [
  { labelId: 'search.sortRelevance', value: 'score' },
  { labelId: 'search.sortYearNewest', value: 'year_desc' }
];

const intl = useIntl();
{SORT_OPTIONS.map(opt => (
  <option value={opt.value}>
    {intl.formatMessage({ id: opt.labelId })}
  </option>
))}
```

**Benefits:**
- Arrays stay module-level (no re-render overhead)
- Labels resolved at render time via intl
- TypeScript ensures labelId validity

### Pattern: Component for Lazy Routes with i18n

**Before:**
```typescript
const renderLazyRoute = (Comp: React.LazyExoticComponent<any>) => (
  <Suspense fallback={<div>Loading…</div>}>
    <Comp />
  </Suspense>
);
```

**After:**
```typescript
function LazyRoute({ component: Component }: { component: React.LazyExoticComponent<any> }) {
  const intl = useIntl();
  return (
    <Suspense fallback={<div>{intl.formatMessage({ id: 'app.loading' })}</div>}>
      <Component />
    </Suspense>
  );
}
```

**Why:** Components can call hooks; helper functions cannot.

## Testing Strategy

### Test 1: Locale Completeness

```typescript
import en from '../locales/en.json';
import es from '../locales/es.json';
import ca from '../locales/ca.json';
import fr from '../locales/fr.json';

test('all locales have identical keys', () => {
  const keys = (obj: Record<string, string>) => Object.keys(obj).sort();
  expect(keys(es)).toEqual(keys(en));
  expect(keys(ca)).toEqual(keys(en));
  expect(keys(fr)).toEqual(keys(en));
});
```

### Test 2: Language Switching

```typescript
test('switching language updates UI', async () => {
  render(
    <IntlWrapper initialLocale="en">
      <LanguageSwitcher />
      {/* Component using i18n */}
    </IntlWrapper>
  );
  
  fireEvent.click(screen.getByRole('button', { name: 'Español' }));
  expect(screen.getByText('Buscar libros…')).toBeInTheDocument();
});
```

### Test 3: localStorage Persistence

```typescript
test('language preference persists', () => {
  render(<IntlWrapper><LanguageSwitcher /></IntlWrapper>);
  fireEvent.click(screen.getByRole('button', { name: 'Español' }));
  expect(localStorage.getItem('aithena.locale')).toBe('es');
});
```

## Key Learnings

1. **Early Design** — Key naming convention must be finalized before extraction
2. **JSON Consistency** — All locale files must have identical keys (enforced by tests)
3. **Browser Locale Detection** — Always fallback to English if user's language isn't supported
4. **localStorage Naming** — Use dot-notation (`aithena.locale`) for consistency
5. **Component vs. Helper** — Helpers can't call hooks; convert to components when translation is needed
6. **Preserve ICU Syntax** — Translators must NOT modify `{plural, ...}` structures
7. **Test Completeness** — Add locale completeness test before accepting new languages
8. **Performance** — Module-level arrays with labelId pattern avoid re-renders

## Contributing Translations

**Checklist:**
1. Copy `en.json` → `{code}.json` (e.g., `de.json`)
2. Translate all ~260 values (preserve ICU syntax & placeholders)
3. Run `npm run lint` (JSON validation)
4. Run `npm test` (locale completeness)
5. Submit PR with updated I18nContext

## References

- **Locale Files:** `src/aithena-ui/src/locales/{code}.json`
- **I18n Context:** `src/aithena-ui/src/contexts/I18nContext.tsx`
- **Contributor Guide:** `docs/i18n-guide.md`
- **Release Notes:** `docs/release-notes-v1.6.0.md`
