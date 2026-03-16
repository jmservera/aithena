# Decision: Accept zizmor `secrets-outside-env` findings for internal CI workflows

**Author:** Kane (Security Engineer)  
**Date:** 2026-03-16  
**Status:** Proposed  
**Issue:** #324 — SEC: Accept or remediate zizmor secrets-outside-env findings (#93, #98, #99, #102)

## Context

zizmor reported `secrets-outside-env` findings in internal GitHub Actions workflows used for release documentation, squad issue assignment, squad heartbeat automation, and release publishing. These workflows are internal CI/CD automation paths and are not production deployment workflows.

## Decision

Accept these `secrets-outside-env` findings via `.zizmor.yml` suppression for the affected workflows:

- `release-docs.yml`
- `squad-issue-assign.yml`
- `squad-heartbeat.yml`
- `release.yml`

## Rationale

- Step-level `env:` scoping is secure and sufficient for the current secret usage pattern in these workflows.
- The affected workflows are internal CI/CD helpers, not production deployment workflows.
- GitHub deployment environments are optional defense-in-depth for this scenario, not a required control for the present risk level.
- Deployment environments will be revisited when production deployment workflows exist, targeted for v1.5.0.
- Kane reviewed the findings and approved risk acceptance instead of remediating the workflow structure.

## Impact

- zizmor findings #93, #98, #99, and #102 are documented as accepted risk rather than treated as actionable vulnerabilities.
- The repository keeps `secrets-outside-env` enabled for other workflows while suppressing these known internal exceptions.
- Future production deployment workflows should use deployment environments where they materially reduce exposure.

## Next steps

1. Reassess this exception when Aithena adds production deployment workflows.
2. Remove the suppression if a future zizmor release narrows `secrets-outside-env` behavior for secure step-scoped usage.
3. Track deployment-environment hardening as part of the v1.5.0 production release workflow effort.
