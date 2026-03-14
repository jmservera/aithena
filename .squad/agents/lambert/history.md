# Lambert — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (pytest), TypeScript (Vitest), Docker Compose
- **Key test concerns:** PDF processing edge cases, multilingual search quality, metadata extraction, file watcher reliability

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Metadata extraction test design

**Real library patterns discovered from `/home/jmservera/booklibrary`:**
- `amades/` behaves like an author folder: files such as `Auca dels costums de Barcelona amades.pdf` and `costumari 1 1 -3 OCR.pdf` should resolve author `Amades`, with author suffixes stripped from titles when duplicated.
- `balearics/ESTUDIS_BALEARICS_01.pdf` behaves like a category/series folder with uppercase underscore-heavy stems; tests expect category extraction plus a readable title.
- `bsal/Bolletí societat arqueologica luliana 1885 - 1886.pdf` is a critical edge case: the year range must stay in the title and must not be misread as `author - title` or a single `year`.

**Key test decisions:**
- `file_path` and `folder_path` are asserted relative to `base_path`, not absolute host paths.
- Unknown patterns are tested with conservative fallbacks: keep the filename stem as title, set author to `Unknown`, and avoid guessing from extra nested folders.
- The new pytest suite currently lands at **11 passing / 4 failing**, with the remaining failures intentionally flagging parser bugs in fallback handling, deep nested paths, and year-range parsing.

### 2026-03-13T20:58 — Phase 1–4 GitHub Issues Assigned

- Ripley decomposed the entire remaining roadmap into 18 single-owner issues (#36–#53), all assigned to `@copilot` with squad labels and release milestones.
- **Your Phase 1 issues:** Metadata extraction tests already written (11 passing, 4 intentional fails)
- **Your Phase 2 issues:** #36–#41 (API + UI integration tests, faceting validation, PDF serving tests)
- **Your Phase 3 issues:** #42–#47 (Embedding quality tests, semantic search benchmarks, kNN performance)
- **Your Phase 4 issues:** #48–#53 (E2E tests, production hardening, health checks, error scenarios)
- Full dependency chain and rationale in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition".

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

### 2026-03-13 — Cross-agent coordination (Phase 1.2–1.5)

**From Ash's schema work:**
- Ash finalized schema with 11 explicit book fields: title_s, author_s, year_i, category_s, file_path_s, folder_path_s, etc. Your test patterns match these field names exactly.
- copyField rules from title_t/author_t into _text_ enable catch-all search while keeping highlights tied to content field.

**From Parker's indexer work:**
- Parker's `extract_metadata()` populates title_s, author_s, year_i, category_s directly from filesystem path parsing. His parser handles amades/ (author), balearics/ (category), bsal/ (journal) patterns.
- Your test suite validates Parker's parser contracts: relative paths, conservative fallbacks, year-range handling. 4 failing tests flag real parser gaps to address in Phase 1.5.

### 2026-03-14 — Ruff linting baseline added to CI

- Added root `ruff.toml` targeting Python 3.11 with 120-character lines, Ruff lint families `E/F/W/I/UP/B/SIM/S`, and test-specific allowances (`S101` globally, all `S` rules under `tests/**`).
- Updated `.github/workflows/ci.yml` with a `python-lint` job using `astral-sh/ruff-action@v3`; each Ruff step uses `continue-on-error: true` so the new checks are visible in CI without gating merges before LINT-5.
- Current repo baseline from the root: `ruff check .` reports **107** lint violations and `ruff format --check .` reports **23** files needing reformatting.
- Regression check after the CI change: `document-indexer` tests still pass (**51 passed**), and `solr-search` suites still pass (**18 passed** total).

