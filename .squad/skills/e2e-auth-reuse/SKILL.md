# E2E Auth Token Reuse Pattern

## Skill ID
`e2e-auth-reuse`

## Confidence
**Medium** — Successfully implemented in PR #1588, validated in CI, and confirmed to resolve chronic rate-limit failures (#1583).

## Last Confirmed
2026-05-31 — PR #1588 merged, CI runs show `[setup] reusing E2E_API_TOKEN from environment (skipping login)` pattern working at scale (28 passed, 22 skipped, 0 failures in ci_e2e_tests workflow run 26717457605).

## Evidence
- **Issue #1583:** Chronic 429 rate-limit failures in E2E workflows (root cause: back-to-back `/v1/auth/login` calls from same IP)
- **PR #1588:** Implementation of token-reuse pattern + single-retry defense-in-depth
- **Files:** `e2e/playwright/global-setup.ts` (lines 71-142) — production code showing pattern in use
- **CI Validation:** Multiple workflow runs passing with `E2E_API_TOKEN` env var present; fallback path (password login) tested locally and working when env var absent

## Context
E2E tests in CI often need authenticated sessions. When the CI workflow mints an auth token (e.g., via curl), downstream test runners should consume that token via environment variable instead of re-authenticating. This avoids rate-limit races and speeds up test setup.

## Pattern

### Workflow Side (CI)
```yaml
- name: Run E2E tests
  env:
    E2E_USERNAME: ${{ env.CI_ADMIN_USERNAME }}
    E2E_PASSWORD: ${{ env.CI_ADMIN_PASSWORD }}
  run: |
    # Mint token once via curl
    export E2E_API_TOKEN="$(curl --fail --silent --show-error \
      -H 'Content-Type: application/json' \
      -d "{\"username\":\"$E2E_USERNAME\",\"password\":\"$E2E_PASSWORD\"}" \
      http://localhost/v1/auth/login | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')"
    
    # Pass token to test runner (it's already exported in this shell)
    npx playwright test
```

### Test Setup Side (e.g., Playwright global-setup)
```typescript
async function writeAuthStorageState(resolvedBaseURL: string): Promise<void> {
  let accessToken = process.env.E2E_API_TOKEN;

  // If E2E_API_TOKEN is already set (e.g., in CI), reuse it to avoid rate limiting.
  // Otherwise, fall back to the legacy login flow for local development.
  if (accessToken) {
    console.log('[setup] reusing E2E_API_TOKEN from environment (skipping login)');
  } else {
    // Local dev fallback: password-based login
    const username = process.env.E2E_USERNAME;
    const password = process.env.E2E_PASSWORD;
    // ... perform login, set accessToken ...
  }

  // Write accessToken to auth storage state
  await writeFile(AUTH_STATE_PATH, JSON.stringify({
    cookies: [],
    origins: [{
      origin: resolvedBaseURL,
      localStorage: [{ name: AUTH_TOKEN_STORAGE_KEY, value: accessToken }],
    }],
  }));
}
```

### Defense-in-Depth: Retry on 429
Add a single retry with jittered backoff when the login endpoint returns 429:
```typescript
let retries = 0;
const maxRetries = 1;

while (retries <= maxRetries) {
  try {
    const response = await api.post('/v1/auth/login', { data: { username, password } });
    
    if (!response.ok()) {
      // On 429, retry once with jittered backoff
      if (response.status() === 429 && retries < maxRetries) {
        const jitter = Math.floor(Math.random() * 2000) + 1000; // 1-3 seconds
        console.warn(`[setup] login returned 429, retrying after ${jitter}ms...`);
        await new Promise(resolve => setTimeout(resolve, jitter));
        retries += 1;
        continue;
      }
      throw new Error(`Login failed (${response.status()}): ${await response.text()}`);
    }
    
    accessToken = (await response.json()).access_token;
    break;
  } catch (error) {
    if (retries >= maxRetries) throw error;
    retries += 1;
  }
}
```

## Benefits
- **Eliminates rate-limit races** — no back-to-back login calls from the same IP
- **Faster test setup** — one fewer HTTP round-trip
- **Clear separation of concerns** — workflow owns auth, tests consume tokens
- **Preserves local dev workflow** — fallback to password login when env var is absent

## When to Use
- CI workflows that mint auth tokens before running tests
- Test setups that currently perform their own login (Playwright global-setup, pytest fixtures, etc.)
- Any scenario where multiple processes might hit the same rate-limited auth endpoint

## Implementation Example
See `e2e/playwright/global-setup.ts` (lines 71-142) for the full implementation that fixed #1583.

## Related
- Issue: #1583 (chronic 429 errors in E2E workflows)
- PR: #1588 (implementation)
- Decision: `.squad/decisions/inbox/parker-e2e-token-reuse.md`

## Discovered
2026-05-31 by Parker (Backend Dev) while fixing CI E2E failures

## Related
- Pattern complements `.squad/skills/playwright-e2e-aithena` (test infrastructure)
- Enables "Always Test Locally Before Pushing" directive (`.squad/decisions.md`)
