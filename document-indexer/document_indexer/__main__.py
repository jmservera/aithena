from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pdfplumber
import pika
import redis
import requests
from pika.adapters.blocking_connection import BlockingChannel
from retry import retry

from . import (
    BASE_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDINGS_HOST,
    EMBEDDINGS_PORT,
    GIT_COMMIT,
    QUEUE_NAME,
    RABBITMQ_HOST,
    RABBITMQ_PASS,
    RABBITMQ_PORT,
    RABBITMQ_USER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    SOLR_COLLECTION,
    SOLR_HOST,
    SOLR_PORT,
    VERSION,
)
from .chunker import chunk_text_with_pages
from .embeddings import get_embeddings
from .metadata import extract_metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOLR_TIMEOUT = 300
SOLR_STARTUP_TIMEOUT = 10
SOLR_STARTUP_DELAY = 5
SOLR_STARTUP_ATTEMPTS = 60
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)
queue = None


def _rabbitmq_connection_parameters() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        RABBITMQ_HOST,
        RABBITMQ_PORT,
        heartbeat=600,
        credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
    )


def get_queue(channel: BlockingChannel):
    """Declare the queue and enable backpressure."""
    global queue
    channel.basic_qos(prefetch_count=1)
    queue = channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
        auto_delete=False,
        passive=queue is not None,
    )
    return queue


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def wait_for_solr_collection(
    max_attempts: int = SOLR_STARTUP_ATTEMPTS,
    delay: int = SOLR_STARTUP_DELAY,
) -> None:
    collections_url = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/admin/collections"
    config_url = f"http://{SOLR_HOST}:{SOLR_PORT}/api/collections/{SOLR_COLLECTION}/config"
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                collections_url,
                params={"action": "LIST", "wt": "json"},
                timeout=SOLR_STARTUP_TIMEOUT,
            )
            response.raise_for_status()
            collections = response.json().get("collections", [])
            if SOLR_COLLECTION not in collections:
                raise RuntimeError(f"Solr collection {SOLR_COLLECTION} is not available yet.")

            config_response = requests.get(config_url, timeout=SOLR_STARTUP_TIMEOUT)
            config_response.raise_for_status()
            if '"/update/extract"' not in config_response.text:
                raise RuntimeError(f"Solr collection {SOLR_COLLECTION} is missing /update/extract handler.")

            logger.info("Solr collection %s is ready.", SOLR_COLLECTION)
            return
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            logger.info(
                "Waiting for Solr collection %s (%s/%s): %s",
                SOLR_COLLECTION,
                attempt,
                max_attempts,
                exc,
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Solr collection {SOLR_COLLECTION} did not become ready after {max_attempts} attempts."
    ) from last_error


def redis_key(file_path: str) -> str:
    return f"/{QUEUE_NAME}/{file_path}"


@retry(redis.exceptions.ConnectionError, delay=5, jitter=(1, 3))
@retry(redis.exceptions.TimeoutError, delay=5, jitter=(1, 3))
def load_state(file_path: str) -> dict:
    current = redis_client.get(redis_key(file_path))
    if current is None:
        return {"path": file_path}

    try:
        return json.loads(current)
    except json.JSONDecodeError:
        logger.warning("Invalid Redis payload for %s. Resetting state.", file_path)
        return {"path": file_path}


@retry(redis.exceptions.ConnectionError, delay=5, jitter=(1, 3))
@retry(redis.exceptions.TimeoutError, delay=5, jitter=(1, 3))
def save_state(state_path: str, **updates) -> dict:
    state = load_state(state_path)
    state.update(updates)
    redis_client.set(redis_key(state_path), json.dumps(state))
    return state


def mark_failure(path: Path, error: str, stage: str = "unknown") -> None:
    """Persist a failure into Redis, recording which *stage* failed.

    Args:
        path: The file that was being processed.
        error: Human-readable description of the error.
        stage: ``"text_indexing"`` when Solr Tika extraction failed, or
            ``"embedding_indexing"`` when chunk/vector indexing failed.
    """
    last_modified = path.stat().st_mtime if path.exists() else None
    save_state(
        str(path),
        path=str(path),
        last_modified=last_modified,
        processed=False,
        failed=True,
        error=error,
        error_stage=stage,
        timestamp=now_iso(),
    )


def get_page_count(path: Path) -> int | None:
    try:
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to determine page count for %s: %s", path, exc)
        return None


def extract_pdf_text(path: Path) -> list[tuple[int, str]]:
    """Extract text per page from a PDF using pdfplumber (for chunk-based embedding indexing).

    Returns:
        An ordered list of ``(page_number, text)`` pairs where *page_number*
        is 1-based.  Pages that yield no text are omitted.
    """
    pages: list[tuple[int, str]] = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                pages.append((page_num, text))
    return pages


def build_literal_params(metadata: dict, page_count: int | None) -> dict[str, str]:
    doc_id = hashlib.sha256(metadata["file_path"].encode("utf-8")).hexdigest()
    params = {
        "resource.name": Path(metadata["file_path"]).name,
        "commitWithin": "10000",
        "literal.id": doc_id,
        "literal.title_s": metadata["title"],
        "literal.author_s": metadata["author"],
        "literal.file_path_s": metadata["file_path"],
        "literal.folder_path_s": metadata["folder_path"],
        "literal.file_size_l": str(metadata["file_size"]),
    }

    if metadata.get("category"):
        params["literal.category_s"] = metadata["category"]
    if metadata.get("year") is not None:
        params["literal.year_i"] = str(metadata["year"])
    if metadata.get("language"):
        params["literal.language_s"] = metadata["language"]
    if page_count is not None:
        params["literal.page_count_i"] = str(page_count)

    return params


