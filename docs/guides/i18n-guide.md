# Internationalization (i18n) Guide

This guide explains how to add new languages, translate strings, and test translations in Aithena's React frontend.

## Overview

Aithena uses **react-intl** for internationalization with JSON-based locale files. The system manages translation state in the `I18nContext` and provides a language switcher component.

### Architecture

- **Locale Files**: `src/aithena-ui/src/locales/{code}.json` (e.g., `en.json`, `es.json`)
- **I18n Context**: `src/aithena-ui/src/contexts/I18nContext.tsx` — manages the current locale, provides locale-detection logic, and provides the `useI18n()` hook
- **Language Switcher**: `src/aithena-ui/src/Components/LanguageSwitcher.tsx` — dropdown UI for switching languages
- **Hook**: `useIntl()` from react-intl — used in components to access translation functions
- **Test Utilities**: `src/aithena-ui/src/__tests__/test-intl-wrapper.tsx` — wraps components in IntlProvider for testing

### Current Supported Locales

- `en` (English) — baseline, 260+ keys
- `es` (Spanish / Español)
- `ca` (Catalan / Català)
- `fr` (French / Français)

---

## Adding a New Language

Follow these steps to add a new language to Aithena:

### Step 1: Create the Locale File

Create a new JSON file at `src/aithena-ui/src/locales/{code}.json`, where `{code}` is the ISO 639-1 language code (e.g., `de.json` for German, `it.json` for Italian).

**Start by copying `en.json` as your baseline:**

```bash
cp src/aithena-ui/src/locales/en.json src/aithena-ui/src/locales/{code}.json
```

Then translate all 260+ keys to your target language. Preserve the JSON structure and key names—only change the string values.

**Example structure:**

```json
{
  "admin.actionFailed": "Acción fallida",
  "app.title": "Aithena",
  "search.placeholder": "Buscar libros por título, autor o contenido…",
  ...
}
```

**Important:** Preserve plural and variable placeholders:

```json
{
  "library.bookCount": "{total, number} {total, plural, one {libro} other {libros}} en colección",
  "search.resultCount": "{total, number} {total, plural, one {resultado} other {resultados}} para \"{query}\""
}
```

Placeholders like `{total}`, `{query}`, `{count}`, etc., are **not** translated—only the surrounding text.

### Step 2: Register the Locale in I18nContext

Open `src/aithena-ui/src/contexts/I18nContext.tsx` and make three changes:

1. **Import the new locale file** at the top:

```typescript
import {code}Messages from '../locales/{code}.json';
```

Example for German:
```typescript
import deMessages from '../locales/de.json';
```

2. **Add the locale to the `Locale` type**:

```typescript
export type Locale = 'en' | 'es' | 'ca' | 'fr' | '{code}';
```

Example:
```typescript
export type Locale = 'en' | 'es' | 'ca' | 'fr' | 'de';
```

3. **Add an entry to the `MESSAGES` map**:

```typescript
const MESSAGES: Record<Locale, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
  {code}: {code}Messages,
};
```

Example:
```typescript
const MESSAGES: Record<Locale, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
  de: deMessages,
};
```

4. **Add to `SUPPORTED_LOCALES`**:

```typescript
const SUPPORTED_LOCALES: Locale[] = ['en', 'es', 'ca', 'fr', '{code}'];
```

Example:
```typescript
const SUPPORTED_LOCALES: Locale[] = ['en', 'es', 'ca', 'fr', 'de'];
```

### Step 3: Add to LanguageSwitcher

Open `src/aithena-ui/src/Components/LanguageSwitcher.tsx` and add an entry to the `LANGUAGES` array:

```typescript
const LANGUAGES: Array<{ code: Locale; flag: string }> = [
  { code: 'en', flag: '🇬🇧' },
  { code: 'es', flag: '🇪🇸' },
  { code: 'ca', flag: '🇨🇦' },
  { code: 'fr', flag: '🇫🇷' },
  { code: '{code}', flag: '{flag_emoji}' },
];
```

Example for German:
```typescript
{ code: 'de', flag: '🇩🇪' }
```

**Important:** Choose an appropriate flag emoji for the language. Common choices:

