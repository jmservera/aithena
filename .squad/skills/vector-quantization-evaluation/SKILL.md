---
name: "vector-quantization-evaluation"
description: "Evaluate Aithena float32 vs int8/Solr scalar-quantized vector search with recall@10 and memory evidence"
domain: "search, embeddings, quantization, benchmarking"
confidence: "high"
source: "earned — issue #1344 scalar quantization validation"
author: "Bishop"
created: "2026-06-06"
last_validated: "2026-06-06"
---

## Context

Apply this skill when validating `VECTOR_QUANTIZATION=int8` or any change to Solr vector storage. The safe release question is whether scalar-quantized results preserve semantic/hybrid top-10 retrieval while reducing vector memory.

## Procedure

1. Confirm schema/config:
   - Solr 10: `ScalarQuantizedDenseVectorField` with `vectorDimension="768"`, `similarityFunction="cosine"`, and `bits="7"`.
   - Solr 9 rollback: `DenseVectorField vectorEncoding="BYTE"`.
   - Runtime selector: `VECTOR_QUANTIZATION=none|fp16|int8`; `int8` routes to `embedding_byte_v`.
2. Index the same representative corpus twice:
   - Float32 reference: `VECTOR_QUANTIZATION=none`.
   - Int8 candidate: `VECTOR_QUANTIZATION=int8`.
   - Treat this as a full reindex migration from `embedding_v` to `embedding_byte_v`; do not mutate an existing vector field in place.
3. Run the benchmark suite in semantic and hybrid modes:
   ```bash
   python3 scripts/benchmark/run_benchmark.py \
     --base-url http://localhost:8080 \
     --modes semantic hybrid \
     --output results/benchmark-1344-float32.json

   python3 scripts/benchmark/run_benchmark.py \
     --base-url http://localhost:8080 \
     --modes semantic hybrid \
     --output results/benchmark-1344-int8.json
   ```
4. Compare top-10 agreement:
   ```bash
   python3 scripts/benchmark/compare_quantization.py \
     --baseline results/benchmark-1344-float32.json \
     --candidate results/benchmark-1344-int8.json \
     --top-k 10 \
     --min-recall 0.95 \
     --output results/benchmark-1344-quantization-comparison.json
   ```
5. Capture memory evidence from the same corpus size:
   ```bash
   docker stats --no-stream solr solr2 solr3
   ```

## Interpretation

- Any semantic/hybrid query below recall@10 `0.95` needs review before enabling int8 broadly.
- The comparison script estimates raw vector payload savings, but release notes must use measured Solr memory samples before claiming actual runtime savings.
- For 1M 768D vectors, raw payload reference points are 3,072,000,000 bytes for float32, about 672,000,000 bytes for Solr 10 bits=7 scalar payload, and 768,000,000 bytes for Solr 9 BYTE compatibility.

## Anti-Patterns

- Do not compare float32 and int8 runs indexed from different corpora.
- Do not claim measured memory or recall unless the JSON reports and `docker stats` samples were captured.
- Do not use Solr 10 `bits="8"`; supported scalar bits are `4` and `7`.
