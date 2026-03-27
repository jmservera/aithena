# PRD: Book Metadata Editing — Single and Batch Mode (Admin)

_Date:_ 2026-03-20  
_Prepared by:_ Newt (Product Manager)  
_Milestone:_ v1.10.0  
_Issue:_ #593

---

## 1. Problem Statement

Currently, all book metadata (title, author, year, category) is extracted **only from filenames and folder structure** at document indexing time via the `metadata.py` pipeline. This approach has critical limitations:

- **No correction path:** If a filename doesn't follow the `Author - Title (Year)` pattern, metadata remains incomplete or wrong
- **Lost manual edits:** When documents are re-indexed (requeue, re-scan), any manual corrections are discarded by the auto-detection logic
- **No grouping for series/collections:** Newspapers (e.g., "The Guardian"), magazines (e.g., "Nature"), and book series (e.g., "Discworld") have no way to be grouped together
- **Inefficient batch workflows:** Admins cannot correct metadata for groups of books without accessing the filesystem or renaming files

**Business impact:** Users discover incomplete or incorrect metadata in search results, reducing trust in the library. Admins have no way to improve metadata quality without manual file manipulation.

---

## 2. Current State Analysis

### Solr Schema

| Field | Type | Indexed | Stored | MultiValued | Status |
|-------|------|---------|--------|-------------|--------|
| `title_s` | string | ✅ | ✅ | ❌ | Exists |
| `title_t` | text_general | ✅ | ✅ | ❌ | Exists (for full-text search) |
| `author_s` | string | ✅ | ✅ | ❌ | Exists |
| `author_t` | text_general | ✅ | ✅ | ❌ | Exists |
| `year_i` | pint | ✅ | ✅ | ❌ | Exists |
| `category_s` | string | ✅ | ✅ | ❌ | Exists |
| `folder_path_s` | string | ✅ | ✅ | ❌ | Exists (for faceting via #592) |
| `series_s` | — | — | — | — | **Missing** — must be added |

### Metadata Extraction

- **Location:** `src/document-indexer/document_indexer/metadata.py`
- **Input:** Document filename + folder path + OCR content
- **Output:** `author_s`, `title_s`, `year_i`, `category_s` (derived from filename pattern and folder hierarchy)
- **Limitation:** No mechanism to persist or override auto-detected values

### Current API

- **Solr Search:** `src/solr-search/main.py` — query endpoints only, no document update endpoints
- **Auth:** v1.9.0 admin role check via `admin_auth.py`
- **Framework:** FastAPI with Pydantic models
- **Database integration:** Redis for caching, no persistent override store

---

## 3. Solution Design

### 3.1 Add Series Field to Solr Schema

Add a new `series_s` (string, indexed, stored, single-valued) field to support grouping books into series/collections:

```xml
<field name="series_s" type="string" multiValued="false" indexed="true" stored="true"/>
```

**Use cases:**
- Newspapers: "The Guardian", "Le Monde", "The New York Times"
- Magazines: "Nature", "Scientific American", "The Economist"
- Book series: "Foundation" (Asimov), "Discworld" (Pratchett), "Sherlock Holmes"

**Naming:** We use `series_s` (not `collection_s`) to avoid confusion with the user-facing "Collections" feature (#591), which is personal reading lists.

### 3.2 Metadata Override Persistence

**Challenge:** When a document is re-indexed, `metadata.py` re-extracts metadata from the filename. Manual edits must survive this process.

**Solution:** Redis-backed override store with permanent TTL.

**Architecture:**
```
Key format:   aithena:metadata-override:{document_id}
Value:        JSON {"year_i": 1984, "series_s": "Discworld", "edited_by": "admin", "edited_at": "2026-03-20T10:30:00Z"}
TTL:          None (permanent until explicitly cleared)
```

**Integration point:** During indexing, `document-indexer` checks for overrides:

```python
# In document-indexer/document_indexer/__main__.py, before sending to Solr
overrides = redis_client.get(f"aithena:metadata-override:{doc_id}")
if overrides:
    metadata_dict.update(json.loads(overrides))  # Manual values win
```

**Why Redis:**
- Already part of the infrastructure (no new data store)
- Fast reads during every index operation
- Atomic operations for concurrent edits
- Can be cleared/exported for auditing

**Alternative considered:** SQLite table in document-indexer with edit history. Rejected because it adds complexity, requires polling Redis for override checks is simpler.

### 3.3 Solr Atomic Updates

Replace full document re-indexing with targeted field updates using Solr's atomic update syntax:

```python
# Example: update title and year for a single document
update_doc = {
    "id": doc_id,
    "title_s": {"set": "New Title"},
    "year_i": {"set": 1984},
    "series_s": {"set": "Discworld"}
}
solr_client.post("/update/json", json=[update_doc], params={"commit": "true"})
```

**Benefits:**
- Immediate effect in search (no full re-index)
- Preserves other fields (embeddings, chunks, language, etc.)
- Scales to batch updates of hundreds of documents

### 3.4 Admin-Only Metadata Edit API

All endpoints require `admin_auth` validation.

#### PATCH Single Document
```
PATCH /v1/admin/documents/{doc_id}/metadata

Body:
{
    "title": "Corrected Title",        # optional
    "author": "Corrected Author",      # optional
    "year": 1984,                      # optional, range: 1000–2099
    "category": "Science Fiction",     # optional
    "series": "Discworld"              # optional
}

Response (200):
{
    "id": "doc-123",
    "updated_fields": ["title", "year"],
    "status": "ok",
    "message": "Metadata updated in Solr and override store"
}

Response (400):
{
    "error": "Validation failed",
    "details": "year must be between 1000 and 2099"
}

Response (404):
{
    "error": "Document not found",
    "id": "doc-123"
}
```

#### PATCH Batch Update by Document IDs
```
PATCH /v1/admin/documents/batch/metadata

Body:
{
    "document_ids": ["doc-id-1", "doc-id-2", "doc-id-3"],
    "updates": {
        "series": "Nature Magazine",
        "category": "Science"
    }
}

Response (200):
{
    "matched": 3,
    "updated": 3,
    "failed": 0,
    "errors": []
}

Response (200, partial):
{
    "matched": 3,
    "updated": 2,
    "failed": 1,
    "errors": [
        {
            "document_id": "doc-id-2",
            "error": "year out of range"
        }
    ]
}
```

#### PATCH Batch Update by Solr Query
```
PATCH /v1/admin/documents/batch/metadata-by-query

Body:
{
    "query": "folder_path_s:\"en/Magazines/Nature\"",
    "updates": {
        "series": "Nature Magazine",
        "category": "Science"
    }
}

Response (200):
{
    "matched": 47,
    "updated": 47,
    "failed": 0,
    "errors": []
}
```

**Validation:**
- `year`: integer, 1000–2099 (future-proofing for historical and near-future documents)
- `category`: alphanumeric + spaces, max 100 chars
- `series`: alphanumeric + spaces, max 100 chars
- `author`, `title`: max 255 chars each
- All fields: trim whitespace, reject if empty after trimming

**Side effects:**
1. Update Solr document via atomic update
2. Store override in Redis (even if some fields are not provided, mark as manually edited)
3. Log edit (who, what, when) — can be added later for audit trail

---

## 4. UI Design

### 4.1 Single Book Metadata Edit

**Trigger:** From search results or library view:
- Click "⋮" (menu) on a book card → "Edit metadata"
- Or: Open book detail page → "Edit metadata" button

**Modal/Drawer:**

```
┌─────────────────────────────────┐
│ Edit: "1984" by George Orwell   │ (header shows current values)
├─────────────────────────────────┤
│                                 │
│ Title:                          │
│ [_________________________]      │ (pre-filled: "1984")
│                                 │
│ Author:                         │
│ [_________________________]      │ (pre-filled: "George Orwell")
│                                 │
│ Year:                           │
│ [____] (1000–2099)              │ (pre-filled: 1949)
│                                 │
│ Category: ▼                     │ (dropdown + free text)
│ [Science Fiction      ▼]        │ (suggests existing categories)
│                                 │
│ Series: ▼                       │ (dropdown + free text, NEW)
│ [Blank                ▼]        │ (suggests existing series)
│                                 │
│                [Save] [Cancel]  │
└─────────────────────────────────┘
```

**Behavior:**
- Category and Series fields: combobox (editable dropdown)
  - Clicking opens a list of existing values (from Solr facets)
  - User can type to filter or enter new value
  - Pressing Enter or Tab confirms selection
- Save button: disabled until at least one field is changed
- After save: dismiss modal, refresh book card/detail view with new metadata
- Error handling: display validation errors inline (e.g., "Year must be 1000–2099")

### 4.2 Batch Metadata Edit

**Trigger:** From search results or library view:

1. **Selection mode:**
   - Toggle "Select mode" in the toolbar (or long-press on mobile)
   - Checkboxes appear on each book card

2. **Selection:**
   - Click checkboxes to select individual books
   - "Select all" button to select all visible results
   - "Deselect all" to clear selection
   - Badge shows count: "N selected"

3. **Batch edit:**
   - "Edit selected (N books)" button in floating action bar (bottom)
   - Opens batch edit panel

**Batch Edit Panel:**

```
┌──────────────────────────────────────────┐
│ Editing metadata for 15 selected books   │
├──────────────────────────────────────────┤
│                                          │
│ Only fill in fields you want to change: │
│ (empty = no change to that field)        │
│                                          │
│ ☐ Title:                                │
│   [_________________________] (disabled) │
│                                          │
│ ☐ Author:                               │
│   [_________________________] (disabled) │
│                                          │
│ ☐ Year:                                 │
│   [____] (1000–2099)          (disabled)│
│                                          │
│ ☐ Category: ▼                           │
│   [                          ▼] (enabled│
│                                          │
│ ☐ Series: ▼                             │
│   [                          ▼] (enabled│
│                                          │
├──────────────────────────────────────────┤
│ Preview:                                 │
│ This will update:                        │
│ • series for 15 documents                │
│ • category for 15 documents              │
│                                          │
│              [Apply] [Cancel]            │
└──────────────────────────────────────────┘
```

**Behavior:**
- Checkbox next to each field enables/disables that field for batch update
- Only checked fields are sent to the API
- Preview shows which fields will be changed and how many documents affected
- Apply button is disabled if no fields are checked
- After apply: dismiss panel, refresh search results, show toast: "Updated 15 books"
- If partial failure: show detailed error message

### 4.3 Series Facet (After Schema Addition)

Once `series_s` is deployed, add a new facet in the search sidebar:

```
Search Filters
├─ Language
├─ Category
├─ Author
├─ Series (NEW)
│  ├─ Nature (47)
│  ├─ Scientific American (12)
│  ├─ The Guardian (89)
│  └─ ... (load more)
├─ Year
└─ Type
```

**Behavior:**
- Clicking a series filters search results to that series
- Facet counts update dynamically
- Multi-select: user can filter by multiple series simultaneously

---

## 5. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Admin UI → Single Edit Modal or Batch Editor                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─→ Validation (year range, string length)
                   │
                   ├─→ HTTP PATCH /v1/admin/documents/{id}/metadata
                   │   or PATCH /v1/admin/documents/batch/metadata
                   │
┌──────────────────────────────────────────────────────────────┐
│ solr-search (FastAPI)                                        │
├──────────────────────────────────────────────────────────────┤
│ 1. Validate admin auth (admin_auth.py)                      │
│ 2. Validate request body (Pydantic model)                   │
│ 3. Resolve document_ids (query Solr if needed)              │
│ 4. For each document:                                        │
│    a. Build atomic update doc                               │
│    b. POST to Solr /update/json                             │
│    c. Store override in Redis                               │
│    d. Log edit (optional: user, timestamp)                  │
│ 5. Return response (count updated, errors)                  │
└──────────────┬───────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  [Solr] (atomic update)  [Redis] (override store)
  Document fields updated  Key: aithena:metadata-override:{id}
  Immediately visible      Value: {"year_i": 1984, ...}
  in search results

┌────────────────────────────────────────────────────────────┐
│ Re-indexing (document-indexer, after manual edit)          │
├────────────────────────────────────────────────────────────┤
│ 1. Extract metadata from filename (as always)              │
│ 2. Check Redis for override: aithena:metadata-override:{id}│
│ 3. If override exists: merge into metadata dict            │
│ 4. Index document with merged metadata                     │
│ → Manual edits are preserved across re-index               │
└────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Plan

### Phase 1: Schema & API (Ash + Parker)

1. **Ash (Search Engineer):**
   - Add `series_s` to `src/solr/books/managed-schema.xml`
   - Test schema deployment (rolling update to running cluster)
   - Add series facet configuration to Solr search

2. **Parker (Backend Dev):**
   - Create Pydantic models for metadata edit requests
   - Implement Solr atomic update utility function
   - Write tests for atomic update behavior

### Phase 2: Backend Implementation (Parker)

3. **Parker:**
   - Implement single document PATCH endpoint (`/v1/admin/documents/{id}/metadata`)
   - Implement Redis override store (init, read, write, delete)
   - Integrate override check into document-indexer indexing pipeline
   - Implement batch PATCH endpoints
   - Add admin auth check to all new endpoints
   - Write comprehensive tests (single, batch, failures, re-index scenarios)

### Phase 3: Frontend Implementation (Dallas)

4. **Dallas (Frontend Dev):**
   - Design and implement single edit modal (React component)
   - Implement batch selection UI (checkboxes, toolbar, floating action bar)
   - Implement batch edit panel
   - Call backend endpoints (error handling, loading states, toasts)
   - Write tests for UI components

### Phase 4: Integration & Polish (Ash, Parker, Dallas)

5. **Ash:**
   - Add series facet to search sidebar (integrate with React query)
   - Update search result cards to display series (if present)

6. **Parker + Dallas:**
   - End-to-end testing (single edit → search refresh → verify)
   - End-to-end testing (batch edit → verify all N documents updated)
   - Test re-index scenario (edit → requeue → verify override persists)

7. **Kane (Security):**
   - Review admin auth implementation
   - Validate input sanitization (injection prevention)
   - Check Redis access control

8. **Lambert (Tester):**
   - Write full test suite (single/batch edit, re-index persistence)
   - Test error scenarios (network errors, validation errors, partial failures)

---

## 7. Technical Decisions

### Override Storage: Redis vs SQLite

**Chosen:** Redis (permanent key-value store)

**Rationale:**
- Redis is already in the infrastructure
- Simple API: `GET aithena:metadata-override:{id}` during every index operation
- No schema migrations needed
- Can be easily exported/imported for backup/restore
- TTL = None (permanent) ensures edits survive indefinitely

**Trade-off:** No built-in audit trail. If audit is needed later, add a separate `metadata_edits_log` table.

### Author as Single vs Multi-Valued

**Chosen:** Keep `author_s` as single-valued (for now)

**Rationale:**
- Current schema and UI assume single author
- Upgrade path exists: rename `author_s` → `author_ss` (multiValued) in future issue
- Batch editor can support comma-separated authors in the text input (parsed and stored as single value)

**Future work:** #XXX — support multiple authors per book

### Series Naming Convention

**Chosen:** `series_s` (not `collection_s`)

**Rationale:**
- "Collections" is already a user-facing feature (#591) for personal reading lists
- Avoids confusion between document metadata (series) and user data (collections)
- Naming convention consistent with schema: `_s` suffix for string fields

### Admin-Only Access

**Chosen:** All metadata edit endpoints require admin role

**Rationale:**
- Metadata quality affects all users
- Non-admins could spam incorrect edits
- Admin role is already defined in v1.9.0 auth system
- Audit trail (optional) can track who made which edits

---

## 8. Success Criteria

1. ✅ **Schema deployment:** `series_s` field added to running SolrCloud cluster without data loss
2. ✅ **Single edit workflow:** Admin can edit one book's metadata via modal, changes reflect immediately in search
3. ✅ **Batch edit workflow:** Admin can select multiple books and update series/category for all at once
4. ✅ **Override persistence:** Manual edits survive document re-indexing (test with requeue + re-scan)
5. ✅ **Series facet:** New "Series" facet appears in search sidebar, filtering works correctly
6. ✅ **API validation:** Invalid requests (year out of range, empty strings) are rejected with clear error messages
7. ✅ **Auth enforcement:** Non-admin users cannot access metadata edit endpoints
8. ✅ **Performance:** Single edit takes <500ms (Solr atomic update), batch edit for 100 books takes <2s
9. ✅ **Tests:** Unit tests for API, integration tests for Solr + Redis, E2E tests for UI workflows

---

## 9. Open Questions for Team Discussion

1. **Override deletion:** Should there be an "Undo" or "Revert to auto-detected" action that clears the Redis override? Or should edits be permanent unless manually changed again?

2. **Author multi-value:** Should we upgrade `author_s` to `author_ss` as part of this work, or defer to a separate issue? Co-authored books currently store only the first author.

3. **Audit trail:** Do we need to log who edited what and when? Useful for shared admin environments but adds complexity. Can be a future enhancement.

4. **Batch size limits:** Should batch operations have a limit (e.g., max 1000 documents per request)? Prevents runaway operations.

5. **Series field editing:** Should admins be able to create new series values, or should series be a curated list (dropdown-only)? Currently designed as free-text (create on edit).

6. **Folder facet integration:** Once #592 (folder facet) lands, should batch editing be pre-filtered by folder selection? E.g., "Edit all books in selected folder"?

7. **Schema migration timing:** Should `series_s` be added before or after the API is ready? Option A: add field now (safe), deploy endpoints when ready. Option B: add field and endpoints together (tighter coupling but simpler rollback).

---

## 10. Related Issues & Dependencies

- **Sister issue:** #592 (Folder path facet) — enables batch selection by folder
- **Depends on:** v1.9.0 auth system (admin role check) — already available
- **Related to:** #591 (User collections) — different concept (personal reading lists vs document metadata)
- **Future:** Metadata edit audit trail, author multi-value support, curated series dropdown

---

## 11. Out of Scope

- Exporting/syncing metadata to external APIs (e.g., ISBN databases)
- Metadata import from CSV or bulk file upload
- Approval workflow for admin edits
- Real-time multi-admin conflict resolution (last write wins)
- Mobile-optimized batch editor (desktop-first for v1.10.0)

---

## 12. Appendix: API Examples

### Example 1: Edit Single Book Year

**Request:**
```
PATCH /v1/admin/documents/aithena-1984/metadata
Content-Type: application/json
Authorization: Bearer {admin_token}

{
    "year": 1949
}
```

**Response:**
```
200 OK

{
    "id": "aithena-1984",
    "updated_fields": ["year_i"],
    "status": "ok",
    "message": "Metadata updated in Solr and override store"
}
```

### Example 2: Batch Update Series for Magazine Collection

**Request:**
```
PATCH /v1/admin/documents/batch/metadata-by-query
Content-Type: application/json
Authorization: Bearer {admin_token}

{
    "query": "folder_path_s:\"en/Magazines/Nature\"",
    "updates": {
        "series": "Nature Magazine",
        "category": "Science"
    }
}
```

**Response:**
```
200 OK

{
    "matched": 47,
    "updated": 47,
    "failed": 0,
    "errors": []
}
```

### Example 3: Batch Update Multiple Specific Books

**Request:**
```
PATCH /v1/admin/documents/batch/metadata
Content-Type: application/json
Authorization: Bearer {admin_token}

{
    "document_ids": [
        "gutenberg-1984",
        "gutenberg-animal-farm",
        "gutenberg-homage-to-catalonia"
    ],
    "updates": {
        "author": "George Orwell"
    }
}
```

**Response:**
```
200 OK

{
    "matched": 3,
    "updated": 3,
    "failed": 0,
    "errors": []
}
```

### Example 4: Validation Error

**Request:**
```
PATCH /v1/admin/documents/aithena-1984/metadata
Content-Type: application/json
Authorization: Bearer {admin_token}

{
    "year": 3000
}
```

**Response:**
```
400 Bad Request

{
    "error": "Validation failed",
    "details": "year must be between 1000 and 2099"
}
```

