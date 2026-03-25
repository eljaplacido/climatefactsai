"""Centralized configuration management for all agents.

This module provides a hierarchical configuration system using Pydantic Settings
for environment variable management. All services use get_settings() to access
configuration, ensuring consistency across the platform.

Architecture:
    - LLMSettings: AI model API keys and pricing
    - ClimateDataSettings: Climate data API configurations
    - KafkaSettings: Event bus configuration
    - RedisSettings: Short-term memory (caching, state)
    - PostgresSettings: Long-term storage
    - VectorDBSettings: pgvector semantic search
    - ScraperSettings: Web scraping configuration
    - WorkflowSettings: Orchestration parameters
    - LocationSettings: Geographic filtering
    - QASettings: Quality assurance thresholds
    - ObservabilitySettings: Logging and tracing

Usage:
    >>> from shared.config import get_settings
    >>> settings = get_settings()
    >>> anthropic_key = settings.llm.anthropic_api_key
    >>> kafka_url = settings.kafka.kafka_bootstrap_servers

Example:
    Configure service with settings:

    ```python
    class MyService:
        def __init__(self):
            self.settings = get_settings()
            self.kafka = KafkaClient(
                bootstrap_servers=self.settings.kafka.kafka_bootstrap_servers
            )
    ```

Note:
    Settings are cached via @lru_cache() - same instance returned on each call.
    Environment variables loaded from .env, ../.env, or ../../.env files.
"""

