"""Tests for the benchmark runner logic.

All API calls are mocked — these tests validate the runner's comparison
logic, metric computation, serialization, and report formatting.
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
    QueryComparison,
    QueryResult,
    compare_results,
    comparison_to_dict,
    compute_summary,
    execute_query,
    format_summary,
    jaccard_similarity,
    load_queries,
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
        "version": "1.0.0",
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
# jaccard_similarity
# ---------------------------------------------------------------------------

class TestJaccardSimilarity:
    def test_identical_sets(self) -> None:
        assert jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self) -> None:
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self) -> None:
        # {a,b,c} ∩ {b,c,d} = {b,c}, union = {a,b,c,d} → 2/4 = 0.5
        assert jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"}) == 0.5

    def test_empty_sets(self) -> None:
        assert jaccard_similarity(set(), set()) == 1.0

    def test_one_empty(self) -> None:
        assert jaccard_similarity({"a"}, set()) == 0.0


# ---------------------------------------------------------------------------
# compare_results
# ---------------------------------------------------------------------------

class TestCompareResults:
    def test_full_overlap(self) -> None:
        baseline = _make_query_result(collection="books", top_k_ids=["d1", "d2", "d3"])
        candidate = _make_query_result(collection="books_e5base", top_k_ids=["d1", "d2", "d3"])
        comp = compare_results(baseline, candidate, "simple_keyword")

        assert comp.jaccard_similarity == 1.0
        assert sorted(comp.overlap_ids) == ["d1", "d2", "d3"]
        assert comp.baseline_only_ids == []
        assert comp.candidate_only_ids == []

    def test_no_overlap(self) -> None:
        baseline = _make_query_result(collection="books", top_k_ids=["d1", "d2"])
        candidate = _make_query_result(collection="books_e5base", top_k_ids=["d3", "d4"])
        comp = compare_results(baseline, candidate, "simple_keyword")

        assert comp.jaccard_similarity == 0.0
        assert comp.overlap_ids == []
        assert sorted(comp.baseline_only_ids) == ["d1", "d2"]
        assert sorted(comp.candidate_only_ids) == ["d3", "d4"]

    def test_partial_overlap(self) -> None:
        baseline = _make_query_result(collection="books", top_k_ids=["d1", "d2", "d3"])
        candidate = _make_query_result(collection="books_e5base", top_k_ids=["d2", "d3", "d4"])
        comp = compare_results(baseline, candidate, "multilingual")

        assert comp.jaccard_similarity == 0.5
        assert sorted(comp.overlap_ids) == ["d2", "d3"]
        assert comp.baseline_only_ids == ["d1"]
        assert comp.candidate_only_ids == ["d4"]

    def test_metadata_preserved(self) -> None:
        baseline = _make_query_result(query_id="nl-01", query="how does X work?", mode="hybrid")
        candidate = _make_query_result(query_id="nl-01", query="how does X work?", mode="hybrid")
        comp = compare_results(baseline, candidate, "natural_language")

        assert comp.query_id == "nl-01"
        assert comp.query == "how does X work?"
        assert comp.mode == "hybrid"
        assert comp.category == "natural_language"


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
            "http://localhost:8080", "test", "sk-01", "books_e5base", "semantic",
        )

        call_url = mock_get.call_args[0][0]
        assert "collection=books_e5base" in call_url
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
        comps = [
            QueryComparison(
                query_id="sk-01", query="q1", category="simple_keyword", mode="semantic",
                baseline=_make_query_result(latency_ms=50.0),
                candidate=_make_query_result(latency_ms=60.0),
                jaccard_similarity=0.8,
            ),
            QueryComparison(
                query_id="sk-02", query="q2", category="simple_keyword", mode="semantic",
                baseline=_make_query_result(latency_ms=40.0),
                candidate=_make_query_result(latency_ms=55.0),
                jaccard_similarity=0.6,
            ),
        ]
        summary = compute_summary(comps)

        assert "semantic" in summary["by_mode"]
        mode_stats = summary["by_mode"]["semantic"]
        assert mode_stats["query_count"] == 2
        assert mode_stats["mean_jaccard"] == 0.7
        assert mode_stats["error_count"] == 0

    def test_summary_by_category(self) -> None:
        comps = [
            QueryComparison(
                query_id="sk-01", query="q1", category="simple_keyword", mode="keyword",
                jaccard_similarity=0.5,
            ),
            QueryComparison(
                query_id="ml-01", query="q2", category="multilingual", mode="keyword",
                jaccard_similarity=0.3,
            ),
        ]
        summary = compute_summary(comps)

        assert "simple_keyword" in summary["by_category"]
        assert summary["by_category"]["simple_keyword"]["mean_jaccard"] == 0.5
        assert summary["by_category"]["multilingual"]["mean_jaccard"] == 0.3

    def test_errors_counted(self) -> None:
        comps = [
            QueryComparison(
                query_id="sk-01", query="q1", category="simple_keyword", mode="keyword",
                baseline=_make_query_result(error="connection refused"),
                candidate=_make_query_result(),
                jaccard_similarity=0.0,
            ),
        ]
        summary = compute_summary(comps)
        assert summary["by_mode"]["keyword"]["error_count"] == 1


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_comparison_to_dict_roundtrip(self) -> None:
        comp = QueryComparison(
            query_id="sk-01", query="test", category="simple_keyword", mode="semantic",
            baseline=_make_query_result(collection="books"),
            candidate=_make_query_result(collection="books_e5base"),
            jaccard_similarity=0.5,
            overlap_ids=["d2"],
            baseline_only_ids=["d1"],
            candidate_only_ids=["d3"],
        )
        d = comparison_to_dict(comp)
        assert d["query_id"] == "sk-01"
        assert d["baseline"]["collection"] == "books"
        assert d["candidate"]["collection"] == "books_e5base"
        # Verify JSON-serializable
        json.dumps(d)

    def test_report_to_dict_json_serializable(self) -> None:
        report = BenchmarkReport(
            timestamp="2026-01-01T00:00:00Z",
            base_url="http://localhost:8080",
            queries_file="queries.json",
            total_queries=2,
            modes_tested=["semantic"],
            comparisons=[
                QueryComparison(
                    query_id="sk-01", query="test", category="test", mode="semantic",
                    baseline=_make_query_result(),
                    candidate=_make_query_result(collection="books_e5base"),
                    jaccard_similarity=1.0,
                ),
            ],
            summary={"by_mode": {}, "by_category": {}},
        )
        d = report_to_dict(report)
        serialized = json.dumps(d)
        assert "sk-01" in serialized


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:
    def test_format_includes_key_sections(self) -> None:
        report = BenchmarkReport(
            timestamp="2026-01-01T00:00:00Z",
            base_url="http://localhost:8080",
            total_queries=1,
            modes_tested=["semantic"],
            comparisons=[
                QueryComparison(
                    query_id="sk-01", query="test query", category="simple_keyword",
                    mode="semantic",
                    baseline=_make_query_result(latency_ms=50.0),
                    candidate=_make_query_result(latency_ms=60.0),
                    jaccard_similarity=0.8,
                ),
            ],
            summary={
                "by_mode": {
                    "semantic": {
                        "query_count": 1,
                        "mean_jaccard": 0.8,
                        "median_jaccard": 0.8,
                        "min_jaccard": 0.8,
                        "max_jaccard": 0.8,
                        "baseline_mean_latency_ms": 50.0,
                        "candidate_mean_latency_ms": 60.0,
                        "baseline_p95_latency_ms": 50.0,
                        "candidate_p95_latency_ms": 60.0,
                        "error_count": 0,
                    },
                },
                "by_category": {
                    "simple_keyword": {"query_count": 1, "mean_jaccard": 0.8},
                },
            },
        )
        text = format_summary(report)

        assert "BENCHMARK REPORT" in text
        assert "semantic" in text
        assert "Jaccard" in text
        assert "Latency" in text
        assert "simple_keyword" in text

    def test_low_overlap_flagged(self) -> None:
        report = BenchmarkReport(
            timestamp="2026-01-01T00:00:00Z",
            base_url="http://localhost:8080",
            total_queries=1,
            modes_tested=["semantic"],
            comparisons=[
                QueryComparison(
                    query_id="ec-05", query="xyzzyplugh42", category="edge_cases",
                    mode="semantic", jaccard_similarity=0.1,
                ),
            ],
            summary={"by_mode": {}, "by_category": {}},
        )
        text = format_summary(report)
        assert "ec-05" in text
        assert "Low Overlap" in text


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

        # 3 queries × 2 modes = 6 comparisons, each calling execute_query twice
        assert mock_execute.call_count == 12  # 6 pairs × 2 collections
        assert report.total_queries == 3
        assert len(report.comparisons) == 6
        assert set(report.modes_tested) == {"keyword", "semantic"}

    @patch("run_benchmark.execute_query")
    def test_collections_passed_correctly(
        self, mock_execute: MagicMock, sample_queries_file: Path,
    ) -> None:
        mock_execute.return_value = _make_query_result()

        run_benchmark(
            base_url="http://test:8080",
            queries_path=sample_queries_file,
            modes=("keyword",),
        )

        collections_used = {call.args[3] for call in mock_execute.call_args_list}
        assert collections_used == {"books", "books_e5base"}
