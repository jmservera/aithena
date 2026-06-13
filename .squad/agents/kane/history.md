# Kane — History

## Core Context

Kane owns security review, scanner triage, baseline exceptions, auth hardening, workflow security, and release-security sign-off.

**Current security posture:**
- CI scanners: Bandit, Checkov, zizmor, and CodeQL.
- Findings are often reported through SARIF/code scanning; green CI alone is not enough if a job soft-fails, suppresses, or emits parser warnings.
- Baseline exceptions must stay documented with rationale in code and in `docs/security/baseline-exceptions.md`.

**Auth posture:** browser flows use JWT cookies, admin access requires role checks, login is rate-limited, and password length must be bounded before Argon2 hashing.

## Key Patterns

- **Security CI must be read, not just observed.** Inspect logs for `--soft-fail`, `continue-on-error`, parser/config warnings, and downgraded findings.
- **`noqa`/`nosec` comments are documentation.** Always include rationale, not just the rule ID.
- **Exclude third-party environments from SAST.** Scanning `.venv` or vendored packages creates noise and hides real regressions.
- **Admin/API auth must layer controls.** API keys alone are not enough for browser/admin flows; combine them with JWT or role enforcement as appropriate.
- **Model-level validation is durable security.** Use Pydantic constraints (`ge`, `max_length`, etc.) so protection survives endpoint refactors.
- **Password length before hashing prevents CPU DoS.** Never let Argon2 process arbitrarily large input.
- **Strict origins matter when credentials are enabled.** `allow_credentials=true` requires tight CORS origin control.
- **Workflow security is a product feature.** Least privilege, safe secret handling, and supply-chain review are part of release quality, not optional cleanup.
- **Private ZooKeeper + enforced Solr auth changes risk.** Default Solr/ZK warnings are medium-risk posture findings, not automatic release blockers, when network exposure stays internal and HTTP auth/RBAC remains required.

## Triage Heuristic

- **CRITICAL/HIGH:** fix or document a narrowly justified mitigation and follow-up.
- **MEDIUM/LOW:** may be accepted only with clear exploitability analysis.
- **False positive:** dismiss with inline rationale and supporting docs.

## Key References

- `docs/security/README.md`
- `docs/security/owasp-zap-audit-guide.md`
- `docs/security/baseline-exceptions.md`
- `.bandit`, `.checkov.yml`, `.zizmor.yml`
- `.squad/skills/security-patterns/SKILL.md`
