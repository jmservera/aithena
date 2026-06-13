# Brett — History

## Core Context

Brett owns Docker Compose, Solr/SolrCloud, ZooKeeper, Redis, RabbitMQ, nginx, CI/CD release plumbing, backup/restore, and infra validation.

### Compose Architecture
- Standard stack: 17 containers (3× SolrCloud, 3× ZooKeeper, Redis, RabbitMQ, nginx, Python services, frontend, admin UIs).
- Only nginx publishes host ports; services use `expose:`. Use `compose.ci-ports.yml` for CI host access, keep `compose.dev-ports.yml` local-only because it exposes ZooKeeper.
- Use `depends_on: condition: service_healthy`, explicit memory/CPU limits, json log rotation, role-based restart policies, and service-specific graceful shutdown.
- Use overlays when optional features change another service's mounts/ports (`ssl`, `gpu`, `e2e`, `ci-ports`). Profiles can disable services but cannot modify other services.

### Permissions and Stateful Data
- Bind-mount ownership is the host's; Dockerfile `RUN chown` does not affect mounts. Setup scripts must `chown` dirs to UIDs: Solr 8983, Redis 999, RabbitMQ 100, nginx 101, app 1000.
- Named volumes avoid many ownership issues because Docker initializes them from the image.
- RabbitMQ credentials apply only on first Mnesia DB creation; stale volumes retain old credentials. Clear bind-mount data on credential/major upgrades and enable feature flags before 3.x → 4.x.

### Solr, ZooKeeper, and Search Capacity
- ZK quorum is 2/3; losing 2 nodes causes write outage. Back up ZK state and Solr data independently. `solr-init` creates collections; consumers poll with exponential backoff.
- Solr 9.7 `solr auth enable` assigns built-in admin roles. Do not `set-user-role` afterward; use built-in `search` for read-only users.
- Page chunking + int8 quantization cuts 54M-vector HNSW memory from ~130GB to ~9GB, making 32GB standalone Solr viable on NVMe; revisit SolrCloud above ~15M vectors or if HA is mandatory.

### nginx and Build Contexts
- nginx routes `/admin/solr/`, `/rabbitmq/`, `/streamlit/`, `/redis/`, frontend, API; `/health` returns 200 `healthy`. nginx starts last to avoid 502s.
- Build contexts: `admin`/`solr-search` use repo root; `embeddings-server`, `document-lister`, `document-indexer`, `aithena-ui` use `src/{service}`.

### Release, CI/CD, and Security
- Docs merge before version tags. `VERSION` is source of truth; prod compose pulls GHCR images; `v*.*.*` tags build/push images and tarball.
- Workflow security: secrets via `with:`, `${{ }}` in `env` not `run`, SHA-pin actions, document Checkov skips, upload SARIF.
- CI split: fast dev checks, full E2E on main/release. `workflow_run` artifact access should use GitHub REST/API.
- Dependabot: patch/minor auto-merge; batch backlogs, exclude majors, resolve lockfiles, patch-bump VERSION only on real changes.

### BCDR and Validation
- Backup tiers: critical SQLite/secrets, high Solr/ZK, medium Redis/RabbitMQ. Auth DB migrations are forward-only with `schema_version`; SQLite `.backup` for snapshots.
- Collections DB uses `/data/collections/` and `COLLECTIONS_DB_PATH`.
- Pre-release validation scans compose logs; Redis overcommit is host/CI-runner `vm.overcommit_memory`, not Compose-only unless sysctls are adopted.
- Stress tests use Docker SDK `container.stats(stream=False)` and `oom`/`die` events with graceful fallback.

## Key Patterns

