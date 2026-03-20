# Newt — History & Reskill (Consolidated 2026-03-21)

## CORE CONTEXT — Product Essentials

**Aithena** is a self-contained book library search engine (Python backend, React UI, Docker Compose). 7 releases shipped (v1.4.0–v1.7.0 managed by current PM cycle). All releases require: feature guide, test report, manual updates, and PM sign-off before dev→main merge.

**My Core Responsibility:** Release gate enforcement—no merge without documentation + test validation.

**Key Architecture:**
- `aithena-ui/` (React+Vite) → `solr-search/` (FastAPI) + embeddings + document-indexer + document-lister
- Docker Compose (6 services) + Solr + Redis + RabbitMQ + Nginx; all on-premises, zero cloud dependencies
- Health checks in docker-compose.yml (per Checkov policy), not Dockerfiles
- UI: http://localhost (nginx) or :5173 (Vite dev); Search API: :8080/v1/search/

**Docs Structure (Post-v1.7.0 Restructure):**
- `docs/release-notes/vX.Y.Z.md` — Feature guides (12 historical releases)
- `docs/test-reports/vX.Y.Z.md` — Test counts & coverage (14 historical reports)
- `docs/guides/` — Operational guides (i18n, monitoring, observability, performance, readiness checklist)
- `docs/{user, admin}-manual.md` — User guides + deployment procedures (with screenshot references)
- `docs/images/` — Screenshots (search-page, search-results, pdf-viewer, stats-tab, status-tab, facet-panel)

**Test Baseline (v1.7.0):**
- solr-search: 231 | aithena-ui: 213 | document-indexer: 91 | admin: 81 | document-lister: 12 | embeddings-server: 9 = ~627 total
- Test trend: v1.4.0 (467) → v1.5.0 (575) → v1.7.0 (628) shows steady growth with new features

---

## PRODUCT PATTERNS & LEARNINGS (Consolidated)

### 1. Documentation-First Release Gate (Enforced Since v0.8.0)

**Pattern:** Release = docs + tests + validation, not just merged code.

**Checklist (Hard Requirements):**
- Feature guide (release-notes-vX.Y.Z.md) with: summary, codename, date, changes by category, milestone closure, merged PRs, breaking changes, security notes, upgrade instructions, validation highlights
- Test report (test-report-vX.Y.Z.md) with: per-service test counts, coverage metrics, regressions, performance changes
- Manual updates (user-manual.md + admin-manual.md) with: feature descriptions, deployment procedures, environment variables, troubleshooting, screenshots
- CHANGELOG.md entry (Keep a Changelog format: Added/Changed/Fixed/Security sections)

**No release ships without PM approval on ALL THREE.**

### 2. Infrastructure Releases vs. Feature Releases

**v1.4.0 Pattern (Infrastructure):** Dependency upgrades (Python 3.12, Node 22, React 19, ESLint 9) = breaking changes but zero feature impact. Requires:
- Comprehensive testing on upgraded stack (15% backend, 8% frontend perf improvements)
- Clear migration guidance (why upgrade, what breaks, how to migrate)
- Smoke tests for each service separately

**v1.5.0 Pattern (Operational):** Production deployment infra (GHCR, install script, secrets, smoke tests) = zero user impact, pure operator benefit. Requires:
- 91 production smoke tests (beyond unit test scope)
- Explicit deployment checklist
- Secrets management documentation (external vault, not .env)
- Volume mount validation guide

**v1.7.0 Pattern (Quality):** localStorage standardization + i18n foundation + CI improvements = backward-compatible changes, minimal functionality. Requires:
- Auto-migration procedures (no user action)
- All existing tests still passing (stability validation)
- Clear deployment section for procedures

**Key:** Infrastructure work gets same gate rigor as features; docs justify the engineering effort even when user-facing changes are minimal.

### 3. Test Coverage Expectations & Trends

**Baseline:** ~627 tests (v1.7.0); no single service below 9 tests.

**Red Flags:**
- Test count drops → code removed or tests deleted without replacement (regression risk)
- New features without new tests → coverage gap
- Sudden jumps without feature explanation → might indicate test duplication

