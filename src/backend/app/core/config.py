"""
Application Configuration

Wraps and re-exports shared.config for domain modules.
Follows the principle of explicit dependencies.
"""

from shared.config import (
    get_settings,
    get_kafka_settings,
    get_postgres_settings,
    KafkaSettings,
    PostgresSettings,
    AppSettings,
)

__all__ = [
    "get_settings",
    "get_kafka_settings",
    "get_postgres_settings",
    "KafkaSettings",
    "PostgresSettings",
    "AppSettings",
    "get_config",
    "Config",
]


class Config:
    """
    Unified configuration object for application modules.
    
    Usage:
        config = get_config()
        db_url = config.database.database_url
        kafka_servers = config.kafka.kafka_bootstrap_servers
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.kafka = get_kafka_settings()
        self.database = get_postgres_settings()
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.settings.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return not self.is_production


# Singleton instance
_config_instance: Config | None = None


def get_config() -> Config:
    """
    Get application configuration singleton.
    
    Returns:
        Config: Application configuration object
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance

