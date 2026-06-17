"""
Logging Module

Wraps shared.logger and provides domain-friendly interface.
"""

from shared.logger import (
    setup_logging as _setup_logging,
    LoggerMixin,
)
from structlog.stdlib import BoundLogger

__all__ = [
    "get_logger",
    "setup_logging",
    "LoggerMixin",
]


def setup_logging(service_name: str) -> BoundLogger:
    """
    Setup structured logging for a service/module.
    
    Args:
        service_name: Name of the service (e.g., "content-service", "intelligence")
    
    Returns:
        logging.Logger: Configured logger instance
    """
    return _setup_logging(service_name)


def get_logger(name: str) -> BoundLogger:
    """
    Get logger instance for a module.
    
    Usage:
        from app.core import get_logger
        
        logger = get_logger(__name__)
        logger.info("Processing article", article_id=123)
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        logging.Logger: Logger instance
    """
    return _setup_logging(name)

