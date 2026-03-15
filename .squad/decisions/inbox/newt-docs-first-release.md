# Decision: Documentation-First Release Process

**Author:** Newt (Product Manager)  
**Date:** 2026-03-20  
**Status:** Proposed  
**Issue:** Release documentation requirements for v0.6.0 and beyond

## Context

v0.5.0 failed to include release documentation until after approval—a process failure that nearly resulted in shipping without user-facing guides. v0.6.0 shipped 5 major features but documentation was not prepared ahead of time, forcing backfill work.

To prevent this pattern, Newt proposes a formalized documentation-first release process.

## Decision

**Feature documentation must be written and committed before release approval.**

### Required artifacts before "Ready for Release"

1. **Feature Guide** (`docs/features/vX.Y.Z.md`)
   - Shipped features with user-facing descriptions
   - Configuration changes (if any)
   - Breaking changes (if any)
   - See `docs/features/v0.6.0.md` as template

2. **User Manual Updates** (`docs/user-manual.md`)
   - New tabs, buttons, or workflows
   - Step-by-step guides for new features
   - Troubleshooting for new upload/admin flows

3. **Admin Manual Updates** (`docs/admin-manual.md`)
   - Deployment changes (new environment variables, ports, volumes)
   - Configuration tuning options
   - Monitoring and health check guidance
   - Troubleshooting for new features

4. **Test Report** (`docs/test-report-vX.Y.Z.md`)
   - Test coverage summary
   - Manual QA validation results
   - Known issues and workarounds

5. **README.md Updates**
   - Feature list must reflect shipped capabilities
   - Links to new documentation must be added
   - Screenshots must be current

### Release gate

- Newt does NOT approve release until all above artifacts are committed to `dev` branch
- PR reviewers check that documentation is present and current
- Release notes are auto-generated from feature guide and test report

### Documentation as code

- Feature guides are stored in git alongside code
- Changes to features require corresponding doc changes (checked in review)
- Documentation is reviewed as rigorously as code

## Rationale

- **User support**: Users and operators need accurate, current documentation
- **Consistency**: Same feature guide format across all releases (v0.6.0, v0.7.0, etc.)
- **Traceability**: Feature docs are versioned alongside code; easy to find docs for any tag
- **Process rigor**: Documentation is not optional or deferred

## Impact

- Adds 1–2 days to each release cycle for documentation
- Prevents user confusion and support burden
- Makes releases feel complete and professional

## Next steps

1. Formalize this decision in squad charter for Newt
2. Create a release documentation checklist (GitHub issue template)
3. Add PR check to enforce doc changes for feature PRs
