"""
Keskitetty konfiguraatiohallinta kaikille agenteille

Käyttää Pydantic Settings -kirjastoa ympäristömuuttujien hallintaan.
"""

from functools import lru_cache
from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM API-konfiguraatiot"""
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env", "../../.env"],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    perplexity_api_key: Optional[str] = Field(default=None, env="PERPLEXITY_API_KEY")
    
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", env="CLAUDE_MODEL")
    gpt_model: str = Field(default="gpt-4o", env="GPT_MODEL")
    perplexity_model: str = Field(default="llama-3.1-sonar-large-128k-online", env="PERPLEXITY_MODEL")
    
    # Token-hinnat (per 1K tokens)
    claude_input_price_per_1k: float = Field(default=0.003, env="CLAUDE_INPUT_PRICE_PER_1K")
    claude_output_price_per_1k: float = Field(default=0.015, env="CLAUDE_OUTPUT_PRICE_PER_1K")
    gpt4o_input_price_per_1k: float = Field(default=0.005, env="GPT4O_INPUT_PRICE_PER_1K")
    gpt4o_output_price_per_1k: float = Field(default=0.015, env="GPT4O_OUTPUT_PRICE_PER_1K")


class ClimateDataSettings(BaseSettings):
    """Ilmastodatan API-konfiguraatiot"""
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


class KafkaSettings(BaseSettings):
    """Kafka-konfiguraatiot"""
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        env="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_schema_registry_url: str = Field(
        default="http://localhost:8081",
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
        default="creation_queue",
        env="KAFKA_TOPIC_CREATION_QUEUE"
    )
    kafka_topic_video_queue: str = Field(
        default="video_queue",
        env="KAFKA_TOPIC_VIDEO_QUEUE"
    )
    kafka_topic_publication_queue: str = Field(
        default="publication_queue",
        env="KAFKA_TOPIC_PUBLICATION_QUEUE"
    )


class RedisSettings(BaseSettings):
    """Redis (lyhytaikainen muisti) konfiguraatiot"""
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_ttl_seconds: int = Field(default=86400, env="REDIS_TTL_SECONDS")  # 24h


class PostgresSettings(BaseSettings):
    """PostgreSQL (pitkäaikainen muisti) konfiguraatiot"""
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, env="POSTGRES_PORT")
    postgres_db: str = Field(default="climatenews", env="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", env="POSTGRES_USER")
    postgres_password: str = Field(default="climatenews123", env="POSTGRES_PASSWORD")
    
    postgres_pool_min_size: int = Field(default=5, env="POSTGRES_POOL_MIN_SIZE")
    postgres_pool_max_size: int = Field(default=20, env="POSTGRES_POOL_MAX_SIZE")
    
    @property
    def database_url(self) -> str:
        """Palauttaa PostgreSQL connection string"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class VectorDBSettings(BaseSettings):
    """Vektoritietokanta-konfiguraatiot"""
    vector_db_type: str = Field(default="pgvector", env="VECTOR_DB_TYPE")
    vector_db_dimension: int = Field(default=1536, env="VECTOR_DB_DIMENSION")
    vector_db_index_type: str = Field(default="ivfflat", env="VECTOR_DB_INDEX_TYPE")
    
    # Pinecone-asetukset (jos käytetään)
    pinecone_api_key: Optional[str] = Field(default=None, env="PINECONE_API_KEY")
    pinecone_environment: Optional[str] = Field(default=None, env="PINECONE_ENVIRONMENT")
    pinecone_index_name: Optional[str] = Field(default=None, env="PINECONE_INDEX_NAME")


class ScraperSettings(BaseSettings):
    """Web scraping -konfiguraatiot"""
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
    """Työnkulun konfiguraatiot"""
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
    """Kohdepaikan konfiguraatiot"""
    target_location_name: str = Field(default="Helsinki", env="TARGET_LOCATION_NAME")
    target_location_latitude: float = Field(default=60.1699, env="TARGET_LOCATION_LATITUDE")
    target_location_longitude: float = Field(default=24.9384, env="TARGET_LOCATION_LONGITUDE")
    target_location_country: str = Field(default="FI", env="TARGET_LOCATION_COUNTRY")
    
    news_sources: List[str] = Field(default=[], env="NEWS_SOURCES")
    
    @validator("news_sources", pre=True)
    def parse_news_sources(cls, v):
        if isinstance(v, str):
            return [url.strip() for url in v.split(",") if url.strip()]
        return v


class QASettings(BaseSettings):
    """Laadunvarmistuksen konfiguraatiot"""
    qa_min_source_credibility: int = Field(default=60, env="QA_MIN_SOURCE_CREDIBILITY")
    qa_target_readability_level: int = Field(default=10, env="QA_TARGET_READABILITY_LEVEL")
    qa_min_content_relevance: float = Field(default=0.80, env="QA_MIN_CONTENT_RELEVANCE")
    qa_golden_dataset_path: str = Field(
        default="/data/golden_dataset.json",
        env="QA_GOLDEN_DATASET_PATH"
    )


class ObservabilitySettings(BaseSettings):
    """Observability & monitorointi -konfiguraatiot"""
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
    """Pääkonfiguraatiot - yhdistää kaikki asetukset"""
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
    """
    Palauttaa singleton-instanssi konfiguraatioista.
    Käyttää lru_cache:a välttääkseen toistuvan .env-tiedoston lukemisen.
    """
    return AppSettings()


# Convenience-funktiot eri asetuksille
@lru_cache()
def get_llm_settings() -> LLMSettings:
    return get_settings().llm


@lru_cache()
def get_kafka_settings() -> KafkaSettings:
    return get_settings().kafka


@lru_cache()
def get_redis_settings() -> RedisSettings:
    return get_settings().redis


@lru_cache()
def get_postgres_settings() -> PostgresSettings:
    return get_settings().postgres


if __name__ == "__main__":
    # Testaa konfiguraation lataaminen
    settings = get_settings()
    print(f"Environment: {settings.environment}")
    print(f"Target Location: {settings.location.target_location_name}")
    print(f"Database URL: {settings.postgres.database_url}")

