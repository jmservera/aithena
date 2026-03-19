# Session Log: User Management Module Planning

**Timestamp:** 2026-03-19T1445  
**Agent:** Ripley (Lead)  
**Task:** Design user management module for v1.9.0  
**Outcome:** ✅ COMPLETE — v1.9.0 milestone + 12 issues created

---

## Background

Aithena authentication is currently basic:
- JWT tokens + Argon2 password hashing (already implemented in v0.8+)
- HTTP-only cookies (secure)
- BUT: No user lifecycle management via UI/API
  - Users created only via CLI (`reset_password.py`) or direct DB access
  - No password change from UI
  - No user listing, editing, deletion
  - No role-based access control beyond admin binary
  - No default admin auto-seeding

This sprint designs a full user management module for **v1.9.0**.

---

## Design Decisions

### 1. Three-Tier RBAC

```
┌─────────┬──────────┬────────────┬──────────────┬───────────────┐
│ Role    │ Search   │ View Books │ Upload       │ Admin Panel   │
├─────────┼──────────┼────────────┼──────────────┼───────────────┤
│ viewer  │ ✅       │ ✅         │ ❌           │ ❌            │
│ user    │ ✅       │ ✅         │ ✅           │ ❌            │
│ admin   │ ✅       │ ✅         │ ✅           │ ✅            │
└─────────┴──────────┴────────────┴──────────────┴───────────────┘
```

**Why three roles?**
- Covers known use cases: public browsing (viewer), contributors (user), sysadmin (admin)
- Simple schema: just a TEXT column `role`
- Adding roles later is data migration, not architecture change
- No over-engineering

### 2. Admin API Key Transition (Phased)

**Current:** All admin endpoints accept `X-API-Key` header

**v1.9.0 (this milestone):**
- RBAC enforced on **new** user management endpoints only
- Existing admin endpoints (docs, stats, etc.) still accept `X-API-Key`
- No breaking changes to existing deployments

**v2.0.0:**
- Migrate all admin endpoints to RBAC
- Accept **both** `X-API-Key` and JWT during transition period
- Deprecation notice in release notes

**v2.1.0+:**
- Remove `X-API-Key` support entirely
- Pure JWT + RBAC

**Why phased?**
- Operators using `X-API-Key`-based automation (scripts, cron jobs, CI/CD) need migration window
- Self-hosted apps can't force immediate updates like SaaS

### 3. Password Policy

**Constraints:**
- Minimum: 10 characters
- Maximum: 128 characters
- Complexity: 3 of 4 categories (upper, lower, digit, special)
- No username in password (case-insensitive substring check)

**Why these numbers?**
- NIST 800-63B recommends 8-char minimum with no composition rules, but we're self-hosted so we can be stricter
- "3 of 4" is reasonable security without frustrating users
- 128-char max prevents Argon2 denial-of-service on huge inputs (Argon2 performance degrades with very long passwords)
- Username check prevents `admin123!` when username is `admin`

**What about existing passwords?**
- We don't retroactively validate them
- Policy applies only to new passwords

### 4. Token Revocation: Deferred to v2.0.0

**Current limitation:**
- JWT tokens are stateless — no revocation mechanism
- Changing your password does **NOT** invalidate existing tokens (they expire naturally via TTL)

**v1.9.0:**
- Accept this limitation
- Default TTL is 24 hours (adequate for a library search tool)
- Document the limitation clearly

**v2.0.0:**
- Implement token version counter in `users` table
- Increment counter when password changes
- Validate token version in JWT middleware
- No performance penalty; just one extra DB lookup per request

**Why defer?**
- Stateless JWT is simpler, faster, and sufficient for our threat model
- Token revocation requires either:
  - Redis blocklist (adds infrastructure)
  - Version check (adds DB hit per request)
- 24-hour TTL mitigates the risk adequately

### 5. Default Admin Seeding

**On first startup** (empty users table):
- Auto-create an admin user from environment variables:
  - `AUTH_DEFAULT_ADMIN_USERNAME` (default: `admin`)
  - `AUTH_DEFAULT_ADMIN_PASSWORD` (required; no default)

**Migration script behavior:**
- Checks if `users` table is empty
- If empty AND `AUTH_DEFAULT_ADMIN_PASSWORD` is set, creates admin user
- Otherwise, skips (assume users already exist or will be created manually)

**Why this approach?**
- Eliminates the manual step of running `reset_password.py` after first deployment
- Makes containerized deployments smoother (just set env vars)
- The CLI tool (`reset_password.py`) remains for password resets

### 6. Database Schema: No Changes Needed for v1.9.0

**Current `users` table:**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

**Why no changes?**
- Already has `role` column (from v0.8 auth implementation)
- Supports three-tier RBAC natively
- No schema migration needed

