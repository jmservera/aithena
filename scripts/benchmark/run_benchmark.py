#!/usr/bin/env python3
"""Benchmark runner for A/B testing search quality across Solr collections.

Executes queries from the benchmark suite against the solr-search API,
comparing results between the baseline (books/distiluse 512D) and
candidate (books_e5base/e5-base 768D) collections.

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
COLLECTIONS = ("books", "books_e5base")
SEARCH_MODES = ("keyword", "semantic", "hybrid")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of a single query execution against one collection."""

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
class QueryComparison:
    """Side-by-side comparison of a query across two collections."""

    query_id: str
    query: str
    category: str
    mode: str
    baseline: QueryResult | None = None
    candidate: QueryResult | None = None
    jaccard_similarity: float | None = None
    overlap_ids: list[str] = field(default_factory=list)
    baseline_only_ids: list[str] = field(default_factory=list)
    candidate_only_ids: list[str] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """Complete benchmark report with all comparisons and aggregate metrics."""

    timestamp: str = ""
    base_url: str = ""
    queries_file: str = ""
    total_queries: int = 0
    modes_tested: list[str] = field(default_factory=list)
    comparisons: list[QueryComparison] = field(default_factory=list)
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
    start = time.perf_counter()

    try:
        response = requests.get(url, timeout=timeout)
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
# Comparison metrics
# ---------------------------------------------------------------------------

def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def compare_results(
    baseline: QueryResult,
    candidate: QueryResult,
    category: str,
) -> QueryComparison:
    """Compare results from baseline and candidate collections."""
    baseline_set = set(baseline.top_k_ids)
    candidate_set = set(candidate.top_k_ids)

    return QueryComparison(
        query_id=baseline.query_id,
        query=baseline.query,
        category=category,
        mode=baseline.mode,
        baseline=baseline,
        candidate=candidate,
        jaccard_similarity=jaccard_similarity(baseline_set, candidate_set),
        overlap_ids=sorted(baseline_set & candidate_set),
        baseline_only_ids=sorted(baseline_set - candidate_set),
        candidate_only_ids=sorted(candidate_set - baseline_set),
    )


# ---------------------------------------------------------------------------
# Aggregate statistics
# ---------------------------------------------------------------------------

def compute_summary(comparisons: list[QueryComparison]) -> dict[str, Any]:
    """Compute aggregate statistics across all comparisons."""
    summary: dict[str, Any] = {"by_mode": {}, "by_category": {}}

    # Group by mode
    by_mode: dict[str, list[QueryComparison]] = {}
    for c in comparisons:
        by_mode.setdefault(c.mode, []).append(c)

    for mode, comps in sorted(by_mode.items()):
        jaccards = [c.jaccard_similarity for c in comps if c.jaccard_similarity is not None]
        baseline_latencies = [
            c.baseline.latency_ms for c in comps if c.baseline and not c.baseline.error
        ]
        candidate_latencies = [
            c.candidate.latency_ms for c in comps if c.candidate and not c.candidate.error
        ]
        errors = sum(
            1 for c in comps
            if (c.baseline and c.baseline.error) or (c.candidate and c.candidate.error)
        )

        summary["by_mode"][mode] = {
            "query_count": len(comps),
            "mean_jaccard": _safe_mean(jaccards),
            "median_jaccard": _safe_median(jaccards),
            "min_jaccard": min(jaccards) if jaccards else None,
            "max_jaccard": max(jaccards) if jaccards else None,
            "baseline_mean_latency_ms": _safe_mean(baseline_latencies),
            "candidate_mean_latency_ms": _safe_mean(candidate_latencies),
            "baseline_p95_latency_ms": _percentile(baseline_latencies, 0.95),
            "candidate_p95_latency_ms": _percentile(candidate_latencies, 0.95),
            "error_count": errors,
        }

    # Group by category
    by_category: dict[str, list[QueryComparison]] = {}
    for c in comparisons:
        by_category.setdefault(c.category, []).append(c)

    for cat, comps in sorted(by_category.items()):
        jaccards = [c.jaccard_similarity for c in comps if c.jaccard_similarity is not None]
        summary["by_category"][cat] = {
            "query_count": len(comps),
            "mean_jaccard": _safe_mean(jaccards),
        }

    return summary


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

