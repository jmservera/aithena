# Aithena v1.0 Readiness Checklist

_Prepared against the v0.12.0 documentation baseline_  
_Prepared by:_ Newt (Product Manager)

This checklist is the pre-release gate for promoting Aithena from the current **v0.12.0** documentation baseline to **v1.0.0**. It combines product history, security posture, operability readiness, CI/CD coverage, documentation status, and the remaining release-gate items that must be explicitly accepted before tagging a v1 release.

## Status legend

- `[x]` Shipped and documented in the current repository state
- `[ ]` Final v1.0 validation or sign-off still required
- `[!]` Known gap, limitation, or decision to carry into the v1.0 release notes

## 1. Milestone issue references for v1.0.0

These milestone issues define the final release gate and must be referenced in the release decision:

- [ ] **#222 — restructure**: confirm the final v1.0 packaging and release narrative are organized as intended
- [ ] **#223 — validate builds**: confirm clean build/test commands and release artifacts from a fresh checkout
- [ ] **#224 — validate CI**: confirm the GitHub Actions pipeline is green on the release candidate
- [ ] **#225 — update docs**: confirm admin, deployment, monitoring, and release docs all match the v1.0 release candidate
- [ ] **#260 — release gate**: record the final go/no-go approval for the v1.0.0 milestone

## 2. Feature history coverage (v0.1 through v0.12)

| Release window | Scope to verify for v1.0 | Evidence in repo |
| --- | --- | --- |
| **v0.1-v0.3 foundations** | Prototype-to-platform build-out: document ingestion, metadata extraction, queue-backed indexing, Solr-centered search architecture, and the move toward the current FastAPI/React stack | `README.md` architecture + project phases, `docs/admin-manual.md`, git tag `v0.3.0`, `.squad/log/2026-03-13T18-44-phase1-implementation.md` |
| **v0.4.0** | Search-first reading experience: keyword search, facet filters, PDF viewer, Status tab, Stats tab | `docs/features/v0.4.0.md`, `docs/test-report-v0.4.0.md` |
| **v0.5.0** | Semantic and hybrid search, Similar Books, embedded admin dashboard, language detection fix, startup ordering hardening | `docs/features/v0.5.0.md`, `docs/test-report-v0.5.0.md` |
| **v0.6.0** | PDF upload flow, upload validation/rate limits, Bandit/Checkov/Zizmor security scans, container health/resource hardening | `docs/features/v0.6.0.md`, `docs/security/baseline-v0.6.0.md`, `docs/test-report-v0.6.0.md` |
| **v0.7.0** | Versioning infrastructure, `/version` endpoints, admin observability, release automation | `docs/features/v0.7.0.md`, `docs/test-report-v0.7.0.md` |
| **v0.8-v0.9 hardening** | Admin/release-confidence and Python dependency security re-baselining remain represented in the current repo, but retained release artifacts are incomplete | git tag `v0.8.0`, `docs/security/baseline-v0.9.0.md`, current workflow + dependency manifests |
| **v0.10.0** | GitHub Actions supply-chain hardening: SHA pinning, least-privilege permissions, fixed Bandit config, `persist-credentials: false` | `docs/release-notes-v0.10.0.md`, `docs/test-report-v0.10.0.md` |
| **v0.11.0** | Local auth, JWT sessions, protected routes, nginx auth gate, installer-driven first run setup | `docs/features/v0.11.0.md`, `docs/release-notes-v0.11.0.md`, `docs/test-report-v0.11.0.md` |
| **v0.12.0** | Metrics endpoint, credential rotation, degraded-mode search, failover runbook/drill, sizing guide/benchmark, integration-test workflow, release-docs workflow, and final GitHub Actions hardening cleanup | `docs/monitoring.md`, `docs/deployment/production.md`, `docs/deployment/failover-runbook.md`, `docs/deployment/sizing-guide.md`, `.github/workflows/integration-test.yml`, `.github/workflows/release-docs.yml`, `.github/workflows/security-zizmor.yml` |

### Feature coverage checklist

