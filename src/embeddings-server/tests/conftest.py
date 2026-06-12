"""Pytest configuration for embeddings-server tests.

Auto-skips tests that depend on PyTorch/CUDA when the runtime libraries
are not available (e.g., local dev machines without GPU drivers).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# Check once at collection time whether torch can actually load.
_TORCH_AVAILABLE = False
try:
    importlib.import_module("torch")
    _TORCH_AVAILABLE = True
except (ImportError, OSError):
    # OSError covers missing shared libraries like libcudnn.so
    pass

# Files where EVERY test uses _fresh_import() → `import main` → torch.
# No torch-free tests exist in these modules, so file-level exclusion
# is correct (not overly broad).
_TORCH_DEPENDENT_FILES = {"test_gpu_config.py", "test_embeddings_server.py"}


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Skip collection of torch-dependent test files when CUDA is unavailable."""
    if not _TORCH_AVAILABLE and collection_path.name in _TORCH_DEPENDENT_FILES:
        return True
    return None
