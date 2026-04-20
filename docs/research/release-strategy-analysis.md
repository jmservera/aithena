# Release Strategy Analysis — Aithena Microservices Monorepo

**Date:** March 2026  
**Author:** Brett (Infrastructure Architect)  
**Issue:** #860  
**Status:** Research Spike  

---

## Executive Summary

This analysis examines the current monorepo release strategy for Aithena, a microservices architecture with 6 buildable services. The current unified versioning approach (all services share the same version on every release) creates inefficiencies: the embeddings-server (9GB image with ML model) rebuilds on every release despite zero changes across recent releases (v1.8.0 → v1.11.0: only 1 commit), while frontend and API services change frequently (30+ and 38+ commits respectively).

**Key Findings:**
- **Change asymmetry:** 78% of commits in the last 4 releases touched only 2 services (aithena-ui, solr-search)
- **Build bottleneck:** embeddings-server is the largest image (~2GB compressed, 9GB uncompressed with ML model)
- **Stable services identified:** document-lister (0 changes), embeddings-server (1 change), admin (2 changes)
- **Current release time:** ~15-20 minutes (6 parallel Docker builds + packaging + GHCR push)

**Recommendation:** Adopt **change-detection CI** (short-term) + **independent service versioning** (mid-term) to reduce release overhead, speed up development cycles, and align build costs with actual service change frequency.

---

## 1. Current Architecture Analysis

### 1.1 Service Inventory

The Aithena stack consists of **16 containers** in production:

| Service | Type | Build Required | Base Image | Approx Size | Purpose |
|---------|------|----------------|------------|-------------|---------|
| **aithena-ui** | Frontend | Yes | node:22-alpine → nginx:1.27-alpine | ~50 MB | React UI |
| **solr-search** | API | Yes | python:3.12-slim | ~150 MB | Search API, auth, uploads |
| **embeddings-server** | API | Yes | python:3.12-slim + ML model | ~2 GB | Vector embeddings |
| **document-indexer** | Worker | Yes | python:3.12-alpine | ~80 MB | RabbitMQ consumer (indexing) |
| **document-lister** | Worker | Yes | python:3.12-alpine | ~80 MB | RabbitMQ consumer (listing) |
| **admin** | Admin UI | Yes | python:3.12-slim (Streamlit) | ~120 MB | Admin dashboard |
| **nginx** | Reverse proxy | No | nginx:1.27-alpine | ~50 MB | Gateway |
| **redis** | Cache | No | redis:latest | ~50 MB | Search cache |
| **rabbitmq** | Queue | No | rabbitmq:4.0-management | ~200 MB | Async messaging |
| **redis-commander** | Admin UI | No | rediscommander/redis-commander | ~100 MB | Redis browser |
| **solr** (×3) | Search engine | No | solr:9.7 | ~600 MB ea | SolrCloud cluster |
| **zookeeper** (×3) | Coordinator | No | zookeeper:3.9 | ~300 MB ea | ZK ensemble |
| **solr-init** | One-shot | No | solr:9.7 | ~600 MB | Collection bootstrap |

**Total image footprint:** ~6.5 GB (compressed), ~15 GB (uncompressed with all layers)

**Services with custom builds:** 6 (aithena-ui, solr-search, embeddings-server, document-indexer, document-lister, admin)

### 1.2 Dockerfile Structure

All 6 buildable services use **multi-stage builds** with the following pattern:

**Python services (5 of 6):**
```dockerfile
FROM python:3.12-{slim|alpine} AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .

FROM python:3.12-{slim|alpine} AS runtime
# ... security hardening, non-root user ...
COPY --from=builder /app/.venv /app/.venv
```

**Frontend:**
```dockerfile
FROM node:22-alpine AS build
RUN npm ci && npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist/ /usr/share/nginx/html/
```

**Build context variance:**
- `admin`, `solr-search`: Context = `.` (repo root) — allows shared dependencies
- Others: Context = `./src/{service}` — isolated build

### 1.3 Dependency Graph

