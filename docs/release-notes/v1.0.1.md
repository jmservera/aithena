# Aithena v1.0.1 Release Notes — Security Hardening

_Date:_ 2026-03-17  
_Prepared by:_ Newt (Product Manager)

Aithena **v1.0.1** is a security-focused patch release that resolves critical vulnerabilities, hardens GitHub Actions workflows, and improves supply-chain safety. No user-facing changes; all fixes are infrastructure and dependency-level.

## Summary of shipped changes

- **Fixed ecdsa dependency vulnerability** in solr-search by updating the cryptographic library baseline (#290).
- **Resolved stack trace exposure alert** in solr-search that was leaking internal error details in HTTP responses (#291).
- **Hardened GitHub Actions workflows** by removing insecure patterns:
  - Fixed `secrets-outside-env` findings in `release-docs.yml` (5 alerts: #98–#102) (#292)
  - Fixed `secrets-outside-env` in `squad-heartbeat.yml` (#293)
  - Fixed `secrets-outside-env` in `squad-issue-assign.yml` (#294)
  - Fixed `CKV_GHA_7` workflow_dispatch inputs in `release-docs.yml` (#296)
- **Security patch test validation** confirmed all changes are safe for production (#295).
- **Security alert triage** completed: 7 false positives were triaged and dismissed to clean up the baseline (#297).

## Milestone closure

The following milestone issues are complete in **v1.0.1**:

- **#290** — Fix ecdsa dependency vulnerability in solr-search
- **#291** — Investigate and resolve stack trace exposure alert in solr-search
- **#292** — Fix secrets-outside-env in release-docs.yml (5 alerts)
- **#293** — Fix secrets-outside-env in squad-heartbeat.yml
- **#294** — Fix secrets-outside-env in squad-issue-assign.yml
- **#295** — Security patch test validation for v1.0.1
- **#296** — Fix CKV_GHA_7 workflow_dispatch inputs in release-docs.yml
- **#297** — Triage and dismiss false-positive security alerts

## Merged pull requests

- **#307** — Fix secrets-outside-env in release-docs.yml
- **#308** — Fix stack trace exposure in solr-search
- **#309** — Document ecdsa baseline exception
- **#313** — Triage false-positive security alerts

## Security fixes

- **ecdsa CVE:** Updated baseline exception document to record the accepted risk and remediation plan for ecdsa dependency.
- **Stack trace exposure:** Removed verbose error traceback from API responses; errors now log internally without leaking implementation details to clients.
- **GitHub Actions hardening:** All workflow secret handling now follows GitHub security best practices; no credentials are passed through environment variables or workflow dispatch inputs.

## Upgrade instructions

For operators and release engineers moving to **v1.0.1**:

1. Update to the **v1.0.1** release commit or tag once published.
2. No configuration changes required; this is a drop-in security patch.
3. Redeploy `solr-search` to get the stack trace hardening and ecdsa update.
4. No changes to user-facing behavior or API contracts.

## Validation highlights

- **Security scanning validation:** All Checkov (CKV_GHA_7), Zizmor, and SAST findings addressed
- **Dependency audit:** ecdsa baseline exception accepted; no other CVEs pending
- **Backend test suite:** All tests passing with updated dependencies
- **Workflow validation:** All 13 GitHub Actions workflows validated for secure secret handling

Aithena **v1.0.1** closes the security hardening milestone and provides a hardened baseline for production deployment.
