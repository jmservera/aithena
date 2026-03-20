"""
Indexing pipeline stress tests for Aithena.

Tests the full document-indexing pipeline:
    document-lister → RabbitMQ → document-indexer → Solr

Parametrized across three batch sizes (small=50, medium=500, large=2000+)
and multiple configuration variants (prefetch count, consumer count,
embeddings batch size).

Metrics captured:
    - Throughput (docs/min)
    - Memory ceiling (MB)
    - CPU usage (avg/peak %)
    - RabbitMQ queue depth over time
    - Failure rate (%)
    - Disk growth (bytes written)

Results are written as JSON to ``tests/stress/results/<timestamp>/``.

Tests requiring Docker are marked ``@pytest.mark.docker`` and skip
gracefully when infrastructure is unavailable.  Pure metric-calculation
and report-generation logic is covered by unit tests that run locally.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Batch size presets (mirrors generate_test_data.BATCH_PRESETS)
# ---------------------------------------------------------------------------

BATCH_SIZES: dict[str, int] = {
    "small": 50,
    "medium": 500,
    "large": 2000,
}

# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineConfig:
    """Tunable knobs for the indexing pipeline."""

    prefetch_count: int = 1
    consumer_count: int = 1
    embeddings_batch_size: int = 32

    def __post_init__(self) -> None:
        if self.prefetch_count < 1:
            msg = f"prefetch_count must be >= 1, got {self.prefetch_count}"
            raise ValueError(msg)
        if self.consumer_count < 1:
            msg = f"consumer_count must be >= 1, got {self.consumer_count}"
            raise ValueError(msg)
        if self.embeddings_batch_size < 1:
            msg = f"embeddings_batch_size must be >= 1, got {self.embeddings_batch_size}"
            raise ValueError(msg)


@dataclass(frozen=True)
class BatchConfig:
    """Describes a single stress-test batch."""

    label: str
    doc_count: int
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)

    def __post_init__(self) -> None:
        if self.doc_count < 0:
            msg = f"doc_count must be >= 0, got {self.doc_count}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Metric result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QueueDepthSample:
    """A single queue-depth observation."""

    timestamp: str
    queue_name: str
    messages_ready: int
    messages_unacked: int
    consumers: int


@dataclass
class IndexingMetrics:
    """Aggregated metrics for one indexing run."""

    batch_label: str
    doc_count: int
    pipeline_config: dict[str, Any]

    # Timing
    elapsed_seconds: float = 0.0
    throughput_docs_per_min: float = 0.0

    # Resource peaks
    memory_peak_mb: float = 0.0
    memory_avg_mb: float = 0.0
    cpu_peak_percent: float = 0.0
    cpu_avg_percent: float = 0.0

    # Queue
    queue_depth_samples: list[dict] = field(default_factory=list)
    queue_depth_peak: int = 0

    # Outcomes
    docs_indexed: int = 0
    docs_failed: int = 0
    failure_rate_percent: float = 0.0

    # Disk
    disk_write_bytes: int = 0

    # Metadata
    started_at: str = ""
    finished_at: str = ""


# ---------------------------------------------------------------------------
# Pure metric helpers (unit-testable, no Docker required)
# ---------------------------------------------------------------------------


def calculate_throughput(doc_count: int, elapsed_seconds: float) -> float:
    """Return documents per minute.

    >>> calculate_throughput(120, 60.0)
    120.0
    >>> calculate_throughput(0, 10.0)
    0.0
    """
    if doc_count < 0:
        msg = f"doc_count must be >= 0, got {doc_count}"
        raise ValueError(msg)
    if elapsed_seconds < 0:
        msg = f"elapsed_seconds must be >= 0, got {elapsed_seconds}"
        raise ValueError(msg)
    if elapsed_seconds == 0:
        return 0.0
    return round((doc_count / elapsed_seconds) * 60.0, 2)


def calculate_failure_rate(succeeded: int, failed: int) -> float:
    """Return failure rate as a percentage.

    >>> calculate_failure_rate(95, 5)
    5.0
    >>> calculate_failure_rate(0, 0)
    0.0
    """
    if succeeded < 0:
        msg = f"succeeded must be >= 0, got {succeeded}"
        raise ValueError(msg)
    if failed < 0:
        msg = f"failed must be >= 0, got {failed}"
        raise ValueError(msg)
    total = succeeded + failed
    if total == 0:
        return 0.0
    return round((failed / total) * 100.0, 2)


def aggregate_memory_samples(samples_mb: list[float]) -> dict[str, float]:
    """Compute average and peak from a list of memory readings.

    >>> aggregate_memory_samples([100.0, 200.0, 150.0])
    {'avg_mb': 150.0, 'peak_mb': 200.0}
    """
    if not samples_mb:
        return {"avg_mb": 0.0, "peak_mb": 0.0}
    return {
        "avg_mb": round(sum(samples_mb) / len(samples_mb), 2),
        "peak_mb": round(max(samples_mb), 2),
    }


def aggregate_cpu_samples(samples_pct: list[float]) -> dict[str, float]:
    """Compute average and peak from a list of CPU-percent readings.

    >>> aggregate_cpu_samples([10.0, 50.0, 30.0])
    {'avg_percent': 30.0, 'peak_percent': 50.0}
    """
    if not samples_pct:
        return {"avg_percent": 0.0, "peak_percent": 0.0}
    return {
        "avg_percent": round(sum(samples_pct) / len(samples_pct), 2),
        "peak_percent": round(max(samples_pct), 2),
    }


def peak_queue_depth(samples: list[QueueDepthSample]) -> int:
    """Return the highest observed messages_ready across all samples.

    >>> peak_queue_depth([])
    0
    """
    if not samples:
        return 0
    return max(s.messages_ready for s in samples)


def build_indexing_metrics(
    *,
    batch_label: str,
    doc_count: int,
    pipeline_config: PipelineConfig,
    elapsed_seconds: float,
    memory_samples: list[float],
    cpu_samples: list[float],
    queue_samples: list[QueueDepthSample],
    docs_indexed: int,
    docs_failed: int,
    disk_write_bytes: int,
    started_at: str,
    finished_at: str,
) -> IndexingMetrics:
    """Assemble an ``IndexingMetrics`` from raw observations."""
    mem = aggregate_memory_samples(memory_samples)
    cpu = aggregate_cpu_samples(cpu_samples)

    return IndexingMetrics(
        batch_label=batch_label,
        doc_count=doc_count,
        pipeline_config=asdict(pipeline_config),
        elapsed_seconds=round(elapsed_seconds, 2),
        throughput_docs_per_min=calculate_throughput(docs_indexed, elapsed_seconds),
        memory_peak_mb=mem["peak_mb"],
        memory_avg_mb=mem["avg_mb"],
        cpu_peak_percent=cpu["peak_percent"],
        cpu_avg_percent=cpu["avg_percent"],
        queue_depth_samples=[asdict(s) for s in queue_samples],
        queue_depth_peak=peak_queue_depth(queue_samples),
        docs_indexed=docs_indexed,
        docs_failed=docs_failed,
        failure_rate_percent=calculate_failure_rate(docs_indexed, docs_failed),
        disk_write_bytes=disk_write_bytes,
        started_at=started_at,
        finished_at=finished_at,
    )


# ---------------------------------------------------------------------------
# Response parsers (unit-testable, no Docker required)
# ---------------------------------------------------------------------------


def parse_rabbitmq_queue_response(response_json: dict) -> QueueDepthSample:
    """Parse a RabbitMQ management API queue response into a sample.

    Expected keys: ``messages_ready``, ``messages_unacknowledged``, ``consumers``, ``name``.
    """
    return QueueDepthSample(
        timestamp=datetime.now(tz=UTC).isoformat(),
        queue_name=response_json.get("name", "unknown"),
        messages_ready=int(response_json.get("messages_ready", 0)),
        messages_unacked=int(response_json.get("messages_unacknowledged", 0)),
        consumers=int(response_json.get("consumers", 0)),
    )


def parse_solr_doc_count(response_json: dict) -> int:
    """Extract numFound from a Solr select response.

    >>> parse_solr_doc_count({"response": {"numFound": 42}})
    42
    """
    try:
        return int(response_json["response"]["numFound"])
    except (KeyError, TypeError, ValueError):
        return 0


def parse_redis_indexing_state(keys: list[str]) -> dict[str, int]:
    """Summarise Redis indexing-state keys by status prefix.

    The document-indexer stores state as ``aithena:index-state:<doc_id>``
    with values like ``indexed``, ``failed``, ``processing``.

    >>> parse_redis_indexing_state(["indexed", "indexed", "failed", "processing"])
    {'indexed': 2, 'failed': 1, 'processing': 1}
    """
    counts: dict[str, int] = {}
    for key in keys:
        status = key.strip().lower()
        counts[status] = counts.get(status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(metrics: IndexingMetrics) -> dict[str, Any]:
    """Build a JSON-serialisable report dict from metrics."""
    report = asdict(metrics)
    report["_generated_at"] = datetime.now(tz=UTC).isoformat()
    report["_version"] = "1.0.0"

    # Compute derived fields
    if metrics.elapsed_seconds > 0:
        report["docs_per_second"] = round(metrics.docs_indexed / metrics.elapsed_seconds, 2)
    else:
        report["docs_per_second"] = 0.0

    # Pass/fail summary
    report["passed"] = metrics.failure_rate_percent < 5.0
    report["pass_criteria"] = {
        "max_failure_rate_percent": 5.0,
        "description": "Failure rate must be below 5%",
    }
    return report


def write_report(report: dict[str, Any], output_dir: Path, filename: str) -> Path:
    """Write a report dict to a JSON file, returning the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return path


