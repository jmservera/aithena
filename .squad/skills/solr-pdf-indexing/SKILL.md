---
name: "solr-pdf-indexing"
description: "How to index PDFs into SolrCloud using Tika extraction with metadata from filesystem paths"
domain: "search, indexing"
confidence: "medium"
source: "earned — architecture review of aithena branch"
---

## Context
When building a document search engine on SolrCloud with PDF files stored on the local filesystem. Applies when Solr has the `extraction` module enabled and a `/update/extract` handler configured.

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
   - Solr auto-detects language → `language_s` field
   - Fallback language configurable (default: `en`)

4. **Extract metadata from filesystem paths with heuristic parsing:**
   - Parse folder structure: `Author/Title (Year).pdf`
   - Always have fallbacks: filename → title, parent folder → author, "Unknown" for missing fields

5. **Schema design for book search:**
   - Use `*_s` (string) suffix for facetable fields (author, language, category)
   - Use `*_t` (text_general) for searchable text fields
   - Use `*_i` (int) for numeric facets (year, page count)
   - Keep Tika auto-generated fields — they hold useful PDF metadata

## Examples

Reference files in aithena:
- `solr/add-conf-overlay.sh` — configures `/update/extract` handler
- `solr/config.json` lines 88-98 — extract handler with langid chain
- `solr/books/managed-schema.xml` — multilingual field types and dynamic fields

## Anti-Patterns

- **Don't use pdfplumber/PyMuPDF for full-text when Solr Tika is available** — duplicates work, loses Tika's rich metadata extraction
- **Don't rely on auto-schema for important fields** — explicitly define book domain fields; auto-schema creates `text_general` for everything
- **Don't store embeddings in the same indexing pass as full-text** — separate concerns; full-text indexing should work independently of the embeddings server availability
