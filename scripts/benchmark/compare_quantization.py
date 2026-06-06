#!/usr/bin/env python3
"""Compare float32 and scalar-quantized benchmark reports.

The benchmark runner records top-k result IDs for every query/mode. This tool
uses a float32 report as the reference set and computes recall@k/top-k overlap
for a quantized candidate report, plus latency deltas. It is intentionally
offline: no Solr, Docker, or embedding services are required.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MIN_RECALL = 0.95
DEFAULT_TOP_K = 10
DEFAULT_VECTOR_DIMENSION = 768
DEFAULT_CANDIDATE_BITS = 7
DEFAULT_MEMORY_VECTOR_COUNT = 1_000_000
FLOAT32_BYTES_PER_DIMENSION = 4


@dataclass(frozen=True)
class Comparison:
    """Per-query/mode comparison between reference and candidate results."""

    query_id: str
    mode: str
    baseline_ids: list[str]
    candidate_ids: list[str]
    recall_at_k: float | None
    overlap_count: int
    baseline_latency_ms: float | None
    candidate_latency_ms: float | None
    latency_delta_pct: float | None
    baseline_error: str | None = None
    candidate_error: str | None = None


def load_report(path: Path) -> dict[str, Any]:
    """Load a benchmark JSON report."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError(f"{path} is not a benchmark report with a results list")
    return data


def _key(result: dict[str, Any]) -> tuple[str, str]:
    return str(result.get("query_id", "")), str(result.get("mode", ""))


def _result_index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for result in report.get("results", []):
        if isinstance(result, dict):
            indexed[_key(result)] = result
    return indexed


def _top_ids(result: dict[str, Any], top_k: int) -> list[str]:
    ids = result.get("top_k_ids", [])
    if not isinstance(ids, list):
        return []
    return [str(item) for item in ids[:top_k]]


def _latency(result: dict[str, Any]) -> float | None:
    value = result.get("latency_ms")
    return float(value) if isinstance(value, (int, float)) else None


def _latency_delta_pct(baseline: float | None, candidate: float | None) -> float | None:
    if baseline is None or candidate is None or baseline <= 0:
        return None
    return round(((candidate - baseline) / baseline) * 100.0, 4)


def _recall_at_k(baseline_ids: list[str], candidate_ids: list[str]) -> tuple[float | None, int]:
    if not baseline_ids:
        return None, 0
    overlap = len(set(baseline_ids) & set(candidate_ids))
    return round(overlap / len(baseline_ids), 4), overlap


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[Comparison]:
    """Compare matching query_id/mode pairs in two benchmark reports."""
    baseline_results = _result_index(baseline)
    candidate_results = _result_index(candidate)
    comparisons: list[Comparison] = []

    for key in sorted(baseline_results):
        base = baseline_results[key]
        cand = candidate_results.get(key)
        if cand is None:
            query_id, mode = key
            baseline_ids = _top_ids(base, top_k)
            comparisons.append(
                Comparison(
                    query_id=query_id,
                    mode=mode,
                    baseline_ids=baseline_ids,
                    candidate_ids=[],
                    recall_at_k=0.0 if baseline_ids else None,
                    overlap_count=0,
                    baseline_latency_ms=_latency(base),
                    candidate_latency_ms=None,
                    latency_delta_pct=None,
                    baseline_error=base.get("error"),
                    candidate_error="missing result",
                ),
            )
            continue

        baseline_ids = _top_ids(base, top_k)
        candidate_ids = _top_ids(cand, top_k)
        recall, overlap = _recall_at_k(baseline_ids, candidate_ids)
        baseline_latency = _latency(base)
        candidate_latency = _latency(cand)
        comparisons.append(
            Comparison(
                query_id=key[0],
                mode=key[1],
                baseline_ids=baseline_ids,
                candidate_ids=candidate_ids,
                recall_at_k=recall,
                overlap_count=overlap,
                baseline_latency_ms=baseline_latency,
                candidate_latency_ms=candidate_latency,
                latency_delta_pct=_latency_delta_pct(baseline_latency, candidate_latency),
                baseline_error=base.get("error"),
                candidate_error=cand.get("error"),
            ),
        )

    return comparisons


