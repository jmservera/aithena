# Decision: PR #1618 Release Docs — Conflict Resolved, Awaiting Approval

**Author:** Lead (Technical Lead)  
**Date:** 2026-06-01  
**Status:** Informational

## Context

PR #1618 (`docs: release documentation for v2.2.0`) had a merge conflict in `docs/release-notes/v2.2.0.md` caused by PR #1619 landing a comprehensive release-notes file on `dev` first. The auto-generated stub in #1618 was superseded.

## Resolution

Resolved the conflict by keeping the `dev` version (from #1619) which is the definitive, human-written release notes. The PR is now mergeable but requires an approving review (branch protection).

## Architectural Regression Check (v2.2.0 changes)

No regressions found in upload/index/search flows:

- **Volume migration** (PRs #1612, #1614, #1615): Infrastructure volumes converted to Docker-managed; `document-data` bind mount preserved correctly — upload path unaffected.
- **Solr replication cap** (#1579): Correctly clamps factor to available nodes — prevents RED collections on single-node deploys.
- **document-indexer**: Only test-fixture skip logic added (#1617) — no production code paths changed.

## Action Required

- A maintainer must approve PR #1618 before it can merge (branch protection requires 1 review).