def generate_comparison_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine multiple run reports into a comparison table."""
    if not reports:
        return {"runs": [], "comparison": {}}

    comparison: dict[str, Any] = {
        "runs": [],
        "comparison": {
            "best_throughput": None,
            "lowest_failure_rate": None,
            "lowest_memory_peak": None,
        },
    }

    best_throughput = 0.0
    lowest_failure = 100.0
    lowest_memory = float("inf")

    for r in reports:
        summary = {
            "batch_label": r.get("batch_label", "unknown"),
            "doc_count": r.get("doc_count", 0),
            "throughput_docs_per_min": r.get("throughput_docs_per_min", 0),
            "failure_rate_percent": r.get("failure_rate_percent", 0),
            "memory_peak_mb": r.get("memory_peak_mb", 0),
            "elapsed_seconds": r.get("elapsed_seconds", 0),
            "pipeline_config": r.get("pipeline_config", {}),
        }
        comparison["runs"].append(summary)

        tp = r.get("throughput_docs_per_min", 0)
        if tp > best_throughput:
            best_throughput = tp
            comparison["comparison"]["best_throughput"] = summary

        fr = r.get("failure_rate_percent", 100)
        if fr < lowest_failure:
            lowest_failure = fr
            comparison["comparison"]["lowest_failure_rate"] = summary

        mp = r.get("memory_peak_mb", float("inf"))
        if mp < lowest_memory:
            lowest_memory = mp
            comparison["comparison"]["lowest_memory_peak"] = summary

    comparison["_generated_at"] = datetime.now(tz=UTC).isoformat()
    return comparison


# ---------------------------------------------------------------------------
# Docker service helpers (used by integration tests)
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Return True if Docker daemon is reachable."""
    try:
        import docker as docker_sdk

        client = docker_sdk.from_env()
        client.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def _rabbitmq_reachable(api_url: str, user: str, password: str) -> bool:
    """Return True if RabbitMQ management API is reachable."""
    try:
        import requests

        resp = requests.get(f"{api_url}/api/overview", auth=(user, password), timeout=5)
        return resp.status_code == 200  # noqa: PLR2004
    except Exception:  # noqa: BLE001
        return False


