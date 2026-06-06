#!/usr/bin/env python3
"""Pre-flight checklist for scalar quantization (int8) benchmark validation.

Verifies environment, tooling, corpus availability, schema, and benchmark suite
before executing Phase 1 (float32 baseline) of the validation workflow.

Usage:
    python3 scripts/benchmark/pre_flight_check.py
    python3 scripts/benchmark/pre_flight_check.py --strict  # Fail on first warning
    python3 scripts/benchmark/pre_flight_check.py --json    # JSON output for CI
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    """Single pre-flight check result."""

    name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, error
    command_hint: str | None = None


@dataclass
class PreFlightReport:
    """Aggregated pre-flight check report."""

    total_checks: int = 0
    passed_checks: int = 0
    warning_checks: int = 0
    failed_checks: int = 0
    checks: list[CheckResult] = field(default_factory=list)

    def add_check(self, result: CheckResult) -> None:
        """Add a check result and update counters."""
        self.total_checks += 1
        if result.passed:
            self.passed_checks += 1
        elif result.severity == "warning":
            self.warning_checks += 1
        else:
            self.failed_checks += 1
        self.checks.append(result)

    def is_ready(self, strict: bool = False) -> bool:
        """Return True if all critical checks passed."""
        if strict:
            return self.failed_checks == 0 and self.warning_checks == 0
        return self.failed_checks == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "warning_checks": self.warning_checks,
            "failed_checks": self.failed_checks,
            "ready": self.is_ready(),
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "severity": c.severity,
                    "command_hint": c.command_hint,
                }
                for c in self.checks
            ],
        }


def check_docker() -> CheckResult:
    """Check Docker availability."""
    import subprocess

    docker_path = shutil.which("docker")
    if docker_path is None:
        return CheckResult(
            name="Docker availability",
            passed=False,
            message="✗ Docker not found or not responding",
            severity="error",
            command_hint="docker --version",
        )

    try:
        result = subprocess.run([docker_path, "--version"], capture_output=True, text=True, timeout=5)  # noqa: S603
        if result.returncode == 0:
            version = result.stdout.strip()
            return CheckResult(
                name="Docker availability",
                passed=True,
                message=f"✓ Docker installed: {version}",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return CheckResult(
        name="Docker availability",
        passed=False,
        message="✗ Docker not found or not responding",
        severity="error",
        command_hint="docker --version",
    )


def check_docker_compose() -> CheckResult:
    """Check Docker Compose availability."""
    import subprocess

    docker_path = shutil.which("docker")
    if docker_path is None:
        return CheckResult(
            name="Docker Compose availability",
            passed=False,
            message="✗ Docker Compose not found or not responding",
            severity="error",
            command_hint="docker compose --version",
        )

    try:
        result = subprocess.run([docker_path, "compose", "--version"], capture_output=True, text=True, timeout=5)  # noqa: S603
        if result.returncode == 0:
            version = result.stdout.strip()
            return CheckResult(
                name="Docker Compose availability",
                passed=True,
                message=f"✓ Docker Compose installed: {version}",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return CheckResult(
        name="Docker Compose availability",
        passed=False,
        message="✗ Docker Compose not found or not responding",
        severity="error",
        command_hint="docker compose --version",
    )


def check_python() -> CheckResult:
    """Check Python version (3.10+)."""
    import subprocess

    python_path = shutil.which("python3")
    if python_path is None:
        return CheckResult(
            name="Python version (3.10+)",
            passed=False,
            message="✗ Python3 not found or not responding",
            severity="error",
            command_hint="python3 --version",
        )

    try:
        result = subprocess.run([python_path, "--version"], capture_output=True, text=True, timeout=5)  # noqa: S603
        if result.returncode == 0:
            version_str = result.stdout.strip()
            # Extract version number
            try:
                version_parts = version_str.replace("Python ", "").split(".")
                major = int(version_parts[0])
                minor = int(version_parts[1])
                if (major > 3) or (major == 3 and minor >= 10):
                    return CheckResult(
                        name="Python version (3.10+)",
                        passed=True,
                        message=f"✓ Python {major}.{minor} installed",
                    )
                else:
                    return CheckResult(
                        name="Python version (3.10+)",
                        passed=False,
                        message=f"✗ Python {major}.{minor} found; 3.10+ required",
                        severity="error",
                    )
            except (IndexError, ValueError):
                return CheckResult(
                    name="Python version (3.10+)",
                    passed=False,
                    message=f"✗ Could not parse version: {version_str}",
                    severity="error",
                )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return CheckResult(
        name="Python version (3.10+)",
        passed=False,
        message="✗ Python3 not found or not responding",
        severity="error",
        command_hint="python3 --version",
    )


def check_dependencies() -> CheckResult:
    """Check Python dependencies (requests, numpy)."""
    try:
        import numpy  # noqa: F401
        import requests  # noqa: F401

        return CheckResult(
            name="Python dependencies (requests, numpy)",
            passed=True,
            message="✓ requests and numpy available",
        )
    except ImportError as e:
        return CheckResult(
            name="Python dependencies (requests, numpy)",
            passed=False,
            message=f"✗ Missing dependency: {e}",
            severity="error",
            command_hint="pip install requests numpy",
        )


def check_queries_file() -> CheckResult:
    """Check benchmark query suite."""
    queries_path = Path("scripts/benchmark/queries.json")
    if not queries_path.exists():
        return CheckResult(
            name="Benchmark query suite (queries.json)",
            passed=False,
            message=f"✗ File not found: {queries_path}",
            severity="error",
        )

    try:
        import json

        with queries_path.open(encoding="utf-8") as f:
            data = json.load(f)

        # Queries are nested under categories
        categories = data.get("categories", {})
        if not isinstance(categories, dict):
            return CheckResult(
                name="Benchmark query suite (queries.json)",
                passed=False,
                message="✗ Invalid queries.json structure: 'categories' is not a dict",
                severity="error",
            )

        query_count = 0
        for cat_data in categories.values():
            if isinstance(cat_data, dict):
                query_count += len(cat_data.get("queries", []))

        if query_count >= 30:
            return CheckResult(
                name="Benchmark query suite (queries.json)",
                passed=True,
                message=f"✓ Query file found with {query_count} queries across {len(categories)} categories",
            )
        else:
            return CheckResult(
                name="Benchmark query suite (queries.json)",
                passed=False,
                message=f"✗ Only {query_count} queries found; expected ≥30",
                severity="error",
            )
    except (json.JSONDecodeError, OSError) as e:
        return CheckResult(
            name="Benchmark query suite (queries.json)",
            passed=False,
            message=f"✗ Error reading queries.json: {e}",
            severity="error",
        )


def check_comparator() -> CheckResult:
    """Check compare_quantization.py availability."""
    comparator_path = Path("scripts/benchmark/compare_quantization.py")
    if not comparator_path.exists():
        return CheckResult(
            name="Benchmark comparator (compare_quantization.py)",
            passed=False,
            message=f"✗ File not found: {comparator_path}",
            severity="error",
        )

    if not comparator_path.is_file():
        return CheckResult(
            name="Benchmark comparator (compare_quantization.py)",
            passed=False,
            message=f"✗ Not a file: {comparator_path}",
            severity="error",
        )

    return CheckResult(
        name="Benchmark comparator (compare_quantization.py)",
        passed=True,
        message="✓ Comparator script found",
    )


def check_schema() -> CheckResult:
    """Check Solr schema for int8 quantization support."""
    schema_path = Path("src/solr/books/managed-schema.xml")
    if not schema_path.exists():
        return CheckResult(
            name="Solr schema (managed-schema.xml)",
            passed=False,
            message=f"✗ File not found: {schema_path}",
            severity="error",
        )

    try:
        with schema_path.open(encoding="utf-8") as f:
            schema_content = f.read()

        # Check for either Solr 10 supported scalar quantization bits or Solr 9 BYTE encoding
        has_scalar_quantized = (
            re.search(
                r'<fieldType\b(?=[^>]*class="solr\.ScalarQuantizedDenseVectorField")(?=[^>]*bits="[47]")',
                schema_content,
            )
            is not None
        )
        has_byte_encoding = "DenseVectorField" in schema_content and 'vectorEncoding="BYTE"' in schema_content

        if has_scalar_quantized or has_byte_encoding:
            if has_scalar_quantized:
                msg = '✓ Schema has ScalarQuantizedDenseVectorField bits="4" or bits="7" (Solr 10)'
            else:
                msg = '✓ Schema has DenseVectorField vectorEncoding="BYTE" (Solr 9)'
            return CheckResult(
                name="Solr schema int8 support",
                passed=True,
                message=msg,
            )
        else:
            return CheckResult(
                name="Solr schema int8 support",
                passed=False,
                message="✗ Schema missing int8 support; check if #1670 is merged",
                severity="warning",
                command_hint="grep -n 'ScalarQuantizedDenseVectorField.*bits' src/solr/books/managed-schema.xml",
            )
    except OSError as e:
        return CheckResult(
            name="Solr schema int8 support",
            passed=False,
            message=f"✗ Error reading schema: {e}",
            severity="error",
        )


def check_benchmark_scripts() -> CheckResult:
    """Check that benchmark scripts exist."""
    scripts = [
        "scripts/benchmark/run_benchmark.py",
        "scripts/benchmark/compare_quantization.py",
        "scripts/index_test_corpus.py",
        "scripts/verify_collections.py",
    ]
    missing = [s for s in scripts if not Path(s).exists()]

    if not missing:
        return CheckResult(
            name="Benchmark scripts",
            passed=True,
            message=f"✓ All {len(scripts)} benchmark scripts found",
        )
    else:
        return CheckResult(
            name="Benchmark scripts",
            passed=False,
            message=f"✗ Missing scripts: {', '.join(missing)}",
            severity="error",
        )


def check_docker_compose_file() -> CheckResult:
    """Check docker-compose.yml exists."""
    compose_file = Path("docker-compose.yml")
    if compose_file.exists():
        return CheckResult(
            name="Docker Compose file",
            passed=True,
            message="✓ docker-compose.yml found",
        )
    return CheckResult(
        name="Docker Compose file",
        passed=False,
        message="✗ docker-compose.yml not found",
        severity="error",
    )


def check_disk_space() -> CheckResult:
    """Check approximate disk space (non-critical warning)."""
    import shutil

    try:
        stat = shutil.disk_usage("/")
        free_gb = stat.free / (1024**3)
        if free_gb >= 20:
            return CheckResult(
                name="Disk space (≥20 GB recommended)",
                passed=True,
                message=f"✓ {free_gb:.1f} GB free available",
            )
        else:
            return CheckResult(
                name="Disk space (≥20 GB recommended)",
                passed=False,
                message=f"⚠ Only {free_gb:.1f} GB free; recommend ≥20 GB",
                severity="warning",
            )
    except Exception as e:
        return CheckResult(
            name="Disk space (≥20 GB recommended)",
            passed=False,
            message=f"⚠ Could not check disk space: {e}",
            severity="warning",
        )


def main() -> int:
    """Run all pre-flight checks."""
    parser = argparse.ArgumentParser(description="Pre-flight checklist for scalar quantization benchmark validation")
    parser.add_argument("--strict", action="store_true", help="Fail on any warning (not just errors)")
    parser.add_argument("--json", action="store_true", help="Output as JSON (for CI)")
    args = parser.parse_args()

    # Run all checks
    report = PreFlightReport()
    checks = [
        check_docker,
        check_docker_compose,
        check_python,
        check_dependencies,
        check_queries_file,
        check_comparator,
        check_schema,
        check_benchmark_scripts,
        check_docker_compose_file,
        check_disk_space,
    ]

    for check_func in checks:
        result = check_func()
        report.add_check(result)

    # Output results
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        # Human-readable output
        print("\n" + "=" * 70)
        print("SCALAR QUANTIZATION BENCHMARK PRE-FLIGHT CHECKLIST")
        print("=" * 70 + "\n")

        for check in report.checks:
            symbol = "✓" if check.passed else ("⚠" if check.severity == "warning" else "✗")
            print(f"{symbol} {check.name}")
            print(f"  {check.message}")
            if check.command_hint:
                print(f"  Hint: {check.command_hint}")
            print()

        print("=" * 70)
        print(f"Summary: {report.passed_checks}/{report.total_checks} checks passed")
        if report.warning_checks > 0:
            print(f"Warnings: {report.warning_checks}")
        if report.failed_checks > 0:
            print(f"Failed: {report.failed_checks}")
        print("=" * 70 + "\n")

        if report.is_ready(strict=args.strict):
            print("✓ Environment ready for benchmark validation!")
            return 0
        else:
            print(
                "✗ Please resolve errors before proceeding."
                if args.strict
                else "⚠ Resolve errors before proceeding; warnings are informational."
            )
            return 1


if __name__ == "__main__":
    sys.exit(main())
