# Aithena v1.7.0 Release Notes — Quality & Infrastructure

_Date:_ 2026-03-18  
_Prepared by:_ Newt (Product Manager)

Aithena **v1.7.0** is a quality and infrastructure release. It introduces Dependabot CI improvements (Node 22 upgrade in auto-merge workflow, failure handling), localStorage key naming standardization with auto-migration for existing users, Dependabot detection and routing in squad heartbeat workflow, and page-level i18n extraction for all 5 page components and App.tsx. This release strengthens CI/CD robustness, improves data persistence consistency, and extends internationalization to all remaining UI layers.

## Summary of shipped changes

### Continuous Integration & Dependabot (#470)

- **Dependabot auto-merge Node 22 upgrade** — Updated `dependabot-automerge.yml` to use Node 22 (was the last Node version holdout), removing continue-on-error from the auto-merge step and adding explicit failure handling with labels and comments for transparency (#470).

### Frontend Data Persistence (#472)

- **Standardized localStorage key naming** — Renamed `aithena-locale` to `aithena.locale` using dot-notation for consistency. Auto-migration logic reads the old key on first load and migrates to the new key, ensuring existing users retain their language preference without disruption (#472).

### Dependency Management & Squad Routing (#483)

- **Heartbeat Dependabot detection** — Extended `squad-heartbeat.yml` with detection for Dependabot PRs. The heartbeat now identifies Dependabot PRs with manual-review labels, CI failures, or staleness, and routes them to the appropriate squad member based on dependency domain (Node dependencies → frontend, Python → backend, Docker → infrastructure) (#483).

### Page-Level Internationalization (#491 — Bonus)

- **Extracted all page component strings** — Hardcoded UI strings extracted from all 5 page components (`SearchPage`, `LibraryPage`, `UploadPage`, `LoginPage`, `AdminPage`) and `App.tsx` to use `react-intl` for consistent multilingual rendering. All extracted keys are now translateable via the locale files (#491).

## Milestone closure

The following issues are complete in **v1.7.0**:

- **#470** — Dependabot CI improvements: Node 22 upgrade in auto-merge workflow, failure handling
- **#472** — Standardize localStorage key naming: Auto-migration from `aithena-locale` to `aithena.locale`
- **#483** — Heartbeat Dependabot detection: Extended with Dependabot PR identification and squad routing
- **#491** — Page i18n: Extracted hardcoded strings from all 5 page components and App.tsx (merged to dev, no separate milestone)

## Breaking changes

None. All changes are backward-compatible.

- **localStorage key migration:** The auto-migration logic ensures existing users with the old `aithena-locale` key automatically transition to `aithena.locale`. No user action required.
- **Dependabot CI:** The Node 22 upgrade and failure handling are internal to CI workflow — no impact on running services.
- **Page i18n:** New strings are now extracted but default to English, maintaining existing UI behavior until translations are added.

## User-facing improvements

- **No visible UI changes** — v1.7.0 is primarily infrastructure and quality work. End users see no functional changes; existing language preferences are seamlessly migrated.

## Operator-facing improvements

- **Dependabot routing clarity:** Operators running the squad heartbeat workflow now receive clearer signals about which Dependabot PRs need review and which squad member owns the domain.
- **localStorage consistency:** New deployments and upgrades now use the standardized `aithena.locale` key for language preference storage, reducing future refactoring complexity.

## Infrastructure improvements

- **CI/CD robustness:** Dependabot auto-merge workflow upgraded to Node 22 with explicit failure handling instead of silent continue-on-error.
- **Dependabot automation:** Enhanced heartbeat workflow detects and routes Dependabot PRs by dependency domain, improving team task distribution.
- **Internationalization foundation:** Page-level i18n extraction enables faster translation of new page features in future releases.

## Security improvements

- **No new security fixes in v1.7.0** — This is a quality and infrastructure release. Node 22 (v1.7.0 CI environment) has standard Node.js security patches.

## Upgrade instructions

For operators moving to **v1.7.0**:

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
5. No Redis or Solr upgrades required.
6. Existing user language preferences (stored under the old `aithena-locale` key) are automatically migrated to `aithena.locale` on first load.

## Validation highlights

- **localStorage auto-migration:** Tested that existing users with the old `aithena-locale` key are seamlessly migrated to `aithena.locale` on first app load.
- **Page i18n extraction:** All 5 page components and App.tsx now use `react-intl` for string rendering. English is the default language (no translation required).
- **Dependabot routing:** Heartbeat workflow correctly identifies Dependabot PRs and routes them to squad members based on dependency domain.
- **CI workflow upgrades:** Dependabot auto-merge workflow passes with Node 22, explicit failure handling working correctly.
- **All tests passing:** 632 tests executed (628 passed, 4 skipped) across 5 services, plus 9 CI-verified embeddings-server tests (641 total). No regressions from v1.6.0.

## Documentation updated for this release

- `docs/release-notes-v1.7.0.md` (this file)
- `docs/test-report-v1.7.0.md` — Full test results across all 6 services
- `docs/admin-manual.md` — v1.7.0 deployment notes
- `CHANGELOG.md` — v1.7.0 entry added

---

Aithena **v1.7.0** is a focused quality and infrastructure release. The localStorage key standardization improves data consistency, Dependabot improvements strengthen CI/CD automation, and page-level i18n extraction future-proofs the UI for rapid translation cycles. The release maintains full backward compatibility while establishing a stronger foundation for infrastructure automation and internationalization work.