- **Health checks:** `CMD-SHELL` for expansion; `CMD` arrays do not expand vars. Node can use built-in `http`. Pad `start_period` 2–3x in CI, avoid grep SIGPIPE, and fail fast on missing auth env.
- **Overlay selection:** Use overlays for SSL/certbot, GPU, CI ports, prod; profiles only for disabling services/topologies.
- **GPU deployment:** NVIDIA uses `deploy.resources.reservations.devices`; Intel uses `/dev/dri`, `video` group, OpenVINO base. WSL2 needs Windows host drivers. Avoid `group_add: [render]` unless the group exists in-image.
- **Embeddings offline loading:** `snapshot_download()` misses metadata needed by `optimum-intel`. Save OpenVINO `SentenceTransformer` to `/models/...` during build, verify with offline env vars, and load local dirs at runtime.
- **Intel XPU:** `intel-extension-for-pytorch` is required for Intel GPU/XPU dispatch; include it only in OpenVINO extras so CPU/torch builds stay unaffected.
- **BuildKit optimization:** Use `RUN --mount=from=...` for transient tools; `COPY --from` creates layers and does not deduplicate. `uv sync --inexact --frozen --no-dev` installs only deltas. Use Dockerfile syntax v1.
- **OpenVINO cache:** Put persistent OV cache under `/app/ov_cache` owned by the app user, not `/tmp`.
- **Auth in E2E:** CI should mint one `E2E_API_TOKEN` and pass it to Playwright/pytest to avoid rate limiting from repeated login calls. Validate CI/test infrastructure locally with Docker + Playwright before pushing.
- **Labels and PR hygiene:** GitHub label hierarchy is not enforced; parent labels need event-driven plus periodic sync. Review threads must be resolved through GraphQL `resolveReviewThread`; comments alone do not satisfy branch protection.

## Research Loop Participation (2026-06-06)

- **#1452 Complexity Reduction Research Pass:** Led decomposition of 7 follow-up PRs from original complexity audit post-PR #1706. Identified risks (LOW/MEDIUM/HIGH), owner routing (Brett/Parker/Dallas/Newt), and validation strategies. Owns items: health-check extraction, CI Compose overlay, buildall error handling, Dockerfile base stage extraction.
- **#1356 Phase 2 Infrastructure Assessment:** Mapped infrastructure gaps (standalone Solr 10 overlay, Overseer-disabled overlay, init script branching). Provided compose overlay blueprints and blocking milestone (v2.5.1 pre-work).
- **#1343 SolrCloud Overseer Decision:** Recorded decision to disable Overseer in production Solr 10 (retains ZooKeeper HA, removes collection-management bottleneck).
- **#1662 OpenVINO Release Gates Decision:** Documented decision to verify inside built Docker image after `uv sync --inexact`; added release gate workflow + smoke tests.

## Learnings

- **2026-06-13T15:23:26+00:00 — manage.sh compose targeting:** A repo-root `manage.sh` should operate on the same compose file chain as the installer-generated `start.sh` by default, while still allowing `AITHENA_COMPOSE_FILES`/`COMPOSE_FILE` overrides for automation and isolated fixture tests. This keeps day-2 commands (`status`, `logs`, `reset`) aligned with the operator's chosen overlays instead of silently targeting only `docker-compose.yml`.
- **2026-06-13T14:54:18+00:00 — Canonical env template defaults:** For issue #1740, the checked-in `.env.example` should be runnable as a smoke-test template (`cp .env.example .env`) with repo-local bind-mount defaults, while installer-generated `.env` remains the secure path for real secrets. Keep every supported variable explicitly assigned in `.env.example`, including overlay/runtime knobs such as `DEVICE`, `BACKEND`, `SEARCH_ARCHITECTURE`, `SOLR_NUM_SHARDS`, and `NGINX_HOST`, so operators no longer have to merge Compose fallbacks by hand.
- **2026-06-13T15:44:59+00:00 — CI make-target orchestration:** Keep GitHub Actions test jobs pointed at root `make` targets, but let workflows override runner-specific args (`PYTEST_ARGS`, `E2E_PYTEST_ARGS`, `PYTEST_CMD`) so CI can preserve junit/coverage outputs while consolidating suite names and logging in one entrypoint.
- **2026-06-13T15:31:32+00:00 — Legacy scripts migration posture:** Treat `./manage.sh` as the canonical day-2 operator entrypoint and keep root-level `scripts/` only as deprecated bridges for specialized runbooks (BCDR, Solr migration, offline export) until the next major version removes them.

