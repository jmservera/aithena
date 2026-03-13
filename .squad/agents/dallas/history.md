# Dallas — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** TypeScript, React, Vite
- **Existing UI:** aithena-ui directory with React + Vite setup
- **UI package.json location:** aithena-ui/package.json

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Architecture Plan: UI Rewrite (from Ripley review)

**Your assignments (Phase 2–4):**
- **Phase 2:** Rewrite React UI from chat to search paradigm (keep Vite/TS scaffolding)
  - Replace `App.tsx` and components with search-oriented layout
  - Search bar with instant search, faceted sidebar (author, year range, language, category)
  - Result cards (title, author, year, language, snippet highlighting)
  - Pagination, click-to-view PDF
  - Add `react-router-dom` for routing
  - Remove old chat components (`ChatMessage.tsx`, `Configbar.tsx`, etc.)
- **Phase 3:** "Find Similar Books" feature (uses semantic search from backend)
- **Phase 4:** PDF upload UI (drag-and-drop) and upload endpoint integration

**UI dependencies:**
- Phase 2 blocked until Parker builds search API (2.1)
- PDF viewer component: use `react-pdf` or `pdf.js` via iframe with search term highlighting
- Search API endpoints: `GET /api/search?q=...&author=...&year_from=...`, `GET /api/facets`, `GET /api/books/{id}/pdf`

**Architecture context:**
- Paradigm shift from chat to search requires component rewrite, not refactor
- Full plan in `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

