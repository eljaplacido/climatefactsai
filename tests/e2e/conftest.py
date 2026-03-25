"""
E2E test fixtures for full pipeline testing.

Provides database and Redis connections for integration testing.
Falls back to mocks when services are unavailable.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4


@pytest.fixture
def db_connection():
    """Get a database connection, skip if unavailable."""
    try:
        from shared.database import get_postgres
        db = get_postgres()
        # Test connection
        db.execute_query("SELECT 1", {})
        return db
    except Exception:
        pytest.skip("PostgreSQL not available for E2E tests")


@pytest.fixture
def redis_connection():
    """Get a Redis connection, skip if unavailable."""
    try:
        import redis
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True,
        )
        r.ping()
        return r
    except Exception:
        pytest.skip("Redis not available for E2E tests")


@pytest.fixture
def mock_db():
    """Mock database for testing without real DB."""
    db = MagicMock()
    db.execute_query = MagicMock(return_value=[])
    db.execute_update = MagicMock()
    return db


@pytest.fixture
def sample_article_id():
    """Generate a sample article UUID."""
    return str(uuid4())


@pytest.fixture
def sample_workflow_state(sample_article_id):
    """Create a sample workflow state dict."""
    return {
        "task_id": f"test-{uuid4()}",
        "country": "FI",
        "article_ids": [sample_article_id],
        "discovery_method": "test",
    }


@pytest.fixture
def sample_article_row(sample_article_id):
    """Create a sample article database row."""
    return {
        "article_id": sample_article_id,
        "title": "Finland Records Highest Arctic Temperature in 2024",
        "url": "https://example.com/finland-temp-2024",
        "source_name": "YLE News",
        "excerpt": "Finland experienced record-breaking temperatures in 2024.",
        "extracted_text": (
            "Finland experienced record-breaking temperatures in 2024, with the "
            "Finnish Meteorological Institute reporting an average temperature increase "
            "of 2.3 degrees Celsius since pre-industrial times. The Arctic amplification "
            "effect continues to drive faster warming in Nordic countries compared to the "
            "global average. Summer temperatures reached 33.8°C in Lapland, one of the "
            "highest recordings in the region's history. The government reaffirmed its "
            "commitment to achieving carbon neutrality by 2035."
        ),
        "country_code": "FI",
        "language_code": "en",
        "summary_text": None,
        "claims_status": "pending",
    }


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='[{"claim_text": "Finland temperature rose 2.3C", "claim_type": "factual", "claim_category": "statistical", "importance_score": 0.9, "claim_context": "Average temperature increase"}]')]
    return mock_message


@pytest.fixture
def mock_verification_result(sample_article_id):
    """Create a mock verification result."""
    return {
        "article_id": sample_article_id,
        "claims_extracted": 3,
        "claims_verified": 2,
        "claims_disputed": 1,
        "claims_unverified": 0,
        "average_confidence": 0.82,
        "article_credibility": 0.78,
        "credibility_level": "medium",
        "status": "completed",
        "claims_by_category": {"statistical": 2, "policy": 1},
    }
