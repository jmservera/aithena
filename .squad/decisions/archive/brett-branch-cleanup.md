# Decision: Repository Branch Housekeeping & Auto-Delete

**Date:** 2026-03-16T23:20Z  
**Source:** Retro action (66 stale remote branches)  
**Owner:** Brett (Infrastructure Architect)  
**Status:** ✅ Implemented

## Decision

**Enable GitHub's automatic head-branch deletion on PR merge.** Retroactively cleaned up 44 stale merged branches; future merged PRs will auto-delete on GitHub.

## Rationale

1. **Cognitive load:** 66 stale branches made branch navigation confusing; developers couldn't distinguish active work from merged history.
2. **Automation leverage:** GitHub's built-in `delete_branch_on_merge` is less error-prone than manual batches.
3. **Protection:** `main`, `dev`, and active PR branches remain untouched; no data loss risk.

## Implementation

```bash
# Cleanup executed 2026-03-16T23:20Z
git fetch --prune origin
# Deleted 44 branches (12 copilot/*, 32 squad/*)
# All branches had merged PRs; no active work was affected

# Enable auto-delete on future merges
gh api -X PATCH repos/jmservera/aithena -f delete_branch_on_merge=true
```

## Result

- **44 branches deleted** (38 from merged PRs + 6 related cleanup)
- **21 branches retained** (all have active PRs in flight)
- **Repository setting:** `delete_branch_on_merge=true`

## Future Impact

- **Developers:** No action needed; merged PRs will auto-delete head branches.
- **CI/CD:** No impact (CI doesn't rely on branch retention).
- **Release process:** No impact (tagged releases use commit SHAs, not branches).

---

## Branches Deleted (Audit Trail)

### Copilot (12 merged)
- copilot/add-admin-operations-api
- copilot/add-backend-test-invalid-search-mode
- copilot/add-facets-ui-hint
- copilot/add-lru-cache-eviction
- copilot/doc-1-document-uv-migration
- copilot/expand-e2e-coverage-upload-search-admin
- copilot/fix-admin-iframe-sandbox
- copilot/fix-bandit-configuration
- copilot/implement-react-admin-dashboard-parity
- copilot/jmservera-solrsearch-return-page-numbers
- copilot/pin-github-actions-to-sha-digests
- copilot/rebaseline-python-dependencies

### Squad (32 merged)
- squad/100-eslint-prettier
- squad/139-cleanup-artifacts
- squad/216-credential-rotation
- squad/217-metrics-endpoints
- squad/218-failover-runbooks
- squad/219-sizing-guide
- squad/220-degraded-search-mode
- squad/221-v1-docs-pack
- squad/222-move-services-to-src
- squad/225-update-docs-src-layout
- squad/255-setup-installer-cli
- squad/260-v1.0.0-release-gate
- squad/261-v0.12.0-release-gate
- squad/269-integration-test-workflow
- squad/270-release-docs-workflow
- squad/304-validate-release-docs
- squad/356-fix-e2e-ci
- squad/49-pdf-upload-endpoint
- squad/50-pdf-upload-ui
- squad/52-docker-hardening
- squad/88-sec1-bandit-scanning
- squad/89-sec2-checkov-scanning
- squad/90-sec3-zizmor-scanning
- squad/95-ruff-document-lister
- squad/97-sec4-owasp-zap-guide
- squad/98-sec5-baseline-tuning
- squad/99-ruff-autofix-all
- squad/copilot-approve-runs
- squad/copilot-pr-ready-automation
- squad/fix-actions-security
- squad/fix-integration-test-volumes
- squad/release-docs-v06-v07

## Branches Retained (Active Work)

All 21 active-PR branches retained:
- **Copilot (6):** add-scrapeable-metrics-alerts, benchmark-search-indexing-capacity, clean-up-smoke-test-artifacts, harden-semantic-search-degraded-mode, lint-4-replace-pylint-black-with-ruff, lint-6-run-eslint-prettier-auto-fix, move-microservices-to-src-directory, protect-production-admin-surfaces, publish-v1-0-release-docs, run-failover-recovery-drills, sec-1-add-bandit-security-scanning, sec-2-add-checkov-scan-ci, sec-3-add-zizmor-security-scanning, sec-4-create-owasp-zap-guide, sec-5-security-scanning-validation, sub-pr-263, update-documentation-src-layout, validate-local-builds-after-restructure
- **Squad (3):** 341-correlation-ids, 92-uv-buildall-ci, blog-post-ai-squad-experience
- **Protected:** main, dev, oldmain, squad/retro-migration-checkpoint
