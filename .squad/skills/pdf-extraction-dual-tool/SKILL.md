---
name: "pdf-extraction-dual-tool"
description: "Tika vs pdfplumber — complementary tools for PDF extraction, not redundant"
domain: "document-processing"
confidence: "high"
source: "documented from v1.11.0 PRD research"
author: "Ripley"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context

Aithena uses two PDF extraction tools that serve different purposes. They are complementary, not redundant. Tika (integrated with Solr) handles full-text keyword search and metadata extraction. pdfplumber (used in the document-indexer) handles per-page semantic chunking for embedding-based search. Removing either tool would break a core search capability.

## Patterns

- **Tika (via Solr):**
  - Extracts full document text for keyword/BM25 search
  - Extracts metadata (title, author, creation date, page count)
  - Integrated into Solr's indexing pipeline via `ExtractingRequestHandler`
  - Handles a wide range of formats beyond PDF (DOCX, PPTX, etc.)
  - Best for: full-text search, metadata extraction, format-agnostic processing

- **pdfplumber (in document-indexer):**
  - Extracts text page-by-page with layout awareness
  - Enables per-page semantic chunking for embedding generation
  - Provides table detection and extraction
  - Gives precise control over text extraction boundaries
  - Best for: semantic search chunks, page-level granularity, table extraction

- **Data flow separation:**
  - File → Solr (Tika) → full-text index → keyword search via solr-search API
  - File → document-indexer (pdfplumber) → page chunks → embeddings-server → vector search

- **When to use which:**
  - User searches by keywords → Tika/Solr path
  - User searches by meaning/concept → pdfplumber/embeddings path
  - Hybrid search combines both results

## Examples

```python
# pdfplumber: per-page extraction for semantic chunks
import pdfplumber

def extract_pages(pdf_path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page": i + 1, "text": text})
    return pages
```

```xml
<!-- Solr: Tika extraction via ExtractingRequestHandler -->
<requestHandler name="/update/extract"
                class="solr.extraction.ExtractingRequestHandler">
  <lst name="defaults">
    <str name="fmap.content">text</str>
    <str name="fmap.meta">ignored_</str>
  </lst>
</requestHandler>
```

## Anti-Patterns

- **Don't remove pdfplumber because "Tika already extracts text"** — Tika produces a single text blob per document; pdfplumber provides page-level chunks needed for semantic search.
- **Don't remove Tika because "pdfplumber already extracts text"** — pdfplumber is PDF-only and doesn't integrate with Solr's keyword search pipeline.
- **Don't use pdfplumber for keyword search indexing** — Solr's Tika integration is purpose-built for this and handles format diversity.
- **Don't use Tika for semantic chunking** — its output lacks the page-level granularity needed for meaningful embedding generation.
