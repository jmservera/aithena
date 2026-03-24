"""E2E tests for RabbitMQ user permissions.

Validates that each service user has exactly the permissions needed
for their operations. Catches permission regressions like the
queue_bind failure that broke v1.14.1.

Permission matrix (from init-definitions.sh):
  lister  — configure: ^documents$, write: ^documents$, read: ^$
  indexer — configure+write+read: ^(documents|shortembeddings.*)$
  search  — configure: ^shortembeddings$, write: ^$, read: ^$
  admin   — full access (.*)
"""

from __future__ import annotations

import os
import uuid

import pika
import pika.exceptions
import pytest

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))

# Credentials from environment, with dev defaults matching init-definitions.sh
USERS = {
    "lister": os.environ.get("RABBITMQ_LISTER_PASS", "lister_dev_pass"),
    "indexer": os.environ.get("RABBITMQ_INDEXER_PASS", "indexer_dev_pass"),
    "search": os.environ.get("RABBITMQ_SEARCH_PASS", "search_dev_pass"),
    "admin": os.environ.get("RABBITMQ_ADMIN_PASS", "admin_dev_pass"),
}

# Unique tag so parallel runs don't collide
_RUN_ID = uuid.uuid4().hex[:8]


def _connect(username: str, password: str) -> pika.BlockingConnection:
    """Create a blocking RabbitMQ connection for a service user."""
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(username, password),
            connection_attempts=3,
            retry_delay=2,
        )
    )


def _user_conn(name: str) -> pika.BlockingConnection:
    """Shortcut: connect as a named service user."""
    return _connect(name, USERS[name])


@pytest.fixture(scope="module")
def rabbitmq_available():
    """Skip all tests in this module if RabbitMQ is not reachable."""
    try:
        conn = _connect("admin", USERS["admin"])
        conn.close()
    except Exception:
        pytest.skip("RabbitMQ not available — start the stack first")


@pytest.fixture(scope="module")
def _ensure_exchange_and_queue(rabbitmq_available):
    """Ensure the documents exchange and shortembeddings queue exist.

    Uses the admin user so the test preconditions are always met,
    regardless of which permission tests run first.
    """
    conn = _user_conn("admin")
    ch = conn.channel()
    ch.exchange_declare(exchange="documents", exchange_type="fanout", durable=True)
    ch.queue_declare(queue="shortembeddings", durable=True)
    ch.queue_bind(queue="shortembeddings", exchange="documents")
    ch.close()
    conn.close()


# ── Indexer ─────────────────────────────────────────────────────────────────


