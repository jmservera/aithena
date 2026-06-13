# Brett — History

## Core Context

Brett owns Docker Compose, Solr/SolrCloud, ZooKeeper, Redis, RabbitMQ, nginx, release plumbing, backup/restore, and infra validation.

- Standard runtime is Solr/SolrCloud + ZooKeeper + app services behind nginx; only nginx should publish host ports.
- Use overlays when a feature changes mounts, ports, or topology; use profiles only to disable services.
- Bind mounts keep host ownership, so setup scripts must fix service UIDs (Solr 8983, Redis 999, RabbitMQ 100, nginx 101, app 1000). Named volumes reduce ownership drift.
- ZooKeeper quorum is 2/3; back up ZK state and Solr data separately. `solr-init` creates collections and dependent services should wait with backoff.
- `VERSION` is the release source of truth; docs merge before tags; auth/ports/security regressions belong in required CI, not ad-hoc evidence.

## Active Patterns

- Prefer shared root entrypoints (`make`, shared shell libs) over duplicated workflow logic.
- Validate package/model integrity inside built images, not only on the CI host.
- Air-gapped/offline exports should be derived from `docker compose config --images` and shipped with a retag manifest.
- Keep OpenVINO cache in persistent app-owned directories, not `/tmp`.

## Recent Learnings

### 2026-06-13T19:02:09+00:00 — Shared Python Docker base
- `Dockerfile.base` can unify standard Python services (`document-lister`, `document-indexer`, `solr-search`) around Python 3.12 slim, `uv`, shared Debian tooling, and a reusable healthcheck script.
- `embeddings-server` should stay on its specialized base because its OpenVINO/model layers and release gates differ materially.

### 2026-06-13T18:06:26+00:00 — Offline package dedupe pattern
- Offline installer bundles should export images from `docker compose config --images`, include a tarball→source-tag→compose-tag manifest, and collapse the four Solr aliases into one exported image that the installer retags on the target host.

### 2026-06-13T15:44:59+00:00 — CI make-target orchestration
- Keep GitHub Actions pointed at root `make` targets while allowing runner-specific overrides such as `PYTEST_ARGS`, `E2E_PYTEST_ARGS`, and `PYTEST_CMD` so CI preserves junit/coverage artifacts without duplicating orchestration logic.

### 2026-06-13T15:37:35+00:00 — Shared build-service discovery
- Keep Dockerfile-based service discovery in `scripts/lib/build-services.sh` and have both `buildall.sh` and `manage.sh build` source it.
- Limit Python prep to discovered directories that also contain `pyproject.toml` so new `src/<service>/Dockerfile` services are auto-detected without treating infra-only images as Python projects.
