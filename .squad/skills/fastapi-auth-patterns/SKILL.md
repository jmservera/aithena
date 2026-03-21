---
name: "fastapi-auth-patterns"
description: "JWT authentication, cookie-based SSO, RBAC, rate limiting, and password management patterns for multi-service FastAPI applications"
domain: "authentication, authorization, security"
confidence: "high"
source: "earned — implemented auth module in solr-search, SSO with admin, fixed cookie lifecycle bugs"
author: "Parker"
created: "2026-Q2"
last_validated: "2026-03-20"
---

## Context
aithena uses a local auth system (no cloud IdP) with:
- SQLite user table in solr-search (source of truth)
- Argon2id password hashing
- JWT tokens shared across services via cookie
- nginx `auth_request` directive for gating
- Streamlit admin SSO via cookie forwarding

Mistakes can cause: infinite login loops, privilege escalation, DoS via password hashing, and broken SSO between services.

## Patterns

### 1. **JWT Cookie SSO Across Services**

For multi-service SSO without a central IdP:
```python
# solr-search sets cookie at login
response.set_cookie(
    key=settings.auth_cookie_name,  # "aithena_auth"
    value=token,
    httponly=True,
    secure=request.url.scheme == "https",
    samesite="lax",
    max_age=max_age,  # None for session cookie, seconds for persistent
)

# admin (Streamlit) reads cookie for SSO
def check_auth():
    try:
        cookie = st.context.cookies.get(AUTH_COOKIE_NAME)
        if cookie:
            payload = decode_access_token(cookie)
            if payload.get("role") == "admin":  # CRITICAL: enforce role!
                return payload
    except (AttributeError, jwt.InvalidTokenError):
        pass
    return None
```

**Critical:** Admin SSO MUST check `role == 'admin'`. Without it, any authenticated user (viewer, editor) gets admin access via the shared cookie.

**Requirements:** Both services must share `AUTH_JWT_SECRET` and `AUTH_COOKIE_NAME` env vars.

### 2. **Cookie Refresh on Validate**

```python
@app.get("/v1/auth/validate")
def validate(request: Request, response: Response):
    user = _get_current_user(request)
    if user:
        set_auth_cookie(response, user.token, request)  # REFRESH cookie
        return {"user": user.username, "role": user.role}
    raise HTTPException(status_code=401)
```

**Why:** Without refresh, the cookie expires while the JWT may still be valid. nginx `auth_request` relies on the cookie, so an expired cookie causes infinite 302 redirects even though the user is authenticated via Authorization header.

### 3. **RBAC with `require_role()` Dependency**

```python
def require_role(*allowed_roles):
    """FastAPI dependency that checks user role."""
    async def inner(request: Request):
        user = _get_current_user(request)
        if not user or user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return Depends(inner)  # Returns Depends(), not the function

# Usage in endpoint
@app.post("/v1/upload", dependencies=[require_role("admin", "user")])
def upload(file: UploadFile):
    ...
```

**Key:** `require_role()` returns `Depends(inner)`, so use it directly in `dependencies=[...]`. Do NOT wrap it again: `Depends(require_role(...))` would be double-wrapped and fail silently.

### 4. **Password Validation Before Hashing**

```python
def validate_password(password: str) -> None:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be 8-128 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain a digit")
```

**Why max length check:** Argon2 processes the entire input. A 1MB password would consume significant CPU — check length BEFORE hashing to prevent DoS.

### 5. **Rate Limiting with Redis**

```python
def check_rate_limit(ip: str, redis_client) -> bool:
    key = f"login_attempts:{ip}"
    attempts = redis_client.get(key)
    if attempts and int(attempts) >= 10:
        return False  # Rate limited
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 900)  # 15 minutes
    pipe.execute()
    return True
```

**Contract:** 10 attempts per 15 minutes per IP. Returns 429 when exceeded.

### 6. **Admin Seeding on Empty Database**

```python
def _seed_default_admin():
    from config import settings  # Lazy import to avoid circular dependency
    if settings.auth_default_admin_password:
        # Only seed if DB is empty AND env var is set
        if get_user_count() == 0:
            create_user("admin", settings.auth_default_admin_password, "admin")
```

**Why lazy import:** `auth.py` is imported by `main.py`, which also imports `config`. If `auth.py` imports `config` at module level, you get a circular import. Lazy import inside the function avoids this.

### 7. **Session vs Persistent Cookies (remember_me)**

```python
class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False

# In login handler:
max_age = settings.auth_jwt_ttl if request.remember_me else None
set_auth_cookie(response, token, request, max_age=max_age)
```

`max_age=None` creates a session cookie (deleted when browser closes). Persistent cookies use the JWT TTL.

## Testing Patterns

### Testing Frozen Config Dataclasses
```python
# Modify frozen @dataclass(frozen=True) in tests
object.__setattr__(settings, "auth_jwt_secret", "test-secret-key")
```
Cleaner than monkeypatch for dataclass instances.

### Testing Auth Endpoints
```python
def get_auth_headers(client, username="admin", password="TestPass1"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}

# In test
headers = get_auth_headers(client)
response = client.get("/v1/admin/users", headers=headers)
assert response.status_code == 200
```

### Mocking Streamlit Context for SSO Tests
```python
# Don't mutate type(MagicMock) — use a scoped stub
class StubSt:
    @property
    def context(self):
        raise AttributeError("no context in test")

with patch("auth.st", StubSt()):
    result = check_auth()
    assert result is None
```

## Anti-Patterns
- **Don't share JWT secret as default/fallback** — must be mandatory env var (security blocker)
- **Don't skip JWT exp validation** — always check expiry explicitly in decode
- **Don't use `logger.exception()` in auth error paths** — exposes internal state
- **Don't assume cookie == authenticated for admin** — always verify role claim
- **Don't wrap `require_role()` in `Depends()`** — it already returns `Depends(inner)`
- **Don't validate password after hashing** — check length/complexity BEFORE Argon2

## Scope
Applies to: solr-search (auth module), admin (SSO consumer), nginx (auth_request proxy)
Files: `src/solr-search/auth.py`, `src/solr-search/main.py`, `src/admin/src/auth.py`
