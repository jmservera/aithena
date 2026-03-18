# Decision: Dependabot PR routing rules in heartbeat

**Date:** 2026-07-24
**Decided by:** Brett (Infrastructure Architect)
**Context:** Issue #483, PR #486

## Decision

Dependabot PRs needing manual attention are auto-routed to squad members by dependency domain:

| Domain | Routes To | Matching Signal |
|---|---|---|
| Auth/crypto libs | Kane | `python-jose`, `cryptography`, `ecdsa`, `pyjwt`, `bcrypt`, `passlib` |
| CI/Docker/Actions | Brett | `.github/workflows/`, `Dockerfile`, `docker-compose`, `actions/` |
| Python backend libs | Parker | `requirements.txt`, `pyproject.toml`, `uv.lock` |
| JS/React/frontend | Dallas | `package.json`, `package-lock.json` |
| Test frameworks + CI failures | Lambert | `pytest`, `vitest`, `jest`, any PR with failing checks |

Unclassified PRs default to Brett (Infrastructure).

## Rationale

- Dependabot PRs were invisible to the squad — only `squad:*` labeled PRs were monitored
- Routing by dependency domain matches team expertise boundaries
- Stale threshold set at 7 days (matches typical Dependabot PR lifecycle)
- CI failures route to Lambert since they require test expertise regardless of dependency domain

## Impact

- All squad members may receive Dependabot PR assignments
- Routing rules live in `squad-heartbeat.yml` — update the `depRouting` array to adjust
