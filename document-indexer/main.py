import pika
from pika.adapters.blocking_connection import BlockingChannel
import os
import redis
from retry import retry
import pdfplumber
import requests
from qdrant_client import models, QdrantClient
import uuid

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = os.environ.get('RABBITMQ_PORT', 5672)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', 6379)
EMBEDDINGS_HOST= os.environ.get('EMBEDDINGS_HOST', 'localhost')
EMBEDDINGS_PORT= os.environ.get('EMBEDDINGS_PORT', 5000)
QDRANT_HOST= os.environ.get('QDRANT_HOST', 'localhost')
QDRANT_PORT= os.environ.get('QDRANT_PORT', 6333)

def get_embeddings(text):
    r = requests.get(f'http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/?text={text}')
    return r.json()['result']

def callback(channel: BlockingChannel, method, properties, body):
    print(f"Received new document: {body}")

    qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")
    qdrant.recreate_collection(
        collection_name="documents",
        vectors_config=models.VectorParams(
            size=4096,# todo: get from service... encoder.get_sentence_embedding_dimension(), # Vector size is defined by used model
            distance=models.Distance.COSINE
        )
    )


    f = body.decode('utf-8')
    with pdfplumber.open(f) as pdf:
        for page in pdf.pages:
            print(f"Processing page {page.page_number}/{len(pdf.pages)} of {f}")          
            text = page.extract_text()
            text = text.split('\n')
            lineNumber = 0
            for line in text:               
                lineNumber += 1
                embedding = get_embeddings(line)
                qdrant.upsert(collection_name="documents",
                              points=[models.PointStruct(
                                id=uuid.uuid4(),
                                vector=embedding,
                                payload={"path": f, "page": page.page_number, "line": lineNumber, "text": line}
                              )]
                )
                              
    
    channel.basic_ack(delivery_tag=method.delivery_tag)

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def consume():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
    channel = connection.channel()
    channel.queue_declare(queue='new_documents', durable=True, auto_delete=False)
    
    channel.basic_consume(queue='new_documents', on_message_callback=callback)

    try:
        channel.start_consuming()
    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


consume()