# Decision: E5 Prefix Handling Internal to Embeddings Server

**Author:** Ash (Search Engineer)
**Date:** 2026-03-22
**Issue:** #874 (P1-1)
**PR:** #883

## Context

E5-family models require `"query: "` prefix for search queries and `"passage: "` prefix for documents to achieve optimal relevance. Two approaches were considered:

1. **Caller-side prefixes:** Each caller (solr-search, document-indexer) applies the prefix based on its own knowledge of the model.
2. **Server-side prefixes:** The embeddings-server detects model family and applies prefixes internally; callers pass `input_type`.

## Decision

**Server-side prefixes (option 2)** — aligned with PRD section P1-1.

Callers send `input_type: "query" | "passage"` (default `"passage"`) in the `/v1/embeddings/` request body. The server auto-prepends the correct prefix for e5-family models. For non-e5 models (distiluse), `input_type` is accepted but ignored.

## Rationale

- Single point of prefix logic — avoids duplication across solr-search and document-indexer
- Backward compatible — existing callers omitting `input_type` get `"passage"` default (correct for indexing)
- Model-agnostic API — if we switch models again, only the server needs updating
- `/v1/embeddings/model` returns `requires_prefix` and `model_family` for client-side verification

## Impact

- **solr-search:** Must pass `input_type: "query"` when encoding search queries (P1-5)
- **document-indexer:** No changes needed — default `"passage"` is correct for indexing
- **Future models:** Add detection logic to `detect_model_family()` only
