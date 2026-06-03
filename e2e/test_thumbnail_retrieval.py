"""
E2E test for thumbnail generation and retrieval.

This module validates thumbnail metadata handling:
  1. Index a PDF into Solr (same path as document-indexer).
  2. Store a thumbnail URL for the document (atomic Solr update).
  3. Verify solr-search returns the correct thumbnail_url field.

Prerequisites:
  • The local stack is running with Solr and solr-search reachable
  • E2E_LIBRARY_PATH is configured for the shared document volume
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
import requests
from conftest import SOLR_ADMIN_PASS, SOLR_ADMIN_USER, wait_for_solr_doc
from test_upload_index_search import _index_pdf

SOLR_AUTH = (SOLR_ADMIN_USER, SOLR_ADMIN_PASS)


def _build_multipage_pdf(texts: list[str]) -> bytes:
    """Return a minimal multi-page PDF containing the provided *texts*."""
    page_count = len(texts)
    page_obj_ids = [3 + i for i in range(page_count)]
    content_obj_ids = [3 + page_count + i for i in range(page_count)]
    font_id = 3 + (2 * page_count)

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    ]
    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_obj_ids)
    objects.append(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {page_count} >>\nendobj\n".encode())

    for page_id, content_id in zip(page_obj_ids, content_obj_ids, strict=True):
        objects.append(
            (
                f"{page_id} 0 obj\n<< /Type /Page /Parent 2 0 R"
                f" /MediaBox [0 0 612 792]"
                f" /Contents {content_id} 0 R"
                f" /Resources << /Font << /F1 {font_id} 0 R >> >> >>\nendobj\n"
            ).encode()
        )

    for content_id, text in zip(content_obj_ids, texts, strict=True):
        stream_body = (f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET").encode()
        objects.append(
            f"{content_id} 0 obj\n<< /Length {len(stream_body)} >>\nstream\n".encode()
            + stream_body
            + b"\nendstream\nendobj\n"
        )

    objects.append(f"{font_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode())

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

    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()

    return header + body + xref + trailer


def _update_solr_fields(solr_url: str, doc_id: str, fields: dict[str, object]) -> None:
    payload = {"id": doc_id}
    payload.update({name: {"set": value} for name, value in fields.items()})
    resp = requests.post(
        f"{solr_url}/update",
        params={"commit": "true", "wt": "json"},
        json=[payload],
        auth=SOLR_AUTH,
        timeout=30,
    )
    resp.raise_for_status()


def _fetch_solr_doc(solr_url: str, doc_id: str, fields: str) -> dict:
    resp = requests.get(
        f"{solr_url}/select",
        params={"q": f"id:{doc_id}", "wt": "json", "fl": fields},
        auth=SOLR_AUTH,
        timeout=10,
    )
    resp.raise_for_status()
    docs = resp.json().get("response", {}).get("docs", [])
    return docs[0] if docs else {}


def _wait_for_solr_field(
    solr_url: str,
    doc_id: str,
    field: str,
    expected: object,
    *,
    timeout: int = 60,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        updated = _fetch_solr_doc(solr_url, doc_id, field)
        if updated.get(field) == expected:
            return updated
        time.sleep(1)
    return {}


def _delete_solr_doc(solr_url: str, doc_id: str) -> None:
    resp = requests.post(
        f"{solr_url}/update",
        params={"commit": "true", "wt": "json"},
        json={"delete": {"id": doc_id}},
        auth=SOLR_AUTH,
        timeout=30,
    )
    resp.raise_for_status()


@pytest.fixture(scope="class")
def indexed_fixture_with_thumbnail(
    solr_url: str,
    fixture_pdf: Path,
    fixture_solr_id: str,
    test_library_root: Path,
    solr_available: None,
) -> dict[str, str]:
    resp = _index_pdf(solr_url, fixture_pdf, test_library_root)
    assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"

    doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=60)
    assert doc is not None, "Fixture document did not appear in Solr after indexing."

    relative = fixture_pdf.relative_to(test_library_root).as_posix()
    thumbnail_relative = f"{relative}.thumb.jpg"
    _update_solr_fields(solr_url, fixture_solr_id, {"thumbnail_url_s": thumbnail_relative})

    updated = _wait_for_solr_field(solr_url, fixture_solr_id, "thumbnail_url_s", thumbnail_relative)
    assert updated.get("thumbnail_url_s") == thumbnail_relative, (
        "Fixture thumbnail field did not appear in Solr after the atomic update."
    )

    yield {"doc_id": fixture_solr_id, "thumbnail_relative": thumbnail_relative}
    _delete_solr_doc(solr_url, fixture_solr_id)


@pytest.fixture(scope="class")
def api_available(api_url: str) -> None:
    """Skip tests that require the solr-search API if it is not reachable."""
    try:
        resp = requests.get(f"{api_url}/health", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            "solr-search API not reachable at "
            f"{api_url} — start the stack first (see README.md §E2E Tests). "
            f"Error: {exc}"
        )


class TestThumbnailGeneration:
    """Validate thumbnail metadata handling during document indexing."""

    def test_thumbnail_url_stored_after_indexing(
        self,
        solr_url: str,
        indexed_fixture_with_thumbnail: dict[str, str],
    ) -> None:
        """
        After indexing a PDF, verify that a thumbnail URL is stored in Solr
        and uses the expected *.thumb.jpg naming convention.
        """
        doc_id = indexed_fixture_with_thumbnail["doc_id"]
        expected = indexed_fixture_with_thumbnail["thumbnail_relative"]
        doc = _fetch_solr_doc(solr_url, doc_id, "thumbnail_url_s")
        assert doc.get("thumbnail_url_s") == expected, (
            "Solr document missing thumbnail_url_s or value mismatch. "
            f"Expected {expected!r}, got {doc.get('thumbnail_url_s')!r}"
        )
        assert expected.endswith(".thumb.jpg"), f"Thumbnail path should end with .thumb.jpg, got {expected!r}"

    def test_thumbnail_generated_for_multipage_pdf(
        self,
        solr_url: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        Index a multi-page PDF and verify the thumbnail URL is stored once.
        """
        pdf_path = test_library_root / "TestAuthor/TestAuthor - Multi Page E2E (2024).pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(_build_multipage_pdf(["Page 1", "Page 2"]))

        relative = pdf_path.relative_to(test_library_root).as_posix()
        doc_id = hashlib.sha256(relative.encode()).hexdigest()
        try:
            resp = _index_pdf(solr_url, pdf_path, test_library_root)
            assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"

            doc = wait_for_solr_doc(solr_url, doc_id, timeout=60)
            assert doc is not None, "Multi-page document did not appear in Solr after indexing."

            thumbnail_relative = f"{relative}.thumb.jpg"
            _update_solr_fields(
                solr_url,
                doc_id,
                {"thumbnail_url_s": thumbnail_relative, "page_count_i": 2},
            )

            updated = _wait_for_solr_field(
                solr_url,
                doc_id,
                "thumbnail_url_s",
                thumbnail_relative,
            )
            assert updated.get("thumbnail_url_s") == thumbnail_relative
            updated = _fetch_solr_doc(solr_url, doc_id, "page_count_i")
            assert updated.get("page_count_i") == 2
        finally:
            _delete_solr_doc(solr_url, doc_id)
            pdf_path.unlink(missing_ok=True)

    def test_book_detail_returns_thumbnail_url(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
        indexed_fixture_with_thumbnail: dict[str, str],
    ) -> None:
        """
        Book detail should include a thumbnail URL prefixed for nginx routing.
        """
        doc_id = indexed_fixture_with_thumbnail["doc_id"]
        expected = indexed_fixture_with_thumbnail["thumbnail_relative"]
        resp = requests.get(f"{api_url}/v1/books/{doc_id}", headers=auth_headers, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        assert body.get("thumbnail_url") == f"/thumbnails/{expected}", (
            "Book detail should include thumbnail_url prefixed with /thumbnails."
        )

    def test_thumbnail_api_returns_404_for_missing_document(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Book detail endpoint returns 404 for unknown documents.
        """
        missing_id = hashlib.sha256(b"missing-thumbnail-doc").hexdigest()
        resp = requests.get(f"{api_url}/v1/books/{missing_id}", headers=auth_headers, timeout=10)
        assert resp.status_code == 404, f"Expected 404 for unknown book id, got {resp.status_code}: {resp.text}"

    def test_thumbnail_url_is_stable_across_requests(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
        indexed_fixture_with_thumbnail: dict[str, str],
    ) -> None:
        """
        Thumbnail URLs should be stable across repeated book-detail requests,
        which enables downstream caching.
        """
        doc_id = indexed_fixture_with_thumbnail["doc_id"]
        first = requests.get(f"{api_url}/v1/books/{doc_id}", headers=auth_headers, timeout=10)
        second = requests.get(f"{api_url}/v1/books/{doc_id}", headers=auth_headers, timeout=10)
        first.raise_for_status()
        second.raise_for_status()
        first_body = first.json()
        second_body = second.json()
        assert first_body.get("thumbnail_url") == second_body.get("thumbnail_url")
        assert "?" not in (first_body.get("thumbnail_url") or ""), (
            "thumbnail_url should be a stable path without query params"
        )
