# Architecture Analysis: HNSW vs Hybrid-Rerank Deployment Modes

**Author:** Ripley (Lead)
**Date:** 2025-07-25
**Status:** Proposal
**Requested by:** jmservera (Juanma)

---

## 1. Executive Summary

The system currently requires an HNSW index for all vector search capabilities (semantic and hybrid modes). This index consumes 9–28 GB RAM for 9M page vectors depending on quantization. We propose a second deployment mode — **hybrid-rerank** — that eliminates the HNSW graph entirely, using BM25 as the primary retrieval stage with application-side vector reranking of top-N results.

---

## 2. Current Architecture — Search Flow Trace

### 2.1 System Diagram (Current — HNSW Mode)

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────────────┐
│  aithena-ui  │────▶│  solr-search    │────▶│  SolrCloud (3-node)     │
│  (React 18)  │     │  (FastAPI)      │     │                         │
│              │     │                 │     │  Collection: books       │
│  MODE_OPTIONS│     │  /v1/search     │     │  ┌─────────────────────┐│
│  - keyword   │     │  ?mode=X        │     │  │ Parent docs (books) ││
│  - semantic  │     │                 │     │  │ - BM25 text index   ││
│  - hybrid    │     │  ┌────────────┐ │     │  └─────────────────────┘│
└──────────────┘     │  │ keyword:   │ │     │  ┌─────────────────────┐│
                     │  │ edismax    │─┼────▶│  │ Chunk docs          ││
                     │  │ BM25       │ │     │  │ - chunk_text_t      ││
                     │  ├────────────┤ │     │  │ - embedding_v       ││
                     │  │ semantic:  │ │     │  │   (knn_vector_768)  ││
                     │  │ {!knn}     │─┼────▶│  │   HNSW cosine index ││
                     │  ├────────────┤ │     │  │ - embedding_byte    ││
                     │  │ hybrid:    │ │     │  │   (knn_vector_768   ││
                     │  │ BM25 + kNN │ │     │  │    _byte) HNSW      ││
                     │  │ → RRF      │ │     │  └─────────────────────┘│
                     │  └────────────┘ │     └─────────────────────────┘
                     │                 │
                     │  ┌────────────┐ │     ┌─────────────────────────┐
                     │  │ embedding  │ │     │  embeddings-server      │
                     │  │ fetch      │─┼────▶│  (FastAPI)              │
                     │  └────────────┘ │     │  multilingual-e5-base   │
                     └─────────────────┘     │  768-dim, cosine sim    │
                                             └─────────────────────────┘

┌──────────────────┐     ┌─────────────────────────┐
│ document-indexer  │────▶│  embeddings-server       │
│ (RabbitMQ)       │     │  /v1/embeddings/          │
│                  │     └─────────────────────────┘
│ PDF → Tika → chunks    │
│ chunks → embeddings    ├──▶ Solr: parent doc (metadata)
│ chunks + vectors → Solr│    Solr: chunk docs (text + embedding_v)
└──────────────────┘
```

### 2.2 Search Mode Implementation Details

**File:** `src/solr-search/main.py` (lines 944–980) + `src/solr-search/search_service.py`

| Mode | Entry Point | Solr Query | Embedding Required | Result Source |
|------|-------------|------------|-------------------|---------------|
| **keyword** | `_search_keyword()` L1002 | `defType=edismax`, BM25 on `_text_` | No | Parent docs (books) via `EXCLUDE_CHUNKS_FQ` |
| **semantic** | `_search_semantic()` L1076 | `{!knn f=embedding_v topK=N}[vector]` | Yes | Chunk docs → deduplicated |
| **hybrid** | `_search_hybrid()` L1144 | BM25 ∥ kNN in ThreadPoolExecutor → `reciprocal_rank_fusion()` | Yes | Fused via RRF (k=60) |

**Key implementation details:**
- **kNN query construction:** `build_knn_params()` in `search_service.py:287-312` — uses `{!knn}` local-parameter syntax
- **RRF fusion:** `reciprocal_rank_fusion()` in `search_service.py:419-463` — application-side fusion of two ranked lists, score = Σ 1/(k + rank)
- **Graceful degradation:** When embeddings are unavailable (502/503/504), semantic and hybrid degrade to keyword with `degraded: true` + message (L506-507, L1101-1115, L1189-1203)
- **Chunk exclusion:** Keyword mode filters with `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` — kNN intentionally does NOT exclude chunks (embeddings live on chunks)
- **Parallel execution:** Hybrid mode runs BM25 query and embedding fetch concurrently via `ThreadPoolExecutor(max_workers=2)` (L1181)

### 2.3 Solr Schema — Vector Fields

**File:** `src/solr/books/managed-schema.xml`

```xml
<!-- Field Types -->
<fieldType name="knn_vector_768" class="solr.DenseVectorField"
           vectorDimension="768" similarityFunction="cosine" knnAlgorithm="hnsw"/>
