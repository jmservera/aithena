# Ash — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Apache Solr, Docker Compose, multilingual embeddings (768-dim)
- **Languages:** Spanish, Catalan, French, English (including very old texts)
- **Current setup:** Qdrant vector DB with embeddings-server (sentence-transformers), being transitioned to Solr

## Learnings

<!-- Append learnings below -->

### 2026-03-13 — Phase 1 book schema fields implemented

- Added explicit book metadata fields in `solr/books/managed-schema.xml`: `title_s`, `title_t`, `author_s`, `author_t`, `year_i`, `page_count_i`, `file_path_s`, `folder_path_s`, `category_s`, `file_size_l`, and `language_detected_s`.
- Added `copyField` rules from `title_t` and `author_t` into `_text_` so general catch-all queries include book title and author terms without removing any Tika-generated metadata fields.
- Updated `solr/books/solrconfig.xml` to default `/query` and `/select` highlighting to the unified highlighter, with `content` as the stored snippet source and `_text_` configured with an alternate-field fallback. This keeps highlight support aligned with catch-all search without duplicating stored full text in `_text_`.

### 2026-03-13T20:58 — Phase 2–3 GitHub Issues Assigned

- Ripley decomposed Phase 2 and 3 into issues #36–#47, all assigned to `@copilot` with squad labels and release milestones.
- **Your Phase 2 issues:** #42–#44 (Search API tuning, faceting, highlighting)
- **Your Phase 3 issues:** #45–#47 (Vector field config, kNN setup, performance benchmarking)
- Full dependency chain and rationale in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition".

**Your assignments (Phase 1–3):**
- **Phase 1 (URGENT):** Add book-specific fields to managed-schema.xml:
  - `title_s` (string, stored), `title_t` (text_general, indexed)
  - `author_s` (string, stored, facetable)
  - `year_i` (int, facetable)
  - `language_s` (string — already via langid, but make explicit)
  - `page_count_i` (int)
  - `file_path_s` (string, stored)
  - `folder_path_s` (string, stored)
  - `category_s` (string, stored, facetable)
  - Keep existing auto-generated Tika metadata fields
- **Phase 2:** Search tuning (faceting config, highlighting, result boosting)
- **Phase 3:** Vector field config for kNN search
  - Add `DenseVectorField` for embeddings (512-dim for distiluse v2)
  - Configure HNSW similarity function (cosine)

**Key architectural decisions:**
- Hybrid indexing: Tika handles full-text + metadata extraction (Phase 1), app-side chunking for embeddings (Phase 3)
- Solr 9.x native kNN support for vector search
- Embeddings model: Standardize on `distiluse-base-multilingual-cased-v2` (512-dim)

**Critical blockers:**
- Phase 1 schema changes must complete before Parker can rewrite the indexer
- Ripley will review & approve schema changes before cluster deployment

