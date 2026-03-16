# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
