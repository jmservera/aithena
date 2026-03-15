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
