---
name: "solr-pdf-indexing"
description: "How to index PDFs into SolrCloud using Tika extraction with metadata from filesystem paths, including chunking and embeddings for semantic search"
domain: "search, indexing"
confidence: "high"
source: "earned — complete architecture review of aithena v0.3+ phases"
---

## Context
When building a hybrid search engine on SolrCloud with PDF files stored on the local filesystem, combining BM25 full-text search with semantic kNN search on embeddings. Applies when Solr 9.x has the `extraction` module enabled, a `/update/extract` handler configured, and an embeddings service available.

## Patterns

1. **Use Solr Tika extraction for full-text, not application-side PDF parsing:**
   - POST the raw PDF binary to `/update/extract` with `literal.*` params for metadata
   - Solr's Tika extracts text → `_text_` field (via `fmap.content`)
   - Saves building/maintaining a PDF parser in application code

2. **Pass metadata as literal fields:**
   ```
   POST /update/extract?literal.id=<hash>&literal.author_s=<author>&literal.title_s=<title>&literal.file_path_s=<path>
   Content-Type: application/pdf
   <binary PDF body>
   ```

3. **Language detection via langid update chain:**
   - Configure `update.chain=langid` on the extract handler
   - Solr auto-detects language → `language_detected_s` field
   - Fallback language configurable (default: `en`)

4. **Extract metadata from filesystem paths with heuristic parsing:**
   - Parse folder structure: `Author/Title (Year).pdf`
   - Always have fallbacks: filename → title, parent folder → author, "Unknown" for missing fields

5. **Schema design for hybrid book search:**
   - **Domain fields (Phase 1):** Explicitly declare `title_s`, `title_t`, `author_s`, `author_t`, `year_i`, `page_count_i`, `file_path_s`, `folder_path_s`, `category_s`, `file_size_l`, `language_detected_s`
   - **Vector field (Phase 3):** Add `book_embedding` (knn_vector_512, 512-dim, HNSW, cosine similarity)
   - **Chunk fields (Phase 3):** `chunk_text_t` (text), `embedding_v` (knn_vector_512), `chunk_index_i`, `parent_id_s`, `page_start_i`, `page_end_i` for chunk-level indexing
   - Use `*_s` (string) for facetable fields; `*_t` (text_general) for searchable text; `*_i` (int) for numeric facets
   - Keep Tika auto-generated fields — they hold useful PDF metadata

6. **Feed title/author into catch-all search and highlight from stored content:**
   - Add `copyField` rules from `title_t` and `author_t` into `_text_` so general search finds title/author matches
   - Keep `_text_` as the default query field, but drive snippets from stored `content`
   - In `solrconfig.xml`, set `/query` and `/select` highlight defaults with `hl.method=unified`, `hl.fl=content,_text_`, and `f._text_.hl.alternateField=content`

7. **Index per-document embeddings separately from chunk embeddings:**
   - At document insert time: store full document text, compute/fetch embedding from external service, store in `book_embedding` field
   - Enables the `/books/{id}/similar` kNN endpoint (book-to-book similarity)
   - For chunk-level embeddings: index chunks as separate Solr documents with parent_id linkage

8. **Support three search modes (keyword, semantic, hybrid):**
   - **Keyword:** BM25 via edismax, with facets and highlighting
   - **Semantic:** kNN query on `book_embedding` field (Solr HNSW), no facets/highlights
   - **Hybrid:** Parallel BM25 + kNN, merged with Reciprocal Rank Fusion (RRF, k=60)
   - All modes support filter queries (`fq_author`, `fq_category`, `fq_language`, `fq_year`)

## Examples

Reference files in aithena:
- `solr/add-conf-overlay.sh` — configures `/update/extract` handler
- `solr/config.json` lines 88-98 — extract handler with langid chain
- `solr/books/managed-schema.xml` — vector field type `knn_vector_512`, chunk fields, copyField rules
- `solr-search/main.py` lines 115–250 — search endpoints (keyword, semantic, hybrid modes)
- `solr-search/search_service.py` — query builders, RRF implementation, kNN parameter syntax

## Anti-Patterns

- **Don't use pdfplumber/PyMuPDF for full-text when Solr Tika is available** — duplicates work, loses Tika's rich metadata extraction
- **Don't rely on auto-schema for important fields** — explicitly define book domain fields; auto-schema creates `text_general` for everything
- **Don't store embeddings in the same indexing pass as full-text** — separate concerns; full-text indexing should work independently of the embeddings server availability
- **Don't query kNN without preprocessing the query text** — must embed the query via external embeddings service first (not free/offline)
