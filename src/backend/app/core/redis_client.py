"""
Redis Client Module

Provides Redis connection management for caching and session storage.
Used alongside Celery (which uses Redis as broker) for application-level caching.
"""

from typing import Optional, Any
import json
from redis import Redis, ConnectionPool
from redis.exceptions import RedisError
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    """Redis configuration settings.

    2026-06-10 audit fix: the per-field ``Field(env="REDIS_HOST")`` syntax is
    a pydantic-v1 idiom that pydantic-settings v2 SILENTLY IGNORES — so
    REDIS_HOST/PORT/PASSWORD env vars never overrode the defaults and Redis
    always pointed at localhost:6379. Use ``env_prefix`` instead: the field
    names below map to REDIS_HOST, REDIS_PORT, … exactly as before.
    """

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        extra="ignore",  # Allow extra env vars
    )

    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0

    # Connection pool settings
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True


class RedisClient:
    """Redis client wrapper with connection pooling and error handling.

    Provides high-level methods for caching, session storage, and rate limiting.
    Separate from Celery's Redis usage (Celery uses DB 0 for broker, DB 1 for results).

    Usage:
        >>> redis = RedisClient()
        >>> redis.set("user:123", {"name": "Alice"}, ttl=3600)
        >>> user = redis.get("user:123")
    """

    def __init__(self, settings: Optional[RedisSettings] = None):
        """Initialize Redis client with connection pool.

        Args:
            settings: Optional RedisSettings instance. If None, loads from env.
        """
        self.settings = settings or RedisSettings()

        # Create connection pool
        self.pool = ConnectionPool(
            host=self.settings.host,
            port=self.settings.port,
            password=self.settings.password,
            db=self.settings.db,
            max_connections=self.settings.max_connections,
            socket_timeout=self.settings.socket_timeout,
            socket_connect_timeout=self.settings.socket_connect_timeout,
            retry_on_timeout=self.settings.retry_on_timeout,
            decode_responses=True,  # Auto-decode bytes to strings
        )

        self.client = Redis(connection_pool=self.pool)

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis and deserialize JSON.

        Args:
            key: Redis key

        Returns:
            Deserialized value or None if not found
        """
        try:
            value = self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except (RedisError, json.JSONDecodeError) as e:
            print(f"Redis GET error for key {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in Redis with JSON serialization.

        Args:
            key: Redis key
            value: Value to store (will be JSON serialized)
            ttl: Time-to-live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            serialized = json.dumps(value)
            if ttl:
                return self.client.setex(key, ttl, serialized)
            return self.client.set(key, serialized)
        except (RedisError, TypeError) as e:
            print(f"Redis SET error for key {key}: {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Delete one or more keys.

        Args:
            *keys: Redis keys to delete

        Returns:
            Number of keys deleted
        """
        try:
            return self.client.delete(*keys)
        except RedisError as e:
            print(f"Redis DELETE error: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """Check if keys exist.

        Args:
            *keys: Redis keys to check

        Returns:
            Number of keys that exist
        """
        try:
            return self.client.exists(*keys)
        except RedisError as e:
            print(f"Redis EXISTS error: {e}")
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key.

        Args:
            key: Redis key
            seconds: TTL in seconds

        Returns:
            True if expiration set, False otherwise
        """
        try:
            return self.client.expire(key, seconds)
        except RedisError as e:
            print(f"Redis EXPIRE error for key {key}: {e}")
            return False

    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a key's value.

        Args:
            key: Redis key
            amount: Amount to increment by (default 1)

        Returns:
            New value after increment, or None on error
        """
        try:
            return self.client.incrby(key, amount)
        except RedisError as e:
            print(f"Redis INCR error for key {key}: {e}")
            return None

    def rate_limit_check(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> bool:
        """Check if rate limit is exceeded using sliding window.

        Args:
            key: Rate limit key (e.g., "rate_limit:user:123:api_calls")
            limit: Maximum number of requests
            window_seconds: Time window in seconds

        Returns:
            True if within rate limit, False if exceeded
        """
        try:
            count = self.incr(key)
            if count == 1:
                self.expire(key, window_seconds)
            return count <= limit
        except Exception as e:
            print(f"Rate limit check error for key {key}: {e}")
            return True  # Fail open

    def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if Redis is reachable, False otherwise
        """
        try:
            return self.client.ping()
        except RedisError:
            return False

    def close(self):
        """Close Redis connection pool."""
        self.pool.disconnect()


# Global Redis client instance (lazy initialization)
_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """Get global Redis client instance.

    Returns:
        Shared RedisClient instance for dependency injection.

    Usage:
        >>> redis = get_redis()
        >>> redis.set("key", "value")
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
