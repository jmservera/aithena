---
name: "hybrid-search-patterns"
description: "How to implement and maintain hybrid search (BM25 + kNN + RRF) with embedding integration, fallback strategies, and timeout handling"
domain: "search, embeddings, hybrid-search"
confidence: "high"
source: "earned — extracted from search_service.py implementation, #562 timeout fix, #706 POST fix, retro R2 learnings"
author: "Ash"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context
Apply this skill when implementing or modifying search endpoints, adding new search modes, changing embedding integration, or debugging search failures (502s, empty results, degraded modes). Covers the full hybrid search pipeline from query to fused results.

## Patterns

### 1. Three search modes with clear boundaries

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

### 2. RRF implementation rules

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

### 3. Embedding integration with graceful degradation

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

### 4. Use POST for Solr queries

kNN vectors are 512 floats serialized as JSON arrays — easily >4KB. Combined with filter queries, this exceeds GET URI limits. Always use POST request body for Solr queries. (Source: #706)

### 5. Facet integration across modes

| Source | keyword | semantic | hybrid |
|--------|---------|----------|--------|
| Facets | Solr `facet_counts` | None | From BM25 leg |
| Highlights | Solr `highlighting` | None | From BM25 leg |
| Sort | Solr-native | By cosine score | By RRF score |

Facet fields are defined in `FACET_FIELDS` dict mapping logical names to Solr field tuples. Multi-field facets (e.g., language uses both `language_detected_s` and `language_s`) fall back to the first non-empty field.

### 6. Filter query security

All facet filter values must be Lucene-escaped before inclusion in `fq` parameters to prevent Solr query injection. Use the `solr_escape()` utility function (typically via `build_filter_queries`, which applies it for you).

## Anti-Patterns

- **Don't apply chunk exclusion to kNN queries** — chunks are the only documents with embeddings (see `solr-parent-chunk-model` skill)
- **Don't set nginx timeout equal to or less than upstream timeout** — always use 1.5x safety margin
- **Don't use GET for Solr queries with kNN vectors** — URI length limits will cause failures
- **Don't return facets from semantic leg** — Solr kNN doesn't produce `facet_counts`; trying to parse them causes KeyError
- **Don't block on embedding generation** — use concurrent execution in hybrid mode (ThreadPoolExecutor for BM25 + embedding fetch)
- **Don't silently swallow embedding errors** — log and degrade to keyword, informing the response with the actual mode used

## Examples

### Example: Adding a new search mode
1. Define the mode in the search endpoint's `mode` enum
2. Implement `_search_{mode}()` following the pattern of existing modes
3. Handle empty query behavior explicitly
4. Add tests for: normal query, empty query, facet filters, error cases
5. Update the search architecture table in history.md

### Example: Debugging 502 on search
1. Check nginx `proxy_read_timeout` vs upstream service timeout
2. Check both `.conf` and `.conf.template` for drift
3. Check embeddings-server health: `GET /health`
4. Check Solr cluster status: `GET /solr/admin/collections?action=CLUSTERSTATUS`

## References
- `src/solr-search/search_service.py` — RRF implementation, query builders
- `src/solr-search/main.py` — search endpoint with mode dispatch
- `src/nginx/default.conf.template` — timeout configuration
- `.squad/skills/solr-parent-chunk-model/SKILL.md` — document model rules