def summarize(comparisons: list[Comparison], *, min_recall: float) -> dict[str, Any]:
    """Build aggregate recall and latency summaries."""
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in sorted({c.mode for c in comparisons}):
        mode_items = [c for c in comparisons if c.mode == mode]
        recalls = [c.recall_at_k for c in mode_items if c.recall_at_k is not None]
        deltas = [c.latency_delta_pct for c in mode_items if c.latency_delta_pct is not None]
        by_mode[mode] = {
            "query_count": len(mode_items),
            "mean_recall_at_k": round(statistics.mean(recalls), 4) if recalls else None,
            "min_recall_at_k": min(recalls) if recalls else None,
            "queries_below_min_recall": [
                c.query_id for c in mode_items if c.recall_at_k is not None and c.recall_at_k < min_recall
            ],
            "mean_latency_delta_pct": round(statistics.mean(deltas), 4) if deltas else None,
            "candidate_error_count": sum(1 for c in mode_items if c.candidate_error),
            "baseline_error_count": sum(1 for c in mode_items if c.baseline_error),
            "empty_baseline_result_count": sum(1 for c in mode_items if not c.baseline_ids),
        }

    failures: list[dict[str, Any]] = []
    for c in comparisons:
        reasons = []
        if c.baseline_error:
            reasons.append("baseline_error")
        if not c.baseline_ids:
            reasons.append("empty_baseline_top_k_ids")
        if c.candidate_error:
            reasons.append("candidate_error")
        if c.recall_at_k is not None and c.recall_at_k < min_recall:
            reasons.append("recall_below_threshold")

        if reasons:
            failures.append(
                {
                    "query_id": c.query_id,
                    "mode": c.mode,
                    "recall_at_k": c.recall_at_k,
                    "reasons": reasons,
                    "error": c.candidate_error or c.baseline_error,
                    "baseline_error": c.baseline_error,
                    "candidate_error": c.candidate_error,
                },
            )

    if not comparisons:
        failures.append(
            {
                "query_id": None,
                "mode": None,
                "recall_at_k": None,
                "reasons": ["no_baseline_comparisons"],
                "error": "baseline report has no comparable results",
                "baseline_error": "baseline report has no comparable results",
                "candidate_error": None,
            },
        )

    return {
        "total_comparisons": len(comparisons),
        "min_recall_threshold": min_recall,
        "by_mode": by_mode,
        "failures": failures,
        "passed": not failures,
    }


def estimate_vector_payload_memory(
    *,
    vector_count: int,
    vector_dimension: int = DEFAULT_VECTOR_DIMENSION,
    candidate_bits: int = DEFAULT_CANDIDATE_BITS,
) -> dict[str, Any]:
    """Estimate raw vector payload memory for float32 vs scalar quantization.

    This does not include Solr/Lucene/HNSW graph overhead; pair it with
    ``docker stats`` from real runs before claiming measured savings.
    """
    if vector_count < 0:
        raise ValueError("vector_count must be non-negative")
    if vector_dimension <= 0:
        raise ValueError("vector_dimension must be positive")
    if candidate_bits <= 0:
        raise ValueError("candidate_bits must be positive")

    baseline_bytes = vector_count * vector_dimension * FLOAT32_BYTES_PER_DIMENSION
    candidate_bytes = (vector_count * vector_dimension * candidate_bits + 7) // 8
    int8_compat_bytes = vector_count * vector_dimension
    saved_bytes = baseline_bytes - candidate_bytes
    baseline_mib = round(baseline_bytes / 1024 / 1024, 4)
    candidate_mib = round(candidate_bytes / 1024 / 1024, 4)
    int8_compat_mib = round(int8_compat_bytes / 1024 / 1024, 4)
    return {
        "vector_count": vector_count,
        "vector_dimension": vector_dimension,
        "baseline_float32_payload_bytes": baseline_bytes,
        "candidate_scalar_payload_bytes": candidate_bytes,
        "solr9_byte_compat_payload_bytes": int8_compat_bytes,
        "candidate_bits": candidate_bits,
        "baseline_float32_payload_mb": baseline_mib,
        "candidate_scalar_payload_mb": candidate_mib,
        "solr9_byte_compat_payload_mb": int8_compat_mib,
        "baseline_float32_payload_mib": baseline_mib,
        "candidate_scalar_payload_mib": candidate_mib,
        "solr9_byte_compat_payload_mib": int8_compat_mib,
        "estimated_savings_pct": round((saved_bytes / baseline_bytes) * 100.0, 4) if baseline_bytes else 0.0,
        "estimated_reduction_ratio": round(baseline_bytes / candidate_bytes, 4) if candidate_bytes else None,
        "note": "Raw vector payload estimate only; measure Solr RSS/heap separately for release evidence.",
    }


