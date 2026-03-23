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

### Release Security Requirement Enforcement (2026-03-22)
Security fixes are MANDATORY for every release. Updated release-checklist.md and .github/ISSUE_TEMPLATE/release.md with PO directive that a release CANNOT ship with known unresolved critical/high security issues. Releases now require:
- Bandit/Checkov/Zizmor/CodeQL scanning with no critical/high findings
- Dependabot alerts reviewed (critical/high fixed, medium/low documented)
- Threat assessment if significant new features added
- Performance benchmarks to verify no regressions
- GitHub Actions supply chain risk review (pinned actions, no script injection, token permissions)
- Input validation review on all new/modified API endpoints
PR #899 targeting dev; expected to land with next release milestone.

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

### Production Migration Planning (2026-03-26, #876)
- Created comprehensive **production migration plan** for e5-base embedding model deployment (`docs/prd/production-migration-plan.md`)
- Plan defines 7-step sequential process: Prepare Compose → Deploy Dual Indexing → Re-Index → Verify Parity → Benchmark → Switch Collection → Monitor 48h
- **Blue/green strategy:** Baseline (books) collection remains queryable during re-indexing; e5-base indexed in parallel via RabbitMQ fanout. Cutover is single config change to SOLR_COLLECTION env var.
- **Timeline:** 9–26 hours (Steps 1-6, mostly re-indexing time) + 48h monitoring = 2–4 days total
- **Rollback:** Instant (<5 min); change SOLR_COLLECTION back to "books" and restart solr-search
- **Key risk mitigation:** Collection parity verification script, benchmark baseline from Step 5, 48h monitoring window with clear alert thresholds
- **Approval gates:** PO (A/B results), Infra Lead (readiness), Search Lead (config review), QA Lead (rollback testing)
- PR #892 targeting dev; awaiting PO approval of A/B test results (issue #877) before implementation

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

## Session 2026-03-22T13:20Z — #878/PR#893: Rollback Plan for A/B Test (P3-3)

Created comprehensive rollback plan for the embedding model A/B test.

**Document:** `docs/prd/rollback-plan.md` (584 lines)

**Sections:**
1. **Rollback triggers:** 5 conditions (quality degradation nDCG@10 -5%, latency p95 >500ms, indexing failures >10 consecutive, resource exhaustion, PO decision)
2. **Dev/staging quick kill:** Stop e5 services, verify baseline continues, cleanup stale data (< 5 min, 0 downtime)
3. **Production rollback:** Revert config to baseline collection, restart solr-search, stop e5 services, verify serving (~15 min, ~2 min downtime)
4. **Data preservation:** Baseline 'books' never deleted; e5-base 'books_e5base' droppable; Redis cache keys collection-prefixed
5. **Verification:** 5-step checklist (collection status, benchmark suite, metrics endpoint, search quality, health check)
6. **Runbooks:** 2 copy-paste bash scripts (quick kill and production rollback) with error handling
7. **Decision tree:** Select procedure based on test phase (A/B test vs post-migration)
8. **Escalation:** 4-level path (on-call → team lead → PO → architect) with communication template
9. **Post-rollback RCA:** Root cause analysis, decision to retry/abandon/pivot

**Learnings:**
- **Two-mode rollback:** Quick kill for dev (stop services, baseline auto-serves) vs full for prod (config + restart cycle)
- **Collection naming convention:** Baseline='books', candidate='books_{model}' ensures no collision across multiple A/B tests
- **Redis cache isolation:** Per-collection cache keys prevent cross-contamination on rollback
- **Verification sequence:** Collection → benchmark → metrics → spot-checks → health covers all layers
- **RabbitMQ queue handling:** Queues naturally drain once indexers stop; optional manual purge depends on monitoring setup
- **Runbook automation:** Bash scripts include waiting loops and health checks rather than fixed delays

**Decision status:** Ready for PR review. Integrates with P2-4 (metrics) and P3-2 (prod deployment deferral).

**PR:** #893

