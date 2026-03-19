# Parker (Backend Dev) — Admin SSO Role Check Security Fix

**Timestamp:** 2026-03-19T19:55:00Z  
**Mode:** background  
**Outcome:** SUCCESS  
**PR:** #570

## Summary

Hardened cookie-based SSO path in admin dashboard (`src/admin/src/auth.py`) by enforcing admin role check.

**Issue:** Cookie SSO accepted any valid JWT, including non-admin tokens issued by main app login flow (privilege escalation vector).

**Solution:** Added explicit `user.role != 'admin'` check in `_check_cookie_auth` after JWT decode; rejects non-admin users.

**Files:**
- `/tmp/wt-570/src/admin/src/auth.py`
- `/tmp/wt-570/tests/test_auth.py`

## Impact

Non-admin users can no longer access admin dashboard via shared cookie. No breaking change for admins. Decision recorded in decisions.md.
