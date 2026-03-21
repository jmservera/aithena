---
name: "copilot-review-to-issues"
description: "Converting Copilot PR review comments into actionable GitHub issues"
domain: "issue-management"
confidence: "high"
source: "v1.10.1: 7 issues created from Copilot review, all fixed"
author: "Ripley"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context

When GitHub Copilot reviews a PR, it often surfaces valid concerns that don't need to block the current PR but should be tracked and addressed. Rather than losing these insights, triage them by priority and convert P0–P2 findings into GitHub issues. This was validated in v1.10.1 where 7 issues were created from Copilot review comments — all were subsequently fixed.

## Patterns

- **Triage by priority:**
  - **P0 (Security)** — SQL injection, auth bypass, credential exposure, path traversal. Must fix before release.
  - **P1 (Performance)** — N+1 queries, missing pagination, unbounded loops, sequential batch ops on large sets. Should fix in current milestone.
  - **P2 (Quality)** — Missing error handling, incomplete validation, dead code, missing tests. Fix in current or next milestone.
  - **P3 (Nice-to-have)** — Style suggestions, minor refactors, documentation improvements. Don't create issues — note in PR comments only.
- **Create issues for P0–P2** with:
  - Clear title: `[P{N}] {description} (from Copilot review)`
  - Link to the PR and specific review comment
  - Reproduction steps or code reference
  - Assign to the current milestone
- **Label issues** with appropriate priority and domain labels.
- **Track conversion rate** — note how many review comments became issues and how many were resolved.

## Examples

```markdown
## Copilot Review Triage — PR #150

| # | Comment | Priority | Action |
|---|---------|----------|--------|
| 1 | SQL injection risk in folder filter | P0 | Issue #601 created |
| 2 | Redis KEYS usage in cache clear | P1 | Issue #602 created |
| 3 | Missing error handling on file read | P2 | Issue #603 created |
| 4 | Consider using dataclass for config | P3 | Noted, no issue |
```

```bash
# Create a P1 issue from a Copilot review comment
gh issue create \
  --title "[P1] Redis uses KEYS instead of SCAN (from Copilot review)" \
  --body "Found in PR #150 review. Redis KEYS command blocks the server on large datasets. Replace with scan_iter(). Ref: https://github.com/org/repo/pull/150#discussion_r123456" \
  --milestone "v1.10.1" \
  --label "performance,squad:parker"
```

## Anti-Patterns

- **Don't create issues for P3 comments** — they clutter the backlog and distract from higher-priority work.
- **Don't ignore Copilot review comments** — even if they seem overly cautious, P0 and P1 findings are often legitimate.
- **Don't block the PR for P2 findings** — create the issue and merge the PR. Fix it in a follow-up.
- **Don't lose the link to the original review comment** — always include the discussion URL in the issue body for traceability.
