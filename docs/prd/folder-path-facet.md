# PRD: Folder Path Facet for Search & Batch Operations

_Date:_ 2026-03-20  
_Prepared by:_ Ash (Search Engineer)  
_Issue:_ #592  
_Milestone:_ v1.11.0

---

## 1. Problem Statement

Users of Aithena organize their book library in a folder hierarchy on the file system:

```
library/
  en/
    Science Fiction/
      Asimov - Foundation (1951).pdf
      Clarke - 2001 (1968).pdf
    History/
      Gibbon - The Decline and Fall (1776).pdf
  es/
    Ciencia Ficción/
      García - El Sueño (2015).pdf
```

The document metadata captures the **folder path** (`folder_path_s` field in Solr) during indexing, but this field is **not exposed as a search facet**. Users cannot:
- **Filter results by folder** ("Show me all books in Science Fiction")
- **Browse the folder structure visually** (hierarchical tree in the UI)
- **Perform batch operations on folders** ("Edit metadata for all 47 books in this folder")

This blocks a key admin workflow: "Find all books in a physical folder → Edit their metadata in bulk."

---

## 2. Current State

| Aspect | Status | Evidence |
|--------|--------|----------|
| `folder_path_s` field in Solr schema | ✅ Exists | `managed-schema.xml`: `<field name="folder_path_s" type="string" indexed="true" stored="true"/>` |
| Populated during indexing | ✅ Yes | `document-indexer/__main__.py:247`: `"folder_path_s": metadata["folder_path"]` |
| Extracted from file system | ✅ Yes | `document_indexer/metadata.py`: computes relative path from base directory |
| Returned in search results | ✅ Yes | Stored field, accessible via `fl` parameter |
| Configured as facet in API | ❌ **No** | `FACET_FIELDS` in `search_service.py` does not include `folder_path_s` |
| Exposed in facet counts response | ❌ **No** | Only `author_s`, `category_s`, `year_i`, `language_detected_s` are returned |
| Tree-view UI component | ❌ **No** | Not yet implemented in frontend |

---

## 3. Requirements

### 3.1 Backend: Add Folder Facet to Search API

**Owner:** Ash (Search Engineer)  
**Complexity:** Small (3–5 lines of code)

#### 3.1.1 Add to FACET_FIELDS

In `src/solr-search/search_service.py`, add `folder` mapping to the `FACET_FIELDS` dictionary:

```python
FACET_FIELDS: dict[str, tuple[str, ...]] = {
    "author": ("author_s",),
    "category": ("category_s",),
    "year": ("year_i",),
    "language": ("language_detected_s", "language_s"),
    "folder": ("folder_path_s",),  # NEW: enable folder faceting
}
```

#### 3.1.2 Path Processing

The indexer already produces relative paths (e.g., `"en/Science Fiction"`). The search API should:
- Return these paths as-is in facet counts (no stripping/normalization needed)
- Support filtering via `filters={"folder": "en/Science Fiction"}` in search requests
- Respect the existing `solr_escape()` logic for special characters (quotes, slashes)

#### 3.1.3 API Response Format

Facet counts should include folder alongside other facets:

```json
{
  "mode": "keyword",
  "results": [...],
  "facets": {
    "author": [
      {"value": "Asimov", "count": 12},
      {"value": "Clarke", "count": 8}
    ],
    "folder": [
      {"value": "en/Science Fiction", "count": 125},
      {"value": "en/History", "count": 89},
      {"value": "es/Ciencia Ficción", "count": 47}
    ],
    ...
  }
}
```

#### 3.1.4 Filter Query Support

Existing filter logic in `build_filter_queries()` should automatically work:
```python
filters = {"folder": "en/Science Fiction"}
# Generates: fq=folder_path_s:"en/Science Fiction"
```

**No code changes needed** — the filter builder is field-agnostic.

---

### 3.2 Frontend: Folder Facet UI Component

**Owner:** Dallas (Frontend Developer)  
**Complexity:** Medium (hierarchical tree rendering, state management)

#### 3.2.1 Facet Panel Integration

Add a "Folder" section to the search sidebar facet panel (same layout as author/category):

```
┌─────────────────────────────┐
│  Search Results (847)        │
├─────────────────────────────┤
│ 📁 Folder                    │
│ ├─ en (456)                 │
│ │ ├─ Science Fiction (125)  │
│ │ ├─ History (89)           │
│ │ └─ Biography (67)         │
│ └─ es (312)                 │
│   ├─ Ciencia Ficción (98)   │
│   └─ Literatura (67)        │
├─────────────────────────────┤
│ 📝 Author (see below)        │
├─────────────────────────────┤
│ 📂 Category (see below)      │
...
```

