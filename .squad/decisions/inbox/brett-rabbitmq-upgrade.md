# Decision: Upgrade RabbitMQ to 4.0 LTS

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-17
**PR:** #403

## Context

RabbitMQ 3.12 reached end-of-life. The running instance logged "This release series has reached end of life and is no longer supported." Additionally, credential mismatch prevented document-lister from connecting.

## Decision

Upgrade from `rabbitmq:3.12-management` to `rabbitmq:4.0-management` (RabbitMQ 4.0.9, current supported LTS).

## Consequences

1. **Volume reset required:** After pulling the new image, the Mnesia data directory at `/source/volumes/rabbitmq-data/` must be cleared. RabbitMQ 4.0 cannot start on 3.12 Mnesia data without enabling feature flags first. Since we have no persistent queues to preserve, a clean start is the correct approach.
2. **Config compatibility:** `rabbitmq.conf` settings (management.path_prefix, vm_memory_high_watermark, consumer_timeout) are all compatible with 4.0. No config changes needed.
3. **Deprecation warning:** RabbitMQ 4.0 warns about `management_metrics_collection` being deprecated. This is informational only and does not affect functionality. Will need attention in a future RabbitMQ 4.x minor release.
4. **Upgrade path for future:** If we ever need to preserve queue data during a major version upgrade, must run `rabbitmqctl enable_feature_flag all` on the old version before upgrading.

## Affected Services

- `rabbitmq` — image tag change
- `document-lister` — was failing to connect due to credential mismatch (now fixed by volume reset)
- `document-indexer` — indirectly affected (no queue to consume from)