from functools import lru_cache
from typing import Optional, List
from urllib.parse import urlparse, unquote
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM API configurations for multi-model AI operations.

    Manages API keys, model selection, and pricing for Claude, GPT-4, and Perplexity.
    All LLM-based agents use these settings for AI model access and cost tracking.

    Attributes:
        anthropic_api_key: API key for Anthropic Claude models
        openai_api_key: API key for OpenAI GPT models
        perplexity_api_key: API key for Perplexity search models
        claude_model: Claude model identifier (default: claude-3-5-sonnet-20241022)
        gpt_model: GPT model identifier (default: gpt-4o)
        perplexity_model: Perplexity model identifier
        claude_input_price_per_1k: Claude input token price per 1000 tokens (USD)
        claude_output_price_per_1k: Claude output token price per 1000 tokens (USD)
        gpt4o_input_price_per_1k: GPT-4 input token price per 1000 tokens (USD)
        gpt4o_output_price_per_1k: GPT-4 output token price per 1000 tokens (USD)

    Example:
        >>> settings = get_settings()
        >>> llm_settings = settings.llm
        >>> print(llm_settings.claude_model)
        'claude-3-5-sonnet-20241022'
    """
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env", "../../.env"],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    perplexity_api_key: Optional[str] = Field(default=None, env="PERPLEXITY_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")

    claude_model: str = Field(default="claude-3-5-sonnet-20240620", env="CLAUDE_MODEL")
    gpt_model: str = Field(default="gpt-4o", env="GPT_MODEL")
    perplexity_model: str = Field(default="llama-3.1-sonar-large-128k-online", env="PERPLEXITY_MODEL")
    deepseek_model: str = Field(default="deepseek-chat", env="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", env="DEEPSEEK_BASE_URL")
    
    # Token-hinnat (per 1K tokens)
    claude_input_price_per_1k: float = Field(default=0.003, env="CLAUDE_INPUT_PRICE_PER_1K")
    claude_output_price_per_1k: float = Field(default=0.015, env="CLAUDE_OUTPUT_PRICE_PER_1K")
    gpt4o_input_price_per_1k: float = Field(default=0.005, env="GPT4O_INPUT_PRICE_PER_1K")
    gpt4o_output_price_per_1k: float = Field(default=0.015, env="GPT4O_OUTPUT_PRICE_PER_1K")


class ClimateDataSettings(BaseSettings):
    """Climate data API configurations for external data sources.

    Manages API access to ClimateCheck, NOAA, and NASA climate data services.
    Used by verification agents for fact-checking climate-related claims.

    Attributes:
        climatecheck_api_key: API key for ClimateCheck service
        climatecheck_api_url: Base URL for ClimateCheck API
        noaa_api_token: API token for NOAA Climate Data Online
        noaa_api_url: Base URL for NOAA API
        nasa_api_key: API key for NASA climate data services
        nasa_api_url: Base URL for NASA APIs

    Example:
        >>> settings = get_settings()
        >>> climate_settings = settings.climate_data
        >>> print(climate_settings.climatecheck_api_url)
        'https://api.climatecheck.com/v1'
    """
    climatecheck_api_key: Optional[str] = Field(default=None, env="CLIMATECHECK_API_KEY")
    climatecheck_api_url: str = Field(
        default="https://api.climatecheck.com/v1", 
        env="CLIMATECHECK_API_URL"
    )
    
    noaa_api_token: Optional[str] = Field(default=None, env="NOAA_API_TOKEN")
    noaa_api_url: str = Field(
        default="https://www.ncdc.noaa.gov/cdo-web/api/v2",
        env="NOAA_API_URL"
    )
    
    nasa_api_key: Optional[str] = Field(default=None, env="NASA_API_KEY")
    nasa_api_url: str = Field(
        default="https://api.nasa.gov",
        env="NASA_API_URL"
    )

    # Evidence retrieval
    evidence_retrieval_timeout_seconds: int = Field(default=30, env="EVIDENCE_RETRIEVAL_TIMEOUT_SECONDS")

    # Open-Meteo (no auth required)
    open_meteo_api_url: str = Field(
        default="https://api.open-meteo.com/v1",
        env="OPEN_METEO_API_URL",
    )

    # Copernicus Climate Data Store
    copernicus_cds_api_key: Optional[str] = Field(default=None, env="COPERNICUS_CDS_API_KEY")

    # European RSS data sources
    carbon_brief_rss_url: str = Field(
        default="https://www.carbonbrief.org/feed/",
        env="CARBON_BRIEF_RSS_URL",
    )
    eea_rss_url: str = Field(
        default="https://www.eea.europa.eu/api/rss",
        env="EEA_RSS_URL",
    )


class KafkaSettings(BaseSettings):
    """Kafka event bus configurations for multi-agent messaging.

    Defines Kafka broker connections, schema registry, and all topic names
    for inter-agent communication. All microservices use these settings
    for reliable message-based coordination.

    Attributes:
        kafka_bootstrap_servers: Kafka broker addresses (comma-separated)
        kafka_schema_registry_url: Schema registry URL for message validation
        kafka_consumer_group_prefix: Consumer group name prefix
        kafka_topic_discovery_queue: Topic for article discovery messages
        kafka_topic_factcheck_queue: Topic for fact-checking workflow
        kafka_topic_creation_queue: Topic for content creation
        kafka_topic_content_creation_queue: Alias for content creation queue
        kafka_topic_video_queue: Topic for video generation
        kafka_topic_publication_queue: Topic for publication events
        kafka_topic_orchestrator_commands: Topic for orchestrator commands
        kafka_topic_orchestrator_responses: Topic for agent responses
        kafka_topic_workflow_events: Topic for workflow state changes

    Example:
        >>> settings = get_settings()
        >>> kafka = settings.kafka
        >>> print(kafka.kafka_bootstrap_servers)
        'localhost:5092'
    """
    kafka_bootstrap_servers: str = Field(
        default="localhost:5092",  # Updated port to avoid conflicts
        env="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_schema_registry_url: str = Field(
        default="http://localhost:5081",  # Updated port to avoid conflicts
        env="KAFKA_SCHEMA_REGISTRY_URL"
    )
    kafka_consumer_group_prefix: str = Field(
        default="climatenews",
        env="KAFKA_CONSUMER_GROUP_PREFIX"
    )
    
    # Kafka-aiheet (topics)
    kafka_topic_discovery_queue: str = Field(
        default="discovery_queue",
        env="KAFKA_TOPIC_DISCOVERY_QUEUE"
    )
    kafka_topic_factcheck_queue: str = Field(
        default="fact_checking_queue",
        env="KAFKA_TOPIC_FACTCHECK_QUEUE"
    )
    kafka_topic_creation_queue: str = Field(
        default="content_creation_queue",
        env="KAFKA_TOPIC_CREATION_QUEUE"
    )
    kafka_topic_content_creation_queue: str = Field(
        default="content_creation_queue",
        env="KAFKA_TOPIC_CONTENT_CREATION_QUEUE"
    )
    kafka_topic_video_queue: str = Field(
        default="video_queue",
        env="KAFKA_TOPIC_VIDEO_QUEUE"
    )
    kafka_topic_publication_queue: str = Field(
        default="publication_queue",
        env="KAFKA_TOPIC_PUBLICATION_QUEUE"
    )
    kafka_topic_orchestrator_commands: str = Field(
        default="orchestrator_commands",
        env="KAFKA_TOPIC_ORCHESTRATOR_COMMANDS"
    )
    kafka_topic_orchestrator_responses: str = Field(
        default="orchestrator_responses",
        env="KAFKA_TOPIC_ORCHESTRATOR_RESPONSES"
    )
    kafka_topic_workflow_events: str = Field(
        default="workflow_events",
        env="KAFKA_TOPIC_WORKFLOW_EVENTS"
    )


class RedisSettings(BaseSettings):
    """Redis short-term memory configurations for ephemeral state.

    Manages Redis connection settings for task state, caching, and rate limiting.
    All agents use Redis for hot data with automatic expiration (24h default TTL).

    Attributes:
        redis_host: Redis server hostname
        redis_port: Redis server port (default: 5379)
        redis_password: Redis authentication password (optional)
        redis_db: Redis database number (default: 0)
        redis_ttl_seconds: Default time-to-live for keys (default: 86400 = 24h)

    Example:
        >>> settings = get_settings()
        >>> redis = settings.redis
        >>> print(f"{redis.redis_host}:{redis.redis_port}")
        'localhost:5379'
    """
    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=5379, env="REDIS_PORT")  # Updated port to avoid conflicts
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_ttl_seconds: int = Field(default=86400, env="REDIS_TTL_SECONDS")  # 24h

    def resolved_connection(self) -> dict:
        """Resolve Redis connection fields, optionally from REDIS_URL."""
        if not self.redis_url:
            return {
                "host": self.redis_host,
                "port": self.redis_port,
                "password": self.redis_password,
                "db": self.redis_db,
            }

        parsed = urlparse(self.redis_url)
        host = parsed.hostname or self.redis_host
        port = parsed.port or 6379
        db = self.redis_db
        if parsed.path and parsed.path != "/":
            try:
                db = int(parsed.path.lstrip("/"))
            except ValueError:
                db = self.redis_db

        password = self.redis_password
        if parsed.password is not None:
            password = unquote(parsed.password)

        return {"host": host, "port": port, "password": password, "db": db}


class PostgresSettings(BaseSettings):
    """PostgreSQL long-term storage configurations for persistent data.

    Manages PostgreSQL connection settings, connection pooling, and database
    credentials. All agents use PostgreSQL for cold data with permanent storage.

    Attributes:
        postgres_host: PostgreSQL server hostname
        postgres_port: PostgreSQL server port (default: 5433)
        postgres_db: Database name (default: climatenews)
        postgres_user: Database username (default: postgres)
        postgres_password: Database password
        postgres_pool_min_size: Minimum connection pool size (default: 5)
        postgres_pool_max_size: Maximum connection pool size (default: 20)

    Example:
        >>> settings = get_settings()
        >>> pg = settings.postgres
        >>> print(pg.database_url)
        'postgresql://postgres:***@localhost:5433/climatenews'
    """
    database_url_override: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, env="POSTGRES_PORT")
    postgres_db: str = Field(default="climatenews", env="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", env="POSTGRES_USER")
    postgres_password: str = Field(default="", env="POSTGRES_PASSWORD")
    
    postgres_pool_min_size: int = Field(default=5, env="POSTGRES_POOL_MIN_SIZE")
    postgres_pool_max_size: int = Field(default=20, env="POSTGRES_POOL_MAX_SIZE")
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL connection URL.

        Returns:
            SQLAlchemy-compatible connection string

        Example:
            >>> settings = get_postgres_settings()
            >>> engine = create_engine(settings.database_url)
        """
        if self.database_url_override:
            return self.database_url_override.strip()
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class VectorDBSettings(BaseSettings):
    """Vector database configurations for semantic search with pgvector.

    Manages vector database settings for storing and querying article embeddings.
    Primary backend is PostgreSQL with pgvector extension for semantic similarity search.

    Attributes:
        vector_db_type: Vector database type (default: "pgvector")
        vector_db_dimension: Embedding vector dimension (default: 1536 for OpenAI)
        vector_db_index_type: Index type for vector search (default: "ivfflat")
        pinecone_api_key: API key for Pinecone (optional, alternative backend)
        pinecone_environment: Pinecone environment name (optional)
        pinecone_index_name: Pinecone index name (optional)

    Example:
        >>> settings = get_settings()
        >>> vector_settings = settings.vector_db
        >>> print(vector_settings.vector_db_type)
        'pgvector'
    """
    vector_db_type: str = Field(default="pgvector", env="VECTOR_DB_TYPE")
    vector_db_dimension: int = Field(default=1536, env="VECTOR_DB_DIMENSION")
    vector_db_index_type: str = Field(default="ivfflat", env="VECTOR_DB_INDEX_TYPE")

    # Pinecone-asetukset (jos käytetään)
    pinecone_api_key: Optional[str] = Field(default=None, env="PINECONE_API_KEY")
    pinecone_environment: Optional[str] = Field(default=None, env="PINECONE_ENVIRONMENT")
    pinecone_index_name: Optional[str] = Field(default=None, env="PINECONE_INDEX_NAME")


