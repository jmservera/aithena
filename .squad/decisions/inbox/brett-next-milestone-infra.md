# Decision: Pre-release Infra Warning Classification for Next Milestone

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-03  
**Status:** Proposed  
**Related:** #1628, #1630, #1631, PR #1638

## Context

Ralph round 1 routed pre-release warning issues to Brett. The deprecation bucket included a Solr CLI deprecation that is already fixed in current compose/init paths and RabbitMQ 4.0-management startup notices for `management_metrics_collection` that the project does not explicitly configure.

## Decision

Known RabbitMQ `management_metrics_collection` pre-release startup deprecation notices should remain visible but be classified as `info` by the pre-release analyzer allowlist until the RabbitMQ image line removes or changes the upstream notice. Redis overcommit should be automated with Compose `sysctls` where supported, while keeping the host sysctl runbook as the portable fallback. Solr/ZooKeeper default credential and ACL warnings require Kane's security posture decision before Brett changes the infra wiring.

## Rationale

This keeps the next milestone warning gate focused on actionable regressions without hiding known upstream image noise. Redis overcommit is safe to automate for Linux Compose deployments and still documented for runtimes that reject the sysctl. ZooKeeper/Solr ACL behavior has security implications, so Brett should not unilaterally define the acceptable dev/test versus production policy.
