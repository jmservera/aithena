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
