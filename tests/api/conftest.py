"""
Module-scoped autouse fixtures for tests/api/ test files.

These ensure that tests using module-level ``client = TestClient(app)``
(without going through the conftest ``client`` fixture) still get a
working in-memory postgres mock instead of trying to connect to a real
PostgreSQL instance.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest


# ---------------------------------------------------------------------------
# Smart in-memory DB that handles both article AND auth queries
# ---------------------------------------------------------------------------

class SmartFakeDB:
    """Combined fake DB covering article and auth operations."""

    def __init__(self) -> None:
        self.now = datetime.utcnow()
        self._article_id = "article-0001"
        self._article_row = {
            "article_id": self._article_id,
            "title": "Test Climate Article",
            "url": "https://example.com/test-article",
            "author": "Test Author",
            "published_date": self.now,
            "source_name": "YLE",
            "source_credibility_score": 85,
            "excerpt": "Summary of the latest climate developments.",
            "extracted_text": "Helsinki temperatures have risen 2 degrees.",
            "tags": ["climate", "policy"],
            "content_relevance_score": 0.92,
            "reliability_score": 88,
            "overall_credibility": "HIGH",
            "created_at": self.now,
            "country_code": "FI",
            "claims_count": 1,
            "verified_claims_count": 1,
            "claims_status": "completed",
            "claims_error_message": None,
            "claims_processed_at": self.now,
        }
        self._claim_row = {
            "claim_id": "claim-0001",
            "claim_text": "Sea level projected to rise one meter by 2100.",
            "claim_context": "Climate projections in Baltic region.",
            "claim_type": "projection",
            "fact_check_id": "fact-0001",
            "verification_status": "VERIFIED",
            "confidence_score": 0.86,
            "justification": "Verified against NOAA datasets.",
            "evidence": '{"sources": ["NOAA", "IPCC"]}',
            "climatecheck_hazard_type": "sea_level_rise",
            "climatecheck_risk_score": 0.71,
            "verified_at": self.now,
        }
        # Auth state
        self._users: Dict[str, Dict[str, Any]] = {}  # email -> user record
        self._users_by_id: Dict[str, Dict[str, Any]] = {}  # user_id -> user record

    def _article_listing(self, params: Optional[Dict]) -> List[Dict]:
        limit = (params or {}).get("limit", 20)
        offset = (params or {}).get("offset", 0)
        if offset and offset > 0:
            return []
        return [self._article_row][:limit]

    # ------------------------------------------------------------------
    # execute_query  – handles both article routes and auth routes
    # ------------------------------------------------------------------

    def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        params = params or {}
        q = " ".join(query.split()).lower()

        # ---- AUTH: INSERT INTO users ----
        if "insert into users" in q and "returning" in q:
            email = params.get("email", "user@example.com")
            user_id = f"mock-{_uuid.uuid4().hex[:8]}"
            password_hash = params.get("password_hash", "")
            user_record = {
                "user_id": user_id,
                "email": email,
                "full_name": params.get("full_name", ""),
                "avatar_url": None,
                "subscription_tier": "freemium",
                "is_active": True,
                "email_verified": False,
                "password_hash": password_hash,
                "created_at": self.now,
                "last_login_at": None,
            }
            self._users[email] = user_record
            self._users_by_id[user_id] = user_record
            return [{"user_id": user_id, "email": email, "subscription_tier": "freemium"}]

        # ---- AUTH: UPDATE users (with or without RETURNING) ----
        if "update users" in q:
            user_id = params.get("user_id", "")
            if user_id in self._users_by_id:
                rec = self._users_by_id[user_id]
                for key in ("full_name", "avatar_url", "password_hash", "last_login_at",
                            "email_verified", "is_active"):
                    if key in params:
                        rec[key] = params[key]
                if "returning" in q:
                    return [rec]
            return []

        # ---- AUTH: SELECT user_id WHERE email (duplicate check) ----
        if "select user_id from users where email" in q:
            email = params.get("email", "")
            if email in self._users:
                return [{"user_id": self._users[email]["user_id"]}]
            return []

        # ---- AUTH: SELECT by user_id (get_current_user, change-password) ----
        # Must come BEFORE password_hash check since change-password selects
        # password_hash WHERE user_id, which would otherwise match login path.
        if "from users" in q and "where user_id" in q:
            user_id = params.get("user_id", "")
            if user_id in self._users_by_id:
                return [self._users_by_id[user_id]]
            return []

        # ---- AUTH: SELECT for login (password_hash needed) ----
        if "from users" in q and "password_hash" in q:
            email = params.get("email", "")
            if email in self._users:
                return [self._users[email]]
            return []

        # ---- AUTH: SELECT * FROM users (no filter) ----
        if "from users" in q:
            email = params.get("email", "")
            if email:
                return [self._users[email]] if email in self._users else []
            return list(self._users.values())

        # ---- COUNTRIES (must come before ARTICLES since country query JOINs articles) ----
        if "from countries" in q:
            return [{
                "country_code": "FI",
                "country_name": "Finland",
                "country_name_native": "Suomi",
                "flag_emoji": "\U0001f1eb\U0001f1ee",
                "language_code": "fi",
                "is_eu_member": True,
                "articles_count": 1,
            }]

        # ---- TAGS ----
        if "unnest(tags)" in q or ("from (" in q and "tags" in q):
            return [{"tag": "climate", "article_count": 1}, {"tag": "policy", "article_count": 1}]

        # ---- ARTICLES ----
        if "from articles a" in q and "where a.article_id" not in q:
            return self._article_listing(params)
        if "where a.article_id" in q:
            aid = params.get("article_id")
            if aid and aid != self._article_id:
                return []
            return [self._article_row]
        if "from articles" in q and "count" in q:
            return [{"total_articles": 1, "articles_today": 1, "last_updated": self.now}]
        if "from articles" in q:
            return self._article_listing(params)

        # ---- CLAIMS ----
        if "from claims" in q:
            return [self._claim_row]

        # ---- FEEDBACK ----
        if "insert into article_feedback" in q:
            row = {
                "feedback_id": f"fb-{_uuid.uuid4().hex[:6]}",
                "article_id": params.get("article_id", self._article_id),
                "feedback_type": params.get("feedback_type", "USEFUL"),
                "reliability_score": params.get("reliability_score"),
                "comment": params.get("comment"),
                "submitted_at": self.now,
            }
            return [row]
        if "from article_feedback" in q:
            return [{"total_feedback": 0, "useful": 0, "not_useful": 0, "flagged": 0, "average_reliability": None}]

        # ---- SELECT 1 (existence check) ----
        if "select 1 from articles where article_id" in q:
            aid = params.get("article_id")
            if aid and aid != self._article_id:
                return []
            return [{"exists": 1}]

        # ---- STATS / FACT CHECKS ----
        if "from fact_checks" in q:
            return [{"total_fact_checks": 1, "verified_claims": 1, "average_confidence": 0.86}]

        # ---- SCHEMA MIGRATIONS ----
        if "schema_migrations" in q:
            return [{"version": 0, "description": "init.sql", "applied_at": self.now}]

        return []

    def execute_update(self, query: str, params: Optional[Dict] = None) -> None:
        return None

    def execute_scalar(self, query: str, params: Optional[Dict] = None) -> int:
        return 0


# ---------------------------------------------------------------------------
# Autouse module-scoped fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="module")
def _mock_postgres_for_api_tests():
    """
    Patch the global postgres singleton for every test module under tests/api/.

    Module-level TestClient instances (created at import time) make DB calls
    when requests are handled.  Without this fixture, those calls attempt a
    real TCP connection to localhost:5432 and either time-out or get a
    connection-refused error.
    """
    import shared.database as _shared_db

    smart_db = SmartFakeDB()
    _orig = _shared_db._postgres_client
    _shared_db._postgres_client = smart_db
    yield smart_db
    _shared_db._postgres_client = _orig
