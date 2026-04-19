# Brett — History

## Core Context — Infrastructure Patterns

### Docker Compose Architecture
- **17 containers:** SolrCloud 3-node cluster + ZooKeeper 3-node ensemble, Redis, RabbitMQ, nginx, 6 Python services, admin UIs
- **Health checks:** 8+ checks with context-specific `start_period` (10-60s). See skill `docker-health-checks`
- **Resource limits:** Memory (128m-2g), CPU (0.5-1.0), log rotation (json-file, 10m × 3 files)
- **Restart policies:** `unless-stopped` (stateful), `on-failure` (stateless workers)
- **Graceful shutdown:** `stop_grace_period` 60s (Solr/ZK), 30s (RabbitMQ/Redis), 10s (others)
- **Dependency ordering:** Always `condition: service_healthy` for critical deps; never bare `depends_on`
- **Port strategy:** Only nginx publishes host ports (80/443); all others use `expose:` only
- **Compose overlays:** `docker-compose.ssl.yml` for certbot/TLS; profiles can't add volumes to other services

### Bind-Mount Permissions (Recurring Pattern)
Bind-mount ownership is **always the host's**. Dockerfile `RUN chown` only applies to the image layer, not bind-mounted paths.
- **Solr:** UID 8983 for `/var/solr/data` volumes
- **Redis:** UID 999 | **RabbitMQ:** UID 100 | **nginx:** UID 101
- **Python services (app user):** UID 1000 (auth DB, collections DB)
- **Named volumes** don't have this problem — Docker initializes them from the image layer
- **Installer/setup scripts** must `chown` bind-mount dirs to match container UIDs

### SolrCloud & ZooKeeper Operations
See skill `solrcloud-docker-operations` for full runbook. Key points:
- ZK quorum = 2 of 3 nodes; losing 2 = write outage
- Solr nodes recover via peer sync, tlog replay, or full replication after restart
- Collection creation via solr-init one-shot container; consumers poll with exponential backoff
- Back up ZK state and Solr data independently — Solr disks alone aren't enough for restore

### nginx Reverse Proxy
- Routes: `/admin/solr/`, `/rabbitmq/`, `/streamlit/`, `/redis/`, frontend (5173), API (8080)
- Health endpoint: `GET /health` (200 "healthy", `access_log off`)
- Starts LAST (`depends_on` all upstreams healthy) to avoid 502 errors

### Build Contexts
| Service | Context | Pattern |
|---------|---------|---------|
| admin, solr-search | `.` (repo root) | Shared deps, `src/{service}/` COPY paths |
| embeddings-server, document-lister, document-indexer, aithena-ui | `./src/{service}` | Isolated, relative paths |

### Docker Image Optimization (Audit Results, v1.7.1 spec)
- **Total image size:** 2.3 GB → 1.44 GB possible (−38%) via multi-stage builds
- **Security gap:** Zero non-root users across Python services (P0 fix)
- **embeddings-server:** Largest at 850 MB; uses pip (not uv), pre-downloads ML model
- **embeddings-server packaging:** Has both `pyproject.toml`+`uv.lock` AND `requirements.txt`; convention treats it as requirements.txt service

### Release Process & Versioning
- **Docs-gate-the-tag:** Release docs merged to `dev` BEFORE version tag created
- **VERSION file:** Source of truth; `buildall.sh` exports `VERSION`, `GIT_COMMIT`, `BUILD_DATE`
- **GHCR distribution:** `docker-compose.prod.yml` uses image pulls (no build in prod)
- **Release automation:** `release.yml` on `v*.*.*` tags → build/push → tarball asset
- **Screenshot pipeline:** integration-test → `release-screenshots` artifact → `update-screenshots.yml` → commits PNGs to `docs/screenshots/` on `dev`

### CI/CD & Workflow Security
- **Secrets:** `with:` parameters only (never step-level `env:`); always `${{ secrets.X }}` syntax
- **IaC scanning:** Checkov (`.checkov.yml`, soft_fail, SARIF upload); all skip rules documented
- **Zizmor compliance:** All `${{ }}` expressions in `env:` blocks, not in `run:` blocks
- **Actions pinning:** All actions SHA-pinned
- **CI split:** Fast checks (~5 min) on dev PRs; full E2E (60 min) on main/release only
- **Dependabot:** Auto-merge patch/minor with CI gate; failures get `dependabot:manual-review` label
- **Cross-workflow artifacts:** Use `actions/github-script` REST API (not `actions/download-artifact`) for `workflow_run` triggers

