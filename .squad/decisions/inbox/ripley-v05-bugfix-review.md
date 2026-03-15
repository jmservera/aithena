# v0.5 Bug Fix PR Review — Ripley (Lead)

**Date:** 2025-07-24
**Reviewer:** Ripley (Lead)
**Requested by:** jmservera (Juanma)

---

## PR #173 — chore(document-lister): confirm persistent state tracking + add missing test

**Closes:** #171 (Document-lister re-indexes all files on restart)
**Branch:** `copilot/fix-document-lister-reindexing` → `dev`
**Verdict:** ✅ APPROVED

**Summary:** The copilot agent investigated and correctly determined that the persistent state tracking was already in place. The lister checks Redis keys (`/{QUEUE_NAME}/{path}`) with mtime comparison before enqueuing — new files are enqueued, modified files are re-enqueued only after processing, and unchanged files are skipped. Redis has a persistent volume so state survives restarts.

**Changes:** +11 lines — one new test (`test_nonexistent_path_is_skipped_gracefully`) covering the edge case where the base directory doesn't exist yet (container starts before volume mount).

**CI:** CodeQL only (4/4 passing). Test-only change — minimal risk.

**Note:** Issue #171 described symptoms that were already resolved. Good judgement not to introduce unnecessary code changes.

---

## PR #174 — fix: language detection producing 0 results

**Closes:** #172 (Language detection not working)
**Branch:** `copilot/fix-language-detection-issue` → `dev`
**Verdict:** ✅ APPROVED

**Summary:** Three independent bugs caused the language facet to always be empty. This PR fixes all three:

1. **Solr langid field mismatch:** `langid.langField` was `language_s` but the search service facets on `language_detected_s`. Renamed to match.
2. **No folder-based language extraction:** `extract_metadata()` never derived language from folder path components (e.g., `ca/`, `es/`). Added `extract_language()` with 35 ISO 639-1 codes.
3. **Indexer didn't pass language to Solr:** Both `build_literal_params()` and `build_chunk_doc()` now write `language_s` when language is present.

**Changes:** +117/-1 across 6 files. 13 new tests (parametrized folder detection, literal params, chunk docs, edge cases).

**Design:** Dual-field architecture — `language_detected_s` (Solr content analysis) + `language_s` (folder-based). Search service merges with content-detection priority. Stats facet uses `language_detected_s`.

**CI:** ⚠️ CodeQL only (4/4 passing). This PR modifies backend Python code — ruff + pytest should be run before merging. Tests look correct from diff review but haven't been CI-validated.

**Reindex required:** Yes — existing documents won't retroactively get language values. Full reindex needed (flush Redis `doc:*` keys + Solr collection, restart document-lister).

---

## Merge Recommendation

**Order:** PR #173 first (no dependencies, test-only), then PR #174 (substantive fix).

**Action needed before merge:**
- Approve the full CI workflows (ruff, pytest) in GitHub UI if they're pending workflow approval
- Verify PR #174's pytest passes, especially the new `test_metadata.py` parametrized tests
- After merging #174, schedule a full reindex of the book library
