# Benchmark & Verification Tools

Tools for A/B testing search quality across Solr collections (distiluse 512D vs e5-base 768D).

## Test Corpus Indexing

Index documents through both embedding pipelines (distiluse → `books`, e5-base → `books_e5base`).

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

**How it works:** The script publishes document file paths to the `documents` fanout exchange in RabbitMQ. Both `document-indexer` (distiluse) and `document-indexer-e5` (e5-base) consume from this exchange, so every document is indexed into both collections.

**Requirements:** `pika` (for RabbitMQ) and `requests` (for status checks). Both are available in the document-lister/indexer containers.

**Idempotent:** Safe to re-run — document-indexer handles deduplication via Solr's unique key.

## Collection Verification

Verify that both collections have matching documents with correct embeddings.

```bash
# Run all verification checks
python scripts/verify_collections.py

# JSON output (for CI/scripts)
python scripts/verify_collections.py --json

# Verbose output (all discrepant IDs)
python scripts/verify_collections.py --verbose

# Custom Solr URL
python scripts/verify_collections.py --solr-url http://solr:8983
```

**Checks performed:**
1. Parent document counts match between `books` and `books_e5base`
2. Parent document IDs are identical in both collections
3. Embedding dimensionality is 512D in `books` and 768D in `books_e5base`

Exit code: `0` if all checks pass, `1` otherwise.

## Benchmark Runner

Compare search quality across collections.

```bash
# Run against a live instance
python scripts/benchmark/run_benchmark.py --base-url http://localhost:8080

# Run specific modes only
python scripts/benchmark/run_benchmark.py --modes semantic hybrid

# Save JSON report
python scripts/benchmark/run_benchmark.py -o results/benchmark.json
```

## End-to-End Workflow

The typical A/B test workflow:

```bash
# 1. Start all services (both indexers, both embeddings servers)
docker compose up -d

# 2. Index the test corpus through both pipelines
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

Each query is tested across:
- **3 modes:** keyword, semantic, hybrid
- **2 collections:** `books` (distiluse 512D), `books_e5base` (e5-base 768D)

Total: 30 queries × 3 modes = 90 comparison pairs per run.

## Metrics

Per query pair:
- **Top-10 document IDs and scores** from each collection
- **Response latency** (ms)
- **Jaccard similarity** of top-10 result sets (overlap metric)

Aggregate (per mode and category):
- Mean/median/min/max Jaccard similarity
- Mean and p95 latency for baseline vs candidate
- Low-overlap queries flagged for human review

## Output

- **Console:** Human-readable summary with per-mode stats and flagged queries
- **JSON** (`--output`): Full comparison data for further analysis

## Running Tests

```bash
cd scripts/benchmark && python -m pytest tests/ -v
```
