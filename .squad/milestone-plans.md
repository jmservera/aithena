# Milestone Plans — v1.2.0, v1.3.0, v1.4.0

**Version:** 1.0.0  
**Created:** 2026-03-16  
**Lead:** Ripley  
**Context:** Three post-1.0 milestones for frontend quality, backend observability, and dependency modernization

---

## ⚠️ HARD GATE: Security Issues (blocks all releases)

**Directive from Juanma:** No milestone can be released until ALL security findings are resolved.

**Status:** 10 open security findings (9 code scanning + 1 Dependabot)

### Security Issues to Create

| Priority | Title | Assignee | Type | Source Alert |
|----------|-------|----------|------|--------------|
| **P0** | SEC: Fix clear-text logging of sensitive data in installer/setup.py:517 | Kane | Code Scanning | Alert #108 (py/clear-text-logging-sensitive-data, ERROR) |
| **P0** | SEC: Fix stack trace exposure in solr-search/main.py:223 | Kane | Code Scanning | Alert #104 (py/stack-trace-exposure, ERROR) |
| **P0** | SEC: Resolve ecdsa CVE-2024-23342 (Minerva timing attack) | Kane | Dependabot | Issue #118 (HIGH severity) |
| **P1** | SEC: Address B404 subprocess warning in installer/setup.py:10 | Kane | Code Scanning | Alert #107 (B404, NOTE) |
| **P1** | SEC: Address B404 subprocess warning in e2e/test_upload_index_search.py:31 | Kane | Code Scanning | Alert #106 (B404, NOTE) |
| **P1** | SEC: Address B112 try-except-pass pattern in e2e/test_search_modes.py:149 | Lambert | Code Scanning | Alert #105 (B112, NOTE) |
| **P2** | SEC: Move secrets to env in .github/workflows/release-docs.yml:242 | Brett | Code Scanning | Alert #102 (zizmor/secrets-outside-env, WARNING) |
| **P2** | SEC: Move secrets to env in .github/workflows/release-docs.yml:161 | Brett | Code Scanning | Alert #99 (zizmor/secrets-outside-env, WARNING) |
| **P2** | SEC: Move secrets to env in .github/workflows/release-docs.yml:61 | Brett | Code Scanning | Alert #98 (zizmor/secrets-outside-env, WARNING) |
| **P2** | SEC: Move secrets to env in .github/workflows/squad-heartbeat.yml:256 | Brett | Code Scanning | Alert #93 (zizmor/secrets-outside-env, WARNING) |

**Gate Criteria:**
- All P0 issues MUST be closed before v1.2.0 ships
- All P1 issues MUST be closed before v1.2.0 ships
- P2 issues SHOULD be closed but can be accepted as tech debt with Juanma approval

**Estimated Effort:** 1-2 weeks (Kane: 5 issues, Brett: 4 issues, Lambert: 1 issue)

---

## v1.2.0 — Frontend Quality & Performance

**Theme:** Production-grade React UI with error handling, performance optimizations, accessibility, and maintainable CSS

**Target Date:** TBD (after Security Gate cleared)

### Scope

**IN SCOPE:**
- Error Boundary implementation for crash resilience
- Code splitting (route-based lazy loading)
- React.memo/useMemo/useCallback optimizations for expensive renders
- Accessibility audit & fixes (ARIA attributes, keyboard navigation, focus management)
- CSS modularization (CSS Modules or styled-components to prevent global conflicts)
- Component-level performance monitoring (React DevTools Profiler integration)

**OUT OF SCOPE:**
- React 19 upgrade (deferred to v1.4.0)
- Backend performance work (see v1.3.0)
- E2E test automation (deferred)
- Design system overhaul (use existing Bootstrap foundation)

**REQUIRES:**
- Security Gate cleared (all P0+P1 security issues resolved)

### Issues

| # | Title | Assignee | Priority | Depends On | Effort |
|---|-------|----------|----------|------------|--------|
| — | FE-1: Implement top-level Error Boundary with fallback UI | Dallas | P0 | Security Gate | 3d |
| — | FE-2: Add route-based code splitting (lazy + Suspense) | Dallas | P1 | FE-1 | 2d |
| — | FE-3: Performance audit & optimize expensive renders (React.memo, useMemo, useCallback) | Dallas | P1 | — | 5d |
| — | FE-4: Accessibility audit with axe-core and fix violations | Dallas | P1 | — | 5d |
| — | FE-5: Convert global CSS to CSS Modules (Components/, pages/) | Dallas | P2 | — | 4d |
| — | FE-6: Add React DevTools Profiler instrumentation for monitoring | Dallas | P2 | FE-3 | 2d |
| — | FE-7: Add Error Boundary unit tests and crash scenario E2E tests | Lambert | P1 | FE-1 | 3d |
| — | FE-8: Document performance best practices in frontend README | Newt | P2 | FE-3, FE-6 | 1d |

