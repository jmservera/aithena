# Aithena v0.4.0 Test Coverage Report

_Date:_ 2026-03-14  
_Prepared by:_ Lambert (Tester)

## Scope and evidence collected

Commands executed for this report:

```bash
cd /home/jmservera/source/aithena/solr-search && uv run pytest -v --tb=short 2>&1
cd /home/jmservera/source/aithena/document-indexer && uv run pytest -v --tb=short 2>&1
cd /home/jmservera/source/aithena/solr-search && uv run pytest -v --tb=short --cov=. --cov-report=term 2>&1
cd /home/jmservera/source/aithena/document-indexer && uv run pytest -v --tb=short --cov=document_indexer --cov-report=term 2>&1
ls -la /home/jmservera/source/aithena/e2e/
cat /home/jmservera/source/aithena/e2e/test_upload_index_search.py
cat /home/jmservera/source/aithena/e2e/conftest.py
ls -la /home/jmservera/source/aithena/e2e/playwright/
cd /home/jmservera/source/aithena/aithena-ui && grep -A12 '"scripts"' package.json
find src -type f \( -name '*.test.*' -o -name '*.spec.*' \) | sort
```

## Executive summary

- **Backend test execution:** **151 / 151 tests passed (100%)**.
- **Backend unit tests:** **101 passing tests**.
- **Backend integration tests:** **50 passing tests**.
- **Backend coverage:**
  - `solr-search`: **97% total coverage**
  - `document-indexer`: **84% total coverage**
- **E2E automation present but not executed in this audit:**
  - `e2e/test_upload_index_search.py`: **5 pytest E2E tests**
  - `e2e/playwright/tests/*.spec.ts`: **7 Playwright browser E2E tests**
- **Frontend unit/component tests:** **none present** in `aithena-ui`.

### Current quality position

The backend is in a strong state for isolated testing: both Python services have broad automated coverage and the FastAPI search service is especially well covered. The biggest gaps are not in backend unit correctness, but in **true full-stack integration**:

1. no automated test exercises the real `document-lister -> RabbitMQ -> document-indexer -> Solr -> API -> UI` pipeline end to end,
2. the browser suite depends on a running local stack and indexed data,
3. the React frontend has **zero** colocated component/hook tests.

## Backend test results

### Summary table

| Service | Type | Files | Tests run | Result | Coverage |
|---|---:|---:|---:|---|---:|
| `document-indexer` | Unit/orchestration | 3 | 73 | 73 passed | 84% |
| `solr-search` | Unit | 1 | 28 | 28 passed | included below |
| `solr-search` | Integration (mocked external services) | 1 | 50 | 50 passed | included below |
| **Total** | **Backend** | **5** | **151** | **151 passed** | — |

### Coverage by module

#### `solr-search`

| Module | Statements | Miss | Cover |
|---|---:|---:|---:|
| `config.py` | 41 | 0 | 100% |
| `main.py` | 229 | 27 | 88% |
| `search_service.py` | 152 | 10 | 93% |
| `tests/test_integration.py` | 554 | 0 | 100% |
| `tests/test_search_service.py` | 146 | 2 | 99% |
| **TOTAL** | **1122** | **39** | **97%** |

#### `document-indexer`

| Module | Statements | Miss | Cover |
|---|---:|---:|---:|
| `document_indexer/__init__.py` | 14 | 0 | 100% |
| `document_indexer/__main__.py` | 172 | 41 | 76% |
| `document_indexer/chunker.py` | 54 | 0 | 100% |
| `document_indexer/embeddings.py` | 14 | 8 | 43% |
| `document_indexer/metadata.py` | 107 | 9 | 92% |
| **TOTAL** | **361** | **58** | **84%** |

### Notable warnings observed

`solr-search` passed cleanly but emitted **43 warnings** during the run:
- `PendingDeprecationWarning` from `starlette.formparsers` (`import multipart`)
- `DeprecationWarning` from `httpx` TestClient usage (`app` shortcut)

These are not failures today, but they are upgrade-risk signals.

## Backend unit tests

### `document-indexer/tests/test_chunker.py` — 28 passed

**Status:** PASS  
**What it covers:** text chunking, overlap semantics, whitespace normalization, invalid arguments, and page-aware chunk/page-range propagation.