<fieldType name="knn_vector_768_byte" class="solr.DenseVectorField"
           vectorDimension="768" vectorEncoding="BYTE" similarityFunction="cosine"
           knnAlgorithm="hnsw" hnswMaxConnections="12"/>

<!-- Fields -->
<field name="embedding_v" type="knn_vector_768" indexed="true" stored="true"/>
<field name="embedding_byte" type="knn_vector_768_byte" indexed="true" stored="true"/>
<field name="book_embedding" type="knn_vector_768" indexed="true" stored="true"/>
```

Both `embedding_v` and `embedding_byte` have `indexed="true"`, which means HNSW graph is built. This is the RAM cost center.

### 2.4 Configuration Touchpoints

**File:** `src/solr-search/config.py`

Relevant settings:
- `knn_field` = `EMBEDDING_V` env var (default: `embedding_v`) — Solr field for kNN queries
- `book_embedding_field` = `BOOK_EMBEDDING_FIELD` env var (default: `embedding_v`) — used by similar-books
- `default_search_mode` = `DEFAULT_SEARCH_MODE` env var (default: `keyword`)
- `embeddings_url` = `EMBEDDINGS_URL` env var
- `rrf_k` = `RRF_K` env var (default: 60)

---

## 3. Proposed Architecture — Dual Deployment Modes

### 3.1 System Diagram (Hybrid-Rerank Mode)

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────────────┐
│  aithena-ui  │────▶│  solr-search    │────▶│  SolrCloud (3-node)     │
│  (React 18)  │     │  (FastAPI)      │     │                         │
│              │     │                 │     │  Collection: books       │
│  MODE_OPTIONS│     │  /v1/search     │     │  ┌─────────────────────┐│
│  - keyword   │     │  ?mode=X        │     │  │ Parent docs (books) ││
│  - hybrid    │     │                 │     │  │ - BM25 text index   ││
│  (semantic   │     │  ┌────────────┐ │     │  └─────────────────────┘│
│   disabled)  │     │  │ keyword:   │ │     │  ┌─────────────────────┐│
└──────────────┘     │  │ edismax    │─┼────▶│  │ Chunk docs          ││
                     │  │ BM25       │ │     │  │ - chunk_text_t      ││
                     │  ├────────────┤ │     │  │ - embedding_v       ││
                     │  │ hybrid:    │ │     │  │   stored="true"     ││
                     │  │ BM25 →     │ │     │  │   indexed="false"   ││
                     │  │ fetch top-N│ │     │  │   ← NO HNSW graph!  ││
                     │  │ vectors →  │ │     │  └─────────────────────┘│
                     │  │ app-side   │ │     └─────────────────────────┘
                     │  │ cosine sim │ │
                     │  │ → rerank   │ │     ┌─────────────────────────┐
                     │  └────────────┘ │     │  embeddings-server      │
                     │  │ embedding  │ │     │  (still needed for      │
                     │  │ fetch      │─┼────▶│   query embedding)      │
                     │  └────────────┘ │     └─────────────────────────┘
                     └─────────────────┘
```

