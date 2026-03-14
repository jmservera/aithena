# Branch Repair Strategy — 9 Broken @copilot PRs

**Author:** Ripley (Lead)  
**Date:** 2026-03-14  
**Status:** PROPOSED

---

## Situation Assessment

All 9 PRs share the same root cause: @copilot branched from `main` (or old
`jmservera/solrstreamlitui`) instead of `dev`, then tried manual "rebases" that
actually merged or duplicated hundreds of unrelated files. The branches are 28
commits behind `dev` (some 126 behind). Most carry ghost diffs from the old repo
layout.

### What `dev` already has that these PRs re-introduce

| Feature | Already on `dev` | PR trying to add it |
|---------|-----------------|---------------------|
| ruff.toml + CI lint job | `ba81148` LINT-1 merged | #143 (redundant) |
| uv migrations (all 4 services) | #116, #129, #130, #131 | #141 (redundant CI changes) |
| /v1/stats/ endpoint + parse_stats_response | `fc2ac86` | #127, #119 (partial overlap) |
| Solr schema page_start_i / page_end_i fields | In managed-schema.xml | #137 (adds the search_service code) |
| PdfViewer component | `aithena-ui/src/Components/PdfViewer.tsx` (92 lines) | #138 (different version) |

---

## Triage: Three Categories

### 🟥 Category A — CLOSE (no salvageable value)

| PR | Reason | Effort to repair | Value of code |
|----|--------|------------------|---------------|
| **#143** Ruff in document-lister | 100% redundant — LINT-1 (#117) already merged with identical ruff.toml + CI job. PR adds a conflicting local config. | Low | **Zero** |
| **#141** buildall.sh + CI for uv | dev already has uv CI with `setup-uv@v5` + `uv sync --frozen`. PR's version is older/different. buildall.sh change is trivial (2 lines). | Low | **Near-zero** |
| **#128** Status tab UI | Branch is 28 commits behind, carries 109 files in diff. The "status tab" is 1 component + hook, but the branch would obliterate the current App.tsx (no router, flatten the faceted search UI). | High | **Low** (no router exists on dev yet, component is simple) |
| **#127** Stats tab UI | Same stale branch problem as #128. Nearly identical CSS + App.tsx changes. The CollectionStats component is ~80 lines but depends on a /stats UI contract that doesn't exist yet. | High | **Low** |
| **#119** Status endpoint | 108-file diff, 6656 insertions. Bundles frontend code, has Redis `KEYS *` perf bug, includes its own copy of uv migration. The actual `/v1/status/` endpoint is ~40 lines of useful code buried in garbage. | Very High | **Low** (one endpoint, easy to rewrite) |

**Action:** Close all 5 with a comment thanking @copilot and explaining why. Link to the replacement approach.

### 🟨 Category B — CHERRY-PICK specific code onto fresh branch

| PR | What's worth saving | How to extract |
|----|--------------------|--------------------|
| **#140** Clean up smoke test artifacts | Deletes 8 legitimate stale files (smoke screenshots, nginx-home.md/png, snapshot.md). The `.gitignore` additions are fine after narrowing the PNG pattern. Only 5 commits ahead, 7 behind — small branch, but targeted at wrong repo. | Cherry-pick the file deletions + gitignore onto a fresh `squad/140-clean-artifacts` from `dev`. Drop the broad `*.png` gitignore — use `/aithena-ui-*.png` pattern instead. ~10 min of work. |
| **#138** PDF viewer page navigation | Has page-navigation enhancement to PdfViewer (jump to specific page from search results). But it depends on #137's `pages` field in search results, and its branch is **126 commits behind** with 70 files changed. Most of the diff is re-adding files that already exist on dev. | Wait for #137 to land. Then create fresh `squad/138-pdf-page-nav` from `dev`. Cherry-pick only the PdfViewer page-jump logic (the component changes, not the entire branch). Review carefully for the `pages_i` backend field — it's unused dead code that should be dropped. ~30 min. |

### 🟩 Category C — REWRITE from scratch (faster than repair)

| PR | What to rewrite | Why rewrite beats repair |
|----|----------------|--------------------------|
| **#145** Ruff across all Python | The ruff auto-fixes are mechanical — just run `ruff check --fix . && ruff format .` from dev. The PR's branch includes fixes to deprecated qdrant-search code we already removed. | `squad/lint-ruff-autofix` from `dev`: run ruff, commit, done. 5 min. |
| **#144** Prettier + eslint on aithena-ui | Same pattern — run the formatters. The PR includes a SearchPage.tsx that doesn't exist on dev (stale code). | `squad/lint-eslint-prettier` from `dev`: add configs, run formatters, commit. 15 min. |

---

## Optimal Merge Order

```
Step 1:  #137 (approved, page ranges) — rebase onto dev, merge
         └── Unblocks #138

Step 2:  #140 (clean up artifacts) — cherry-pick onto fresh branch, merge
         └── Independent, quick win

Step 3:  #145-replacement (ruff autofix) — fresh branch, run ruff
         └── Independent, should go before any new Python code

Step 4:  #144-replacement (eslint/prettier) — fresh branch, run formatters
         └── Independent, should go before any new UI code

Step 5:  #138-replacement (PDF page nav) — cherry-pick after #137 lands
         └── Depends on #137

Step 6:  Close #143, #141, #128, #127, #119 with explanation
```

