#!/usr/bin/env python
"""Verify OpenVINO runtime packages after Docker uv sync --inexact."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import sys
import tomllib
from pathlib import Path

REQUIRED_PACKAGES = ("openvino", "optimum-intel", "openvino-tokenizers")


def _normalize_package_name(value: str) -> str:
    return value.replace("_", "-").lower()


def _version_parts(value: str) -> tuple[int, ...]:
    match = re.match(r"^\d+(?:\.\d+)*", value)
    if not match:
        raise ValueError(f"Version does not start with numeric components: {value}")
    return tuple(int(part) for part in match.group(0).split("."))


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    width = max(len(left_parts), len(right_parts))
    padded_left = left_parts + (0,) * (width - len(left_parts))
    padded_right = right_parts + (0,) * (width - len(right_parts))
    return (padded_left > padded_right) - (padded_left < padded_right)


def _dependency_name(dependency: str) -> str:
    return _normalize_package_name(re.split(r"\s|\[|>=|<=|==|!=|~=|>|<", dependency, maxsplit=1)[0])


def _load_openvino_dependency_specs(pyproject_path: Path) -> dict[str, str]:
    with pyproject_path.open("rb") as handle:
        pyproject = tomllib.load(handle)

    dependencies = pyproject.get("project", {}).get("optional-dependencies", {}).get("openvino", [])
    specs: dict[str, str] = {}
    for dependency in dependencies:
        name = _dependency_name(dependency)
        if name in REQUIRED_PACKAGES:
            constraints = re.findall(r"(>=|<=|==|>|<|~=)\s*([0-9][^,;\s]*)", dependency)
            specs[name] = ",".join(f"{operator}{version}" for operator, version in constraints)
    return specs


def _satisfies_specifier(version: str, specifier: str) -> bool:
    if not specifier:
        return True

    for constraint in specifier.split(","):
        if not constraint:
            continue
        match = re.match(r"(>=|<=|==|>|<|~=)(.+)", constraint)
        if not match:
            raise ValueError(f"Unsupported version constraint: {constraint}")
        operator, expected = match.groups()
        comparison = _compare_versions(version, expected)
        if operator == ">=" and comparison < 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
        if operator == "==" and comparison != 0:
            return False
        if operator == "~=":
            lower_ok = comparison >= 0
            upper = str(_version_parts(expected)[0] + 1)
            upper_ok = _compare_versions(version, upper) < 0
            if not (lower_ok and upper_ok):
                return False
    return True


def _installed_version(package_name: str) -> str:
    return metadata.version(package_name)


def verify_openvino_runtime(pyproject_path: Path) -> list[str]:
    specs = _load_openvino_dependency_specs(pyproject_path)
    failures: list[str] = []
    installed: dict[str, str] = {}

    print("OpenVINO runtime package verification")
    print(f"Spec source: {pyproject_path}")

    for package_name in REQUIRED_PACKAGES:
        specifier = specs.get(package_name, "")
        try:
            version = _installed_version(package_name)
        except metadata.PackageNotFoundError:
            failures.append(f"{package_name} is not installed")
            print(f"- {package_name}: MISSING required={specifier or '(present)'}")
            continue

        installed[package_name] = version
        status = "OK" if _satisfies_specifier(version, specifier) else "FAIL"
        print(f"- {package_name}: installed={version} required={specifier or '(present)'} status={status}")
        if status == "FAIL":
            failures.append(f"{package_name} {version} does not satisfy {specifier}")

    try:
        import openvino

        runtime_version = openvino.get_version()
        print(f"- openvino.get_version(): {runtime_version}")
    except Exception as exc:  # pragma: no cover - diagnostic path for container builds
        failures.append(f"openvino.get_version() failed: {exc}")
        print(f"- openvino.get_version(): FAIL ({exc})")

    openvino_version = installed.get("openvino")
    tokenizer_version = installed.get("openvino-tokenizers")
    if openvino_version and tokenizer_version:
        openvino_minor = _version_parts(openvino_version)[:2]
        tokenizer_minor = _version_parts(tokenizer_version)[:2]
        if openvino_minor != tokenizer_minor:
            failures.append(
                f"openvino and openvino-tokenizers minor versions differ: {openvino_version} vs {tokenizer_version}"
            )

    if failures:
        print("OpenVINO runtime verification failed:")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("OpenVINO runtime verification passed")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "pyproject.toml",
        help="Path to embeddings-server pyproject.toml",
    )
    args = parser.parse_args()

    return 1 if verify_openvino_runtime(args.pyproject) else 0


if __name__ == "__main__":
    sys.exit(main())