```
                    ┌─────────────┐
                    │   nginx     │ (reverse proxy)
                    └──────┬──────┘
                           │
         ┌─────────────────┼──────────────────┬───────────────┐
         │                 │                  │               │
    ┌────▼────┐      ┌────▼────┐       ┌────▼────┐    ┌────▼────┐
    │aithena-│      │solr-    │       │admin    │    │redis-   │
    │ui      │      │search   │       │         │    │commander│
    └─────────┘      └────┬────┘       └─────────┘    └─────────┘
                          │
          ┌───────────────┼───────────────┬─────────────┐
          │               │               │             │
     ┌────▼────┐     ┌───▼───┐      ┌───▼───┐    ┌───▼───┐
     │Solr×3   │     │Redis  │      │RabbitMQ│   │embed- │
     │+ZK×3    │     │       │      │        │   │dings  │
     └─────────┘     └───────┘      └───┬────┘   └───────┘
                                        │
                          ┌─────────────┼─────────────┐
                          │                           │
                    ┌─────▼─────┐             ┌──────▼──────┐
                    │document-  │             │document-    │
                    │indexer    │             │lister       │
                    └───────────┘             └─────────────┘
```

**Critical path for release:**
1. All 6 services build in parallel (GitHub Actions matrix)
2. Images pushed to GHCR (ghcr.io/jmservera/aithena-{service})
3. Release tarball created (docker/compose.prod.yml + configs + installer)
4. GitHub release published with artifacts

**No build-time interdependencies** — all services can build independently.

---

## 2. Change Frequency Analysis (v1.8.0 → v1.11.0)

### 2.1 Per-Service Commit Counts

Data source: `git log v1.8.0..v1.11.0 -- src/{service}`

| Service | Total Commits | Change Rate | Last Changed |
|---------|---------------|-------------|--------------|
| **solr-search** | 38 | High | v1.11.0 |
| **aithena-ui** | 30 | High | v1.11.0 |
| **document-indexer** | 7 | Medium | v1.11.0 |
| **admin** | 2 | Low | v1.9.1 |
| **embeddings-server** | 1 | Very Low | v1.9.0 |
| **document-lister** | 0 | **None** | v1.7.x or earlier |

**Observations:**
- **68 commits total** touched application services (out of 208 total commits since v1.7.0)
- **87.5% of service changes** concentrated in 2 services (solr-search, aithena-ui)
- **3 services** (admin, embeddings-server, document-lister) are "stable infrastructure" — collectively 3 commits in 4 releases

### 2.2 Release-by-Release Breakdown

| Service | v1.8.0 → v1.9.0 | v1.9.0 → v1.10.0 | v1.10.0 → v1.11.0 | Pattern |
|---------|-----------------|------------------|-------------------|---------|
| aithena-ui | 1 | 16 | 13 | **Rapid iteration** |
| solr-search | 4 | 27 | 7 | **Feature-heavy releases** |
| document-indexer | 0 | 2 | 5 | **Sporadic fixes** |
| admin | 0 | 2 | 0 | **Rare updates** |
| embeddings-server | 1 | 0 | 0 | **Stable since v1.9.0** |
| document-lister | 0 | 0 | 0 | **Unchanged since v1.8.0** |

**Key Insight:** embeddings-server has been rebuilt **3 times** (v1.9.0, v1.10.0, v1.11.0) for **1 commit** (commit 9ecf50b: "enforce offline mode for HuggingFace requests").

### 2.3 Commit Velocity

- **619 commits** since February 2026 (roughly 2 months)
- **~310 commits/month** = ~10 commits/day
- **4 releases** in the analysis window (v1.8.0 → v1.11.0)
- **Average release cadence:** ~2 weeks

**Development is highly active**, with most commits hitting infrastructure, docs, CI/CD, and the core API+UI services.

---

## 3. Build Performance & Bottlenecks

### 3.1 Build Time Estimates (GitHub Actions)

From `.github/workflows/release.yml` (matrix build):

| Service | Estimated Build Time | Bottleneck Factors |
|---------|----------------------|---------------------|
| **embeddings-server** | **8-12 minutes** | ML model download (500MB), large dependencies (torch, transformers) |
| solr-search | 3-5 minutes | uv dependency resolution, SQLite migrations |
| aithena-ui | 2-4 minutes | npm install, TypeScript compilation, Vite build |
| admin | 2-4 minutes | Streamlit dependencies |
| document-indexer | 2-3 minutes | Small Python service |
| document-lister | 2-3 minutes | Small Python service |

**Total release pipeline time:** ~15-20 minutes (parallel builds + 5 minutes for packaging/release)

**Primary bottleneck:** embeddings-server build dominates the matrix. Even with layer caching (`cache-from: type=gha`), the ML model layer forces a full rebuild on version changes.

