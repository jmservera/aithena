"""Contract tests for the Solr search API.

These tests verify the public contract of the /search and /health endpoints:
response shape, field normalisation, facets, highlights, pagination metadata,
document_url construction, validation behaviour, and upstream-error handling.

No live Solr instance or book library is required — all Solr I/O is mocked.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /search — successful responses
# ---------------------------------------------------------------------------


def test_search_returns_200_for_valid_query(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    assert resp.status_code == 200


def test_search_response_contains_top_level_keys(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    body = resp.json()
    assert set(body.keys()) >= {"query", "pagination", "results", "facets", "highlights"}


def test_search_echoes_query_in_response(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    assert resp.json()["query"] == "Barcelona"


def test_search_result_contains_normalised_fields(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    result = resp.json()["results"][0]
    assert "id" in result
    assert "title" in result
    assert "author" in result
    assert "year" in result
    assert "category" in result
    assert "language" in result
    assert "file_path" in result
    assert "document_url" in result


def test_search_result_normalises_solr_fields_correctly(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    result = resp.json()["results"][0]
    assert result["title"] == "Auca dels costums de Barcelona"
    assert result["author"] == "Amades"
    assert result["year"] == 1950
    assert result["category"] == "folklore"
    assert result["language"] == "ca"
    assert "amades/Auca dels costums de Barcelona amades.pdf" in result["file_path"]


def test_search_constructs_document_url(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    result = resp.json()["results"][0]
    assert result["document_url"] is not None
    assert result["file_path"] in result["document_url"]


def test_search_document_url_includes_base_url(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    result = resp.json()["results"][0]
    # document_url must start with the configured DOCUMENT_BASE_URL
    assert result["document_url"].startswith("/api/documents/")


# ---------------------------------------------------------------------------
# /search — pagination metadata
# ---------------------------------------------------------------------------


def test_search_pagination_contains_required_keys(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "book"})
    pagination = resp.json()["pagination"]
    assert "total" in pagination
    assert "rows" in pagination
    assert "start" in pagination


def test_search_pagination_reflects_query_params(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "book", "rows": 5, "start": 10})
    pagination = resp.json()["pagination"]
    assert pagination["rows"] == 5
    assert pagination["start"] == 10


def test_search_pagination_total_reflects_solr_num_found(solr_ok):
    client, payload = solr_ok
    resp = client.get("/search", params={"q": "book"})
    assert resp.json()["pagination"]["total"] == payload["response"]["numFound"]


# ---------------------------------------------------------------------------
# /search — facets
# ---------------------------------------------------------------------------


def test_search_includes_facets_by_default(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "book"})
    facets = resp.json()["facets"]
    assert isinstance(facets, dict)
    assert len(facets) > 0


def test_search_facets_contain_expected_fields(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "book"})
    facets = resp.json()["facets"]
    assert "category_s" in facets
    assert "author_s" in facets
    assert "language_detected_s" in facets


def test_search_facet_values_are_int_counts(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "book"})
    for field_counts in resp.json()["facets"].values():
        for count in field_counts.values():
            assert isinstance(count, int)
            assert count > 0


def test_search_facets_omitted_when_facet_false(solr_ok):
    client, _ = solr_ok
    resp = client.get("/search", params={"q": "book", "facet": "false"})
    assert resp.json()["facets"] == {}


# ---------------------------------------------------------------------------
# /search — highlights
# ---------------------------------------------------------------------------


def test_search_includes_highlighting(solr_ok):
    client, payload = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    highlights = resp.json()["highlights"]
    assert isinstance(highlights, dict)
    assert len(highlights) > 0


def test_search_highlights_contain_snippets(solr_ok):
    client, payload = solr_ok
    resp = client.get("/search", params={"q": "Barcelona"})
    highlights = resp.json()["highlights"]
    doc_id = list(highlights.keys())[0]
    fields = highlights[doc_id]
    # At least one highlight field must have a non-empty snippet list
    assert any(isinstance(v, list) and len(v) > 0 for v in fields.values())


# ---------------------------------------------------------------------------
# /search — empty results
# ---------------------------------------------------------------------------


def test_search_empty_results_returns_200(solr_empty):
    client, _ = solr_empty
    resp = client.get("/search", params={"q": "xyzzy_no_match"})
    assert resp.status_code == 200


def test_search_empty_results_has_zero_total(solr_empty):
    client, _ = solr_empty
    resp = client.get("/search", params={"q": "xyzzy_no_match"})
    assert resp.json()["pagination"]["total"] == 0


def test_search_empty_results_has_empty_results_list(solr_empty):
    client, _ = solr_empty
    resp = client.get("/search", params={"q": "xyzzy_no_match"})
    assert resp.json()["results"] == []


def test_search_empty_results_has_empty_highlights(solr_empty):
    client, _ = solr_empty
    resp = client.get("/search", params={"q": "xyzzy_no_match"})
    assert resp.json()["highlights"] == {}


# ---------------------------------------------------------------------------
# /search — request validation
# ---------------------------------------------------------------------------


def test_search_missing_q_returns_422(client):
    resp = client.get("/search")
    assert resp.status_code == 422


def test_search_empty_q_returns_422(client):
    resp = client.get("/search", params={"q": ""})
    assert resp.status_code == 422


def test_search_negative_rows_returns_422(client):
    resp = client.get("/search", params={"q": "book", "rows": -1})
    assert resp.status_code == 422


def test_search_zero_rows_returns_422(client):
    resp = client.get("/search", params={"q": "book", "rows": 0})
    assert resp.status_code == 422


def test_search_rows_above_max_returns_422(client):
    resp = client.get("/search", params={"q": "book", "rows": 101})
    assert resp.status_code == 422


def test_search_negative_start_returns_422(client):
    resp = client.get("/search", params={"q": "book", "start": -1})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /search — upstream Solr failures
# ---------------------------------------------------------------------------


def test_search_solr_500_returns_502(solr_error_500):
    client = solr_error_500
    resp = client.get("/search", params={"q": "book"})
    assert resp.status_code == 502


def test_search_solr_500_error_detail_mentions_status(solr_error_500):
    client = solr_error_500
    resp = client.get("/search", params={"q": "book"})
    detail = resp.json().get("detail", "")
    assert "500" in detail


def test_search_solr_unreachable_returns_502(solr_unreachable):
    client = solr_unreachable
    resp = client.get("/search", params={"q": "book"})
    assert resp.status_code == 502


def test_search_solr_unreachable_error_detail_is_informative(solr_unreachable):
    client = solr_unreachable
    resp = client.get("/search", params={"q": "book"})
    detail = resp.json().get("detail", "")
    assert len(detail) > 0
