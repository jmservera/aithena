# Decision: v2.2.1 Patch Release Outcome

**Author:** Ripley (Lead)  
**Date:** 2026-06-03  
**Timestamp:** 2026-06-03T22:02:03.765+00:00  
**Status:** Completed  
**Scope:** v2.2.1 patch release after v2.2.0 tag collision

## Context

The published `v2.2.0` tag did not include the final PR #1623 E2E skeleton work or the release metadata merged by PR #1624. Newt approved a patch release path rather than moving or remediating the existing tag.

## Outcome

- `VERSION` and `CHANGELOG.md` were updated for `2.2.1` on `dev` via PR #1627.
- Release review threads were resolved with follow-up documentation fixes before promotion.
- `dev` was promoted to `main` through release PR #1625 after required checks passed and review threads were resolved.
- Annotated tag `v2.2.1` was created only after the release metadata was reachable from `main`.
- The `release.yml` workflow completed successfully and published the GitHub Release for `v2.2.1`.

## Follow-up

- PR #1638 prepares `VERSION=2.3.0-dev` for the next development cycle, but it is blocked by the `assign-work` automation check. The failure was routed to Brett because it is an infra/workflow permission issue.
- Ralph loop restarted with v2.5 as the next open milestone and #1629/#1640 as the first actionable release-backlog item.
