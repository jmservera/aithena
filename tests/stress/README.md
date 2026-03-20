# Aithena Stress Tests

Automated stress tests for measuring performance, resource usage, and hardware
sizing of the Aithena Docker Compose deployment.

## Prerequisites

- Python 3.12+
- Docker and Docker Compose (the stack must be running)
- The Aithena stack started via `docker compose up -d`

## Setup

Install stress test dependencies:

```bash
pip install -r tests/stress/requirements-stress.txt
```

## Running Tests

### Run all stress tests

```bash
cd tests/stress
pytest -v
```

### Run a specific test category

```bash
# Indexing pipeline benchmarks
pytest -v -m indexing

# Search latency benchmarks
pytest -v -m search

# Concurrent user simulation
pytest -v -m concurrent
```

### Run Locust load tests

#### Interactive mode (web UI)

```bash
cd tests/stress
locust -f locustfile.py --host http://localhost:8080
# Open http://localhost:8089 in your browser
```

#### Headless mode (CI)

```bash
# Light scenario — 5 users, 80% search / 20% browse
LOCUST_SCENARIO=light locust -f tests/stress/locustfile.py --headless \
    -u 5 -r 1 --run-time 60s \
    --csv tests/stress/results/light \
    --host http://localhost:8080

# Medium scenario — 10 users, mixed workload
locust -f tests/stress/locustfile.py --headless \
    -u 10 -r 2 --run-time 120s \
    --csv tests/stress/results/medium \
    --host http://localhost:8080

# Heavy scenario — 25 users, uploads + admin
locust -f tests/stress/locustfile.py --headless \
    -u 25 -r 5 --run-time 180s \
    --csv tests/stress/results/heavy \
    --host http://localhost:8080
```

#### Via pytest (all three scenarios automatically)

```bash
cd tests/stress
pytest -v -m concurrent
```

#### Smoke tests (no stack required)

```bash
cd tests/stress
python3 -m pytest test_locust_smoke.py -x -q --timeout=30
```

#### Output

Headless runs produce CSV files (Locust default) and a `locust_summary.json`
with aggregated throughput, error rate, and latency percentiles (p50/p95/p99).

### Run with resource monitoring

The `docker_monitor` fixture automatically captures Docker resource metrics
during tests. Results are written to `tests/stress/results/<timestamp>/`.

### Run the resource monitor standalone

Monitor Docker resource usage without running tests:

```bash
python -m tests.stress.monitor --interval 2 --label my_session
# Press Ctrl+C to stop and write results
```

Or from the repo root:

```bash
python tests/stress/monitor.py --interval 2 --output-dir tests/stress/results --label manual_run
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPOSE_FILE` | `docker-compose.yml` | Path to Docker Compose file |
| `COMPOSE_PROJECT` | `aithena` | Docker Compose project name |
| `SOLR_URL` | `http://localhost:8983/solr/books` | Solr collection URL |
| `SEARCH_API_URL` | `http://localhost:8080` | solr-search API URL |
| `RABBITMQ_API_URL` | `http://localhost:15672` | RabbitMQ management URL |
| `RABBITMQ_USER` | `guest` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `guest` | RabbitMQ password |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | *(empty)* | Redis password |
| `STRESS_RESULTS_DIR` | `tests/stress/results` | Results output directory |
| `MONITOR_INTERVAL` | `2` | Docker stats sampling interval (seconds) |

## Directory Structure

```
tests/stress/
├── conftest.py               # Shared fixtures (Docker Compose lifecycle, URLs, helpers)
├── generate_test_data.py     # Synthetic PDF/EPUB generator
├── locustfile.py             # Locust user classes & task definitions
├── monitor.py                # Docker resource monitoring collector
├── pytest.ini                # pytest configuration for stress tests
├── requirements-stress.txt   # Python dependencies
├── README.md                 # This file
├── test_concurrent.py        # Pytest wrapper for headless Locust scenarios
├── test_generate_test_data.py # Tests for the data generator
├── test_indexing.py          # Indexing pipeline benchmarks
├── test_locust_smoke.py      # Unit tests for Locust helpers (no stack needed)
└── results/                  # Output directory (gitignored)
    └── .gitkeep
```

## Synthetic Test Data Generator

Generate deterministic PDF and EPUB files for stress testing:

```bash
# Generate 50 PDFs with default seed
python generate_test_data.py --count 50 --type pdf

# Generate EPUBs with a specific seed
python generate_test_data.py --count 100 --type epub --seed 99

# Use batch presets (small=50, medium=500, large=2000 docs)
python generate_test_data.py --batch medium --type pdf

# Custom output directory
python generate_test_data.py --count 10 --type pdf --output /tmp/test_data
```

Output is written to `tests/stress/test_data/` by default (gitignored).

## Results Output

Each test run creates a timestamped subdirectory under `results/`:

```
results/
└── 20250120T143022Z/
    ├── indexing_small.json           # Test results
    ├── indexing_small_timeseries_*.json  # Docker resource time-series
    └── indexing_small_summary_*.json     # Aggregated resource summary
```

### Time-series JSON format

```json
{
  "label": "indexing_small",
  "start_time": "2025-01-20T14:30:22Z",
  "end_time": "2025-01-20T14:35:22Z",
  "duration_seconds": 300.0,
  "interval_seconds": 2.0,
  "samples": [
    {
      "timestamp": "2025-01-20T14:30:24Z",
      "service": "solr",
      "cpu_percent": 45.2,
      "memory_mb": 1024.5,
      "memory_limit_mb": 2048.0,
      "memory_percent": 50.0,
      "net_rx_bytes": 123456,
      "net_tx_bytes": 654321,
      "block_read_bytes": 1048576,
      "block_write_bytes": 2097152
    }
  ],
  "service_metrics": [
    {
      "timestamp": "2025-01-20T14:30:24Z",
      "source": "solr_heap",
      "metrics": {"heap_used_mb": 512.3, "heap_max_mb": 1024.0}
    }
  ],
  "oom_events": []
}
```

## Playwright Stress Tests

Browser-based stress tests live in `e2e/stress/` and are run separately
via Playwright. See the main `e2e/` directory for setup instructions.
