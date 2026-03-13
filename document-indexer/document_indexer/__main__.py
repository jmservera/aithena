from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path

import pdfplumber
import pika
from pika.adapters.blocking_connection import BlockingChannel
import redis
import requests
from retry import retry

from . import (
    BASE_PATH,
    QUEUE_NAME,
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    REDIS_HOST,
    REDIS_PORT,
    SOLR_COLLECTION,
    SOLR_HOST,
    SOLR_PORT,
)
from .metadata import extract_metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOLR_TIMEOUT = 300
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
queue = None


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
    return datetime.now(timezone.utc).isoformat()


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
def save_state(file_path: str, **updates) -> dict:
    state = load_state(file_path)
    state.update(updates)
    redis_client.set(redis_key(file_path), json.dumps(state))
    return state


def mark_failure(path: Path, error: str) -> None:
    last_modified = path.stat().st_mtime if path.exists() else None
    save_state(
        str(path),
        path=str(path),
        last_modified=last_modified,
        processed=False,
        failed=True,
        error=error,
        timestamp=now_iso(),
    )


def get_page_count(path: Path) -> int | None:
    try:
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to determine page count for %s: %s", path, exc)
        return None


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
    if page_count is not None:
        params["literal.page_count_i"] = str(page_count)

    return params


def index_document(path: Path) -> dict:
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported file type: {path.suffix or 'unknown'}")
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    metadata = extract_metadata(str(path), base_path=BASE_PATH)
    page_count = get_page_count(path)
    params = build_literal_params(metadata, page_count)
    solr_url = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}/update/extract"

    with path.open("rb") as handle:
        response = requests.post(
            solr_url,
            params=params,
            files={"file": (path.name, handle, "application/pdf")},
            timeout=SOLR_TIMEOUT,
        )

    response.raise_for_status()

    save_state(
        str(path),
        path=str(path),
        last_modified=path.stat().st_mtime,
        processed=True,
        failed=False,
        error=None,
        timestamp=now_iso(),
        solr_id=params["literal.id"],
        title=metadata["title"],
        author=metadata["author"],
        year=metadata["year"],
        category=metadata["category"],
        file_path=metadata["file_path"],
        folder_path=metadata["folder_path"],
        file_size=metadata["file_size"],
        page_count=page_count,
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
            mark_failure(Path(file_path), str(exc))
        except Exception:
            logger.exception("Unable to persist failed state for %s", file_path)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def consume() -> None:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT, heartbeat=600)
    )
    channel = connection.channel()
    get_queue(channel)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    try:
        channel.start_consuming()
    except pika.exceptions.ConnectionClosedByBroker:
        logger.warning("RabbitMQ closed the connection.")


if __name__ == "__main__":
    logger.info(
        "Starting document-indexer against Solr %s:%s/%s",
        SOLR_HOST,
        SOLR_PORT,
        SOLR_COLLECTION,
    )
    consume()
