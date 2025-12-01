"""
RabbitMQ producer for publishing messages to message queues
Improved with persistent connection and retry logic
"""
import pika
import json
import logging
import time
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Constants
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1


class RabbitMQProducer:
    """Publisher for RabbitMQ messages with persistent connection"""
    
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._declared_queues = set()  # Track declared queues to avoid redeclaring
    
    def _ensure_connection(self):
        """Ensure connection is established and valid"""
        try:
            if self.connection is None or self.connection.is_closed:
                self.connect()
            elif self.channel is None or self.channel.is_closed:
                self.channel = self.connection.channel()
                # Re-declare known queues
                for queue_name in self._declared_queues:
                    try:
                        self.channel.queue_declare(queue=queue_name, durable=True)
                    except Exception:
                        pass  # Queue might already exist
        except Exception as e:
            logger.error(f"Failed to ensure RabbitMQ connection: {str(e)}")
            raise
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                virtual_host=settings.RABBITMQ_VHOST,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise
    
    def declare_queue(self, queue_name: str, durable: bool = True):
        """Declare a queue (idempotent)"""
        try:
            self._ensure_connection()
            if queue_name not in self._declared_queues:
                self.channel.queue_declare(queue=queue_name, durable=durable)
                self._declared_queues.add(queue_name)
        except Exception as e:
            logger.error(f"Failed to declare queue {queue_name}: {str(e)}")
            raise
    
    def publish(self, queue_name: str, message: Dict[str, Any], durable: bool = True, retry: bool = True):
        """
        Publish message to queue with retry logic
        
        Args:
            queue_name: Name of the queue
            message: Message to publish
            durable: Whether the queue is durable
            retry: Whether to retry on failure
            
        Returns:
            bool: True if published successfully, False otherwise
            
        Raises:
            Exception: If all retry attempts fail and retry=False
        """
        last_error = None
        
        for attempt in range(MAX_RETRY_ATTEMPTS if retry else 1):
            try:
                self._ensure_connection()
                self.declare_queue(queue_name, durable)
                
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2 if durable else 1,  # 2 = persistent
                        content_type='application/json'
                    )
                )
                logger.info(f"Message published to queue: {queue_name}, requestId: {message.get('requestId', 'N/A')}")
                return True
                
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to publish message to {queue_name} (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}): {str(e)}")
                
                # Close connection to force reconnect on next attempt
                try:
                    if self.connection and not self.connection.is_closed:
                        self.connection.close()
                    self.connection = None
                    self.channel = None
                except Exception:
                    pass
                
                # Wait before retry (exponential backoff)
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
        
        # All retries failed
        error_msg = f"Failed to publish message to {queue_name} after {MAX_RETRY_ATTEMPTS} attempts"
        logger.error(f"{error_msg}: {str(last_error)}")
        
        if not retry:
            raise last_error
        
        return False
    
    def close(self):
        """Close connection (call on application shutdown)"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
            self.connection = None
            self.channel = None
            self._declared_queues.clear()
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {str(e)}")


# Global RabbitMQ producer instance
rabbitmq_producer = RabbitMQProducer()


async def get_rabbitmq_producer() -> RabbitMQProducer:
    """Dependency for RabbitMQ producer"""
    return rabbitmq_producer


def publish_message_safe(queue_name: str, message: dict, retry: bool = True) -> bool:
    """
    Helper function to publish messages safely without managing connection lifecycle.
    Connection is persistent and managed automatically.
    
    Args:
        queue_name: Name of the queue
        message: Message dictionary to publish
        retry: Whether to retry on failure
        
    Returns:
        bool: True if published successfully, False otherwise
    """
    try:
        return rabbitmq_producer.publish(queue_name, message, durable=True, retry=retry)
    except Exception as e:
        logger.error(f"Failed to publish message to {queue_name}: {str(e)}")
        return False


async def send_email_notification(
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
    request_id: str = None
) -> bool:
    """
    Publica una notificación de correo electrónico en la cola de RabbitMQ.
    
    Args:
        to_email: Correo electrónico del destinatario
        subject: Asunto del correo
        template_name: Nombre de la plantilla a utilizar
        context: Diccionario con las variables para la plantilla
        request_id: ID opcional para seguimiento
        
    Returns:
        bool: True si el mensaje se publicó correctamente, False en caso contrario
    """
    from datetime import datetime
    import uuid
    
    message = {
        "requestId": request_id or str(uuid.uuid4()),
        "to": to_email,
        "subject": subject,
        "template": template_name,
        "context": context,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return publish_message_safe("email.notifications", message, retry=True)