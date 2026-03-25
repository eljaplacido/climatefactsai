"""
Unit tests for Celery configuration module.

Tests CelerySettings and configuration generation.
"""

import pytest
from unittest.mock import patch
from app.core.celery_config import (
    CelerySettings,
    get_celery_config,
    get_celery_settings,
)


class TestCelerySettings:
    """Test CelerySettings class."""

    def test_default_settings(self):
        """Test default Celery settings."""
        settings = CelerySettings()

        assert settings.broker_url == "redis://localhost:6379/0"
        assert settings.result_backend == "redis://localhost:6379/1"
        assert settings.task_serializer == "json"
        assert settings.worker_concurrency == 4
        assert settings.timezone == "UTC"
        assert settings.enable_utc is True

    def test_queue_names(self):
        """Test queue name configuration."""
        settings = CelerySettings()

        assert settings.queue_ingestion == "ingestion_queue"
        assert settings.queue_processing == "processing_queue"
        assert settings.queue_video == "video_queue"
        assert settings.queue_publication == "publication_queue"

    def test_worker_settings(self):
        """Test worker configuration."""
        settings = CelerySettings()

        assert settings.worker_concurrency == 4
        assert settings.worker_prefetch_multiplier == 4
        assert settings.worker_max_tasks_per_child == 1000
        assert settings.task_acks_late is True
        assert settings.task_reject_on_worker_lost is True

    def test_task_execution_settings(self):
        """Test task execution limits."""
        settings = CelerySettings()

        assert settings.task_time_limit == 3600  # 1 hour
        assert settings.task_soft_time_limit == 3300  # 55 minutes
        assert settings.task_default_rate_limit == "100/m"

    @patch.dict("os.environ", {
        "CELERY_BROKER_URL": "redis://custom-host:6379/0",
        "CELERY_WORKER_CONCURRENCY": "8",
    })
    def test_environment_override(self):
        """Test environment variable override."""
        settings = CelerySettings()

        assert settings.broker_url == "redis://custom-host:6379/0"
        assert settings.worker_concurrency == 8


class TestGetCeleryConfig:
    """Test get_celery_config function."""

    def test_config_dictionary_structure(self):
        """Test that config returns correct dictionary structure."""
        config = get_celery_config()

        # Check required keys
        assert "broker_url" in config
        assert "result_backend" in config
        assert "task_serializer" in config
        assert "timezone" in config
        assert "task_routes" in config

    def test_task_routing(self):
        """Test task routing configuration."""
        config = get_celery_config()

        routes = config["task_routes"]
        assert "app.tasks.ingestion.*" in routes
        assert "app.tasks.processing.*" in routes
        assert "app.tasks.video.*" in routes
        assert "app.tasks.publication.*" in routes

        # Check queue assignments
        assert routes["app.tasks.ingestion.*"]["queue"] == "ingestion_queue"
        assert routes["app.tasks.processing.*"]["queue"] == "processing_queue"

    def test_retry_configuration(self):
        """Test retry settings in config."""
        config = get_celery_config()

        assert config["task_autoretry_for"] == (Exception,)
        assert config["task_retry_kwargs"]["max_retries"] == 3
        assert config["task_retry_backoff"] is True
        assert config["task_retry_backoff_max"] == 300
        assert config["task_retry_jitter"] is True

    def test_monitoring_settings(self):
        """Test monitoring configuration."""
        config = get_celery_config()

        assert config["worker_send_task_events"] is True
        assert config["task_send_sent_event"] is True
        assert config["task_track_started"] is True

    def test_result_backend_settings(self):
        """Test result backend configuration."""
        config = get_celery_config()

        assert config["result_expires"] == 3600
        assert config["result_persistent"] is True


class TestGetCelerySettings:
    """Test get_celery_settings function."""

    def test_returns_settings_instance(self):
        """Test that function returns CelerySettings instance."""
        settings = get_celery_settings()

        assert isinstance(settings, CelerySettings)
        assert hasattr(settings, "broker_url")
        assert hasattr(settings, "worker_concurrency")


@pytest.mark.integration
class TestCeleryConfigIntegration:
    """Integration tests for Celery configuration."""

    def test_config_can_be_used_with_celery(self):
        """Test that config can be used to configure Celery app."""
        from celery import Celery

        config = get_celery_config()
        app = Celery("test")

        # Should not raise any errors
        app.config_from_object(config)

        # Verify configuration applied
        assert app.conf.broker_url == config["broker_url"]
        assert app.conf.task_serializer == config["task_serializer"]
        assert app.conf.timezone == config["timezone"]

    def test_queue_names_valid(self):
        """Test that queue names are valid identifiers."""
        settings = get_celery_settings()

        queues = [
            settings.queue_ingestion,
            settings.queue_processing,
            settings.queue_video,
            settings.queue_publication,
            settings.queue_priority,
        ]

        for queue in queues:
            # Queue names should be alphanumeric with underscores
            assert queue.replace("_", "").isalnum()
            assert len(queue) > 0
