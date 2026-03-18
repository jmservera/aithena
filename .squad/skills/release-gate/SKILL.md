---
name: "release-gate"
description: "Release validation checklist and PM gate for dev→main merges"
domain: "release, quality"
confidence: "high"
source: "validated across v1.4.0–v1.7.0 release cycles"
author: "Newt"
created: "2026-03-15"
last_validated: "2026-03-18"
---

## Context

Apply before any release: merge dev→main, version tag, or release notes publication.
Newt (PM) is the release gate owner — no release without Newt's explicit approval.

**Validation enforced since v0.8.0; proven across 4 major releases (v1.4.0–v1.7.0).**

## Release Checklist (ALL must pass before approval)

### Quality Gate (CI/Tests)
1. ✅ **Milestone clear:** 0 open issues — check BOTH GitHub milestone AND issue labels
2. ✅ **All tests pass:**
   - Python services: `cd src/{service} && uv run pytest -v` (all services must pass)
   - Frontend: `cd src/aithena-ui && npm test` or `npx vitest run`
   - Typical test count: 467–628 tests (varies by release scope)
   - Per-service baseline (as of v1.7.0): solr-search 231, aithena-ui 213, document-indexer 91, document-lister 12, admin 81, embeddings-server 9
3. ✅ **Frontend builds clean:** `cd src/aithena-ui && npm run build` (Vite + TypeScript)
4. ✅ **Docker Compose validates:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
   bash -n buildall.sh
   ```

### Documentation Gate (REQUIRED — blocks release if incomplete)
5. ✅ **Release notes created:** `docs/release-notes-vX.Y.Z.md` with:
   - Summary/codename/date
   - Milestone closure (all issues listed with GitHub #)
   - Per-category changes (Dependency Upgrades, Bug Fixes, Infrastructure, etc.)
   - Merged PRs with references
   - Breaking changes (if any) with migration guidance
   - User-facing improvements
   - Operator/infrastructure improvements (if applicable)
   - Security improvements (if any)
   - Upgrade instructions and validation highlights
6. ✅ **Test report created:** `docs/test-report-vX.Y.Z.md` with:
   - Per-service test counts (e.g., solr-search 231, aithena-ui 213, ...)
   - Total test count and pass/fail/skip breakdown
   - Coverage metrics (% of critical code)
   - Regressions vs. previous release (expected: none)
   - Performance metrics if applicable (% improvement)
7. ✅ **User manual updated:** `docs/user-manual.md` with:
   - Reference updated to current release
   - New features documented with usage examples
   - Breaking changes noted (if any)
   - Shareable links to feature guide and test report
8. ✅ **Admin manual updated:** `docs/admin-manual.md` with:
   - Reference updated to current release
   - Deployment procedures (environment variables, installation steps)
   - Troubleshooting/rollback section if infrastructure changed
   - Version-specific configuration checklist
9. ✅ **CHANGELOG.md updated:** Keep a Changelog format:
   - `[vX.Y.Z] - YYYY-MM-DD` header
   - Added / Changed / Fixed / Security sections (only if applicable)
   - Cross-reference all closed issues (#123)
10. ✅ **README.md current:** Feature list and status reflect released version

## Documentation Quality Standards (v1.4.0–v1.7.0)

### Release Notes Template
```
# Release vX.Y.Z: [Codename]

**Date:** YYYY-MM-DD

## Summary
[1-3 sentences: what this release delivers]

## What's New

### [Category 1] — Issue #X, #Y
- Feature/fix description with GitHub issue references
- User or operator impact explanation

### [Category 2] — Issue #Z
...

## Milestone Closure
All X issues in the vX.Y.Z milestone have been closed.

## Merged PRs
- #NNN — Title (author)
- #OOO — Title (author)

## Breaking Changes
[If none, state "None" explicitly]

## User-Facing Improvements
[Examples: new search UI, performance gains, etc.]

## Operator Improvements
[Examples: new env vars, deployment procedures, monitoring]

## Security
[If none, state "No security changes"]

## Upgrade Instructions
[Step-by-step: docker pull, env vars, migrations, etc.]

## Validation Highlights
[Test counts, coverage %, smoke test results, etc.]