### Air-Gapped Offline Installer (2026-07-25, #921/PR#925)
- Created 3-script offline deployment system: `scripts/export-images.sh` (build+export), `installer/install-offline.sh` (load+deploy), `installer/verify.sh` (health check)
- **11 unique Docker images** identified from compose files: 5 custom (GHCR) + 6 official (redis, rabbitmq, redis-commander, nginx, zookeeper, solr). Multiple compose services share the same base image (3× zookeeper, 4× solr including solr-init)
- **Package structure**: images/, compose/, config/ (solr, nginx, rabbitmq), install.sh, verify.sh, VERSION, README.md — all bundled into `staging/aithena-offline-v{VERSION}.tar.gz`
- **Install script**: validates Docker ≥24.0 + Compose v2, loads images via `gunzip | docker load`, generates `.env` with `openssl rand` secrets, creates bind-mount dirs with correct UIDs (Solr=8983, Redis=999, RabbitMQ=100, ZK=1000), preserves existing `.env` on updates
- **Verify script**: checks all 15 services + solr-init, probes HTTP health endpoints through nginx, uses internal connectivity checks via `docker exec`
- **Script conventions**: `set -euo pipefail`, `umask 077`, colors, `--dry-run`, `--help`, consistent with backup scripts pattern
- **Documentation**: `docs/deployment/offline-deployment.md` covers full lifecycle (build → transfer → install → verify → update → troubleshoot)

### 2026-03-22T13:49Z: Spawned for release checklist hardening

**Scope:** Update release process to make security & performance review mandatory

**Changes Required:**
- Add "Security Review Sign-Off" step (before version tag)
- Add "Performance Review Sign-Off" step (new requirement)
- Update PR template to reference threat assessment requirement
- Integrate Kane's threat assessment v1.12 into release gate

**User Directives:**
- Security fixes mandatory in releases (non-optional)
- Threat assessment required before each release
- Performance metrics baseline required before release

**Timeline:** Complete before next release cycle.

## Session 2026-03-22T14:41Z — Completed Spawn Work Summary

### Issues Closed This Batch

1. **#894 — Thumbnail libstdc++ fix** (PR #920)
   - Root cause: Alpine document-indexer Dockerfile missing libstdc++, libgomp, libgcc
   - Symptom: Silent crashes during PDF page number extraction
   - Fix: Added missing libraries to apk dependencies
   - Impact: 178 tests pass; thumbnail page extraction reliable

2. **#921 — Offline installer** (PR #925)
   - 3-script architecture: export-images.sh → install-offline.sh → verify.sh
   - Single .tar.gz package (11 Docker image tarballs + scripts + docs)
   - Install target: /opt/aithena/ with bind-mount volumes at /source/volumes/
   - Enables deployment on air-gapped/disconnected networks
   - Docs: offline-deployment.md (422 lines, comprehensive guide)

### Decisions Merged to .squad/decisions.md

1. **Offline Installer Architecture** — 3-stage pattern, convention alignment (VERSION, .env management), single package design
2. **Mandatory Security Review in Release Checklist** — Implements PO directives: security fixes mandatory; threat assessment for significant features; supply chain checks (GitHub Actions); release cannot ship with critical/high security issues
3. **A/B Testing Human Evaluation UI** — Awaiting PO review; environment-gated; SQLite storage; nDCG@10+MRR metrics; per-session blinding

### Orchestration Logs Created

