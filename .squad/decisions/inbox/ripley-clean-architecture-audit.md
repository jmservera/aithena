# Decision: Clean Architecture Audit — Findings & Recommendations

**Author:** Ripley (Lead Architect)
**Date:** 2026-03-27
**Status:** Active
**Trigger:** Issue #1288 + PO directive to adopt Clean Architecture principles
**Reference:** [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) — Robert C. Martin

---

## Summary

Audited the full aithena codebase against Clean Architecture principles. Found **2 high-severity**, **3 medium-severity**, and **2 low-severity** violations. The `aithena-common` shared package (created for #1288) is a strong foundation but adoption is incomplete — only the installer uses it. The admin service and solr-search still maintain independent auth implementations with duplicated logic.

---

## Violations Found

### V1: Admin `sys.path` Manipulation in Production Code

**Severity:** 🔴 High
**File:** `src/admin/src/pages/shared/config.py:22-24`

```python
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
```

**Impact:** Production code modifies Python's import system at module load time. This is fragile, affects all downstream imports globally, and indicates the admin service isn't properly packaged.

**Fix:** Make admin an installable package (`pyproject.toml` with proper dependencies). Remove `sys.path` manipulation. Use `uv sync` to install.

---

### V2: Duplicated Auth Logic Between Admin and Solr-Search

**Severity:** 🔴 High
**Files:**
- `src/admin/src/auth.py` (180 lines) — Streamlit-specific auth
- `src/solr-search/auth.py` (472 lines) — FastAPI-specific auth

**Duplicated functions/classes:**
| Symbol | `solr-search/auth.py` | `admin/src/auth.py` | `aithena-common` |
|--------|----------------------|---------------------|-------------------|
| `parse_ttl_to_seconds()` | ✅ | ✅ (identical logic) | ❌ not yet |
| `AuthenticatedUser` | ✅ | ✅ (identical) | ❌ not yet |
| `hash_password()` | ✅ | ❌ (not needed) | ✅ extracted |
| `init_auth_db()` | ✅ | ❌ | ✅ extracted |
| `authenticate_user()` | ✅ (DB-based, Argon2) | ✅ (env-var, hmac) | ❌ |
| JWT encode/decode | ✅ | ✅ (identical logic) | ❌ not yet |

**Impact:** Bug fixes to auth must be applied in two places. Divergence risk is high — admin uses `hmac.compare_digest` for password comparison while solr-search uses Argon2 + SQLite. JWT creation/validation logic is duplicated.

**Fix:** Extract `parse_ttl_to_seconds()`, `AuthenticatedUser`, and JWT encode/decode into `aithena-common`. Each service keeps only its framework-specific adapter (Streamlit session management, FastAPI middleware).

---

### V3: Duplicated Logging Configuration Across 4 Services

**Severity:** 🟡 Medium
**Files:**
- `src/solr-search/logging_config.py` (104 lines) — full features + correlation ID
- `src/document-lister/document_lister/logging_config.py` (96 lines) — reduced, no correlation import
- `src/document-indexer/document_indexer/logging_config.py` — similar to document-lister
- `src/admin/src/logging_config.py` (88 lines) — no correlation at all

**Impact:** Logging format inconsistency across services. Correlation ID tracing only works in solr-search. Changes to log format require updating 4 files.

**Fix:** Extract `AithenaJsonFormatter` and `setup_logging()` into `aithena-common/logging.py`. Each service calls `setup_logging(service_name)`.

---

### V4: Solr-Search `correlation.py` Mixes Framework and Domain

**Severity:** 🟡 Medium
**File:** `src/solr-search/correlation.py`

This module imports `fastapi.Request`, `fastapi.Response`, and `starlette.middleware.base.BaseHTTPMiddleware`. It implements correlation ID propagation, which is a cross-cutting infrastructure concern — not specific to FastAPI.

**Impact:** Cannot reuse correlation ID logic in non-FastAPI services (document-indexer, document-lister). The framework-specific middleware is mixed with the generic correlation ID generation/propagation logic.

**Fix:** Split into:
- `aithena-common/correlation.py` — pure `get_correlation_id()`, `CorrelationIdFilter` (no framework imports)
- `src/solr-search/middleware/correlation.py` — FastAPI-specific `CorrelationIdMiddleware`

---

### V5: Solr-Search Tests Use `sys.path.append` (30+ files)

**Severity:** 🟡 Medium
**Files:** 30+ test files in `src/solr-search/tests/` all contain:

```python
sys.path.append(str(Path(__file__).resolve().parents[1]))
```

**Impact:** Each test file independently manipulates `sys.path` instead of relying on proper package installation. This pattern is fragile and inconsistent with how `document-indexer` and `document-lister` (which are proper packages) handle test imports.

**Fix:** Make solr-search an installable package. Add a single `conftest.py` that handles path setup, or (better) use `uv run pytest` which automatically installs the project.

---

### V6: Solr-Search `reset_password.py` Uses `sys.path.insert`

**Severity:** 🟢 Low
**File:** `src/solr-search/reset_password.py:29`

```python
sys.path.insert(0, str(_SCRIPT_DIR))
```

**Impact:** Standalone script, not part of the service's HTTP API. Low blast radius.

**Fix:** Should use `aithena-common` for password hashing and be invoked via `uv run`.

---

### V7: Benchmark Scripts Use `sys.path.insert`

**Severity:** 🟢 Low
**Files:** `scripts/benchmark/tests/test_*.py` (3 files)

**Impact:** Utility scripts, not production code. Acceptable as transitional.

**Fix:** Low priority. Consider making benchmark scripts a proper package if they grow.

---

## Recommendation for #1288: Shared Auth Library

The `aithena-common` package already exists and is the correct architectural direction. To complete issue #1288:

### Phase 1: Expand `aithena-common` (current gap)

Add to `src/aithena-common/aithena_common/`:

```
aithena_common/
├── __init__.py         ✅ exists
├── passwords.py        ✅ exists (hash_password, verify_password)
├── auth_db.py          ✅ exists (init_auth_db, find_user)
├── auth_models.py      ❌ NEW — AuthenticatedUser, AuthSettings base
├── ttl.py              ❌ NEW — parse_ttl_to_seconds()
├── jwt_utils.py        ❌ NEW — create_access_token(), decode_access_token()
└── logging_setup.py    ❌ NEW — AithenaJsonFormatter, setup_logging()
```

**Key constraint:** `aithena-common` must have ZERO framework dependencies. Only stdlib + `argon2-cffi` + `pyjwt`.

### Phase 2: Migrate solr-search

- `solr-search/auth.py` imports `AuthenticatedUser`, `parse_ttl_to_seconds`, JWT utils from `aithena-common`
- Keeps FastAPI-specific middleware, route guards, and DB-backed user lookup locally
- Add `aithena-common` to `solr-search/pyproject.toml` dependencies

### Phase 3: Migrate admin

- `admin/src/auth.py` imports shared types from `aithena-common`
- Keeps Streamlit-specific session management (`st.session_state`, cookie handling) locally
- Remove `sys.path` manipulation from `config.py`
- Add `aithena-common` to `admin/pyproject.toml` dependencies

### Phase 4: Consolidate logging

- Extract unified logging formatter to `aithena-common`
- All services call `setup_logging(service_name)` from the shared package
- Correlation ID logic split: pure logic in common, FastAPI middleware stays in solr-search

---

## Architecture Principle

The Dependency Inversion Principle applied to aithena:

```
installer ──────────────┐
admin ──────────────────┼──→ aithena-common (entities + pure logic)
solr-search ────────────┤
document-indexer ───────┘
```

All services depend **inward** on `aithena-common`. No service depends on another service's internals. Inter-service communication happens **only** via HTTP APIs or message queues.

---

## Priority

| Action | Priority | Owner | Effort |
|--------|----------|-------|--------|
| V1: Fix admin sys.path in config.py | P1 | Parker/Copilot | Small |
| V2: Extract TTL, AuthenticatedUser, JWT to common | P1 | Parker | Medium |
| V3: Consolidate logging | P2 | Parker/Brett | Medium |
| V4: Split correlation.py | P2 | Parker | Small |
| V5: Fix solr-search test imports | P3 | Lambert | Medium |
| V6-V7: Script sys.path cleanup | P3 | Copilot | Small |

---

## Skill Created

Created `.squad/skills/clean-architecture/SKILL.md` with:
- Dependency Rule mapped to aithena layers
- Concrete rules (R1–R5) for the team
- PR review checklist
- Common violation detection patterns