**Named tests / cases:**
- `TestChunkText`: `test_empty_string_returns_empty_list`, `test_whitespace_only_returns_empty_list`, `test_short_text_fits_in_single_chunk`, `test_exact_chunk_size_produces_one_chunk`, `test_text_split_into_multiple_chunks_no_overlap`, `test_overlap_repeats_words_at_chunk_boundaries`, `test_overlap_words_appear_in_consecutive_chunks`, `test_output_is_deterministic`, `test_normalises_internal_whitespace`, `test_invalid_chunk_size_raises`, `test_negative_overlap_raises`, `test_overlap_equal_to_chunk_size_raises`, `test_last_chunk_contains_remaining_words`, `test_single_word`
- `TestChunkTextWithPages`: `test_empty_pages_returns_empty_list`, `test_pages_with_no_text_return_empty_list`, `test_single_page_short_text_fits_in_one_chunk`, `test_single_page_chunk_tracks_correct_page_number`, `test_multi_page_single_chunk_spans_all_pages`, `test_chunk_spanning_two_pages_has_correct_page_range`, `test_chunk_confined_to_single_page_has_matching_start_and_end`, `test_returns_tuples_of_text_page_start_page_end`, `test_chunk_text_matches_expected_words`, `test_overlap_propagated_correctly`, `test_invalid_chunk_size_raises`, `test_negative_overlap_raises`, `test_overlap_equal_to_chunk_size_raises`, `test_page_numbering_non_sequential`

**Assessment:** excellent low-level coverage of the chunking logic, including edge cases that matter for semantic/chunk-based search.

### `document-indexer/tests/test_indexer.py` — 30 passed

**Status:** PASS  
**What it covers:** document chunk doc construction, chunk upload orchestration, Solr startup gating, failure-state recording, and high-level indexing flow with mocked dependencies.

**Named tests / cases:**
- `TestBuildChunkDoc`: `test_chunk_id_is_deterministic`, `test_chunk_index_zero_padded`, `test_embedding_stored_in_doc`, `test_parent_id_linked`, `test_metadata_propagated`, `test_optional_category_included_when_present`, `test_optional_category_absent_when_none`, `test_optional_year_included_when_present`, `test_page_fields_included_when_provided`, `test_page_fields_absent_when_not_provided`, `test_page_start_equals_page_end_for_single_page_chunk`
- `TestIndexChunks`: `test_returns_chunk_count`, `test_posts_json_docs_to_solr`, `test_empty_text_returns_zero_without_calling_embeddings`, `test_propagates_embedding_error`, `test_propagates_solr_error`, `test_page_numbers_propagated_to_solr_docs`
- `TestWaitForSolrCollection`: `test_returns_when_collection_and_extract_handler_are_ready`, `test_retries_until_extract_handler_exists`, `test_raises_after_exhausting_attempts`
- `TestIndexDocument`: `test_successful_indexing_marks_processed_true`, `test_text_indexing_records_text_indexed_true_before_embeddings`, `test_text_indexing_failure_marks_text_indexing_stage`, `test_embedding_indexing_failure_marks_embedding_indexing_stage`, `test_text_indexing_failure_does_not_attempt_embedding_indexing`, `test_non_pdf_raises_value_error`, `test_missing_file_raises_file_not_found`
- `TestMarkFailure`: `test_records_stage_in_redis_state`, `test_embedding_stage_recorded_correctly`
- `TestSaveState`: `test_allows_file_path_metadata_field`

**Assessment:** strong orchestration coverage, but still mocked. It validates control flow and Redis state updates without proving the real services interoperate.

### `document-indexer/tests/test_metadata.py` — 15 passed (10 test functions, 15 collected cases)

**Status:** PASS  
**What it covers:** metadata extraction heuristics across root files, author folders, category folders, Unicode filenames, non-PDF paths, deep nested paths, conservative fallbacks, and real-library naming patterns.

**Named tests / cases:**
- `test_extract_metadata_parses_author_directory_pattern`
- `test_extract_metadata_parses_author_title_year_filename_pattern`
- `test_extract_metadata_parses_category_author_title_pattern`
- `test_extract_metadata_parses_category_filename_pattern`
- `test_extract_metadata_handles_unicode_and_non_pdf_paths[special-characters-author-title-year]`
- `test_extract_metadata_handles_unicode_and_non_pdf_paths[missing-year]`
- `test_extract_metadata_handles_unicode_and_non_pdf_paths[non-pdf]`
- `test_extract_metadata_keeps_very_long_titles_intact`
- `test_extract_metadata_falls_back_for_root_level_unknown_pattern`
- `test_extract_metadata_handles_nested_deep_paths_conservatively`
- `test_extract_metadata_uses_filename_fallback_for_unknown_patterns`
- `test_extract_metadata_matches_real_library_patterns[real-amades-author-folder]`
- `test_extract_metadata_matches_real_library_patterns[real-amades-irregular-numeric]`
- `test_extract_metadata_matches_real_library_patterns[real-balearics-series-folder]`
- `test_extract_metadata_matches_real_library_patterns[real-bsal-year-range]`

