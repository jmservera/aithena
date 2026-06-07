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
- **2026-06-06:** For #1344 scalar quantization closure, validate against `dev` when #1670 is only merged there; schema/preflight/unit checks can prove bits=7 wiring, but recall@10 and memory savings still require same-corpus float32 vs int8 runtime benchmark artifacts.
- **2026-06-07:** For #1717 preflight, quantization acceptance is per semantic/hybrid query-mode recall@10 ≥0.95 from `compare_quantization.py`, or explicit exception review; measured same-host Docker stats are required and payload estimates are not release evidence.

## Research Loop Participation (2026-06-06)

- **#1354 Scalar Quantization Benchmark Execution Plan:** Authored 3-phase benchmark workflow (Phase 1: float32 baseline, Phase 2: int8 candidate, Phase 3: offline comparison). Defined corpus requirements (~1K–2K docs, ~5–10 MB), pass/fail criteria (recall@10 ≥0.95, memory 4×, latency ±5–10%), and deliverables.
- **#1344 int8 Evaluation Protocol:** Authored comprehensive evaluation protocol specifying comparison tool reference, JSON schema, closure checklist, and blocker resolution path. Benchmark is blocked on PR #1670 (Solr 10 schema fix).
- **Solver 10 readiness:** Both #1344 and #1354 recipes are executable post-PR-#1670 merge with no further code changes; validates recall/memory/latency from research loop prioritization.
