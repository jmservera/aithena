# Architecture Plan — aithena Book Library Search Engine

**Author:** Ripley (Lead)
**Date:** 2026-03-13
**Branch:** `jmservera/solrstreamlitui`
**Status:** PROPOSED — awaiting team review

---

## Executive Summary

This branch has solid infrastructure foundations: a 3-node SolrCloud cluster with ZooKeeper, multilingual field types for ~20 languages, Tika extraction enabled, language detection configured, a document-lister polling service, and Redis/RabbitMQ for state and queuing. However, the indexing pipeline is still fully Qdrant-bound and the search API + UI don't exist yet.

The plan is four phases: get PDFs indexed into Solr end-to-end, build the search experience, layer in semantic search, then polish with file watching and uploads.

---

## Current State Assessment

### What EXISTS and is SOLID

| Component | Status | Notes |
|---|---|---|
| SolrCloud (3 nodes + 3 ZK) | ✅ Running | `docker-compose.yml` lines 182–296 |
| Solr extraction module | ✅ Configured | `/update/extract` handler with Tika |
| Solr langid module | ✅ Configured | Auto-detects language → `language_s` field |
| Multilingual field types | ✅ Schema has ~20 | `text_ca`, `text_es`, `text_fr`, `text_en`, etc. with stopwords + stemmers |
| Dynamic fields for languages | ✅ | `*_txt_ca`, `*_txt_es`, etc. |
| Document lister service | ✅ Working | Scans `/data/documents/`, tracks state in Redis, queues to RabbitMQ every 10 min |
| Redis state tracking | ✅ Working | Tracks path, last_modified, processed status |
| RabbitMQ queue | ✅ Working | Durable queue `shortembeddings` |
| Embeddings server | ✅ Builds | FastAPI + `distiluse-base-multilingual-cased-v2` (768-dim) |
| Streamlit admin UI | ✅ Basic | Shows document queue state from Redis |
| React UI (aithena-ui) | ✅ Scaffolded | But designed for chat, not search |
| Nginx + Certbot | ✅ Configured | TLS termination ready |

### What's BROKEN or MISSING

| Issue | Severity | Detail |
|---|---|---|
| **Document indexer → Qdrant** | 🔴 CRITICAL | `document_indexer/__main__.py` hard-imports `qdrant_client`, uses `pdfplumber` for text extraction instead of Solr Tika. The entire indexing pipeline bypasses Solr. |
| **No search API** | 🔴 CRITICAL | `qdrant-search` is commented out. No replacement exists for Solr. |
| **Book library not mounted** | 🔴 CRITICAL | User's library is at `/home/jmservera/booklibrary` on host. `document-data` volume maps to `/source/volumes/document-data`. The actual books aren't accessible to the services. |
| **Indexer reads from Azure Blob** | 🟡 HIGH | `document_indexer` uses `BlobStorage` (Azure SDK) to download files. For local library indexing, this needs to be replaced with local file access. |
| **Schema lacks book fields** | 🟡 HIGH | No explicit `title`, `author`, `year`, `language`, `page_count`, `file_path`, `folder_path` fields. Current fields are auto-generated Tika metadata (`pdf_docinfo_*`, `stream_name`, etc.). |
| **Embeddings model mismatch** | 🟡 MEDIUM | Dockerfile pulls `distiluse-base-multilingual-cased-v2`, but `main.py` loads `use-cmlm-multilingual`. Need to decide on ONE model. |
| **React UI is chat-oriented** | 🟡 MEDIUM | Current UI talks to `/v1/question/` (LLaMA-powered Q&A). Needs redesign for search + facets + PDF viewer. |
| **No file watcher** | 🟢 LOW (Phase 4) | Current 10-min polling works but isn't real-time. |
| **No upload endpoint** | 🟢 LOW (Phase 4) | No way to add books through UI. |

---

## Key Architectural Decisions Needed

### ADR-001: Indexing Strategy — Solr Tika vs Application-Side Extraction

**Options:**
1. **Solr-native Tika extraction** — POST PDFs directly to `/update/extract`. Solr extracts text + metadata via Tika. Simpler, fewer moving parts.
2. **Application-side extraction** — Use `pdfplumber`/`PyMuPDF` in a Python service, then POST structured JSON to Solr. More control over chunking and metadata.
3. **Hybrid** — Use Solr Tika for full-text indexing + metadata, use application-side for per-page chunks (for embeddings later).

