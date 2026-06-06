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
