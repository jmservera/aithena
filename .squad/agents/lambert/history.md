# Lambert — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (pytest), TypeScript (Vitest), Docker Compose
- **Key test concerns:** PDF processing edge cases, multilingual search quality, metadata extraction, file watcher reliability

## Learnings

<!-- Append learnings below -->

### 2026-03-14 — Playwright browser E2E suite for the local stack

- The new browser suite lives in `e2e/playwright/` and is intentionally **read-only**: it discovers suitable indexed queries from the live `/v1/search/` API instead of uploading fixture books, so repeated runs do not mutate Solr or the library mount.
- `playwright.config.ts` keeps `baseURL` aligned with the nginx entry point (`http://localhost`) while `global-setup.ts` polls both `http://localhost/search` and `http://localhost:5173/search`, exporting `PLAYWRIGHT_APP_BASE_URL` so the same tests work against either nginx or the Vite dev server.
- Search, facet, pagination, and PDF tests are data-aware: they skip with explicit reasons when the stack has no indexed books, no meaningful author facet, or no multi-page PDF rather than failing for missing sample data.
- The current PDF viewer is an iframe wrapper with no custom page controls, so Playwright page-navigation coverage is implemented via standard PDF fragment navigation (`#page=2`) after opening the modal.

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

### 2026-03-14 — Local smoke test blockers

- Docker Engine and Docker Compose were available, and `docker compose config --quiet` passed, so the compose file is syntactically valid.
- `zoo1` publishes host port `8080`, which collides with `solr-search` also publishing `8080`; starting `solr-search` failed with `Bind for 0.0.0.0:8080 failed: port is already allocated`.
- The Solr services use `docker-entrypoint.sh solr start -c -f`, but the current `solr:latest` image rejects `-c` with `ERROR: -c is not supported by this script`, leaving `solr` in a restart loop and preventing the platform stack from becoming healthy.
- Because nginx served its default welcome page and no UI was exposed on `localhost:5173`, Playwright could only capture infrastructure evidence (`nginx-home.png`) rather than execute a search/PDF smoke flow.

### 2026-03-14 — Full local smoke retest

- Brett’s compose fixes are effective: ZooKeeper (3 nodes), SolrCloud (3 nodes), Search API, Redis, RabbitMQ, nginx, document-lister, and document-indexer all came up locally with `docker compose up -d --build --pull never`.
- The Solr bind-mounted data directories under `/source/volumes/solr-data*` were owned by `root:root` (`755`), so Solr could not create `core.properties`; fixing ownership to `8983:8983` and re-running the config upload + `CREATE` request was necessary before the `books` collection could be created.
- The stack does **not** auto-bootstrap the `books` collection yet. A manual `solr zk upconfig` plus `collections?action=CREATE&name=books...` was required before `/search` stopped returning 502.
- After collection bootstrap, the backend `/search` API worked but `numFound` stayed `0`; RabbitMQ showed queue `shortembeddings` with `0` messages and one consumer, so no documents had been indexed during the smoke window.
- `aithena-ui` required `npm install --legacy-peer-deps` because `vite@8.0.0` conflicts with `@vitejs/plugin-react@4.7.0` peer requirements during a plain `npm install`.
- Playwright confirmed the React shell loads on `http://localhost:5173`, but search is currently broken in the UI because `aithena-ui/src/hooks/search.tsx` calls `${VITE_API_URL}/v1/search/` while the backend exposes `/search`; browser network logs showed `GET http://localhost:8080/v1/search/?q=balearics... -> 404`.
- Because UI search fails before any results render, PDF viewing and faceted filtering remain unverified in the browser smoke flow.

### 2026-03-14 — /v1 alias verification rerun