def comparison_to_dict(c: QueryComparison) -> dict[str, Any]:
    """Serialize a QueryComparison to a JSON-compatible dict."""
    result: dict[str, Any] = {
        "query_id": c.query_id,
        "query": c.query,
        "category": c.category,
        "mode": c.mode,
        "jaccard_similarity": c.jaccard_similarity,
        "overlap_ids": c.overlap_ids,
        "baseline_only_ids": c.baseline_only_ids,
        "candidate_only_ids": c.candidate_only_ids,
    }
    for label, qr in [("baseline", c.baseline), ("candidate", c.candidate)]:
        if qr:
            result[label] = {
                "collection": qr.collection,
                "top_k_ids": qr.top_k_ids,
                "top_k_scores": qr.top_k_scores,
                "total_results": qr.total_results,
                "latency_ms": round(qr.latency_ms, 2),
                "degraded": qr.degraded,
                "error": qr.error,
            }
    return result


def report_to_dict(report: BenchmarkReport) -> dict[str, Any]:
    """Serialize a BenchmarkReport to a JSON-compatible dict."""
    return {
        "timestamp": report.timestamp,
        "base_url": report.base_url,
        "queries_file": report.queries_file,
        "total_queries": report.total_queries,
        "modes_tested": report.modes_tested,
        "summary": report.summary,
        "comparisons": [comparison_to_dict(c) for c in report.comparisons],
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
    lines.append(f"  Queries:      {report.total_queries}")
    lines.append(f"  Modes:        {', '.join(report.modes_tested)}")
    lines.append("=" * 72)

    summary = report.summary

    # Per-mode summary
    for mode, stats in sorted(summary.get("by_mode", {}).items()):
        lines.append("")
        lines.append(f"--- Mode: {mode} ({stats['query_count']} queries) ---")
        lines.append("  Jaccard (top-10 overlap):")
        lines.append(f"    Mean:   {_fmt(stats['mean_jaccard'])}")
        lines.append(f"    Median: {_fmt(stats['median_jaccard'])}")
        lines.append(f"    Range:  [{_fmt(stats['min_jaccard'])}, {_fmt(stats['max_jaccard'])}]")
        lines.append("  Latency (ms):")
        lines.append(f"    Baseline mean:  {_fmt(stats['baseline_mean_latency_ms'])} ms")
        lines.append(f"    Candidate mean: {_fmt(stats['candidate_mean_latency_ms'])} ms")
        lines.append(f"    Baseline p95:   {_fmt(stats['baseline_p95_latency_ms'])} ms")
        lines.append(f"    Candidate p95:  {_fmt(stats['candidate_p95_latency_ms'])} ms")
        if stats["error_count"]:
            lines.append(f"  ⚠ Errors: {stats['error_count']}")

    # Per-category summary
    lines.append("")
    lines.append("--- By Category ---")
    for cat, stats in sorted(summary.get("by_category", {}).items()):
        lines.append(f"  {cat:20s}  queries={stats['query_count']:<3d}  mean_jaccard={_fmt(stats['mean_jaccard'])}")

    # Low-overlap queries (interesting for human review)
    lines.append("")
    lines.append("--- Low Overlap Queries (Jaccard < 0.3) ---")
    low_overlap = [
        c for c in report.comparisons
        if c.jaccard_similarity is not None and c.jaccard_similarity < 0.3
    ]
    if low_overlap:
        for c in low_overlap:
            lines.append(f"  [{c.mode}] {c.query_id}: \"{c.query[:60]}\" → jaccard={c.jaccard_similarity:.2f}")
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
    collections: tuple[str, ...] = COLLECTIONS,
    top_k: int = DEFAULT_TOP_K,
    timeout: float = 30.0,
) -> BenchmarkReport:
    """Execute the full benchmark suite and return a report."""
    queries = load_queries(queries_path)
    baseline_col, candidate_col = collections[0], collections[1]

    report = BenchmarkReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        base_url=base_url,
        queries_file=str(queries_path),
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

            baseline = execute_query(
                base_url, q["query"], q["id"], baseline_col, mode, top_k, timeout,
            )
            candidate = execute_query(
                base_url, q["query"], q["id"], candidate_col, mode, top_k, timeout,
            )

            comparison = compare_results(baseline, candidate, q["category"])
            report.comparisons.append(comparison)

    report.summary = compute_summary(report.comparisons)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark runner for A/B testing search quality across Solr collections.",
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
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of top results to compare (default: {DEFAULT_TOP_K})",
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
    args = parser.parse_args()

    report = run_benchmark(
        base_url=args.base_url,
        queries_path=args.queries,
        modes=tuple(args.modes),
        top_k=args.top_k,
        timeout=args.timeout,
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