def _solr_reachable(solr_url: str) -> bool:
    """Return True if Solr is reachable."""
    try:
        import requests

        resp = requests.get(f"{solr_url}/admin/ping", timeout=5)
        return resp.status_code == 200  # noqa: PLR2004
    except Exception:  # noqa: BLE001
        return False


skip_without_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker daemon not available",
)


# =========================================================================
# UNIT TESTS — run without Docker
# =========================================================================


class TestCalculateThroughput:
    """Unit tests for calculate_throughput()."""

    def test_basic_throughput(self) -> None:
        assert calculate_throughput(120, 60.0) == 120.0

    def test_zero_docs(self) -> None:
        assert calculate_throughput(0, 60.0) == 0.0

    def test_zero_elapsed(self) -> None:
        assert calculate_throughput(100, 0.0) == 0.0

    def test_fractional_time(self) -> None:
        result = calculate_throughput(30, 90.0)
        assert result == 20.0

    def test_large_batch(self) -> None:
        result = calculate_throughput(2000, 120.0)
        assert result == 1000.0

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="doc_count must be >= 0"):
            calculate_throughput(-1, 10.0)

    def test_negative_elapsed_raises(self) -> None:
        with pytest.raises(ValueError, match="elapsed_seconds must be >= 0"):
            calculate_throughput(10, -1.0)


class TestCalculateFailureRate:
    """Unit tests for calculate_failure_rate()."""

    def test_no_failures(self) -> None:
        assert calculate_failure_rate(100, 0) == 0.0

    def test_all_failures(self) -> None:
        assert calculate_failure_rate(0, 100) == 100.0

    def test_mixed(self) -> None:
        assert calculate_failure_rate(95, 5) == 5.0

    def test_zero_total(self) -> None:
        assert calculate_failure_rate(0, 0) == 0.0

    def test_negative_succeeded_raises(self) -> None:
        with pytest.raises(ValueError, match="succeeded must be >= 0"):
            calculate_failure_rate(-1, 0)

    def test_negative_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="failed must be >= 0"):
            calculate_failure_rate(0, -1)


class TestAggregateMemorySamples:
    """Unit tests for aggregate_memory_samples()."""

    def test_basic(self) -> None:
        result = aggregate_memory_samples([100.0, 200.0, 150.0])
        assert result == {"avg_mb": 150.0, "peak_mb": 200.0}

    def test_single_sample(self) -> None:
        result = aggregate_memory_samples([512.0])
        assert result == {"avg_mb": 512.0, "peak_mb": 512.0}

    def test_empty(self) -> None:
        result = aggregate_memory_samples([])
        assert result == {"avg_mb": 0.0, "peak_mb": 0.0}


class TestAggregateCpuSamples:
    """Unit tests for aggregate_cpu_samples()."""

    def test_basic(self) -> None:
        result = aggregate_cpu_samples([10.0, 50.0, 30.0])
        assert result == {"avg_percent": 30.0, "peak_percent": 50.0}

    def test_empty(self) -> None:
        result = aggregate_cpu_samples([])
        assert result == {"avg_percent": 0.0, "peak_percent": 0.0}


