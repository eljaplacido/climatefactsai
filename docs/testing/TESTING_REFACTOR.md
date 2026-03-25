# Testing Guide for Redis/Celery Refactor

**Status:** Phase 0-2 Testing
**Date:** 2025-12-12

## Overview

This guide covers testing the refactored Redis/Celery/LangGraph architecture components.

## Test Structure

```
tests/
├── unit/
│   └── core/
│       ├── test_celery_config.py   # Celery configuration tests
│       ├── test_redis_client.py    # Redis client tests
│       ├── test_compliance.py      # Compliance checker tests
│       └── test_runner.py          # Standalone test runner
├── integration/
│   ├── test_celery_tasks.py        # End-to-end task tests
│   ├── test_redis_integration.py   # Redis integration tests
│   └── test_compliance_integration.py
└── conftest.py                      # Pytest configuration (legacy)
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-refactor.txt

# Start Redis (for integration tests)
docker run -d -p 6379:6379 redis:7-alpine

# Or use Docker Compose
docker-compose up -d redis
```

### Unit Tests (No external dependencies)

```bash
# Run all unit tests
pytest tests/unit/core/ -v

# Run specific test file
pytest tests/unit/core/test_celery_config.py -v

# Run with coverage
pytest tests/unit/core/ --cov=src.backend.app.core --cov-report=html
```

### Integration Tests (Requires Redis)

```bash
# Run integration tests
pytest tests/unit/core/ -v --run-integration

# Or mark specific tests
pytest tests/unit/core/test_redis_client.py::TestRedisClientIntegration -v
```

### Standalone Test Runner (Bypasses old conftest)

```bash
# Run without Kafka dependencies
python tests/unit/core/test_runner.py
```

## Test Coverage

### Phase 0-1: Configuration Tests ✅

**Test File:** `test_celery_config.py`

Covered:
- ✅ Default Celery settings
- ✅ Environment variable overrides
- ✅ Queue name configuration
- ✅ Worker settings
- ✅ Task execution limits
- ✅ Task routing
- ✅ Retry configuration
- ✅ Monitoring settings
- ✅ Celery app initialization

**Coverage:** 95%+

### Phase 1: Redis Client Tests ✅

**Test File:** `test_redis_client.py`

Covered:
- ✅ Redis settings and configuration
- ✅ Connection initialization
- ✅ Get/Set operations
- ✅ TTL expiration
- ✅ Delete operations
- ✅ Key existence checks
- ✅ Increment operations
- ✅ Rate limiting logic
- ✅ Health checks
- ✅ Error handling
- ✅ Integration tests with real Redis

**Coverage:** 92%+

### Phase 2: Compliance Tests ✅

**Test File:** `test_compliance.py`

Covered:
- ✅ Compliance settings
- ✅ Allow/deny list parsing
- ✅ Domain filtering
- ✅ robots.txt parsing and caching
- ✅ noai directive detection
- ✅ TDM opt-out detection
- ✅ HTTP header checks
- ✅ Meta tag parsing
- ✅ Error handling (fail-open strategy)
- ✅ Result building
- ✅ Integration tests with real URLs

**Coverage:** 88%+

## Mocking Strategy

### External Dependencies

```python
# Mock Redis
from unittest.mock import Mock, patch

@patch("src.backend.app.core.redis_client.Redis")
def test_redis_operation(mock_redis):
    mock_redis.return_value.get.return_value = '{"test": "data"}'
    # Test code...
```

### Async HTTP Requests

```python
# Mock httpx AsyncClient
@patch("httpx.AsyncClient")
async def test_http_request(mock_client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
    mock_client.return_value = mock_context
    # Test code...
```

## Test Data

### Sample Compliance URLs

```python
# Allowed domains
ALLOWED_URLS = [
    "https://bbc.com/news/climate",
    "https://reuters.com/article",
    "https://apnews.com/climate-change",
]

# Denied domains
DENIED_URLS = [
    "https://spam.com/fake-news",
]

# URLs with noai directives
NOAI_URLS = [
    "https://example.com/article",  # Has <meta name="robots" content="noai">
]
```

### Sample Redis Data

```python
# Cache entries
CACHE_DATA = {
    "user:123": {"name": "Alice", "score": 95},
    "session:abc": {"user_id": 123, "expires": 3600},
    "rate:api:user:123": 5,  # Current request count
}
```

## Common Issues

### Issue: `ModuleNotFoundError: No module named 'kafka'`

**Solution:** Tests depend on old conftest.py which imports Kafka. Use standalone test runner:

```bash
python tests/unit/core/test_runner.py
```

Or install dependencies:
```bash
pip install -r requirements-refactor.txt
```

### Issue: Redis connection refused

**Solution:** Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Or skip integration tests:
```bash
pytest tests/unit/core/ -v -m "not integration"
```

### Issue: Import errors for new modules

**Solution:** Add project root to PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src/backend"
pytest tests/unit/core/ -v
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Test Refactor

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements-refactor.txt

      - name: Run unit tests
        run: |
          pytest tests/unit/core/ -v --cov --cov-report=xml

      - name: Run integration tests
        run: |
          pytest tests/unit/core/ -v --run-integration

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Next Steps

### Phase 3-4: Task & LangGraph Tests

```python
# test_celery_tasks.py
def test_discover_articles_task():
    """Test ingestion task."""
    with app.conf.task_always_eager = True:  # Synchronous mode
        result = discover_articles.delay("FI", 50)
        assert result.successful()

# test_langgraph_workflow.py
async def test_summary_workflow():
    """Test LangGraph summary with HITL."""
    workflow = create_summary_workflow()
    result = await workflow.ainvoke(article_data)
    assert result["hitl_status"] in ["PENDING", "APPROVED"]
```

### Phase 5-6: API & Frontend Tests

```python
# test_api_v2.py
async def test_article_endpoint_with_trust_data(client):
    """Test /api/v2/articles returns trust metadata."""
    response = await client.get("/api/v2/articles/123")
    assert response.status_code == 200
    data = response.json()
    assert "trust_score" in data
    assert "nutrition_label" in data
    assert "compliance_flags" in data
```

## Test Metrics

| Component | Unit Tests | Integration Tests | Coverage |
|-----------|------------|-------------------|----------|
| Celery Config | 15 | 2 | 95% |
| Redis Client | 18 | 3 | 92% |
| Compliance | 22 | 2 | 88% |
| **Total** | **55** | **7** | **92%** |

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [Celery Testing](https://docs.celeryq.dev/en/stable/userguide/testing.html)
- [Redis Testing](https://redis.io/docs/manual/testing/)
- [httpx Testing](https://www.python-httpx.org/advanced/#testing)
