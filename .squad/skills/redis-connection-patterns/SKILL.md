---
name: "redis-connection-patterns"
description: "Proper Redis authentication, connection pooling, and batch operations for multi-worker FastAPI services"
domain: "redis, caching, state management"
confidence: "high"
source: "earned — critical bug fix in solr-search, audit of all backends, tested in production"
---

## Context
Redis is used in aithena for:
- Document indexing state (processed/failed counts)
- Rate limiting (login attempts per IP)
- Caching (search results, embeddings)
- Session state (optional, for future auth)

Multi-worker FastAPI services (solr-search runs with uvicorn workers) require thread-safe connection management. Mistakes can cause:
- Silent authentication failures (502 errors on /stats and /search)
- Lost rate limiting (attacks possible)
- Memory leaks (unclosed connections)
- Cascading failures (Solr health check fails when Redis fails)

## Patterns

### 1. **ConnectionPool Must Include Password Parameter**

❌ **CRITICAL BUG** — password was missing:
```python
# OLD CODE (solr-search main.py:854)
pool = redis_lib.ConnectionPool(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    # BUG: password=settings.redis_password NOT included!
)
```

✅ **FIXED** — password must be passed to ConnectionPool:
```python
pool = redis_lib.ConnectionPool(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    password=settings.redis_password,  # REQUIRED when REDIS_PASSWORD is set
)
```

**Why:** The ConnectionPool constructor creates all connections in the pool with the specified parameters. Passing password to `Redis(pool=pool)` is not enough — the pool itself must know about the password.

### 2. **Singleton ConnectionPool with Double-Checked Locking**

For thread-safe, lazy-initialized connection pool:
```python
_redis_pool = None
_pool_lock = threading.Lock()

def _get_redis_pool():
    global _redis_pool
    if _redis_pool is None:
        with _pool_lock:
            if _redis_pool is None:
                _redis_pool = redis_lib.ConnectionPool(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password,
                    decode_responses=True,
                )
    return _redis_pool

def get_redis():
    return redis_lib.Redis(connection_pool=_get_redis_pool())
```

**Why:** Double-checked locking avoids lock contention after initialization. All FastAPI workers share the same pool and its connections.

### 3. **Use `scan_iter()` Instead of `KEYS`**

❌ **Bad** — blocks Redis server:
```python
all_keys = redis.keys("*")  # BLOCKS if many keys exist
```

✅ **Good** — iterates in batches:
```python
for key in redis.scan_iter(match="*", count=100):
    # process key
```

**Why:** `KEYS` is O(N) and blocks the entire server until complete. `scan_iter()` uses SCAN cursor-based iteration (non-blocking, batches of ~100 keys).

### 4. **Use `mget()` for Batch Reads**

❌ **Bad** — N round-trips to Redis:
```python
values = {}
for key in keys:
    values[key] = redis.get(key)  # N network round-trips
```

✅ **Good** — single batch operation:
```python
values = redis.mget(keys)  # 1 network round-trip
```

**Why:** Each `get()` requires a network round-trip. `mget()` fetches all keys in one command, dramatically faster.

### 5. **Use `mset()` for Batch Writes**

❌ **Bad** — N round-trips:
```python
for key, value in batch.items():
    redis.set(key, value)  # N round-trips
```

✅ **Good** — single batch:
```python
redis.mset(batch)  # 1 round-trip
```

### 6. **Set TTL for Temporary State**

For rate limiting and time-bounded state:
```python
key = f"rate_limit:{ip_address}"
current = redis.incr(key)
if current == 1:
    redis.expire(key, 900)  # 15 minutes auto-cleanup
```

Or in one command:
```python
redis.set(key, value, ex=900)  # ex = expire in 900 seconds
```

### 7. **Credential Sourcing**

Always use environment variables:
```python
class Settings:
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    # ...
```

In docker-compose.yml:
```yaml
services:
  redis:
    command: redis-server --requirepass ${REDIS_PASSWORD}
  
  solr-search:
    environment:
      REDIS_PASSWORD: ${REDIS_PASSWORD}
```

**Why:** Never hardcode passwords. Separate code from configuration.

## Examples

Reference implementations in aithena:
- `src/solr-search/main.py` — connection pool (fixed version)
- `src/solr-search/search_service.py` — batch operations for indexing state
- `src/document-indexer/` — rate limiting usage
- `src/admin/src/pages/shared/config.py` — health check

## Anti-Patterns

- **Don't use `redis.Redis(..., password=...)` alone** — must also update ConnectionPool
- **Don't use `KEYS` in production** — use SCAN or maintain explicit key registries
- **Don't chain individual `get()`/`set()` calls** — use `mget()`/`mset()` for batches
- **Don't forget TTL on rate limiting keys** — they'll accumulate forever
- **Don't assume connection pooling is automatic** — FastAPI doesn't auto-pool; you must create it
- **Don't share redis.Redis() instances across threads** — thread-safe only when using ConnectionPool

## Testing

Mock Redis for unit tests:
```python
from unittest.mock import patch, MagicMock

@patch("main.redis_lib.ConnectionPool")
def test_redis_auth(mock_pool_class):
    mock_pool = MagicMock()
    mock_pool_class.return_value = mock_pool
    
    from main import _get_redis_pool
    _get_redis_pool()
    
    # Verify password was passed
    mock_pool_class.assert_called_once()
    call_kwargs = mock_pool_class.call_args.kwargs
    assert call_kwargs["password"] == "expected_password"
```

## Scope & Enforcement

Applies to:
- solr-search (state tracking, rate limiting, caching)
- document-indexer (state management)
- document-lister (optional, future optimization)
- admin (optional, dashboard state)

Checked in:
- Code reviews (architecture audit)
- Unit tests (mocked Redis behavior)
- Integration tests (real Redis container)