### 3.2 How Hybrid-Rerank Works

1. **BM25 retrieval:** Same edismax query as keyword mode, but fetch **more candidates** (e.g., top 100–200 chunks via `parent_id_s:[* TO *]` instead of excluding them)
2. **Fetch stored vectors:** Request `embedding_v` in the `fl` (field list) for the top-N BM25 chunk results
3. **Query embedding:** Get the query vector from embeddings-server (same as today)
4. **Application-side cosine similarity:** Compute `cos(query_vec, doc_vec)` for each candidate
5. **Rerank or RRF:** Either pure rerank by cosine score, or RRF fusion of BM25 rank + cosine rank
6. **Return top-K:** Deduplicate by parent_id_s and return

**Key insight:** Vectors are still stored in Solr (for retrieval), but `indexed="false"` means no HNSW graph is built. RAM savings: **9–28 GB freed**.

---

## 4. Configuration Design

### 4.1 Environment Variable

```
SEARCH_ARCHITECTURE=hnsw|hybrid-rerank
```

Default: `hnsw` (backward compatible)

**Why not auto-detect from schema?**
- Auto-detection would require querying Solr's Schema API at startup to check if `embedding_v` is indexed
- This creates a startup dependency and a fragile coupling to Solr schema internals
- Explicit configuration is clearer, easier to debug, and follows the existing pattern (e.g., `VECTOR_QUANTIZATION`, `DEFAULT_SEARCH_MODE`)
- Auto-detection could be added later as a convenience enhancement

### 4.2 Startup Behavior

On startup, `solr-search` should:
1. Read `SEARCH_ARCHITECTURE` from environment
2. Set `VALID_SEARCH_MODES` based on architecture:
   - `hnsw`: `{"keyword", "semantic", "hybrid"}` (unchanged)
   - `hybrid-rerank`: `{"keyword", "hybrid"}` (no standalone semantic)
3. Log the active architecture mode at INFO level
4. Adjust `DEFAULT_SEARCH_MODE` if it's incompatible (e.g., `semantic` in `hybrid-rerank` → fall back to `keyword` with WARNING)

### 4.3 Configuration Matrix

| Feature | HNSW Mode | Hybrid-Rerank Mode |
|---------|-----------|-------------------|
| **keyword search** | ✅ BM25 edismax | ✅ BM25 edismax (identical) |
| **semantic search** | ✅ Solr `{!knn}` on HNSW | ❌ Not available |
| **hybrid search** | ✅ BM25 ∥ kNN → RRF | ✅ BM25 → fetch vectors → app-side cosine → RRF |
| **similar books** | ✅ kNN on stored vectors | ❌ Not available (no HNSW to search against) |
| **embedding_v field** | `indexed="true" stored="true"` | `indexed="false" stored="true"` |
| **HNSW RAM cost** | 9–28 GB (768-dim × 9M chunks) | **0 GB** |
| **Embeddings server** | Required for semantic/hybrid | Required for hybrid (query embedding) |
| **Facets in hybrid** | From BM25 leg | From BM25 leg (identical) |
| **Highlights in hybrid** | From BM25 leg | From BM25 leg (identical) |
| **Reranking latency** | N/A (HNSW handles it) | App-side: ~5-20ms for 200 vectors |

---

## 5. Impact Analysis by Layer

### 5.1 Solr Schema (`src/solr/books/managed-schema.xml`)

**Change:** Add a stored-only variant of the vector field type.

```xml
<!-- NEW: stored-only vector type — no HNSW index, no RAM cost -->
<fieldType name="knn_vector_768_stored"
           class="solr.DenseVectorField"
           vectorDimension="768"
           similarityFunction="cosine"
           indexed="false"
           stored="true"/>
```

