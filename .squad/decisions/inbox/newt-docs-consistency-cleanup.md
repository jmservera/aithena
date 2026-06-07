# Decision: Docs Must Describe Shipped v2.5 Behavior

Author: Newt (Product Manager)
Date: 2026-06-07
Status: Proposed
Related: #1452, #1344, v2.5.0 docs audit

## Context

The pending-work audit found several v2.5 documents describing planned or issue-title behavior that diverged from the shipped code and migration runbooks. Conflicts included ZooKeeper-free standalone mode, `blockUnknown=true`, non-runtime HNSW parameter names, and overconfident quantization claims.

## Decision

When release documentation conflicts, operator-facing docs must be reconciled to the shipped code/runtime and current migration runbooks. Future planned hardening or optimization should be named as follow-up work, not documented as already shipped behavior.

## Current v2.5 Source of Truth

- Lightweight Solr deployments use single-node SolrCloud (`docker/compose.single-node.yml`), not true ZooKeeper-free standalone/core mode.
- Aithena v2.5 explicitly keeps `blockUnknown=false`; moving to `true` requires a dedicated hardening change.
- Solr 10 HNSW names are `hnswM` and `hnswEfConstruction`; Solr 9 compatibility rewrites them during rollback/support windows.
- int8 quantization remains evidence-gated for production and should point to #1344-style benchmark evidence.
