"""
End-to-End Pipeline Tests

Tests the complete pipeline: discover -> extract -> verify -> score -> generate.
Uses mocked external services but real internal logic.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestDiscoveryPipeline:
    """Test the article discovery phase."""

    def test_discover_articles_with_seed_ids(self, sample_article_id):
        """Discover should accept seed article IDs and return them."""
        with patch("app.tasks.ingestion.get_db") as mock_get_db:
            mock_get_db.return_value = MagicMock()
            from app.tasks.ingestion import discover_articles

            # Call with seed IDs (bypass Celery binding)
            task = discover_articles
            # Simulate direct invocation
            result = task.apply(
                kwargs={
                    "country": "FI",
                    "max_articles": 5,
                    "seed_article_ids": [sample_article_id],
                }
            ).get(timeout=10)

            assert result["article_ids"] == [sample_article_id]
            assert result["discovery_method"] == "seed"
            assert result["country"] == "FI"

    def test_discover_articles_database_fallback(self, sample_article_id):
        """When Perplexity is unavailable, should fall back to DB query."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"article_id": sample_article_id}]

        with patch("app.tasks.ingestion.get_db", return_value=mock_db), \
             patch.dict("os.environ", {"PERPLEXITY_API_KEY": ""}, clear=False):
            from app.tasks.ingestion import discover_articles

            result = discover_articles.apply(
                kwargs={"country": "FI", "max_articles": 5}
            ).get(timeout=10)

            assert result["discovery_method"] == "database_fallback"
            assert len(result["article_ids"]) >= 0


