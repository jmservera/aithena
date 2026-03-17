# Decision: Retroactive Release Documentation Process

**Date:** 2026-03-17  
**Author:** Newt (Product Manager)  
**Status:** Adopted

## Problem

Three milestones (v1.0.1, v1.1.0, v1.2.0) were completed and merged to dev, but release documentation was never created. This created a gap in the release history and left stakeholders without clear records of what was fixed, improved, or secured in each release.

## Solution

Retroactively generated comprehensive release documentation for all three milestones following the v1.0.0 release notes format:

1. **docs/release-notes-v1.0.1.md** — Security Hardening (8 issues, 4 merged PRs)
2. **docs/release-notes-v1.1.0.md** — CI/CD & Documentation (7 issues, 2 merged PRs)
3. **docs/release-notes-v1.2.0.md** — Frontend Quality & Security (14 issues, 15+ merged PRs)
4. **CHANGELOG.md** — Keep a Changelog format covering v1.0.0 through v1.2.0

## Impact

- **Historical record:** Complete release history is now documented and discoverable.
- **Stakeholder clarity:** Users, operators, and contributors can see what was delivered in each release.
- **Future reference:** Team has a clear baseline for the remaining v1.x cycle.

## Implications for future work

- **Release gate enforcement:** Going forward, release notes MUST be committed to docs/ before the release tag is created. Retroactive documentation should not be the norm.
- **Milestone tracking:** All completed milestones should have associated release notes in the PR that closes the final issue.
- **CHANGELOG maintenance:** CHANGELOG.md should be updated incrementally as releases land, not retroactively.

## Related decisions

- "Documentation-First Release Gate" (Newt, v0.8.0) — Feature guides, test reports, and manual updates must be completed before release. This decision extends to release notes themselves.
