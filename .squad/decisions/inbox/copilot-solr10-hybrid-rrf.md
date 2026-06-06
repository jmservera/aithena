# Decision Proposal: Keep App-Side Hybrid RRF Until Solr Combined Query Is Benchmarked

**Date:** 2026-06-06  
**Author:** Ash (via Copilot)  
**Related:** #1349, SOLR-17319

## Context

Solr 10.0.0 does not include a native RRF/combined-query handler. Solr mainline after the 10.0.0 tag now includes `CombinedQuerySearchHandler` / `CombinedQueryComponent` for multi-query fusion with built-in Reciprocal Rank Fusion (RRF). This is relevant to Aithena's current BM25 + kNN + RRF hybrid search implementation.

## Proposal

Keep Aithena's current app-side hybrid search as the production default until the shipped Solr runtime includes SOLR-17319 and a dedicated prototype proves that Solr Combined Query RRF preserves or improves relevance and latency on the real corpus.

## Rationale

Aithena currently fuses parent-document BM25 results with chunk-document kNN results after normalizing chunks to book IDs in Python. Solr native RRF fuses by Solr document ID, so a naive parent BM25 + chunk kNN combined query will not reward overlap between the same book's parent and chunks. Combined Query also does not support grouping/cursors, so parent-level chunk grouping cannot be assumed inside the fusion step.

## Next Step

Prototype behind a separate Solr handler/flag and benchmark:

1. Current app-side chunk-kNN RRF.
2. Solr Combined Query RRF with parent/book-level vectors, if parent vectors are indexed.
3. Optional chunk-keyword + chunk-vector fusion with post-normalization.

Do not change default ranking without judged relevance, latency, facet/highlight, and page-range validation.
