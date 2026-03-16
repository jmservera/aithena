## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

---

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

### 2026-03-15 — SEC-4 Implementation Complete (OWASP ZAP Audit Guide)

**Summary:** Created comprehensive OWASP ZAP manual security audit guide (PR #194, issue #97). 30KB+ documentation covering DAST workflow and Docker Compose IaC review.

**Implementation Details:**

**Files Created:**
- `docs/security/owasp-zap-audit-guide.md` (900+ lines, 30KB)
- `docs/security/README.md` (security docs index)

**Guide Content:**
1. **Prerequisites** — ZAP installation (v2.14.0+), browser proxy config, FoxyProxy setup
2. **Environment Setup** — Local docker-compose stack startup, service health verification
3. **Proxy Configuration** — ZAP on port 8090 (avoids conflict with solr-search:8080), browser config, SSL cert install
4. **Manual Explore Phase** — 15-30 min guided crawling:
   - React UI (search form, PDF viewer, edge cases with XSS/SQLi test strings)
   - Search API (FastAPI /v1/search, /v1/documents with path traversal tests)
   - Admin endpoints (Streamlit, Solr, RabbitMQ guest/guest, Redis no auth)
   - Upload testing (malicious filenames, non-PDF files)
5. **Active Scan Configuration** — Scan policies (Default, SQL Injection, XSS, Path Traversal), custom aithena policy, scope/thread settings
6. **Scan Targets** — Complete endpoint inventory:
   - User-facing (nginx:80, aithena-ui, solr-search:8080 via nginx)
   - Admin (Streamlit:8501, Solr:8983, RabbitMQ:15672, Redis:8081)
   - Dev-only ports (10+ exposed in docker-compose.override.yml)
7. **Docker Compose IaC Review** — Manual checklist (compensates for checkov docker-compose gap):
   - Port exposure audit (identified 10+ dev-only ports, Solr 8983-8985 direct access)
   - Volume mount security (validated /source/volumes paths, read-only configs)
   - Network isolation (single default network, no segmentation — documented for v0.7.0)
   - Secrets in env vars (no hardcoded secrets in Compose, RabbitMQ/Redis defaults in app code)
   - Image pinning (identified missing tags: redis lacks explicit version, no SHA digests)
   - Container privileges (no privileged containers, no cap_add)
8. **Result Interpretation** — Severity levels (High/Medium/Low), CWE mapping (CWE-89, CWE-79, CWE-22), triage workflow, baseline exception template
9. **Reporting** — Audit report template with expected findings (missing auth, default credentials, insecure HTTP), baseline exception format

**Key Features:**
- Beginner-friendly (screenshot placeholders, step-by-step)
- Architecture-accurate (references actual nginx routes, docker-compose ports, service names)
- Documents known baseline exceptions (missing auth on /admin/*, RabbitMQ guest/guest, Redis no password)
- Provides IaC checklist covering all 7 docker-compose security categories
- Includes example audit report with finding classification, CVSS scores, mitigation steps

**Architecture Research:**
- Reviewed docker-compose.yml (production config) + docker-compose.override.yml (dev ports)
- Analyzed nginx/default.conf routing (10 proxied endpoints, no auth_basic/auth_request)
- Documented all exposed ports: nginx (80/443), direct services (8080, 8501, 8983-8985, 15672, 6379, etc.)
- Identified ZAP port conflict with solr-search:8080 → recommended ZAP on 8090

**Known Issues Documented:**
- HIGH: Missing auth on /admin/solr, /admin/rabbitmq, /admin/redis (deferred to v0.7.0, issue #98)
- HIGH: Default RabbitMQ credentials (guest/guest), Redis no auth (deferred to v0.7.0)
- MEDIUM: No Content Security Policy on React UI (NEW finding — recommend for v0.6.1/v0.7.0)
- MEDIUM: Image tags lack SHA digests (supply chain risk)
- INFO: Single default network (no frontend/backend/data segmentation)

**Outcome:**
✅ SEC-4 complete — OWASP ZAP audit guide ready for v0.6.0 release validation  
✅ PR #194 opened targeting dev (documentation only, no code changes)  
✅ Next: SEC-5 (issue #98) — triage bandit/checkov/zizmor findings, establish security baseline
### 2026-03-15 — SEC-1 Bandit Implementation Complete

**Summary:** Implemented SEC-1 (issue #88) bandit Python SAST scanning for CI. Created PR #193 targeting dev branch with complete workflow and configuration.

**Implementation Details:**
- Created `.bandit` config file with baseline skip rules:
  - S101 (pytest assert), S104 (0.0.0.0 binding), S603/S607 (subprocess in tests)
  - S105/S106/S108 (test data false positives)
  - Excludes .venv, site-packages, node_modules
- Created `.github/workflows/security-bandit.yml`:
  - Triggers on push/PR to dev and main branches
  - Installs bandit with SARIF support
  - Runs recursive scan with --exit-zero
  - Uploads SARIF to GitHub Code Scanning
  - Stores SARIF artifact (30-day retention)
  - Non-blocking (continue-on-error: true)
  - Proper permissions (security-events: write)
- Scans all Python services: document-indexer, document-lister, solr-search, admin, embeddings-server, e2e

**Key Decisions:**
- Used centralized `.bandit` config instead of command-line flags for maintainability
- Added SARIF artifact upload in addition to Code Scanning for audit trail
- Applied 7 skip rules covering 60+ pattern instances based on security spec
- Workflow follows existing CI patterns (permissions block, concurrency, Python 3.11)

**Testing:**
- Workflow syntax validated
- Branch pushed successfully
- PR #193 created targeting dev (Closes #88)

**Lessons Learned:**
- Bandit config file supports `targets` list but CLI `-r .` with exclusions is simpler
- SARIF upload requires both bandit[sarif] package and proper permissions
- continue-on-error at job level ensures non-blocking behavior


### 2026-03-15 — SEC-3 Implementation Complete (PR #192)

**Summary:** Implemented zizmor GitHub Actions supply chain security scanning workflow. Previous @copilot PR was empty/rejected; implemented from scratch as Kane per squad charter.

**Implementation Details:**

**Workflow:** `.github/workflows/security-zizmor.yml`
- **Tool:** Official `zizmorcore/zizmor-action@v0.1.1` action from GitHub Marketplace
- **Triggers:** Push/PR to dev/main, path filter: `.github/workflows/**`
- **Non-blocking:** `continue-on-error: true` prevents CI breakage during baseline tuning phase
- **SARIF Upload:** Integrated with GitHub Code Scanning via `security-events: write` permission
- **Focus:** P0 findings (template-injection, dangerous-triggers) per v0.6.0 spec

**Tool Research:**
- Zizmor has official GitHub Action (zizmorcore/zizmor-action) - preferred over pip install
- Supports SARIF output natively when `advanced-security: true` is configured
- Focuses on GitHub Actions supply chain risks: template injection, dangerous triggers, excessive permissions, unpinned dependencies
- Template injection occurs when user-controllable input (PR titles, issue bodies, commit messages) flows into `run` commands without escaping
- Dangerous triggers like `pull_request_target` run with base repo secrets/permissions but allow untrusted fork code

**Known Baseline:**
- CKV_GHA_7 (pin actions to SHA) is a Checkov finding, not zizmor - deferred to v0.7.0 audit per spec
- No zizmor-specific baseline exceptions identified yet (will triage findings in SEC-5)

**Configuration:**
- No zizmor config file created initially - allows all findings to surface for SEC-5 triage
- Zizmor supports inline ignores via comments (`# zizmor: ignore[rule-name]`) and `zizmor.yml` config for project-wide exceptions
- Will document baseline exceptions during SEC-5 triage after first scan results

**Branch/PR:**
- Branch: `squad/90-sec3-zizmor-scanning` from dev
- PR #192 targeting dev (closes #90)
- Single commit with detailed implementation notes
- Ready for review and merge

**Next:** SEC-3 complete → Awaiting SEC-1/SEC-2 completion → Kane review SEC-4/SEC-5

### 2026-03-16 — Follow-up review approvals for PRs #245, #247, #249

**Summary:** Reviewed the post-feedback commits on three security PRs and approved all three after the follow-ups addressed the previously requested corrections.

- **PR #245** — Approved after commit `3991f68` corrected the Bandit skip list from invalid `S*` IDs to valid `B*` IDs, which resolves the misconfigured baseline-exception issue raised in review.
- **PR #247** — Approved after commit `33d664b` moved secret references into named `env:` entries and continued passing them explicitly through `with: github-token`, preserving the PAT override without reintroducing the zizmor complaint.
- **PR #249** — Approved after commit `467fcda` fixed the actual `zizmor/artipacked` root cause by adding `persist-credentials: false` to the affected `actions/checkout@v4` steps across the impacted workflows.

**Outcome:** 
- Follow-up reviews submitted on all three PRs with approval from Kane (Security)
- #245 merged by Coordinator
- #247 has merge conflicts pending Copilot rebase
- #249 ready for merge approval

**Orchestration:** Session documented in `.squad/orchestration-log/2026-03-16T07-36-36Z-kane.md`

### 2026-03-17 — Stack Trace Exposure Investigation (Issue #291, Alert #104)

**Summary:** Investigated and resolved CodeQL alert #104 (py/stack-trace-exposure) in solr-search. Determined the alert was a false positive but applied defense-in-depth fix.

**Investigation Findings:**
- **Alert Location:** `src/solr-search/main.py:223` — `{"detail": detail}` in `_unauthorized_response()`
- **Data Flow:** `auth.py` raises `AuthenticationError` with exception chaining (`from exc`) → `main.py:266` catches and calls `str(exc)` → flows into JSON response
- **Root Cause Analysis:**
  - Python's `str(exc)` only returns the exception message, never the traceback
  - All `AuthenticationError` messages are hardcoded ("Invalid authentication token", "Token expired")
  - FastAPI is not in debug mode (no automatic stack trace exposure)
  - No custom exception handlers that might leak stack traces
  - **Conclusion: False positive** — no actual information exposure

**Why CodeQL Flagged This:**
- Exception chaining (`from exc`) creates `__cause__` and `__context__` attributes
- CodeQL's conservative data flow analysis flags any exception-to-string conversion that might flow to user responses
- Even though `str(exc)` is safe, the scanner can't guarantee custom `__str__` implementations won't leak

**Defense-in-Depth Fix Applied:**
- Removed exception chaining (`from exc`) at three sites in `auth.py`:
  - JWT decoding: `ExpiredSignatureError` → `TokenExpiredError`
  - JWT decoding: `JWTError` → `AuthenticationError`
  - Payload validation: `KeyError/TypeError/ValueError` → `AuthenticationError`
- Exception messages remain identical (no functional change)
- All 144 solr-search tests pass
- Eliminates theoretical attack surface

**Rationale for Fix Despite False Positive:**
1. CodeQL's flagging indicates a potential risk area worth hardening
2. Exception chaining is unnecessary here (user messages are already clear)
3. Removing the chain improves code clarity (no hidden internal exception context)
4. Satisfies the security scanner and prevents future confusion

**PR:** #308 (squad/291-stack-trace-exposure → dev)  
**Testing:** All 144 solr-search tests pass (auth, integration, upload)  
**Security Impact:** Reduces theoretical information exposure risk with zero functional impact

### 2026-03-16 — Security review of PR #263 (local auth module)

**Summary:** Performed an auth-focused security review of PR #263 (`feat: add local auth module with JWT and SQLite user store`) covering `solr-search/auth.py`, `config.py`, `main.py`, auth tests/helpers, and dependency changes. I could not file a formal `CHANGES_REQUESTED` review because the authenticated GitHub account is the PR author, so I posted the blockers as a PR comment instead.

**Blocking findings:**
- `solr-search/config.py:99` falls back to the hardcoded JWT secret `development-only-change-me`. I also verified `docker-compose.yml` does not set `AUTH_JWT_SECRET` for `solr-search`, so the default deployment path would accept attacker-forged HS256 tokens unless startup fails closed.
- `solr-search/auth.py:153-171` does not require an `exp` claim when decoding JWTs. I reproduced this locally by signing a token with only `sub`, `user_id`, `role`, and `iat`; `decode_access_token()` accepted it, proving expiration is not strictly enforced.
- `solr-search/main.py:263-268` exposes a public Argon2-backed login endpoint with no brute-force/rate-limit control, despite the same module already implementing upload throttling. This leaves the auth surface open to online password guessing and CPU exhaustion.

**Validated positives:**
- Argon2 uses `Type.ID` with library-managed salts (`time_cost=3`, `memory_cost=65536`, `parallelism=4`).
- SQLite queries in the auth path are parameterized.
- Cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` on HTTPS requests.
- Bearer and cookie token paths both flow through the same JWT decoder.

**Verification:**
- Ran `solr-search` auth-related tests locally: `tests/test_auth.py`, `tests/test_admin_documents.py`, `tests/test_integration.py`, and `tests/test_upload.py` → **99 passed**.
- Posted blocker comment on PR #263: `https://github.com/jmservera/aithena/pull/263#issuecomment-4065855357`.

### 2026-03-16 — Follow-up Approval: PR #263 (local auth module, all blockers resolved)

**Status:** ✅ All blockers fixed and verified  
**PR:** #263 (solr-search local auth implementation)  

**Blocker resolutions:**
1. **JWT secret fallback** → Environment variable now mandatory; raises `ConfigurationError` if missing/empty. Verified with missing env test.
2. **Exp claim not enforced** → Added explicit `exp` claim check in JWT decode pipeline. Verified: token after expiry rejects with `TokenExpiredError`.
3. **No login rate limiting** → Implemented Redis-backed rate limiter (10 attempts / 15 min per IP). Verified: 11th attempt triggers 429.

**Sign-off:** ✅ **APPROVED** for merge to `dev`

**Documentation:** Orchestration log recorded in `.squad/orchestration-log/2026-03-16_08-19-32-kane-auth-review.md`