**Recommendation:** Option 3 (Hybrid). Solr Tika handles the heavy lifting for full-text search (Phase 1). Later, the app-side chunker generates page-level chunks for embeddings (Phase 3). This gets us to a working search fastest.

### ADR-002: Metadata Extraction from Filesystem Paths

Books are organized in the filesystem with structure like `Author/Title (Year).pdf` or `Category/Author - Title.pdf`.

**Recommendation:** Build a Python metadata-extraction module that parses folder structure and filenames using regex heuristics. Store extracted metadata as explicit Solr fields (`author_s`, `title_s`, `year_i`, `category_s`). This runs in the indexer service before Solr submission.

### ADR-003: Search API Technology

**Options:**
1. **FastAPI (Python)** — Consistent with existing backend services. Can share Solr client code.
2. **Express/Node.js** — Closer to the React frontend stack.

**Recommendation:** FastAPI. All backend services are Python. The search API is a thin wrapper around Solr's `/select` endpoint with additional logic for faceting and highlighting config.

### ADR-004: Embeddings Model

**Options:**
- `distiluse-base-multilingual-cased-v2` (512-dim, fast, lighter)
- `use-cmlm-multilingual` (768-dim, heavier, multilingual BERT)
- `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, good balance)

**Recommendation:** Defer to Phase 3. For now, freeze embeddings server as-is. Resolve the Dockerfile/main.py mismatch by standardizing on `distiluse-base-multilingual-cased-v2` (already in Dockerfile). It handles ES/CA/FR/EN well and is lightweight.

### ADR-005: React UI — Rewrite or Refactor?

The existing React UI is a chat interface (LLaMA Q&A). The new requirement is a search interface with faceted filtering, result list, and PDF viewer.

**Recommendation:** Keep the React/Vite/TypeScript scaffolding. Replace `App.tsx` and components with a search-oriented layout. The chat approach is fundamentally different from search UX — this is effectively a rewrite of the UI components, not a refactor.

---

## Phased Architecture Plan

### Phase 1: Core Solr Indexing (Foundation)

**Goal:** PDFs from the book library are indexed into Solr with full text + metadata, searchable via Solr admin UI.

#### 1.1 Fix Volume Mapping
- **What:** Mount `/home/jmservera/booklibrary` into services as `/data/documents`
- **Who:** Parker (backend)
- **Change:** Update `docker-compose.yml` `document-data` volume to bind-mount the actual book library path
- **Risk:** Large library may need incremental indexing strategy

#### 1.2 Add Book-Specific Schema Fields
- **What:** Add explicit fields to `managed-schema.xml`:
  ```
  title_s (string, stored)
  title_t (text_general, indexed)
  author_s (string, stored, facetable)
  year_i (int, facetable)
  language_s (string — already exists via langid)
  page_count_i (int)
  file_path_s (string, stored)
  folder_path_s (string, stored)
  category_s (string, stored, facetable)
  ```
- **Who:** Ash (search)
- **Dependency:** None
- **Note:** Keep existing auto-generated fields (Tika metadata) — they're useful. Add these on top.

#### 1.3 Build Solr Indexer Service
- **What:** Rewrite `document-indexer` to:
  1. Consume from RabbitMQ queue (keep existing pattern)
  2. Read PDF from local filesystem (replace Azure Blob Storage)
  3. Extract metadata from filename/path (new module)
  4. POST PDF to Solr `/update/extract` with metadata as literal fields
  5. Update Redis state to `processed: true`
- **Who:** Parker (backend)
- **Dependencies:** 1.1, 1.2
- **Key detail:** Use `curl`-equivalent: `POST /update/extract?literal.id=<hash>&literal.author_s=<author>&literal.title_s=<title>` with the PDF binary as the body. Solr Tika handles text extraction.

#### 1.4 Metadata Extraction Module
- **What:** Python module that parses book paths to extract author, title, year, category from folder/filename conventions
- **Who:** Parker (backend)
- **Heuristics:** Support patterns like:
  - `Author/Title.pdf`
  - `Author - Title (Year).pdf`
  - `Category/Author/Title.pdf`
  - Fallback: filename = title, folder = author
- **Testing:** Lambert writes unit tests with sample paths from the actual library

#### 1.5 Verify End-to-End
- **What:** Lambert writes integration tests: drop a PDF → verify it appears in Solr with correct metadata
- **Who:** Lambert (tester)
- **Dependencies:** 1.1–1.4

**Phase 1 deliverable:** All books indexed in Solr. Searchable via `http://localhost:8983/solr/books/select?q=*:*`.

