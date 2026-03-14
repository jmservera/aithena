# Page-Level Search Results + PDF Navigation

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Status:** PROPOSED
**Requested by:** jmservera (Juanma)

## Goal

Search results show which page number(s) contain matching text. Clicking opens the PDF at the correct page.

## Current State

| Component | How it works today | Page-aware? |
|---|---|---|
| **Solr Tika extraction** | PDF binary → `/update/extract` → flat `_text_` blob | ❌ Tika strips page boundaries |
| **pdfplumber `extract_pdf_text()`** | Iterates `pdf.pages` but joins into flat string | ❌ Page info discarded at join |
| **Chunker** | Word-count split with overlap, no page tracking | ❌ No page metadata |
| **Chunk docs in Solr** | `chunk_index_i`, `chunk_text_t`, `embedding_v` | ❌ No `page_number_i` |
| **Search API** | edismax on `_text_` + highlights (3 × 160-char snippets) | ❌ Highlights have no page context |
| **PDF Viewer** | `<iframe src={pdfUrl}>` | ❌ No `#page=N` fragment |

**Key finding:** Solr Tika's `/update/extract` does **not** preserve page boundaries — the extracted text is a flat blob. This is confirmed by Apache documentation. Any page-level feature must come from app-side extraction.

## Options Analysis

### Option A: Solr Nested (Child) Documents — Per-Page Indexing

Index each page as a child document under the book parent using Solr's block-join.

**Changes required:**
- Indexer: Replace Tika extraction with pdfplumber per-page extraction; post each page as a child doc
- Schema: Add `page_number_i`, `page_text_t`; configure `_root_` field for block-join
- Search API: Use `{!parent}` / `{!child}` query parsers; collect page numbers from child hits
- UI: Pass `page_number` to PdfViewer; append `#page=N` to iframe src

**Pros:** Most accurate — search directly returns page-level hits with highlights.
**Cons:** Breaks ADR-001 (Solr Tika for full-text). Nested docs add query complexity. Full re-index required. Schema migration.
**Effort:** 🔴 HIGH (3–5 days across Parker, Ash, Dallas)
**Risk:** Nested doc queries are harder to tune for relevance ranking.

### Option B: Page Markers in Tika Content

Inject `[PAGE:N]` markers into the extracted text, then parse highlights to find the nearest marker.

**Changes required:**
- Indexer: Switch to `extractOnly=true`, post-process Tika XHTML output to insert markers, then re-index
- Search API: Parse highlight snippets for `[PAGE:N]` markers
- UI: Same as Option A (pass page number)

**Pros:** Keeps parent-doc-level search; page info embedded in highlights.
**Cons:** Requires two-pass extraction (extract → parse → re-index). Markers pollute `_text_` field and affect search relevance. Fragile: markers may be split across highlight boundaries.
**Effort:** 🟡 MEDIUM-HIGH (2–3 days)
**Risk:** Marker splitting across snippet boundaries makes page detection unreliable.

### Option C: pdfplumber Per-Page Chunks (★ Recommended)

Extend the existing chunk pipeline to track page numbers. Keep Solr Tika for full-text parent doc.

**Changes required:**
- `extract_pdf_text()` → return `list[tuple[int, str]]` (page_number, page_text) instead of flat string
- `chunk_text()` → accept page-aware input, track which page(s) each chunk spans
- `build_chunk_doc()` → add `page_start_i`, `page_end_i` fields
- Schema: Add `page_start_i` (int), `page_end_i` (int) to chunk docs
- Search API: Add optional chunk-level search mode; return page numbers with results
- UI: Pass page number to PdfViewer; append `#page=N` to iframe src

**Pros:**
- Builds on existing infrastructure — pdfplumber already iterates pages, chunks already indexed
- Preserves ADR-001 — Solr Tika still handles the parent full-text doc
- Minimal schema change — just two new int fields on chunk docs
- Natural fit — chunks already carry metadata (`title_s`, `author_s`, etc.)
- Enables future "search within book" feature (query chunk docs filtered by `parent_id_s`)

**Cons:** Chunks may span page boundaries (overlap region) — `page_start_i` / `page_end_i` handles this. Requires re-indexing existing chunk docs.
**Effort:** 🟢 MEDIUM (1.5–2.5 days)
**Risk:** Low. All building blocks exist.

### Option D: Frontend-Only PDF.js Text Search

Don't track pages in the index. When user clicks a result, use PDF.js to search for the highlighted text and scroll to the matching page.

