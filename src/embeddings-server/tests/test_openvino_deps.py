"""Tests for OpenVINO optional-dependencies in pyproject.toml.

These tests guard against dependency drift between the OpenVINO base image and
the lockfile. The Dockerfile intentionally uses ``uv sync --inexact`` to keep
heavy base-image packages, so pyproject constraints and uv.lock must stay on the
documented OpenVINO series.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"
LOCK_PATH = Path(__file__).resolve().parents[1] / "uv.lock"


def _load_openvino_extras() -> list[str]:
    """Parse pyproject.toml and return the openvino optional-dependencies list."""
    with open(PYPROJECT_PATH, "rb") as fh:
        data = tomllib.load(fh)
    extras = data.get("project", {}).get("optional-dependencies", {})
    assert "openvino" in extras, "pyproject.toml missing 'openvino' optional-dependencies group"
    return extras["openvino"]


def _load_openvino_config() -> dict[str, str]:
    """Parse the OpenVINO compatibility matrix from pyproject.toml."""
    with open(PYPROJECT_PATH, "rb") as fh:
        data = tomllib.load(fh)
    config = data.get("tool", {}).get("aithena", {}).get("openvino", {})
    assert config, "pyproject.toml missing [tool.aithena.openvino] compatibility matrix"
    return config


def _load_lock_packages() -> dict[str, str]:
    """Parse uv.lock and return locked package versions by normalized name."""
    if not LOCK_PATH.exists():
        import pytest

        pytest.skip("uv.lock not found — skipping lockfile check")

    with open(LOCK_PATH, "rb") as fh:
        data = tomllib.load(fh)
    return {pkg["name"].lower(): pkg["version"] for pkg in data.get("package", [])}


def _package_names(deps: list[str]) -> list[str]:
    """Strip version specifiers to get bare package names (lowercased)."""
    import re

    return [re.split(r"[>=<!\[;]", d)[0].strip().lower() for d in deps]


def _dependency_by_name(deps: list[str]) -> dict[str, str]:
    return dict(zip(_package_names(deps), deps, strict=True))


def _version_tuple(version: str) -> tuple[int, ...]:
    """Return numeric version parts, ignoring local/build suffixes."""
    import re

    return tuple(int(part) for part in re.findall(r"\d+", version))


def _assert_version_range(version: str, minimum: str, maximum_exclusive: str):
    actual = _version_tuple(version)
    assert actual >= _version_tuple(minimum), f"{version} is lower than required minimum {minimum}"
    assert actual < _version_tuple(maximum_exclusive), f"{version} is outside the supported maximum {maximum_exclusive}"


def test_pyproject_openvino_extras_includes_ipex():
    """openvino extras must include intel-extension-for-pytorch (IPEX)."""
    deps = _load_openvino_extras()
    names = _package_names(deps)
    assert "intel-extension-for-pytorch" in names, (
        f"intel-extension-for-pytorch not in openvino extras — #1286 fix may not be applied. Current deps: {deps}"
    )


# ---------- 2. openvino still listed ----------


def test_pyproject_openvino_extras_includes_openvino():
    """openvino package must remain in the openvino extras."""
    deps = _load_openvino_extras()
    names = _package_names(deps)
    assert "openvino" in names, f"openvino missing from extras: {deps}"


# ---------- 3. optimum-intel still listed ----------


def test_pyproject_openvino_extras_includes_optimum_intel():
    """optimum-intel must remain in the openvino extras."""
    deps = _load_openvino_extras()
    names = _package_names(deps)
    assert "optimum-intel" in names, f"optimum-intel missing from extras: {deps}"


# ---------- 4. openvino-tokenizers included ----------


def test_pyproject_openvino_extras_includes_openvino_tokenizers():
    """openvino-tokenizers must be included for OpenVINO 2025.x compatibility."""
    deps = _load_openvino_extras()
    names = _package_names(deps)
    assert "openvino-tokenizers" in names, (
        f"openvino-tokenizers missing from extras — required for OpenVINO 2025.x. Current deps: {deps}"
    )


def test_openvino_extras_match_supported_series():
    """OpenVINO packages must be constrained to the configured base-image series."""
    deps = _dependency_by_name(_load_openvino_extras())
    config = _load_openvino_config()

    expected_specs = {
        "openvino": f">={config['openvino-min']},<{config['openvino-max-exclusive']}",
        "openvino-tokenizers": (
            f">={config['openvino-tokenizers-min']},<{config['openvino-tokenizers-max-exclusive']}"
        ),
        "optimum-intel": f">={config['optimum-intel-min']},<{config['optimum-intel-max-exclusive']}",
    }
    for package, spec in expected_specs.items():
        assert deps[package].endswith(spec), f"{package} must use {spec}; got {deps[package]!r}"


def test_uv_lock_contains_ipex():
    """If uv.lock exists, it should contain an entry for intel-extension-for-pytorch."""
    packages = _load_lock_packages()
    assert "intel-extension-for-pytorch" in packages, (
        "uv.lock does not contain intel-extension-for-pytorch — "
        "run `uv lock` after adding IPEX to openvino extras (#1286)"
    )


def test_uv_lock_contains_openvino_tokenizers():
    """If uv.lock exists, it should contain an entry for openvino-tokenizers."""
    packages = _load_lock_packages()
    assert "openvino-tokenizers" in packages, (
        "uv.lock does not contain openvino-tokenizers — "
        "run `uv lock` after adding openvino-tokenizers to openvino extras"
    )


def test_uv_lock_openvino_packages_match_supported_series():
    """Locked OpenVINO packages must stay compatible with the configured base image."""
    packages = _load_lock_packages()
    config = _load_openvino_config()

    for package in ("openvino", "openvino-tokenizers"):
        assert packages[package].startswith(config["base-image-series"]), (
            f"{package} {packages[package]} must match OpenVINO base-image series {config['base-image-series']}"
        )

    _assert_version_range(
        packages["optimum-intel"],
        config["optimum-intel-min"],
        config["optimum-intel-max-exclusive"],
    )