---

### Phase 2: Search API & UI (User-Facing)

**Goal:** Users can search books through a React UI with faceted filtering and result highlighting.

#### 2.1 Search API Service (FastAPI)
- **What:** New service `search-api/` with endpoints:
  - `GET /api/search?q=<query>&author=<>&year_from=<>&year_to=<>&language=<>&page=<>&size=<>`
  - `GET /api/books/{id}` — single book metadata
  - `GET /api/facets` — available facet values (authors, years, languages, categories)
  - `GET /api/books/{id}/pdf` — serve PDF file for viewing
- **Who:** Parker (backend)
- **Tech:** FastAPI, `pysolr` or `requests` to Solr
- **Key:** Solr highlighting enabled (`hl=true&hl.fl=_text_&hl.snippets=3`)
- **Docker:** New service in `docker-compose.yml`, port 8090

#### 2.2 React Search UI
- **What:** Replace chat UI with search interface:
  - Search bar with instant search
  - Faceted sidebar (author, year range, language, category)
  - Result cards showing: title, author, year, language, highlighted snippet
  - Pagination
  - Click to open PDF viewer
- **Who:** Dallas (frontend)
- **Dependencies:** 2.1 (needs API)
- **Tech:** Keep React 18 + Vite + TypeScript. Add `react-router-dom` for routing.
- **Note:** Remove old chat components (`ChatMessage.tsx`, `Configbar.tsx`, etc.)

#### 2.3 PDF Viewer Component
- **What:** In-browser PDF viewing with text highlighting of search terms
- **Who:** Dallas (frontend)
- **Tech:** `react-pdf` or `pdf.js` via iframe. Highlight matches via search term overlay.
- **Dependencies:** 2.1 (PDF serving endpoint)

#### 2.4 Integration Testing
- **Who:** Lambert
- **What:** API contract tests, UI smoke tests with Playwright

**Phase 2 deliverable:** Working search experience. Users find books, see highlighted results, view PDFs.

---

### Phase 3: Embeddings Enhancement (Semantic Search)

**Goal:** Semantic search alongside keyword search for "find similar" and concept queries.

