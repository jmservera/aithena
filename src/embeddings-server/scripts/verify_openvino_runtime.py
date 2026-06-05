#!/usr/bin/env python
"""Verify OpenVINO runtime packages after Docker uv sync --inexact."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import sys
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

REQUIRED_PACKAGES = ("openvino", "optimum-intel", "openvino-tokenizers")


def _normalize_package_name(value: str) -> str:
    return value.replace("_", "-").lower()


def _release_parts(value: str) -> tuple[int, ...]:
    """Extract release version tuple using PEP 440 parsing."""
    return Version(value).release


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
    """Check if version satisfies specifier, including PEP 440 operators like ~= (compatible release)."""
    if not specifier:
        return True

    return SpecifierSet(specifier).contains(version, prereleases=True)


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
        openvino_minor = _release_parts(openvino_version)[:2]
        tokenizer_minor = _release_parts(tokenizer_version)[:2]
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
