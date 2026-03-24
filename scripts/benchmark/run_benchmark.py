#!/usr/bin/env python3
"""Benchmark runner for search quality measurement.

Executes queries from the benchmark suite against the solr-search API,
measuring latency, result quality, and search behavior across keyword,
semantic, and hybrid modes against the books collection (e5-base 768D).

Usage:
    python run_benchmark.py                         # defaults: localhost:8080
    python run_benchmark.py --base-url http://host:8080
    python run_benchmark.py --modes semantic hybrid  # only specific modes
    python run_benchmark.py --output results.json    # save JSON report
    python run_benchmark.py --queries queries.json   # custom query file
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_QUERIES_PATH = Path(__file__).parent / "queries.json"
DEFAULT_TOP_K = 10
COLLECTION = "books"
SEARCH_MODES = ("keyword", "semantic", "hybrid")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of a single query execution."""

    query_id: str
    query: str
    collection: str
    mode: str
    top_k_ids: list[str]
    top_k_scores: list[float]
    total_results: int
    latency_ms: float
    degraded: bool = False
    error: str | None = None


@dataclass
class BenchmarkReport:
    """Complete benchmark report with all results and aggregate metrics."""

    timestamp: str = ""
    base_url: str = ""
    queries_file: str = ""
    collection: str = COLLECTION
    total_queries: int = 0
    modes_tested: list[str] = field(default_factory=list)
    results: list[QueryResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Query loading
# ---------------------------------------------------------------------------

def load_queries(path: Path) -> list[dict[str, Any]]:
    """Load and flatten queries from the benchmark suite JSON file."""
    with open(path) as f:
        data = json.load(f)

    queries: list[dict[str, Any]] = []
    for category_key, category_data in data.get("categories", {}).items():
        for q in category_data.get("queries", []):
            queries.append({
                "id": q["id"],
                "query": q["query"],
                "category": category_key,
                "notes": q.get("notes", ""),
            })
    return queries


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

def execute_query(
    base_url: str,
    query_text: str,
    query_id: str,
    collection: str,
    mode: str,
    top_k: int = DEFAULT_TOP_K,
    timeout: float = 30.0,
    token: str | None = None,
) -> QueryResult:
    """Execute a single search query against the solr-search API."""
    params: dict[str, Any] = {
        "q": query_text,
        "mode": mode,
        "collection": collection,
        "page_size": top_k,
        "page": 1,
    }

    url = f"{base_url}/search?{urlencode(params)}"
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    start = time.perf_counter()

    try:
        response = requests.get(url, timeout=timeout, headers=headers)
        latency_ms = (time.perf_counter() - start) * 1000.0
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, OSError) as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return QueryResult(
            query_id=query_id,
            query=query_text,
            collection=collection,
            mode=mode,
            top_k_ids=[],
            top_k_scores=[],
            total_results=0,
            latency_ms=latency_ms,
            error=str(exc),
        )

    results = data.get("results", [])
    return QueryResult(
        query_id=query_id,
        query=query_text,
        collection=collection,
        mode=mode,
        top_k_ids=[r["id"] for r in results],
        top_k_scores=[r.get("score", 0.0) for r in results],
        total_results=data.get("total_results", data.get("total", 0)),
        latency_ms=latency_ms,
        degraded=data.get("degraded", False),
    )


# ---------------------------------------------------------------------------
# Aggregate statistics
# ---------------------------------------------------------------------------

def compute_summary(results: list[QueryResult]) -> dict[str, Any]:
    """Compute aggregate statistics across all results."""
    summary: dict[str, Any] = {"by_mode": {}, "by_category": {}}

    # Group by mode
    by_mode: dict[str, list[QueryResult]] = {}
    for r in results:
        by_mode.setdefault(r.mode, []).append(r)

    for mode, mode_results in sorted(by_mode.items()):
        latencies = [r.latency_ms for r in mode_results if not r.error]
        result_counts = [float(r.total_results) for r in mode_results if not r.error]
        errors = sum(1 for r in mode_results if r.error)

        summary["by_mode"][mode] = {
            "query_count": len(mode_results),
            "mean_latency_ms": _safe_mean(latencies),
            "median_latency_ms": _safe_median(latencies),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "mean_result_count": _safe_mean(result_counts),
            "error_count": errors,
        }

    # Group by category
    by_category: dict[str, list[QueryResult]] = {}
    for r in results:
        by_category.setdefault(_category_from_id(r.query_id), []).append(r)

    for cat, cat_results in sorted(by_category.items()):
        latencies = [r.latency_ms for r in cat_results if not r.error]
        summary["by_category"][cat] = {
            "query_count": len(cat_results),
            "mean_latency_ms": _safe_mean(latencies),
        }

    return summary


_CATEGORY_MAP = {
    "sk": "simple_keyword",
    "nl": "natural_language",
    "ml": "multilingual",
    "lc": "long_complex",
    "ec": "edge_cases",
}


def _category_from_id(query_id: str) -> str:
    """Derive category name from query ID prefix."""
    prefix = query_id.split("-")[0] if "-" in query_id else query_id
    return _CATEGORY_MAP.get(prefix, prefix)


