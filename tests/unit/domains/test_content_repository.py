from datetime import datetime

from app.domains.content.repository import ArticleRepository


class DummyDB:
    def execute_query(self, query, params):
        return []


def test_row_to_article_includes_trust_fields():
    repo = ArticleRepository(DummyDB())
    row = {
        # Article.article_id is a UUID (model tightened); use a real one.
        "article_id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Sample Title",
        "url": "https://example.com/article",
        "source_name": "Example Source",
        "author": "Reporter",
        "published_date": datetime.utcnow(),
        "excerpt": "Teaser text",
        "reliability_score": 80,
        "overall_credibility": "HIGH",
        "source_credibility_score": 75,
        "country_code": "FI",
        "language_code": "en",
        "tags": ["climate"],
        "claim_count": 2,
        "verified_claim_count": 1,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "trust_score_cache": 88,
        "publisher_trust_score": 90,
        "nutrition_label": {"transparency_score": 0.9},
        "video_status": "COMPLETED",
        "video_url": "https://videos.local/sample-001.mp4",
        "hitl_status": "APPROVED",
        "compliance_check_passed": True,
        "compliance_skip_reason": None,
        "tdm_opt_out": False,
    }

    article = repo._row_to_article(row)
    assert str(article.article_id) == "550e8400-e29b-41d4-a716-446655440000"
    assert article.trust_score == 88
    assert article.publisher_trust_score == 90
    assert article.compliance_flags == {"passed": True, "tdm_opt_out": False}
    assert article.cta_url == row["url"]
    assert article.nutrition_label == {"transparency_score": 0.9}
    assert article.video_status == "COMPLETED"
    assert article.hitl_status == "APPROVED"


def test_build_compliance_flags_handles_missing_values():
    repo = ArticleRepository(DummyDB())
    flags = repo._build_compliance_flags(
        {"compliance_check_passed": None, "compliance_skip_reason": None, "tdm_opt_out": None}
    )
    assert flags is None

    flags = repo._build_compliance_flags(
        {"compliance_check_passed": False, "compliance_skip_reason": "robots", "tdm_opt_out": True}
    )
    assert flags == {"passed": False, "reason": "robots", "tdm_opt_out": True}


def test_parse_json_field_handles_strings():
    repo = ArticleRepository(DummyDB())
    assert repo._parse_json_field(None) is None
    assert repo._parse_json_field({"a": 1}) == {"a": 1}
    assert repo._parse_json_field('[{"k": "v"}]')[0]["k"] == "v"
