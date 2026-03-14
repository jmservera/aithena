from __future__ import annotations

import importlib
from pathlib import Path

import pytest

BOOK_LIBRARY_ROOT = Path("/home/jmservera/booklibrary")
REQUIRED_METADATA_KEYS = {
    "title",
    "author",
    "year",
    "category",
    "file_path",
    "folder_path",
    "file_size",
}


@pytest.fixture(scope="session")
def extract_metadata_func():
    try:
        module = importlib.import_module("document_indexer.metadata")
    except ModuleNotFoundError as exc:
        if exc.name != "document_indexer.metadata":
            raise
        pytest.fail(
            "document_indexer.metadata is not implemented yet. "
            "Add metadata.py with an extract_metadata(file_path, base_path) function.",
            pytrace=False,
        )

    extract_metadata = getattr(module, "extract_metadata", None)
    if extract_metadata is None:
        pytest.fail(
            "document_indexer.metadata.extract_metadata is missing.",
            pytrace=False,
        )

    return extract_metadata


@pytest.fixture
def make_document(tmp_path: Path):
    def _make(
        relative_path: str, content: bytes = b"metadata-test"
    ) -> tuple[Path, Path]:
        document_path = tmp_path / relative_path
        document_path.parent.mkdir(parents=True, exist_ok=True)
        document_path.write_bytes(content)
        return document_path, tmp_path

    return _make


@pytest.fixture(scope="session")
def booklibrary_root() -> Path:
    return BOOK_LIBRARY_ROOT
