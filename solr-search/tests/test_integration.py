from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


def get_client() -> TestClient:
    return TestClient(app)


@patch("main.requests.get")
def test_search_returns_results_with_mocked_solr(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "id": "doc1",
                    "title_s": "Catalan Folklore",
                    "author_s": "Joan Amades",
                    "year_i": 1950,
                    "category_s": "Folklore",
                    "language_detected_s": "ca",
                    "file_path_s": "amades/catalan_folklore.pdf",
                    "folder_path_s": "amades",
                    "page_count_i": 250,
                    "file_size_l": 5242880,
                    "score": 12.5,
                },
                {
                    "id": "doc2",
                    "title_s": "Rondalles Populars",
                    "author_s": "Joan Amades",
                    "year_i": 1952,
                    "category_s": "Folklore",
                    "language_s": "ca",
                    "file_path_s": "amades/rondalles.pdf",
                    "folder_path_s": "amades",
                    "page_count_i": 320,
                    "file_size_l": 6291456,
                    "score": 10.2,
                },
            ],
        },
        "highlighting": {
            "doc1": {
                "content": ["<em>folklore</em> traditions"],
            },
            "doc2": {
                "_text_": ["popular <em>tales</em>"],
            },
        },
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Joan Amades", 2],
                "category_s": ["Folklore", 2],
                "year_i": [1950, 1, 1952, 1],
                "language_detected_s": ["ca", 2],
                "language_s": [],
            }
        },
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/search", params={"q": "folklore", "page": 1, "page_size": 10})

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "folklore"
    assert data["total_results"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["results"]) == 2

    first_result = data["results"][0]
    assert first_result["id"] == "doc1"
    assert first_result["title"] == "Catalan Folklore"
    assert first_result["author"] == "Joan Amades"
    assert first_result["year"] == 1950
    assert first_result["highlights"] == ["<em>folklore</em> traditions"]

    facets = data["facets"]
    assert facets["author"] == [{"value": "Joan Amades", "count": 2}]
    assert facets["category"] == [{"value": "Folklore", "count": 2}]
    assert len(facets["year"]) == 2


@patch("main.requests.get")
def test_search_handles_empty_query(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/search", params={"q": ""})

    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] == 0
    assert data["results"] == []

    mock_solr_get.assert_called_once()
    call_args = mock_solr_get.call_args
    assert call_args[1]["params"]["q"] == "*:*"


@patch("main.requests.get")
def test_facets_endpoint_returns_facet_counts(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 5, "docs": []},
        "highlighting": {},
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author A", 3, "Author B", 2],
                "category_s": ["History", 4, "Science", 1],
                "year_i": [2020, 2, 2019, 3],
                "language_detected_s": ["en", 3, "ca", 2],
                "language_s": [],
            }
        },
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/facets", params={"q": "test"})

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "test"
    assert "facets" in data
    assert data["facets"]["author"] == [
        {"value": "Author A", "count": 3},
        {"value": "Author B", "count": 2},
    ]
    assert data["facets"]["category"] == [
        {"value": "History", "count": 4},
        {"value": "Science", "count": 1},
    ]


@patch("main.requests.get")
def test_search_handles_solr_timeout(mock_solr_get: MagicMock) -> None:
    import requests

    mock_solr_get.side_effect = requests.Timeout("Connection timeout")

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 504
    assert "Timed out" in response.json()["detail"]


@patch("main.requests.get")
def test_search_handles_solr_connection_error(mock_solr_get: MagicMock) -> None:
    import requests

    mock_solr_get.side_effect = requests.ConnectionError("Cannot connect to Solr")

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 502
    assert "failed" in response.json()["detail"]


@patch("main.requests.get")
def test_search_handles_invalid_solr_response(mock_solr_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 502
    assert "invalid JSON" in response.json()["detail"]


def test_health_endpoint_returns_ok() -> None:
    client = get_client()
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data


def test_info_endpoint_returns_service_info() -> None:
    client = get_client()
    response = client.get("/info")

    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "version" in data


@patch("main.requests.get")
def test_search_pagination_parameters_passed_correctly(mock_solr_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 100, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "test", "page": 3, "page_size": 25})

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert data["page_size"] == 25
    assert data["total_pages"] == 4

    mock_solr_get.assert_called_once()
    call_args = mock_solr_get.call_args
    assert call_args[1]["params"]["start"] == 50
    assert call_args[1]["params"]["rows"] == 25


@patch("main.requests.get")
def test_search_sorting_parameters_applied(mock_solr_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get(
        "/search", params={"q": "test", "sort_by": "year", "sort_order": "asc"}
    )

    assert response.status_code == 200

    mock_solr_get.assert_called_once()
    call_args = mock_solr_get.call_args
    assert call_args[1]["params"]["sort"] == "year_i asc"
