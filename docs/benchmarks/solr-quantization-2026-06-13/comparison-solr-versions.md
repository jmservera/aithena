# Solr 9.7 vs Solr 10 Benchmark Comparison

Generated from paired benchmark JSON reports. Claims are evidence-gated and require same-host, same-corpus metadata.

## Evidence Gate

- Valid paired evidence: **no**
- Gate failures: missing_corpus_metadata, solr9_version_mismatch, missing_vector_quantization_mode
- Solr versions: None vs 10.0
- Vector quantization modes: None vs none

## Query Latency by Mode

| Mode | Solr 9 queries/errors | Solr 10 queries/errors | Solr 9 mean ms | Solr 10 mean ms | Solr 9 p95 ms | Solr 10 p95 ms | p95 delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| hybrid | 30/0 | 30/0 | 101.0563 | 96.6083 | 221.0100 | 204.9200 | -7.28% |
| keyword | 30/0 | 30/0 | 51.0423 | 46.3350 | 120.6100 | 152.7500 | 26.65% |
| semantic | 30/0 | 30/0 | 70.5693 | 69.0353 | 101.1800 | 94.1000 | -7.00% |

## Resource and Build Metrics

| Metric | Solr 9.7 | Solr 10 | Factor (>1 means Solr 10 improved) |
|---|---:|---:|---:|
| Memory bytes | N/A | N/A | N/A |
| Startup seconds | N/A | N/A | N/A |
| Index build seconds | N/A | N/A | N/A |
| Vector indexing seconds | N/A | N/A | N/A |
| Concurrent throughput qps | N/A | N/A | N/A |
| Throughput concurrency | N/A | N/A | N/A |
| Vector quantization mode | N/A | none | N/A |

## Claimed Improvements

| Claim | Target | Observed factor | Status |
|---|---:|---:|---|
| memory_4x | 4.0x | N/A | insufficient_evidence |
| indexing_40x | 40.0x | N/A | insufficient_evidence |

## Regressions

- `latency_p95` in `keyword`: {'type': 'latency_p95', 'mode': 'keyword', 'delta_pct': 26.6479, 'threshold_pct': 20.0}

## Failed Query IDs

- solr9: (none)
- solr10: (none)

## Production Recommendation

Do not publish performance claims or make deployment decisions yet. Re-run Solr 9.7 and Solr 10 on the same host with the same corpus and matching vector quantization mode; attach benchmark JSON, docker stats, corpus size, Solr versions, quantization mode, and failed query IDs.
