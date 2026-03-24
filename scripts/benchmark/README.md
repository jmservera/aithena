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

## Running Tests

```bash
cd scripts/benchmark && python -m pytest tests/ -v
```
