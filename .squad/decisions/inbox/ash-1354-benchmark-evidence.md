# Decision: Gate Solr 9.7 vs Solr 10 performance claims on paired evidence

Author: Ash  
Date: 2026-06-06
Status: Proposed  
Related: #1354, #1711

## Context

Issue #1354 asks for Solr 9.7 vs Solr 10 performance benchmark conclusions,
including validating 4× memory and 40× indexing improvements. Unpaired runs can
produce misleading claims because host capacity, corpus size, Docker topology,
and failed query sets materially affect the result.

## Decision

Do not publish Solr 9.7 vs Solr 10 performance claims unless both reports come
from the same host and the same corpus, with benchmark JSON, Docker stats,
corpus ID/document count/byte count, startup/index timing, and failed query IDs.

## Consequences

- `scripts/benchmark/compare_solr_versions.py` marks evidence invalid when host
  or corpus metadata is missing/mismatched.
- Production recommendations should be "rerun benchmark" until the evidence gate
  passes.
- The same evidence rule should apply to future Solr runtime and quantization
  benchmark reports.
