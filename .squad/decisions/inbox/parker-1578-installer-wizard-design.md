### 2026-05-24: Wizard Installer — Design Proposal (Research Spike for #1578)
**By:** Parker (via Ralph v2.2.0 sweep)
**Status:** Proposal — awaiting Ripley + Juanma approval
**Scope:** Architecture only. No code in this PR.

## 1. Current State (verified)
- Bind mounts found in `docker-compose.yml`: **16** base bind-backed local volumes under `/source/volumes/`, grouped by consuming service:
  - `redis`: `redis-data` → `/source/volumes/redis`
  - `rabbitmq`: `rabbitmq-data` → `/source/volumes/rabbitmq-data`
  - `solr-search`: `collections-db` → `${COLLECTIONS_DB_DIR:-/source/volumes/collections-db}`
  - `zoo1`: `zoo-data1_logs` → `/source/volumes/zoo-data1/logs`; `zoo-data1_data` → `/source/volumes/zoo-data1/data`; `zoo-data1_datalog` → `/source/volumes/zoo-data1/datalog`; `zoo-backup` → `/source/volumes/zoo-backup`
  - `zoo2`: `zoo-data2_logs` → `/source/volumes/zoo-data2/logs`; `zoo-data2_data` → `/source/volumes/zoo-data2/data`; `zoo-data2_datalog` → `/source/volumes/zoo-data2/datalog`; `zoo-backup` → `/source/volumes/zoo-backup`
  - `zoo3`: `zoo-data3_logs` → `/source/volumes/zoo-data3/logs`; `zoo-data3_data` → `/source/volumes/zoo-data3/data`; `zoo-data3_datalog` → `/source/volumes/zoo-data3/datalog`; `zoo-backup` → `/source/volumes/zoo-backup`
  - `solr`: `solr-data` → `/source/volumes/solr-data`
  - `solr2`: `solr-data2` → `/source/volumes/solr-data2`
  - `solr3`: `solr-data3` → `/source/volumes/solr-data3`
- Additional non-base SSL bind-backed volumes: `docker/compose.ssl.yml` defines `certbot-data-conf` → `/source/volumes/certbot-data/conf` and `certbot-data-www` → `/source/volumes/certbot-data/www`; `installer/setup.py` also creates/checks these paths in the generated SSL `start.sh` block.
- Missing compose overlays referenced by generated `start.sh`: **none**. `installer/setup.py` references `docker-compose.yml`, `docker/compose.prod.yml`, `docker/compose.dev-ports.yml`, `docker/compose.gpu-nvidia.yml`, `docker/compose.gpu-intel.yml`, `docker/compose.ssl.yml`, and `docker/compose.single-node.yml`; all exist. The generated root `start.sh` itself is absent from the checkout until the installer runs.
- Current installer LOC + key entry points: `installer/setup.py` is **914 lines**. Key entry points are `main()` → `build_parser()` → `ensure_runtime_dependencies()` → `run_setup()` → `generate_start_script()` / `write_env_file()` / `bootstrap_admin_user()`.
- Installer directory layout: Python package files (`__init__.py`, `__main__.py`, `setup.py`), `pyproject.toml`, `uv.lock`, `tests/`, `install-offline.sh`, `setupdev.sh`, and `verify.sh`. There is **no installer Dockerfile** and no `requirements.txt` today.
- Hard Python dependencies: the installer requires Python `>=3.12` and direct dependency `aithena-common`; `aithena-common` depends on `argon2-cffi>=23.1`. `setup.py` shells out to `uv run --project installer python -m installer.setup ...` when `aithena-common` is not importable, so a host needs `uv` unless dependencies are already installed.
- Quick Start currently documents `python3 -m installer` followed by `./start.sh`, not a Docker-only bootstrap flow. `.env.example` already exists and documents installer-generated secrets, auth paths, GPU overlays, and Solr topology.

## 2. Proposed Architecture
Use a two-layer installer architecture:

1. **Tiny host bootstrap script**
   - Responsibilities: verify Docker + Compose v2, create a working directory, pull a versioned installer image, and run that image with the minimum required mounts.
   - Keep it as boring shell: no Python, no package manager, no project checkout required.
   - It should support `--dry-run`, `--version`, `--image`, `--install-dir`, and `--library-path` from day one so Juanma can validate the promised “clean WSL + Docker only” story without hidden dependencies.

2. **Versioned installer container image**
   - Package the current Python installer and its `aithena-common` / `argon2-cffi` dependency inside the image.
   - Run the existing wizard logic in-container first, then evolve the prompts; avoid rewriting the wizard before the packaging boundary is proven.
   - Mount only what the wizard needs: target install directory, optional book library path, and a Docker control mechanism if the container will create volumes or run Compose.
   - Generate `.env`, create/seed auth DB, render `start.sh`, and optionally run `docker compose config` before starting services.

