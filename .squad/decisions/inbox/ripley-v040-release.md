# v0.4.0 Release — Merge to Main & GitHub Release

**Decision Owner:** Ripley (Lead)  
**Date:** 2026-03-14  
**Status:** ✅ COMPLETED

## Summary
Successfully merged `dev` → `main` and created v0.4.0 GitHub release. All validation gates passed; release is live.

## Actions Completed

1. ✅ **Dev Branch Finalization**
   - Pulled latest from origin/dev
   - Pushed 5 local dev commits to origin
   - Dev is synchronized with origin

2. ✅ **Merge to Main**
   - Checked out main and pulled from origin
   - Merged dev → main with `--no-ff` to preserve merge commit
   - Resolved merge conflict in `aithena-ui/package.json` (kept both `test` and `format` scripts)
   - Merge commit created with full feature changelog

3. ✅ **Release Tag & Push**
   - Created annotated tag `v0.4.0`
   - Pushed tag to origin
   - Main branch now synced to origin with all changes

4. ✅ **GitHub Release**
   - Created GitHub release for v0.4.0
   - Release notes include:
     - Backend features (status, stats endpoints)
     - Frontend features (Status/Stats tabs, PDF page navigation)
     - Tooling updates (Prettier, ESLint CI)
     - Validation summary (78/78 backend tests, PM approval)
     - Open items (#41 deferred to next milestone)

5. ✅ **Branch Management**
   - Switched back to dev
   - Cleaned up temporary files

## Release Content

**Features:**
- GET /v1/status/ — Aggregated health (Solr, Redis, RabbitMQ)
- GET /v1/stats/ — Collection statistics
- Status tab — live dashboard with auto-refresh
- Stats tab — collection overview with facets
- PDF viewer page navigation — opens at matched page
- Prettier + ESLint CI for frontend

**Validation:**
- Approved by: Newt (Product Manager)
- Backend tests: 78/78 passing
- Frontend: Build clean, types aligned, ESLint/Prettier gated
- Open items: #41 (test runner setup) deferred as non-blocking

**Release URL:** https://github.com/jmservera/aithena/releases/tag/v0.4.0

## Technical Details

- **Merge Strategy:** `--no-ff` to preserve merge commit history
- **Conflict Resolution:** aithena-ui/package.json — merged both HEAD (test script) and dev (format scripts)
- **Tag Type:** Annotated tag with release message
- **GH Release:** Created via `gh release create` with detailed release notes

## Decisions & Rationale

### Package.json Conflict Resolution
When merging, both main and dev branches modified scripts in package.json:
- **main** had: `"test": "vitest run"`
- **dev** had: `"format": "prettier --write ."` and `"format:check": "prettier --check ."`

**Decision:** Keep both sets of scripts. These represent orthogonal concerns (testing vs code formatting) and should coexist in the release.

### Release Notes Structure
Release notes follow a clear hierarchy:
1. What's New (organized by backend/frontend/tooling)
2. Open Items (transparency on deferred work)
3. Validation (proof of quality gates)

This structure is clear for users and stakeholders.

## Sign-off

**Ripley (Lead):** Release merge and tag ceremony completed successfully. v0.4.0 is live on main and GitHub.

---
*This decision will be merged into `.squad/decisions.md` by the Scribe during the next orchestration cycle.*
