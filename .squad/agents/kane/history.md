# Kane — History

## Core Context

Kane owns security review, scanner posture, auth hardening, baseline exceptions, and release security triage.

- Core scanners: Bandit (Python SAST), Checkov (IaC / Docker / Actions posture), zizmor (Actions supply chain), CodeQL, and OWASP ZAP guidance.
- Current auth baseline: mandatory JWT secret, Argon2id with pre-hash length validation, Redis-backed login rate limiting, RBAC via `require_role()`, and shared JWT cookie SSO between `solr-search` and admin.
- Baseline exceptions must stay documented with rationale; low exploitability findings may be accepted only with mitigation/context.
- Security CI being green is necessary but not sufficient; inspect warnings, soft-fails, and `continue-on-error` behavior.

## Active Patterns

- Exclude third-party envs/site-packages from Bandit scans to avoid noisy findings.
- Treat `noqa` / `nosec` comments as security documentation, not just suppression toggles.
- API-key-only admin auth is insufficient; browser/admin paths still need JWT role checks.
- Model/schema/input constraints are durable defenses: validate length/range at the model boundary first.

## Recent Learnings

### 2026-06-07T18:32:36+00:00 — Security alert triage
- Updated `solr-search` lockfiles to address high `urllib3` and medium `starlette` alerts.
- `transformers` remains accepted risk for now because the patched line is still release-candidate/transitive relative to `sentence-transformers`.
- Cleared the low-severity zizmor `artipacked` CodeQL alert by setting `persist-credentials: false` in CodeQL checkout.

### 2026-06-06T22:00:15.185+00:00 — PR #1712 / #1711 / #1710 review
- No PR-blocking security issue was found in the quantization, benchmark, or Phase 2 validation diffs.
- Follow-up hardening remains: Bandit config parsing must stay clean, Checkov soft-fails should be tracked honestly, and zizmor low-severity notes are backlog items unless exploitability changes.

### 2026-03-24 — Internal service authentication assessment
- Production Compose isolation can justify thinner internal auth for non-exposed Redis/ZooKeeper, but Solr BasicAuth remains the thin compliance/security layer.
- Any simplification must preserve the no-external-port assumption and document compensating controls.

### 2026-03-22 — Threat-assessment release gate
- Comprehensive threat assessment became a mandatory release-gate artifact.
- Security fixes and review are expected in every release cycle, not only major versions.
