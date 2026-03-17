# Decision: react-intl for i18n Foundation

**Date:** 2026-01-21  
**Author:** Dallas (Frontend Dev)  
**Issue:** #374  
**PR:** #422

## Context

Setting up internationalization infrastructure for Aithena UI to support English, Spanish, Catalan, and French. Need to choose between react-intl and react-i18next, and establish the architecture for locale management.

## Decision

### 1. Use react-intl (not react-i18next)

**Rationale:**
- Superior ICU MessageFormat support for complex formatting (plurals, dates, numbers, gender, selectordinal)
- Better handling of non-Latin scripts and Unicode normalization (future-proofs for potential Arabic, Japanese, Chinese)
- First-class TypeScript support with message extraction tooling
- Follows Unicode CLDR standards for locale data

### 2. Language Detection Fallback Chain

**Architecture:**
```
localStorage preference → browser locale → English (default)
```

**Implementation details:**
- Exact match first (`es` → Spanish)
- Prefix match second (`es-AR` → `es` → Spanish)
- Default to English if no match
- Detection runs once on app bootstrap
- User selections persist to `localStorage` with key `aithena-locale`

### 3. Locale File Structure

```
src/aithena-ui/src/locales/
  en.json  # English (baseline, ~30 keys)
  es.json  # Spanish (sample translations)
  ca.json  # Catalan (sample translations)
  fr.json  # French (sample translations)
```

- Flat JSON structure (no nesting)
- Keys use dot notation: `app.title`, `nav.search`, `loading.searchMessage`
- All locale files include same keys (react-intl falls back to `defaultLocale` messages for missing keys)

### 4. Context Architecture

- **I18nProvider:** Outermost context wrapper in `main.tsx` (wraps BrowserRouter, AuthProvider)
- **Exports:** 
  - `useI18n()` hook for locale switching (`locale`, `setLocale`)
  - `Locale` type for type-safe locale codes
- **Integration:** React components use `useIntl()` from react-intl for message formatting

### 5. Language Switcher Placement

- Added to TabNav component in `tab-nav-actions` section
- Positioned before username display, after nav links
- Basic select dropdown (issue #379 will refine UI)
- Visible only when authenticated (matches existing TabNav pattern)

## Impact

### Unblocks
- #375: Extract all hardcoded strings to locale files
- #376-378: Complete Spanish/Catalan/French translations
- #379: Refine language switcher UI
- #380: Add date/number formatting with `FormattedDate`/`FormattedNumber`
- #381: Add pluralization with `FormattedMessage`

### Testing
- All 180 existing tests pass
- No test regressions from i18n integration
- Future string extraction may require updating test snapshots

### Dependencies
- `react-intl` added to `package.json` (only new production dependency)

## Alternatives Considered

### react-i18next
**Pros:** Larger community, more plugins, simpler setup for basic translations  
**Cons:** Weaker ICU MessageFormat support, manual pluralization rules, less Unicode-aware  
**Rejected because:** ICU MessageFormat and non-Latin script support are critical for quality i18n

### Custom i18n solution
**Pros:** No external dependencies, full control  
**Cons:** Reinventing the wheel, missing CLDR data, no pluralization engine  
**Rejected because:** Not worth the maintenance burden

## Follow-up Actions

1. Issue #375: Extract all remaining hardcoded English strings
2. Issue #379: Improve language switcher UX (flag display, keyboard nav, aria-label)
3. Document i18n patterns for future component authors (use `FormattedMessage`, avoid string concatenation)
