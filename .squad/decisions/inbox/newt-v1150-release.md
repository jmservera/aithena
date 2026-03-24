# Decision: v1.15.0 Release Approval

**Author:** Newt (Product Manager)
**Date:** 2026-03-24
**Status:** Approved (pending CI)

## Context

v1.15.0 is a release-quality and CI hardening release with 29 merged PRs covering admin portal improvements, CI/CD workflow enhancements, and critical bug fixes.

## Decision

Release v1.15.0 is approved by the PM gate with the following conditions:

1. **PR #1087** (release docs) must merge to dev before the release PR #1088 is merged
2. **Merge strategy:** Use `--merge` (NOT squash) for dev→main per team convention
3. **Do NOT create the git tag manually** — the release workflow handles tagging

## Test Gate

1,939 tests across 6 services. 5 pre-existing failures (not release blockers):
- 4 metadata pattern edge cases in document-indexer
- 1 auth defaults test environment issue in admin

## Documentation Gate

All required documentation committed:
- CHANGELOG.md, release notes, test report, user manual, admin manual

## Open Items for Next Cycle

- Admin service coverage at 62% — recommend improvement to 70%+ in next milestone
- Pre-existing test failures should be tracked and fixed
