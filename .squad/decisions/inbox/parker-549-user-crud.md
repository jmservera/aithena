# Decision: User CRUD API Pattern (Issue #549)

**Author:** Parker (Backend Dev)
**Date:** 2026-03-19
**PR:** #572

## Context
Implemented the 4 User Management API endpoints as the v1.9.0 critical-path foundation.

## Decisions Made

### 1. `require_role()` as reusable FastAPI dependency
- Returns `Depends(inner_function)` so it can be used directly in `Annotated[AuthenticatedUser, require_role("admin")]`
- Centralizes role checking — all future admin-only endpoints should use this pattern
- Lives in `main.py` alongside the other auth helpers (`_get_current_user`, `_authenticate_request`)

### 2. Password policy enforcement in auth.py
- 8 char minimum, 128 char maximum — enforced in `validate_password()` before Argon2 hashing
- Max-length check prevents DoS via oversized inputs to Argon2
- Policy lives in auth.py constants (`MIN_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH`) for single source of truth

### 3. Custom exception types for auth errors
- `UserExistsError(ValueError)` — for duplicate username on create/update
- `PasswordPolicyError(ValueError)` — for password validation failures
- Endpoints catch these and translate to appropriate HTTP status codes (409, 422)

### 4. PUT /v1/auth/users/{id} authorization model
- Admin: can update any user's username and role
- Non-admin: can update ONLY their own username, cannot change role
- This allows self-service username changes while preventing privilege escalation

### 5. Self-delete prevention
- Admin cannot delete their own account via DELETE /v1/auth/users/{id}
- Prevents last-admin lockout scenario
- Simple check: `admin_user.id == user_id` → 400 Bad Request

## Impact on Other Issues
This unblocks all 8 dependent issues in v1.9.0 milestone. The `require_role()` dependency and auth CRUD functions are ready for reuse.
