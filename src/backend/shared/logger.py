"""Centralized structured logging for all agents with OpenTelemetry integration.

This module provides structured JSON logging using structlog for consistent,
queryable logs across all microservices. All agents use LoggerMixin to access
structured logging with automatic context enrichment.

Features:
    - Structured JSON logging (or human-readable text format)
    - Automatic context injection (agent_name, environment, service_name)
    - Task-specific context binding (task_id, phase, metrics)
    - Specialized logging methods for API calls, agent handoffs, LLM interactions
    - OpenTelemetry integration for distributed tracing
    - Configurable log levels and formats via environment

Architecture:
    - setup_logging(): Initializes structlog with agent context
    - LoggerMixin: Mixin class for easy logger integration in agent classes
    - bind_task_context(): Adds task-specific context to logger
    - Automatic timestamp, log level, and exception info

Log Formats:
    **JSON (Production):**
    ```json
    {
      "timestamp": "2025-11-20T10:30:45.123Z",
      "level": "info",
      "agent_name": "ingestion_agent",
      "environment": "production",
      "task_id": "task-123",
      "message": "Articles discovered",
      "article_count": 15
    }
    ```

    **Text (Development):**
    ```
    2025-11-20 10:30:45 [INFO] ingestion_agent: Articles discovered article_count=15 task_id=task-123
    ```

Usage:
    >>> from shared.logger import setup_logging, bind_task_context
    >>>
    >>> # Basic setup
    >>> logger = setup_logging("my_agent")
    >>> logger.info("Processing started", key="value")
    >>>
    >>> # With task context
    >>> task_logger = bind_task_context(logger, task_id="task-123", phase="ingestion")
    >>> task_logger.info("Task progress", progress=50)

Example:
    Agent using LoggerMixin for structured logging:

    ```python
    from shared.logger import LoggerMixin

    class IngestionAgent(LoggerMixin):
        def __init__(self):
            self.setup_logger("ingestion_agent")
            self.logger.info("Agent initialized")

        def process_task(self, task_id: str):
            # Bind task context for all subsequent logs
            self.logger = bind_task_context(self.logger, task_id=task_id)

            self.logger.info("Starting task processing")

            # Log API call
            self.log_api_call(
                api_name="Perplexity",
                endpoint="/v1/search",
                method="POST",
                status_code=200,
                duration_ms=1234.5
            )

            # Log LLM interaction with cost tracking
            self.log_llm_interaction(
                model="claude-3-5-sonnet",
                prompt_tokens=1500,
                completion_tokens=800,
                total_cost_usd=0.045,
                duration_ms=3500
            )

            # Log agent handoff
            self.log_agent_handoff(
                from_agent="ingestion_agent",
                to_agent="verification_agent",
                task_id=task_id,
                payload_schema_version="1.0"
            )

            # Error handling
            try:
                # ... processing ...
                pass
            except Exception as e:
                self.log_error(e, context={"task_id": task_id, "phase": "discovery"})
    ```

Configuration:
    Set via environment variables or .env file:
    ```bash
    LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT=json             # json or text
    OTEL_SERVICE_NAME=climatenews-mas
    ENVIRONMENT=production      # development, staging, production
    ```

Note:
    All logs automatically include timestamp, log level, agent name, environment,
    and service name. Use bind() or bind_task_context() to add custom context
    that persists across multiple log calls.
"""

import logging
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import BoundLogger
from pythonjsonlogger import jsonlogger

from .config import get_settings
from . import request_context
from . import telemetry