**Option A — Dual field types, single schema:**
- Define both `knn_vector_768` (HNSW) and `knn_vector_768_stored` (stored-only) field types
- Use different field names: `embedding_v` (HNSW) vs `embedding_stored_v` (stored-only)
- Indexer writes to the correct field based on `SEARCH_ARCHITECTURE`

**Option B — Configurable schema via envsubst (RECOMMENDED):**
- Use a single `embedding_v` field whose type switches between `knn_vector_768` and `knn_vector_768_stored` based on a build-time or init-time variable
- Simpler: one field name, no indexer changes for field routing
- Solr init script applies the appropriate schema variant

**Recommendation:** Option B. Fewer moving parts, no indexer field-routing logic.

### 5.2 Search API (`src/solr-search/`)

#### 5.2.1 `config.py`

Add new setting:
```python
search_architecture: str  # "hnsw" or "hybrid-rerank"
```

Read from `SEARCH_ARCHITECTURE` env var, default `"hnsw"`.

#### 5.2.2 `search_service.py`

Add new function for hybrid-rerank:

```python
def build_bm25_with_vectors_params(
    query: str,
    page: int,
    candidate_limit: int,
    sort_by: str,
    sort_order: str,
    facet_limit: int,
    vector_field: str,
    *,
    sort: str | None = None,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build BM25 params that ALSO return stored vectors for top-N chunks."""
    # Query chunks (not parents) so we get vectors
    params = build_solr_params(query, 1, candidate_limit, sort_by, sort_order, facet_limit,
                               sort=sort, filters=filters)
    # Override fq to include chunks instead of excluding them
    filter_queries = build_filter_queries(filters)
    filter_queries.append("parent_id_s:[* TO *]")  # chunks only
    params["fq"] = filter_queries
    # Add vector field to fl
    params["fl"] = ",".join(SOLR_FIELD_LIST + [vector_field])
    params["rows"] = candidate_limit
    return params


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rerank_by_similarity(
    candidates: list[dict[str, Any]],
    query_vector: list[float],
    vector_field: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Rerank BM25 candidates by cosine similarity to query vector."""
    scored = []
    for doc in candidates:
        vec = doc.get(vector_field)
        if vec:
            sim = cosine_similarity(query_vector, vec)
            scored.append((sim, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]
```

**Performance note:** For 200 candidates × 768 dimensions, cosine similarity is ~0.3ms in pure Python. If perf matters, use numpy: `np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))` — ~0.05ms for 200 vectors.

#### 5.2.3 `main.py`

**New `_search_hybrid_rerank()` function:**

```python
def _search_hybrid_rerank(
    request, q, page, page_size, sort_by, sort_order, sort, filters,
    *, collection=None,
) -> dict[str, Any]:
    """BM25 retrieval + application-side vector reranking."""
    candidate_limit = max(page_size * 5, 100)  # over-fetch for reranking pool

    # 1. BM25 on chunks (with vectors in fl)
    chunk_params = build_bm25_with_vectors_params(...)

    # 2. Concurrent: BM25 query + query embedding
    with ThreadPoolExecutor(max_workers=2) as pool:
        bm25_future = pool.submit(query_solr, chunk_params, collection=collection)
        emb_future = pool.submit(_fetch_embedding, q, collection=collection)

        bm25_payload = bm25_future.result()
        query_vector = emb_future.result()  # graceful degradation if fails

    # 3. Extract BM25 chunk results with their stored vectors
    chunk_docs = bm25_payload["response"]["docs"]

    # 4. Compute cosine similarity for each chunk
    for doc in chunk_docs:
        vec = doc.get(settings.knn_field)
        doc["_rerank_score"] = cosine_similarity(query_vector, vec) if vec else 0.0

    # 5. RRF fusion of BM25 rank and cosine rank
    bm25_ranked = chunk_docs  # already in BM25 order
    cosine_ranked = sorted(chunk_docs, key=lambda d: d["_rerank_score"], reverse=True)
    fused = reciprocal_rank_fusion(bm25_ranked, cosine_ranked, k=settings.rrf_k)

    # 6. Deduplicate by parent_id_s, take top page_size
    ...
```

