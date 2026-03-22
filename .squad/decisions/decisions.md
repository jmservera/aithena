# Squad Decisions

## Decision: Disable ZooKeeper AdminServer across all environments

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**PR:** #928 (Closes #913)

### Context
ZooKeeper AdminServer exposes cluster topology and operational commands via port 8080, creating unnecessary security risk. Not required for SolrCloud operations.

### Decision
ZooKeeper AdminServer disabled via `ZOO_CFG_EXTRA: "admin.enableServer=false"` on all 3 ZK nodes in both docker-compose.yml and docker-compose.prod.yml. Port 8080 expose and host mapping removed.

### Rationale
- Security hardening — reduces attack surface
- No operational impact — SolrCloud doesn't depend on AdminServer
- Consistent across all environments (dev, staging, prod)

---

## Decision: Non-Root Container Standard

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**PR:** #930 (Closes #912)
**References:** D-2 security finding from infrastructure audit

### Context
All custom Dockerfiles must follow container security best practices by running as non-root users. Reduces attack surface significantly.

### Decision
All custom Dockerfiles must implement non-root users with standardized patterns:

#### Alpine Linux Pattern
```dockerfile
RUN addgroup -S -g 1000 app && \
    adduser -S -u 1000 -G app app
USER app
```

#### Debian-based Pattern
```dockerfile
RUN groupadd --system --gid 1000 app && \
    useradd --system --uid 1000 --gid app --create-home app
USER app
```

#### Special Cases
- **nginx:** Use built-in `nginx` user with non-privileged port (8080)
- **Solr-search:** `gosu` pattern acceptable when bind-mount ownership must be fixed at runtime

### Services Updated
- document-indexer (Alpine)
- document-lister (Alpine)
- aithena-ui (Debian-based)
- solr-search (already using gosu)

### Rationale
- Container security hardening per D-2 audit finding
- UID 1000 chosen as standard for consistency across containers
- Reduces privilege escalation attack surface
- Supports bind-mount permission patterns (Solr: 8983, Redis: 999, RabbitMQ: 100, nginx: 101)

---

## Decision: HSTS and Security Headers for nginx TLS

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**PR:** #932 (Closes #917)
**References:** Infrastructure security audit findings

### Context
nginx reverse proxy needs to harden TLS configuration and response headers to prevent SSL stripping attacks and enforce secure browser behavior.

### Decision
Implemented security headers via new `ssl.conf.template`:

#### HTTPS Server Block (TLS 1.2/1.3)
- Strict-Transport-Security (HSTS): `max-age=31536000; includeSubDomains` (1 year)
- X-Content-Type-Options: `nosniff`
- X-Frame-Options: `DENY`
- Referrer-Policy: `strict-origin-when-cross-origin`
- Server-tokens: `off` (hide nginx version)

#### Critical Implementation Details
- **HSTS only over HTTPS:** Separate HTTP server block (no HSTS header)
- **Location block re-declaration:** All location blocks that use `add_header` must re-declare security headers to prevent nginx server-level suppression
- **Required:** NGINX_HOST environment variable when using SSL overlay

### Services Updated
- nginx reverse proxy (all HTTPS traffic)
- All location blocks hardened

### Rationale
- Prevents SSL stripping attacks (HSTS enforcement)
- Hardens browser security policies (X-Content-Type-Options, X-Frame-Options)
- Hides infrastructure details (server_tokens off)
- Prevents referrer data leakage (Referrer-Policy)

---

## Decision: v1.12.1 Release Shipped

**Author:** Newt (Product Manager)  
**Date:** 2026-03-22  
**Status:** SHIPPED  
**PRs:** #927 (version bump) + #929 (dev→main release merge)
**GitHub Release:** v1.12.1 published

### Context
v1.12.1 consolidates all work since v1.11.0 into a single release point.

### Release Scope
- **v1.12.0 issues (11):** A/B embedding infrastructure
- **v1.12.1 issues (7):** Bug fixes and polish
- **Total:** 18 issues resolved

### Changes
- VERSION file bumped to 1.12.1
- CHANGELOG.md updated with all issue descriptions and release notes
- Git tag `v1.12.1` created on main branch
- GitHub Release page published with feature guide and test report

