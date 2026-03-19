# Decision: Nginx proxy timeouts must match upstream service timeouts

**Author:** Ash (Search Engineer)
**Date:** 2026-03-19
**Context:** Issue #562 — 502 Bad Gateway on vector/hybrid search

## Decision

Any nginx `location` block that proxies to a service with configurable timeouts (e.g., embeddings generation, Solr bulk operations) **must** set `proxy_read_timeout` to at least 1.5× the upstream service timeout.

For the `/v1/` API location (which routes search requests through solr-search → embeddings-server):
- `proxy_read_timeout 180s` (1.5× the 120s `EMBEDDINGS_TIMEOUT`)
- `proxy_connect_timeout 10s` (fail fast on unreachable upstream)

## Rationale

The default nginx `proxy_read_timeout` is 60s. The embeddings server timeout is 120s. When embedding generation for long queries exceeded 60s, nginx killed the connection before solr-search could return a graceful degradation response (fallback to keyword search). This caused a raw 502 error to reach the user.

## Impact

Team members adding new nginx proxy locations or changing service timeouts should verify the nginx timeout chain is consistent.
