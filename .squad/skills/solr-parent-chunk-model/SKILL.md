---
name: "solr-parent-chunk-model"
description: "Parent/chunk document architecture and hybrid search implementation (BM25 + kNN + RRF) in aithena's Solr schema"
domain: "search, solr, data-model, hybrid-search, embeddings"
confidence: "high"
source: "earned — extracted from retro R2 incident (PR #701/#723), search_service.py, hybrid-search implementation, #562 timeout fix, #706 POST fix"
author: "Ash"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context
Apply this skill when modifying Solr queries, adding schema fields, changing search modes, or reviewing PRs that touch `search_service.py`, `managed-schema.xml`, or document-indexer chunking logic. The parent/chunk split is the most common source of correctness bugs in this project.

## Patterns

### 1. Two document types share one Solr collection

**Parent documents (books):**
- `id` = SHA-256 of file path (unique per book)
- Metadata: `title_s/t`, `author_s/t`, `year_i`, `category_s`, `series_s`, `language_detected_s`, `file_path_s`, `folder_path_s`, `page_count_i`, `file_size_l`
- Optional: `book_embedding` (512D) for book-level similarity
- **No `parent_id_s` field** — this is how you identify a parent

**Chunk documents (text fragments):**
- `id` = `{parent_id}_chunk_{index}` (index is zero-padded, e.g. `{parent_id}_chunk_0000`)
- `parent_id_s` = parent book's `id` (foreign key)
- `chunk_text_t` = extracted text (400 words, 50-word overlap, page-aware)
- `embedding_v` = 512D dense vector (HNSW cosine) — **primary kNN search field**
- `chunk_index_i`, `page_start_i`, `page_end_i` for positioning
- Inherits parent metadata for display (title, author, year, etc.)

### 2. Filter rules differ by search mode

**Keyword (BM25):**
- Apply `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` to return only parent documents
- Chunks would pollute keyword results with fragment-level matches

**Semantic (kNN):**
- Do NOT apply chunk exclusion — kNN MUST target chunk documents (they carry `embedding_v`)
- Results are deduplicated at book level after retrieval

**Hybrid (RRF):**
- BM25 leg: apply chunk exclusion (parents only)
- kNN leg: no chunk exclusion (chunks only)
- RRF fusion merges both, deduplicates at book level

### 3. Adding new fields — which document type?

| Field purpose | Add to parent? | Add to chunk? | Why |
|---------------|---------------|---------------|-----|
| Book metadata (author, year) | Yes | Copy from parent | Chunks need it for display after kNN |
| Full-text search field | Yes (via Tika) | No (use chunk_text_t) | Tika extracts to parent; chunks have own text |
| Dense vector embedding | Optional (book_embedding) | Yes (embedding_v) | kNN searches chunks, not parents |
| Facet field | Yes | Not needed | Facets come from BM25 leg (parents only) |

### 4. ID generation
- Parent: `hashlib.sha256(file_path.encode()).hexdigest()`
- Chunk: `f"{parent_id}-chunk-{chunk_index}"`
- Deleting a book must delete parent AND all chunks with matching `parent_id_s`

## Anti-Patterns

