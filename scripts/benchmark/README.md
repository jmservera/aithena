# Benchmark & Verification Tools

Tools for measuring search quality and verifying collection health for the books collection (e5-base 768D).

## Test Corpus Indexing

Index documents through the e5-base embedding pipeline into the `books` collection.

```bash
# Index all documents in the configured BASE_PATH
python scripts/index_test_corpus.py

# Limit to first 10 documents (useful for testing)
python scripts/index_test_corpus.py --limit 10

# Custom document directory
python scripts/index_test_corpus.py --base-path /path/to/documents

# Preview without publishing
python scripts/index_test_corpus.py --dry-run

# Check current indexing status only
python scripts/index_test_corpus.py --status-only
```

**How it works:** The script publishes document file paths to the `documents` exchange in RabbitMQ. The `document-indexer` (e5-base) consumes from this exchange and indexes each document into the `books` collection.

**Requirements:** `pika` (for RabbitMQ) and `requests` (for status checks). Both are available in the document-lister/indexer containers.

**Idempotent:** Safe to re-run — document-indexer handles deduplication via Solr's unique key.

## Collection Verification

Verify that the books collection has correctly indexed documents with e5-base embeddings.

```bash
# Run all verification checks
python scripts/verify_collections.py

# JSON output (for CI/scripts)
python scripts/verify_collections.py --json

# Verbose output (all details)
python scripts/verify_collections.py --verbose

# Custom Solr URL
python scripts/verify_collections.py --solr-url http://solr:8983
```

**Checks performed:**
1. The `books` collection is accessible and contains documents
2. Parent and chunk documents are present
3. Embedding dimensionality is 768D (e5-base)

Exit code: `0` if all checks pass, `1` otherwise.

## Benchmark Runner

Measure search quality across keyword, semantic, and hybrid modes.

```bash
# Run against a live instance
python scripts/benchmark/run_benchmark.py --base-url http://localhost:8080

# Run specific modes only
python scripts/benchmark/run_benchmark.py --modes semantic hybrid

# Save JSON report
python scripts/benchmark/run_benchmark.py -o results/benchmark.json

# Custom collection
python scripts/benchmark/run_benchmark.py --collection books
```

## End-to-End Workflow

```bash
# 1. Start all services
docker compose up -d

# 2. Index the test corpus
python scripts/index_test_corpus.py

# 3. Wait for indexing to complete, then verify
python scripts/verify_collections.py

# 4. Run the benchmark
python scripts/benchmark/run_benchmark.py -o results/benchmark.json
```

## Query Suite (`queries.json`)

30 queries organized by category:

| Category | Count | Purpose |
|----------|-------|---------|
| `simple_keyword` | 5 | Basic catalog keyword searches |
| `natural_language` | 6 | Questions benefiting from semantic understanding |
| `multilingual` | 6 | Spanish, Catalan, French queries |
| `long_complex` | 4 | Long queries testing 512-token context window |
| `edge_cases` | 9 | Short queries, special chars, empty results |

Each query is tested across **3 modes:** keyword, semantic, hybrid.

Total: 30 queries × 3 modes = 90 query executions per run.

## Metrics

Per query:
- **Top-10 document IDs and scores**
- **Response latency** (ms)

Aggregate (per mode and category):
- Mean/median/p95 latency
- Mean result count
- Error count

## Output

- **Console:** Human-readable summary with per-mode stats and errors
- **JSON** (`--output`): Full result data for further analysis


## Scalar Quantization Validation (#1344)

Use this workflow now that PR #1670 (Solr 10 `bits=7` compatibility) has merged, once the same representative corpus can be indexed twice in a controlled environment. It avoids fabricating performance claims by reusing the existing 30-query suite and comparing top-k agreement between a float32 reference collection and an int8/scalar-quantized candidate collection.

### Validation checklist

1. Confirm the runtime contains the #1670 schema fix (`ScalarQuantizedDenseVectorField bits="7"` on Solr 10; Solr 9 compatibility still rewrites to `DenseVectorField vectorEncoding="BYTE"`).
2. Index the same representative corpus with `VECTOR_QUANTIZATION=none` and save a float32 benchmark report.
3. Re-index the same corpus with `VECTOR_QUANTIZATION=int8` and save a candidate benchmark report.
4. Compare reports with `compare_quantization.py`; treat recall@10 below `0.95` for any semantic/hybrid query as a release blocker until reviewed.
5. Capture memory from `docker stats --no-stream solr solr2 solr3` (or the existing `e2e/benchmark.sh` report when a small generated corpus is acceptable) for float32 and int8 runs.
6. Attach the JSON reports, comparison output, Solr memory samples, corpus size, and any failed query IDs to #1344.

### Commands

```bash
# Float32 reference run
VECTOR_QUANTIZATION=none docker compose up -d --build
python3 scripts/index_test_corpus.py --status-only
python3 scripts/verify_collections.py --verbose
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-float32.json

docker stats --no-stream solr solr2 solr3

# Int8/scalar-quantized candidate run after re-indexing the same corpus
VECTOR_QUANTIZATION=int8 docker compose up -d --build
python3 scripts/index_test_corpus.py --status-only
python3 scripts/verify_collections.py --verbose
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-int8.json

docker stats --no-stream solr solr2 solr3

# Offline recall/latency comparison (safe to run without Docker)
python3 scripts/benchmark/compare_quantization.py \
  --baseline results/benchmark-1344-float32.json \
  --candidate results/benchmark-1344-int8.json \
  --top-k 10 \
  --min-recall 0.95 \
  --output results/benchmark-1344-quantization-comparison.json
```

**Remaining blocker:** do not publish pass/fail performance or memory claims until the float32 and int8 runs have been executed on the same host, with the same corpus, and with captured benchmark JSON plus `docker stats` evidence.

## Running Tests

```bash
cd scripts/benchmark && python -m pytest tests/ -v
```
