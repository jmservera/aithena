# Decision: Block v2.2.0 Tag After PR #1623

**Author:** Ripley (Lead)  
**Date:** 2026-06-03  
**Status:** Blocked — needs Newt version decision  
**Scope:** Release v2.2.0 after PR #1623

## Context

PR #1623 merged into `dev` after checks passed and review threads were resolved. Newt approved the release gate for v2.2.0, and PR #1624 merged the release metadata (`VERSION`, `CHANGELOG.md`, and Newt history) to `dev`.

A pre-tag audit found that `v2.2.0` already exists and has a published GitHub Release. The existing tag points to an older `dev` commit that is an ancestor of current `dev`, but it does not include the final PR #1623 work or the merged release metadata from PR #1624.

## Decision

Do not move, delete, or reuse the published `v2.2.0` tag during this release pass. Stop before dev→main/tag until Newt explicitly approves either:

1. a new patch version for the complete release commit, likely `v2.2.1`, or
2. a deliberate remediation plan for the already-published `v2.2.0` tag/release.

## Rationale

Moving an existing published tag would break release auditability and consumers that may already have pulled `v2.2.0`. Tagging current `dev` as `v2.2.0` is impossible without rewriting the existing tag, and tagging a new patch without Newt approval would bypass the release gate.

## Follow-up

Newt should issue a short release-gate addendum naming the approved patch version. After that, Ripley can resume the standard sequence: merge `dev` to `main`, tag the approved version on the release commit, push the tag, and monitor `release.yml`.
