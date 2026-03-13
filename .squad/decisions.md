# Squad Decisions

## Active Decisions

### Architecture Plan — aithena Solr Migration (2026-03-13)

**Author:** Ripley (Lead)  
**Status:** PROPOSED — awaiting team review  
**Branch:** `jmservera/solrstreamlitui`

#### Executive Summary

Solid SolrCloud infrastructure exists, but the indexing pipeline is Qdrant-bound. Plan: 4-phase migration to Solr-native search with semantic layer (Phase 3).

**Phases:**
1. **Core Solr Indexing:** Fix volume mounting, add schema fields, rewrite indexer for Tika extraction, metadata extraction module
2. **Search API & UI:** FastAPI search service, React search interface with faceting, PDF viewer
3. **Embeddings Enhancement:** Vector field in Solr, embedding indexing pipeline, hybrid search mode, similar books feature
4. **Polish:** File watcher (60s polling), PDF upload endpoint, admin dashboard, production hardening

#### Key Architectural Decisions (ADRs)

| ADR | Decision | Rationale |
|---|---|---|
| ADR-001 | Hybrid indexing: Solr Tika (full-text) + app-side chunking (embeddings, Ph.3) | Fast Phase 1 execution, better control for Phase 3 |
| ADR-002 | Build metadata extraction module for filesystem path parsing | Explicit book fields (title, author, year, category) in Solr |
| ADR-003 | FastAPI for search API | Consistent with Python backend stack, thin Solr wrapper |
| ADR-004 | Standardize on `distiluse-base-multilingual-cased-v2` (Phase 3) | Lightweight, good multilingual support; resolve Dockerfile/main.py mismatch |
| ADR-005 | React UI rewrite (chat → search), keep Vite/TS scaffolding | Paradigm shift requires component rewrite, not refactor |

#### Team Assignments

| Member | Ph.1 | Ph.2 | Ph.3 | Ph.4 |
|---|---|---|---|---|
| **Parker** (backend) | Indexer rewrite, metadata extraction, volume fix | Search API (FastAPI) | Embedding pipeline, hybrid search | Upload endpoint, file watcher |
| **Dallas** (frontend) | — | Search UI, PDF viewer | Similar books feature | Upload UI |
| **Ash** (search) | Schema fields (title, author, year, category, etc.) | Search API tuning | Vector field config, kNN setup | — |
| **Lambert** (tester) | Integration tests (PDF → Solr) | API + UI tests | Embedding quality tests | E2E tests, production hardening |
| **Ripley** (lead) | Architecture review, decision approval | API contract review | Model selection review | Production readiness review |

#### Immediate Next Steps

1. Ash: Add book-specific fields to Solr schema (title_s, author_s, year_i, category_s, etc.)
2. Parker: Fix `docker-compose.yml` volume mapping (`/home/jmservera/booklibrary` → `/data/documents`)
3. Parker: Rewrite `document-indexer` for Solr Tika extraction (drop Qdrant dependency)
4. Parker: Build metadata extraction module with path parsing (support `Author/Title.pdf`, `Category/Author - Title (Year).pdf` patterns)
5. Lambert: Write tests for metadata extraction using actual library paths
6. Ripley: Review & approve schema changes before cluster deployment

#### Critical Gaps (to fix in Ph.1)

1. Book library (`/home/jmservera/booklibrary`) not mounted in docker-compose
2. Indexer fully Qdrant-dependent (imports `qdrant_client`, uses `pdfplumber` not Solr Tika)
3. No search API (qdrant-search commented out)
4. Schema lacks explicit book domain fields
5. Embeddings model mismatch (Dockerfile vs main.py)
6. React UI designed for chat, not search

#### Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Large PDF library overwhelms Solr Tika | HIGH | Batch with backpressure (RabbitMQ prefetch=1), retry + DLQ |
| Old books have OCR-quality text | MEDIUM | Accept lower quality; embeddings may handle noisy text better |
| Solr kNN search performance at scale | MEDIUM | Benchmark with real data in Phase 3 (Solr 9.x HNSW suitable for <1M vectors) |
| Docker bind-mount perf on macOS | LOW | Dev only; production on Linux is fine |
| Metadata heuristics fail on irregular paths | MEDIUM | Build with fallback defaults (title=filename, author="Unknown"), improve iteratively |

**Full architecture plan, current state assessment, phased breakdown, service diagram, and team roadmap:** See `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

---

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
