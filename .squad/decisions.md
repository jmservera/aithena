# Squad Decisions

---

# Decision: OpenVINO Embeddings Container Regression Root Cause

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-31T09:10:00Z  
**Status:** Analysis Complete

## Summary

The OpenVINO embeddings container regressed between rc.3 and rc.23 due to a **Dockerfile change that stopped chown-ing `/models`**. In rc.3 the chown layer was `chown -R app:app /app /models`, but in rc.23 it was changed to `chown -R app:app /app && chmod -R a+rX /models`. This makes `/models` **read-only** for the `app` user in rc.23 — the directory is owned by `root:root` with mode 755. Any runtime write to `/models` (e.g. OpenVINO model cache, lock files, HuggingFace cache updates) will fail with "Permission denied".

## Root Cause Details

| Dimension | rc.3 | rc.23 | Contributing? |
|-----------|------|-------|---------------|
| `/models/` ownership | app:app 755 | root:root 755 | **🔴 YES** |
| `/models/` writable by app user | ✅ Yes | ❌ No | **🔴 YES** |
| Process user | uid=999(app) | uid=999(app) | ✅ No |
| Python packages (torch, optimum, optimum-intel, sentence-transformers) | Identical | Identical | ✅ No |
| Environment variables | Identical | Identical | ✅ No |
| `main.py` code | Identical | Identical | ✅ No |
| `model_utils.py` code | Original | Enhanced device routing | 🟡 No (improvements) |

## Why rc.23 Changed

The Dockerfile comment explains: *"Don't chown /models — it duplicates the entire ~5 GB model directory as a new layer. Models are read-only; just ensure world-readable permissions"*

The rationale is valid for the model files themselves (read-only), but the side effect is that OpenVINO and HuggingFace libraries cannot write cache/lock files at runtime inside `/models`.

## Recommended Fixes (priority order)

1. **Create a writable cache directory** (preferred):
   ```dockerfile
   RUN mkdir -p /models/.cache && chown app:app /models/.cache
   ENV OPENVINO_CACHE_DIR=/models/.cache
   ```
   Targeted, doesn't bloat the image, explicitly controls where cache writes go.

2. **Make only directory inodes writable**:
   ```dockerfile
   RUN find /models -type d -exec chmod 777 {} +
   ```
   Avoids full chown, but less explicit about which cache directories are writable.

3. **Revert to full chown**:
   ```dockerfile
   RUN chown -R app:app /app /models
   ```
   Simplest fix, acceptable if layer size is acceptable.

## Impact

- Unblocks Dockerfile fix PR targeting embeddings-server
- Provides root cause documentation for regression prevention
- Validates against future permission-related regressions

---

# Decision: OpenVINO Smoke Test as Separate CI Job

**Author:** Lambert (Tester)  
**Date:** 2026-03-31T09:10:00Z  
**Status:** Proposed

## Context

The OpenVINO embeddings container regressed between rc.3 and rc.23 due to a Permission denied error when creating `model_cache` inside the read-only `/models/` directory. The existing smoke-test matrix entry checks `/health` but provides no targeted diagnostics or automatic issue filing.

## Decision

Created a dedicated `smoke-test-openvino` CI job (not a matrix extension) that:
1. Validates model directory permissions with `mkdir -p` / `touch` as uid 1000
2. Audits container user identity and directory ownership
3. Tests model loading via `/health` with `BACKEND=openvino DEVICE=cpu`
4. Verifies embedding inference returns correct 768-dim vectors
5. Auto-creates a GitHub Issue with root-cause documentation on failure

## Rationale

- The existing matrix smoke test only checks health endpoint liveness — no diagnostics on *why* it failed
- Permission regressions are silent until the container crashes; targeted `mkdir -p` catches them before model loading
- Auto-issue with documented root cause pattern reduces MTTR — the fix (restore `chown` or pre-create cache dir) is immediately actionable
- Separate job avoids complicating the generic matrix pattern with openvino-specific logic

## Files

- `e2e/smoke-openvino-permissions.sh` — smoke test script (5 diagnostic checks)
- `e2e/smoke-openvino-permissions.ci.yml` — CI job snippet (add to `.github/workflows/pre-release.yml`)

## Impact

