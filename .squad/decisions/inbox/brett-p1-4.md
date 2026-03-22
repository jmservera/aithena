# Decision: Docker Compose A/B Infrastructure (P1-4)

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-26
**Issue:** #870

## Context

P1-4 required Docker Compose configuration for dual-indexer A/B testing (distiluse baseline vs multilingual-e5-base candidate). OQ-1 resolved: use fanout exchange pattern.

## Decisions

### 1. Embeddings Dockerfile MODEL_NAME as build ARG

Made `MODEL_NAME` a build-time ARG in the embeddings-server Dockerfile (previously hardcoded ENV). This allows building separate Docker images with different models pre-baked, which is required because the image runs in `HF_HUB_OFFLINE=1` mode (no runtime model downloads).

**Impact:** Any future embeddings model variant can be built from the same Dockerfile by passing `MODEL_NAME` as a build arg in docker-compose.

### 2. Indexers depend on solr-init (service_completed_successfully)

Both `document-indexer` and `document-indexer-e5` now depend on `solr-init` with `condition: service_completed_successfully`. This prevents indexers from starting before their target Solr collections exist.

**Impact:** Eliminates a startup race condition where indexers could fail if the collection hadn't been created yet.

### 3. No static RabbitMQ definitions

The fanout exchange and queue bindings are declared dynamically by application code (document-lister publishes to exchange, each indexer declares its queue and binds). Topology is documented in `rabbitmq.conf` comments rather than `definitions.json`.

**Rationale:** Dynamic declaration is more resilient — queues are created by the consumers that need them. Static definitions would require coordinating changes in two places.

### 4. Memory budget: 3.5GB addition

- `embeddings-server-e5`: 3GB limit / 2GB reservation (e5-base model ~1.1GB + runtime)
- `document-indexer-e5`: 512MB limit / 256MB reservation

Total stack memory increase: ~3.5GB. Hosts running the full A/B stack need at least 16GB RAM (was ~12.5GB for baseline).

### 5. Dev-only scope

A/B services are in `docker-compose.yml` (base) and `docker-compose.override.yml` (dev ports). `docker-compose.prod.yml` is intentionally NOT modified — production A/B deployment deferred to P3-2.
