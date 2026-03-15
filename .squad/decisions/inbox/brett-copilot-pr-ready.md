# Brett — Copilot PR auto-ready decision

## Context

`@copilot` opens draft PRs, finishes work, requests review, and sometimes leaves the PR in draft state. That blocks the squad because reviewable work is hidden until someone manually inspects PR status.

## Workflow review

- `squad-heartbeat.yml` does **not** listen for `pull_request` `review_requested`; it only listens for `pull_request: [closed]`, issue events, and manual dispatch.
- `squad-heartbeat.yml` currently has `pull-requests: read`, so it cannot mark PRs ready without a permission increase.
- There was no existing workflow that marks draft Copilot PRs ready when review is requested.

## Options evaluated

### Option A — Dedicated workflow on `pull_request.review_requested`
**Pros**
- Best event fidelity: reacts exactly when Copilot requests review.
- Least privilege: only needs `pull-requests: write`.
- Small and easy to audit.
- No checkout required, so it avoids running PR code.

**Cons**
- One additional workflow file.

### Option B — Extend `squad-heartbeat.yml`
**Pros**
- Reuses existing workflow.
- Fewer workflow files.

**Cons**
- Broadens Ralph's monitoring workflow with write access to pull requests.
- Mixes unrelated responsibilities (board monitoring + PR state mutation).
- Current heartbeat cadence is not a strong fallback because the schedule is disabled.

### Option C — Dedicated workflow + heartbeat fallback
**Pros**
- Highest theoretical resilience.

**Cons**
- More moving parts for a small automation.
- Heartbeat fallback is weak until the schedule is re-enabled.
- Extra maintenance for limited practical gain.

## Decision

Chosen: **Option A**.

Add a dedicated workflow, `.github/workflows/copilot-pr-ready.yml`, triggered by `pull_request` `review_requested`. When the PR author is `copilot-swe-agent[bot]`, `app/copilot-swe-agent`, or `copilot-swe-agent` and the PR is still draft, the workflow marks it ready for review using `github.rest.pulls.readyForReview()`.

## Notes

- Yes, we **could** add `review_requested` to `squad-heartbeat.yml`, but the dedicated workflow is cleaner and more secure.
- I did **not** remove `[WIP]` from PR titles. Draft state is the real workflow gate, while title rewriting is more opinionated and can surprise humans.
- If Ralph's scheduled heartbeat is re-enabled later, a lightweight fallback scan can be added then if we observe missed events in practice.
