---
name: "release-gate"
description: "Release validation checklist and PM gate for dev→main merges"
domain: "release, quality"
confidence: "medium"
source: "extracted from newt charter during reskill audit"
author: "Ripley"
created: "2026-03-15"
last_validated: "2026-03-15"
---

## Context

Apply before any release: merge dev→main, version tag, or release notes publication.
Newt (PM) is the release gate owner — no release without Newt's explicit approval.

## Release Checklist (ALL must pass)

1. ✅ Milestone clear (0 open issues — check both label AND milestone)
2. ✅ All tests pass (frontend + backend)
3. ✅ Frontend builds clean
4. ✅ Feature documentation created (`docs/features/vX.Y.Z.md`)
5. ✅ User manual updated with new features
6. ✅ Admin manual updated if infra changed
7. ✅ Test report updated
8. ✅ README feature list current

## Tools

- Playwright MCP or browser tools for screenshots
- `docker compose up` for local stack validation (if Docker available)
- `gh release` for release management

## Anti-Patterns

- Don't skip the docs gate — missing docs is a release blocker, same as failing tests
- Don't merge dev→main without Newt's sign-off, even if CI is green
- Don't approve a release with open issues in the milestone
