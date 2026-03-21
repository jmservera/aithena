# Metadata Editing — Test Report

**Version:** _fill in_
**Date:** _fill in_
**Tester:** _fill in_

## Summary

| Suite | Tests | Passed | Failed | Skipped |
|-------|-------|--------|--------|---------|
| API — single document edit (`test_metadata_edit.py`) | | | | |
| API — batch edit (`test_batch_metadata_edit.py`) | | | | |
| API — security (`test_metadata_edit_security.py`) | | | | |
| API — integration (`test_metadata_editing.py`) | | | | |
| Frontend — BatchEditPanel (`BatchEditPanel.test.tsx`) | | | | |
| Frontend — useBatchMetadataEdit (`useBatchMetadataEdit.test.ts`) | | | | |
| E2E — metadata-editing (`metadata-editing.spec.ts`) | | | | |
| **Total** | | | | |

## Test environment

- **OS:** _e.g. Ubuntu 22.04_
- **Python:** _e.g. 3.12.3_
- **Node.js:** _e.g. 22.x_
- **Docker Compose:** _e.g. 2.x_
- **Browser (E2E):** _e.g. Chromium (Playwright)_

## API test results

### Single document edit (`test_metadata_edit.py`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | `test_patch_title_only` | ☐ Pass / ☐ Fail | |
| 2 | `test_patch_multiple_fields` | ☐ Pass / ☐ Fail | |
| 3 | `test_patch_year_only` | ☐ Pass / ☐ Fail | |
| 4 | `test_patch_series_field` | ☐ Pass / ☐ Fail | |
| 5 | `test_patch_category_field` | ☐ Pass / ☐ Fail | |
| 6 | `test_patch_trims_whitespace` | ☐ Pass / ☐ Fail | |
| 7 | `test_patch_empty_body_returns_422` | ☐ Pass / ☐ Fail | |
| 8 | `test_patch_year_below_range_returns_422` | ☐ Pass / ☐ Fail | |
| 9 | `test_patch_year_above_range_returns_422` | ☐ Pass / ☐ Fail | |
| 10 | `test_patch_title_too_long_returns_422` | ☐ Pass / ☐ Fail | |
| 11 | `test_patch_document_not_found_returns_404` | ☐ Pass / ☐ Fail | |
| 12 | `test_patch_solr_timeout_returns_504` | ☐ Pass / ☐ Fail | |
| 13 | `test_patch_solr_error_returns_502` | ☐ Pass / ☐ Fail | |
| 14 | `test_patch_redis_failure_returns_503` | ☐ Pass / ☐ Fail | |

### Batch edit (`test_batch_metadata_edit.py`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | `test_batch_edit_two_documents` | ☐ Pass / ☐ Fail | |
| 2 | `test_batch_edit_partial_failure` | ☐ Pass / ☐ Fail | |
| 3 | `test_batch_edit_empty_document_ids_returns_422` | ☐ Pass / ☐ Fail | |
| 4 | `test_batch_edit_too_many_ids_returns_422` | ☐ Pass / ☐ Fail | |
| 5 | `test_batch_edit_exactly_1000_ids_accepted` | ☐ Pass / ☐ Fail | |
| 6 | `test_query_batch_edit_success` | ☐ Pass / ☐ Fail | |
| 7 | `test_query_batch_edit_no_matches` | ☐ Pass / ☐ Fail | |
| 8 | `test_query_batch_edit_pagination` | ☐ Pass / ☐ Fail | |

### Integration (`test_metadata_editing.py`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | `test_override_written_on_single_edit` | ☐ Pass / ☐ Fail | |
| 2 | `test_override_contains_edited_by_and_timestamp` | ☐ Pass / ☐ Fail | |
| 3 | `test_override_maps_all_solr_fields` | ☐ Pass / ☐ Fail | |
| 4 | `test_batch_stores_one_override_per_document` | ☐ Pass / ☐ Fail | |
| 5 | `test_title_maps_to_title_s_and_title_t` | ☐ Pass / ☐ Fail | |
| 6 | `test_single_edit_solr_timeout` | ☐ Pass / ☐ Fail | |
| 7 | `test_single_edit_redis_down_returns_503` | ☐ Pass / ☐ Fail | |
| 8 | `test_batch_edit_redis_failure_reports_partial` | ☐ Pass / ☐ Fail | |
| 9 | `test_last_write_wins_on_single_document` | ☐ Pass / ☐ Fail | |
| 10 | `test_batch_and_single_edit_same_document` | ☐ Pass / ☐ Fail | |

## Frontend test results

### BatchEditPanel (`BatchEditPanel.test.tsx`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | renders with correct title showing document count | ☐ Pass / ☐ Fail | |
| 2 | renders 5 field toggle checkboxes | ☐ Pass / ☐ Fail | |
| 3 | has submit button disabled initially | ☐ Pass / ☐ Fail | |
| 4 | enables submit button when a field toggle is checked | ☐ Pass / ☐ Fail | |
| 5 | submits batch edit and calls onSaved on success | ☐ Pass / ☐ Fail | |
| 6 | shows error when API returns failure | ☐ Pass / ☐ Fail | |
| 7 | shows partial failure results | ☐ Pass / ☐ Fail | |
| 8 | shows validation error for invalid year | ☐ Pass / ☐ Fail | |
| 9 | shows error alert on network failure | ☐ Pass / ☐ Fail | |
| 10 | can enable and use the series field | ☐ Pass / ☐ Fail | |

### useBatchMetadataEdit (`useBatchMetadataEdit.test.ts`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | accepts a valid title | ☐ Pass / ☐ Fail | |
| 2 | rejects title over 255 characters | ☐ Pass / ☐ Fail | |
| 3 | accepts year boundary 1000 | ☐ Pass / ☐ Fail | |
| 4 | accepts year boundary 2099 | ☐ Pass / ☐ Fail | |
| 5 | rejects negative year | ☐ Pass / ☐ Fail | |
| 6 | validates each field independently | ☐ Pass / ☐ Fail | |

## E2E test results

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1–4 | Single document edit stubs | ☐ Skipped | Requires running app |
| 5–8 | Batch edit stubs | ☐ Skipped | Requires running app |
| 9–13 | Validation error display stubs | ☐ Skipped | Requires running app |
| 14–17 | Admin access restriction stubs | ☐ Skipped | Requires running app |

## Known issues

_None identified during this test cycle._

## Sign-off

| Role | Name | Date | Approval |
|------|------|------|----------|
| Tester | | | ☐ |
| Developer | | | ☐ |
| Product Owner | | | ☐ |
