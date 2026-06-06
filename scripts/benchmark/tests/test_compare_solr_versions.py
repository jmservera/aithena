"""Tests for paired Solr version benchmark comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compare_solr_versions import (  # noqa: E402
    analyze_claims,
    build_comparison,
    compare_modes,
    format_markdown,
    throughput_value,
    validate_evidence,
)


def _result(query_id: str, mode: str, latency_ms: float, error: str | None = None) -> dict:
    return {
        "query_id": query_id,
        "query": "test",
        "collection": "books",
        "mode": mode,
        "top_k_ids": [] if error else ["doc1"],
        "top_k_scores": [] if error else [1.0],
        "total_results": 0 if error else 1,
        "latency_ms": latency_ms,
        "degraded": False,
        "error": error,
    }


def _report(
    *,
    solr_version: str,
    corpus_id: str = "corpus-a",
    node: str = "bench-host",
    memory_bytes: int = 400,
    index_seconds: float = 100.0,
    results: list[dict] | None = None,
) -> dict:
    return {
        "timestamp": "2026-06-06T21:10:43Z",
        "base_url": "http://localhost:8080",
        "queries_file": "queries.json",
        "collection": "books",
        "total_queries": 1,
        "modes_tested": ["keyword"],
        "run_metadata": {
            "solr_version": solr_version,
            "host": {
                "node": node,
                "system": "Linux",
                "release": "test",
                "machine": "x86_64",
                "processor": "test-cpu",
            },
            "corpus": {"id": corpus_id, "document_count": 10, "bytes": 1234},
            "timings": {
                "startup_seconds": 5.0,
                "index_build_seconds": index_seconds,
                "vector_indexing_seconds": index_seconds / 2,
            },
            "throughput": {"concurrency": 8, "qps": 20.0},
            "docker_stats": {"solr": {"mem_usage_bytes": memory_bytes}},
        },
        "summary": {},
        "results": results if results is not None else [_result("sk-01", "keyword", 10.0)],
    }


class TestEvidenceValidation:
    def test_same_host_same_corpus_is_valid(self) -> None:
        evidence = validate_evidence(_report(solr_version="9.7"), _report(solr_version="10"))

        assert evidence["valid"] is True
        assert evidence["failures"] == []

    def test_host_mismatch_is_invalid(self) -> None:
        evidence = validate_evidence(
            _report(solr_version="9.7"),
            _report(solr_version="10", node="other-host"),
        )

        assert evidence["valid"] is False
        assert "host_mismatch" in evidence["failures"]

    def test_corpus_mismatch_is_invalid(self) -> None:
        evidence = validate_evidence(
            _report(solr_version="9.7"),
            _report(solr_version="10", corpus_id="corpus-b"),
        )

        assert evidence["valid"] is False
        assert "corpus_mismatch" in evidence["failures"]


class TestModeComparison:
    def test_compares_latency_and_errors_by_mode(self) -> None:
        solr9 = _report(
            solr_version="9.7",
            results=[_result("sk-01", "keyword", 10.0), _result("sk-02", "keyword", 20.0)],
        )
        solr10 = _report(
            solr_version="10",
            results=[
                _result("sk-01", "keyword", 15.0),
                _result("sk-02", "keyword", 25.0, error="boom"),
            ],
        )

        comparison = compare_modes(solr9, solr10)[0]

        assert comparison.mode == "keyword"
        assert comparison.solr9_query_count == 2
        assert comparison.solr10_error_count == 1
        assert comparison.solr9_mean_latency_ms == 15.0
        assert comparison.solr10_mean_latency_ms == 15.0


class TestClaims:
    def test_validates_claims_when_factors_meet_targets(self) -> None:
        solr9 = _report(solr_version="9.7", memory_bytes=400, index_seconds=400.0)
        solr10 = _report(solr_version="10", memory_bytes=100, index_seconds=10.0)

        claims = analyze_claims(solr9, solr10)

        assert claims["memory_4x"]["status"] == "validated"
        assert claims["indexing_40x"]["status"] == "validated"

    def test_marks_missing_claim_data_as_insufficient(self) -> None:
        solr9 = _report(solr_version="9.7")
        solr10 = _report(solr_version="10")
        solr10["run_metadata"].pop("docker_stats")

        claims = analyze_claims(solr9, solr10)

        assert claims["memory_4x"]["status"] == "insufficient_evidence"

    def test_throughput_value_preserves_ints(self) -> None:
        report = _report(solr_version="10")

        assert throughput_value(report, "concurrency") == 8
        assert isinstance(throughput_value(report, "concurrency"), int)
        assert throughput_value(report, "qps") == 20.0
        assert isinstance(throughput_value(report, "qps"), float)


class TestOutput:
    def test_build_comparison_from_files_and_format_markdown(self, tmp_path: Path) -> None:
        solr9_path = tmp_path / "solr9.json"
        solr10_path = tmp_path / "solr10.json"
        solr9_path.write_text(json.dumps(_report(solr_version="9.7")), encoding="utf-8")
        solr10_path.write_text(json.dumps(_report(solr_version="10")), encoding="utf-8")

        comparison = build_comparison(solr9_path, solr10_path)
        markdown = format_markdown(comparison)

        assert comparison["evidence"]["valid"] is True
        assert "Query Latency by Mode" in markdown
        assert "Claimed Improvements" in markdown
        assert "Factor (>1 means Solr 10 improved)" in markdown

    def test_invalid_evidence_recommendation_blocks_claims(self) -> None:
        comparison = {
            "evidence": {"valid": False, "failures": ["host_mismatch"]},
            "mode_comparisons": [],
            "resource_comparison": {
                "solr9_memory_bytes": None,
                "solr10_memory_bytes": None,
                "memory_reduction_factor": None,
                "solr9_startup_seconds": None,
                "solr10_startup_seconds": None,
                "startup_speedup_factor": None,
                "solr9_index_build_seconds": None,
                "solr10_index_build_seconds": None,
                "indexing_speedup_factor": None,
                "solr9_vector_indexing_seconds": None,
                "solr10_vector_indexing_seconds": None,
                "vector_indexing_speedup_factor": None,
                "solr9_throughput_qps": None,
                "solr10_throughput_qps": None,
                "throughput_factor": None,
                "solr9_concurrency": None,
                "solr10_concurrency": None,
            },
            "claims": {
                "memory_4x": {"target_factor": 4.0, "factor": None, "status": "insufficient_evidence"},
                "indexing_40x": {"target_factor": 40.0, "factor": None, "status": "insufficient_evidence"},
            },
            "regressions": [],
            "failed_query_ids": {"solr9": [], "solr10": []},
        }

        markdown = format_markdown(comparison)

        assert "Do not publish performance claims" in markdown
