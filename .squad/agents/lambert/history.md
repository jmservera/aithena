# Lambert — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (pytest), TypeScript (Vitest), Docker Compose
- **Key test concerns:** PDF processing edge cases, multilingual search quality, metadata extraction, file watcher reliability

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Metadata extraction test design

**Real library patterns discovered from `/home/jmservera/booklibrary`:**
- `amades/` behaves like an author folder: files such as `Auca dels costums de Barcelona amades.pdf` and `costumari 1 1 -3 OCR.pdf` should resolve author `Amades`, with author suffixes stripped from titles when duplicated.
- `balearics/ESTUDIS_BALEARICS_01.pdf` behaves like a category/series folder with uppercase underscore-heavy stems; tests expect category extraction plus a readable title.
- `bsal/Bolletí societat arqueologica luliana 1885 - 1886.pdf` is a critical edge case: the year range must stay in the title and must not be misread as `author - title` or a single `year`.

**Key test decisions:**
- `file_path` and `folder_path` are asserted relative to `base_path`, not absolute host paths.
- Unknown patterns are tested with conservative fallbacks: keep the filename stem as title, set author to `Unknown`, and avoid guessing from extra nested folders.
- The new pytest suite currently lands at **11 passing / 4 failing**, with the remaining failures intentionally flagging parser bugs in fallback handling, deep nested paths, and year-range parsing.

### 2026-03-13 — Architecture Plan: QA & Testing (from Ripley review)

**Your assignments (Phase 1–4):**
- **Phase 1:** Write integration tests for end-to-end indexing (PDF in → verify Solr with correct metadata)
  - Test metadata extraction module with sample paths from `/home/jmservera/booklibrary`
  - Verify schema fields populated correctly (title, author, year, category, file_path)
  - Test edge cases: irregular path formats, special characters, missing metadata
- **Phase 2:** API contract tests (search endpoint responses), UI smoke tests (Playwright)
  - Verify facet aggregation (authors, years, languages, categories)
  - Test pagination, highlighting, PDF serving
- **Phase 3:** Embedding quality tests (semantic search precision), benchmark kNN performance
- **Phase 4:** E2E tests, production hardening (health checks, error scenarios)

**Key technical context:**
- Document-lister already works (scans `/data/documents/`, queues to RabbitMQ every 10 min)
- RabbitMQ durable queue `shortembeddings` handles backpressure
- Phase 1 focus: Solr Tika extraction + metadata parsing
- Phase 3 concern: Solr 9.x HNSW vector search with <1M vectors

**Test data source:** `/home/jmservera/booklibrary` (actual user library with old texts, OCR issues)

**Full architecture:** `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

### 2026-03-13 — Cross-agent coordination (Phase 1.2–1.5)

**From Ash's schema work:**
- Ash finalized schema with 11 explicit book fields: title_s, author_s, year_i, category_s, file_path_s, folder_path_s, etc. Your test patterns match these field names exactly.
- copyField rules from title_t/author_t into _text_ enable catch-all search while keeping highlights tied to content field.

**From Parker's indexer work:**
- Parker's `extract_metadata()` populates title_s, author_s, year_i, category_s directly from filesystem path parsing. His parser handles amades/ (author), balearics/ (category), bsal/ (journal) patterns.
- Your test suite validates Parker's parser contracts: relative paths, conservative fallbacks, year-range handling. 4 failing tests flag real parser gaps to address in Phase 1.5.