class TestIndexerPermissions:
    """Indexer must publish, consume, and queue_bind on documents/shortembeddings."""

    def test_indexer_can_publish_to_documents_exchange(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Indexer can publish messages to the documents fanout exchange."""
        conn = _user_conn("indexer")
        ch = conn.channel()
        ch.basic_publish(
            exchange="documents",
            routing_key="",
            body=f"test-indexer-publish-{_RUN_ID}".encode(),
        )
        ch.close()
        conn.close()

    def test_indexer_can_declare_shortembeddings_queue(self, rabbitmq_available):
        """Indexer can (re-)declare the shortembeddings queue."""
        conn = _user_conn("indexer")
        ch = conn.channel()
        ch.queue_declare(queue="shortembeddings", durable=True)
        ch.close()
        conn.close()

    def test_indexer_can_consume_from_shortembeddings(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Indexer can consume from the shortembeddings queue."""
        conn = _user_conn("indexer")
        ch = conn.channel()
        ch.queue_declare(queue="shortembeddings", durable=True)
        # basic_consume + immediate cancel proves the READ permission
        tag = ch.basic_consume(
            queue="shortembeddings", auto_ack=True, on_message_callback=lambda *_: None
        )
        ch.basic_cancel(tag)
        ch.close()
        conn.close()

    def test_indexer_can_queue_bind(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """CRITICAL: Indexer can bind shortembeddings queue to documents exchange.

        queue_bind requires WRITE on the destination queue AND READ on
        the source exchange. This is the exact operation that broke in
        v1.14.1 when permissions were accidentally narrowed.
        """
        conn = _user_conn("indexer")
        ch = conn.channel()
        ch.queue_declare(queue="shortembeddings", durable=True)
        # This is the call that failed in v1.14.1
        ch.queue_bind(queue="shortembeddings", exchange="documents")
        ch.close()
        conn.close()


# ── Lister ──────────────────────────────────────────────────────────────────


class TestListerPermissions:
    """Lister can only publish to the documents exchange."""

    def test_lister_can_publish_to_documents(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Lister can publish to the documents fanout exchange."""
        conn = _user_conn("lister")
        ch = conn.channel()
        ch.basic_publish(
            exchange="documents",
            routing_key="",
            body=f"test-lister-publish-{_RUN_ID}".encode(),
        )
        ch.close()
        conn.close()

    def test_lister_cannot_consume_from_shortembeddings(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Lister must NOT be able to consume from shortembeddings.

        Lister has read: ^$ so any basic_consume should be refused.
        """
        conn = _user_conn("lister")
        ch = conn.channel()
        with pytest.raises(pika.exceptions.ChannelClosedByBroker) as exc_info:
            ch.basic_consume(
                queue="shortembeddings",
                auto_ack=True,
                on_message_callback=lambda *_: None,
            )
        # 403 = ACCESS_REFUSED
        assert exc_info.value.reply_code == 403
        conn.close()

    def test_lister_cannot_declare_shortembeddings(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Lister must NOT be able to declare the shortembeddings queue.

        Lister has configure: ^documents$ — shortembeddings doesn't match.
        """
        conn = _user_conn("lister")
        ch = conn.channel()
        with pytest.raises(pika.exceptions.ChannelClosedByBroker) as exc_info:
            # passive=False forces a configure check
            ch.queue_declare(queue="shortembeddings", durable=True)
        assert exc_info.value.reply_code == 403
        conn.close()


# ── Search ──────────────────────────────────────────────────────────────────


class TestSearchPermissions:
    """Search user has very limited permissions."""

    def test_search_cannot_publish_to_documents(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Search must NOT be able to publish to the documents exchange.

        Search has write: ^$ so publishing should be refused.
        Enable confirm_delivery so basic_publish waits for broker response
        and surfaces the ACCESS_REFUSED synchronously.
        """
        conn = _user_conn("search")
        ch = conn.channel()
        with pytest.raises(pika.exceptions.ChannelClosedByBroker) as exc_info:
            ch.confirm_delivery()
            ch.basic_publish(
                exchange="documents",
                routing_key="",
                body=b"should-fail",
            )
        assert exc_info.value.reply_code == 403
        conn.close()

    def test_search_cannot_consume_from_shortembeddings(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Search must NOT be able to consume from shortembeddings.

        Search has read: ^$ so basic_consume should be refused.
        """
        conn = _user_conn("search")
        ch = conn.channel()
        with pytest.raises(pika.exceptions.ChannelClosedByBroker) as exc_info:
            ch.basic_consume(
                queue="shortembeddings",
                auto_ack=True,
                on_message_callback=lambda *_: None,
            )
        assert exc_info.value.reply_code == 403
        conn.close()

    def test_search_can_declare_shortembeddings(self, rabbitmq_available):
        """Search can passively declare shortembeddings (configure: ^shortembeddings$)."""
        conn = _user_conn("search")
        ch = conn.channel()
        ch.queue_declare(queue="shortembeddings", durable=True)
        ch.close()
        conn.close()


# ── Admin ───────────────────────────────────────────────────────────────────


class TestAdminPermissions:
    """Admin has full access — sanity check."""

    def test_admin_can_perform_all_operations(
        self, rabbitmq_available, _ensure_exchange_and_queue
    ):
        """Admin can declare, bind, publish, and consume."""
        conn = _user_conn("admin")
        ch = conn.channel()

        ch.exchange_declare(exchange="documents", exchange_type="fanout", durable=True)
        ch.queue_declare(queue="shortembeddings", durable=True)
        ch.queue_bind(queue="shortembeddings", exchange="documents")
        ch.basic_publish(
            exchange="documents",
            routing_key="",
            body=f"test-admin-{_RUN_ID}".encode(),
        )
        tag = ch.basic_consume(
            queue="shortembeddings",
            auto_ack=True,
            on_message_callback=lambda *_: None,
        )
        ch.basic_cancel(tag)

        # Clean up any test messages we published
        ch.queue_purge(queue="shortembeddings")
        ch.close()
        conn.close()
