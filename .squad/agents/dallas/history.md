# Dallas — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** TypeScript, React, Vite
- **Existing UI:** aithena-ui directory with React + Vite setup
- **UI package.json location:** aithena-ui/package.json

## Learnings

<!-- Append learnings below -->

### 2026-03-13T20:58 — Phase 2–4 GitHub Issues Assigned

- Ripley decomposed Phase 2–4 into issues #36–#53, all assigned to `@copilot` with squad labels and release milestones.
- **Your Phase 2 issues:** #42–#44 (Search UI component rewrite, PDF viewer, frontend tests)
- **Your Phase 3 issues:** #45–#47 (Similar books feature, semantic search integration)
- **Your Phase 4 issues:** #48–#51 (PDF upload UI, admin dashboard)
- Full dependency chain and rationale in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition".

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