**Assessment:** this is the strongest evidence that the parser is aligned with the real book library naming conventions.

### `solr-search/tests/test_search_service.py` — 28 passed

**Status:** PASS  
**What it covers:** pure helper/service logic for Solr parameter building, facet parsing, filter query construction, result normalization, page-range normalization, tokenized document URLs, traversal protection, query sanitization, inline content disposition, pagination, kNN parameter building, reciprocal rank fusion, Solr escaping, and stats parsing.

**Named tests / cases:**
- `test_build_solr_params_adds_pagination_sort_facets_and_highlights`
- `test_parse_facet_counts_prefers_detected_language_buckets`
- `test_build_filter_queries_supports_language_fallback_and_exact_matches`
- `test_normalize_book_collects_fields_and_highlights`
- `test_normalize_book_includes_page_range_for_chunk_hit`
- `test_normalize_book_pages_null_for_full_doc_hit`
- `test_normalize_book_single_page_chunk`
- `test_normalize_book_page_start_only`
- `test_normalize_book_page_end_only`
- `test_document_tokens_round_trip_and_stay_under_base_path`
- `test_resolve_document_path_rejects_traversal`
- `test_normalize_search_query_rejects_local_params`
- `test_build_inline_content_disposition_sanitizes_newlines`
- `test_build_pagination_handles_empty_results`
- `test_build_knn_params_produces_correct_solr_query`
- `test_build_knn_params_custom_field`
- `test_reciprocal_rank_fusion_empty_inputs`
- `test_reciprocal_rank_fusion_keyword_only`
- `test_reciprocal_rank_fusion_semantic_only`
- `test_reciprocal_rank_fusion_shared_doc_ranks_first`
- `test_reciprocal_rank_fusion_scores_descending`
- `test_reciprocal_rank_fusion_rrf_score_overwrites_original_score`
- `test_reciprocal_rank_fusion_preserves_metadata`
- `test_solr_escape_handles_special_characters`
- `test_parse_stats_response_extracts_all_fields`
- `test_parse_stats_response_handles_empty_collection`
- `test_parse_stats_response_handles_missing_stats_section`
- `test_parse_stats_response_rounds_average`

**Assessment:** excellent helper-level coverage, including security-sensitive path traversal and Solr local-param rejection.

## Backend integration tests

### `solr-search/tests/test_integration.py` — 50 passed

**Status:** PASS  
**Type:** API-level integration with `FastAPI TestClient`; external Solr/embeddings/Redis interactions mocked.  
**What it covers:** endpoint contracts, alias compatibility, pagination, sorting, facets, hybrid/semantic modes, similar-books endpoint, stats endpoint, and status endpoint behavior.

**Named tests / cases:**
- Search and aliases: `test_search_returns_results_with_mocked_solr`, `test_v1_search_alias_supports_ui_contract_params`, `test_search_handles_empty_query`, `test_facets_endpoint_returns_facet_counts`, `test_search_handles_solr_timeout`, `test_search_handles_solr_connection_error`, `test_search_handles_invalid_solr_response`, `test_health_endpoint_returns_ok`, `test_info_endpoint_returns_service_info`, `test_v1_health_and_info_aliases_return_ok`, `test_search_pagination_parameters_passed_correctly`, `test_search_sorting_parameters_applied`
- Search modes: `test_search_keyword_mode_explicit`, `test_search_default_mode_is_keyword`, `test_search_semantic_mode_calls_embeddings_and_knn`, `test_search_semantic_empty_query_returns_400`, `test_search_hybrid_mode_fuses_both_legs`, `test_search_hybrid_empty_query_returns_400`
- Similar books: `test_similar_returns_200_with_results`, `test_v1_similar_alias_returns_results`, `test_similar_result_contains_required_fields`, `test_similar_excludes_source_document_via_fq`, `test_similar_uses_knn_query_parser`, `test_similar_retrieves_embedding_field_from_source`, `test_similar_limit_controls_rows_in_knn_query`, `test_similar_min_score_filters_results`, `test_similar_returns_404_for_unknown_id`, `test_similar_returns_422_when_embedding_missing`, `test_similar_returns_empty_list_when_no_similar_found`, `test_similar_returns_502_on_solr_error`, `test_v1_document_alias_is_registered`
- Stats and chunk-hit behavior: `test_stats_returns_200_with_correct_shape`, `test_stats_no_slash_alias_returns_200`, `test_stats_legacy_path_returns_200`, `test_stats_sends_correct_solr_params`, `test_stats_handles_empty_collection`, `test_stats_returns_504_on_solr_timeout`, `test_stats_returns_502_on_solr_error`, `test_search_chunk_hits_include_page_range`, `test_search_solr_field_list_includes_page_fields`
- Status endpoint and helpers: `test_status_endpoint_returns_expected_shape`, `test_status_endpoint_slash_alias`, `test_status_services_down_when_tcp_fails`, `test_get_solr_status_on_connection_error`, `test_get_solr_status_parses_cluster_response`, `test_get_solr_status_degraded_with_fewer_nodes`, `test_get_indexing_status_counts_states`, `test_get_indexing_status_on_redis_error`, `test_tcp_check_success`, `test_tcp_check_failure`

