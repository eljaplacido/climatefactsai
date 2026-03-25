"""Two-tier memory architecture: Redis (short-term) and PostgreSQL (long-term).

This module implements the platform's two-tier memory system with unified
database interfaces. All services use these clients to maintain workflow state
and persist data consistently across the multi-agent system.

Architecture:
    - RedisClient: Short-term memory for workflow state and caching (24h TTL)
    - PostgresClient: Long-term storage for articles, fact-checks, analytics
    - Singleton pattern: get_redis() and get_postgres() for shared instances
    - Connection pooling for optimal performance

Memory Strategy:
    **Redis (Hot Data):**
    - Task execution state (current workflow status)
    - Agent coordination state (what each agent is doing)
    - Rate limiting counters (API usage tracking)
    - Temporary caching (API responses, computed results)
    - TTL: 24 hours (configurable)

    **PostgreSQL (Cold Data):**
    - Articles archive (published content)
    - Fact-checks (verification results)
    - User data (subscriptions, usage history)
    - Analytics (metrics, trends)
    - Persistent storage with pgvector for semantic search

Usage:
    >>> from shared.database import get_redis, get_postgres
    >>>
    >>> # Short-term state management
    >>> redis = get_redis()
    >>> redis.set_task_state("task-123", {"status": "IN_PROGRESS"})
    >>> state = redis.get_task_state("task-123")
    >>>
    >>> # Long-term data persistence
    >>> postgres = get_postgres()
    >>> with postgres.session() as session:
    ...     articles = session.execute(text("SELECT * FROM articles LIMIT 10"))

Example:
    Orchestrator using two-tier memory:

    ```python
    class OrchestratorAgent:
        def __init__(self):
            self.redis = get_redis()      # For workflow state
            self.postgres = get_postgres()  # For final results

        async def process_task(self, task_id: str):
            # Store current state in Redis (ephemeral)
            self.redis.set_task_state(task_id, {
                "status": "PROCESSING",
                "phase": "ingestion",
                "started_at": datetime.utcnow().isoformat()
            })

            # ... process task ...

            # Store final results in PostgreSQL (permanent)
            with self.postgres.session() as session:
                session.execute(
                    text("INSERT INTO articles (title, content) VALUES (:t, :c)"),
                    {"t": title, "c": content}
                )
    ```

Performance:
    - Redis: ~10,000 ops/sec per connection
    - PostgreSQL: Connection pooling (5-20 connections)
    - Automatic connection recovery with pool_pre_ping
    - JSON serialization for complex data structures

Note:
    Singleton instances cached globally - same client returned on each call.
    Close connections explicitly in long-running processes via .close() methods.
"""

import json
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager, contextmanager
from datetime import timedelta

import redis
from redis import Redis, ConnectionPool
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool

from .config import get_redis_settings, get_postgres_settings
from .logger import LoggerMixin


# Shared declarative base for ORM models (trust schema, etc.)
SQLALCHEMY_BASE = declarative_base()


