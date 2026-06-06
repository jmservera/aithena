# Solr 10 v2.5 Documentation Index

_Last updated:_ 2026-06-06
_Release:_ v2.5.0
_Status:_ 🟢 Documentation package ready; Solr 10 default runtime merged in PR #1680

---

## Overview

This index consolidates all Solr 10 migration documentation for **v2.5.0 release**. The documentation package is complete for v2.5. PR #1680 made Solr 10 the default runtime with an explicit Solr 9 rollback overlay. PR #1670 remains held and is documented as an optional scalar-quantization follow-up.

---

## Core Documents

### 1. **[Solr 9→10 Migration Plan](./solr-9-to-10.md)**
**Purpose**: Technical deep-dive on breaking changes, schema updates, and CLI syntax changes.
**Audience**: Developers, DevOps engineers
**Status**: ✅ Complete (merged)
**Sections**:
- Pre-migration assessment (current Solr 9 config)
- Breaking changes (CLI, HNSW, security, etc.)
- Migration steps (code-by-code walkthrough)
- Rollback plan
- Testing strategy
- Timeline and dependencies

**Key facts**:
- HNSW parameter names: Solr 10 uses `hnswM` / `hnswEfConstruction`; Solr 9 rollback rewrites to `hnswMaxConnections` / `hnswBeamWidth`
- CLI double-dash syntax: `-z $ZK` → `--zk-host $ZK`
- `blockUnknown` default changed from `false` (Solr 9) to `true` (Solr 10)
- Vector quantization options: default float32 is supported for v2.5; `int8` scalar quantization remains held in PR #1670
- Java requirement: Java 17 → Java 21+

---