Steps 2-4 can run in parallel once Step 1 is done.

---

## Concrete Git Workflows

### For #137 (Rebase approved PR)

```bash
git fetch origin
git checkout -b squad/137-page-ranges origin/copilot/jmservera-solrsearch-return-page-numbers
git rebase origin/dev
# Resolve conflicts (mainly in search_service.py field list + normalize_book)
# The stats code is already on dev — may need to drop duplicate hunks
git push origin squad/137-page-ranges
# Open new PR targeting dev, reference #137, close old PR
```

### For #140 (Cherry-pick cleanup)

```bash
git checkout -b squad/140-clean-artifacts origin/dev
# Cherry-pick only the meaningful commits (skip merge commits):
git cherry-pick 709ccc7   # Remove smoke test artifacts
git cherry-pick 7594f4f   # Fix .gitignore pattern
# Edit .gitignore to narrow PNG pattern: /*.png → /aithena-ui-*.png
git commit --amend
git push origin squad/140-clean-artifacts
```

### For #145-replacement (Ruff autofix — fresh)

```bash
git checkout -b squad/lint-ruff-autofix origin/dev
cd /home/jmservera/source/aithena
ruff check --fix .
ruff format .
git add -A && git commit -m "style: run ruff auto-fix and format across Python services"
git push origin squad/lint-ruff-autofix
```

### For #144-replacement (ESLint/Prettier — fresh)

```bash
git checkout -b squad/lint-eslint-prettier origin/dev
cd aithena-ui
npx eslint --fix 'src/**/*.{ts,tsx}'
npx prettier --write 'src/**/*.{ts,tsx,css}'
git add -A && git commit -m "style: run eslint + prettier auto-fix on aithena-ui"
git push origin squad/lint-eslint-prettier
```

### For #138 (Cherry-pick PDF page nav — after #137 merges)

```bash
git checkout -b squad/138-pdf-page-nav origin/dev  # dev now includes #137
# Cherry-pick only the PdfViewer page-jump changes:
git cherry-pick 372eff4   # The "surgical extraction" commit
# Resolve conflicts, drop any pages_i backend additions
# Verify PdfViewer reads the `pages` field from search results
git push origin squad/138-pdf-page-nav
```

---

## Can @copilot Do These Repairs?

**Short answer: No, not safely.**

Evidence from these 9 PRs:
1. @copilot cannot manage branch targets (8/9 targeted wrong branch)
2. Its "rebases" are actually merges or full-file replacements (creates ghost diffs)
3. It bundles unrelated changes (108 files in #119 for a 40-line endpoint)
4. It duplicates work already on dev (ruff config, uv migrations)

**Recommendation:**
- **Squad members should do the rebases/cherry-picks** — these require git judgment that @copilot has proven it lacks
- @copilot CAN be assigned the **fresh rewrites** (#145-replacement, #144-replacement) IF given extremely specific instructions: exact branch name, exact base branch, exact commands to run, and explicit "do not modify any other files"
- For #137 rebase: a squad member (Parker or Ripley) should handle it — the conflict resolution in search_service.py needs human judgment about which hunks to keep

---

## Value Priority (ROI ranking)

| Priority | PR/Task | Value | Effort | ROI |
|----------|---------|-------|--------|-----|
| 1 | **#137 rebase** | High — unlocks page-level search | 20 min | ★★★★★ |
| 2 | **#145-replacement** (ruff) | Medium — code quality baseline | 5 min | ★★★★★ |
| 3 | **#144-replacement** (eslint) | Medium — code quality baseline | 15 min | ★★★★ |
| 4 | **#140 cherry-pick** | Low-medium — repo hygiene | 10 min | ★★★★ |
| 5 | **#138 cherry-pick** | Medium — PDF page navigation UX | 30 min | ★★★ |
| 6 | **Close #143, #141** | Zero cost — just close | 2 min | ★★★★★ |
| 7 | **Close #128, #127, #119** | Zero cost — just close | 5 min | ★★★★★ |

**Total estimated effort: ~1.5 hours** to repair all valuable code and close the rest.

---

## Preventive Measures

To stop this from recurring:
1. **Branch protection on `dev`**: require PRs, block force pushes
2. **Issue assignment instructions**: always include `base branch: dev` in issue body
3. **PR template**: add "Target branch: [ ] dev" checkbox
4. **Limit @copilot to single-issue PRs** — never let it bundle multiple features
5. **Auto-close PRs that target `main`** from copilot branches (GitHub Action)

---

## Summary

Of 9 broken PRs: **close 5, cherry-pick 2, rewrite 2 from scratch**. The total
salvageable code is small — maybe 200 lines of actual value across all 9 PRs.
Most of the "work" in these PRs is ghost diffs from stale branches. The fastest
path to value is: rebase #137 (approved), run formatters on fresh branches, and
close everything else.
