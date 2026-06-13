# Solr Quantization & Version Benchmark Results

**Issue:** #1717  
**Host:** jmsquad-1 (dedicated benchmark host)  
**Corpus:** benchmark-20260612T205519Z — 1,502 multilingual PDFs (EN:400, FR:401, ES:401, CA:300) from Project Gutenberg, 21.4 MB total → ~14,000 Solr chunks

## Benchmark Results Summary

### Solr 9.7 float32 (single node)
| Mode | Mean ms | Median ms | p95 ms | Errors |
|------|---------|-----------|--------|--------|
| keyword | 51 | 40 | 121 | 0 |
| semantic | 71 | 69 | 101 | 0 |
| hybrid | 101 | 94 | 221 | 0 |
- RAM: 1.05 GiB (single node)

### Solr 10 float32 (3-node SolrCloud)
| Mode | Mean ms | Median ms | p95 ms | Errors |
|------|---------|-----------|--------|--------|
| keyword | 46 | 36 | 153 | 0 |
| semantic | 69 | 68 | 94 | 0 |
| hybrid | 97 | 88 | 205 | 0 |
- RAM: ~1.1-1.3 GiB per node (3 nodes)

### Solr 10 int8 (ScalarQuantizedDenseVectorField bits=7, 3-node SolrCloud)
| Mode | Mean ms | Median ms | p95 ms | Errors |
|------|---------|-----------|--------|--------|
| keyword | 111 | 91 | 244 | 0 |
| semantic | 2276 | 3094 | 3663 | 0 |
| hybrid | 2834 | 3474 | 3977 | 0 |
- RAM: ~1.1-1.3 GiB per node
- **NOTE:** Semantic/hybrid latency dominated by CPU-based int8 embedding computation (~3s per query). Actual Solr kNN time is comparable.

## Quantization Recall Analysis (int8 vs float32)
- **Keyword recall:** 0.96 (expected — keyword doesn't use vectors)
- **Semantic recall:** 0.47 ⚠️ (below 0.95 threshold)
- **Hybrid recall:** 0.72 ⚠️
- **Storage reduction:** estimated 4.57x for vector data
- **Verdict:** FAIL — int8 with bits=7 degrades semantic search quality significantly

## Key Findings
1. **Solr 10 vs 9.7 (float32):** ~10% faster on semantic/hybrid, comparable on keyword
2. **Int8 quantization:** Reduces storage but severely impacts semantic recall (0.47). Not production-ready without further tuning (e.g., re-ranking, training-aware quantization)
3. **Architecture difference:** Solr 9.7 ran single-node; Solr 10 ran 3-node SolrCloud — not an apples-to-apples comparison for RAM

## Artifacts
- benchmark-solr97-float32.json
- benchmark-solr10-float32.json
- benchmark-solr10-int8.json
- docker-stats-solr97-float32.json
- docker-stats-solr10-float32.json
- docker-stats-solr10-int8.json
- comparison-quantization.json
- comparison-solr-versions.json / .md
