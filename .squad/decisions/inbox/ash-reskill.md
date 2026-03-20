# Decision: Ash Reskill — History Consolidation + Skill Extraction

**Author:** Ash (Search Engineer)
**Date:** 2026-03-21
**Status:** IMPLEMENTED

## What Changed

### History Consolidation
- **Before:** 177 lines with significant redundancy (two overlapping #562 entries, duplicated PRD decomposition, stale v0.5 roadmap items, repeated schema snapshots)
- **After:** 82 lines with zero information loss on actionable knowledge
- **Removed:** Duplicate #562 fix entries (merged into one pattern), stale roadmap items (v0.5 issues long closed), verbose PRD decomposition tables (compressed to principles), redundant 2026-03-14 reskill snapshot (subsumed by Core Context)
- **Added:** Reskill Notes section with confidence self-assessment and knowledge gaps

### New Skill Extracted
- **`hybrid-search-parent-chunk`** — Documents the parent-chunk document model, EXCLUDE_CHUNKS_FQ correctness rule, all three search mode implementations, and embedding pipeline. This was the #1 knowledge gap that caused the PR #701 near-incident. Now any agent touching search queries has a reference skill.

### Existing Skills Reviewed
- `solr-pdf-indexing` — Still accurate, covers indexing side well. No changes needed.
- `solrcloud-docker-operations` — Still accurate, covers cluster ops. No changes needed.

## Impact
- **Ash spawn cost:** Reduced context tokens (~380 tokens saved)
- **Team safety:** The parent-chunk model is now a standalone skill that any agent can reference before modifying search code
- **Charter:** No changes needed (already lean at 27 lines)

## Knowledge Improvement Estimate
~25% — Primary improvement is in consolidation quality (removing noise) and externalizing the most critical pattern (parent-chunk model) into a reusable skill. Domain knowledge was already solid; the improvement is in how it's organized and accessible.