- Requires `issues: write` permission on the pre-release workflow
- Adds ~3-4 min to the pre-release pipeline (parallel with existing smoke tests)
- Parker/Brett: if changing `/models` permissions in the Dockerfile, this test will catch regressions
- Auto-issue on failure provides immediate root cause documentation

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

---

# Decision: Dependabot PR Routing in ralph-triage.js

**Author:** Parker  
**Date:** 2026-03-30  
**Status:** Implemented

## Context

The heartbeat workflow lost Dependabot PR auto-assignment when inline JS was refactored to `ralph-triage.js`. PRs were silently filtered out by `isUntriagedIssue()`.

## Decision

Added a separate Dependabot PR triage pipeline alongside the existing issue triage. The classification uses a two-tier member lookup:

1. **Routing rules** (from `routing.md`) — matches dependency domain keywords against work type columns
2. **Role-based fallback** (from `team.md` roster) — matches against member role text

This makes it resilient to routing table format changes while still respecting routing.md as the source of truth when available.

## Dependency domain patterns

File and title patterns map PRs to six domains: python-backend, frontend-js, github-actions, docker-infra, security, testing. Each domain carries both `workTypeKeywords` (for routing rules) and `roleKeywords` (for roster fallback).

## Impact

- `pull-requests: write` permission added to heartbeat workflow
- New triage results include PRs alongside issues (same JSON format, uses `issueNumber` field since GitHub's label API works for both)
- No changes to existing issue triage logic

---

# Decision: Embeddings-Server Docker Layer Optimization — Approach Analysis

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-31
**Status:** Recommendation
**Context:** Issue #1325 — reduce ~4GB .venv COPY layer; Juanma asked whether multi-stage can avoid keeping `uv` in runtime image

## Problem

The current app Dockerfile has a two-stage build:
- **Stage 1** (`python:3.12-slim`): `uv sync` installs ALL deps into `/app/.venv` (~8GB uncompressed)
- **Stage 2** (base image): `COPY --chown /app/.venv` from stage 1 → creates a ~4GB compressed layer

The base image already contains the heavy packages (torch 1.7GB, nvidia-* 4.3GB, triton 641MB) at system site-packages. The COPY duplicates them entirely.

**Prerequisite for Approaches 1–4:** The base image must be rebuilt to own `/app/.venv` with heavy deps pre-installed (instead of system site-packages). This is a one-time change to both base variants.

## Comparison Table

| Criteria | 1: In-place `uv sync` | 2: Multi-stage full COPY | 3: BuildKit `--mount=from` | 4: Delta-only COPY | 5: Strip + PYTHONPATH |
|----------|----------------------|--------------------------|---------------------------|--------------------|-----------------------|
| **New layer size** | ~200MB ✅ | ~4–8GB ❌ | ~200MB ✅ | ~200MB ✅ | ~1.1GB ⚠️ |
| **Base layer sharing** | ✅ Preserved | ❌ COPY overrides | ✅ Preserved | ✅ Preserved | ✅ Preserved |
| **uv in runtime** | ❌ Yes (~30MB) | ✅ No | ✅ No | ✅ No | ✅ No |
| **Dockerfile complexity** | Low | Low-medium | Low | Very high | Medium |
| **Maintainability** | Good | Good | Excellent | Poor | Fragile |
| **Security** | ⚠️ uv binary in image | Good | Excellent | Good | Good |
| **Build cache** | Good | Poor (full COPY) | Good | Moderate | Moderate |
| **Compatibility** | Both variants ✅ | Both variants ✅ | Both variants ✅ | Fragile ⚠️ | Different PYTHONPATH per variant ⚠️ |
| **CI/CD requirements** | Standard Docker | Standard Docker | BuildKit (already used) | Standard Docker | Standard Docker |
| **Base image change needed** | Yes | Yes | Yes | Yes | **No** |
| **Python symlink fix** | Not needed | Needed (cross-stage COPY) | Not needed | Not needed | Needed |

## Detailed Analysis

### Approach 1: In-place `uv sync --inexact` (Option C)

```dockerfile
FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG}
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --inexact --native-tls
```

**How it works:** Base image pre-owns `/app/.venv` with heavy deps. `uv sync --inexact` detects what's installed and only adds missing light deps (fastapi, uvicorn, etc.) as a ~200MB delta layer.

**Pros:** Simple, small layer, base layers shared, great cache behavior.
**Cons:** `COPY --from=...uv /uv /usr/local/bin/uv` permanently adds `uv` (~30MB) to the image. It's a development tool with no runtime purpose — unnecessary attack surface.

### Approach 2: Multi-stage with full .venv COPY

```dockerfile
FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --inexact --native-tls

FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS runtime
COPY --from=build /app/.venv /app/.venv
```

**Critical flaw:** `COPY` always writes the **full directory contents** as a new layer, regardless of what's already in the base image. Even though both stages share the same base, the COPY creates a ~4–8GB layer containing ALL of `/app/.venv` (heavy deps + delta). Docker layer deduplication works at the layer ID level, not file level — a new COPY layer is a completely new layer.

**This approach is strictly worse than the current Dockerfile.** It adds multi-stage complexity without solving the layer size problem. The only benefit is removing `uv` from runtime, but at the cost of a massive layer that destroys base-image pull optimization.

**Verdict:** ❌ Do not use.

### Approach 3: BuildKit `--mount=from` bind mount ⭐ RECOMMENDED

```dockerfile
# syntax=docker/dockerfile:1
FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS runtime
COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/usr/local/bin/uv \
    uv sync --frozen --no-dev --no-install-project --inexact --native-tls
```

**How it works:** `--mount=from=image` creates a read-only bind mount of a file from another image, available ONLY for the duration of the `RUN` command. After the command completes, the mount is removed. The `uv` binary never exists in any image layer.

**Key insight:** This combines every advantage:
- Same ~200MB delta layer as Approach 1 (only new packages)
- Base image layers fully preserved (RUN adds on top, doesn't replace)
- Zero `uv` in the final image (mounted transiently, not copied)
- Actually *simpler* than Approach 1 (one fewer Dockerfile instruction)
- No Python interpreter symlink fix needed (venv was created on this base)

**BuildKit compatibility:**
- `--mount` syntax requires BuildKit, available since Docker 18.09+ (2018)
- Default builder since Docker Engine 23.0+ (2023)
- CI already uses `docker/setup-buildx-action` which enables BuildKit
- The `# syntax=docker/dockerfile:1` directive ensures compatibility with older Docker daemons
- Docker Desktop (developer machines) has had BuildKit as default since 2020

**Verdict:** ✅ Clear winner.

### Approach 4: Multi-stage delta-only COPY

```dockerfile
FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN find /app/.venv -type f > /before.txt
RUN uv sync --frozen --no-dev --no-install-project --inexact --native-tls
RUN find /app/.venv -type f > /after.txt && \
    comm -13 /before.txt /after.txt | tar cf /delta.tar -T - 

FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS runtime
COPY --from=build /delta.tar /delta.tar
RUN tar xf /delta.tar && rm /delta.tar
```

**Pros:** Small delta, no uv in runtime.
**Cons:** Extremely fragile. File diff logic breaks on path changes, special characters, symlinks. Multiple RUN layers reduce cache efficiency. The tar approach creates two layers (COPY + RUN) instead of one. Hard to debug when it breaks.

**Verdict:** ❌ Approach 3 achieves the same result with zero complexity.

### Approach 5: Strip + PYTHONPATH (Issue's original proposal)

```dockerfile
FROM python:3.12-slim AS dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls && \
    pip list --path /app/.venv/lib/python3.12/site-packages --format=freeze | \
    grep -iE '^(torch|nvidia|triton)' | cut -d= -f1 | \
    xargs -I{} rm -rf /app/.venv/lib/python3.12/site-packages/{}*

FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS runtime
COPY --from=dependencies --chown=app:app /app/.venv /app/.venv
ENV PYTHONPATH="/usr/local/lib/python3.12/site-packages:${PYTHONPATH}"
```

**Pros:** No base image modification required — works today.
**Cons:**
- PYTHONPATH differs per variant (slim: `/usr/local/lib/...`, openvino: `/opt/venv/lib/...`) — needs conditional logic
- Strip list must stay in sync with base image contents manually
- ~1.1GB layer (still includes sentence-transformers and transitive deps not in strip list)
- Python interpreter symlink fix still needed (cross-base COPY)
- `PYTHONPATH` for package resolution is an anti-pattern — can cause version conflicts

**Verdict:** ⚠️ Viable interim solution if base image change is delayed, but not recommended long-term.

## Recommendation

**Use Approach 3: BuildKit `--mount=from` bind mount.**

It wins on every axis: smallest layer (~200MB), no tools in runtime, simplest Dockerfile, best maintainability, full CI compatibility. The only prerequisite is the base image rebuild to use `/app/.venv` (needed for Approaches 1–4 anyway).

### Recommended Dockerfile (complete)

```dockerfile
# syntax=docker/dockerfile:1
ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ARG BASE_TAG=3.12-slim-multilingual-e5-base
ARG INSTALL_OPENVINO=false

# Single stage: base image owns .venv with heavy deps; we add only the delta.
FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS runtime

ARG VERSION
ARG GIT_COMMIT
ARG BUILD_DATE

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/jmservera/aithena" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MODEL_NAME=intfloat/multilingual-e5-base \
    HF_HOME=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence_transformers \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    DEVICE=cpu \
    BACKEND=torch

WORKDIR /app

# System packages (needs root; openvino base may run as non-root)
USER root

RUN apt-get update && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/*

RUN if ! id -u app >/dev/null 2>&1; then \
      groupadd --system --gid 1000 app 2>/dev/null || groupadd --system app; \
      useradd --system --uid 1000 --gid app --create-home app 2>/dev/null || \
        useradd --system --gid app --create-home app; \
    fi

# ── Delta dependency install (~200MB layer) ──
# uv is bind-mounted from its official image for this RUN only.
# It does NOT exist in any layer of the final image.
# --inexact preserves base-image packages; only missing deps are added.
COPY pyproject.toml uv.lock ./
ARG INSTALL_OPENVINO=false
RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/usr/local/bin/uv \
    if [ "$INSTALL_OPENVINO" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --inexact --extra openvino --native-tls; \
    else \
      uv sync --frozen --no-dev --no-install-project --inexact --native-tls; \
    fi

ENV PATH="/app/.venv/bin:${PATH}"

COPY --chown=app:app main.py model_utils.py /app/
COPY --chown=app:app config /app/config

# Ownership: only /app (tiny). /models stays root-owned, world-readable.
RUN chown -R app:app /app && chmod -R a+rX /models

# Writable cache for OpenVINO compiled-model cache
RUN mkdir -p /tmp/ov_cache && chown app:app /tmp/ov_cache
ENV OPENVINO_CACHE_DIR=/tmp/ov_cache

EXPOSE 8080

USER app

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
```

### Changes vs. Current Dockerfile

| What changed | Why |
|---|---|
| Removed `FROM python:3.12-slim AS dependencies` stage | No longer needed — delta installed in-place |
| Removed `COPY --from=dependencies /app/.venv` | No cross-stage .venv copy — eliminates the ~4GB layer |
| Added `--mount=from=ghcr.io/astral-sh/uv:latest` on RUN | uv available only during build, not in image |
| Added `--inexact` flag to `uv sync` | Preserves base packages, installs only delta |
| Removed Python symlink fix (`ln -sf`) | venv created on same base — no interpreter mismatch |
| Added `# syntax=docker/dockerfile:1` | Ensures BuildKit syntax compatibility |

### Required Base Image Changes

Both base variants must be updated to:
1. Create `/app/.venv` (instead of system site-packages or /opt/venv)
2. Install heavy deps (torch, nvidia-*, triton, sentence-transformers) into `/app/.venv` via uv
3. Create `app:1000` user owning the venv
4. Set `PATH="/app/.venv/bin:${PATH}"`

This is a one-time change. Heavy deps rarely change (torch version bumps are ~quarterly).

## Impact

- **Download size:** ~4.1GB → ~200MB compressed (when base cached) — **95% reduction**
- **Build time:** Faster (only delta install, no cross-stage COPY of 8GB)
- **Security:** Removes uv binary from runtime image
- **CI:** No changes needed (BuildKit already enabled via buildx-action)
- **Base image:** One-time rebuild required for both slim and openvino variants


---

# Decision: BuildKit --mount=from + --inexact for embeddings-server layer optimization

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-31T13:16:00Z
**Status:** Implemented (blocked on base image)

## Summary

Replaced the multi-stage `COPY --from=dependencies /app/.venv` pattern in the embeddings-server Dockerfile with a single-stage BuildKit `--mount=from` approach. The app Dockerfile now bind-mounts `uv` at build time and runs `uv sync --inexact` to install only the delta of app-specific packages into the base image's pre-populated `.venv`.

## What Changed

- **Approach:** Approach 3 from the analysis — BuildKit `--mount=from` bind mount
- **App Dockerfile:** `src/embeddings-server/Dockerfile` — removed dependencies stage, added `--mount=from` + `--inexact`
- **Base image:** Blocks on jmservera/embeddings-server-base#5 — both Dockerfiles need to switch from system site-packages to `/app/.venv`
- **PR:** jmservera/aithena#1328 (draft, blocked on base image update)

## Key Design Decisions

1. **`--inexact` over `--exact`:** Preserves base image packages, installs only missing deps. This is critical — `--exact` would remove the pre-installed heavy packages.
2. **Single conditional RUN:** Both torch and openvino variants handled in one `if/else` block instead of two separate RUN commands.
3. **OV cache at `/app/ov_cache`:** Moved from `/tmp/ov_cache` for consistency and to avoid potential noexec issues.
4. **`# syntax=docker/dockerfile:1`:** Required as first line for cross-version BuildKit compatibility.

## Impact

| Metric | Before | After |
|--------|--------|-------|
| .venv layer | ~4.1 GB compressed | ~200 MB compressed |
| Build stages | 2 | 1 |
| Python symlink hack | Required | Eliminated |

## Dependencies

This is a **breaking change pair** — the base image must be updated to provide `/app/.venv` before the app Dockerfile will build. Coordination tracked via:
- Base: jmservera/embeddings-server-base#5
- App: jmservera/aithena#1328

---

# Decision: Base image uses /app/.venv with uv

**Author:** Parker (Backend Dev)
**Date:** 2026-03-31T13:16:00Z
**Status:** Implemented

## Context

The embeddings-server base image previously installed heavy Python packages (torch, sentence-transformers, nvidia-*, etc.) into system site-packages via `pip install`. The app image then had to COPY the entire ~4GB .venv from a build stage, creating a massive duplicate layer.

## Decision

Both base image Dockerfiles (`Dockerfile` and `Dockerfile.openvino`) now:

1. **Install packages into `/app/.venv`** using `uv venv` + `uv pip install` instead of system `pip`
2. **Use BuildKit `--mount=from`** to transiently mount the `uv` binary — it never exists in the final image
3. **Create `app:1000` user** that owns `/app` — consistent with the app image's runtime user
4. **Keep `/models` root-owned** with `chmod a+rX` to avoid duplicating the ~5GB model layer via chown
5. **Provide `/models/.cache`** with `app:app` ownership for OpenVINO/HuggingFace cache writes

## Consequences

- The app Dockerfile (in aithena) **must** be updated to use `uv sync --inexact` instead of the current multi-stage COPY pattern. This is a coordinated change.
- The `# syntax=docker/dockerfile:1` directive is now required (first line of each Dockerfile) to enable BuildKit mount syntax.
- `uv` is never present at runtime — any debugging requiring package installs must use a temporary mount or exec into the container with a different approach.
- The openvino variant now uses `app:1000` instead of the base image's `openvino` user, which is a breaking change for anything that depended on that user identity.

## Impact on Team

- **Brett (Infra):** This implements the prerequisite from his BuildKit mount analysis. The app Dockerfile changes can now proceed.
- **Lambert (Tester):** Base image rebuild required before testing the full optimization pipeline.
- **Dallas (Frontend):** No impact.

---

# User Directive: Base image Dockerfiles should use proper files instead of inline Python

**Date:** 2026-03-31T13:16:00Z
**By:** jmservera (via Copilot)

## Directive

Base image Dockerfiles should use proper `pyproject.toml` and `.py` script files for model download/verification instead of inline Python in RUN commands. No more writing Python code directly into the console in Dockerfile RUN instructions.

## Rationale

Inline Python in Dockerfiles is:
- Fragile and error-prone (escaping issues, shell interpretation)
- Hard to maintain and review
- Not testable independently
- Violates separation of concerns (build config vs. build logic)

Proper files are cleaner, more maintainable, and testable.

## Implementation

Both base image Dockerfiles should extract model download/verification logic into:
- `scripts/download_models.py` — handles model fetching, checksums, cache population
- `scripts/verify_models.py` — validates model files, checksums, integrity
- `pyproject.toml` — declares these as build-time dependencies or scripts

Then in Dockerfile: `RUN uv run python scripts/download_models.py` (clean, testable, auditable).
