"""
Pytest configuration and shared fixtures.

Provides a comprehensive testing infrastructure with:
- Lightweight in-memory database stub (PostgreSQL mock)
- Kafka producer/consumer mocks
- Redis cache mocks
- FastAPI test client with dependency overrides
- Test configuration and environment setup

All fixtures are reusable across test modules and automatically isolated per test.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure repository root is on sys.path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Configure environment variables for tests
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_climatenews")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from api.main import app, get_db  # noqa: E402
from api.auth_routes import get_db as auth_get_db  # noqa: E402


# =============================================================================
# Mock Classes for External Services
# =============================================================================


class MockKafkaProducer:
    """Mock Kafka producer for testing message publishing without Kafka instance."""

    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.is_closed = False

    def send(self, topic: str, value: Any = None, key: Any = None) -> "MockFutureRecord":
        """Simulate sending message to Kafka topic."""
        self.messages.append({
            "topic": topic,
            "key": key,
            "value": value,
            "timestamp": datetime.utcnow()
        })
        return MockFutureRecord(success=True)

    def flush(self, timeout: int = 30) -> None:
        """Mock flush operation."""
        pass

    def close(self) -> None:
        """Mock close operation."""
        self.is_closed = True

    def reset(self) -> None:
        """Clear all recorded messages."""
        self.messages.clear()


class MockFutureRecord:
    """Mock Kafka FutureRecordMetadata for testing async operations."""

    def __init__(self, success: bool = True, exception: Optional[Exception] = None) -> None:
        self.success = success
        self.exception = exception

    def get(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Simulate getting record metadata."""
        if not self.success:
            raise self.exception or Exception("Mock send failed")
        return {
            "topic": "test-topic",
            "partition": 0,
            "offset": 0,
            "timestamp": datetime.utcnow()
        }


class MockKafkaConsumer:
    """Mock Kafka consumer for testing message consumption."""

    def __init__(self, *topics: str, **kwargs) -> None:
        self.topics = topics
        self.messages: List[Dict[str, Any]] = []
        self.is_closed = False
        self.current_offset = 0

    def add_message(self, topic: str, value: Any, key: Any = None) -> None:
        """Add message to consumer queue for testing."""
        self.messages.append({
            "topic": topic,
            "key": key,
            "value": value,
            "offset": len(self.messages),
            "timestamp": datetime.utcnow()
        })

    def __iter__(self):
        """Iterate through messages."""
        return iter(self.messages)

    def close(self) -> None:
        """Mock close operation."""
        self.is_closed = True

    def reset(self) -> None:
        """Clear all recorded messages."""
        self.messages.clear()


class MockRedisClient:
    """Mock Redis client for testing caching operations without Redis instance."""

    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}
        self.ttl_map: Dict[str, Optional[int]] = {}
        self.is_connected = True

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Mock set operation with optional TTL."""
        self.store[key] = value
        self.ttl_map[key] = ex
        return True

    def get(self, key: str) -> Optional[Any]:
        """Mock get operation."""
        return self.store.get(key)

    def delete(self, *keys: str) -> int:
        """Mock delete operation."""
        count = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                del self.ttl_map[key]
                count += 1
        return count

    def exists(self, *keys: str) -> int:
        """Mock exists check."""
        return sum(1 for key in keys if key in self.store)

    def incr(self, key: str) -> int:
        """Mock increment operation."""
        current = int(self.store.get(key, 0))
        self.store[key] = current + 1
        return self.store[key]

    def expire(self, key: str, time: int) -> bool:
        """Mock expire operation."""
        if key in self.store:
            self.ttl_map[key] = time
            return True
        return False

    def ttl(self, key: str) -> int:
        """Mock TTL check."""
        if key not in self.store:
            return -2
        if self.ttl_map.get(key) is None:
            return -1
        return self.ttl_map[key]

    def flush(self) -> None:
        """Clear all data."""
        self.store.clear()
        self.ttl_map.clear()

    def close(self) -> None:
        """Mock connection close."""
        self.is_connected = False


class MockPostgresConnection:
    """Mock PostgreSQL connection for testing database operations."""

    def __init__(self) -> None:
        self.queries: List[Dict[str, Any]] = []
        self.is_open = True

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Mock query execution."""
        self.queries.append({
            "query": query,
            "params": params,
            "timestamp": datetime.utcnow()
        })
        return []

    def commit(self) -> None:
        """Mock transaction commit."""
        pass

    def rollback(self) -> None:
        """Mock transaction rollback."""
        pass

    def close(self) -> None:
        """Mock connection close."""
        self.is_open = False