**Mode routing change in `search()` endpoint:**

```python
if mode == "hybrid":
    if settings.search_architecture == "hybrid-rerank":
        response = _search_hybrid_rerank(...)
    else:
        response = _search_hybrid(...)
```

**Semantic mode guard:**

```python
if mode == "semantic" and settings.search_architecture == "hybrid-rerank":
    raise HTTPException(
        status_code=400,
        detail="Semantic search requires HNSW mode. Current architecture: hybrid-rerank."
    )
```

### 5.3 Embeddings Server (`src/embeddings-server/`)

**No changes required.** The embeddings server generates vectors on demand for both modes:
- HNSW mode: generates query vectors for kNN search
- Hybrid-rerank mode: generates query vectors for application-side reranking

### 5.4 Document Indexer (`src/document-indexer/`)

**Minimal changes:**

The indexer writes to `embedding_v` (or `embedding_byte` for int8 quantization) regardless of mode. The Solr schema determines whether the vector is indexed (HNSW) or just stored.

- If using **Option B** (configurable schema), no indexer changes needed
- If using **Option A** (dual fields), the indexer needs to know which field to write to via `EMBEDDING_FIELD` env var

**Recommendation:** No indexer changes (Option B schema approach).

### 5.5 Docker Compose

```yaml
solr-search:
  environment:
    - SEARCH_ARCHITECTURE=${SEARCH_ARCHITECTURE:-hnsw}

# For hybrid-rerank deployments, add a compose override:
# docker/compose.hybrid-rerank.yml
```

New override file `docker/compose.hybrid-rerank.yml`:
```yaml
services:
  solr-search:
    environment:
      - SEARCH_ARCHITECTURE=hybrid-rerank
      - DEFAULT_SEARCH_MODE=keyword
```

### 5.6 UI (`src/aithena-ui/`)

#### 5.6.1 Capabilities Discovery

The UI needs to know which search modes are available. Two approaches:

**Option A — API capabilities endpoint (RECOMMENDED):**

```
GET /v1/capabilities
{
  "search_architecture": "hybrid-rerank",
  "available_modes": ["keyword", "hybrid"],
  "default_mode": "keyword",
  "features": {
    "similar_books": false,
    "facets": true,
    "semantic_search": false
  }
}
```

**Option B — Embedded in search response:**
Already partially done — the `mode` field in search responses tells the UI what mode was used. But the UI needs to know *before* searching to populate the mode selector.

**Recommendation:** Option A. Add `/v1/capabilities` endpoint. The UI fetches it once on load and conditionally renders mode options.

#### 5.6.2 UI Changes

In `src/aithena-ui/src/pages/SearchPage.tsx`:
- `MODE_OPTIONS` should be filtered based on capabilities response
- When `semantic` is unavailable, hide it from the mode selector
- The "Similar Books" panel should be hidden/disabled when `similar_books: false`

In `src/aithena-ui/src/hooks/search.ts`:
- `SearchMode` type remains the same (superset)
- Validation falls back to `keyword` if selected mode is unavailable

---

## 6. API Contract Proposal

### 6.1 New Endpoint: `/v1/capabilities`

```
GET /v1/capabilities

Response 200:
{
  "search_architecture": "hnsw" | "hybrid-rerank",
  "available_modes": ["keyword", "semantic", "hybrid"] | ["keyword", "hybrid"],
  "default_mode": "keyword" | "semantic" | "hybrid",
  "features": {
    "semantic_search": true | false,
    "similar_books": true | false,
    "vector_reranking": true | false,
    "facets": true,
    "highlights": true
  },
  "vector_config": {
    "dimensions": 768,
    "model": "multilingual-e5-base",
    "quantization": "none" | "fp16" | "int8"
  }
}
```

