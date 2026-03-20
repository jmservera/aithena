# Squad Decisions Archive

**Last updated:** 2026-03-16  
**Archived:** Decisions older than 30 days, moved from decisions.md to reduce file size.

------

# Decision: Container Version Metadata Baseline

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-15  
**Status:** Proposed  
**Issue:** #199 — Versioning infrastructure

## Context

The v0.7.0 milestone needs a single, repeatable way to stamp every source-built container with release metadata. Without a shared convention, local builds, CI builds, and tagged releases can drift, making support and debugging harder.

## Decision

Use a repo-root `VERSION` file as the default application version source, overridden by an exact git tag when present. Pass `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` through Docker Compose build args into every source-built Dockerfile, and bake them into both OCI labels and runtime environment variables.

## Rationale

- Keeps release numbering aligned with the semver tagging flow on `dev` → `main`
- Gives operators a stable fallback (`VERSION`) before a release tag exists
- Makes image provenance visible both from container registries (OCI labels) and inside running containers (`ENV`)
- Uses one metadata contract across Python, Node, and nginx-based images

## Impact

- Source-built services now share one image metadata schema
- `buildall.sh` can build tagged and untagged snapshots consistently
- CI/CD can override any of the three variables without patching Dockerfiles

## Next steps

1. Reuse the same metadata contract in release workflows that publish images
2. Surface the runtime `VERSION` in application health/status endpoints where useful


# Decision: Documentation-First Release Process

**Author:** Newt (Product Manager)  
**Date:** 2026-03-20  
**Status:** Proposed  
**Issue:** Release documentation requirements for v0.6.0 and beyond

## Context

v0.5.0 failed to include release documentation until after approval—a process failure that nearly resulted in shipping without user-facing guides. v0.6.0 shipped 5 major features but documentation was not prepared ahead of time, forcing backfill work.

To prevent this pattern, Newt proposes a formalized documentation-first release process.

## Decision

Documentation for a release must be complete and reviewed before the release ships to production. All user-facing features must have:

1. Migration guides (if applicable)
2. API or feature documentation
3. Example usage or screenshots
4. Known limitations or caveats

Documentation review is part of the release gate (see `release-gate` skill).

## Rationale

- Prevents shipping features without guidance
- Catches undocumented edge cases before release
- Makes support and feedback easier for users
- Reduces post-release documentation backfill

## Impact

- Release checklists now include documentation sign-off
- Newt has authority to block releases missing docs
- Squad members must write docs in parallel with code (not after)

## Next steps

1. Apply to v0.7.0 release planning
2. Link from release PRs to documentation PRs


---

# Archived Decisions (2026-03-20)


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
# Decision: Certbot container is optional via docker-compose.ssl.yml

**Author:** Brett (Infrastructure Architect)
**Date:** 2025-07-18
**Status:** Implemented

## Context

The certbot service and its Let's Encrypt volumes were always started by
`docker compose up`, even for deployments that run behind a reverse proxy or
on local networks without TLS. This forced operators to create
`/source/volumes/certbot-data/{conf,www}` directories even when they had no
use for them.

## Decision

All certbot/SSL configuration has been moved to `docker-compose.ssl.yml`:

- **HTTP-only (default):** `docker compose up -d`
- **With SSL:** `docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d`

The overlay adds port 443, certbot volume mounts on nginx, the periodic nginx
reload command, and the certbot sidecar container.

## Rationale

Docker Compose profiles (`profiles: ["ssl"]`) can disable services but cannot
conditionally add volume mounts or ports to other services. Since nginx needed
certbot's bind-mount volumes, profiles alone would still require the host
directories to exist. A compose overlay file cleanly isolates all SSL config.

## Impact

- **New HTTP deployments:** No change needed — `docker compose up` works.
- **Existing SSL deployments:** Add `-f docker-compose.ssl.yml` to all
  `docker compose` commands.
- Docs updated: production.md, quickstart.md, admin-manual.md,
  failover-runbook.md.

---

# User Directive: Certbot Optional

**Date:** 2026-03-19T13:10Z
**By:** jmservera (via Copilot)
**What:** Make the certbot container optional in docker-compose. Most deployments run behind a general reverse proxy or on local networks and don't need Let's Encrypt certificate management.
**Why:** User request — simplifies default deployment, reduces unnecessary container overhead.

---
