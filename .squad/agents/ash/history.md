# Ash — History

## Core Context

Ash owns Solr/search architecture, schema evolution, hybrid ranking, multilingual analyzers, and embedding-model evaluation.

- Aithena uses a parent/chunk model: parent docs hold book metadata, chunk docs hold text and vectors.
- `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` applies only to the BM25 leg; never apply it to kNN queries.
- Keyword search is BM25 + facets/highlights, semantic search is chunk-kNN, and hybrid search is BM25 + kNN fused with RRF.
- Long vector payloads should go through POST bodies, not GET URLs; embeddings timeout and nginx proxy timeout must stay aligned.
- Model changes use dual-collection A/B testing with shared analyzers and independent vector dimensions.

## Active Patterns

- Schema changes are the critical path for search work and must be coordinated early.
- Parent/chunk correctness is the most failure-prone area; deletion, similar-books, and hybrid ranking all depend on it.
- Keep current app-side book normalization unless Solr-native alternatives are benchmarked against real corpus data.
- E5 prefix handling belongs in embeddings-server/runtime adapters, not in Solr.

## Recent Learnings

### 2026-06-06 — Solr 9.7 vs Solr 10 benchmark evidence (#1354)
- Performance claims must come from paired same-host, same-corpus runs with recorded corpus metadata, memory samples, timing, and failed query IDs.
- The benchmark harness and comparison scripts are evidence gates, not substitutes for live measured runs.

### 2026-06-06 — DocumentCategorizer prototype feasibility (#1348)
- Solr 10 `DocumentCategorizerUpdateProcessorFactory` is feasible only as a disabled scaffold until a real ONNX model fixture and labeled corpus exist.
- Classifier output should go to separate fields such as `topic_category_s` / `document_sentiment_s`; never overwrite manual `category_s`.

### 2026-06-06 — Combined Query / hybrid search evaluation (#1349)
- Solr-native combined-query RRF is promising, but it is not a drop-in replacement because Aithena fuses parent-doc BM25 results with chunk-doc kNN results.
- Keep Python-side chunk normalization/RRF in production until a prototype is benchmarked for relevance, latency, facets/highlights, and page-range quality.

### 2026-06-06 — v2.5.1 board / research loop
- Phase 3 readiness and quantization work remain blocked on schema correctness plus real benchmark evidence.
- The production Solr 10 stance stays: Overseer disabled mode is acceptable, app-side RRF remains default, and optional quantization needs measured recall/memory proof before broad enablement.
