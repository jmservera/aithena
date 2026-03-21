# Decision: Metadata Edit API — Redis Override Store Format

**Date:** 2026-03-20
**Author:** Parker (Backend Dev)
**Issue:** #681

## Context
The metadata edit endpoint needs to store overrides in Redis so document-indexer can apply them during re-indexing.

## Decision
Redis override values use **Solr field names** (e.g., `title_s`, `title_t`, `year_i`) rather than request field names (e.g., `title`, `year`). This means document-indexer can apply overrides directly to the Solr document without needing a field mapping table.

Key format: `aithena:metadata-override:{document_id}`
Value: JSON with Solr field names + `edited_by` + `edited_at`

## Impact
- **Ash (Search/Solr):** Override keys use Solr field names — if schema changes, update `_METADATA_FIELD_MAP` in main.py
- **Document-indexer integration:** Can do `metadata_dict.update(json.loads(overrides))` directly (after filtering out `edited_by`/`edited_at`)
