# SEC-4 Decision: OWASP ZAP Manual Audit Guide

**Date:** 2025-03-15  
**Author:** Kane (Security Engineer)  
**Issue:** #97  
**PR:** #194  
**Status:** Implemented

## Context

Implementing SEC-4 from v0.6.0 security scanning plan. Created comprehensive OWASP ZAP manual security audit guide as the primary dynamic application security testing (DAST) methodology before release.

## Decision

Created 30KB+ OWASP ZAP audit guide (`docs/security/owasp-zap-audit-guide.md`) covering:

1. **DAST Workflow** — Prerequisites, environment setup, proxy config, manual explore phase, active scan, result interpretation, reporting
2. **Docker Compose IaC Review** — Manual checklist for `docker-compose.yml` security (compensates for checkov's lack of docker-compose support)

## Rationale

**Why OWASP ZAP:**
- Industry-standard DAST tool (OWASP project)
- Free and open source
- Supports both manual exploration (guided crawling) and automated active scanning
- Generates SARIF reports for CI/CD integration (future work)

**Why Manual Guide (Not Automated):**
- v0.6.0 has no authentication yet — ZAP automation scripts require authenticated sessions
- Manual exploration captures nuanced UI workflows (React search, PDF viewer, admin dashboards)
- Allows security engineer judgment for baseline exceptions vs. true findings
- Educational — team learns DAST methodology, not just CI job results

**Why Docker Compose IaC Review:**
- Checkov 3.2.508 does not support `--framework docker-compose` (confirmed in SEC-2)
- docker-compose.yml is critical infrastructure surface (ports, volumes, networks, secrets)
- Manual checklist provides structured review until checkov adds support or alternate tool adopted

## Key Decisions

### 1. ZAP Proxy Port: 8090 (Not Default 8080)

**Reason:** aithena's `solr-search` service uses port 8080 (docker-compose.override.yml). Running ZAP on 8090 avoids port conflict while still testing solr-search through nginx proxy.

### 2. Manual Explore Phase: 15-30 Minutes

**Scope:**
- React UI (search, pagination, PDF viewer, edge cases)
- Search API (Swagger UI, all endpoints with valid + malicious inputs)
- Admin interfaces (Streamlit, Solr, RabbitMQ, Redis)
- File upload (if applicable)

**Reason:** Thorough crawling builds complete ZAP site map before active scan, ensuring all endpoints tested.

### 3. Docker Compose IaC Checklist: 7 Categories

**Categories:**
1. Port exposure (dev vs. prod ports, unnecessary publications)
2. Volume mounts (host path security, read-only configs)
3. Network isolation (frontend/backend/data segmentation)
4. Secrets in env vars (hardcoded credentials, .env usage)
5. Image pinning (version tags, SHA digests)
6. Container privileges (privileged, cap_add, security_opt)
7. Restart policies (crash loops, one-time init)

**Reason:** Comprehensive coverage of docker-compose attack surface. Checklist ensures consistent review across releases.

### 4. Result Interpretation: Baseline Exception Workflow

**Triage Levels:**
- **HIGH/CRITICAL:** MUST fix or document baseline exception with justification
- **MEDIUM:** Fix recommended; low-priority exceptions allowed (if low exploitability)
- **LOW/INFO:** Optional fix; exceptions allowed

**Baseline Exception Template:**
- Finding ID, severity, CWE, endpoint
- Reason for exception (e.g., "Admin endpoints internal-only, firewalled in prod")
- Mitigating controls (network ACLs, deployment docs, future issues)
- Approved by, date, review date

**Reason:** Balances security rigor with pragmatic release velocity. Documents risk acceptance for audit trail.

## Implementation Notes

### Known Baseline Exceptions Documented

**HIGH Severity:**
1. Missing authentication on `/admin/solr/`, `/admin/rabbitmq/`, `/admin/redis/` — Known issue #98, deferred to v0.7.0 (production deploys firewall these endpoints)
2. Default RabbitMQ credentials (`guest/guest`) — Known issue #98, deferred to v0.7.0
3. Redis no authentication — Known issue #98, deferred to v0.7.0

**MEDIUM Severity:**
1. Missing Anti-clickjacking Header — Acceptable (nginx not security boundary yet)
2. No Content Security Policy — NEW finding, recommend for v0.6.1/v0.7.0
3. Missing X-Content-Type-Options — Acceptable (informational hardening)

**Docker Compose Findings:**
1. 10+ internal ports exposed in `docker-compose.override.yml` — Dev-only, verified not in production deploy
2. Solr nodes publish 8983-8985 directly — Should be internal-only in prod (document in deployment guide)
3. Images lack SHA digest pinning — Supply chain risk, recommend SHA pinning for v0.7.0
4. `redis` image lacks explicit version tag — Recommend `redis:7.2-alpine`

### Architecture References

**Verified Accurate:**
- docker-compose.yml (production config)
- docker-compose.override.yml (dev port exposures)
- nginx/default.conf (proxy routes: /, /v1/, /admin/streamlit/, /admin/solr/, /admin/rabbitmq/, /admin/redis/, /documents/, /solr/)
- Service ports: nginx (80/443), solr-search (8080), streamlit (8501), Solr (8983-8985), RabbitMQ (15672), Redis (6379), ZooKeeper (18080/2181-2183)

## Benefits

1. **Release Gating:** OWASP ZAP audit now required before major releases (v0.X.0)
2. **Team Education:** Step-by-step guide trains developers on DAST methodology
3. **IaC Coverage Gap:** Docker Compose checklist fills checkov limitation
4. **Baseline Documentation:** Audit report template standardizes risk acceptance process
5. **Future Automation:** Guide lays groundwork for zap-baseline.py / zap-full-scan.py CI integration (after auth implemented)

## Risks

1. **Manual Process:** Relies on security engineer availability and discipline
   - **Mitigation:** Guide is thorough enough for any team member to execute; consider rotating responsibility
2. **Checkov Gap:** docker-compose.yml still needs manual review
   - **Mitigation:** Checklist is comprehensive; revisit if checkov adds support or adopt alternative tool
3. **No Authentication Testing:** Guide skips auth workflows (none implemented yet)
   - **Mitigation:** v0.7.0 guide update will add authenticated scan instructions

## Future Work

1. **v0.6.1/v0.7.0:** Add Content Security Policy header (ZAP finding NEW)
2. **v0.7.0:** Update guide for authenticated scans (after implementing /admin/* auth)
3. **v0.7.0:** Pin Docker images to SHA digests (supply chain hardening)
4. **v0.7.0+:** Automate ZAP baseline scan in CI (`zap-baseline.py` on PR builds)
5. **v0.7.0+:** Implement network segmentation (frontend/backend/data networks in docker-compose)

## Related

- **SEC-1 (Bandit):** Python SAST, complements ZAP's DAST
- **SEC-2 (Checkov):** IaC scanning (Dockerfile + GitHub Actions), manual Compose review
- **SEC-3 (Zizmor):** GitHub Actions supply chain security
- **SEC-5 (#98):** Security baseline triage (will reference ZAP findings + baseline exceptions)

## Approval

**Reviewed by:** Kane  
**Status:** ✅ Approved for v0.6.0  
**PR:** #194 (targeting dev)  
**Next:** SEC-5 triage (bandit/checkov/zizmor findings → security baseline document)

---

**Document Version:** 1.0  
**Last Updated:** 2025-03-15
