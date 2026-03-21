---
name: "milestone-branching-strategy"
description: "Using milestone/* branches for v1.11.0+ to enable parallel milestone work"
domain: "git-workflow"
confidence: "medium"
source: "planned for v1.11.0, not yet validated"
author: "Ripley"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context

Starting with v1.11.0, feature PRs target a `milestone/v{X.Y.Z}` branch instead of `dev` directly. This enables parallel work on multiple milestones without blocking each other. The milestone branch is merged to `dev` when all issues in the milestone are complete. This strategy has not yet been validated in practice — confidence is medium.

## Patterns

- **Create a milestone branch** from `dev` at the start of each milestone:
  ```bash
  git checkout dev && git pull
  git checkout -b milestone/v1.11.0
  git push -u origin milestone/v1.11.0
  ```
- **Feature PRs target the milestone branch**, not `dev`:
  ```bash
  gh pr create --base milestone/v1.11.0 --title "feat: ..."
  ```
- **Merge milestone branch to `dev`** when all issues are closed and the milestone gate review passes:
  ```bash
  gh pr create --base dev --head milestone/v1.11.0 --title "Merge milestone v1.11.0 to dev"
  ```
- **Parallel milestones** — multiple `milestone/*` branches can coexist:
  - `milestone/v1.11.0` — current feature work
  - `milestone/v1.10.2` — hotfix work (if needed)
- **Keep milestone branches up to date** — periodically merge `dev` into the milestone branch to reduce conflicts at merge time.

## Examples

```bash
# Full workflow for a feature in v1.11.0
git checkout milestone/v1.11.0 && git pull
git checkout -b squad/42-add-folder-filter
# ... make changes ...
gh pr create --base milestone/v1.11.0 --title "feat: add folder filter (#42)"

# When milestone is complete, merge to dev
gh pr create --base dev --head milestone/v1.11.0 \
  --title "Merge milestone v1.11.0" \
  --body "All 15 issues closed. Gate review: APPROVE."
```

## Anti-Patterns

- **Don't target `dev` directly for milestone work** — this defeats the purpose of isolation and can cause conflicts with parallel milestones.
- **Don't let milestone branches diverge too far from `dev`** — merge `dev` into the milestone branch at least weekly to catch conflicts early.
- **Don't create milestone branches for hotfixes that need immediate release** — hotfixes should go directly to `dev` (or a `hotfix/*` branch) for fast-track release.
- **Don't forget to delete the milestone branch** after merging to `dev` — stale branches cause confusion.
