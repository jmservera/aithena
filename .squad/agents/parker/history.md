# Parker — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), Docker Compose, RabbitMQ, Redis, Apache Solr
- **Book library:** `/home/jmservera/booklibrary`
- **Existing Python services:** document-lister, document-indexer, embeddings-server, qdrant-search, qdrant-clean

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Phase 1 backend: Solr indexer rewrite

- Rewrote `document-indexer/document_indexer/__main__.py` into a RabbitMQ consumer that reads local PDFs from `/data/documents`, extracts path metadata, uploads binaries to Solr `/update/extract`, and updates Redis state with `processed` / `failed` outcomes.
- Added `document-indexer/document_indexer/metadata.py` with heuristics for the required folder patterns plus real library cases found under `/home/jmservera/booklibrary`.
- Updated `docker-compose.yml` so `document-data` bind-mounts `/home/jmservera/booklibrary`; `document-lister`, `document-indexer`, and all Solr nodes now mount that library path.
- Updated `document-indexer/document_indexer/__init__.py`, `document-indexer/requirements.txt`, and `document-indexer/Dockerfile` to remove Qdrant/Azure configuration and switch to Solr env vars (`SOLR_HOST`, `SOLR_PORT`, `SOLR_COLLECTION`, `BASE_PATH`).
- Real book library patterns observed during implementation:
  - `amades/<title> ... amades.pdf` behaves like a single-author folder; filename suffix repeats the author and should be stripped from the title.
  - `balearics/ESTUDIS_BALEARICS_01.pdf` behaves like a category/series folder; uppercase underscore filenames should keep title text and fall back to `author="Unknown"`.
  - `bsal/Bolletí ... 1885 - 1886.pdf` behaves like a category/journal folder; year ranges should not be mistaken for `Author - Title` splits, but the first year is still useful metadata.
- Validation completed with `python3 -m compileall` plus metadata smoke tests against required synthetic patterns and real sample paths from the mounted library.

### 2026-03-13 — Architecture Plan: Solr Migration (from Ripley review)

**Your assignments (Phase 1–4):**
- **Phase 1:** Rewrite document-indexer for Solr Tika extraction (drop Qdrant), build metadata extraction module (path → author/title/year/category), fix docker-compose.yml volume mounting
- **Phase 2:** Build FastAPI search API with Solr `/select` wrapper (endpoints: search, facets, books/{id}, PDF serving)
- **Phase 3:** Implement embeddings indexing pipeline (post-Tika), hybrid search mode (keyword|semantic|hybrid), extend search API
- **Phase 4:** PDF upload endpoint, file watcher service (60s polling recommended over inotify for Docker reliability)

**Key technical decisions affecting your work:**
- Hybrid indexing: Solr Tika for full-text (Ph.1), app-side chunking for embeddings (Ph.3)
- Embeddings model: Standardize on `distiluse-base-multilingual-cased-v2` (fix Dockerfile/main.py mismatch)
- Search API: FastAPI (consistent Python stack)
- File watching: 60s polling over inotify

**Dependencies:** 
- Phase 1 blocked until Ash adds schema fields + you fix volume mount
- Phase 2 blocked on Phase 1 completion
- See full plan in `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

### 2026-03-13 — Cross-agent coordination (Phase 1.2–1.5)

**From Ash's schema work:**
- Ash confirmed all 11 fields in managed-schema.xml: title_s, title_t, author_s, author_t, year_i, page_count_i, file_path_s, folder_path_s, category_s, file_size_l, language_detected_s.
- copyField rules from title_t/author_t into _text_ are live. Your literal.* field population aligns with Ash's field definitions.

**From Lambert's test suite:**
- Lambert wrote 15 metadata extraction tests (11 passing, 4 failing). Review `document-indexer/tests/test_metadata.py` to validate your parser handles real library conventions (amades/ author, balearics/ category, bsal/ journal).
- Test expectations: `file_path` and `folder_path` relative to `base_path`, year ranges (1885 - 1886) must stay in title, unknown patterns conservatively fallback to title=filename, author=Unknown.

