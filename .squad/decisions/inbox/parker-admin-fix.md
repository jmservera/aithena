# Decision: Admin endpoints accept JWT sessions alongside API keys

**Author:** Parker (Backend Dev)
**Date:** 2026-03-22
**Status:** IMPLEMENTED
**PR:** #895 (Closes #887)

## Context

Admin API endpoints (`/v1/admin/*`) used `require_admin_auth` which only accepted `X-API-Key` headers. The React admin dashboard sends JWT Bearer tokens, not API keys. This caused 401/403 responses that triggered the frontend's auth failure handler, creating an infinite login loop.

## Decision

`require_admin_auth` now accepts **either**:
1. `X-API-Key` header (machine-to-machine, validated against `ADMIN_API_KEY` env var)
2. JWT session with `role == "admin"` (browser access, validated by auth middleware)

If an X-API-Key is present and ADMIN_API_KEY is configured, the key is checked first. A wrong key fails immediately (no JWT fallback). If no API key is present, the JWT session is checked.

## Impact

- **Frontend (Dallas):** Admin page now works without X-API-Key. No frontend changes needed.
- **Scripts/CI:** X-API-Key flow unchanged. Existing scripts continue to work.
- **Security:** Non-admin JWT users are explicitly rejected (401). Defense-in-depth is maintained.
- **All team members:** When adding new auth gates to endpoints, always test both API-key and JWT browser paths.
