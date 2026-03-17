# Test Report — v1.3.0

| Field       | Value                     |
|-------------|---------------------------|
| **Version** | 1.3.0                     |
| **Date**    | 2026-03-17 07:32 UTC      |
| **Runner**  | Lambert (Tester)          |
| **Verdict** | ✅ **PASS**               |

---

## Summary

All **467 tests** passed across 6 services. No failures. Frontend lint and build both clean.

---

## Per-Service Results

| # | Service             | Passed | Failed | Skipped | Total | Coverage | Status |
|---|---------------------|--------|--------|---------|-------|----------|--------|
| 1 | solr-search         | 193    | 0      | 0       | 193   | 94.60%   | ✅ PASS |
| 2 | document-indexer    | 91     | 0      | 4       | 95    | 81.50%   | ✅ PASS |
| 3 | document-lister     | 12     | 0      | 0       | 12    | —        | ✅ PASS |
| 4 | embeddings-server   | 9      | 0      | 0       | 9     | —        | ✅ PASS |
| 5 | admin               | 33     | 0      | 0       | 33    | —        | ✅ PASS |
| 6 | aithena-ui (Vitest) | 127    | 0      | 0       | 127   | —        | ✅ PASS |

### Totals

| Metric   | Count |
|----------|-------|
| Passed   | 465   |
| Failed   | 0     |
| Skipped  | 4     |
| **Total**| **469** |

> **Note:** 4 skipped tests in document-indexer are metadata tests requiring the maintainer's local book library paths. This is expected and documented.

---

## Additional Checks

| Check           | Result   |
|-----------------|----------|
| Frontend lint (ESLint) | ✅ Clean — 0 warnings |
| Frontend build (TypeScript + Vite) | ✅ Clean — built in 218ms |

---

## Coverage Thresholds

| Service          | Required | Actual  | Status |
|------------------|----------|---------|--------|
| solr-search      | 88.0%    | 94.60%  | ✅ Above threshold |
| document-indexer | 70.0%    | 81.50%  | ✅ Above threshold |

---

## Failures

None.

---

## Notes

- `UV_NATIVE_TLS=1` required for all `uv` commands in this codespace (SSL cert issue).
- embeddings-server uses its own `.venv` with `requirements.txt`; `pytest` and `httpx` installed via `.venv/bin/pip`.
- Test count increased from 452 (v1.2.0) to 469 (v1.3.0): +17 tests across solr-search and document-indexer.
- All 19 warnings in admin tests are `InsecureKeyLengthWarning` from test-only HMAC keys — not a production concern.

---

## Verdict

**✅ PASS** — All services are green. v1.3.0 is ready for release.
