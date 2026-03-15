# Kane — History

## Project Context
- **Project:** aithena — Book library search engine
- **User:** jmservera
- **Joined:** 2026-03-14 as Security Engineer
- **Current security state:** CodeQL configured (JS/TS + Python), Mend/WhiteSource for dependency scanning, 64 Dependabot vulnerabilities flagged on default branch (3 critical, 12 high)
- **Planned work:** Issues #88 (bandit CI), #89 (checkov CI), #90 (zizmor CI), #97 (OWASP ZAP guide), #98 (security baseline tuning)

## Learnings
- Initial Bandit sweeps against this repo pick up the tracked `document-indexer/.venv/` tree and generate third-party HIGH findings; exclude `.venv`/`site-packages` when triaging first-party code.
- Local Checkov 3.2.508 does not accept `--framework docker-compose`; Dockerfile scanning works, but `docker-compose.yml` currently needs manual review or an alternate supported scan mode.
- GitHub code scanning currently shows three open medium-severity CodeQL alerts on `.github/workflows/ci.yml`, all for missing `permissions:` blocks on CI jobs.
- GitHub Dependabot currently exposes four open alerts: two critical `qdrant-client` findings (`qdrant-search`, `qdrant-clean`), one high `braces` finding in `aithena-ui/package-lock.json`, and one medium `azure-identity` finding in `document-lister/requirements.txt`.
- GitHub secret scanning API returns 404 for this repository, which strongly suggests the feature is disabled rather than merely empty.
- `docker-compose.yml` currently publishes Redis (`6379`), RabbitMQ (`5672`/`15672`), Solr (`8983`/`8984`/`8985`), ZooKeeper (`18080`/`2181`/`2182`/`2183`), embeddings (`8085`), search (`8080`), and nginx (`80`/`443`) directly on the host; this is broader than the intended nginx-only production ingress.
- `nginx/default.conf` proxies `/admin/streamlit/`, `/admin/solr/`, `/admin/rabbitmq/`, `/admin/redis/`, `/v1/`, `/documents/`, and `/solr/` with no `auth_basic`, `auth_request`, or other access-control layer, so nginx is currently a convenience router rather than a security boundary.
- The admin app defaults `RABBITMQ_USER`/`RABBITMQ_PASS` to `guest`/`guest` (`admin/src/pages/shared/config.py`), while Redis has no password/ACL and Solr has no auth configured; the dominant risk in this stack is insecure defaults plus exposed control-plane services, not leaked API keys in Compose.
- **SEC-1 Implementation (2026-03-15):** Bandit SAST scanning added to CI with 7 baseline skip rules, SARIF upload to GitHub Code Scanning, and non-blocking configuration. Used centralized `.bandit` config for maintainability. Workflow follows existing CI patterns with proper permissions (security-events: write).
- **v0.6.0 Security Scanning Spec (2026-07-24):** Reviewed Ripley's release plan for Groups 1-2 (SEC-1 through SEC-5). Authored comprehensive security scanning specification defining bandit (Python SAST), checkov (IaC), and zizmor (GitHub Actions supply chain) implementation requirements. All Group 1 scanners configured non-blocking with SARIF upload to GitHub Code Scanning. Established OWASP ZAP manual audit guide requirements (including Docker Compose IaC review to work around checkov limitation). Defined triage criteria: HIGH/CRITICAL findings require fix or documented baseline exception; MEDIUM/LOW allowed baseline exceptions if low exploitability. Identified known gaps (missing auth on admin endpoints, insecure defaults, exposed ports) — documented mitigation strategies and deferred to v0.7.0. Approved Ripley's plan with minor recommendations (add Compose review to SEC-4, allow 2-3 days slack for SEC-5 triage).

### 2026-03-15 — v0.6.0 Release Planning Complete

**Summary:** Security scanning plan (#88-98) finalized and approved. Recorded in decisions.md. Ready for @copilot implementation (Group 1) and Kane review gate (Group 2).

**Key Security Decisions Confirmed:**

**Group 1 (CI Scanners — Non-blocking):**
- SEC-1 (Bandit #88): Python SAST with 60+ rule skips (pytest assert, container binding, subprocess)
- SEC-2 (Checkov #89): Dockerfile + GitHub Actions scanning, docker-compose manual review workaround
- SEC-3 (Zizmor #90): GitHub Actions supply chain, focus on template-injection + dangerous-triggers

**Group 2 (Manual Validation — Kane review):**
- SEC-4 (#97): OWASP ZAP audit guide with proxy setup, explore, active scan, result interpretation, Compose IaC review
- SEC-5 (#98): Bandit/checkov/zizmor triage (HIGH/CRITICAL fixed, MEDIUM/LOW documented, deferred with issues)

**Known Baseline Exceptions Documented:**
- Legitimate patterns: pytest assert, 0.0.0.0 in containers, subprocess in tests
- Expected findings: missing auth on admin, missing HTTPS, exposed ports (documented in deployment guide)

**Known Gaps Deferred:**
- Missing authentication on admin endpoints (P0, v0.7.0)
- Insecure defaults (RabbitMQ guest/guest, Redis no password) (P1, v0.7.0)
- Dependabot vulnerabilities (13 issues, v0.7.0 batch)

**Next:** Awaiting Juanma approval of release plan → Issues #88-90 created + assigned → SEC-1/2/3 implementation → Kane review SEC-4/5