def comparison_to_dict(comparison: Comparison) -> dict[str, Any]:
    """Serialize a comparison to a JSON-compatible dict."""
    return {
        "query_id": comparison.query_id,
        "mode": comparison.mode,
        "baseline_ids": comparison.baseline_ids,
        "candidate_ids": comparison.candidate_ids,
        "recall_at_k": comparison.recall_at_k,
        "overlap_count": comparison.overlap_count,
        "baseline_latency_ms": comparison.baseline_latency_ms,
        "candidate_latency_ms": comparison.candidate_latency_ms,
        "latency_delta_pct": comparison.latency_delta_pct,
        "baseline_error": comparison.baseline_error,
        "candidate_error": comparison.candidate_error,
    }


def build_output(
    baseline_path: Path,
    candidate_path: Path,
    comparisons: list[Comparison],
    *,
    top_k: int,
    min_recall: float,
    vector_dimension: int = DEFAULT_VECTOR_DIMENSION,
    candidate_bits: int = DEFAULT_CANDIDATE_BITS,
    vector_count: int = DEFAULT_MEMORY_VECTOR_COUNT,
) -> dict[str, Any]:
    """Build the full JSON comparison report."""
    return {
        "baseline_report": str(baseline_path),
        "candidate_report": str(candidate_path),
        "top_k": top_k,
        "summary": summarize(comparisons, min_recall=min_recall),
        "memory_estimate": estimate_vector_payload_memory(
            vector_count=vector_count,
            vector_dimension=vector_dimension,
            candidate_bits=candidate_bits,
        ),
        "comparisons": [comparison_to_dict(c) for c in comparisons],
    }


def format_summary(output: dict[str, Any]) -> str:
    """Format a concise human-readable summary."""
    lines = ["QUANTIZATION RECALL COMPARISON", "=" * 36]
    summary = output["summary"]
    lines.append(f"top_k: {output['top_k']}")
    lines.append(f"min_recall_threshold: {summary['min_recall_threshold']}")
    lines.append(f"total_comparisons: {summary['total_comparisons']}")
    memory = output.get("memory_estimate")
    if memory:
        reduction_ratio = memory["estimated_reduction_ratio"]
        reduction_text = f"{reduction_ratio}x" if reduction_ratio is not None else "N/A"
        lines.append(
            "estimated_payload: "
            f"vectors={memory['vector_count']} "
            f"float32={memory['baseline_float32_payload_mib']} MiB "
            f"scalar_bits={memory['candidate_bits']}:{memory['candidate_scalar_payload_mib']} MiB "
            f"reduction={reduction_text}",
        )
    lines.append("")
    for mode, stats in sorted(summary["by_mode"].items()):
        lines.append(
            f"{mode}: mean_recall={stats['mean_recall_at_k']} "
            f"min_recall={stats['min_recall_at_k']} "
            f"mean_latency_delta_pct={stats['mean_latency_delta_pct']} "
            f"below_threshold={len(stats['queries_below_min_recall'])} "
            f"baseline_errors={stats['baseline_error_count']} "
            f"empty_baselines={stats['empty_baseline_result_count']} "
            f"candidate_errors={stats['candidate_error_count']}",
        )
    lines.append("")
    lines.append("PASS" if summary["passed"] else "FAIL")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare float32 and scalar-quantized benchmark JSON reports.",
    )
    parser.add_argument("--baseline", required=True, type=Path, help="Float32 benchmark JSON report")
    parser.add_argument("--candidate", required=True, type=Path, help="Quantized benchmark JSON report")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Top-k depth to compare")
    parser.add_argument(
        "--vector-dimension",
        type=int,
        default=DEFAULT_VECTOR_DIMENSION,
        help=f"Embedding vector dimension for memory estimates (default: {DEFAULT_VECTOR_DIMENSION})",
    )
    parser.add_argument(
        "--candidate-bits",
        type=int,
        default=DEFAULT_CANDIDATE_BITS,
        help=f"Scalar quantization bits for memory estimates (default: {DEFAULT_CANDIDATE_BITS})",
    )
    parser.add_argument(
        "--vector-count",
        type=int,
        default=DEFAULT_MEMORY_VECTOR_COUNT,
        help=f"Vector count for memory estimates (default: {DEFAULT_MEMORY_VECTOR_COUNT})",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=DEFAULT_MIN_RECALL,
        help="Minimum per-query recall@k threshold for pass/fail",
    )
    parser.add_argument("--output", "-o", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)
    comparisons = compare_reports(baseline, candidate, top_k=args.top_k)
    output = build_output(
        args.baseline,
        args.candidate,
        comparisons,
        top_k=args.top_k,
        min_recall=args.min_recall,
        vector_dimension=args.vector_dimension,
        candidate_bits=args.candidate_bits,
        vector_count=args.vector_count,
    )
    print(format_summary(output))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(f"\nJSON comparison saved to: {args.output}")

    sys.exit(0 if output["summary"]["passed"] else 1)


if __name__ == "__main__":
    main()