### BCDR Planning (v1.10.0)
- **3-tier backup strategy:** Critical (SQLite + secrets), High (Solr + ZK), Medium (Redis + RabbitMQ)
- **Auth DB migrations:** Forward-only with `schema_version` table; SQLite `.backup` for snapshots
- **Collections DB:** New volume mount `/data/collections/`, env var `COLLECTIONS_DB_PATH`
- **Pre-release validation:** `e2e/pre-release-check.sh` scans compose logs for 9 categories; POSIX-compatible
- **Stress testing:** Docker SDK `container.stats(stream=False)` for metrics; OOM detection via events API

---

## Key Learnings (Distilled)

### RabbitMQ Credentials
Credentials only applied on first Mnesia DB creation. Stale volumes retain old credentials. Must clear bind-mount dirs completely on upgrade. Feature flags must be enabled before 3.x → 4.0 upgrade.

### Health Check Debugging
- `CMD` = array format (no shell expansion) vs `CMD-SHELL` = string passed to `/bin/sh -c`
- For Node.js containers without curl/wget, use built-in `http` module with explicit timeout
- `start_period` must account for worst-case init; pad 2-3x in CI environments
- Piping to grep in health checks causes SIGPIPE — simplify or avoid

### Compose Overlay vs Profiles
Use overlay files (not profiles) when making a sidecar optional affects the main service's volume mounts or port bindings. Profiles can't conditionally modify other services.

### GitHub Actions Patterns
- `workflow_run` event for cross-workflow orchestration; scope to branch + success
- Heredocs consume stdin in shell steps — use subprocess piping instead
- GitHub label hierarchies aren't enforced; ensure parent labels via event-driven + periodic audit
- GitHub Data API requires `workflow` scope for `.github/workflows/` modifications

### Docker SDK for Monitoring
`container.stats(stream=False)` for structured metrics. Events API with `{"event": ["oom", "die"]}` for OOM detection. Service collectors need graceful fallback (debug-level logging).

---

## Completed Work (Summary)

| Date | Issue/PR | What |
|------|----------|------|
| 2026-03-14 | — | Joined as Infra Architect; SolrCloud research |
| 2026-03-16 | #304, #303, #356 | Release-docs fixes, health check timing |
| 2026-03-17 | #363/PR#427 | Release packaging (GHCR, tarball, prod compose) |
| 2026-03-17 | PR#403 | RabbitMQ 4.0 upgrade + ZK health check fix |
| 2026-03-17 | PR#424 | redis-commander health check fix |
| 2026-03-17 | — | CI test strategy restructuring (fast dev / full E2E) |
| 2026-03-18 | PR#539 | Squad label sync fix (parent label enforcement) |
| 2026-03-19 | #531/PR#536, #532/PR#537 | Screenshot pipeline (artifact + commit workflow) |
| 2026-03-19 | — | Docker Compose diagnostic (auth DB bind-mount UID) |
| 2026-03-20 | — | Compose build audit; found admin missing from prod.yml |
| 2026-03-20 | — | v1.10.0 PRD decomposition (19 issues for BCDR + CI/CD) |
| 2026-07-22 | #557/PR#571 | Auth DB migration framework + backup script |
| 2026-07-24 | #470/PR#485, #483/PR#486 | Dependabot CI hardening + heartbeat integration |
| 2026-07-24 | — | Docker build optimization spec (v1.7.1) |
| 2026-07-25 | #542/PR#544 | Pre-release validation workflow + log analyzer |
| 2026-07-25 | — | Certbot extraction to ssl overlay |
| 2026-07-25 | — | setupdev.sh expansion (all dev tools) |
| 2026-03-16 | — | Cleaned 44 stale branches; enabled auto-delete |
| 2026-03-22 | #826/PR#847 | nginx static thumbnail serving (volume mount + /thumbnails/ location) |
| — | #1120 | Extract reusable container build workflow (build-containers.yml) |
| — | #1123 | Pre-release container workflow (RC tags via build-containers.yml, auto-increment) |
| — | #1118/PR#TBD | RC smoke tests in pre-release workflow (same matrix as release.yml, advisory) |
| — | #1153,#1154/PR#1213 | GPU compose override files (NVIDIA + Intel) for embeddings-server |
| — | #1286 | Add intel-extension-for-pytorch (IPEX) to openvino extras |
| — | #1325/PR#1328 | BuildKit --mount=from + --inexact for embeddings-server layer optimization (~95% reduction) |

