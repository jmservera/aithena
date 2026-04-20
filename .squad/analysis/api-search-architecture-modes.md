# API & Backend Analysis: Dual Search Architecture Modes

**Author:** Parker (Backend Dev)
**Date:** 2026-07-15
**Status:** Analysis Complete

---

## 1. Current Search API — `src/solr-search/main.py`

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search` (`/v1/search`) | GET | Main search — keyword, semantic, hybrid |
| `/books/{id}/similar` (`/v1/books/{id}/similar`) | GET | kNN similarity search for a specific document |
| `/facets` (`/v1/facets`) | GET | Standalone facet counts |
| `/v1/search/compare` | GET | Side-by-side comparison across two collections |
| `/books` (`/v1/books`) | GET | Browse/list books |
| `/stats` (`/v1/stats`) | GET | Collection statistics |

### Search Parameters

The `/search` endpoint accepts:
- `q` (str): Search query (empty = all for keyword mode)
- `page` (int, ≥1): Pagination
- `limit` / `page_size` (int): Results per page (max from `MAX_PAGE_SIZE`)
- `sort` / `sort_by` / `sort_order`: Sorting (score, title, author, year, category, language)
- `fq_author`, `fq_category`, `fq_language`, `fq_year`, `fq_series`, `fq_folder`: Filter queries
- `mode` (str): `keyword` | `semantic` | `hybrid` (default from `DEFAULT_SEARCH_MODE` env var)
- `collection` (str): Target Solr collection (default: `books`)

### How `search_type` (mode) Is Handled

```
search() → dispatches based on mode:
  ├─ "keyword"  → _search_keyword()  → BM25 via edismax
  ├─ "semantic" → _search_semantic() → kNN via {!knn} query parser
  └─ "hybrid"   → _search_hybrid()  → parallel BM25 + kNN → RRF fusion
