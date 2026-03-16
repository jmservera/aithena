# Decision: Exception Chaining in Error Responses

**Date:** 2026-03-17  
**Author:** Kane (Security Engineer)  
**Context:** Issue #291, CodeQL Alert #104  
**Status:** Implemented in PR #308

## Problem

CodeQL flagged potential stack trace exposure in `solr-search/main.py:223` where exception chaining (`from exc`) was used in `auth.py` and the exception message was converted to string and returned in HTTP responses.

## Investigation

**Technical Analysis:**
- Python's `str(exc)` only returns the exception message, never the traceback
- All exception messages in the flagged code were hardcoded and safe
- FastAPI default behavior does not expose stack traces in production
- **This was technically a false positive**

**However:** CodeQL's conservative analysis correctly identified a potential risk area:
- Exception chaining creates `__cause__` and `__context__` attributes
- While `str()` is safe, custom `__str__` implementations could theoretically leak
- The chained exceptions serve no purpose in user-facing error messages

## Decision

**Remove exception chaining (`from exc`) when raising exceptions that will be returned to users.**

**Rationale:**
1. **Defense-in-depth:** Even false positives indicate areas worth hardening
2. **Code clarity:** Exception chaining adds no value when messages are already clear
3. **Scanner compliance:** Eliminates security alerts and prevents future confusion
4. **Zero cost:** No functional impact, all tests pass

## Implementation

Applied to `src/solr-search/auth.py`:
- Removed `from exc` from `TokenExpiredError` raises
- Removed `from exc` from `AuthenticationError` raises
- Exception messages unchanged
- All 144 tests pass

## Guidelines for Team

**When to use exception chaining (`from exc`):**
- ✅ Internal code where context helps debugging
- ✅ Logged errors (server-side only)
- ✅ Development/debug mode

**When NOT to use exception chaining:**
- ❌ Exceptions that flow into HTTP responses
- ❌ User-facing error messages
- ❌ When the message is already hardcoded and clear

**Pattern:**
```python
# ❌ Avoid for user-facing errors
except JWTError as exc:
    raise AuthenticationError("Invalid token") from exc

# ✅ Better for user-facing errors
except JWTError:
    raise AuthenticationError("Invalid token")

# ✅ OK for internal/logged errors
except DatabaseError as exc:
    logger.error("Database connection failed", exc_info=True)
    raise ServiceError("Database unavailable") from exc  # If logged/internal
```

## Impact

- **Security:** Reduces theoretical information exposure risk
- **Maintainability:** Clearer exception handling patterns
- **Compliance:** Satisfies CodeQL scanner
- **Functionality:** Zero impact (all tests pass)

## References

- Issue: #291
- CodeQL Alert: #104 (py/stack-trace-exposure)
- PR: #308
- Testing: 144/144 solr-search tests pass
