# Hybrid-Rerank Search Pipeline Analysis

**Author:** Ash (Search Engineer)  
**Date:** 2025-07-23  
**Status:** Analysis Complete

---

## 1. Current Solr Query Construction

### 1.1 kNN Query Construction

The kNN path is built in `search_service.py:build_knn_params()` (line 287):

```python
params = {
    "q": f"{{!knn f={knn_field} topK={top_k}}}{vector_str}",
    "rows": top_k,
    "fl": ",".join(SOLR_FIELD_LIST),
    "wt": "json",
}
```

Key details:
- **QParser:** Solr `{!knn}` local-parameter syntax
- **Field:** `embedding_v` (768-dim, `knn_vector_768` type, HNSW cosine)
- **topK:** Passed as `candidate_limit = max(page_size * 2, 20)` for hybrid; `page_size` for pure semantic
- **Vector format:** JSON array string `[0.1,0.2,...]`
- **No EXCLUDE_CHUNKS_FQ:** Chunks carry `parent_id_s`, so filtering them out would eliminate all kNN candidates (explicitly documented in code comments)
- **Optional filter queries:** User facet filters (author, category, etc.) are passed as `fq` params via `build_filter_queries()`

### 1.2 Keyword (BM25) Query Construction

Built in `search_service.py:build_solr_params()` (line 115):

- **QParser:** `edismax` with default field `_text_`
- **Facets:** All six facet fields enabled (author, category, year, language, series, folder)
- **Highlights:** Unified highlighter on `content` and `_text_` fields
- **EXCLUDE_CHUNKS_FQ:** Always applied (`-parent_id_s:[* TO *]`) — returns parent (book-level) docs only
- **Pagination:** Standard `start`/`rows` offset
- **Post-search enrichment:** A second Solr query fetches matching chunk page ranges for keyword results (`build_chunk_page_params`)

### 1.3 Hybrid Search (RRF Fusion)

Implemented in `main.py:_search_hybrid()` (line 1144):

1. **Two separate Solr queries** — NOT a single combined query:
   - **BM25 leg:** `build_solr_params()` with `candidate_limit` rows (includes facets, highlights, EXCLUDE_CHUNKS_FQ)
   - **kNN leg:** `build_knn_params()` with `candidate_limit` candidates (no facets, no highlights, targets chunks)

2. **Concurrency:** BM25 query and embedding fetch run in parallel via `ThreadPoolExecutor(max_workers=2)`. The kNN Solr query runs *after* the embedding returns (sequential dependency).

3. **RRF Fusion:** `reciprocal_rank_fusion()` merges the two result lists:
   - Score formula: `Σ 1/(k + rank)` per list (1-based rank)
   - Default k=60 (configurable via `RRF_K` env var)
   - Documents in both lists score higher
   - Facets sourced from BM25 leg; kNN results get empty highlights
   - Final result truncated to `page_size`

4. **Graceful degradation:** If embeddings service is down (502/503/504), hybrid falls back to keyword-only with `degraded=True`

### 1.4 Solr Response Fields Returned

Standard field list (`SOLR_FIELD_LIST`):
```
id, title_s, author_s, year_i, category_s, language_detected_s, language_s,
series_s, file_path_s, folder_path_s, page_count_i, file_size_l,
thumbnail_url_s, page_start_i, page_end_i, chunk_text_t, parent_id_s, score
```

Note: **`embedding_v` is NOT in the field list** — vectors are never returned in search responses today.

### 1.5 Solr Transport

All queries use `requests.post(url, data=params)` — form-encoded POST body. This avoids URI length limits with large vector payloads (>4KB).

---

## 2. Schema Changes for Hybrid-Rerank Mode

### 2.1 Current Schema Vector Fields

| Field | Type | Indexed | Stored | Usage |
|-------|------|---------|--------|-------|
| `embedding_v` | `knn_vector_768` (HNSW, cosine) | true | true | Primary chunk embedding (float32) |
| `embedding_byte` | `knn_vector_768_byte` (HNSW, BYTE, cosine) | true | true | Int8 quantized chunk embedding |
| `book_embedding` | `knn_vector_768` (HNSW, cosine) | true | true | Parent-level book embedding |

### 2.2 Stored-Only Vector Field Option

**Option A: `stored="true" indexed="false"` on DenseVectorField**