def _add_observability_context(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    request_id = request_context.get_request_id()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id

    task_id = request_context.get_task_id()
    if task_id and "task_id" not in event_dict:
        event_dict["task_id"] = task_id

    user_id = request_context.get_user_id()
    if user_id and "user_id" not in event_dict:
        event_dict["user_id"] = user_id

    trace_id, span_id = telemetry.get_trace_ids()
    if trace_id and "trace_id" not in event_dict:
        event_dict["trace_id"] = trace_id
    if span_id and "span_id" not in event_dict:
        event_dict["span_id"] = span_id

    return event_dict


def setup_logging(
    agent_name: str,
    log_level: Optional[str] = None,
    log_format: Optional[str] = None
) -> BoundLogger:
    """Initialize structured logging for an agent with automatic context injection.

    Creates a structlog logger configured with JSON or text formatting,
    timestamp injection, exception handling, and agent/environment context.

    Args:
        agent_name: Name of the agent (e.g., "orchestrator", "ingestion_agent")
        log_level: Log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to LOG_LEVEL from environment.
        log_format: Format override ("json" or "text").
                    Defaults to LOG_FORMAT from environment.

    Returns:
        BoundLogger: Configured logger with agent_name, environment, and
                     service_name automatically bound to all log messages.

    Example:
        >>> logger = setup_logging("ingestion_agent", log_level="DEBUG")
        >>> logger.info("Processing started", task_id="task-123", article_count=15)
        # Output (JSON):
        # {"timestamp": "2025-11-20T10:30:45Z", "level": "info",
        #  "agent_name": "ingestion_agent", "message": "Processing started",
        #  "task_id": "task-123", "article_count": 15}

    Note:
        Logger is cached by structlog after first use. Multiple calls with the
        same agent_name return the same logger instance.
    """
    settings = get_settings()
    
    # Käytä konfiguraatiosta tai parametreista
    log_level = log_level or settings.observability.log_level
    log_format = log_format or settings.observability.log_format
    
    # Aseta Python-loggaustaso
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # Structlog-prosessorit
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_observability_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Lisää agent_name ja environment jokaiseen lokimerkintään
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Valitse formaatti
    if log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Aseta formatter root loggerille
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    if logging.root.handlers:
        for existing_handler in logging.root.handlers:
            existing_handler.setFormatter(formatter)
    else:
        logging.root.handlers = [handler]
    
    # Luo ja palauta logger agentti-spesifisillä konteksteilla
    logger = structlog.get_logger(agent_name)
    logger = logger.bind(
        agent_name=agent_name,
        environment=settings.environment,
        service_name=settings.observability.otel_service_name
    )
    
    return logger


def bind_task_context(logger: BoundLogger, task_id: str, **kwargs) -> BoundLogger:
    """Bind task-specific context to logger for persistent context.

    Creates new logger with task_id and custom context attached to all
    subsequent log calls. Useful for tracking logs across task lifecycle.

    Args:
        logger: Structured logger instance from setup_logging()
        task_id: Unique task identifier
        **kwargs: Additional context variables (phase, agent, metrics, etc.)

    Returns:
        New logger instance with bound context

    Example:
        >>> logger = setup_logging("orchestrator")
        >>> task_logger = bind_task_context(
        ...     logger,
        ...     task_id="task-123",
        ...     phase="ingestion",
        ...     country="FI"
        ... )
        >>> task_logger.info("Processing started")
        >>> # Output includes: task_id=task-123, phase=ingestion, country=FI
    """
    return logger.bind(task_id=task_id, **kwargs)


class LoggerMixin:
    """Mixin class providing structured logging capabilities to agent classes.

    This mixin adds a logger attribute and specialized logging methods for
    common operations like API calls, agent handoffs, and LLM interactions.
    All agents should inherit from this class for consistent logging.

    Features:
        - Automatic logger initialization with agent context
        - Structured error logging with tracebacks
        - Specialized methods for API calls, LLM interactions, agent handoffs
        - Cost tracking for LLM usage
        - Custom context binding via bind()

    Attributes:
        logger (BoundLogger): Structured logger instance with agent context

    Usage:
        >>> class IngestionAgent(LoggerMixin):
        ...     def __init__(self):
        ...         self.setup_logger("ingestion_agent")
        ...         self.logger.info("Agent initialized")
        ...
        ...     def process(self, task_id: str):
        ...         self.logger.info("Processing task", task_id=task_id, phase="discovery")

    Example:
        Full agent implementation with logging:

        ```python
        from shared.logger import LoggerMixin
        from shared.database import get_redis

        class VerificationAgent(LoggerMixin):
            def __init__(self):
                # Initialize logger with agent name
                self.setup_logger("verification_agent", version="2.0")
                self.redis = get_redis()
                self.logger.info("Verification agent ready")

            def verify_articles(self, task_id: str, articles: List[Dict]):
                # Bind task context to all subsequent logs
                self.logger = self.logger.bind(
                    task_id=task_id,
                    article_count=len(articles)
                )

                self.logger.info("Starting verification")

                for article in articles:
                    try:
                        # Log API call to fact-checking service
                        start_time = time.time()
                        result = self.check_facts(article)
                        duration_ms = (time.time() - start_time) * 1000

                        self.log_api_call(
                            api_name="ClimateCheck",
                            endpoint="/v1/verify",
                            method="POST",
                            status_code=200,
                            duration_ms=duration_ms
                        )

                        # Log successful verification
                        self.logger.info(
                            "Article verified",
                            article_id=article["id"],
                            credibility_score=result["score"]
                        )

                    except Exception as e:
                        # Log error with context
                        self.log_error(
                            e,
                            context={
                                "article_id": article.get("id"),
                                "source": article.get("source")
                            }
                        )

                self.logger.info("Verification completed", task_id=task_id)
        ```

    Note:
        Call setup_logger() in __init__() to initialize the logger.
        Use self.logger.bind() to add persistent context to all subsequent logs.
    """
    
    logger: BoundLogger
    
    def setup_logger(self, agent_name: str, **bind_kwargs):
        """Initialize structured logger for this agent.

        Args:
            agent_name: Name of the agent (e.g., "ingestion_agent", "orchestrator")
            **bind_kwargs: Additional context to bind to all logs from this logger

        Example:
            >>> self.setup_logger("verification_agent", version="2.0", region="EU")
        """
        self.logger = setup_logging(agent_name)
        if bind_kwargs:
            self.logger = self.logger.bind(**bind_kwargs)
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Log error with structured data and automatic traceback.

        Args:
            error: Exception instance to log
            context: Additional context dict (task_id, article_id, etc.)

        Example:
            >>> try:
            ...     process_article(article)
            ... except Exception as e:
            ...     self.log_error(e, context={"task_id": task_id, "article_id": article["id"]})
        """
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_traceback": True  # structlog adds full traceback automatically
        }

        if context:
            error_data.update(context)

        self.logger.error("Error occurred", **error_data, exc_info=True)
    
    def log_api_call(
        self,
        api_name: str,
        endpoint: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """Log external API call with timing and status information.

        Structured logging for all external API interactions (ClimateCheck,
        OpenAI, NASA, etc.) with automatic duration tracking and status codes.

        Args:
            api_name: API service name (e.g., "ClimateCheck", "OpenAI", "Perplexity")
            endpoint: API endpoint path (e.g., "/v1/verify", "/chat/completions")
            method: HTTP method (default: "GET")
            status_code: HTTP response status code
            duration_ms: Request duration in milliseconds
            **kwargs: Additional context (request_id, payload_size, etc.)

        Example:
            >>> import time
            >>> start = time.time()
            >>> response = requests.post("https://api.example.com/v1/verify", ...)
            >>> duration_ms = (time.time() - start) * 1000
            >>> self.log_api_call(
            ...     api_name="ClimateCheck",
            ...     endpoint="/v1/verify",
            ...     method="POST",
            ...     status_code=200,
            ...     duration_ms=duration_ms,
            ...     claims_verified=5
            ... )
        """
        self.logger.info(
            "API call",
            api_name=api_name,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_agent_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task_id: str,
        payload_schema_version: str,
        **kwargs
    ):
        """Log inter-agent communication handoff for workflow tracking.

        Records when one agent passes work to another via Kafka messages.
        Essential for understanding workflow progression in multi-agent system.

        Args:
            from_agent: Source agent name (e.g., "ingestion_agent")
            to_agent: Destination agent name (e.g., "verification_agent")
            task_id: Unique task identifier for correlation
            payload_schema_version: Message schema version (e.g., "1.0")
            **kwargs: Additional context (article_count, topic, etc.)

        Example:
            >>> self.log_agent_handoff(
            ...     from_agent="ingestion_agent",
            ...     to_agent="verification_agent",
            ...     task_id="task-123",
            ...     payload_schema_version="1.0",
            ...     article_count=15,
            ...     topic="fact_checking_queue"
            ... )
        """
        self.logger.info(
            "Agent handoff",
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id,
            schema_version=payload_schema_version,
            **kwargs
        )
    
    def log_llm_interaction(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: float,
        duration_ms: float,
        **kwargs
    ):
        """Log LLM API interaction with token usage and cost tracking.

        Critical for monitoring AI costs and usage patterns. Automatically
        calculates total tokens and rounds costs for consistent reporting.

        Args:
            model: LLM model identifier (e.g., "claude-3-5-sonnet", "gpt-4o")
            prompt_tokens: Input token count
            completion_tokens: Output/completion token count
            total_cost_usd: Total API call cost in USD
            duration_ms: Request duration in milliseconds
            **kwargs: Additional context (operation, task_id, etc.)

        Example:
            >>> self.log_llm_interaction(
            ...     model="claude-3-5-sonnet-20241022",
            ...     prompt_tokens=1500,
            ...     completion_tokens=800,
            ...     total_cost_usd=0.0435,
            ...     duration_ms=3500,
            ...     operation="fact_check_generation",
            ...     task_id="task-123"
            ... )
        """
        self.logger.info(
            "LLM interaction",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            total_cost_usd=round(total_cost_usd, 6),
            duration_ms=duration_ms,
            **kwargs
        )


# Globaali logger sovellustason tapahtumille
app_logger = setup_logging("app")


if __name__ == "__main__":
    # Testaa logging
    test_logger = setup_logging("test_agent")
    
    test_logger.info("Test info message", key="value")
    test_logger.warning("Test warning", metric=123)
    
    try:
        raise ValueError("Test error")
    except Exception as e:
        test_logger.error("Caught exception", exc_info=True)

