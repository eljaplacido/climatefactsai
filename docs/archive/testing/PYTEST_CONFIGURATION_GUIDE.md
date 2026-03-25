# Pytest Configuration Guide

## Overview

This project uses a comprehensive pytest configuration with parallel execution, coverage reporting, and extensive fixture support for testing the Climate News Multi-Agent System.

## Quick Start

### Run All Tests
```bash
pytest
```

### Run with Specific Markers
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only e2e tests
pytest -m e2e

# Exclude slow tests
pytest -m "not slow"
```

### Run with Coverage
```bash
# Coverage is enabled by default
pytest

# View HTML coverage report
pytest && open htmlcov/index.html

# Run without coverage
pytest --no-cov
```

### Parallel Execution
```bash
# Auto-detect number of CPUs (default)
pytest -n auto

# Specify number of workers
pytest -n 4

# Disable parallel execution
pytest -n 0
```

## Configuration Details

### Test Discovery

- **Test paths**: `tests/`
- **File pattern**: `test_*.py`
- **Class pattern**: `Test*`
- **Function pattern**: `test_*`

### Test Markers

All tests should be marked with appropriate markers for categorization:

```python
import pytest

@pytest.mark.unit
def test_example_unit():
    """Fast unit test with no external dependencies"""
    assert 1 + 1 == 2

@pytest.mark.integration
@pytest.mark.redis
def test_example_integration():
    """Integration test requiring Redis"""
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_example_e2e():
    """Full end-to-end test"""
    pass
```

#### Available Markers

- **unit**: Unit tests (fast, no external services)
- **integration**: Integration tests (requires external services)
- **e2e**: End-to-end tests (full system testing)
- **slow**: Slow running tests (>1 second)
- **kafka**: Tests requiring Kafka infrastructure
- **redis**: Tests requiring Redis cache
- **postgres**: Tests requiring PostgreSQL database
- **api**: API endpoint tests
- **service**: Business logic service tests
- **fixture**: Fixture and mock tests

### Coverage Configuration

Coverage is automatically collected for:
- `api/` directory
- `src/backend/` directory

**Omitted from coverage:**
- Virtual environments (`venv/`)
- Test files (`tests/`)
- Site packages

**Coverage Reports:**
- HTML report: `htmlcov/index.html`
- JSON report: `coverage.json`
- Terminal output with missing lines

**Coverage Exclusions:**
```python
# These lines are excluded from coverage
# pragma: no cover
def __repr__():  # Excluded
    pass

if __name__ == "__main__":  # Excluded
    main()

if TYPE_CHECKING:  # Excluded
    from typing import Protocol
```

### Parallel Execution

Tests run in parallel by default using `pytest-xdist`:

- **Strategy**: `loadscope` (groups tests by class/module)
- **Workers**: Auto-detect CPU count (`-n auto`)
- **Max failures**: Stop after 5 failures (`--maxfail=5`)

**Benefits:**
- 2-4x faster test execution
- Efficient resource utilization
- Isolated test execution

### Timeouts

- **Default timeout**: 10 seconds per test
- **Function-only**: Only test functions timeout (not fixtures)
- **Override for slow tests**:
  ```python
  @pytest.mark.slow
  @pytest.mark.timeout(300)
  def test_slow_operation():
      # This test can run for up to 5 minutes
      pass
  ```

## Available Fixtures

### Mock Service Fixtures

#### mock_kafka_producer
```python
def test_kafka_publishing(mock_kafka_producer):
    mock_kafka_producer.send("test-topic", value={"data": "test"})
    assert len(mock_kafka_producer.messages) == 1
    assert mock_kafka_producer.messages[0]["topic"] == "test-topic"
```

#### mock_kafka_consumer
```python
def test_kafka_consuming(mock_kafka_consumer):
    mock_kafka_consumer.add_message("test-topic", {"data": "test"})
    messages = list(mock_kafka_consumer)
    assert len(messages) == 1
```

#### mock_redis
```python
def test_redis_caching(mock_redis):
    mock_redis.set("key", "value", ex=300)
    assert mock_redis.get("key") == "value"
    assert mock_redis.ttl("key") == 300
```

#### mock_postgres
```python
def test_database_query(mock_postgres):
    mock_postgres.execute("SELECT * FROM articles")
    assert len(mock_postgres.queries) == 1
```

### Sample Data Fixtures

#### sample_article
```python
def test_article_processing(sample_article):
    assert sample_article["article_id"] == "test-article-001"
    assert "climate" in sample_article["tags"]
```

#### sample_claim
```python
def test_claim_verification(sample_claim):
    assert sample_claim["verification_status"] == "VERIFIED"
    assert sample_claim["confidence_score"] > 0.8
