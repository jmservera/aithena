---
name: "dependabot-batch-sweep"
description: "Batch multiple Dependabot PRs into a single PR with cherry-pick + lockfile regeneration"
domain: "dependency-management"
confidence: "high"
source: "earned from PR #1584 batch sweep (16 PRs, 2026-05-31)"
author: "Ripley"
created: "2026-05-31"
last_validated: "2026-05-31"
---

## Context

When Dependabot opens many PRs simultaneously, merging them individually creates noise and CI churn. Batch them into a single PR for cleaner history and fewer CI runs.

## Recipe

### 1. Setup
```bash
git fetch origin
git worktree add ../<repo>-dependabot-<date> -b chore/dependabot-batch-<date> origin/dev
cd ../<repo>-dependabot-<date>
```

### 2. Triage
- **LOW/MEDIUM risk** (patch/minor bumps, dev deps): Include in batch
- **HIGH risk** (major versions, runtime changes like Python/Node base images): Exclude, create tracking issues

### 3. Cherry-pick
For each included PR:
```bash
branch=$(gh pr view <N> --json headRefName -q .headRefName)
git cherry-pick origin/$branch
```

**Lockfile conflicts** are expected when stacking bumps for the same service. Resolution:
```bash
git checkout --theirs <lockfile>
git add <lockfile>
git cherry-pick --continue --no-edit
```

### 4. Regenerate lockfiles
After all cherry-picks, regenerate lockfiles per service:
```bash
# Python services
cd src/<service> && uv lock

# Node services
cd src/<service> && npm install
```

Commit the regenerated lockfile separately with a clear message.

### 5. Verify
```bash
.squad/scripts/verify.sh --all
```

### 6. PR + CI + Merge
- Push branch, create PR to dev with grouped bullet list
- Watch CI: `gh pr checks <N> --watch --interval 60`
- E2E may flake (#1583) — rerun up to 3 times: `gh run rerun <id> --failed`
- Resolve review threads via GraphQL before merge
- If strict mode: merge `origin/dev` into branch before final merge
- Merge: `gh pr merge <N> --squash --delete-branch` (or `--admin` if classic protection)

### 7. Cleanup
- Close superseded PRs: `gh pr close <N> --comment "Superseded by #<batch>" --delete-branch`
- Post summary on milestone issue

## Anti-Patterns

- ❌ Don't include major version bumps (Python, Node, Solr) in low-risk batches
- ❌ Don't skip lockfile regeneration — cherry-picked lockfiles may be stale
- ❌ Don't assume `--admin` bypasses rulesets (it only bypasses classic branch protection)
- ❌ Don't forget to resolve code-scanning review threads before merge

## Gotchas

- **Squash-merge does NOT auto-close referenced PRs** — must manually close each superseded PR
- **Each push triggers new code-scanning review threads** — resolve all before merge attempt
- **Pre-commit hooks run tests during cherry-pick --continue** — may modify lockfiles (reset with `git checkout --`)
- **npm lockfiles auto-merge cleanly** more often than uv.lock; Python lockfiles almost always need regeneration
