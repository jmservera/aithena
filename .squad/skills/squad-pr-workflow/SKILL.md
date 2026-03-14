---
name: "squad-pr-workflow"
description: "Branch naming, PR conventions, and commit trailers for squad agents"
domain: "workflow, git"
confidence: "high"
source: "earned — extracted from copilot charter during reskill audit"
author: "Ripley"
created: "2026-07-14"
last_validated: "2026-07-14"
---

## Context

Apply when any squad agent creates branches, opens PRs, or makes commits for issue work.

## Patterns

### Branch Naming

```
squad/{issue-number}-{kebab-case-slug}
```

Example: `squad/42-fix-login-validation`

### PR Conventions

1. **Reference the issue:** `Closes #{issue-number}`
2. **If working a `squad:{member}` labeled issue:** mention the member in PR description — `Working as {member} ({role})`
3. **If 🟡 needs-review:** add `⚠️ This task was flagged as "needs review" — please have a squad member review before merging.`
4. **Commit trailer:** Always include:
   ```
   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
   ```

### Stale PR Detection

Before reviewing or rebasing a PR:

1. Check PR diff stat for unexpected deletions of recently-added files
2. Compare PR file list against current branch state
3. If PR deletes files that were recently added → DEFINITELY stale
4. **Triage heuristic:** If a PR modifies `ChatMessage.tsx`, `Configbar.tsx`, `chat.tsx`, or `qdrant-search/` → stale beyond repair, close it

### PR Base Branch

All PRs target `dev` (not `main`). The `dev` branch is the active development integration branch. Only Ripley or Juanma merge `dev` → `main` at phase boundaries.

## Anti-Patterns

- **Don't create PRs from stale branches** — always pull latest base before starting
- **Don't batch-assign issues to copilot without checking base branch freshness** — causes architecture-violating PRs
- **Don't self-merge** — all PRs require squad member review
- **Don't target `main` directly** — all feature work goes through `dev`
