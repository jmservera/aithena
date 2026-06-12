"""Pytest configuration for embeddings-server tests.

Auto-skips tests that depend on PyTorch/CUDA when the runtime libraries
are not available (e.g., local dev machines without GPU drivers).
"""

from __future__ import annotations

import importlib

import pytest

# Check once at collection time whether torch can actually load.
# Tests that import the app module (main, config) transitively require torch.
_TORCH_AVAILABLE = False
try:
    importlib.import_module("torch")
    _TORCH_AVAILABLE = True
except (ImportError, OSError):
    # OSError covers missing .so files like libcudnn.so
    pass


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests that require torch/CUDA when the runtime isn't available."""
    if _TORCH_AVAILABLE:
        return

    skip_torch = pytest.mark.skip(reason="torch not functional (missing CUDA libs)")
    # Test files that import from main/config/app code requiring torch
    torch_dependent_files = {"test_gpu_config.py", "test_embeddings_server.py"}

    for item in items:
        if item.path and item.path.name in torch_dependent_files:
            item.add_marker(skip_torch)
