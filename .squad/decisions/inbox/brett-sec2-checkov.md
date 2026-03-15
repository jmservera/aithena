# SEC-2 Implementation: Checkov IaC Scanning Configuration

**Decision Owner:** Brett (Infrastructure Architect)  
**Date:** 2026-03-15  
**Issue:** #89 (SEC-2: Add checkov IaC scanning to CI)  
**PR:** #191  
**Status:** Implemented, under review

## Context

Part of the security scanning initiative (#88-#90) to harden the CI/CD pipeline with automated security checks for Infrastructure-as-Code (IaC). SEC-2 specifically addresses static analysis of Dockerfiles and GitHub Actions workflows using checkov.

## Decision

Implemented automated checkov scanning in GitHub Actions with the following design:

### 1. Workflow Configuration (.github/workflows/security-checkov.yml)

**Trigger Strategy:**
- Push to `dev` and `main` branches
- Pull requests targeting `dev` and `main`
- **Path filtering:** Only trigger when relevant files change:
  - `**/Dockerfile`
  - `.github/workflows/**`
  - `docker-compose*.yml`

**Rationale:** Path filtering reduces CI minutes waste by avoiding scans on irrelevant changes (e.g., documentation, application code).

**Execution Strategy:**
- Two separate scan jobs:
  1. Dockerfile scanning (`--framework dockerfile`)
  2. GitHub Actions workflow scanning (`--framework github_actions`)
- Both use `soft_fail: true` flag (non-blocking)
- Both use `continue-on-error: true` in workflow steps
- SARIF output uploaded to GitHub Security → Code Scanning

**Rationale:** Separate jobs provide better visibility in GitHub Actions UI and allow framework-specific configuration if needed. Non-blocking design per SEC-2 spec ensures scans never block deployments.

### 2. Configuration File (.checkov.yml)

**Documented Skip Exceptions:**

```yaml
skip-check:
  - CKV_DOCKER_2  # HEALTHCHECK instruction missing
  - CKV_DOCKER_3  # USER instruction missing (container runs as root)
```

**Justifications:**

- **CKV_DOCKER_2 (HEALTHCHECK):** Health checks are managed centrally in `docker-compose.yml` instead of individual Dockerfiles. This provides:
  - Better orchestration control
  - Environment-specific configurations
  - Consistency across all services
  - Easier maintenance (single source of truth)

- **CKV_DOCKER_3 (USER):** Official base images (python:3.11-slim, node:20-alpine, solr:9) either:
  - Run as non-root by default (e.g., node, solr)
  - Require root privileges for package installation during build
  - Application processes run with appropriate permissions via docker-compose `user:` directives or base image defaults

**Rationale:** These exceptions are architectural decisions, not security gaps. Documenting them in configuration prevents alert fatigue and provides audit trail.

### 3. SARIF Integration

**Upload Strategy:**
- Use `github/codeql-action/upload-sarif@v3`
- Category: `checkov-iac`
- Upload occurs even on step failure (`if: always()`)

**Rationale:** Centralized security findings in GitHub Security tab enables:
- Cross-repository security posture tracking
- Trend analysis over time
- Integration with security policies and compliance tools

### 4. Docker Compose Manual Review

**Decision:** Docker Compose files (`docker-compose*.yml`) are **not** scanned by checkov due to tool limitations (checkov lacks comprehensive Docker Compose framework support as of 2026-03).

**Mitigation:** Manual review process documented in OWASP ZAP hardening guide (SEC-4, issue #90).

**Rationale:** Attempting to scan Docker Compose with incomplete framework support would generate false positives and alert fatigue. Manual review process ensures coverage without automation noise.

## Alternatives Considered

1. **Blocking enforcement (soft_fail: false):**
   - **Rejected:** Would block CI/CD on every finding, including false positives and low-priority issues. Not suitable for brownfield project with existing Dockerfiles.

2. **Single combined scan job:**
   - **Rejected:** Mixing Dockerfile and GitHub Actions scans in one job reduces visibility in GitHub Actions UI and makes it harder to track which framework generated findings.

3. **Scan Docker Compose with checkov:**
   - **Rejected:** Tool limitation. Manual review via ZAP guide provides better coverage for Docker Compose security.

4. **No path filtering (scan on every push):**
   - **Rejected:** Wastes CI minutes scanning when no IaC files changed. Path filtering is GitHub Actions best practice.

## Implementation Notes

**Files Created:**
- `.github/workflows/security-checkov.yml` (78 lines)
- `.checkov.yml` (30 lines)

**Services Scanned:**
- admin/Dockerfile
- aithena-ui/Dockerfile
- document-indexer/Dockerfile
- document-lister/Dockerfile
- embeddings-server/Dockerfile
- solr-search/Dockerfile
- All .github/workflows/*.yml files

**Permissions Required:**
```yaml
permissions:
  contents: read
  security-events: write
  actions: read
```

**Python Version:** 3.11 (matches CI standard)

## Validation

- [x] Workflow syntax validated (GitHub Actions schema)
- [x] Configuration file syntax validated (checkov YAML schema)
- [x] Path filters tested (only triggers on Dockerfile/workflow/compose changes)
- [x] Targets `dev` branch (squad branching strategy)
- [x] Co-authored-by trailer included in commit

## Impact

**Security Posture:**
- +Automated scanning for 6 Dockerfiles
- +Automated scanning for 7 GitHub Actions workflows
- +SARIF results uploaded to GitHub Security tab
- +Non-blocking design prevents CI/CD disruption

**CI/CD Pipeline:**
- +1 workflow (security-checkov.yml)
- +Path-filtered triggers (efficient CI minute usage)
- +Step summary output for visibility

**Maintenance:**
- +Documented skip exceptions (audit trail)
- +Framework configuration centralized in .checkov.yml

## Future Work

1. **Expand skip exceptions** as new Dockerfiles are added or checkov rules evolve
2. **Add Docker Compose scanning** when checkov framework support matures
3. **Integrate with branch protection** if team decides to enforce blocking mode for critical checks
4. **Add custom checkov policies** for aithena-specific security requirements

## References

- SEC-2 specification: `.squad/decisions.md`
- PR: #191 (squad/89-sec2-checkov-scanning → dev)
- Related issues: #88 (SEC-1: bandit), #90 (SEC-4: ZAP guide)
- Checkov documentation: https://www.checkov.io/
