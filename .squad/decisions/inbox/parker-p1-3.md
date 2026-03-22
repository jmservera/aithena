# P1-3: Fanout Exchange for Dual-Model Indexing

**Date:** 2026-03-22
**Author:** Parker (Backend Dev)
**Issue:** #871

## Decision

Implemented the fanout exchange pattern per OQ-1 resolution:

- **Exchange:** `documents` (type=fanout, durable=true)
- **Producer (document-lister):** Publishes to `exchange="documents"` with `routing_key=""`. No longer declares or targets a specific queue.
- **Consumer (document-indexer):** Each instance declares its own queue (`QUEUE_NAME` env var), declares the exchange (idempotent), and binds its queue to the exchange.

## New Environment Variables

| Variable | Service | Default | Purpose |
|----------|---------|---------|---------|
| `EXCHANGE_NAME` | document-lister, document-indexer | `documents` | RabbitMQ fanout exchange name |

Pre-existing env vars (`QUEUE_NAME`, `SOLR_COLLECTION`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EMBEDDINGS_HOST`) were already in the indexer code; no defaults changed.

## Backward Compatibility

Running without any new env vars produces identical behavior to pre-change. The exchange is created automatically; existing queues continue to work once bound.

## Impact

- **Ash:** The `books_e5base` Solr collection (already defined in solr-init) will now receive documents from the `document-indexer-e5` service.
- **Ripley:** Docker-compose already has both indexer services defined with correct env vars.
- **All:** RabbitMQ now requires exchange support (standard in all versions).