- 🇩🇪 German
- 🇮🇹 Italian
- 🇵🇹 Portuguese
- 🇯🇵 Japanese
- 🇨🇳 Chinese
- 🇷🇺 Russian

### Step 4: Update the i18n Test Suite

Open `src/aithena-ui/src/__tests__/i18n.test.tsx` and add the new locale to the test imports and test data:

1. **Import the new locale file**:

```typescript
import {code}Messages from '../locales/{code}.json';
```

Example:
```typescript
import deMessages from '../locales/de.json';
```

2. **Add to the `LOCALE_FILES` test object** (around line 16):

```typescript
const LOCALE_FILES: Record<string, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
  {code}: {code}Messages,
};
```

Example:
```typescript
const LOCALE_FILES: Record<string, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
  de: deMessages,
};
```

3. **Add to the locale test array** (around line 53):

The test suite iterates over locale files to verify completeness. Find the `.each([...])` block:

```typescript
it.each([
  ['es', esMessages],
  ['ca', caMessages],
  ['fr', frMessages],
])('%s locale has all keys from en.json', (_locale, messages) => {
  ...
});
```

Add your locale:
```typescript
it.each([
  ['es', esMessages],
  ['ca', caMessages],
  ['fr', frMessages],
  ['de', deMessages],
])('%s locale has all keys from en.json', (_locale, messages) => {
  ...
});
```

**Do this for both `.each()` blocks** (one tests key presence, one tests for extra keys).

### Step 5: Verify Registration

Run the i18n test suite to ensure your new locale is properly registered:

```bash
cd src/aithena-ui
npm test -- i18n.test.tsx
```

The tests verify:
- All keys from `en.json` are present in your locale
- No extra keys exist in your locale
- No empty translation values exist

---

## Adding New Strings to Existing Components

When adding a new translatable string to a component, you must add the key to **all locale files**:

### Step 1: Add to the English Baseline

1. Open `src/aithena-ui/src/locales/en.json`
2. Add your new key with an English translation:

```json
{
  "footer.copyright": "© 2024 Aithena. All rights reserved."
}
```

**Use namespaced keys** following the existing pattern:

- `admin.*` — Admin dashboard strings
- `app.*` — Application-level strings (title, subtitle)
- `book.*` — Book detail/metadata strings
- `error.*` — Error messages
- `facet.*` — Search facets/filters
- `filters.*` — Filter UI
- `language.*` — Language selector
- `library.*` — Library view
- `nav.*` — Navigation menu
- `search.*` — Search UI
- `upload.*` — Upload form
- `stats.*` — Statistics page

### Step 2: Add to All Other Locale Files

Copy the same key to `es.json`, `ca.json`, and `fr.json`, translating the value:

**es.json:**
```json
{
  "footer.copyright": "© 2024 Aithena. Todos los derechos reservados."
}
```

**ca.json:**
```json
{
  "footer.copyright": "© 2024 Aithena. Tots els drets reservats."
}
```

**fr.json:**
```json
{
  "footer.copyright": "© 2024 Aithena. Tous droits réservés."
}
```

### Step 3: Use `useIntl()` in Your Component

In your React component, import `useIntl` from react-intl and use it to resolve strings:

```typescript
import { useIntl } from 'react-intl';

function Footer() {
  const intl = useIntl();

  return (
    <footer>
      <p>{intl.formatMessage({ id: 'footer.copyright' })}</p>
    </footer>
  );
}
```

**For JSX content, you can also use `<FormattedMessage>`** (less common):

```typescript
import { FormattedMessage } from 'react-intl';

function Footer() {
  return (
    <footer>
      <p>
        <FormattedMessage id="footer.copyright" />
      </p>
    </footer>
  );
}
```

**For attributes (alt text, aria-label, title, placeholder, etc.), always use `useIntl()`:**

```typescript
const intl = useIntl();

return (
  <input
    placeholder={intl.formatMessage({ id: 'search.placeholder' })}
    aria-label={intl.formatMessage({ id: 'search.inputAriaLabel' })}
  />
);
```

### Step 4: Run Tests

Run the i18n test suite to verify all locales have the new key:

```bash
cd src/aithena-ui
npm test -- i18n.test.tsx
```