---

## Learnings

### GPU Compose Override Pattern
- Used override files (`docker-compose.nvidia.override.yml`, `docker-compose.intel.override.yml`) rather than profiles — consistent with existing ssl/e2e overlay pattern
- `DEVICE` and `BACKEND` env vars in base compose default to `cpu`/`torch` for backward compatibility
- NVIDIA: `deploy.resources.reservations.devices` with `driver: nvidia` and `capabilities: [gpu]`
- Intel: `/dev/dri` device passthrough + `video` group_add + `BASE_TAG` build arg (selects openvino base image)
- Key files: `docker-compose.nvidia.override.yml`, `docker-compose.intel.override.yml`

### HF Hub Offline Loading — Pre-Cached Local Model Directory
- `snapshot_download()` does NOT fully cache the API metadata `optimum-intel` needs (`tree/main?recursive=True` endpoint)
- Base images pre-cache models into a local directory during build using `m = SentenceTransformer(name, backend='openvino'); m.save('/models/...')`
- Runtime: `os.path.isdir(local_path)` → load from disk (zero HF Hub API calls); fall back to hub if missing (backward-compat)
- Always add an offline verification RUN step (`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -c "SentenceTransformer('/models/...')"`) to fail-fast during build
- Key files: `embeddings-server-base/Dockerfile`, `src/embeddings-server/main.py`

### IPEX Dependency for Intel XPU (Issue #1286)
- `intel-extension-for-pytorch` (IPEX) is required in the openvino extras for Intel GPU/XPU inference
- Without IPEX, PyTorch detects Intel GPU hardware but cannot dispatch to it — inference fails at runtime
- IPEX 2.8.0 resolved cleanly against torch 2.10.0 and sentence-transformers 5.3.0 (no version conflicts)
- No Dockerfile or config changes needed — IPEX is pulled in automatically via `uv sync --extra openvino`
- The CPU/torch variant is unaffected; IPEX is only installed when `INSTALL_OPENVINO=true`
- Key file: `src/embeddings-server/pyproject.toml`

### Container Group Gotcha
- `group_add: [render]` in Docker Compose fails if the `render` group doesn't exist inside the container image
- The `render` group is a host-level Linux concept for GPU DRM access; slim Python images don't have it
- For WSL2 Intel GPU (`/dev/dxg`), only `video` group is needed

### BuildKit `--mount=from` for Transient Build Tools (Issue #1325)
- `RUN --mount=from=image,source=/bin,target=/usr/local/bin/tool` bind-mounts a file from another image for the duration of a single RUN command only — it never appears in any image layer
- This is the preferred pattern for build tools (uv, cargo, etc.) that should not ship in runtime images
- `COPY --from=image /tool /usr/local/bin/tool` creates a permanent layer — use `--mount=from` instead when the tool is only needed during build
- Docker COPY always writes the full directory content as a new layer regardless of what exists in the base — it does NOT deduplicate against base layers. This makes multi-stage "build→COPY .venv→runtime" ineffective when both stages share the same base with a pre-populated .venv
- `uv sync --inexact` preserves existing packages and only installs the delta — combine with `--mount=from` for minimal layers (~200MB vs ~4GB)
- Requires `# syntax=docker/dockerfile:1` directive for cross-version compatibility; BuildKit is default since Docker 23.0+ and already enabled in CI via `docker/setup-buildx-action`
- Key file: `src/embeddings-server/Dockerfile`

### OV Cache Location — /app over /tmp
- OpenVINO cache dir moved from `/tmp/ov_cache` to `/app/ov_cache` for consistency — owned by `app` user, inside WORKDIR
- `/tmp` should be avoided for persistent cache in containers (ephemeral, sometimes noexec-mounted)

