# Ripley — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), TypeScript/React + Vite (UI), Docker Compose, Apache Solr, multilingual embeddings
- **Book library:** `/home/jmservera/booklibrary`
- **Existing services:** Redis, RabbitMQ, Qdrant (being replaced), LLaMA server, embeddings server, document lister/indexer, search API, React UI

## Core Context

**Architectural Achievements (Phase 2-3 Complete):**
- Solr migration COMPLETE: SolrCloud 3-node cluster, Tika extraction, multilingual langid detection
- FastAPI search service (`solr-search/`) live: secure, well-tested (+11 unit tests), clean architecture
- React search UI converted from chat to search: FacetPanel, ActiveFilters, BookCard, pagination, sort
- PDF viewer panel integrated with page navigation
- Status + Stats tabs: health monitoring (Solr, Redis, RabbitMQ), collection stats by lang/author/year/category
- Embeddings model aligned to `distiluse-base-multilingual-cased-v2`, dense vectors added, chunking implemented
- Search modes (keyword/semantic/hybrid) with RRF fusion; similar-books endpoint working

**Critical Bugs Identified:**
- #166: RabbitMQ timeout on first start (khepri_projections)
- #167: Document pipeline stalled (new files not detected)

**Branch Management Lessons:**
- Copilot agents must pull fresh base before starting (prevent stale branches by 28+ commits)
- Stale branches create "time bomb" PRs that delete recently merged work
- Established guardrails: explicit base-branch instructions, scope fences, dependency gating

**Codbase patterns established:**
- Clean Architecture: Presentation → Application → Domain → Infrastructure
- TDD mandatory for all work; all services have 8-14 unit tests each
- Type-first: Backend Python return dicts mirror TypeScript interface contracts
- Zero defects: Phase 2 + 3 PRs merged with clean code quality

**Outstanding Work:**
- v0.5 Phase 3 completion: #163 (search mode selector UI), #41 (frontend tests), #47 (similar books UI)
- v0.6 Phase 4: upload endpoint (#49), upload UI (#50), hardening (#52)
- Security scanning: #88-#98 (requires triage or Kane assignment)

## Learnings

<!-- Append learnings below -->

### 2026-03-14T23:xx — Reskill: Current Codebase State & v0.5 Roadmap Update

**Release Status:**
- **v0.4.0 SHIPPED** — All 7 Phase 2 PRs merged to `dev` (Search API, UI, Status/Stats tabs, PDF navigation). Release commit: `c27fa4b`
- **v0.5 (Phase 3: Embeddings Enhancement) IN PROGRESS** — 5 of 6 core issues verified complete on `dev`:
  - #42, #43, #44, #45, #46 all delivered (embeddings model, dense vectors, chunking, search modes, similar-books API)
  - #163 (search mode selector UI) created as the remaining gap — assigned `squad:copilot`, 🟢 good fit
  - Two parallel copilot issues also open: #41 (frontend tests, 🟢) and #47 (similar books UI, 🟡 needs review)
- **v0.6 (Phase 4)** planned but unstarted — upload endpoint (#49), upload UI (#50), hardening (#52)

**Key Patterns Observed:**
1. **Copilot work is highly reliable:** Phase 2 + Phase 3 PRs are well-structured, test-covered, clean code. Zero defects merged to dev.
2. **Phase-based issue decomposition works:** Explicit dependencies + single-owner issues prevent PR sprawl.
3. **Architecture board (decisions.md) is the source of truth:** All major decisions (ADRs, team assignments, risk mitigations) recorded and traceable.
4. **Clean Code + TDD is the standard:** All services follow separation of concerns, comprehensive type hints, error handling edge cases in tests.

**Next Lead Action Items:**
1. Triage & assign bugs #166-#167 (RabbitMQ + file detection failures)
2. Clarify v0.5 copilot queue: #163, #41, #47 parallelization + merge sequencing
3. Review open security scanning issues (#88-#98) — defer or assign to security team (Kane)?
4. Plan v0.6 roadmap: #49, #50, #52 — coordinate with Parker (backend) + Dallas (frontend) + Ash (search tuning)