**Total Estimated Effort:** 25 days (Dallas: 21d, Lambert: 3d, Newt: 1d)

**Critical Path:** Security Gate → FE-1 → FE-2 → FE-7

**Acceptance Criteria:**
- ✅ All components wrapped in error boundaries with graceful degradation
- ✅ Bundle size reduced by 30%+ via code splitting
- ✅ No accessibility violations (WCAG 2.1 AA compliance)
- ✅ No global CSS conflicts or style leakage
- ✅ Lighthouse Performance score ≥90

---

## v1.3.0 — Backend Observability & Hardening

**Theme:** Production-ready backend with structured logging, authentication, test coverage reporting, and URL-based search state

**Target Date:** TBD (after v1.2.0)

### Scope

**IN SCOPE:**
- Structured JSON logging (replace print statements, add correlation IDs)
- Admin dashboard authentication (JWT or session-based, no anonymous access)
- Test coverage reporting (pytest-cov integration, HTML reports, CI badge)
- URL-based search state (shareable search links with filters/sort/page)
- Graceful degradation for service failures (Redis/Solr timeouts)

**OUT OF SCOPE:**
- Metrics/observability platform integration (Prometheus/Grafana deferred)
- Distributed tracing (OpenTelemetry deferred)
- Advanced RBAC (single admin role sufficient for v1.3)
- Rate limiting per-user (global rate limits already implemented)

**REQUIRES:**
- v1.2.0 shipped

### Issues

| # | Title | Assignee | Priority | Depends On | Effort |
|---|-------|----------|----------|------------|--------|
| — | BE-1: Add structured JSON logging to all Python services (solr-search, document-indexer, document-lister, admin) | Parker | P0 | — | 5d |
| — | BE-2: Implement admin dashboard authentication (login page + JWT) | Parker | P0 | — | 5d |
| — | BE-3: Add pytest-cov configuration and HTML coverage reports to CI | Lambert | P1 | — | 3d |
| — | BE-4: Add URL-based search state management (useSearchParams in SearchPage) | Dallas | P1 | — | 4d |
| — | BE-5: Implement graceful degradation for Redis/Solr failures (circuit breaker pattern) | Parker | P1 | BE-1 | 5d |
| — | BE-6: Add correlation ID tracking across service boundaries | Ash | P2 | BE-1 | 3d |
| — | BE-7: Create observability runbook (log analysis, debugging workflows) | Newt | P2 | BE-1 | 2d |
| — | BE-8: Add integration tests for auth flow and URL state persistence | Lambert | P1 | BE-2, BE-4 | 4d |

**Total Estimated Effort:** 31 days (Parker: 15d, Dallas: 4d, Ash: 3d, Lambert: 7d, Newt: 2d)

**Critical Path:** BE-1 → BE-5 → BE-6

**Acceptance Criteria:**
- ✅ All services emit structured JSON logs with timestamps, levels, correlation IDs
- ✅ Admin dashboard requires authentication (no anonymous access)
- ✅ Test coverage reports generated in CI with ≥80% coverage
- ✅ Search URLs are shareable and restore full search state
- ✅ Services degrade gracefully under Redis/Solr failures (no crashes)

---

## v1.4.0 — Dependency Modernization

**Theme:** Upgrade major dependencies, audit security posture, update container base images

**Target Date:** TBD (after v1.3.0)

### Scope

**IN SCOPE:**
- React 19 evaluation & migration (if stable and beneficial)
- ESLint major version upgrade (v8 → v9+)
- Python dependency audit (all services, check for newer versions)
- Container base image updates (Python 3.11 → 3.12+, Node 20 → 22+)
- Dependency vulnerability scan with automated Dependabot PR review workflow

**OUT OF SCOPE:**
- Vite major upgrade (currently on v8, stable)
- Python 3.13 upgrade (wait for ecosystem stability)
- Complete rewrite of any service (incremental upgrades only)
- Breaking API changes (maintain backward compatibility)

**REQUIRES:**
- v1.3.0 shipped

### Issues

