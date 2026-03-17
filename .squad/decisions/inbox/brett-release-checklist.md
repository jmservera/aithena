# Decision: Docs-gate-the-tag release process

**Date:** 2026-07-14
**Decided by:** Brett (Infrastructure Architect), requested by Juanma (Product Owner)
**Context:** Issue #369, PR #398
**Status:** Approved

## Decision

Adopt "docs gate the tag" (Option B) as the standard release process. Release documentation must be generated and merged to `dev` BEFORE creating the version tag.

## Implementation

1. **Release issue template** (`.github/ISSUE_TEMPLATE/release.md`) provides an ordered checklist:
   - Pre-release: close milestone issues → run release-docs workflow → merge docs PR → update manuals → run tests → bump VERSION
   - Release: merge dev→main → create tag
   - Post-release: verify GitHub Release → close milestone

2. **release-docs.yml** extended to include `docs/admin-manual.md` and `docs/user-manual.md` in the Copilot CLI prompt and git add step.

3. **release.yml** (tag-triggered) remains unchanged — it builds Docker images and publishes the GitHub Release.

## Rationale

- Documentation quality is best when done before, not after, the release tag.
- The checklist formalizes the process already described in copilot-instructions but not enforced.
- Manual reviews (Newt's screenshots, manual updates) happen between doc generation and tagging.

## Impact

- **All team members:** Use the release issue template when starting a new release.
- **Newt:** Reviews generated docs PR and updates manuals with screenshots before the tag step.
- **Brett/CI:** No workflow changes needed for release.yml; release-docs.yml gets manual review scope.