#### 3.1 Resolve Embeddings Model
- **What:** Standardize on `distiluse-base-multilingual-cased-v2`. Fix `main.py` to match Dockerfile.
- **Who:** Parker (backend)
- **Note:** The `semitechnologies/transformers-inference` Docker image in the Dockerfile is a different inference server than the FastAPI `main.py`. Decision: use the FastAPI server (it's ours, we control it). Update Dockerfile to standard Python base.

#### 3.2 Solr Dense Vector Support
- **What:** Add a `DenseVectorField` to the Solr schema for storing embeddings. Solr 9.x supports kNN search natively.
  ```xml
  <fieldType name="knn_vector" class="solr.DenseVectorField"
    vectorDimension="512" similarityFunction="cosine"/>
  <field name="embedding" type="knn_vector" indexed="true" stored="true"/>
  ```
- **Who:** Ash (search)
- **Key decision:** Vector dimension depends on model choice (512 for distiluse v2)

#### 3.3 Embedding Indexing Pipeline
- **What:** After Tika indexes the full text, a second pass generates embeddings per page/chunk and stores them in Solr's vector field
- **Who:** Parker (backend)
- **Design:** Separate queue or post-processing step. Don't block Phase 1 indexing.

#### 3.4 Hybrid Search API
- **What:** Extend search API with `mode=keyword|semantic|hybrid` parameter
- **Who:** Parker (backend) + Ash (search)
- **Design:** Keyword search via Solr standard query. Semantic via kNN. Hybrid combines scores with configurable weighting.

#### 3.5 "Find Similar Books" Feature
- **What:** UI button on each book result → finds semantically similar books
- **Who:** Dallas (frontend)

**Phase 3 deliverable:** Users can do both keyword and "meaning-based" search. Similar books feature.

---

### Phase 4: Polish (Production Readiness)

#### 4.1 File Watcher Service
- **What:** Replace 10-min polling with `inotify`-based watcher for near-real-time detection of new books
- **Who:** Parker (backend)
- **Tech:** `watchdog` Python library
- **Alternative:** Keep polling but reduce interval to 60s. Simpler, fewer edge cases with Docker volume mounts.
- **Recommendation:** Keep polling at 60s. inotify doesn't work reliably across Docker bind mounts on all platforms.

#### 4.2 PDF Upload via UI
- **What:** Upload endpoint in search API + drag-and-drop in React UI
- **Who:** Parker (backend) + Dallas (frontend)
- **Design:** Upload → save to `/data/documents/uploads/` → document lister picks it up naturally

#### 4.3 Streamlit Admin Enhancements
- **What:** Add Solr status dashboard, reindex controls, schema management
- **Who:** Parker (backend)
- **Low priority:** Only if admin UI proves useful beyond the React UI

#### 4.4 Production Hardening
- **What:** Health checks for all services, proper logging, rate limiting, error handling
- **Who:** Lambert (tester) + Parker (backend)

---

## Service Architecture Diagram (Target State)

```
                    ┌─────────────┐
                    │   nginx     │ :80/:443
                    │  (reverse   │
                    │   proxy)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    ┌─────────▼──┐  ┌──────▼─────┐  ┌──▼──────────┐
    │ aithena-ui │  │ search-api │  │ admin       │
    │ (React)    │  │ (FastAPI)  │  │ (Streamlit) │
    │ :3000      │  │ :8090      │  │ :8501       │
    └────────────┘  └──────┬─────┘  └─────────────┘
                           │
                    ┌──────▼──────┐
                    │ SolrCloud   │
                    │ (3 nodes)   │
                    │ :8983-8985  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ ZooKeeper   │
                    │ (3 nodes)   │
                    └─────────────┘

    ┌──────────────┐     ┌───────────────┐     ┌─────────────────┐
    │ document-    │────▶│  RabbitMQ     │────▶│ document-       │
    │ lister       │     │  (queue)      │     │ indexer          │
    │ (scanner)    │     └───────────────┘     │ (Tika→Solr)     │
    └──────┬───────┘                           └────────┬────────┘
           │                                            │
    ┌──────▼───────┐                           ┌────────▼────────┐
    │ Redis        │                           │ embeddings-     │
    │ (state)      │                           │ server (Ph.3)   │
    └──────────────┘                           └─────────────────┘

    ┌─────────────────────────────────────────────────┐
    │ /home/jmservera/booklibrary (bind mount)        │
    │ → /data/documents inside containers             │
    └─────────────────────────────────────────────────┘
```

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Large PDF library overwhelms Solr Tika extraction | HIGH | Batch indexing with backpressure. RabbitMQ prefetch=1 already limits. Add retry + dead-letter queue. |
| Old books have OCR-quality text (garbled) | MEDIUM | Accept lower quality for old texts. Embeddings (Phase 3) may handle noisy text better than keyword search. |
| Solr kNN search performance at scale | MEDIUM | Phase 3 concern. Benchmark with real data first. Solr 9.x HNSW is decent for <1M vectors. |
| Docker bind-mount performance on macOS | LOW | Dev concern only. Linux production is fine. |
| Metadata heuristics fail on irregular paths | MEDIUM | Build with fallback defaults. Title = filename, author = "Unknown". Improve iteratively. |

---

## Team Assignments Summary

| Team Member | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| **Parker** (backend) | Indexer rewrite, metadata extraction, volume fix | Search API | Embedding pipeline, hybrid search | Upload endpoint, file watcher |
| **Dallas** (frontend) | — | Search UI, PDF viewer | Similar books UI | Upload UI |
| **Ash** (search) | Schema fields, Solr config | Search tuning | Vector field, kNN config | — |
| **Lambert** (tester) | Integration tests | API + UI tests | Embedding quality tests | E2E tests |
| **Ripley** (lead) | Architecture review, decision approval | API contract review | Model selection review | Production readiness review |

---

## Immediate Next Steps

1. **Ash:** Add book-specific fields to Solr schema (ADR-002 fields)
2. **Parker:** Fix `docker-compose.yml` volume mapping for book library
3. **Parker:** Rewrite `document-indexer` to use Solr Tika extraction (drop Qdrant dependency)
4. **Parker:** Build metadata extraction module with path-parsing heuristics
5. **Lambert:** Write tests for metadata extraction using sample paths from `/home/jmservera/booklibrary`
6. **Ripley:** Review and approve schema changes before they're applied to the running cluster

---

*This plan builds on what's already working. We don't throw away the SolrCloud cluster, the document-lister, or the queue infrastructure. We replace the Qdrant-bound indexer with a Solr-native one and build up from there.*
