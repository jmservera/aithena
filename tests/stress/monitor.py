"""
Docker resource monitoring collector for stress tests.

Captures per-service metrics during test runs:
- CPU usage (average/peak %)
- Memory usage (average/peak MB)
- Disk I/O (read/write bytes)
- Network I/O (rx/tx bytes)
- Solr heap usage (via Solr admin API)
- RabbitMQ queue depth (via management API)
- Redis memory usage (via INFO memory)
- OOM kill detection (via Docker events API)

Usage as a context manager:
    collector = DockerStatsCollector(interval=2, output_dir=Path("results"), label="test_run")
    with collector:
        # ... run workload ...
        pass
    summary = collector.summary()

Usage as a pytest fixture:
    See conftest.py ``docker_monitor`` fixture.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import docker
import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_INTERVAL = 2.0
DEFAULT_COMPOSE_PROJECT = os.environ.get("COMPOSE_PROJECT", "aithena")
SOLR_ADMIN_URL = os.environ.get("SOLR_ADMIN_URL", "http://localhost:8983")
RABBITMQ_API_URL = os.environ.get("RABBITMQ_API_URL", "http://localhost:15672")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "guest")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ServiceSample:
    """A single point-in-time resource sample for one container."""

    timestamp: str
    service: str
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: float
    memory_percent: float
    net_rx_bytes: int
    net_tx_bytes: int
    block_read_bytes: int
    block_write_bytes: int


@dataclass
class OOMEvent:
    """Record of a container OOM kill event."""

    timestamp: str
    container_name: str
    container_id: str


@dataclass
class ServiceMetricSample:
    """A single point-in-time service-specific metric sample."""

    timestamp: str
    source: str
    metrics: dict


@dataclass
class CollectorResult:
    """Aggregated result from a monitoring session."""

    label: str
    start_time: str
    end_time: str
    duration_seconds: float
    samples: list[ServiceSample] = field(default_factory=list)
    service_metrics: list[ServiceMetricSample] = field(default_factory=list)
    oom_events: list[OOMEvent] = field(default_factory=list)

    def summary(self) -> dict:
        """Compute per-service aggregate metrics."""
        by_service: dict[str, list[ServiceSample]] = defaultdict(list)
        for s in self.samples:
            by_service[s.service].append(s)

        service_summaries = {}
        for svc, samples in sorted(by_service.items()):
            cpus = [s.cpu_percent for s in samples]
            mems = [s.memory_mb for s in samples]
            service_summaries[svc] = {
                "sample_count": len(samples),
                "cpu_avg_percent": round(sum(cpus) / len(cpus), 2) if cpus else 0,
                "cpu_peak_percent": round(max(cpus), 2) if cpus else 0,
                "memory_avg_mb": round(sum(mems) / len(mems), 2) if mems else 0,
                "memory_peak_mb": round(max(mems), 2) if mems else 0,
                "memory_limit_mb": round(samples[-1].memory_limit_mb, 2) if samples else 0,
                "net_rx_bytes_session": samples[-1].net_rx_bytes - samples[0].net_rx_bytes if len(samples) > 1 else 0,
                "net_tx_bytes_session": samples[-1].net_tx_bytes - samples[0].net_tx_bytes if len(samples) > 1 else 0,
                "block_read_bytes_session": (
                    samples[-1].block_read_bytes - samples[0].block_read_bytes if len(samples) > 1 else 0
                ),
                "block_write_bytes_session": (
                    samples[-1].block_write_bytes - samples[0].block_write_bytes if len(samples) > 1 else 0
                ),
            }

        # Collect service-specific metrics summaries
        service_specific = defaultdict(list)
        for sm in self.service_metrics:
            service_specific[sm.source].append(sm.metrics)

        return {
            "label": self.label,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.duration_seconds, 2),
            "services": service_summaries,
            "service_specific_metrics": {
                src: samples for src, samples in sorted(service_specific.items())
            },
            "oom_events": [
                {"timestamp": e.timestamp, "container": e.container_name}
                for e in self.oom_events
            ],
            "oom_count": len(self.oom_events),
        }


# ---------------------------------------------------------------------------
# Helpers: parse docker stats
# ---------------------------------------------------------------------------


def _calculate_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from Docker stats API response."""
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})

    cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get("cpu_usage", {}).get(
        "total_usage", 0
    )
    system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)

    if system_delta > 0 and cpu_delta >= 0:
        online_cpus = cpu_stats.get("online_cpus", 1) or 1
        return round((cpu_delta / system_delta) * online_cpus * 100.0, 2)
    return 0.0


