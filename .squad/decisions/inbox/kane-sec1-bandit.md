# SEC-1: Bandit Python Security Scanning Implementation

**Date:** 2026-03-15
**Author:** Kane (Security Engineer)
**Issue:** #88
**PR:** #193

## Decision

Implemented bandit Python SAST scanning in CI with the following configuration:

### Workflow Design
- **File:** `.github/workflows/security-bandit.yml`
- **Triggers:** Push and PR to dev/main branches
- **Non-blocking:** Uses `continue-on-error: true` to prevent CI failures
- **Permissions:** Includes `security-events: write` for SARIF upload
- **Output:** SARIF format uploaded to GitHub Code Scanning + artifact storage (30 days)

### Configuration File
- **File:** `.bandit` (centralized config)
- **Rationale:** Centralized config is more maintainable than inline command flags
- **Exclusions:** `.venv`, `venv`, `site-packages`, `node_modules`, `__pycache__`
- **Targets:** All Python source directories (document-indexer, document-lister, solr-search, admin, embeddings-server, e2e)

### Baseline Skip Rules (7 rules, 60+ pattern instances)
- **S101:** Use of assert detected - Required by pytest test framework
- **S104:** Binding to 0.0.0.0 - Legitimate for containerized services
- **S603:** subprocess call - Used in e2e tests with controlled input
- **S607:** Partial executable path - Used in e2e tests
- **S105:** Hardcoded password string - False positives in test data
- **S106:** Hardcoded password function arg - False positives in test data
- **S108:** Temp file usage - Legitimate test fixtures

## Rationale

1. **Non-blocking approach:** Allows security visibility without breaking CI, enabling gradual remediation
2. **SARIF upload:** Integrates findings into GitHub Security tab for centralized tracking
3. **Artifact retention:** 30-day SARIF storage enables historical analysis and compliance audits
4. **Skip rules:** Balance security scanning with pytest conventions and containerized deployment patterns
5. **Centralized config:** `.bandit` file provides single source of truth for baseline exceptions

## Alternatives Considered

1. **Inline skip flags in workflow:** Rejected - harder to maintain and audit
2. **Per-directory scanning:** Rejected - single scan with exclusions is simpler
3. **Blocking workflow:** Rejected - current codebase has legitimate patterns that would fail

## Impact

- **Positive:** Automated Python security scanning in CI pipeline
- **Positive:** GitHub Code Scanning integration for security dashboard
- **Positive:** Non-blocking ensures CI velocity maintained
- **Risk:** Skip rules may hide real vulnerabilities - requires SEC-5 manual triage

## Next Steps

1. Monitor first workflow run on PR merge
2. Review SARIF output in GitHub Security tab
3. Proceed with SEC-5 (baseline tuning) to triage actual findings
4. Document any HIGH/CRITICAL findings requiring fixes
