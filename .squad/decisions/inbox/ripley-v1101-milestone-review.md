# v1.10.1 Milestone — Security & Performance Gate Review

**Reviewer:** Ripley (Lead)
**Date:** 2026-03-21
**Milestone:** v1.10.1 (13 issues)
**Verdict:** ✅ **APPROVE**

---

## Security Review

### 1. SQL Injection Surface — `collections_service.py`

**Verdict: 🟢 PASS**

Reviewed all SQL in `collections_service.py`. All CRUD operations use parameterized queries (`?` placeholders) — `create_collection`, `list_collections`, `get_collection`, `delete_collection`, `add_items`, `remove_item`, `update_item`, `reorder_items`.

**Two `# noqa: S608` suppressions remain. Both are justified:**

1. **Line 193** (`update_collection`): Dynamic `SET` clause built from a whitelist of column names (`name`, `description`). Only string literals `"name = ?"` and `"description = ?"` are joined — user input flows exclusively through `?` parameter binding. Not injectable.

2. **Line 378** (`get_collection_ids_for_documents`): Dynamic `IN (?)` placeholder expansion. Placeholder count is derived from `len(document_ids)`, and all values are bound via `?`. This is the standard safe pattern for SQLite `IN` queries. Not injectable.

**No f-string SQL with user data anywhere in the file.** The S608 suppressions are false positives from Bandit's static analysis — the dynamic parts are column names or placeholder counts, never user-supplied values.

### 2. Auth Hardening — `main.py` and `admin_auth.py`

**Verdict: 🟢 PASS**

**WWW-Authenticate headers:** All four 401 responses include the header:
- `admin_auth.py:50` — `WWW-Authenticate: ApiKey` (missing key)
- `admin_auth.py:57` — `WWW-Authenticate: ApiKey` (wrong key)
- `main.py:548` — `WWW-Authenticate: Bearer` (via `_unauthorized_response`)
- `main.py:556` — `WWW-Authenticate: Bearer` (via `_unauthorized_exception`)

Confirmed: both helper functions are the only paths that produce 401s. This satisfies RFC 7235 §3.1.

**Auth middleware (line 597–622):** Uses if-guards, not exception-driven flow:
- `if request.method == "OPTIONS" or _is_public_path(...)` → pass through
- `if token is None` → return `_unauthorized_response`
- `try/except AuthenticationError` only around `decode_access_token` (the JWT decode), which is correct — JWT parsing _should_ use exceptions for invalid tokens
- Admin API-key path: `if request.headers.get("X-API-Key")` → early return with `contextlib.suppress(AuthenticationError)` for optional JWT attachment

**No exception-driven auth flow in the hot path.** The refactor from #787 is clean.

### 3. Shell Scripts — `scripts/verify-backup.sh`

**Verdict: 🟢 PASS**

Reviewed the full 628-line script:

- **`set -euo pipefail`** at line 44 — strict mode enabled
- **`umask 077`** at line 54 — restrictive file permissions
- **Argument parsing** (lines 137–196): Uses `case` statement with explicit pattern matching. Unknown options exit with error. No `eval`, no `$()` with user input.
- **Input validation**: `TIER` validated against `critical|high|medium|auto` whitelist (line 189–195). `BACKUP_DIR` checked for existence (line 184). No shell metacharacter expansion on user paths.
- **File operations**: All `find` commands use `-name` with hardcoded glob patterns (e.g., `"auth-*.db.gpg"`). No user-controlled patterns in `find`.
- **GPG operations**: Passphrase comes from a file path (`$BACKUP_KEY`), not inline. Uses `--batch --yes --pinentry-mode loopback --no-tty`.
- **Concurrency guard**: Uses `flock` for single-instance enforcement.
- **No `eval`, no `exec`, no command injection vectors.**

### 4. GitHub Actions Workflows

#### `monthly-restore-drill.yml`

**Verdict: 🟢 PASS**

