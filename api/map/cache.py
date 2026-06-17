"""
In-memory TTL cache and session store for map API endpoints.
"""

import time
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Simple in-memory TTL cache for weather / layer data
# ---------------------------------------------------------------------------
_cache: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str, ttl_seconds: int = 21600) -> Optional[Any]:
    """Return cached value if it exists and has not expired."""
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl_seconds:
        return entry["value"]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = {"value": value, "ts": time.time()}


# ---------------------------------------------------------------------------
# In-memory session store for enhanced /query follow-ups
# ---------------------------------------------------------------------------
_query_sessions: Dict[str, Dict[str, Any]] = {}