In Solr 9.7, `solr.DenseVectorField` with `indexed="false"` **does not build an HNSW graph**. The field becomes a stored-only binary blob. This is the cleanest approach:

```xml
<fieldType name="knn_vector_768_stored"
           class="solr.DenseVectorField"
           vectorDimension="768"
           similarityFunction="cosine"/>

<field name="embedding_stored"
       type="knn_vector_768_stored"
       indexed="false"
       stored="true"/>
```

**Caveat:** No `knnAlgorithm` attribute is needed (and should be omitted) since there's no index to build. Solr 9.7 accepts this configuration — the DenseVectorField class respects the `indexed` attribute. Verified in Solr source: `DenseVectorField.createField()` checks `indexed()` before building the HNSW codec data.

**Option B: MultivalueFloat field (backup approach)**

If DenseVectorField with `indexed="false"` causes issues in any Solr 9.x minor version:

```xml
<field name="embedding_stored"
       type="pfloats"
       indexed="false"
       stored="true"
       multiValued="true"/>
```

This stores the vector as a plain float array. Works universally but loses type safety and the vector is stored as individual float values rather than a compact binary blob.

**Recommendation: Option A.** It's native, compact, and Solr 9.7-compatible.

### 2.3 Storage Overhead Comparison

| Mode | Field Config | Disk per 768-dim vector | RAM per vector | HNSW graph overhead |
|------|-------------|------------------------|----------------|---------------------|
| HNSW (current) | indexed=true, stored=true | ~3 KB stored + ~3 KB HNSW | ~3 KB (in heap for graph) + neighbors list | ~48 bytes × M neighbors per level |
| Stored-only | indexed=false, stored=true | ~3 KB stored | 0 (no graph in RAM) | 0 |
| HNSW + stored (dual) | Both fields | ~6 KB total | ~3 KB (HNSW only) | Same as HNSW |

For 100K chunks:
- **HNSW mode:** ~600 MB disk, ~300 MB heap for graph navigation
- **Stored-only mode:** ~300 MB disk, ~0 MB heap for vectors (dramatic RAM savings)
- **Dual-field mode:** ~600 MB disk, ~300 MB heap (same as HNSW-only since stored field adds disk but no heap)

**Key insight:** The main savings of hybrid-rerank mode are in **RAM** (no HNSW graph in memory) and **indexing speed** (no graph construction). Disk savings are ~50% since the stored representation is similar size either way.

---

## 3. Query Construction for Hybrid-Rerank Mode

### 3.1 Stage 1: BM25 Candidate Retrieval

Reuse the existing keyword search path almost entirely:

```python
# Existing build_solr_params() works as-is
# But request MORE candidates (recall pool)
bm25_params = build_solr_params(
    query=q, page=1, page_size=rerank_pool_size,  # e.g., 200
    sort_by="score", sort_order="desc",
    facet_limit=facet_limit, filters=filters,
)
```

**Critical change:** `EXCLUDE_CHUNKS_FQ` should remain — BM25 returns parent (book) docs. But we need chunk-level vectors for reranking. Two sub-approaches:

- **Approach A (book-level rerank):** Use `book_embedding` on parent docs for reranking. Simpler, but less precise since book-level embeddings are averaged over all chunks.
- **Approach B (chunk-level rerank):** After BM25 returns parent IDs, fetch their chunk embeddings in a second query. More precise, but requires an additional Solr round-trip.

**Recommendation: Approach A for v1** — rerank using `book_embedding` stored on parent docs. The existing `book_embedding` field already exists on parent documents.

### 3.2 Stage 2: Vector Retrieval for Reranking

To retrieve stored vectors efficiently:

```python
# Add embedding field to fl (field list) for rerank mode
RERANK_FIELD_LIST = SOLR_FIELD_LIST + ["book_embedding"]

# In build_solr_params, when mode is hybrid-rerank:
params["fl"] = ",".join(RERANK_FIELD_LIST)
```

**Solr returns vectors as JSON arrays** when they're in the `fl` list and stored=true. For 768-dim float32 vectors, each result adds ~6 KB to the response payload. For a pool of 200 candidates, that's ~1.2 MB of vector data — acceptable.

For chunk-level reranking (future Approach B):

