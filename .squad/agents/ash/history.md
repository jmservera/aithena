# Ash — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Apache Solr, Docker Compose, multilingual embeddings (768-dim)
- **Languages:** Spanish, Catalan, French, English (including very old texts)
- **Current setup:** Qdrant vector DB with embeddings-server (sentence-transformers), being transitioned to Solr

## Learnings

<!-- Append learnings below -->

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

