"""
Rate Limiting Middleware
Enforces usage limits based on subscription tiers
"""

from datetime import datetime, date
from typing import Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from shared.database import get_postgres, get_redis
from shared.logger import setup_logging


logger = setup_logging("rate_limiter")


# Subscription tier limits
# Tiers: freemium (free), standard (10 EUR/mo), professional (20 EUR/mo)
TIER_LIMITS = {
    "freemium": {
        "articles_per_day": 10,
        "url_analyses_per_month": 0,
        "api_calls_per_day": 0,
        "searches_per_day": 10,
        "discovery_queries_per_day": 1,
        "countries_limit": 3,
        "auto_update_frequency": "weekly",
        "qa_per_article_per_day": 2,
        "infographics": False,
        "data_source_tiers": ["public"],
        "export_formats": [],
        "advanced_insights": False,
    },
    "standard": {
        "articles_per_day": 100,
        "url_analyses_per_month": 5,
        "api_calls_per_day": 0,
        "searches_per_day": 25,
        "discovery_queries_per_day": 5,
        "countries_limit": 5,
        "auto_update_frequency": "daily",
        "qa_per_article_per_day": 10,
        "infographics": True,
        "data_source_tiers": ["public", "research"],
        "export_formats": ["csv"],
        "advanced_insights": False,
    },
    "professional": {
        "articles_per_day": None,  # Unlimited
        "url_analyses_per_month": None,  # Unlimited
        "api_calls_per_day": 1000,
        "searches_per_day": 50,
        "discovery_queries_per_day": 10,
        "countries_limit": 10,
        "auto_update_frequency": "daily",
        "qa_per_article_per_day": None,  # Unlimited
        "infographics": True,
        "data_source_tiers": ["public", "research", "scientific"],
        "export_formats": ["csv", "pdf"],
        "advanced_insights": True,
    },
    "enterprise": {
        "articles_per_day": None,  # Unlimited
        "url_analyses_per_month": None,  # Unlimited
        "api_calls_per_day": None,  # Unlimited
        "searches_per_day": None,  # Unlimited
        "discovery_queries_per_day": None,  # Unlimited
        "countries_limit": None,  # Unlimited
        "auto_update_frequency": "realtime",
        "qa_per_article_per_day": None,  # Unlimited
        "infographics": True,
        "data_source_tiers": ["public", "research", "scientific"],
        "export_formats": ["csv", "pdf", "json", "xml"],
        "advanced_insights": True,
        "custom_sources": None,  # Unlimited
    },
}

# Backwards-compatible alias: "basic" → "standard"
TIER_LIMITS["basic"] = TIER_LIMITS["standard"]


