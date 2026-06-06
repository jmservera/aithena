#!/usr/bin/env python3
"""Compare paired Solr 9.7 and Solr 10 benchmark reports.

This tool is intentionally evidence-gated: benchmark claims are only marked
valid when both reports include matching host and corpus metadata.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_LATENCY_REGRESSION_PCT = 20.0
MEMORY_IMPROVEMENT_TARGET = 4.0
INDEXING_IMPROVEMENT_TARGET = 40.0


@dataclass(frozen=True)
class ModeComparison:
    mode: str
    solr9_query_count: int
    solr10_query_count: int
    solr9_error_count: int
    solr10_error_count: int
    solr9_mean_latency_ms: float | None
    solr10_mean_latency_ms: float | None
    solr9_p95_latency_ms: float | None
    solr10_p95_latency_ms: float | None
    p95_delta_pct: float | None


def load_report(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        report = json.load(f)
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        raise ValueError(f"{path} is not a benchmark report with a results list")
    return report


def _metadata(report: dict[str, Any]) -> dict[str, Any]:
    metadata = report.get("run_metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _host_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    host = _metadata(report).get("host", {})
    if not isinstance(host, dict):
        return {}
    return {key: host.get(key) for key in ("node", "system", "release", "machine", "processor") if host.get(key)}


def _corpus_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    corpus = _metadata(report).get("corpus", {})
    if not isinstance(corpus, dict):
        return {}
    return {key: corpus.get(key) for key in ("id", "document_count", "bytes") if corpus.get(key) is not None}


def validate_evidence(solr9: dict[str, Any], solr10: dict[str, Any]) -> dict[str, Any]:
    host9 = _host_fingerprint(solr9)
    host10 = _host_fingerprint(solr10)
    corpus9 = _corpus_fingerprint(solr9)
    corpus10 = _corpus_fingerprint(solr10)
    failures: list[str] = []
    if not host9 or not host10:
        failures.append("missing_host_metadata")
    elif host9 != host10:
        failures.append("host_mismatch")
    if not corpus9 or not corpus10:
        failures.append("missing_corpus_metadata")
    elif corpus9 != corpus10:
        failures.append("corpus_mismatch")
    return {
        "valid": not failures,
        "failures": failures,
        "solr9_host": host9,
        "solr10_host": host10,
        "solr9_corpus": corpus9,
        "solr10_corpus": corpus10,
    }


def _successful_latencies(results: list[dict[str, Any]], mode: str) -> list[float]:
    latencies: list[float] = []
    for result in results:
        if result.get("mode") != mode or result.get("error"):
            continue
        latency = result.get("latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
    return latencies


def _error_count(results: list[dict[str, Any]], mode: str) -> int:
    return sum(1 for result in results if result.get("mode") == mode and result.get("error"))


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    idx = min(int(len(sorted_values) * pct), len(sorted_values) - 1)
    return round(sorted_values[idx], 4)


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def _delta_pct(baseline: float | None, candidate: float | None) -> float | None:
    if baseline is None or candidate is None or baseline <= 0:
        return None
    return round(((candidate - baseline) / baseline) * 100.0, 4)


def compare_modes(solr9: dict[str, Any], solr10: dict[str, Any]) -> list[ModeComparison]:
    solr9_results = [r for r in solr9.get("results", []) if isinstance(r, dict)]
    solr10_results = [r for r in solr10.get("results", []) if isinstance(r, dict)]
    modes = sorted({str(r.get("mode")) for r in solr9_results + solr10_results if r.get("mode")})
    comparisons: list[ModeComparison] = []
    for mode in modes:
        solr9_latencies = _successful_latencies(solr9_results, mode)
        solr10_latencies = _successful_latencies(solr10_results, mode)
        solr9_p95 = _percentile(solr9_latencies, 0.95)
        solr10_p95 = _percentile(solr10_latencies, 0.95)
        comparisons.append(
            ModeComparison(
                mode=mode,
                solr9_query_count=sum(1 for r in solr9_results if r.get("mode") == mode),
                solr10_query_count=sum(1 for r in solr10_results if r.get("mode") == mode),
                solr9_error_count=_error_count(solr9_results, mode),
                solr10_error_count=_error_count(solr10_results, mode),
                solr9_mean_latency_ms=_mean(solr9_latencies),
                solr10_mean_latency_ms=_mean(solr10_latencies),
                solr9_p95_latency_ms=solr9_p95,
                solr10_p95_latency_ms=solr10_p95,
                p95_delta_pct=_delta_pct(solr9_p95, solr10_p95),
            ),
        )
    return comparisons


def failed_query_ids(report: dict[str, Any]) -> list[str]:
    failed = []
    for result in report.get("results", []):
        if isinstance(result, dict) and result.get("error"):
            query_id = result.get("query_id")
            mode = result.get("mode")
            failed.append(f"{query_id}:{mode}")
    return sorted(str(item) for item in failed)


def _extract_memory_bytes(value: Any) -> int | None:
    if isinstance(value, dict):
        if isinstance(value.get("mem_usage_bytes"), int):
            return value["mem_usage_bytes"]
        if isinstance(value.get("memory_usage_bytes"), int):
            return value["memory_usage_bytes"]
        child_values = [_extract_memory_bytes(v) for v in value.values()]
        total = sum(v for v in child_values if v is not None)
        return total or None
    if isinstance(value, list):
        child_values = [_extract_memory_bytes(v) for v in value]
        total = sum(v for v in child_values if v is not None)
        return total or None
    return None


def memory_bytes(report: dict[str, Any]) -> int | None:
    return _extract_memory_bytes(_metadata(report).get("docker_stats"))


def timing_seconds(report: dict[str, Any], key: str) -> float | None:
    timings = _metadata(report).get("timings", {})
    if not isinstance(timings, dict):
        return None
    value = timings.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def throughput_value(report: dict[str, Any], key: str) -> float | None:
    throughput = _metadata(report).get("throughput", {})
    if not isinstance(throughput, dict):
        return None
    value = throughput.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _factor(baseline: float | int | None, candidate: float | int | None) -> float | None:
    if baseline is None or candidate is None or candidate <= 0:
        return None
    return round(float(baseline) / float(candidate), 4)


def _inverse_factor(baseline: float | int | None, candidate: float | int | None) -> float | None:
    if baseline is None or candidate is None or baseline <= 0:
        return None
    return round(float(candidate) / float(baseline), 4)


def analyze_claims(solr9: dict[str, Any], solr10: dict[str, Any]) -> dict[str, Any]:
    mem_factor = _factor(memory_bytes(solr9), memory_bytes(solr10))
    index_factor = _factor(
        timing_seconds(solr9, "index_build_seconds"),
        timing_seconds(solr10, "index_build_seconds"),
    )
    return {
        "memory_4x": {
            "factor": mem_factor,
            "status": _claim_status(mem_factor, MEMORY_IMPROVEMENT_TARGET),
            "target_factor": MEMORY_IMPROVEMENT_TARGET,
        },
        "indexing_40x": {
            "factor": index_factor,
            "status": _claim_status(index_factor, INDEXING_IMPROVEMENT_TARGET),
            "target_factor": INDEXING_IMPROVEMENT_TARGET,
        },
    }


def _claim_status(factor: float | None, target: float) -> str:
    if factor is None:
        return "insufficient_evidence"
    return "validated" if factor >= target else "not_validated"


def identify_regressions(
    comparisons: list[ModeComparison],
    *,
    latency_regression_pct: float = DEFAULT_LATENCY_REGRESSION_PCT,
) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    for comparison in comparisons:
        if comparison.p95_delta_pct is not None and comparison.p95_delta_pct > latency_regression_pct:
            regressions.append(
                {
                    "type": "latency_p95",
                    "mode": comparison.mode,
                    "delta_pct": comparison.p95_delta_pct,
                    "threshold_pct": latency_regression_pct,
                },
            )
        if comparison.solr10_error_count > comparison.solr9_error_count:
            regressions.append(
                {
                    "type": "query_errors",
                    "mode": comparison.mode,
                    "solr9_errors": comparison.solr9_error_count,
                    "solr10_errors": comparison.solr10_error_count,
                },
            )
    return regressions


def build_comparison(
    solr9_path: Path,
    solr10_path: Path,
    *,
    latency_regression_pct: float = DEFAULT_LATENCY_REGRESSION_PCT,
) -> dict[str, Any]:
    solr9 = load_report(solr9_path)
    solr10 = load_report(solr10_path)
    comparisons = compare_modes(solr9, solr10)
    return {
        "solr9_report": str(solr9_path),
        "solr10_report": str(solr10_path),
        "evidence": validate_evidence(solr9, solr10),
        "mode_comparisons": [comparison.__dict__ for comparison in comparisons],
        "resource_comparison": {
            "solr9_memory_bytes": memory_bytes(solr9),
            "solr10_memory_bytes": memory_bytes(solr10),
            "memory_reduction_factor": _factor(memory_bytes(solr9), memory_bytes(solr10)),
            "solr9_startup_seconds": timing_seconds(solr9, "startup_seconds"),
            "solr10_startup_seconds": timing_seconds(solr10, "startup_seconds"),
            "startup_speedup_factor": _factor(
                timing_seconds(solr9, "startup_seconds"),
                timing_seconds(solr10, "startup_seconds"),
            ),
            "solr9_index_build_seconds": timing_seconds(solr9, "index_build_seconds"),
            "solr10_index_build_seconds": timing_seconds(solr10, "index_build_seconds"),
            "indexing_speedup_factor": _factor(
                timing_seconds(solr9, "index_build_seconds"),
                timing_seconds(solr10, "index_build_seconds"),
            ),
            "solr9_vector_indexing_seconds": timing_seconds(solr9, "vector_indexing_seconds"),
            "solr10_vector_indexing_seconds": timing_seconds(solr10, "vector_indexing_seconds"),
            "vector_indexing_speedup_factor": _factor(
                timing_seconds(solr9, "vector_indexing_seconds"),
                timing_seconds(solr10, "vector_indexing_seconds"),
            ),
            "solr9_throughput_qps": throughput_value(solr9, "qps"),
            "solr10_throughput_qps": throughput_value(solr10, "qps"),
            "throughput_factor": _inverse_factor(
                throughput_value(solr9, "qps"),
                throughput_value(solr10, "qps"),
            ),
            "solr9_concurrency": throughput_value(solr9, "concurrency"),
            "solr10_concurrency": throughput_value(solr10, "concurrency"),
        },
        "claims": analyze_claims(solr9, solr10),
        "regressions": identify_regressions(
            comparisons,
            latency_regression_pct=latency_regression_pct,
        ),
        "failed_query_ids": {
            "solr9": failed_query_ids(solr9),
            "solr10": failed_query_ids(solr10),
        },
    }


def format_markdown(comparison: dict[str, Any]) -> str:
    evidence = comparison["evidence"]
    lines = [
        "# Solr 9.7 vs Solr 10 Benchmark Comparison",
        "",
        "Generated from paired benchmark JSON reports. Claims are evidence-gated and require "
        "same-host, same-corpus metadata.",
        "",
        "## Evidence Gate",
        "",
        f"- Valid paired evidence: **{'yes' if evidence['valid'] else 'no'}**",
        f"- Gate failures: {', '.join(evidence['failures']) if evidence['failures'] else '(none)'}",
        "",
        "## Query Latency by Mode",
        "",
        "| Mode | Solr 9 queries/errors | Solr 10 queries/errors | Solr 9 mean ms | "
        "Solr 10 mean ms | Solr 9 p95 ms | Solr 10 p95 ms | p95 delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["mode_comparisons"]:
        lines.append(
            "| {mode} | {s9q}/{s9e} | {s10q}/{s10e} | {s9mean} | {s10mean} | {s9p95} | {s10p95} | {delta} |".format(
                mode=row["mode"],
                s9q=row["solr9_query_count"],
                s9e=row["solr9_error_count"],
                s10q=row["solr10_query_count"],
                s10e=row["solr10_error_count"],
                s9mean=_fmt(row["solr9_mean_latency_ms"]),
                s10mean=_fmt(row["solr10_mean_latency_ms"]),
                s9p95=_fmt(row["solr9_p95_latency_ms"]),
                s10p95=_fmt(row["solr10_p95_latency_ms"]),
                delta=_fmt_pct(row["p95_delta_pct"]),
            ),
        )
    resources = comparison["resource_comparison"]
    lines.extend(
        [
            "",
            "## Resource and Build Metrics",
            "",
            "| Metric | Solr 9.7 | Solr 10 | Factor (Solr 9.7 / Solr 10) |",
            "|---|---:|---:|---:|",
            "| Memory bytes | "
            f"{_fmt(resources['solr9_memory_bytes'])} | "
            f"{_fmt(resources['solr10_memory_bytes'])} | "
            f"{_fmt(resources['memory_reduction_factor'])} |",
            "| Startup seconds | "
            f"{_fmt(resources['solr9_startup_seconds'])} | "
            f"{_fmt(resources['solr10_startup_seconds'])} | "
            f"{_fmt(resources['startup_speedup_factor'])} |",
            "| Index build seconds | "
            f"{_fmt(resources['solr9_index_build_seconds'])} | "
            f"{_fmt(resources['solr10_index_build_seconds'])} | "
            f"{_fmt(resources['indexing_speedup_factor'])} |",
            "| Vector indexing seconds | "
            f"{_fmt(resources['solr9_vector_indexing_seconds'])} | "
            f"{_fmt(resources['solr10_vector_indexing_seconds'])} | "
            f"{_fmt(resources['vector_indexing_speedup_factor'])} |",
            "| Concurrent throughput qps | "
            f"{_fmt(resources['solr9_throughput_qps'])} | "
            f"{_fmt(resources['solr10_throughput_qps'])} | "
            f"{_fmt(resources['throughput_factor'])} |",
            "| Throughput concurrency | "
            f"{_fmt(resources['solr9_concurrency'])} | "
            f"{_fmt(resources['solr10_concurrency'])} | N/A |",
            "",
            "## Claimed Improvements",
            "",
            "| Claim | Target | Observed factor | Status |",
            "|---|---:|---:|---|",
        ],
    )
    for name, claim in comparison["claims"].items():
        lines.append(
            f"| {name} | {claim['target_factor']}x | {_fmt(claim['factor'])} | {claim['status']} |",
        )
    lines.extend(["", "## Regressions", ""])
    if comparison["regressions"]:
        for regression in comparison["regressions"]:
            lines.append(f"- `{regression['type']}` in `{regression['mode']}`: {regression}")
    else:
        lines.append("- None detected from available evidence.")
    lines.extend(["", "## Failed Query IDs", ""])
    for version, failures in comparison["failed_query_ids"].items():
        lines.append(f"- {version}: {', '.join(failures) if failures else '(none)'}")
    lines.extend(["", "## Production Recommendation", ""])
    if not evidence["valid"]:
        lines.append(
            "Do not publish performance claims or make deployment decisions yet. Re-run Solr 9.7 "
            "and Solr 10 on the same host with the same corpus and attach benchmark JSON, "
            "docker stats, corpus size, and failed query IDs.",
        )
    elif comparison["regressions"]:
        lines.append("Hold production rollout until regressions are triaged and re-benchmarked.")
    else:
        lines.append(
            "No regressions detected in the supplied paired evidence; proceed with staged production validation.",
        )
    lines.append("")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Solr 9.7 and Solr 10 benchmark reports")
    parser.add_argument("--solr9", required=True, type=Path, help="Solr 9.7 benchmark JSON report")
    parser.add_argument("--solr10", required=True, type=Path, help="Solr 10 benchmark JSON report")
    parser.add_argument("--output-json", type=Path, help="Optional machine-readable comparison output")
    parser.add_argument("--output-md", type=Path, help="Optional markdown report output")
    parser.add_argument(
        "--latency-regression-pct",
        type=float,
        default=DEFAULT_LATENCY_REGRESSION_PCT,
        help=f"p95 latency regression threshold (default: {DEFAULT_LATENCY_REGRESSION_PCT})",
    )
    args = parser.parse_args()

    comparison = build_comparison(
        args.solr9,
        args.solr10,
        latency_regression_pct=args.latency_regression_pct,
    )
    markdown = format_markdown(comparison)
    print(markdown)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
