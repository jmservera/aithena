# Squad Team

> aithena — Book library search engine with Solr full-text indexing, multilingual embeddings, PDF processing, and React UI

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Ripley | Lead | `.squad/agents/ripley/charter.md` | Active |
| Parker | Backend Dev | `.squad/agents/parker/charter.md` | Active |
| Dallas | Frontend Dev | `.squad/agents/dallas/charter.md` | Active |
| Ash | Search Engineer | `.squad/agents/ash/charter.md` | Active |
| Lambert | Tester | `.squad/agents/lambert/charter.md` | Active |
| Scribe | Session Logger | `.squad/agents/scribe/charter.md` | Active |
| Ralph | Work Monitor | — | Monitor |
| Brett | Infra Architect | `.squad/agents/brett/charter.md` | Active |
| Kane | Security Engineer | `.squad/agents/kane/charter.md` | Active |
| Juanma | Product Owner | — | Human |
| @copilot | Coding Agent | `.squad/agents/copilot/charter.md` | Active |
| Newt | Product Manager | `.squad/agents/newt/charter.md` | Active |


## Coding Agent

<!-- copilot-auto-assign: true -->

| Name | Role | Charter | Status |
|------|------|---------|--------|
| @copilot | Coding Agent | — | 🤖 Coding Agent |

### Capabilities

**🟢 Good fit — auto-route when enabled:**
- Bug fixes with clear reproduction steps
- Test coverage (adding missing tests, fixing flaky tests)
- Lint/format fixes and code style cleanup
- Dependency updates and version bumps
- Small isolated features with clear specs
- Boilerplate/scaffolding generation
- Documentation fixes and README updates

**🟡 Needs review — route to @copilot but flag for squad member PR review:**
- Medium features with clear specs and acceptance criteria
- Refactoring with existing test coverage
- API endpoint additions following established patterns
- Migration scripts with well-defined schemas

**🔴 Not suitable — route to squad member instead:**
- Architecture decisions and system design
- Multi-system integration requiring coordination
- Ambiguous requirements needing clarification
- Security-critical changes (auth, encryption, access control)
- Performance-critical paths requiring benchmarking
- Changes requiring cross-team discussion

## Project Context

- **Project:** aithena
- **User:** jmservera
- **Created:** 2026-03-13
- **Stack:** Python (backend services), TypeScript/React + Vite (UI), Docker Compose, Apache Solr (search), multilingual embeddings
- **Description:** A book library database that indexes PDFs using Solr for full-text search. Extracts metadata (author, date, language) from filenames, folder names, and PDF content. Supports multilingual texts (Spanish, Catalan, French, English), including very old documents. Features file watching for new books, PDF upload via UI, search with filtering, and PDF viewing with highlighting. Plans to enhance native Solr word search with local multilingual embedding models.
- **Book library path:** Ask user during first run, typically: `~/booklibrary`
- **Existing services:** Redis, RabbitMQ, Qdrant (being replaced by Solr), LLaMA server, embeddings server, document lister/indexer, qdrant-search API, React UI (aithena-ui)