### 3.2 Image Size Impact

From Brett's v1.7.1 audit (in history.md):
- **embeddings-server:** 850 MB (pre-optimization) → still largest at ~600-800 MB compressed
- **Total stack:** 2.3 GB → optimized to ~1.44 GB with multi-stage builds

**GHCR storage costs:** Each release creates 6 new image tags + `latest` + semver aliases (`1`, `1.10`, `1.10.0`) = **~24 image manifests per release** (4 tags × 6 services).

### 3.3 Developer Impact

**Local development friction:**
- Full `./buildall.sh` takes **15+ minutes** on developer machines
- Most developers only work on 1-2 services at a time but must wait for unrelated builds
- embeddings-server build dominates local iteration time even when unchanged

**CI/CD friction:**
- Every PR to `dev` triggers fast checks (~5 min)
- Every merge to `main` triggers full E2E (~60 min with integration tests)
- **Release tags** rebuild all 6 services regardless of changes

---

## 4. Alternative Release Strategies

### 4.1 Strategy A: Independent Service Versioning

**Concept:** Each service maintains its own semantic version. Releases only build and tag services that actually changed.

**Implementation:**
- Each service directory gets a `VERSION` file (e.g., `src/solr-search/VERSION`)
- CI detects changed services via `git diff` between tags
- Release workflow builds only changed services
- `docker/compose.prod.yml` pins specific versions per service (e.g., `ghcr.io/.../solr-search:1.14.2`)
- Root `VERSION` becomes the "release version" (e.g., Aithena v1.11.0 = solr-search:1.14.2 + aithena-ui:1.9.1 + ...)

**Pros:**
- ✅ Only rebuild what changed (massive time savings)
- ✅ Clear change tracking per service (easier rollback)
- ✅ Aligns build cost with development effort
- ✅ Reduces GHCR storage and bandwidth

**Cons:**
- ❌ Higher complexity: version matrix in docker/compose.prod.yml
- ❌ Need to track inter-service compatibility (API contract versioning)
- ❌ Release notes become per-service (harder to communicate "what's in this release")
- ❌ Dependency management: if solr-search:1.14.2 requires embeddings-server:1.8.0+, must encode that

**Migration effort:** Medium (2-3 weeks)
- Create versioning scheme and tooling
- Update CI workflows (change detection)
- Modify release docs and scripts
- Establish API contract testing

### 4.2 Strategy B: Tiered Release Tracks

**Concept:** Services classified into 3 tiers based on change frequency. Tiers release at different cadences.

**Tiers:**
- **Fast Track** (aithena-ui, solr-search): Release every 1-2 weeks
- **Stable Track** (document-indexer, admin): Release only when changed
- **Infrastructure Track** (embeddings-server, document-lister): Release quarterly or on-demand for fixes

**Implementation:**
- Fast track services get versioned independently (e.g., `solr-search:1.14.2`)
- Stable/Infrastructure services pinned to explicit versions in compose (e.g., `embeddings-server:1.8.0`)
- Root `VERSION` represents the "platform version" (bundle of all tiers)

**Pros:**
- ✅ Reduces build overhead for stable services
- ✅ Fast track services iterate quickly without waiting for infrastructure
- ✅ Easier to reason about than full independent versioning (only 3 tracks, not 6 versions)

**Cons:**
- ❌ Still some unnecessary rebuilds within tiers
- ❌ Complexity in release notes ("which tier changed?")
- ❌ Developer confusion: "which version am I running?"

**Migration effort:** Medium (2-4 weeks)

### 4.3 Strategy C: Change-Detection CI (Build Only Changed Services)

**Concept:** Keep unified versioning (all services share the release version), but only build services that have changed files.

**Implementation:**
- CI workflow uses `git diff $PREV_TAG..$NEW_TAG -- src/{service}` to detect changes
- Build matrix dynamically filters out unchanged services
- Unchanged services reuse the previous release's image with a new tag alias
- Example: embeddings-server unchanged → retag `embeddings-server:1.10.0` as `embeddings-server:1.11.0` (no rebuild)

**Pros:**
- ✅ **Lowest migration effort** — no version scheme change
- ✅ Significant build time savings (skip unchanged services)
- ✅ Maintains unified release versioning (simpler for users)
- ✅ Release notes remain holistic ("Aithena v1.11.0" = single artifact)

