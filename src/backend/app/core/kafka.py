"""
Kafka Messaging Module

Wraps shared.kafka_client and provides domain-friendly interface.
"""

from shared.kafka_client import (
    KafkaClient as _KafkaClient,
    KafkaProducerClient,
)
from .config import get_config

__all__ = [
    "get_kafka_client",
    "KafkaClient",
    "KafkaProducerClient",
]


# Type alias for clarity
KafkaClient = _KafkaClient


def get_kafka_client(agent_name: str = "app") -> KafkaClient:
    """
    Get Kafka client instance for dependency injection.
    
    Usage in services:
        kafka = get_kafka_client("content-service")
        kafka.produce(
            topic="article_verified",
            payload={"article_id": 123},
            schema_name="article_verified"
        )
    
    Args:
        agent_name: Name of the service/agent using Kafka
    
    Returns:
        KafkaClient: Configured Kafka client
    """
    return KafkaClient(agent_name=agent_name)