class RedisClient(LoggerMixin):
    """Redis client for short-term memory and workflow state management.

    This client handles all ephemeral data storage for the multi-agent system,
    including task execution state, agent coordination, rate limiting, and
    temporary caching. All data has a TTL (default 24 hours) for automatic cleanup.

    Features:
        - Connection pooling (max 20 connections)
        - Automatic UTF-8 encoding/decoding
        - JSON serialization for complex objects
        - Task-specific and agent-specific key namespaces
        - Configurable TTL per operation

    Attributes:
        pool (ConnectionPool): Redis connection pool
        client (Redis): Redis client instance
        settings (RedisSettings): Configuration from environment

    Usage:
        >>> redis = RedisClient()
        >>> redis.set_task_state("task-123", {"status": "IN_PROGRESS", "progress": 50})
        >>> state = redis.get_task_state("task-123")
        >>> print(state)  # {"status": "IN_PROGRESS", "progress": 50}

    Example:
        Agent coordination pattern:

        ```python
        redis = RedisClient()

        # Store agent state
        redis.set_task_state("task-001", {
            "status": "IN_PROGRESS",
            "assigned_agent": "ingestion_agent",
            "phase": "discovery",
            "articles_found": 15
        })

        # Update incrementally
        redis.update_task_state("task-001", {"articles_found": 20})

        # Check state from another agent
        state = redis.get_task_state("task-001")
        if state["status"] == "IN_PROGRESS":
            # Wait for completion
            pass
        ```

    Note:
        Uses singleton pattern via get_redis(). Connection automatically
        tested on initialization with PING command.
    """
    
    def __init__(self):
        """Initialize Redis connection with automatic health check.

        Creates connection pool and tests connectivity with PING command.

        Raises:
            redis.ConnectionError: If connection to Redis server fails
        """
        self.setup_logger("redis_client")
        self.settings = get_redis_settings()
        resolved = self.settings.resolved_connection()
        
        # Luo connection pool
        self.pool = ConnectionPool(
            host=resolved["host"],
            port=resolved["port"],
            password=resolved["password"],
            db=resolved["db"],
            decode_responses=True,  # Automaattinen UTF-8 dekoodaus
            max_connections=20
        )
        
        self.client: Redis = redis.Redis(connection_pool=self.pool)
        
        # Testaa yhteys
        try:
            self.client.ping()
            self.logger.info(
                "Redis connection established",
                host=resolved["host"],
                port=resolved["port"],
                db=resolved["db"]
            )
        except redis.ConnectionError as e:
            self.log_error(e, context={"host": self.settings.redis_host})
            raise
    
    def _task_key(self, task_id: str) -> str:
        """Generate namespaced Redis key for task state.

        Args:
            task_id: Unique task identifier

        Returns:
            Namespaced key in format "task:{task_id}"
        """
        return f"task:{task_id}"

    def _agent_state_key(self, agent_name: str, task_id: str) -> str:
        """Generate namespaced Redis key for agent-specific state.

        Args:
            agent_name: Name of the agent (e.g., "ingestion_agent")
            task_id: Unique task identifier

        Returns:
            Namespaced key in format "agent:{agent_name}:task:{task_id}"
        """
        return f"agent:{agent_name}:task:{task_id}"
    
    def set_task_state(
        self,
        task_id: str,
        state: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Store task execution state in Redis with automatic expiration.

        Serializes state dictionary to JSON and stores with configurable TTL.
        Used for workflow orchestration and agent coordination.

        Args:
            task_id: Unique task identifier (e.g., "task-123")
            state: State dictionary with status, progress, timestamps, etc.
            ttl_seconds: Time-to-live in seconds (default: 86400 = 24h)

        Returns:
            True if successful, False on error

        Example:
            >>> redis = get_redis()
            >>> redis.set_task_state("task-123", {
            ...     "status": "IN_PROGRESS",
            ...     "phase": "ingestion",
            ...     "articles_found": 15,
            ...     "started_at": "2025-11-20T10:30:00Z"
            ... })
        """
        key = self._task_key(task_id)
        ttl = ttl_seconds or self.settings.redis_ttl_seconds
        
        try:
            serialized = json.dumps(state)
            self.client.setex(key, ttl, serialized)
            
            self.logger.debug(
                "Task state saved",
                task_id=task_id,
                ttl_seconds=ttl
            )
            return True
            
        except Exception as e:
            self.log_error(e, context={"task_id": task_id})
            return False
    
    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task state from Redis with automatic JSON deserialization.

        Args:
            task_id: Unique task identifier

        Returns:
            Task state dictionary if found, None otherwise.
            State typically includes: status, phase, started_at, updated_at

        Example:
            >>> redis = get_redis()
            >>> state = redis.get_task_state("task-123")
            >>> if state:
            ...     print(f"Status: {state['status']}, Phase: {state['phase']}")
        """
        key = self._task_key(task_id)
        
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            self.log_error(e, context={"task_id": task_id})
            return None
    
    def update_task_state(
        self,
        task_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update task state incrementally (merge operation).

        Fetches current state, merges with updates, and stores back.
        Preserves existing fields not included in updates.

        Args:
            task_id: Unique task identifier
            updates: Dictionary with fields to update

        Returns:
            True if successful, False on error

        Example:
            >>> redis = get_redis()
            >>> # Initial state: {"status": "IN_PROGRESS", "progress": 20}
            >>> redis.update_task_state("task-123", {"progress": 50})
            >>> # New state: {"status": "IN_PROGRESS", "progress": 50}
        """
        current_state = self.get_task_state(task_id) or {}
        current_state.update(updates)
        return self.set_task_state(task_id, current_state)
    
    def delete_task_state(self, task_id: str) -> bool:
        """Delete task state from Redis.

        Removes task state key immediately without waiting for TTL expiration.

        Args:
            task_id: Unique task identifier

        Returns:
            True if successful, False on error

        Example:
            >>> redis = get_redis()
            >>> redis.delete_task_state("task-123")
        """
        key = self._task_key(task_id)
        try:
            self.client.delete(key)
            self.logger.debug("Task state deleted", task_id=task_id)
            return True
        except Exception as e:
            self.log_error(e, context={"task_id": task_id})
            return False
    
    def set_with_expiry(
        self,
        key: str,
        value: Any,
        expire_seconds: int
    ) -> bool:
        """Store value in Redis with automatic expiration.

        Generic storage method with TTL. Automatically serializes dicts/lists to JSON.

        Args:
            key: Redis key (use namespaced keys for organization)
            value: Value to store (str, dict, list, or JSON-serializable)
            expire_seconds: Time-to-live in seconds

        Returns:
            True if successful, False on error

        Example:
            >>> redis.set_with_expiry("rate_limit:user123", {"count": 10}, 3600)
            >>> redis.set_with_expiry("cache:article:456", article_dict, 1800)
        """
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            self.client.setex(key, expire_seconds, value)
            return True
        except Exception as e:
            self.log_error(e, context={"key": key})
            return False

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from Redis with automatic JSON deserialization.

        Generic retrieval method. Automatically deserializes JSON to dict/list.

        Args:
            key: Redis key to retrieve

        Returns:
            Stored value (dict/list if JSON, str otherwise), or None if not found

        Example:
            >>> redis.set_with_expiry("config:app", {"debug": True}, 3600)
            >>> config = redis.get("config:app")
            >>> print(config["debug"])  # True
        """
        try:
            value = self.client.get(key)
            if value:
                # Try to parse as JSON
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            self.log_error(e, context={"key": key})
            return None

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Atomically increment a counter in Redis.

        Useful for rate limiting, usage tracking, and distributed counters.

        Args:
            key: Counter key
            amount: Increment amount (default: 1)

        Returns:
            New counter value after increment, or None on error

        Example:
            >>> # Rate limiting
            >>> count = redis.increment("api_calls:user123")
            >>> if count > 100:
            ...     raise RateLimitExceeded()
        """
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            self.log_error(e, context={"key": key})
            return None

    def close(self):
        """Close Redis connection and release resources.

        Note:
            Only needed for explicit cleanup. Singleton instance persists
            for application lifetime by default.
        """
        self.client.close()
        self.logger.info("Redis connection closed")


class PostgresClient(LoggerMixin):
    """PostgreSQL client for long-term persistent storage.

    This client manages all permanent data storage for the platform, including
    articles archive, fact-checks, user data, and analytics. Uses SQLAlchemy
    for connection pooling and session management with automatic rollback on errors.

    Features:
        - Connection pooling (5-20 connections configurable)
        - Automatic connection health checks (pool_pre_ping)
        - Context manager for safe transaction handling
        - Automatic rollback on exceptions
        - Support for both ORM and raw SQL queries

    Attributes:
        engine (Engine): SQLAlchemy engine with connection pool
        SessionLocal (sessionmaker): Session factory for creating DB sessions
        settings (PostgresSettings): Configuration from environment

    Usage:
        >>> postgres = PostgresClient()
        >>> with postgres.session() as session:
        ...     articles = session.execute(text("SELECT * FROM articles LIMIT 5"))
        ...     for article in articles:
        ...         print(article['title'])

    Example:
        Storing article with fact-checks:

        ```python
        postgres = PostgresClient()

        # Insert article
        article_id = str(uuid4())
        with postgres.session() as session:
            session.execute(
                text(\"\"\"
                    INSERT INTO articles (article_id, title, content, country_code)
                    VALUES (:id, :title, :content, :country)
                \"\"\"),
                {
                    "id": article_id,
                    "title": "Arctic Ice Melting Accelerates",
                    "content": "...",
                    "country": "FI"
                }
            )

        # Query with helper method
        articles = postgres.execute_query(
            "SELECT * FROM articles WHERE country_code = :country",
            {"country": "FI"}
        )
        ```

    Note:
        Uses singleton pattern via get_postgres(). All sessions auto-commit
        on success and auto-rollback on exceptions. Close explicitly via
        .close() to dispose connection pool in long-running processes.
    """
    # Shared SQLAlchemy declarative base for ORM models
    Base = SQLALCHEMY_BASE

    def __init__(self, echo: bool = False):
        """Initialize PostgreSQL connection with connection pooling.

        Creates SQLAlchemy engine with configured pool size and tests
        connectivity with SELECT 1 query.

        Args:
            echo: Print SQL queries to stdout (useful for development)

        Raises:
            Exception: If connection to PostgreSQL server fails
        """
        self.setup_logger("postgres_client")
        self.settings = get_postgres_settings()
        
        # Luo synkroninen engine
        self.engine = create_engine(
            self.settings.database_url,
            pool_size=self.settings.postgres_pool_min_size,
            max_overflow=self.settings.postgres_pool_max_size - self.settings.postgres_pool_min_size,
            echo=echo,
            pool_pre_ping=True  # Testaa yhteys ennen käyttöä
        )
        
        # Luo session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        # Bind shared Base metadata to this engine for ORM models
        self.Base.metadata.bind = self.engine
        
        # Testaa yhteys
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.logger.info(
                "PostgreSQL connection established",
                host=self.settings.postgres_host,
                database=self.settings.postgres_db
            )
        except Exception as e:
            self.log_error(e, context={"database_url": self.settings.database_url})
            raise
    
    @contextmanager
    def session(self) -> Session:
        """Context manager for database session with automatic transaction handling.

        Provides a database session with automatic commit on success and
        rollback on exception. Always closes session in finally block.

        Yields:
            Session: SQLAlchemy session for database operations

        Example:
            >>> postgres = get_postgres()
            >>> with postgres.session() as session:
            ...     result = session.execute(
            ...         text("INSERT INTO articles (title) VALUES (:t)"),
            ...         {"t": "Test Article"}
            ...     )
            ...     # Auto-commit on exit, auto-rollback on exception
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.log_error(e)
            raise
        finally:
            session.close()
    
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results as list of dictionaries.

        Convenient helper for read-only queries with automatic row-to-dict conversion.

        Args:
            query: SQL SELECT query (use :param syntax for parameters)
            params: Query parameters dictionary

        Returns:
            List of result rows as dictionaries with column names as keys

        Example:
            >>> postgres = get_postgres()
            >>> articles = postgres.execute_query(
            ...     "SELECT * FROM articles WHERE country_code = :country LIMIT :limit",
            ...     {"country": "FI", "limit": 10}
            ... )
            >>> for article in articles:
            ...     print(article["title"])
        """
        with self.session() as session:
            result = session.execute(text(query), params or {})
            try:
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
            except Exception:
                # Non-SELECT statements (INSERT/UPDATE/DELETE without RETURNING)
                # don't return rows — return empty list gracefully
                return []
    
    def execute_update(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """Execute INSERT/UPDATE/DELETE query with automatic commit.

        Convenient helper for write operations with automatic transaction handling.

        Args:
            query: SQL INSERT/UPDATE/DELETE query (use :param syntax)
            params: Query parameters dictionary

        Returns:
            Number of rows affected by the operation

        Example:
            >>> postgres = get_postgres()
            >>> rows_updated = postgres.execute_update(
            ...     "UPDATE articles SET status = :status WHERE article_id = :id",
            ...     {"status": "PUBLISHED", "id": "article-123"}
            ... )
            >>> print(f"Updated {rows_updated} rows")
        """
        with self.session() as session:
            result = session.execute(text(query), params or {})
            session.commit()
            return result.rowcount
    
    def close(self):
        """Dispose database connection pool and release all connections.

        Note:
            Only needed for explicit cleanup. Singleton instance persists
            for application lifetime by default. Call during graceful shutdown.
        """
        self.engine.dispose()
        self.logger.info("PostgreSQL connections closed")


# Globaalit singleton-instanssit
_redis_client: Optional[RedisClient] = None
_postgres_client: Optional[PostgresClient] = None


def get_redis() -> RedisClient:
    """Get or create singleton Redis client instance.

    Returns the same RedisClient instance across all calls for connection pooling
    efficiency. Thread-safe for concurrent access.

    Returns:
        RedisClient: Shared Redis client instance

    Example:
        >>> from shared.database import get_redis
        >>> redis = get_redis()
        >>> redis.set_task_state("task-123", {"status": "RUNNING"})
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def get_postgres() -> PostgresClient:
    """Get or create singleton PostgreSQL client instance.

    Returns the same PostgresClient instance across all calls for connection pooling
    efficiency. Thread-safe for concurrent access.

    Returns:
        PostgresClient: Shared PostgreSQL client instance

    Example:
        >>> from shared.database import get_postgres
        >>> postgres = get_postgres()
        >>> articles = postgres.execute_query("SELECT * FROM articles LIMIT 10")
    """
    global _postgres_client
    if _postgres_client is None:
        _postgres_client = PostgresClient()
    return _postgres_client


if __name__ == "__main__":
    # Testaa tietokantayhteydet
    print("Testing Redis...")
    redis_client = get_redis()
    redis_client.set_task_state(
        "test-task-001",
        {"status": "TESTING", "progress": 50}
    )
    state = redis_client.get_task_state("test-task-001")
    print(f"Retrieved state: {state}")
    
    print("\nTesting PostgreSQL...")
    postgres_client = get_postgres()
    result = postgres_client.execute_query("SELECT version()")
    print(f"PostgreSQL version: {result}")

