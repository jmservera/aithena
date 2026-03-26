---
name: "branch-protection-strict-mode"
description: "Handling GitHub branch protection strict mode with sequential PR merges"
domain: "git-workflow"
confidence: "high"
source: "earned from v1.10.1 PR merge cascade (7 PRs)"
author: "Ripley"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context

When branch protection requires "Require branches to be up to date before merging" (strict mode), merging one PR invalidates all other approved PRs targeting the same base branch. Each merge updates the base, pushing remaining PRs into a BEHIND state that blocks their merge. This cascading invalidation makes sequential multi-PR merges painful — discovered during v1.10.1 when 7 PRs needed to be merged into `dev`.

## Patterns

- **Use `gh pr merge --admin --merge`** to bypass the "branch is not up to date" check when status checks have already passed. The `--admin` flag overrides branch protection rules.
- **Merge in dependency order** — if PR B depends on PR A's changes, merge A first.
- **Expect cascading BEHIND states** — after merging PR 1 of N, PRs 2–N will all show as behind. This is normal and expected.
- **Retry with short delays** — GitHub needs a few seconds to update branch status after a merge. Add a 5–10 second delay between sequential merges.
- **Batch related PRs** — if multiple PRs are independent, merge them in rapid succession with `--admin` to avoid waiting for CI to re-run on each.

## Examples

```bash
# Merge 7 PRs sequentially with admin override
for pr in 101 102 103 104 105 106 107; do
  gh pr merge $pr --admin --merge
  sleep 5
done
```

```bash
# Single PR merge with admin bypass
gh pr merge 42 --admin --merge --delete-branch
```

## Anti-Patterns

- **Don't wait for CI to re-run on each PR** after the base branch updates — if checks already passed and the changes are independent, use `--admin` to merge immediately.
- **Don't rebase each PR onto the updated base** before merging — this triggers full CI re-runs and wastes time when changes are independent.
- **Don't use `--squash` when preserving individual commit history matters** — `--merge` keeps the full commit trail for traceability.
- **Don't forget that `--admin` bypasses ALL protection rules** — only use it when you've verified checks have passed and reviews are approved.
