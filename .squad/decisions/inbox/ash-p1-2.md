# Decision: books_e5base configset is a full copy of books

**Author:** Ash (Search Engineer)
**Date:** 2026-07-21
**Context:** P1-2, PR #882, Issue #873

## Decision

The `books_e5base` configset is a full independent copy of the `books` configset directory, not a symlink or overlay. Only the vector field type and dimension differ.

## Rationale

- Full copy allows independent evolution (e.g., different HNSW tuning parameters for 768D vectors)
- Avoids symlink complexity in Docker volume mounts
- The `solr-init` script treats each configset identically — upload to ZK, create collection, apply overlay
- If the A/B test succeeds and books_e5base replaces books, the old configset can be removed cleanly

## Impact

- Any future schema changes to non-vector fields (new metadata fields, analyzer tweaks) must be applied to BOTH configsets
- Parker and Brett should be aware that `SOLR_COLLECTION=books_e5base` is now a valid target for document-indexer-e5

## Alternatives Considered

- **Shared configset with parameterized vector dimension:** Solr doesn't support schema parameterization at configset level
- **Symlinks for shared files:** Would complicate Docker volume mounts and ZooKeeper uploads
