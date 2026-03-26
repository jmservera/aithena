# Decision: 404 vs 422 for Missing Embeddings in Similar Books

**Author:** Parker (Backend Dev)
**Date:** 2026-03-26
**Status:** Implemented (PR #1226)
**Context:** PR #1226 review comment

## Problem

The `/books/{id}/similar` endpoint returned 404 for two different failure modes:
1. No chunks found for the book (book not indexed)
2. Chunks found but no `embedding_v` field (book indexed, embeddings pending)

Both cases returned 404, but they have different semantics.

## Decision

- **404** — No indexed chunks found for this book
- **422** — Chunks exist but no embedding → can't process for similarity

## Rationale

HTTP 404 means "resource not found." When no chunks exist for the requested book ID, the book may not have been indexed yet, or may still be processing — no chunk documents have been created for it. This is a genuine "not found" condition because the parent document may or may not exist; what matters is that there is nothing to compute similarity from. HTTP 422 (Unprocessable Entity) applies when chunks exist (proving the book is at least partially indexed) but the first chunk has no `embedding_v` field yet — the server understands the request but can't fulfill it because the embedding pipeline hasn't run.

This lets clients distinguish between "no chunks for this book" (check back after indexing) and "chunks exist but embeddings aren't ready yet" (retry after embedding pipeline runs).

## Impact

- Clients checking for 404 to mean "book not found" won't get false positives from unprocessed books
- Frontend can show "embeddings processing" message on 422 vs "not found" on 404
- Pattern applies to any future endpoint that depends on async pipeline output