**Changes required:**
- UI: Replace iframe with PDF.js viewer; implement text search on open; scroll to match
- No indexer or API changes

**Pros:** Zero backend changes. Works with existing index.
**Cons:** Slow user experience (PDF must load + parse before page is found). Text matching may fail (highlight snippets are truncated/partial). Requires adding PDF.js dependency. Doesn't scale to "show page numbers in results list."
**Effort:** 🟢 LOW-MEDIUM (1–2 days)
**Risk:** Fragile text matching; poor UX for large PDFs.

## Comparison Matrix

| Criterion | A: Nested Docs | B: Page Markers | C: Page Chunks ★ | D: PDF.js |
|---|---|---|---|---|
| Page numbers in results list | ✅ Exact | ⚠️ Approximate | ✅ Exact (range) | ❌ Not available |
| Navigate to page on click | ✅ | ✅ | ✅ | ⚠️ Slow |
| Preserves ADR-001 (Tika full-text) | ❌ Breaks | ⚠️ Two-pass | ✅ Preserved | ✅ N/A |
| Reuses existing code | ❌ Major rewrite | ❌ New extraction path | ✅ Extends chunks | ⚠️ New PDF.js |
| Schema complexity | 🔴 High (nested) | 🟡 Medium | 🟢 Low (+2 fields) | 🟢 None |
| Query complexity | 🔴 Block-join | 🟡 Parse highlights | 🟢 Standard query | 🟢 N/A |
| Re-index required | ✅ Full | ✅ Full | ⚠️ Chunks only | ❌ No |
| Effort | 🔴 3–5 days | 🟡 2–3 days | 🟢 1.5–2.5 days | 🟢 1–2 days |

## Recommendation: Option C — Page-Aware Chunks

**Why:** It's the natural evolution of what we already have. The `extract_pdf_text()` function already iterates pages — it just throws away the page numbers. The chunk pipeline already creates per-chunk Solr docs — we just need to add `page_start_i` and `page_end_i`. The iframe PDF viewer already works — browser native PDF renderers support `#page=N` out of the box.

This preserves our ADR-001 architecture (Solr Tika for full-text, pdfplumber for embeddings) and adds page tracking with minimal risk.

## Implementation Plan

### Step 1: Page-Aware Text Extraction (Parker — 0.5 day)

Modify `extract_pdf_text()` in `__main__.py`:
```python
def extract_pdf_text(path: Path) -> list[tuple[int, str]]:
    """Extract text per page. Returns [(page_number, text), ...]."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                pages.append((i, text))
    return pages
```

### Step 2: Page-Aware Chunker (Parker — 0.5 day)

Extend `chunk_text()` to accept page-tagged input and return page ranges with each chunk:
```python
def chunk_text_paged(pages: list[tuple[int, str]], ...) -> list[dict]:
    # Returns [{"text": "...", "page_start": 1, "page_end": 2}, ...]
```

### Step 3: Chunk Docs with Page Fields (Parker + Ash — 0.5 day)

- Add `page_start_i` and `page_end_i` to `build_chunk_doc()`
- Ash: add explicit field definitions to schema (or rely on dynamic `*_i` fields)

### Step 4: Search API Page Support (Parker — 0.5 day)

- Add chunk-level search endpoint or mode: query `chunk_text_t` instead of `_text_`
- Return `page_start_i`, `page_end_i` in results
- Merge with parent doc metadata for display

### Step 5: UI Page Navigation (Dallas — 0.5 day)

- Display page range in search results: "Pages 12–13"
- Modify `PdfViewer` to append `#page=N` to iframe src URL
- No PDF.js needed — browser PDF viewers handle `#page=N` natively

### Step 6: Re-index Chunks (Lambert — 0.5 day)

- Trigger re-indexing of all chunk docs (parent docs unchanged)
- Verify page numbers in Solr

**Total effort: ~3 days** across 4 team members, parallelizable.

## Future Extensions

- **"Search within this book"**: Filter chunk docs by `parent_id_s`, show page-level results
- **Page-level highlighting in PDF**: If we add PDF.js later, we can highlight the exact text on the page
- **Table of contents**: Extract PDF bookmarks/TOC via pdfplumber for chapter-level navigation

## Dependencies

- No new Python dependencies (pdfplumber already present)
- No new JS dependencies (browser PDF viewer supports `#page=N`)
- Requires: chunk docs re-index after schema change
