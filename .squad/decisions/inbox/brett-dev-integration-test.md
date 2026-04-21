# Brett Decision: Dev Integration Test Single-Node Topology (#1496)

**Date:** 2026-04-21  
**Status:** ACCEPTED  
**Scope:** CI/CD, GitHub Actions workflows  

## Summary

Created a new GitHub Actions workflow (`dev-integration-test.yml`) that runs integration tests on the `dev` branch using a single-node Solr topology instead of the full 3-node SolrCloud cluster used in `integration-test.yml` (which targets `main`).

## Problem

The existing `integration-test.yml` workflow runs on PRs to `main` and uses a 3-node SolrCloud topology with a 3-node ZooKeeper quorum. This full topology:
- Takes 75 minutes to complete
- Requires significant resources (~17 containers)
- Is overkill for dev branch testing, where resilience isn't critical

Dev branch PRs need faster feedback without sacrificing test coverage.

## Solution

**New workflow:** `.github/workflows/dev-integration-test.yml`

**Topology:**
- 1 Solr node (vs 3)
- 1 ZooKeeper node (vs 3)
- All other services (Python, Redis, RabbitMQ, nginx) unchanged
- ~6 active containers (vs 17 in full SolrCloud)

**Implementation approach:**
- Docker Compose profile overrides in CI step (`services: { solr2: { profiles: [disabled] }, solr3: { profiles: [disabled] }, ... }`)
- No separate `compose.single-node.yml` file — keeps maintenance burden low
- Consistent with existing `docker/compose.e2e.yml` pattern

**Test coverage:** Unchanged
- Python E2E tests (full suite)
- Playwright browser tests (full suite)
- Same auth/admin API validation
- Solr cluster health checks adapted for single node

**Timeout:** 45 minutes (vs 75 for full workflow)

## Design Rationale

### Why single-node for dev?
- SolrCloud resilience features (replication, replica recovery, leader election, peer sync) add complexity and time
- Dev branch testing validates application correctness, not cluster robustness
- Node failures and recovery are tested on `main` with the full SolrCloud topology
- Single-node is sufficient to catch indexing bugs, query issues, and API integration problems

### Why not a separate `compose.single-node.yml` overlay?
- Profile overrides are applied inline in the CI step, avoiding a new file
- Reduces maintenance burden — no need to keep two compose file variants in sync
- Consistent with `docker/compose.e2e.yml` which applies minimal, workflow-specific overrides
- The override is small (~30 lines) and self-documenting in the workflow

### Timeout justification
- Full SolrCloud workflow: 75 minutes (includes 3-node startup, leader election, etc.)
- Single-node: expected 30–35 minutes with cold Docker build, 20 min with cached layers
- 45 minutes is conservative and allows for slower runners or extended health checks

## Deployment & CI Changes

**New files:**
- `.github/workflows/dev-integration-test.yml` — 415 lines

**Modified files:** None

**Workflow triggers:**
- `push` to `dev` branch
- `pull_request` to `dev` branch
- `workflow_dispatch` (manual)

**Change detection:** Inherits from existing pattern — skips if only non-build files changed (docs, .squad/, etc.)

## Related Workflows

| Workflow | Branch | Topology | Timeout |
|----------|--------|----------|---------|
| integration-test.yml | main | 3-node SolrCloud + ZK quorum | 75 min |
| dev-integration-test.yml | dev | 1-node Solr + single ZK | 45 min |

Both workflows run the same test suites; topology differs only.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Single-node Solr doesn't catch replica/replication bugs | Full 3-node tests run on main; dev is for app-level validation |
| ZooKeeper single-node behavior differs from quorum | Single ZK node still validates Solr can connect to ZK; most app code doesn't interact with ZK directly |
| Single node runs out of memory or hits resource limits | Monitoring in dev can catch this; containers have same limits as in 3-node setup |

## Future Considerations

1. **Branch-specific test matrices:** If dev & main test suites diverge, may need separate test configs per workflow
2. **Performance baselines:** Monitor actual runtimes; adjust timeout if consistently too high/low
3. **SolrCloud feature coverage:** If new features depend on replication/leader election, add tests to integration-test.yml only
