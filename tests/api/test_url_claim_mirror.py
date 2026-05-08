"""Tests for the URL → corpus claim mirror (migration 016).

The mirror runs as a side-effect of URL analysis completion.  It UPSERTs the
analyzed article into the canonical `articles` table and INSERTs each
extracted claim into `claims` so user-submitted URLs participate in
deep-search, hybrid RAG, and transparency cross-references.

Coverage:
1. Inserts an articles row with is_user_submitted=TRUE on first analysis.
2. Inserts N claims rows with source_kind='url_analysis' and importance_score.
3. ON CONFLICT (url) UPDATEs the existing article instead of duplicating.
4. Failures (e.g. FK violation, missing article_id) are swallowed — the
   helper never raises.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from api import url_analysis_routes


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

class RecorderDB:
    """Records every execute_query / execute_update with the resolved query+params.

    Behaviour:
    - The first INSERT INTO articles ... RETURNING article_id returns
      `article_id_to_return` (or empty list if `simulate_no_returning=True`).
    - All other queries return [].
    - execute_update is a no-op unless `claim_failures` is set, in which case
      it raises on each `INSERT INTO claims` call to exercise the per-claim
      try/except.
    """

    def __init__(
        self,
        article_id_to_return: str = "11111111-2222-3333-4444-555555555555",
        simulate_no_returning: bool = False,
        claim_failures: bool = False,
    ) -> None:
        self.article_id_to_return = article_id_to_return
        self.simulate_no_returning = simulate_no_returning
        self.claim_failures = claim_failures
        self.queries: List[Dict[str, Any]] = []
        self.updates: List[Dict[str, Any]] = []

    def execute_query(self, query: str, params: Optional[Dict] = None):
        params = params or {}
        normalized = " ".join(query.split()).lower()
        self.queries.append({"query": normalized, "params": params})

        if "insert into articles" in normalized and "returning article_id" in normalized:
            if self.simulate_no_returning:
                return []
            return [{"article_id": self.article_id_to_return}]

        # populate_embedding -> SELECT ... FROM articles WHERE article_id
        if "from articles" in normalized and "where article_id" in normalized:
            # Return no rows so EmbeddingService.populate_embedding short-circuits
            return []

        return []

    def execute_update(self, query: str, params: Optional[Dict] = None):
        params = params or {}
        normalized = " ".join(query.split()).lower()
        self.updates.append({"query": normalized, "params": params})

        if self.claim_failures and "insert into claims" in normalized:
            raise RuntimeError("simulated FK violation on claims insert")
        return None


def _make_claim(
    text: str = "Solar generation grew 35% YoY in 2024.",
    claim_type: str = "factual",
    importance: float = 0.85,
    context: str = "Discussed in the renewables section.",
):
    """Build an AtomicClaim-shaped duck-typed object."""
    return SimpleNamespace(
        claim_text=text,
        claim_type=claim_type,
        importance_score=importance,
        claim_context=context,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestUrlClaimMirror:
    """End-to-end behaviour of _mirror_url_analysis_to_corpus."""

    @pytest.mark.asyncio
    async def test_inserts_article_with_user_submitted_flag(self):
        """First mirror call must UPSERT articles with is_user_submitted=TRUE
        and the url_analysis_id back-reference."""
        db = RecorderDB()
        analysis_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        await url_analysis_routes._mirror_url_analysis_to_corpus(
            db=db,
            analysis_id=analysis_id,
            url="https://example.com/article-1",
            title="Climate news",
            source_name="example.com",
            text="Lorem ipsum " * 60,
            language_code="en",
            claims_list=[],
            reliability_score=70,
            overall_credibility="HIGH",
        )

        # Article INSERT must have happened exactly once
        article_inserts = [q for q in db.queries if "insert into articles" in q["query"]]
        assert len(article_inserts) == 1, db.queries

        ins = article_inserts[0]
        # Mandatory fields propagated
        assert ins["params"]["url"] == "https://example.com/article-1"
        assert ins["params"]["title"] == "Climate news"
        assert ins["params"]["source_name"] == "example.com"
        assert ins["params"]["language_code"] == "en"
        assert ins["params"]["reliability"] == 70
        assert ins["params"]["credibility"] == "HIGH"
        assert ins["params"]["analysis_id"] == analysis_id

        # SQL itself must mark is_user_submitted=TRUE and reference url_analysis_id
        assert "is_user_submitted" in ins["query"]
        assert "true" in ins["query"]
        assert "url_analysis_id" in ins["query"]
        # ON CONFLICT (url) clause is the upsert key — required for re-analysis
        assert "on conflict (url)" in ins["query"]
        assert "do update set" in ins["query"]

    @pytest.mark.asyncio
    async def test_inserts_each_claim_with_url_analysis_source_kind(self):
        """Each AtomicClaim must produce a claims row with source_kind='url_analysis'
        and the original importance_score preserved."""
        db = RecorderDB(article_id_to_return="cafef00d-0000-0000-0000-000000000001")
        claims = [
            _make_claim("Wind capacity reached 1GW.", "factual", 0.9, "ctx-1"),
            _make_claim("Coal use declined 12%.", "factual", 0.75, "ctx-2"),
            _make_claim("Net zero by 2050 likely.", "prediction", 0.6, "ctx-3"),
        ]

        await url_analysis_routes._mirror_url_analysis_to_corpus(
            db=db,
            analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            url="https://example.com/multi-claim",
            title="Multi-claim article",
            source_name="example.com",
            text="x" * 600,
            language_code="en",
            claims_list=claims,
            reliability_score=55,
            overall_credibility="MEDIUM",
        )

        claim_inserts = [u for u in db.updates if "insert into claims" in u["query"]]
        assert len(claim_inserts) == 3, db.updates

        # Every claim row must reference the returned article_id
        article_ids = {c["params"]["article_id"] for c in claim_inserts}
        assert article_ids == {"cafef00d-0000-0000-0000-000000000001"}

        # source_kind='url_analysis' is hard-coded in SQL (not a param)
        for c in claim_inserts:
            assert "source_kind" in c["query"]
            assert "'url_analysis'" in c["query"]

        # importance_score round-trips with the original float
        importances = sorted(c["params"]["importance_score"] for c in claim_inserts)
        assert importances == [0.6, 0.75, 0.9]

        # claim_text + claim_type pulled correctly from AtomicClaim attrs
        texts = sorted(c["params"]["claim_text"] for c in claim_inserts)
        assert texts == [
            "Coal use declined 12%.",
            "Net zero by 2050 likely.",
            "Wind capacity reached 1GW.",
        ]
        types = {c["params"]["claim_type"] for c in claim_inserts}
        assert types == {"factual", "prediction"}

    @pytest.mark.asyncio
    async def test_empty_claims_list_inserts_article_only(self):
        """No claims -> still upserts article, but no claims-insert calls."""
        db = RecorderDB()

        await url_analysis_routes._mirror_url_analysis_to_corpus(
            db=db,
            analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            url="https://example.com/no-claims",
            title="Empty",
            source_name="example.com",
            text="short body",
            language_code="en",
            claims_list=[],
            reliability_score=25,
            overall_credibility="LOW",
        )

        article_inserts = [q for q in db.queries if "insert into articles" in q["query"]]
        assert len(article_inserts) == 1

        claim_inserts = [u for u in db.updates if "insert into claims" in u["query"]]
        assert claim_inserts == []

    @pytest.mark.asyncio
    async def test_on_conflict_does_not_raise_when_no_returning_row(self):
        """If the upsert returns no row (degenerate driver edge case), the helper
        must log + bail out without raising and without attempting claim inserts."""
        db = RecorderDB(simulate_no_returning=True)

        # Must not raise
        await url_analysis_routes._mirror_url_analysis_to_corpus(
            db=db,
            analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            url="https://example.com/edge",
            title="Edge",
            source_name="example.com",
            text="body",
            language_code="en",
            claims_list=[_make_claim()],
            reliability_score=50,
            overall_credibility="MEDIUM",
        )

        # Article insert was attempted
        assert any("insert into articles" in q["query"] for q in db.queries)
        # But no claim inserts because article_id was unavailable
        assert not any("insert into claims" in u["query"] for u in db.updates)

    @pytest.mark.asyncio
    async def test_claim_insert_failure_does_not_raise(self):
        """A FK violation or schema mismatch on the claims table must be
        swallowed — URL analysis must complete even if mirroring partially
        fails."""
        db = RecorderDB(claim_failures=True)

        # Must not raise despite RuntimeError on every claim insert
        await url_analysis_routes._mirror_url_analysis_to_corpus(
            db=db,
            analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            url="https://example.com/fk-fail",
            title="FK fail",
            source_name="example.com",
            text="body" * 50,
            language_code="en",
            claims_list=[_make_claim(), _make_claim("Another claim text here.")],
            reliability_score=60,
            overall_credibility="MEDIUM",
        )

        # Article insert succeeded
        assert any("insert into articles" in q["query"] for q in db.queries)
        # Claim inserts were attempted (and raised, but were swallowed)
        claim_attempts = [u for u in db.updates if "insert into claims" in u["query"]]
        assert len(claim_attempts) == 2

    @pytest.mark.asyncio
    async def test_top_level_db_failure_is_swallowed(self):
        """If execute_query itself blows up (e.g. table missing because the
        migration hasn't been applied yet), the helper must NOT raise."""
        broken = MagicMock()
        broken.execute_query.side_effect = RuntimeError("relation 'articles' does not exist")
        broken.execute_update = MagicMock()

        # Must not raise
        await url_analysis_routes._mirror_url_analysis_to_corpus(
            db=broken,
            analysis_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            url="https://example.com/no-table",
            title="No table",
            source_name="example.com",
            text="body",
            language_code="en",
            claims_list=[_make_claim()],
            reliability_score=30,
            overall_credibility="LOW",
        )

        # Helper bailed out before reaching claim inserts
        broken.execute_update.assert_not_called()
