# Decision: Documentation as Hard Release Gate

**Date:** 2026-03-15  
**Author:** Newt (Product Manager)  
**Status:** PROPOSED — awaiting team approval

## The Problem

v0.6.0 and v0.7.0 GitHub releases were cut without finalizing documentation. This left users and operators without:

- Feature guides explaining what shipped
- User manual updates for new functionality
- Admin manual updates for deployment changes
- Test reports validating the release

Discovery happened after the releases were already published, requiring retroactive documentation work.

## The Decision

**Effective immediately, documentation is a hard gate before any release can be cut.**

The release checklist now requires:

1. ✅ Milestone clear (0 open issues)
2. ✅ All tests pass (frontend + backend)
3. ✅ Frontend builds clean
4. ✅ **Feature documentation created** (`docs/features/vX.Y.Z.md`) — **NOW REQUIRED BEFORE RELEASE**
5. ✅ **User manual updated** with new features — **NOW REQUIRED BEFORE RELEASE**
6. ✅ **Admin manual updated** if infra changed — **NOW REQUIRED BEFORE RELEASE**
7. ✅ **Test report created** (`docs/test-report-vX.Y.Z.md`) — **NOW REQUIRED BEFORE RELEASE**
8. ✅ **README feature list current** — **NOW REQUIRED BEFORE RELEASE**

## Requirements for Release Documentation

### Version Numbers (mandatory)

- **Every release doc must have the version number prominently in the title**
  - ✅ `# v0.6.0 — PDF Upload, Security Scanning, Docker Hardening`
  - ❌ `# Feature Guide` (unclear which version)

- **Feature guides should include the version in section headers where relevant**
  - ✅ `## Docker Hardening (v0.6.0)`
  - ✅ `## Versioning Infrastructure (v0.7.0)`

### Feature Documentation (`docs/features/vX.Y.Z.md`)

- Describe all major features shipped in this release
- Include implementation details, API contracts, configuration options
- Cover user-facing features and operational changes
- Validate against GitHub release notes

### Test Reports (`docs/test-report-vX.Y.Z.md`)

- Document which tests exist and their pass/fail status
- Link to CI/CD workflows or provide test execution commands
- Report coverage by area (backend, frontend, security scanning)
- Verify no regressions from previous release

### Manual Updates

- **User Manual**: Add new user-facing capabilities
- **Admin Manual**: Add deployment changes, new environment variables, configuration updates
- Both should reference the new feature guide and version numbers

### README.md

- Update the "What It Does" section with new capabilities
- Update the "Features" list
- Update the "Documentation" section to reference the latest feature guide and test report

## Implementation

All release documentation must be:

1. **Committed and merged to `dev` before the release tag is cut**
2. **Reviewed as part of the PR review process** (not backfilled after tagging)
3. **Linked in the GitHub Release** notes for discoverability

## Rollout

- **v0.6.0 and v0.7.0**: Documentation being backfilled (this is the corrective action)
- **v0.8.0 and later**: Documentation-first gate will be enforced

For v0.8.0: Ripley (Lead) will not approve the release until all documentation is committed and reviewed.

## Approval Chain

- [ ] Ripley (Lead) — approve enforcement for v0.8.0 forward
- [ ] Juanma (Product Owner) — approve as policy

## Related Documents

- `.squad/agents/newt/charter.md` — Newt's responsibility for documentation
- `docs/features/v0.6.0.md` — v0.6.0 documentation (backfilled)
- `docs/features/v0.7.0.md` — v0.7.0 documentation (backfilled)
- `docs/test-report-v0.6.0.md` — v0.6.0 test report (backfilled)
- `docs/test-report-v0.7.0.md` — v0.7.0 test report (backfilled)
