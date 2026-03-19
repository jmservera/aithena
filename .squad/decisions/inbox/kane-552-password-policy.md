# Decision: Password Policy Module Design

**Author:** Kane (Security Engineer)  
**Date:** 2026-03-19  
**PR:** #574 (Closes #552)  
**Status:** PROPOSED

## Context

v1.9.0 user management needs password validation beyond the basic 8-char length check in the User CRUD PR (#572). Issue #552 defines the required policy.

## Decision

Created a standalone `password_policy.py` module with a single public function:

```python
validate_password(password: str, username: str) -> list[str]
```

Returns a list of violation messages (empty = valid). This list-based return enables the API to send all violations at once (422 response) rather than failing on the first one.

**Policy defaults (v1.9.0, hardcoded):**
- Min length: 10 characters
- Max length: 128 characters (Argon2 DoS protection)
- Complexity: at least 3 of 4 categories (uppercase, lowercase, digit, special)
- No username in password (case-insensitive substring match)

## Design Rationale

1. **Standalone module** — no dependency on auth.py. Any endpoint (register, change-password, reset-password CLI) can import it independently.
2. **List return vs. exception** — returning violations as a list lets the caller decide whether to raise, log, or aggregate. The CRUD PR's `PasswordPolicyError` exception can still be used by wrapping the list check.
3. **Unicode as special** — non-ASCII characters (`[^A-Za-z0-9]`) count as "special". This is the secure default — it broadens the character space and avoids locale-dependent regex behavior.
4. **Hardcoded constants** — configurable policy deferred to a future release. Constants are module-level for easy access from tests and future config loading.

## Integration Path

The User CRUD PR (#572) should:
1. Import `validate_password` from `password_policy`
2. Replace the existing `validate_password` in auth.py
3. Call it in `create_user()` and pass violations to `PasswordPolicyError`
4. Return 422 with the violation list

## Impact

- **Parker (Backend):** Integration needed in User CRUD PR #572 — replace auth.py's basic check with this module.
- **Dallas (Frontend):** API will return a list of violation strings in 422 responses — display them to the user.
- **All:** Password minimum increased from 8 to 10 characters. Existing users are not affected until they change their password.