```

#### sample_workflow_task
```python
def test_task_orchestration(sample_workflow_task):
    assert sample_workflow_task["command"] == "discover_content"
    assert "parameters" in sample_workflow_task
```

### API Testing Fixtures

#### client
```python
def test_api_endpoint(client):
    response = client.get("/api/articles")
    assert response.status_code == 200
```

#### authenticated_client
```python
def test_protected_endpoint(authenticated_client):
    response = authenticated_client.get("/api/protected")
    assert response.status_code == 200
```

### Database Fixtures

#### fake_db
```python
def test_database_operations(fake_db):
    result = fake_db.execute_query("SELECT * FROM articles")
    assert len(result) > 0
```

### Utility Fixtures

#### freeze_time
```python
def test_time_dependent_logic(freeze_time):
    # All datetime operations use frozen_time
    assert datetime.utcnow() == freeze_time
```

#### temp_test_file
```python
def test_file_operations(temp_test_file):
    temp_test_file.write_text("test data")
    assert temp_test_file.read_text() == "test data"
    # Automatic cleanup after test
```

#### test_environment_vars
```python
def test_with_env_vars(test_environment_vars):
    # Environment variables are automatically set
    assert os.getenv("ENVIRONMENT") == "test"
```

### Integration Test Fixtures

#### kafka_integration
```python
@pytest.mark.kafka
def test_real_kafka(kafka_integration):
    # Automatically skips if Kafka not available
    # Provides real Kafka connection
    pass
```

#### redis_integration
```python
@pytest.mark.redis
def test_real_redis(redis_integration):
    # Automatically skips if Redis not available
    pass
```

#### postgres_integration
```python
@pytest.mark.postgres
def test_real_postgres(postgres_integration):
    # Automatically skips if PostgreSQL not available
    pass
```

## Running Tests in CI/CD

### GitHub Actions Example
```yaml
- name: Run tests
  run: |
    pytest --cov --cov-report=xml
  env:
    ENVIRONMENT: test
    POSTGRES_AVAILABLE: "true"
    REDIS_AVAILABLE: "true"
    KAFKA_AVAILABLE: "true"
```

### Docker Compose Testing
```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run tests
docker-compose -f docker-compose.test.yml run --rm test pytest

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Best Practices

### 1. Use Appropriate Markers
```python
@pytest.mark.unit  # Fast, isolated tests
def test_pure_function():
    pass

@pytest.mark.integration
@pytest.mark.postgres
def test_database_integration():
    pass
```

### 2. Leverage Fixtures
```python
# Good: Reusable fixture
def test_with_fixture(mock_redis, sample_article):
    mock_redis.set(f"article:{sample_article['article_id']}", sample_article)
    assert mock_redis.exists(f"article:{sample_article['article_id']}")

# Avoid: Manual setup in each test
def test_without_fixture():
    redis = MockRedisClient()
    article = {"article_id": "test-001", ...}
    # ... duplicate setup code
```

### 3. Isolate Test Data
```python
@pytest.fixture
def unique_article(sample_article):
    """Create unique article for each test"""
    article = sample_article.copy()
    article["article_id"] = f"test-{uuid.uuid4()}"
    return article
```

### 4. Use Parametrize for Multiple Cases
```python
@pytest.mark.parametrize("status,expected", [
    ("VERIFIED", True),
    ("UNVERIFIED", False),
    ("DISPUTED", False),
])
def test_claim_status(status, expected):
    claim = {"verification_status": status}
    assert is_verified(claim) == expected
```

### 5. Test Error Conditions
```python
def test_invalid_input_raises_error():
    with pytest.raises(ValueError, match="Invalid article ID"):
        process_article(None)
```

## Troubleshooting

### Tests Running Slowly
```bash
# Identify slow tests
pytest --durations=10

# Run without parallel execution for debugging
pytest -n 0 -v
```

### Coverage Not Showing
```bash
# Ensure source paths are correct
pytest --cov=api --cov=src/backend --cov-report=term

# Check coverage configuration in pytest.ini
```

### Fixtures Not Found
```bash
# Ensure conftest.py is in tests/ directory
# Check fixture scope and availability
pytest --fixtures  # List all available fixtures
```

### Parallel Execution Issues
```bash
# Disable parallel execution
pytest -n 0

# Use different distribution strategy
pytest -n auto --dist loadfile
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Plugin](https://pytest-cov.readthedocs.io/)
- [pytest-xdist Plugin](https://pytest-xdist.readthedocs.io/)
- [pytest-timeout Plugin](https://github.com/pytest-dev/pytest-timeout)