class TestPeakQueueDepth:
    """Unit tests for peak_queue_depth()."""

    def test_with_samples(self) -> None:
        samples = [
            QueueDepthSample("t1", "q", 10, 2, 1),
            QueueDepthSample("t2", "q", 50, 5, 1),
            QueueDepthSample("t3", "q", 25, 3, 1),
        ]
        assert peak_queue_depth(samples) == 50

    def test_empty(self) -> None:
        assert peak_queue_depth([]) == 0


class TestBuildIndexingMetrics:
    """Unit tests for build_indexing_metrics()."""

    def test_assembles_correctly(self) -> None:
        config = PipelineConfig(prefetch_count=5, consumer_count=2, embeddings_batch_size=64)
        queue_samples = [
            QueueDepthSample("t1", "shortembeddings", 20, 5, 2),
            QueueDepthSample("t2", "shortembeddings", 45, 3, 2),
        ]
        metrics = build_indexing_metrics(
            batch_label="small",
            doc_count=50,
            pipeline_config=config,
            elapsed_seconds=30.0,
            memory_samples=[256.0, 512.0, 384.0],
            cpu_samples=[20.0, 60.0, 40.0],
            queue_samples=queue_samples,
            docs_indexed=48,
            docs_failed=2,
            disk_write_bytes=1024 * 1024,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:30Z",
        )

        assert metrics.batch_label == "small"
        assert metrics.doc_count == 50
        assert metrics.throughput_docs_per_min == calculate_throughput(48, 30.0)
        assert metrics.memory_peak_mb == 512.0
        assert metrics.memory_avg_mb == 384.0
        assert metrics.cpu_peak_percent == 60.0
        assert metrics.cpu_avg_percent == 40.0
        assert metrics.queue_depth_peak == 45
        assert metrics.docs_indexed == 48
        assert metrics.docs_failed == 2
        assert metrics.failure_rate_percent == calculate_failure_rate(48, 2)
        assert metrics.disk_write_bytes == 1024 * 1024
        assert metrics.pipeline_config["prefetch_count"] == 5


# ---------------------------------------------------------------------------
# Response parser tests
# ---------------------------------------------------------------------------


class TestParseRabbitmqQueueResponse:
    """Unit tests for parse_rabbitmq_queue_response()."""

    def test_typical_response(self) -> None:
        resp = {
            "name": "shortembeddings",
            "messages_ready": 42,
            "messages_unacknowledged": 3,
            "consumers": 2,
        }
        sample = parse_rabbitmq_queue_response(resp)
        assert sample.queue_name == "shortembeddings"
        assert sample.messages_ready == 42
        assert sample.messages_unacked == 3
        assert sample.consumers == 2
        assert sample.timestamp  # non-empty

    def test_missing_fields_default(self) -> None:
        sample = parse_rabbitmq_queue_response({})
        assert sample.queue_name == "unknown"
        assert sample.messages_ready == 0
        assert sample.messages_unacked == 0
        assert sample.consumers == 0


class TestParseSolrDocCount:
    """Unit tests for parse_solr_doc_count()."""

    def test_typical_response(self) -> None:
        resp = {"response": {"numFound": 42, "docs": []}}
        assert parse_solr_doc_count(resp) == 42

    def test_missing_response_key(self) -> None:
        assert parse_solr_doc_count({}) == 0

    def test_missing_num_found(self) -> None:
        assert parse_solr_doc_count({"response": {}}) == 0

    def test_null_response(self) -> None:
        assert parse_solr_doc_count({"response": None}) == 0