### Cross-Repo Coordination for Base Image Changes
- Base image changes (jmservera/embeddings-server-base) and app Dockerfile changes (jmservera/aithena) must be coordinated as a breaking pair
- Created issue in base repo (embeddings-server-base#4) with full Dockerfile specs for both variants
- App-side PR is intentionally DRAFT/BLOCKED until base image is updated

## Reskill Notes (2026-07-25)

### Self-Assessment
- **Strongest areas:** Docker Compose orchestration, health check design, SolrCloud operations, CI/CD workflow security
- **Growth areas:** Have moved from pure infra into BCDR planning, stress testing, and release automation
- **Knowledge gaps:** Container runtime security (seccomp/AppArmor profiles), Kubernetes migration path (if ever needed), advanced BuildKit features (cache mounts, heredoc syntax in Dockerfiles)

### What I Consolidated
- Compressed 599 lines → ~120 lines of Core Context + distilled learnings + work log table
- Merged 15+ detailed PR entries into pattern summaries (health checks, bind-mounts, workflows)
- Removed duplicate content already covered by skills (docker-compose-operations, docker-health-checks, solrcloud-docker-operations)
- Removed verbose screenshot pipeline architecture docs (decision already in `.squad/decisions.md`)
- Removed stale sprint manifests and queued task tracking

### Skills Coverage
- `docker-compose-operations` — comprehensive, covers lifecycle and troubleshooting
- `docker-health-checks` — comprehensive, covers all 8 service patterns
- `solrcloud-docker-operations` — comprehensive, covers backup/restore/recovery
- **Gap identified:** nginx patterns scattered across history; build context patterns not in a skill
- **Gap identified:** Bind-mount permission patterns are the #1 recurring issue but only partially covered in docker-compose-operations

## Additional Historical Context (Summarized)

### Release Process Enhancements
- **Security mandatory (v1.14.0):** All releases must pass Bandit/Checkov/zizmor/CodeQL with no critical/high findings; Dependabot alerts reviewed; threat assessment on significant features
- **BCDR Validation (v1.14.0):** Restore scripts support `DRY_RUN=1` for CI mock environments; exit code 2 (warnings) acceptable; pytest markers for infrastructure-dependent tests
- **Production e5 Migration Plan (2026-03-26):** Blue/green deployment strategy documented; 7-step process with rollback (<5 min); parity verification + 48h monitoring

### Release Optimization Analysis
- **Asymmetric changes:** v1.8.0–v1.11.0 shows 78% commits in 2 services; embeddings-server (9GB, 1 commit) rebuilt 3× unnecessarily
- **Recommendation:** Change-detection CI (40% build time savings, 1 week effort, low risk) — detect changed services via `git diff`, skip builds for unchanged, retag images

### Additional Technical Decisions Documented in `.squad/decisions.md`
- 4-stage Dockerfile optimization for embeddings-server (independent layer caching)
- Non-root container patterns (Alpine + Debian)
- HSTS + security headers in nginx SSL config
- Offline installer architecture (3-stage)
- A/B testing human evaluation UI (SQLite storage, nDCG@10+MRR metrics)
- ZooKeeper AdminServer hardening

---

## v1.17.0 GPU Acceleration: Admin Manual Documentation (WI-11, 2026-03-25)

### Work Item WI-11: Admin Manual GPU Documentation

**PR #1216 opened (squad/1158-admin-manual-gpu).** Operator documentation for GPU deployment and troubleshooting.

**Content added to admin-manual.md (137 lines):**
- Architecture section: `DEVICE` and `BACKEND` environment variable reference table
- NVIDIA GPU prerequisites, Container Toolkit installation (Ubuntu/Debian), host + Docker verification
- Intel GPU prerequisites, compute-runtime installation, device verification
- WSL2 GPU passthrough patterns for both vendors (Windows driver requirement emphasized)
- Docker Compose override file usage pattern (`-f docker-compose.nvidia.override.yml`)
- Embeddings-server health endpoint verification with expected GPU output
- Troubleshooting table: 5 symptoms with diagnosis and resolution

**Key learning for ops:** WSL2 GPU passthrough differs significantly by vendor:
- **NVIDIA:** `/dev/dxg` exposed by WSL2 automatically; install drivers on Windows host; install Container Toolkit inside WSL
- **Intel:** `/dev/dri/renderD128` exposed by WSL2; install drivers on Windows host; container override maps `/dev/dri` into container
- **Critical:** Both vendors require GPU drivers installed on the Windows host, not inside WSL. This is the #1 failure point.

**Placement:** Section added after "Deployment with Docker Compose" section (logical flow for first-time operators). Appears before "Backup dashboard and restore workflow" section.

## v1.18.1 Release (2026-03-29)

### Issue #1286: Add intel-extension-for-pytorch to OpenVINO extras

**Completed:** 2026-03-29T10:10:00Z

Added `intel-extension-for-pytorch` (IPEX) to `src/embeddings-server/pyproject.toml` openvino extras group. Regenerated `uv.lock`. 52 tests pass.

**Key insight:** IPEX is the required bridge between PyTorch and Intel's XPU runtime. Without it, PyTorch detects Intel GPU hardware but cannot dispatch inference to it. IPEX 2.8.0 resolves cleanly with torch 2.10.0 — no version conflicts.

**Architecture:** Dependency chain: `uv sync --extra openvino` pulls in IPEX automatically. CPU-only builds (without `--extra openvino`) are unaffected. Existing `docker-compose.intel.override.yml` continues to work without changes.

---

## 2026-03-31T13:16Z — BuildKit Dockerfile Implementation Complete

**Status:** ✅ PR #1328 implemented. All 61 tests passing. Base image PR merged and images published.

**What happened:**
- Implemented `--mount=from=ghcr.io/astral-sh/uv:0.11.2` bind mount in `src/embeddings-server/Dockerfile`
- Reduced multi-stage COPY pattern to single-stage build
- Layer size: 13GB → 37MB (99.7% reduction when base cached)
- Key flags: `uv sync --inexact --frozen --no-dev` (preserves base packages, installs delta only)
- uv pinned to specific version tag for reproducibility (no floating `:latest`)

**Decision:** `.squad/decisions.md` updated with full analysis and rationale.

**Cross-reference:** Parker's base image work (orchestration log 2026-03-31T13-16Z-parker-base-dockerfiles.md) unblocks next steps.

---

## 2026-04-02 — Solr 9.7 Auth Role Alignment (#1332)

**Status:** ✅ PR #1333 created targeting dev (post-v1.18.1 hardening).

**Root cause:** Solr 9.7's `solr auth enable` assigns all 4 built-in roles (superadmin, admin, search, index) to the created user. Our solr-init script was calling `set-user-role` afterward, overwriting these to just `["admin"]`, stripping superadmin (needed for security-edit) and search (needed for collection-admin-read).

**Fix applied:**
- Removed set-user-role call for admin user in both docker-compose.yml and docker-compose.prod.yml
- Changed readonly user role from custom "readonly" to Solr 9.7 built-in "search" role
- Updated security.json to use the 4-tier built-in role hierarchy (superadmin > admin > search > index)
- Tests updated to verify admin roles are NOT overwritten and readonly gets "search" role

**Key learning:** In Solr 9.7, `solr auth enable` handles admin role assignment automatically. Never overwrite with `set-user-role` for the admin user — it strips critical roles. The built-in "search" role replaces custom "readonly" and includes collection-admin-read permissions.

## 2026-04-19 — Dependabot Batch Merge Workflow

### Bug Fix
- `dependabot-automerge.yml` line 41: `dependabot[bot]` → `app/dependabot` — the `gh pr list --json author` returns `app/dependabot` as the login, not `dependabot[bot]`. This was the root cause of 38 PRs piling up unmergeable.

### New Workflow: `dependabot-batch-merge.yml`
- Consolidates N dependabot PRs into a single `dependabot/batch-YYYY-MM-DD` branch
- Lockfile conflict resolution: `uv lock` for Python services, `npm install --package-lock-only` for aithena-ui
- Major version bumps excluded automatically (per team policy in decisions.md)
- VERSION file patch-bumped only when actual changes merged
- Dry-run mode via workflow_dispatch for safe preview
- Both workflows coexist: auto-merge for day-to-day, batch-merge for backlogs

### Key Files
- `.github/workflows/dependabot-automerge.yml` — single-PR auto-merge (fixed)
- `.github/workflows/dependabot-batch-merge.yml` — new batch workflow
- `.squad/decisions/inbox/brett-dependabot-batch.md` — design decision
