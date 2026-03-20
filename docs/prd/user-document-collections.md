# PRD: User Document Collections — Personal Bookshelves with Notes

_Date:_ 2026-03-20  
_Prepared by:_ Ripley (Project Lead)  
_Milestone:_ v1.10.0  
_Related Issue:_ #591

---

## 1. Problem Statement

Aithena is a powerful search engine for book discovery, but it lacks persistent organization and annotation capabilities. Users can find documents via semantic and keyword search, but cannot:

- **Organize** findings into thematic collections (research topics, course reading lists, themed bookshelves)
- **Annotate** individual documents with personal notes or insights
- **Revisit** curated reading lists without running searches again
- **Share** or export their collections for collaboration

Researchers, librarians, educators, and readers need lightweight, integrated bookmarking and note-taking to capture the value of their searches.

---

## 2. Current State

### Existing Capabilities
- **Search:** Keyword + semantic hybrid search via Solr with RRF fusion
- **Authentication:** JWT-based user identity (v1.9.0+)
- **Persistence:** SQLite auth database (`/data/auth/users.db`)
- **Frontend:** React 18 + TypeScript, reactive search results
- **Backend API:** FastAPI on solr-search service (v1.3.0+)

### Gaps
- No user-centric data model beyond authentication
- Search results are stateless — cannot be bookmarked
- No note-taking capability
- No multi-document collection structure
- No persistent user-document relationships

---

## 3. Proposed Architecture

### 3.1 Data Model

**New SQLite Database:** `collections.db` (separate from auth.db)  
Located at `/data/collections/collections.db`

```sql
-- Collections (personal bookshelves)
CREATE TABLE collections (
    id TEXT PRIMARY KEY,                 -- UUID4
    user_id TEXT NOT NULL,              -- FK to auth.users(id)
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK (length(name) > 0 AND length(name) <= 255)
);

-- Collection items (documents within collections with optional notes)
CREATE TABLE collection_items (
    id TEXT PRIMARY KEY,                 -- UUID4
    collection_id TEXT NOT NULL,
    document_id TEXT NOT NULL,           -- Solr document ID (e.g., docid_s value)
    position INTEGER DEFAULT 0,          -- Sort order within collection
    note TEXT DEFAULT '',                -- Per-document notes (plain text)
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(collection_id, document_id)   -- Prevent duplicate documents in collection
);

-- Indexes for common query patterns
CREATE INDEX idx_collections_user_id ON collections(user_id);
CREATE INDEX idx_collection_items_collection_id ON collection_items(collection_id);
CREATE INDEX idx_collection_items_position ON collection_items(position);
CREATE INDEX idx_collection_items_document_id ON collection_items(document_id);
```

**Rationale:**
- **Separate DB:** Keeps collections isolated from auth; allows independent schema evolution
- **UUID4 IDs:** Consistent with existing auth patterns
- **Position field:** Enables drag-and-drop reordering without ETags or full list rewrites
- **Plain text notes:** Avoids Markdown rendering complexity; sanitization not required
- **UNIQUE constraint:** Prevents accidental duplicate document insertion
- **Created/Updated timestamps:** Supports sorting by recency and last-modified queries
- **Cascading deletes:** Ensure data consistency when collections or users are deleted

### 3.2 Backend Service Architecture

**Service:** solr-search (no new service required)  
**Database Location:** `/data/collections/collections.db` (mounted volume)  
**Config Extension:** Add to `config.py`:
- `collections_db_path` (default: `/data/collections/collections.db`)
- `collections_note_max_length` (default: 5000 characters)

**Module:** New `collections.py` module  
- SQLite schema initialization and migrations
- Connection pool with double-checked locking (per Redis pattern in codebase)
- CRUD functions for collections and items

**Authentication:** All collection endpoints require `@_authenticate_request` middleware  
Users can only view/edit their own collections (checked via `user_id` in request context)

### 3.3 REST API Design

#### Collections Endpoints