- **Never apply `EXCLUDE_CHUNKS_FQ` to kNN queries** — this silently returns zero results since chunks are the only documents with embeddings. (Source: PR #701 incident)
- **Never assume parent documents have embeddings** — `book_embedding` is optional; `embedding_v` on chunks is the primary vector field.
- **Never add a new field to only one document type without considering search modes** — if the field is needed for display in semantic results, it must exist on chunks too.
- **Never delete a parent without also deleting its chunks** — orphaned chunks waste index space and pollute kNN results.

## Examples

### Correct: kNN query targeting chunks
```python
params = {
    "q": "{!knn f=embedding_v topK=10}[0.5, -0.2, ...]",
    # NO fq excluding chunks — chunks ARE the target
}
```

### Correct: BM25 query excluding chunks
```python
params = {
    "q": "search terms",
    "defType": "edismax",
    "fq": ["-parent_id_s:[* TO *]"],  # parents only
}
```

### Correct: Delete book and its chunks
```python
solr.delete(q=f'id:"{book_id}" OR parent_id_s:"{book_id}"')
solr.commit()
```

## 5. Hybrid search implementation (BM25 + kNN + RRF)

### Three search modes with clear boundaries

**Keyword (BM25):**
- Solr edismax parser, query fields: `_text_` (default), phrase boost: `title_t^2`
- Returns: results + facets + highlights
- Empty query normalized to `*:*` (returns everything)
- Filter: exclude chunk documents (`-parent_id_s:[* TO *]`)

**Semantic (kNN):**
- Solr `{!knn}` local-parameter syntax on `embedding_v` field
- Requires external embedding via `POST /v1/embeddings/`
- Returns: results only (no facets, no highlights from Solr)
- Empty query returns 400 (cannot embed empty string)
- Targets chunk documents (they carry vectors)

**Hybrid (RRF):**
- Run BM25 and kNN in parallel (ThreadPoolExecutor)
- Fuse with Reciprocal Rank Fusion: `score = sum(1/(k + rank))`, k=60
- Facets and highlights from BM25 leg only
- Deduplicate at book level

### RRF implementation rules

```python
def reciprocal_rank_fusion(keyword_results, semantic_results, k=60):
    scores = {}
    result_map = {}
    for rank, doc in enumerate(keyword_results, start=1):
        scores[doc["id"]] = 1.0 / (k + rank)
        result_map[doc["id"]] = doc
    for rank, doc in enumerate(semantic_results, start=1):
        scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank)
        if doc["id"] not in result_map:
            result_map[doc["id"]] = doc
    return sorted by scores descending, with RRF score replacing original score
```

Key properties:
- k=60 is from the original RRF paper; configurable via `RRF_K` env var
- Documents in both legs score higher than documents in only one
- Original BM25/cosine scores are replaced with RRF combined scores
- BM25 candidate limit should be `max(page_size * 2, 20)` for adequate fusion

### Embedding integration with graceful degradation

**Call pattern:**
```python
response = httpx.post(EMBEDDINGS_URL, json={"input": query_text}, timeout=EMBEDDINGS_TIMEOUT)
vector = response.json()["data"][0]["embedding"]  # 512-dim float list
```

**Fallback chain:**
1. If embeddings-server returns error or timeout: fall back to keyword mode
2. If empty query: return 400 (semantic/hybrid) or `*:*` results (keyword)
3. If Solr kNN returns zero results: return empty result set (not an error)

**Timeout alignment (critical):**
- Embeddings service timeout: 120s (configurable via `EMBEDDINGS_TIMEOUT`)
- Nginx `proxy_read_timeout`: must be >= 1.5x embeddings timeout (180s)
- Solr query timeout: default (no explicit timeout, relies on Solr defaults)
- If nginx timeout < upstream timeout, you get 502 Bad Gateway

### Use POST for Solr queries

kNN vectors are 512 floats serialized as JSON arrays — easily >4KB. Combined with filter queries, this exceeds GET URI limits. Always use POST request body for Solr queries. (Source: #706)

### Facet integration across modes

| Source | keyword | semantic | hybrid |
|--------|---------|----------|--------|
| Facets | Solr `facet_counts` | None | From BM25 leg |
| Highlights | Solr `highlighting` | None | From BM25 leg |
| Sort | Solr-native | By cosine score | By RRF score |

Facet fields are defined in `FACET_FIELDS` dict mapping logical names to Solr field tuples. Multi-field facets (e.g., language uses both `language_detected_s` and `language_s`) fall back to the first non-empty field.

### Filter query security

All facet filter values must be Lucene-escaped before inclusion in `fq` parameters to prevent Solr query injection. Use the `solr_escape()` utility function (typically via `build_filter_queries`, which applies it for you).

### Embedding pipeline

- Model: `distiluse-base-multilingual-cased-v2` (512 dimensions)
- Embeddings generated by `embeddings-server` at `POST /v1/embeddings/`
- Book-level embedding (`book_embedding`): computed during indexing, used for similar-books
- Chunk-level embedding (`embedding_v`): computed per chunk during indexing, used for search
- Query embedding: computed at search time by `solr-search` calling embeddings-server
- Empty query → 400 error (can't embed empty string; this is intentional)

### Filter queries work across all modes

All search modes support the same filter query parameters:
- `fq_author`, `fq_category`, `fq_language`, `fq_year`
- These filter on parent document fields and are safe to apply to all query types
- For kNN, filters are applied post-kNN (Solr applies fq after vector scoring)

## References
- `docs/architecture/solr-data-model.md` — full architecture reference
- `src/solr-search/search_service.py` — RRF implementation, EXCLUDE_CHUNKS_FQ constant, query builders
- `src/solr/books/managed-schema.xml` — field definitions
- `src/solr-search/README.md` — data model summary
- PR #723 — Solr data model documentation (retro action R2)
- PR #701 — The near-incident that motivated this documentation
- PR #562 — Timeout fix
- PR #706 — POST fix for large kNN vectors