| # | Title | Assignee | Priority | Depends On | Effort |
|---|-------|----------|----------|------------|--------|
| — | DEP-1: Evaluate React 19 migration (research spike: benefits, breaking changes, migration effort) | Dallas | P0 | — | 3d |
| — | DEP-2: Upgrade ESLint v8 → v9+ (flat config migration) | Dallas | P1 | — | 3d |
| — | DEP-3: Audit all Python dependencies for updates (create dependency matrix) | Parker | P0 | — | 2d |
| — | DEP-4: Upgrade Python services to Python 3.12 (pyproject.toml, Dockerfiles, CI) | Brett | P1 | DEP-3 | 5d |
| — | DEP-5: Upgrade Node base images to Node 22 LTS (aithena-ui Dockerfile) | Brett | P1 | DEP-1 | 2d |
| — | DEP-6: Create automated Dependabot PR review workflow (security check + test run before merge) | Brett | P2 | — | 3d |
| — | DEP-7: Migrate to React 19 (if DEP-1 recommends upgrade) | Dallas | P1 | DEP-1 (conditional) | 5d |
| — | DEP-8: Update all Python dependencies to latest compatible versions | Parker | P1 | DEP-3, DEP-4 | 4d |
| — | DEP-9: Run full regression test suite on upgraded stack | Lambert | P0 | DEP-7, DEP-8 | 3d |
| — | DEP-10: Document upgrade decisions and rollback procedures | Newt | P2 | DEP-9 | 2d |

**Total Estimated Effort:** 32 days (Dallas: 11d, Parker: 6d, Brett: 10d, Lambert: 3d, Newt: 2d)

**Critical Path:** DEP-1 → DEP-7 (if applicable) → DEP-9

**Acceptance Criteria:**
- ✅ All dependencies reviewed and updated to latest stable versions
- ✅ No HIGH/CRITICAL Dependabot alerts remaining
- ✅ Container base images updated to latest LTS releases
- ✅ All tests pass on upgraded stack (197+ tests green)
- ✅ Automated Dependabot workflow reduces manual review burden by 70%+

---

## Implementation Notes

### Security Gate Strategy

1. **Week 1-2:** Kane tackles P0 errors (alerts #108, #104) + Dependabot #118
2. **Week 2-3:** Kane resolves P1 warnings (alerts #107, #106); Lambert fixes alert #105
3. **Week 3:** Brett resolves P2 workflow warnings (alerts #102, #99, #98, #93)
4. **Gate review:** Juanma approves P2 tech debt acceptance or requires resolution before v1.2.0

### Milestone Sequencing

- **Security Gate** (2-3 weeks) MUST complete before v1.2.0 work begins
- **v1.2.0** (5-6 weeks) focuses on frontend quality without backend dependencies
- **v1.3.0** (6-7 weeks) builds on stable frontend with backend observability
- **v1.4.0** (6-7 weeks) performs low-risk dependency upgrades on stable foundation

**Total Timeline:** ~20-23 weeks (5-6 months from Security Gate start)

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Security Gate delayed by unclear alert context | Kane triages all alerts first week, escalates blockers to Ripley |
| React 19 migration reveals breaking changes | DEP-1 spike includes PoC migration + decision gate before DEP-7 |
| Performance optimizations break existing behavior | FE-3 requires Lambert test validation before merge |
| Coverage reporting reveals low test coverage | BE-3 acceptance requires plan to reach 80% before v1.3.0 ships |
| URL state breaks existing bookmarks | BE-4 maintains backward compatibility with old search flow |

### Review Gates

- **Security Gate:** All P0+P1 issues reviewed by Ripley before v1.2.0 kickoff
- **FE-1 (Error Boundary):** Ripley reviews implementation strategy before Dallas starts
- **BE-2 (Admin Auth):** Parker reviews auth design, Kane reviews security model
- **DEP-1 (React 19):** Dallas presents research to Juanma for upgrade decision
- **DEP-4 (Python 3.12):** Brett validates container builds, Parker validates service behavior

---

## Next Steps (Juanma Review)

1. **Approve or revise** scope for each milestone
2. **Confirm** Security Gate is acceptable blocker for all releases
3. **Prioritize** milestones if timeline needs compression (can we defer v1.4.0 dependency work?)
4. **Authorize** issue creation once plan approved

**After approval, Ripley will:**
1. Create GitHub issues for Security Gate (10 issues)
2. Create GitHub milestone `v1.2.0` with FE issues (8 issues)
3. Create GitHub milestone `v1.3.0` with BE issues (8 issues)
4. Create GitHub milestone `v1.4.0` with DEP issues (10 issues)
5. Apply `squad:{member}` labels per routing table
6. Set milestone due dates based on approved timeline

**Total Issues to Create:** 36 issues across 4 work streams
