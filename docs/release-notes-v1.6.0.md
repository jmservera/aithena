# Aithena v1.6.0 Release Notes — Internationalization & Quality

_Date:_ 2026-03-17  
_Prepared by:_ Newt (Product Manager)

Aithena **v1.6.0** is the internationalization and quality release. It introduces full multilingual UI support across four languages (English, Spanish, Catalan, French), a language switcher component with browser locale detection and localStorage persistence, a contributor guide for adding new languages, significant backend test coverage improvements (38 new `/v1/books` endpoint tests), Redis 7.3.0 migration across all Python services, ESLint 10 upgrade, and frontend code quality fixes. This release makes Aithena accessible to a broader audience while strengthening the quality foundation.

## Summary of shipped changes

### Internationalization — i18n (I18N-1 through I18N-7)

- **Extract all UI strings to locale files** — All user-facing text extracted from React components into structured JSON locale files with English as the baseline language. Over 153 locale keys covering search, navigation, filters, errors, admin, and metadata display (#375).
- **Spanish (es) translations** — Complete Spanish translation of all 153+ locale keys, professionally reviewed for accuracy and natural phrasing (#376).
- **Catalan (ca) translations** — Complete Catalan translation of all 153+ locale keys, supporting the project's Catalan-language book collection (#377).
- **French (fr) translations** — Complete French translation of all 153+ locale keys, extending coverage to the fourth supported language (#378).
- **Language switcher UI component** — LanguageSwitcher dropdown in the application header. Detects browser locale on first visit, persists selection to localStorage, and switches all UI text without page reload (#379).
- **Vitest tests for locale switching and translation completeness** — Automated tests verify that all locale files contain the same keys, that switching languages updates rendered text, and that missing translations fall back to English (#380).
- **i18n contributor guide** — `docs/i18n-guide.md` documenting the process for adding new languages: file structure, key naming conventions, testing requirements, and PR checklist (#381).

### Frontend Code Quality (FE-Q)

- **useRef and URL param improvements** — Fixed strictNullChecks issues with `useRef` usage across components, standardized URL search parameter handling for consistency with the URL-based search state introduced in v1.2.0 (#469).

### Backend Test Coverage (BE-Q)

- **38 new `/v1/books` endpoint tests** — Comprehensive test coverage for the books API endpoint including pagination, filtering, sorting, error handling, and edge cases. solr-search now at 231 tests with 95% code coverage (#471).

### Infrastructure Upgrades

- **Redis 4→7 migration** — All four Python services (solr-search, document-indexer, document-lister, admin) upgraded from redis-py 4.x to redis 7.3.0. Connection pool patterns, scan operations, and pipeline usage validated for compatibility (#479).
- **Dependabot dependency updates** — Merged batch of Dependabot PRs: redis 7.3.0, sentence-transformers update, ESLint 10 with react-hooks 7, and additional security patches.

## Milestone closure

The following issues are complete in **v1.6.0**:

- **#375** — i18n: Extract all UI strings to locale files (English baseline)
- **#376** — i18n: Add Spanish (es) translations
- **#377** — i18n: Add Catalan (ca) translations
- **#378** — i18n: Add French (fr) translations
- **#379** — i18n: Language switcher UI component
- **#380** — i18n: Add Vitest tests for locale switching and translation completeness
- **#381** — i18n: Document adding new languages (contributor guide)
- **#469** — Frontend code quality improvements (useRef, URL params)
- **#471** — Add test coverage for /v1/books endpoint (38 new tests)
- **#479** — Redis 4→7 migration across all Python services

## Breaking changes

None. All changes are backward-compatible.

- **i18n:** English remains the default locale. Existing deployments will see no change in behavior unless users switch languages via the new LanguageSwitcher component.
- **Redis 7.3.0:** The redis-py 7.x client is backward-compatible with Redis server 6+. No Redis server upgrade is required, though Redis 7 server is recommended for new deployments.
- **ESLint 10:** Only affects development tooling. No runtime impact.

## User-facing improvements

- **Multilingual UI:** Users can switch the interface to English, Spanish, Catalan, or French via the language dropdown in the header. The selection persists across sessions.
- **Browser locale detection:** First-time visitors automatically see the UI in their browser's preferred language (if supported).
- **Consistent URL parameters:** Search URLs are now standardized, improving bookmarkability and shareability.

## Operator-facing improvements

- **Redis 7.3.0 compatibility:** All services now use the latest redis-py client, compatible with Redis 6+ servers. Operators running Redis 7 servers get full feature compatibility.
- **No configuration changes required:** The i18n feature requires no environment variables or configuration. Locale files are bundled in the UI build.

## Infrastructure improvements

- **Redis client upgrade:** redis-py 7.3.0 across all Python services with improved connection pooling, scan operations, and pipeline patterns.
- **ESLint 10:** Major linting toolchain upgrade with react-hooks 7 for stricter hook dependency checking.
- **Test coverage:** solr-search reaches 231 tests at 95% coverage; aithena-ui reaches 212 tests with full i18n coverage.

## Security improvements

- **Dependency updates:** All Dependabot PRs merged, including security patches for redis, sentence-transformers, and ESLint ecosystem packages.
- **Redis 7.3.0:** Includes security fixes from redis-py 5.x and 6.x release lines.

## Upgrade instructions

For operators moving to **v1.6.0**:

1. Pull the latest images:
   ```bash
   docker compose pull
   ```
2. Restart the stack:
   ```bash
   docker compose up -d
   ```
3. No database migrations required.
4. No configuration changes required.
5. Verify the language switcher appears in the UI header.
6. No Redis server upgrade is mandatory (redis-py 7.3.0 is compatible with Redis 6+ servers).

## Validation highlights

- **Locale completeness:** Automated tests verify all 4 locale files (en, es, ca, fr) contain identical key sets — no missing translations.
- **Language switching:** Vitest tests confirm switching languages updates all rendered text without page reload.
- **localStorage persistence:** Language preference survives browser refresh and new tab opens.
- **Browser locale detection:** First-time visitors see their preferred language if supported; falls back to English otherwise.
- **Books API coverage:** 38 new tests cover pagination, filtering, sorting, error responses, and edge cases for `/v1/books`.
- **Redis 7.3.0 compatibility:** All Python service tests pass with the upgraded redis-py client. Connection pooling, `scan_iter()`, `mget()`, and pipeline operations verified.
- **ESLint 10:** Frontend lint passes clean with the new ESLint configuration.

## Documentation updated for this release

- `docs/release-notes-v1.6.0.md` (this file)
- `docs/test-report-v1.6.0.md` — Full test results across all 6 services
- `docs/i18n-guide.md` — Contributor guide for adding new languages
- `docs/admin-manual.md` — Updated with v1.6.0 deployment notes
- `CHANGELOG.md` — v1.6.0 entry added

---

Aithena **v1.6.0** makes the application accessible to a broader multilingual audience while significantly strengthening test coverage and infrastructure quality. The i18n framework is extensible — contributors can add new languages by following the guide in `docs/i18n-guide.md`.