**Authentication:** Public (no auth required) — same as `/health`.

### 6.2 Search Endpoint Behavior Changes

| `search_type` | HNSW Mode | Hybrid-Rerank Mode |
|---------------|-----------|-------------------|
| `keyword` | BM25 (unchanged) | BM25 (unchanged) |
| `semantic` | Solr kNN (unchanged) | **400 error**: "Semantic search requires HNSW architecture" |
| `hybrid` | BM25 + kNN → RRF (unchanged) | BM25 → vector rerank → RRF |

### 6.3 Degradation Behavior in Hybrid-Rerank Mode

If embeddings server is down in hybrid-rerank mode:
- **hybrid** degrades to **keyword** with `degraded: true` (same as today)
- This is consistent with existing degradation behavior (L506-507)

### 6.4 Similar Books Endpoint

| Endpoint | HNSW Mode | Hybrid-Rerank Mode |
|----------|-----------|-------------------|
| `/v1/books/{id}/similar` | kNN search (unchanged) | **501 error**: "Similar books requires HNSW architecture" |

---

## 7. Edge Cases and Risks

### 7.1 Migration: Switching Modes Mid-Deployment

**HNSW → Hybrid-Rerank:**
1. Update Solr schema to change `embedding_v` from `indexed="true"` to `indexed="false"`
2. **Requires full re-index** — Solr cannot drop an HNSW index without reindexing
3. Set `SEARCH_ARCHITECTURE=hybrid-rerank`, restart `solr-search`
4. Freed RAM is reclaimed after reindex completes

**Hybrid-Rerank → HNSW:**
1. Update Solr schema to change `embedding_v` to `indexed="true"`
2. **Requires full re-index** — vectors are stored but HNSW graph needs to be built
3. RAM consumption will spike during indexing
4. Set `SEARCH_ARCHITECTURE=hnsw`, restart `solr-search`

**Risk mitigation:** Document that mode switching requires scheduled maintenance with reindex.

### 7.2 Reindexing Requirements

| Scenario | Reindex Required? | Reason |
|----------|-------------------|--------|
| Initial deployment as hybrid-rerank | No (fresh index) | Schema configured from start |
| HNSW → hybrid-rerank | **Yes** | Must rebuild without HNSW graph |
| hybrid-rerank → HNSW | **Yes** | Must build HNSW graph from stored vectors |
| Change quantization (within same mode) | **Yes** | Different field types |

### 7.3 Quality: Recall Ceiling of BM25+Rerank vs Full kNN

| Metric | Full kNN (HNSW) | BM25 + Rerank |
|--------|----------------|---------------|
| **Recall@10** | ~95%+ (HNSW approximate, configurable) | Bounded by BM25 recall in top-N |
| **Semantic coverage** | Finds conceptually similar but lexically different docs | Only reranks docs already found by BM25 |
| **Zero-overlap queries** | Handles them (vector-only) | **Misses entirely** — if no keyword match, no candidates to rerank |
| **Multilingual cross-lingual** | Strong (embedding model handles) | Weak — BM25 is language-dependent |

**The fundamental trade-off:** Reranking can only reorder what BM25 finds. If a relevant document shares no keywords with the query, it won't appear in the candidate pool. This is acceptable for cost-constrained deployments but should be clearly documented.

**Mitigation:** Use a generous candidate pool (100–200) and edismax's flexible matching to maximize BM25 recall.

### 7.4 Performance: Latency Trade-offs

| Component | HNSW Mode | Hybrid-Rerank Mode |
|-----------|-----------|-------------------|
| BM25 query | ~10-50ms | ~10-50ms |
| kNN query (HNSW) | ~5-20ms | N/A |
| Embedding fetch | ~20-100ms | ~20-100ms |
| Vector fetch from stored fields | N/A | ~5-15ms (200 × 768 floats) |
| App-side cosine similarity | N/A | ~0.3ms (pure Python, 200 vectors) |
| RRF fusion | <1ms | <1ms |
| **Total hybrid** | **~35-170ms** | **~35-165ms** |

