# Decision: Stats Book Count Architecture (PR #416)

**Date:** 2026-03-17  
**Decider:** Ripley (Lead)  
**Context:** Issue #404 — Stats showing chunk count (127) instead of book count (3)

## Decision

Approved Phase 1 quick win using **Solr grouping** to count distinct books instead of implementing full parent/child document hierarchy.

## Implementation

**Approach:**
- Use `group=true&group.field=parent_id_s&group.limit=0` in stats query
- Extract `ngroups` from grouped response (distinct parent count)
- Replace previous `numFound` extraction (total document count)

**Why This Works:**
- The `parent_id_s` field already exists in schema and is populated by document-indexer
- No schema changes required
- No reindexing required
- Solr grouping is a standard, performant feature for this exact use case

## Rationale

**Trade-offs Considered:**
1. **Phase 1 (chosen):** Grouping for stats only
   - ✅ Minimal change (48 additions, 12 deletions)
   - ✅ Solves user-facing problem immediately
   - ✅ Zero migration/reindexing cost
   - ⚠️ Doesn't deduplicate search results (not a requirement yet)

2. **Full parent/child hierarchy:** Separate parent + child documents
   - ❌ Requires schema redesign
   - ❌ Requires reindexing all documents
   - ❌ Adds complexity to search logic
   - ✅ Would enable search result deduplication (if needed later)

**Decision:** Phase 1 is architecturally sound. Full hierarchy can be Phase 2 if search deduplication becomes a requirement.

## Pattern for Future Use

**When to use Solr grouping for stats:**
- Counting distinct parent entities in a parent/child relationship
- The `ngroups` field gives exact unique parent count
- More efficient than nested documents when you only need counts, not result deduplication

## Team Impact

- **Parker/Ash:** Pattern established for counting distinct entities in Solr
- **Future stats work:** Use grouping when counting distinct books, authors, categories, etc.
- **Search deduplication:** If needed later, implement full parent/child hierarchy as Phase 2

## Verification

- ✅ All 193 tests pass (7 stats tests updated to grouped response format)
- ✅ Integration tests verify correct Solr parameters
- ✅ PR #416 merged to `dev`, closes #404
