# Parker — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), Docker Compose, RabbitMQ, Redis, Apache Solr
- **Book library:** `/home/jmservera/booklibrary`
- **Existing Python services:** document-lister, document-indexer, embeddings-server, qdrant-search, qdrant-clean

## Learnings

<!-- Append learnings below -->

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