## See Also
- Feature guide: docs/features/vX.Y.Z.md (if applicable)
- Test report: docs/test-report-vX.Y.Z.md
- User manual: docs/user-manual.md
- Admin manual: docs/admin-manual.md
```

### Test Report Template
```
# Test Report — vX.Y.Z

## Summary
[Total tests, pass/fail/skip, coverage %, any notable changes]

## Per-Service Breakdown

| Service | Tests | Status | Coverage | Change from v(X-1).(Y) |
|---------|-------|--------|----------|-------------------------|
| solr-search | 231 | ✅ pass | 94.76% | — |
| aithena-ui | 213 | ✅ pass | 82% | ↑1 (i18n test added) |
| ... | ... | ... | ... | ... |

## Critical Validations
- [Regression testing result]
- [Performance improvements, if any]
- [New test coverage for features shipped]

## Known Gaps
[If any: AdminPage failures, skipped tests, etc.]
```

## Test Count Baseline (Recent Releases)

Typical range: **467–628 tests total**

| Release | Total | solr-search | aithena-ui | document-indexer | document-lister | admin | embeddings-server |
|---------|-------|---|---|---|---|---|---|
| v1.4.0 | 467 | 193 | 127 | 91 | 12 | 33 | 11 |
| v1.5.0 | 575 | 198 | 132 | 94 | 13 | 36 | 11 |
| v1.6.0 | 628 | 231 | 212 | 91 | 12 | 81 | 9 |
| v1.7.0 | 628 | 231 | 213 | 91 | 12 | 81 | 9 |

**Expectation:** Test count grows with features; regressions (significant drops) are red flags. Significant variations in per-service counts indicate test refactoring or new feature test coverage.

## Tools & Workflows

### Local Validation
```bash
# All Python tests
for dir in src/solr-search src/document-indexer src/document-lister src/admin src/embeddings-server; do
  echo "Testing $dir..."
  cd "$dir" && uv run pytest -v --tb=short && cd - || exit 1
done

# Frontend tests
cd src/aithena-ui && npm test && npm run build && cd -

# Docker Compose validation
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))" && echo "✅ Docker Compose valid"
bash -n buildall.sh && echo "✅ buildall.sh syntax valid"
```

### GitHub Actions Evidence
- All PR CI/CD jobs must pass (unit tests, linting, build)
- CI logs linked in release notes under "Validation Highlights"

### Documentation Tools
- Playwright MCP or browser tools for feature screenshots
- `gh release` for GitHub Release package creation
- `gh issue` for milestone verification

## Anti-Patterns (BLOCKING)

❌ **Don't approve a release without:**
- Feature documentation (release notes) committed
- Test report committed
- User/admin manual updates committed
- All milestone issues closed (both label AND milestone)

❌ **Don't merge dev→main without Newt's explicit sign-off**, even if CI is green

❌ **Don't skip documentation** — missing docs is a release blocker, same severity as failing tests

❌ **Don't approve with open issues in the milestone** — check both GitHub milestone view AND issue labels

❌ **Don't ship breaking changes undocumented** — v1.4.0's Python 3.12 / Node 22 / React 19 upgrades required detailed migration guides

## Acceptance Criteria for Newt's Approval

1. ✅ All checklist items (1–10) completed and verified
2. ✅ Release notes and test report follow templates above
3. ✅ No open issues in milestone (cross-check label + milestone view)
4. ✅ All tests pass locally and in CI
5. ✅ Documentation reflects actual code changes (no stale info)
6. ✅ Breaking changes justified and explained (if any)
7. ✅ Rollback procedure documented (if infrastructure/deployment changed)

**Release approved when all 7 criteria met. Newt signs off in PR review or issue comment.**

## References & Historical Context

- **v1.4.0** (2026-03-17): Dependency Upgrades & Infrastructure — 14 issues, 467 tests, Python 3.12/Node 22/React 19/ESLint 9 upgrades, 4 critical bug fixes
- **v1.5.0** (2026-03-17): Production Deployment & Infrastructure — 12 issues, 575 tests, GHCR images, install script, smoke tests, deployment procedures
- **v1.6.0** (2026-03-17): i18n Framework — Foundation for internationalization (reference point for v1.7.0)
- **v1.7.0** (2026-03-18): Quality & Infrastructure — 4 issues, 628 tests, localStorage migration, page i18n extraction, Dependabot CI improvements

All releases followed this gate and achieved zero production regressions.