---

## Testing Components with Translations

When writing tests for components that use `useIntl()` or react-intl, wrap them in the `IntlWrapper`:

### Example Test

```typescript
import { render, screen } from '@testing-library/react';
import { IntlWrapper } from '../test-intl-wrapper';
import MyComponent from '../Components/MyComponent';

describe('MyComponent', () => {
  it('displays translated text', () => {
    render(
      <IntlWrapper>
        <MyComponent />
      </IntlWrapper>
    );
    expect(screen.getByText('Book Library Search')).toBeInTheDocument();
  });
});
```

The `IntlWrapper` provides:
- The English locale (`en`)
- English messages from `en.json`
- The react-intl `IntlProvider`

This allows components to access `useIntl()` without errors and ensures consistent translations in tests.

---

## Locale Detection and Persistence

The I18nContext automatically detects the user's preferred locale with the following priority:

1. **localStorage preference** — User's previous selection (stored as `aithena-locale`)
2. **Browser locale** — `navigator.language` (e.g., `en-US` → `en`, `es-ES` → `es`)
3. **English fallback** — Default to `en` if no match

When a user switches languages, the selection is saved to `localStorage` and persists across sessions.

---

## Locale File Template

Here's a complete template with all current keys (260+ keys as of v1.5.0):

```json
{
  "admin.actionFailed": "Action failed",
  "admin.cancel": "Cancel",
  "admin.clearAll": "🗑️ Clear All",
  "admin.clearConfirm": "Clear {count} processed {count, plural, one {document} other {documents}}?",
  "admin.confirm": "✅ Confirm",
  "admin.emptyFailed": "No failed documents. 🎉",
  "admin.emptyProcessed": "No processed documents yet.",
  "admin.emptyQueued": "No documents currently queued. ✓",
  "admin.errorPrefix": "⚠",
  "admin.failed.empty": "No failed documents. 🎉",
  "admin.failed.headerAction": "Action",
  "admin.failed.headerError": "Error",
  "admin.failed.headerFailedAt": "Failed at",
  "admin.failed.headerPath": "Path",
  "admin.failed.noError": "No error details recorded.",
  "admin.failed.requeue": "🔄 Requeue",
  "admin.failed.requeueAll": "🔄 Requeue All ({count})",
  "admin.loading": "Loading queue state…",
  "admin.metricFailed": "Failed",
  "admin.metricProcessed": "Processed",
  "admin.metricQueued": "Queued",
  "admin.metricTotal": "Total",
  "admin.metricsAria": "Queue metrics",
  "admin.metricsLabel": "Queue metrics",
  "admin.noErrorDetails": "No error details recorded.",
  "admin.processed.cancel": "Cancel",
  "admin.processed.clearAll": "🗑️ Clear All",
  "admin.processed.clearConfirm": "Clear {count, plural, one {# processed document} other {# processed documents}}?",
  "admin.processed.confirm": "✅ Confirm",
  "admin.processed.empty": "No processed documents yet.",
  "admin.processed.headerAuthor": "Author",
  "admin.processed.headerIndexedAt": "Indexed at",
  "admin.processed.headerPath": "Path",
  "admin.processed.headerTitle": "Title",
  "admin.processed.headerYear": "Year",
  "admin.queued.empty": "No documents currently queued. ✓",
  "admin.queued.headerPath": "Path",
  "admin.queued.headerQueuedAt": "Queued at",
  "admin.refresh": "🔄 Refresh",
  "admin.requeue": "🔄 Requeue",
  "admin.requeueAll": "🔄 Requeue All ({count})",
  "admin.tab.failed": "❌ Failed ({count})",
  "admin.tab.processed": "✅ Processed ({count})",
  "admin.tab.queued": "⏳ Queued ({count})",
  "admin.tabFailed": "❌ Failed ({count})",
  "admin.tabProcessed": "✅ Processed ({count})",
  "admin.tabQueued": "⏳ Queued ({count})",
  "admin.tabsAria": "Document status tabs",
  "admin.tabsLabel": "Document status tabs",
  "admin.thAction": "Action",
  "admin.thAuthor": "Author",
  "admin.thError": "Error",
  "admin.thFailedAt": "Failed at",
  "admin.thIndexedAt": "Indexed at",
  "admin.thPath": "Path",
  "admin.thQueuedAt": "Queued at",
  "admin.thTitle": "Title",
  "admin.thYear": "Year",
  "admin.title": "🏛️ Admin Dashboard",
  "app.subtitle": "Book Library Search",
  "app.title": "Aithena",
  "book.foundOnPage": "Found on page {pageStart}",
  "book.foundOnPages": "Found on pages {pageStart}–{pageEnd}",
  "book.loadingSimilarBooks": "Loading similar books…",
  "book.metaAuthor": "Author:",
  "book.metaCategory": "Category:",
  "book.metaLanguage": "Language:",
  "book.metaPages": "Pages:",
  "book.metaYear": "Year:",
  "book.noSimilarBooks": "No similar books found",
  "book.openPdf": "Open PDF",
  "book.openPdfFor": "Open PDF for {title}",
  "book.openSimilarBook": "Open similar book {title}",
  "book.similarBooks": "Similar Books",
  "book.similarBooksError": "We couldn't load similar books right now. Try another title in a moment.",
  "book.similarBooksSubtitle": "Readers also looked at these semantically related titles.",
  "book.similarityScore": "{score}% match",
  "book.unknownAuthor": "Unknown author",
  "common.items": "Items",
  "common.loadingMessage": "Please wait while Aithena prepares this view.",
  "common.loadingPage": "Loading page…",
  "common.title": "Title",
  "config.limit": "limit:",
  "config.limitDescription": "The maximum number of results to generate.",
  "config.reset": "Reset",
  "config.title": "Config",
  "error.boundary.details": "Technical details",
  "error.boundary.message": "An unexpected error occurred. Please try refreshing.",
  "error.boundary.reload": "Reload page",
  "error.boundary.retry": "Retry",
  "error.boundary.title": "Something went wrong",
  "error.eyebrow": "⚠️",
  "error.message": "An unexpected error occurred. Please try refreshing.",
  "error.prefix": "⚠️",
  "error.reloadButton": "Reload page",
  "error.technicalDetails": "Technical details",
  "error.title": "Something went wrong",
  "facet.author": "Author",
  "facet.category": "Category",
  "facet.language": "Language",
  "facet.semanticUnavailable": "Facets are only available in keyword mode",
  "facet.year": "Year",
  "filters.activeFilters": "Active filters:",
  "filters.activeLabel": "Active filters:",
  "filters.author": "Author",
  "filters.category": "Category",
  "filters.clearAll": "Clear all",
  "filters.language": "Language",
  "filters.removeAria": "Remove {label} filter",
  "filters.removeFilter": "Remove {label} filter",
  "filters.semanticUnavailable": "Facets are only available in keyword mode",
  "filters.year": "Year",
  "footer.aria": "Application version",
  "footer.version": "Aithena v{version}",
  "indexing.discovered": "Discovered",
  "indexing.failed": "Failed",
  "indexing.indexed": "Indexed",
  "indexing.loading": "Loading status…",
  "indexing.pending": "Pending",
  "indexing.progress": "Indexing Progress",
  "indexing.rabbitmq": "RabbitMQ",
  "indexing.redis": "Redis",
  "indexing.serviceHealth": "Service Health",
  "indexing.solr": "Solr",
  "indexing.solrDetail": "{status} · {nodes, plural, one {# node} other {# nodes}} · {docs} docs",
  "indexing.title": "System Status",
  "indexing.updated": "Updated {time}",
  "language.ca": "Català",
  "language.en": "English",
  "language.es": "Español",
  "language.fr": "Français",
  "language.select": "Language",
  "library.bookCount": "{total, number} {total, plural, one {book} other {books}} in collection",
  "library.booksHeading": "Library books",
  "library.loading": "Loading…",
  "library.noBooksFound": "No books found.",
  "library.noBooksFoundFiltered": "No books found with the selected filters.",
  "library.pageInfo": "Page {page} of {totalPages}",
  "library.perPageLabel": "Per page:",
  "library.sortAuthorAZ": "Author (A–Z)",
  "library.sortAuthorZA": "Author (Z–A)",
  "library.sortLabel": "Sort:",
  "library.sortTitleAZ": "Title (A–Z)",
  "library.sortTitleZA": "Title (Z–A)",
  "library.sortYearNewest": "Year (newest)",
  "library.sortYearOldest": "Year (oldest)",
  "library.title": "📖 Library",
  "loading.admin": "Loading admin…",
  "loading.adminMessage": "Getting the admin dashboard ready.",
  "loading.library": "Loading library…",
  "loading.libraryMessage": "Fetching your library view.",
  "loading.search": "Loading search…",
  "loading.searchMessage": "Preparing your search workspace.",
  "loading.signIn": "Loading sign in…",
  "loading.signInMessage": "Getting the sign-in view ready.",
  "loading.stats": "Loading statistics…",
  "loading.statsMessage": "Crunching the latest library numbers.",
  "loading.status": "Loading status…",
  "loading.statusMessage": "Checking indexing and service status.",
  "loading.upload": "Loading upload…",
  "loading.uploadMessage": "Preparing the upload tools.",
  "login.description": "Use your account to access search, upload, and admin tools.",
  "login.password": "Password",
  "login.signIn": "Sign in",
  "login.signingIn": "Signing in…",
  "login.title": "Sign in to Aithena",
  "login.username": "Username",
  "nav.admin": "Admin",
  "nav.library": "Library",
  "nav.login": "Login",
  "nav.mainNavigation": "Main navigation",
  "nav.search": "Search",
  "nav.signOut": "Sign out",
  "nav.signedIn": "Signed in",
  "nav.stats": "Stats",
  "nav.status": "Status",
  "nav.upload": "Upload",
  "pagination.ariaLabel": "Search results pagination",
  "pagination.nextPage": "Next page",
  "pagination.previousPage": "Previous page",
  "pdf.authorSeparator": " — {author}",
  "pdf.closeViewer": "Close PDF viewer",
  "pdf.document": "Document",
  "pdf.loadError": "Could not load the PDF document.",
  "pdf.loadErrorDetail": "The file may be unavailable or the URL is invalid.",
  "pdf.noDocumentUrl": "No document URL available for this result.",
  "pdf.openInNewTab": "Try opening in a new tab",
  "pdf.pdfDocument": "PDF document",
  "search.button": "Search",
  "search.emptyPrompt": "Enter a search term above to find books.",
  "search.errorMessage": "Your current search settings are still here. Try loading the results again or reload the app.",
  "search.errorReload": "Reload app",
  "search.errorRetry": "Try again",
  "search.errorTitle": "Search results are temporarily unavailable.",
  "search.formLabel": "Search the library",
  "search.inputAriaLabel": "Search query",
  "search.inputLabel": "Search books by title, author, or content",
  "search.modeGroupLabel": "Search mode",
  "search.modeHybrid": "Hybrid",
  "search.modeHybridTitle": "Combined keyword + semantic search",
  "search.modeKeyword": "Keyword",
  "search.modeKeywordTitle": "Traditional keyword search",
  "search.modeLabel": "Search mode: {mode}",
  "search.modeSemantic": "Semantic",
  "search.modeSemanticTitle": "Vector-based semantic search",
  "search.noResults": "No results found for \"{query}\".",
  "search.noResultsFiltered": "No results found for \"{query}\" with the selected filters.",
  "search.pageInfo": "Page {page} of {totalPages}",
  "search.perPageLabel": "Per page:",
  "search.placeholder": "Search books by title, author, or content…",
  "search.resultCount": "{total, number} {total, plural, one {result} other {results}} for \"{query}\"",
  "search.resultsHeading": "Search results",
  "search.searching": "Searching…",
  "search.sortAuthorAZ": "Author (A–Z)",
  "search.sortLabel": "Sort:",
  "search.sortRelevance": "Relevance",
  "search.sortTitleAZ": "Title (A–Z)",
  "search.sortYearNewest": "Year (newest)",
  "search.sortYearOldest": "Year (oldest)",
  "similar.empty": "No similar books found.",
  "similar.error": "Couldn't load similar books.",
  "similar.loading": "Loading similar books…",
  "similar.matchScore": "{score}% match",
  "similar.openAria": "Open similar book {title}",
  "similar.subtitle": "Readers also looked at these semantically related titles.",
  "similar.title": "Similar Books",
  "similar.unknownAuthor": "Unknown author",
  "stats.average": "Average",
  "stats.booksIndexed": "Books indexed",
  "stats.byAuthor": "By Author (top 20)",
  "stats.byCategory": "By Category",
  "stats.byLanguage": "By Language",
  "stats.byYear": "By Year",
  "stats.headerCount": "Count",
  "stats.headerValue": "Value",
  "stats.loading": "Loading statistics…",
  "stats.max": "Max",
  "stats.min": "Min",
  "stats.noData": "No data available.",
  "stats.pageStats": "Page stats",
  "stats.title": "Collection Stats",
  "stats.totalPages": "Total pages",
  "upload.backToSearch": "Back to Search",
  "upload.browse": "browse",
  "upload.description": "Add a new book to the library by uploading a PDF file (max 50MB)",
  "upload.dragPrompt": "Drag and drop a PDF file here, or",
  "upload.errorMessage": "Try reloading this section first. If the issue keeps happening, reload the app and retry the file.",
  "upload.errorReload": "Reload app",
  "upload.errorRetry": "Try again",
  "upload.errorTitle": "The upload panel hit an unexpected problem.",
  "upload.failedTitle": "Upload Failed",
  "upload.fileInputLabel": "Choose a PDF file to upload",
  "upload.filenameLabel": "Filename:",
  "upload.maxFileSize": "Maximum file size: 50MB",
  "upload.progressLabel": "Upload progress",
  "upload.sizeLabel": "Size:",
  "upload.statusLabel": "Status:",
  "upload.successTitle": "Upload Successful",
  "upload.title": "Upload PDF",
  "upload.tryAgain": "Try Again",
  "upload.uploadAnother": "Upload Another",
  "upload.uploading": "Uploading…"
}
```