- [x] Foundational ingestion/search architecture is present in the current stack and reflected in the README/admin manual
- [x] Search UX baseline from v0.4.0 is documented and test-reported
- [x] Semantic/hybrid retrieval and admin operations from v0.5.0 are documented and test-reported
- [x] Upload flow, security scanning, and container hardening from v0.6.0 are documented and test-reported
- [x] Versioning and release automation from v0.7.0 are documented and test-reported
- [x] Security and dependency hardening through v0.10.0 and v0.11.0 are documented in release notes/test reports
- [x] v0.12.0 operability work is documented in monitoring and deployment guides
- [!] Historical release artifacts are incomplete for **v0.1-v0.3** and **v0.8-v0.9**; treat this as a documentation-history gap, not a missing runtime feature

## 3. Security hardening readiness

### Access control, auth, and browser boundary

- [x] `solr-search` ships local authentication with a SQLite user store, Argon2id password hashing, JWT issuance/validation, and bearer-token/cookie sessions
- [x] nginx protects `/v1/*`, `/documents/*`, and `/admin/*` through `auth_request`, with browser redirects to `/login` and `401` responses for API clients
- [x] Installer-managed first-run setup creates the auth DB path and JWT secret before Compose startup
- [ ] Confirm the v1.0 release candidate still enforces login across the standard nginx surface after a clean install (**#223**, **#260**)

### CORS and origin control

- [x] `solr-search` exposes `CORS_ORIGINS` and the installer collects a public origin during setup
- [x] Deployment docs consistently frame the nginx origin as the production entrypoint
- [ ] Confirm the production `CORS_ORIGINS` / public origin values match the final v1 hostname and do not allow stale development origins (**#223**)

### Input validation and abuse resistance

- [x] Upload handling validates MIME type, `.pdf` extension, PDF magic bytes, maximum size, and rate limits per client IP
- [x] Path traversal protections are documented for uploaded filenames and staging paths
- [x] Security scanning is in place for Python code, Docker/GitHub Actions IaC, and GitHub Actions supply-chain risks
- [ ] Decide whether the v1.0 release gate should require follow-up closure for the remaining dependency-security backlog recorded in `docs/security/baseline-v0.9.0.md`

### Credential rotation and secret hygiene

- [x] The installer can rotate JWT/auth bootstrap values and regenerate service credentials
- [x] Production docs include manual rotation guidance for `RABBITMQ_USER`, `RABBITMQ_PASS`, and `REDIS_PASSWORD`
- [x] GitHub Actions are SHA-pinned, least-privilege, and use non-persistent checkout credentials
- [x] The prior GitHub Actions security audit backlog is resolved in current release documentation, including the reported reduction from 17 to 0 `zizmor` alerts
- [ ] Re-run the documented credential-rotation procedure on the v1 candidate and verify all dependent services reconnect cleanly (**#223**, **#260**)

## 4. Operability readiness

### Monitoring and observability

- [x] `/v1/status/` gives operator-friendly application health with Solr, Redis, RabbitMQ, and embeddings visibility
- [x] `/v1/stats/` reports indexed-book totals plus language/author/year/category breakdowns
- [x] `/v1/metrics` exposes Prometheus-compatible counters, histograms, and gauges for search, queue depth, failures, embeddings availability, and Solr live nodes
- [x] `docs/monitoring.md` includes a scrape example and starter alert thresholds
- [ ] Confirm the v1 deployment includes a real Prometheus scrape target, alert routing, and dashboard ownership—not just endpoint availability (**#260**)

### Resilience and graceful degradation

- [x] Semantic and hybrid search now fall back to keyword mode when embeddings are unavailable and return explicit degraded metadata
- [x] A failover runbook exists for Solr, Redis, RabbitMQ, embeddings, and nginx outage scenarios
- [x] `e2e/failover-drill.sh` exists to rehearse the documented recovery path in a Docker-capable environment
- [ ] Run or review at least one failover drill against the release candidate and record outcomes before v1.0 approval (**#260**)

### Capacity and sizing

- [x] `docs/deployment/sizing-guide.md` provides sizing formulas, deployment profiles, and operator guidance for Solr, Redis, RabbitMQ, embeddings, and indexing throughput
- [x] `e2e/benchmark.sh` exists to replace analytical sizing assumptions with measured results
- [ ] Capture at least one benchmark snapshot on representative hardware or explicitly accept that v1.0 ships with analytical sizing only (**#260**)

## 5. CI/CD pipeline readiness

### Automated validation inventory

- [x] `ci.yml` covers `document-indexer` tests, `solr-search` tests, and Python linting on `dev`
- [x] `lint-frontend.yml` covers ESLint and Prettier for `aithena-ui`
- [x] `integration-test.yml` runs a Compose-based environment with Python E2E tests and Playwright browser coverage
- [x] `version-check.yml` validates the `VERSION` file and Dockerfile `ARG VERSION` declarations
- [x] `release.yml` handles release tagging/build publication
- [x] `release-docs.yml` automates release notes/test report generation for future releases
- [x] `security-bandit.yml`, `security-checkov.yml`, and `security-zizmor.yml` provide continuous security scanning
- [x] `squad-heartbeat.yml` is present with manual/issue-driven triggers, and its current implementation no longer blocks the v1 docs gate even though the cron schedule remains intentionally disabled

### Standard validation set to confirm before v1.0

- [ ] `cd src/solr-search && uv run pytest -v --tb=short`
- [ ] `cd src/document-indexer && uv run pytest -v --tb=short`
- [ ] `cd src/aithena-ui && npx vitest run`
- [ ] `cd src/aithena-ui && npm run lint && npm run build`
- [ ] Confirm the GitHub integration-test workflow is green on the release candidate branch/PR (**#224**)
- [ ] Confirm the security workflows complete cleanly enough for Code Scanning review, even where configured as non-blocking (**#224**, **#260**)

### Current local validation snapshot for this docs pack

- [x] `solr-search` tests passed locally (144 tests)
- [x] `aithena-ui` Vitest passed locally (83 tests)
- [x] `aithena-ui` lint and build passed locally
- [!] `document-indexer` local pytest execution was blocked in this offline environment by dependency download/certificate resolution, so the definitive signal must come from CI or a network-enabled clean environment

## 6. Documentation completeness

### Operator and deployment docs

- [x] `docs/admin-manual.md` exists and includes deployment, monitoring, auth, and v0.12.0 operator guidance
- [x] `docs/deployment/production.md` covers first-run setup, credential rotation, health validation, backup/restore, and production hardening checks
- [x] `docs/deployment/failover-runbook.md` covers outage detection and recovery order
- [x] `docs/deployment/sizing-guide.md` covers capacity planning assumptions and benchmark usage
- [x] `docs/monitoring.md` covers the metrics surface and alert starter rules
- [x] Release notes/test reports exist for the latest formal release artifacts already captured in the repo

### Documentation gaps to accept or close

- [!] There is **no dedicated standalone API reference**; endpoint behavior is spread across the README, admin manual, and feature guides
- [!] Early historical release artifacts are incomplete for **v0.1-v0.3** and **v0.8-v0.9**
- [ ] Decide whether v1.0 requires a dedicated API reference page, or whether the current distributed documentation is acceptable for GA (**#225**, **#260**)

## 7. Known issues / gaps to surface in v1.0 release notes

- [!] **Primary Solr routing remains a manual failover concern.** The application tier still points at `http://solr:8983/solr`, so losing the primary `solr` service is user-visible even if replica nodes are healthy.
- [!] **Embeddings are still a single-service dependency.** The new degraded-mode path keeps search usable, but semantic quality drops to keyword-only during embeddings outages.
- [!] **Sizing guidance is analytical until benchmarked.** The benchmark script exists, but the published guide is explicit that the current numbers are planning baselines rather than production measurements.
- [!] **RabbitMQ and Redis remain single-node services in the shipped Compose deployment.** Persistence is documented, but cross-node HA is not part of the current deployment story.
- [!] **API documentation is fragmented.** Operators have the necessary deployment guidance, but integrators still lack a single canonical endpoint reference.
- [!] **Historical release documentation is incomplete for some pre-v0.10 milestones.** This affects archival completeness more than runtime readiness.

## 8. Recommended go/no-go summary

Aithena now has the feature set, security posture, and operability documentation expected of a v1 candidate. The remaining work is primarily **release-gate validation** rather than missing functionality:

- [ ] close the milestone gate items (**#222, #223, #224, #225, #260**)
- [ ] confirm green CI on the actual release candidate
- [ ] confirm build/install/credential-rotation paths from a clean environment
- [ ] decide whether the known infrastructure limitations are acceptable for v1.0 GA and explicitly document them in the release notes

If those release-gate checks are completed and the known limitations are accepted, the current **v0.12.0** baseline is a credible launch point for **v1.0.0**.
