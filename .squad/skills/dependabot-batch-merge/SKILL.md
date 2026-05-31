---
name: "dependabot-batch-merge"
description: "How to consolidate multiple dependabot PRs into a single batch without silently reverting earlier bumps"
domain: "dependency-management, git-workflows"
confidence: "low"
source: "observed"
tools:
  - name: "git"
    description: "3-way merge, conflict resolution, lockfile regeneration"
    when: "Resolving multi-branch manifest conflicts during batch merge"
---

## Context

When batching multiple dependabot branches (e.g., 17 PR chain across npm, Python, GitHub Actions), manifest files (package.json, pyproject.toml) often conflict if multiple branches touch the same file. Naive conflict resolution via `git checkout --theirs` can silently revert earlier merged bumps.

**Observed scenario (2026-05-31):**
- Batch PR #1608 consolidated 17 bumps
- Merge #1596 (pika bump to solr-search/pyproject.toml)
- Merge #1601 (uvicorn bump to solr-search/pyproject.toml)
- Later merge #1602 from branch dep-1602 which had pyproject.toml with only its own bump
- Naive `git checkout --theirs` on conflict → uvicorn + pika reverted silently
- Same pattern on package.json: npm bumps from #1594/#1595/#1599/#1600 disappeared when merging dep-1597

**Root cause:** Each dependabot branch has its own snapshot of the manifest. When merging, the incoming branch's version of the file replaces all prior changes to the same file, even if they're from already-merged branches.

## Patterns

### ❌ Anti-Pattern: Naive `--theirs`

```bash
git merge --no-ff dep-1602-pyjwt
# Conflict in src/solr-search/pyproject.toml
git checkout --theirs src/solr-search/pyproject.toml
git add src/solr-search/pyproject.toml
git commit -m "Merge PR #1602"
# Result: uvicorn + pika bumps silently gone
```

### ✅ Pattern 1: Manual 3-Way Reconciliation

For each conflicted manifest:

1. **Identify all bumps:** Extract version specs from the incoming branch + all prior merged branches that touched this file
2. **Merge bump entries:** Combine all distinct version updates into a single manifest entry
3. **Regenerate lockfile:** `uv lock` or `npm ci` to ensure consistency
4. **Verify:** Run `verify.sh` to confirm all tests pass before committing

Example (pyproject.toml conflict):

```bash
# Before merge: solr-search/pyproject.toml has pika 1.2.0, uvicorn 0.20.0
# Incoming dep-1602: has pika 1.2.0 (no change), pyjwt 2.8.0 (new bump)
# Conflict occurs because incoming version is older (has pika 1.0.0)

# Resolution:
# 1. Take incoming spec for pyjwt (2.8.0)
# 2. Keep pika 1.2.0 from current main
# 3. Keep uvicorn 0.20.0 from current main
# 4. Update pyproject.toml with all three
# 5. Run: cd src/solr-search && uv lock
# 6. Run: cd src/solr-search && uv run pytest
# 7. Commit with explicit message about what was restored
```

### ✅ Pattern 2: Higher-Level Strategy (Recommended)

**For future dependabot batch workflows:**

- **Use a 3-way merge tool** (git mergetool, VS Code merge UI) that shows incoming ∆ base ∆ current
- **Batch _before_ creating branch:** Instead of merging 17 individual branches, cherry-pick all 17 bumps onto a single worktree from main, then create _one_ PR
- **Automate lockfile regeneration:** Add a pre-commit hook that runs `uv lock` / `npm ci` whenever manifest changes

## Examples

### Recovering Lost Bumps (2026-05-31)

**Commit 4fd7ed3** — restoration after conflict gotcha:

```bash
# Identified 6 reverted bumps:
#   #1591: pika (doc-lister)
#   #1592: pika (doc-indexer)
#   #1596: pika (solr-search)
#   #1601: uvicorn (solr-search)
#   #1594/#1595/#1599/#1600: npm bumps (aithena-ui)

# Fixed by:
# 1. Manually restoring version specs from prior commits
# 2. Regenerating src/solr-search/uv.lock + src/aithena-ui/package-lock.json
# 3. Running .squad/scripts/verify.sh
# 4. Confirming 1094 backend + 841 UI tests pass

git add -A
git commit -m "chore: restore reverted bumps from earlier PRs

Re-apply bumps from #1601 (uvicorn), #1596 (pika), #1594/#1595/#1599/#1600 (npm)
which were clobbered by naive --theirs conflict resolution during batch merge.
Run local verify: 1094 backend + 841 UI tests pass."
```

## Anti-Patterns

- ❌ `git checkout --ours` or `--theirs` without reviewing what's being dropped
- ❌ Merging multiple dependabot branches without checking for overlaps in manifest files first
- ❌ Assuming `git diff` between commits will show all lost bumps (lockfile regeneration makes diffs hard to read)
- ❌ Pushing batch PR without running full `verify.sh` locally

## Related Skills

- `dependabot-batch-sweep` — The high-level strategy for batching multiple dependabot PRs. This skill focuses on tactical manifest-conflict handling during the merge phase of that workflow.
- `git-workflows` — worktrees, 3-way merges, rebase strategies
- `python-dependency-management` — uv lock regeneration, pyproject.toml semantics
- `npm-dependency-management` — npm ci, package-lock.json regeneration

## Confidence Notes

**Low confidence** — observed in one session (Ralph round 3, 2026-05-31). Pattern holds if:
1. Future batches also merge multiple overlapping manifest branches
2. Conflict resolution continues to use `--ours`/`--theirs` workflows
3. No tooling changes (e.g., git mergetool config)

If this pattern recurs in next dependabot cycle, bump to **medium** confidence.
