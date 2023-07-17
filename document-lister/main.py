import json
import pika
import os
import redis
from retry import retry
from datetime import datetime
from pathlib import Path

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = os.environ.get('RABBITMQ_PORT', 5672)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', 6379)


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def produce():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
    channel = connection.channel()
    channel.queue_declare(queue='new_documents', durable=True,auto_delete=False)

    try:
        while True:
            
            for p in Path( '/documents' ).glob( '**/*.pdf' ):
                value=r.get(f'/new_document/{p}')
                if value is None:
                    print(f"Found new document: {p}")
                    r.set(f'/new_document/{p}', json.dumps({'path': f'{p}', 'processed':False, 'timestamp': datetime.now().isoformat()}))
                    channel.basic_publish(exchange='', routing_key='new_documents', body=f"{p}", properties=pika.BasicProperties(delivery_mode=2))

            connection.sleep(300)

    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


produce()