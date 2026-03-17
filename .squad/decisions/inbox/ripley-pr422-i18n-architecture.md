# Decision: react-intl for i18n Foundation

**Date:** 2026-03-17  
**Decided by:** Ripley (Lead) — Reviewed Dallas's implementation in PR #422  
**Context:** Issue #374, i18n foundational infrastructure  
**Status:** Approved and merged to `dev`

## Decision

Adopt **react-intl** as the i18n library for Aithena's React frontend, wrapping it with a custom `I18nProvider` context for locale state management.

## Context

### Requirements
- Support 4 languages: English (en), Spanish (es), Catalan (ca), French (fr)
- ICU MessageFormat for plurals, gender, dates, numbers
- Language detection with localStorage persistence
- Language switcher UI component
- Foundation for 7 downstream i18n issues (#375-#381)

### Implementation (PR #422)
Dallas implemented:
1. `react-intl` v10.0.0 installation
2. `I18nProvider` context wrapping `IntlProvider` (react-intl)
3. Locale detection fallback chain: localStorage → browser locale → English
4. Basic language switcher component in TabNav
5. Sample locale files for all 4 languages (en.json, es.json, ca.json, fr.json)

## Options Considered

### Option 1: react-intl (SELECTED)
- **Pros:** 
  - ICU MessageFormat native support (plurals, gender, dates, numbers)
  - Official React integration (maintained by Format.JS)
  - Type-safe with TypeScript
  - Rich formatting APIs (FormattedMessage, FormattedDate, FormattedNumber, etc.)
- **Cons:** Slightly larger bundle size vs react-i18next
- **Verdict:** ✅ Best for complex i18n scenarios with diverse language requirements

### Option 2: react-i18next
- **Pros:** Popular, good community support, smaller bundle
- **Cons:** 
  - ICU MessageFormat requires plugin
  - More configuration overhead for advanced features
  - Less type-safe out of the box
- **Verdict:** ❌ Not as strong for ICU MessageFormat needs

### Option 3: Custom i18n solution
- **Pros:** Minimal bundle size
- **Cons:** 
  - Requires building plural rules, date/number formatting from scratch
  - High maintenance burden
  - No ecosystem support
- **Verdict:** ❌ Not viable for 4-language support

## Rationale

1. **ICU MessageFormat is critical:** Catalan, Spanish, and French have complex plural rules that require ICU MessageFormat. react-intl provides this natively.
2. **Type safety:** react-intl's TypeScript types integrate cleanly with our existing React + TypeScript stack.
3. **Extensibility:** The custom `I18nProvider` wrapper gives us flexibility for future enhancements (RTL support, dynamic locale loading, locale-specific date formatting) while keeping react-intl as the underlying engine.
4. **Clean architecture:** Separation of concerns — I18nContext manages locale state, IntlProvider handles message formatting.

## Implementation Details

### Provider Structure
```tsx
<I18nProvider>           // Custom context for locale state
  <IntlProvider>         // react-intl's formatting engine
    <App />
  </IntlProvider>
</I18nProvider>
```

### Locale Detection Chain
1. localStorage (`aithena-locale` key)
2. Browser locale with prefix matching (e.g., `en-US` → `en`)
3. English default

### Locale File Structure
- Path: `src/locales/{locale}.json`
- Key namespace: `app.*`, `nav.*`, `loading.*`, `language.*`
- Sample keys in English baseline (issue #375 will extract all UI strings)

### Known Issues (Non-blocking)
- **Catalan flag:** 🇨🇦 (Canadian) instead of 🏴 (Catalan) — intentional placeholder, issue #379 will refine

## Impact

- **Teams:** Frontend (Dallas), future i18n contributors
- **Timeline:** Unblocks i18n chain (#375-#381)
- **Users:** Foundation for full UI internationalization
- **Bundle size:** +~50KB (react-intl + locale data) — acceptable for 4-language support

## Testing

- ✅ All 180 tests pass
- ✅ TypeScript compilation clean
- ✅ ESLint, Prettier, all CI checks green
- ✅ E2E tests pass

## Next Steps

1. Issue #375: Extract all UI strings to locale files (English baseline)
2. Issue #376-#378: Translate to Spanish, Catalan, French
3. Issue #379: Enhance language switcher UI
4. Issue #380: Implement language-specific date/number formatting
5. Issue #381: Document i18n contribution guidelines

## References

- **Issue:** #374
- **PR:** #422
- **Downstream issues:** #375-#381
- **Documentation:** react-intl docs (https://formatjs.io/docs/react-intl/)
