"""
Pytest wrapper for headless Locust load-test scenarios.

Runs Locust in-process so results feed back into the normal ``pytest``
report and ``write_result`` fixture.  Each scenario (light / medium / heavy)
is a separate test case parametrized by user count and workload mix.

Markers:
    concurrent  — all tests in this module
    docker      — requires a running Aithena stack
    slow        — runs take ≥ 60 s each

Skip logic:
    The ``stack_healthy`` fixture (from conftest) skips the entire module
    when the API is unreachable, so these tests are safe to include in a
    default ``pytest`` run.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scenario dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadScenario:
    """Immutable description of one load-test run."""

    name: str
    users: int
    spawn_rate: int
    run_time_seconds: int
    weights: dict[str, int] = field(default_factory=dict)


SCENARIOS: list[LoadScenario] = [
    LoadScenario(
        "light", users=5, spawn_rate=1, run_time_seconds=60,
        weights={"search": 80, "browse": 20},
    ),
    LoadScenario(
        "medium", users=10, spawn_rate=2, run_time_seconds=120,
        weights={"search": 60, "browse": 20, "upload": 20},
    ),
    LoadScenario(
        "heavy", users=25, spawn_rate=5, run_time_seconds=180,
        weights={"search": 50, "upload": 25, "admin": 25},
    ),
]


# ---------------------------------------------------------------------------
# Helpers (unit-testable)
# ---------------------------------------------------------------------------


def build_locust_command(
    scenario: LoadScenario,
    host: str,
    csv_prefix: str | None = None,
) -> list[str]:
    """Build the CLI arguments for a headless Locust run.

    Returns a list suitable for ``subprocess.run(cmd)``.
    """
    locustfile = str(Path(__file__).resolve().parent / "locustfile.py")
    cmd = [
        "locust",
        "-f", locustfile,
        "--headless",
        "-u", str(scenario.users),
        "-r", str(scenario.spawn_rate),
        "--run-time", f"{scenario.run_time_seconds}s",
        "--host", host,
    ]
    if csv_prefix:
        cmd.extend(["--csv", csv_prefix])
    return cmd


def parse_locust_csv_stats(csv_path: str | Path) -> list[dict[str, Any]]:
    """Parse a Locust ``_stats.csv`` file into a list of dicts.

    Each row becomes a dict with keys from the CSV header.
    Returns an empty list if the file is missing.
    """
    import csv

    path = Path(csv_path)
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def summarise_locust_run(stats_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a summary dict from parsed Locust CSV stats.

    The *Aggregated* row (Name == "Aggregated") carries overall metrics.
    """
    aggregated = next((r for r in stats_rows if r.get("Name") == "Aggregated"), None)
    if aggregated is None:
        return {"error": "no aggregated row found"}

    def _safe_float(val: Any, default: float = 0.0) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    total_requests = int(aggregated.get("Request Count", 0))
    total_failures = int(aggregated.get("Failure Count", 0))

    return {
        "total_requests": total_requests,
        "total_failures": total_failures,
        "error_rate_percent": round(
            (total_failures / max(total_requests, 1)) * 100, 2
        ),
        "requests_per_second": _safe_float(aggregated.get("Requests/s")),
        "avg_response_time_ms": _safe_float(aggregated.get("Average Response Time")),
        "p50_ms": _safe_float(aggregated.get("50%")),
        "p95_ms": _safe_float(aggregated.get("95%")),
        "p99_ms": _safe_float(aggregated.get("99%")),
    }


def check_pass_criteria(summary: dict[str, Any], users: int) -> dict[str, bool]:
    """Check results against PRD §6.1 targets.

    Returns a dict of ``{criterion_name: passed}`` booleans.
    """
    return {
        "throughput_10rps_at_10u": (
            summary.get("requests_per_second", 0) >= 10.0 if users >= 10 else True
        ),
        "error_rate_below_1pct": summary.get("error_rate_percent", 100) < 1.0,
        "p95_below_2000ms": summary.get("p95_ms", 99999) < 2000,
    }


# ---------------------------------------------------------------------------
# Pytest tests
# ---------------------------------------------------------------------------


@pytest.mark.concurrent
@pytest.mark.docker
@pytest.mark.slow
class TestConcurrentLoad:
    """Run Locust scenarios and assert against PRD targets."""

    @pytest.mark.parametrize(
        "scenario",
        SCENARIOS,
        ids=[s.name for s in SCENARIOS],
    )
    def test_load_scenario(
        self,
        scenario: LoadScenario,
        search_api_url: str,
        results_dir: Path,
        write_result,
        stack_healthy,
    ):
        import subprocess

        csv_prefix = str(results_dir / f"locust_{scenario.name}")
        os.environ["LOCUST_SCENARIO"] = scenario.name

        cmd = build_locust_command(scenario, host=search_api_url, csv_prefix=csv_prefix)
        logger.info("Running: %s", " ".join(cmd))

        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=scenario.run_time_seconds + 60,
        )

        stats_file = f"{csv_prefix}_stats.csv"
        rows = parse_locust_csv_stats(stats_file)
        summary = summarise_locust_run(rows)
        summary["scenario"] = scenario.name
        summary["users"] = scenario.users
        summary["spawn_rate"] = scenario.spawn_rate
        summary["run_time_seconds"] = scenario.run_time_seconds
        summary["locust_exit_code"] = result.returncode

        write_result(f"concurrent_{scenario.name}", summary)

        criteria = check_pass_criteria(summary, scenario.users)
        summary["pass_criteria"] = criteria

        # Assertions per PRD §6.1
        assert summary.get("total_requests", 0) > 0, "No requests completed"
        assert criteria["error_rate_below_1pct"], (
            f"Error rate {summary['error_rate_percent']}% exceeds 1% threshold"
        )
        if scenario.users >= 10:
            assert criteria["throughput_10rps_at_10u"], (
                f"Throughput {summary['requests_per_second']} rps below 10 rps target at {scenario.users} users"
            )
