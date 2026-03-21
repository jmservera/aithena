# PRD: Search Results, PDF Viewer & Similar Books Redesign

**Author:** Ripley (Lead)  
**Requested by:** Juanma (jmservera)  
**Date:** 2026-03-21  
**Status:** DRAFT — Awaiting PO Review  
**Target Milestone:** v1.11.0

---

## 1. Overview

This PRD covers four interconnected improvements to the Aithena search experience:

1. **Vector search text preview** — Show the matching chunk text when semantic/hybrid search returns results
2. **PDF viewer improvements** — Full-screen mode, download button, open-in-new-window
3. **Similar books & book detail view** — Clickable similar books, book detail page with metadata
4. **Book cover thumbnails** — First-page thumbnail images in search result cards

Together these changes transform search results from a metadata-only list into a rich, browsable experience where users can preview matching text, see book covers, explore related books, and view PDFs comfortably.

---

## 2. Current State

### 2.1 Vector Search & Text Preview

**How chunking works today:**

The document-indexer performs two-phase indexing:

- **Phase 1 (Tika):** PDF is sent to Solr's `/update/extract` endpoint. Solr Tika extracts full text and indexes it as a **parent document** with id = SHA256(file_path). Parent documents store metadata (title, author, year, category) and full text in `content`/`_text_` fields.

- **Phase 2 (Chunking + Embedding):** The indexer separately extracts text page-by-page using `pdfplumber`, then splits it into chunks using a word-based sliding window:
  - **Chunk size:** 400 words (configurable via `CHUNK_SIZE` env var)
  - **Overlap:** 50 words (configurable via `CHUNK_OVERLAP` env var)
  - **Stride:** 350 words per step
  - Each chunk tracks `page_start` and `page_end` (which PDF pages it spans)

Each chunk is indexed as a separate Solr document with:
| Field | Description |
|-------|-------------|
| `id` | `{parent_id}_chunk_{index:04d}` |
| `parent_id_s` | Links to parent document |
| `chunk_index_i` | Sequential position (0, 1, 2…) |
| `chunk_text_t` | **Full chunk text — stored and indexed in Solr** |
| `embedding_v` | 512-dim vector from `distiluse-base-multilingual-cased-v2` |
| `page_start_i` / `page_end_i` | Page range covered by chunk |
| Inherited metadata | `title_s`, `author_s`, `category_s`, `year_i`, `file_path_s`, `folder_path_s` |

**The gap:** The chunk text IS stored in Solr (`chunk_text_t` field is `stored="true"` in the managed schema), but it is **not returned in search results**. The `SOLR_FIELD_LIST` in `search_service.py` does not include `chunk_text_t`. The `normalize_book()` function does not extract or pass chunk text to the API response. The frontend `BookResult` TypeScript type has no field for chunk text.

**Search modes:**
- **Keyword search:** Queries parent documents only (chunks excluded via `-parent_id_s:[* TO *]` filter). Returns highlights from Solr's unified highlighter against `_text_`/`content` fields.
- **Semantic search:** Queries chunk documents via kNN on `embedding_v`. Returns chunk-level results with `page_start_i`/`page_end_i` but **no chunk text and no highlighting**.
- **Hybrid search:** Runs both, merges via Reciprocal Rank Fusion (RRF, k=60). Keyword results have highlights; semantic results do not.

**Bottom line:** The infrastructure to show chunk text previews is 80% built. The chunk text is stored, the page ranges are tracked, we just don't retrieve it or display it.

### 2.2 PDF Viewer

**Current implementation** (`src/aithena-ui/src/Components/PdfViewer.tsx`):

- **Side panel overlay:** Fixed position, right-aligned, width `min(740px, 90vw)`
- **Rendering:** `<iframe>` pointing to the document URL with optional `#page={N}` anchor
- **Controls:** Only a close button (✕) and ESC key handler
- **Missing:** No fullscreen toggle, no download button, no open-in-new-window button
- **Accessibility:** Good — ARIA modal dialog, focus trapping, tab management, escape key
- **Error handling:** Shows fallback message with "Open in New Tab" link if iframe fails

The 740px max width is often too small for complex PDFs with diagrams, tables, or multi-column layouts.

