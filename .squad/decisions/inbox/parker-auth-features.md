# Decision: Enhanced Password Policy and Auth Feature Patterns

**Author:** Parker (Backend Dev)
**Date:** 2026-03-19
**PR:** #576 (Closes #550, #551, #553)
**Status:** PROPOSED

## Context

Three auth features were implemented together because they share the same module surface: admin seeding, change-password, and RBAC enforcement on endpoints.

## Decisions

### 1. Password policy now requires uppercase + lowercase + digit
The `validate_password()` function was enhanced beyond simple length checks to require at least one uppercase letter, one lowercase letter, and one digit. This is a breaking change for any code creating users with weak passwords (e.g., tests).

### 2. Admin seeding is triggered inside `init_auth_db()`
Rather than adding a separate startup step, `_seed_default_admin()` runs automatically at the end of `init_auth_db()`. This ensures seeding happens exactly once when the table is created and is idempotent (skips if any users exist).

### 3. RBAC Phase 1: new endpoints only, backward compat for admin
- `/v1/upload` gets `require_role("admin", "user")` — viewers cannot upload
- `/v1/admin/*` endpoints keep X-API-Key authentication (no change)
- Search and books endpoints remain accessible to any authenticated user
- Phase 2 (future): Consider migrating admin endpoints from API-key to role-based auth

### 4. `require_role()` returns `Depends()` directly
The factory pattern `require_role("admin", "user")` already wraps the inner function in `Depends()`. Use it directly in `dependencies=[...]` lists or `Annotated[AuthenticatedUser, require_role(...)]` type hints.

## Impact

- **All team members:** Test passwords must now include uppercase, lowercase, and digit (e.g., "SecurePass123" instead of "password123")
- **Dallas (Frontend):** New endpoint `PUT /v1/auth/change-password` available for UI integration
- **Brett (Infrastructure):** New env vars `AUTH_DEFAULT_ADMIN_USERNAME` and `AUTH_DEFAULT_ADMIN_PASSWORD` for Docker Compose
