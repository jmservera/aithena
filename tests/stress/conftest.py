"""
Shared fixtures for the Aithena stress test suite.

Provides:
- Docker Compose lifecycle management (start/stop the stack)
- Service URL resolution (Solr, API, RabbitMQ, Redis)
- Test data paths
- Result output helpers (JSON writer, timestamped results directory)
- Docker resource monitor integration

Environment variables (with defaults for the local dev stack):
  COMPOSE_FILE        Path to docker-compose.yml (default: repo root)
  COMPOSE_PROJECT     Docker Compose project name (default: aithena)
  SOLR_URL            Solr base URL (default: http://localhost:8983/solr/books)
  SEARCH_API_URL      solr-search base URL (default: http://localhost:8080)
  RABBITMQ_API_URL    RabbitMQ management URL (default: http://localhost:15672)
  RABBITMQ_USER       RabbitMQ username (default: guest)
  RABBITMQ_PASSWORD   RabbitMQ password (default: guest)
  REDIS_HOST          Redis host (default: localhost)
  REDIS_PORT          Redis port (default: 6379)
  STRESS_RESULTS_DIR  Results output directory (default: tests/stress/results)
  MONITOR_INTERVAL    Docker stats sampling interval in seconds (default: 2)
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STRESS_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = STRESS_DIR / "results"

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

COMPOSE_FILE: str = os.environ.get("COMPOSE_FILE", str(REPO_ROOT / "docker-compose.yml"))
COMPOSE_PROJECT: str = os.environ.get("COMPOSE_PROJECT", "aithena")
SOLR_URL: str = os.environ.get("SOLR_URL", "http://localhost:8983/solr/books")
SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")
RABBITMQ_API_URL: str = os.environ.get("RABBITMQ_API_URL", "http://localhost:15672")
RABBITMQ_USER: str = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD: str = os.environ.get("RABBITMQ_PASSWORD", "guest")
REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))
STRESS_RESULTS_DIR: str = os.environ.get("STRESS_RESULTS_DIR", str(DEFAULT_RESULTS_DIR))
MONITOR_INTERVAL: float = float(os.environ.get("MONITOR_INTERVAL", "2"))


# ---------------------------------------------------------------------------
# Service URL fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def solr_url() -> str:
    """Base Solr collection URL."""
    return SOLR_URL


@pytest.fixture(scope="session")
def search_api_url() -> str:
    """Base URL for the solr-search API."""
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def rabbitmq_api_url() -> str:
    """RabbitMQ management API URL."""
    return RABBITMQ_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def redis_config() -> dict[str, str | int]:
    """Redis connection parameters."""
    return {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
    }


# ---------------------------------------------------------------------------
# Docker Compose lifecycle
# ---------------------------------------------------------------------------


def _compose_cmd(*args: str) -> list[str]:
    """Build a docker compose command list."""
    return ["docker", "compose", "-f", COMPOSE_FILE, "-p", COMPOSE_PROJECT, *args]


@pytest.fixture(scope="session")
def compose_up() -> Generator[None, None, None]:
    """
    Ensure the Docker Compose stack is running for the test session.

    If ALL expected services are running, this is a no-op.  Otherwise it brings
    the stack up and waits for health checks to pass.  The stack is NOT
    torn down after tests (operator is expected to manage lifecycle).
    """
    # Check if all services (not just any) are running
    try:
        expected = subprocess.run(  # noqa: S603
            _compose_cmd("config", "--services"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        expected_count = len(expected.stdout.strip().splitlines()) if expected.stdout.strip() else 0

        result = subprocess.run(  # noqa: S603
            _compose_cmd("ps", "--status=running", "-q"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        running_count = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0

        if expected_count > 0 and running_count >= expected_count:
            yield
            return
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    subprocess.run(  # noqa: S603
        _compose_cmd("up", "-d", "--wait"),
        check=True,
        timeout=300,
    )
    yield


# ---------------------------------------------------------------------------
# Results output helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def results_dir() -> Path:
    """
    Return the results output directory, creating it if needed.

    Each test run creates a timestamped subdirectory so results are not
    overwritten.
    """
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(STRESS_RESULTS_DIR) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


@pytest.fixture(scope="session")
def write_result(results_dir: Path):
    """
    Return a helper function that writes a result dict to a JSON file.

    Usage in tests:
        def test_something(write_result):
            data = {"throughput": 42.5, "p95_ms": 120}
            write_result("indexing_small", data)
    """

    def _write(name: str, data: dict) -> Path:
        path = results_dir / f"{name}.json"
        data["_timestamp"] = datetime.now(tz=UTC).isoformat()
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    return _write


# ---------------------------------------------------------------------------
# Docker resource monitor fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def docker_monitor(results_dir: Path):
    """
    Provide a context manager that records Docker resource metrics during
    the enclosed block.

    Usage:
        def test_indexing(docker_monitor):
            with docker_monitor("indexing_small") as monitor:
                # ... run test workload ...
                pass
            summary = monitor.summary()
    """
    from monitor import DockerStatsCollector

    class _MonitorContext:
        def __init__(self, label: str):
            self._collector = DockerStatsCollector(
                interval=MONITOR_INTERVAL,
                output_dir=results_dir,
                label=label,
                compose_project=COMPOSE_PROJECT,
            )

        def __enter__(self):
            self._collector.start()
            return self._collector

        def __exit__(self, *exc):
            self._collector.stop()
            return False

    from contextlib import contextmanager

    @contextmanager
    def _create_monitor(label: str):
        ctx = _MonitorContext(label)
        with ctx as collector:
            yield collector

    return _create_monitor


# ---------------------------------------------------------------------------
# Stack health checks
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stack_healthy(solr_url: str, search_api_url: str) -> None:
    """Skip the test session if the core services are not reachable."""
    import requests

    errors = []
    for name, url in [
        ("Solr", f"{solr_url}/admin/ping?distrib=true"),
        ("solr-search", f"{search_api_url}/health"),
    ]:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as exc:
            errors.append(f"{name} not reachable at {url}: {exc}")

    if errors:
        pytest.skip(
            "Stack not healthy — start the stack first.\n" + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------


@pytest.fixture()
def timer():
    """Provide a simple wall-clock timer context manager."""

    class Timer:
        def __init__(self):
            self.start_time: float = 0
            self.end_time: float = 0

        @property
        def elapsed(self) -> float:
            return self.end_time - self.start_time

        def __enter__(self):
            self.start_time = time.monotonic()
            return self

        def __exit__(self, *exc):
            self.end_time = time.monotonic()
            return False

    return Timer
