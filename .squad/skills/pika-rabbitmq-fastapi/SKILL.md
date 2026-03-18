---
name: "pika-rabbitmq-fastapi"
description: "Thread-safe RabbitMQ integration with Pika in multi-worker FastAPI applications"
domain: "messaging, async processing, RabbitMQ"
confidence: "high"
source: "earned — PDF upload endpoint design and implementation, thread-safety audit"
---

## Context
FastAPI runs with multiple worker processes (uvicorn with `--workers N`). Pika's `BlockingConnection` is NOT thread-safe across workers. Mistakes can cause:
- Connection leaks (each request creates new connection, never closes)
- Queue lockups (multiple workers writing to same queue)
- Race conditions (credentials not applied correctly)
- Silent failures in RabbitMQ

aithena uses RabbitMQ for:
- Document pipeline (document-lister → RabbitMQ → document-indexer)
- PDF uploads (solr-search → /v1/upload → RabbitMQ)

## Patterns

### 1. **Per-Request RabbitMQ Connection in FastAPI**

❌ **WRONG** — global connection, reused across workers:
```python
# module-level (shared)
connection = pika.BlockingConnection(...)
channel = connection.channel()

@app.post("/upload")
def upload(file: UploadFile):
    # Multiple worker processes reusing same connection!
    channel.basic_publish(...)
```

✅ **RIGHT** — create and close per request:
```python
def get_rabbitmq_channel():
    """Create a new connection for this request."""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            credentials=pika.PlainCredentials(
                settings.rabbitmq_user,
                settings.rabbitmq_pass
            )
        )
    )
    channel = connection.channel()
    return connection, channel

@app.post("/upload")
def upload(file: UploadFile):
    connection, channel = get_rabbitmq_channel()
    try:
        channel.basic_publish(
            exchange="",
            routing_key="shortembeddings",
            body=file_path
        )
    finally:
        connection.close()
```

**Why:** Each FastAPI worker is a separate process. Sharing connections across processes causes undefined behavior.

**Overhead:** Per-request connection creation is ~50-100ms. Acceptable for async workflows where indexing happens in background. Use connection pooling for high-frequency operations.

### 2. **Always Set Credentials Explicitly**

❌ **WRONG** — relies on RabbitMQ default guest:
```python
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=settings.rabbitmq_host)
    # No credentials!
)
```

✅ **RIGHT** — always specify credentials:
```python
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=pika.PlainCredentials(
            settings.rabbitmq_user,
            settings.rabbitmq_pass
        )
    )
)
```

**Why:** Guest user is disabled in production. Even if enabled, credentials from env should be explicit (defense-in-depth).

### 3. **Graceful Shutdown**

Ensure queue acknowledgment before closing:
```python
try:
    channel.basic_publish(exchange="", routing_key="shortembeddings", body=message)
    # Don't close until publish is confirmed
    # (or use publisher confirms for higher reliability)
finally:
    channel.close()
    connection.close()
```

For consumers with acknowledgment:
```python
def callback(ch, method, properties, body):
    try:
        process_message(body)
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue="shortembeddings", on_message_callback=callback)
channel.start_consuming()
```

### 4. **Prefetch Count for Backpressure**

In document-indexer (RabbitMQ consumer):
```python
# Only fetch 1 message at a time (don't hog all queued messages)
channel.basic_qos(prefetch_count=1)

def on_message(ch, method, properties, body):
    try:
        process_large_pdf(body)  # may take 30s
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        # Now next message can be fetched

channel.basic_consume(queue="shortembeddings", on_message_callback=on_message)
channel.start_consuming()
```

**Why:** If worker stops mid-processing, prefetch_count=1 ensures no other messages are stuck in the worker's buffer.

### 5. **Queue Durability and Message Persistence**

