"""
E2E test scenario: upload → indexing → search → PDF viewing

This module tests the full aithena pipeline against a local dev stack:

  1. Upload   — a fixture PDF is written to the test library directory
               (the same bind-mount used by the document-lister and
               document-indexer services).
  2. Indexing — the test POSTs the PDF directly to Solr's /update/extract
               endpoint (mirroring exactly what the document-indexer does)
               so the test is fast and deterministic without requiring the
               10-minute polling cycle to elapse.
  3. Search   — the test queries Solr for the uploaded document and checks
               that all expected metadata fields are present and correct.
  4. Viewing  — the test verifies that the file_path_s field returned by
               Solr is a valid relative path so the viewer/serving layer
               can locate the PDF.

Prerequisites (see README.md §E2E Tests):
  • The local stack is running:
      docker compose -f docker-compose.yml -f docker/compose.e2e.yml up -d
  • Solr is healthy at http://localhost:8983 (or SOLR_URL).
  • E2E_LIBRARY_PATH matches the volume bind-mount in docker/compose.e2e.yml.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # noqa: S404 — diagnostic logging only, uses list args for safety
from pathlib import Path

import requests
from conftest import (
    SOLR_ADMIN_PASS,
    SOLR_ADMIN_USER,
    wait_for_solr_doc,
)

SOLR_TIMEOUT = 60  # seconds to wait for a Solr document to appear
SOLR_AUTH = (SOLR_ADMIN_USER, SOLR_ADMIN_PASS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _index_pdf(solr_url: str, pdf_path: Path, base_path: Path) -> requests.Response:
    """
    POST *pdf_path* to the Solr /update/extract endpoint with the same
    literal parameters that document-indexer uses.  This is the 'upload'
    step of the E2E test — it exercises the actual Solr Tika integration
    path rather than a mock.
    """
    relative = pdf_path.relative_to(base_path)
    # Always use forward slashes for the Solr ID hash (matches conftest.fixture_solr_id)
    relative_posix = relative.as_posix()
    doc_id = hashlib.sha256(relative_posix.encode()).hexdigest()

    stem = pdf_path.stem  # "TestAuthor - E2E Test Book (2024)"
    # Parse "Author - Title (Year)" filename convention
    parts = stem.split(" - ", 1)
    author = parts[0].strip() if len(parts) == 2 else "Unknown"
    title_year = parts[1].strip() if len(parts) == 2 else stem
    if title_year.endswith(")") and "(" in title_year:
        title_part, year_part = title_year.rsplit("(", 1)
        title = title_part.strip()
        year = year_part.rstrip(")")
    else:
        title = title_year
        year = None

    folder_path = relative.parent.as_posix()

    params: dict[str, str] = {
        "resource.name": pdf_path.name,
        "commitWithin": "2000",
        "literal.id": doc_id,
        "literal.title_s": title,
        "literal.author_s": author,
        "literal.file_path_s": relative_posix,
        "literal.folder_path_s": folder_path,
        "literal.file_size_l": str(pdf_path.stat().st_size),
        "literal.category_s": "TestCategory",
    }
    if year:
        params["literal.year_i"] = year

    with pdf_path.open("rb") as fh:
        resp = requests.post(
            f"{solr_url}/update/extract",
            params=params,
            files={"file": (pdf_path.name, fh, "application/pdf")},
            auth=SOLR_AUTH,
            timeout=60,
        )
    return resp


def _capture_diagnostics(solr_url: str, label: str) -> None:
    """Dump Solr admin stats and recent docs to stdout for CI diagnostics."""
    print(f"\n{'=' * 60}")
    print(f"DIAGNOSTIC CAPTURE: {label}")
    print(f"{'=' * 60}")
    try:
        info = requests.get(
            f"{solr_url}/select",
            params={"q": "*:*", "rows": "5", "wt": "json", "sort": "id asc"},
            auth=SOLR_AUTH,
            timeout=10,
        )
        print(f"[Solr recent docs] status={info.status_code}")
        print(json.dumps(info.json(), indent=2)[:2000])
    except Exception as exc:
        print(f"[Solr query failed] {exc}")

    # Attempt to dump docker compose logs for the indexer service
    try:
        docker_executable = shutil.which("docker")
        if docker_executable is None:
            raise FileNotFoundError("docker executable not found")
        result = subprocess.run(
            [docker_executable, "compose", "logs", "--tail=50", "document-indexer"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent,
        )
        print(f"\n[document-indexer logs (last 50 lines)]\n{result.stdout or result.stderr}")
    except Exception as exc:
        print(f"[docker logs unavailable] {exc}")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadIndexSearchView:
    """End-to-end scenario: upload → index → search → view."""

    # ------------------------------------------------------------------
    # Step 1 — Upload (write fixture PDF to the test library)
    # ------------------------------------------------------------------

    def test_fixture_pdf_exists_in_library(
        self, fixture_pdf: Path, test_library_root: Path, solr_available: None
    ) -> None:
        """
        The fixture PDF must be present in the test library directory before
        indexing can proceed.  This validates the 'upload' step of the
        pipeline (writing a file to the shared library mount).
        """
        assert fixture_pdf.exists(), (
            f"Fixture PDF not found at {fixture_pdf}. Check that the fixture was created correctly."
        )
        assert fixture_pdf.stat().st_size > 0, "Fixture PDF is empty."

    # ------------------------------------------------------------------
    # Step 2 — Indexing (POST to Solr /update/extract)
    # ------------------------------------------------------------------

    def test_index_document_into_solr(
        self,
        solr_url: str,
        fixture_pdf: Path,
        fixture_solr_id: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        POST the fixture PDF to Solr's /update/extract endpoint — the same
        API call that document-indexer makes — and verify Solr accepts it
        (HTTP 200) and the document is committed within SOLR_TIMEOUT seconds.
        """
        resp = _index_pdf(solr_url, fixture_pdf, test_library_root)

        if resp.status_code != 200:
            _capture_diagnostics(solr_url, "indexing-failure")
        assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"

        # Wait for the commit to propagate
        doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=SOLR_TIMEOUT)
        if doc is None:
            _capture_diagnostics(solr_url, "commit-timeout")
        assert doc is not None, (
            f"Document {fixture_solr_id} did not appear in Solr within {SOLR_TIMEOUT}s after indexing."
        )

    # ------------------------------------------------------------------
    # Step 3 — Search (full-text query via Solr select handler)
    # ------------------------------------------------------------------

    def test_search_returns_indexed_document(
        self,
        solr_url: str,
        fixture_solr_id: str,
        solr_available: None,
    ) -> None:
        """
        Query Solr for the fixture document by its deterministic ID and verify
        the indexed metadata fields are present and correct.
        """
        resp = requests.get(
            f"{solr_url}/select",
            params={
                "q": f"id:{fixture_solr_id}",
                "wt": "json",
                "fl": "id,title_s,author_s,year_i,file_path_s,folder_path_s",
            },
            auth=SOLR_AUTH,
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()

        docs = body["response"]["docs"]
        if not docs:
            _capture_diagnostics(solr_url, "search-returned-empty")
        assert docs, (
            "Solr returned no results for the fixture document. "
            "Ensure indexing completed before running the search test."
        )

        # Find our specific document (there may be others from earlier runs)
        fixture_doc = next((d for d in docs if d.get("id") == fixture_solr_id), None)
        if fixture_doc is None:
            _capture_diagnostics(solr_url, "fixture-doc-missing")
        assert fixture_doc is not None, (
            f"Fixture document (id={fixture_solr_id}) not in search results. Got: {[d.get('id') for d in docs]}"
        )

        assert fixture_doc.get("title_s") == "E2E Test Book", f"Unexpected title: {fixture_doc.get('title_s')!r}"
        assert fixture_doc.get("author_s") == "TestAuthor", f"Unexpected author: {fixture_doc.get('author_s')!r}"
        assert fixture_doc.get("year_i") == 2024, f"Unexpected year: {fixture_doc.get('year_i')!r}"

    # ------------------------------------------------------------------
    # Step 4 — PDF viewing (file_path_s resolves to an accessible file)
    # ------------------------------------------------------------------

    def test_pdf_file_path_is_accessible(
        self,
        solr_url: str,
        fixture_pdf: Path,
        fixture_solr_id: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        Retrieve file_path_s from the Solr document and verify the PDF file
        is accessible at {library_root}/{file_path_s}.  This validates the
        'open in viewer' step — the viewer relies on this path to serve the PDF.
        """
        resp = requests.get(
            f"{solr_url}/select",
            params={
                "q": f"id:{fixture_solr_id}",
                "wt": "json",
                "fl": "file_path_s",
            },
            auth=SOLR_AUTH,
            timeout=10,
        )
        resp.raise_for_status()
        docs = resp.json()["response"]["docs"]
        assert docs, f"Fixture document {fixture_solr_id} not found in Solr."

        file_path_s: str = docs[0].get("file_path_s", "")
        assert file_path_s, "file_path_s field is empty or missing in the Solr document."

        # The viewer reconstructs the full path as: library_root / file_path_s
        full_path = test_library_root / file_path_s
        assert full_path.exists(), f"PDF not accessible at {full_path}. file_path_s from Solr: {file_path_s!r}"
        assert full_path.stat().st_size > 0, f"PDF at {full_path} is empty."

    # ------------------------------------------------------------------
    # Cleanup — delete the fixture document from Solr after all steps pass
    # ------------------------------------------------------------------

    def test_cleanup_solr_document(
        self,
        solr_url: str,
        fixture_solr_id: str,
        solr_available: None,
    ) -> None:
        """
        Remove the fixture document from Solr so subsequent runs start clean.
        This test always runs last in the class due to alphabetical ordering
        (test_cleanup sorts after test_fixture, test_index, test_pdf, test_search).
        """
        resp = requests.post(
            f"{solr_url}/update",
            params={"commitWithin": "2000", "wt": "json"},
            json={"delete": {"id": fixture_solr_id}},
            auth=SOLR_AUTH,
            timeout=30,
        )
        # A 200 or 404 are both acceptable (document may not exist)
        assert resp.status_code in (200, 404), f"Unexpected status deleting fixture document: {resp.status_code}"
