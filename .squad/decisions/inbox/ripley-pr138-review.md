# Ripley — PR #138 Review Decision

**Date:** 2026-07-15
**PR:** #138 — Open PDF viewer at specific page from search results
**Author:** @copilot
**Verdict:** NEEDS CHANGES

## Decision

PR #138 introduces a `pages_i` multi-valued Solr field to pass matched page numbers to the UI. However, nothing in the indexing pipeline writes `pages_i`. The existing data flow uses `page_start_i`/`page_end_i` on chunk documents (PR #136, merged), and PR #137 (approved, pending merge) already converts those to a `pages` API response field.

**Required sequence:** Merge PR #137 first, then rebase #138 and drop the `pages_i` backend plumbing. The UI changes (BookCard page display + PdfViewer `#page=N` navigation) are correct and should be kept as-is.

## Impact

- PR #138 is blocked until PR #137 merges.
- No new schema fields (`pages_i`) should be added — `page_start_i`/`page_end_i` are the source of truth.
- The `pages` key in the API response is owned by PR #137's `normalize_book()` logic.
