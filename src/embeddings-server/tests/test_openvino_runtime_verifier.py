from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import verify_openvino_runtime

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_openvino_runtime_verifier_accepts_current_constraints(monkeypatch: pytest.MonkeyPatch):
    versions = {
        "openvino": "2025.4.0",
        "optimum-intel": "1.27.0",
        "openvino-tokenizers": "2025.4.0",
    }

    monkeypatch.setattr(verify_openvino_runtime, "_installed_version", versions.__getitem__)
    monkeypatch.setitem(sys.modules, "openvino", _OpenVinoModule("2025.4.0"))

    assert verify_openvino_runtime.verify_openvino_runtime(PYPROJECT_PATH) == []


def test_openvino_runtime_verifier_rejects_lockfile_drift(monkeypatch: pytest.MonkeyPatch):
    versions = {
        "openvino": "2026.0.0",
        "optimum-intel": "1.27.0",
        "openvino-tokenizers": "2025.4.0",
    }

    monkeypatch.setattr(verify_openvino_runtime, "_installed_version", versions.__getitem__)
    monkeypatch.setitem(sys.modules, "openvino", _OpenVinoModule("2026.0.0"))

    failures = verify_openvino_runtime.verify_openvino_runtime(PYPROJECT_PATH)

    # openvino 2026.0.0 satisfies >=2025.4,<2027 but the runtime verifier
    # still rejects when openvino and openvino-tokenizers minor versions differ
    assert any("minor versions differ" in failure for failure in failures)


def test_openvino_runtime_verifier_uses_pep440_compatible_release_bounds():
    assert verify_openvino_runtime._satisfies_specifier("1.4.5", "~=1.4.5")
    assert verify_openvino_runtime._satisfies_specifier("1.4.99", "~=1.4.5")
    assert not verify_openvino_runtime._satisfies_specifier("1.5.0", "~=1.4.5")
    assert not verify_openvino_runtime._satisfies_specifier("2.0.0", "~=1.4.5")


class _OpenVinoModule:
    def __init__(self, version: str) -> None:
        self._version = version

    def get_version(self) -> str:
        return self._version
