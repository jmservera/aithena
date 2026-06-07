# Solr 9.7 vs Solr 10 Benchmark Evidence Runbook

Date: 2026-06-06

## Status

No same-host, same-corpus Solr 9.7 vs Solr 10 benchmark evidence has been
captured in this repository yet. Do not publish the 4× memory or 40× indexing
claims until paired reports, Docker stats, corpus size, and failed query IDs are
attached.

## Required Matrix

| Area | Evidence source | Required comparison |
|---|---|---|
| Vector indexing speed | `run_metadata.timings.index_build_seconds` or `vector_indexing_seconds` | Solr 9.7 seconds ÷ Solr 10 seconds |
| kNN latency | `semantic` mode p95 latency | Solr 10 p95 must not regress beyond threshold |
| Keyword latency | `keyword` mode p95 latency | Solr 10 p95 must not regress beyond threshold |
| Hybrid latency | `hybrid` mode p95 latency | Solr 10 p95 must not regress beyond threshold |
| Memory with/without quantization | `run_metadata.docker_stats.*.mem_usage_bytes` | Float32 and quantized paired runs |
| Index build time | `run_metadata.timings.index_build_seconds` | Same corpus, fresh index |
| Concurrent throughput | `run_metadata.throughput.qps` from an external load run | Same query mix and concurrency |
| Startup time | `run_metadata.timings.startup_seconds` | Same compose topology |

## Paired Run Commands

Run both versions on the same host with the same corpus. Replace corpus values
with measured values from the local book library.

```bash
docker compose -f docker-compose.yml -f docker/compose.solr9.yml up -d --build
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --solr-version 9.7 \
  --vector-quantization-mode none \
  --run-label solr9-float32 \
  --corpus-id booklibrary-2026-06-06 \
  --corpus-documents <document-count> \
  --corpus-bytes <corpus-bytes> \
  --startup-seconds <startup-seconds> \
  --index-build-seconds <index-build-seconds> \
  --vector-indexing-seconds <vector-indexing-seconds> \
  --concurrency <concurrent-clients> \
  --throughput-qps <qps> \
  --docker-stats-json results/solr9-docker-stats.json \
  --output results/benchmark-solr9.json

docker compose down
docker compose -f docker-compose.yml -f docker/compose.solr10.yml up -d --build
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --solr-version 10 \
  --vector-quantization-mode none \
  --run-label solr10-float32 \
  --corpus-id booklibrary-2026-06-06 \
  --corpus-documents <document-count> \
  --corpus-bytes <corpus-bytes> \
  --startup-seconds <startup-seconds> \
  --index-build-seconds <index-build-seconds> \
  --vector-indexing-seconds <vector-indexing-seconds> \
  --concurrency <concurrent-clients> \
  --throughput-qps <qps> \
  --docker-stats-json results/solr10-docker-stats.json \
  --output results/benchmark-solr10.json

python3 scripts/benchmark/compare_solr_versions.py \
  --solr9 results/benchmark-solr9.json \
  --solr10 results/benchmark-solr10.json \
  --output-json results/benchmark-solr9-vs-solr10-comparison.json \
  --output-md results/benchmark-solr9-vs-solr10-report.md
```

## Recommendation Rule

- If the evidence gate fails, rerun the benchmark; no production recommendation
  may be made from mismatched host/corpus data, wrong Solr versions, or mixed
  vector quantization modes.
- If any Solr 10 p95 latency mode regresses by more than 20% or has additional
  failed query IDs, hold rollout pending triage.
- If evidence is valid and no regressions are reported, proceed to staged
  production validation with the generated markdown report attached to #1354.
