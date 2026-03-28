# Squad Decisions

---

> 📦 Older decisions archived to decisions-archive.md

# Decision: User directive — PR Review Gate

**Author:** Juanma (via Copilot)  
**Date:** 2026-03-26T11:44:33Z  
**Status:** Active

Always check PR comments and failing checks — a PR is not finished until all comments are addressed and all checks pass. User request — captured for team memory.

---

# Decision: 404 vs 422 for Missing Embeddings in Similar Books

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-26  
**Status:** Implemented (PR #1226)  
**Context:** PR #1226 review comment

### Problem

The `/books/{id}/similar` endpoint returned 404 for two different failure modes:
1. No chunks found for the book (book not indexed)
2. Chunks found but no `embedding_v` field (book indexed, embeddings pending)

Both cases returned 404, but they have different semantics.

### Decision

- **404** — No indexed chunks found for this book
- **422** — Chunks exist but no embedding → can't process for similarity

### Rationale

HTTP 404 means "resource not found." When no chunks exist for the requested book ID, the book may not have been indexed yet, or may still be processing — no chunk documents have been created for it. This is a genuine "not found" condition because the parent document may or may not exist; what matters is that there is nothing to compute similarity from. HTTP 422 (Unprocessable Entity) applies when chunks exist (proving the book is at least partially indexed) but the first chunk has no `embedding_v` field yet — the server understands the request but can't fulfill it because the embedding pipeline hasn't run.

This lets clients distinguish between "no chunks for this book" (check back after indexing) and "chunks exist but embeddings aren't ready yet" (retry after embedding pipeline runs).

### Impact

- Clients checking for 404 to mean "book not found" won't get false positives from unprocessed books
- Frontend can show "embeddings processing" message on 422 vs "not found" on 404
- Pattern applies to any future endpoint that depends on async pipeline output

---

# Decision: User directive — No A/B comparison for v1.14.0

**Author:** Juanma (Project Owner)  
**Date:** 2026-03-23T09:05Z  
**Status:** CLOSED (v1.14.0 milestone)  
**Impact:** All A/B evaluation issues (#900-918) closed as "not planned"

## Directive

"We are not going to have a side by side comparer as we already decided to move to the new model directly." The e5-base benchmark showed clear superiority. The stack moves directly to multilingual-e5-base via PR #964.

## Context

A/B testing infrastructure was prepared for user-facing comparison of distiluse-base vs multilingual-e5-base embeddings. However, internal benchmarks demonstrated e5-base superiority across all metrics, eliminating the need for end-user A/B evaluation.

## Decision

- Close all v1.14.0 A/B evaluation issues (#900-918) as "not planned"
- Mark v1.14.0 milestone complete
- Proceed with e5-base deployment via #964 (no dual-model production stack)
- Dual-model infrastructure remains available for future testing/rollback scenarios

---


---

## Decision: Thumbnail Volume Permission Handling

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-24
**Status:** Implemented (PR #1090)
**Context:** Issue #1089

### Problem

Pre-release log analyzer flags `Permission denied: '/data/thumbnails/'` errors from document-indexer as security findings. These are caused by missing directory ownership in the Dockerfile — the named volume is root-owned but the container runs as UID 1000.

### Decision

1. **Allowlist rule:** `security:*permission denied*/data/thumbnails/*=ignore` — thumbnail generation is non-critical; indexing succeeds without thumbnails
2. **Dockerfile fix:** `RUN mkdir -p /data/thumbnails && chown app:app /data/thumbnails` — named volumes inherit image layer permissions on first creation

### Rationale

- Thumbnail failures don't block document indexing (non-critical feature)
- The Dockerfile fix is the correct infrastructure-level approach for named volume permissions
- The allowlist provides defense-in-depth for CI environments where volumes may not initialize cleanly

### Impact

- Unblocks v1.15.0 release (PR #1088)
- Pattern applies to any future service that writes to named volumes as non-root

---

# User directive: review PR comments before merging

**Date:** 2026-03-24T21:55:00Z  
**Author:** Juanma (via Copilot)  
**Status:** Proposed

## Context
PR #1095 was merged with 8 unaddressed review comments. The user has requested that this must not happen again.

## Decision
Always review PR comments before merging. Never merge a PR with unresolved review threads.

## Rationale
Ensuring all review comments are addressed before merging prevents regressions, maintains code quality, and respects reviewer feedback, aligning with the user's explicit request after the PR #1095 incident.

---

# Decision: Admin Portal React Migration Architecture

**Date**: 2025-07-18
**Author**: Newt (Product Manager)
**Status**: Proposed
**Requested by**: Juanma (jmservera)

## Context

The admin portal (`src/admin/`) was originally a standalone Streamlit (Python) app with 7 pages. The `streamlit-admin` Compose service has since been removed and nginx redirects `/admin/streamlit` → `/admin`, but the `src/admin/` source tree is retained as reference. The React UI (`src/aithena-ui/`) already has 3 admin pages (`/admin`, `/admin/users`, `/admin/backups`). For v2.0, we need to complete the migration of all remaining Streamlit admin features into React.

## Decision

**Integrate admin pages into the existing `aithena-ui` React application** as `/admin/*` routes, rather than building a separate React admin application.

## Rationale

1. **Infrastructure already exists**: `AdminRoute` component, `AuthContext`, `apiFetch` API layer, admin hooks, and tab navigation are all in place.
2. **No duplication**: A separate app would duplicate auth, routing, theming, i18n, and build tooling.
3. **Single deployment artifact**: One nginx container serves everything — simpler ops.
4. **Lazy loading**: Admin pages are code-split, so they don't affect search page performance.
5. **Precedent**: The existing `/admin`, `/admin/users`, and `/admin/backups` pages already follow this pattern.

## Implications

- Admin pages share the same build pipeline, test suite, and deployment as the main UI
- An `AdminLayout.tsx` component with sidebar sub-navigation will wrap all admin routes
- Four new backend API endpoints are required in `solr-search` (queue-status, indexing-status, logs, infrastructure)
- Docker socket mount moves from Streamlit container to `solr-search` backend (for log API)
- The Streamlit `streamlit-admin` service is removed from Docker Compose in v2.0

## Alternatives Considered

1. **Separate React app** (`admin-ui/`): More isolation but duplicates auth/routing/theming. Rejected.
2. **Micro-frontend**: Over-engineered for a single-tenant on-premises app. Rejected.
3. **Keep Streamlit**: Maintains tech stack split and Docker socket security concern. Rejected.

## Full PRD

See `docs/prd/admin-react-migration.md` for the complete Product Requirements Document including feature inventory, API requirements, migration phases, and success metrics.
---

# Decision: Thumbnail URL Prefix in Search API

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-25  
**Status:** Implemented (PR #1139)  
**Context:** Issue #1137

## Problem

Thumbnail URLs stored in Solr are relative paths (e.g., `folder/book.pdf.thumb.jpg`). The search API returned these as-is, but the frontend uses them directly in `<img src>`. Without a `/thumbnails/` prefix, the browser resolved them as relative URLs against the current page, hitting the SPA catch-all instead of the nginx static-file location block.

## Decision

The search API now prefixes relative thumbnail paths with `/thumbnails/` via `_thumbnail_url()` in `search_service.py`. Absolute URLs (http/https) and already-prefixed paths (starting with `/`) are passed through unchanged.

## Rationale

- The backend is the right place to apply URL prefixes because it knows the routing scheme
- The frontend should receive ready-to-use URLs without needing path manipulation
- Preserving absolute URLs ensures backward compatibility with any externally-hosted thumbnails
- The nginx location block `^/thumbnails/(.+\.thumb\.jpg)$` expects this prefix

## Impact

- All search, books, and similar-books responses now return `/thumbnails/`-prefixed URLs
- Frontend components (`BookCard`, `BookDetailView`) work without changes
- nginx correctly routes to `/data/thumbnails/` filesystem path

---

# Decision: Bug Triage for v1.16.0 (2026-03-25)

**Author:** Ripley (Project Lead)  
**Date:** 2026-03-25T15:30Z  
**Requested by:** Juanma (jmservera)  
**Status:** DECIDED

## Context

Three new bugs submitted for triage with no assigned milestones:
- #1137 — Thumbnails not loaded in UI (squad:parker)
- #1138 — Admin dashboard queued/processed/failed list not paged (squad:dallas)
- #1136 — RabbitMQ deprecation warning (squad:lambert)

## Decision

All three bugs assigned to **v1.16.0 milestone**.

### Priority Ranking (for Ralph's backlog)

1. **#1137 (Thumbnails)** — Parker | Medium severity | Low–Medium effort
   - User-visible feature broken; nginx route or volume mount issue
   - Investigate static `/thumbnails` serving; verify Docker volume creation

2. **#1138 (Admin pagination)** — Dallas | Medium severity | Low effort
   - Scales with data size; missing React pagination component
   - **Note:** Streamlit admin deprecated in v2.0; consider deferred if v2.0 React migration imminent

3. **#1136 (RabbitMQ warning)** — Lambert (investigation) → Parker (fix) | Low severity | Very Low effort
   - Log noise only; blocks future RabbitMQ upgrades
   - Add `deprecated_features.permit.management_metrics_collection` config before next patch release

### Label Actions

- Removed `go:needs-research` from all three (clear enough to implement immediately)
- Preserved squad routing: Parker (backend), Dallas (frontend), Lambert (testing)

## Rationale

- **User impact ordering:** Visible bugs before warnings
- **#1137 first:** Broken feature, direct user impact
- **#1138 second:** Unscalable UX, but Streamlit admin EOL in v2.0 (risk: low-ROI effort if timeline tight)
- **#1136 last:** No functional impact; maintenance task

## Risk

#1138 (admin paging) may be low-ROI if v2.0 React migration happens soon. Recommend Ralph check with Newt on admin-react-migration timeline before committing.

---

# Decision: Pre-built Base Image for embeddings-server Model Cache

**Author:** Brett (Infrastructure Architect)
**Date:** 2025-07-24
**Status:** Implemented (PR #1243)
**Context:** Issue #1231

## Problem

The embeddings-server Dockerfile's Stage 1 (`model-downloader`) installed sentence-transformers and downloaded the multilingual-e5-base model (~850 MB) on every build. This took ~15-20 minutes and was the dominant cost in CI, even when only application code changed.

## Decision

Replace the `model-downloader` build stage with a `FROM` reference to a pre-built base image (`ghcr.io/jmservera/embeddings-server-base:3.12-slim-multilingual-e5-base`) that caches the model at `/models/huggingface` and `/models/sentence_transformers`.

The base image is maintained in a separate repo (`jmservera/embeddings-server-base`) and only needs to be rebuilt when the model version changes.

## Rationale

- **Build time:** Code-only rebuilds drop from ~20 min to ~2 min
- **Layer caching:** Docker/GHCR caches the model layers; only changed app code layers are rebuilt
- **Separation of concerns:** Model versioning is decoupled from application code changes
- **No HF_TOKEN secret needed at build time:** The model is pre-baked in the base image

## Impact

- `src/embeddings-server/Dockerfile` Stage 1 is now a single `FROM` line
- `COPY --from=model-downloader` → `COPY --from=model-cache`
- Stages 2-4 (dependencies, app-builder, runtime) are unchanged
- CI builds that only change application code skip the model download entirely
- When the model needs updating, rebuild and push the base image first, then update the tag in the Dockerfile

---

# Decision: GPU acceleration via Compose override files (not profiles)

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-26
**Status:** Implemented (PR #1213)
**Context:** Issues #1153, #1154 (v1.17.0 GPU acceleration PRD)

## Problem

Need to support NVIDIA and Intel GPU acceleration for `embeddings-server` without breaking the default CPU-only deployment.

## Decision

Use **Compose override files** (`docker-compose.nvidia.override.yml`, `docker-compose.intel.override.yml`) instead of Compose profiles.

## Rationale

- Consistent with existing overlay pattern (`docker-compose.ssl.yml`, `docker-compose.e2e.yml`)
- Override files are self-documenting with prerequisite comments and usage examples
- No service name confusion (profiles create separate services like `embeddings-server-nvidia`)
- Override files can add `deploy.resources.reservations.devices`, `devices`, `group_add`, and `build.args` — all merge cleanly
- Base compose adds `DEVICE=${DEVICE:-cpu}` and `BACKEND=${BACKEND:-torch}` — zero change for existing users

## Impact

- Parker/Dallas: `DEVICE` and `BACKEND` env vars are now available in the embeddings-server container
- Installer scripts may need updating to support `-f docker-compose.nvidia.override.yml` flag
- Future: `docker-compose.prod.yml` should also support the GPU overrides (verified: works with `-f docker-compose.prod.yml -f docker-compose.nvidia.override.yml`)

---

# Decision: Local Path Loading for Offline HF Models (Supersedes snapshot_download)

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-28
**Status:** Implemented (base image: main, aithena: PR #1259)
**Context:** OpenVINO offline loading fails even with `snapshot_download()` caching

## Problem

The first fix (calling `snapshot_download()` before `SentenceTransformer()`) didn't work. While `snapshot_download()` caches model files, `optimum-intel`'s OpenVINO loading path makes an API call (`tree/main?recursive=True`) that is NOT covered by the snapshot cache. The offline verification step we added caught this failure at build time.

## Decision

1. **Save models to a known local directory** using `model.save('/models/sentence_transformers/{model_name}')` instead of relying on HF Hub cache.
2. **Load from local path at runtime** — when a directory exists at the expected path, pass it to `SentenceTransformer()` instead of the model name. Loading from a local directory bypasses ALL HF Hub API calls.
3. **Remove `snapshot_download()`** — unnecessary when saving to a local directory.
4. **Keep the offline verification step** — validates the local path loads correctly with `HF_HUB_OFFLINE=1`.

## Rationale

- A local directory path is the ONLY reliable way to get zero HF Hub calls with `optimum-intel` + openvino
- `SentenceTransformer('/path/to/model')` never touches the Hub — no metadata, no tree listings, no API calls
- Backward-compatible: if the local path doesn't exist (no base image), falls back to hub download
- The offline verification step caught the `snapshot_download()` failure, proving its value as a build-time safety net

## Impact

- Base image (`embeddings-server-base`): Dockerfile updated, pushed to main
- Aithena (`src/embeddings-server/main.py`): Checks for local path before hub fallback (PR #1259)
- Pattern applies to any future base image that pre-caches HF models for offline use

---

# Decision: Similar Books Endpoint: Chunk ID Resilience

**Date:** 2026-03-28  
**Author:** Parker  
**Status:** Implemented (PR #1262, #1263; tagged v1.17.0)

## Context

Semantic search returns chunk document IDs (e.g., `abc123_chunk_0000`) to the frontend because embeddings live on chunk documents, not parent book docs. When users click "similar books" from a semantic search result, the UI was sending the chunk ID to the endpoint, which expected a parent book ID.

## Decision

1. **Frontend data enrichment:** Added `parent_id` field to `normalize_book()` response, so the frontend receives both the chunk ID and parent book ID.

2. **Backend resilience:** The `similar_books` endpoint now detects chunk IDs (by checking for `"_chunk_"` in the ID) and automatically resolves them to the parent book ID before proceeding.

## Why This Matters

- **User experience:** "Similar books" works seamlessly from semantic search results
- **API robustness:** Callers don't need to know whether they have a chunk ID or parent ID
- **Data model transparency:** The parent/chunk separation is an internal Solr implementation detail that shouldn't leak into the user-facing API

## Files Changed

- `src/solr-search/search_service.py` — `normalize_book()` now returns `parent_id`
- `src/solr-search/main.py` — `similar_books()` resolves chunk IDs to parent IDs
- `src/solr-search/tests/test_search_service.py` — test updated for new field
- `src/aithena-ui/src/pages/SearchPage.tsx` — uses `parent_id` for similar books
- `src/aithena-ui/src/Components/BookDetailView.tsx` — similar books call updated
- `src/aithena-ui/src/hooks/search.ts` — type definitions include `parent_id`

---

# Decision: GPU Config Design for embeddings-server

**Author:** Parker (Backend Dev)
**Date:** 2026-03-25
**Status:** Proposed (PR #1215)
**Context:** Issues #1152, #1151 — v1.17.0 GPU Acceleration PRD

## Decision

GPU device and backend selection uses two environment variables (`DEVICE`, `BACKEND`) with defaults that produce identical behavior to pre-change code. OpenVINO is an optional Dockerfile build arg, not a runtime dependency.

## Key Design Choices

1. **Kwargs only when non-default:** `DEVICE=cpu` and `BACKEND=torch` pass zero extra kwargs to SentenceTransformer. This guarantees backward compatibility without conditional logic in downstream consumers.

2. **`DEVICE=auto` maps to `None`:** Lets PyTorch's internal device detection run (CUDA > CPU fallback). Useful for environments where GPU availability isn't known at config time.

3. **OpenVINO as build arg:** `INSTALL_OPENVINO=true` installs ~150MB of optional deps into `.venv`. Not in `pyproject.toml` because it's an acceleration backend, not a core dependency. This keeps the default image slim.

4. **Endpoint exposure:** `/health` and `/version` include `device` and `backend` fields so operators can verify GPU config without checking env vars directly.

## Impact

- Docker Compose files may add `DEVICE` and `BACKEND` env vars for GPU-enabled deployments
- CI/CD pipelines that build embeddings-server can pass `--build-arg INSTALL_OPENVINO=true` for Intel GPU targets
- No changes needed for existing CPU-only deployments

---

# Decision: Three-Mode Pre-release Trigger Pattern

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-26
**Status:** Implemented (PR #1248)
**Context:** Issue #1246

## Problem

The pre-release workflow (`pre-release.yml`) previously had only two activation modes:
1. `pull_request: branches: [main]` — Dry-run on release PR validation
2. `workflow_dispatch` — Manual trigger with custom version/RC number

This meant that on every dev push (after PR merge), the team had to manually trigger a workflow dispatch to publish RC containers. This was error-prone and created friction in the release pipeline.

## Decision

Added a third trigger mode: **`push: branches: [dev]`** that automatically builds and publishes RC containers whenever code is merged to dev.

### Three-Mode Design

| Mode | Trigger | Behavior | Use Case |
|------|---------|----------|----------|
| **Dev Publish** | `push: branches: [dev]` | Build + push RC containers | Automatic on every merge to dev |
| **Release Validation** | `pull_request: branches: [main]` | Build only (dry-run) | Validate code builds before release tag |
| **Manual Override** | `workflow_dispatch` | Build + push with custom version | Backports, off-schedule releases |

### Implementation

**File:** `.github/workflows/pre-release.yml`

1. Added `push: branches: [dev]` to `on:` section
2. Updated `prepare` job condition to allow `push` events
3. Existing conditions handle the rest (build-and-push, smoke-test)

## Rationale

1. **Reduces toil:** Eliminates manual workflow dispatch for routine RC builds
2. **Faster feedback:** Developers get RC containers immediately after merge, not after manual trigger
3. **Backward compatible:** Existing dry-run and manual override flows unchanged
4. **Natural condition mapping:** The existing `event_name != 'pull_request'` condition naturally handles both modes

## Impact

- **Dev workflow:** Merging to dev now automatically triggers RC container publication
- **Release process:** Main branch PRs still validate with dry-run builds (no change)
- **Manual override:** `workflow_dispatch` still available for special releases (no change)
- **Smoke tests:** Now run for `push` events (advisory status)

---

# Decision: Remove INSTALL_OPENVINO build arg, use system-site-packages

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-26
**Status:** Implemented (PR #1257)
**Context:** Juanma request — simplify openvino build pipeline

## Problem

The `INSTALL_OPENVINO=true` build arg caused `uv sync --extra openvino` to reinstall `optimum-intel` and `openvino` inside the .venv, even though the openvino base image already ships those packages at the system Python level. This created duplicate packages, version drift risk, and unnecessary build complexity.

## Decision

Remove `INSTALL_OPENVINO` entirely. Instead, enable `include-system-site-packages = true` in the .venv's `pyvenv.cfg` so it inherits packages from the base image. The `BASE_TAG` build arg is the sole mechanism for selecting the openvino variant.

## Rationale

- Single source of truth: openvino packages come from the base image only
- Simpler Dockerfile: no conditional RUN block
- Smaller .venv: no duplicated openvino wheels
- `BASE_TAG` already selects the right base image — a second build arg was redundant

## Impact

- `docker-compose.intel.override.yml` no longer passes `INSTALL_OPENVINO`
- CI matrix (`build-containers.yml`) no longer passes `INSTALL_OPENVINO`
- `pyproject.toml` no longer has `[project.optional-dependencies] openvino`
- Docs updated to remove `INSTALL_OPENVINO` references
- **No runtime behavior change** — openvino packages are still available in the container

---

# Decision: GPU Base Image Variants & Env-Driven Platform Selection

**Author:** Ripley (Lead)  
**Date:** 2026-07-27  
**Status:** Proposed  
**Requested by:** Juanma (jmservera)  
**Context:** v1.17.0 GPU acceleration, follows decisions in `brett-embeddings-base-image.md`, `brett-gpu-compose.md`, `parker-gpu-config.md`, `ripley-gpu-prd.md`

### Part 1: embeddings-server-base repo — OpenVINO variant image

**Build two tags** from the `embeddings-server-base` repo:

| Tag | Contents | Size (est.) |
|---|---|---|
| `3.12-slim-multilingual-e5-base` | Python 3.12-slim + cached model (~850 MB) | ~1.2 GB |
| `3.12-slim-multilingual-e5-base-openvino` | Same as above + `optimum-intel` + `openvino` pre-installed | ~1.5 GB |

### Part 2: aithena repo — Dockerfile changes

- `ARG BASE_TAG` replaces the hardcoded base image reference
- The `INSTALL_OPENVINO` build arg and conditional `pip install` are removed
- An optional `cp` step makes base-image OpenVINO visible inside `.venv` (safe no-op on CPU image)

### Part 3: aithena repo — docker-compose changes

**Introduce `GPU_PLATFORM` env var** (or explicit `EMBEDDINGS_BASE_TAG`) that controls base image selection.

**Mapping table:**

| `GPU_PLATFORM` | `EMBEDDINGS_BASE_TAG` | `DEVICE` | `BACKEND` | Override file needed? |
|---|---|---|---|---|
| `cpu` (default) | `3.12-slim-multilingual-e5-base` | `cpu` | `torch` | No |
| `nvidia` | `3.12-slim-multilingual-e5-base` | `cuda` | `torch` | Yes — `docker-compose.nvidia.override.yml` |
| `intel` | `3.12-slim-multilingual-e5-base-openvino` | `xpu` | `openvino` | Yes — `docker-compose.intel.override.yml` |

### Part 4: .env.example additions

```bash
# ── GPU Platform ──────────────────────────────────────────────────────────────
# Set these for GPU-accelerated embeddings. Default is CPU-only (no changes needed).
DEVICE=cpu
BACKEND=torch
EMBEDDINGS_BASE_TAG=3.12-slim-multilingual-e5-base
```

### Part 5: docker-compose.prod.yml changes

Pre-built GHCR image already contains the correct base. CI publishes two image variants:
- `ghcr.io/jmservera/aithena-embeddings-server:1.17.0` (CPU/NVIDIA — torch only)
- `ghcr.io/jmservera/aithena-embeddings-server:1.17.0-openvino` (Intel — includes OpenVINO)

## Migration Path

### For existing CPU users
**Zero changes required.** All defaults remain `cpu`/`torch`/base tag without `-openvino`.

### For existing NVIDIA GPU users
1. Add to `.env`: `DEVICE=cuda` and `BACKEND=torch`
2. Keep using `-f docker-compose.nvidia.override.yml` for device passthrough

### For existing Intel GPU users
1. Add to `.env`: `DEVICE=xpu`, `BACKEND=openvino`, `EMBEDDINGS_BASE_TAG=3.12-slim-multilingual-e5-base-openvino`
2. Keep using `-f docker-compose.intel.override.yml` for device passthrough

---

# Decision: GPU Acceleration PRD for v1.17.0

**Author:** Ripley (Lead)  
**Date:** 2026-03-25  
**Status:** Proposed  
**Impact:** Architecture, release planning, documentation updates  
**Related Issues:** #1148–#1161 (14 work items), PRD: docs/prd/gpu-acceleration.md

## Problem

The embeddings-server runs on **CPU only**, limiting indexing throughput for users with available GPU hardware (NVIDIA, Intel). Indexing 50,000 documents takes 8–12 hours on CPU; with GPU it could take 2–4 hours (2–4× improvement).

## Decision

**Implement single-image, environment-variable-driven GPU acceleration:**

1. **Single Dockerfile** — One embeddings-server image with torch+cu128, OpenVINO (~150 MB), and sentence-transformers with native device/backend support

2. **Environment Variables for Configuration:**
   - `DEVICE` (auto/cpu/cuda/xpu) — controls PyTorch device selection; `auto` is default with fallback to CPU
   - `BACKEND` (torch/openvino) — controls inference engine; `torch` is default for NVIDIA/CPUs, `openvino` for Intel GPUs/CPUs

3. **Docker Compose override files for Hardware-Specific Setup:**
   - `docker-compose.nvidia.override.yml` activates nvidia-runtime and GPU capability directives
   - `docker-compose.intel.override.yml` activates /dev/dri device passthrough for Intel GPU
   - Default (no override) = CPU-only, unchanged behavior

4. **Auto-Fallback Strategy:**
   - If `DEVICE=auto` and CUDA unavailable → fall back to CPU (graceful, logged)
   - If `BACKEND=openvino` unavailable → fall back to torch

## Rationale

- Single image with env var configuration is standard Docker practice
- SentenceTransformer natively supports device/backend parameters (zero code changes)
- torch+cu128 is already installed (zero cost addition)
- OpenVINO adds ~150 MB (acceptable)

## Impact

- **Dockerfile:** Add OpenVINO package
- **Python code:** Modify model initialization to accept DEVICE/BACKEND env vars (4–5 line change)
- **Docker Compose:** Add override files with device passthrough directives
- **Documentation:** Add GPU acceleration section to user/admin manuals

## Acceptance Criteria

✅ **Must-Have:**
- DEVICE env var implemented (auto/cpu/cuda/xpu)
- BACKEND env var implemented (torch/openvino)
- OpenVINO integrated (binary size <= 300 MB added)
- Docker Compose override files for nvidia and intel
- E2E test on NVIDIA shows 2–4× throughput improvement
- E2E test on Intel GPU shows 1.5–2× improvement
- CPU-only deployment backward compatible (zero regressions)
- User and admin manuals updated with GPU setup instructions

---

# Decision: v1.18.0 PRD Batch Decomposition & Milestone Assignment

**Author:** Ripley (Project Lead)  
**Date:** 2026-03-26  
**Status:** DECIDED  
**Requested by:** Juanma (jmservera)

## Context

Four PRDs submitted for decomposition (CI/CD, stress testing, folder facet, BCDR). The milestones referenced (v1.9.0–v1.11.0) are outdated. v1.16.0 just released; v1.17.0 active with 15 GPU issues.

## Decision

All 25 work items (8 CI/CD, 6 stress testing, 4 folder facet, 7 BCDR) assigned to **v1.18.0**, a new infrastructure-focused milestone.

### Milestone Rationale

- **v1.17.0** already has 15 GPU acceleration issues. Adding 25 more infrastructure items = 40-issue milestone with split focus.
- **v1.18.0** provides a dedicated lane for infrastructure, tooling, and performance work.
- **Scope:** Non-feature work — operational, testing, and search-infrastructure focused.

### Per-PRD Assignments

| PRD | Issues | Owner | Effort | Type |
|-----|--------|-------|--------|------|
| CI/CD Workflow Review | #1188–#1195 (8) | Brett | ~2 weeks | Tooling consolidation |
| Stress Testing Suite | #1196–#1201 (6) | Parker | ~5 weeks (phased) | Performance infrastructure |
| Folder Path Facet | #1202–#1205 (4) | Ash (backend), Dallas (UI) | ~2 weeks | Search feature |
| BCDR Plan | #1206–#1212 (7) | Brett | ~3 weeks | Operational resilience |

## Key Technical Decisions

### 1. Bandit as Hard Blocker

`security-bandit.yml` will enforce Bandit SAST findings as a **required** status check for dev and main PRs (currently non-blocking).

**Rationale:** Prevents critical vulnerabilities from being merged; Bandit is fast (~30s) and rarely produces false positives on this codebase.

### 2. Phase-Gated Stress Testing

Stress testing is strictly phase-gated: Phase 1 (infrastructure setup) must complete before Phase 2–6 benchmarks can run.

**Rationale:** Phase 1 builds shared test fixtures, data generators, Docker stats collectors; all subsequent phases depend on these foundations.

### 3. BCDR Tiers with RPO/RTO Targets

Three-tier backup system:
- **Critical** (auth DB, collections DB, secrets): RPO < 1 hour, RTO < 5 min, every 30 min
- **High** (Solr + ZooKeeper): RPO < 24 hours, RTO 15–60 min, daily 2 AM
- **Medium** (Redis + RabbitMQ): RPO < 4 hours, RTO 5–15 min, daily 3 AM

**Rationale:** Tiered approach keeps backup costs reasonable while protecting against realistic failure scenarios.

### 4. Folder Facet as Zero-Schema Work

Folder path facet requires **zero schema changes** — the `folder_path_s` field is already indexed and stored.

**Rationale:** Backend work is trivial (3-line addition); frontend work is medium (hierarchical tree component); no risk of Solr reindexing or downtime.

## Acceptance Criteria

- [ ] All 25 issues assigned to v1.18.0 milestone
- [ ] Each issue has clear acceptance criteria and PRD reference
- [ ] Team routing is clear (Brett: CI/CD + BCDR, Ash: folder facet backend, Dallas: UI, Parker: stress testing)
- [ ] Phase dependencies documented (stress testing Phase 1 blocks 2–6; BCDR scripts block restore)
- [ ] User review confirms scope and priorities before squad assignment

