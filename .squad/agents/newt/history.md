# Newt — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), TypeScript/React + Vite (UI), Docker Compose, Apache Solr, multilingual embeddings
- **UI URL:** http://localhost (nginx) or http://localhost:5173 (vite dev)
- **Search API:** http://localhost:8080/v1/search/
- **Current version:** v0.3.0 — Stabilize Core
- **Next milestone:** v0.4.0 — Dashboard & Polish

## Key Paths
- `aithena-ui/` — React frontend
- `solr-search/` — FastAPI search API
- `document-indexer/` — PDF indexing pipeline
- `document-lister/` — File watcher
- `docker-compose.yml` — Full local stack
- `README.md` — Project documentation

## Learnings

- v0.4.0's user-facing flow is centered on Search, Status, and Stats; the visible Library tab is still a placeholder and should not be documented as a finished browse feature.
- The Search UI exposes keyword search with author/category/language/year facets, sort controls, 10/20/50 per-page options, highlight snippets, and PDF deep-linking to the first matched page when page metadata exists.
- The Status tab polls `/v1/status/` every 10 seconds, while the Stats tab loads `/v1/stats/` once on page open and requires a manual refresh to show newly indexed totals.
- The Docker Compose stack mounts the library through `BOOKS_PATH` into `/data/documents`, and `document-lister` scans `*.pdf` files every 60 seconds into the `shortembeddings` RabbitMQ queue.

<!-- Append learnings below -->