- 2026-03-22T14:41:02Z-brett-thumbnail-libstdc.md (#894, PR #920)
- 2026-03-22T14:41:02Z-brett-offline-installer.md (#921, PR #925)
- 2026-03-22T14:41:02Z-ripley-offline-audit.md (offline audit confirmation)

---

## 2026-03-22 — Security Hardening Sprint Complete

**Sprint:** Infrastructure Security Hardening  
**Issues Closed:** #913 (ZK AdminServer), #912 (non-root containers), #917 (HSTS + headers)  
**PRs Merged:** #928, #930, #932  
**Status:** COMPLETE

### 1. ZooKeeper AdminServer Hardening (Issue #913, PR #928)
- **What:** Disabled AdminServer via `ZOO_CFG_EXTRA: "admin.enableServer=false"` on all 3 ZK nodes
- **Where:** docker-compose.yml + docker-compose.prod.yml
- **Rationale:** AdminServer exposes cluster topology; not needed for SolrCloud operations
- **Decision:** Recorded in `.squad/decisions.md`

### 2. Non-Root Container Standard (Issue #912, PR #930)
- **What:** Implemented container security hardening across custom Dockerfiles
- **Pattern (Alpine):** `addgroup -S -g 1000 app && adduser -S -u 1000 -G app app` + `USER app`
- **Pattern (Debian):** `groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --create-home app` + `USER app`
- **Services:** document-indexer, document-lister, aithena-ui; solr-search already using gosu
- **Rationale:** D-2 audit finding; reduces attack surface per container security best practices
- **Decision:** Standardized patterns recorded in `.squad/decisions.md` for future work

### 3. HSTS and Security Headers (Issue #917, PR #932)
- **What:** New `ssl.conf.template` with hardened TLS configuration
- **Headers:** Strict-Transport-Security (HSTS), X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- **Implementation:** HSTS only over HTTPS; all location blocks re-declare headers; `server_tokens off`
- **Requirement:** NGINX_HOST env var required when using SSL overlay
- **Rationale:** Prevents SSL stripping attacks; hardens response headers per infrastructure audit
- **Decision:** Recorded in `.squad/decisions.md`

### Key Standardizations Established
1. **Container UIDs:** Python services UID 1000 standard across Alpine + Debian
2. **nginx:** Built-in nginx user + non-privileged port (8080)
3. **TLS Configuration:** Dedicated HTTPS server block; HSTS enforcement; security header re-declaration in location blocks


## 2026-03-23 — E5 Migration Stack Build & SASL Auth Fixes

**Branch:** squad/e5-migration
**Status:** Stack builds and runs successfully after 3 critical SASL/JAAS fixes

### Build Results
- **All 5 custom images built successfully** (~16 min total, embeddings-server dominant at ~1.1GB model download)
- **Images:** aithena-ui (75MB), document-lister (162MB), solr-search (267MB), document-indexer (500MB), embeddings-server (27.4GB)
- **All 16 services start and become healthy** including ZK 3-node cluster, SolrCloud 3-node, books collection created

### SASL/JAAS Infrastructure Issues Found & Fixed

1. **ZooKeeper JAAS file permissions** — `entrypoint-sasl.sh` wrote `/conf/jaas.conf` as root with `chmod 600`, but ZK docker-entrypoint.sh re-execs as `zookeeper` user (UID 1000) via gosu, making the file unreadable. **Fix:** Added `chown zookeeper:zookeeper` before chmod.

2. **Solr JAAS file path** — `entrypoint-sasl.sh` wrote to `/opt/solr/server/etc/solr-jaas.conf` which is a root-owned directory. Solr 9.7 runs as `solr` user (UID 8983) and can't write there. **Fix:** Changed path to `/var/solr/solr-jaas.conf`.

3. **Solr 9.7 Java Security Manager blocks SASL** — Solr 9.7's security manager denies `accessClassInPackage.sun.security.provider`, preventing JAAS DigestLoginModule from loading. **Fix:** Set `SOLR_SECURITY_MANAGER_ENABLED=false` on all 4 Solr services.

4. **Solr 9.7 ZK client missing DigestLoginModule** — The ZK client jar bundled with Solr 9.7 does NOT include `org.apache.zookeeper.server.auth.DigestLoginModule`. SASL DIGEST-MD5 auth from Solr to ZK is fundamentally broken. **Fix:** Removed `requireClientAuthScheme=sasl` from ZK config; kept quorum SASL (inter-node) and digest ACLs (Solr → ZK znodes).

### Architecture Decision: ZK Client Auth Model
- **ZK quorum:** SASL DIGEST-MD5 (inter-node auth) ✅ works
- **Solr → ZK:** Digest ACL credentials via `DigestZkCredentialsProvider` ✅ works
- **Solr → ZK SASL:** ❌ NOT possible with Solr 9.7's bundled ZK client
- **Decision:** Dropped `requireClientAuthScheme=sasl` from ZK; security relies on Docker network isolation + ZK digest ACLs

### Learnings
- ZK's `requireClientAuthScheme=sasl` is incompatible with Solr 9.7's embedded ZK client
- The `SOLR_ZK_CREDS_AND_ACLS` env var is only used by `solr zk` CLI commands (line 730 of /opt/solr/bin/solr), NOT by the main Solr JVM startup; ZK creds must go in `SOLR_OPTS`
- Solr 9.7 security manager defaults to enabled; SASL/JAAS needs it disabled or custom policy grants
- ZK docker image (zookeeper:3.9) runs initial entrypoint as root then switches to `zookeeper` (UID 1000) via gosu; JAAS file must be owned by zookeeper
- Solr docker image (solr:9.7) runs entirely as `solr` (UID 8983); writable paths: `/var/solr/`