### Process Notes
- Branch protection on dev requires PRs even for version bump commits
- Integration tests in CI may be flaky (embeddings-server health check has intermittent timing issues)
- Main branch merges may need admin override due to branch protection
- Release documentation (feature guide, test report) required before release merge

---

## Directive: v1.14.0 Gated on Embeddings Evaluation Results

**Author:** Juanma (Product Owner, via Copilot)  
**Date:** 2026-03-22T16:35Z  
**Status:** ACTIVE  
**Milestones:** v1.12.2 created for evaluation (#34), v1.14.0 awaits results

### Context
v1.14.0 (A/B Testing Evaluation UI) was planned to help users choose between embedding models. However, the new e5-base model may render this unnecessary.

### Directive
v1.14.0 is **ON HOLD** pending embeddings evaluation results.

#### Conditional Outcomes

**If new e5-base model benchmarks show negligible performance loss vs baseline:**
- Skip v1.14.0 entirely
- Migrate directly to new e5-base model in a smaller patch release
- Rationale: Unnecessary UI if model quality is clearly better

**If evaluation shows significant quality differences:**
- Proceed with v1.14.0 A/B Testing Evaluation UI
- Rationale: Differences require human judgment to select best model

### Related Issues
- #926: Embeddings benchmark (in progress under v1.12.2 milestone)
- #34: v1.12.2 milestone for evaluation work

### Rationale
- Avoids building unnecessary UI if technical decision is clear
- Preserves engineering resources for higher-impact work
- User-driven prioritization based on actual benchmark results

---

## Decision: Security Re-Review — ZooKeeper SASL DIGEST-MD5 Implementation

**Reviewer:** Kane (Security Engineer)  
**Date:** 2026-03-22  
**Commit:** 891df48  
**Branch:** squad/904-zk-sasl-clean  
**Status:** APPROVED ✅  
**PR:** #955 (Closes #904)

### Context
ZooKeeper SASL DIGEST-MD5 authentication implementation (Issue #904) underwent initial review and found 5 security findings (1 CRITICAL, 4 MEDIUM). The team remediated all findings. This is the post-remediation re-review.

### Original Findings — All Remediated

1. **Shell Injection via Unquoted sed Substitution (CRITICAL)** → Fixed via `printf` replacement with safe format specifiers
2. **World-Readable JAAS Config Files (CRITICAL)** → Fixed via explicit `chmod 600` immediately after generation
3. **solr-init Inline sed Injection (CRITICAL)** → Fixed via injection-safe `printf` in both compose files
4. **Redundant JVM Flag (MEDIUM)** → Fixed via removal of duplicate `requireClientAuthScheme=sasl` from `SERVER_JVMFLAGS`
5. **Dev Default Password Allowed in Prod (MEDIUM)** → Fixed via mandatory validation using `${VAR:?error message}` syntax in production compose

### New Security Assessment

- **Entrypoint Scripts:** Reviewed for additional vulnerabilities. Both use `set -euo pipefail` for strict error handling and `: "${VAR:?error message}"` for variable validation. No injection points identified.
- **JAAS Template Files:** Both files marked "DOCUMENTATION ONLY" — safe, serve as reference only. Runtime generation eliminates stale template risks.
- **Compose Configuration:** No new vulnerabilities. Services use read-only mounts, minimal port exposure, and health checks.

### Verdict
**✅ APPROVED** — All 5 findings comprehensively remediated. Implementation demonstrates industry best practices (injection-safe string handling, principle of least privilege, fail-secure defaults, defense in depth). Recommended for merge to dev and next release.

### Notes for Future
- Team's choice to eliminate template files in favor of runtime generation is superior (prevents stale templates).
- Consider documenting JAAS structure in markdown instead of `.conf` templates to avoid confusion.
- Add integration test verifying SASL authentication actually works (not just service startup).

---

## Process Notes

- Decisions are recorded by the Scribe (silent archive, no user communication)
- When decisions.md exceeds 20KB, old entries are archived to decisions-archive.md
- All PRs reference the issues they close (e.g., "Closes #912")
- All decisions include context, decision, and rationale sections