---

## Checklist for Adding a New Language

- [ ] Create `src/aithena-ui/src/locales/{code}.json` with all 260+ keys translated
- [ ] Add import to `I18nContext.tsx`
- [ ] Add to `Locale` type in `I18nContext.tsx`
- [ ] Add to `MESSAGES` map in `I18nContext.tsx`
- [ ] Add to `SUPPORTED_LOCALES` in `I18nContext.tsx`
- [ ] Add entry to `LANGUAGES` array in `LanguageSwitcher.tsx`
- [ ] Import new locale file in `i18n.test.tsx`
- [ ] Add to `LOCALE_FILES` in `i18n.test.tsx`
- [ ] Add to both `.each([...])` test blocks in `i18n.test.tsx`
- [ ] Run i18n tests: `cd src/aithena-ui && npm test -- i18n.test.tsx`
- [ ] Verify all tests pass

---

## Troubleshooting

### Tests fail with "missing keys"

**Cause**: A locale file is missing one or more keys from `en.json`.

**Solution**: Run `npm test -- i18n.test.tsx` to see which keys are missing, then add them to your locale file.

### useIntl() throws "must be used within an I18nProvider"

**Cause**: A component using `useIntl()` is not wrapped in the `I18nContext`.

**Solution**: In tests, wrap components with `<IntlWrapper>`. In production, ensure the `I18nProvider` wraps your app (check `App.tsx`).

### Language doesn't appear in the switcher

**Cause**: The locale wasn't added to `LANGUAGES` in `LanguageSwitcher.tsx`.

**Solution**: Add an entry to the `LANGUAGES` array with a `code` matching your locale file and a `flag` emoji.

### Plural forms don't translate correctly

**Cause**: Plural rules may differ between languages. The placeholders like `{count, plural, one {...} other {...}}` define the rules.

**Solution**: Translate the text inside the curly braces, not the syntax itself. Example:

English:
```json
"{count, plural, one {# book} other {# books}}"
```

German (Deutsch):
```json
"{count, plural, one {# Buch} other {# Bücher}}"
```

---

## References

- [react-intl Documentation](https://formatjs.io/docs/react-intl)
- [Format.js (Formatting & Internationalization)](https://formatjs.io/)
- [ISO 639-1 Language Codes](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes)

