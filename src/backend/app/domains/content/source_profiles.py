"""
Source Profile Service

Manages reusable source trust profiles with historical reliability tracking.
Supports MVP Feature 5: Source trust metadata with historical reliability context.
"""

from typing import Optional
from urllib.parse import urlparse

from app.core.database import Database


class SourceProfileService:
    """Service for managing source trust profiles."""

    def __init__(self, db: Database):
        self.db = db

    def list_profiles(
        self,
        limit: int = 50,
        min_credibility: Optional[int] = None,
        source_type: Optional[str] = None,
    ) -> list[dict]:
        """List source profiles ordered by credibility."""
        conditions = []
        if min_credibility is not None:
            conditions.append(f"credibility_score >= {int(min_credibility)}")
        if source_type:
            safe_type = source_type.replace("'", "''")
            conditions.append(f"source_type = '{safe_type}'")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = self.db.execute_query(
            f"""SELECT source_id, source_name, source_domain, credibility_score,
                       editorial_standards, fact_check_record, transparency_level,
                       total_articles_analyzed, average_reliability_score,
                       total_claims_verified, total_claims_disputed, false_claim_rate,
                       source_type, country_code, description, website_url,
                       first_seen_at, last_updated_at,
                       COALESCE(reliability_tier, 'public') as reliability_tier
                FROM source_profiles
                {where}
                ORDER BY credibility_score DESC NULLS LAST
                LIMIT {int(limit)}""",
            {},
        )
        return rows or []

    def get_profile_by_domain(self, domain: str) -> Optional[dict]:
        """Get source profile by domain name."""
        safe_domain = domain.replace("'", "''").lower()
        rows = self.db.execute_query(
            f"""SELECT source_id, source_name, source_domain, credibility_score,
                       editorial_standards, fact_check_record, transparency_level,
                       total_articles_analyzed, average_reliability_score,
                       total_claims_verified, total_claims_disputed, false_claim_rate,
                       source_type, country_code, description, website_url,
                       first_seen_at, last_updated_at,
                       COALESCE(reliability_tier, 'public') as reliability_tier
                FROM source_profiles
                WHERE source_domain = '{safe_domain}'""",
            {},
        )
        return rows[0] if rows else None

    def get_profile_by_name(self, name: str) -> Optional[dict]:
        """Get source profile by source name."""
        safe_name = name.replace("'", "''")
        rows = self.db.execute_query(
            f"""SELECT source_id, source_name, source_domain, credibility_score,
                       editorial_standards, fact_check_record, transparency_level,
                       total_articles_analyzed, average_reliability_score,
                       total_claims_verified, total_claims_disputed, false_claim_rate,
                       source_type, country_code, description, website_url,
                       first_seen_at, last_updated_at,
                       COALESCE(reliability_tier, 'public') as reliability_tier
                FROM source_profiles
                WHERE LOWER(source_name) = LOWER('{safe_name}')""",
            {},
        )
        return rows[0] if rows else None

    def upsert_from_article(self, source_name: str, url: str, reliability_score: Optional[int] = None) -> dict:
        """
        Create or update source profile from article data.
        Called during article ingestion to maintain source stats.
        """
        # Extract domain from URL
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().lstrip("www.")
        except Exception:
            domain = source_name.lower().replace(" ", "-")

        safe_name = source_name.replace("'", "''")
        safe_domain = domain.replace("'", "''")

        # Upsert profile
        self.db.execute_update(
            f"""INSERT INTO source_profiles (source_name, source_domain, website_url)
                VALUES ('{safe_name}', '{safe_domain}', '{url[:2048]}')
                ON CONFLICT (source_domain) DO UPDATE SET
                    total_articles_analyzed = source_profiles.total_articles_analyzed + 1,
                    last_updated_at = CURRENT_TIMESTAMP""",
            {},
        )

        # Update rolling average reliability if provided
        if reliability_score is not None:
            self.db.execute_update(
                f"""UPDATE source_profiles SET
                        average_reliability_score = COALESCE(
                            (average_reliability_score * (total_articles_analyzed - 1) + {int(reliability_score)})
                            / NULLIF(total_articles_analyzed, 0),
                            {int(reliability_score)}
                        ),
                        credibility_score = COALESCE(
                            (credibility_score * 0.8 + {int(reliability_score)} * 0.2)::int,
                            {int(reliability_score)}
                        )
                    WHERE source_domain = '{safe_domain}'""",
                {},
            )

        return self.get_profile_by_domain(domain) or {}

    def update_claim_stats(self, source_domain: str, verified: int = 0, disputed: int = 0) -> None:
        """Update claim verification stats for a source."""
        safe_domain = source_domain.replace("'", "''").lower()
        total = verified + disputed
        if total == 0:
            return

        self.db.execute_update(
            f"""UPDATE source_profiles SET
                    total_claims_verified = total_claims_verified + {int(verified)},
                    total_claims_disputed = total_claims_disputed + {int(disputed)},
                    false_claim_rate = CASE
                        WHEN (total_claims_verified + total_claims_disputed + {total}) > 0
                        THEN (total_claims_disputed + {int(disputed)})::float
                             / (total_claims_verified + total_claims_disputed + {total})
                        ELSE 0.0
                    END,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE source_domain = '{safe_domain}'""",
            {},
        )
