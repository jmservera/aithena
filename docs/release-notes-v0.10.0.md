# Aithena v0.10.0 Release Notes — Security Hardening

_Date:_ 2026-03-16  
_Prepared by:_ Newt (Product Manager)

Aithena v0.10.0 delivers the **Security Hardening** milestone. This release closes the remaining GitHub Actions and Bandit remediation work tracked under the parent security issue (#241) and strengthens the project’s release pipeline without changing runtime behavior for users.

## Summary of security hardening changes

- **Pinned all GitHub Actions to immutable SHA digests** to reduce supply-chain risk from mutable action tags.
- **Fixed the Bandit configuration** by converting `.bandit` to valid YAML and correcting rule IDs so Python SAST runs with the intended profile.
- **Reduced GitHub Actions permissions and improved secret handling** by scoping permissions per job and moving secrets into `env:` blocks instead of script contexts.
- **Disabled persisted checkout credentials** by adding `persist-credentials: false` to checkout steps so workflow tokens are not left behind in the workspace.
- **Closed the parent security tracker** after all remediation items in this milestone were completed.

## Merged pull requests

- **#243** — Pin all GitHub Actions to immutable SHA digests
- **#245** — Fix Bandit config YAML and correct test IDs
- **#247** — Fix GitHub Actions permissions and secrets-outside-env findings
- **#249** — Add `persist-credentials: false` to checkout steps

## Breaking changes

**None expected.**

This milestone hardens CI/CD and repository security posture, but it does not change public APIs, deployment topology, or application data formats.

## Upgrade instructions

1. Update to the v0.10.0 release commit or tag once it is published.
2. If you maintain a fork or custom workflows, sync the `.github/workflows/` directory so you inherit:
   - SHA-pinned action references
   - least-privilege workflow permissions
   - `persist-credentials: false` on checkout steps
3. If you maintain a custom Bandit configuration, ensure it is valid YAML and uses Bandit’s `B`-prefixed test IDs.
4. Re-run the standard validation set after upgrading:
   - `cd src/solr-search && uv run pytest -v --tb=short`
   - `cd src/aithena-ui && npx vitest run`
   - `cd src/aithena-ui && npm run lint && npm run build`
5. No application configuration changes, database migrations, or user-facing feature toggles are required for this release.
