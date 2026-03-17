## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

---

# Brett — History

## Project Context
- **Project:** aithena — Book library search engine with Solr full-text indexing, multilingual embeddings, PDF processing, and React UI
- **User:** jmservera
- **Stack:** Python (backend services), TypeScript/React + Vite (UI), Docker Compose, Apache Solr (search), multilingual embeddings
- **Joined:** 2026-03-14 as Infrastructure Architect (Docker, Compose, SolrCloud)
- **Current infrastructure:** SolrCloud 3-node cluster + ZooKeeper 3-node ensemble, Redis, RabbitMQ, nginx, 9 Python services in Docker
- **Active initiative:** UV migration across 7 Python services (issues #81-#87), security scanning (#88-#90), CI hardening

## Core Context

**SolrCloud Docker Operations (Standardized):**
- **Cluster topology:** 3-node ZooKeeper ensemble + 3-node Solr cloud cluster, all healthy. ZooKeeper AdminServer 8080 and Solr node 1 port 8080 create host-port collision (namespace works but needs cleanup).
- **Service startup:** Depends_on uses `service_started` instead of `service_healthy` — services can start before infra is ready. Missing health checks for Solr and ZooKeeper are critical gap.
- **Volume strategy:** All bind-backed local volumes pointing to `/source/volumes/` + `/home/jmservera/booklibrary`. Solr mounts `/var/solr/data` only (no persistent logs). Backup path configured but not mounted.

**CI/CD & Build:**
- `buildall.sh` runs `uv sync` in all 4 uv-managed Python services (`admin`, `document-indexer`, `document-lister`, `solr-search`), skips `embeddings-server` (no pyproject.toml).
- GitHub Actions: `ci.yml` runs Python unit tests + ruff linting, `lint-frontend.yml` for React, `release.yml` coordinates releases.
- All 4 Python services migrated to uv + `pyproject.toml` + `uv.lock`.

**nginx Reverse-Proxy Ingress:**
- Routes `/admin/solr/`, `/admin/rabbitmq/`, `/admin/streamlit/`, `/admin/redis/` to respective admin UIs (with X-Forwarded-Prefix, WebSocket upgrade support, path rewriting).
- Routes `/`, `/v1/`, `/documents/` to React app and solr-search API.
- No HTTPS or auth enforcement in current config (cert setup via ACME but HTTP-only).

**Known Infrastructure Bugs (Blocking v0.5):**
1. **#166 — RabbitMQ cold-start failure:** `timeout_waiting_for_khepri_projections` on first `docker compose up`. Second run succeeds. Root: Khepri metadata store projection registration race + stale volume state. Fix: increase health check retries/start_period, pin RabbitMQ version, or clear volume.
2. **#167 — Document pipeline stall:** New PDFs not detected/indexed. Cascaded from #166 (RabbitMQ unhealthy) + `depends_on: service_started` doesn't wait for health. Fix: add connection retry logic in services, use `service_healthy` conditions.

**Docker Compose Gaps vs Skill (High Priority):**
- ❌ No health checks for Solr (should be curl to `/admin/info/system`)
- ❌ No health checks for ZooKeeper (should be 4LW `ruok`)
- ❌ `depends_on` uses `service_started` instead of `service_healthy`
- ❌ ZooKeeper has no restart policy (`unless-stopped` needed)
- ❌ No `stop_grace_period` for Solr/ZooKeeper
- ❌ No `SOLR_HEAP` or memory limits
- ❌ No Docker log caps
- ❌ No backup path mount on Solr nodes
- ❌ Solr volumes only mount `/var/solr/data`, not full `/var/solr`

## Learnings

<!-- Append learnings below -->

### Release checklist and docs-gate-the-tag pattern

**Decision:** Release docs must be generated and merged BEFORE tagging (Option B: docs gate the tag). This is formalized in `.github/ISSUE_TEMPLATE/release.md` with an ordered checklist.

**Key paths:**
- `.github/ISSUE_TEMPLATE/release.md` — release checklist issue template
- `.github/workflows/release-docs.yml` — generates release notes, test reports, and reviews admin/user manuals
- `.github/workflows/release.yml` — triggers on `v*.*.*` tags to build Docker images

**Token scope lesson:** GitHub blocks ALL Git Data API operations (trees, commits, refs) that touch `.github/workflows/` paths without the `workflow` scope. This includes the low-level Git Data API, not just the Contents API. When automating workflow file changes, ensure the token has `workflow` scope or use a GitHub App token with that permission.

**Manuals:** Both `docs/admin-manual.md` and `docs/user-manual.md` exist and are now included in the release-docs workflow Copilot CLI prompt for review each release.

### 2026-03-16T23:20Z — Retro Action: Clean up stale remote branches

**Task:** Address retro finding: 66 stale remote branches (38 from merged PRs + ~28 abandoned).

**Execution:**
1. Fetched and pruned remote branches (2 already removed by prior cleanup)
2. Identified 44 branches with merged PRs across `copilot/*` and `squad/*` patterns
3. Deleted all 44 in 9 batches of 5 branches each (smooth, no rate limiting)
4. Verified 21 remaining branches all have active PRs (not abandoned)
5. Protected branches kept: `main`, `dev`, `oldmain`, `squad/retro-migration-checkpoint`
6. Enabled GitHub repository setting `delete_branch_on_merge=true` — future merged PRs will auto-delete

**Outcome:**
- 44 branches deleted (44/66 identified in retro)
- Repository cleanup enables continuous head-branch housekeeping going forward
- Reduced cognitive load on branch navigation; retro concern resolved

**Branch breakdown:**
- `copilot/*`: 12 merged deletions + 6 active PRs remain
- `squad/*`: 32 merged deletions + 15 active PRs remain
- Active PR branches are features in flight; no deletion risk

### 2026-03-16T16:10Z — Issue #356: solr-search E2E health check timing

- The `solr-search` FastAPI container exposes a lightweight `/health` endpoint, but the app still runs auth DB initialization in its startup lifespan before that route is reachable.
- In CI, the original `start_period: 10s` for the Compose health check was too aggressive; increasing it to `30s` gives the container enough time to finish startup on slower runners without changing application code.
- The `solr-search` image already includes `wget`, so the E2E failure was a readiness-timing problem, not a missing health check binary.

### 2026-03-16T15:25Z — Issue #304: release-docs workflow validation

- Fixed a broken `gh run list | python3 - <<'PY'` pattern in `.github/workflows/release-docs.yml`; the heredoc consumed stdin, so integration-test run IDs were never parsed for artifact download.
- Added a release-context fallback so milestone-based PR queries can drop back to recent merged PRs on `dev` when no PRs are tagged with the selected milestone.
- Removed the stale `Closes #270` footer from generated release-doc PR bodies so future automation runs do not reference the original bootstrap issue.

### 2026-03-16T13:00Z — Issue #303: release-docs Copilot CLI refresh

- Updated `.github/workflows/release-docs.yml` to install only the official `@github/copilot` package and rely on the documentation template fallback when CLI installation or generation fails.
- Switched the workflow invocation to `copilot --agent squad --autopilot --allow-all-tools` and rewrote the prompt to address Newt explicitly as the release-doc author.
- Preserved the existing fallback template generation path so release-note and test-report drafts still land in `docs/` when Copilot CLI is unavailable.


### 2026-03-16T12:27Z — Validated CI/CD pipelines post-restructure (#224) [COMPLETE]

- ✅ Issue #224 closed. All workflows validated.
- Verified all workflow files for path correctness: ci.yml, lint-frontend.yml, version-check.yml, integration-test.yml.
- All working-directory and cache-dependency paths updated correctly.
- docker-compose.yml syntax valid; all service context paths and volume mounts reflect `src/...` structure.
- buildall.sh syntax check passes; Python service directory list updated to `src/admin`, `src/document-indexer`, etc.
- No broken working-directory or cache-dependency paths; git history preserved (git mv operations).
- Docker build contexts intentionally remain rooted at repo root (per Parker's design decision).
- CI/CD pipelines ready for merged PR on dev; downstream testing complete (Dallas #223 passed).
- Future improvement noted: consider adding Solr/ZooKeeper health checks in docker-compose.yml (separate issue).

### 2026-03-15 — Issue #204: GitHub Actions versioned release automation

- Replaced the old tag-only release workflow with a semver-validated GHCR publish pipeline for all six source-built services: `admin`, `aithena-ui`, `document-indexer`, `document-lister`, `embeddings-server`, and `solr-search`.
- The new `.github/workflows/release.yml` builds each image with `VERSION`, `GIT_COMMIT`, and `BUILD_DATE`, then publishes four release tags per image via `docker/metadata-action`: full (`X.Y.Z`), minor (`X.Y`), major (`X`), and `latest`.
- Kept GitHub Release publication in the workflow so the tag ceremony still produces release notes after all image pushes succeed.
- Added `.github/workflows/version-check.yml` to gate PRs into `dev` and `main` on a valid root `VERSION` file plus `ARG VERSION` declarations in the six release Dockerfiles.
- No `ci.yml` change was required because the existing CI workflow only runs on `dev` branch pushes/PRs, so it does not conflict with tag-triggered release publishing.

### 2026-03-14 — Reskill session: current infrastructure snapshot

**9 services operational:**
- Source-built: `aithena-ui`, `admin` (Streamlit), `document-lister`, `document-indexer`, `solr-search`, `embeddings-server`, `redis-commander`
- SolrCloud 3-node: `solr`, `solr2`, `solr3` (8983, 8984, 8985), all healthy
- ZooKeeper 3-node: `zoo1` (2181 + AdminServer 8080), `zoo2` (2182), `zoo3` (2183)
- Infrastructure: Redis 6379 (healthy ✓), RabbitMQ 5672/15672 (health check ✓ but cold-start fails #166)

**nginx reverse-proxy:**
- Admin ingress: `/admin/solr/`, `/admin/rabbitmq/`, `/admin/streamlit/`, `/admin/redis/` (with X-Forwarded-Prefix, WebSocket support, path rewriting)
- API ingress: `/v1/` and `/documents/` → solr-search, `/` → React app
- No HTTPS/auth in current config (cert setup ready but HTTP-only)

**Recommended priority fixes for v0.5:**
1. Fix #166 (RabbitMQ cold-start): increase health check retries, pin RabbitMQ version to 3.13 or 4.0
2. Add Solr + ZooKeeper health checks, switch `depends_on` to `service_healthy`
3. Fix #167 (document pipeline): add service connection retry logic
4. Harden ZooKeeper: add `unless-stopped` restart, consider autopurge
5. Move ZooKeeper AdminServer from 8080 to 18080 (collision with solr-search)
6. Mount Solr `/backup` path for persistent backups
7. Add resource limits: `SOLR_HEAP=1g`, memory limits, log caps
8. Add graceful shutdown: `stop_grace_period: 60s` for Solr/ZooKeeper
9. Expand Solr volume mount: `/var/solr` instead of just `/var/solr/data`

### 2026-03-14 — Production vs development port publishing split

- `docker-compose.yml` now leaves host publishing to `nginx` only (`80`/`443`); Redis, RabbitMQ, ZooKeeper, Solr nodes, solr-search, and embeddings stay network-internal via `expose:`.
- `docker-compose.override.yml` restores the local debug surfaces: Redis `6379`, RabbitMQ `5672`/`15672`, solr-search `8080`, Streamlit `8501`, Redis Commander `8081`, ZooKeeper `18080`/`2181`-`2183`, Solr `8983`-`8985`, embeddings `8085`.
- nginx already covers the UI and operator surfaces that production needs: `/`, `/v1/`, `/documents/`, `/admin/solr/`, `/admin/rabbitmq/`, `/admin/streamlit/`, `/admin/redis/`.
- This closes the earlier hardening gap about over-published Compose ports without breaking the local debugging workflow.

### 2026-07-24 — v0.6.0 Group 6: Docker Compose hardening spec for #52

**Task:** Review Ripley's v0.6.0 release plan and create production hardening specification for #52 (Phase 4 hardening).

**Current state assessment (20+ services analyzed):**
- ✅ **Already hardened:** Redis, RabbitMQ, ZooKeeper (zoo1-3), Solr (solr, solr2, solr3) have health checks and correct restart policies
- ✅ **Port security correct:** Prod/dev split already implemented (nginx-only publishing in base compose, debug ports in override)
- ❌ **Missing health checks (8 services):** embeddings-server, solr-search, document-lister, document-indexer, aithena-ui, streamlit-admin, redis-commander, nginx
- ❌ **Restart policy gaps:** redis/rabbitmq use `on-failure` (should be `unless-stopped`); ZooKeeper nodes missing restart policy entirely
- ❌ **No resource limits:** Zero services have memory/CPU limits or log rotation configured
- ❌ **No graceful shutdown:** Solr/ZooKeeper/RabbitMQ/Redis need `stop_grace_period` (60s/60s/30s/30s respectively)
- ❌ **depends_on gaps:** 5 services use `service_started` instead of `service_healthy` (embeddings in document-indexer, solr-search dependencies, nginx upstreams)
- 🔴 **CRITICAL BUG:** embeddings-server has port conflict (`expose: 8080` but `PORT=8085` env var) — health checks will fail until fixed

**Hardening spec deliverables (.squad/decisions/inbox/brett-hardening-spec.md):**
1. **Service-by-service health checks:** 8 new health checks with specific intervals/timeouts/retries/start_periods
2. **Restart policies:** 8 upgrades to `unless-stopped`, 3 new policies (ZooKeeper nodes)
3. **Resource limits:** Memory limits for all services (128m-2g), CPU reservations for Solr/embeddings (1.0 core), log rotation (10m × 3 files)
4. **Graceful shutdown:** `stop_grace_period` for Solr (60s), ZooKeeper (60s), RabbitMQ (30s), Redis (30s)
5. **Dependency fixes:** 5 changes from `service_started` → `service_healthy`
6. **Code changes:** Health endpoints for nginx (`/health`), solr-search (`/health`), embeddings-server (`/health`); fix embeddings port conflict
7. **Documentation:** New `docs/deployment/production.md` with startup order, resource requirements, volume initialization, health validation, backup/restore, troubleshooting

**Key architectural decisions:**
- **Tiered service classification:** Tier 1 (core infra: high availability), Tier 2 (stateless apps), Tier 3 (one-shot init)
- **Resource limit philosophy:** 2-2.5x observed usage headroom; CPU reservations (not hard limits) to avoid throttling; log rotation to prevent disk exhaustion
- **Health check timing:** Conservative `start_period` values (embeddings 60s for model loading, ZooKeeper/Solr 30s for cluster formation)
- **Dependency graph validation:** nginx is LAST to start (waits for all upstreams healthy) — ensures zero-downtime production startup
- **Dev workflow preservation:** No changes to docker-compose.override.yml; all hardening in base compose

**Changes to Ripley's plan:**
1. Expand #52 acceptance criteria to include resource limits + graceful shutdown + production guide
2. Group 6 can start in parallel with Groups 1-4 (no code dependencies except embeddings port fix)
3. Change issue label from `squad:parker` to `squad:brett` (hardening is infra domain, not backend)

**Implementation strategy for @copilot:**
- Order: Fix embeddings port conflict → add health endpoints → add health checks → update restart/limits/grace/deps → log rotation → documentation
- Validation: Cold start test, failure recovery test, graceful shutdown timing, resource limit check, log rotation verification
- PR checklist: 7 validation commands for Brett review gate

**Risk mitigations:**
- Embeddings port conflict (HIGH): Remove `PORT=8085` env var, standardize on 8080 internal
- False positive health checks (MEDIUM): All checks have appropriate `start_period` (10-60s)
- Resource limits too tight (HIGH): Conservative 2-2.5x headroom based on observed usage
- Graceful shutdown too short (MEDIUM): 60s grace = compromise between safety and operator patience

### 2026-03-15 — v0.6.0 Release Planning Complete

**Summary:** Docker hardening spec (#52) finalized and approved. Recorded in decisions.md. Ready for @copilot implementation after Groups 1-5 complete.

**Key Infrastructure Decisions Confirmed:**
- Health Checks: 8 new checks + 5 depends_on fixes (service_started → service_healthy)
- Restart Policies: `unless-stopped` for critical/stateful services
- Resource Limits: Memory (256m-2g) + CPU reservations + log rotation (10m × 3 files)
- Graceful Shutdown: 60s Solr/ZooKeeper, 30s RabbitMQ/Redis
- Critical Fix: embeddings-server port conflict (remove PORT=8085, standardize on 8080)
- Documentation: docs/deployment/production.md with startup order, requirements, troubleshooting

**Implementation Order:** Port fix → health endpoints → health checks → restart/limits/grace → depends_on fixes → log rotation → documentation

**Next:** Awaiting Juanma approval of release plan → Groups 1-5 execution → Issue #52 created + assigned → Implementation

### 2026-03-15 — SEC-2 Implementation: Checkov IaC Scanning

**Summary:** Implemented issue #89 (SEC-2) to add automated IaC security scanning to CI pipeline using checkov.

**Deliverables (PR #191):**
- `.github/workflows/security-checkov.yml`: GitHub Actions workflow for checkov scanning
  - Scans all Dockerfiles (admin, aithena-ui, document-indexer, document-lister, embeddings-server, solr-search)
  - Scans GitHub Actions workflow files (.github/workflows/*.yml)
  - Runs in `soft_fail` mode (non-blocking, per SEC-2 spec)
  - Outputs SARIF results and uploads to GitHub Code Scanning
  - Path-filtered triggers: only runs when Dockerfiles, workflows, or docker-compose files change
- `.checkov.yml`: Configuration with documented skip exceptions
  - `CKV_DOCKER_2` (HEALTHCHECK): Health checks managed centrally in docker-compose.yml
  - `CKV_DOCKER_3` (USER): Official base images run as non-root by default

**Key Design Decisions:**
- **Non-blocking enforcement:** `soft_fail: true` + `continue-on-error: true` ensures scans never block CI/CD
- **Path filtering:** Workflow only triggers on relevant file changes (Dockerfiles, .github/workflows/*, docker-compose*.yml) to avoid wasting CI minutes
- **SARIF integration:** Results uploaded to GitHub Security tab for centralized vulnerability tracking
- **Documented exceptions:** All skip rules include detailed justifications in .checkov.yml comments

**Validation:**
- Workflow syntax validated (GitHub Actions YAML structure correct)
- Configuration follows checkov best practices (framework specification, skip-check array format)
- PR targets `dev` branch per squad branching strategy

**Branch:** squad/89-sec2-checkov-scanning → dev
**Status:** PR #191 open, awaiting review

### 2026-03-15 — Issue #52 Implementation: Production Docker Hardening

**Summary:** Implemented complete production hardening specification for docker-compose.yml per Phase 4 requirements.

**Deliverables (PR #196):**

**1. Port Conflict Fix (Critical Bug)**
- Removed `PORT=8085` env var from embeddings-server in docker-compose.yml
- Updated embeddings-server config default from 8086 to 8080
- Fixed EMBEDDINGS_PORT in document-indexer (8085 → 8080)
- Fixed EMBEDDINGS_URL in solr-search (8001 → 8080)
- Resolves mismatch between `expose: 8080` and env vars

**2. Health Endpoints**
- Added `/health` endpoint to embeddings-server (returns status, model, embedding_dim)
- Added `/health` location to nginx (200 "healthy", access_log off)
- Verified solr-search already has `/health` endpoint

**3. Health Checks (8 new services)**
- embeddings-server: `wget http://localhost:8080/health` (60s start_period for model loading)
- solr-search: `wget http://localhost:8080/health`
- document-lister: `pgrep -f python`
- document-indexer: `pgrep -f python`
- aithena-ui: `wget http://localhost:80/`
- streamlit-admin: `wget /_stcore/health`
- redis-commander: `wget http://localhost:8081/`
- nginx: `wget http://localhost:80/health`

**4. Restart Policies**
- `unless-stopped` (14 services): redis, rabbitmq, zoo1-3, solr1-3, embeddings-server, solr-search, streamlit-admin, redis-commander, aithena-ui, nginx
- `on-failure` (2 services): document-lister, document-indexer (stateless workers)

**5. Resource Limits (all 20+ services)**
- Memory limits: 128m-2g range (2-2.5x observed usage headroom)
- Memory reservations: Conservative allocations prevent OOM cascade
- CPU reservations: Solr nodes 1.0 core each, embeddings 1.0, solr-search 0.5
- Log rotation: json-file driver, 10m × 3 files per service (30MB max)

**6. Graceful Shutdown (stop_grace_period)**
- 60s: Solr (solr, solr2, solr3), ZooKeeper (zoo1, zoo2, zoo3)
- 30s: Redis, RabbitMQ
- 10s: All other services

**7. Dependency Fixes (5 changes service_started → service_healthy)**
- document-indexer: embeddings-server condition upgraded
- solr-search: Added `condition: service_healthy` for solr and embeddings-server
- aithena-ui: Added `condition: service_healthy` for solr-search
- nginx: All upstreams now wait for `service_healthy` (aithena-ui, solr-search, streamlit-admin, redis-commander, solr)

**8. Production Deployment Guide**
- Created `docs/deployment/production.md` (509 lines)
- Sections: prerequisites, resource requirements (16GB RAM, 8+ cores), startup order (5 tiers, 3-5min cold start), volume initialization, health validation, graceful shutdown, monitoring/logging, troubleshooting, backup/restore
- Includes production hardening checklist (SSL, auth, firewall, monitoring)

**Key Architectural Decisions:**
- Tiered service classification: Tier 1 (core infra, high availability) → Tier 5 (nginx ingress, starts last)
- Resource limit philosophy: 2-2.5x observed usage headroom; CPU reservations (not hard limits) to avoid throttling
- Health check timing: Conservative start_period (60s embeddings, 30s ZK/Solr) prevents false positives
- Dependency graph validation: nginx waits for all upstreams healthy → zero-downtime production startup
- Dev workflow preservation: All hardening in base compose, no changes to docker-compose.override.yml

**Total System Requirements:**
- Memory: ~15GB limits, ~8GB reserved
- CPU: 8+ cores recommended (3 cores Solr + 1 embeddings + 0.5 search + overhead)
- Disk: 100GB+ for infrastructure volumes + library size

**Validation:**
- YAML syntax validated with Python yaml.safe_load()
- All service health checks have appropriate start_period and retries
- Dependency graph ensures correct startup order (verified via spec review)

**Branch:** squad/52-docker-hardening → dev
**Status:** PR #196 open, awaiting review
**Implementation Time:** ~2 hours (spec reading, implementation, validation, documentation)

**Learnings:**
- Health check start_period is critical for model-loading services (embeddings 60s) and cluster formation (ZK/Solr 30s)
- Log rotation prevents disk exhaustion in long-running production deployments (30MB per service × 20 services = 600MB max)
- depends_on service_healthy creates implicit startup ordering that matches tier-based dependency graph
- Resource reservations guarantee minimum allocation but allow bursting; limits prevent OOM cascade
- nginx should start LAST to ensure zero 502 errors during cold start (all upstreams must be healthy first)

### 2026-03-15 — Issue #199: container version metadata baseline

- Added a root `VERSION` file (`0.7.0`) as the repo fallback for container image versioning.
- Standardized all six source-built Dockerfiles to accept `VERSION`, `GIT_COMMIT`, and `BUILD_DATE`, publish OCI labels, and expose the same metadata at runtime via environment variables.
- Updated `docker-compose.yml` so every source-built service passes the version metadata as build args, preserving existing health checks, restart policies, and resource limits.
- `buildall.sh` now resolves the image version from an exact git tag first (stripping a leading `v`), then falls back to `VERSION`, and exports `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` before `docker compose up --build -d`.
- Added `.env.example` entries for the version metadata so local builds and CI have a documented override surface.

### 2026-03-15 — Copilot Workflow Run Auto-Approval

**Summary:** Created `.github/workflows/copilot-approve-runs.yml` to automatically approve pending workflow runs on @copilot PRs.

**Problem:** When @copilot pushes to PR branches, GitHub Actions requires manual approval before running workflows (security feature for bot-authored changes). Team members keep forgetting to approve these runs, which blocks the entire review cycle. Instructions haven't worked — automation is needed.

**Solution:** New workflow that:
- Triggers on `pull_request_target` (opens, synchronize) — runs in trusted base-branch context, no approval required
- Guards on copilot author detection: `contains(fromJson('["copilot-swe-agent[bot]","app/copilot-swe-agent","copilot-swe-agent"]'), github.event.pull_request.user.login)`
- Waits 15 seconds for workflow runs to be created
- Lists runs for PR head SHA in `action_required` status
- Approves each via `github.rest.actions.approveWorkflowRun`
- Handles errors gracefully (GITHUB_TOKEN permission edge cases)

**Security:** pull_request_target runs trusted base-branch code. Never checks out PR code — API-only operations. Only approves runs from verified @copilot PRs.

**Learnings:**
- `pull_request_target` is the correct event for trusted automation on bot PRs (avoids approval chicken-and-egg)
- `actions: write` permission needed for `approveWorkflowRun` API
- The approve API endpoint: `github.rest.actions.approveWorkflowRun({ owner, repo, run_id })`
- Workflow runs aren't instant — 15s wait needed before querying
- `status === 'action_required'` is the filter for runs needing approval

**Branch:** squad/copilot-approve-runs → dev
**Decision:** Recorded in `.squad/decisions/inbox/brett-copilot-approve-runs.md`

### 2025-01-20 — Issue #224: CI/CD Pipeline Validation after src/ Restructure

**Summary:** Validated all CI/CD pipelines after PR #287 moved 9 service directories into src/. **Status: ALL VALIDATIONS PASSED** ✓

**Scope:** Comprehensive validation of 13 GitHub Actions workflows covering:
- document-indexer, solr-search (Python services)
- aithena-ui (Node.js frontend)
- admin, document-lister, embeddings-server (Docker services)

**Validation Results:**
1. **YAML Syntax:** All 13 workflows validated with Python yaml.safe_load() → ✓ PASS
2. **Service Paths:** 
   - ci.yml: working-directory refs → src/document-indexer ✓, src/solr-search ✓
   - lint-frontend.yml: working-directory & cache-dependency-path → src/aithena-ui ✓
   - integration-test.yml: e2e/ path refs ✓, src/solr-search for installer ✓
   - No old service path references found → ✓ PASS
3. **Dockerfile Validation:**
   - All 6 Dockerfiles exist in src/: admin, aithena-ui, document-indexer, document-lister, embeddings-server, solr-search
   - All declare ARG VERSION for release tagging → ✓ PASS
4. **Release Pipeline (release.yml):**
   - Build contexts: ./src/{admin,aithena-ui,document-indexer,document-lister,embeddings-server} ✓
   - solr-search: context=. with dockerfile=./src/solr-search/Dockerfile ✓ (requires root build context for COPY src/solr-search/)
   - version-check.yml: Dockerfile list updated for all 6 services ✓
5. **Docker Compose Configuration:**
   - Validated docker-compose.yml with AUTH env vars → ✓ PASS
   - Build contexts resolve correctly for all services
   - Cache build args propagate VERSION, GIT_COMMIT, BUILD_DATE ✓
6. **Squad Workflows:**
   - squad-heartbeat.yml, squad-issue-assign.yml: No service paths (team management) → ✓ PASS

**Key Findings:**
- PR #287 correctly updated all workflow paths to src/
- No remaining stale references to old service directory locations
- solr-search has special build context (root) but COPY paths are correct for that context
- Docker Compose validation passes with required environment variables

**Learnings:**
- The solr-search pattern (context=. + dockerfile=src/solr-search/Dockerfile + COPY src/solr-search/) is valid and intentional to satisfy multi-service COPY needs
- Integration tests correctly use `uv run --project src/solr-search` to execute installer from the right service context
- version-check.yml arrays must be manually updated when adding new Dockerfiles — no automation opportunity

**Time:** ~30 minutes (systematic validation of all 10 checklist items)
**Result:** Issue #224 closed — all CI/CD pipelines validated and correct ✓

### 2026-03-16 — Issue #294: Fix secrets-outside-env in squad-issue-assign.yml (#94) [PR #313]

**Summary:** Fixed security alert #94 by removing step-level `env:` block exposing `COPILOT_ASSIGN_TOKEN` in `.github/workflows/squad-issue-assign.yml`.

**Changes:**
- Removed `env: COPILOT_ASSIGN_TOKEN: ${{ secrets.COPILOT_ASSIGN_TOKEN }}` block from step
- Passed secret directly as inline parameter: `github-token: ${{ secrets.COPILOT_ASSIGN_TOKEN }}`
- This prevents the secret from being exposed as an environment variable in the step execution context

**Security rationale:**
- Secrets passed via `with:` parameters to actions are handled securely by the action runtime
- Exposing secrets in `env:` blocks makes them available to all commands in the step, increasing attack surface
- Direct parameter passing limits secret exposure to only the specific action that needs it

**Validation:**
- ✅ YAML syntax validated with `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/squad-issue-assign.yml'))"`
- ✅ No functional change — PAT still used to assign copilot-swe-agent bot
- ✅ Follows GitHub security best practices for workflow secrets handling

**Lessons learned:**
1. **Prefer inline secret parameters over env blocks:** When an action accepts a token parameter (like `github-token`), pass secrets directly via `with:` rather than through `env:`
2. **Zizmor secrets-outside-env rule intent:** The rule flags secrets that could be accessed by unintended commands or scripts in the step
3. **Step-level vs inline secrets:** Step-level `env:` makes secrets available to all bash commands; inline `with:` parameters restrict access to the action itself

### 2026-03-16 — Issue #305: Add release milestone labels for v1.x milestones [PR #315]

**Summary:** Added five new release milestone labels (v1.0.1 through v1.4.0) to the sync-squad-labels workflow automation.

**Changes:**
- Extended `RELEASE_LABELS` array in `.github/workflows/sync-squad-labels.yml` with:
  - `release:v1.0.1`, `release:v1.1.0`, `release:v1.2.0`, `release:v1.3.0`, `release:v1.4.0`
- Used blue color theme (`0075ca`) for v1.x labels to visually distinguish them from v0.x labels (which use `6B8EB5` and `8B7DB5`)
- Labels were already created manually by jmservera — this change brings them under automation control

**Rationale:**
- Issue #305 was assigned to v1.1.0 milestone, which triggered the need for milestone labels
- Labels need to exist in the workflow file so they're automatically synced, updated, and maintained
- Consistent color scheme helps users quickly identify the release series (v0.x vs v1.x)

**Technical notes:**
- The workflow uses GitHub's `issues.createLabel` and `issues.updateLabel` REST APIs
- Labels are synced on push to `.squad/team.md` or via manual `workflow_dispatch`
- Adding labels to the array ensures they won't be deleted by automation and their metadata (color, description) stays consistent

**Validation:**
- ✅ YAML syntax validated with `python3 -c "import yaml; yaml.safe_load(...)"`
- ✅ Branch created following squad convention: `squad/305-add-milestone-labels`
- ✅ PR #315 created targeting `dev` branch

**Lessons learned:**
1. **Label automation is declarative:** The workflow treats the `RELEASE_LABELS` array as the source of truth and syncs the repo to match
2. **Color coding conventions:** Use consistent color themes within label families (all v1.x labels share `0075ca`, v0.x labels use purples/blues)
3. **Manual labels need workflow updates:** When labels are created manually, they must be added to the workflow file to prevent drift
### 2026-03-16 — Issue #296: CKV_GHA_7 Exception for release-docs.yml

**Summary:** Fixed Checkov alert #103 (CKV_GHA_7) by adding documented exception to `.checkov.yml` for release-docs.yml workflow.

**Problem:** CKV_GHA_7 policy requires empty `workflow_dispatch` inputs per SLSA guidelines (build outputs must not be affected by user parameters). The release-docs.yml workflow triggered alert #103 because it defines `version` and `milestone` inputs.

**Solution:** Added CKV_GHA_7 to skip-check list in `.checkov.yml` with comprehensive justification:
- The release-docs.yml workflow is an internal documentation automation tool (not a build/release pipeline)
- Requires version and milestone parameters to function (generates release notes and test reports)
- Version input is validated with regex in workflow steps (lines 46-50)
- Protected by maintainer-only access and branch protection requirements
- Does not affect build artifacts or supply chain integrity

**Learnings:**
- CKV_GHA_7 enforces SLSA supply chain security by requiring empty workflow_dispatch inputs
- The policy aims to prevent arbitrary user parameters from affecting build behavior
- Documented exceptions are appropriate when:
  1. Workflow is not part of build/release pipeline for artifacts
  2. Inputs are validated and protected by access controls
  3. Risk is assessed and accepted with clear justification
- `.checkov.yml` skip-check pattern requires detailed comments explaining rationale
- Follows existing exception pattern (CKV_DOCKER_2, CKV_DOCKER_3)

**Deliverables:**
- PR #316: squad/296-fix-ckv-gha7-release-docs → dev
- Added 10 lines to `.checkov.yml` documenting CKV_GHA_7 exception
- YAML validation passed for both `.checkov.yml` and `release-docs.yml`
- Resolves alert #103, closes issue #296

**Branch:** squad/296-fix-ckv-gha7-release-docs → dev
**Status:** PR #316 open (https://github.com/jmservera/aithena/pull/316)

### 2026-03-17 — Cascading Docker Compose failure diagnosis

**Symptoms:** RabbitMQ auth failure, ZK broken pipe errors, missing books collection, 502s from nginx.

**Root causes identified:**
1. **RabbitMQ stale volume** — `/source/volumes/rabbitmq-data` contained Mnesia DB from prior run with different credentials. `RABBITMQ_DEFAULT_USER/PASS` only works on first init. Fix: clear the volume data.
2. **ZK health check noise** — `mntr` 4LW command output piped to `grep -Eq` caused SIGPIPE when grep exits after matching. Server-side "broken pipe" log messages are cosmetic; health check still passes. Simplified to `ruok`-only check.
3. **Books collection timing** — `solr-init` one-shot container creates the collection after full ZK+Solr startup chain. document-indexer had no compose-level `solr` dependency, so it started polling before Solr was running.

**Code changes:**
- Simplified zoo1/zoo2/zoo3 health checks from `ruok + mntr leader/follower grep` → `ruok` only
- Added `solr: condition: service_healthy` to document-indexer's `depends_on`
- Decision doc written to `.squad/decisions/inbox/brett-infra-diagnosis.md`

**Key learnings:**
- RabbitMQ `RABBITMQ_DEFAULT_USER/PASS` env vars are **first-init only** — changing them requires clearing the volume
- ZK `ruok` is sufficient for compose health gating; Solr's ZK client handles quorum detection
- The `solr-init` container (`restart: "no"`) creates the books collection with configset upload + collection CREATE + add-conf-overlay.sh
- document-indexer's `wait_for_solr_collection()` polls 60×5s (300s) and also verifies `/update/extract` handler exists
- document-indexer's RabbitMQ retry is **infinite** (no `tries` param on `@retry` decorator) — will never give up on auth failure

### 2026-03-17 — Infrastructure diagnosis coordinated with Parker

**Status:** Orchestrated background agent diagnosis of cascading Docker Compose failures + Redis auth wiring.

**Outcomes:**
- ZooKeeper health checks simplified (ruok-only) — removed SIGPIPE noise
- document-indexer now depends on Solr (condition: service_healthy) — prevents premature polling
- RabbitMQ stale volume issue identified and documented (operational fix)

**Files Modified:** docker-compose.yml

**Decisions:** 2 merged to decisions.md
- `.squad/decisions.md#Infrastructure-Cascading-Failures`
- `.squad/decisions.md#solr-search-Redis-ConnectionPool-Authentication`

**Orchestration Log:** `.squad/orchestration-log/2026-03-17T08-13-brett.md`

**Cross-Coordination:** Parker diagnosed Redis auth issue independently; both root causes merged into single decision set for holistic system view.
