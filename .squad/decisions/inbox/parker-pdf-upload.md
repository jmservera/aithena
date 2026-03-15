# Parker — PDF Upload Endpoint Implementation Decisions

**Date:** 2026-07-24  
**Author:** Parker (Backend Dev)  
**Context:** Issue #49 implementation — PDF upload endpoint for FastAPI backend  
**PR:** #197  
**Status:** PROPOSED — awaiting squad review

---

## Decision 1: Per-Request RabbitMQ Connections (Thread Safety)

**Context:**  
FastAPI runs multi-worker in production (gunicorn/uvicorn workers). Pika's `BlockingConnection` is NOT thread-safe and cannot be shared across workers or async contexts.

**Decision:**  
Create and close a RabbitMQ connection per upload request in `_publish_to_queue()`.

**Rationale:**
- Thread-safe by design (no shared state)
- Overhead (~50-100ms per upload) is acceptable for an async workflow
- Simpler than connection pooling (which requires complex thread-local or async-safe wrappers)
- Upload is a low-frequency operation (not a hot path)

**Alternatives Considered:**
- ❌ **Singleton connection pool:** Pika pooling libs are unmaintained or async-only (incompatible with `BlockingConnection`)
- ❌ **FastAPI dependency injection with lifespan:** Still requires per-worker pools, adds complexity
- ⚠️ **Async Pika (`aio-pika`):** Better for high-frequency operations but adds async complexity; overkill for upload endpoint

**Implementation:**
```python
def _publish_to_queue(file_path: Path) -> None:
    connection = pika.BlockingConnection(...)
    channel = connection.channel()
    channel.queue_declare(queue=settings.rabbitmq_queue_name, durable=True)
    channel.basic_publish(...)
    connection.close()
```

**Trade-offs:**
- ✅ Pro: Thread-safe, simple, no state management
- ✅ Pro: Connection failures are isolated to single request
- ⚠️ Con: ~50-100ms overhead per upload (acceptable for async workflow)
- ⚠️ Con: Not suitable for high-frequency operations (>100 uploads/sec)

**Monitoring Recommendation:**  
Track RabbitMQ connection latency in logs or APM to detect network issues.

---

## Decision 2: Triple Validation (MIME + Extension + Magic Number)

**Context:**  
HTTP clients can spoof `Content-Type` headers. Malicious actors could upload non-PDF files disguised as PDFs, causing indexer crashes or security issues.

**Decision:**  
Validate PDF files using THREE checks:
1. **MIME type:** `Content-Type: application/pdf`
2. **Extension:** Filename ends with `.pdf`
3. **Magic number:** File content starts with `%PDF-`

**Rationale:**
- **Defense in depth:** MIME and extension can be spoofed; magic number is authoritative
- **Fast:** Magic number check reads only first 5 bytes (no full file parsing)
- **Security:** Prevents malicious file uploads that could exploit Solr Tika or document-indexer

**Implementation:**
```python
if file.content_type != "application/pdf":
    raise HTTPException(400, "Invalid file type")
if not file.filename.lower().endswith(".pdf"):
    raise HTTPException(400, "Must have .pdf extension")
content = await file.read()
if not content.startswith(b"%PDF-"):
    raise HTTPException(400, "Invalid PDF header")
```

**Why Not Just Magic Number?**
- MIME/extension checks provide **early rejection** (before reading file content)
- Reduces bandwidth/memory for obviously invalid uploads
- Magic number is the **authoritative check** (MIME is a hint, magic is proof)

**Trade-offs:**
- ✅ Pro: Prevents content-type spoofing attacks
- ✅ Pro: Fast early rejection for invalid uploads
- ⚠️ Con: Reads entire file into memory (mitigated by 50MB size limit)

**Future Improvement:**  
Stream file validation (read first 5 bytes for magic number, then stream to disk) to avoid loading 50MB files into memory.

---

## Decision 3: Filename Collision Handling with Timestamps

**Context:**  
Multiple users may upload files with the same name (e.g., "report.pdf"). Overwriting existing files would lose data.

**Decision:**  
When a filename collision is detected:
1. Check if `upload_dir / filename` exists
2. If yes, append `_{YYYYMMDD}_{HHMMSS}` timestamp to the stem
3. Example: `report.pdf` → `report_20260724_143022.pdf`

**Rationale:**
- **No data loss:** Every upload is preserved
- **Predictable naming:** Timestamp format is sortable and human-readable
- **Simple:** No database or UUID overhead

**Alternatives Considered:**
- ❌ **UUID suffix:** Less readable (`report_a3f2e1d8.pdf`)
- ❌ **Overwrite existing:** Data loss risk
- ⚠️ **User-provided metadata:** Requires UI changes (deferred to Phase 5)

**Implementation:**
```python
target_path = settings.upload_dir / safe_filename
if target_path.exists():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_stem = target_path.stem
    target_path = settings.upload_dir / f"{name_stem}_{timestamp}.pdf"
```

**Edge Case:**  
Two uploads of "report.pdf" in the same second would still collide. Acceptable risk (sub-second uploads of identical filenames are rare; future fix: add milliseconds or UUID suffix).

**Trade-offs:**
- ✅ Pro: No data loss, readable filenames
- ✅ Pro: No external dependencies (database, UUID)
- ⚠️ Con: Sub-second collisions not handled (rare, low priority)

---

## Decision 4: File Cleanup on RabbitMQ Failure

**Context:**  
If file is written to disk but RabbitMQ publish fails, the file becomes an orphan (not indexed, takes up disk space).