class FakeDB:
    """
    Minimal in-memory database stub that satisfies the queries executed by
    api.main routes. This allows API tests to run deterministically without a
    live PostgreSQL instance.
    """

    def __init__(self) -> None:
        self.now = datetime.utcnow()
        self.article_id = "article-0001"

        self.article_row = {
            "article_id": self.article_id,
            "title": "Test Climate Article",
            "url": "https://example.com/test-article",
            "author": "Test Author",
            "published_date": self.now,
            "source_name": "YLE",
            "source_credibility_score": 85,
            "excerpt": "Summary of the latest climate developments in Finland.",
            "extracted_text": (
                "Helsinki temperatures have risen 2 degrees over the last 50 years."
            ),
            "tags": ["climate", "policy"],
            "content_relevance_score": 0.92,
            "reliability_score": 88,
            "overall_credibility": "HIGH",
            "created_at": self.now,
            "country_code": "FI",
            "claims_count": 1,
            "verified_claims_count": 1,
            "claims_status": "completed",
            "claims_error_message": None,
            "claims_processed_at": self.now,
        }

        self.claim_row = {
            "claim_id": "claim-0001",
            "claim_text": "Sea level is projected to rise one meter by 2100.",
            "claim_context": "Climate change projections in the Baltic Sea region.",
            "claim_type": "projection",
            "fact_check_id": "fact-0001",
            "verification_status": "VERIFIED",
            "confidence_score": 0.86,
            "justification": "Verified against NOAA datasets.",
            "evidence": '{"sources": ["NOAA", "IPCC"]}',
            "climatecheck_hazard_type": "sea_level_rise",
            "climatecheck_risk_score": 0.71,
            "verified_at": self.now,
        }

        self.feedback_rows: List[Dict[str, Any]] = []

    def _article_listing(self, params: Dict[str, Any]):
        limit = params.get("limit", 20)
        offset = params.get("offset", 0)
        if offset > 0:
            return []
        return [self.article_row][:limit]

    def _article_detail(self):
        return [self.article_row]

    def _claims_for_article(self):
        return [self.claim_row]

    def _countries(self):
        return [
            {
                "country_code": "FI",
                "country_name": "Finland",
                "country_name_native": "Suomi",
                "flag_emoji": "🇫🇮",
                "language_code": "fi",
                "is_eu_member": True,
                "articles_count": 1,
            }
        ]

    def _tag_stats(self):
        return [
            {"tag": "climate", "article_count": 1},
            {"tag": "policy", "article_count": 1},
        ]

    def _article_stats(self):
        return [
            {
                "total_articles": 1,
                "articles_today": 1,
                "last_updated": self.now,
            }
        ]

    def _fact_stats(self):
        return [
            {
                "total_fact_checks": 1,
                "verified_claims": 1,
                "average_confidence": 0.86,
            }
        ]

    def _workflows(self):
        return []

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        params = params or {}
        normalized_query = " ".join(query.split()).lower()

        if "insert into article_feedback" in normalized_query:
            entry = {
                "feedback_id": f"fb-{len(self.feedback_rows) + 1}",
                "article_id": params.get("article_id", self.article_id),
                "feedback_type": params.get("feedback_type", "USEFUL"),
                "reliability_score": params.get("reliability_score"),
                "comment": params.get("comment"),
                "submitted_at": self.now,
            }
            self.feedback_rows.append(entry)
            return [entry]

        if "from article_feedback" in normalized_query and "count" in normalized_query:
            total = len(self.feedback_rows)
            useful = sum(1 for row in self.feedback_rows if row["feedback_type"] == "USEFUL")
            not_useful = sum(
                1 for row in self.feedback_rows if row["feedback_type"] == "NOT_USEFUL"
            )
            flagged = sum(
                1 for row in self.feedback_rows if row["feedback_type"] == "FLAGGED"
            )
            avg = (
                sum(row["reliability_score"] or 0 for row in self.feedback_rows) / total
                if total
                else None
            )
            return [
                {
                    "total_feedback": total,
                    "useful": useful,
                    "not_useful": not_useful,
                    "flagged": flagged,
                    "average_reliability": avg,
                }
            ]

        if "select 1 from articles where article_id" in normalized_query:
            aid = params.get("article_id") if params else None
            if aid and aid != self.article_id:
                return []
            return [{"exists": 1}]

        if "from articles a" in normalized_query and "where a.article_id" not in normalized_query:
            return self._article_listing(params)

        if "where a.article_id" in normalized_query:
            aid = params.get("article_id") if params else None
            if aid and aid != self.article_id:
                return []
            return self._article_detail()

        if "from claims c" in normalized_query:
            return self._claims_for_article()

        if "from countries c" in normalized_query:
            return self._countries()

        if "from ( select unnest(tags)" in normalized_query or "from (" in normalized_query and "unnest(tags)" in normalized_query:
            return self._tag_stats()

        if "from articles" in normalized_query and "count" in normalized_query and "filter" not in normalized_query and "left join" not in normalized_query:
            return self._article_stats()

        if "from fact_checks" in normalized_query and "count" in normalized_query:
            return self._fact_stats()

        if "from workflow_logs" in normalized_query:
            return self._workflows()

        # Default: return empty results
        return []


