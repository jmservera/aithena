# Decision: Disable SolrCloud Overseer in production Solr 10 deployments

**Date:** 2026-06-06T16:09:02.162+00:00
**Owner:** Brett
**Related issue:** #1343

## Decision

`docker/compose.prod.yml` starts all three production Solr nodes with
`-Dsolr.cloud.overseer.enabled=false` by default. The production topology still
uses three SolrCloud nodes and a three-node ZooKeeper ensemble for HA.

## Rationale

Solr 10 supports distributed cluster-state updates without the legacy Overseer
queue. Disabling Overseer removes a collection-management bottleneck and avoids
coupling cluster operations to one busy or restarting Overseer leader, while
retaining the existing ZooKeeper-backed HA topology.

## Guardrails

- Dev/default/single-node topology is unchanged.
- Operators can temporarily set `SOLR_CLOUD_OVERSEER_ENABLED=true` for rollback.
- Runtime validation is documented in
  `tests/solrcloud-overseer-disabled-validation.sh`; failover is opt-in with
  `RUN_FAILOVER=1` because it intentionally stops a Solr node.

---

# Decision: Docs Must Describe Shipped v2.5 Behavior

**Author:** Newt (Product Manager)  
**Date:** 2026-06-07  
**Status:** Proposed  
**Related:** #1452, #1344, v2.5.0 docs audit

## Context

The pending-work audit found several v2.5 documents describing planned or issue-title behavior that diverged from the shipped code and migration runbooks. Conflicts included ZooKeeper-free standalone mode, `blockUnknown=true`, non-runtime HNSW parameter names, and overconfident quantization claims.

## Decision

When release documentation conflicts, operator-facing docs must be reconciled to the shipped code/runtime and current migration runbooks. Future planned hardening or optimization should be named as follow-up work, not documented as already shipped behavior.

## Current v2.5 Source of Truth

- Lightweight Solr deployments use single-node SolrCloud (`docker/compose.single-node.yml`), not true ZooKeeper-free standalone/core mode.
- Aithena v2.5 explicitly keeps `blockUnknown=false`; moving to `true` requires a dedicated hardening change.
- Solr 10 HNSW names are `hnswM` and `hnswEfConstruction`; Solr 9 compatibility rewrites them during rollback/support windows.
- int8 quantization remains evidence-gated for production and should point to #1344-style benchmark evidence.

---

# Decision: Canonical environment template

**Author:** Parker  
**Date:** 2026-06-07  
**Status:** Proposed  
**Related:** #1452, #1716

## Decision

`.env.example` is the canonical environment template for development, production, and offline deployment. The separate `.env.prod.example` template is removed; release packaging and docs should copy/reference `.env.example` and override values in the generated `.env`/`.env.prod` as needed.

## Rationale

Maintaining separate templates let production-only variables and compose defaults drift. A single template keeps variable coverage reviewable and lets installer/release paths consume the same documented defaults without changing runtime secret generation behavior.
