# Ripley — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), TypeScript/React + Vite (UI), Docker Compose, Apache Solr, multilingual embeddings
- **Book library:** `/home/jmservera/booklibrary`
- **Existing services:** Redis, RabbitMQ, Qdrant (being replaced), LLaMA server, embeddings server, document lister/indexer, search API, React UI

## Learnings

<!-- Append learnings below -->

### 2026-03-13T20:58 — Phase 2-4 Issue Decomposition (`jmservera/solrstreamlitui`)

- **COMPLETED:** Broke the remaining roadmap into 18 single-owner GitHub issues targeted at `squad:copilot`: Phase 2 (#36-#41), Phase 3 (#42-#47), and Phase 4 (#48-#53).
- Established the dependency spine as search API → UI shell/facets/PDF/tests, embeddings model → Solr vectors → embedding indexing → hybrid search → similar books, and 60s file polling → upload/admin/hardening/E2E.
- Kept the planned upload endpoint in the FastAPI backend so new ingestion work stays aligned with ADR-003 and the existing Redis/RabbitMQ/Solr pipeline.
- Recorded decision in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition". All 18 issues now tracked with explicit dependencies and milestones.

### 2026-03-13 — Branch Architecture Review (`jmservera/solrstreamlitui`)

**Architecture decisions made:**
- Hybrid indexing strategy: Solr Tika for full-text, app-side chunking for embeddings (Phase 3)
- FastAPI for search API (consistent with Python backend stack)
- Standardize on `distiluse-base-multilingual-cased-v2` for multilingual embeddings
- React UI effectively needs rewrite from chat to search paradigm; keep Vite/TS scaffolding
- Keep 60s polling over inotify for file watching (Docker bind-mount reliability)

**Key file paths:**
- `docker-compose.yml` — 3-node SolrCloud + 3 ZK + Redis + RabbitMQ + nginx/certbot
- `solr/books/managed-schema.xml` — Solr schema with ~20 multilingual field types, Tika-extracted fields
- `solr/books/solrconfig.xml` — Solr config (extraction, langid, spellcheck)
- `solr/add-conf-overlay.sh` — Config overlay script (sets up /update/extract handler + langid chain)
- `solr/config.json` — Full Solr config dump (Lucene 9.10, langid chain, extraction handler)
- `document-lister/document_lister/__main__.py` — File scanner (polls /data/documents/ every 10 min)
- `document-lister/document_lister/__init__.py` — Env config (RABBITMQ, REDIS, QUEUE_NAME, BASE_PATH)
- `document-indexer/document_indexer/__main__.py` — **Still Qdrant-bound!** Needs full rewrite for Solr
- `document-indexer/document_indexer/blob_storage/__init__.py` — Azure Blob Storage client (to be replaced with local FS)
- `embeddings-server/Dockerfile` — Uses `distiluse-base-multilingual-cased-v2` (semitechnologies image)
- `embeddings-server/main.py` — FastAPI server loading `use-cmlm-multilingual` (MODEL MISMATCH)
- `admin/src/main.py` — Streamlit main page
- `admin/src/pages/document_lister.py` — Shows Redis queue state
- `aithena-ui/src/App.tsx` — Chat-oriented React UI (talks to /v1/question/ — old qdrant-search)

**Critical gaps identified:**
1. Book library path (`/home/jmservera/booklibrary`) not mounted in docker-compose
2. Document indexer fully Qdrant-dependent (imports qdrant_client, uses pdfplumber instead of Solr Tika)
3. No search API service exists (qdrant-search commented out)
4. Schema lacks explicit book domain fields (title, author, year, category)
5. Embeddings server has model mismatch between Dockerfile and main.py
6. React UI designed for chat, not search+facets+PDF viewing

**User preferences:**
- Multilingual focus: Spanish, Catalan, French, English (including very old texts)
- Local-first: books on local filesystem, no cloud dependency for core features
- Phased approach: keyword search first, embeddings later