```
GET    /v1/collections
       Response: { collections: [{ id, name, description, item_count, created_at, updated_at }] }
       Auth: Required
       Rate limit: 100/minute (standard)
       Filters: ?sort_by=name|created_at|updated_at (default: updated_at DESC)

POST   /v1/collections
       Body: { name: string, description?: string }
       Response: { id, name, description, created_at, updated_at }
       Auth: Required
       Validation: name required, 1-255 chars; description ≤ 1000 chars
       Rate limit: 10/minute (write-protected)

GET    /v1/collections/{collection_id}
       Response: { id, name, description, items: [...], created_at, updated_at }
       Auth: Required (owner check)
       Item schema: { id, document_id, position, note, added_at, updated_at }
       Rate limit: 100/minute

PUT    /v1/collections/{collection_id}
       Body: { name?: string, description?: string }
       Response: { id, name, description, updated_at }
       Auth: Required (owner check)
       Validation: Same as POST
       Rate limit: 10/minute

DELETE /v1/collections/{collection_id}
       Response: { deleted: true }
       Auth: Required (owner check)
       Rate limit: 10/minute
       Note: Cascades to all collection_items
```

#### Collection Items Endpoints

```
POST   /v1/collections/{collection_id}/items
       Body: { document_ids: string[] }
       Response: { items_added: number, duplicates_skipped: number, items: [...] }
       Auth: Required (owner check)
       Behavior: Silently skip duplicates (document_ids already in collection)
       Max items per request: 50
       Rate limit: 20/minute

DELETE /v1/collections/{collection_id}/items/{item_id}
       Response: { deleted: true }
       Auth: Required (owner check)
       Rate limit: 20/minute

PUT    /v1/collections/{collection_id}/items/{item_id}
       Body: { note?: string, position?: integer }
       Response: { id, document_id, note, position, updated_at }
       Auth: Required (owner check)
       Validation: note ≤ 5000 chars, position ≥ 0
       Rate limit: 20/minute

PUT    /v1/collections/{collection_id}/items/reorder
       Body: { item_ids: string[] }
       Response: { reordered: number }
       Auth: Required (owner check)
       Behavior: Assign positions [0, 1, 2, ...] to items in provided order
       Validation: All item_ids must belong to collection, no duplicates in request
       Rate limit: 20/minute
```

#### Search Integration Endpoint

```
GET    /v1/search?...
       New response field (optional): in_collections?: string[] (list of collection IDs containing this document)
       Auth: Required
       Behavior: Added to each search result document; empty array if document not in any user's collections
       Performance: Left join to collection_items for current user_id
       Rate limit: 100/minute (existing)
```

---

## 4. Frontend Design

### 4.1 New Pages & Routes

| Route | Component | Purpose | Auth |
|-------|-----------|---------|------|
| `/collections` | `CollectionsPage` | List all user's collections; create new collection | Required |
| `/collections/{id}` | `CollectionDetailPage` | View/edit collection; manage items and notes | Required |

### 4.2 New Components

| Component | Location | Purpose | Props |
|-----------|----------|---------|-------|
| **CollectionsGrid** | `src/Components/` | Responsive card grid of collections | collections, onSelect, onCreate |
| **CollectionDetailView** | `src/Components/` | Collection header + sortable item list | collection, onUpdate, onDelete |
| **CollectionItemCard** | `src/Components/` | Individual document card with note editor | item, onUpdate, onDelete |
| **AddToCollectionModal** | `src/Components/` | Modal triggered from search results | documentId(s), onAdd | |
| **CollectionBadge** | `src/Components/` | Small pill showing collection membership | collectionNames |
| **NoteEditor** | `src/Components/` | Inline/expanded text editor for notes | note, onSave, placeholder |
| **CollectionPicker** | `src/Components/` | Dropdown/search to select target collection | userCollections, onSelect |

### 4.3 UX Flows

#### Flow 1: Create Collection from Search

