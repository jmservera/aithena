
# Decision: Replication Factor Must Clamp to Expected Nodes

**Author:** Parker (Backend Dev)  
**Date:** 2026-05-24  
**Status:** Approved  
**Issue:** #1544 (implemented in PR #1579)

**Decision:** All Solr collection initialization paths must clamp `replicationFactor` to the in-scope `EXPECTED_NODES` value when `SOLR_REPLICATION_FACTOR` is higher than the available topology. Do not only warn and continue with an oversized replication factor.

**Rationale:** Single-node overlays can inherit stale `.env` values such as `SOLR_REPLICATION_FACTOR=3`. If init requests more replicas than available nodes, Solr can create collections with zero active replicas, causing RED health and cascading overlay failures.

---

# Decision: CodeQL-Safe Naming for Sensitive Credential Status Logs

**Author:** Parker (Backend Dev)  
**Date:** 2026-05-24  
**Status:** Approved  
**Issue:** #1576 (implemented in PR #1580)

**Context:** GHAS alert #233 (`py/clear-text-logging-sensitive-data`) flagged the installer summary line that prints `- JWT secret: generated|kept existing`. The printed value is a literal status derived from a boolean, not the secret itself, but the previous local name (`secret_status`) made the false-positive harder for CodeQL to disambiguate.

**Decision:** When logging summaries about credential rotation or generation, local variables that contain only enum/status literals should avoid sensitive substrings such as `secret` or `password`. Prefer names that describe the operation state, such as `jwt_rotation_status` or `solr_rotation_status`, and keep comments explicit that only literal status values are logged.

**Impact:** This preserves user-facing installer output while making false positives less likely in CodeQL and other taint/name-based scanners.

---

# Decision: Wizard Installer — Design Proposal (Research Spike for #1578)

**Author:** Parker (Backend Dev)  
**Date:** 2026-05-24  
**Status:** Proposal — awaiting Ripley + Juanma approval  
**Issue:** #1578 (research spike PR #1581)

### Current State (verified)

- 16 base bind-backed local volumes under `/source/volumes/`, grouped by consuming service
- Additional non-base SSL bind-backed volumes in `docker/compose.ssl.yml` (certbot paths)
- All missing compose overlays referenced by generated `start.sh` exist
- Current installer: 914 lines in `installer/setup.py`
- Hard Python dependencies: Python `>=3.12`, `aithena-common`, `argon2-cffi>=23.1`
- Quick Start currently documents `python3 -m installer` followed by `./start.sh`

### Proposed Architecture

Two-layer installer:

1. **Tiny host bootstrap script**
   - Verify Docker + Compose v2, create working directory, pull versioned installer image, run with minimum required mounts
   - No Python, no package manager, no project checkout required
   - Support `--dry-run`, `--version`, `--image`, `--install-dir`, `--library-path` from day one

2. **Versioned installer container image**
   - Package current Python installer + dependencies inside image
   - Run existing wizard logic in-container first, then evolve prompts
   - Mount only: target install directory, optional book library path, Docker control if creating volumes
   - Generate `.env`, create/seed auth DB, render `start.sh`, optionally run `docker compose config`

### Open Questions (need Ripley / Juanma)

- What registry namespace and image name: `ghcr.io/jmservera/aithena-installer`, main app namespace, or other?
- Version-locking: repo `VERSION`, milestone tag (`v2.2.0`), or `latest` with `--version` override?
- Migration path for existing deployments using `/source/volumes/*`: automated copy, documented manual, or "new installs only"?
- Converting 16 base volumes: breaking change requiring major/minor migration note or feature flag?
- Docker socket mount in installer: acceptable for default flow, or stop at file generation and ask host to run `docker compose` separately?
- SSL certbot paths: include in volume migration, or defer?

### Phase Order Recommendation

Split into approval-gated PRs, land Phase 1 before container installer:

1. **Phase 1:** Migrate/abstract 16 base `/source/volumes/` paths, decide SSL path strategy, fix/validate `start.sh` template, audit `.env.example`
2. **Phase 2:** Installer image Dockerfile
3. **Phase 3:** Bootstrap script with `--dry-run`
4. **Phase 4:** Wizard UX in container
5. **Phase 5:** Migration/upgrade path
6. **Phase 6:** Release docs and smoke tests

### Risks

- Backwards compatibility: bind mounts → Docker-managed volumes is data migration for RabbitMQ, Redis, Solr, ZooKeeper, collections DB, certbot
- Data loss if migration runs while services live or direction is wrong
- Docker socket mount grants broad host control
- `/source/volumes/` paths embedded in multiple places; partial migration causes split-brain storage
- `docker/compose.single-node.yml` uses Compose `!override`; existing offline scripts may fork incompatibly

### Recommended Next Step

Smallest implementation PR after approval: **Phase 1a — volume contract cleanup in compose only**. Convert one low-risk internal state volume (e.g., Redis/RabbitMQ, not Solr/ZooKeeper first) to Docker-managed named volumes, add `docker compose config` validation, update `.env.example`.

Alternative if Ripley prefers UX validation first: add only installer image Dockerfile + bootstrap `--dry-run` that prints planned mounts and compose files without writing `.env`, creating volumes, or starting services.

---

# Decision: Dependabot Batch Sweep 2026-05-31

**Date:** 2026-05-31  
**Author:** Ripley (Lead)  
**Status:** Completed

## Summary

Batched 16 low/medium-risk Dependabot PRs into PR #1584 (squash-merged to dev). Deferred 5 high-risk PRs with tracking issues.

## What Merged

16 dependency bumps across: .github/workflows (2), aithena-ui (6), solr-search (4), document-indexer (2), document-lister (1), embeddings-server (1).

## What's Deferred

- **Solr 10** (#1562): Belongs to v2.5 milestone, tracked in #1335
- **Python 3.14** (#1565, #1566, #1567): New tracking issue #1585
- **Node 26** (#1564): New tracking issue #1586

## Process Notes

- Cherry-pick + lockfile-regen pattern works well for batch sweeps
- Rulesets require all conversations resolved AND branch up-to-date — cannot bypass with --admin
- E2E flake #1583 caused 4 reruns; remains a reliability concern
- Code-scanning review threads auto-create on each push; must resolve before merge

## Affects

All team members doing future dependency sweeps should follow same pattern.