For critical queues (document processing):
```python
# Queue is durable (survives broker restart)
channel.queue_declare(queue="shortembeddings", durable=True)

# Message is persistent (survives broker restart)
channel.basic_publish(
    exchange="",
    routing_key="shortembeddings",
    body=message,
    properties=pika.BasicProperties(delivery_mode=2)  # 2 = persistent
)
```

**Why:** Without durability, queue and messages disappear on RabbitMQ restart.

### 6. **Error Handling and Retry**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def publish_with_retry(message):
    connection, channel = get_rabbitmq_channel()
    try:
        channel.basic_publish(
            exchange="",
            routing_key="shortembeddings",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
    finally:
        connection.close()

@app.post("/upload")
def upload(file: UploadFile):
    try:
        publish_with_retry(file_path)
        return {"status": "queued", "upload_id": file_id}
    except Exception as exc:
        logger.error("Failed to queue upload: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Message queue unavailable")
```

### 7. **Health Checks**

Verify RabbitMQ connectivity:
```python
def check_rabbitmq_health():
    try:
        connection, channel = get_rabbitmq_channel()
        connection.close()
        return "CLOSED"  # circuit breaker state
    except pika.exceptions.AMQPConnectionError as exc:
        logger.error("RabbitMQ health check failed: %s", type(exc).__name__)
        return "OPEN"  # circuit breaker state
```

Expose in health endpoint:
```python
@app.get("/health")
def health():
    return {
        "solr": check_solr_health(),
        "redis": check_redis_health(),
        "rabbitmq": check_rabbitmq_health()
    }
```

## Examples

Reference implementations in aithena:
- `src/solr-search/main.py:680-720` — POST /v1/upload endpoint with RabbitMQ integration
- `src/document-indexer/` — consumer with prefetch_count=1
- `src/document-lister/` — publisher pattern
- `src/solr-search/main.py:200-220` — health check circuit breaker

## Anti-Patterns

- **Don't use global module-level connections in multi-worker apps** — connection not thread-safe
- **Don't skip credentials** — even if guest is allowed, always specify them
- **Don't forget `connection.close()`** — leaks file descriptors, eventually exhausts system
- **Don't set high `prefetch_count`** — causes message starvation if workers are slow
- **Don't publish without error handling** — queue might be down; return 502 to caller
- **Don't use non-persistent messages for critical work** — messages disappear on broker restart
- **Don't ignore connection errors** — wrap in try/finally or circuit breaker

## Testing

Mock Pika for unit tests:
```python
from unittest.mock import patch, MagicMock

@patch("main.pika.BlockingConnection")
def test_upload_publishes_to_queue(mock_connection_class):
    mock_connection = MagicMock()
    mock_channel = MagicMock()
    mock_connection.channel.return_value = mock_channel
    mock_connection_class.return_value = mock_connection
    
    # Call upload endpoint
    response = client.post("/upload", files={"file": ("test.pdf", b"%PDF-...")})
    
    # Verify basic_publish was called
    mock_channel.basic_publish.assert_called_once()
    args, kwargs = mock_channel.basic_publish.call_args
    assert kwargs["routing_key"] == "shortembeddings"
    
    # Verify connection was closed
    mock_connection.close.assert_called_once()
```

Integration test with real RabbitMQ:
```python
def test_upload_with_real_rabbitmq(client, docker_services):
    # Start real RabbitMQ via docker-services fixture
    response = client.post("/upload", files={"file": ("test.pdf", b"%PDF-...")})
    assert response.status_code == 202
    
    # Verify message in queue
    connection = pika.BlockingConnection(...)
    channel = connection.channel()
    method, properties, body = channel.basic_get(queue="shortembeddings")
    assert body  # message was delivered
```

## Scope & Enforcement

Applies to:
- solr-search (PDF upload endpoint)
- document-lister (periodic queue publisher)
- document-indexer (consumer, different pattern)
- admin (optional, future features)

Checked in:
- Code reviews (thread-safety audit)
- Integration tests (real RabbitMQ container)
- Health checks (circuit breaker validation)