class ScraperSettings(BaseSettings):
    """Web scraping configurations for ethical and compliant data collection.

    Manages web scraping behavior including rate limiting, robots.txt compliance,
    user agent identification, and browser automation settings via Playwright.

    Attributes:
        scraper_user_agent: User-Agent string for HTTP requests
        scraper_rate_limit_delay: Delay between requests in seconds (default: 2.0)
        scraper_respect_robots_txt: Whether to respect robots.txt directives
        scraper_max_concurrent_requests: Maximum concurrent scraping requests
        playwright_browser: Browser type for Playwright (chromium/firefox/webkit)
        playwright_headless: Run browser in headless mode (default: True)

    Example:
        >>> settings = get_settings()
        >>> scraper = settings.scraper
        >>> print(scraper.scraper_rate_limit_delay)
        2.0
    """
    scraper_user_agent: str = Field(
        default="ClimateNewsBot/1.0 (+https://climatenews.com/bot)",
        env="SCRAPER_USER_AGENT"
    )
    scraper_rate_limit_delay: float = Field(default=2.0, env="SCRAPER_RATE_LIMIT_DELAY")
    scraper_respect_robots_txt: bool = Field(default=True, env="SCRAPER_RESPECT_ROBOTS_TXT")
    scraper_max_concurrent_requests: int = Field(
        default=10,
        env="SCRAPER_MAX_CONCURRENT_REQUESTS"
    )

    playwright_browser: str = Field(default="chromium", env="PLAYWRIGHT_BROWSER")
    playwright_headless: bool = Field(default=True, env="PLAYWRIGHT_HEADLESS")