```
User searches for books
  ↓
Clicks "📁 Save to collection" on a result (or selects multiple with checkboxes)
  ↓
AddToCollectionModal opens:
  - Shows user's existing collections (searchable list)
  - Button: "+ Create new collection"
  ↓
User picks existing collection OR creates new one
  ↓
Toast: "✓ Added to My Research Books"
  ↓
Search result shows small collection badge (hover: "In 1 collection")
```

#### Flow 2: Manage Collections

```
Click "📚 Collections" in main nav
  ↓
CollectionsPage shows:
  - Grid of collection cards (name, description preview, item count, last updated)
  - Button: "+ New collection"
  - Options on hover: Edit, Delete, Open
  ↓
Click collection card
  ↓
CollectionDetailPage shows:
  - Header: name, description, edit/delete buttons
  - Sortable list of items (title, author, year, cover thumbnail)
  - Each item has:
    - Small note preview (truncated)
    - "+" button to expand/edit note
    - "Remove" button
    - Drag handle (reorder)
  ↓
Click note expand
  ↓
NoteEditor overlays inline:
  - Text area for editing
  - "Save" / "Cancel" buttons
  - Auto-saves on blur (optimistic, with error handling)
  ↓
Click item title
  ↓
Navigates to PDF viewer (existing flow) with collection context preserved
```

#### Flow 3: Add Notes in Collection Detail

```
In CollectionDetailPage, user hovers over item
  ↓
"Edit note" button appears
  ↓
Click → NoteEditor expands inline
  ↓
User types note (up to 5000 chars)
  ↓
Click "Save" or blur
  ↓
Note persisted via PUT /v1/collections/{id}/items/{item_id}
  ↓
Toast: "✓ Note saved"
```

### 4.4 Navigation Integration

**Main Navigation (TabNav.tsx):**
Add new link between "Search" and "Admin":
```
[Search] | [Collections] | [Admin] | [Profile]
```

**Search Results Context:**
Each BookCard shows optional collection badge:
```
[Book Title]
Author, Year
┌─────────────┐
│ In 2 collections ↓ │  ← Click for quick add
└─────────────┘
```

---

## 5. Database Migration & Initialization

### 5.1 Schema Migration

**File:** `src/solr-search/migrations/001_collections_init.py`

```python
def upgrade(connection: sqlite3.Connection) -> None:
    """Initialize collections and collection_items tables."""
    cursor = connection.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS collections (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (length(name) > 0 AND length(name) <= 255),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS collection_items (
        id TEXT PRIMARY KEY,
        collection_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        position INTEGER DEFAULT 0,
        note TEXT DEFAULT '',
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(collection_id, document_id),
        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_collections_user_id ON collections(user_id);
    CREATE INDEX IF NOT EXISTS idx_collection_items_collection_id ON collection_items(collection_id);
    CREATE INDEX IF NOT EXISTS idx_collection_items_position ON collection_items(position);
    CREATE INDEX IF NOT EXISTS idx_collection_items_document_id ON collection_items(document_id);
    """)
    connection.commit()

def downgrade(connection: sqlite3.Connection) -> None:
    """Drop collections and collection_items tables."""
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS collection_items;")
    cursor.execute("DROP TABLE IF EXISTS collections;")
    connection.commit()
```

**Execution:** Run on solr-search startup (via `main.py` lifespan event)  
**Safety:** Check schema_version table (existing auth pattern) before applying

### 5.2 Database Location

**Development:** `/data/collections/collections.db` (docker-compose volume)  
**Docker Volume:** New volume `collections-db` in `docker-compose.yml`  
**Permissions:** `644` (readable/writable by solr-search container)

---

## 6. Implementation Phases

### Phase 1: Backend Data Model & CRUD API (Week 1)
**Owner:** Parker (Backend Developer)

**Deliverables:**
- [ ] Schema migration and initialization (`migrations/001_collections_init.py`)
- [ ] `collections.py` module with SQLite wrapper and connection pool
- [ ] CRUD endpoints: POST, GET, PUT, DELETE for collections
- [ ] CRUD endpoints: POST, DELETE, PUT for collection items
- [ ] Unit tests (≥80% coverage)
- [ ] API integration tests (test with real Solr data)

