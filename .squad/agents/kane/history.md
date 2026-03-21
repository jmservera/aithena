# Kane — History

## Core Context

**Role:** Security Engineer — SAST scanning, supply chain security, baseline exceptions, auth review

**Expertise:** Bandit (Python SAST), Checkov (IaC), zizmor (Actions supply chain), OWASP ZAP (DAST), JWT auth review, dependency triage

**Current Blockers:** None

### Security Posture (as of v1.10.0)

**CI Scanners (all non-blocking, SARIF → GitHub Code Scanning):**
- Bandit: Python SAST with `.bandit` config, 7 baseline skip rules (B101, B104, B603, B607, B105, B106, B108)
- Checkov: Dockerfile + GitHub Actions scanning (docker-compose needs manual review — checkov limitation)
- Zizmor: GitHub Actions supply chain (template-injection, dangerous-triggers, secrets-outside-env)
- CodeQL: JS/TS + Python (pre-existing)

**Baseline Exceptions (documented in `docs/security/baseline-exceptions.md`):**
- Legitimate: pytest assert (B101), 0.0.0.0 in containers (B104), subprocess in tests (B603/B607)
- ecdsa CVE-2024-23342: No fix exists; runtime uses pyca/cryptography backend (OpenSSL), not pure-Python ecdsa. Deferred: python-jose → PyJWT migration
- noqa comments document each suppression with rationale for future reviewers

**Known Gaps (tracked, deferred):**
- Network segmentation: single Docker network (all services reachable from any container)
- TLS for inter-service (RabbitMQ AMQP, Redis) — deferred to v2.0
- CSP header on React UI — non-trivial with Vite HMR in dev

**Auth System (implemented, reviewed, approved):**
- JWT cookie SSO across solr-search ↔ admin (shared secret, HttpOnly/SameSite/Secure cookies)
- Argon2id hashing with pre-hash length validation (8-128 chars, prevents DoS)
- Redis-backed rate limiting: 10 attempts/15 min per IP on login
- RBAC via `require_role()` FastAPI dependency (admin role enforced on admin SSO)
- JWT secret is mandatory env var (no fallback); `exp` claim strictly enforced

### Triage Criteria

| Severity | Action |
|----------|--------|
| CRITICAL/HIGH | Must fix or documented baseline exception with mitigation |
| MEDIUM/LOW | Baseline exception acceptable if low exploitability |
| False positive | Dismiss with noqa + inline rationale comment |

### Key Docs
- `docs/security/owasp-zap-audit-guide.md` — DAST guide with Docker Compose IaC checklist
- `docs/security/baseline-exceptions.md` — CVE exceptions with risk assessments
- `docs/security/README.md` — Security docs index
- `.bandit`, `.checkov.yml`, `.zizmor.yml` — Scanner configs

---

## Completed Work (Summary)

### v0.6.0: Security Scanning Infrastructure
- SEC-1 (PR #193): Bandit CI workflow with centralized `.bandit` config
- SEC-2 (PR #245): Checkov Dockerfile + Actions scanning
- SEC-3 (PR #192): Zizmor supply chain scanning (official `zizmorcore/zizmor-action@v0.1.1`)
- SEC-4 (PR #194): OWASP ZAP audit guide (900+ lines) with IaC review checklist
- SEC-5 (#98): Full triage of bandit/checkov/zizmor findings

### v1.0.1: Auth & Vulnerability Triage
- PR #263 review: Found 3 blockers in auth module (hardcoded JWT secret fallback, missing exp enforcement, no rate limiting) — all fixed before approval
- PR #308: Stack trace exposure false positive — applied defense-in-depth fix (removed exception chaining)
- PR #309: ecdsa CVE-2024-23342 baseline exception with risk assessment
- PR #313: Triaged 4 false-positive bandit/ruff alerts with noqa + documentation
- Full 10-alert triage for release gate: 7 stale (already fixed), 3 acceptable risk → **APPROVED**

### v1.7.1+: STRIDE Threat Assessment
- 23 vulnerabilities identified (5 critical, 5 high, 9 medium, 4 low)
- Critical findings: unprotected admin endpoints, nginx 1.15 EOL, default credentials, missing CSP
- Produced prioritized roadmap: v1.7.1 blockers → v1.8.0 hardening → v1.9.0+ defense-in-depth

### v1.10.0: Collections & Metadata Security
- PR #722: 67 security tests, found 4 vulnerabilities (missing JWT role check on metadata edit, negative position, unbounded reorder, missing max_length)
- Confirmed: parameterized SQL, cross-user isolation, Solr query escaping, safe Redis key construction

### Workflow Security Reviews
- PRs #245, #247, #249: Approved after corrections (Bandit B-IDs, secret handling, persist-credentials: false)
- PR #419: Blocked Dependabot auto-merge (2 real findings: secrets-outside-env, overly broad permissions)
- PR #419 follow-up: Verified fixes, baselined bot-conditions in `.zizmor.yml`, found impostor commit SHA

---

## Learnings (Distilled)

1. **Exclude .venv/site-packages** from Bandit scans — generates third-party false positives
2. **Checkov can't scan docker-compose** — use manual IaC checklist (in OWASP ZAP guide)
3. **Stale Code Scanning alerts** are common post-fix — re-scan or push commit to close them
4. **Exception chaining (`from exc`) is safe** but remove it when CodeQL flags it (defense-in-depth, zero cost)
5. **noqa comments ARE documentation** — always include rationale, not just the rule ID
6. **python-jose always installs ecdsa** even with cryptography backend — known design issue, mitigate by verifying runtime backend
7. **Zizmor secrets-outside-env** flags step-level env without deployment environments — step-level env IS secure, deployment environments are optional defense-in-depth
8. **API key auth alone is insufficient** for admin endpoints — always combine with JWT role verification
9. **Pydantic Field constraints** (ge, max_length) are model-level defense that persists across refactors — validate at model first, then runtime
10. **Password length BEFORE hashing** — Argon2 processes full input, 1MB password = CPU DoS
11. **CORS allow_credentials=true** needs strict origin validation — misconfigured browser + malicious origin = CSRF risk

## Reskill Notes

**Self-assessment:** Strong coverage of SAST tooling, auth review, and CI security patterns. Skills `fastapi-auth-patterns`, `ci-workflow-security`, `logging-security`, `workflow-secrets-security` already capture most reusable patterns. Gap: no skill for security scanning baseline configuration and triage workflow — extracted as new skill.

**Knowledge rating:** 85% — deep on auth, scanning infrastructure, and triage. Gaps remain in runtime DAST (ZAP guide exists but no automated integration) and container image CVE scanning (trivy/grype not yet integrated).

**Compression:** 678 → ~120 lines. Removed verbose PR narratives, duplicate SEC descriptions, full code snippets (covered by skills), and investigation blow-by-blow details. Retained all security decisions, posture state, and distilled learnings.
