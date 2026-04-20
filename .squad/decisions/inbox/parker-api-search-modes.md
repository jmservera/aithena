# Decision: API Design for Dual Search Architecture Modes

**Author:** Parker (Backend Dev)
**Date:** 2026-07-15
**Status:** Proposed

## Context

We need to support two search architecture modes: HNSW (current Solr kNN) and hybrid-rerank (BM25 candidates + app-side cosine reranking). This affects solr-search API behavior, configuration, and the new capabilities endpoint.

## Decisions

1. **`SEARCH_ARCHITECTURE` env var** controls mode (`hnsw` default, `hybrid-rerank`). Added to solr-search `config.py` Settings dataclass.

2. **`GET /v1/capabilities` endpoint** — public, no auth. Returns architecture type, available search modes, quantization, embedding dimensions, allowed collections. UI calls this at startup.

3. **Reranking logic lives in `search_service.py`** — new `rerank_by_cosine_similarity()` function using numpy cosine similarity. Fed into existing `reciprocal_rank_fusion()`.

4. **Document indexer is architecture-agnostic** — it always writes vectors to the field the embeddings server specifies. The stored-vs-indexed distinction is handled entirely by the Solr schema (Ash's domain).

5. **numpy added as dependency** to solr-search for cosine similarity computation. Performance is ~1-5ms for 200×768D vectors — negligible.

6. **`RERANK_CANDIDATES` env var** (default 200) — number of BM25 candidates to fetch for reranking in hybrid-rerank mode.

7. **Hybrid-rerank requires stored vectors in Solr** — `embedding_v` (or `embedding_byte_v`) must have `stored="true"` in the schema. This is a blocking dependency on Ash.

## Impact

- solr-search: 4 files modified (config.py, search_service.py, main.py, plus tests)
- document-indexer: no code changes (schema-driven)
- embeddings-server: no changes
- Backward compatible: defaults to `hnsw` (current behavior)

## Full Analysis

See `.squad/analysis/api-search-architecture-modes.md`