#### 3.2.2 Hierarchical Tree Display

Path values from the API are flat (e.g., `["en", "en/Science Fiction", "en/History", "es"]`), so the frontend must:

1. **Parse paths** — Split by `/` to build a tree structure
2. **Sort hierarchically** — Group by parent directory
3. **Count propagation** — Parent folder count = sum of children (or total matching that prefix)
4. **Progressive disclosure** — Expand/collapse folders on click
5. **Visual hierarchy** — Indentation + folder icons (📁) vs leaf items

**Implementation approach (Option A — Client-side tree building):**

```typescript
interface FacetTreeNode {
  label: string;           // e.g., "en", "Science Fiction"
  fullPath: string;        // e.g., "en/Science Fiction"
  count: number;
  children: FacetTreeNode[];
  isLeaf: boolean;
}

// Frontend parses flat facet array into tree:
const flatPaths = ["en", "en/Science Fiction", "en/History", "es"];
const tree = buildFacetTree(flatPaths, folderCounts);

// Render with collapsible tree component
<FacetTree node={tree} onSelect={handleFolderSelect} />
```

#### 3.2.3 Filter Integration

When user clicks a folder:
- Apply filter: `filters: {"folder": "en/Science Fiction"}`
- Re-search with updated filters
- Show in active filters bar (breadcrumbs)
- Allow multi-select (AND logic): `filters: {"folder": "en/Science Fiction,es/Ciencia Ficción"}`

#### 3.2.4 Breadcrumb & Clear Filters

Display selected folders in the active filters section:
```
Active filters:
✕ folder: en/Science Fiction   [clear]
✕ author: Asimov               [clear]
```

---

### 3.3 Folder Facet for Batch Operations

**Owner:** Dallas (Frontend) + Parker (Backend)  
**Scope:** Depends on sister issue (batch metadata editing)

The folder facet is the **primary selection mechanism** for batch operations:

1. User searches for all books → sees 847 results
2. User selects "en/Science Fiction" folder → filters to 125 books
3. "Select all 125 results" → enters batch edit mode
4. Edits metadata (category, tags, etc.) → applies to all 125 via batch PATCH