@pytest.fixture
def fake_db():
    """Provide a fresh FakeDB for each test."""
    return FakeDB()


@pytest.fixture
def client(fake_db):
    """
    Provide a TestClient with the database dependency overridden to use FakeDB.

    Overrides both main.get_db and auth_routes.get_db (used by get_optional_user).
    Also patches api.map_routes.get_postgres and api.translation_routes.get_postgres
    for routes that call get_postgres() directly rather than via FastAPI DI.
    """

    def override_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_db
    # auth_routes defines its own get_db used by get_optional_user
    app.dependency_overrides[auth_get_db] = lambda: fake_db

    # Patch the global singleton so ALL modules get the mock when they call get_postgres().
    # This covers every api/* module that does `from shared.database import get_postgres`
    # and calls get_postgres() directly (rate_limiter, search_routes, chat_routes, etc.).
    postgres_mock = MagicMock()
    postgres_mock.execute_query.return_value = []
    postgres_mock.execute_update.return_value = None
    postgres_mock.execute_scalar.return_value = 0

    import shared.database as _shared_db
    _orig_pg = _shared_db._postgres_client
    _shared_db._postgres_client = postgres_mock
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        _shared_db._postgres_client = _orig_pg
        app.dependency_overrides.clear()


# =============================================================================
# Additional Shared Fixtures for Common Testing Scenarios
# =============================================================================


@pytest.fixture
def mock_kafka_producer() -> Generator[MockKafkaProducer, None, None]:
    """
    Provide a fresh MockKafkaProducer instance for each test.

    Usage:
        def test_example(mock_kafka_producer):
            mock_kafka_producer.send("test-topic", value={"data": "test"})
            assert len(mock_kafka_producer.messages) == 1
    """
    producer = MockKafkaProducer()
    yield producer
    producer.close()


@pytest.fixture
def mock_kafka_consumer() -> Generator[MockKafkaConsumer, None, None]:
    """
    Provide a fresh MockKafkaConsumer instance for each test.

    Usage:
        def test_example(mock_kafka_consumer):
            mock_kafka_consumer.add_message("test-topic", {"data": "test"})
            messages = list(mock_kafka_consumer)
            assert len(messages) == 1
    """
    consumer = MockKafkaConsumer("test-topic")
    yield consumer
    consumer.close()


@pytest.fixture
def mock_redis() -> Generator[MockRedisClient, None, None]:
    """
    Provide a fresh MockRedisClient instance for each test.

    Usage:
        def test_example(mock_redis):
            mock_redis.set("key", "value", ex=300)
            assert mock_redis.get("key") == "value"
    """
    redis_client = MockRedisClient()
    yield redis_client
    redis_client.flush()
    redis_client.close()


@pytest.fixture
def mock_postgres() -> Generator[MockPostgresConnection, None, None]:
    """
    Provide a fresh MockPostgresConnection instance for each test.

    Usage:
        def test_example(mock_postgres):
            mock_postgres.execute("SELECT * FROM articles")
            assert len(mock_postgres.queries) == 1
    """
    conn = MockPostgresConnection()
    yield conn
    conn.close()


@pytest.fixture
def sample_article() -> Dict[str, Any]:
    """
    Provide sample article data for testing.

    Returns a complete article dictionary matching the database schema.
    """
    return {
        "article_id": "test-article-001",
        "title": "Climate Change Impact on Nordic Countries",
        "url": "https://example.com/climate-article",
        "author": "Test Author",
        "published_date": datetime.utcnow(),
        "source_name": "Test News",
        "source_credibility_score": 85,
        "excerpt": "A comprehensive analysis of climate change effects.",
        "extracted_text": "Full article text about climate change impacts...",
        "tags": ["climate", "environment", "nordic"],
        "content_relevance_score": 0.92,
        "reliability_score": 88,
        "overall_credibility": "HIGH",
        "country_code": "FI",
    }


@pytest.fixture
def sample_claim() -> Dict[str, Any]:
    """
    Provide sample claim data for testing.

    Returns a complete claim dictionary matching the database schema.
    """
    return {
        "claim_id": "test-claim-001",
        "claim_text": "Temperature has increased by 2 degrees Celsius",
        "claim_context": "Climate measurements in Finland over 50 years",
        "claim_type": "statistical",
        "verification_status": "VERIFIED",
        "confidence_score": 0.89,
        "justification": "Verified against meteorological data",
        "evidence": '{"sources": ["FMI", "SMHI"]}',
    }


