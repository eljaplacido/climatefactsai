import pytest

from app.domains.intelligence.research_report_service import ResearchReportService


class DummyDB:
    def execute_query(self, query, params=None):
        return []

    def execute_update(self, query, params=None):
        return 0


@pytest.mark.asyncio
async def test_analyze_report_uses_credibility_service_for_prior():
    service = ResearchReportService(db=DummyDB())

    async def fake_resolve_document(url, doi, text):
        return {
            "title": "Sample Research Report",
            "text": "Methodology section. Data section. References [1] [2].",
            "content_type": "research_report",
            "doi": None,
            "publication_venue": None,
            "page_count": 12,
        }

    async def fake_fetch_doi_metadata(doi):
        return {}

    async def fake_analyze_with_llm(
        text,
        content_type,
        metadata,
        reference_count=0,
        has_methodology=False,
        data_indicators=None,
    ):
        return {
            "summary": "Good report",
            "key_claims": ["Claim A"],
            "methodology_score": 72,
            "citation_score": 68,
            "data_transparency_score": 70,
            "topics": ["climate"],
            "climate_relevance": "high",
            "limitations_noted": True,
            "peer_reviewed_indicators": False,
            "potential_biases": [],
            "recommendation": "Useful",
        }

    def fake_adjust_scores(analysis, reference_count, has_methodology, data_indicators, content_type):
        return analysis

    service._resolve_document = fake_resolve_document
    service._fetch_doi_metadata = fake_fetch_doi_metadata
    service._analyze_with_llm = fake_analyze_with_llm
    service._adjust_scores = fake_adjust_scores

    calls = {}

    def fake_prior(*, has_doi, venue, content_type):
        calls["prior"] = {
            "has_doi": has_doi,
            "venue": venue,
            "content_type": content_type,
        }
        return 64.0

    def fake_weighted(prior, evidence_scores, prior_weight=0.2):
        calls["weighted"] = {
            "prior": prior,
            "evidence_scores": evidence_scores,
            "prior_weight": prior_weight,
        }
        return {"posterior_score": 71.0, "methodology": "weighted_average"}

    service.credibility.compute_research_prior = fake_prior
    service.credibility.compute_weighted_score = fake_weighted

    result = await service.analyze_report(text="ignored by test stub")

    assert result["status"] == "completed"
    assert calls["prior"]["content_type"] == "research_report"
    assert calls["weighted"]["prior"] == 64.0
    assert result["credibility"]["prior_score"] == 64.0
    assert result["credibility"]["posterior"]["posterior_score"] == 71.0
