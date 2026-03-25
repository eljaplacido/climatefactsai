"""
Core Infrastructure Module

Provides shared services for the entire application:
- Database connections and sessions
- Messaging (Kafka legacy / Celery new)
- Logging configuration
- Application configuration
- Redis caching
- Compliance checking
"""

from .config import get_config, Config
from .database import get_db, Database
from .logging import get_logger, setup_logging

# Refactor: New imports for Redis/Celery migration
from .celery_config import get_celery_config, get_celery_settings
from .redis_client import get_redis, RedisClient
from .compliance import get_compliance_checker, ComplianceChecker

__all__ = [
    # Existing
    "get_config",
    "Config",
    "get_db",
    "Database",
    "get_logger",
    "setup_logging",
    # Refactor additions
    "get_celery_config",
    "get_celery_settings",
    "get_redis",
    "RedisClient",
    "get_compliance_checker",
    "ComplianceChecker",
]

# Legacy Kafka imports - conditionally loaded during transition
# These will be removed in Phase 6
try:
    from .kafka import get_kafka_client, KafkaClient
    __all__.extend(["get_kafka_client", "KafkaClient"])
except ImportError:
    # Kafka not available - this is expected during refactor
    # Don't fail if kafka-python is not installed
    pass
