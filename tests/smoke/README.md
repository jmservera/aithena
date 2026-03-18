# Smoke Test Suite

Production deployment validation tests for Aithena.

## Overview

The smoke test suite provides automated post-deployment validation to ensure all services are healthy and critical user flows are functional.

## Usage

### Running the smoke tests

```bash
# Test against localhost (default)
./tests/smoke/production-smoke-test.sh

# Test against a specific host
./tests/smoke/production-smoke-test.sh --host example.com

# With custom timeout
./tests/smoke/production-smoke-test.sh --timeout 30

# With admin authentication (enables additional tests)
ADMIN_PASSWORD=your-password ./tests/smoke/production-smoke-test.sh
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AITHENA_HOST` | `localhost` | Host to test against |
| `AITHENA_TIMEOUT` | `10` | HTTP request timeout in seconds |
| `ADMIN_USERNAME` | `admin` | Admin username for authenticated endpoints |
| `ADMIN_PASSWORD` | _(empty)_ | Admin password (required for auth tests) |

## Test Coverage

### Service Health Checks
- ✅ Nginx health endpoint
- ✅ API (solr-search) health endpoint
- ✅ Admin dashboard (Streamlit) health endpoint

### Version Endpoints
- ✅ API version endpoint
- ✅ Version field validation

### Search API Functionality
- ✅ Search endpoint
- ✅ Search with query parameter
- ✅ Facets endpoint
- ✅ Stats endpoint
- ✅ Books endpoint

### UI and Frontend
- ✅ Homepage loads
- ✅ HTML response validation

### Admin Dashboard
- ✅ Dashboard accessibility
- ✅ Streamlit routing

### Infrastructure Health
- ✅ Solr cluster status (via API)
- ✅ Redis connectivity (via API)
- ✅ RabbitMQ connectivity (via API)

### Authenticated Endpoints (requires ADMIN_PASSWORD)
- ✅ Admin login flow
- ✅ Admin containers endpoint
- ✅ Auth token validation

### Feature Endpoints
- ✅ Similar books endpoint existence

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Integration with Deployment

The smoke test script can be integrated into your deployment pipeline:

```bash
# Example: Run smoke tests after deployment
./buildall.sh && \
./tests/smoke/production-smoke-test.sh || \
  { echo "Smoke tests failed! Rolling back..."; exit 1; }
```

Or in a CI/CD pipeline:

```yaml
# Example: GitHub Actions
- name: Run smoke tests
  run: |
    ADMIN_PASSWORD=${{ secrets.ADMIN_PASSWORD }} \
    ./tests/smoke/production-smoke-test.sh
```

## Design Principles

- **No Docker dependency**: Tests run via HTTP calls, not Docker commands
- **Self-contained**: Only requires `curl` and basic shell utilities
- **Clear output**: Color-coded pass/fail/skip indicators
- **Configurable**: Host, timeout, and credentials via environment variables
- **Fast**: Designed to complete in under 1 minute on a healthy deployment
- **Graceful degradation**: Skips optional tests (e.g., auth) when credentials not provided

## Limitations

- PDF viewer and similar books features require indexed documents - these tests only verify endpoint availability
- Solr, Redis, and RabbitMQ are not directly exposed in production deployments - tests use the API's `/v1/status` endpoint instead
- Upload and indexing pipeline tests are not included (see `e2e/` for full integration tests)

## Related Tests

- **E2E tests** (`e2e/`): Full integration tests with document upload, indexing, and search flows
- **Unit tests**: Service-specific tests in each service's `tests/` directory
- **Playwright tests** (`e2e/playwright/`): Browser-based UI testing
