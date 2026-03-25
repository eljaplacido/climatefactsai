"""
Full Climate News pipeline runner with multi-country support and
richer fact-checking signals (Perplexity + ClimateCheck + NOAA + NASA).
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

# Make sure agents/ is on the path when running from repository root
sys.path.insert(0, str(Path(__file__).parent / "agents"))

from content_discovery.perplexity_news_discovery import PerplexityNewsDiscovery
from fact_checking.perplexity_client import PerplexityClient
from fact_checking.climate_api import ClimateCheckClient, NOAAClient, NASAClient
from shared.database import get_postgres
from shared.config import get_settings

# ---------------------------------------------------------------------------
# Static metadata for countries we commonly track. Values can be extended.
# ---------------------------------------------------------------------------
COUNTRY_PRESETS: Dict[str, Dict[str, object]] = {
    "FI": {
        "name": "Finland",
        "location_name": "Helsinki",
        "latitude": 60.1699,
        "longitude": 24.9384,
        "noaa_location": "GM000010962",
    },
    "SE": {
        "name": "Sweden",
        "location_name": "Stockholm",
        "latitude": 59.3293,
        "longitude": 18.0686,
        "noaa_location": "SW000024280",
    },
    "NO": {
        "name": "Norway",
        "location_name": "Oslo",
        "latitude": 59.9139,
        "longitude": 10.7522,
        "noaa_location": "NO000024080",
    },
    "DK": {
        "name": "Denmark",
        "location_name": "Copenhagen",
        "latitude": 55.6761,
        "longitude": 12.5683,
        "noaa_location": "DA000024003",
    },
    "EE": {
        "name": "Estonia",
        "location_name": "Tallinn",
        "latitude": 59.4370,
        "longitude": 24.7536,
        "noaa_location": "EN000022118",
    },
    "DE": {
        "name": "Germany",
        "location_name": "Berlin",
        "latitude": 52.5200,
        "longitude": 13.4050,
        "noaa_location": "GM000004480",
    },
    "FR": {
        "name": "France",
        "location_name": "Paris",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "noaa_location": "FR000007003",
    },
    "GB": {
        "name": "United Kingdom",
        "location_name": "London",
        "latitude": 51.5072,
        "longitude": -0.1276,
        "noaa_location": "UK000056225",
    },
}

# Tags are derived from Perplexity topics + article summary keywords
TAG_KEYWORDS: Dict[str, List[str]] = {
    'saa_ilmiot': [
        'storm',
        'heat wave',
        'heatwave',
        'flood',
        'rain',
        'snow',
        'drought',
        'wildfire',
        'weather',
        'temperature',
    ],
    'ilmastonmuutos': [
        'climate',
        'emission',
        'greenhouse',
        'warming',
        'net zero',
    ],
    'kiertotalous': ['circular economy', 'recycling', 'reuse', 'waste'],
    'vihrea_siirtyma': ['energy transition', 'renewable', 'wind', 'solar'],
    'kestava_kehitys': ['sustainable', 'sdg', 'biodiversity', 'resilience'],
    'esg': ['esg', 'sustainability reporting', 'taxonomy'],
}

# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full climate-news pipeline for one or more countries."
    )
    parser.add_argument(
        "--country",
        help="Human readable country name (defaults to Finland).",
    )
    parser.add_argument(
        "--country-code",
        help="ISO 3166-1 alpha-2 code (defaults to FI).",
    )
    parser.add_argument(
        "--countries",
        help="Comma separated list of country codes, e.g. FI,SE,NO. Overrides --country.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=5,
        help="Maximum number of articles per country to ingest.",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Look back window in days when querying Perplexity.",
    )
    parser.add_argument(
        "--task-id",
        help="Optional workflow/task identifier stored in database entries.",
    )
    parser.add_argument(
        "--skip-external-data",
        action="store_true",
        help="Skip ClimateCheck/NOAA/NASA enrichment (Perplexity only).",
    )
    return parser.parse_args()


def resolve_country_batch(args: argparse.Namespace) -> List[Tuple[str, str]]:
    if args.countries:
        codes = [code.strip().upper() for code in args.countries.split(",") if code.strip()]
        pairs = []
        for code in codes:
            preset = COUNTRY_PRESETS.get(code)
            name = preset["name"] if preset else code
            pairs.append((code, name))
        return pairs

    code = (args.country_code or "FI").upper()
    name = args.country or COUNTRY_PRESETS.get(code, {}).get("name", "Finland")
    return [(code, name)]


def to_pg_array(items: Optional[List[str]]) -> str:
    if not items:
        return "{}"
    escaped = []
    for item in items:
        safe = item.replace('"', '\\"')
        escaped.append(f'"{safe}"')
    return "{" + ",".join(escaped) + "}"


def derive_tags(article: Dict[str, object]) -> List[str]:
    tags: List[str] = []
    text_fragments = " ".join(
        [
            " ".join(article.get("topics", []) or []),
            article.get("summary", ""),
            article.get("title", ""),
        ]
    ).lower()

    for tag, keywords in TAG_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_fragments:
                tags.append(tag)
                break

    # Add Perplexity provided topics as-is to capture finer grained labels
    topics = article.get("topics") or []
    tags.extend(topic.lower() for topic in topics if isinstance(topic, str))

    # De-duplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for tag in tags:
        if tag not in seen:
            deduped.append(tag)
            seen.add(tag)
    return deduped


def collect_external_signals(
    country_code: str,
    enrichment_enabled: bool,
    climate_client: Optional[ClimateCheckClient],
    noaa_client: Optional[NOAAClient],
    nasa_client: Optional[NASAClient],
) -> Tuple[Dict[str, object], Dict[str, int]]:
    """Fetch external climate data for the given country.

    Returns a tuple: (evidence_payload, api_call_counts)
    """

    evidence: Dict[str, object] = {}
    api_calls = {"climatecheck": 0, "noaa": 0, "nasa": 0}

    if not enrichment_enabled:
        return evidence, api_calls

    preset = COUNTRY_PRESETS.get(country_code)
    if not preset:
        return evidence, api_calls

    lat = preset.get("latitude")
    lon = preset.get("longitude")
    location_name = preset.get("location_name", country_code)

    if climate_client and climate_client.api_key:
        response = climate_client.get_risk_scores(latitude=lat, longitude=lon)
        if response:
            evidence["climatecheck"] = response
            api_calls["climatecheck"] = 1

    if noaa_client and noaa_client.api_token and preset.get("noaa_location"):
        response = noaa_client.get_climate_data(
            location=preset["noaa_location"],
            data_type="temperature",
            start_date=datetime.utcnow().strftime("%Y-01-01"),
            end_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        if response:
            evidence["noaa"] = response
            api_calls["noaa"] = 1

    if nasa_client:
        response = nasa_client.get_earth_temperature(latitude=lat, longitude=lon)
        if response:
            evidence["nasa"] = response
            api_calls["nasa"] = 1

    if evidence:
        evidence["location"] = {"name": location_name, "lat": lat, "lon": lon}

    return evidence, api_calls


def build_fact_justification(
    perplexity_text: str,
    evidence: Dict[str, object],
) -> str:
    lines = []
    if perplexity_text:
        lines.append(perplexity_text.strip())

    climatecheck = evidence.get("climatecheck") if evidence else None
    if climatecheck:
        hazard = climatecheck.get("hazardType", "risk")
        risk = climatecheck.get("riskScore")
        lines.append(f"ClimateCheck risk for {hazard}: {risk}/100 (confidence {climatecheck.get('confidence', 0.0):.0%}).")

    noaa = evidence.get("noaa") if evidence else None
    if noaa:
        dataset = noaa.get("dataType", "climate data")
        sample_count = len(noaa.get("results", []))
        lines.append(f"NOAA {dataset} dataset returned {sample_count} recent measurements.")

    nasa = evidence.get("nasa") if evidence else None
    if nasa:
        temperature = nasa.get("temperature")
        lines.append(f"NASA satellite surface temperature snapshot: {temperature} �C.")

    return " ".join(lines).strip()


def compute_combined_confidence(
    perplexity_confidence: float,
    evidence: Dict[str, object],
) -> float:
    boost = 0.0
    if evidence.get("climatecheck"):
        boost += 0.1
    if evidence.get("noaa"):
        boost += 0.05
    if evidence.get("nasa"):
        boost += 0.05
    combined = perplexity_confidence + boost
    return max(0.1, min(combined, 0.99))


def compute_reliability_score(
    source_score: int,
    fact_confidence: float,
    verified_ratio: float,
    external_evidence: Dict[str, object],
) -> int:
    """Return a 0-100 reliability score used for ranking on the frontend."""
    base = source_score * 0.4
    fact_component = fact_confidence * 100 * 0.3
    ratio_component = verified_ratio * 100 * 0.2
    enrichment_bonus = 10 if external_evidence else 0
    return int(round(base + fact_component + ratio_component + enrichment_bonus))


def run_pipeline_for_country(
    country_code: str,
    country_name: str,
    max_articles: int,
    days_back: int,
    task_id: str,
    enrichment_enabled: bool,
    perplexity_key: str,
    climate_client: Optional[ClimateCheckClient],
    noaa_client: Optional[NOAAClient],
    nasa_client: Optional[NASAClient],
) -> None:
    print("\n" + "=" * 80)
    print(f"Running pipeline for {country_name} ({country_code})")
    print("=" * 80)

    discovery = PerplexityNewsDiscovery(perplexity_key)
    fact_checker = PerplexityClient(perplexity_key)
    db = get_postgres()

    articles = discovery.discover_news(
        country=country_name,
        country_code=country_code,
        max_articles=max_articles,
        days_back=days_back,
    )

    print(f"Found {len(articles)} candidate articles from Perplexity.")
    if not articles:
        return

    saved_articles: List[Dict[str, object]] = []

    for index, article in enumerate(articles, 1):
        print(f"\n[{index}/{len(articles)}] {article['title']}")

        tags = derive_tags(article)
        article_summary = article.get("summary", "")
        article_excerpt = article_summary[:280]
        source_score = article.get("credibility_score") or 70

        insert_query = """
            INSERT INTO articles (
                title,
                url,
                source_name,
                extracted_text,
                excerpt,
                language_code,
                published_date,
                country_code,
                source_credibility_score,
                tags,
                task_id
            )
            VALUES (
                :title,
                :url,
                :source,
                :content,
                :excerpt,
                :lang,
                :published,
                :country,
                :credibility,
                 CAST(:tags AS text[]),
                :task_id
            )
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                source_name = EXCLUDED.source_name,
                extracted_text = EXCLUDED.extracted_text,
                excerpt = EXCLUDED.excerpt,
                language_code = EXCLUDED.language_code,
                published_date = EXCLUDED.published_date,
                location_name = EXCLUDED.location_name,\n                location_country = EXCLUDED.location_country,
                source_credibility_score = EXCLUDED.source_credibility_score,
                tags = EXCLUDED.tags,
                task_id = EXCLUDED.task_id,
                updated_at = NOW()
            RETURNING article_id
        """

        insert_params = {
            "title": article.get("title"),
            "url": article.get("url"),
            "source": article.get("source_name"),
            "content": article_summary,
            "excerpt": article_excerpt,
            "lang": article.get("language_code", "en"),
            "published": article.get("published_date"),
            # Country metadata
            "country": country_code,           # for country_code column
            "location_name": country_name,     # for location_name column (ON CONFLICT update)
            "location_country": country_code,  # for location_country column (ON CONFLICT update)
            "credibility": source_score,
            "tags": to_pg_array(tags),
            "task_id": task_id,
        }

        insert_result = db.execute_query(insert_query, insert_params)
        if not insert_result:
            print("  ! Failed to persist article (skipping)")
            continue

        article_id = insert_result[0]["article_id"]
        article["article_id"] = article_id
        article["tags"] = tags
        saved_articles.append(article)
        # Use plain ASCII to avoid Windows console encoding issues
        print("  - Saved to database")

        claim_text = article.get("title")
        start_time = time.time()
        fact_result = fact_checker.verify_claim(
            claim=claim_text,
            context=article_summary[:400],
            location=country_name,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        evidence, api_calls = collect_external_signals(
            country_code=country_code,
            enrichment_enabled=enrichment_enabled,
            climate_client=climate_client,
            noaa_client=noaa_client,
            nasa_client=nasa_client,
        )

        justification = build_fact_justification(
            perplexity_text=fact_result.get("explanation", ""),
            evidence=evidence,
        )
        confidence = compute_combined_confidence(
            perplexity_confidence=fact_result.get("confidence", 0.5),
            evidence=evidence,
        )

        claim_query = """
            INSERT INTO claims (
                article_id,
                claim_text,
                claim_type,
                claim_context
            )
            VALUES (:article_id, :claim_text, 'FACTUAL_STATEMENT', :claim_context)
            RETURNING claim_id
        """

        claim_params = {
            "article_id": article_id,
            "claim_text": claim_text,
            "claim_context": article_summary[:500],
        }

        claim_result = db.execute_query(claim_query, claim_params)
        if not claim_result:
            print("  ! Could not persist claim; fact-check skipped")
            continue

        claim_id = claim_result[0]["claim_id"]
        verdict = fact_result.get("verdict", "UNKNOWN")
        status_map = {
            "TRUE": "VERIFIED",
            "FALSE": "FALSE",
            "PARTIALLY_TRUE": "PARTIALLY_VERIFIED",
            "DISPUTED": "DISPUTED",
        }
        status = status_map.get(verdict, "UNVERIFIED")
        article['verified'] = status == 'VERIFIED'

        evidence_payload = {
            "sources": fact_result.get("sources", []),
            "perplexity": fact_result.get("raw_response"),
        }
        if evidence:
            evidence_payload["external"] = evidence

        fact_query = """
            INSERT INTO fact_checks (
                claim_id,
                verification_status,
                confidence_score,
                justification,
                evidence,
                climatecheck_hazard_type,
                climatecheck_risk_score,
                fact_check_agent_version,
                processing_time_ms,
                api_calls_made,
                task_id
            )
            VALUES (
                :claim_id,
                :status,
                :confidence,
                :justification,
                :evidence,
                :hazard_type,
                :risk_score,
                :agent_version,
                :processing_time_ms,
                :api_calls_made,
                :task_id
            )
            RETURNING fact_check_id
        """

        climatecheck_data = evidence.get("climatecheck") if evidence else None
        fact_params = {
            "claim_id": claim_id,
            "status": status,
            "confidence": confidence,
            "justification": justification[:1000],
            "evidence": json.dumps(evidence_payload),
            "hazard_type": climatecheck_data.get("hazardType") if climatecheck_data else None,
            "risk_score": climatecheck_data.get("riskScore") if climatecheck_data else None,
            "agent_version": "perplexity_cli_v2",
            "processing_time_ms": elapsed_ms,
            "api_calls_made": json.dumps(api_calls),
            "task_id": task_id,
        }

        db.execute_query(fact_query, fact_params)
        # Use plain ASCII to avoid Windows console encoding issues
        print(f"  - Fact check stored ({status}, confidence {confidence:.0%})")

        verified_ratio = 1.0 if status == "VERIFIED" else 0.0
        reliability_score = compute_reliability_score(
            source_score=source_score,
            fact_confidence=confidence,
            verified_ratio=verified_ratio,
            external_evidence=evidence,
        )

        db.execute_update(
            """
            UPDATE articles
            SET
                overall_credibility = CASE
                    WHEN :reliability >= 80 THEN 'HIGH'
                    WHEN :reliability >= 55 THEN 'MEDIUM'
                    ELSE 'LOW'
                END,
                content_relevance_score = :relevance,
                reliability_score = :reliability,
                claims_count = (
                    SELECT COUNT(*) FROM claims WHERE article_id = :article_id
                ),
                verified_claims_count = (
                    SELECT COUNT(*) FROM fact_checks fc
                    JOIN claims c ON c.claim_id = fc.claim_id
                    WHERE c.article_id = :article_id AND fc.verification_status = 'VERIFIED'
                ),
                updated_at = NOW()
            WHERE article_id = :article_id
            """,
            {
                "reliability": reliability_score,
                "relevance": min(0.99, confidence + 0.2),
                "article_id": article_id,
            },
        )

    if not saved_articles:
        print("No articles were saved; skipping summary generation.")
        return

    print("\nGenerating summary across saved articles...")
    content_creator = ContentCreator(perplexity_key)
    summary = content_creator.create_summary(
        articles=saved_articles,
        country=country_name,
        language="fi",
    )

    summary_query = """
        INSERT INTO content_packages (
            task_id,
            headline,
            summary_markdown,
            summary_plain_text,
            publication_date,
            language_code,
            target_location_name,
            target_location_country,
            source_article_ids,
            tags,
            metadata,
            verified_claims_count
        )
        VALUES (
            :task_id,
            :headline,
            :markdown,
            :plain,
            NOW(),
            :language,
            :location_name,
            :country_code,
            :article_ids,
            CAST(:tags AS text[]),
            CAST(:metadata AS jsonb),
            :verified_count
        )
        ON CONFLICT (task_id) DO UPDATE SET
            headline = EXCLUDED.headline,
            summary_markdown = EXCLUDED.summary_markdown,
            summary_plain_text = EXCLUDED.summary_plain_text,
            tags = EXCLUDED.tags,
            metadata = CAST(EXCLUDED.metadata AS jsonb),
            updated_at = NOW()
        RETURNING package_id
    """

    summary_tags = sorted({tag for article in saved_articles for tag in article.get("tags", [])})
    article_ids = [str(article.get("article_id")) for article in saved_articles if article.get("article_id")]

    metadata_payload = {
        "key_findings": summary.get("key_findings", []),
        "impact_analysis": summary.get("impact_analysis"),
        "confidence_assessment": summary.get("confidence_assessment"),
        "recommended_actions": summary.get("recommended_actions", []),
        "language": summary.get("language", "fi")
    }
    summary_params = {
        "task_id": f"{task_id}-{country_code}",
        "headline": summary.get("title", f"Climate news recap: {country_name}"),
        "markdown": summary.get("summary_markdown") or summary.get("summary", ""),
        "plain": summary.get("summary_plain_text") or summary.get("summary", ""),
        "language": summary.get("language", "fi"),
        "location_name": COUNTRY_PRESETS.get(country_code, {}).get("location_name", country_name),
        "country_code": country_code,
        "article_ids": json.dumps(article_ids),
        "tags": to_pg_array(summary_tags),
        "verified_count": sum(1 for article in saved_articles if article.get("verified")),
        "metadata": json.dumps(metadata_payload),
    }

    db.execute_query(summary_query, summary_params)
    print("Summary stored in content_packages.")


class ContentCreator:
    """Wrapper that extends ContentCreator to avoid circular import."""

    def __init__(self, api_key: str):
        from content_creation.content_creator import ContentCreator as BaseCreator

        self._impl = BaseCreator(api_key)

    def create_summary(self, **kwargs):
        return self._impl.create_summary(**kwargs)


if __name__ == "__main__":
    args = parse_args()
    settings = get_settings()

    perplexity_key = settings.llm.perplexity_api_key
    if not perplexity_key:
        raise SystemExit("PERPLEXITY_API_KEY missing. Set it in your environment or .env file.")

    climate_client = None
    noaa_client = None
    nasa_client = None

    if not args.skip_external_data:
        climate_client = ClimateCheckClient(
            api_key=settings.climate_data.climatecheck_api_key,
            api_url=settings.climate_data.climatecheck_api_url,
        ) if settings.climate_data.climatecheck_api_key else None

        noaa_client = NOAAClient(
            api_token=settings.climate_data.noaa_api_token,
            api_url=settings.climate_data.noaa_api_url,
        ) if settings.climate_data.noaa_api_token else None

        nasa_client = NASAClient(
            api_key=settings.climate_data.nasa_api_key,
            api_url=settings.climate_data.nasa_api_url,
        )

    task_id = args.task_id or f"cli-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    countries = resolve_country_batch(args)

    print("Starting Climate News pipeline")
    print(f"Task ID: {task_id}")
    print(f"Countries: {', '.join(code for code, _ in countries)}")

    for code, name in countries:
        run_pipeline_for_country(
            country_code=code,
            country_name=name,
            max_articles=args.max_articles,
            days_back=args.days_back,
            task_id=task_id,
            enrichment_enabled=not args.skip_external_data,
            perplexity_key=perplexity_key,
            climate_client=climate_client,
            noaa_client=noaa_client,
            nasa_client=nasa_client,
        )

    print("\nPipeline finished.")