class WorkflowSettings(BaseSettings):
    """Workflow orchestration configurations for multi-agent pipeline.

    Controls timing, timeouts, and thresholds for the automated content workflow
    including article discovery, fact-checking, content creation, and video generation.

    Attributes:
        workflow_trigger_time: Daily workflow trigger time in HH:MM format
        workflow_discovery_timeout: Discovery agent timeout in seconds (default: 7200)
        workflow_factcheck_timeout: Fact-checking timeout in seconds (default: 7200)
        workflow_creation_timeout: Content creation timeout in seconds (default: 3600)
        workflow_video_timeout: Video generation timeout in seconds (default: 1800)
        workflow_hitl_timeout: Human-in-the-loop review timeout in seconds (default: 3600)
        workflow_min_articles_for_summary: Minimum articles required for summary
        workflow_max_articles_per_summary: Maximum articles per summary generation

    Example:
        >>> settings = get_settings()
        >>> workflow = settings.workflow
        >>> print(f"Trigger time: {workflow.workflow_trigger_time}")
        Trigger time: 01:00
    """
    workflow_trigger_time: str = Field(default="01:00", env="WORKFLOW_TRIGGER_TIME")

    # Aikakatkaisut (sekunteina)
    workflow_discovery_timeout: int = Field(default=7200, env="WORKFLOW_DISCOVERY_TIMEOUT")
    workflow_factcheck_timeout: int = Field(default=7200, env="WORKFLOW_FACTCHECK_TIMEOUT")
    workflow_creation_timeout: int = Field(default=3600, env="WORKFLOW_CREATION_TIMEOUT")
    workflow_video_timeout: int = Field(default=1800, env="WORKFLOW_VIDEO_TIMEOUT")
    workflow_hitl_timeout: int = Field(default=3600, env="WORKFLOW_HITL_TIMEOUT")

    # Kynnysarvot
    workflow_min_articles_for_summary: int = Field(
        default=5,
        env="WORKFLOW_MIN_ARTICLES_FOR_SUMMARY"
    )
    workflow_max_articles_per_summary: int = Field(
        default=20,
        env="WORKFLOW_MAX_ARTICLES_PER_SUMMARY"
    )


