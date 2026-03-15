# v0.5 Merge Progress — Session 2026-03-15T00:10

## Summary

Coordination round completed: 5 PRs merged to `dev` in two batches. All CI gates passed. Rebase conflict resolved (App.css). Next: address reindexing requirement from bug fix PR #174.

## Batch 1 — v0.5 Feature PRs (Ripley review: ✅ all approved)

| PR | Issue | Title | Status | Notes |
|---|---|---|---|---|
| #165 | #41 | feat(aithena-ui): add Vitest test coverage | ✅ Merged | Frontend test baseline established. CI gap: `npm run test` not in pipeline — recommend adding. Pre-existing ruff failure in solr-search unrelated. |
| #164 | #163 | feat(ui): add search mode selector (keyword/semantic/hybrid) | ✅ Merged | Search mode defaults to `keyword` until embeddings confirmed library-wide. Mode badge in UI, graceful degradation. |
| #170 | #168 | feat(ui): Add Admin tab embedding Streamlit dashboard | ✅ Merged | App.css conflict during rebase resolved. Iframe sandbox restrictive. Stop-gap before v0.6 native migration. |

## Batch 2 — v0.5 Bug Fix PRs (Ripley review: ✅ both approved)

| PR | Issue | Title | Status | Notes |
|---|---|---|---|---|
| #173 | #171 | chore(document-lister): confirm persistent state tracking + add missing test | ✅ Merged | Test-only change. Redis state tracking already working (mtime comparison, persistent volume). Minimal risk. |
| #174 | #172 | fix: language detection producing 0 results | ✅ Merged | Three bugs fixed: Solr field mismatch, missing folder-based language extraction, indexer not writing language. **REINDEX REQUIRED**. |

## Directives Captured from Merge Reviews

1. **CI Gate:** Never merge if CI has `action_required` or failing status. Verify workflows actually run (not just CodeQL).
2. **Milestones:** Always use GitHub milestones for release grouping. Never release with open milestone issues.
3. **Reindex:** After PR #174 merges, full reindex required (flush Redis `doc:*` keys + Solr collection, restart document-lister).

## Blocking Items

- ⚠️ **Frontend test CI job missing:** `npm run test` not in GitHub Actions workflow. Should be added to prevent regressions.
- ⚠️ **Reindex pending:** PR #174 requires library reindex before language facet is functional in search.

## Next Actions

- [ ] Add `npm run test` job to CI workflow
- [ ] Schedule full document reindex after #174 merges
- [ ] Monitor language facet functionality post-reindex
