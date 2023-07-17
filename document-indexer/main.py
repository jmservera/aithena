import pika
from pika.adapters.blocking_connection import BlockingChannel
import os
import redis
from retry import retry

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = os.environ.get('RABBITMQ_PORT', 5672)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', 6379)

def callback(channel: BlockingChannel, method, properties, body):
    print(f"Received new document: {body}")
    #TODO: Process document
    #channel.basic_ack(delivery_tag=method.delivery_tag)

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