class LocationSettings(BaseSettings):
    """Target location configurations for geographic content filtering.

    Defines the primary geographic target for climate news discovery and relevance
    filtering. Supports localized content discovery with news source management.

    Attributes:
        target_location_name: City or region name (default: "Helsinki")
        target_location_latitude: Geographic latitude (default: 60.1699)
        target_location_longitude: Geographic longitude (default: 24.9384)
        target_location_country: ISO 3166-1 alpha-2 country code (default: "FI")
        news_sources: List of news source URLs for content discovery

    Example:
        >>> settings = get_settings()
        >>> location = settings.location
        >>> print(f"{location.target_location_name}: {location.target_location_country}")
        Helsinki: FI
    """
    target_location_name: str = Field(default="Helsinki", env="TARGET_LOCATION_NAME")
    target_location_latitude: float = Field(default=60.1699, env="TARGET_LOCATION_LATITUDE")
    target_location_longitude: float = Field(default=24.9384, env="TARGET_LOCATION_LONGITUDE")
    target_location_country: str = Field(default="FI", env="TARGET_LOCATION_COUNTRY")

    news_sources: List[str] = Field(default=[], env="NEWS_SOURCES")

    @validator("news_sources", pre=True)
    def parse_news_sources(cls, v):
        """Parse comma-separated news sources from environment variable.

        Args:
            v: Raw value (comma-separated string or list)

        Returns:
            List of trimmed news source URLs
        """
        if isinstance(v, str):
            return [url.strip() for url in v.split(",") if url.strip()]
        return v


class QASettings(BaseSettings):
    """Quality assurance configurations for content validation thresholds.

    Defines quality gates and thresholds for automated content validation including
    source credibility requirements, readability standards, and relevance filtering.

    Attributes:
        qa_min_source_credibility: Minimum source credibility score (0-100, default: 60)
        qa_target_readability_level: Target readability grade level (default: 10)
        qa_min_content_relevance: Minimum content relevance score (0.0-1.0, default: 0.80)
        qa_golden_dataset_path: Path to golden dataset for validation testing

    Example:
        >>> settings = get_settings()
        >>> qa = settings.qa
        >>> if source_score < qa.qa_min_source_credibility:
        ...     print("Source credibility too low")
    """
    qa_min_source_credibility: int = Field(default=60, env="QA_MIN_SOURCE_CREDIBILITY")
    qa_target_readability_level: int = Field(default=10, env="QA_TARGET_READABILITY_LEVEL")
    qa_min_content_relevance: float = Field(default=0.80, env="QA_MIN_CONTENT_RELEVANCE")
    qa_golden_dataset_path: str = Field(
        default="/data/golden_dataset.json",
        env="QA_GOLDEN_DATASET_PATH"
    )


class ObservabilitySettings(BaseSettings):
    """Observability and monitoring configurations for distributed tracing.

    Manages OpenTelemetry integration, logging configuration, and service
    identification for comprehensive system monitoring and debugging.

    Attributes:
        otel_exporter_otlp_endpoint: OpenTelemetry OTLP endpoint URL
        otel_service_name: Service name for telemetry identification
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format type ("json" or "text")

    Example:
        >>> settings = get_settings()
        >>> obs = settings.observability
        >>> print(f"Service: {obs.otel_service_name}, Level: {obs.log_level}")
        Service: climatenews-mas, Level: INFO
    """
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4318",
        env="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(
        default="climatenews-mas",
        env="OTEL_SERVICE_NAME"
    )

    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")


