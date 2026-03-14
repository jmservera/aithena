---
name: "project-conventions"
description: "Project context, tech stack, and conventions for the aithena codebase"
domain: "project-conventions"
confidence: "high"
source: "earned — consolidated from all agent charters during reskill audit"
author: "Ripley"
created: "2026-07-14"
last_validated: "2026-07-14"
---

## Project Context

- **Project:** aithena — Book library search engine
- **User:** jmservera
- **Book library:** `/home/jmservera/booklibrary` (bind-mounted to `/data/documents` in containers)
- **Languages in texts:** Spanish, Catalan, French, English (including very old texts)
- **Key concern:** Transitioning from Qdrant vector DB to Solr for full-text + semantic search
- **Approach:** Phased — keyword search first, embeddings later

## Services

| Service | Path | Role |
|---------|------|------|
| document-lister | `document-lister/` | Polls `/data/documents/` for new PDFs, publishes to RabbitMQ |
| document-indexer | `document-indexer/` | Consumes queue, indexes into Solr via Tika extraction |
| embeddings-server | `embeddings-server/` | FastAPI server for `distiluse-base-multilingual-cased-v2` |
| solr-search | `solr-search/` | FastAPI search API (BM25 + facets + document serving) |
| aithena-ui | `aithena-ui/` | React/Vite frontend (search + facets + PDF viewer) |
| solr | `solr/` | SolrCloud 3-node cluster with ZooKeeper ensemble |

## Tech Stack

### Backend (Python 3.x)
- FastAPI + uvicorn (APIs)
- pysolr (Solr client)
- PyPDF2 / pdfplumber / PyMuPDF (PDF processing)
- watchdog (file system monitoring)
- RabbitMQ (message queue), Redis (caching/state)
- pytest (testing)

### Frontend (TypeScript)
- React 18+ with Vite
- Vitest + React Testing Library (testing)
- PDF.js / react-pdf (PDF viewing)

### Infrastructure
- Docker / Docker Compose / multi-stage builds
- Apache Solr 9.x / SolrCloud / ZooKeeper ensemble
- astral uv (Python package management in containers)
- nginx reverse proxy

## Patterns

### File Structure
- Each service is a top-level directory with its own `Dockerfile` and `requirements.txt`
- Solr config lives in `solr/books/` (managed-schema.xml, solrconfig.xml)
- Docker Compose orchestrates all services

### Testing
- Python: pytest — tests live alongside source or in `tests/` subdirectory
- Frontend: Vitest — test files as `*.test.ts` / `*.test.tsx`

### Error Handling
- FastAPI services use HTTP status codes + JSON error responses
- PDF processing uses try/catch with fallbacks for corrupted files

## Anti-Patterns

- **Don't target qdrant-search for new work** — it's deprecated; use solr-search
- **Don't use pdfplumber for full-text when Solr Tika is available** — see skill `solr-pdf-indexing`
- **Don't pin application traffic to a single Solr node** — see skill `solrcloud-docker-operations`