**Future-proofing:**
- Add `schema_version` table for tracking migrations
- Allows v2.0.0 to add columns (e.g., `password_version`, `last_login`, `locked_until`) without guessing the current schema

---

## Feature Breakdown by Agent

### Parker (Backend Dev) — 4 Issues

| # | Title | Priority | Effort | Depends On |
|---|-------|----------|--------|-----------|
| #549 | User CRUD API endpoints | P0 | Large | #553, #552 |
| #550 | Default admin user seeding | P0 | Small | — |
| #551 | Change password endpoint | P0 | Small | #552 |
| #553 | RBAC middleware | P0 | Medium | — |

**#549 Details:**
- `POST /api/users` — create user (admin only)
- `GET /api/users` — list users (admin only)
- `GET /api/users/{id}` — get user (admin + self)
- `PUT /api/users/{id}` — update user (admin + self, limited fields)
- `DELETE /api/users/{id}` — delete user (admin only)
- Input validation: username uniqueness, password policy (via #552)

**#550 Details:**
- Startup hook: check if `users` table is empty
- If empty and `AUTH_DEFAULT_ADMIN_PASSWORD` env var is set, create admin
- Log: "Default admin created with username `admin`"

**#551 Details:**
- `POST /api/auth/change-password`
- Input: current password, new password
- Validation: password policy (#552)
- Response: JWT token (session continues)

**#553 Details:**
- Middleware that extracts JWT and checks user role
- Supports route decorators: `@require_role("admin")`, `@require_role("user")`, etc.
- Returns 403 if insufficient role

### Dallas (Frontend Dev) — 3 Issues

| # | Title | Priority | Effort | Depends On |
|---|-------|----------|--------|-----------|
| #554 | User management page (admin) | P1 | Large | #549, #553 |
| #555 | Change password form | P1 | Small | #551 |
| #556 | User profile page | P1 | Small | — |

**#554 Details:**
- Admin-only page: `/admin/users`
- Table of all users with columns: username, role, created_at
- Actions: create (modal), edit role (dropdown), delete (confirm)
- Search/filter by username

**#555 Details:**
- Modal form accessible from profile dropdown or `/change-password`
- Inputs: current password, new password, confirm password
- Validation: client-side password policy preview, server-side enforcement
- Success: redirect to dashboard

**#556 Details:**
- User profile page: `/profile`
- Show: username, role, created_at
- Actions: change password button, logout button

### Kane (Security Engineer) — 2 Issues

| # | Title | Priority | Effort | Depends On |
|---|-------|----------|--------|-----------|
| #552 | Password policy enforcement | P0 | Small | — |
| #560 | Security review (full module) | P0 | Medium | All implementation issues |

**#552 Details:**
- Implement password validator function in shared auth module
- Checks: length (10–128), complexity (3 of 4), username substring
- Returns detailed error messages
- Used by #549 (create), #551 (change password)
- Unit tests with edge cases (boundary lengths, all digits, etc.)

**#560 Details:**
- Review all RBAC middleware (#553), API endpoints (#549, #551), frontend logic (#554, #555)
- Check for: bypass vulnerabilities, token handling, credential storage
- Produce security report with findings and sign-off

### Brett (Infrastructure Architect) — 1 Issue

| # | Title | Priority | Effort | Depends On |
|---|-------|----------|--------|-----------|
| #557 | Auth DB migration & backup | P1 | Medium | — |

**#557 Details:**
- Document backup procedure for `auth.db` (schema dump, user data export)
- Create migration script that runs on container startup if needed
- Schema versioning table: `schema_version(version INT, applied_at TIMESTAMP)`
- Idempotent: safe to run multiple times

### Lambert (Tester) — 2 Issues

| # | Title | Priority | Effort | Depends On |
|---|-------|----------|--------|-----------|
| #558 | Auth API integration tests | P0 | Large | #549, #550, #551, #553 |
| #559 | RBAC access control tests | P0 | Medium | #553, #549 |

**#558 Details:**
- Test user CRUD endpoints with valid/invalid inputs
- Test default admin seeding with env vars
- Test password change with valid/invalid current password
- Test edge cases: duplicate username, password policy violations

**#559 Details:**
- Test RBAC middleware: verify 403 on insufficient role
- Test access matrix: viewer cannot upload, user cannot manage users, admin can do all
- Test role transitions: promote user→admin, demote admin→viewer

---

## Execution Plan

### Phase 1: Foundation (Parallel, Sprint 1)

**Parker starts:**
- #553: RBAC middleware (core dependency for all API work)
- #550: Default admin seeding (independent)

**Kane starts:**
- #552: Password policy enforcement (core dependency for passwords)

**Brett starts:**
- #557: DB migration & backup (independent)

**Blockers:** None (all parallel)

**Acceptance:**
- #553 passes unit tests; middleware can be imported and used in decorators
- #552 passes unit tests on edge cases; validators return detailed errors
- #550 logs "Default admin created" when triggered
- #557 includes schema_version table and migration script

### Phase 2: Core API (Depends on Phase 1, Sprint 2)

**Parker starts:**
- #549: User CRUD API endpoints (uses #553 RBAC + #552 password policy)
- #551: Change password endpoint (uses #552 password policy)

**Blockers:** Phase 1 complete

**Acceptance:**
- #549 endpoints return 403 for non-admin roles
- #551 rejects weak passwords via #552 validator
- All endpoints have OpenAPI schema (not internal: `include_in_schema=False`)

### Phase 3: Frontend (Depends on Phase 2, Sprint 3)

**Dallas starts:**
- #554: User management page (calls #549 endpoints, checks #553 RBAC state)
- #555: Change password form (calls #551 endpoint)
- #556: User profile page (independent, no API calls yet)

**Lambert starts:**
- #558: Integration tests (tests #549, #550, #551, #553 together)
- #559: RBAC tests (tests #553 + #549 access matrix)

**Blockers:** Phase 2 complete

**Acceptance:**
- #554 page only renders for admin role (check token)
- #555 form validates password policy before submission
- All tests pass with >90% code coverage

### Phase 4: Final Gate (Depends on Phase 3, Sprint 4)

**Kane starts:**
- #560: Security review (audits all work from Phases 1–3)

**Fix-up:**
- Any findings from #560 review

**Blockers:** All implementation issues complete

**Acceptance:**
- Security sign-off from Kane
- No "must-fix" vulnerabilities
- All findings tracked in milestone for v2.0.0

---

## Risks & Mitigations

### Risk 1: RBAC Breaks Existing Admin Endpoints

**Scenario:** Existing X-API-Key-based integrations break when RBAC is enforced.

**Mitigation:**
- Phase 1 design: RBAC middleware only enforced on **new** endpoints (#549, #551)
- Existing endpoints (`/admin/stats`, `/admin/docs`) keep X-API-Key
- v2.0.0 migration window allows operators to switch to JWT

**Acceptance Criteria:**
- Existing endpoints still work with X-API-Key
- No test failures in integration-test workflow

### Risk 2: Password Policy Too Strict for Existing Passwords

**Scenario:** Users with weak existing passwords can't change them because new policy rejects their old password.

**Mitigation:**
- Policy applies **only** to new passwords
- Existing passwords are NOT retroactively validated
- Users can change weak password to strong one via #551

**Acceptance Criteria:**
- Old weak passwords still authenticate
- New password must meet policy

### Risk 3: Token Revocation Gap

**Scenario:** User changes password; existing sessions remain valid until TTL expires (24h).

**Mitigation:**
- Document this limitation in release notes
- Default 24h TTL is acceptable for a library tool
- v2.0.0 implements token versioning (not critical for v1.9.0)

**Acceptance Criteria:**
- Release notes mention the limitation
- Token TTL set to 24h in config

### Risk 4: SQLite Concurrent Writes During User Management

**Scenario:** Two admins create users simultaneously; SQLite locks or corrupts.

**Mitigation:**
- SQLite WAL (Write-Ahead Logging) mode handles concurrent reads + single writer
- User management is low-frequency (not high-velocity data)
- Existing deployments already use SQLite for auth DB; no regression

**Acceptance Criteria:**
- No test failures under concurrent create/update load
- WAL mode enabled in config

---

## Open Questions for Squad Consensus

1. **Account lockout after N failed login attempts?**
   - Deferred to v2.0.0
   - Rate limiting (already in place) is sufficient for v1.9.0

2. **Email field for password reset?**
   - Deferred (no email infrastructure in on-premises deployments)
   - Self-hosted apps don't have SMTP by default

3. **Audit logging of user management actions?**
   - Nice-to-have for v1.9.0
   - Required for v2.0.0 (compliance, debugging)
   - Create separate issues if needed

4. **Two-factor authentication?**
   - Out of scope for v1.9.0
   - Defer to v2.0.0+

---

## Next Steps

1. **Squad review:** Get consensus on design decisions (RBAC model, admin API transition, password policy)
2. **Create milestone:** Add v1.9.0 to GitHub milestones
3. **Create issues:** Create 12 issues (#549–#560) and assign to agents
4. **Sprint 1 kickoff:** Parker, Kane, Brett start Phase 1 work
5. **Review gates:** Gate each phase on completion of previous phase

---

## Related Documents

- **Orchestration Log:** `.squad/orchestration-log/2026-03-19T1445-ripley-user-management-planning.md`
- **Decision (merged):** `.squad/decisions.md` (under "User Management Module (v1.9.0)")
- **Milestone:** [v1.9.0 on GitHub](https://github.com/jmservera/aithena/milestone/23)