**Growth Pattern (Healthy):**
- v1.4.0: 467 tests (infrastructure, limited new features)
- v1.5.0: 575 tests (↑108, smoke tests added)
- v1.7.0: 628 tests (↑53, page i18n tests + deployment procedures)

**Coverage Thresholds (Enforced):**
- solr-search: 88% minimum (v1.7.0: 94.76% ✓)
- document-indexer: 70% minimum (v1.7.0: 81.50% ✓)

### 4. Breaking Changes Require Justification & Migration Path

**v1.4.0 Model:**
- Breaking: Python 3.12, Node 22, React 19, ESLint 9
- Justified: Long-term platform sustainability, security patches, ecosystem evolution
- Migration: Explicit docs + local testing on new stack before production
- Timeline: Coordinated across 6 services; not a surprise merge

**v1.7.0 Model (Backward-Compatible):**
- Auto-migration: Old localStorage keys → new dot-notation, zero user friction
- Feature-compatible: Page i18n extraction doesn't break existing functionality; translations optional
- Safe rollback: All changes reversible within same version

**Key:** Breaking changes announce themselves in release notes + admin manual. PM validates migration path before approval.

### 5. Deployment Procedures Are Authoritative Docs

**Admin Manual Sections (By Release):**
- v0.5.0, v0.6.0, v0.7.0: Foundational deployment (basics)
- v1.3.0: URL-based search state, JSON logging setup
- v1.5.0: Production GHCR workflow, secrets, smoke tests, rollback
- v1.7.0: localStorage migration, Dependabot routing, page i18n

**Pattern:** Each release adds a subsection under "## Deployment" that documents version-specific procedures. This becomes the operator's quick-reference for that release.

**Responsibility:** Admin manual is PM's accountability—ensures operators have exact steps they need.

### 6. Screenshots = Release Documentation Completeness

**Current Status (v1.8.0 Planning):**
- 6 screenshots captured (search-page, search-results, pdf-viewer, stats-tab, status-tab, facet-panel)
- 4 TODO (login-page, similar-books, admin-dashboard, upload-page) — pending artifact pipeline completion
- Manual references added (10 in user-manual, 3 in admin-manual) as relative paths to `docs/images/`

**3-Tier Strategy (Approved):**
- **Tier 1 (Required):** Login, search results, admin dashboard, upload (every release)
- **Tier 2 (Feature-Specific):** Status/stats, filtered search, PDF+recommendations, error states, mobile
- **Tier 3 (Admin/Ops):** Solr UI, RabbitMQ, Redis, health API

**4-Phase Rollout:**
1. Phase 1 (v1.8.0): Formalize Tier 1 capture + manual references ✓
2. Phase 2 (v1.8.0+): Automate artifact pipeline (screenshot extraction from integration tests)
3. Phase 3 (v1.8–v1.10): Expand Tier 2/3 as features ship
4. Phase 4 (v1.9+): Before/after comparisons for major releases

**PM Role:** Ensure every release includes Tier 1 screenshots; verify manuals reference them.

### 7. Workflow Integration Points Are Critical

