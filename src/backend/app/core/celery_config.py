"""
Celery Configuration Module

Provides Celery settings and configuration for the modular monolith.
Replaces Kafka message queuing with Redis/Celery task queue.
"""

from typing import Dict, Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class CelerySettings(BaseSettings):
    """Celery configuration settings loaded from environment variables.

    This configuration replaces the Kafka-based message queue with Redis/Celery
    for asynchronous task processing in the modular monolith architecture.

    Environment variables are read with the ``CELERY_`` prefix, so the field
    ``broker_url`` maps to the env var ``CELERY_BROKER_URL``.
    """

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # Broker and backend
    broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery message broker",
    )
    result_backend: str = Field(
        default="redis://localhost:6379/1",
        description="Redis URL for Celery result storage",
    )

    # Serialization
    task_serializer: str = Field(default="json")
    result_serializer: str = Field(default="json")
    accept_content: List[str] = Field(default=["json"])

    # Timezone
    timezone: str = Field(default="UTC")
    enable_utc: bool = Field(default=True)

    # Worker settings
    worker_concurrency: int = Field(
        default=4,
        description="Number of concurrent worker processes",
    )
    worker_prefetch_multiplier: int = Field(
        default=4,
        description="Number of tasks to prefetch per worker",
    )
    worker_max_tasks_per_child: int = Field(
        default=1000,
        description="Max tasks before worker restarts (memory leak prevention)",
    )

    # Task execution
    task_acks_late: bool = Field(
        default=True,
        description="Acknowledge task after execution (not on receipt)",
    )
    task_reject_on_worker_lost: bool = Field(
        default=True,
        description="Requeue task if worker crashes",
    )
    task_time_limit: int = Field(
        default=3600,
        description="Hard time limit in seconds (1 hour)",
    )
    task_soft_time_limit: int = Field(
        default=3300,
        description="Soft time limit in seconds (55 minutes)",
    )
    task_default_rate_limit: str = Field(
        default="100/m",
        description="Default rate limit (100 tasks per minute)",
    )

    # Queue names
    queue_ingestion: str = Field(default="ingestion_queue")
    queue_processing: str = Field(default="processing_queue")
    queue_video: str = Field(default="video_queue")
    queue_publication: str = Field(default="publication_queue")
    queue_priority: str = Field(default="priority_queue")
    queue_scheduled_ingestion: str = Field(default="scheduled_ingestion_queue")

    # Monitoring
    send_task_events: bool = Field(
        default=True,
        description="Send task events for monitoring (Flower, etc.)",
    )
    send_task_sent_event: bool = Field(default=True, description="Send task-sent events")
    track_started: bool = Field(default=True, description="Track when tasks start")


def get_celery_config() -> Dict[str, Any]:
    """Get Celery configuration as a dictionary.

    Returns:
        Dictionary of Celery configuration settings suitable for Celery app config.

    Example:
        >>> config = get_celery_config()
        >>> app = Celery("climatenews")
        >>> app.config_from_object(config)
    """
    settings = CelerySettings()

    return {
        # Broker and backend
        "broker_url": settings.broker_url,
        "result_backend": settings.result_backend,

        # Serialization
        "task_serializer": settings.task_serializer,
        "result_serializer": settings.result_serializer,
        "accept_content": settings.accept_content,

        # Timezone
        "timezone": settings.timezone,
        "enable_utc": settings.enable_utc,

        # Worker settings
        "worker_concurrency": settings.worker_concurrency,
        "worker_prefetch_multiplier": settings.worker_prefetch_multiplier,
        "worker_max_tasks_per_child": settings.worker_max_tasks_per_child,

        # Task execution
        "task_acks_late": settings.task_acks_late,
        "task_reject_on_worker_lost": settings.task_reject_on_worker_lost,
        "task_time_limit": settings.task_time_limit,
        "task_soft_time_limit": settings.task_soft_time_limit,
        "task_default_rate_limit": settings.task_default_rate_limit,

        # Task routing
        "task_routes": {
            "app.tasks.ingestion.scheduled_multi_country_ingestion": {"queue": settings.queue_scheduled_ingestion},
            "app.tasks.ingestion.*": {"queue": settings.queue_ingestion},
            "app.tasks.processing.*": {"queue": settings.queue_processing},
            "app.tasks.video.*": {"queue": settings.queue_video},
            "app.tasks.publication.*": {"queue": settings.queue_publication},
        },

        # Default queue
        "task_default_queue": settings.queue_processing,
        "task_default_exchange": "climatenews",
        "task_default_routing_key": "default",

        # Monitoring
        "worker_send_task_events": settings.send_task_events,
        "task_send_sent_event": settings.send_task_sent_event,
        "task_track_started": settings.track_started,

        # Result backend settings
        "result_expires": 3600,  # Results expire after 1 hour
        "result_persistent": True,  # Persist results to disk

        # Error handling
        "task_reject_on_worker_lost": True,
        "task_acks_late": True,

        # Retry settings
        "task_autoretry_for": (Exception,),
        "task_retry_kwargs": {"max_retries": 3},
        "task_retry_backoff": True,
        "task_retry_backoff_max": 300,  # Max 5 minutes
        "task_retry_jitter": True,
    }


def get_celery_settings() -> CelerySettings:
    """Get Celery settings instance.

    Returns:
        CelerySettings instance loaded from environment variables.
    """
    return CelerySettings()
