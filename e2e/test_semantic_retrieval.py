"""E2E semantic retrieval test for vector and hybrid search.

This module creates two PDFs with deliberately different subject matter, indexes
both parent documents into Solr via ``/update/extract``, then enqueues the same
files for the document-indexer so chunk embeddings are generated.  The semantic
queries intentionally avoid exact keyword overlap with the source texts so the
assertions exercise embedding similarity rather than BM25 keyword matching.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pika
import pytest
import requests
from conftest import SOLR_ADMIN_PASS, SOLR_ADMIN_USER, _build_pdf, wait_for_solr_doc

SOLR_AUTH = (SOLR_ADMIN_USER, SOLR_ADMIN_PASS)
SEARCH_ENDPOINT = "/v1/search"
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_ADMIN_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_ADMIN_PASS", "admin_dev_pass")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE_NAME", "shortembeddings")
# Container-visible base path for the document-indexer (matches docker-compose.yml)
INDEXER_BASE_PATH = os.environ.get("INDEXER_BASE_PATH", "/data/documents")
# Default kept under the per-test pytest-timeout (120s — see e2e/pytest.ini)
# so a missing override doesn't silently consume the whole budget.  The
# first test using the module-scoped fixture below applies a generous
# @pytest.mark.timeout to cover the indexing wait.
INDEX_TIMEOUT = int(os.environ.get("E2E_INDEX_TIMEOUT", "90"))
POLL_INTERVAL = 5
RUN_ID = uuid.uuid4().hex[:8]

DOC_CASES = (
    {
        "slug": "reef",
        "relative_path": (f"SemanticE2E/{RUN_ID}/Pelagia North/Pelagia North - Shallow Atoll Survey (2024).pdf"),
        "title": "Shallow Atoll Survey",
        "text": (
            "The coral reef biome shelters clownfish, sea anemones, crustaceans, "
            "and bright algae. Sunlit lagoons build calcium structures that protect "
            "coastlines and provide nursery grounds for countless animals."
        ),
        "query": "underwater life and biodiversity",
    },
    {
        "slug": "mars",
        "relative_path": (f"SemanticE2E/{RUN_ID}/Aster Vale/Aster Vale - Jezero Core Archive (2024).pdf"),
        "title": "Jezero Core Archive",
        "text": (
            "The rover explored Jezero Crater, drilled basalt cores, and sealed "
            "geological specimens for return to Earth. Researchers inspect the "
            "samples for biosignatures that could reveal whether ancient microbes "
            "once inhabited the planet."
        ),
        "query": "searching for extraterrestrial organisms on other worlds",
    },
)


def _compute_doc_id(pdf_path: Path, base_path: Path) -> str:
    relative = pdf_path.relative_to(base_path).as_posix()
    return hashlib.sha256(relative.encode()).hexdigest()


def _index_pdf(solr_url: str, pdf_path: Path, base_path: Path) -> requests.Response:
    """POST *pdf_path* to Solr's extract handler using the document-indexer shape."""
    relative = pdf_path.relative_to(base_path)
    relative_posix = relative.as_posix()
    doc_id = hashlib.sha256(relative_posix.encode()).hexdigest()

    stem = pdf_path.stem
    author, title_year = stem.split(" - ", 1)
    title_part, year_part = title_year.rsplit("(", 1)
    title = title_part.strip()
    year = year_part.rstrip(")")

    params = {
        "resource.name": pdf_path.name,
        "commitWithin": "2000",
        "literal.id": doc_id,
        "literal.title_s": title,
        "literal.author_s": author,
        "literal.file_path_s": relative_posix,
        "literal.folder_path_s": relative.parent.as_posix(),
        "literal.file_size_l": str(pdf_path.stat().st_size),
        "literal.category_s": "SemanticE2E",
        "literal.year_i": year,
    }

    with pdf_path.open("rb") as fh:
        return requests.post(
            f"{solr_url}/update/extract",
            params=params,
            files={"file": (pdf_path.name, fh, "application/pdf")},
            auth=SOLR_AUTH,
            timeout=60,
        )