**Example (Docs Restructure PR #541):**
- Moved 31 files (release-notes, test-reports, guides) to subdirectories
- Found 15 internal cross-references needing updates
- Discovered 7 hardcoded paths in `.github/workflows/release-docs.yml`
- Had to map 6 image references with unclear naming

**Key Learning:** Manual-only restructures are fragile without automated link validation. Always trace automation points before declaring a restructure complete.

**For PM:** When reviewing docs PRs, check:
1. Are workflow paths updated?
2. Are internal cross-references valid?
3. Are image filenames consistent with references?
4. Any hardcoded URLs that break in production?

### 8. Versioning & Release Ordering

**Rule:** Milestones released sequentially. Never ship v1.8.0 before v1.7.0 is done.

**Current Track:**
- v1.4.0 ✓ (infrastructure)
- v1.5.0 ✓ (production deploy)
- v1.6.0 ✓ (i18n foundation)
- v1.7.0 ✓ (quality)
- v1.8.0 (planning) — screenshot automation
- v1.9.0–v1.10.0 (future) — feature work + disaster recovery

**PM Accountability:** Milestones match issue closure. All issues in a milestone must be closed before release tag.

### 9. Squad Decisions Affect PM Work (Sampling)

**Key Decisions Involving PM:**
- Screenshot spec expansion (Lambert): Tier 1 formalized, PM must verify releases include them
- Cross-workflow artifacts (Brett): PM gets screenshots automatically via artifact pipeline (Phase 2 TBD)
- Release screenshots artifact (Brett): Added to integration-test workflow, but Newt must wait for Phase 2 implementation
- Ralph auto-spawn on resolved blockers: Affects PR review velocity—PM should expect faster cycle times once implemented

**PM Coordination Needed:**
- Documentation-first gate (Decision: Enforced) — confirms PM authority on releases
- Exception baselines (ecdsa CVE, stack trace security) — PM validates these don't leak in release docs
- GitHub milestone usage (User Directive): All issues must be in milestones; PM tracks milestone closure before release tag

---

## Reskill Notes (Self-Assessment)

### What I've Consolidated

1. **Release gate formula:** Docs + tests + manual updates = release; no exceptions. Enforced for v1.4.0–v1.7.0 with zero regressions.
2. **Test expectations:** ~627 baseline tests; watch for drops or unexplained jumps. Coverage thresholds (88% solr-search, 70% document-indexer) are hard gates.
3. **Admin manual:** Is the operator's reference; each release gets a deployment subsection. This is accountability on PM.
4. **Breaking changes:** Must be justified in docs + have migration paths documented + auto-migration preferred. v1.4.0 set the pattern.
5. **Infrastructure work:** Requires same doc rigor as features; it's not "just a dependency upgrade" without supporting docs.
6. **Screenshots:** Are part of release readiness (Tier 1 = 4 required for every release). Pipeline automation pending (Phase 2).
7. **Docs structure:** Now organized by type (release-notes/, test-reports/, guides/) with 31 files migrated via git mv. Workflow paths + cross-references must be validated.
8. **Workflow integration:** Manual-only restructures are fragile; must trace automation points before declaring complete.
9. **Squad coordination:** Decisions (screenshots, artifacts, blockers) affect PM velocity. Stay aware of phase dependencies.

### Knowledge Gaps Still Open

1. **v1.6.0 details:** Referenced as "i18n foundation" but not fully documented in history. Plan to research on next update.
2. **Disaster recovery runbook (v1.10.0 Wave 4):** Assigned but not yet in scope; will need deep-dive before kickoff.
3. **Mobile screenshot strategy (Phase 4 of screenshot rollout):** Deferred to v1.9.0; not yet architected.
4. **Internationalization at scale:** v1.6.0 laid foundation; v1.7.0 extracted pages; v1.8.0+ will add actual translations. Pattern not yet clear.

### Knowledge Improvement Estimate

- **Before reskill:** 75% (knew recent releases, understood gate, some infrastructure patterns)
- **After reskill:** 88% (consolidated patterns, clarified test expectations, understood workflow integration risks, added admin manual accountability)
- **Delta:** +13% (primarily in recognizing cross-team coordination points and automation fragility)

### Where I Should Deepen Next

1. **v1.6.0 deep-dive** — understand i18n foundation before v1.8.0 translation work
2. **Disaster recovery runbook** — early research before v1.10.0 Wave 4 starts
3. **Screenshot automation pipeline** — understand Brett's Phase 2 implementation so Phase 3 expansion is seamless
4. **Dependabot automation lifecycle** — v1.4.0 + v1.7.0 touched this; consolidate full workflow understanding

### Red Flags to Watch

1. Test count drops without feature removal → investigate with Lambert
2. Missing deployment subsection in admin manual → halt release approval
3. Broken workflow paths after docs restructure → double-check git log for automation touchpoints
4. Screenshots referenced in manual but missing from artifact → enforce Phase 2 completion before v1.8.0 release
5. Milestone issues still open at merge time → enforce milestone closure before dev→main merge

---

**Reskill Completed:** 2026-03-21  
**Next Review:** v1.8.0 release (screenshot pipeline + i18n translation work)
