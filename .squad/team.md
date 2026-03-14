# Squad Team

> aithena — Book library search engine with Solr full-text indexing, multilingual embeddings, PDF processing, and React UI

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| 🏗️ Ripley | Lead | `.squad/agents/ripley/charter.md` | ✅ Active |
| 🔧 Parker | Backend Dev | `.squad/agents/parker/charter.md` | ✅ Active |
| ⚛️ Dallas | Frontend Dev | `.squad/agents/dallas/charter.md` | ✅ Active |
| 📊 Ash | Search Engineer | `.squad/agents/ash/charter.md` | ✅ Active |
| 🧪 Lambert | Tester | `.squad/agents/lambert/charter.md` | ✅ Active |
| 📋 Scribe | Session Logger | `.squad/agents/scribe/charter.md` | ✅ Active |
| 🔄 Ralph | Work Monitor | — | 🔄 Monitor |
| ⚙️ Brett | Infra Architect | `.squad/agents/brett/charter.md` | ✅ Active |
| 🔒 Kane | Security Engineer | `.squad/agents/kane/charter.md` | ✅ Active |
| 🤖 Copilot | Coding Agent | `.squad/agents/copilot/charter.md` | ✅ Active |

<!-- copilot-auto-assign: true -->

## Project Context

- **Project:** aithena
- **User:** jmservera
- **Created:** 2026-03-13
- **Stack:** Python (backend services), TypeScript/React + Vite (UI), Docker Compose, Apache Solr (search), multilingual embeddings
- **Description:** A book library database that indexes PDFs using Solr for full-text search. Extracts metadata (author, date, language) from filenames, folder names, and PDF content. Supports multilingual texts (Spanish, Catalan, French, English), including very old documents. Features file watching for new books, PDF upload via UI, search with filtering, and PDF viewing with highlighting. Plans to enhance native Solr word search with local multilingual embedding models.
- **Book library path:** `/home/jmservera/booklibrary`
- **Existing services:** Redis, RabbitMQ, Qdrant (being replaced by Solr), LLaMA server, embeddings server, document lister/indexer, qdrant-search API, React UI (aithena-ui)