**Full context:** `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

### 2026-03-13 — Cross-agent coordination (Phase 1.2–1.5)

**From Parker's indexer work:**
- Parker is populating fields `title_s`, `author_s`, `year_i`, `category_s`, `file_path_s`, `folder_path_s` via `literal.*` params in Solr `/update/extract`.
- Your schema decisions are enabling stable field names across indexing and search. All fields confirmed implemented in managed-schema.xml.

**From Lambert's test suite:**
- Lambert's 15 metadata extraction tests validate the parser contracts you'll search against. 4 intentional failures expose parser gaps—review `document-indexer/tests/test_metadata.py` for expected shapes before Phase 2 tuning.
- Test patterns (amades/, balearics/, bsal/) align with your copyField strategy for author/category faceting.

### 2026-03-15 — Reskilling: Complete search infrastructure review (ADR-004 → Phase 3+4 delivered)

#### Solr Schema Inventory (Complete)

**Field Types Defined:**
- **Vector field:** `knn_vector_512` — DenseVectorField with 512 dimensions, cosine similarity, HNSW index (distiluse-base-multilingual-cased-v2 model per ADR-004)
- **Multilingual text:** `text_en`, `text_es`, `text_fr`, `text_ca`, `text_de`, etc. — language-specific tokenizers, stemmers, stop-word filters
- **Numeric types:** `pint` (int), `plong` (long), `pdouble` (double), `pfloat` (float) — with docValues enabled
- **String types:** `string` (sortable, facetable), `strings` (multiValued)
- **Timestamp types:** `pdate`, `pdates` — date/time with docValues
- **Catch-all:** `text_general` — standard Solr text analyzer for indexed content

**Indexed Fields (Book Metadata):**
- **Stored & searchable:** `title_s` (string), `title_t` (text_general), `author_s` (string), `author_t` (text_general)
- **Facet fields:** `author_s`, `category_s`, `year_i`, `language_detected_s`, `language_s`
- **Numeric metadata:** `year_i`, `page_count_i`, `file_size_l`
- **Path fields:** `file_path_s`, `folder_path_s` (both stored, for document resolution)
- **Vector fields:** `book_embedding` (knn_vector_512, indexed, stored) — per-document embeddings
- **Chunk-level fields:** `chunk_text_t` (full text), `embedding_v` (knn_vector_512), `chunk_index_i`, `parent_id_s`, `page_start_i`, `page_end_i`
- **Tika-generated:** ~50+ auto-extracted fields (PDF metadata, content type, permissions, etc.)
- **Copy-field rules:** `title_t` → `_text_`, `author_t` → `_text_` (enables title/author in catch-all queries)

**Dynamic Fields:**
- Extensive language-specific suffixes (`*_txt_en`, `*_txt_es`, etc.)
- Numeric variants: `*_i` (pint), `*_s` (string), `*_l` (plong), `*_f` (pfloat), `*_d` (pdouble)
- Tika fallback: content copied to `*_str` fields (256-char limit for faceting)

#### Search Modes & Implementation

**1. Keyword Mode (BM25, default)**
- Handler: `/v1/search?mode=keyword` or `/v1/search` (defaults to keyword)
- Query type: `edismax` (Extended Dismax parser)
- Fields searched: `_text_` (via catch-all), `title_t`, `author_t`, `content` (all populated via copyField or Tika)
- Results: BM25 relevance scores, facet counts (author, category, year, language), highlights from `content` and `_text_`
- Pagination: `page` (1-indexed) + `page_size` (default 20, max 100)
- Sorting: `score`, `title_s`, `author_s`, `year_i`, `category_s`, `language_s`, `language_detected_s`
- Filters: `fq_author`, `fq_category`, `fq_language`, `fq_year` (facet-aware filter queries)

**2. Semantic Mode (kNN, Solr HNSW)**
- Handler: `/v1/search?mode=semantic`
- Query vector: embedded via embeddings-server (distiluse-base-multilingual-cased-v2, 512-dim)
- Field: `book_embedding` (knn_vector_512, HNSW index)
- Query syntax: `{!knn f=book_embedding topK=top_k}[v0,v1,...]`
- Results: cosine similarity scores, **NO facets** (kNN doesn't support Solr facet aggregation), **NO highlights**
- Pagination: fixed `top_k=page_size` (1 "page" of kNN results)
- Filters: supported via `fq` clauses (before kNN search)
- Limitation: empty query string → 400 error (must embed something)

**3. Hybrid Mode (RRF fusion)**
- Handler: `/v1/search?mode=hybrid`
- Parallel execution: BM25 leg + kNN leg simultaneously
- Fusion algorithm: Reciprocal Rank Fusion (RRF) with damping constant `k=60` (configurable via `RRF_K` env var)
- Scoring: `rrf_score = sum(1/(k + rank_i)) for rank_i in [bm25_rank, knn_rank]`
- Results: fused ranking, facets + highlights from BM25 leg, kNN-only matches boosted
- Pagination: `page_size` applied to final fused results

#### kNN/Embedding Configuration

**Embeddings Server:**
- URL: `http://embeddings-server:8001/v1/embeddings/` (configurable via `EMBEDDINGS_URL`)
- Model: `distiluse-base-multilingual-cased-v2` (multilingual, 512-dim output)
- Timeout: 120s (configurable via `EMBEDDINGS_TIMEOUT`)
- Request payload: `{"input": "text_to_embed"}`
- Response format: `{"data": [{"embedding": [v0, v1, ...]}]}`
- Called at query time (semantic + hybrid search) and indexing time (document-indexer)

**Solr kNN Index:**
- Field type: `DenseVectorField` with `vectorDimension="512"`, `similarityFunction="cosine"`, `knnAlgorithm="hnsw"`
- HNSW tuning: Solr defaults (ef=200 for construction, dynamically tuned at query time)
- Index location: `book_embedding` field (1 vector per document)

