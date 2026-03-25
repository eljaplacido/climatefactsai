"""
Tietokantayhteydet: Redis (lyhytaikainen) ja PostgreSQL (pitkäaikainen muisti)

Tarjoaa yhtenäisen rajapinnan tietokantojen kanssa kommunikointiin.
"""

import json
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager, contextmanager
from datetime import timedelta

import redis
from redis import Redis, ConnectionPool
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from .config import get_redis_settings, get_postgres_settings
from .logger import LoggerMixin


class RedisClient(LoggerMixin):
    """
    Redis-asiakasluokka lyhytaikaiseen muistiin (state management)
    
    Käyttö:
        redis_client = RedisClient()
        redis_client.set_task_state("task-123", {"status": "IN_PROGRESS"})
        state = redis_client.get_task_state("task-123")
    """
    
    def __init__(self):
        """Alusta Redis-yhteys"""
        self.setup_logger("redis_client")
        self.settings = get_redis_settings()
        
        # Luo connection pool
        self.pool = ConnectionPool(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
            password=self.settings.redis_password,
            db=self.settings.redis_db,
            decode_responses=True,  # Automaattinen UTF-8 dekoodaus
            max_connections=20
        )
        
        self.client: Redis = redis.Redis(connection_pool=self.pool)
        
        # Testaa yhteys
        try:
            self.client.ping()
            self.logger.info(
                "Redis connection established",
                host=self.settings.redis_host,
                port=self.settings.redis_port
            )
        except redis.ConnectionError as e:
            self.log_error(e, context={"host": self.settings.redis_host})
            raise
    
    def _task_key(self, task_id: str) -> str:
        """Generoi task-spesifinen Redis-avain"""
        return f"task:{task_id}"
    
    def _agent_state_key(self, agent_name: str, task_id: str) -> str:
        """Generoi agentti-spesifinen tila-avain"""
        return f"agent:{agent_name}:task:{task_id}"
    
    def set_task_state(
        self,
        task_id: str,
        state: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Tallenna tehtävän tila Redisiin
        
        Args:
            task_id: Tehtävätunniste
            state: Tila-dictionary
            ttl_seconds: Time-to-live sekunteina (oletus: 24h)
        
        Returns:
            True jos onnistui
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
        """
        Hae tehtävän tila Redisistä
        
        Args:
            task_id: Tehtävätunniste
        
        Returns:
            Tila-dictionary tai None jos ei löydy
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
        """
        Päivitä tehtävän tilaa (merge-operaatio)
        
        Args:
            task_id: Tehtävätunniste
            updates: Päivitettävät kentät
        
        Returns:
            True jos onnistui
        """
        current_state = self.get_task_state(task_id) or {}
        current_state.update(updates)
        return self.set_task_state(task_id, current_state)
    
    def delete_task_state(self, task_id: str) -> bool:
        """
        Poista tehtävän tila
        
        Args:
            task_id: Tehtävätunniste
        
        Returns:
            True jos onnistui
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
        """Generinen set-operaatio TTL:llä"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            self.client.setex(key, expire_seconds, value)
            return True
        except Exception as e:
            self.log_error(e, context={"key": key})
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Generinen get-operaatio"""
        try:
            value = self.client.get(key)
            if value:
                # Yritä parsea JSON:iksi
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            self.log_error(e, context={"key": key})
            return None
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Inkrementoi laskuria"""
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            self.log_error(e, context={"key": key})
            return None
    
    def close(self):
        """Sulje Redis-yhteys"""
        self.client.close()
        self.logger.info("Redis connection closed")


class PostgresClient(LoggerMixin):
    """
    PostgreSQL-asiakasluokka pitkäaikaiseen muistiin
    
    Käyttö:
        db = PostgresClient()
        with db.session() as session:
            result = session.execute(text("SELECT * FROM articles"))
    """
    
    def __init__(self, echo: bool = False):
        """
        Alusta PostgreSQL-yhteys
        
        Args:
            echo: Tulosta SQL-kyselyt (kehitystilassa)
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
        """
        Context manager tietokantasessiolle
        
        Käyttö:
            with db.session() as session:
                result = session.execute(...)
                session.commit()
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
        """
        Suorita SELECT-kysely ja palauta tulokset
        
        Args:
            query: SQL-kysely
            params: Kyselyn parametrit
        
        Returns:
            Lista tuloksista dictionary-muodossa
        """
        with self.session() as session:
            result = session.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    
    def execute_update(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Suorita INSERT/UPDATE/DELETE-kysely
        
        Args:
            query: SQL-kysely
            params: Kyselyn parametrit
        
        Returns:
            Muutettujen rivien määrä
        """
        with self.session() as session:
            result = session.execute(text(query), params or {})
            session.commit()
            return result.rowcount
    
    def close(self):
        """Sulje tietokantayhteydet"""
        self.engine.dispose()
        self.logger.info("PostgreSQL connections closed")


# Globaalit singleton-instanssit
_redis_client: Optional[RedisClient] = None
_postgres_client: Optional[PostgresClient] = None


def get_redis() -> RedisClient:
    """Palauta singleton Redis-asiakas"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def get_postgres() -> PostgresClient:
    """Palauta singleton PostgreSQL-asiakas"""
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

