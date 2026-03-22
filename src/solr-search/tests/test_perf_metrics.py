"""Tests for the in-memory rolling-window performance metrics store."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from perf_metrics import PerfMetricsStore, TimedSample, _percentile, _summarize  # noqa: E402
from tests.auth_helpers import create_authenticated_client  # noqa: E402

_TEST_ADMIN_KEY = "test-perf-metrics-key"


def _get_admin_client():
    client = create_authenticated_client()
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    """Patch ADMIN_API_KEY so admin endpoints are accessible in these tests."""
    with patch("admin_auth._get_admin_api_key", return_value=_TEST_ADMIN_KEY):
        yield


# ---------------------------------------------------------------------------
# Unit tests — PerfMetricsStore
# ---------------------------------------------------------------------------


class TestTimedSample:
    def test_frozen_dataclass(self) -> None:
        s = TimedSample(timestamp=1.0, value=0.5)
        assert s.timestamp == 1.0
        assert s.value == 0.5
        with pytest.raises(AttributeError):
            s.timestamp = 2.0  # type: ignore[misc]


class TestPercentile:
    def test_empty_list_returns_zero(self) -> None:
        assert _percentile([], 50) == 0.0

    def test_single_value(self) -> None:
        assert _percentile([1.0], 99) == 1.0

    def test_median_of_sorted_list(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile(values, 50) == 3.0

    def test_p95_of_100_values(self) -> None:
        values = list(range(1, 101))
        result = _percentile([float(v) for v in values], 95)
        assert result >= 95.0


class TestSummarize:
    def test_empty_samples(self) -> None:
        result = _summarize([])
        assert result == {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}

    def test_single_sample(self) -> None:
        result = _summarize([TimedSample(0, 0.123)])
        assert result["count"] == 1
        assert result["avg"] == 0.123
        assert result["p50"] == 0.123

    def test_multiple_samples(self) -> None:
        samples = [TimedSample(i, float(i)) for i in range(1, 11)]
        result = _summarize(samples)
        assert result["count"] == 10
        assert result["avg"] == 5.5
        assert result["p50"] > 0


class TestPerfMetricsStore:
    def test_new_store_has_empty_snapshot(self) -> None:
        store = PerfMetricsStore()
        snap = store.snapshot()
        assert snap["collections"] == {}
        assert snap["window_seconds"] == 3600
        assert snap["uptime_seconds"] >= 0

    def test_record_request_basic(self) -> None:
        store = PerfMetricsStore()
        store.record_request("books", 0.5, solr_latency_s=0.3)
        snap = store.snapshot()
        assert "books" in snap["collections"]
        col = snap["collections"]["books"]
        assert col["request_count"] == 1
        assert col["error_count"] == 0
        assert col["latency"]["count"] == 1
        assert col["latency"]["avg"] == 0.5
        assert col["solr_latency"]["count"] == 1
        assert col["embedding_latency"]["count"] == 0

    def test_record_request_with_embedding_and_solr(self) -> None:
        store = PerfMetricsStore()
        store.record_request("books_e5base", 1.0, embedding_latency_s=0.4, solr_latency_s=0.6)
        col = store.snapshot()["collections"]["books_e5base"]
        assert col["embedding_latency"]["count"] == 1
        assert col["solr_latency"]["count"] == 1

    def test_error_tracking(self) -> None:
        store = PerfMetricsStore()
        store.record_request("books", 0.1, error=True)
        store.record_request("books", 0.2)
        col = store.snapshot()["collections"]["books"]
        assert col["request_count"] == 2
        assert col["error_count"] == 1
        assert col["error_rate"] == 0.5

    def test_record_error_standalone(self) -> None:
        store = PerfMetricsStore()
        store.record_error("books")
        col = store.snapshot()["collections"]["books"]
        assert col["error_count"] == 1
        assert col["request_count"] == 0

    def test_multiple_collections(self) -> None:
        store = PerfMetricsStore()
        store.record_request("books", 0.1)
        store.record_request("books_e5base", 0.2)
        snap = store.snapshot()
        assert set(snap["collections"].keys()) == {"books", "books_e5base"}

    def test_reset_clears_all_data(self) -> None:
        store = PerfMetricsStore()
        store.record_request("books", 0.5)
        store.record_error("books")
        store.reset()
        snap = store.snapshot()
        assert snap["collections"] == {}

    def test_rolling_window_prunes_old_samples(self) -> None:
        store = PerfMetricsStore(window_seconds=1)
        # Inject an old sample by manipulating internals
        old_ts = time.monotonic() - 10
        store._buckets["books"].request_latencies.append(TimedSample(old_ts, 9.9))
        store._buckets["books"].request_count = 1
        # Fresh sample
        store.record_request("books", 0.1)
        snap = store.snapshot()
        col = snap["collections"]["books"]
        # Old sample should be pruned from latency list
        assert col["latency"]["count"] == 1
        assert col["latency"]["avg"] == 0.1

    def test_custom_window_seconds(self) -> None:
        store = PerfMetricsStore(window_seconds=300)
        assert store.snapshot()["window_seconds"] == 300

    def test_error_rate_zero_when_no_errors(self) -> None:
        store = PerfMetricsStore()
        store.record_request("books", 0.1)
        col = store.snapshot()["collections"]["books"]
        assert col["error_rate"] == 0.0

    def test_error_rate_with_no_requests(self) -> None:
        store = PerfMetricsStore()
        store.record_error("books")
        col = store.snapshot()["collections"]["books"]
        # error_count=1, request_count=0 -> max(0,1) = 1 -> rate=1.0
        assert col["error_rate"] == 1.0


class TestPerfMetricsThreadSafety:
    def test_concurrent_record_requests(self) -> None:
        store = PerfMetricsStore()
        num_threads = 8
        requests_per_thread = 100
        barrier = threading.Barrier(num_threads)

        def worker(collection: str) -> None:
            barrier.wait()
            for i in range(requests_per_thread):
                store.record_request(
                    collection,
                    0.01 * i,
                    embedding_latency_s=0.005 * i,
                    solr_latency_s=0.005 * i,
                )

        threads = []
        for i in range(num_threads):
            col = "books" if i % 2 == 0 else "books_e5base"
            t = threading.Thread(target=worker, args=(col,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        snap = store.snapshot()
        books = snap["collections"]["books"]
        e5 = snap["collections"]["books_e5base"]
        assert books["request_count"] == (num_threads // 2) * requests_per_thread
        assert e5["request_count"] == (num_threads // 2) * requests_per_thread

    def test_concurrent_record_and_snapshot(self) -> None:
        store = PerfMetricsStore()
        stop_event = threading.Event()
        snapshots: list[dict] = []

        def writer() -> None:
            i = 0
            while not stop_event.is_set():
                store.record_request("books", 0.01 * (i % 100))
                i += 1

        def reader() -> None:
            while not stop_event.is_set():
                snap = store.snapshot()
                snapshots.append(snap)

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)
        writer_thread.start()
        reader_thread.start()
        time.sleep(0.2)
        stop_event.set()
        writer_thread.join()
        reader_thread.join()

        # No crashes or corrupted data
        assert len(snapshots) > 0
        for snap in snapshots:
            assert "collections" in snap
            assert "uptime_seconds" in snap

    def test_concurrent_reset_and_record(self) -> None:
        store = PerfMetricsStore()
        stop_event = threading.Event()

        def writer() -> None:
            while not stop_event.is_set():
                store.record_request("books", 0.1)

        def resetter() -> None:
            while not stop_event.is_set():
                store.reset()

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=resetter),
        ]
        for t in threads:
            t.start()
        time.sleep(0.2)
        stop_event.set()
        for t in threads:
            t.join()

        # No crashes — store is in a valid state
        snap = store.snapshot()
        assert "collections" in snap


# ---------------------------------------------------------------------------
# Endpoint integration tests — /v1/admin/metrics and /v1/admin/metrics/reset
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_perf_metrics():
    """Ensure perf_metrics singleton is clean for every test."""
    from perf_metrics import perf_metrics

    perf_metrics.reset()
    yield
    perf_metrics.reset()


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_admin_metrics_endpoint_returns_json(
    mock_solr_post: MagicMock,
    _s: MagicMock,
    _i: MagicMock,
    _q: MagicMock,
    _e: MagicMock,
) -> None:
    client = _get_admin_client()
    response = client.get("/v1/admin/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert "window_seconds" in data
    assert "collections" in data


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_admin_metrics_includes_search_data(
    mock_solr_post: MagicMock,
    _s: MagicMock,
    _i: MagicMock,
    _q: MagicMock,
    _e: MagicMock,
) -> None:
    from perf_metrics import perf_metrics

    perf_metrics.record_request("books", 0.5, solr_latency_s=0.3, embedding_latency_s=0.1)
    perf_metrics.record_request("books_e5base", 0.8, solr_latency_s=0.4, embedding_latency_s=0.3)

    client = _get_admin_client()
    response = client.get("/v1/admin/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "books" in data["collections"]
    assert "books_e5base" in data["collections"]
    assert data["collections"]["books"]["request_count"] == 1
    assert data["collections"]["books"]["latency"]["avg"] == 0.5


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_admin_metrics_reset_clears_data(
    mock_solr_post: MagicMock,
    _s: MagicMock,
    _i: MagicMock,
    _q: MagicMock,
    _e: MagicMock,
) -> None:
    from perf_metrics import perf_metrics

    perf_metrics.record_request("books", 0.5)

    client = _get_admin_client()
    # Verify data exists
    response = client.get("/v1/admin/metrics")
    assert response.json()["collections"]["books"]["request_count"] == 1

    # Reset
    reset_response = client.post("/v1/admin/metrics/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "ok"

    # Verify cleared
    response = client.get("/v1/admin/metrics")
    assert response.json()["collections"] == {}


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_admin_metrics_rejects_non_admin_jwt(
    mock_solr_post: MagicMock,
    _s: MagicMock,
    _i: MagicMock,
    _q: MagicMock,
    _e: MagicMock,
) -> None:
    # Non-admin JWT user should be rejected
    from auth import AuthenticatedUser

    non_admin = AuthenticatedUser(id=2, username="reader", role="user")
    client = create_authenticated_client(user=non_admin)
    response = client.get("/v1/admin/metrics")
    assert response.status_code == 401


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_admin_metrics_not_in_openapi_schema(
    mock_solr_post: MagicMock,
    _s: MagicMock,
    _i: MagicMock,
    _q: MagicMock,
    _e: MagicMock,
) -> None:
    client = _get_admin_client()
    response = client.get("/openapi.json")
    schema = response.json()
    paths = schema.get("paths", {})
    assert "/v1/admin/metrics" not in paths
    assert "/v1/admin/metrics/reset" not in paths


@patch("main._embeddings_available", return_value=True)
@patch("main._get_indexing_queue_depth", return_value=0)
@patch(
    "main._get_indexing_status_details",
    return_value=({"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}, set()),
)
@patch("main._get_solr_status", return_value={"status": "ok", "nodes": 3, "docs_indexed": 0})
@patch("main.requests.post")
def test_search_records_perf_metrics(
    mock_solr_post: MagicMock,
    _s: MagicMock,
    _i: MagicMock,
    _q: MagicMock,
    _e: MagicMock,
) -> None:
    """Verify that a search request records timing data in perf_metrics."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": {"numFound": 1, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_post.return_value = mock_response

    client = _get_admin_client()
    search_resp = client.get("/search", params={"q": "test", "mode": "keyword"})
    assert search_resp.status_code == 200

    from perf_metrics import perf_metrics

    snap = perf_metrics.snapshot()
    assert "books" in snap["collections"]
    col = snap["collections"]["books"]
    assert col["request_count"] == 1
    assert col["latency"]["count"] == 1
    assert col["solr_latency"]["count"] == 1
