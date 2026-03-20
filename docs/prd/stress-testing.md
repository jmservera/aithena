# PRD: Stress Testing Suite & Minimum Requirements Documentation

| Field        | Value                                      |
|--------------|--------------------------------------------|
| **Issue**    | [#590](https://github.com/jmservera/aithena/issues/590) |
| **Status**   | Draft                                      |
| **Milestone**| v1.9.0                                     |
| **Author**   | Parker (Backend Dev)                       |
| **Date**     | 2025-07-17                                 |

---

## 1. Goals

Aithena ships as a self-hosted Docker Compose deployment, but today we provide no
data-driven guidance on hardware sizing. Operators are left guessing how many CPU
cores, how much RAM, and how much disk they need.

This initiative has two deliverables:

1. **Stress testing suite** — automated tests that measure performance under
   realistic load so we can detect regressions and characterise bottlenecks.
2. **Minimum requirements documentation** — a hardware-sizing table in the admin
   manual, backed by measured data, covering small, medium, and large deployments.

### Success Criteria

- Indexing throughput (docs/minute) is measured at three dataset sizes.
- Search latency (p50/p95/p99) is measured for keyword, semantic, and hybrid modes
  across five index sizes.
- Concurrent-user behaviour is tested at 5, 10, and 25 simultaneous sessions.
- Resource usage (CPU, RAM, disk I/O) is recorded per service during every run.
- A minimum-requirements table is published in `docs/admin-manual.md`.
- Stress tests are runnable locally and optionally in CI (manual or nightly trigger).

---

## 2. Problem Statement

| Gap | Impact |
|-----|--------|
| No document-capacity guidance for given hardware | Operators over- or under-provision infrastructure |
| No search-latency baselines across index sizes | Performance regressions go undetected |
| Unknown bottleneck services under load | Scaling decisions are guesswork (Solr? Embeddings? Redis?) |
| No concurrent-user testing | Multi-user deployments risk unexpected failures |

---

## 3. Scope

### 3.1 In Scope

| Area | What to Test |
|------|-------------|
| **Indexing pipeline** | End-to-end throughput: file upload → document-lister → RabbitMQ → document-indexer → Solr |
| **Search latency** | Keyword (Solr), Semantic (embeddings), and Hybrid search at 1K–50K page index sizes |
| **Concurrent users** | Simultaneous search and upload sessions (5 / 10 / 25 users) |
| **Resource profiling** | CPU, memory, disk I/O, and network per Docker service during test runs |
| **UI workflows under load** | Playwright-based upload, search, admin, and pagination stress scenarios |
| **Documentation** | Minimum hardware requirements table and tuning guide in admin manual |

### 3.2 Out of Scope

- Benchmarking alternative embedding models (only the default model is tested).
- Multi-node Docker Swarm or Kubernetes deployments.
- Network partitioning or chaos-engineering scenarios.
- Automated performance regression gates in CI (future work).

---

## 4. Tools & Technology

| Purpose | Recommended Tool | Rationale |
|---------|-----------------|-----------|
| **API load testing** | [Locust](https://locust.io/) (Python) | Native Python fits our backend stack; scriptable scenarios; real-time web UI for monitoring runs; supports distributed mode for higher load generation |
| **Alternative** | [k6](https://k6.io/) (Go + JS) | Higher raw throughput; good CI integration; consider if Locust's Python overhead limits load generation |
| **Backend benchmarks** | pytest + custom fixtures | Consistent with existing test suite; outputs JSON/CSV for analysis |
| **UI stress tests** | Playwright | Already used for e2e tests; supports multiple browser contexts for concurrency simulation |
| **Resource monitoring** | `docker stats` + custom collector | Lightweight; no extra infrastructure; outputs time-series JSON |
| **Test data generation** | Custom Python script (seeded `Faker`) | Deterministic synthetic PDFs/EPUBs for reproducibility |
| **Results visualisation** | Matplotlib / Jupyter notebook | Quick charting of latency curves and resource usage; portable output as PNG for docs |

### Tool Decision: Locust vs k6

We recommend **Locust** as the primary tool because:

- All existing backend code and tests are Python — no context-switching.
- Locust scenarios are plain Python classes, making it easy to reuse our existing
  API client code and authentication helpers.
- The built-in web UI provides real-time dashboards during development.
- For CI, Locust supports headless mode with CSV/JSON output.

If load-generation throughput becomes a bottleneck (unlikely at our scale), k6 can
be introduced for specific high-concurrency scenarios.

---

## 5. Test Scenarios

### 5.1 Indexing Pipeline Stress Tests

**Location:** `tests/stress/test_indexing.py`

| Scenario | Documents | Est. Pages | Document Types |
|----------|-----------|-----------|----------------|
| Small batch | 50 | ~500 | PDF (text), EPUB |
| Medium batch | 500 | ~5,000 | PDF (text), PDF (OCR), EPUB |
| Large batch | 2,000+ | ~20,000 | PDF (text), PDF (OCR), EPUB |

**Metrics captured per scenario:**

| Metric | Collection Method |
|--------|------------------|
| Documents/minute throughput | Wall-clock time for full batch ingestion |
| Memory ceiling per service | Peak RSS from `docker stats` during run |
| CPU usage per service | Average and peak CPU % from `docker stats` |
| RabbitMQ queue depth over time | Management API polling (`/api/queues`) |
| Failure rate | Count of failed documents in Redis |
| Disk growth per 1K pages | Solr data directory size delta |

**Variables to explore:**
- RabbitMQ prefetch count (1, 5, 10)
- Number of document-indexer consumers (1, 2, 4)
- Embeddings batch size (default vs. 2×)

### 5.2 Search Latency Benchmarks

**Location:** `tests/stress/test_search_latency.py`

| Index Size (pages) | Keyword (Solr) | Semantic (Embeddings) | Hybrid |
|---------------------|----------------|----------------------|--------|
| 1,000 | p50 / p95 / p99 | p50 / p95 / p99 | p50 / p95 / p99 |
| 5,000 | p50 / p95 / p99 | p50 / p95 / p99 | p50 / p95 / p99 |
| 10,000 | p50 / p95 / p99 | p50 / p95 / p99 | p50 / p95 / p99 |
| 25,000 | p50 / p95 / p99 | p50 / p95 / p99 | p50 / p95 / p99 |
| 50,000 | p50 / p95 / p99 | p50 / p95 / p99 | p50 / p95 / p99 |

**Additional search measurements:**

- **Cold-start latency** — first query after full service restart (measures cache warm-up).
- **Concurrent searches** — 5, 10, and 25 simultaneous users issuing random queries.
- **Faceted search overhead** — latency delta when adding language, author, or year filters.
- **Embedding generation time** — isolated measurement of query-embedding computation.

**Query corpus:** 50 representative queries (mix of single-word, multi-word, phrase,
and natural-language questions) run 100 times each per index size to produce stable
percentiles.

### 5.3 Concurrent User Simulation

**Location:** `tests/stress/test_concurrent.py`

| Scenario | Users | Workload Mix |
|----------|-------|-------------|
| Light load | 5 | 80% search, 20% browse |
| Medium load | 10 | 60% search, 20% browse, 20% upload |
| Heavy load | 25 | 50% search, 25% upload, 25% admin |

**Metrics:**
- Request throughput (requests/second)
- Error rate (HTTP 5xx, timeouts)
- Latency distribution under load (p50/p95/p99)
- Service restart or OOM events

### 5.4 UI End-to-End Stress Tests (Playwright)

**Location:** `e2e/stress/`

| Test File | Scenario |
|-----------|----------|
| `upload-stress.spec.ts` | Upload 10 documents simultaneously; verify queue appearance |
| `search-stress.spec.ts` | Execute searches while indexing is running; verify results return |
| `admin-stress.spec.ts` | Monitor queue, requeue failed docs, clear processed — under load |
| `pagination-stress.spec.ts` | Search returning 1,000+ results; paginate through all pages |
| `concurrent-sessions.spec.ts` | Multiple browser contexts performing different operations |

---

## 6. Metrics to Capture

### 6.1 Performance Metrics

| Metric | Unit | Target (Medium Deployment) |
|--------|------|---------------------------|
| Indexing throughput | docs/min | ≥ 20 docs/min |
| Search latency p50 | ms | < 500 ms |
| Search latency p95 | ms | < 1,500 ms |
| Search latency p99 | ms | < 3,000 ms |
| Concurrent search throughput | req/s | ≥ 10 req/s at 10 users |
| Error rate under load | % | < 1% |
| Cold-start first-query latency | ms | < 5,000 ms |

### 6.2 Resource Metrics (Per Service)

| Metric | Collection Method |
|--------|------------------|
| CPU usage (avg / peak %) | `docker stats` sampled every 2s |
| Memory usage (avg / peak MB) | `docker stats` sampled every 2s |
| Memory limit hits / OOM kills | Docker events API |
| Disk I/O (read/write MB) | `docker stats` or `/proc` counters |
| Network I/O (rx/tx MB) | `docker stats` |
| Solr heap usage | Solr admin API (`/solr/admin/info/system`) |
| RabbitMQ queue depth | RabbitMQ management API |
| Redis memory usage | `INFO memory` command |

### 6.3 Output Format

All test results are written to `tests/stress/results/` (gitignored):

- **JSON** — machine-readable, one file per test run with full metrics.
- **CSV** — latency curves for easy import into spreadsheets or notebooks.
- **Summary report** — Markdown file generated per run with key findings.

---

## 7. Hardware Profiling & Minimum Requirements

### 7.1 Profiling Method

Each test scenario records per-service resource consumption. We aggregate across
three hardware profiles:

| Profile | CPU | RAM | Disk | Representative Hardware |
|---------|-----|-----|------|------------------------|
| Small (personal) | 4 cores | 8 GB | 20 GB SSD | Laptop, low-end NUC |
| Medium (team) | 8 cores | 16 GB | 50 GB SSD | Desktop workstation, small server |
| Large (org) | 16 cores | 32 GB | 200 GB SSD | Dedicated server, VM |

### 7.2 Minimum Requirements Table (Target Output)

This table will be populated with measured data and published in `docs/admin-manual.md`:

| Deployment Size | Documents | CPU | RAM | Disk | Expected Search Latency (p95) |
|-----------------|-----------|-----|-----|------|-------------------------------|
| Small (personal) | < 500 | 4 cores | 8 GB | 20 GB | < 500 ms |
| Medium (team) | < 5,000 | 8 cores | 16 GB | 50 GB | < 1 s |
| Large (org) | < 50,000 | 16 cores | 32 GB | 200 GB | < 2 s |

> **Note:** These are initial estimates from the issue. Actual values will be
> refined after stress test runs. The final table will include per-service memory
> breakdowns (Solr heap, embeddings model, Redis cache).

### 7.3 Per-Service Resource Breakdown

The profiling will also produce a per-service resource guide:

| Service | Min RAM | Recommended RAM | CPU-Bound? | Notes |
|---------|---------|----------------|------------|-------|
| solr (×3 nodes) | 512 MB each | 1–2 GB each | No (I/O) | Heap size = ~50% of container RAM |
| embeddings-server | 1 GB | 2–4 GB | Yes | Model loading dominates; batch size affects throughput |
| solr-search (API) | 256 MB | 512 MB | No | Lightweight FastAPI; Redis caching reduces load |
| document-indexer | 256 MB | 512 MB | Moderate | PDF parsing is CPU-intensive |
| document-lister | 128 MB | 256 MB | No | File listing is I/O-bound |
| redis | 128 MB | 256 MB–1 GB | No | Scales with cached embedding count |
| rabbitmq | 128 MB | 256 MB | No | Memory alarm at 40% of container RAM |
| nginx | 64 MB | 128 MB | No | Static proxy; minimal resource usage |

---

## 8. Implementation Phases

### Phase 1: Foundation & Test Data (Week 1)

**Owner:** Parker (Backend) + Brett (Infra)

- [ ] Set up `tests/stress/` directory structure with `conftest.py` shared fixtures.
- [ ] Create synthetic test-data generator (`tests/stress/generate_test_data.py`):
  - Seeded random for deterministic output.
  - Configurable document count, page count, and type (PDF text, PDF OCR, EPUB).
  - Uses `Faker` for realistic text content.
- [ ] Build Docker stats collector (`tests/stress/monitor.py`):
  - Polls `docker stats` every 2 seconds during test runs.
  - Outputs time-series JSON to `tests/stress/results/`.
- [ ] Add `tests/stress/results/` to `.gitignore`.
- [ ] Add stress-test dependencies to a dedicated `requirements-stress.txt`.

### Phase 2: Indexing Pipeline Benchmarks (Week 2)

**Owner:** Parker (Backend) + Brett (Infra)

- [ ] Implement `tests/stress/test_indexing.py`:
  - Parametrised pytest tests for small/medium/large batches.
  - Measure docs/minute, failure rate, queue depth.
  - Record per-service resource usage via monitor.
- [ ] Test with varying RabbitMQ prefetch and consumer counts.
- [ ] Document initial findings: bottleneck service, memory ceilings.

### Phase 3: Search Latency Benchmarks (Week 3)

**Owner:** Ash (Search) + Parker (Backend)

- [ ] Implement `tests/stress/test_search_latency.py`:
  - Pre-populate index at 1K/5K/10K/25K/50K pages.
  - Run query corpus (50 queries × 100 iterations) for each search mode.
  - Output p50/p95/p99 latency per (index-size, search-mode) pair.
- [ ] Implement cold-start latency measurement.
- [ ] Measure faceted search overhead.
- [ ] Measure embedding generation time in isolation.

### Phase 4: Concurrent User Testing (Week 4)

**Owner:** Parker (Backend)

- [ ] Implement `tests/stress/test_concurrent.py` with Locust:
  - User classes for search, browse, upload, and admin workflows.
  - Headless runs at 5/10/25 users with CSV output.
- [ ] Measure throughput, error rate, and latency under concurrent load.
- [ ] Identify breaking points and resource exhaustion thresholds.

### Phase 5: UI Stress Tests (Week 4–5)

**Owner:** Dallas (Frontend) + Lambert (Tester)

- [ ] Implement Playwright stress tests in `e2e/stress/`.
- [ ] Test upload, search, admin, pagination, and concurrent browser sessions.
- [ ] Validate UI responsiveness during backend load.

### Phase 6: Analysis & Documentation (Week 5–6)

**Owner:** Lambert (Tester) + Brett (Infra)

- [ ] Aggregate results across all test runs.
- [ ] Produce latency-curve charts (Matplotlib/Jupyter).
- [ ] Finalise minimum requirements table with measured data.
- [ ] Update `docs/admin-manual.md` with:
  - Minimum hardware requirements table.
  - Per-service resource breakdown.
  - Bottleneck analysis and scaling recommendations.
  - Tuning guide (Solr heap, embeddings batch size, RabbitMQ prefetch).
- [ ] Write summary report for release notes.

---

## 9. Proposed File Structure

```
tests/
  stress/
    conftest.py               # Shared fixtures (Docker Compose lifecycle, test data)
    generate_test_data.py     # Synthetic PDF/EPUB generator
    monitor.py                # Docker stats collector (time-series JSON)
    test_indexing.py           # Indexing pipeline benchmarks
    test_search_latency.py    # Search latency curves
    test_concurrent.py         # Concurrent user simulation (Locust-based)
    locustfile.py             # Locust user definitions
    requirements-stress.txt   # Stress test dependencies
    results/                  # Output directory (gitignored)
      .gitkeep

e2e/
  stress/
    upload-stress.spec.ts     # Playwright upload stress tests
    search-stress.spec.ts     # Playwright search under load
    admin-stress.spec.ts      # Playwright admin workflows
    pagination-stress.spec.ts # Playwright pagination stress
    concurrent-sessions.spec.ts # Multi-browser-context tests
```

---

## 10. Open Questions

These questions should be resolved during Phase 1 before full implementation:

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | **Test data source** | Synthetic (Faker) vs. public domain (Project Gutenberg) | Start with synthetic for reproducibility; add a Gutenberg-based variant later for realism |
| 2 | **CI integration** | Every PR / nightly / manual only | Manual trigger initially; add nightly schedule after stabilisation |
| 3 | **Baseline hardware** | Current VM (8 CPU, 32 GB) as "medium" | Yes — profile on current VM, extrapolate small/large from resource scaling curves |
| 4 | **Embeddings model variants** | Default only vs. multiple models | Default model only for v1.9.0; model comparison is a separate future initiative |
| 5 | **SolrCloud topology** | 1-node vs. 3-node benchmarks | Benchmark both; document the scaling benefit in the tuning guide |

---

## 11. Dependencies & Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Stress tests are too slow for regular CI | High | Medium | Run manually or on nightly schedule; keep fast smoke variants |
| Synthetic test data doesn't represent real workloads | Medium | Medium | Validate against a small real-world corpus; adjust generator parameters |
| Hardware profiling varies across machines | High | Low | Document the exact hardware profile used; provide scaling formulas |
| Embeddings server OOM on large batches | Medium | High | Implement batch-size limits; document memory requirements clearly |
| Results vary between Docker Desktop and Linux Docker | Medium | Low | Standardise on Linux Docker for official benchmarks; note caveats for Docker Desktop |

---

## 12. Acceptance Criteria

- [ ] `tests/stress/` contains working pytest-based indexing and search benchmarks.
- [ ] `e2e/stress/` contains working Playwright stress tests.
- [ ] All stress tests produce JSON/CSV output in `tests/stress/results/`.
- [ ] `docs/admin-manual.md` includes a data-backed minimum requirements table.
- [ ] `docs/admin-manual.md` includes a tuning guide with actionable recommendations.
- [ ] A performance summary report is available for the v1.9.0 release notes.
- [ ] Stress tests can be run locally with a single command (documented in README or contributing guide).
