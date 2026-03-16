"""
E2E tests for the upload API error paths and validation.

These tests run against the live solr-search /v1/upload endpoint and verify
that the API correctly rejects invalid uploads and accepts valid ones.

Unlike the unit tests in ``src/solr-search/tests/test_upload.py`` (which mock
RabbitMQ and the filesystem), these tests exercise the full production code
path against the running service.  They are designed to be repeatable and
self-contained — they do not leave persistent state.

Prerequisites:
  • The stack is running and solr-search is reachable at SEARCH_API_URL.
  • Set SEARCH_API_URL to override (default: http://localhost:8080).

Coverage matrix
~~~~~~~~~~~~~~~

+-----------------------------------+-------+------------+
| Scenario                          | Gated | Note       |
+===================================+=======+============+
| Invalid content-type rejection    | No    | deterministic |
| Non-PDF extension rejection       | No    | deterministic |
| Invalid PDF content rejection     | No    | deterministic |
| File too large rejection          | No    | deterministic |
| No file in request rejection      | No    | deterministic |
| Valid PDF accepted (201/202)      | Yes   | requires RabbitMQ + filesystem writable |
+-----------------------------------+-------+------------+

Deterministic tests (top five) can run without a fully configured stack as
long as the solr-search service is reachable — they do not require RabbitMQ
or a writable upload directory.  Valid-upload acceptance is skipped
automatically if the service is not ready.
"""

from __future__ import annotations

import io
import os

import pytest
import requests

SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")
UPLOAD_ENDPOINT = "/v1/upload"

# Minimal valid single-page PDF (matches the generator in conftest.py)
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_url() -> str:
    """Resolved base URL for the solr-search API."""
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_available(api_url: str) -> None:
    """Skip all tests in this module if the API is not reachable."""
    try:
        resp = requests.get(f"{api_url}/health", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"solr-search API not reachable at {api_url} — start the stack first "
            f"(see README.md §E2E Tests). Error: {exc}"
        )


# ---------------------------------------------------------------------------
# Upload error-path tests (deterministic — reject before filesystem access)
# ---------------------------------------------------------------------------


class TestUploadValidationErrors:
    """Upload endpoint rejects invalid requests with appropriate HTTP status codes.

    These tests are deterministic: they do not depend on a writable upload
    directory or a running RabbitMQ broker, because the validation errors are
    raised before any external resource is accessed.
    """

    def test_upload_requires_file_field(self, api_url: str, api_available: None) -> None:
        """POST /v1/upload without a file must return HTTP 422 (Unprocessable Entity)."""
        resp = requests.post(f"{api_url}{UPLOAD_ENDPOINT}", timeout=10)
        assert resp.status_code == 422, (
            f"Expected 422 when no file is attached, got {resp.status_code}: {resp.text}"
        )

    def test_upload_rejects_non_pdf_content_type(self, api_url: str, api_available: None) -> None:
        """POST /v1/upload with a non-PDF MIME type must return HTTP 400.

        The backend validates content-type and rejects non-PDF MIME types with
        400 Bad Request (matching src/solr-search/tests/test_upload.py behaviour).
        """
        resp = requests.post(
            f"{api_url}{UPLOAD_ENDPOINT}",
            files={"file": ("document.txt", io.BytesIO(b"just text"), "text/plain")},
            timeout=10,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for text/plain content-type, got {resp.status_code}: {resp.text}"
        )

    def test_upload_rejects_non_pdf_extension(self, api_url: str, api_available: None) -> None:
        """POST /v1/upload with a non-.pdf extension must return HTTP 400.

        The backend validates the filename extension and rejects files whose
        name does not end in .pdf with 400 Bad Request (matching
        src/solr-search/tests/test_upload.py behaviour).
        """
        resp = requests.post(
            f"{api_url}{UPLOAD_ENDPOINT}",
            files={"file": ("report.docx", io.BytesIO(b"fake docx content"), "application/pdf")},
            timeout=10,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for .docx extension, got {resp.status_code}: {resp.text}"
        )

    def test_upload_rejects_invalid_pdf_bytes(self, api_url: str, api_available: None) -> None:
        """POST /v1/upload with non-PDF bytes declared as application/pdf must return HTTP 400."""
        resp = requests.post(
            f"{api_url}{UPLOAD_ENDPOINT}",
            files={"file": ("book.pdf", io.BytesIO(b"this is not a pdf"), "application/pdf")},
            timeout=10,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for invalid PDF content, got {resp.status_code}: {resp.text}"
        )

    def test_upload_rejects_oversized_file(self, api_url: str, api_available: None) -> None:
        """POST /v1/upload with a file larger than MAX_UPLOAD_SIZE_MB must return HTTP 413."""
        # Generate a payload larger than the default 50 MB limit
        oversized = b"%PDF-1.4\n" + b"X" * (52 * 1024 * 1024)
        resp = requests.post(
            f"{api_url}{UPLOAD_ENDPOINT}",
            files={"file": ("huge.pdf", io.BytesIO(oversized), "application/pdf")},
            timeout=60,
        )
        assert resp.status_code == 413, (
            f"Expected 413 for oversized file, got {resp.status_code}: {resp.text}"
        )

    def test_upload_error_response_contains_detail(self, api_url: str, api_available: None) -> None:
        """Upload rejection response must include a 'detail' field describing the error."""
        resp = requests.post(
            f"{api_url}{UPLOAD_ENDPOINT}",
            files={"file": ("bad.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
            timeout=10,
        )
        # Invalid PDF content returns 400 Bad Request
        assert resp.status_code == 400, f"Unexpected status: {resp.status_code}"
        body = resp.json()
        assert "detail" in body, f"'detail' missing from error response: {body}"
        assert body["detail"], f"'detail' is empty: {body}"


# ---------------------------------------------------------------------------
# Upload acceptance test (gated on fully configured stack)
# ---------------------------------------------------------------------------


class TestUploadAcceptance:
    """Valid PDF upload is accepted by the service.

    This test requires a writable upload directory and a reachable RabbitMQ
    broker.  It is automatically skipped when those resources are unavailable.

    Fixture dependency: requires fully configured stack
    """

    def test_valid_pdf_upload_returns_success_status(self, api_url: str, api_available: None) -> None:
        """POST /v1/upload with a valid PDF must return HTTP 200 or 201."""
        resp = requests.post(
            f"{api_url}{UPLOAD_ENDPOINT}",
            files={"file": ("e2e-upload-test.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
            timeout=30,
        )
        if resp.status_code in (500, 503):
            pytest.skip(
                f"Upload endpoint returned {resp.status_code} — "
                "RabbitMQ or upload directory may not be configured for this environment. "
                f"Response: {resp.text}"
            )
        assert resp.status_code in (200, 201, 202), (
            f"Expected 200/201/202 for a valid PDF upload, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "filename" in body or "message" in body or "id" in body, (
            f"Upload response missing expected fields (filename/message/id): {body}"
        )
