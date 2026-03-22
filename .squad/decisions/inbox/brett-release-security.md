# Decision: Mandatory Security Review in Release Checklist

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**PR:** #899  
**References:** PO directive from Juanma  

## Context

The Product Owner issued two mandatory directives:
1. "New releases should always fix security issues" — security fixes are MANDATORY in every release
2. "For next releases, run a thorough security and performance review" — threat assessment before each release

## Decision

Implemented comprehensive security and performance review sections in the release checklist and templates:

### 1. Release Checklist (`docs/deployment/release-checklist.md`)

Added **Security Review (MANDATORY)** with 8 checkpoints after "Verify All Tests Pass":
- Run security scanning suite (Bandit, Checkov, Zizmor, CodeQL) on `dev`
- Review and resolve ALL open Dependabot/security alerts (critical/high MUST be fixed; medium/low documented)
- Verify no new security regressions since last release
- Run threat assessment session if significant new features were added
- Verify all security fixes from previous releases are still in place
- Check GitHub Actions workflows for supply chain risks (unpinned actions, script injection, excessive token permissions)
- Review input validation and sanitization on all new/modified API endpoints
- Document any accepted security risks in `docs/security/baseline-exceptions.md`

Added explicit note: **"A release CANNOT ship with known unresolved critical or high security issues. Security fixes are MANDATORY in every release."**

Added **Performance Review (MANDATORY)** with 4 checkpoints:
- Run benchmark suite against dev deployment
- Compare latency metrics (p50/p95/p99) against previous release baseline
- Verify no performance regressions in search, indexing, or embedding generation
- Check resource utilization (memory, CPU, disk) under expected load

### 2. Release Issue Template (`.github/ISSUE_TEMPLATE/release.md`)

Added to Pre-release section:
- [ ] Security scan clean (Bandit, Checkov, Zizmor, CodeQL — no critical/high)
- [ ] Dependabot alerts reviewed (critical/high fixed, medium/low documented)
- [ ] Threat assessment completed (if significant new features)
- [ ] Performance benchmarks show no regressions

### 3. PR Checklist (`.squad/templates/pr-checklist.md`)

Enhanced Security section:
- [ ] No new security warnings introduced (Bandit, CodeQL)
- [ ] Input validation on new API parameters

## Impact

**All team members:**
- Releases now have explicit security and performance gates
- No release can proceed without resolving critical/high findings
- New features trigger automatic threat assessment requirement

**Newt (Release Documentation):**
- Release issue template now includes security/performance checkpoints
- Release docs must include security verification status

**Security & QA:**
- Clear, auditable trail of security reviews before every release
- Documented accepted risks in baseline-exceptions.md

## Rationale

- **Security first:** Enforces PO directive that security is non-negotiable
- **Consistency:** Same checklist used across all releases
- **Transparency:** Threat assessments for new features prevent regression
- **Risk management:** Supply chain risks (GitHub Actions) explicitly reviewed
- **Performance:** Prevents silent latency/resource degradation between releases

## Related Decisions

None — this is a new control, not replacing existing process.

## Team Members Affected

- **Juanma** (PO): Directives enforced in release process
- **Newt** (Release Lead): Uses release issue template for release coordination
- **All developers:** PR checklist expanded with security/CodeQL requirements
