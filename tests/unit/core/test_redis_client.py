"""
Unit tests for Redis client module.

Tests RedisClient functionality with mocked Redis.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from app.core.redis_client import (
    RedisSettings,
    RedisClient,
    get_redis,
)


class TestRedisSettings:
    """Test RedisSettings class."""

    def test_default_settings(self, monkeypatch):
        """Test default Redis settings.

        Hermetic: ignore a developer's .env (which sets REDIS_HOST=redis for
        docker) and any REDIS_* env so the DEFAULTS are what's asserted. The
        env-override path is covered by test_environment_override.
        """
        for k in list(os.environ):
            if k.startswith("REDIS_"):
                monkeypatch.delenv(k, raising=False)
        settings = RedisSettings(_env_file=None)

        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.password is None
        assert settings.db == 0
        assert settings.max_connections == 50
        assert settings.socket_timeout == 5

    @patch.dict("os.environ", {
        "REDIS_HOST": "redis-server",
        "REDIS_PORT": "6380",
        "REDIS_PASSWORD": "secret",
        "REDIS_MAX_CONNECTIONS": "100",
    })
    def test_environment_override(self):
        """Test environment variable override."""
        settings = RedisSettings()

        assert settings.host == "redis-server"
        assert settings.port == 6380
        assert settings.password == "secret"
        assert settings.max_connections == 100


class TestRedisClient:
    """Test RedisClient class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        with patch("app.core.redis_client.Redis") as mock:
            yield mock

    @pytest.fixture
    def mock_connection_pool(self):
        """Create mock connection pool."""
        with patch("app.core.redis_client.ConnectionPool") as mock:
            yield mock

    @pytest.fixture
    def redis_client(self, mock_redis, mock_connection_pool):
        """Create RedisClient instance with mocked dependencies."""
        settings = RedisSettings()
        client = RedisClient(settings)
        return client

    def test_initialization(self, redis_client):
        """Test RedisClient initialization."""
        assert redis_client.settings is not None
        assert redis_client.pool is not None
        assert redis_client.client is not None

    def test_get_success(self, redis_client):
        """Test successful get operation."""
        test_data = {"name": "Alice", "age": 30}
        redis_client.client.get = Mock(return_value=json.dumps(test_data))

        result = redis_client.get("user:123")

        assert result == test_data
        redis_client.client.get.assert_called_once_with("user:123")

    def test_get_not_found(self, redis_client):
        """Test get operation when key doesn't exist."""
        redis_client.client.get = Mock(return_value=None)

        result = redis_client.get("nonexistent")

        assert result is None

    def test_get_json_decode_error(self, redis_client):
        """Test get operation with invalid JSON."""
        redis_client.client.get = Mock(return_value="invalid json")

        result = redis_client.get("bad_key")

        assert result is None

    def test_set_success(self, redis_client):
        """Test successful set operation."""
        redis_client.client.set = Mock(return_value=True)

        test_data = {"name": "Bob", "score": 95}
        result = redis_client.set("user:456", test_data)

        assert result is True
        redis_client.client.set.assert_called_once()

    def test_set_with_ttl(self, redis_client):
        """Test set operation with TTL."""
        redis_client.client.setex = Mock(return_value=True)

        test_data = {"session": "abc123"}
        result = redis_client.set("session:xyz", test_data, ttl=3600)

        assert result is True
        redis_client.client.setex.assert_called_once_with(
            "session:xyz",
            3600,
            json.dumps(test_data)
        )

    def test_delete_single_key(self, redis_client):
        """Test delete operation with single key."""
        redis_client.client.delete = Mock(return_value=1)

        result = redis_client.delete("key1")

        assert result == 1
        redis_client.client.delete.assert_called_once_with("key1")

    def test_delete_multiple_keys(self, redis_client):
        """Test delete operation with multiple keys."""
        redis_client.client.delete = Mock(return_value=3)

        result = redis_client.delete("key1", "key2", "key3")

        assert result == 3
        redis_client.client.delete.assert_called_once_with("key1", "key2", "key3")

    def test_exists(self, redis_client):
        """Test exists operation."""
        redis_client.client.exists = Mock(return_value=2)

        result = redis_client.exists("key1", "key2")

        assert result == 2
        redis_client.client.exists.assert_called_once_with("key1", "key2")

    def test_expire(self, redis_client):
        """Test expire operation."""
        redis_client.client.expire = Mock(return_value=True)

        result = redis_client.expire("key1", 300)

        assert result is True
        redis_client.client.expire.assert_called_once_with("key1", 300)

    def test_incr(self, redis_client):
        """Test increment operation."""
        redis_client.client.incrby = Mock(return_value=5)

        result = redis_client.incr("counter", amount=2)

        assert result == 5
        redis_client.client.incrby.assert_called_once_with("counter", 2)

    def test_rate_limit_check_within_limit(self, redis_client):
        """Test rate limit check when within limit."""
        redis_client.client.incrby = Mock(return_value=5)
        redis_client.client.expire = Mock(return_value=True)

        result = redis_client.rate_limit_check("rate:user:123", limit=10, window_seconds=60)

        assert result is True  # 5 <= 10

    def test_rate_limit_check_exceeds_limit(self, redis_client):
        """Test rate limit check when limit exceeded."""
        redis_client.client.incrby = Mock(return_value=15)

        result = redis_client.rate_limit_check("rate:user:123", limit=10, window_seconds=60)

        assert result is False  # 15 > 10

    def test_rate_limit_check_first_request(self, redis_client):
        """Test rate limit check on first request (sets expiry)."""
        redis_client.client.incrby = Mock(return_value=1)
        redis_client.client.expire = Mock(return_value=True)

        result = redis_client.rate_limit_check("rate:user:456", limit=10, window_seconds=60)

        assert result is True
        redis_client.client.expire.assert_called_once_with("rate:user:456", 60)

    def test_health_check_success(self, redis_client):
        """Test successful health check."""
        redis_client.client.ping = Mock(return_value=True)

        result = redis_client.health_check()

        assert result is True
        redis_client.client.ping.assert_called_once()

    def test_health_check_failure(self, redis_client):
        """Test failed health check."""
        from redis.exceptions import RedisError
        redis_client.client.ping = Mock(side_effect=RedisError("Connection failed"))

        result = redis_client.health_check()

        assert result is False