### 2.3 Similar Books

**Current implementation** (`src/aithena-ui/src/Components/SimilarBooks.tsx`):

- **API:** `GET /v1/books/{documentId}/similar` — uses kNN on `book_embedding` field (parent-level embedding), returns up to 5 results with cosine similarity scores
- **Display:** Horizontal scrollable row of 240px-wide cards below search results
- **When shown:** Only when a book is selected (i.e., PDF viewer is open)
- **Card content:** Title, author, year, category, similarity percentage badge
- **Clicking:** Cards ARE clickable — `onSelectBook(book.id)` switches the PDF viewer to that book
- **Visual issue:** The "grayed out" appearance the user reports may be due to:
  - Cards rendering behind/below the PDF overlay panel
  - The semi-transparent dark overlay (`rgba(0,0,0,0.65)`) that covers the page when PDF is open
  - Cards appearing in the DOM but visually obscured by the overlay z-index

**Architecture issue:** Similar books are conceptually tied to the PDF viewer state — you can't see them without opening a PDF. There's no standalone "book detail" view.

### 2.4 Book Cover Thumbnails

**Current implementation:** None. Book cards show text-only metadata:
- Title, author, year, category, language, series, page count
- Search highlight snippets (HTML with `<em>` tags)
- File path
- "Open PDF" button

No thumbnail generation, storage, or display exists anywhere in the pipeline. The document-indexer uses `pdfplumber` for text extraction but doesn't render pages to images.

---

## 3. Requirements

### R1: Vector Search Text Preview

**User story:** As a user performing semantic or hybrid search, I want to see a preview of the matching text chunk so I can evaluate relevance without opening the PDF.

**Acceptance criteria:**
- [ ] Semantic and hybrid search results display a text snippet from the matching chunk
- [ ] The snippet is clearly labeled as "Matching text" or similar, distinct from keyword highlights
- [ ] Page numbers where the match was found are displayed (already partially working via `page_start_i`/`page_end_i`)
- [ ] Chunk text is truncated to a reasonable preview length (e.g., 300 characters) with "show more" option
- [ ] Performance: Adding chunk text to results does not degrade search response time by more than 10%

### R2: PDF Viewer Improvements

**User story:** As a user reading a PDF, I want fullscreen mode, download, and open-in-new-window so the reading experience isn't constrained by the side panel.

**Acceptance criteria:**
- [ ] **Fullscreen toggle:** Button to expand PDF viewer to fill the entire browser window (not just the side panel). ESC or toggle button returns to side panel mode.
- [ ] **Download button:** Downloads the PDF file directly to the user's device
- [ ] **Open in new window:** Opens the PDF in a new browser tab/window at the direct URL
- [ ] All new controls are keyboard-accessible and have ARIA labels
- [ ] Existing close button and ESC behavior remain unchanged
- [ ] Controls are visible in both side-panel and fullscreen modes

### R3: Similar Books & Book Detail View

**User story:** As a user browsing search results, I want to click a book card to see similar books and full metadata without having to open the PDF first.

**Acceptance criteria:**
- [ ] **Book detail view:** Clicking a book card (not the "Open PDF" button) opens a detail view showing:
  - Full metadata (title, author, year, category, language, series, page count, file size)
  - Editable metadata (if user has admin/edit permissions)
  - Similar books list
  - PDF file size
  - "Open PDF" button within the detail view
- [ ] **Similar books in detail view:** Similar books section is visible and interactive without opening the PDF
- [ ] **Clickable similar books:** Clicking a similar book navigates to that book's detail view
- [ ] **No more grayed-out state:** Similar books are always fully visible and interactive when shown
- [ ] The PDF viewer can still be opened from the detail view

### R4: Book Cover/First Page Thumbnails

**User story:** As a user browsing search results, I want to see a thumbnail of the book's cover or first page so I can visually identify books.

**Acceptance criteria:**
- [ ] Search result cards display a thumbnail image (cover or first page)
- [ ] Thumbnails are generated during indexing and stored for fast retrieval
- [ ] Thumbnail format: JPEG or WebP, reasonable size (e.g., 200×280px)
- [ ] Fallback: Generic book icon shown when no thumbnail is available
- [ ] Library page also shows thumbnails
- [ ] Performance: Thumbnails do not cause noticeable page load delays (lazy loading)

