# Lambert — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (pytest), TypeScript (Vitest), Docker Compose
- **Key test concerns:** PDF processing edge cases, multilingual search quality, metadata extraction, file watcher reliability

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Architecture Plan: QA & Testing (from Ripley review)

**Your assignments (Phase 1–4):**
- **Phase 1:** Write integration tests for end-to-end indexing (PDF in → verify Solr with correct metadata)
  - Test metadata extraction module with sample paths from `/home/jmservera/booklibrary`
  - Verify schema fields populated correctly (title, author, year, category, file_path)
  - Test edge cases: irregular path formats, special characters, missing metadata
- **Phase 2:** API contract tests (search endpoint responses), UI smoke tests (Playwright)
  - Verify facet aggregation (authors, years, languages, categories)
  - Test pagination, highlighting, PDF serving
- **Phase 3:** Embedding quality tests (semantic search precision), benchmark kNN performance
- **Phase 4:** E2E tests, production hardening (health checks, error scenarios)

**Key technical context:**
- Document-lister already works (scans `/data/documents/`, queues to RabbitMQ every 10 min)
- RabbitMQ durable queue `shortembeddings` handles backpressure
- Phase 1 focus: Solr Tika extraction + metadata parsing
- Phase 3 concern: Solr 9.x HNSW vector search with <1M vectors

**Test data source:** `/home/jmservera/booklibrary` (actual user library with old texts, OCR issues)

**Full architecture:** `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