def _calculate_memory(stats: dict) -> tuple[float, float]:
    """Return (usage_mb, limit_mb) from Docker stats."""
    mem = stats.get("memory_stats", {})
    usage = mem.get("usage", 0)
    # Subtract cache for more accurate active memory
    cache = mem.get("stats", {}).get("cache", 0)
    active = max(usage - cache, 0)
    limit = mem.get("limit", 0)
    return round(active / (1024 * 1024), 2), round(limit / (1024 * 1024), 2)


def _calculate_network_io(stats: dict) -> tuple[int, int]:
    """Return (rx_bytes, tx_bytes) summed across all interfaces."""
    networks = stats.get("networks", {})
    rx = sum(iface.get("rx_bytes", 0) for iface in networks.values())
    tx = sum(iface.get("tx_bytes", 0) for iface in networks.values())
    return rx, tx


def _calculate_block_io(stats: dict) -> tuple[int, int]:
    """Return (read_bytes, write_bytes) from block I/O stats."""
    bio = stats.get("blkio_stats", {}).get("io_service_bytes_recursive", []) or []
    read_bytes = sum(entry.get("value", 0) for entry in bio if entry.get("op", "").lower() == "read")
    write_bytes = sum(entry.get("value", 0) for entry in bio if entry.get("op", "").lower() == "write")
    return read_bytes, write_bytes


def _extract_service_name(container_labels: dict, container_name: str) -> str:
    """Extract the Docker Compose service name from container labels."""
    return container_labels.get("com.docker.compose.service", container_name.lstrip("/"))


# ---------------------------------------------------------------------------
# Service-specific metric collectors
# ---------------------------------------------------------------------------


def _collect_solr_heap() -> dict | None:
    """Query Solr admin API for JVM heap usage."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{SOLR_ADMIN_URL}/solr/admin/info/system")
            if resp.status_code == 200:
                data = resp.json()
                jvm = data.get("jvm", {}).get("memory", {})
                return {
                    "heap_used_mb": _parse_solr_memory(jvm.get("used", "0")),
                    "heap_max_mb": _parse_solr_memory(jvm.get("max", "0")),
                    "heap_used_percent": jvm.get("raw", {}).get("used%", 0),
                }
    except Exception as exc:
        logger.debug("Solr heap collection failed: %s", exc)
    return None


def _parse_solr_memory(value: str) -> float:
    """Parse Solr memory string like '256.5 MB' to float MB."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        parts = str(value).strip().split()
        num = float(parts[0])
        if len(parts) > 1:
            unit = parts[1].upper()
            if unit == "GB":
                num *= 1024
            elif unit == "KB":
                num /= 1024
        return round(num, 2)
    except (ValueError, IndexError):
        return 0.0


