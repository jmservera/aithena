# Decision: Embedding Model A/B Test PRD — Architecture & Work Plan

**Author:** Ripley (Lead)
**Date:** 2026-03-22
**Status:** PROPOSED — Awaiting PO Review
**PRD:** `docs/prd/embedding-model-ab-test.md`

## Context

Ash completed research on embedding model alternatives (#861). The PO approved moving forward with an in-repo A/B test of `multilingual-e5-base` (512 tokens, 768D) vs the current `distiluse-base-multilingual-cased-v2` (128 tokens, 512D). This decision documents the architectural approach and key trade-offs.

## Decisions Made

### 1. Dual-Collection Architecture (not dual-schema)
Two separate Solr collections (`books` and `books_e5base`) rather than two vector fields in one collection. Rationale: cleaner separation, independent schema evolution, easier cleanup after test, no risk to production data.

### 2. Docker Compose Overlay for A/B Services
New services (`embeddings-server-e5`, `document-indexer-e5`) defined in a compose overlay file, not inline in the production `docker-compose.yml`. Keeps production config clean; overlay activated only during testing.

### 3. Embeddings Server Handles Prefix (not Indexer)
E5 models require `"query: "` / `"passage: "` prefixes. These are configured on the embeddings server via `QUERY_PREFIX`/`PASSAGE_PREFIX` env vars, not in the indexer or search service. Centralizes model-specific behavior in the model-serving layer.

### 4. Chunking Recalculation: 300 words / 50 overlap
Proportional scaling from PO's 90/10 decision for 128-token window → 300/50 for 512-token window. 300 words ≈ 390 tokens, safely within 512-token budget. PO to confirm.

### 5. Phase-Gated Execution (3 phases)
Phase 1 (infra setup) → Phase 2 (indexing & benchmarking) → Phase 3 (evaluation & migration). PO decision gate between Phase 2 and Phase 3. Consistent with team's proven phase-gated pattern.

## Open / Blocking Questions

- **OQ-1 (BLOCKING):** RabbitMQ competing consumers means only one indexer gets each message. Need fanout exchange or separate queues for dual indexing. Ash + Brett must resolve before P1-3/P1-4.
- **OQ-2:** Final CHUNK_SIZE confirmation from PO (300/50 recommended).
- **OQ-5:** Whether Dallas builds a comparison UI or API/CLI is sufficient.

## Impact

- **Ash:** Primary on search/Solr items (12 pts across 5 work items)
- **Parker:** Backend API changes (8 pts across 3 items)
- **Brett:** Infrastructure/Docker (7 pts across 3 items)
- **Lambert:** Metrics collection (2 pts, 1 item)
- **Dallas:** No assignment in this PRD (stretch goal only)
- **Total resource cost:** ~31 pts, ~9.5GB host RAM during A/B test