class AppSettings(BaseSettings):
    """Main application settings aggregating all configuration sections.

    Root configuration class that combines all subsystem settings (LLM, Kafka,
    databases, etc.) with application-level settings for environment, security,
    and cost tracking.

    Attributes:
        environment: Deployment environment (development/staging/production)
        llm: LLM API configurations
        climate_data: Climate data API settings
        kafka: Kafka event bus configuration
        redis: Redis short-term memory settings
        postgres: PostgreSQL long-term storage settings
        vector_db: Vector database configuration
        scraper: Web scraping settings
        workflow: Workflow orchestration settings
        location: Target location configuration
        qa: Quality assurance thresholds
        observability: Logging and tracing settings
        gdpr_enabled: Enable GDPR compliance features
        content_safety_enabled: Enable content safety filtering
        data_retention_days: Data retention period in days
        cost_tracking_enabled: Enable cost tracking
        cost_alert_threshold: Cost alert threshold in USD

    Example:
        >>> settings = AppSettings()
        >>> print(settings.environment)
        'development'
        >>> print(settings.llm.claude_model)
        'claude-3-5-sonnet-20241022'
    """
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env", "../../.env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )

    environment: str = Field(default="development", env="ENVIRONMENT")

    # Alikonfiguraatiot
    llm: LLMSettings = Field(default_factory=LLMSettings)
    climate_data: ClimateDataSettings = Field(default_factory=ClimateDataSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)
    location: LocationSettings = Field(default_factory=LocationSettings)
    qa: QASettings = Field(default_factory=QASettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    # Turvallisuus & compliance
    gdpr_enabled: bool = Field(default=True, env="GDPR_ENABLED")
    content_safety_enabled: bool = Field(default=True, env="CONTENT_SAFETY_ENABLED")
    data_retention_days: int = Field(default=90, env="DATA_RETENTION_DAYS")

    # Kustannusseuranta
    cost_tracking_enabled: bool = Field(default=True, env="COST_TRACKING_ENABLED")
    cost_alert_threshold: float = Field(default=50.0, env="COST_ALERT_THRESHOLD")


@lru_cache()
def get_settings() -> AppSettings:
    """Get singleton configuration instance with automatic .env loading.

    Returns the same AppSettings instance on all subsequent calls for
    performance optimization. Loads configuration from environment variables
    and .env files (searches current dir, parent, and grandparent).

    Returns:
        AppSettings: Singleton configuration object with all settings sections

    Example:
        >>> from shared.config import get_settings
        >>> settings = get_settings()
        >>> anthropic_key = settings.llm.anthropic_api_key
        >>> kafka_url = settings.kafka.kafka_bootstrap_servers
    """
    return AppSettings()


# Convenience functions for specific settings sections
@lru_cache()
def get_llm_settings() -> LLMSettings:
    """Get LLM configuration section.

    Returns:
        LLMSettings: LLM API keys and pricing configuration
    """
    return get_settings().llm


@lru_cache()
def get_kafka_settings() -> KafkaSettings:
    """Get Kafka configuration section.

    Returns:
        KafkaSettings: Kafka broker and topic configuration
    """
    return get_settings().kafka


@lru_cache()
def get_redis_settings() -> RedisSettings:
    """Get Redis configuration section.

    Returns:
        RedisSettings: Redis connection and TTL configuration
    """
    return get_settings().redis


@lru_cache()
def get_postgres_settings() -> PostgresSettings:
    """Get PostgreSQL configuration section.

    Returns:
        PostgresSettings: PostgreSQL connection and pooling configuration
    """
    return get_settings().postgres


if __name__ == "__main__":
    # Testaa konfiguraation lataaminen
    settings = get_settings()
    print(f"Environment: {settings.environment}")
    print(f"Target Location: {settings.location.target_location_name}")
    print(f"Database URL: {settings.postgres.database_url}")

