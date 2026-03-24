"""Tests for the benchmark runner logic.

All API calls are mocked — these tests validate the runner's query
execution, metric computation, serialization, and report formatting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_benchmark import (
    BenchmarkReport,
    QueryResult,
    compute_summary,
    execute_query,
    format_summary,
    load_queries,
    query_result_to_dict,
    report_to_dict,
    run_benchmark,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_queries_file(tmp_path: Path) -> Path:
    """Create a minimal benchmark queries file."""
    data = {
        "version": "2.0.0",
        "categories": {
            "simple_keyword": {
                "description": "Simple queries",
                "queries": [
                    {"id": "sk-01", "query": "machine learning", "notes": "test"},
                    {"id": "sk-02", "query": "python", "notes": "test"},
                ],
            },
            "edge_cases": {
                "description": "Edge cases",
                "queries": [
                    {"id": "ec-01", "query": "a", "notes": "single char"},
                ],
            },
        },
    }
    path = tmp_path / "queries.json"
    path.write_text(json.dumps(data))
    return path


def _make_query_result(
    query_id: str = "sk-01",
    query: str = "machine learning",
    collection: str = "books",
    mode: str = "semantic",
    top_k_ids: list[str] | None = None,
    top_k_scores: list[float] | None = None,
    total_results: int = 100,
    latency_ms: float = 50.0,
    degraded: bool = False,
    error: str | None = None,
) -> QueryResult:
    return QueryResult(
        query_id=query_id,
        query=query,
        collection=collection,
        mode=mode,
        top_k_ids=top_k_ids or ["d1", "d2", "d3"],
        top_k_scores=top_k_scores or [0.9, 0.8, 0.7],
        total_results=total_results,
        latency_ms=latency_ms,
        degraded=degraded,
        error=error,
    )


# ---------------------------------------------------------------------------
# load_queries
# ---------------------------------------------------------------------------

class TestLoadQueries:
    def test_loads_and_flattens_queries(self, sample_queries_file: Path) -> None:
        queries = load_queries(sample_queries_file)
        assert len(queries) == 3
        assert queries[0]["id"] == "sk-01"
        assert queries[0]["category"] == "simple_keyword"

    def test_all_queries_have_required_fields(self, sample_queries_file: Path) -> None:
        queries = load_queries(sample_queries_file)
        for q in queries:
            assert "id" in q
            assert "query" in q
            assert "category" in q

    def test_loads_production_queries(self) -> None:
        """Verify the actual queries.json is valid and has 30 queries."""
        path = Path(__file__).resolve().parent.parent / "queries.json"
        if path.exists():
            queries = load_queries(path)
            assert len(queries) == 30


# ---------------------------------------------------------------------------
# execute_query (mocked HTTP)
# ---------------------------------------------------------------------------

class TestExecuteQuery:
    @patch("run_benchmark.requests.get")
    def test_successful_query(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": "doc1", "score": 0.95},
                {"id": "doc2", "score": 0.80},
            ],
            "total_results": 42,
            "degraded": False,
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = execute_query(
            "http://localhost:8080", "test query", "sk-01", "books", "semantic",
        )

        assert result.top_k_ids == ["doc1", "doc2"]
        assert result.top_k_scores == [0.95, 0.80]
        assert result.total_results == 42
        assert result.error is None
        assert result.latency_ms > 0

    @patch("run_benchmark.requests.get")
    def test_query_with_collection_parameter(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [], "total_results": 0}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        execute_query(
            "http://localhost:8080", "test", "sk-01", "books", "semantic",
        )

        call_url = mock_get.call_args[0][0]
        assert "collection=books" in call_url
        assert "mode=semantic" in call_url

    @patch("run_benchmark.requests.get")
    def test_http_error_captured(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = ConnectionError("Connection refused")

        result = execute_query(
            "http://localhost:8080", "test", "sk-01", "books", "keyword",
        )

        assert result.error is not None
        assert "Connection refused" in result.error
        assert result.top_k_ids == []

    @patch("run_benchmark.requests.get")
    def test_degraded_flag_captured(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": "d1", "score": 1.0}],
            "total_results": 1,
            "degraded": True,
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = execute_query(
            "http://localhost:8080", "test", "sk-01", "books", "hybrid",
        )
        assert result.degraded is True


# ---------------------------------------------------------------------------
# compute_summary
# ---------------------------------------------------------------------------

class TestComputeSummary:
    def test_summary_by_mode(self) -> None:
        results = [
            _make_query_result(query_id="sk-01", mode="semantic", latency_ms=50.0, total_results=10),
            _make_query_result(query_id="sk-02", mode="semantic", latency_ms=40.0, total_results=20),
        ]
        summary = compute_summary(results)

        assert "semantic" in summary["by_mode"]
        mode_stats = summary["by_mode"]["semantic"]
        assert mode_stats["query_count"] == 2
        assert mode_stats["mean_latency_ms"] == 45.0
        assert mode_stats["error_count"] == 0

    def test_summary_by_category(self) -> None:
        results = [
            _make_query_result(query_id="sk-01", mode="keyword", latency_ms=30.0),
            _make_query_result(query_id="ml-01", mode="keyword", latency_ms=60.0),
        ]
        summary = compute_summary(results)

        assert "simple_keyword" in summary["by_category"]
        assert "multilingual" in summary["by_category"]

    def test_errors_counted(self) -> None:
        results = [
            _make_query_result(query_id="sk-01", mode="keyword", error="connection refused"),
        ]
        summary = compute_summary(results)
        assert summary["by_mode"]["keyword"]["error_count"] == 1

    def test_p95_latency(self) -> None:
        results = [
            _make_query_result(query_id=f"sk-{i:02d}", mode="semantic", latency_ms=float(i * 10))
            for i in range(1, 21)
        ]
        summary = compute_summary(results)
        assert summary["by_mode"]["semantic"]["p95_latency_ms"] is not None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_query_result_to_dict(self) -> None:
        qr = _make_query_result(collection="books", latency_ms=55.123)
        d = query_result_to_dict(qr)
        assert d["collection"] == "books"
        assert d["latency_ms"] == 55.12
        json.dumps(d)  # Verify JSON-serializable

    def test_report_to_dict_json_serializable(self) -> None:
        report = BenchmarkReport(
            timestamp="2026-01-01T00:00:00Z",
            base_url="http://localhost:8080",
            queries_file="queries.json",
            collection="books",
            total_queries=2,
            modes_tested=["semantic"],
            results=[_make_query_result()],
            summary={"by_mode": {}, "by_category": {}},
        )
        d = report_to_dict(report)
        serialized = json.dumps(d)
        assert "sk-01" in serialized
        assert d["collection"] == "books"


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:
    def test_format_includes_key_sections(self) -> None:
        report = BenchmarkReport(
            timestamp="2026-01-01T00:00:00Z",
            base_url="http://localhost:8080",
            collection="books",
            total_queries=1,
            modes_tested=["semantic"],
            results=[_make_query_result(latency_ms=50.0)],
            summary={
                "by_mode": {
                    "semantic": {
                        "query_count": 1,
                        "mean_latency_ms": 50.0,
                        "median_latency_ms": 50.0,
                        "p95_latency_ms": 50.0,
                        "mean_result_count": 100.0,
                        "error_count": 0,
                    },
                },
                "by_category": {
                    "simple_keyword": {"query_count": 1, "mean_latency_ms": 50.0},
                },
            },
        )
        text = format_summary(report)

        assert "BENCHMARK REPORT" in text
        assert "semantic" in text
        assert "Latency" in text
        assert "simple_keyword" in text
        assert "Collection:   books" in text

    def test_errors_section_shown(self) -> None:
        report = BenchmarkReport(
            timestamp="2026-01-01T00:00:00Z",
            base_url="http://localhost:8080",
            collection="books",
            total_queries=1,
            modes_tested=["semantic"],
            results=[_make_query_result(error="Connection refused")],
            summary={"by_mode": {}, "by_category": {}},
        )
        text = format_summary(report)
        assert "Errors (1)" in text
        assert "Connection refused" in text


# ---------------------------------------------------------------------------
# run_benchmark (integration with mocked API)
# ---------------------------------------------------------------------------

class TestRunBenchmark:
    @patch("run_benchmark.execute_query")
    def test_runs_all_combinations(
        self, mock_execute: MagicMock, sample_queries_file: Path,
    ) -> None:
        mock_execute.return_value = _make_query_result()

        report = run_benchmark(
            base_url="http://localhost:8080",
            queries_path=sample_queries_file,
            modes=("keyword", "semantic"),
        )

        # 3 queries x 2 modes = 6 executions (one collection)
        assert mock_execute.call_count == 6
        assert report.total_queries == 3
        assert len(report.results) == 6
        assert set(report.modes_tested) == {"keyword", "semantic"}

    @patch("run_benchmark.execute_query")
    def test_collection_passed_correctly(
        self, mock_execute: MagicMock, sample_queries_file: Path,
    ) -> None:
        mock_execute.return_value = _make_query_result()

        run_benchmark(
            base_url="http://test:8080",
            queries_path=sample_queries_file,
            modes=("keyword",),
            collection="books",
        )

        collections_used = {call.args[3] for call in mock_execute.call_args_list}
        assert collections_used == {"books"}

    @patch("run_benchmark.execute_query")
    def test_custom_collection(
        self, mock_execute: MagicMock, sample_queries_file: Path,
    ) -> None:
        mock_execute.return_value = _make_query_result(collection="my_collection")

        report = run_benchmark(
            base_url="http://test:8080",
            queries_path=sample_queries_file,
            modes=("keyword",),
            collection="my_collection",
        )

        assert report.collection == "my_collection"
        collections_used = {call.args[3] for call in mock_execute.call_args_list}
        assert collections_used == {"my_collection"}
