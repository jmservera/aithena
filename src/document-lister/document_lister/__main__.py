"""Scan the local document library and enqueue PDFs for indexing."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import pika
import redis
from retry import retry

from . import (
    BASE_PATH,
    DOCUMENT_WILDCARD,
    EXCHANGE_NAME,
    GIT_COMMIT,
    POLL_INTERVAL,
    QUEUE_NAME,
    RABBITMQ_HOST,
    RABBITMQ_PASS,
    RABBITMQ_PORT,
    RABBITMQ_USER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    VERSION,
)
from .logging_config import setup_logging

setup_logging(service_name="document-lister")
logger = logging.getLogger(__name__)


def _rabbitmq_connection_parameters() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        RABBITMQ_HOST,
        RABBITMQ_PORT,
        credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
    )


@retry(redis.exceptions.ConnectionError, delay=5, jitter=(1, 3))
@retry(redis.exceptions.TimeoutError, delay=5, jitter=(1, 3))
def process_path(path: str, redis_client: redis.Redis, channel: pika.channel.Channel):
    """Scan the local filesystem and enqueue matching PDFs."""

    base_path = Path(path)
    if not base_path.exists():
        logger.warning("Document path does not exist yet: %s", base_path)
        return

    logger.info("Scanning %s for %s", base_path, DOCUMENT_WILDCARD)
    for file_path in base_path.rglob(DOCUMENT_WILDCARD):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() != ".pdf":
            logger.info("Skipping non-PDF file: %s", file_path)
            continue
        handle_document(file_path, redis_client, channel)


def handle_document(path: Path, redis_client: redis.Redis, channel: pika.channel.Channel):
    """
    Handles a document by checking its status and pushing it to the queue if necessary.

    Args:
        path (Path): The path to the document file.
        redis_client (redis.Redis): The Redis client used for caching.
        channel (pika.channel.Channel): The RabbitMQ channel used for message queueing.
    """

    value = redis_client.get(f"/{QUEUE_NAME}/{path}")
    if value is None:
        logger.info("Found new document: %s", path)
        push_file_to_queue(channel, path)
        redis_client.set(
            f"/{QUEUE_NAME}/{path}",
            json.dumps(
                {
                    "path": f"{path}",
                    "last_modified": path.stat().st_mtime,
                    "processed": False,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        )
    else:
        value = json.loads(value)
        if value.get("last_modified", 0) != path.stat().st_mtime:
            logger.info("Found modified document: %s", path)
            value["last_modified"] = path.stat().st_mtime
            value["timestamp"] = datetime.now().isoformat()
            if value.get("processed", False) is True:
                logger.info("Document marked as unprocessed: %s", path)
                value["processed"] = False
                push_file_to_queue(channel, path)
            redis_client.set(f"/{QUEUE_NAME}/{path}", json.dumps(value))
        else:
            if value.get("processed", False) is False:
                logger.info("Document already in queue: %s", path)
            else:
                logger.info("Document already processed: %s", path)


def push_file_to_queue(channel, file):
    """
    Pushes a file path to the queue.

    Args:
        channel: The channel to use for publishing the blob.
        file: The file path to be pushed to the queue.

    Returns:
        None
    """
    correlation_id = str(uuid.uuid4())
    logger.info(
        "Enqueuing %s",
        file,
        extra={"file_path": str(file), "correlation_id": correlation_id},
    )
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=f"{file}",
        properties=pika.BasicProperties(
            delivery_mode=2,
            headers={"X-Correlation-ID": correlation_id},
        ),
    )


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def produce():
    """
    Produces messages to a RabbitMQ queue by recursively listing all files in a folder and sending
    them to the queue.

    This function connects to a Redis server and a RabbitMQ server, declares a queue, and then
    continuously lists all files in a specified folder.
    The file paths are sent as messages to the RabbitMQ queue.

    Raises:
        pika.exceptions.ConnectionClosedByBroker: If the connection to the RabbitMQ server is closed
        by the broker.
    """
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)

    connection = pika.BlockingConnection(_rabbitmq_connection_parameters())
    channel = connection.channel()
    logger.info("Declaring fanout exchange %s", EXCHANGE_NAME)
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)

    try:
        # recursively list all files in folder '/data'
        while True:
            process_path(BASE_PATH, redis_client, channel)
            # sleep for the configured poll interval
            connection.sleep(POLL_INTERVAL)

    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


if __name__ == "__main__":
    logger.info(
        "Starting document-lister v%s (commit: %s)",
        VERSION,
        GIT_COMMIT,
        extra={"version": VERSION, "commit": GIT_COMMIT},
    )
    produce()
