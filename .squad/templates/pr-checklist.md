# Pre-PR Self-Review Checklist (R4)

Run through this checklist before opening any PR. Copy into your PR description.

---

## Quality Gate (MANDATORY)

- [ ] Ran `.squad/scripts/verify.sh` — all checks pass
- [ ] `ruff check` + `ruff format --check` pass for all changed Python files
- [ ] `npm run lint` + `npm run format:check` pass (if aithena-ui changed)
- [ ] Tests pass for all changed services (`uv run pytest` / `npx vitest run`)
- [ ] No `--no-verify` was used on any commit

## Scope

- [ ] `git diff --stat origin/dev` shows ONLY files related to this issue
- [ ] No unrelated formatting changes, imports, or refactors included

## Security

- [ ] Security implications reviewed (auth flows, input validation, permissions)
- [ ] No secrets, credentials, or API keys in the diff
- [ ] File operations use safe patterns (streaming reads, path validation)
- [ ] No new security warnings introduced (Bandit, CodeQL)
- [ ] Input validation on new API parameters (check request bodies and query strings)

## Data Model

- [ ] Data model impact assessed (parent/chunk docs, cross-service data flows)
- [ ] Changes to Solr schema, Redis keys, or RabbitMQ messages are documented
- [ ] No breaking changes to API contracts without version bump

## Error Handling

- [ ] Error handling doesn't silently change user-visible behavior
- [ ] Any fallback/degradation has explicit Lead or PO approval (per no-degradation rule)
- [ ] Errors are logged at appropriate level (WARNING+)

## Testing

- [ ] Tests cover the specific bug/feature, not just happy path
- [ ] Edge cases and error paths have test coverage
- [ ] `uv run pytest` / `npm test` passes locally

## Branch Hygiene

- [ ] Branch was created from `origin/dev` (not local `dev` or working tree)
- [ ] No commits from other branches leaked into this PR