---

## 4. Technical Analysis

### 4.1 R1: Vector Search Text Preview

**Backend changes (solr-search):**

| Change | File | Complexity |
|--------|------|------------|
| Add `chunk_text_t` to `SOLR_FIELD_LIST` | `search_service.py:19-35` | S |
| Add `parent_id_s` to `SOLR_FIELD_LIST` (to identify chunk results) | `search_service.py:19-35` | S |
| Extract `chunk_text` in `normalize_book()` | `search_service.py:214-243` | S |
| Return `chunk_text` and `is_chunk` flag in API response | `main.py` | S |
| Truncate chunk text to configurable max length (API level) | `search_service.py` | S |

**Frontend changes (aithena-ui):**

| Change | File | Complexity |
|--------|------|------------|
| Add `chunk_text?: string` to `BookResult` type | `Components/types/search.ts` | S |
| Display chunk text snippet in `BookCard` | `Components/BookCard.tsx` | M |
| Style the chunk preview (collapsible, "show more") | `App.css` | S |
| Differentiate chunk preview from keyword highlights | `Components/BookCard.tsx` | S |

**Dependencies:** None — chunk text is already in Solr.

**Performance considerations:**
- `chunk_text_t` is a `text_general` field, stored in Solr. Adding it to `fl` increases response payload size proportionally to chunk count × avg chunk size (~400 words ≈ 2KB per chunk). For 10 results, this adds ~20KB — negligible.
- Consider returning a truncated version (first 300 chars) at the API level with an option to fetch full text.

**Estimated complexity: Small (S)**

### 4.2 R2: PDF Viewer Improvements

**Frontend changes (aithena-ui):**

| Change | File | Complexity |
|--------|------|------------|
| Add fullscreen state + toggle button | `Components/PdfViewer.tsx` | M |
| Add CSS for fullscreen mode (100vw × 100vh) | `App.css` | S |
| Add download button (anchor with `download` attribute) | `Components/PdfViewer.tsx` | S |
| Add open-in-new-window button (anchor with `target="_blank"`) | `Components/PdfViewer.tsx` | S |
| Add toolbar/header with all controls | `Components/PdfViewer.tsx` | M |
| Update ARIA labels and keyboard navigation | `Components/PdfViewer.tsx` | S |
| Add Lucide React icons for new buttons | `Components/PdfViewer.tsx` | S |

**Backend changes:** None — the document URL already serves the PDF file directly.

**Dependencies:** None.

**Performance considerations:** Fullscreen mode renders the same iframe at a larger size. No performance impact expected.

**Estimated complexity: Medium (M)**

### 4.3 R3: Similar Books & Book Detail View

**Frontend changes (aithena-ui):**

| Change | File | Complexity |
|--------|------|------------|
| Create `BookDetailView` component | New: `Components/BookDetailView.tsx` | L |
| Create `BookDetailPage` or inline panel | New or modify `pages/SearchPage.tsx` | L |
| Modify `BookCard` to navigate to detail on card click | `Components/BookCard.tsx` | M |
| Move `SimilarBooks` rendering from PDF-dependent to detail-view | `pages/SearchPage.tsx`, `pages/LibraryPage.tsx` | M |
| Add book detail API endpoint (or reuse existing fields) | `src/solr-search/main.py` | S |
| Fix z-index/overlay issue for similar books visibility | `App.css` | S |
| Add file_size display to book detail | `Components/BookDetailView.tsx` | S |
| Integrate metadata editing into detail view | `Components/BookDetailView.tsx` | M |

**Backend changes (solr-search):**

| Change | File | Complexity |
|--------|------|------------|
| Add `GET /v1/books/{id}` endpoint for single book detail | `main.py` | M |
| Return file_size, page_count, all metadata in detail response | `main.py` | S |

**Design decision needed:** Should the book detail view be:
- (a) A panel/drawer that replaces the search results area (like a detail pane)?
- (b) A separate page/route (`/books/{id}`)?
- (c) A modal overlay?