def _safe_mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def _safe_median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct)
    idx = min(idx, len(sorted_vals) - 1)
    return round(sorted_vals[idx], 2)


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------

def query_result_to_dict(r: QueryResult) -> dict[str, Any]:
    """Serialize a QueryResult to a JSON-compatible dict."""
    return {
        "query_id": r.query_id,
        "query": r.query,
        "collection": r.collection,
        "mode": r.mode,
        "top_k_ids": r.top_k_ids,
        "top_k_scores": r.top_k_scores,
        "total_results": r.total_results,
        "latency_ms": round(r.latency_ms, 2),
        "degraded": r.degraded,
        "error": r.error,
    }


def report_to_dict(report: BenchmarkReport) -> dict[str, Any]:
    """Serialize a BenchmarkReport to a JSON-compatible dict."""
    return {
        "timestamp": report.timestamp,
        "base_url": report.base_url,
        "queries_file": report.queries_file,
        "collection": report.collection,
        "total_queries": report.total_queries,
        "modes_tested": report.modes_tested,
        "summary": report.summary,
        "results": [query_result_to_dict(r) for r in report.results],
    }


# ---------------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------------

def format_summary(report: BenchmarkReport) -> str:
    """Format a human-readable summary of benchmark results."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("BENCHMARK REPORT")
    lines.append(f"  Timestamp:    {report.timestamp}")
    lines.append(f"  Base URL:     {report.base_url}")
    lines.append(f"  Collection:   {report.collection}")
    lines.append(f"  Queries:      {report.total_queries}")
    lines.append(f"  Modes:        {', '.join(report.modes_tested)}")
    lines.append("=" * 72)

    summary = report.summary

    # Per-mode summary
    for mode, stats in sorted(summary.get("by_mode", {}).items()):
        lines.append("")
        lines.append(f"--- Mode: {mode} ({stats['query_count']} queries) ---")
        lines.append("  Latency (ms):")
        lines.append(f"    Mean:   {_fmt(stats['mean_latency_ms'])} ms")
        lines.append(f"    Median: {_fmt(stats['median_latency_ms'])} ms")
        lines.append(f"    p95:    {_fmt(stats['p95_latency_ms'])} ms")
        lines.append(f"  Mean result count: {_fmt(stats['mean_result_count'])}")
        if stats["error_count"]:
            lines.append(f"  \u26a0 Errors: {stats['error_count']}")

    # Per-category summary
    lines.append("")
    lines.append("--- By Category ---")
    for cat, stats in sorted(summary.get("by_category", {}).items()):
        lines.append(f"  {cat:20s}  queries={stats['query_count']:<3d}  mean_latency={_fmt(stats['mean_latency_ms'])} ms")

    # Error queries
    lines.append("")
    error_results = [r for r in report.results if r.error]
    lines.append(f"--- Errors ({len(error_results)}) ---")
    if error_results:
        for r in error_results:
            lines.append(f"  [{r.mode}] {r.query_id}: {r.error[:60]}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "N/A"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_benchmark(
    base_url: str = DEFAULT_BASE_URL,
    queries_path: Path = DEFAULT_QUERIES_PATH,
    modes: tuple[str, ...] = SEARCH_MODES,
    collection: str = COLLECTION,
    top_k: int = DEFAULT_TOP_K,
    timeout: float = 30.0,
    token: str | None = None,
) -> BenchmarkReport:
    """Execute the full benchmark suite and return a report."""
    queries = load_queries(queries_path)

    report = BenchmarkReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        base_url=base_url,
        queries_file=str(queries_path),
        collection=collection,
        total_queries=len(queries),
        modes_tested=list(modes),
    )

    total = len(queries) * len(modes)
    completed = 0

    for mode in modes:
        for q in queries:
            completed += 1
            progress = f"[{completed}/{total}]"
            print(f"{progress} {mode:8s} | {q['id']:6s} | {q['query'][:50]}...", flush=True)

            result = execute_query(
                base_url, q["query"], q["id"], collection, mode, top_k, timeout, token=token,
            )
            report.results.append(result)

    report.summary = compute_summary(report.results)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark runner for search quality measurement.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"solr-search API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=DEFAULT_QUERIES_PATH,
        help="Path to benchmark queries JSON file",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=SEARCH_MODES,
        default=list(SEARCH_MODES),
        help="Search modes to test (default: all)",
    )
    parser.add_argument(
        "--collection",
        default=COLLECTION,
        help=f"Solr collection to benchmark (default: {COLLECTION})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of top results to retrieve (default: {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file for JSON report (default: stdout summary only)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token for authenticated APIs (default: none)",
    )
    args = parser.parse_args()

    report = run_benchmark(
        base_url=args.base_url,
        queries_path=args.queries,
        modes=tuple(args.modes),
        collection=args.collection,
        top_k=args.top_k,
        timeout=args.timeout,
        token=args.token,
    )

    # Human-readable summary to stdout
    print(format_summary(report))

    # JSON report to file if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(report_to_dict(report), f, indent=2)
        print(f"\nJSON report saved to: {args.output}")


if __name__ == "__main__":
    main()