```python
# Second query to fetch chunk embeddings for candidate parent IDs
chunk_params = {
    "q": "*:*",
    "fq": [f"parent_id_s:({' OR '.join(parent_ids)})"],
    "fl": "parent_id_s,embedding_stored",
    "rows": len(parent_ids) * 3,  # ~3 chunks per book
    "wt": "json",
}
```

### 3.3 Stage 3: Application-Side Cosine Similarity

```python
import numpy as np

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))
```

For 200 candidates × 768 dimensions, this takes <1ms with NumPy. Negligible latency.

### 3.4 RRF Fusion for Hybrid-Rerank

The existing `reciprocal_rank_fusion()` function can be reused directly:

```python
# BM25 results are already ranked by Solr score
bm25_ranked = [...]  # from Stage 1

# Reranked by cosine similarity
vector_ranked = sorted(bm25_ranked, key=lambda d: d["cosine_sim"], reverse=True)

# Fuse using existing RRF
fused = reciprocal_rank_fusion(bm25_ranked, vector_ranked, k=settings.rrf_k)
```

**Key difference from current hybrid:** Both ranked lists come from the SAME candidate pool (BM25 top-N), just ranked differently. Current hybrid draws from two independent pools (BM25 books vs kNN chunks). This means hybrid-rerank fusion can never introduce documents that BM25 didn't find.

---

## 4. Solr Configuration

### 4.1 Single Schema Supporting Both Modes

**Yes — a single schema can support both modes.** Add the stored-only field alongside existing HNSW fields:

```xml
<!-- Existing HNSW fields (unchanged) -->
<field name="embedding_v" type="knn_vector_768" indexed="true" stored="true"/>
<field name="embedding_byte" type="knn_vector_768_byte" indexed="true" stored="true"/>
<field name="book_embedding" type="knn_vector_768" indexed="true" stored="true"/>

<!-- NEW: stored-only field for hybrid-rerank mode (no HNSW graph) -->
<fieldType name="knn_vector_768_stored"
           class="solr.DenseVectorField"
           vectorDimension="768"
           similarityFunction="cosine"/>
<field name="embedding_rerank"
       type="knn_vector_768_stored"
       indexed="false"
       stored="true"/>
```

The indexer chooses which fields to populate based on a `SEARCH_ARCHITECTURE` env var:
- `hnsw`: Write to `embedding_v` (or `embedding_byte`) — current behavior
- `hybrid-rerank`: Write to `embedding_rerank` (and `book_embedding` for parent-level rerank)
- `both`: Write to both (for A/B testing between modes)

**No separate schema variants needed.** Unpopulated DenseVectorFields have zero overhead.

### 4.2 solrconfig.xml Changes

**No changes required for v1.** The hybrid-rerank mode uses only standard `/select` queries (BM25 + field retrieval). No Solr-side reranking plugins needed.

For future optimization, consider:

```xml
<!-- Optional: dedicated handler with larger maxBooleanClauses for chunk retrieval -->
<requestHandler name="/rerank-vectors" class="solr.SearchHandler">
  <lst name="defaults">
    <str name="echoParams">explicit</str>
    <str name="wt">json</str>
    <int name="rows">600</int>
  </lst>
</requestHandler>
```

The existing LTR module (`solr.modules=ltr`) could enable Solr-side reranking in the future, but application-side reranking is simpler and more flexible for v1.

### 4.3 Mode Selection Architecture

```
┌──────────────────────────────────────────────────────┐
│  Search API (mode parameter)                         │
│                                                      │
│  keyword ──────► BM25 (existing, unchanged)          │
│  semantic ─────► kNN HNSW (existing, unchanged)      │
│  hybrid ───────► BM25 + kNN + RRF (existing)         │
│  hybrid-rerank ► BM25 + stored vectors + app cosine  │  ◄── NEW
│                  + RRF                               │
└──────────────────────────────────────────────────────┘
```

Add `"hybrid-rerank"` to `VALID_SEARCH_MODES` and implement `_search_hybrid_rerank()` as a new code path in `main.py`.

---

## 5. Quality Analysis

### 5.1 BM25 Recall Estimation for Book Search

For a library book search system with structured queries (author names, titles, topics):

