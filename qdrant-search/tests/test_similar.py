"""Tests for the /similar/ endpoint."""
from __future__ import annotations

from tests.conftest import (
    DUMMY_VECTOR,
    SIMILAR_PAYLOADS,
    SOURCE_PAYLOAD,
    _make_record,
    _make_scored_point,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_similar(mock_qdrant, source_id="abc-123", similar_ids=None):
    """Wire mock_qdrant so that retrieve returns the source point and search
    returns a list of similar scored points."""
    if similar_ids is None:
        similar_ids = ["id-1", "id-2"]

    source_record = _make_record(source_id, DUMMY_VECTOR, SOURCE_PAYLOAD)
    mock_qdrant.retrieve.return_value = [source_record]

    scored_points = [
        _make_scored_point(similar_ids[i], 0.9 - i * 0.1, SIMILAR_PAYLOADS[i])
        for i in range(min(len(similar_ids), len(SIMILAR_PAYLOADS)))
    ]
    mock_qdrant.search.return_value = scored_points

    return source_record, scored_points


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


def test_similar_returns_200_with_results(client, mock_qdrant):
    """Endpoint returns HTTP 200 and a non-empty results list."""
    _setup_similar(mock_qdrant)

    response = client.get("/similar/?id=abc-123")

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert len(body["results"]) > 0


def test_similar_result_contains_required_fields(client, mock_qdrant):
    """Each result must contain the fields required by the acceptance criteria."""
    _setup_similar(mock_qdrant)

    response = client.get("/similar/?id=abc-123")

    assert response.status_code == 200
    result = response.json()["results"][0]
    for field in ("id", "title", "author", "year", "category", "document_url", "score"):
        assert field in result, f"Missing field: {field}"


def test_similar_result_values_match_payload(client, mock_qdrant):
    """Result values are taken from the Qdrant point payload."""
    _setup_similar(mock_qdrant)

    response = client.get("/similar/?id=abc-123")

    result = response.json()["results"][0]
    expected = SIMILAR_PAYLOADS[0]
    assert result["title"] == expected["title"]
    assert result["author"] == expected["author"]
    assert result["year"] == expected["year"]
    assert result["category"] == expected["category"]
    assert result["score"] == 0.9


# ---------------------------------------------------------------------------
# Self-match exclusion
# ---------------------------------------------------------------------------


def test_similar_excludes_source_document(client, mock_qdrant):
    """The source document path must not appear in the results."""
    source_record = _make_record("abc-123", DUMMY_VECTOR, SOURCE_PAYLOAD)
    mock_qdrant.retrieve.return_value = [source_record]

    # Pretend Qdrant already filtered it via `must_not`; we verify the filter
    # is passed and the source path is absent from returned results.
    mock_qdrant.search.return_value = [
        _make_scored_point("id-1", 0.9, SIMILAR_PAYLOADS[0]),
    ]

    response = client.get("/similar/?id=abc-123")

    assert response.status_code == 200
    paths = [r["document_url"] for r in response.json()["results"]]
    assert SOURCE_PAYLOAD["path"] not in paths

    # Verify that the filter was passed to qdrant.search.
    _, search_kwargs = mock_qdrant.search.call_args
    query_filter = search_kwargs.get("query_filter")
    assert query_filter is not None, "No query_filter passed to qdrant.search"


def test_similar_deduplicates_chunks_from_same_book(client, mock_qdrant):
    """Multiple chunks from the same book must produce only one result entry."""
    source_record = _make_record("abc-123", DUMMY_VECTOR, SOURCE_PAYLOAD)
    mock_qdrant.retrieve.return_value = [source_record]

    # Two chunks from the same book, different pages.
    duplicate_payload = {**SIMILAR_PAYLOADS[0], "page": 3}
    mock_qdrant.search.return_value = [
        _make_scored_point("id-1", 0.95, SIMILAR_PAYLOADS[0]),
        _make_scored_point("id-2", 0.85, duplicate_payload),
        _make_scored_point("id-3", 0.80, SIMILAR_PAYLOADS[1]),
    ]

    response = client.get("/similar/?id=abc-123&limit=10")

    assert response.status_code == 200
    results = response.json()["results"]
    # Both Book B and Book C should appear, but Book B only once.
    paths = [r["document_url"] for r in results]
    assert paths.count(SIMILAR_PAYLOADS[0]["path"]) == 1
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Query parameter tests
# ---------------------------------------------------------------------------


def test_similar_limit_parameter(client, mock_qdrant):
    """limit=1 returns at most one result."""
    _setup_similar(mock_qdrant)

    response = client.get("/similar/?id=abc-123&limit=1")

    assert response.status_code == 200
    assert len(response.json()["results"]) <= 1


def test_similar_passes_min_score_threshold(client, mock_qdrant):
    """When min_score > 0, score_threshold is forwarded to qdrant.search."""
    _setup_similar(mock_qdrant)

    client.get("/similar/?id=abc-123&min_score=0.8")

    _, search_kwargs = mock_qdrant.search.call_args
    assert search_kwargs.get("score_threshold") == 0.8


def test_similar_zero_min_score_omits_threshold(client, mock_qdrant):
    """When min_score=0 (default), score_threshold is None (no filtering)."""
    _setup_similar(mock_qdrant)

    client.get("/similar/?id=abc-123")

    _, search_kwargs = mock_qdrant.search.call_args
    assert search_kwargs.get("score_threshold") is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_similar_returns_404_for_unknown_id(client, mock_qdrant):
    """A point ID that does not exist must return HTTP 404."""
    mock_qdrant.retrieve.return_value = []

    response = client.get("/similar/?id=nonexistent-id")

    assert response.status_code == 404


def test_similar_returns_400_on_qdrant_error(client, mock_qdrant):
    """A Qdrant retrieval error must return HTTP 400."""
    mock_qdrant.retrieve.side_effect = RuntimeError("Connection refused")

    response = client.get("/similar/?id=bad-id")

    assert response.status_code == 400


def test_similar_returns_empty_results_when_no_matches(client, mock_qdrant):
    """When no similar books exist the endpoint returns an empty results list."""
    source_record = _make_record("abc-123", DUMMY_VECTOR, SOURCE_PAYLOAD)
    mock_qdrant.retrieve.return_value = [source_record]
    mock_qdrant.search.return_value = []

    response = client.get("/similar/?id=abc-123")

    assert response.status_code == 200
    assert response.json()["results"] == []


# ---------------------------------------------------------------------------
# document_url construction
# ---------------------------------------------------------------------------


def test_similar_document_url_uses_payload_url_when_present(client, mock_qdrant):
    """If the payload already contains document_url it must be used verbatim."""
    payload_with_url = {
        **SIMILAR_PAYLOADS[0],
        "document_url": "https://cdn.example.com/books/bookb.pdf",
    }
    source_record = _make_record("abc-123", DUMMY_VECTOR, SOURCE_PAYLOAD)
    mock_qdrant.retrieve.return_value = [source_record]
    mock_qdrant.search.return_value = [_make_scored_point("id-1", 0.9, payload_with_url)]

    response = client.get("/similar/?id=abc-123")

    assert response.status_code == 200
    assert response.json()["results"][0]["document_url"] == payload_with_url["document_url"]


def test_similar_document_url_falls_back_to_path(client, mock_qdrant):
    """Without a prebuilt document_url and storage config, path is used."""
    import main  # noqa: PLC0415

    # Ensure no storage config is set for this test.
    original = main.STORAGE_ACCOUNT_NAME
    main.STORAGE_ACCOUNT_NAME = None
    try:
        source_record = _make_record("abc-123", DUMMY_VECTOR, SOURCE_PAYLOAD)
        mock_qdrant.retrieve.return_value = [source_record]
        mock_qdrant.search.return_value = [_make_scored_point("id-1", 0.9, SIMILAR_PAYLOADS[0])]

        response = client.get("/similar/?id=abc-123")

        assert response.status_code == 200
        assert response.json()["results"][0]["document_url"] == SIMILAR_PAYLOADS[0]["path"]
    finally:
        main.STORAGE_ACCOUNT_NAME = original
