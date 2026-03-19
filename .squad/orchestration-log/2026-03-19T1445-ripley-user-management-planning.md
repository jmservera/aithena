# Orchestration: Ripley — User Management Module Planning

**Timestamp:** 2026-03-19T1445  
**Agent:** Ripley (Lead)  
**Task:** Design user management module for v1.9.0

## Outcome

✅ **v1.9.0 Milestone Created** + **12 Issues Generated** (#549–#560)

### Milestone Overview
- **Total Issues:** 12
- **Agents Assigned:** Parker (4), Dallas (3), Kane (2), Brett (1), Lambert (2)
- **Phases:** 5 (Foundation, Core API, Frontend, Validation, Final Gate)
- **Status:** PROPOSED (awaiting squad consensus)

### Key Decisions

#### 1. Three-Tier RBAC Model
```
viewer  → Search + view books only
user    → Search + upload (no admin panel)
admin   → Full access (search, upload, user management, admin panel)
```

#### 2. Admin API Key Phased Transition
- **v1.9.0:** RBAC on new endpoints only; X-API-Key still works for existing admin endpoints
- **v2.0.0:** Accept both RBAC + X-API-Key
- **v2.1.0+:** Remove X-API-Key

#### 3. Password Policy
- 10–128 characters
- 3 of 4 complexity categories (upper, lower, digit, special)
- No username in password (case-insensitive)
- Max length prevents Argon2 DoS

#### 4. Token Revocation Deferred
- Accept stateless JWT limitation for v1.9.0 (24h TTL acceptable)
- Implement version counter on password change in v2.0.0

#### 5. Default Admin Seeding
- Auto-create admin from `AUTH_DEFAULT_ADMIN_USERNAME` + `AUTH_DEFAULT_ADMIN_PASSWORD`
- Eliminates manual `reset_password.py` step

### Issues Breakdown

**Parker (Backend Dev) — 4 Issues**
- #549: User CRUD API endpoints (P0, Large)
- #550: Default admin user seeding (P0, Small)
- #551: Change password endpoint (P0, Small)
- #553: RBAC middleware (P0, Medium)

**Dallas (Frontend Dev) — 3 Issues**
- #554: User management page (admin) (P1, Large)
- #555: Change password form (P1, Small)
- #556: User profile page (P1, Small)

**Kane (Security Engineer) — 2 Issues**
- #552: Password policy enforcement (P0, Small)
- #560: Security review (full module) (P0, Medium)

**Brett (Infrastructure Architect) — 1 Issue**
- #557: Auth DB migration & backup (P1, Medium)

**Lambert (Tester) — 2 Issues**
- #558: Auth API integration tests (P0, Large)
- #559: RBAC access control tests (P0, Medium)

### Execution Strategy

| Phase | Sprint | Work | Status |
|-------|--------|------|--------|
| 1 — Foundation | Sprint 1 | Parker #553 + #550; Kane #552; Brett #557 (parallel) | Pending |
| 2 — Core API | Sprint 2 | Parker #549 + #551 (depends on Phase 1) | Pending |
| 3 — Frontend | Sprint 3 | Dallas #554, #555, #556; Lambert #558, #559 | Pending |
| 4 — Validation | Sprint 4 | Kane #560 (security review + fix any findings) | Pending |

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| RBAC breaks existing endpoints | Phase 1 keeps X-API-Key; RBAC only on new endpoints |
| Password policy too strict | Existing passwords not retroactively validated |
| Token revocation gap | Accepted for v1.9.0; 24h TTL adequate |
| SQLite concurrent writes | WAL mode handles; user management low-frequency |

### Deferred to v2.0.0+

- Account lockout after N failed attempts
- Email field for password reset (no email infra in on-premises)
- Audit logging of user management actions (v2.0.0 required)
- Token revocation on password change

---

## Session Log

See `.squad/log/2026-03-19T1445-user-management-planning.md`