- Pulled `origin/jmservera/solrstreamlitui`, started the full compose stack, and waited for Solr (`:8983`) plus the search API (`:8080`) to report healthy.
- The running `aithena-solr-search` container initially still returned `404` for `/v1/search/` and `/v1/health`; rebuilding just the `solr-search` image with `docker compose up -d --build solr-search` picked up Parker’s FastAPI aliases from `solr-search/main.py`.
- After rebuild, `GET http://localhost:8080/v1/search/?q=*&limit=5` returned `200 OK` with the expected response shape, and `GET http://localhost:8080/v1/health` returned the normal health payload.
- Playwright confirmed the UI now calls `GET http://localhost:8080/v1/search/?q=*&limit=10&page=1&sort=score+desc` and receives `200 OK`, so the route mismatch is fixed end-to-end.
- Search still shows `0 results` because Solr collection `books` currently has `numFound: 0`; `/v1/facets` also returns empty arrays, so results, facet rendering, and PDF viewing remain blocked by missing indexed documents rather than routing errors.
- Smoke artifacts captured: `aithena-ui-smoke-initial-2.png`, `aithena-ui-smoke-results.png`, `aithena-ui-smoke-initial.md`, `aithena-ui-smoke-results.md`, `aithena-ui-smoke-network.txt`, and `aithena-ui-smoke-console.txt`.

### 2026-03-14 — Real-book indexing pipeline retest

- `docker compose up -d` brought up Redis, RabbitMQ, ZooKeeper, SolrCloud, `solr-init`, `document-lister`, and `document-indexer`; `solr-init` finished and `http://localhost:8983/solr/books/admin/ping` returned healthy.
- The real library mount is present: `/data/documents` exposed 169 files across folders like `amades/`, `balearics/`, `bsal/`, and `ultima hora/` inside the running containers.
- Automatic indexing is still broken: after waiting through multiple poll intervals, Solr stayed at `numFound=0`, RabbitMQ queue `shortembeddings` stayed empty, and Redis had no `/shortembeddings/*` state keys.
- `document-lister` logs stop after `Declaring queue shortembeddings`; there are no `Found new document` or `Document already processed` lines, so the lister never enqueued the mounted PDFs during the smoke window.
- A manual RabbitMQ publish of `balearics/ESTUDIS_BALEARICS_01.pdf` proved the downstream path is partially alive: `document-indexer` consumed it and Solr indexed one document with `title_s="ESTUDIS BALEARICS 01"`, `category_s="Balearics"`, `author_s="Unknown"`.
- The indexer then crashed during Redis state persistence with `TypeError: multiple values for argument 'file_path'` in `document_indexer/__main__.py` (`save_state(...)`), marking the sample as failed in Redis even though the Solr document was already written.
- Net result: the autonomous `document-lister -> RabbitMQ -> document-indexer -> Solr` flow did **not** succeed end-to-end; only a manually enqueued sample reached Solr, and even that ended in a post-index failure state.

### 2026-03-14 — P2 real search validation with indexed books

- Starting the stack with plain `docker compose up -d` still left `document-indexer` in `Created` state while `document-lister` was already queueing real PDFs; at that point Solr only contained the old `blank.pdf` test document, so real-book search was still blocked immediately after startup.
- Running `docker compose up -d document-indexer` started the consumer, RabbitMQ `shortembeddings` switched to `consumers=1`, and Solr grew to `76` indexed documents during the smoke window while the queue continued draining.
- Real full-text search now works once the indexer is actually running: querying API `/v1/search/?q=Etnologia&limit=5` returned `1` hit for `amades/costumari 1 1 -3 OCR.pdf`, proving content words from an indexed book are searchable.
- Facets are now populated on wildcard search: at the validation point `/v1/search/?q=*&limit=1` reported `76` total results with non-empty `author` (7 values), `category` (2), `year` (24), and `language` (3) facet groups.
- Playwright verified the Vite UI against the live stack: searching `AMADES` showed `7` visible results, rendered facet filters (Author, Category, Language), and displayed real indexed titles such as `Auca dels edificis notables de Barcelona` and `costumari 1 1 -3 OCR`.
- Metadata quality is **partial** rather than fully good: sampled Amades titles/authors look correct and BSAL category extraction appears, but OCR-heavy docs still surface noisy author/title values (for example `Ocr`) and many records depend on extracted text quality.