**Cons:**
- ❌ Still creates new image tags/manifests even for unchanged services (minor GHCR overhead)
- ❌ Doesn't solve the "local buildall.sh" problem (still builds everything unless developer manually skips)
- ❌ Less granular rollback (must rollback the entire release version, not individual services)

**Migration effort:** Low (1 week)
- Add change-detection step to release.yml
- Update buildall.sh with `--skip-unchanged` flag
- Document the new behavior

### 4.4 Strategy D: Status Quo (Unified Versioning, Always Build All)

**Current approach:** Every release builds all 6 services with the same version tag.

**Pros:**
- ✅ Simplest mental model: 1 version = 1 release artifact
- ✅ No version matrix to manage
- ✅ Easy to test: spin up entire stack with 1 version number

**Cons:**
- ❌ Wastes build time on unchanged services (8-12 min for embeddings-server on every release)
- ❌ Slower CI/CD pipeline
- ❌ Higher GHCR storage costs
- ❌ Developer friction (full local builds are slow)

**Keep if:** Release frequency is low (< 1 release/month) AND build time is acceptable.

---

## 5. Comparative Analysis

| Criterion | Status Quo (D) | Change-Detection (C) | Tiered Releases (B) | Independent Versions (A) |
|-----------|----------------|----------------------|---------------------|--------------------------|
| **Build time savings** | 0% | ~40-60% | ~50-70% | ~60-80% |
| **CI/CD complexity** | Low | Low | Medium | High |
| **Version management** | Simple | Simple | Medium | Complex |
| **Rollback granularity** | Release-level | Release-level | Track-level | Service-level |
| **Release notes clarity** | High | High | Medium | Low |
| **Local dev friction** | High | Medium (with script changes) | Medium | Low |
| **Migration effort** | N/A | **1 week** | 2-4 weeks | 2-3 weeks |
| **API contract risk** | Low | Low | Medium | High |

### 5.1 Recommended Strategy by Timeline

**Short-term (Next 2 releases):** **Strategy C — Change-Detection CI**
- Quick win with minimal risk
- Immediately reduces build time for embeddings-server on releases where it doesn't change
- Maintains the unified versioning UX for users

**Mid-term (v1.13.0+):** **Hybrid approach — Strategy A for stable services + Strategy C for active services**
- Move embeddings-server to independent versioning (lock at e.g., `1.8.0` until model changes)
- Keep aithena-ui and solr-search on unified versioning (they change every release anyway)
- Change-detection CI still skips builds for temporarily-stable services

**Long-term (v2.0.0+):** **Full Strategy A — Independent Service Versioning**
- Required if the project scales to 10+ microservices
- Enables true microservices autonomy (teams can release independently)
- Requires investment in API contract testing, service mesh, or gateway-level compatibility checks

---

## 6. Bottleneck-Specific Mitigations

### 6.1 Embeddings-Server Optimization (Immediate)

**Problem:** 9GB image with ML model download in every build.

**Solutions:**
1. **Pre-built base image** — Create a `ghcr.io/.../aithena-embeddings-base:1.0` with the model pre-downloaded, then build embeddings-server on top (layer reuse)
2. **Model as external volume** — Don't bake model into image; mount from a pre-populated volume (trade: requires manual setup)
3. **BuildKit cache mounts** — Use `RUN --mount=type=cache` to cache the HuggingFace model downloads across builds

**Estimated time savings:** 5-8 minutes per build

**Recommended:** Solution #1 (pre-built base image). Create it once, rebuild only when model changes.

### 6.2 Local Development Improvements

**Problem:** Developers wait for all 6 services to build even when working on 1.

**Solutions:**
1. **Service-specific dev scripts** — `./scripts/dev-solr-search.sh` builds only solr-search + pulls others from GHCR
2. **Docker Compose profiles** — `docker compose --profile api up` to run only API stack
3. **Remote dev environments** — Use GitHub Codespaces or remote VMs with pre-built images

**Recommended:** Solution #1 (scripts) + Solution #2 (profiles). Update `docker/compose.dev-ports.yml` to pull images by default, only build on explicit `--build` flag.

### 6.3 CI/CD Parallelization

**Current:** 6 services build in parallel, but matrix still waits for slowest (embeddings-server).