**Assessment:** very good contract coverage for the search API. However, because Solr and the embeddings service are mocked, these tests do **not** prove real schema compatibility or live Solr query correctness.

### What is not currently covered by backend integration tests

- No live-Solr integration suite for `solr-search`
- No live-Redis integration suite for status/indexing counters
- No live embeddings-server integration suite
- No integration test for `document-indexer` against a real Solr `/update/extract` handler plus real Redis state persistence
- No automated test for the real RabbitMQ consumer callback path

## E2E tests

### Python E2E: `e2e/test_upload_index_search.py` — 5 tests present

**Status in this audit:** discovered and reviewed, **not executed**  
**Execution model:** pytest E2E against a running local stack  
**Can it run without full stack?** **No.** It requires at least a healthy Solr collection and an E2E library bind mount.

**What it tests:**
- `test_fixture_pdf_exists_in_library` — writes a minimal fixture PDF into the shared test library
- `test_index_document_into_solr` — POSTs the fixture directly to Solr `/update/extract`
- `test_search_returns_indexed_document` — verifies the indexed document is searchable with expected metadata
- `test_pdf_file_path_is_accessible` — checks `file_path_s` resolves back to a real file on disk
- `test_cleanup_solr_document` — removes the fixture from Solr after the scenario

**Important limitation:** this suite does **not** test the real `document-lister` polling cycle or RabbitMQ-driven ingestion. It deliberately shortcuts indexing by POSTing directly to Solr for determinism and speed.

### Shared E2E fixtures: `e2e/conftest.py`

This file provides:
- a minimal valid PDF generator,
- `solr_available` skip-fast behavior when Solr is unreachable,
- a temporary test library root,
- deterministic Solr ID generation from relative paths,
- `wait_for_solr_doc()` polling helper.

**Implication:** the E2E pytest suite is practical for local validation but still environment-dependent.

### Browser E2E: `e2e/playwright/` — 7 Playwright tests present

**Status in this audit:** discovered and reviewed, **not executed**  
**Can it run without full stack?** **No.** It requires the UI and API to be reachable, and most tests also require indexed documents/facets/PDFs.

#### Tooling and setup

- `e2e/playwright/package.json` exposes:
  - `npm run test`
  - `npm run test:e2e`
  - `npm run test:e2e:ui`
- `playwright.config.ts` runs Chromium with HTML + list reporters.
- `global-setup.ts` probes `http://localhost/search` and `http://localhost:5173/search`, then exports `PLAYWRIGHT_APP_BASE_URL`.

#### Browser test files

##### `e2e/playwright/tests/navigation.spec.ts` — 2 tests

- `renders the empty search state before any query is submitted`
- `navigates across the Search, Library, Status, and Stats tabs`

**Coverage:** shell routing, empty state, tab navigation, and placeholder surfaces.

##### `e2e/playwright/tests/search.spec.ts` — 5 tests

- `search flow renders result cards with title, author, and snippet data`
- `author facet filtering narrows results and chip removal restores them`
- `pdf viewer opens from a search result and loads the document iframe`
- `pdf viewer supports page fragment navigation for multi-page PDFs`
- `search pagination requests and displays the next page of results`

**Coverage:** realistic browser behavior for search, author facets, PDF viewer opening, PDF page fragments, and pagination.

#### Strengths and limitations of the Playwright suite

**Strengths**
- Read-only design; it discovers existing indexed data instead of mutating the corpus.
- Data-aware skips prevent false negatives when the stack has no books, no author facets, or no multi-page PDFs.
- Supports both nginx-hosted and Vite-dev-server frontends.

**Limitations**
- Not deterministic on an empty or partially indexed stack.
- Heavy dependence on available local data means CI viability is limited unless the environment is pre-seeded.
- Does not cover an actual upload flow in the browser.