@pytest.fixture
def sample_workflow_task() -> Dict[str, Any]:
    """
    Provide sample workflow task data for testing agent orchestration.

    Returns a complete task dictionary for Kafka message testing.
    """
    return {
        "taskId": "task-test-001",
        "command": "discover_content",
        "parameters": {
            "targetLocation": {
                "name": "Helsinki",
                "latitude": 60.1699,
                "longitude": 24.9384,
                "country": "FI"
            },
            "dateRange": {
                "from": "2025-01-01",
                "to": "2025-01-31"
            }
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@pytest.fixture
def test_environment_vars(monkeypatch) -> None:
    """
    Set up test environment variables.

    Automatically applied environment configuration for testing.
    Use monkeypatch to override specific variables in individual tests.
    """
    env_vars = {
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "ERROR",
        "JWT_SECRET_KEY": "test-secret-key-do-not-use",
        "DATABASE_URL": "postgresql://test:test@localhost/test_db",
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "REDIS_URL": "redis://localhost:6379/0",
        "API_RATE_LIMIT": "1000",
        "CACHE_TTL": "300",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def authenticated_client(client) -> TestClient:
    """
    Provide a TestClient with authentication headers already set.

    Usage:
        def test_protected_endpoint(authenticated_client):
            response = authenticated_client.get("/api/protected")
            assert response.status_code == 200
    """
    # Mock JWT token for testing
    test_token = "test.jwt.token"
    client.headers.update({"Authorization": f"Bearer {test_token}"})
    return client


@pytest.fixture(autouse=True)
def reset_app_state():
    """
    Automatically reset application state between tests.

    This fixture runs before each test to ensure clean state.
    """
    # Clear any dependency overrides
    app.dependency_overrides.clear()

    yield

    # Cleanup after test
    app.dependency_overrides.clear()


@pytest.fixture
def freeze_time():
    """
    Provide a frozen datetime for deterministic time-based testing.

    Usage:
        def test_time_dependent(freeze_time):
            now = freeze_time
            # All datetime.utcnow() calls will return this value
    """
    frozen_datetime = datetime(2025, 1, 15, 12, 0, 0)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = frozen_datetime
        mock_datetime.now.return_value = frozen_datetime
        yield frozen_datetime


@pytest.fixture
def temp_test_file(tmp_path):
    """
    Provide a temporary file path for file I/O testing.

    Args:
        tmp_path: pytest built-in fixture providing temporary directory

    Returns:
        Path object to a temporary file that will be cleaned up after test

    Usage:
        def test_file_operations(temp_test_file):
            temp_test_file.write_text("test data")
            assert temp_test_file.read_text() == "test data"
    """
    file_path = tmp_path / "test_file.txt"
    yield file_path
    # Cleanup is automatic with tmp_path


# =============================================================================
# Marker-based Fixtures for Integration Tests
# =============================================================================


@pytest.fixture
def kafka_integration(request):
    """
    Fixture for tests marked with @pytest.mark.kafka.

    Provides real Kafka connection for integration testing.
    Skips test if Kafka is not available.
    """
    if "kafka" not in request.keywords:
        pytest.skip("Not a Kafka integration test")

    # Check if Kafka is available
    kafka_available = os.getenv("KAFKA_AVAILABLE", "false").lower() == "true"
    if not kafka_available:
        pytest.skip("Kafka not available for integration testing")

    # Setup real Kafka connection here
    # yield kafka_connection
    # Cleanup


@pytest.fixture
def redis_integration(request):
    """
    Fixture for tests marked with @pytest.mark.redis.

    Provides real Redis connection for integration testing.
    Skips test if Redis is not available.
    """
    if "redis" not in request.keywords:
        pytest.skip("Not a Redis integration test")

    redis_available = os.getenv("REDIS_AVAILABLE", "false").lower() == "true"
    if not redis_available:
        pytest.skip("Redis not available for integration testing")

    # Setup real Redis connection here
    # yield redis_connection
    # Cleanup


@pytest.fixture
def postgres_integration(request):
    """
    Fixture for tests marked with @pytest.mark.postgres.

    Provides real PostgreSQL connection for integration testing.
    Skips test if PostgreSQL is not available.
    """
    if "postgres" not in request.keywords:
        pytest.skip("Not a PostgreSQL integration test")

    postgres_available = os.getenv("POSTGRES_AVAILABLE", "false").lower() == "true"
    if not postgres_available:
        pytest.skip("PostgreSQL not available for integration testing")

    # Setup real PostgreSQL connection here
    # yield postgres_connection
    # Cleanup
