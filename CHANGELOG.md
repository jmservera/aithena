# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **User CRUD API endpoints** — register, list, update, and delete users via `/v1/auth/` (#572)
- **Password policy enforcement** — configurable password strength requirements (#574)
- **Auth DB migration framework and backup tooling** — versioned schema migrations with backup/restore (#571)
- **User management UI** — admin-only user management page, user profile page, and change password form (#554, #555, #556, #579)
- **Password reset CLI tool** for solr-search admin operations (#547)
- **Auth API integration tests** for full authentication flow validation (#575)

### Fixed

- **Incomplete i18n translations** on Search, Library, and Upload pages (#567)
- **Stats UI service status display** incorrectly showing RabbitMQ as down (#573)
- **Vector/hybrid search errors** on empty query and 502 responses (#568)
- **Admin page infinite login loop** preventing admin access (#570)
- **Version display** corrected to show actual VERSION file value in UI (#569)

### Documentation

- **Password reset instructions** added to user and admin manuals

## [1.8.0] — 2026-03-19

### Added

- **Design tokens (CSS custom properties)** — Centralized design system for colors, typography, spacing, and shadows (#510)
- **Lucide React icon library** — Professional SVG icons replacing emoji, improving visual consistency and accessibility (#511)
- **Loading states and skeleton screens** — Intelligent loading indicators for data-fetching operations (#508)
- **Mobile-responsive design** — Responsive layout with breakpoints for phones, tablets, and desktops (#509)
- **Search rate limiting** — Redis-based rate limiting on `/v1/search` endpoint (50 requests per 15 minutes per IP) to prevent abuse (#516)
- **Improved empty and error states** — Enhanced messaging and visual design for empty searches, failed requests, and errors (#513)
- **Pre-release integration test process** — Docker Compose integration testing framework for multi-service validation (#542)
- **Screenshot automation** — Playwright-based screenshot capture and GitHub Actions workflow for UI documentation (#530, #531, #532)
- **Release documentation automation** — GitHub Actions integration with Copilot CLI for automated release notes (#523)

### Fixed

- **UI version display** — Fixed header to correctly display the running application version (#545)
- **solr-search auth directory permissions** — Corrected permissions issue on host bind mounts (#543)

### Changed

- **Repository settings** — Enabled GitHub Actions to create PRs for automated workflows (#534)

### Documentation

- **Updated user and admin manuals** to reference screenshots and new features (#533)

## [1.7.1] — 2026-03-18

### Changed

- **Embeddings-server migrated to uv** — Replaced bare `requirements.txt` with `pyproject.toml` + `uv.lock` for consistent, reproducible dependency management aligned with all other Python services (#517)
- **Docker multi-stage builds** for all services — Separates build and runtime stages, reducing final image sizes and eliminating build-time tooling from production images (#521)

### Fixed

- **document-indexer test collection error** resolved — Tests now pass cleanly (#497)
- **document-lister failing tests** resolved — Tests now pass cleanly (#498)

### Security

- **Nginx upgraded to 1.27 LTS** — Base image updated from EOL 1.15 to current stable LTS in both dev and production compose files (#518)
- **Default credentials removed** — RabbitMQ and Redis no longer fall back to `guest/guest` or empty passwords. Compose files use `${VAR:?error}` syntax to require explicit credentials. **Breaking:** `.env` must define `RABBITMQ_USER`, `RABBITMQ_PASS`, and `REDIS_PASSWORD` (#518)
- **Admin API key authentication** — All solr-search admin endpoints (`/v1/admin/*`) now require a valid `ADMIN_API_KEY` via `X-API-Key` header. **Breaking:** `ADMIN_API_KEY` environment variable must be set (#519)
- **Content-Security-Policy header** added to nginx — Restricts resource loading origins to mitigate XSS and data injection attacks (#520)

## [1.7.0] — 2026-03-18

### Added

- **Page-level internationalization** — Extracted hardcoded UI strings from all 5 page components (SearchPage, LibraryPage, UploadPage, LoginPage, AdminPage) and App.tsx to use `react-intl` for consistent multilingual rendering across all application layers (#491)
- **Dependabot PR detection in squad heartbeat** — Extended `squad-heartbeat.yml` to detect Dependabot PRs with manual-review labels, CI failures, or staleness, and route them to appropriate squad members by dependency domain (Node/frontend, Python/backend, Docker/infrastructure) (#483)

### Changed

- **Dependabot auto-merge Node 22 upgrade** — Updated `dependabot-automerge.yml` to use Node 22 (was the last Node version holdout) and replaced continue-on-error with explicit failure handling using labels and comments for transparency (#470)
- **localStorage key naming standardization** — Renamed storage key from `aithena-locale` to `aithena.locale` using dot-notation for consistency with future keys. Auto-migration logic reads the old key on first load and migrates existing users without disruption (#472)

### Fixed

- **localStorage auto-migration** — Existing users with the old `aithena-locale` key are seamlessly migrated to `aithena.locale` on first app load, preserving their language preference (#472)

### Security

- None (infrastructure and quality release)

## [1.6.0] — 2026-03-17

### Added

- **Full internationalization (i18n) support** with 4 languages: English (baseline), Spanish, Catalan, and French — 153+ locale keys extracted from all React components (#375, #376, #377, #378)
- **LanguageSwitcher UI component** in the application header with browser locale detection, localStorage persistence, and instant language switching without page reload (#379)
- **Vitest tests for i18n** validating locale switching, translation completeness across all 4 languages, localStorage persistence, and fallback behavior (#380)
- **i18n contributor guide** (`docs/i18n-guide.md`) documenting locale file structure, key naming conventions, testing requirements, and PR checklist for adding new languages (#381)
- **38 new `/v1/books` endpoint tests** covering pagination, filtering, sorting, error handling, and edge cases — solr-search now at 231 tests with 95% coverage (#471)

### Changed

- **Redis client upgrade:** redis-py upgraded from 4.x to 7.3.0 across all Python services (solr-search, document-indexer, document-lister, admin) with validated connection pooling and scan operations (#479)
- **ESLint 10 upgrade:** Major frontend linting toolchain upgrade with react-hooks 7 for stricter hook dependency checking
- **Frontend code quality:** Fixed `useRef` strictNullChecks issues and standardized URL search parameter handling across components (#469)
- **Dependency updates:** Merged Dependabot PRs for redis 7.3.0, sentence-transformers, ESLint 10, react-hooks 7, and additional security patches

### Fixed

- **useRef null reference warnings** in multiple React components when running with TypeScript strict mode (#469)
- **URL parameter inconsistencies** across search and navigation components (#469)

### Security

- **Redis 7.3.0:** Includes security fixes from redis-py 5.x and 6.x release lines
- **Dependency updates:** All Dependabot security patches merged for frontend and backend dependencies

## [1.5.0] — 2026-03-17

### Added

- **Docker image tagging and versioning strategy** for GHCR, enabling semantic version tracking and reproducible releases (#358)
- **GitHub Actions CI/CD workflow** for building and pushing production-grade Docker images to GHCR with multi-architecture support (#359)
- **Production docker-compose.yml** using pre-built GHCR images instead of local builds, enabling deployments without source code (#360)
- **Production install script** automating configuration, secret management, and deployment setup (#361)
- **Production environment variables and secrets management** with support for external vault integration (#362)
- **GitHub Release package** bundling production artifacts (compose file, install script, smoke tests) for distribution (#363)
- **Production deployment and rollback procedures documentation** providing step-by-step operator guides (#364)
- **Smoke test suite** (91 tests) validating production deployments end-to-end: service startup, health checks, inter-service connectivity, search functionality, and data persistence (#365)
- **Production nginx image and UI build optimization** for nginx reverse proxy deployment (#366)
- **GHCR authentication documentation** guiding developers and operators through credential setup and private registry access (#367)
- **Production volume mount and data persistence validation** ensuring all persistent data survives container restarts (#368)
- **Release checklist and CI/CD automation integration** documenting pre-release validation gates (#369)

### Changed

- **Deployment model:** Production deployments now use pre-built GHCR images instead of source-code-based local builds
- **Installation workflow:** Production install script automates environment configuration and replaces manual .env setup
- **Docker Compose usage:** Production deployments explicitly use `-f docker-compose.yml` without override files

### Fixed

- **Data persistence validation:** All volumes now validated and tested to ensure data survives container restarts
- **Release artifacts:** Standardized GitHub Release format with checksums and comprehensive documentation

### Security

- **Image signing and provenance:** Docker images include SBOM and security scanning results from GHCR
- **Environment variable hardening:** Production configuration supports external secret vaults; secrets not hardcoded in .env
- **Private registry RBAC:** GHCR image repositories support role-based access control via GitHub PAT authentication

## [1.4.0] — 2026-03-17

### Added

- **Python 3.12 upgrade** across all backend services (solr-search, document-indexer, document-lister, embeddings-server, admin) with 15-20% performance improvement (#347)
- **Node 22 LTS upgrade** for aithena-ui frontend with long-term support through 2026 (#348)
- **React 19 migration** with improved performance, new features, and better TypeScript support (#350)
- **ESLint v9 migration** with flat config format (eslint.config.js) replacing legacy .eslintrc.json (#345)
- **Python dependency audit** with DEP-3 matrix documenting compatibility, security patches, and upgrade priorities (#346)
- **React 19 evaluation research spike** documenting compatibility, breaking changes, ecosystem readiness, and migration effort (#344)
- **Automated Dependabot PR review workflow** reducing manual review burden by 70%+ with security checks and auto-merge for patch/minor updates (#349)
- **Full regression test suite** on upgraded stack (Python 3.12, Node 22, React 19, updated dependencies) verifying no regressions (#352)
- **Upgrade guide and rollback procedures** in v1.4.0 upgrade guide with compatibility matrix and recovery instructions (#353)
- **Parent/child document hierarchy in Solr** for accurate book counting with distinct parent documents representing books and child documents representing chunks (#404)

### Changed

- **Python version requirement:** All services now require Python 3.12 or later; Python 3.11 and earlier no longer supported
- **Node version requirement:** aithena-ui now requires Node 22 LTS or later; Node 20 and earlier no longer supported
- **ESLint configuration:** Migrated from .eslintrc.json to flat config format (eslint.config.js); .eslintrc.json removed
- **React component types:** Updated to modern patterns (function components with JSX.Element return type instead of React.FC)
- **All dependencies updated** to latest compatible versions with security patches and performance improvements
- **Stats endpoint response:** Now returns distinct book count instead of total indexed document count

### Fixed

- **Stats show indexed chunks instead of book count** (#404) — Implemented parent/child document hierarchy; stats now correctly show 3 books instead of 127 chunks
- **Library page shows empty — no books displayed** (#405) — Fixed frontend API endpoint and authentication token handling in library browse view
- **Semantic search returns 502** (#406) — Fixed vector field population, kNN query formatting for Solr 9.x, and embeddings server integration
- **release.yml Publish GitHub Release job fails** (#407) — Added missing checkout step to enable GitHub Release creation in CI workflow

### Security

- **Automated dependency scanning:** Dependabot PRs run full security checks (CodeQL, dependency scanning) before auto-merge
- **Supported language versions:** Python 3.12 and Node 22 LTS receive regular security patches from official vendors
- **Updated dependencies:** All dependencies updated to latest versions with CVE fixes and security patches

## [1.3.0] — 2026-03-17

### Added

- **Structured JSON logging** for all Python services (solr-search, document-indexer, document-lister, admin) with consistent schema, correlation IDs, and ISO 8601 timestamps (#336)
- **Admin dashboard authentication** with Streamlit login page, JWT-based sessions, bcrypt password hashing, and protected routes (#337)
- **pytest-cov configuration** with HTML coverage reports generated in CI/CD, enabling ≥80% test coverage visibility (#338)
- **URL-based search state management** using React Router's useSearchParams, enabling shareable search links with filters, sort, and pagination (#339)
- **Circuit breaker pattern** for Redis and Solr connections to enable graceful degradation on service failures (#340)
- **Correlation ID tracking** across service boundaries (HTTP headers, RabbitMQ messages, logs) for end-to-end request tracing (#341)
- **Observability runbook** documenting log analysis, request tracing with correlation IDs, and debugging workflows (#342)
- **Integration tests** for admin authentication flow and URL-based search state persistence (#343)

### Changed

- **Log output format:** All Python services now emit structured JSON logs (machine-parseable) instead of human-readable text
- **Log level configuration:** Moved to environment variable `LOG_LEVEL` (default: `INFO`) for all Python services
- **Admin dashboard access:** Now requires authentication; anonymous access to `/admin/streamlit/` redirects to login
- **Search URL structure:** Filter state preserved in URL query parameters for bookmarkable, shareable searches

### Fixed

- **Redis/Solr resilience:** Services no longer crash on connection timeouts; graceful degradation allows continued operation at reduced capacity
- **Admin auth security:** Password hashing and JWT session management prevent unauthorized access

### Security

- **Admin dashboard:** Login required; no anonymous access permitted
- **Session isolation:** JWT tokens stored in browser session state only; no persistent credentials
- **Correlation ID audit trail:** All requests tagged with UUID v4 correlation IDs for forensic investigation

## [1.2.0] — 2026-03-17

### Added

- **Error Boundary component** with fallback UI for graceful error recovery (#328)
- **Route-based code splitting** using React.lazy() and Suspense for reduced initial bundle size (#329)
- **React DevTools Profiler instrumentation** for production-ready performance monitoring (#333)
- **CSS Modules** for component-scoped styling and elimination of global style conflicts (#332)
- **Accessibility audit fixes** ensuring WCAG 2.1 Level AA compliance across all interactive elements (#331)
- **Error Boundary unit tests and crash scenario E2E tests** for validation of error recovery paths (#334)
- **Frontend performance best practices documentation** capturing optimization patterns (#335)
- **URL-based search state** for bookmarkable search results (#389)
- **Structured JSON logging** for improved observability across services (#388)
- **Admin dashboard authentication** for secure access to Streamlit admin interface (#391)
- **Circuit breaker pattern** for Redis and Solr connections to improve resilience (#392)

### Changed

- **Performance optimization** using React.memo, useMemo, and useCallback to eliminate unnecessary re-renders (#330)
- **Python-Jose to PyJWT migration** for stronger cryptographic guarantees (#326, #327)
- **Global CSS converted to CSS Modules** for improved maintainability and scoped styling (#332)
- **Embeddings-server logging** with exc_info removed to prevent stack trace exposure (#299)
- **Document-indexer logging** migrated from logger.exception() to logger.error() for cleaner output (#302)
- **Logging infrastructure** refined for production security posture (#314, #388)

### Fixed

- **solr-search container health check** in E2E CI pipeline to ensure reliable integration testing (#356)
- **CodeQL security scanning baseline** cleaned of 7 stale alerts (#323)
- **Zizmor secrets-outside-env findings** triaged and accepted as false positives or intentional patterns (#324)

### Security

- **ecdsa CVE-2024-23342:** Eliminated via Python-Jose to PyJWT migration (#325, #326)
- **PyJWT migration:** Replaces python-jose for stronger authentication baseline
- **CodeQL baseline:** 7 stale alerts closed; active scanning now clean
- **Secrets handling:** All zizmor findings categorized; false positives accepted to reduce noise (#370, #371)

## [1.1.0] — 2026-03-17

### Added

- **v1.x Development Process documentation** with branching strategy, PR workflow, and release procedures (#298)
- **E2E smoke test** for release-docs workflow to validate automated release pipeline (#306)
- **Release milestone labels** for all v1.x milestones to improve issue tracking (#305)

### Changed

- **release-docs.yml workflow:** Updated Copilot CLI package references to align with current versions (#303)
- **Embeddings-server logging:** Removed exc_info parameter to prevent stack trace exposure (#299)
- **Document-indexer logging:** Replaced logger.exception() with logger.error() (#302)

### Fixed

- **release-docs.yml configuration:** Validated end-to-end and fixed path references for reliable automation (#304)

## [1.0.1] — 2026-03-17

### Added

- **Security alert triage process** to categorize false positives and actionable findings (#297)

### Changed

- **ecdsa dependency baseline exception:** Documented accepted risk and remediation plan (#290)
- **GitHub Actions workflow hardening:** Removed insecure patterns from secrets handling (#292, #293, #294, #296)

### Fixed

- **ecdsa CVE** in solr-search dependency baseline (#290)
- **Stack trace exposure** in solr-search HTTP error responses (#291)
- **secrets-outside-env findings** in release-docs.yml (5 alerts: #98–#102) (#292)
- **secrets-outside-env in squad-heartbeat.yml** (#293)
- **secrets-outside-env in squad-issue-assign.yml** (#294)
- **CKV_GHA_7 workflow_dispatch inputs** in release-docs.yml (#296)

### Security

- Validated all security patches and dependency updates before release (#295)

## [1.0.0] — 2026-03-16

### Added

- **Repository restructure:** Moved 9 service directories under `src/` for cleaner top-level layout (#222)

### Changed

- **Documentation updated** for new `src/` layout with updated contributor instructions and validation commands (#225)
- **Service locations:** All services now under `src/` (e.g., `src/solr-search`, `src/aithena-ui`, `src/document-indexer`)

### Fixed

- **Local build and test validation** completed successfully after restructure (#223)
- **CI/CD validation** confirmed all 13 GitHub Actions workflows correct for post-restructure layout (#224)
- **Integration test volume fix:** Applied tmpfs override to preserve operability in CI (#224)

### Security

- Release validation ensures security baseline is maintained after major restructure

## [0.12.0] — 2026-03-15

### Added

- **Admin containers endpoint** returning health and version information for system status page (#202)
- **UI version footer** displaying application version in user interface (#201)

### Changed

- **Version infrastructure** established with semantic versioning and OCI image labels (#199, #204)

### Fixed

- **Version endpoint implementation** in all services for consistent versioning (#200, #203)
- **CI/CD automation** for release process including artifact signing and SBOM generation (#204)

## [0.11.0] — Previous Release

See `docs/release-notes-v0.11.0.md` for details.

## [0.10.0] — Previous Release

See `docs/release-notes-v0.10.0.md` for details.

---

**Note:** Historical versions v0.4.0 through v0.9.0 are documented in `docs/release-notes-v0.*.md` files. This CHANGELOG summarizes the most recent releases and their impact.