**Decision:**  
Delete the uploaded file if RabbitMQ publish fails:
```python
try:
    _publish_to_queue(target_path)
except HTTPException:
    try:
        target_path.unlink(missing_ok=True)
    except Exception:
        pass  # Log but don't fail the request twice
    raise
```

**Rationale:**
- **Consistency:** Upload is atomic (file + queue message, or neither)
- **No orphans:** Failed uploads don't accumulate on disk
- **User clarity:** 502 error means "upload failed, try again" (not "file saved but not indexed")

**Alternatives Considered:**
- ❌ **Keep orphaned files:** User sees 502 but file is saved (confusing state)
- ⚠️ **Retry RabbitMQ publish:** Adds complexity; better to fail fast and let user retry

**Trade-offs:**
- ✅ Pro: Atomic operation (file + queue, or neither)
- ✅ Pro: No orphaned files on RabbitMQ downtime
- ⚠️ Con: User must re-upload on transient RabbitMQ errors (acceptable for reliability)

**Monitoring Recommendation:**  
Track 502 error rate to detect RabbitMQ outages.

---

## Decision 5: Reuse Existing `shortembeddings` Queue (No New Queue)

**Context:**  
The `document-lister` service already publishes to the `shortembeddings` RabbitMQ queue for file discovery. We could create a new queue for uploads.

**Decision:**  
Publish uploaded files to the existing `shortembeddings` queue.

**Rationale:**
- **Simplicity:** No new queue/consumer infrastructure
- **Consistency:** All indexing flows through the same queue
- **Existing consumer:** `document-indexer` already consumes this queue (no code changes needed)

**Why Not a Separate Queue?**
- ❌ **Overhead:** Separate consumer, separate monitoring, separate backlog tracking
- ❌ **Duplication:** document-indexer logic would need to be duplicated or abstracted
- ✅ **Single source of truth:** All PDFs (watched + uploaded) go through the same pipeline

**Implementation:**
```python
channel.basic_publish(
    exchange="",
    routing_key=settings.rabbitmq_queue_name,  # "shortembeddings"
    body=str(file_path),
    properties=pika.BasicProperties(delivery_mode=2),  # Persistent
)
```

**Trade-offs:**
- ✅ Pro: Reuses existing infrastructure (no new services)
- ✅ Pro: Consistent indexing pipeline (watched files + uploads)
- ⚠️ Con: Upload backlog is mixed with filesystem scan backlog (acceptable, same consumer)

---

## Decision 6: Frozen Dataclass Settings (Test Fixture Pattern)

**Context:**  
`Settings` is a `@dataclass(frozen=True)`, so tests can't use `monkeypatch.setattr()` or `patch()` to override config values.

**Decision:**  
Use `object.__setattr__(settings, "field", value)` in test fixtures to modify frozen settings.

**Rationale:**
- **Immutability in production:** Frozen dataclass prevents accidental config mutation
- **Test flexibility:** `object.__setattr__` bypasses frozen check for isolated test changes
- **Cleaner than env vars:** Test-specific values without polluting `os.environ`

**Implementation:**
```python
@pytest.fixture
def upload_dir(tmp_path):
    from config import settings
    upload_path = tmp_path / "uploads"
    upload_path.mkdir(exist_ok=True)
    object.__setattr__(settings, "upload_dir", upload_path)
    yield upload_path
```

**Alternatives Considered:**
- ❌ **Remove `frozen=True`:** Allows accidental config mutation in production
- ❌ **Environment variables in tests:** Pollutes global state, harder to isolate tests
- ⚠️ **Recreate settings per test:** Expensive (requires re-parsing all env vars)

**Trade-offs:**
- ✅ Pro: Immutable config in production (prevents bugs)
- ✅ Pro: Flexible test fixtures (isolated per-test changes)
- ⚠️ Con: `object.__setattr__` is a "magic method" (less readable than monkeypatch)

**Convention:**  
Always restore original values in fixture teardown to avoid test pollution.

---

## Summary of Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| Per-request RabbitMQ connections | Thread-safe, simple | ~50-100ms overhead |
| Triple validation (MIME + ext + magic) | Prevents content-type spoofing | Reads full file into memory |
| Timestamp collision handling | No data loss, readable filenames | Sub-second collisions not handled |
| File cleanup on RabbitMQ failure | Atomic uploads, no orphans | User must retry on transient errors |
| Reuse `shortembeddings` queue | Simplicity, no new infrastructure | Upload/watch backlog mixed |
| Frozen dataclass settings | Immutable config in production | Test fixtures use `object.__setattr__` |

---

## Open Questions / Future Work

1. **Stream validation:** Read first 5 bytes for magic number, then stream to disk (avoid 50MB memory load)
2. **Upload metrics:** Log upload count, size distribution, RabbitMQ latency for monitoring
3. **E2E test:** Full pipeline test (upload → queue → indexing → search) in `e2e/`
4. **UI integration:** Frontend upload form (issue #50) + status polling via `/v1/status`
5. **Metadata override:** Allow users to specify title/author/category in upload form (deferred to Phase 5)
6. **Batch uploads:** Support multiple files in single request (low priority, nice-to-have)

---

## Approval Status

- ✅ **Implementation complete:** PR #197 ready for review
- ⏳ **Squad review pending:** Awaiting Dallas (UI), Ash (Solr), Ripley (Lead) review
- ⏳ **Merge to dev:** After approval, before v0.6.0 release

---

**Next Steps:**
1. Scribe merges this decision into `.squad/decisions.md`
2. Squad reviews PR #197
3. Merge to `dev` after approval
4. UI integration (issue #50) picks up after backend merge