- **2026-06-13T14:54:18+00:00 — Canonical env template defaults:** For issue #1740, the checked-in `.env.example` should be runnable as a smoke-test template (`cp .env.example .env`) with repo-local bind-mount defaults, while installer-generated `.env` remains the secure path for real secrets. Keep every supported variable explicitly assigned in `.env.example`, including overlay/runtime knobs such as `DEVICE`, `BACKEND`, `SEARCH_ARCHITECTURE`, `SOLR_NUM_SHARDS`, and `NGINX_HOST`, so operators no longer have to merge Compose fallbacks by hand.
- **2026-06-06T22:00:15.185+00:00 — PR #1712 infra quality review:** Solr 10 `bits=7` scalar quantization is compatible with current Solr 9 fallback rewrites when every compatibility path rewrites `bits="[47]"` to `vectorEncoding="BYTE"` (compose, prod compose, `docker/solr-init.sh`, `scripts/solr-import.sh`). Validate with dummy required auth envs: `docker compose config --quiet`, `docker compose -f docker/compose.prod.yml config --quiet`, `bash -n docker/solr-init.sh scripts/solr-import.sh`, and targeted Solr/benchmark pytest. A one-off PR #1712 pre-release embeddings-server failure was BuildKit bootstrap pulling `moby/buildkit` from Docker Hub (`context deadline exceeded`) before repository build logic; later pre-release runs passed, so track as transient unless repeated.
- **2026-06-06T17:35:30.213+00:00 — buildall service discovery:** Keep `buildall.sh` behavior-preserving by discovering Python container service directories from `src/*/{pyproject.toml,Dockerfile}`. This includes only buildable Python services and intentionally excludes source-only packages such as `aithena-common`.
- **2026-06-06T09:36:46.687+00:00 — Pre-release warning cleanup:** Solr 10 `solr.log.dir` is an actionable Aithena config deprecation; use only `solr.logs.dir` in Compose and log4j2. Solr/JVM `sun.misc.Unsafe::arrayBaseOffset` and RabbitMQ `management_metrics_collection` are upstream/runtime notices in the current topology, so track them as narrow info allowlist entries. Solr `ZkCredentialsInjector` is the Solr 10 wording for the already accepted internal-only ZooKeeper ACL posture; allowlist it narrowly alongside Provider/ACLProvider while keeping unrelated auth/config warnings actionable.
- **2026-06-06T09:36:46.687+00:00 — Pre-release auth-pattern overmatch:** Issue #1686 showed that the log analyzer's broad `auth*fail` security glob matched `TestAuthor ... Thumbnail generation failed`. Keep security patterns phrase-based (`auth failed`, `authentication failed`, `authorization failed`) so benign filenames/authors do not become release-blocking security errors while real auth failures still fail.
- **2026-06-06T16:09:02.162+00:00 — SolrCloud Overseer disabled mode:** For Solr 10 production HA, keep the existing 3×SolrCloud + 3×ZooKeeper topology and pass `-Dsolr.cloud.overseer.enabled=false` on every Solr node. This enables distributed cluster-state updates without changing dev/single-node topology; validate with compose config plus a runtime create/delete collection smoke test, and run `RUN_FAILOVER=1 tests/solrcloud-overseer-disabled-validation.sh` only in a production-like maintenance window because it stops `solr2`.
- **2026-06-04 — Squad upgrade and zizmor configuration:** Squad v0.9.4 upgrade completes coordinator refresh, workflow/skill sync, and template refresh smoothly. Opened PR #1650 (brett-5). Generated `squad-*` workflows triggered zizmor code-scanning alerts; resolved by configuring zizmor-action to exclude generated workflow basenames via repository-owned input list (brett-6, c7be8d0). User directive: project does not control upstream Squad workflows, so generated security noise should be ignored.
- **2026-06-04 — Solr readiness auth:** Solr readiness probes must validate `SOLR_ADMIN_USER` and `SOLR_ADMIN_PASS` before constructing curl credentials; missing installer-exported `.env` values should produce explicit CI errors, not opaque 401 retry loops.
- **2026-06-04 — ZooKeeper exposure:** CI/production overlays must keep ZooKeeper ports unpublished while preserving Solr auth env wiring for init and health checks. Add compose config regression tests for both.
- **2026-06-03 — Pre-release analyzer:** Keep fixture labels unique and monotonic so CI output maps back to scripts. Known RabbitMQ startup deprecation notices can remain `info` when non-actionable.
- **2026-05-31 — Local-test-first:** Infrastructure and E2E workflow changes should be tested locally against Docker/Playwright before pushing because local tooling is available.
- **2026-05-31 — E2E token reuse:** Workflows minting auth tokens should export them for downstream Playwright and pytest consumers; see skill `e2e-auth-reuse`.
- **2026-04-21 — Dev integration workflow:** Single-node Solr/ZK topology cuts dev CI resource use while running the same E2E suite. Disable extra Solr/ZK services with profile overrides in the workflow.
- **2026-04-20 — Search capacity:** With page chunking and int8 quantization, 32GB standalone Solr on NVMe is the cost-optimal target; previous 130GB requirement assumed unoptimized vectors.
- **2026-04-19 — Dependabot backlog:** `gh pr list --json author` reports Dependabot as `app/dependabot`, not `dependabot[bot]`. Batch merge workflows are useful for large dependency backlogs.
- **2026-04-02 — Solr auth roles:** Solr 9.7 built-in roles should be preserved; overwriting the admin role after `solr auth enable` breaks security-edit and collection-admin-read permissions.
- **2026-03-31 — Embeddings Dockerfile:** BuildKit uv mount plus `uv sync --inexact` reduced embeddings-server app layer from multi-GB to tens of MB when the base is cached.
- **2026-03-29 — IPEX:** IPEX 2.8.0 resolves cleanly with torch 2.10.0 and sentence-transformers 5.3.0; no compose changes required when installed via OpenVINO extras.
- **2026-03-25 — GPU admin docs:** GPU troubleshooting should emphasize host driver installation, vendor-specific WSL2 passthrough, compose override usage, and health endpoint verification.
- **2026-03-22 — nginx thumbnails:** Static thumbnail serving needs both a volume mount and a dedicated `/thumbnails/` location.
- **2026-03-20 — Release optimization:** v1.8–v1.11 showed asymmetric changes; change-detection builds can skip unchanged service builds and retag images to save build time.
- **2026-03-19 — Auth DB permissions:** Docker Compose diagnostics traced auth DB failures to host bind-mount UID ownership; this remains the top recurring local setup issue.

