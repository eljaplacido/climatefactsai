"""
Database Module

Wraps shared.database and provides domain-friendly interface.
"""

from shared.database import (
    get_postgres,
    PostgresClient,
)

__all__ = [
    "get_db",
    "Database",
    "Base",
    "PostgresClient",
]

# Type alias for cleaner domain code
Database = PostgresClient
Base = PostgresClient.Base


def get_db() -> PostgresClient:
    """
    Get database instance for dependency injection.
    
    Usage in FastAPI:
        from fastapi import Depends
        from app.core import Database, get_db
        
        @router.get("/")
        async def endpoint(db: Database = Depends(get_db)):
            result = db.fetch_one("SELECT * FROM articles")
    
    Returns:
        Database: PostgreSQL database instance
    """
    return get_postgres()

