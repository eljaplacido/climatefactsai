"""
Create demo articles, claims, and fact checks for the Climate News portal.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent / "agents"))

from shared.database import get_postgres


ArticleSeed = Dict[str, Any]
ClaimSeed = Dict[str, Any]


def _seed_articles() -> List[ArticleSeed]:
    """Return static demo dataset used for local development."""
    now = datetime.utcnow()
    return [
        {
            "title": "Finland commits to carbon neutrality by 2035",
            "url": "https://example.com/finland-net-zero-2035",
            "author": "Matti Meikalainen",
            "source_name": "Nordic Climate Desk",
            "source_credibility_score": 95,
            "excerpt": "Finland's government confirmed an ambitious carbon neutrality target for 2035.",
            "extracted_text": (
                "The Finnish government has reaffirmed its goal of reaching carbon neutrality by 2035. "
                "The roadmap covers renewable energy expansion, energy-efficiency investments, and stronger forest sinks."
            ),
            "language_code": "en",
            "published_date": now - timedelta(days=1, hours=2),
            "tags": ["climate_policy", "emissions", "finland"],
            "content_relevance_score": 0.92,
            "reliability_score": 92,
            "overall_credibility": "HIGH",
        },
        {
            "title": "Arctic sea ice melt continues to accelerate",
            "url": "https://example.com/arctic-sea-ice-2024",
            "author": "Anna Virtanen",
            "source_name": "Polar Research Network",
            "source_credibility_score": 92,
            "excerpt": "Satellite observations show another record-low Arctic sea ice extent.",
            "extracted_text": (
                "A new international study confirms that Arctic sea ice is melting faster than expected. "
                "Scientists warn the changes will disrupt northern ecosystems and global weather patterns."
            ),
            "language_code": "en",
            "published_date": now - timedelta(days=2),
            "tags": ["weather", "arctic", "climate_change"],
            "content_relevance_score": 0.88,
            "reliability_score": 90,
            "overall_credibility": "HIGH",
        },
        {
            "title": "Solar energy adoption grew 40 percent across Finland",
            "url": "https://example.com/solar-growth-finland",
            "author": "Pekka Virtanen",
            "source_name": "Helsinki Energy Monitor",
            "source_credibility_score": 88,
            "excerpt": "Households and companies accelerated solar panel investments during 2024.",
            "extracted_text": (
                "Solar capacity in Finland expanded by 40 percent last year according to the national energy regulator. "
                "Small-scale rooftop installations accounted for most of the increase."
            ),
            "language_code": "en",
            "published_date": now - timedelta(hours=16),
            "tags": ["renewables", "solar", "green_transition"],
            "content_relevance_score": 0.81,
            "reliability_score": 84,
            "overall_credibility": "MEDIUM",
        },
        {
            "title": "COP29 climate summit delivers historic emissions deal",
            "url": "https://example.com/cop29-agreement",
            "author": "Laura Korhonen",
            "source_name": "Global Climate News",
            "source_credibility_score": 94,
            "excerpt": "Over 190 countries agreed to halve global emissions by 2030 and boost climate finance.",
            "extracted_text": (
                "Negotiators at COP29 adopted a landmark agreement committing 190+ countries to a 50 percent emissions cut by 2030. "
                "The deal introduces new climate finance mechanisms targeting vulnerable nations."
            ),
            "language_code": "en",
            "published_date": now - timedelta(hours=6),
            "tags": ["climate_policy", "cop29", "global"],
            "content_relevance_score": 0.95,
            "reliability_score": 93,
            "overall_credibility": "HIGH",
        },
        {
            "title": "Forest carbon sinks weaken as harvesting intensifies",
            "url": "https://example.com/forest-carbon-sinks",
            "author": "Mikko Laaksonen",
            "source_name": "Boreal Ecology Journal",
            "source_credibility_score": 86,
            "excerpt": "Researchers warn that high harvesting rates are eroding Nordic forest carbon sinks.",
            "extracted_text": (
                "Forest researchers report that Finland's carbon sink capacity has fallen due to intensive harvesting and climate impacts. "
                "The findings raise concerns about meeting national climate targets."
            ),
            "language_code": "en",
            "published_date": now - timedelta(days=3, hours=4),
            "tags": ["forests", "nature", "emissions"],
            "content_relevance_score": 0.77,
            "reliability_score": 78,
            "overall_credibility": "MEDIUM",
        },
    ]


def _claim_library() -> Dict[str, List[ClaimSeed]]:
    """Return demo claims keyed by identifying substring."""
    return {
        "Finland commits": [
            {
                "claim_text": "Finland will reach net-zero emissions by 2035",
                "verification_status": "VERIFIED",
                "confidence": 0.95,
                "justification": "The target is anchored in government policy papers approved by parliament.",
                "sources": [
                    "https://government.fi/climate-neutral-finland-2035",
                    "https://environment.fi/climate-policy"
                ],
            }
        ],
        "Arctic sea ice": [
            {
                "claim_text": "Arctic sea ice extent is shrinking faster than previously modelled",
                "verification_status": "VERIFIED",
                "confidence": 0.92,
                "justification": "NASA and NOAA satellite observations confirm the accelerated decline.",
                "sources": [
                    "https://climate.nasa.gov/news/"
                ],
            }
        ],
        "Solar energy": [
            {
                "claim_text": "Solar installations in Finland grew by 40 percent in 2024",
                "verification_status": "PARTIALLY_VERIFIED",
                "confidence": 0.78,
                "justification": "Energy Authority data shows a 38 percent increase; rounded statements overstate growth slightly.",
                "sources": [
                    "https://energyauthority.fi/statistics"
                ],
            }
        ],
        "COP29": [
            {
                "claim_text": "More than 190 countries committed to cutting emissions 50 percent by 2030",
                "verification_status": "VERIFIED",
                "confidence": 0.89,
                "justification": "The COP29 decision text lists quantified commitments for participating nations.",
                "sources": [
                    "https://unfccc.int/cop29/outcomes"
                ],
            }
        ],
        "Forest carbon": [
            {
                "claim_text": "Finland's forest carbon sink has weakened in recent years",
                "verification_status": "DISPUTED",
                "confidence": 0.65,
                "justification": "Reports from the Natural Resources Institute show declining sinks, but some industry studies disagree.",
                "sources": [
                    "https://luke.fi/carbon-sinks",
                    "https://forestcentre.fi/climate"
                ],
            }
        ],
    }


def create_demo_articles() -> None:
    db = get_postgres()
    articles = _seed_articles()
    claim_library = _claim_library()

    print("\n[INFO] Creating demo articles...")
    print("=" * 70)

    for idx, article in enumerate(articles, start=1):
        insert_sql = """
            INSERT INTO articles (
                title,
                url,
                author,
                source_name,
                source_credibility_score,
                excerpt,
                extracted_text,
                language_code,
                published_date,
                tags,
                content_relevance_score,
                reliability_score,
                overall_credibility
            )
            VALUES (
                :title,
                :url,
                :author,
                :source_name,
                :source_credibility_score,
                :excerpt,
                :extracted_text,
                :language_code,
                :published_date,
                :tags,
                :content_relevance_score,
                :reliability_score,
                :overall_credibility
            )
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                author = EXCLUDED.author,
                source_name = EXCLUDED.source_name,
                source_credibility_score = EXCLUDED.source_credibility_score,
                excerpt = EXCLUDED.excerpt,
                extracted_text = EXCLUDED.extracted_text,
                language_code = EXCLUDED.language_code,
                published_date = EXCLUDED.published_date,
                tags = EXCLUDED.tags,
                content_relevance_score = EXCLUDED.content_relevance_score,
                reliability_score = EXCLUDED.reliability_score,
                overall_credibility = EXCLUDED.overall_credibility,
                updated_at = CURRENT_TIMESTAMP
            RETURNING article_id
        """

        result = db.execute_query(insert_sql, article)
        article_id = result[0]["article_id"]
        print(f"[OK] {idx}. {article['title']}")

        # Reset claims for idempotency
        db.execute_update(
            "DELETE FROM claims WHERE article_id = :article_id",
            {"article_id": article_id},
        )

        for key, claims in claim_library.items():
            if key in article["title"]:
                for claim in claims:
                    claim_result = db.execute_query(
                        """
                        INSERT INTO claims (
                            article_id,
                            claim_text,
                            claim_type,
                            identified_at
                        )
                        VALUES (
                            :article_id,
                            :claim_text,
                            'FACTUAL_STATEMENT',
                            NOW()
                        )
                        RETURNING claim_id
                        """,
                        {
                            "article_id": article_id,
                            "claim_text": claim["claim_text"],
                        },
                    )

                    claim_id = claim_result[0]["claim_id"]

                    evidence_payload = {
                        "summary": claim["justification"],
                        "sources": claim["sources"],
                    }

                    db.execute_update(
                        """
                        INSERT INTO fact_checks (
                            claim_id,
                            verification_status,
                            confidence_score,
                            justification,
                            evidence,
                            fact_check_agent_version,
                            processing_time_ms,
                            verified_at,
                            created_at
                        )
                        VALUES (
                            :claim_id,
                            :verification_status,
                            :confidence_score,
                            :justification,
                            :evidence,
                            'demo-agent/1.0',
                            1500,
                            NOW(),
                            NOW()
                        )
                        """,
                        {
                            "claim_id": claim_id,
                            "verification_status": claim["verification_status"],
                            "confidence_score": claim["confidence"],
                            "justification": claim["justification"],
                            "evidence": json.dumps(evidence_payload),
                        },
                    )
        # Update aggregate counters
        db.execute_update(
            """
            UPDATE articles
            SET
                claims_count = (
                    SELECT COUNT(*) FROM claims WHERE article_id = :article_id
                ),
                verified_claims_count = (
                    SELECT COUNT(*)
                    FROM fact_checks fc
                    JOIN claims c ON c.claim_id = fc.claim_id
                    WHERE c.article_id = :article_id
                      AND fc.verification_status = 'VERIFIED'
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE article_id = :article_id
            """,
            {"article_id": article_id},
        )

    print("\n[DONE] Demo data ready. Refresh http://localhost:5173 to view articles.\n")
    db.close()


if __name__ == "__main__":
    create_demo_articles()
