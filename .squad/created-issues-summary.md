# Created Issues Summary — v1.2.0, v1.3.0, v1.4.0

**Created:** 2026-03-16
**Created by:** Ripley (Lead)
**Total Issues:** 30

## Summary Table

| # | Title | Milestone | Assignee | Priority |
|---|-------|-----------|----------|----------|
| 323 | SEC: Trigger CodeQL re-scan to close 7 stale security alerts | v1.2.0 | 🔒 kane | P1 |
| 324 | SEC: Accept or remediate zizmor secrets-outside-env findings (#93, #98, #99, #102) | v1.2.0 | 🔒 kane | P1 |
| 325 | SEC: Accept or remediate ecdsa CVE-2024-23342 baseline exception (#118) | v1.2.0 | 🔒 kane | P1 |
| 326 | SEC: Migrate python-jose to PyJWT (eliminates ecdsa dependency) | v1.2.0 | 🔧 parker | P1 |
| 328 | FE-1: Implement top-level Error Boundary with fallback UI | v1.2.0 | ⚛️ dallas | P0 |
| 329 | FE-2: Add route-based code splitting (lazy + Suspense) | v1.2.0 | ⚛️ dallas | P1 |
| 330 | FE-3: Performance audit & optimize expensive renders (React.memo, useMemo, useCallback) | v1.2.0 | ⚛️ dallas | P1 |
| 331 | FE-4: Accessibility audit with axe-core and fix violations | v1.2.0 | ⚛️ dallas | P1 |
| 332 | FE-5: Convert global CSS to CSS Modules (Components/, pages/) | v1.2.0 | ⚛️ dallas | P2 |
| 333 | FE-6: Add React DevTools Profiler instrumentation for monitoring | v1.2.0 | ⚛️ dallas | P2 |
| 334 | FE-7: Add Error Boundary unit tests and crash scenario E2E tests | v1.2.0 | 🧪 lambert | P1 |
| 335 | FE-8: Document performance best practices in frontend README | v1.2.0 | 📝 newt | P2 |
| 336 | BE-1: Add structured JSON logging to all Python services (solr-search, document-indexer, document-lister, admin) | v1.3.0 | 🔧 parker | P0 |
| 337 | BE-2: Implement admin dashboard authentication (login page + JWT) | v1.3.0 | 🔧 parker | P0 |
| 338 | BE-3: Add pytest-cov configuration and HTML coverage reports to CI | v1.3.0 | 🧪 lambert | P1 |
| 339 | BE-4: Add URL-based search state management (useSearchParams in SearchPage) | v1.3.0 | ⚛️ dallas | P1 |
| 340 | BE-5: Implement graceful degradation for Redis/Solr failures (circuit breaker pattern) | v1.3.0 | 🔧 parker | P1 |
| 341 | BE-6: Add correlation ID tracking across service boundaries | v1.3.0 | 📊 ash | P2 |
| 342 | BE-7: Create observability runbook (log analysis, debugging workflows) | v1.3.0 | 📝 newt | P2 |
| 343 | BE-8: Add integration tests for auth flow and URL state persistence | v1.3.0 | 🧪 lambert | P1 |
| 344 | DEP-1: Evaluate React 19 migration (research spike: benefits, breaking changes, migration effort) | v1.4.0 | ⚛️ dallas | P0 |
| 345 | DEP-2: Upgrade ESLint v8 → v9+ (flat config migration) | v1.4.0 | ⚛️ dallas | P1 |
| 346 | DEP-3: Audit all Python dependencies for updates (create dependency matrix) | v1.4.0 | 🔧 parker | P0 |
| 347 | DEP-4: Upgrade Python services to Python 3.12 (pyproject.toml, Dockerfiles, CI) | v1.4.0 | ⚙️ brett | P1 |
| 348 | DEP-5: Upgrade Node base images to Node 22 LTS (aithena-ui Dockerfile) | v1.4.0 | ⚙️ brett | P1 |
| 349 | DEP-6: Create automated Dependabot PR review workflow (security check + test run before merge) | v1.4.0 | ⚙️ brett | P2 |
| 350 | DEP-7: Migrate to React 19 (if DEP-1 recommends upgrade) | v1.4.0 | ⚛️ dallas | P1 |
| 351 | DEP-8: Update all Python dependencies to latest compatible versions | v1.4.0 | 🔧 parker | P1 |
| 352 | DEP-9: Run full regression test suite on upgraded stack | v1.4.0 | 🧪 lambert | P0 |
| 353 | DEP-10: Document upgrade decisions and rollback procedures | v1.4.0 | 📝 newt | P2 |

## Breakdown by Milestone

**v1.2.0 — Frontend Quality & Performance:** 12 issues
- Security Gate: 4 issues (SEC issues)
- Frontend work: 8 issues (FE-1 through FE-8)

**v1.3.0 — Backend Observability & Hardening:** 8 issues
- Backend work: 8 issues (BE-1 through BE-8)

**v1.4.0 — Dependency Modernization:** 10 issues
- Dependency work: 10 issues (DEP-1 through DEP-10)

## Notes

1. **Security Gate**: All 4 security issues (323-326) MUST be resolved before v1.2.0 release.
2. **Issue #327** was a duplicate and has been closed.
3. **Dependencies**: Critical path documented in milestone plans.
4. **Assignees**: Labels applied per squad routing table.

## Next Actions

1. Security team (Kane, Brett, Parker) starts on security gate issues
2. Frontend team (Dallas, Lambert, Newt) waits for security gate clearance
3. Backend work (v1.3.0) starts after v1.2.0 ships
4. Dependency work (v1.4.0) starts after v1.3.0 ships