#### Similar Books Endpoint

**Handler:** `GET /v1/books/{document_id}/similar`
- Fetches the document's `book_embedding` vector from Solr
- Executes kNN query with that vector as the seed
- Returns top-k similar books (cosine neighbors)
- Contract: Returns `{results, query, mode: "semantic", ...}` (same shape as `/search?mode=semantic`)

#### API Statistics & Status Endpoints

**Stats Endpoint:** `GET /v1/stats/`
- Returns: `total_books`, `by_language` (facet), `by_author` (facet), `by_year` (facet), `by_category` (facet), `page_stats` (min/max/avg page count)
- Query: Solr `stats` component on `page_count_i` + `facets` on metadata fields
- Use case: collection size, distribution analysis

**Status Endpoint:** `GET /v1/status`
- Aggregated health: Solr, Redis, RabbitMQ
- Returns: per-service status (UP/DOWN), error details, indexing progress (via Redis key pattern `doc:*`)
- TCP checks for Redis/RabbitMQ connectivity; Solr health via `/admin/ping`

#### Search Service Helpers (search_service.py)

**Query Building:**
- `build_solr_params()` — constructs full `/select` query with facets, highlights, pagination
- `build_knn_params()` — constructs kNN local-parameter syntax
- `normalize_search_query()` — sanitizes user input, rejects `{!` to prevent injection
- `solr_escape()` — escapes Lucene special chars for literal filters

**Result Processing:**
- `normalize_book()` — transforms raw Solr doc → API book schema (title, author, year, pages, score, highlights, document_url)
- `parse_facet_counts()` — extracts and normalizes Solr facet counts to `{author: [{value, count}], ...}`
- `collect_highlights()` — merges snippets from multiple highlight fields
- `reciprocal_rank_fusion()` — RRF algorithm implementation

**Document Access:**
- `encode_document_token()` — base64-url encodes file_path for safe document_id
- `decode_document_token()` — reverses encoding (with validation)
- `resolve_document_path()` — safely resolves token back to filesystem path (prevents directory traversal)

#### Environment Configuration (config.py)

**Solr:**
- `SOLR_URL` (default: `http://solr:8983/solr`)
- `SOLR_COLLECTION` (default: `books`)
- `SOLR_TIMEOUT` (default: 30s)

**Search:**
- `DEFAULT_SEARCH_MODE` (default: `keyword`)
- `RRF_K` (default: 60)
- `KNN_FIELD` (default: `book_embedding`)

**Embeddings:**
- `EMBEDDINGS_URL`, `EMBEDDINGS_TIMEOUT`

**Document Serving:**
- `BASE_PATH` (default: `/data/documents`) — root for file resolution
- `DOCUMENT_URL_BASE` (optional) — external URL prefix for document links

**Pagination:**
- `DEFAULT_PAGE_SIZE` (default: 20)
- `MAX_PAGE_SIZE` (default: 100)
- `FACET_LIMIT` (default: 25)

**Monitoring (Phase 4):**
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_KEY_PATTERN` (indexing status)
- `RABBITMQ_HOST`, `RABBITMQ_PORT`

#### Recent Milestones (Git History)

- **Phase 4:** `/v1/status` endpoint with health aggregation (PR #159)
- **Phase 3.5:** Page range tracking in search results (`page_start_i`, `page_end_i` returned in result)
- **Phase 3.2:** `/v1/stats` endpoint with collection statistics
- **Phase 3.1:** Similar books endpoint (`/v1/books/{id}/similar`) using kNN
- **Phase 3:** Hybrid search modes (keyword + semantic + hybrid RRF), embeddings integration
- **Phase 2:** Faceting, highlighting, result sorting, BM25 tuning

#### Gaps & Future Work

1. **Chunk-level search:** Fields exist (`chunk_text_t`, `embedding_v`, `chunk_index_i`, `page_start_i`, `page_end_i`, `parent_id_s`) but no API endpoint routes chunk queries yet
2. **Reranking:** No cross-encoder reranking on hybrid results (only RRF)
3. **Query expansion:** No synonym injection or query rewriting
4. **Performance:** No mention of query caching or result deduplication

