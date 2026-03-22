---
name: "milestone-gate-review"
description: "Security, performance, and architecture review gate before milestone closure"
domain: "release-management"
confidence: "high"
source: "first enforced in v1.10.1 (13 issues reviewed, verdict APPROVE)"
author: "Ripley"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context

Before closing a milestone, all merged issues must pass a security, performance, and architecture review gate. This prevents shipping vulnerabilities, performance regressions, or architectural debt. The gate was first enforced in v1.10.1 where 13 issues were audited with a final verdict of APPROVE.

## Patterns

- **Audit every issue in the milestone** — no exceptions. Each merged PR gets a quick scan for security, performance, and architecture concerns.
- **Security checks:**
  - Scan for `# noqa: S608` (SQL injection suppression) — every instance must be justified
  - Look for dynamic SQL construction (string concatenation, f-strings in queries)
  - Check for authentication/authorization bypass paths
  - Verify input validation on all public endpoints
- **Performance checks:**
  - Flag sequential batch operations on >100 items (should be bulk/batch)
  - Check for N+1 query patterns
  - Verify Redis uses `scan_iter()` not `KEYS`, `mget()` not per-key loops
  - Look for missing pagination on list endpoints
- **Architecture checks:**
  - Verify new endpoints follow existing patterns (FastAPI conventions, Pydantic models)
  - Check that new config uses dataclass-based `config.py` with env vars
  - Ensure Docker health checks are in `docker-compose.yml`, not Dockerfiles
- **Verdict:** Issue a clear APPROVE or BLOCK with specific findings for each concern.

## Examples

```markdown
## Milestone Gate Review — v1.10.1

### Summary
- Issues reviewed: 13
- Security findings: 0 critical, 1 low (S608 suppression justified)
- Performance findings: 0 critical
- Architecture findings: 0 critical

### Verdict: APPROVE

### Issue-by-Issue Audit
| Issue | Title | Security | Performance | Architecture |
|-------|-------|----------|-------------|--------------|
| #601  | Fix folder search | ✅ | ✅ | ✅ |
| #602  | Redis connection pool | ✅ | ✅ (uses mget) | ✅ |
...
```

## Anti-Patterns

- **Don't skip the gate for "small" milestones** — even single-issue milestones get reviewed. Security bugs hide in small changes.
- **Don't rubber-stamp** — actually read the diffs. A 5-minute scan catches most red flags.
- **Don't block on style issues** — the gate is for security, performance, and architecture. Style issues should be caught in PR review, not at the milestone gate.
- **Don't ignore `# noqa` comments** — each suppression must have a documented justification. Unjustified suppressions are automatic blockers.
