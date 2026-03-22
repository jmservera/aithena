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

---

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

## Learnings

### CI Workflow Patterns for BCDR Validation (2026-07-25)
- Restore scripts support `DRY_RUN=1` and `--dry-run` flags — CI can validate orchestrator logic without Docker or real backup data by creating a mock backup directory structure with placeholder files.
- `restore.sh` exit code 2 = warnings (e.g., missing files in a tier) — acceptable in CI mock environments. Only exit code 1 is fatal.
- Stress tests use pytest markers (`indexing`, `search`, `concurrent`, `docker`) and a `stack_healthy` fixture that gracefully skips when services are unreachable — `--collect-only` validates infrastructure without a live stack.
- `test_locust_smoke.py` is always safe to run in CI (no stack needed) — useful as a baseline sanity check in the stress workflow.

### nginx Static File Serving from Docker Volumes (2026-03-22)
- nginx can serve static files directly from named Docker volumes — mount as read-only and use `alias` with regex capture groups to map URL paths to filesystem paths.
- `auth_request` works inside regex location blocks — can gate static file access with the same subrequest auth used for proxy locations.
- Both `docker-compose.yml` and `docker-compose.prod.yml` need volume mounts updated in parallel — prod compose is a separate file, not an overlay of the dev one.
- The `document-data` volume was previously only mounted in application services (solr-search, document-lister, document-indexer, admin); adding it to nginx enables direct static serving without proxy overhead.

### Release Strategy Asymmetry Analysis (2026-03-26, #860)
- **Change frequency is highly asymmetric** across services: in v1.8.0→v1.11.0 (4 releases), 78% of commits touched only 2 services (aithena-ui: 30, solr-search: 38), while 3 services had 0-2 commits total.
- **embeddings-server is a rebuild bottleneck:** 9GB image with ML model, 8-12 min build time, but only 1 commit in 4 releases — rebuilt 3 times unnecessarily.
- **Current unified versioning** (all services share version) is simple but wastes ~40-60% of build time on unchanged services.
- **Change-detection CI** (Strategy C) is the lowest-risk improvement: detect changed services via `git diff`, skip builds for unchanged ones, retag previous images — reduces build time by 40% with 1 week migration effort.
- **Independent service versioning** (Strategy A) is the long-term architecture for scaling beyond 10+ services, but requires API contract testing and version compatibility management — migration effort 2-3 weeks, high complexity.
- **Tiered releases** (Strategy B) are a middle ground: classify services as Fast/Stable/Infrastructure tracks with different release cadences — reduces complexity vs full independent versioning but still requires track management.
- **Short-term recommendation:** Change-detection CI + embeddings-server base image (pre-bake ML model) for immediate 40% build time savings with minimal risk.

## Session 2026-03-22T10:50Z — PR #862 Merged (Release Strategy Analysis)

Release strategy analysis for issue #860 completed and merged to dev. Findings:
- Current approach rebuilds all 6 services despite asymmetric change frequency
- embeddings-server (9GB, 1 commit/4 releases) rebuilt unnecessarily 3 times
- document-lister (0 commits/4 releases) always rebuilt
- Current waste: 40-60% of build time on unchanged services

**Phased recommendation:**
1. **v1.12.0 (short-term):** Change-detection CI — skip unchanged services, retag images (40% savings, 1 week effort, low risk)
2. **v1.13.0 (mid-term):** Hybrid versioning for stable services (60% savings, 2-3 weeks, medium risk)
3. **v2.0.0+ (long-term):** Full independent versioning (60-80% savings, 4-6 weeks, high complexity)

**Decision status:** Awaiting PO decision on phase prioritization. Ready to implement short-term change-detection CI immediately if approved.

**Next:** Phase 1 implementation when approved — `git diff`-based change detection, image retagging logic, `--skip-unchanged` flag for buildall.sh.

## Session 2026-03-26 — #870/PR: Docker Compose A/B Setup (P1-4)

Implemented Docker Compose configuration for dual-indexer A/B testing (distiluse vs e5-base).

**Changes:**
- **docker-compose.yml:** Added `embeddings-server-e5` (3GB limit, e5-base model baked via build arg) and `document-indexer-e5` (512MB, reads from `shortembeddings_e5base` queue, writes to `books_e5base` collection). Both indexers now depend on `solr-init` (service_completed_successfully) to avoid racing collection creation.
- **docker-compose.override.yml:** Dev port 8086 for embeddings-server-e5 API debugging.
- **embeddings-server Dockerfile:** Made `MODEL_NAME` a build ARG (was hardcoded ENV). Enables building separate images with different models pre-baked while keeping `HF_HUB_OFFLINE=1` for air-gapped production.
- **rabbitmq.conf:** Documented expected fanout exchange topology (exchange=documents → queues shortembeddings + shortembeddings_e5base). Definitions are declared dynamically by application code, not static JSON.
- **docker-compose.prod.yml:** Intentionally NOT modified — A/B test is dev/staging only per P3-2 deferral.

**Memory budget:** embeddings-server-e5 ~3GB + document-indexer-e5 ~0.5GB = ~3.5GB total addition.

### Learnings

- **Dockerfile MODEL_NAME as build arg:** The embeddings-server uses `HF_HUB_OFFLINE=1` so models MUST be pre-baked at build time. Making `MODEL_NAME` an ARG (not just ENV) is required for multi-model builds from the same Dockerfile. The runtime ENV inherits the ARG value for the health endpoint's model name reporting.
- **solr-init dependency:** `service_completed_successfully` is the correct condition for one-shot init containers. Using `service_healthy` would fail since solr-init has no healthcheck and exits after completion.
- **Fanout exchange pattern:** No RabbitMQ static definitions needed — each indexer declares its own queue and binding on startup. This is more resilient than static definitions because queues are created by the consumers that need them.
