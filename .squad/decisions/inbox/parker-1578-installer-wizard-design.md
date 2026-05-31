# Decision: Wizard Installer — Two-Layer Architecture (#1578)

**Author:** Parker (via Ralph v2.2.0 sweep)
**Date:** 2026-05-24
**Status:** Approved — open questions resolved by jmservera 2026-05-31
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
   - It should support `--dry-run`, `--version`, `--image`, `--install-dir`, and `--library-path` from day one so Juanma can validate the promised "clean WSL + Docker only" story without hidden dependencies.

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

Operational caveats still to handle in implementation:
- Running a wizard container with `/var/run/docker.sock` mounted is operationally simple but security-sensitive; the repo already warns about Docker socket risk in `solr-search`. Mitigation: document the risk in release notes and use a minimal base image.
- A "2 commands install" may conflict with required choices (library path, domain/SSL, admin password) unless the UX accepts either interactive prompts or command flags in command 2.

## 3. Decisions (resolved by jmservera 2026-05-31)

| # | Question | Decision |
|---|---|---|
| 1 | Registry namespace / image name | **`ghcr.io/jmservera/aithena-*`** — publish and use the existing release-image namespace at `https://github.com/jmservera?tab=packages&repo_name=aithena`. No separate registry. |
| 2 | Bootstrap script version-locking | **Lock to the current release `VERSION` during the release pipeline.** Every published `bootstrap.sh` is regenerated with the matching versioned installer image tag — so users always pull a deterministic, tested combination. No floating `latest`. |
| 3 | Migration path for existing `/source/volumes/*` deployments | **None — new version starts from scratch.** No automated copy, no documented manual migration. Release notes notify users that v2.2.0 is a clean install. |
| 4 | Converting 16 base bind-backed volumes — breaking change handling | **Not treated as a breaking migration.** Clean-install policy means there is nothing to migrate; release notes simply call out "v2.2.0 installs from scratch — pre-existing `/source/volumes/` is not preserved." |
| 5 | Mounting `/var/run/docker.sock` in installer container | **Acceptable** for the default flow. Documented as a known requirement with a security note. |
| 6 | SSL certbot paths in `docker/compose.ssl.yml` | **Same clean-install policy** — no migration. Users with existing certbot data must re-issue or restore from their own backup. |

These decisions deliberately trade backward compatibility for a clean v2.2.0 installer story, reducing implementation scope and eliminating the entire migration phase.

## 4. Phase Order Recommendation

With the clean-install policy in place, the implementation collapses from six phases to five:

1. **Phase 1: volume contract cleanup** — convert the 16 base `/source/volumes/` bind mounts to Docker-managed named volumes in `docker-compose.yml` and the SSL overlay, fix/validate the `start.sh` template, and audit `.env.example` for parity. Includes `docker compose config` validation in CI.
2. **Phase 2: installer image packaging** — add `installer/Dockerfile` and a release-pipeline job that builds and pushes `ghcr.io/jmservera/aithena-installer:${VERSION}` alongside the other release images.
3. **Phase 3: bootstrap script with `--dry-run`** — generate a versioned `bootstrap.sh` during release that pulls the matching installer image tag and validates the "Docker-only" UX without starting the full stack by default.
4. **Phase 4: wizard UX inside the container** — adapt prompts and non-interactive flags once the packaging boundary is stable.
5. **Phase 5: release docs and smoke tests** — update Quick Start, offline docs, a clean-WSL validation checklist, and the v2.2.0 release note that calls out the clean-install policy.

This preserves the issue's direction. Phase 1 can ship independently because it improves today's installer even if the container wrapper is delayed.

## 5. Risks

- Docker socket mount in a bootstrap container grants broad host control; this needs explicit documentation and a minimal base image.
- Users who upgrade in place from earlier versions will lose `/source/volumes/` data unless they take their own backup before running the v2.2.0 installer — release notes must call this out prominently to avoid surprise data loss.
- Existing scripts assume `/source/volumes/` in multiple places (`docker-compose.yml`, SSL overlay, generated SSL `start.sh` block); Phase 1 must convert all of them in one PR to avoid split-brain storage.
- `docker/compose.single-node.yml` uses Compose `!override`; `.env.example` notes Docker Compose v2.20+ for that overlay, which should become an installer prerequisite if single-node remains a first-run choice.
- Current offline installer scripts already exist; the new wizard should not accidentally fork two incompatible install stories.

## 6. Recommended Next Step

Open the smallest implementation PR after approval: **Phase 1a — convert one low-risk internal state volume class (Redis + RabbitMQ) to Docker-managed named volumes**. Land that, validate `docker compose config` in CI, then proceed with the remaining services (ZooKeeper, Solr, certbot) in subsequent Phase 1 PRs.

Alternative if Ripley wants to validate UX before storage changes: add only an installer image Dockerfile + bootstrap `--dry-run` that prints the planned mounts and compose files, but does not write `.env`, create volumes, or start services.