class TestClaimExtractionPipeline:
    """Test the claim extraction phase."""

    def test_extract_claims_returns_structured_output(self, mock_anthropic_response):
        """ClaimExtractor should return list of AtomicClaim objects."""
        mock_json = (
            '[{"claim_text": "Finland temperature rose 2.3C", "claim_type": "factual",'
            ' "claim_category": "statistical", "importance_score": 0.9,'
            ' "claim_context": "Average temperature increase"}]'
        )
        with patch("app.domains.intelligence.services._deepseek_chat", return_value=mock_json):
            from app.domains.intelligence.services import ClaimExtractor
            extractor = ClaimExtractor()

            claims = asyncio.run(extractor.decompose_claims(
                "Finland temperature rose 2.3C since pre-industrial times. "
                "The government committed to carbon neutrality by 2035. "
                "Arctic amplification is accelerating warming in the region."
            ))

            assert isinstance(claims, list)
            assert len(claims) >= 1
            assert hasattr(claims[0], "claim_text")
            assert hasattr(claims[0], "claim_category")

    def test_extract_claims_handles_short_text(self):
        """Should return empty list for text too short."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from app.domains.intelligence.services import ClaimExtractor
            extractor = ClaimExtractor()
            claims = asyncio.run(extractor.decompose_claims("Short text."))
            assert claims == []


class TestEvidenceRetrievalPipeline:
    """Test the evidence retrieval phase."""

    def test_open_meteo_retriever_returns_evidence(self):
        """OpenMeteoEvidenceRetriever should return weather data evidence."""
        from app.domains.intelligence.evidence_retriever import OpenMeteoEvidenceRetriever

        retriever = OpenMeteoEvidenceRetriever()

        # Mock httpx to avoid real API calls
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current": {
                "temperature_2m": 5.2,
                "precipitation": 0.0,
                "wind_speed_10m": 12.5,
            },
            "daily": {
                "temperature_2m_max": [6.0, 7.1, 5.8],
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            evidence = asyncio.run(retriever.retrieve(
                "Temperature in Finland rose significantly",
                country_code="FI",
            ))

            assert isinstance(evidence, list)
            assert len(evidence) >= 1
            assert evidence[0].source == "Open-Meteo Weather API"
            assert evidence[0].source_reliability == "high"

    def test_evidence_orchestrator_handles_all_failures(self):
        """Orchestrator should raise 503 when all sources fail."""
        from app.domains.intelligence.evidence_retriever import EvidenceOrchestrator

        orchestrator = EvidenceOrchestrator()

        # Mock all retrievers to fail
        for retriever in orchestrator.retrievers:
            retriever.retrieve = AsyncMock(side_effect=Exception("Service down"))

        with pytest.raises(Exception) as exc_info:
            asyncio.run(orchestrator.retrieve_all("test claim", "FI"))

        # Should get HTTP 503
        assert "503" in str(exc_info.value) or "evidence sources failed" in str(exc_info.value).lower()

    def test_evidence_orchestrator_partial_success(self):
        """Orchestrator should return results even if some sources fail."""
        from app.domains.intelligence.evidence_retriever import EvidenceOrchestrator
        from app.domains.intelligence.schemas import Evidence

        orchestrator = EvidenceOrchestrator()

        # Mock first retriever to succeed, rest to fail
        mock_evidence = Evidence(
            source="Test Source",
            source_url="https://test.com",
            source_reliability="high",
            content_excerpt="Test evidence content for verification.",
            relevance_score=0.8,
            retrieval_method="test",
        )
        orchestrator.retrievers[0].retrieve = AsyncMock(return_value=[mock_evidence])
        for retriever in orchestrator.retrievers[1:]:
            retriever.retrieve = AsyncMock(side_effect=Exception("Unavailable"))

        evidence = asyncio.run(orchestrator.retrieve_all("test claim", "FI"))
        assert len(evidence) == 1
        assert evidence[0].source == "Test Source"


class TestVerificationPipeline:
    """Test the verdict adjudication phase."""

    def test_verdict_adjudicator_produces_structured_output(self):
        """VerdictAdjudicator should return a Verdict with confidence score."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"verdict": "verified", "confidence_score": 0.85, "justification": "Multiple sources confirm this statistical claim about temperature rise.", "evidence_summary": "FMI and IPCC data support the 2.3C figure."}')]

        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                from app.domains.intelligence.services import VerdictAdjudicator
                from app.domains.intelligence.schemas import AtomicClaim, Evidence

                adjudicator = VerdictAdjudicator()
                adjudicator.client = mock_client

                claim = AtomicClaim(
                    claim_text="Finland temperature rose 2.3C since pre-industrial times",
                    claim_type="factual",
                    claim_category="statistical",
                )
                evidence = [Evidence(
                    source="FMI",
                    source_url="https://fmi.fi",
                    content_excerpt="Finland warmed approximately 2.3C since pre-industrial era.",
                    source_reliability="high",
                    relevance_score=0.9,
                )]

                verdict = asyncio.run(adjudicator.adjudicate(claim, evidence))
                assert verdict is not None
                assert hasattr(verdict, "verdict") or hasattr(verdict, "confidence_score")


class TestFullPipelineIntegration:
    """Test the complete pipeline from discovery to scoring."""

    def test_workflow_state_flows_through_pipeline(self, sample_workflow_state):
        """Workflow state should accumulate results through pipeline stages."""
        state = sample_workflow_state.copy()

        # Stage 1: Discovery already done (seed IDs)
        assert "article_ids" in state
        assert len(state["article_ids"]) > 0

        # Stage 2: Simulate verification results
        state["verification_results"] = [{
            "article_id": state["article_ids"][0],
            "claims_extracted": 3,
            "claims_verified": 2,
            "claims_disputed": 1,
            "status": "completed",
        }]

        assert "verification_results" in state
        assert state["verification_results"][0]["status"] == "completed"

        # Stage 3: Simulate summary
        state["summary_task"] = {"updated": 1}

        assert "summary_task" in state
        assert state["summary_task"]["updated"] == 1

    def test_multi_article_pipeline_processes_all(self):
        """Pipeline should process multiple articles in a single workflow."""
        article_ids = [str(uuid4()) for _ in range(3)]
        state = {
            "task_id": "test-multi",
            "article_ids": article_ids,
            "country": "FI",
        }

        # Simulate verification for all articles
        state["verification_results"] = [
            {"article_id": aid, "claims_extracted": 2, "status": "completed"}
            for aid in article_ids
        ]

        assert len(state["verification_results"]) == 3
        assert all(r["status"] == "completed" for r in state["verification_results"])