class TestGetRedis:
    """Test get_redis function."""

    def test_returns_redis_client(self):
        """Test that function returns RedisClient instance."""
        with patch("app.core.redis_client.RedisClient"):
            client = get_redis()

            assert client is not None

    def test_singleton_pattern(self):
        """Test that get_redis returns the same instance."""
        with patch("app.core.redis_client.RedisClient") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            # Reset singleton
            import app.core.redis_client as redis_module
            redis_module._redis_client = None

            client1 = get_redis()
            client2 = get_redis()

            # Should return same instance
            assert client1 is client2
            # Should only create once
            assert mock_client.call_count == 1


@pytest.mark.integration
@pytest.mark.skipif(
    True,  # Integration tests require a running Redis server
    reason="Integration tests disabled by default (set RUN_INTEGRATION=1 to enable)"
)
class TestRedisClientIntegration:
    """Integration tests with real Redis (requires Redis running)."""

    @pytest.fixture
    def real_redis_client(self):
        """Create RedisClient connected to real Redis."""
        settings = RedisSettings(db=15)  # Use separate test DB
        client = RedisClient(settings)

        yield client

        # Cleanup
        client.client.flushdb()
        client.close()

    def test_set_get_integration(self, real_redis_client):
        """Test set and get with real Redis."""
        test_data = {"test": "data", "number": 42}

        # Set
        result = real_redis_client.set("test:key", test_data)
        assert result is True

        # Get
        retrieved = real_redis_client.get("test:key")
        assert retrieved == test_data

    def test_rate_limiting_integration(self, real_redis_client):
        """Test rate limiting with real Redis."""
        key = "rate:test:user"

        # First 5 requests should pass
        for i in range(5):
            result = real_redis_client.rate_limit_check(key, limit=5, window_seconds=60)
            assert result is True

        # 6th request should fail
        result = real_redis_client.rate_limit_check(key, limit=5, window_seconds=60)
        assert result is False