Latencies are comparable. The vector fetch from stored fields replaces the kNN query. Network overhead of transferring 200 × 768 × 4 bytes ≈ 600 KB is the main delta.

### 7.5 Disk Space

Stored-only vectors still consume disk space (and Solr segment memory for stored field access). The saving is purely in HNSW graph RAM:
- HNSW graph overhead: ~1.5–4× the raw vector size (due to neighbor lists)
- Stored fields: raw vector size only

---

## 8. Recommended Implementation Order

### Phase 1 — Foundation (1–2 sprints)
1. **Add `SEARCH_ARCHITECTURE` config** — `config.py` + env var
2. **Add `/v1/capabilities` endpoint** — read-only, returns architecture info
3. **Add stored-only schema variant** — `knn_vector_768_stored` field type
4. **Add cosine similarity helper** — `search_service.py`
5. **Unit tests** for new helpers

### Phase 2 — Search Path (1–2 sprints)
6. **Implement `_search_hybrid_rerank()`** — BM25 + vector fetch + rerank
7. **Mode routing** — switch hybrid implementation based on `SEARCH_ARCHITECTURE`
8. **Guard semantic mode** — 400 error in hybrid-rerank mode
9. **Guard similar-books** — 501 error in hybrid-rerank mode
10. **Integration tests** with both modes

### Phase 3 — UI + Docker (1 sprint)
11. **UI capabilities hook** — fetch `/v1/capabilities`, filter mode options
12. **Docker compose override** — `compose.hybrid-rerank.yml`
13. **Documentation** — deployment guide, migration guide

### Phase 4 — Validation (1 sprint)
14. **A/B quality testing** — compare HNSW hybrid vs rerank hybrid on test queries
15. **Performance benchmarks** — latency and throughput comparison
16. **Memory profiling** — confirm RAM savings

---

## 9. Open Questions for Team Discussion

1. **Should hybrid-rerank use pure cosine rerank or RRF fusion?** RRF preserves BM25 signal; pure rerank trusts vectors more. Recommend RRF (consistent with HNSW hybrid behavior).

2. **Candidate pool size for reranking?** Too small = poor recall, too large = slow vector fetch. Recommend configurable via `RERANK_CANDIDATE_LIMIT` env var, default 200.

3. **Should similar-books work in hybrid-rerank mode?** Could do BM25 on the source book's title/author → vector rerank. Lower quality than kNN but better than nothing. Defer to Phase 2.

4. **Numpy dependency for cosine similarity?** Currently not in solr-search's deps. Pure Python is fast enough for 200 vectors. Add numpy only if profiling shows it's needed.

5. **Schema management:** How do we handle the configurable schema? Options: (a) envsubst at Solr init time, (b) Solr Schema API call at startup, (c) two separate schema files. Recommend (a) — aligns with existing `VECTOR_QUANTIZATION` pattern.

---

## 10. Ownership Assignment (Recommendation)

| Component | Owner | Rationale |
|-----------|-------|-----------|
| Schema variant + Solr init | **Ash** (Search Engineering) | Schema is Ash's domain |
| `config.py` + capabilities endpoint | **Parker** (Backend) | Config and API changes |
| `_search_hybrid_rerank()` | **Ash** (Search Engineering) | Search algorithm implementation |
| UI capabilities integration | **Dallas** (Frontend) | UI mode selector changes |
| Docker compose + docs | **Brett** (Infrastructure) | Deployment configuration |
| Quality benchmarks | **Ash** + **Lambert** (Testing) | Search quality validation |
| Architecture review | **Ripley** (Lead) | Decision arbitration |
