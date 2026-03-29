# Squad Decisions


---

# Decision: User directive — PR Review Gate

**Author:** Juanma (via Copilot)  
**Date:** 2026-03-26T11:44:33Z  
**Status:** Active

Always check PR comments and failing checks — a PR is not finished until all comments are addressed and all checks pass. User request — captured for team memory.

---

# Decision: Add intel-extension-for-pytorch to OpenVINO extras

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-29T10:10:00Z
**Status:** Implemented (Issue #1286)

## Problem

The OpenVINO embeddings-server image installed `openvino` and `optimum-intel` but not `intel-extension-for-pytorch` (IPEX). Without IPEX, PyTorch detects Intel XPU hardware but cannot dispatch inference to it — the bridge between PyTorch and Intel's XPU runtime is missing.

## Decision

Add `intel-extension-for-pytorch` to the `[project.optional-dependencies] openvino` group in `src/embeddings-server/pyproject.toml`. This ensures IPEX is installed automatically when the OpenVINO variant is built (`INSTALL_OPENVINO=true`).

## Rationale

- IPEX is the standard PyTorch extension for Intel GPU/XPU support — it's the required bridge
- Adding it to the existing `openvino` extras group keeps the dependency scoped correctly (CPU builds unaffected)
- IPEX 2.8.0 resolves cleanly with torch 2.10.0 — no version pinning needed
- No Dockerfile or application code changes required — the existing `uv sync --extra openvino` picks it up

## Impact

- OpenVINO image size will increase (IPEX adds ~50-100MB of compiled extensions)
- CPU-only builds are completely unaffected
- Existing Intel GPU override (`docker-compose.intel.override.yml`) works without changes

---

# Decision: Solr auth bootstrap requires explicit role assignment

**Author:** Parker (Backend Dev)
**Date:** 2026-03-29T10:10:00Z
**Status:** Implemented (#1287)

## Problem

`solr auth enable` creates a BasicAuth user but does not assign the admin role to it. All RBAC-gated operations (collection-admin-edit, etc.) fail with "does not have the right role." Additionally, the readonly user was assigned a `search` role that doesn't exist in security.json — the correct role name is `readonly`.

## Decision

1. After `solr auth enable`, explicitly call `set-user-role` to assign `["admin"]` to the admin user.
2. Assign `["readonly"]` (not `["search"]`) to the readonly user.
3. Add Solr credentials to the installer's credential generation pipeline so production deployments don't use hardcoded default passwords.

## Impact

- All RBAC-gated Solr operations now work correctly
- Production deployments use generated secrets instead of defaults
- All team members modifying solr-init entrypoints must ensure role assignments match the role names in security.json permissions.
- The installer now generates 4 additional env vars (SOLR_ADMIN_USER, SOLR_ADMIN_PASS, SOLR_READONLY_USER, SOLR_READONLY_PASS). Existing .env files with insecure defaults will be rotated on next installer run.

---

# Decision: Test Coverage for #1287 (Solr Credentials) and #1286 (IPEX)

**Author:** Lambert (Tester)
**Date:** 2026-03-29T10:10:00Z
**Status:** Implemented

## Context

Issues #1286 and #1287 required proactive test coverage to verify fixes for:
1. Installer Solr credential management (generate, preserve, rotate, reset passwords)
2. IPEX in openvino optional-dependencies
3. Solr-init readonly role assignment (fix from "search" to "readonly")

## Decision

Added 14 tests across 3 new test files:
- `installer/tests/test_solr_credentials.py` — 6 tests for `build_env_values()` Solr credential handling
- `src/embeddings-server/tests/test_openvino_deps.py` — 4 tests for pyproject.toml/uv.lock validation
- `src/solr-search/tests/test_solr_init_script.py` — 4 tests for docker-compose.yml solr-init script

Created shared installer test infrastructure (`conftest.py`) with auth mocking and deterministic fixtures.

## Rationale

- Installer tests follow the same pattern as RabbitMQ password tests (deterministic secret_factory, autouse auth mock)
- Config/packaging tests (openvino deps) use `tomllib` for reliable TOML parsing rather than regex
- Docker-compose tests parse YAML and use regex on the inline bash script to verify role assignments
- All tests produce clear failure messages pointing to the specific issue number if a fix is missing

## Impact

- 14 new tests guard against credential management regressions in the installer
- Packaging tests prevent accidental removal of IPEX from openvino extras
- Solr-init tests prevent role assignment regressions (readonly vs search)

---

# Decision: Collection Cards Reuse BookCard Visual Layout

**Author:** Parker (Backend Dev)
**Date:** 2026-03-28T00:00:00Z
**Status:** Implemented (PR #1278)
**Context:** Issue #1233

## Problem

Collections page had a separate, minimal `CollectionItemCard` component that looked very different from the Library page's `BookCard` — missing thumbnails, metadata labels, and PDF open button.

## Decision

- Refactor `CollectionItemCard` to reuse BookCard's CSS classes (`book-card-body`, `book-card-thumbnail`, `book-meta`, `open-pdf-btn`) for visual consistency
- Keep `CollectionItemCard` as a separate component (not merge into `BookCard`) because the data types (`CollectionItem` vs `BookResult`), interactions, and collection-specific features (notes, remove) differ significantly
- Backend enriches collection items with `thumbnail_url` and `document_url` in `_enrich_collection_items`

## Rationale

Merging into a single `BookCard` component with mode switching would require handling two different data types and many conditional branches, increasing complexity. Sharing CSS classes gives visual consistency with less coupling. Collection-specific features (NoteEditor, remove confirmation) stay co-located in the collection component.

## Impact

- Any future CSS changes to BookCard's core layout classes will automatically apply to collection cards too
- Dallas should be aware that `.book-card-*` classes are now shared across both Library and Collections

---

# Decision: Extract Shared Auth Library (aithena-common)

**Author:** Parker (Backend Dev)
**Date:** 2026-03-29T10:25:00Z
**Status:** Implemented (PR for #1288)
**Context:** Issue #1288 — installer depended on solr-search internals via sys.path manipulation

## Problem

The installer imported `hash_password` and `init_auth_db` from `src/solr-search/auth.py` by appending solr-search to `sys.path`. This violated the Dependency Rule — an orchestrator (installer) depended directly on a service's internals.

## Decision

Created `src/aithena-common/` as a shared Python package containing:
- `aithena_common.passwords` — `hash_password()`, `verify_password()`, `check_needs_rehash()`
- `aithena_common.auth_db` — `init_auth_db()`, `find_user()`, `get_schema_version()`, `SCHEMA_VERSION`

Both installer and solr-search now depend on aithena-common via uv path sources.

## What Stays in solr-search

- JWT creation/verification, token handling, cookies
- User CRUD (create_user, list_users, update_user, delete_user)
- Migrations framework, default admin seeding
- Password policy validation
- All HTTP/FastAPI-specific auth logic

## Impact

- Installer is now a proper uv project (`installer/pyproject.toml`)
- `ensure_runtime_dependencies()` fallback uses `--project installer` instead of `--project src/solr-search`
- Future services needing auth DB access should depend on `aithena-common`, not import from solr-search
- `reset_password.py` in solr-search is unchanged (still imports from local `auth` module which re-exports from aithena-common)

---

# Decision: Copilot Directive — Extract Shared Auth Library Instead of Inline

**Author:** Juanma (via Copilot)
**Date:** 2026-03-29T10:15:00Z
**Status:** Active

When fixing the installer's dependency on solr-search (#1288), extract a shared auth library instead of inlining. Follow clean architecture / Dependency Inversion Principle — shared utilities belong in a standalone package, not duplicated across consumers.

**Why:** User request — captured for team memory. Multiple projects (installer, solr-search, potentially future services) need auth utilities. The sys.path hack is a code smell; proper packaging is the solution.

---

# Decision: nginx X-Frame-Options strategy for iframe-served content

**Author:** Dallas (Frontend Dev)
**Date:** 2025-07-22T00:00:00Z
**Status:** Active
**Context:** Issue #1234 — PDF viewer iframe blocked by X-Frame-Options

## Decision

All nginx locations that serve content displayed inside iframes (currently `/documents/`) must:

1. **Use `proxy_hide_header X-Frame-Options;`** before `add_header` to strip any upstream X-Frame-Options and avoid duplicate conflicting headers.
2. **Set `add_header X-Frame-Options "SAMEORIGIN" always;`** to allow same-origin iframe embedding.
3. **Re-declare all security headers** (`X-Content-Type-Options`, `Referrer-Policy`, HSTS in SSL) at location level because `add_header` suppresses server-level directives.

Additionally, named locations used as error handlers (e.g. `@auth_error`) must have their own `add_header` directives since they inherit from the server block, not the calling location.

## Rationale

nginx's `add_header` behaviour has two non-obvious interactions:
- Location-level `add_header` completely suppresses server-level `add_header` directives
- Named locations inherit headers from the *server* block, not the calling location
- `add_header` doesn't strip upstream headers; `proxy_hide_header` is needed for that

These created edge cases where some PDF requests received `X-Frame-Options: DENY` despite the `/documents/` location setting SAMEORIGIN.

## Impact

Parker/Ash: If you add new nginx locations for iframe-served content, follow this pattern. If the backend starts adding security headers, the `proxy_hide_header` directive ensures no conflicts.

---

# Decision: Clean Architecture Audit — Findings & Recommendations

**Author:** Ripley (Lead Architect)
**Date:** 2026-03-29T10:20:00Z
**Status:** Active
**Trigger:** Issue #1288 + PO directive to adopt Clean Architecture principles
**Reference:** [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) — Robert C. Martin

## Summary

Audited the full aithena codebase against Clean Architecture principles. Found **2 high-severity**, **3 medium-severity**, and **2 low-severity** violations. The `aithena-common` shared package (created for #1288) is a strong foundation but adoption is incomplete — only the installer uses it. The admin service and solr-search still maintain independent auth implementations with duplicated logic.

## Violations Found

### V1: Admin `sys.path` Manipulation in Production Code

**Severity:** 🔴 High
**File:** `src/admin/src/pages/shared/config.py:22-24`
**Impact:** Production code modifies Python's import system at module load time. This is fragile, affects all downstream imports globally, and indicates the admin service isn't properly packaged.
**Fix:** Make admin an installable package (`pyproject.toml` with proper dependencies). Remove `sys.path` manipulation. Use `uv sync` to install.

### V2: Duplicated Auth Logic Between Admin and Solr-Search

**Severity:** 🔴 High
**Files:**
- `src/admin/src/auth.py` (180 lines) — Streamlit-specific auth
- `src/solr-search/auth.py` (472 lines) — FastAPI-specific auth

**Duplicated functions:** `parse_ttl_to_seconds()`, `AuthenticatedUser`, JWT encode/decode have identical logic in both.

**Impact:** Bug fixes to auth must be applied in two places. Divergence risk is high — admin uses `hmac.compare_digest` for password comparison while solr-search uses Argon2 + SQLite.

**Fix:** Extract `parse_ttl_to_seconds()`, `AuthenticatedUser`, and JWT encode/decode into `aithena-common`. Each service keeps only its framework-specific adapter (Streamlit session management, FastAPI middleware).

### V3: Duplicated Logging Configuration Across 4 Services

**Severity:** 🟡 Medium
**Files:** solr-search, document-lister, document-indexer, admin
**Impact:** Logging format inconsistency across services. Correlation ID tracing only works in solr-search.

### V4: Solr-Search `correlation.py` Mixes Framework and Domain

**Severity:** 🟡 Medium
**File:** `src/solr-search/correlation.py`
**Impact:** Framework-specific middleware mixed with generic correlation ID logic. Cannot reuse in non-FastAPI services.

### V5: Solr-Search Tests Use `sys.path.append` (30+ files)

**Severity:** 🟡 Medium
**Impact:** Each test file independently manipulates `sys.path` instead of relying on proper package installation.

### V6: Solr-Search `reset_password.py` Uses `sys.path.insert`

**Severity:** 🟢 Low
**Impact:** Standalone script with low blast radius.

### V7: Benchmark Scripts Use `sys.path.insert`

**Severity:** 🟢 Low
**Impact:** Utility scripts, not production code.

## Recommendation for #1288: Shared Auth Library

### Phase 1: Expand `aithena-common`

Add to `src/aithena-common/aithena_common/`:
- `auth_models.py` — AuthenticatedUser, AuthSettings base
- `ttl.py` — parse_ttl_to_seconds()
- `jwt_utils.py` — create_access_token(), decode_access_token()
- `logging_setup.py` — AithenaJsonFormatter, setup_logging()

**Key constraint:** `aithena-common` must have ZERO framework dependencies.

### Phase 2: Migrate solr-search and admin

- Import shared entities from `aithena-common`
- Keep only framework-specific adapters locally
- Remove sys.path manipulation

## Architecture Principle

**Dependency Inversion Applied:**
```
installer ──────────────┐
admin ──────────────────┼──→ aithena-common (entities + pure logic)
solr-search ────────────┤
document-indexer ───────┘
```

All services depend inward. No service depends on another service's internals except via HTTP APIs.

## Skill Created

Created `.squad/skills/clean-architecture/SKILL.md` with dependency rules, PR checklist, and violation detection patterns.

## Priority

| Action | Priority | Owner | Effort |
|--------|----------|-------|--------|
| V1: Fix admin sys.path in config.py | P1 | Parker | Small |
| V2: Extract TTL, AuthenticatedUser, JWT to common | P1 | Parker | Medium |
| V3: Consolidate logging | P2 | Parker/Brett | Medium |
| V4: Split correlation.py | P2 | Parker | Small |
| V5: Fix solr-search test imports | P3 | Lambert | Medium |