**Dependencies:** R2 (PDF viewer improvements) — the detail view should integrate the improved PDF viewer.

**Performance considerations:**
- Similar books API already uses LRU caching (100 entries) on the frontend — no concern.
- Single-book detail endpoint is a simple Solr `id` query — very fast.

**Estimated complexity: Large (L)**

### 4.4 R4: Book Cover Thumbnails

**Backend changes (document-indexer):**

| Change | File | Complexity |
|--------|------|------------|
| Add thumbnail generation during indexing | `document_indexer/__main__.py` | L |
| Add `pdf2image` or `pymupdf` dependency for PDF rendering | `pyproject.toml` | S |
| Store thumbnails (filesystem or Solr BLOB) | New decision needed | M |
| Add `thumbnail_url` field to Solr schema | `src/solr/books/managed-schema.xml` | S |

**Backend changes (solr-search):**

| Change | File | Complexity |
|--------|------|------------|
| Add `thumbnail_url` to field list and `normalize_book()` | `search_service.py` | S |
| Add thumbnail serving endpoint (if filesystem storage) | `main.py` | M |

**Frontend changes (aithena-ui):**

| Change | File | Complexity |
|--------|------|------------|
| Add thumbnail image to `BookCard` | `Components/BookCard.tsx` | M |
| Add lazy loading (`loading="lazy"`) | `Components/BookCard.tsx` | S |
| Add fallback placeholder icon | `Components/BookCard.tsx` | S |
| Update card layout for image + text side-by-side | `App.css` | M |

**Infrastructure decisions needed:**
- **Rendering library:** `pymupdf` (fast, C-based) vs `pdf2image` (uses poppler, larger dependency) vs `pdfplumber` (no native rendering)
- **Storage:** Filesystem alongside PDFs? Dedicated thumbnails directory? Stored in Solr as base64?
- **Serving:** Via nginx (static files) or via solr-search API endpoint?
- **Generation timing:** During indexing (adds time) or lazy/on-demand (adds latency on first view)?
- **Docker impact:** Rendering libraries require system-level dependencies (e.g., `poppler-utils` for pdf2image, or `libmupdf` for pymupdf). The document-indexer Dockerfile needs updating.

**Performance considerations:**
- Thumbnail generation adds ~1-3 seconds per PDF during indexing (for first page render + resize)
- Serving: Static file via nginx is fastest; API endpoint adds latency
- Page load: 10 thumbnails at ~15KB each (JPEG, 200×280) = ~150KB — acceptable with lazy loading
- Re-indexing: Must regenerate or cache thumbnails to avoid stale images

**Estimated complexity: Extra Large (XL)**

---

## 5. Open Questions

### For Juanma (PO)

1. **Book detail view design:** Should it be a side panel, separate page, or modal? (Affects R3 routing and navigation)
2. **Thumbnail priority:** Is R4 (thumbnails) a must-have for v1.11.0 or can it be deferred to v1.12.0? It's the largest effort and has infrastructure dependencies.
3. **Thumbnail storage location:** Filesystem alongside PDFs, or a separate thumbnails directory?
4. **Chunk text preview length:** How many characters should be shown by default? (Suggestion: 300 chars with "show more")
5. **Similar books without PDF:** When the user clicks a book card (not "Open PDF"), should we show a quick preview with similar books, or navigate to a full detail page?

### For Ash (Search Engineering)

6. **Chunk deduplication in semantic results:** When multiple chunks from the same parent match, should we show the best-matching chunk per book, or allow multiple entries?
7. **Chunk text highlighting:** Should we apply the search query as highlight markup within the chunk text preview?

### Chunking Strategy (Separate Issue)

See the linked chunking strategy issue for in-depth questions about:
- Current 400-word/50-word-overlap defaults — are they optimal?
- Whether chunk boundaries should respect paragraph/sentence boundaries
- Whether overlapping chunks cause confusing duplicate text in previews
- Impact on embedding quality and search relevance

---

## 6. Phasing Suggestion

### Phase 1: Quick Wins (v1.11.0 Wave 1) — 1-2 weeks

