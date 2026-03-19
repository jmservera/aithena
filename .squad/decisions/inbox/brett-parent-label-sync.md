# Decision: Enforce Parent `squad` Label on `squad:{member}` Assignment

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-18
**PR:** #539

## Context

Ralph discovers work by querying `gh issue list --label "squad"`. Issues with only a `squad:{member}` label (no parent `squad` label) are invisible. Three issues (#509, #514, #515) were missed because of this gap.

## Decision

Any workflow path that applies a `squad:{member}` label MUST also ensure the parent `squad` label is present. This is enforced in two places:

1. **`squad-issue-assign.yml`** — event-driven, adds `squad` immediately when `squad:*` fires
2. **`squad-heartbeat.yml`** — periodic audit during the member-issue scan loop

## Impact on Team

- **Ralph:** No longer misses assigned issues. Discovery query `label:squad` is now comprehensive.
- **All members:** If you apply a `squad:{member}` label manually, the parent label will be added automatically. No action needed.
- **Future workflows:** Any new workflow that applies `squad:{member}` labels should follow this pattern — always include the parent `squad` label.