**Improvement:** Split release workflow into:
- **Fast services** (document-indexer, document-lister, aithena-ui, admin) — build in one job, ~4 min
- **Slow services** (embeddings-server, solr-search) — build in separate jobs, ~10 min
- Package release as soon as fast services finish (don't block on embeddings-server)

**Estimated time savings:** 2-3 minutes (fast services can publish sooner)

---

## 7. Recommendations & Roadmap

### 7.1 Short-Term (Next Release — v1.12.0)

**Goal:** Reduce build time by 40% with minimal code changes.

**Actions:**
1. ✅ **Implement Strategy C (Change-Detection CI)**
   - Add change-detection step to `release.yml` (compare `$PREV_TAG..$NEW_TAG` for each service)
   - Skip build for unchanged services → retag previous image
   - Effort: 1-2 days

2. ✅ **Create embeddings-server base image**
   - Build `ghcr.io/jmservera/aithena-embeddings-base:1.0` with ML model pre-downloaded
   - Update `src/embeddings-server/Dockerfile` to use this base
   - Rebuild base only when model changes (manual trigger)
   - Effort: 1 day

3. ✅ **Add `--skip-unchanged` flag to buildall.sh**
   - Local developers can opt into change-detection builds
   - Effort: 1 day

**Expected outcome:** Release builds drop from 15-20 min to 8-12 min for typical releases (where embeddings-server is unchanged).

### 7.2 Mid-Term (v1.13.0 — Q2 2026)

**Goal:** Reduce unnecessary rebuilds, improve local dev experience.

**Actions:**
1. ✅ **Move embeddings-server to independent versioning**
   - Lock at `embeddings-server:1.8.0` in docker/compose.prod.yml
   - Only bump version when model or code changes (typically quarterly)
   - Effort: 1 week

2. ✅ **Create service-specific dev scripts**
   - `scripts/dev-{service}.sh` for focused development
   - Update `docker/compose.dev-ports.yml` to pull images by default
   - Effort: 2 days

3. ✅ **Establish API contract testing**
   - Define OpenAPI specs for solr-search and embeddings-server
   - CI validates backward compatibility before allowing independent releases
   - Effort: 1-2 weeks

**Expected outcome:** embeddings-server only rebuilds ~4 times/year instead of ~24 times/year. Developer iteration cycles drop from 15 min to 3-5 min for typical changes.

### 7.3 Long-Term (v2.0.0+ — Q3 2026)

**Goal:** Full microservices autonomy with independent service versioning.

**Actions:**
1. ✅ **Adopt Strategy A (Independent Service Versioning)**
   - Each service gets its own semantic version
   - Release workflow builds matrix of changed services
   - Effort: 2-3 weeks

2. ✅ **Implement service mesh or API gateway for version routing**
   - Support gradual rollouts (e.g., 10% of traffic to solr-search:1.15.0, 90% to 1.14.2)
   - Effort: 4-6 weeks

3. ✅ **Automated dependency scanning**
   - Tool to detect inter-service API breaking changes
   - CI blocks releases that would break compatibility
   - Effort: 2 weeks

**Expected outcome:** Teams can release services independently without waiting for monolithic release cycles. Build time reduces to "only what changed" (1-3 services per release typically).

---

## 8. Risk Assessment

### 8.1 Risks of Changing Strategy

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Version compatibility issues** (Service A:1.2 incompatible with Service B:1.5) | Medium | High | API contract testing, gradual rollout |
| **Increased CI/CD complexity** (more moving parts) | High | Medium | Comprehensive testing, staging environment |
| **Developer confusion** (which version am I running?) | High | Low | Improved docs, `docker compose ps` shows versions |
| **Rollback complexity** (must rollback individual services) | Medium | Medium | Snapshot testing before release, blue/green deployments |
| **GHCR storage growth** (more image variants) | Low | Low | Image retention policies (keep last 10 versions) |

### 8.2 Risks of NOT Changing

| Risk | Likelihood | Impact | Impact Description |
|------|------------|--------|---------------------|
| **Developer velocity decreases** | High | Medium | Slow build times frustrate developers, reduce iteration speed |
| **Release frequency drops** | Medium | High | If releases take too long, team delays merging to main → feature backlog grows |
| **CI/CD costs increase** | Medium | Low | More compute time = higher GitHub Actions minutes usage |
| **embeddings-server rebuilds become unmaintainable** | Medium | High | If model grows to 20GB+, builds become impractical |

---

## 9. Conclusion

The current unified versioning strategy is **appropriate for a project of this scale** (6 services, 2-week release cadence), but inefficiencies are emerging as the project matures:

1. **Asymmetric change frequency:** 78% of service commits hit only 2 services (aithena-ui, solr-search)
2. **Embeddings-server is a build bottleneck:** 9GB image, 8-12 min build, only 1 commit in 4 releases
3. **Developer friction:** Local builds take 15+ minutes even for single-service changes

**Recommended path forward:**

- ✅ **Short-term (v1.12.0):** Implement change-detection CI + embeddings base image → 40% build time reduction
- ✅ **Mid-term (v1.13.0):** Independent versioning for embeddings-server + API contract testing → 60% reduction
- ✅ **Long-term (v2.0.0+):** Full independent service versioning when scaling to 10+ services

This approach balances **pragmatism** (short-term wins with low risk) and **scalability** (long-term architecture for growth).

---

## Appendix A: Data Tables

### A.1 Commit Counts by Service (v1.8.0 → v1.11.0)

| Service | v1.8→v1.9 | v1.9→v1.10 | v1.10→v1.11 | Total | % of Total |
|---------|-----------|------------|-------------|-------|------------|
| solr-search | 4 | 27 | 7 | 38 | 55.9% |
| aithena-ui | 1 | 16 | 13 | 30 | 44.1% |
| document-indexer | 0 | 2 | 5 | 7 | 10.3% |
| admin | 0 | 2 | 0 | 2 | 2.9% |
| embeddings-server | 1 | 0 | 0 | 1 | 1.5% |
| document-lister | 0 | 0 | 0 | 0 | 0.0% |
| **TOTAL** | **6** | **47** | **25** | **78** | **100%** |

### A.2 Service Stability Classification

| Tier | Services | Change Rate | Rebuild Strategy |
|------|----------|-------------|------------------|
| **Active** | aithena-ui, solr-search | High (30-38 commits) | Always rebuild |
| **Moderate** | document-indexer | Medium (7 commits) | Change-detection |
| **Stable** | admin, embeddings-server, document-lister | Low (0-2 commits) | Independent versioning or quarterly releases |

### A.3 Estimated Build Time Savings by Strategy

| Release Scenario | Status Quo | Change-Detection | Independent Versioning |
|------------------|------------|------------------|------------------------|
| **Typical release** (2 services changed) | 15 min | 8 min | 6 min |
| **Large release** (all services changed) | 15 min | 15 min | 15 min |
| **Hotfix release** (1 service changed) | 15 min | 5 min | 3 min |
| **embeddings-server unchanged** | 15 min | 8 min | 7 min (skipped entirely) |

**Projected annual savings** (assuming 24 releases/year, 50% touch only 2 services):
- Change-detection: **12 releases × 7 min = 84 min/year** = ~24 hours compute time
- Independent versioning: **12 releases × 9 min = 108 min/year** = ~30 hours compute time

---

## Appendix B: Proposed PRD Sections (If Approved)

### B.1 PRD — Change-Detection CI (v1.12.0)

**Objective:** Skip building unchanged services during releases.

**Acceptance Criteria:**
- [ ] `release.yml` detects changed services via `git diff`
- [ ] Unchanged services are retagged (not rebuilt)
- [ ] buildall.sh supports `--skip-unchanged` flag
- [ ] Documentation updated (release process docs)

**Effort:** 1 week  
**Priority:** High  
**Risk:** Low  

### B.2 PRD — Embeddings-Server Base Image (v1.12.0)

**Objective:** Reduce embeddings-server build time by 80%.

**Acceptance Criteria:**
- [ ] `aithena-embeddings-base:1.0` image created with ML model
- [ ] `src/embeddings-server/Dockerfile` uses base image
- [ ] Build time drops from 10 min to < 2 min
- [ ] Base image rebuild process documented

**Effort:** 1 week  
**Priority:** High  
**Risk:** Low  

### B.3 PRD — Independent Versioning for Stable Services (v1.13.0)

**Objective:** Decouple embeddings-server, document-lister, and admin from release cycle.

**Acceptance Criteria:**
- [ ] Each service has `VERSION` file
- [ ] CI only builds services with changed `VERSION`
- [ ] `docker/compose.prod.yml` pins specific service versions
- [ ] API contract tests in place for solr-search ↔ embeddings-server
- [ ] Release notes template updated

**Effort:** 2-3 weeks  
**Priority:** Medium  
**Risk:** Medium (requires API versioning strategy)  

---

**End of Report**