### 2026-06-05 — OpenVINO Smoke Failure Root-Cause & Prevention (Issue #1662)
- **Context:** Pre-release run 27022717607 smoke test embeddings-server-openvino failed; fix at 27026253418 (a8a5cb5)
- **Root cause:** `uv sync --inexact` allowed transitive drift; `--frozen` alone did not guarantee built-image correctness
- **Prevention:** Post-sync version verification inside Dockerfile; Python import + version check fails build if mismatch detected
- **Rubber Duck critique:** Confirmed verification must run inside the built image, not just CI assumptions
- **Pattern:** Add Python version-check step after each `uv sync --inexact` in embeddings-server Dockerfiles to catch future drift immediately
- **Decision:** `.squad/decisions.md` (OpenVINO Smoke Failure section)

## 2026-06-06 — v2.5.1 Board Completion

Completed #1343 (Configure SolrCloud with Overseer disabled) via PR #1700, merged to dev. Issued pre-release validation analyzer hardening decisions:
- Narrow pre-release auth failure classification (explicit phrase matching vs. substring globs)
- Pre-release warning policy for Solr/RabbitMQ runtime noise (allowlist narrowing)

Related: #1686, #1695, #1696
### 2026-06-06 — Workflow Consolidation Follow-up (Issue #1449)
- Phase 1 consolidation is already merged on `dev`; keep later release/heartbeat workflow rewrites deferred instead of changing required release gates during v2.5.1 cleanup.
- `squad-ci.yml` is a manual-dispatch placeholder with no required-check or release behavior; removing it is safe dead-code cleanup and preserves CI/release semantics.
- **2026-06-07T10:39:19.545+00:00 — buildall failure reporting:** Keep `buildall.sh` bounded to preparation/build failure handling: capture each `uv sync` and Compose build step in `.test-artifacts/buildall-{step}-{timestamp}.log`, continue checking all Python prep steps, then skip Compose when prep failed and summarize failing steps with log paths.