def _publish_to_indexer(pdf_path: Path, test_library_root: Path) -> None:
    """Publish a container-visible file path to the RabbitMQ queue.

    The document-indexer runs inside Docker with BASE_PATH=/data/documents.
    The E2E library path on the host is bind-mounted at /data/documents inside
    the container, so we translate host paths to container paths before publishing.
    """
    relative = pdf_path.relative_to(test_library_root)
    container_path = f"{INDEXER_BASE_PATH}/{relative.as_posix()}"

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
            connection_attempts=3,
            retry_delay=2,
        )
    )
    try:
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True, auto_delete=False)
        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=container_path,
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        connection.close()


def _wait_for_chunk_docs(
    solr_url: str,
    parent_id: str,
    *,
    timeout: int = INDEX_TIMEOUT,
    poll_interval: int = POLL_INTERVAL,
) -> list[dict]:
    """Poll Solr until chunk documents for *parent_id* exist or timeout elapses."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = requests.get(
                f"{solr_url}/select",
                params={
                    "q": f"parent_id_s:{parent_id}",
                    "rows": "10",
                    "fl": "id,parent_id_s,title_s,file_path_s",
                    "wt": "json",
                },
                auth=SOLR_AUTH,
                timeout=10,
            )
            resp.raise_for_status()
            docs = resp.json()["response"]["docs"]
            if docs:
                return docs
        except Exception as exc:
            last_error = exc
            time.sleep(poll_interval)
            continue
        time.sleep(poll_interval)
    if last_error:
        print(f"[_wait_for_chunk_docs] last error while polling for {parent_id}: {last_error}")
    return []


def _delete_solr_documents(solr_url: str, doc_id: str) -> None:
    """Delete a parent document and all of its chunk documents.

    Best-effort: Solr returns 200/4xx for transient auth or collection
    state issues during teardown.  We log non-2xx responses so failures
    are visible rather than silently swallowed.
    """
    for payload in (
        {"delete": {"query": f"parent_id_s:{doc_id}"}},
        {"delete": {"id": doc_id}},
    ):
        try:
            resp = requests.post(
                f"{solr_url}/update",
                params={"commitWithin": "2000", "wt": "json"},
                json=payload,
                auth=SOLR_AUTH,
                timeout=30,
            )
            if not resp.ok:
                print(f"WARNING: Solr delete returned {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            print(f"WARNING: Solr delete failed: {exc}")


def _search(
    api_url: str, auth_headers: dict[str, str], *, query: str, mode: str, category: str | None = None
) -> requests.Response:
    params: dict[str, str] = {"q": query, "mode": mode, "limit": "5"}
    if category:
        params["fq_category"] = category
    return requests.get(
        f"{api_url}{SEARCH_ENDPOINT}",
        params=params,
        headers=auth_headers,
        timeout=30,
    )


def _assert_top_result_matches(
    body: dict,
    *,
    expected_title: str,
    expected_doc_id: str,
    expected_file_path: str,
    wrong_title: str,
) -> None:
    results = body.get("results", [])
    assert results, f"Search returned no results: {body}"

    top = results[0]
    assert top.get("title") == expected_title, (
        f"Expected top result {expected_title!r}, got {top.get('title')!r}. Full response: {body}"
    )
    assert top.get("title") != wrong_title, f"Wrong document {wrong_title!r} ranked first. Full response: {body}"
    assert top.get("file_path") == expected_file_path, (
        f"Expected file_path {expected_file_path!r}, got {top.get('file_path')!r}. Full response: {body}"
    )
    result_id = top.get("id", "")
    parent_id = top.get("parent_id") or ""
    assert result_id == expected_doc_id or result_id.startswith(expected_doc_id) or parent_id == expected_doc_id, (
        f"Top result did not map to document {expected_doc_id!r}. Full response: {body}"
    )


@pytest.fixture(scope="module")
def embeddings_ready(api_url: str, solr_available: None) -> None:
    """Skip when semantic search infrastructure is not available."""
    try:
        status = requests.get(f"{api_url}/v1/status", timeout=10)
        status.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Status endpoint unavailable; cannot verify embeddings readiness. Error: {exc}")

    payload = status.json()
    if not payload.get("embeddings_available"):
        pytest.skip("Embeddings service is unavailable; semantic retrieval E2E cannot run.")
    if payload.get("services", {}).get("rabbitmq") != "up":
        pytest.skip("RabbitMQ is unavailable; document-indexer cannot generate chunk embeddings.")

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
                connection_attempts=3,
                retry_delay=2,
            )
        )
        connection.close()
    except Exception as exc:
        pytest.skip(f"RabbitMQ admin connection failed; cannot enqueue PDFs for indexing. Error: {exc}")


@pytest.fixture(scope="module")
def semantic_test_docs(
    test_library_root: Path,
    solr_url: str,
    embeddings_ready: None,
) -> Generator[list[dict[str, str]], None, None]:
    """Create, index, and enqueue both semantic-retrieval fixture PDFs.

    Cleanup runs in finally-block regardless of setup failures, so partial
    runs don't leave stale documents or files behind.
    """
    created: list[dict[str, str]] = []

    try:
        for case in DOC_CASES:
            pdf_path = test_library_root / case["relative_path"]
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(_build_pdf(case["text"]))

            doc_id = _compute_doc_id(pdf_path, test_library_root)
            # Track immediately so cleanup runs even if indexing fails
            created.append(
                {
                    **case,
                    "doc_id": doc_id,
                    "pdf_path": str(pdf_path),
                }
            )

            response = _index_pdf(solr_url, pdf_path, test_library_root)
            assert response.status_code == 200, (
                f"Solr /update/extract returned {response.status_code} for {pdf_path.name}: {response.text}"
            )

            parent_doc = wait_for_solr_doc(solr_url, doc_id, timeout=INDEX_TIMEOUT, auth=SOLR_AUTH)
            assert parent_doc is not None, f"Parent document {doc_id} did not appear in Solr."

            _publish_to_indexer(pdf_path, test_library_root)
            chunk_docs = _wait_for_chunk_docs(solr_url, doc_id)
            assert chunk_docs, (
                f"Chunk documents for {doc_id} ({case['slug']}) were not indexed within {INDEX_TIMEOUT}s. "
                f"Check document-indexer logs for errors processing the queued file."
            )

        yield created
    finally:
        for entry in created:
            _delete_solr_documents(solr_url, entry["doc_id"])
            pdf_path = Path(entry["pdf_path"])
            pdf_path.unlink(missing_ok=True)
            current = pdf_path.parent
            while current != test_library_root and current.exists():
                try:
                    current.rmdir()
                except OSError:
                    break
                current = current.parent


class TestSemanticRetrieval:
    """Validate semantic and hybrid search over freshly indexed documents."""

    # The first test that uses the module-scoped semantic_test_docs fixture
    # triggers the indexing wait (up to 2 * INDEX_TIMEOUT for parent + chunks).
    # Override the suite-wide pytest-timeout so the indexing wait fits.
    @pytest.mark.timeout(INDEX_TIMEOUT * 2 + 60)
    def test_semantic_mode_ranks_the_correct_document(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        semantic_test_docs: list[dict[str, str]],
    ) -> None:
        """Semantic mode must retrieve the intended document for synonym-style queries."""
        for case in semantic_test_docs:
            wrong_title = next(doc["title"] for doc in semantic_test_docs if doc["slug"] != case["slug"])
            response = _search(api_url, auth_headers, query=case["query"], mode="semantic", category="SemanticE2E")
            assert response.status_code == 200, (
                f"Semantic search failed for {case['slug']}: {response.status_code} {response.text}"
            )

            body = response.json()
            assert body.get("mode") == "semantic", f"Expected semantic mode response, got: {body}"
            _assert_top_result_matches(
                body,
                expected_title=case["title"],
                expected_doc_id=case["doc_id"],
                expected_file_path=case["relative_path"],
                wrong_title=wrong_title,
            )

    def test_hybrid_mode_ranks_the_correct_document(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        semantic_test_docs: list[dict[str, str]],
    ) -> None:
        """Hybrid mode must keep the semantically correct document ahead of the wrong one."""
        for case in semantic_test_docs:
            wrong_title = next(doc["title"] for doc in semantic_test_docs if doc["slug"] != case["slug"])
            response = _search(api_url, auth_headers, query=case["query"], mode="hybrid", category="SemanticE2E")
            assert response.status_code == 200, (
                f"Hybrid search failed for {case['slug']}: {response.status_code} {response.text}"
            )

            body = response.json()
            assert body.get("mode") == "hybrid", f"Expected hybrid mode response, got: {body}"
            _assert_top_result_matches(
                body,
                expected_title=case["title"],
                expected_doc_id=case["doc_id"],
                expected_file_path=case["relative_path"],
                wrong_title=wrong_title,
            )