def _collect_rabbitmq_queue_depth() -> dict | None:
    """Query RabbitMQ management API for queue depths."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(
                f"{RABBITMQ_API_URL}/api/queues",
                auth=(RABBITMQ_USER, RABBITMQ_PASSWORD),
            )
            if resp.status_code == 200:
                queues = resp.json()
                return {
                    q["name"]: {
                        "messages": q.get("messages", 0),
                        "messages_ready": q.get("messages_ready", 0),
                        "messages_unacknowledged": q.get("messages_unacknowledged", 0),
                        "consumers": q.get("consumers", 0),
                    }
                    for q in queues
                    if isinstance(q, dict)
                }
    except Exception as exc:
        logger.debug("RabbitMQ queue depth collection failed: %s", exc)
    return None


def _collect_redis_memory() -> dict | None:
    """Query Redis INFO memory for memory usage stats."""
    try:
        import redis

        conn_kwargs: dict = {"host": REDIS_HOST, "port": REDIS_PORT, "socket_timeout": 5}
        r = redis.Redis(**conn_kwargs)
        info = r.info("memory")
        r.close()
        return {
            "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
            "used_memory_peak_mb": round(info.get("used_memory_peak", 0) / (1024 * 1024), 2),
            "used_memory_rss_mb": round(info.get("used_memory_rss", 0) / (1024 * 1024), 2),
            "mem_fragmentation_ratio": info.get("mem_fragmentation_ratio", 0),
        }
    except Exception as exc:
        logger.debug("Redis memory collection failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# OOM event watcher
# ---------------------------------------------------------------------------


class _OOMWatcher:
    """Background thread that watches Docker events for OOM kills."""

    def __init__(self, client: docker.DockerClient):
        self._client = client
        self._events: list[OOMEvent] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._watch, daemon=True, name="oom-watcher")
        self._thread.start()

    def stop(self) -> list[OOMEvent]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        return list(self._events)

    def _watch(self) -> None:
        try:
            # Docker events API with filter for OOM kills
            for event in self._client.events(
                decode=True,
                filters={"event": ["oom", "die"]},
            ):
                if self._stop.is_set():
                    break
                event_status = event.get("status", "")
                actor = event.get("Actor", {})
                attrs = actor.get("Attributes", {})

                is_oom = event_status == "oom" or (
                    event_status == "die" and attrs.get("exitCode") == "137"
                )

                if is_oom:
                    self._events.append(
                        OOMEvent(
                            timestamp=datetime.now(tz=UTC).isoformat(),
                            container_name=attrs.get("name", "unknown"),
                            container_id=actor.get("ID", "unknown")[:12],
                        )
                    )
        except Exception as exc:
            if not self._stop.is_set():
                logger.debug("OOM watcher error: %s", exc)


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------


class DockerStatsCollector:
    """
    Polls Docker stats and service-specific metrics at a configurable interval.

    Can be used as a context manager or started/stopped manually.

    Args:
        interval: Sampling interval in seconds (default: 2.0).
        output_dir: Directory for JSON output files.
        label: Label for this collection session (used in filenames).
        compose_project: Docker Compose project name for container filtering.
        collect_service_metrics: Whether to poll Solr/RabbitMQ/Redis (default: True).
    """

    def __init__(
        self,
        interval: float = DEFAULT_INTERVAL,
        output_dir: Path | str = Path("results"),
        label: str = "stress_run",
        compose_project: str = DEFAULT_COMPOSE_PROJECT,
        collect_service_metrics: bool = True,
    ):
        self.interval = interval
        self.output_dir = Path(output_dir)
        import re

        self.label = re.sub(r"[^A-Za-z0-9._-]", "_", label)
        self.compose_project = compose_project
        self.collect_service_metrics = collect_service_metrics

        self._client: docker.DockerClient | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._oom_watcher: _OOMWatcher | None = None
        self._result: CollectorResult | None = None
        self._start_time: float = 0

    def start(self) -> None:
        """Start background collection threads."""
        self._client = docker.from_env()
        self._stop.clear()
        self._start_time = time.monotonic()
        start_ts = datetime.now(tz=UTC).isoformat()

        self._result = CollectorResult(
            label=self.label,
            start_time=start_ts,
            end_time="",
            duration_seconds=0,
        )

        # Start OOM watcher
        self._oom_watcher = _OOMWatcher(self._client)
        self._oom_watcher.start()

        # Start stats collection thread
        self._thread = threading.Thread(target=self._collect_loop, daemon=True, name="stats-collector")
        self._thread.start()

        logger.info("Docker stats collector started (interval=%.1fs, label=%s)", self.interval, self.label)

    def stop(self) -> CollectorResult:
        """Stop collection and return aggregated results."""
        self._stop.set()

        if self._thread:
            self._thread.join(timeout=10)

        oom_events = []
        if self._oom_watcher:
            oom_events = self._oom_watcher.stop()

        if self._result:
            self._result.end_time = datetime.now(tz=UTC).isoformat()
            self._result.duration_seconds = time.monotonic() - self._start_time
            self._result.oom_events = oom_events

        if self._client:
            self._client.close()
            self._client = None

        # Write results to disk
        self._write_output()

        logger.info(
            "Docker stats collector stopped: %d samples, %d OOM events",
            len(self._result.samples) if self._result else 0,
            len(oom_events),
        )
        if self._result is None:
            raise RuntimeError("Collector was never started or start() failed before recording results")
        return self._result

    def summary(self) -> dict:
        """Return the aggregated summary. Call after stop()."""
        if self._result is None:
            return {}
        return self._result.summary()

    def __enter__(self) -> DockerStatsCollector:
        self.start()
        return self

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _get_project_containers(self) -> list:
        """Return running containers belonging to the compose project."""
        if not self._client:
            return []
        try:
            return self._client.containers.list(
                filters={"label": f"com.docker.compose.project={self.compose_project}"},
            )
        except Exception as exc:
            logger.debug("Failed to list containers: %s", exc)
            return []

    def _collect_loop(self) -> None:
        """Main collection loop running in a background thread."""
        while not self._stop.is_set():
            try:
                self._collect_once()
            except Exception as exc:
                logger.debug("Collection cycle error: %s", exc)
            self._stop.wait(timeout=self.interval)

    def _collect_once(self) -> None:
        """Perform a single collection cycle."""
        now = datetime.now(tz=UTC).isoformat()
        containers = self._get_project_containers()

        for container in containers:
            try:
                stats = container.stats(stream=False)
                service_name = _extract_service_name(container.labels, container.name)
                cpu = _calculate_cpu_percent(stats)
                mem_mb, mem_limit_mb = _calculate_memory(stats)
                mem_pct = round(mem_mb / mem_limit_mb * 100, 2) if mem_limit_mb > 0 else 0
                net_rx, net_tx = _calculate_network_io(stats)
                blk_read, blk_write = _calculate_block_io(stats)

                sample = ServiceSample(
                    timestamp=now,
                    service=service_name,
                    cpu_percent=cpu,
                    memory_mb=mem_mb,
                    memory_limit_mb=mem_limit_mb,
                    memory_percent=mem_pct,
                    net_rx_bytes=net_rx,
                    net_tx_bytes=net_tx,
                    block_read_bytes=blk_read,
                    block_write_bytes=blk_write,
                )
                if self._result:
                    self._result.samples.append(sample)

            except Exception as exc:
                logger.debug("Stats collection failed for %s: %s", container.name, exc)

        # Collect service-specific metrics
        if self.collect_service_metrics:
            self._collect_service_metrics(now)

    def _collect_service_metrics(self, timestamp: str) -> None:
        """Collect Solr, RabbitMQ, and Redis metrics."""
        if not self._result:
            return

        solr = _collect_solr_heap()
        if solr:
            self._result.service_metrics.append(
                ServiceMetricSample(timestamp=timestamp, source="solr_heap", metrics=solr)
            )

        rabbit = _collect_rabbitmq_queue_depth()
        if rabbit:
            self._result.service_metrics.append(
                ServiceMetricSample(timestamp=timestamp, source="rabbitmq_queues", metrics=rabbit)
            )

        redis_mem = _collect_redis_memory()
        if redis_mem:
            self._result.service_metrics.append(
                ServiceMetricSample(timestamp=timestamp, source="redis_memory", metrics=redis_mem)
            )

    def _write_output(self) -> None:
        """Write collected data to JSON files in the output directory."""
        if not self._result:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts_suffix = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")

        # Write time-series data
        timeseries_path = self.output_dir / f"{self.label}_timeseries_{ts_suffix}.json"
        timeseries_data = {
            "label": self._result.label,
            "start_time": self._result.start_time,
            "end_time": self._result.end_time,
            "duration_seconds": round(self._result.duration_seconds, 2),
            "interval_seconds": self.interval,
            "samples": [
                {
                    "timestamp": s.timestamp,
                    "service": s.service,
                    "cpu_percent": s.cpu_percent,
                    "memory_mb": s.memory_mb,
                    "memory_limit_mb": s.memory_limit_mb,
                    "memory_percent": s.memory_percent,
                    "net_rx_bytes": s.net_rx_bytes,
                    "net_tx_bytes": s.net_tx_bytes,
                    "block_read_bytes": s.block_read_bytes,
                    "block_write_bytes": s.block_write_bytes,
                }
                for s in self._result.samples
            ],
            "service_metrics": [
                {
                    "timestamp": sm.timestamp,
                    "source": sm.source,
                    "metrics": sm.metrics,
                }
                for sm in self._result.service_metrics
            ],
            "oom_events": [
                {
                    "timestamp": e.timestamp,
                    "container_name": e.container_name,
                    "container_id": e.container_id,
                }
                for e in self._result.oom_events
            ],
        }
        timeseries_path.write_text(json.dumps(timeseries_data, indent=2))
        logger.info("Time-series data written to %s", timeseries_path)

        # Write summary
        summary_path = self.output_dir / f"{self.label}_summary_{ts_suffix}.json"
        summary_path.write_text(json.dumps(self._result.summary(), indent=2))
        logger.info("Summary written to %s", summary_path)


# ---------------------------------------------------------------------------
# Standalone context manager (for use outside pytest)
# ---------------------------------------------------------------------------


@contextmanager
def monitor_resources(
    label: str = "stress_run",
    interval: float = DEFAULT_INTERVAL,
    output_dir: Path | str = Path("results"),
    compose_project: str = DEFAULT_COMPOSE_PROJECT,
    collect_service_metrics: bool = True,
):
    """
    Context manager for resource monitoring.

    Usage:
        from tests.stress.monitor import monitor_resources

        with monitor_resources("my_test", output_dir=Path("results")) as collector:
            # ... run workload ...
            pass
        print(collector.summary())
    """
    collector = DockerStatsCollector(
        interval=interval,
        output_dir=Path(output_dir),
        label=label,
        compose_project=compose_project,
        collect_service_metrics=collect_service_metrics,
    )
    collector.start()
    try:
        yield collector
    finally:
        collector.stop()


# ---------------------------------------------------------------------------
# CLI entrypoint for standalone monitoring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import signal

    parser = argparse.ArgumentParser(description="Docker resource monitor for Aithena stress tests")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="Sampling interval in seconds")
    parser.add_argument("--output-dir", type=str, default="tests/stress/results", help="Output directory")
    parser.add_argument("--label", type=str, default="manual_run", help="Label for this monitoring session")
    parser.add_argument("--project", type=str, default=DEFAULT_COMPOSE_PROJECT, help="Docker Compose project name")
    parser.add_argument("--no-service-metrics", action="store_true", help="Skip Solr/RabbitMQ/Redis metrics")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    collector = DockerStatsCollector(
        interval=args.interval,
        output_dir=Path(args.output_dir),
        label=args.label,
        compose_project=args.project,
        collect_service_metrics=not args.no_service_metrics,
    )

    def _handle_signal(signum, frame):
        logger.info("Received signal %s, stopping collector...", signum)
        result = collector.stop()
        summary = result.summary()
        print(json.dumps(summary, indent=2))
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    collector.start()
    logger.info("Monitoring started. Press Ctrl+C to stop.")

    # Block until interrupted
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