Validated by repo investigation:
- Containerizing the installer is justified because the current host path requires Python 3.12 + `uv` + `aithena-common` + transitive `argon2-cffi` before the user can even generate `.env`.
- Phase 1 volume work is real: base compose has 16 `/source/volumes/` bind-backed volumes, plus SSL has 2 more certbot paths.
- The `start.sh` template is real and centralized in `generate_start_script()`.
- `.env.example` already exists, so Phase 1 should audit/fill gaps rather than create it from scratch.

Questionable or needs approval before implementation:
- Running a wizard container with `/var/run/docker.sock` mounted is operationally simple but security-sensitive; the repo already warns about Docker socket risk in `solr-search`.
- Switching bind-backed local volumes to Docker-managed named volumes changes backup, migration, and inspect/debug workflows for existing deployments.
- A “2 commands install” may conflict with required choices (library path, domain/SSL, admin password) unless the UX accepts either interactive prompts or command flags in command 2.

## 3. Open Questions (need Ripley / Juanma)
- What registry namespace and image name should the bootstrap script pull from: `ghcr.io/jmservera/aithena-installer`, the main app image namespace, or another release namespace?
- Should the bootstrap script version-lock to the repo `VERSION`, a milestone tag such as `v2.2.0`, or `latest` with an explicit `--version` override?
- What is the supported migration path for existing deployments using `/source/volumes/*`: automated copy into Docker-managed volumes, documented manual migration, or “new installs only” for v2.2.0?
- Is converting the 16 base bind-backed volumes a breaking change that should be gated behind a major/minor migration note or feature flag?
- Is mounting `/var/run/docker.sock` into the installer container acceptable for the default flow, or should the first release stop at file generation and ask the host to run `docker compose` separately?
- Should SSL certbot paths be included in the same volume migration as the base 16, even though they live in `docker/compose.ssl.yml` rather than `docker-compose.yml`?

## 4. Phase Order Recommendation
Recommend splitting the issue into approval-gated PRs and landing Phase 1 before the container installer:

1. **Phase 1: infra prerequisites** — migrate or abstract the 16 base `/source/volumes/` paths, decide how to handle the 2 SSL certbot paths, fix/validate the `start.sh` template, and audit `.env.example` for installer parity.
2. **Phase 2: installer image packaging** — add a Dockerfile only after the host dependencies and target filesystem contract are approved.
3. **Phase 3: bootstrap script with `--dry-run`** — validate the “Docker only” UX without starting the full stack by default.
4. **Phase 4: wizard UX inside the container** — adapt prompts and non-interactive flags once the packaging boundary is stable.
5. **Phase 5: migration/upgrade path** — document and/or automate bind-mount-to-volume moves for existing installations.
6. **Phase 6: release docs and smoke tests** — update Quick Start, offline docs, and a clean-WSL validation checklist.

This preserves the issue’s direction but moves risky data layout work before installer-container work. Phase 1 can ship as its own PR series because it improves today’s installer even if the container wrapper is delayed.

## 5. Risks
- Backwards compatibility: bind mounts → Docker-managed named volumes is a data migration for RabbitMQ, Redis, Solr, ZooKeeper, collections DB, and certbot state.
- Data loss risk if migration scripts copy the wrong direction, run while services are live, or do not preserve Solr/ZooKeeper ownership expectations.
- Docker socket mount in a bootstrap container grants broad host control; this needs explicit approval and documentation.
- Existing scripts assume `/source/volumes/` in multiple places (`docker-compose.yml`, SSL overlay, generated SSL `start.sh` block), so partial migration can produce split-brain storage.
- `docker/compose.single-node.yml` uses Compose `!override`; `.env.example` notes Docker Compose v2.20+ for that overlay, which should become an installer prerequisite if single-node remains a first-run choice.
- Current offline installer scripts already exist; the new wizard should not accidentally fork two incompatible install stories.

## 6. Recommended Next Step
Open the smallest implementation PR after approval: **Phase 1a — volume contract cleanup proposal implemented in compose only**. Convert one low-risk internal state volume class (for example Redis/RabbitMQ, not Solr/ZooKeeper first) to Docker-managed named volumes behind a documented migration note, add `docker compose config` validation, and update `.env.example` only where it reflects verified behavior.

Alternative if Ripley wants to validate UX before storage changes: add only an installer image Dockerfile + bootstrap `--dry-run` that prints the planned mounts and compose files, but does not write `.env`, create volumes, or start services.