**Review Gate:** Kane (Security — access control validation)

**PR:** `squad/591-phase1-collections-api`

---

### Phase 2: Access Control & Security Review (Week 1, concurrent)
**Owner:** Kane (Security Engineer)

**Deliverables:**
- [ ] Access control middleware: users can only view/edit own collections
- [ ] Input validation: name, description, note length limits
- [ ] Rate limiting: write endpoints (10/min collections, 20/min items)
- [ ] SQL injection prevention review
- [ ] Security test cases (unauthorized access, boundary conditions)

**Dependencies:** Blocks phase 3 (frontend)

**PR:** `squad/591-phase2-access-control` (or merged with phase 1)

---

### Phase 3: Frontend — Collections Pages (Week 2)
**Owner:** Dallas (Frontend Developer)

**Deliverables:**
- [ ] `CollectionsPage` (list/grid of user's collections)
- [ ] `CollectionDetailPage` (collection view with item list)
- [ ] Create/edit/delete collection modals
- [ ] CollectionsGrid and CollectionDetailView components
- [ ] Navigation integration (TabNav.tsx)
- [ ] Styling (responsive, light/dark mode support)
- [ ] Vitest unit tests (≥70% coverage)
- [ ] React Testing Library tests for critical flows

**Dependencies:** Phase 1 (API available)

**PR:** `squad/591-phase3-collections-ui`

---

### Phase 4: Frontend — Search Integration (Week 2, concurrent)
**Owner:** Dallas (Frontend Developer)

**Deliverables:**
- [ ] AddToCollectionModal component
- [ ] Integration with search results page (add "Save to collection" action)
- [ ] CollectionBadge component (shows in search results)
- [ ] NoteEditor component (inline/expanded)
- [ ] "Add note" flow in CollectionDetailPage
- [ ] Toast notifications for actions
- [ ] Vitest tests (flow tests with mocked API)

**Dependencies:** Phase 1 (API available), Phase 3 (collections pages)

**PR:** `squad/591-phase4-search-integration`

---

### Phase 5: Search Result Enrichment (Week 3)
**Owner:** Ash (Search Engineer)

**Deliverables:**
- [ ] Modify `/v1/search` to include `in_collections` field
- [ ] Left join query: collection_items for current user_id
- [ ] Performance testing: no regression on search latency
- [ ] Unit tests (mock Solr responses)

**Dependencies:** Phase 1 (API available)

**PR:** `squad/591-phase5-search-enrichment`

---

### Phase 6: Testing & Documentation (Week 3)
**Owner:** Lambert (QA/Test Engineer)

**Deliverables:**
- [ ] Full API test suite (pytest, ≥90% coverage)
- [ ] Playwright E2E tests (create/edit/delete collection, add notes)
- [ ] Search integration E2E tests (add from search, verify badge)
- [ ] User manual update (`docs/user-manual.md`)
- [ ] Admin manual addendum (optional: bulk collection export?)
- [ ] Test report for release notes

**Dependencies:** All phases complete

**PR:** `squad/591-phase6-testing-docs`

---

## 7. Success Criteria

### Functional Acceptance
- [ ] User can create collection with name and optional description
- [ ] User can view all own collections in grid/list format
- [ ] User can view collection detail with all items and notes
- [ ] User can add one or more documents from search results to a collection
- [ ] User can add, edit, and delete notes on documents within a collection
- [ ] User can reorder documents within a collection (drag-and-drop or positional API)
- [ ] User can delete collections (with confirmation)
- [ ] Collection badges appear on search results
- [ ] Users cannot view/edit other users' collections (security)

### Performance Acceptance
- [ ] GET /v1/collections completes in <100ms (10+ collections)
- [ ] GET /v1/collections/{id} completes in <200ms (100+ items)
- [ ] POST /v1/collections/{id}/items completes in <150ms
- [ ] Search result enrichment (in_collections) adds <50ms to search query

### Code Quality Acceptance
- [ ] Backend unit tests: ≥80% coverage (solr-search)
- [ ] Frontend unit tests: ≥70% coverage (aithena-ui)
- [ ] All API endpoints documented in OpenAPI spec
- [ ] No security warnings from Bandit or Checkov
- [ ] Ruff lint passing on all Python code

### UX Acceptance
- [ ] Collections page renders within 1 second (including API call)
- [ ] AddToCollectionModal responsive on mobile (<600px width)
- [ ] Note editor usable on touch devices
- [ ] Dark mode support on all new components
- [ ] Proper i18n placeholders for future translation

---

## 8. Data Privacy & Security Considerations

### User Data Isolation
- All queries filtered by `user_id` from JWT token
- Collections foreign key to auth.users ensures data ownership
- DELETE user flow (future) cascades to remove all collections

### Input Validation
- Collection name: 1-255 characters (required)
- Description: ≤1000 characters
- Note text: ≤5000 characters
- Document IDs: Validated against Solr document schema
- Position (reorder): Non-negative integer

### Rate Limiting
- Read endpoints: 100/minute (standard)
- Write endpoints: 10/minute (collections), 20/minute (items)
- Bulk operations (add multiple documents): 50 items per request max

### Audit Trail (Future)
- Potential enhancement: Log collection_items additions/deletions for audit
- Out of scope for v1.10.0, can be added in v1.11.0

---

## 9. Out of Scope (v1.10.0)

- [ ] Collection sharing (sharing collections with other users)
- [ ] Collection export (BibTeX, CSV, PDF export)
- [ ] Collection search (full-text search within collection items)
- [ ] Markdown support for notes (plain text only)
- [ ] Collection templates (pre-made collection structures)
- [ ] Collaborative editing (multiple users in one collection)
- [ ] Mobile-native app (web-only in v1.10.0)
- [ ] Bulk import collections (future feature)

---

## 10. Related Issues & Dependencies

**Depends On:**
- v1.9.0 authentication system (user identity established)

**Future Work:**
- #XXX (future): Collection sharing and permissions
- #XXX (future): Collection export and bibliography formats
- #XXX (future): Full-text search within collections
- #XXX (future): Markdown note support with sanitization

**Related Issues:**
- #590: User authentication system (v1.9.0)
- #592: Admin dashboard updates
- #593: Release documentation for v1.10.0

---

## 11. Team Roster & Assignments

| Role | Member | Domain | Notes |
|------|--------|--------|-------|
| **Project Lead** | Ripley | Architecture, roadmap, release planning | Leading this PRD; phase oversight |
| **Product Manager** | Newt | UX validation, acceptance criteria | UX flow review, user testing |
| **Backend Dev** | Parker | Data model, API, database | Phase 1 owner (CRUD API) |
| **Security Engineer** | Kane | Access control, input validation, CVEs | Phase 2 owner (security review) |
| **Frontend Dev** | Dallas | React, TypeScript, components, routing | Phase 3-4 owner (UI & search integration) |
| **Search Engineer** | Ash | Solr, RRF fusion, search optimization | Phase 5 owner (search enrichment) |
| **QA/Test Engineer** | Lambert | Pytest, Playwright, test coverage, docs | Phase 6 owner (testing & docs) |

**Scribe:** (TBD by Ralph at issue assignment)

---

## 12. Open Questions for Team Review

1. **Note format:** Plain text (v1.10.0) or prepare data model for Markdown (v1.11.0)?
2. **Ordering UX:** Drag-and-drop reorder (complex, mobile-unfriendly) or sort-by dropdown (name, date added, date updated)?
3. **Collection limits:** Any soft/hard limits? (e.g., max 100 collections per user, max 1000 items per collection?)
4. **Offline capability:** Should collections sync to offline-first local storage (future PWA feature)?
5. **Share intent:** Should we add a `public` flag to the data model now (for v1.11.0 sharing), or design it later?
6. **Bulk operations:** Allow multi-select in search results to add 10+ docs at once, or one-at-a-time only?
7. **Soft delete:** Archive collections instead of permanent delete (future feature)?
8. **API versioning:** New endpoints as /v1/collections or future-proof as /v2/collections?

---

## 13. Appendix: API Response Examples

### POST /v1/collections (Create)
**Request:**
```json
{
  "name": "My AI Research",
  "description": "Papers and books on machine learning and neural networks"
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My AI Research",
  "description": "Papers and books on machine learning and neural networks",
  "created_at": "2026-03-20T14:30:00Z",
  "updated_at": "2026-03-20T14:30:00Z"
}
```

### GET /v1/collections (List)
**Response:**
```json
{
  "collections": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "My AI Research",
      "description": "Papers and books on...",
      "item_count": 23,
      "created_at": "2026-03-20T14:30:00Z",
      "updated_at": "2026-03-21T09:15:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Course Reading List",
      "description": "CS 301: Database Systems",
      "item_count": 12,
      "created_at": "2026-03-19T10:00:00Z",
      "updated_at": "2026-03-19T10:00:00Z"
    }
  ]
}
```

### GET /v1/collections/{id} (Detail)
**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My AI Research",
  "description": "Papers and books on machine learning...",
  "items": [
    {
      "id": "item-001",
      "document_id": "doc_12345",
      "position": 0,
      "note": "Great introduction to transformers. Key reference for literature review.",
      "added_at": "2026-03-20T14:35:00Z",
      "updated_at": "2026-03-21T08:45:00Z"
    },
    {
      "id": "item-002",
      "document_id": "doc_12346",
      "position": 1,
      "note": "Focus on chapter 3 (attention mechanisms).",
      "added_at": "2026-03-20T15:00:00Z",
      "updated_at": "2026-03-20T15:00:00Z"
    }
  ],
  "created_at": "2026-03-20T14:30:00Z",
  "updated_at": "2026-03-21T09:15:00Z"
}
```

### POST /v1/collections/{id}/items (Add Documents)
**Request:**
```json
{
  "document_ids": ["doc_12345", "doc_12346", "doc_12347"]
}
```

**Response:**
```json
{
  "items_added": 3,
  "duplicates_skipped": 0,
  "items": [
    {
      "id": "item-001",
      "document_id": "doc_12345",
      "position": 0,
      "note": "",
      "added_at": "2026-03-21T10:00:00Z",
      "updated_at": "2026-03-21T10:00:00Z"
    }
  ]
}
```

### PUT /v1/collections/{id}/items/{item_id} (Update Note)
**Request:**
```json
{
  "note": "Updated note text here"
}
```

**Response:**
```json
{
  "id": "item-001",
  "document_id": "doc_12345",
  "note": "Updated note text here",
  "position": 0,
  "updated_at": "2026-03-21T10:05:00Z"
}
```

### PUT /v1/collections/{id}/items/reorder (Reorder)
**Request:**
```json
{
  "item_ids": ["item-003", "item-001", "item-002"]
}
```

**Response:**
```json
{
  "reordered": 3
}
```

---

## 14. Release Artifacts

### Documentation
- [ ] User manual update: Collections section with screenshots
- [ ] API documentation (OpenAPI spec auto-generated from FastAPI)
- [ ] Admin manual: Optional bulk export feature planning
- [ ] CHANGELOG entry with user-facing feature description

### Testing
- [ ] Unit test report (pytest coverage)
- [ ] E2E test report (Playwright screenshots)
- [ ] Security scan results (Bandit, Checkov)
- [ ] Performance baseline (search query latency before/after enrichment)

### Screenshots (for Release Notes)
- [ ] Collections page (grid view)
- [ ] Collection detail view (with items and notes)
- [ ] Add to collection modal (from search results)
- [ ] Collection badges on search results

---

**Document Status:** READY FOR REVIEW  
**Next Step:** Team discussion on open questions (Section 12), then phase decomposition and issue creation.
