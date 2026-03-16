# Squad Log — 2026-03-16 10:00 UTC

## PRs Merged
- PR #265 — feat: installer CLI with security hardening (closes #255)

## PRs Closed (Superseded)
- PR #266 — login UX (content already on dev via #265 squash)
- PR #267 — stale copilot security fix attempt

## Issues Closed
- #252 — Login UX (implemented, on dev)
- #255 — Installer CLI (merged via #265)

## Issues Created
- #269 — Integration-test GitHub Actions workflow (Brett, v0.9.0)
- #270 — Copilot-powered release-docs workflow (Brett, v0.9.0)

## Agents Spawned
- Brett → #253 nginx auth_request
- Newt → #259 v0.10.0 release docs
- Copilot → #256 compose wiring

## Decisions
- Dallas's login UX merged via installer PR squash (shared workspace artifact)
- AUTH_JWT_SECRET now uses fail-closed `${VAR:?error}` compose syntax
- COPILOT_TOKEN secret verified available for future CI workflows
