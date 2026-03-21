from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from metrics import METRICS_CONTENT_TYPE, metrics_registry  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

PROMETHEUS_SAMPLE_RE = re.compile(
    r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]+\})? [-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?$"
)


@pytest.fixture(autouse=True)
def reset_metrics() -> None:
    metrics_registry.reset()
    yield
    metrics_registry.reset()


@pytest.fixture
def client() -> TestClient:
    return create_authenticated_client()


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=7)
@patch("main._get_indexing_status_details")
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 42})
def test_metrics_endpoint_returns_prometheus_format(
    _mock_solr_status: MagicMock,
    mock_indexing_status_details: MagicMock,
    _mock_queue_depth: MagicMock,
    _mock_embeddings_available: MagicMock,
    client: TestClient,
) -> None:
    metrics_registry.increment_search_request("keyword")
    metrics_registry.observe_search_latency("keyword", 0.2)
    mock_indexing_status_details.return_value = (
        {"total_discovered": 3, "indexed": 1, "failed": 1, "pending": 1},
        {"doc:failed-1"},
    )

    response = client.get("/v1/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"] == METRICS_CONTENT_TYPE

    lines = [line for line in response.text.strip().splitlines() if line]
    assert "# HELP aithena_search_requests_total Total number of search requests by mode." in lines
    assert "# TYPE aithena_search_requests_total counter" in lines
    assert 'aithena_search_requests_total{mode="keyword"} 1' in lines
    assert 'aithena_indexing_queue_depth 7' in lines
    assert 'aithena_indexing_failures_total 1' in lines
    assert 'aithena_embeddings_available 1' in lines
    assert 'aithena_solr_live_nodes 3' in lines
    assert any(
        line.startswith('aithena_search_latency_seconds_bucket{mode="keyword",le="0.25"} 1')
        for line in lines
    )

    for line in lines:
        if line.startswith("# "):
            continue
        assert PROMETHEUS_SAMPLE_RE.match(line), f"Invalid Prometheus sample line: {line}"


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_search_requests_counter_increments(
    mock_solr_get: MagicMock,
    _mock_solr_status: MagicMock,
    _mock_indexing_status_details: MagicMock,
    _mock_queue_depth: MagicMock,
    _mock_embeddings_available: MagicMock,
    client: TestClient,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": {"numFound": 1, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    search_response = client.get("/search", params={"q": "folklore", "mode": "keyword"})
    metrics_response = client.get("/v1/metrics")

    assert search_response.status_code == 200
    assert metrics_response.status_code == 200
    assert 'aithena_search_requests_total{mode="keyword"} 1' in metrics_response.text
    assert 'aithena_search_requests_total{mode="semantic"} 0' in metrics_response.text
    assert 'aithena_search_requests_total{mode="hybrid"} 0' in metrics_response.text
