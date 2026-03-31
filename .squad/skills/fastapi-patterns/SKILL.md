---
name: "fastapi-patterns"
description: "FastAPI authentication, authorization, query parameter handling, and API design patterns"
domain: "authentication, authorization, api-design"
confidence: "high"
source: "consolidated from fastapi-auth-patterns, fastapi-query-params"
author: "Ripley"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Apply when building or reviewing FastAPI endpoints in aithena, particularly for authentication, authorization, cookie management, and query parameter handling. Covers the local auth system (SQLite + Argon2id + JWT + nginx).

## Pattern 1: JWT Cookie SSO Across Services

```python
# solr-search sets cookie at login
response.set_cookie(
    key=settings.auth_cookie_name,  # "aithena_auth"
    value=token,
    httponly=True,
    secure=request.url.scheme == "https",
    samesite="lax",
    max_age=max_age,  # None for session cookie
)

# admin (Streamlit) reads cookie for SSO — MUST check role
def check_auth():
    cookie = st.context.cookies.get(AUTH_COOKIE_NAME)
    if cookie:
        payload = decode_access_token(cookie)
        if payload.get("role") == "admin":  # CRITICAL
            return payload
    return None
```

**Requirements:** Both services share `AUTH_JWT_SECRET` and `AUTH_COOKIE_NAME` env vars.

## Pattern 2: Cookie Refresh on Validate

```python
@app.get("/v1/auth/validate")
def validate(request: Request, response: Response):
    user = _get_current_user(request)
    if user:
        set_auth_cookie(response, user.token, request)  # REFRESH
        return {"user": user.username, "role": user.role}
    raise HTTPException(status_code=401)
```

Without refresh, expired cookies cause infinite 302 redirects via nginx `auth_request`.

## Pattern 3: RBAC with `require_role()`

```python
def require_role(*allowed_roles):
    async def inner(request: Request):
        user = _get_current_user(request)
        if not user or user.role not in allowed_roles:
            raise HTTPException(status_code=403)
        return user
    return Depends(inner)  # Returns Depends(), not the function

# Usage — do NOT wrap in Depends() again
@app.post("/v1/upload", dependencies=[require_role("admin", "user")])
def upload(file: UploadFile): ...
```

## Pattern 4: Password Safety

- **Validate BEFORE hashing:** Check length (8–128 chars), uppercase, lowercase, digit
- **Max length check prevents DoS:** Argon2 processes entire input; 1MB password consumes significant CPU
- **Rate limiting:** 10 attempts per 15 minutes per IP via Redis (`login_attempts:{ip}`)

## Pattern 5: Query Parameter Declaration

**FastAPI silently ignores undeclared query parameters.** Unlike Flask/Express, you must explicitly declare them.

```python
# BUG: fq_folder silently dropped — not in signature
@app.get("/search")
async def search(q: str):
    ...  # /search?q=hello&fq_folder=books → fq_folder LOST

# FIX: explicitly declare
@app.get("/search")
async def search(q: str, fq_folder: str | None = None):
    ...  # fq_folder = "books"
```

**Use `Query()` for validation:**
```python
from fastapi import Query

@app.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    fq_folder: str | None = Query(None, description="Folder filter"),
): ...
```

**For dynamic parameters:** Use `request.query_params`:
```python
@app.get("/search")
async def search(request: Request):
    all_params = dict(request.query_params)
```

## Pattern 6: Testing Auth

```python
# Modify frozen config dataclass in tests
object.__setattr__(settings, "auth_jwt_secret", "test-secret-key")

# Get auth headers helper
def get_auth_headers(client, username="admin", password="TestPass1"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['token']}"}
```

## Anti-Patterns

- ❌ **Don't share JWT secret as default/fallback** — mandatory env var
- ❌ **Don't skip JWT exp validation** — always check expiry in decode
- ❌ **Don't use `logger.exception()` in auth error paths** — exposes internal state
- ❌ **Don't assume cookie == authenticated for admin** — verify role claim
- ❌ **Don't wrap `require_role()` in `Depends()`** — already returns `Depends(inner)`
- ❌ **Don't validate password after hashing** — check length/complexity BEFORE Argon2
- ❌ **Don't assume query params are automatically available** — FastAPI requires explicit declaration
- ❌ **Don't add frontend params without updating backend** — 200 OK but silently ignored
- ❌ **Don't use `**kwargs` for query params** — FastAPI doesn't support it; use `request.query_params`

## References

- `src/solr-search/auth.py`, `src/solr-search/main.py`
- `src/admin/src/auth.py`
- Issue #656 (fq_folder bug)
- v1.10.1 auth hardening
