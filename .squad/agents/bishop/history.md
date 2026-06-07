# Bishop — History

## Project Context
- **Project:** aithena — Book library search engine with Solr full-text indexing, multilingual embeddings, PDF processing, and React UI
- **User:** jmservera
- **Stack:** Python (backend services), TypeScript/React + Vite (UI), Docker Compose, Apache Solr (search), multilingual embeddings
- **Key services:** embeddings-server (sentence-transformers), solr-search (FastAPI), document-indexer, document-lister
- **Search modes:** keyword (BM25), semantic (kNN vector), hybrid (BM25 + vector rerank), hybrid-rerank (configurable)
- **Quantization:** Configurable — none (fp32), fp16, int8
- **Vector field:** embedding_v (chunk-level), configured via KNN_FIELD env var

## Learnings
- Semantic E2E coverage should index parent PDFs via Solr `/update/extract`, then enqueue the same file paths to `shortembeddings` so document-indexer produces chunk docs with vectors before asserting `/v1/search` semantic and hybrid ranking.
- 2026-06-06: Solr 10 scalar quantization must use `bits="7"` (or `4`) rather than `8`; Aithena's int8 path keeps `vectorDimension="768"` and `similarityFunction="cosine"`, with Solr 9 rollback rewriting to `DenseVectorField vectorEncoding="BYTE"`.
- 2026-06-06: Quantization evaluation lives in `scripts/benchmark/`: run paired float32/int8 reports with `run_benchmark.py`, compare recall@10 with `compare_quantization.py`, and attach measured `docker stats` memory samples before claiming runtime savings.
- 2026-06-07: #1344 is not closeable from unpaired readiness data. A local Solr 9.7/`VECTOR_QUANTIZATION=none` run can validate benchmark auth and corpus availability, but closure still requires same-host Solr 10 float32 vs `int8` (`bits=7`) reports, `compare_quantization.py`, and measured Solr memory samples from the same corpus.
