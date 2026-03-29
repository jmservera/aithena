"""Shared fixtures for installer tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure installer/ is importable (no pyproject.toml for this package)
_INSTALLER_DIR = str(Path(__file__).resolve().parents[1])
if _INSTALLER_DIR not in sys.path:
    sys.path.insert(0, _INSTALLER_DIR)


@pytest.fixture(autouse=True)
def _mock_auth_helpers():
    """Mock load_auth_helpers so tests don't need solr-search dependencies."""
    fake_hash = lambda pw: f"hashed:{pw}"  # noqa: E731
    fake_init = lambda db_path: None  # noqa: E731
    with patch("setup.load_auth_helpers", return_value=(fake_hash, fake_init)):
        yield


@pytest.fixture()
def deterministic_secret():
    """Return a predictable secret factory for test assertions."""
    return lambda n: f"generated_{n}"


@pytest.fixture()
def minimal_env_args(tmp_path: Path, deterministic_secret):
    """Common kwargs for build_env_values with empty existing_env."""
    return {
        "library_path": tmp_path / "books",
        "auth_db_path": tmp_path / "auth" / "users.db",
        "origin": "http://localhost",
        "admin_user": "admin",
        "admin_password": "adminpass",
        "existing_env": {},
        "secret_factory": deterministic_secret,
        "reset": False,
    }
