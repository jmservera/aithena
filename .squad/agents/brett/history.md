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

## Learnings

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
