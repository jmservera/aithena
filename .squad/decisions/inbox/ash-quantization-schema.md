# Decision: Dual-Field Schema for Vector Quantization (#1502)

**Author:** Ash (Search Engineer)
**Date:** 2025-07-22
**Status:** Proposed

## Context

Issue #1502 introduces configurable vector quantization. The schema needs to support both float32 and int8 (BYTE) vector storage.

## Decision

Use a **dual-field approach** rather than replacing the existing vector field:

| Quantization Mode | Field Type | Field Name | Encoding |
|---|---|---|---|
| `none` / `fp16` | `knn_vector_768` | `embedding_v` | float32 |
| `int8` | `knn_vector_768_byte` | `embedding_byte` | BYTE (signed byte) |

The indexer (embeddings-server) selects which field to write based on `VECTOR_QUANTIZATION` env var. The search service queries the appropriate field.

## HNSW Tuning

`knn_vector_768_byte` uses `hnswMaxConnections="12"` (vs default 16). Rationale:
- Byte vectors already provide ~4x memory savings
- Slightly fewer connections further reduces graph memory overhead
- 12 connections is still within the recommended range for 768D vectors

## Implications

- **Search service** (`solr-search`) must be aware of which field to query based on quantization config
- **Indexer** writes to exactly one field per document — no dual-writing
- **Backward compatible** — existing `embedding_v` field and `knn_vector_768` type are unchanged
- **Re-index required** when switching quantization modes (vectors are not interchangeable)