**No additional backend work required** for this issue. The folder facet itself is complete. Batch operations are a separate feature (see #593 or similar).

---

## 4. Implementation Notes

### 4.1 Schema & Indexing

**No schema changes needed.** The field already exists and is correctly indexed:

```xml
<field name="folder_path_s" type="string" multiValued="false" indexed="true" stored="true"/>
```

**Why this is sufficient:**
- `indexed="true"` → Solr facets work
- `stored="true"` → Results include folder_path
- `string` type → Exact matching (appropriate for paths with `/` separators)

### 4.2 Facet Limits & Performance

The `facet.limit` parameter (configurable via `settings.facet_limit`, default 100) applies to folder facets like other facets. With thousands of unique folder paths, facet generation might be slow, but:

- **First release:** Use default facet.limit (100 top folders by count)
- **Future optimization:** If performance issues arise, add `facet.prefix` parameter for prefix-based filtering (e.g., user types "en/" to see English folders only)

### 4.3 Path Normalization

The document-indexer already ensures:
- **Relative paths only** (no absolute file system paths)
- **Forward slashes** (`/`, not `\` on Windows)
- **No trailing slashes**
- **UTF-8 support** (handles accented folder names, CJK characters)

The search API should preserve these without additional normalization.

### 4.4 Empty Paths & Root Folder

If a PDF is in the library root (not in any subfolder), `metadata["folder_path"]` is set to `""` (empty string). In facets:
- Empty string will appear as a facet value (may want to label as "(root)" or hide)
- This is correct behavior — documents in the root should be selectable

### 4.5 Hierarchical Faceting: Solr PathHierarchy Option

**Current approach (Option A):** Client-side tree building from flat facet values.

**Alternative approach (Option C):** Use Solr's `PathHierarchyTokenizer` to enable native hierarchical faceting:

```xml
<fieldType name="folder_hierarchy" class="solr.TextField">
  <analyzer type="index">
    <tokenizer name="pathHierarchy" delimiter="/"/>
  </analyzer>
  <analyzer type="query">
    <tokenizer name="keyword"/>
  </analyzer>
</fieldType>

<field name="folder_hierarchy" type="folder_hierarchy" multiValued="true" indexed="true" stored="false"/>
<copyField source="folder_path_s" dest="folder_hierarchy"/>
```

**Tradeoff:**
- Option A (current): Simple backend, more frontend logic, flat facet values
- Option C: More complex schema, native Solr hierarchies, cleaner API

**Recommendation:** Start with Option A. If UI rendering performance becomes an issue with thousands of paths, upgrade to Option C in a follow-up release.

---

## 5. Acceptance Criteria

### Backend (Ash)
- [ ] Add `"folder": ("folder_path_s",)` to `FACET_FIELDS` in `search_service.py`
- [ ] Verify `build_filter_queries()` accepts `folder` filter without changes
- [ ] Facet endpoint (`/facets` and `/search`) returns folder facet counts
- [ ] Folder facet values are correctly escaped (special characters handled)
- [ ] All existing tests pass; no regression in other facets
- [ ] Verify with Solr admin UI: folder_path_s appears in facet results

### Frontend (Dallas)
- [ ] Flat folder facet renders in sidebar (list of paths + counts)
- [ ] Hierarchical tree view displays (expandable/collapsible folders)
- [ ] Clicking a folder applies filter: `fq=folder_path_s:"path"`
- [ ] Selected folder shown in active filters bar
- [ ] Multi-select works (multiple folders can be selected)
- [ ] Clear filters works for folder selections
- [ ] All existing tests pass; no regression in other facets

### Testing (Lambert)
- [ ] Unit: `parse_facet_counts()` correctly handles folder facet values
- [ ] Unit: `build_filter_queries()` correctly escapes folder paths
- [ ] Integration: End-to-end search with folder filter works
- [ ] UI: Tree rendering with deeply nested paths (3+ levels)
- [ ] UI: UTF-8 folder names display correctly
- [ ] UI: Empty root folder ("") is handled gracefully

---

## 6. Work Order

The tasks can be parallelized; no hard dependencies:

1. **Ash:** Add `folder` to `FACET_FIELDS` + verify with Solr (**parallel**)
2. **Dallas:** Implement flat facet list + tree view (**parallel, can start immediately**)
3. **Parker:** Filter query support (if not already working) (**parallel, low-risk**)
4. **Lambert:** All facet tests (**after** 1, 2, 3 are ready)
5. **Integration:** Test batch operation flow with folder selection (**after** 1-3 complete)

---

## 7. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Large number of unique folder paths → slow facet computation | Medium | Use `facet.limit` to cap results; add prefix filtering if needed |
| Special characters in folder names (quotes, slashes) → escaping issues | Low | Existing `solr_escape()` handles this; verify in tests |
| Folder hierarchy too deep → UI tree rendering slow | Low | Start with Option A (client-side); upgrade to Option C if needed |
| Empty folder paths (root documents) → confusing UX | Low | Label as "(root)" or hide; document behavior |
| Folder renamed on disk after indexing → stale facet values | Low | Same as any metadata change; will be fixed on re-index |

---

## 8. Related Issues & Dependencies

- **Sister issue:** #593 (Batch metadata editing — uses folder facet for selection)
- **Enables:** "Fix all books in this folder" admin workflow
- **Depends on:** Nothing (folder_path_s already indexed)

---

## 9. Team Review Questions

1. **Tree depth:** Should we cap the tree depth displayed (e.g., show only 2 levels initially)?
2. **Empty root folder:** How should documents in the library root be displayed in the folder tree?
3. **Performance threshold:** At what number of unique folder paths should we consider upgrading to Solr PathHierarchy (Option C)?
4. **Folder renaming:** Should we document the behavior when a user renames a folder and re-indexes?

---

## Appendix A: Current Facet Configuration

### FACET_FIELDS in search_service.py

```python
FACET_FIELDS: dict[str, tuple[str, ...]] = {
    "author": ("author_s",),
    "category": ("category_s",),
    "year": ("year_i",),
    "language": ("language_detected_s", "language_s"),
}
```

### How Facets Work

1. **Request:** User searches with filters `?filters=author:Asimov`
2. **Backend:** `build_filter_queries()` converts to Solr `fq=author_s:Asimov`
3. **Solr:** Returns counts for all other facet fields
4. **Response:** `parse_facet_counts()` returns nested structure:
   ```json
   {
     "facets": {
       "author": [{"value": "Asimov", "count": 12}, ...],
       "category": [{"value": "Science Fiction", "count": 47}, ...],
       ...
     }
   }
   ```

### Adding folder follows the exact same pattern:
- Add to `FACET_FIELDS` ✅
- `build_filter_queries()` automatically supports it ✅
- `parse_facet_counts()` automatically includes it ✅
- Frontend renders the new facet ✅

---

## Appendix B: Folder Path Examples

From real indexing runs:

```
"en/Science Fiction"
"en/History"
"en/Biography"
"en/Fiction/Classics"
"es/Ciencia Ficción"
"es/Historia"
"fr/Roman Policier"
"ca/Literatura"
"" (empty = root)
```

---
