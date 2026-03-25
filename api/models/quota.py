"""
Quota models for tier-based usage tracking.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DiscoveryQuotaInfo(BaseModel):
    """Response model for discovery quota information."""
    tier: str = Field(..., description="User's subscription tier")
    discovery_queries_used: int = Field(0, description="Queries used today")
    discovery_queries_limit: Optional[int] = Field(None, description="Daily limit (None=unlimited)")
    discovery_queries_remaining: Optional[int] = Field(None, description="Remaining today")
    countries_accessible: Optional[int] = Field(None, description="Max countries (None=all)")

    @classmethod
    def from_usage(
        cls,
        tier: str,
        used: int,
        limit: Optional[int],
        countries_limit: Optional[int] = None,
    ) -> "DiscoveryQuotaInfo":
        remaining = None
        if limit is not None:
            remaining = max(0, limit - used)
        return cls(
            tier=tier,
            discovery_queries_used=used,
            discovery_queries_limit=limit,
            discovery_queries_remaining=remaining,
            countries_accessible=countries_limit,
        )


class QuotaHeaders(BaseModel):
    """Standard quota headers to include in API responses."""
    x_ratelimit_limit: Optional[int] = None
    x_ratelimit_remaining: Optional[int] = None
    x_ratelimit_reset: Optional[str] = None

    def to_headers(self) -> dict[str, str]:
        headers = {}
        if self.x_ratelimit_limit is not None:
            headers["X-RateLimit-Limit"] = str(self.x_ratelimit_limit)
        if self.x_ratelimit_remaining is not None:
            headers["X-RateLimit-Remaining"] = str(self.x_ratelimit_remaining)
        if self.x_ratelimit_reset is not None:
            headers["X-RateLimit-Reset"] = self.x_ratelimit_reset
        return headers