```

**Keyword:** Builds Solr edismax params via `build_solr_params()`, queries Solr, enriches with chunk page ranges.

**Semantic:** Calls `_fetch_embedding()` → embeddings server, then `build_knn_params()` → `{!knn f=embedding_v topK=N}[vector]`. No facets or highlighting. Degrades to keyword if embeddings unavailable (502/503/504).

**Hybrid:** Runs BM25 + embedding fetch concurrently via `ThreadPoolExecutor(max_workers=2)`. Then fires kNN query. Merges with `reciprocal_rank_fusion(kw_results, sem_results, k=settings.rrf_k)`. Facets come from BM25 leg. Degrades to keyword on embedding failure.

### Solr Client

- **Library:** `requests` (no dedicated Solr client)
- **Transport:** `requests.post(url, data=params)` to `{solr_url}/{collection}/select`
- **Circuit breaker:** `solr_circuit` wraps all queries; `embeddings_circuit` wraps embedding calls
- **Auth:** Optional HTTP Basic Auth via `SOLR_AUTH_USER`/`SOLR_AUTH_PASS`

### Result Format

```json
{
  "query": "...",
  "mode": "keyword|semantic|hybrid",
  "sort": {"by": "score", "order": "desc"},
  "degraded": false,
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "results": [{ "id": "...", "title": "...", "score": 0.95, ... }],
  "facets": { "author": [...], "category": [...], "year": [...], "language": [...] },
  "message": "..." // optional, present on degradation
}
```

---

## 2. Reranking Implementation Design

### Where to Insert Reranking

The reranking step replaces the Solr-side kNN query in `hybrid` and `semantic` modes when `SEARCH_ARCHITECTURE=hybrid-rerank`.

**For hybrid mode** (`_search_hybrid()`):
1. Current flow: BM25 query → kNN query → `reciprocal_rank_fusion()`
2. New flow: BM25 query (with `fl=...,embedding_v`) → app-side cosine rerank → `reciprocal_rank_fusion()`

**For semantic mode** (`_search_semantic()`):
1. Current flow: embedding → `{!knn}` query
2. New flow: BM25 `*:*` query (or boosted q) → retrieve stored vectors → cosine rerank

**Implementation location:** New function in `search_service.py`:

```python
def rerank_by_cosine_similarity(
    docs: list[dict[str, Any]],
    query_vector: list[float],
    embedding_field: str = "embedding_v",
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Rerank documents by cosine similarity to query vector."""
    import numpy as np

    q_vec = np.array(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return docs

    scored = []
    for doc in docs:
        vec = doc.get(embedding_field)
        if vec is None:
            continue
        d_vec = np.array(vec, dtype=np.float32)
        d_norm = np.linalg.norm(d_vec)
        if d_norm == 0:
            continue
        sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
        scored.append((doc, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    if top_k:
        scored = scored[:top_k]
    return [dict(doc, score=sim) for doc, sim in scored]
```

### Retrieving Stored Vectors from Solr

Add the embedding field to the Solr field list in the BM25 query:
- Modify `SOLR_FIELD_LIST` conditionally (or pass an extended `fl` param)
- In `build_solr_params()`, append `embedding_v` (or `embedding_byte_v`) to the `fl` parameter
- The field must be **stored** in the Solr schema (Ash's domain — we need `stored="true"` on the vector field)

**Key detail:** In HNSW mode, vector fields are typically `indexed="true" stored="false"` for performance. In hybrid-rerank mode, they MUST be `stored="true" indexed="false"` — stored-only, no HNSW index overhead.

### RRF Score Fusion

The existing `reciprocal_rank_fusion()` in `search_service.py` (line 419) already implements:
```
score(d) = 1/(k + rank_bm25) + 1/(k + rank_vector)
```
with k=60 (configurable via `RRF_K` env var). **No changes needed** — just feed it cosine-reranked results instead of kNN results.

### Performance: Reranking 200 Candidates × 768D Vectors

```python
# Benchmark estimate:
# - 200 vectors × 768 floats = 614,400 floats (≈2.4 MB)
# - Cosine similarity = dot product + 2 norms per vector
# - NumPy vectorized: ~0.2ms for 200 cosine similarities
# - With Python loop overhead: ~1-3ms
# - Sorting 200 items: negligible
```

**Total estimated latency: 1-5ms** for 200 candidates with 768D vectors. This is negligible compared to the Solr BM25 query latency (~20-50ms) and embedding generation (~50-200ms). **No performance concern.**

For larger candidate sets (1000+), use numpy broadcasting for batch cosine:
```python
# Batch cosine: Q @ D^T / (||Q|| * ||D||)
# 1000 × 768: ~2ms with numpy
```

---

## 3. Capabilities Endpoint

### Proposed: `GET /v1/capabilities`

```python
@app.get("/v1/capabilities")
def capabilities() -> dict[str, Any]:
    """Returns server capabilities for UI feature negotiation."""
    return {
        "search_architecture": settings.search_architecture,  # "hnsw" | "hybrid-rerank"
        "available_modes": list(VALID_SEARCH_MODES),           # always ["keyword", "semantic", "hybrid"]
        "vector_search": {
            "type": settings.search_architecture,
            "knn_available": settings.search_architecture == "hnsw",
            "rerank_available": settings.search_architecture == "hybrid-rerank",
        },
        "quantization": {
            "mode": settings.vector_quantization,              # "none" | "fp16" | "int8"
        },
        "embedding": {
            "dimensions": settings.embedding_dimensions,       # fetched from embeddings server at startup
            "field": settings.knn_field,
        },
        "collections": {
            "default": settings.default_collection,
            "allowed": sorted(settings.allowed_collections),
        },
    }
```

**Why this matters:**
- The UI currently assumes HNSW kNN is always available
- With hybrid-rerank mode, semantic/hybrid search still works but uses a different backend path
- The UI should call `/v1/capabilities` at startup to discover what's available
- Future modes (e.g., pure BM25 without any vectors) can be added without UI code changes

**Auth:** This endpoint should be **public** (no auth required) — add to `PUBLIC_PATHS` set. It contains no sensitive data and is needed before login.

---

## 4. Configuration

### New Environment Variables

| Variable | Values | Default | Where |
|----------|--------|---------|-------|
| `SEARCH_ARCHITECTURE` | `hnsw`, `hybrid-rerank` | `hnsw` | solr-search `config.py` |
| `VECTOR_QUANTIZATION` | `none`, `fp16`, `int8` | `none` | embeddings-server `config/__init__.py` (already exists) |

### New Settings Fields (solr-search `config.py`)

```python
# Add to Settings dataclass:
search_architecture: str  # "hnsw" | "hybrid-rerank"
vector_quantization: str  # "none" | "fp16" | "int8" (informational, from embeddings server)
embedding_dimensions: int  # populated at startup from embeddings server /v1/embeddings/model
rerank_candidates: int  # number of BM25 candidates for reranking (default 200)
```

```python
# Add to settings instantiation:
search_architecture=os.environ.get("SEARCH_ARCHITECTURE", "hnsw"),
vector_quantization=os.environ.get("VECTOR_QUANTIZATION", "none").lower(),
embedding_dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "768")),
rerank_candidates=int(os.environ.get("RERANK_CANDIDATES", "200")),
```

### Interaction with `VECTOR_QUANTIZATION`

| Architecture | Quantization | Solr Field | Indexed? | Stored? |
|-------------|-------------|------------|----------|---------|
| `hnsw` | `none` | `embedding_v` | ✅ (HNSW) | ❌ |
| `hnsw` | `fp16` | `embedding_v` | ✅ (HNSW) | ❌ |
| `hnsw` | `int8` | `embedding_byte_v` | ✅ (HNSW, ByteEncoding) | ❌ |
| `hybrid-rerank` | `none` | `embedding_v` | ❌ | ✅ |
| `hybrid-rerank` | `fp16` | `embedding_v` | ❌ | ✅ |
| `hybrid-rerank` | `int8` | `embedding_byte_v` | ❌ | ✅ |

**Key insight:** The quantization mode determines which field name the embeddings server returns (`embedding` → `embedding_v`, `embedding_byte` → `embedding_byte_v`). This is already handled by `quantize_embedding()` in embeddings-server. The document-indexer uses `emb_result.field_name` to write to the correct Solr field. **No change needed in the embeddings or indexer flow for field routing.**

The **Solr schema** is what changes between modes (Ash's domain):
- HNSW mode: `DenseVectorField` with `indexed="true" stored="false"`
- Hybrid-rerank mode: regular stored field with `indexed="false" stored="true"`

### Indexing Behavior Per Mode

| Mode | What Happens at Index Time |
|------|---------------------------|
| `hnsw` | Vectors written to `embedding_v` (or `embedding_byte_v`). Solr builds HNSW index. |
| `hybrid-rerank` | Same vectors written to same field names. Solr stores them without HNSW indexing. |

**The document-indexer code does NOT need to change based on architecture mode.** The indexer always writes vectors to the field the embeddings server specifies. The difference is entirely in the Solr schema definition (stored vs. indexed). This is a clean separation of concerns.

---

## 5. Document Indexer Changes — `src/document-indexer/`

### Current Vector Writing Flow

```
__main__.py:index_chunks()
  → extract_pdf_text(path)
  → chunk_text_with_pages(pages, chunk_size, overlap)
  → for each batch:
      → get_embeddings(chunks, host, port)          # calls embeddings-server
      → build_chunk_doc(..., embedding=vector,
                        embedding_field=emb_result.field_name)
      → requests.post(solr_url, json=docs)           # writes to Solr
```

**`build_chunk_doc()`** (line 248-283): Constructs the Solr JSON document. The vector is written to `{embedding_field}_v` — e.g., `embedding_v` for float32/fp16, `embedding_byte_v` for int8. This field name comes from the embeddings server's `field_name` response field, which is set by `quantize_embedding()`.

### Changes Needed for Hybrid-Rerank Mode

**Answer: NONE on the document-indexer side.**

The indexer is architecture-agnostic by design:
1. It calls the embeddings server → gets vectors with `field_name`
2. It writes to `{field_name}_v` in Solr
3. Whether Solr indexes (HNSW) or just stores the field is determined by the **Solr schema**, not the indexer

The only deployment-time change is the Solr schema configuration, which is Ash's responsibility.

### Optional Enhancement: Informational Logging

Could add a startup log line in the indexer showing which architecture mode is active:

```python
SEARCH_ARCHITECTURE = os.environ.get("SEARCH_ARCHITECTURE", "hnsw")
logger.info("Search architecture: %s (vectors will be %s)",
            SEARCH_ARCHITECTURE,
            "HNSW-indexed" if SEARCH_ARCHITECTURE == "hnsw" else "stored-only for reranking")
```

This is purely informational — no behavioral change.

---

## 6. Implementation Plan (solr-search changes only)

### Files to Modify

| File | Change |
|------|--------|
| `config.py` | Add `search_architecture`, `vector_quantization`, `embedding_dimensions`, `rerank_candidates` fields |
| `search_service.py` | Add `rerank_by_cosine_similarity()` function |
| `main.py` | Add `/v1/capabilities` endpoint; modify `_search_hybrid()` and `_search_semantic()` to branch on architecture |
| `main.py` | Add `SEARCH_ARCHITECTURE` to `PUBLIC_PATHS` for capabilities |

### Branching Logic in Search

```python
def _search_hybrid(request, q, page, page_size, ...):
    if settings.search_architecture == "hybrid-rerank":
        return _search_hybrid_rerank(request, q, page, page_size, ...)
    else:
        return _search_hybrid_hnsw(request, q, page, page_size, ...)  # existing code
```

The `_search_hybrid_rerank()` function:
1. Fetch query embedding (same as now)
2. Run BM25 with extended `fl` (include `embedding_v`)
3. Call `rerank_by_cosine_similarity(bm25_docs, query_vector)`
4. Feed BM25 + reranked results into existing `reciprocal_rank_fusion()`
5. Return in same response format

### Testing Strategy

- Unit tests for `rerank_by_cosine_similarity()` with known vectors
- Mock-based integration tests for `_search_hybrid_rerank()` path
- Parametrize existing search tests with `search_architecture` setting
- Performance benchmark test for reranking (assert <50ms for 200×768D)

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Stored vectors increase Solr memory | Medium | int8 quantization reduces 4× vs fp32; only stored, no HNSW overhead |
| Reranking quality vs true kNN | Low | RRF fusion compensates; BM25 pre-filter is strong for text search |
| BM25 candidate set misses relevant docs | Medium | Use higher `RERANK_CANDIDATES` (200-500); log coverage metrics |
| Config mismatch (architecture vs schema) | High | `/v1/capabilities` should probe Solr schema at startup to validate |
| numpy dependency in solr-search | Low | numpy is lightweight; already used transitively via other deps |

---

## 8. Dependencies on Other Team Members

| Who | What | Blocking? |
|-----|------|-----------|
| **Ash** (Schema) | Solr schema with stored-only vector fields for hybrid-rerank mode | ✅ Yes — without stored fields, reranking has no vectors to read |
| **Devon** (UI) | Call `/v1/capabilities` at startup; adapt search mode selector | ❌ No — UI works with current modes; capabilities is additive |
| **Brett** (Infra) | Docker compose config for `SEARCH_ARCHITECTURE` env var | ❌ No — defaults to `hnsw` (current behavior) |
