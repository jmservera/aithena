# Decision: Hybrid-Rerank Search Pipeline Design

**Author:** Ash (Search Engineer)  
**Date:** 2025-07-23  
**Status:** Proposed

## Context

We want to support a second search architecture mode ("hybrid-rerank") that avoids HNSW indexing overhead. Instead of kNN retrieval, BM25 finds candidates and application-side cosine similarity reranks them using stored vectors.

## Decision

### Schema
- Add a `knn_vector_768_stored` field type (DenseVectorField, no `knnAlgorithm`) and an `embedding_rerank` field with `indexed="false" stored="true"`. This avoids HNSW graph construction and saves ~300 MB heap per 100K chunks.
- Single schema supports both modes. Unpopulated fields have zero overhead.

### Query Architecture
- New `hybrid-rerank` search mode added to `VALID_SEARCH_MODES`.
- Stage 1: BM25 via existing `build_solr_params()` with larger candidate pool (200+).
- Stage 2: Retrieve `book_embedding` (parent-level) via `fl` parameter for app-side cosine reranking.
- Stage 3: RRF fusion using existing `reciprocal_rank_fusion()` — BM25 rank + cosine rank.

### Tradeoffs Accepted
- **BM25 recall ceiling:** Conceptual and cross-lingual queries will have lower recall since HNSW is not a first-stage retriever. Mitigated by larger candidate pools and synonym expansion.
- **Book-level vs chunk-level reranking:** v1 uses `book_embedding` for simplicity. Chunk-level reranking deferred to v2.

### No Changes Needed
- `solrconfig.xml` unchanged — standard `/select` queries suffice.
- Existing search modes (keyword, semantic, hybrid) unchanged.

## Alternatives Considered
- **pfloats field for stored vectors:** Works universally but loses type safety. DenseVectorField with indexed=false is cleaner.
- **Solr-side LTR reranking:** More complex, requires module loading and model management. App-side reranking is simpler for v1.
- **Two separate schema variants:** Rejected — single schema with optional fields is simpler to maintain.

## Impact
- **Ash:** Schema PR to add field type + field (Phase 1)
- **Parker:** Indexer and query path changes (Phases 2-3)
- **Quality:** A/B comparison needed before production (Phase 4). Success: ≤5% nDCG@10 regression, ≥30% RAM reduction.