class UsageTracker:
    """Tracks and enforces usage limits"""

    @staticmethod
    def log_usage(
        user_id: str,
        usage_type: str,
        resource_id: Optional[str] = None,
        resource_url: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """Log a usage event to the database"""
        db = get_postgres()

        query = """
            INSERT INTO user_usage (
                user_id, usage_type, resource_id, resource_url,
                ip_address, user_agent, metadata
            )
            VALUES (
                :user_id, :usage_type, :resource_id, :resource_url,
                :ip_address, :user_agent, CAST(:metadata AS jsonb)
            )
        """

        import json

        db.execute_query(query, params={
            "user_id": user_id,
            "usage_type": usage_type,
            "resource_id": resource_id,
            "resource_url": resource_url,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "metadata": json.dumps(metadata or {})
        })

    @staticmethod
    def get_usage_count(
        user_id: str,
        usage_type: str,
        period: str = "day"  # "day" or "month"
    ) -> int:
        """Get usage count for a user in a time period"""
        db = get_postgres()

        if period == "day":
            time_filter = "DATE(created_at) = CURRENT_DATE"
        elif period == "month":
            time_filter = "DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)"
        else:
            time_filter = "TRUE"

        query = f"""
            SELECT COUNT(*) as count
            FROM user_usage
            WHERE user_id = :user_id
              AND usage_type = :usage_type
              AND {time_filter}
        """

        result = db.execute_query(query, params={
            "user_id": user_id,
            "usage_type": usage_type
        })

        return result[0]["count"] if result else 0

    @staticmethod
    def check_limit(
        user_id: str,
        subscription_tier: str,
        usage_type: str,
        period: str = "day"
    ) -> tuple[bool, int, Optional[int]]:
        """
        Check if user has exceeded their limit
        Returns (allowed, current_usage, limit)
        """
        limits = TIER_LIMITS.get(subscription_tier, TIER_LIMITS["freemium"])

        # Determine the limit key based on usage type and period
        if usage_type == "article_view":
            limit_key = "articles_per_day" if period == "day" else None
        elif usage_type == "url_analysis":
            limit_key = "url_analyses_per_month" if period == "month" else None
        elif usage_type == "api_call":
            limit_key = "api_calls_per_day" if period == "day" else None
        elif usage_type == "search":
            limit_key = "searches_per_day" if period == "day" else None
        elif usage_type == "discovery_query":
            limit_key = "discovery_queries_per_day" if period == "day" else None
        else:
            return True, 0, None  # Unknown type, allow

        if not limit_key or limits.get(limit_key) is None:
            # Unlimited for this tier
            current_usage = UsageTracker.get_usage_count(user_id, usage_type, period)
            return True, current_usage, None

        limit = limits[limit_key]
        current_usage = UsageTracker.get_usage_count(user_id, usage_type, period)

        allowed = current_usage < limit

        return allowed, current_usage, limit

    @staticmethod
    def check_discovery_limit(
        user_id: str,
        subscription_tier: str,
    ) -> tuple[bool, int, Optional[int]]:
        """Check if user has exceeded daily discovery query limit."""
        return UsageTracker.check_limit(user_id, subscription_tier, "discovery_query", "day")

    @staticmethod
    def check_country_access(
        subscription_tier: str,
        requested_countries: list[str],
    ) -> tuple[bool, int, Optional[int]]:
        """
        Check if user tier allows access to the requested countries.
        Returns (allowed, requested_count, limit).
        """
        limits = TIER_LIMITS.get(subscription_tier, TIER_LIMITS["freemium"])
        country_limit = limits.get("countries_limit")

        if country_limit is None:
            return True, len(requested_countries), None

        return len(requested_countries) <= country_limit, len(requested_countries), country_limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on API endpoints
    """

    def _check_ip_rate_limit(self, ip: str, usage_type: str, max_per_day: int):
        """Check and enforce IP-based rate limits for unauthenticated requests.

        Uses Redis-backed counters with automatic daily expiry.
        Falls back to allowing the request if Redis is unavailable.
        """
        today = date.today().isoformat()
        redis_key = f"ratelimit:ip:{ip}:{usage_type}:{today}"

        try:
            redis_client = get_redis()
            current = redis_client.increment(redis_key)

            if current is None:
                # Redis increment failed; allow request with warning
                logger.warning(
                    "Redis increment returned None, allowing request",
                    ip=ip, usage_type=usage_type
                )
                return

            # Set TTL on first increment (when counter is 1)
            if current == 1:
                try:
                    redis_client.client.expire(redis_key, 86400)
                except Exception as e:
                    logger.warning(f"Failed to set Redis TTL: {e}")

            if current > max_per_day:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Daily {usage_type} limit exceeded for anonymous users ({current}/{max_per_day}). Sign in for higher limits."
                )
        except HTTPException:
            raise
        except Exception as e:
            # Redis connection failure — allow the request but log a warning
            logger.warning(
                f"Redis unavailable for rate limiting, allowing request: {e}",
                ip=ip, usage_type=usage_type
            )

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for auth endpoints and health checks
        if request.url.path.startswith("/api/auth") or request.url.path in ["/", "/health", "/api/stats"]:
            return await call_next(request)

        # Get user from request state (set by auth dependency)
        user = getattr(request.state, "user", None)

        # For article views, enforce limits
        if request.url.path.startswith("/api/articles/") and request.method == "GET":
            if user:
                user_id = str(user.get("user_id"))
                subscription_tier = user.get("subscription_tier", "freemium")

                # Check daily article view limit
                allowed, current, limit = UsageTracker.check_limit(
                    user_id, subscription_tier, "article_view", "day"
                )

                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Daily article limit exceeded ({current}/{limit}). Upgrade to access more articles."
                    )

                # Log usage
                UsageTracker.log_usage(
                    user_id=user_id,
                    usage_type="article_view",
                    resource_url=str(request.url),
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
            else:
                # IP-based rate limiting for unauthenticated users
                client_ip = request.client.host if request.client else "unknown"
                self._check_ip_rate_limit(client_ip, "article_view", max_per_day=20)

        # For search endpoints
        elif request.url.path.startswith("/api/search") and request.method in ["GET", "POST"]:
            if user:
                user_id = str(user.get("user_id"))
                subscription_tier = user.get("subscription_tier", "freemium")

                allowed, current, limit = UsageTracker.check_limit(
                    user_id, subscription_tier, "search", "day"
                )

                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Daily search limit exceeded ({current}/{limit}). Upgrade for more searches."
                    )

                UsageTracker.log_usage(
                    user_id=user_id,
                    usage_type="search",
                    resource_url=str(request.url),
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
            else:
                # IP-based rate limiting for unauthenticated users
                client_ip = request.client.host if request.client else "unknown"
                self._check_ip_rate_limit(client_ip, "search", max_per_day=15)

        # For URL analysis
        elif request.url.path.startswith("/api/analyze-url") and request.method == "POST":
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required for URL analysis"
                )

            user_id = str(user.get("user_id"))
            subscription_tier = user.get("subscription_tier", "freemium")

            if subscription_tier == "freemium":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="URL analysis is not available on the free tier. Upgrade to access this feature."
                )

            allowed, current, limit = UsageTracker.check_limit(
                user_id, subscription_tier, "url_analysis", "month"
            )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Monthly URL analysis limit exceeded ({current}/{limit}). Upgrade for more analyses."
                )

        response = await call_next(request)

        return response


def check_premium_feature(user_tier: str, feature: str) -> bool:
    """
    Check if user tier has access to a premium feature

    Args:
        user_tier: Subscription tier string (freemium, basic, professional, enterprise)
        feature: Feature name to check
    """
    # Support both string tier and full user dict
    if isinstance(user_tier, dict):
        tier = user_tier.get("subscription_tier", "freemium")
    elif isinstance(user_tier, str):
        tier = user_tier
    else:
        tier = str(user_tier)
    tier = tier.lower()

    premium_features = {
        "url_analysis": ["standard", "basic", "professional", "enterprise"],
        "api_access": ["professional", "enterprise"],
        "export": ["standard", "basic", "professional", "enterprise"],
        "saved_searches": ["standard", "basic", "professional", "enterprise"],
        "notifications": ["standard", "basic", "professional", "enterprise"],
        "semantic_search": ["professional", "enterprise"],
        "advanced_analytics": ["professional", "enterprise"],
        "infographics": ["standard", "basic", "professional", "enterprise"],
        "feed_customization": ["standard", "basic", "professional", "enterprise"],
        "advanced_insights": ["professional", "enterprise"],
        "source_registration": ["standard", "basic", "professional", "enterprise"],
        "document_ingestion": ["standard", "basic", "professional", "enterprise"],
        "deep_search": ["professional", "enterprise"],
        "comparative_analysis": ["professional", "enterprise"],
        "weather_context": ["standard", "basic", "professional", "enterprise"],
    }

    allowed_tiers = premium_features.get(feature, [])
    return tier in allowed_tiers


def require_premium(feature: str):
    """
    Decorator to require premium access for an endpoint
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get current_user from kwargs
            current_user = kwargs.get("current_user")

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Extract tier from user object (handles both dict and database row)
            user_tier = current_user.get("subscription_tier") if isinstance(current_user, dict) else getattr(current_user, "subscription_tier", "freemium")

            if not check_premium_feature(user_tier, feature):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This feature requires a premium subscription. Current tier: {user_tier}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
