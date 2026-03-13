# Ash — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Apache Solr, Docker Compose, multilingual embeddings (768-dim)
- **Languages:** Spanish, Catalan, French, English (including very old texts)
- **Current setup:** Qdrant vector DB with embeddings-server (sentence-transformers), being transitioned to Solr

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Phase 1 book schema fields implemented

- Added explicit book metadata fields in `solr/books/managed-schema.xml`: `title_s`, `title_t`, `author_s`, `author_t`, `year_i`, `page_count_i`, `file_path_s`, `folder_path_s`, `category_s`, `file_size_l`, and `language_detected_s`.
- Added `copyField` rules from `title_t` and `author_t` into `_text_` so general catch-all queries include book title and author terms without removing any Tika-generated metadata fields.
- Updated `solr/books/solrconfig.xml` to default `/query` and `/select` highlighting to the unified highlighter, with `content` as the stored snippet source and `_text_` configured with an alternate-field fallback. This keeps highlight support aligned with catch-all search without duplicating stored full text in `_text_`.

### 2026-03-13 — Architecture Plan: Solr Schema Evolution (from Ripley review)

**Your assignments (Phase 1–3):**
- **Phase 1 (URGENT):** Add book-specific fields to managed-schema.xml:
  - `title_s` (string, stored), `title_t` (text_general, indexed)
  - `author_s` (string, stored, facetable)
  - `year_i` (int, facetable)
  - `language_s` (string — already via langid, but make explicit)
  - `page_count_i` (int)
  - `file_path_s` (string, stored)
  - `folder_path_s` (string, stored)
  - `category_s` (string, stored, facetable)
  - Keep existing auto-generated Tika metadata fields
- **Phase 2:** Search tuning (faceting config, highlighting, result boosting)
- **Phase 3:** Vector field config for kNN search
  - Add `DenseVectorField` for embeddings (512-dim for distiluse v2)
  - Configure HNSW similarity function (cosine)

**Key architectural decisions:**
- Hybrid indexing: Tika handles full-text + metadata extraction (Phase 1), app-side chunking for embeddings (Phase 3)
- Solr 9.x native kNN support for vector search
- Embeddings model: Standardize on `distiluse-base-multilingual-cased-v2` (512-dim)

**Critical blockers:**
- Phase 1 schema changes must complete before Parker can rewrite the indexer
- Ripley will review & approve schema changes before cluster deployment

**Full context:** `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

### 2026-03-13 — Cross-agent coordination (Phase 1.2–1.5)

**From Parker's indexer work:**
- Parker is populating fields `title_s`, `author_s`, `year_i`, `category_s`, `file_path_s`, `folder_path_s` via `literal.*` params in Solr `/update/extract`.
- Your schema decisions are enabling stable field names across indexing and search. All fields confirmed implemented in managed-schema.xml.

**From Lambert's test suite:**
- Lambert's 15 metadata extraction tests validate the parser contracts you'll search against. 4 intentional failures expose parser gaps—review `document-indexer/tests/test_metadata.py` for expected shapes before Phase 2 tuning.
- Test patterns (amades/, balearics/, bsal/) align with your copyField strategy for author/category faceting.

