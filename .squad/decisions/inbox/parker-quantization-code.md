# Decision: Embeddings Response Includes field_name (#1502)

**Author:** Parker (Backend Dev)
**Date:** 2026-04-20
**Status:** Implemented

## Context

Issue #1502 adds configurable vector quantization. Different modes (none, fp16, int8) target different Solr fields — `embedding_v` for float vectors and `embedding_byte_v` for int8 byte-encoded vectors.

## Decision

The embeddings-server `/v1/embeddings/` response now includes a `field_name` key per embedding item (e.g., `"embedding"` or `"embedding_byte"`). The document-indexer uses this field name (suffixed with `_v`) as the Solr field key in the indexed document.

This keeps the field-routing logic centralized in the embeddings-server (which knows the quantization mode) rather than requiring every consumer to duplicate mode→field mapping.

## Implications

- **Backward compatible**: `field_name` defaults to `"embedding"` — existing consumers that ignore it get the same behavior
- **Ash (Solr schema)**: The `embedding_byte` field must exist in the Solr schema when int8 mode is active. Ash has already added this field type.
- **Dallas (UI)**: No UI impact — quantization is transparent to the frontend
- **Future consumers**: Any new service that calls `/v1/embeddings/` should use `field_name` to determine the correct storage field