def build_chunk_doc(
    parent_id: str,
    chunk_index: int,
    chunk: str,
    embedding: list[float],
    metadata: dict,
    page_start: int | None = None,
    page_end: int | None = None,
) -> dict:
    """Build a Solr JSON document for a single text chunk."""
    chunk_id = f"{parent_id}_chunk_{chunk_index:04d}"
    doc: dict = {
        "id": chunk_id,
        "parent_id_s": parent_id,
        "chunk_index_i": chunk_index,
        "chunk_text_t": chunk,
        "embedding_v": embedding,
        "title_s": metadata["title"],
        "author_s": metadata["author"],
        "file_path_s": metadata["file_path"],
        "folder_path_s": metadata["folder_path"],
    }
    if metadata.get("category"):
        doc["category_s"] = metadata["category"]
    if metadata.get("year") is not None:
        doc["year_i"] = metadata["year"]
    if metadata.get("language"):
        doc["language_s"] = metadata["language"]
    if page_start is not None:
        doc["page_start_i"] = page_start
    if page_end is not None:
        doc["page_end_i"] = page_end
    return doc


def index_chunks(
    path: Path,
    parent_id: str,
    metadata: dict,
) -> int:
    """Chunk the PDF text, obtain embeddings, and index into Solr.

    Returns:
        The number of chunks successfully indexed.

    Raises:
        Exception: Propagates any HTTP or embedding error so the caller can
            record the appropriate Redis failure stage.
    """
    pages = extract_pdf_text(path)
    page_chunks = chunk_text_with_pages(pages, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not page_chunks:
        logger.info("No text chunks extracted from %s; skipping embedding indexing.", path)
        return 0

    chunks = [chunk for chunk, _, _ in page_chunks]
    embeddings = get_embeddings(chunks, host=EMBEDDINGS_HOST, port=EMBEDDINGS_PORT)

    docs = [
        build_chunk_doc(parent_id, idx, chunk, emb, metadata, page_start, page_end)
        for idx, ((chunk, page_start, page_end), emb) in enumerate(zip(page_chunks, embeddings, strict=False))
    ]

    solr_url = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}/update?commitWithin=10000"
    response = requests.post(
        solr_url,
        json=docs,
        timeout=SOLR_TIMEOUT,
    )
    response.raise_for_status()
    return len(docs)


def index_document(path: Path) -> dict:
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported file type: {path.suffix or 'unknown'}")
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    metadata = extract_metadata(str(path), base_path=BASE_PATH)
    page_count = get_page_count(path)
    params = build_literal_params(metadata, page_count)
    solr_url = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}/update/extract"

    # ── Phase 1: full-text indexing via Solr Tika ──────────────────────────
    try:
        with path.open("rb") as handle:
            response = requests.post(
                solr_url,
                params=params,
                files={"file": (path.name, handle, "application/pdf")},
                timeout=SOLR_TIMEOUT,
            )
        response.raise_for_status()
    except Exception as exc:
        mark_failure(path, str(exc), stage="text_indexing")
        raise

    parent_id = params["literal.id"]
    save_state(
        str(path),
        path=str(path),
        last_modified=path.stat().st_mtime,
        processed=False,
        failed=False,
        error=None,
        error_stage=None,
        timestamp=now_iso(),
        solr_id=parent_id,
        text_indexed=True,
        embedding_indexed=False,
        title=metadata["title"],
        author=metadata["author"],
        year=metadata["year"],
        category=metadata["category"],
        file_path=metadata["file_path"],
        folder_path=metadata["folder_path"],
        file_size=metadata["file_size"],
        page_count=page_count,
    )

    # ── Phase 2: chunk + embedding indexing ────────────────────────────────
    try:
        chunk_count = index_chunks(path, parent_id, metadata)
    except Exception as exc:
        mark_failure(path, str(exc), stage="embedding_indexing")
        raise

    save_state(
        str(path),
        processed=True,
        embedding_indexed=True,
        chunk_count=chunk_count,
    )
    return metadata


def callback(
    channel: BlockingChannel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes,
):
    """Process a single queued document path."""
    file_path = body.decode("utf-8")
    remaining = get_queue(channel).method.message_count
    logger.info("Received %s. Remaining messages: %s", file_path, remaining)

    try:
        metadata = index_document(Path(file_path))
        logger.info(
            "Indexed %s by %s into Solr collection %s",
            metadata["title"],
            metadata["author"],
            SOLR_COLLECTION,
        )
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Failed to process %s", file_path)
        try:
            mark_failure(Path(file_path), str(exc), stage="unknown")
        except Exception:
            logger.exception("Unable to persist failed state for %s", file_path)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def consume() -> None:
    connection = pika.BlockingConnection(_rabbitmq_connection_parameters())
    channel = connection.channel()
    get_queue(channel)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    try:
        channel.start_consuming()
    except pika.exceptions.ConnectionClosedByBroker:
        logger.warning("RabbitMQ closed the connection.")


if __name__ == "__main__":
    logger.info("Starting document-indexer v%s (commit: %s)", VERSION, GIT_COMMIT)
    logger.info(
        "Starting document-indexer against Solr %s:%s/%s",
        SOLR_HOST,
        SOLR_PORT,
        SOLR_COLLECTION,
    )
    wait_for_solr_collection()
    consume()
