"""
Tests for the PDF upload endpoint (POST /documents/upload).

The tests are intentionally self-contained: they patch the LIBRARY_PATH
config value to a temporary directory and mock the StaticFiles mount so
the tests can run without the ``static/`` directory being present.
"""

import io
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: make the qdrant-search package importable from this directory.
# ---------------------------------------------------------------------------
QDRANT_SEARCH_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(QDRANT_SEARCH_DIR))

# Stub heavy optional dependencies before importing main so that the tests
# work in a lightweight CI environment without Qdrant / qdrant-client.
qdrant_stub = mock.MagicMock()
sys.modules.setdefault("qdrant_client", qdrant_stub)
sys.modules.setdefault("qdrant_client.models", qdrant_stub.models)

# Stub StaticFiles so we do not need the ./static directory.
from fastapi.staticfiles import StaticFiles  # noqa: E402

with mock.patch.object(StaticFiles, "__init__", return_value=None):
    import main as app_module  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_PDF = (
    b"%PDF-1.0\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n0\n%%EOF\n"
)


def _make_pdf_upload(filename: str = "book.pdf", content: bytes = _MINIMAL_PDF):
    return ("file", (filename, io.BytesIO(content), "application/pdf"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect LIBRARY_PATH to a temporary directory for each test."""
    monkeypatch.setattr(app_module, "LIBRARY_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture()
def client():
    """Return a TestClient bound to api_app (mounted at /v1 in production)."""
    return TestClient(app_module.api_app)


# ---------------------------------------------------------------------------
# Tests: successful upload
# ---------------------------------------------------------------------------


def test_upload_pdf_returns_created(client: TestClient, tmp_library: Path):
    """A valid PDF should be saved and the response should say 'created'."""
    response = client.post(
        "/documents/upload",
        files=[_make_pdf_upload("my_book.pdf")],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "my_book.pdf"
    assert data["status"] == "created"
    assert data["size"] == len(_MINIMAL_PDF)
    assert data["path"] == "my_book.pdf"
    assert (tmp_library / "my_book.pdf").read_bytes() == _MINIMAL_PDF


def test_upload_creates_library_dir_if_missing(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The endpoint should create LIBRARY_PATH if it does not exist yet."""
    nested = tmp_path / "new" / "library"
    monkeypatch.setattr(app_module, "LIBRARY_PATH", str(nested))
    response = client.post(
        "/documents/upload",
        files=[_make_pdf_upload("book.pdf")],
    )
    assert response.status_code == 200
    assert (nested / "book.pdf").exists()


# ---------------------------------------------------------------------------
# Tests: validation failures
# ---------------------------------------------------------------------------


def test_upload_rejects_non_pdf_extension(client: TestClient, tmp_library: Path):
    """Files whose extension is not .pdf should be rejected with 422."""
    response = client.post(
        "/documents/upload",
        files=[("file", ("resume.docx", io.BytesIO(b"data"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert response.status_code == 422
    assert "PDF" in response.json()["detail"]


def test_upload_rejects_txt_file(client: TestClient, tmp_library: Path):
    """Plain-text files should be rejected."""
    response = client.post(
        "/documents/upload",
        files=[("file", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))],
    )
    assert response.status_code == 422


def test_upload_rejects_pdf_extension_with_wrong_content_type(client: TestClient, tmp_library: Path):
    """A .pdf extension with a wrong content-type should also be rejected."""
    response = client.post(
        "/documents/upload",
        files=[("file", ("book.pdf", io.BytesIO(_MINIMAL_PDF), "text/plain"))],
    )
    assert response.status_code == 422


def test_upload_rejects_empty_filename(client: TestClient, tmp_library: Path):
    """A file with an empty name should be rejected."""
    response = client.post(
        "/documents/upload",
        files=[("file", ("", io.BytesIO(_MINIMAL_PDF), "application/pdf"))],
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: duplicate / overwrite handling
# ---------------------------------------------------------------------------


def test_upload_overwrite_default_replaces_file(client: TestClient, tmp_library: Path):
    """
    Uploading the same filename twice with the default overwrite=true should
    replace the file and return status 'overwritten'.
    """
    # First upload
    client.post("/documents/upload", files=[_make_pdf_upload("book.pdf")])

    # Second upload with different content
    new_content = _MINIMAL_PDF + b"% extra"
    response = client.post(
        "/documents/upload",
        files=[("file", ("book.pdf", io.BytesIO(new_content), "application/pdf"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "overwritten"
    assert data["size"] == len(new_content)
    assert (tmp_library / "book.pdf").read_bytes() == new_content


def test_upload_no_overwrite_returns_conflict(client: TestClient, tmp_library: Path):
    """
    When overwrite=false and the file already exists, the endpoint should
    return HTTP 409 Conflict and leave the original file intact.
    """
    # First upload
    client.post("/documents/upload", files=[_make_pdf_upload("book.pdf")])
    original = (tmp_library / "book.pdf").read_bytes()

    # Second upload with overwrite=false
    response = client.post(
        "/documents/upload?overwrite=false",
        files=[("file", ("book.pdf", io.BytesIO(b"different"), "application/pdf"))],
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    # Original file must be untouched.
    assert (tmp_library / "book.pdf").read_bytes() == original


# ---------------------------------------------------------------------------
# Tests: path-traversal prevention
# ---------------------------------------------------------------------------


def test_upload_strips_directory_components(client: TestClient, tmp_library: Path):
    """
    A filename like '../../etc/passwd.pdf' must be sanitised to 'passwd.pdf'
    and written inside LIBRARY_PATH only.
    """
    response = client.post(
        "/documents/upload",
        files=[("file", ("../../etc/passwd.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "passwd.pdf"
    assert (tmp_library / "passwd.pdf").exists()
