# Decision: Pre-release warning policy for Solr/RabbitMQ runtime noise

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-06T09:36:46.687+00:00  
**Status:** Proposed for Scribe merge  
**Related:** #1695, #1696

## Context

Pre-release validation run 27058984234 reported warnings for Solr/JVM deprecations, RabbitMQ `management_metrics_collection`, Solr `solr.log.dir`, and Solr `ZkCredentialsInjector`.

## Decision

Pre-release allowlist entries should stay narrow and preserve signal:

- Fix actionable first-party configuration deprecations in Compose/scripts instead of allowlisting them. The Solr 10 `solr.log.dir` warning is actionable; Aithena should use `solr.logs.dir`.
- Keep known upstream/runtime notices as `info` only when there is no safe first-party knob for the supported topology. Current examples are Solr/JVM `sun.misc.Unsafe` terminal deprecation notices and RabbitMQ 4.0-management `management_metrics_collection` startup notices.
- Keep the Solr `Using default ZkCredentialsInjector` message in the same accepted posture as `ZkCredentialsProvider/ZkACLProvider`: acceptable only while ZooKeeper remains internal-only and Solr HTTP BasicAuth/RBAC remains enforced.
- Do not use broad allowlist patterns such as `deprecation:*deprecated*`; unrelated deprecations must continue to surface as warnings.

## Rationale

Issue #1695 mixed one actionable Solr logging configuration warning with upstream Solr/JVM and RabbitMQ runtime deprecations. Issue #1696 used the newer Solr 10 `ZkCredentialsInjector` wording for the previously accepted ZooKeeper ACL posture. Narrow rules prevent recurring pre-release issues for known noise without hiding new deprecations, authentication failures, or production hardening gaps.