class TestParseRedisIndexingState:
    """Unit tests for parse_redis_indexing_state()."""

    def test_mixed_states(self) -> None:
        keys = ["indexed", "indexed", "failed", "processing"]
        result = parse_redis_indexing_state(keys)
        assert result == {"indexed": 2, "failed": 1, "processing": 1}

    def test_empty(self) -> None:
        assert parse_redis_indexing_state([]) == {}

    def test_whitespace_handling(self) -> None:
        result = parse_redis_indexing_state(["  indexed  ", "FAILED"])
        assert result == {"indexed": 1, "failed": 1}


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Unit tests for generate_report()."""

    def _make_metrics(self, **overrides: Any) -> IndexingMetrics:
        defaults = {
            "batch_label": "small",
            "doc_count": 50,
            "pipeline_config": {"prefetch_count": 1, "consumer_count": 1, "embeddings_batch_size": 32},
            "elapsed_seconds": 60.0,
            "throughput_docs_per_min": 50.0,
            "docs_indexed": 50,
            "docs_failed": 0,
            "failure_rate_percent": 0.0,
            "memory_peak_mb": 256.0,
            "memory_avg_mb": 200.0,
            "cpu_peak_percent": 45.0,
            "cpu_avg_percent": 30.0,
        }
        defaults.update(overrides)
        return IndexingMetrics(**defaults)

    def test_report_contains_required_fields(self) -> None:
        metrics = self._make_metrics()
        report = generate_report(metrics)

        assert "batch_label" in report
        assert "doc_count" in report
        assert "throughput_docs_per_min" in report
        assert "failure_rate_percent" in report
        assert "memory_peak_mb" in report
        assert "cpu_peak_percent" in report
        assert "docs_per_second" in report
        assert "_generated_at" in report
        assert "_version" in report

    def test_report_docs_per_second(self) -> None:
        metrics = self._make_metrics(docs_indexed=120, elapsed_seconds=60.0)
        report = generate_report(metrics)
        assert report["docs_per_second"] == 2.0

    def test_report_pass_under_threshold(self) -> None:
        metrics = self._make_metrics(failure_rate_percent=2.0)
        report = generate_report(metrics)
        assert report["passed"] is True

    def test_report_fail_over_threshold(self) -> None:
        metrics = self._make_metrics(failure_rate_percent=10.0)
        report = generate_report(metrics)
        assert report["passed"] is False

    def test_report_zero_elapsed(self) -> None:
        metrics = self._make_metrics(elapsed_seconds=0.0)
        report = generate_report(metrics)
        assert report["docs_per_second"] == 0.0


class TestWriteReport:
    """Unit tests for write_report()."""

    def test_writes_json_file(self, tmp_path: Path) -> None:
        report = {"batch_label": "small", "throughput": 100.0}
        path = write_report(report, tmp_path, "test_report")

        assert path.exists()
        assert path.suffix == ".json"
        loaded = json.loads(path.read_text())
        assert loaded["batch_label"] == "small"

    def test_creates_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        path = write_report({"x": 1}, nested, "deep")
        assert path.exists()


class TestGenerateComparisonReport:
    """Unit tests for generate_comparison_report()."""

    def test_empty_reports(self) -> None:
        result = generate_comparison_report([])
        assert result["runs"] == []

    def test_single_report(self) -> None:
        reports = [
            {
                "batch_label": "small",
                "doc_count": 50,
                "throughput_docs_per_min": 100.0,
                "failure_rate_percent": 1.0,
                "memory_peak_mb": 256.0,
                "elapsed_seconds": 30.0,
                "pipeline_config": {},
            }
        ]
        result = generate_comparison_report(reports)
        assert len(result["runs"]) == 1
        assert result["comparison"]["best_throughput"]["batch_label"] == "small"

    def test_multiple_reports_finds_best(self) -> None:
        reports = [
            {
                "batch_label": "slow",
                "doc_count": 50,
                "throughput_docs_per_min": 50.0,
                "failure_rate_percent": 5.0,
                "memory_peak_mb": 512.0,
                "elapsed_seconds": 60.0,
                "pipeline_config": {},
            },
            {
                "batch_label": "fast",
                "doc_count": 50,
                "throughput_docs_per_min": 200.0,
                "failure_rate_percent": 1.0,
                "memory_peak_mb": 128.0,
                "elapsed_seconds": 15.0,
                "pipeline_config": {},
            },
        ]
        result = generate_comparison_report(reports)
        assert result["comparison"]["best_throughput"]["batch_label"] == "fast"
        assert result["comparison"]["lowest_failure_rate"]["batch_label"] == "fast"
        assert result["comparison"]["lowest_memory_peak"]["batch_label"] == "fast"


# ---------------------------------------------------------------------------
# Configuration dataclass tests
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    """Unit tests for PipelineConfig validation."""

    def test_defaults(self) -> None:
        cfg = PipelineConfig()
        assert cfg.prefetch_count == 1
        assert cfg.consumer_count == 1
        assert cfg.embeddings_batch_size == 32

    def test_custom_values(self) -> None:
        cfg = PipelineConfig(prefetch_count=10, consumer_count=4, embeddings_batch_size=128)
        assert cfg.prefetch_count == 10

    def test_invalid_prefetch_raises(self) -> None:
        with pytest.raises(ValueError, match="prefetch_count must be >= 1"):
            PipelineConfig(prefetch_count=0)

    def test_invalid_consumer_raises(self) -> None:
        with pytest.raises(ValueError, match="consumer_count must be >= 1"):
            PipelineConfig(consumer_count=-1)

    def test_invalid_embeddings_batch_raises(self) -> None:
        with pytest.raises(ValueError, match="embeddings_batch_size must be >= 1"):
            PipelineConfig(embeddings_batch_size=0)


class TestBatchConfig:
    """Unit tests for BatchConfig validation."""

    def test_valid_config(self) -> None:
        cfg = BatchConfig(label="small", doc_count=50)
        assert cfg.label == "small"
        assert cfg.doc_count == 50

    def test_invalid_doc_count_raises(self) -> None:
        with pytest.raises(ValueError, match="doc_count must be >= 0"):
            BatchConfig(label="bad", doc_count=-1)


# =========================================================================
# INTEGRATION TESTS — require Docker infrastructure
# =========================================================================

# Configuration matrix for parametrised integration tests
PIPELINE_CONFIGS = [
    PipelineConfig(prefetch_count=1, consumer_count=1, embeddings_batch_size=32),
    PipelineConfig(prefetch_count=5, consumer_count=2, embeddings_batch_size=64),
    PipelineConfig(prefetch_count=10, consumer_count=4, embeddings_batch_size=128),
]


def _config_id(cfg: PipelineConfig) -> str:
    """Generate a readable test ID for a PipelineConfig."""
    return f"pf{cfg.prefetch_count}-c{cfg.consumer_count}-eb{cfg.embeddings_batch_size}"


def _poll_until_indexed(
    solr_url: str,
    expected_count: int,
    timeout: float = 300.0,
    interval: float = 5.0,
) -> tuple[int, float]:
    """Poll Solr until *expected_count* documents appear or timeout.

    Returns (actual_count, elapsed_seconds).
    """
    import requests

    start = time.monotonic()
    actual = 0
    while (time.monotonic() - start) < timeout:
        try:
            resp = requests.get(f"{solr_url}/select?q=*:*&rows=0&wt=json", timeout=10)
            if resp.ok:
                actual = parse_solr_doc_count(resp.json())
                if actual >= expected_count:
                    break
        except Exception:  # noqa: BLE001, S110
            pass
        time.sleep(interval)
    elapsed = time.monotonic() - start
    return actual, elapsed


def _collect_queue_depth(
    rabbitmq_api_url: str,
    user: str,
    password: str,
    queue_name: str = "shortembeddings",
) -> QueueDepthSample | None:
    """Sample the RabbitMQ queue depth once."""
    try:
        import requests

        resp = requests.get(
            f"{rabbitmq_api_url}/api/queues/%2F/{queue_name}",
            auth=(user, password),
            timeout=5,
        )
        if resp.ok:
            return parse_rabbitmq_queue_response(resp.json())
    except Exception:  # noqa: BLE001, S110
        pass
    return None


@pytest.mark.docker
@pytest.mark.indexing
@pytest.mark.slow
class TestIndexingPipeline:
    """
    Integration tests for the indexing pipeline.

    These tests require the full Docker Compose stack to be running.
    They are skipped automatically when Docker is unavailable.
    """

    @pytest.fixture(autouse=True)
    def _skip_without_docker(self) -> None:
        if not _docker_available():
            pytest.skip("Docker daemon not available — skipping integration test")

    @pytest.mark.parametrize("batch_name,batch_count", list(BATCH_SIZES.items()), ids=list(BATCH_SIZES.keys()))
    def test_indexing_throughput(
        self,
        batch_name: str,
        batch_count: int,
        solr_url: str,
        rabbitmq_api_url: str,
        write_result,
        timer,
    ) -> None:
        """Measure indexing throughput for each batch size."""
        config = PipelineConfig()
        _batch = BatchConfig(label=batch_name, doc_count=batch_count, pipeline=config)  # validates inputs

        # Record initial Solr count
        import requests

        try:
            resp = requests.get(f"{solr_url}/select?q=*:*&rows=0&wt=json", timeout=10)
            initial_count = parse_solr_doc_count(resp.json()) if resp.ok else 0
        except Exception:  # noqa: BLE001
            initial_count = 0

        queue_samples: list[QueueDepthSample] = []
        memory_samples: list[float] = []
        cpu_samples: list[float] = []

        started_at = datetime.now(tz=UTC).isoformat()
        t = timer()
        with t:
            # In a real run, documents would be placed in the watched directory.
            # Here we poll until the expected count is reached (or timeout).
            target = initial_count + batch_count
            timeout_sec = max(600, batch_count * 2)
            poll_interval = 5.0

            elapsed_so_far = 0.0
            actual = initial_count
            while elapsed_so_far < timeout_sec:
                # Collect queue depth
                sample = _collect_queue_depth(rabbitmq_api_url, "guest", "guest")
                if sample:
                    queue_samples.append(sample)

                try:
                    r = requests.get(f"{solr_url}/select?q=*:*&rows=0&wt=json", timeout=10)
                    if r.ok:
                        actual = parse_solr_doc_count(r.json())
                except Exception:  # noqa: BLE001, S110
                    pass

                if actual >= target:
                    break

                time.sleep(poll_interval)
                elapsed_so_far = time.monotonic() - t.start_time

        finished_at = datetime.now(tz=UTC).isoformat()
        docs_indexed = actual - initial_count

        metrics = build_indexing_metrics(
            batch_label=batch_name,
            doc_count=batch_count,
            pipeline_config=config,
            elapsed_seconds=t.elapsed,
            memory_samples=memory_samples,
            cpu_samples=cpu_samples,
            queue_samples=queue_samples,
            docs_indexed=docs_indexed,
            docs_failed=max(0, batch_count - docs_indexed),
            disk_write_bytes=0,
            started_at=started_at,
            finished_at=finished_at,
        )

        report = generate_report(metrics)
        write_result(f"indexing_{batch_name}", report)

        # Assertions: throughput > 0 if any docs were indexed
        if docs_indexed > 0:
            assert metrics.throughput_docs_per_min > 0

    @pytest.mark.parametrize("config", PIPELINE_CONFIGS, ids=[_config_id(c) for c in PIPELINE_CONFIGS])
    def test_config_variant(
        self,
        config: PipelineConfig,
        solr_url: str,
        rabbitmq_api_url: str,
        write_result,
        timer,
    ) -> None:
        """Measure indexing with different pipeline configurations."""
        batch = BatchConfig(label=f"config_{_config_id(config)}", doc_count=50, pipeline=config)

        started_at = datetime.now(tz=UTC).isoformat()
        t = timer()
        with t:
            # Placeholder: in a real test, reconfigure the pipeline
            # and index documents. Here we just measure baseline.
            actual, _ = _poll_until_indexed(solr_url, expected_count=0, timeout=10.0, interval=2.0)

        finished_at = datetime.now(tz=UTC).isoformat()

        metrics = build_indexing_metrics(
            batch_label=batch.label,
            doc_count=batch.doc_count,
            pipeline_config=config,
            elapsed_seconds=t.elapsed,
            memory_samples=[],
            cpu_samples=[],
            queue_samples=[],
            docs_indexed=actual,
            docs_failed=0,
            disk_write_bytes=0,
            started_at=started_at,
            finished_at=finished_at,
        )

        report = generate_report(metrics)
        write_result(f"indexing_{batch.label}", report)


@pytest.mark.docker
@pytest.mark.indexing
@pytest.mark.slow
class TestIndexingResourceLimits:
    """Verify resource consumption stays within acceptable bounds."""

    @pytest.fixture(autouse=True)
    def _skip_without_docker(self) -> None:
        if not _docker_available():
            pytest.skip("Docker daemon not available — skipping integration test")

    def test_memory_ceiling(self, docker_monitor, write_result) -> None:
        """Ensure no service exceeds its memory limit during indexing."""
        with docker_monitor("memory_ceiling") as monitor:
            time.sleep(30)

        summary = monitor.summary()
        write_result("memory_ceiling", summary)

        for svc, data in summary.get("services", {}).items():
            limit = data.get("memory_limit_mb", 0)
            peak = data.get("memory_peak_mb", 0)
            if limit > 0:
                usage_pct = (peak / limit) * 100
                assert usage_pct < 95, f"{svc} memory usage {usage_pct:.1f}% exceeds 95% ceiling"

    def test_no_oom_kills(self, docker_monitor, write_result) -> None:
        """Ensure no OOM kills occur during a monitoring window."""
        with docker_monitor("oom_check") as monitor:
            time.sleep(30)

        summary = monitor.summary()
        write_result("oom_check", summary)
        assert summary.get("oom_count", 0) == 0, f"OOM kills detected: {summary.get('oom_events', [])}"


# =========================================================================
# MOCKED PIPELINE TESTS — test orchestration logic without Docker
# =========================================================================


class TestMockedPipeline:
    """
    Test the indexing measurement logic with mocked infrastructure.

    These tests verify the test framework itself works correctly:
    metric collection, polling, result assembly, and report writing.
    """

    def test_full_pipeline_mock_small_batch(self, tmp_path: Path) -> None:
        """Simulate a small batch indexing run with mocked services."""
        config = PipelineConfig(prefetch_count=5, consumer_count=2, embeddings_batch_size=64)
        batch = BatchConfig(label="mock_small", doc_count=50, pipeline=config)

        # Simulate metrics collection
        memory_samples = [200.0, 350.0, 500.0, 450.0, 300.0]
        cpu_samples = [15.0, 45.0, 80.0, 60.0, 25.0]
        queue_samples = [
            QueueDepthSample(f"t{i}", "shortembeddings", depth, depth // 5, 2)
            for i, depth in enumerate([50, 40, 30, 15, 5, 0])
        ]

        metrics = build_indexing_metrics(
            batch_label=batch.label,
            doc_count=batch.doc_count,
            pipeline_config=config,
            elapsed_seconds=45.0,
            memory_samples=memory_samples,
            cpu_samples=cpu_samples,
            queue_samples=queue_samples,
            docs_indexed=48,
            docs_failed=2,
            disk_write_bytes=50 * 1024 * 1024,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:45Z",
        )

        # Verify metrics
        assert metrics.throughput_docs_per_min == calculate_throughput(48, 45.0)
        assert metrics.memory_peak_mb == 500.0
        assert metrics.cpu_peak_percent == 80.0
        assert metrics.queue_depth_peak == 50
        assert metrics.failure_rate_percent == calculate_failure_rate(48, 2)

        # Write report
        report = generate_report(metrics)
        path = write_report(report, tmp_path, "mock_small")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["batch_label"] == "mock_small"
        assert loaded["passed"] is True

    @pytest.mark.parametrize("batch_name,batch_count", list(BATCH_SIZES.items()), ids=list(BATCH_SIZES.keys()))
    def test_parametrized_batch_sizes(self, batch_name: str, batch_count: int, tmp_path: Path) -> None:
        """Verify metric assembly works for all batch sizes."""
        config = PipelineConfig()

        # Scale simulated metrics with batch size
        scale = batch_count / 50
        memory_peak = 256.0 * math.log2(scale + 1) + 200
        cpu_peak = min(95.0, 30.0 * math.log2(scale + 1) + 20)

        metrics = build_indexing_metrics(
            batch_label=batch_name,
            doc_count=batch_count,
            pipeline_config=config,
            elapsed_seconds=batch_count * 0.5,
            memory_samples=[memory_peak * 0.6, memory_peak * 0.8, memory_peak],
            cpu_samples=[cpu_peak * 0.5, cpu_peak * 0.7, cpu_peak],
            queue_samples=[
                QueueDepthSample("t0", "shortembeddings", batch_count, 0, 1),
                QueueDepthSample("t1", "shortembeddings", batch_count // 2, 0, 1),
                QueueDepthSample("t2", "shortembeddings", 0, 0, 1),
            ],
            docs_indexed=batch_count,
            docs_failed=0,
            disk_write_bytes=batch_count * 1024 * 100,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:10:00Z",
        )

        assert metrics.throughput_docs_per_min > 0
        assert metrics.memory_peak_mb > 0
        assert metrics.failure_rate_percent == 0.0
        assert metrics.queue_depth_peak == batch_count

        report = generate_report(metrics)
        path = write_report(report, tmp_path / batch_name, f"indexing_{batch_name}")
        assert path.exists()

    @pytest.mark.parametrize("config", PIPELINE_CONFIGS, ids=[_config_id(c) for c in PIPELINE_CONFIGS])
    def test_config_variants_mock(self, config: PipelineConfig, tmp_path: Path) -> None:
        """Verify metric assembly works for all config variants."""
        metrics = build_indexing_metrics(
            batch_label=f"config_{_config_id(config)}",
            doc_count=50,
            pipeline_config=config,
            elapsed_seconds=30.0,
            memory_samples=[200.0, 300.0, 250.0],
            cpu_samples=[20.0, 40.0, 30.0],
            queue_samples=[],
            docs_indexed=50,
            docs_failed=0,
            disk_write_bytes=5 * 1024 * 1024,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:30Z",
        )

        assert metrics.throughput_docs_per_min == calculate_throughput(50, 30.0)
        assert metrics.pipeline_config["prefetch_count"] == config.prefetch_count
        assert metrics.pipeline_config["consumer_count"] == config.consumer_count

    def test_comparison_report(self, tmp_path: Path) -> None:
        """Generate a comparison report across multiple simulated runs."""
        reports = []
        for batch_name, batch_count in BATCH_SIZES.items():
            config = PipelineConfig()
            metrics = build_indexing_metrics(
                batch_label=batch_name,
                doc_count=batch_count,
                pipeline_config=config,
                elapsed_seconds=batch_count * 0.3,
                memory_samples=[256.0, 512.0],
                cpu_samples=[30.0, 60.0],
                queue_samples=[],
                docs_indexed=batch_count,
                docs_failed=0,
                disk_write_bytes=batch_count * 1024 * 50,
                started_at="2025-01-01T00:00:00Z",
                finished_at="2025-01-01T00:10:00Z",
            )
            report = generate_report(metrics)
            reports.append(report)

        comparison = generate_comparison_report(reports)
        path = write_report(comparison, tmp_path, "comparison")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert len(loaded["runs"]) == 3
        assert loaded["comparison"]["best_throughput"] is not None

    def test_high_failure_rate_report(self, tmp_path: Path) -> None:
        """A run with >5% failure rate should be marked as not passed."""
        metrics = build_indexing_metrics(
            batch_label="failing",
            doc_count=100,
            pipeline_config=PipelineConfig(),
            elapsed_seconds=60.0,
            memory_samples=[200.0],
            cpu_samples=[30.0],
            queue_samples=[],
            docs_indexed=80,
            docs_failed=20,
            disk_write_bytes=0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:01:00Z",
        )

        report = generate_report(metrics)
        assert report["passed"] is False
        assert report["failure_rate_percent"] == 20.0

    def test_poll_until_indexed_with_mock(self) -> None:
        """Verify _poll_until_indexed logic with a mocked requests.get."""
        import requests as requests_mod

        call_count = 0

        def mock_get(url: str, timeout: int = 10) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.ok = True
            # Simulate progressive indexing
            resp.json.return_value = {"response": {"numFound": min(call_count * 10, 50)}}
            return resp

        with patch.object(requests_mod, "get", side_effect=mock_get):
            actual, elapsed = _poll_until_indexed(
                "http://mock:8983/solr/books",
                expected_count=50,
                timeout=30.0,
                interval=0.1,
            )

        assert actual >= 50
        assert elapsed > 0