| Query Type | Estimated BM25 recall@100 | BM25 recall@200 | Notes |
|------------|--------------------------|-----------------|-------|
| Known-item (author + title) | 95–99% | 98–99% | BM25 excels at exact/near-exact matches |
| Topic keyword ("machine learning") | 80–90% | 85–95% | Good if `_text_` covers content + metadata |
| Conceptual ("books about grief") | 30–50% | 40–60% | BM25 misses semantic meaning |
| Cross-lingual ("libros sobre IA" in EN corpus) | 5–15% | 10–20% | BM25 is language-bound |
| Synonym-dependent ("automobile" vs "car") | 50–70% | 60–80% | Depends on synonym file quality |

**Overall weighted estimate** (assuming 60% known-item/topic, 25% conceptual, 15% cross-lingual/synonym):
- **recall@100:** ~65–75%
- **recall@200:** ~72–82%

### 5.2 What's Lost Without HNSW First-Stage Retrieval

When BM25 is the sole first-stage retriever:

1. **Semantic recall gap:** Documents that are semantically relevant but lack exact keyword overlap are completely invisible. The reranking stage can only reorder what BM25 found — it cannot resurrect missed documents.

2. **Conceptual queries suffer most:** "Books that make you think about mortality" — BM25 won't find *The Death of Ivan Ilyich* unless the words "mortality" or "think" appear in the indexed text.

3. **Cross-lingual recall is near-zero:** A Spanish query against English content (or vice versa) gets virtually no BM25 candidates. E5-base handles this natively via its multilingual training.

4. **Diminishing returns of larger rerank pools:** Increasing from recall@100 to recall@200 yields modest gains (5–10%) because BM25's ranking tail contains increasingly irrelevant documents.

### 5.3 Where Pure Semantic Beats BM25

| Query Type | Semantic Advantage | Example |
|------------|-------------------|---------|
| **Conceptual queries** | High | "books about overcoming adversity" |
| **Cross-lingual** | Very high | Spanish query → English books |
| **Synonym/paraphrase** | Medium-high | "automobile repair" finds "car maintenance" |
| **Typo tolerance** | Medium | "machien lerning" → machine learning |
| **Vague/exploratory** | Medium | "something like Borges" |
| **Known-item with exact terms** | Low (BM25 wins) | "Don Quixote Cervantes" |
| **Metadata-specific** | Low (BM25 wins) | "published in 2020" |

### 5.4 Recommendations for Mitigation

To compensate for BM25's recall limitations in hybrid-rerank mode:

1. **Expand BM25 candidate pool aggressively:** Use recall@200 or recall@300 to catch more potential matches.
2. **Enrich the `_text_` copy field** with metadata concatenation (author + title + category + series) to boost known-item recall.
3. **Invest in synonym files** for each language to close the synonym gap.
4. **Add query expansion:** Before BM25 query, use the embedding to find related terms and append them (pseudo-relevance feedback).
5. **Track quality metrics:** Measure nDCG@10 for both modes using the existing A/B comparison endpoint.

---

## 6. Implementation Roadmap

### Phase 1: Schema (Ash)
- Add `knn_vector_768_stored` field type and `embedding_rerank` field to managed-schema.xml
- No existing fields modified

### Phase 2: Indexer changes (Parker)
- Add `SEARCH_ARCHITECTURE` env var logic
- Write to `embedding_rerank` field when in hybrid-rerank mode

### Phase 3: Query path (Parker, schema guidance from Ash)
- Add `hybrid-rerank` search mode to `VALID_SEARCH_MODES`
- Implement `_search_hybrid_rerank()` using existing BM25 path + stored vector retrieval + app-side cosine + RRF
- Add `book_embedding` (or `embedding_rerank`) to `fl` for rerank queries

### Phase 4: A/B comparison
- Use existing comparison endpoint to measure HNSW hybrid vs hybrid-rerank quality
- Success criteria: ≤5% nDCG@10 regression, ≥30% RAM reduction

---

## 7. Key Risks and Open Questions

1. **DenseVectorField indexed=false in Solr 9.7:** Needs integration test. If it fails, fall back to Option B (pfloats field).
2. **Book-level vs chunk-level reranking precision:** Book-level embeddings average over all chunks, potentially losing passage-level signal. Monitor quality metrics.
3. **BM25 recall ceiling:** For conceptual/cross-lingual queries, no amount of reranking can fix a bad candidate set. Consider a "fallback to HNSW" mode for queries with low BM25 confidence.
4. **Vector serialization format:** Verify Solr returns stored DenseVectorField values as JSON arrays (not binary) when included in `fl`. If binary, a deserialization step is needed.
