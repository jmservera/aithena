"""Tests for openvino optional-dependencies in pyproject.toml (issue #1286).

Verifies that the openvino extras include intel-extension-for-pytorch (IPEX)
alongside the existing openvino and optimum-intel packages. If the fix for
#1286 has not been applied, test_pyproject_openvino_extras_includes_ipex will
fail with a clear message.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _load_openvino_extras() -> list[str]:
    """Parse pyproject.toml and return the openvino optional-dependencies list."""
    with open(PYPROJECT_PATH, "rb") as fh:
        data = tomllib.load(fh)
    extras = data.get("project", {}).get("optional-dependencies", {})
    assert "openvino" in extras, "pyproject.toml missing 'openvino' optional-dependencies group"
    return extras["openvino"]


def _package_names(deps: list[str]) -> list[str]:
    """Strip version specifiers to get bare package names (lowercased)."""
    import re

    return [re.split(r"[>=<!\[;]", d)[0].strip().lower() for d in deps]


# ---------- 1. IPEX included ----------


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


# ---------- 4. uv.lock contains IPEX ----------


def test_uv_lock_contains_ipex():
    """If uv.lock exists, it should contain an entry for intel-extension-for-pytorch."""
    lock_path = Path(__file__).resolve().parents[1] / "uv.lock"
    if not lock_path.exists():
        import pytest

        pytest.skip("uv.lock not found — skipping lockfile check")

    content = lock_path.read_text(encoding="utf-8")
    assert "intel-extension-for-pytorch" in content, (
        "uv.lock does not contain intel-extension-for-pytorch — "
        "run `uv lock` after adding IPEX to openvino extras (#1286)"
    )