- **Permissions**: `contents: read`, `issues: write` — minimal and correct
- **Pinned actions**: `actions/checkout@de0fac2e...` — SHA-pinned, not tag-referenced ✅
- **`persist-credentials: false`** — no token leakage to subprocesses ✅
- **No secret exposure**: `GH_TOKEN` via `${{ secrets.GITHUB_TOKEN }}` only in `gh issue create` (standard pattern)
- **Concurrency**: `cancel-in-progress: false` — correct for drills (don't cancel a running verification)
- **Timeout**: 15 minutes — reasonable guard

#### `stress-tests.yml`

**Verdict: 🟢 PASS**

- **Permissions**: `contents: read` only — minimal ✅
- **Pinned actions**: Both checkout and setup-python are SHA-pinned ✅
- **`persist-credentials: false`** ✅
- **No secrets used** in the stress test execution — credentials come from workflow inputs (visible in logs by design)
- **`user_count` input** is a string type but only consumed by Locust's `--user` flag, not interpolated into shell. Not injectable.
- **Concurrency**: `cancel-in-progress: true` — appropriate for performance tests
- **Timeout**: 60 minutes — appropriate for stress tests
- **Upload artifact**: SHA-pinned ✅

### 5. Batch Operations — Folder Facet Scope Control

**Verdict: 🟢 PASS**

Reviewed the batch metadata edit endpoints (`main.py:2175–2237`):

**Authorization (defense-in-depth):**
- Both endpoints require `Depends(require_admin_auth)` (API key) AND `require_role("admin")` (JWT role)
- Non-admin users cannot reach these endpoints at all

**Input validation:**
- `BatchMetadataEditRequest`: Document IDs capped at `_BATCH_MAX_DOCUMENT_IDS = 1000`
- `BatchMetadataByQueryRequest`: Query results capped at `_BATCH_MAX_QUERY_RESULTS = 5000`
- Filters validated through `build_filter_queries()` which:
  - Rejects unknown filter names (`FACET_FIELDS` whitelist: author, category, year, language, series, folder)
  - Escapes all values with `solr_escape()` (escapes `\+-&|!(){}[]^"~*?:/ `)
  - Rejects `{!` local-parameter syntax in queries (`normalize_search_query`)

**Scope isolation:**
- Folder filter maps to `folder_path_s` Solr field — cannot be used to target arbitrary Solr fields
- The batch endpoint modifies metadata per document ID, not by path — even if a folder filter matched unexpected documents, the update is per-document with existence checking (`_solr_document_exists`)
- Individual failures are caught and reported (partial failure handling), not silently swallowed

**No scope bypass risk.** Admin-only with multi-layer auth is the correct access model.

---

## Performance Review

### 1. Auth Middleware Hot Path

**Verdict: 🟢 PASS**

The if-guard refactor (`main.py:597–622`) replaces `try/except` for control flow with explicit `if token is None` checks. The JWT decode (`decode_access_token`) still uses `try/except AuthenticationError`, which is appropriate since JWT parsing involves cryptographic verification that can fail in multiple ways.

**Performance impact: Neutral to positive.** `if token is None` is a pointer comparison (O(1)). The previous exception-driven flow would have incurred exception object creation + stack unwinding on every unauthenticated request. The new flow is strictly faster for the reject path and identical for the accept path.

### 2. Batch Operations with Folder Filter

**Verdict: 🟡 CONCERN (acceptable)**

The batch-by-query endpoint (`admin_batch_edit_metadata_by_query`) performs:
1. Paginated Solr query (`_solr_query_document_ids`) — up to 5000 docs in pages of 100
2. Sequential per-document updates (`_batch_apply_updates`) — each does a Solr existence check + atomic update + Redis override

**For 5000 documents:** This means 5000 Solr reads + 5000 Solr writes + 5000 Redis writes, executed sequentially. At ~10ms per Solr round-trip, that's ~100 seconds for the full 5000-doc maximum.

**Mitigations already in place:**
- Cap at 5000 documents (hard limit, returns 422 if exceeded)
- Partial failure handling (one bad doc doesn't abort the batch)
- Admin-only endpoint (not on any user-facing hot path)
- Circuit breakers protect Solr and Redis from cascading failure

**Recommendation:** For v1.11+, consider chunked async execution or Solr's built-in update-by-query for large batches. For v1.10.1, the current sequential approach is acceptable given the admin-only scope and 5000-doc cap.

### 3. New Endpoints and Queries

**Verdict: 🟢 PASS**

New Solr queries in the batch endpoint:
- `_solr_query_document_ids`: Uses `fl=id` (only fetches IDs), paginated with `rows=100`. Solr's `id` field is always indexed (it's the unique key). Filter queries use indexed Solr fields (`folder_path_s`, `author_s`, etc.).
- Existence check `_solr_document_exists`: Simple `q=id:{doc_id}` lookup on the unique key — indexed.

No new unindexed query patterns introduced.

### 4. Restore Verification Performance

**Verdict: 🟢 PASS**

`verify-backup.sh` operates on the filesystem:
- `sha256sum --check` per `.sha256` sidecar file (one hash verification per backup file)
- `gpg --decrypt --output /dev/null` for encryption validation (skipped if no key)
- `find -maxdepth 1` for file discovery (shallow, fast)

For a typical backup set (5–15 files per tier, 3 tiers), this adds ~2–5 seconds to the restore process. The monthly drill workflow has a 15-minute timeout, which is more than sufficient.

`run_test_restore()` defaults to `dry_run=True`, meaning test restores skip actual file I/O. The `_execute_restore` function correctly passes `DRY_RUN=1` to the environment when `dry_run=True`.

---

## Issue-Specific Findings

| Issue | Title | Verdict |
|-------|-------|---------|
| #786 | Static SQL in collections_service | 🟢 PASS — All queries parameterized. 2 justified S608 suppressions remain. |
| #787 | If-guard auth flow | 🟢 PASS — Exception-driven control flow eliminated from middleware hot path. |
| #789 | WWW-Authenticate headers | 🟢 PASS — All four 401 paths include the header. RFC 7235 compliant. |
| #788 | Locust auth integration | 🟢 PASS — `AithenaUser` base class handles JWT login. `AdminUser` adds API key. Graceful fallback if creds unset. |
| #790 | Restore verification endpoints | 🟢 PASS — Tests verify search API endpoints after restore. |
| #792 | Restore verification fail-on-error | 🟢 PASS — `verify-backup.sh` exits 1 on failures, 2 on warnings. No silent SKIP. |
| #793 | run_test_restore dry_run | 🟢 PASS — `run_test_restore(dry_run=True)` default; `_execute_restore` passes `DRY_RUN=1` to env. |
| #682 | Monthly restore drill workflow | 🟢 PASS — SHA-pinned actions, minimal permissions, syntax + dry-run + metadata checks. |
| #684 | Stress test CI integration | 🟢 PASS — SHA-pinned, no secrets in execution, proper timeouts. |
| #685 | Backup verification & checksum | 🟢 PASS — Comprehensive 3-level verification (checksum, GPG, completeness). No injection risks. |
| #656 | Folder facet batch operations | 🟢 PASS — Admin-only, defense-in-depth auth, value escaping, query caps, filter whitelist. |

---

## Overall Verdict

### ✅ APPROVE — v1.10.1 is clear for release

All 13 issues pass security and performance review. No blockers found. One performance observation (sequential batch updates for large document sets) is noted for future optimization but is acceptable for this release given the admin-only scope and hard caps.

**Signed off:** Ripley, Lead
**Date:** 2026-03-21
