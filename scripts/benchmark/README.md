# Benchmark Query Suite

Tools for A/B testing search quality across Solr collections (distiluse 512D vs e5-base 768D).

## Quick Start

```bash
# Run against a live instance
python scripts/benchmark/run_benchmark.py --base-url http://localhost:8080

# Run specific modes only
python scripts/benchmark/run_benchmark.py --modes semantic hybrid

# Save JSON report
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