## Frontend tests

### `aithena-ui`

**Current state:** no frontend unit/component/integration tests are configured.

Evidence:
- `package.json` has scripts for `dev`, `build`, `lint`, `format`, `format:check`, and `preview`
- there is **no `test` script**
- `find src -type f \( -name '*.test.*' -o -name '*.spec.*' \)` returned **no files**

### Assessment

This is the largest coverage gap in the repository. The UI currently relies on:
- backend API contract tests,
- Playwright smoke/E2E coverage,
- manual verification.

That leaves component behavior, hook behavior, and regression prevention under-covered.

## Coverage gaps

### High-priority gaps

1. **No real full-stack ingestion test**
   - Missing automated coverage for `document-lister -> RabbitMQ -> document-indexer -> Solr`
   - Current pytest E2E bypasses the queue and lister intentionally

2. **No frontend unit/component tests**
   - No React Testing Library/Vitest coverage for search form, result cards, facets, pagination, PDF viewer state, or data hooks

3. **Low coverage in `document_indexer/embeddings.py` (43%)**
   - Success path exists but error cases and response validation are lightly exercised

4. **Moderate gap in `document_indexer/__main__.py` (76%)**
   - Runtime-only paths such as `consume()`, `callback()`, queue declaration, Redis retry behavior, and real PDF page counting are not thoroughly exercised

5. **Search API integration is mocked, not live**
   - `solr-search/tests/test_integration.py` proves API behavior with mocked dependencies, not with a real Solr collection or live embeddings responses

### Medium-priority gaps

6. **Document streaming endpoint lacks direct endpoint-level assertions with real files**
   - Helper security is tested (`resolve_document_path`, token encoding), but full response behavior for `/documents/{token}` is not comprehensively covered with real PDFs

7. **Status endpoint is not exercised against real Redis/Solr outages**
   - Current status coverage is mocked helper behavior, not live service diagnostics

8. **Playwright suite is data-dependent**
   - Many tests skip when the local stack lacks indexed books, author facets, or multi-page PDFs

9. **No regression tests for warning-producing dependency compatibility**
   - `httpx`/Starlette compatibility warnings suggest future breakage risk around TestClient dependencies

## Recommendations

### Priority 1 — add next

1. **Add one true pipeline integration test for document ingestion**
   - Bring up Redis + RabbitMQ + Solr locally in a test harness or dedicated compose profile
   - Drop a fixture PDF into the watched directory
   - Assert queue message creation, document-indexer consumption, Solr document creation, and Redis processed state

2. **Add frontend tests to `aithena-ui` with Vitest + React Testing Library**
   - Start with: search form submit behavior, result rendering, author facet chip add/remove, pagination controls, PDF viewer open/close, and empty/error states

3. **Raise `document_indexer/embeddings.py` coverage**
   - Add tests for HTTP failure, timeout, malformed JSON, missing `data`, and embedding count mismatch

### Priority 2 — strengthen current suites

4. **Add live-Solr contract tests for `solr-search`**
   - Use a seeded Solr collection and validate actual query params, highlights, facets, page ranges, `/documents/{token}`, `/stats`, and `/books/{id}/similar`

5. **Add direct tests for `/documents/{token}`**
   - Verify 200 on valid PDF, 404 on traversal/invalid token/non-PDF, and safe `Content-Disposition`

6. **Add Redis/RabbitMQ runtime-path tests in `document-indexer`**
   - Cover `get_queue()`, `callback()`, `load_state()` invalid JSON reset behavior, and retry-safe state persistence paths

### Priority 3 — improve release confidence

7. **Make Playwright CI-friendly**
   - Seed a small deterministic Solr fixture corpus so browser tests do not depend on local library contents

8. **Track and remove backend warnings**
   - Pin or update `httpx` / Starlette-compatible dependencies before the deprecations become breaking changes

## Release view for v0.4.0

### What is well tested

- Search-service helper logic and API contract behavior
- Metadata extraction heuristics for real library path patterns
- Chunk/page-range generation logic for embedding indexing
- Document-indexer orchestration and failure-state transitions

### What still needs confidence work before calling testing “complete”

- Real infrastructure-backed ingestion pipeline validation
- React UI unit/component regression coverage
- Deterministic browser E2E in an environment with seeded data
- More runtime-path coverage in `document-indexer`

## Bottom line

**v0.4.0 backend quality is solid in isolated automated testing (151/151 passing, 97% and 84% coverage), but end-to-end confidence is still limited by missing true full-stack ingestion automation and the absence of frontend unit tests.**
