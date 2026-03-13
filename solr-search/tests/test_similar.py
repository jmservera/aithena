"""Tests for the GET /similar/ endpoint in solr-search."""
from __future__ import annotations

from tests.conftest import (
    DUMMY_VECTOR,
    SIMILAR_DOCS,
    SOURCE_DOC,
    _solr_error_response,
    _solr_response,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_similar(mock_requests_get, source=None, similar=None, similar_count=None):
    """Wire mock_requests_get to return source doc on first call and similar
    docs on the second call."""
    if source is None:
        source = SOURCE_DOC
    if similar is None:
        similar = SIMILAR_DOCS

    source_response = _solr_response([source])
    similar_response = _solr_response(similar, num_found=similar_count or len(similar))
    mock_requests_get.side_effect = [source_response, similar_response]


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


def test_similar_returns_200_with_results(client, mock_requests_get):
    """Endpoint returns HTTP 200 and a results list."""
    _setup_similar(mock_requests_get)

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert len(body["results"]) > 0


def test_similar_result_contains_required_fields(client, mock_requests_get):
    """Each result must include the fields required by the issue acceptance criteria."""
    _setup_similar(mock_requests_get)

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 200
    result = response.json()["results"][0]
    for field in ("id", "title", "author", "year", "category", "document_url", "score"):
        assert field in result, f"Missing required field: {field}"


def test_similar_result_values_match_solr_payload(client, mock_requests_get):
    """Values in each result item are taken from the Solr document fields."""
    _setup_similar(mock_requests_get)

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["title"] == SIMILAR_DOCS[0]["title_s"]
    assert result["author"] == SIMILAR_DOCS[0]["author_s"]
    assert result["year"] == SIMILAR_DOCS[0]["year_i"]
    assert result["category"] == SIMILAR_DOCS[0]["category_s"]
    assert result["document_url"] == SIMILAR_DOCS[0]["file_path_s"]
    assert result["score"] == SIMILAR_DOCS[0]["score"]


# ---------------------------------------------------------------------------
# Self-match exclusion
# ---------------------------------------------------------------------------


def test_similar_excludes_source_document_via_fq(client, mock_requests_get):
    """Endpoint must pass fq=-id:{id} to Solr so the source doc is excluded."""
    _setup_similar(mock_requests_get)

    client.get("/similar/?id=abc123")

    # Second call is the kNN search — verify -id filter is present.
    assert mock_requests_get.call_count == 2
    second_call_params = mock_requests_get.call_args_list[1].kwargs.get(
        "params", mock_requests_get.call_args_list[1].args[1] if len(mock_requests_get.call_args_list[1].args) > 1 else {}
    )
    fq = second_call_params.get("fq", "")
    assert "abc123" in fq
    assert fq.startswith("-id:")


def test_similar_source_id_absent_from_results(client, mock_requests_get):
    """Even if Solr returned the source doc, it must not appear in results.

    The fq filter should prevent this, but an extra client-side check
    confirms the contract regardless.
    """
    _setup_similar(mock_requests_get)

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 200
    result_ids = [r["id"] for r in response.json()["results"]]
    assert "abc123" not in result_ids


# ---------------------------------------------------------------------------
# Query parameter tests
# ---------------------------------------------------------------------------


def test_similar_limit_is_forwarded_to_solr(client, mock_requests_get):
    """The limit parameter controls rows sent to Solr kNN query."""
    _setup_similar(mock_requests_get)

    client.get("/similar/?id=abc123&limit=3")

    second_call_params = mock_requests_get.call_args_list[1].kwargs.get(
        "params", {}
    )
    assert second_call_params.get("rows") == 3


def test_similar_min_score_filters_results(client, mock_requests_get):
    """Results with score below min_score must be excluded from the response."""
    source_response = _solr_response([SOURCE_DOC])
    # Return two docs: one with score 0.92 and one with score 0.50.
    low_score_doc = {**SIMILAR_DOCS[1], "score": 0.50}
    similar_response = _solr_response([SIMILAR_DOCS[0], low_score_doc])
    mock_requests_get.side_effect = [source_response, similar_response]

    response = client.get("/similar/?id=abc123&min_score=0.8")

    assert response.status_code == 200
    scores = [r["score"] for r in response.json()["results"]]
    assert all(s >= 0.8 for s in scores)


def test_similar_zero_min_score_does_not_filter(client, mock_requests_get):
    """With min_score=0 (default), all Solr results are included."""
    _setup_similar(mock_requests_get)

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 200
    assert len(response.json()["results"]) == len(SIMILAR_DOCS)


# ---------------------------------------------------------------------------
# Solr kNN query format
# ---------------------------------------------------------------------------


def test_similar_uses_knn_query_parser(client, mock_requests_get):
    """The kNN Solr query must use the {!knn} parser against embedding_v."""
    _setup_similar(mock_requests_get)

    client.get("/similar/?id=abc123")

    second_call_params = mock_requests_get.call_args_list[1].kwargs.get("params", {})
    q = second_call_params.get("q", "")
    assert "{!knn" in q
    assert "embedding_v" in q


def test_similar_vector_field_retrieved_from_source_doc(client, mock_requests_get):
    """The first Solr call must request the embedding_v field."""
    _setup_similar(mock_requests_get)

    client.get("/similar/?id=abc123")

    first_call_params = mock_requests_get.call_args_list[0].kwargs.get("params", {})
    fl = first_call_params.get("fl", "")
    assert "embedding_v" in fl


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_similar_returns_404_for_unknown_id(client, mock_requests_get):
    """A document ID with no Solr match must return HTTP 404."""
    mock_requests_get.return_value = _solr_response([])

    response = client.get("/similar/?id=nonexistent-id")

    assert response.status_code == 404


def test_similar_returns_422_when_embedding_missing(client, mock_requests_get):
    """A document without an embedding must return HTTP 422."""
    doc_no_vector = {k: v for k, v in SOURCE_DOC.items() if k != "embedding_v"}
    mock_requests_get.return_value = _solr_response([doc_no_vector])

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 422


def test_similar_returns_502_on_solr_error(client, mock_requests_get):
    """A Solr communication error must return HTTP 502."""
    mock_requests_get.return_value = _solr_error_response(500)

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 502


def test_similar_returns_empty_list_when_no_similar_found(client, mock_requests_get):
    """When Solr returns no kNN matches the endpoint returns an empty results list."""
    source_response = _solr_response([SOURCE_DOC])
    empty_response = _solr_response([])
    mock_requests_get.side_effect = [source_response, empty_response]

    response = client.get("/similar/?id=abc123")

    assert response.status_code == 200
    assert response.json()["results"] == []
