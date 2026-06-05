"""Tests for scalar quantization benchmark report comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compare_quantization import (  # noqa: E402
    build_output,
    compare_reports,
    format_summary,
    load_report,
    summarize,
)


def _result(query_id: str, mode: str, ids: list[str], latency_ms: float = 10.0) -> dict:
    return {
        "query_id": query_id,
        "query": "test",
        "collection": "books",
        "mode": mode,
        "top_k_ids": ids,
        "top_k_scores": [1.0] * len(ids),
        "total_results": len(ids),
        "latency_ms": latency_ms,
        "degraded": False,
        "error": None,
    }


def _report(results: list[dict]) -> dict:
    return {
        "timestamp": "2026-06-05T00:00:00Z",
        "base_url": "http://localhost:8080",
        "queries_file": "queries.json",
        "collection": "books",
        "total_queries": len(results),
        "modes_tested": sorted({r["mode"] for r in results}),
        "summary": {},
        "results": results,
    }


class TestCompareReports:
    def test_identical_results_have_full_recall(self) -> None:
        baseline = _report([_result("sk-01", "semantic", ["a", "b", "c"])])
        candidate = _report([_result("sk-01", "semantic", ["a", "b", "c"])])

        comparisons = compare_reports(baseline, candidate, top_k=3)

        assert len(comparisons) == 1
        assert comparisons[0].recall_at_k == 1.0
        assert comparisons[0].overlap_count == 3

    def test_partial_overlap_computes_recall_at_k(self) -> None:
        baseline = _report([_result("sk-01", "semantic", ["a", "b", "c", "d"])])
        candidate = _report([_result("sk-01", "semantic", ["a", "x", "c", "y"])])

        comparison = compare_reports(baseline, candidate, top_k=4)[0]

        assert comparison.recall_at_k == 0.5
        assert comparison.overlap_count == 2

    def test_missing_candidate_result_fails_comparison(self) -> None:
        baseline = _report([_result("sk-01", "hybrid", ["a", "b"])])
        candidate = _report([])

        comparison = compare_reports(baseline, candidate, top_k=2)[0]

        assert comparison.recall_at_k == 0.0
        assert comparison.candidate_error == "missing result"

    def test_latency_delta_is_reported(self) -> None:
        baseline = _report([_result("sk-01", "semantic", ["a"], latency_ms=100.0)])
        candidate = _report([_result("sk-01", "semantic", ["a"], latency_ms=125.0)])

        comparison = compare_reports(baseline, candidate, top_k=1)[0]

        assert comparison.latency_delta_pct == 25.0


class TestSummarize:
    def test_summary_passes_when_all_recalls_meet_threshold(self) -> None:
        comparisons = compare_reports(
            _report([_result("sk-01", "semantic", ["a", "b"])]),
            _report([_result("sk-01", "semantic", ["b", "a"])]),
            top_k=2,
        )

        summary = summarize(comparisons, min_recall=0.95)

        assert summary["passed"] is True
        assert summary["by_mode"]["semantic"]["mean_recall_at_k"] == 1.0

    def test_summary_fails_when_recall_below_threshold(self) -> None:
        comparisons = compare_reports(
            _report([_result("sk-01", "semantic", ["a", "b"])]),
            _report([_result("sk-01", "semantic", ["x", "y"])]),
            top_k=2,
        )

        summary = summarize(comparisons, min_recall=0.95)

        assert summary["passed"] is False
        assert summary["failures"][0]["query_id"] == "sk-01"
        assert summary["by_mode"]["semantic"]["queries_below_min_recall"] == ["sk-01"]


class TestOutput:
    def test_build_output_is_json_serializable(self) -> None:
        comparisons = compare_reports(
            _report([_result("sk-01", "keyword", ["a"])]),
            _report([_result("sk-01", "keyword", ["a"])]),
            top_k=1,
        )

        output = build_output(
            Path("results/float32.json"),
            Path("results/int8.json"),
            comparisons,
            top_k=1,
            min_recall=0.95,
        )

        assert output["summary"]["passed"] is True
        assert "sk-01" in json.dumps(output)

    def test_format_summary_includes_pass_fail(self) -> None:
        comparisons = compare_reports(
            _report([_result("sk-01", "keyword", ["a"])]),
            _report([_result("sk-01", "keyword", ["a"])]),
            top_k=1,
        )
        output = build_output(Path("baseline.json"), Path("candidate.json"), comparisons, top_k=1, min_recall=0.95)

        text = format_summary(output)

        assert "QUANTIZATION RECALL COMPARISON" in text
        assert "PASS" in text

    def test_load_report_rejects_invalid_shape(self, monkeypatch) -> None:
        class FakePath:
            def open(self, encoding: str):
                assert encoding == "utf-8"
                return self

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, *_args, **_kwargs):
                return "{}"

            def __str__(self) -> str:
                return "fake.json"

        monkeypatch.setattr(json, "load", lambda _f: {})

        try:
            load_report(FakePath())  # type: ignore[arg-type]
        except ValueError as exc:
            assert "results list" in str(exc)
        else:
            raise AssertionError("ValueError not raised")
