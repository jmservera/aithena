# Solr 10 Hybrid Search Evaluation

**Date:** 2026-06-06  
**Issue:** [#1349](https://github.com/jmservera/aithena/issues/1349)  
**Owner:** Ash (Search Engineer)  
**Status:** Research complete; prototype deferred until corpus/runtime validation is scheduled.

## Summary

Solr 10.0.0 does **not** provide an immediately actionable, drop-in hybrid-search replacement for Aithena's current BM25 + chunk-kNN + app-side RRF path. The most relevant improvement is on Apache Solr mainline after the 10.0.0 tag: SOLR-17319 / PR #3418 adds `CombinedQuerySearchHandler` / `CombinedQueryComponent` JSON DSL support for executing multiple named queries and fusing them with Reciprocal Rank Fusion (RRF). That feature is directly relevant to Aithena, but it must be treated as a follow-up target until the runtime image includes it and it has been benchmarked against Aithena's parent/chunk model.

The current Aithena implementation should stay in place. The next useful step, once a Solr release/runtime includes SOLR-17319, is a benchmark/prototype that compares current app-side RRF with Solr Combined Query RRF on a book-level vector variant, and explicitly measures whether any relevance, latency, or operational simplicity gain is worth losing chunk-level semantic overlap behavior.

## Current Aithena Hybrid Search Audit

Aithena's default `hnsw` search architecture in `src/solr-search/main.py` does the following:

1. **Keyword leg:** BM25/eDisMax on parent book documents, with `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` so chunk documents do not pollute keyword results.
2. **Semantic leg:** query embedding from the local embeddings-server, then Solr `{!knn f=<KNN_FIELD> topK=N}` against chunk vectors. The chunk-exclusion filter is intentionally not applied.
3. **Fusion:** `reciprocal_rank_fusion()` in `search_service.py`, default `RRF_K=60`, after normalizing chunk hits to book-level results.
4. **Facets/highlights:** sourced from the BM25 leg only.
5. **Fallback:** if embeddings are unavailable, hybrid degrades to keyword results.

There is also a `SEARCH_ARCHITECTURE=hybrid-rerank` mode that avoids HNSW search: BM25 retrieves parent candidates, first-chunk vectors are fetched from Solr, app-side cosine similarity reranks candidates, and RRF combines BM25 rank with vector rank.

The schema is already Solr-10-oriented for vector fields (`DenseVectorField`, `ScalarQuantizedDenseVectorField`, 768D E5 vectors), and current docs already defer `efSearchScaleFactor`, cuVS, and language-models work to later validation.

## Solr 10.0.0 / Mainline Findings

### 1. Query parsers

Official dense-vector docs list three vector query parsers:

- `{!knn}` for top-K nearest vectors.
- `{!vectorSimilarity}` for threshold-based vector matches.
- `{!knn_text_to_vector}` for query-time text-to-vector encoding through a configured text-to-vector model.

Aithena already uses `{!knn}` correctly with POST bodies. `vectorSimilarity` may be useful for threshold-style semantic filters, but it does not replace hybrid fusion. `knn_text_to_vector` is not immediately actionable for Aithena's local/private E5 flow because prior research found Solr's language-models integration is still provider/adapter driven and does not remove the local embeddings-server cleanly.

### 2. Native score fusion / RRF

Solr 10.0.0 does not contain a native RRF/combined-query handler. Verification against the Apache Solr `releases/solr/10.0.0` tag found no `json-combined-query-dsl.adoc` reference-guide page and no SOLR-17319 changelog entry.

Apache Solr mainline does now contain SOLR-17319 Combined Query support for hybrid search with RRF:

- New handler/component: `solr.CombinedQuerySearchHandler` and `solr.CombinedQueryComponent`.
- JSON DSL can provide multiple named queries under `queries`.
- `params.combiner=true` enables fusion.
- `params.combiner.query` selects the named queries to fuse.
- `params.combiner.algorithm=rrf` is the built-in algorithm.
- `params.combiner.rrf.k` controls the RRF `k` value; default is `60`.
- Docs say it works in Standalone and SolrCloud modes, but grouping and cursors are unsupported.

This is the strongest candidate for future simplification once it is available in the Solr runtime Aithena ships, because it can move RRF fusion into Solr and make distributed fusion Solr-owned.

### 3. Why it is not drop-in for Aithena

A naive Combined Query request would fuse different document identities:

- BM25 query returns **parent book IDs**.
- kNN query returns **chunk IDs** like `{parent_id}_chunk_0000`.

RRF rewards documents that appear in multiple ranked lists, but parent IDs and chunk IDs will not overlap. That means native RRF would not reproduce the current app behavior where chunk hits are normalized/deduplicated to book IDs before fusion. Combined Query docs also call out no grouping support, so we cannot simply group/collapse chunk hits to parent IDs inside that combined-query step.

Potential prototype routes:

1. **Book-level vector leg:** fuse BM25 parent docs with parent-level vectors. This aligns document IDs, but Aithena's indexer currently writes chunk vectors, not parent `book_embedding` vectors, and this may lose chunk-level semantic recall/page context.
2. **Chunk-only hybrid:** run keyword and vector legs over chunks, then normalize to books after Solr. This would require indexing/searching chunk text as the lexical leg and rethinking facets/highlights.
3. **Keep app fusion:** continue normalizing to book IDs in Python; use Solr 10 tuning improvements independently.

### 4. Reranking and relevance tuning

Solr's ReRank Query Parser supports `reRankQuery`, `reRankDocs`, `reRankWeight`, `reRankScale`, `reRankMainScale`, and `reRankOperator`. Dense-vector docs show kNN can be used as a rerank query, but note a current limitation: the second-pass kNN still executes on the whole index, and then only contributes to first-pass documents that are within the global top-K.

For Aithena, native rerank has the same identity-alignment issue if the main query returns parents and vector query returns chunks. It may be viable with a book-level vector field, but it needs corpus validation before changing production ranking.

### 5. HNSW tuning parameters

Solr 10 exposes `efSearchScaleFactor` for kNN search-time recall/latency tuning: effective `efSearch = efSearchScaleFactor * topK`, with accepted values `>= 1.0`. This is actionable as a separate tuning feature, already tracked outside this research issue. It requires benchmark validation because higher values can improve recall while slowing queries.

Other vector improvements (scalar/binary quantization and cuVS) are important for memory/build performance, but they are not hybrid-fusion improvements by themselves.

## Recommendation

Do **not** replace Aithena's current hybrid search path immediately.

Recommended next steps:

1. Keep current app-side BM25 + chunk-kNN + book-level RRF as the production-safe implementation.
2. Open a follow-up prototype/benchmark task for Solr Combined Query RRF only after the target Solr image includes SOLR-17319.
3. Prototype on a branch with a separate Solr handler (for example `/combined-search`) rather than changing `/select` or `/query` defaults.
4. Compare at least these variants against the benchmark query suite and real corpus:
   - Current app-side chunk-kNN RRF.
   - Solr Combined Query RRF using parent/book-level vectors, if parent vectors are indexed.
   - Optional chunk-keyword + chunk-vector Combined Query with post-normalization to books.
5. Measure relevance and runtime before any product decision: nDCG@10 / judged relevance, top-K overlap, p50/p95 latency, facets/highlight behavior, and page-range quality.

## References

- Solr dense vector search docs: `knn`, `vectorSimilarity`, `knn_text_to_vector`, rerank usage, `efSearchScaleFactor`, cuVS.
- SOLR-17319: Reciprocal Rank Fusion / combined queries for hybrid search; absent from the `releases/solr/10.0.0` tag, present on mainline.
- Apache Solr PR #3418: merged Combined Query implementation and reference-guide docs on mainline after the 10.0.0 tag.
- `src/solr-search/main.py` and `src/solr-search/search_service.py`: current hybrid implementation.
- `src/solr/books/managed-schema.xml`: current 768D vector schema.
- `docs/architecture/solr-data-model.md`: parent/chunk search model.
