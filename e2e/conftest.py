"""
Shared fixtures for the aithena E2E test suite.

Environment variables (with defaults for the local dev stack):
  SOLR_URL          Solr base URL, e.g. http://localhost:8983/solr/books
  SEARCH_API_URL    solr-search base URL, e.g. http://localhost:8080
  E2E_LIBRARY_PATH  Absolute path used as the test book library root.
                    The document-data volume must be bound to the same path
                    when running the stack with docker-compose.e2e.yml.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Generator
from pathlib import Path

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOLR_URL: str = os.environ.get("SOLR_URL", "http://localhost:8983/solr/books")
SOLR_ADMIN_USER: str = os.environ.get("SOLR_ADMIN_USER", "solr_admin")
SOLR_ADMIN_PASS: str = os.environ.get("SOLR_ADMIN_PASS", "SolrAdmin_dev2024!")
SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")
E2E_LIBRARY_PATH: str = os.environ.get("E2E_LIBRARY_PATH", "/tmp/aithena-e2e-library")

# Relative path inside the library; uses the Author - Title (Year) pattern so
# the metadata extractor produces deterministic fields.
FIXTURE_RELATIVE_PATH = "TestAuthor/TestAuthor - E2E Test Book (2024).pdf"


# ---------------------------------------------------------------------------
# Minimal-PDF generator (no external dependencies)
# ---------------------------------------------------------------------------


def _build_pdf(text: str = "E2E test document for aithena") -> bytes:
    """Return a minimal but valid single-page PDF containing *text*."""

    stream_body = (f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET").encode()

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R"
            b" /MediaBox [0 0 612 792]"
            b" /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (
            b"4 0 obj\n<< /Length "
            + str(len(stream_body)).encode()
            + b" >>\nstream\n"
            + stream_body
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    header = b"%PDF-1.4\n"
    body = b""
    offsets: list[int] = []
    offset = len(header)
    for obj in objects:
        offsets.append(offset)
        body += obj
        offset += len(obj)

    xref_offset = len(header) + len(body)
    xref = b"xref\n" + f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n").encode()

    return header + body + xref + trailer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def solr_url() -> str:
    """Base Solr collection URL, e.g. http://localhost:8983/solr/books."""
    return SOLR_URL


@pytest.fixture(scope="session")
def solr_auth() -> tuple[str, str]:
    """Solr basic auth credentials (username, password)."""
    return (SOLR_ADMIN_USER, SOLR_ADMIN_PASS)


@pytest.fixture(scope="session")
def solr_available(solr_url: str, solr_auth: tuple[str, str]) -> None:
    """Fail fast if the Solr books collection is not reachable."""
    try:
        resp = requests.get(
            f"{solr_url}/admin/ping",
            params={"distrib": "true"},
            auth=solr_auth,
            timeout=5,
        )
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"Solr not reachable at {solr_url} — start the stack first (see README.md §E2E Tests). Error: {exc}"
        )


@pytest.fixture(scope="session")
def api_url() -> str:
    """Resolved base URL for the solr-search API."""
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def auth_headers(api_url: str) -> dict[str, str]:
    """Log into the live API and return bearer auth headers for protected endpoints."""
    username = os.environ.get("E2E_USERNAME", os.environ.get("CI_ADMIN_USERNAME", "admin"))
    password = os.environ.get("E2E_PASSWORD")
    if not password:
        password = os.environ.get("CI_ADMIN_PASSWORD")
    if not password:
        pytest.skip("E2E_PASSWORD environment variable must be set for authenticated endpoints")

    resp = requests.post(
        f"{api_url}/v1/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not isinstance(token, str) or not token:
        pytest.fail(f"Login response missing access_token: {resp.text}")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_api_headers() -> dict[str, str]:
    """Return X-API-Key headers for admin endpoints."""
    api_key = os.environ.get("ADMIN_API_KEY")
    if not api_key:
        pytest.skip("ADMIN_API_KEY environment variable must be set for admin endpoints")
    return {"X-API-Key": api_key}


@pytest.fixture(scope="session")
def test_library_root() -> Generator[Path, None, None]:
    """
    Temporary library directory used as the document-data volume root.

    The directory is created before the session and removed afterwards.
    Set E2E_LIBRARY_PATH to override the location (must match the volume
    bind-mount used by docker-compose.e2e.yml).
    """
    root = Path(E2E_LIBRARY_PATH)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    # Cleanup: remove only the fixture subdirectory, leaving the root intact
    # so that any manually added files are preserved between runs.


@pytest.fixture(scope="session")
def fixture_pdf(test_library_root: Path) -> Generator[Path, None, None]:
    """
    Copy a minimal test PDF into *test_library_root* / FIXTURE_RELATIVE_PATH
    and yield its absolute path.  Removes the file (and empty parent dirs)
    after the session.
    """
    pdf_path = test_library_root / FIXTURE_RELATIVE_PATH
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(_build_pdf())
    yield pdf_path
    # Teardown — remove fixture file and its empty parent directory
    try:
        pdf_path.unlink(missing_ok=True)
        if pdf_path.parent.exists() and not any(pdf_path.parent.iterdir()):
            pdf_path.parent.rmdir()
    except OSError:
        pass


@pytest.fixture(scope="session")
def fixture_solr_id(fixture_pdf: Path) -> str:
    """
    Return the deterministic Solr document ID for the fixture PDF.

    The indexer uses SHA-256 of the relative file path (relative to BASE_PATH).
    """
    relative = Path(FIXTURE_RELATIVE_PATH)
    return hashlib.sha256(relative.as_posix().encode()).hexdigest()


def wait_for_solr_doc(
    solr_url: str,
    doc_id: str,
    timeout: int = 90,
    poll_interval: int = 5,
    auth: tuple[str, str] | None = None,
) -> dict | None:
    """
    Poll Solr until a document with *doc_id* appears or *timeout* seconds pass.

    Returns the Solr document dict on success, or None on timeout.
    """
    if auth is None:
        auth = (SOLR_ADMIN_USER, SOLR_ADMIN_PASS)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(
                f"{solr_url}/select",
                params={"q": f"id:{doc_id}", "wt": "json"},
                auth=auth,
                timeout=10,
            )
            resp.raise_for_status()
            docs = resp.json()["response"]["docs"]
            if docs:
                return docs[0]
        except Exception:
            time.sleep(poll_interval)
            continue
        time.sleep(poll_interval)
    return None
