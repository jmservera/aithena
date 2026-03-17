# Decision: Auth & URL State Test Strategy (#343)

**Author:** Lambert (Tester)  
**Date:** 2026-07-14  
**Status:** Implemented  

## Context
Issue #343 required integration tests for admin auth flow and frontend URL state persistence — the last blocker for v1.3.0.

## Decisions

1. **Integration tests live alongside unit tests** — backend in `src/admin/tests/test_auth_integration.py`, frontend in `src/aithena-ui/src/__tests__/useSearchState.integration.test.tsx`. No separate `integration/` directory; follows existing test file conventions.

2. **Mock Streamlit session state, not JWT internals** — Auth tests mock `st.session_state` as a plain dict to test the full login→check→logout cycle without Streamlit runtime. JWT encoding/decoding uses real `pyjwt` library.

3. **Frontend hook tests use MemoryRouter** — `useSearchState` tests wrap hooks in `MemoryRouter` with `initialEntries` to simulate URL deep-links and state restoration without browser navigation.

4. **Edge case: `hmac.compare_digest` rejects non-ASCII** — Python's `hmac.compare_digest` raises `TypeError` for non-ASCII strings. Test documents this behavior rather than suppressing it.

## Impact
- Team members writing new auth features should add tests to `test_auth_integration.py`
- URL state changes should add corresponding round-trip tests
