# Pre-PR Self-Review Checklist (R4)

Run through this checklist before opening any PR. Copy into your PR description.

---

## Scope

- [ ] `git diff --stat origin/dev` shows ONLY files related to this issue
- [ ] No unrelated formatting changes, imports, or refactors included

## Security

- [ ] Security implications reviewed (auth flows, input validation, permissions)
- [ ] No secrets, credentials, or API keys in the diff
- [ ] File operations use safe patterns (streaming reads, path validation)

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