| # | Requirement | Rationale |
|---|-------------|-----------|
| R1 | Vector search text preview | Infrastructure is 80% done. Small backend + frontend change. Highest user impact per effort. |
| R2 | PDF viewer improvements | Self-contained frontend work. No backend changes. No dependencies. |

### Phase 2: Book Experience (v1.11.0 Wave 2) — 2-3 weeks

| # | Requirement | Rationale |
|---|-------------|-----------|
| R3 | Similar books & book detail view | Depends on R2 (improved viewer integrates into detail view). Larger frontend effort with design decisions. |

### Phase 3: Visual Polish (v1.11.0 Wave 3 or v1.12.0) — 2-3 weeks

| # | Requirement | Rationale |
|---|-------------|-----------|
| R4 | Book cover thumbnails | Largest effort (XL). Requires infrastructure decisions, new dependencies, Docker changes. Can be deferred without blocking other work. |

**Recommendation:** Ship R1 + R2 as quick wins, then R3 as the main deliverable. Defer R4 to v1.12.0 unless Juanma feels it's essential for v1.11.0.

---

## 7. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Chunk text increases API payload size** | Low | Medium | Truncate at API level; paginate chunks if needed |
| **Fullscreen iframe security** | Low | Low | Same-origin PDFs served by nginx; no cross-origin concerns |
| **Book detail view scope creep** | Medium | High | Define MVP detail view first (read-only metadata + similar books); defer editable metadata to follow-up |
| **Thumbnail generation slows indexing** | Medium | High | Generate asynchronously (background task after main indexing); or generate on first access |
| **Thumbnail Docker dependencies** | Medium | Medium | Choose `pymupdf` (pip-installable, no system deps) over `pdf2image` (requires poppler) |
| **Chunk deduplication confusion** | Medium | Medium | Show best chunk per parent document in results; collapse duplicates |
| **Similar books z-index/overlay issue** | Low | High | Move similar books into detail view (R3 solves this architecturally) |
| **Breaking existing semantic search behavior** | High | Low | Feature-flag chunk text preview; maintain backward-compatible API |

---

## Appendix A: Key Source Files

| Component | File | Purpose |
|-----------|------|---------|
| Chunking pipeline | `src/document-indexer/document_indexer/chunker.py` | Word-based sliding window chunker |
| Chunk indexing | `src/document-indexer/document_indexer/__main__.py` | Two-phase indexing (Tika + chunks) |
| Embeddings client | `src/document-indexer/document_indexer/embeddings.py` | HTTP client for embeddings server |
| Embeddings server | `src/embeddings-server/main.py` | SentenceTransformers model serving |
| Solr schema | `src/solr/books/managed-schema.xml` | Field definitions for chunks and parents |
| Search service | `src/solr-search/search_service.py` | SOLR_FIELD_LIST, normalize_book(), kNN params |
| Search API | `src/solr-search/main.py` | REST endpoints, similar books API |
| PDF viewer | `src/aithena-ui/src/Components/PdfViewer.tsx` | iframe-based side panel |
| Similar books | `src/aithena-ui/src/Components/SimilarBooks.tsx` | Horizontal card list with LRU cache |
| Book card | `src/aithena-ui/src/Components/BookCard.tsx` | Text-only search result card |
| Search page | `src/aithena-ui/src/pages/SearchPage.tsx` | Search layout, PDF + similar books integration |
| Library page | `src/aithena-ui/src/pages/LibraryPage.tsx` | All-books view with same integration pattern |

## Appendix B: Data Model Reference

```
Parent Document (book level)
├── id: SHA256(file_path)
├── title_s, author_s, year_i, category_s, language_s, series_s
├── file_path_s, folder_path_s, file_size_l, page_count_i
├── content / _text_ (full text via Tika)
└── book_embedding (parent-level embedding, used by similar books)

Chunk Document (text segment)
├── id: {parent_id}_chunk_{index:04d}
├── parent_id_s → links to parent
├── chunk_index_i (0, 1, 2, ...)
├── chunk_text_t (400-word segment, stored)
├── embedding_v (512-dim vector, HNSW cosine)
├── page_start_i, page_end_i (page range)
└── Inherited: title_s, author_s, category_s, year_i, file_path_s, folder_path_s
```