### 2. **[Solr 10 Production Migration Runbook](./solr-10-production-runbook.md)** ✨ NEW
**Purpose**: Operator's step-by-step guide for production deployments.
**Audience**: Site operators, infrastructure engineers
**Status**: ✅ New (docs-only PR for #1353/#1359)
**Sections**:
- Pre-migration checklist (24 hours before)
- 3-phase migration procedure (pre-cutover, cutover, post-migration)
- Rollback triggers and procedures
- Troubleshooting guide
- Post-upgrade tuning (optional, deferred to v2.5.1)
- Escalation contacts

**Key workflows**:
- Pre-migration: backups, baseline metrics, team notification
- Cutover: maintenance window (2–8 hours), node-by-node upgrade, re-bootstrap
- Validation: search functionality, version check, metrics comparison
- Rollback: immediate (< 30 min) or via full reindex (1–4 hours)

---

### 3. **[Solr 10 PRD](../prd/solr10-migration-prd.md)**
**Purpose**: Business and technical rationale for Solr 10 migration.
**Audience**: Product managers, architects
**Status**: ✅ Complete (reference)
**Key points**:
- Eliminate embeddings-server for on-prem via `language-models` module (deferred)
- Simplify topology over time; v2.5 ships distributed and single-node SolrCloud, not standalone/core mode
- Future memory savings via scalar quantization once PR #1670 or an equivalent fix lands
- 40× faster GPU-accelerated indexing via cuVS (optional, deferred)

---

## Implementation Status

### Merged (Ready for v2.5.0)

| Component | PR/Commit | Status | Notes |
|-----------|-----------|--------|-------|
| HNSW schema migration | #1667 (53d454f) | ✅ Merged | Solr 9/10 compatibility, renames tested |
| CLI syntax rewrite | #1673 (2a04404) | ✅ Merged | solr-init fully updated for Solr 10 |
| `blockUnknown` default fix | #1663 | ✅ Merged | Health checks secured for Solr 10 |
| pathHierarchyTokenizer compat | #1665 | ✅ Merged | Field type compatibility verified |
| E2E tests (Solr 10 opt-in) | #1676 | ✅ Merged | Preflight + safe test coverage |
| Solr 10 default runtime cutover | #1680 | ✅ Merged | `solr:10` default, Tika service added, Solr 9 rollback overlay preserved |

### Held / Not Merged

| Component | PR | Status | Impact | Needed for |
|-----------|----|---------|---------|----|
| Scalar quantization bits fix | #1670 | ⏸️ Owner hold — do not merge | Keeps optional `VECTOR_QUANTIZATION=int8` on a safe Solr 10 setting | Optional v2.5.1+ memory optimization; do not enable int8 in v2.5 cutover |

### Deferred to v2.5.1+

| Feature | Scope | Reason | ETA |
|---------|-------|--------|-----|
| Vector quantization enabled by default | Schema + reindex | Needs benchmark for accuracy impact | v2.5.1 |
| cuVS GPU codec | Solr Dockerfile + compose override | Requires NVIDIA GPU, separate image | v2.5.1 |
| `efSearchScaleFactor` tuning | API + search logic | Query tuning optimization only | v2.5.1 |
| `language-models` module (Solr embeddings) | Search refactor | Depends on upstream LangChain4j work | v2.6+ |

---

## Deployment Scenarios

### Dev/Small (Single-Node SolrCloud)

**Migration path**:
1. Start the Solr 10 single-node SolrCloud overlay.
2. Run `solr-init` once.
3. Verify the `books` collection exists.
4. Reindex if the configset changed or the existing data was created under Solr 9 HNSW/luceneMatchVersion settings.

**Time**: < 10 minutes for runtime cutover; longer if reindexing.

**Docs**: Use production runbook § 2 (Phase 1–3), adapting node counts for the single-node SolrCloud overlay. True standalone/core mode is not shipped in v2.5.

### Production SolrCloud (3-Node HA)

**Migration path**:
1. Pre-migration: backup, notify team
2. Maintenance window: upgrade all 3 nodes + ZooKeeper, re-bootstrap auth/collection
3. Post-migration: validate, resume indexing

**Time**: 2–8 hours (depends on index size)

**Docs**: Follow production runbook § 2 exactly; rollback procedure in § 3.

---

## v2.5 Release Checklist

- [x] Migration plan complete ([solr-9-to-10.md](./solr-9-to-10.md))
- [x] Production runbook complete ([solr-10-production-runbook.md](./solr-10-production-runbook.md))
- [x] HNSW schema compatibility tested (PR #1667)
- [x] CLI syntax updated and tested (PR #1673)
- [x] Health check auth verified (PR #1663)
- [x] E2E test coverage added (PR #1676)
- [ ] Scalar quantization bits fix (PR #1670 held; optional for v2.5.1+, not default v2.5 runtime)
- [ ] Performance benchmarks (deferred to v2.5.1)
- [ ] GPU acceleration docs (deferred to v2.5.1)
- [ ] Embeddings-server optional mode docs (deferred to v2.6)

---

## How to Use These Docs

### For Release Notes (v2.5.0 announcement)

Reference:
- **What changed**: 🟢 Solr 10 upgrade (major version)
- **Why**: Solr 10 compatibility, future vector optimization path, GPU-ready foundation
- **Migration impact**: 2–8 hour maintenance window required; rollback available
- **Link**: [Production Migration Runbook](./solr-10-production-runbook.md)

### For Operators Planning Upgrade

1. **Read**: [Pre-Migration Checklist](./solr-10-production-runbook.md#1-pre-migration-checklist) (24 hours before)
2. **Review**: [Migration Procedure](./solr-10-production-runbook.md#2-migration-procedure) (understand all phases)
3. **Execute**: Follow § 2 step-by-step during maintenance window
4. **Troubleshoot**: Use [§ 4 Troubleshooting](./solr-10-production-runbook.md#4-troubleshooting) if any issues
5. **Rollback** (if needed): Follow [§ 3 Rollback Procedure](./solr-10-production-runbook.md#3-rollback-procedure)

### For Developers Adding Features

- **Query tuning**: See [Post-Upgrade Tuning](./solr-10-production-runbook.md#5-post-upgrade-tuning) for `efSearchScaleFactor` (v2.5.1)
- **Schema changes**: See [Breaking Changes](./solr-9-to-10.md#2-breaking-changes-in-solr-10) for HNSW and quantization status
- **CLI updates**: See [CLI Syntax](./solr-9-to-10.md#step-23-update-solr-init-cli-commands) for shell script patterns
- **Backward compat**: Solr 9 configsets still work if `solr-init` does compatibility rewrites (see test coverage)

---

## Remaining Issues & Blockers

### For v2.5.0 Release

Documentation coverage is ready once this docs-only PR merges:

- ✅ Issue #1353: Update documentation for Solr 10 → covered by migration plan, compatibility guide, docs index, and runbook.
- ✅ Issue #1359: Create Solr 10 migration runbook → covered by the production runbook.

Release implementation blocker:

- ⏸️ PR #1670 remains on owner hold. Keep `VECTOR_QUANTIZATION=int8` disabled unless that fix lands separately.

### For v2.5.1

- 📋 Perf tuning docs (vector quantization enabled, `efSearchScaleFactor` API)
- 📋 GPU acceleration guide (cuVS codec, NVIDIA Solr image)

### For v2.6

- 📋 Embeddings-server optional mode (requires `language-models` module upstream work)

---

## Document Maintenance

| Document | Last Updated | Maintainer | Review Cycle |
|----------|--------------|------------|--------------|
| solr-9-to-10.md | 2026-06-05 | Ash | Before each release |
| solr-10-production-runbook.md | 2026-06-05 | Brett | After each production deployment |
| solr10-migration-prd.md | 2026-03-31 | Ripley | Feature freeze for each release |

---

## Related Docs

- **Admin Manual**: [docs/admin-manual.md](../admin-manual.md) (security, backup, monitoring)
- **Deployment Topologies**: [docs/deployment-topologies.md](../deployment-topologies.md) (architecture)
- **Hardware Requirements**: [docs/hardware-requirements.md](../hardware-requirements.md) (Java 21+ required)
- **Disaster Recovery**: [docs/admin/disaster-recovery-runbook.md](../admin/disaster-recovery-runbook.md) (backup strategy)
- **Release Notes**: [docs/release-notes/v2.5.0.md](../release-notes/v2.5.0.md) (user-facing summary)
