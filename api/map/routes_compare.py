"""Map routes — country comparison and timeline."""
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, HTTPException, Query
from .models import CompareResponse, TimelineEntry, CountryComparison, REGION_COUNTRIES
from .services import _get_country_names
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("map-api")
router = APIRouter()


@router.get("/compare", response_model=CompareResponse)
async def compare_countries(
    countries: str = Query(..., description="Comma-separated country codes, e.g. FI,SE,NO"),
):
    """
    Compare multiple countries across article coverage, credibility,
    top topics, and climate risk score.
    """
    codes = [c.strip().upper() for c in countries.split(",") if c.strip()]
    if not codes or len(codes) > 10:
        raise HTTPException(status_code=400, detail="Provide 1-10 comma-separated country codes")

    db = get_postgres()
    country_names = _get_country_names(db)
    results: List[CountryComparison] = []

    for cc in codes:
        try:
            # Basic stats
            stat_rows = db.execute_query("""
                SELECT COUNT(*) as cnt,
                       COUNT(DISTINCT source_name) as src_cnt,
                       AVG(reliability_score) as avg_cred
                FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
            """, {"cc": cc})
            s = stat_rows[0] if stat_rows else {}

            # Top topics
            topic_rows = db.execute_query("""
                SELECT UNNEST(tags) as tag, COUNT(*) as cnt
                FROM articles WHERE country_code = :cc AND tags IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
                GROUP BY tag ORDER BY cnt DESC LIMIT 5
            """, {"cc": cc})
            top_topics = [r["tag"] for r in (topic_rows or [])]

            # Category breakdown (sustainability dimensions)
            cat_rows = db.execute_query("""
                SELECT content_category, COUNT(*) as cnt
                FROM articles WHERE country_code = :cc AND content_category IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
                GROUP BY content_category ORDER BY cnt DESC
            """, {"cc": cc})
            category_breakdown = {r["content_category"]: r["cnt"] for r in (cat_rows or [])}

            # Climate risk score (normalised 0-10)
            risk_rows = db.execute_query("""
                SELECT COUNT(c.claim_id) as total_claims,
                       COUNT(CASE WHEN fc.verification_status
                             IN ('FALSE','MISLEADING','LACKS_CONTEXT') THEN 1 END) as disputed
                FROM claims c
                JOIN articles a ON a.article_id = c.article_id
                LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
                WHERE a.country_code = :cc
            """, {"cc": cc})
            risk_score = 0.0
            if risk_rows and risk_rows[0]["total_claims"]:
                tc = risk_rows[0]["total_claims"]
                disp = risk_rows[0].get("disputed", 0) or 0
                # Score: base from claim volume + penalty for disputed ratio
                risk_score = round(min(10.0, (tc / 5.0) + (disp / max(tc, 1)) * 5), 1)

            # Green transition dimension scores (0-10 scale, 2 articles/point)
            def _cat_score(cat: str) -> float:
                return round(min(10.0, category_breakdown.get(cat, 0) / 2.0), 1)

            # Recent articles (5) for the side-by-side compare view. Frontend
            # MapCompareView reads article_id/title/source_name/overall_credibility.
            recent_articles: List[Dict[str, Any]] = []
            try:
                ra_rows = db.execute_query("""
                    SELECT article_id, title, source_name, published_date, overall_credibility
                    FROM articles
                    WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
                    ORDER BY created_at DESC LIMIT 5
                """, {"cc": cc})
                recent_articles = [
                    {
                        "article_id": str(r["article_id"]),
                        "title": r.get("title", ""),
                        "source_name": r.get("source_name"),
                        "published_date": str(r["published_date"]) if r.get("published_date") else None,
                        "overall_credibility": r.get("overall_credibility") or "UNKNOWN",
                    }
                    for r in (ra_rows or [])
                ]
            except Exception:
                pass

            results.append(CountryComparison(
                country_code=cc,
                country_name=country_names.get(cc, cc),
                article_count=s.get("cnt", 0),
                source_count=s.get("src_cnt", 0),
                avg_credibility=round(float(s["avg_cred"]), 1) if s.get("avg_cred") else None,
                top_topics=top_topics,
                topic_count=len(top_topics),
                climate_risk_score=risk_score,
                climate_risk=risk_score,
                category_breakdown=category_breakdown if category_breakdown else None,
                green_transition_score=_cat_score("green_transition"),
                renewable_energy_score=_cat_score("renewable_energy"),
                cleantech_score=_cat_score("cleantech"),
                circular_economy_score=_cat_score("circular_economy"),
                resource_efficiency_score=_cat_score("resource_efficiency"),
                regenerative_score=_cat_score("regenerative_economy"),
                sustainability_score=_cat_score("sustainability"),
                recent_articles=recent_articles,
            ))
        except Exception as e:
            logger.warning(f"Compare failed for {cc}: {e}")
            results.append(CountryComparison(
                country_code=cc,
                country_name=country_names.get(cc, cc),
            ))

    # Build comparison summary
    summary = None
    if len(results) >= 2:
        ranked = sorted(results, key=lambda r: r.article_count, reverse=True)
        parts = [f"{r.country_name}: {r.article_count} articles" for r in ranked]
        top = ranked[0]
        summary = (
            f"Coverage comparison: {'; '.join(parts)}. "
            f"{top.country_name} has the most coverage"
        )
        if top.avg_credibility:
            summary += f" with avg credibility {top.avg_credibility}"
        summary += "."
        highest_risk = max(results, key=lambda r: r.climate_risk_score or 0)
        if highest_risk.climate_risk_score and highest_risk.climate_risk_score > 0:
            summary += (
                f" {highest_risk.country_name} has the highest climate risk score "
                f"({highest_risk.climate_risk_score}/10)."
            )

    return CompareResponse(
        countries=results,
        comparison_summary=summary,
        country_a=results[0] if results else None,
        country_b=results[1] if len(results) > 1 else None,
    )


@router.get("/timeline", response_model=List[TimelineEntry])
async def get_timeline(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    granularity: str = Query("month", description="Granularity: day, week, or month"),
):
    """
    Time series of article distribution across countries.
    Returns array of {date, data: {country_code: article_count}}.
    """
    db = get_postgres()

    trunc = granularity if granularity in ("day", "week", "month") else "month"

    try:
        rows = db.execute_query("""
            SELECT DATE_TRUNC(:trunc, created_at) as bucket,
                   country_code,
                   COUNT(*) as cnt
            FROM articles
            WHERE country_code IS NOT NULL
              AND is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND created_at >= :start_d
              AND created_at <= :end_d
            GROUP BY bucket, country_code
            ORDER BY bucket ASC
        """, {"trunc": trunc, "start_d": start_date, "end_d": end_date})

        # Pivot into {date -> {cc: count}}
        buckets: Dict[str, Dict[str, int]] = {}
        for r in (rows or []):
            d = str(r["bucket"].date()) if hasattr(r["bucket"], "date") else str(r["bucket"])
            buckets.setdefault(d, {})[r["country_code"]] = r["cnt"]

        return [
            TimelineEntry(date=d, data=cc_map)
            for d, cc_map in sorted(buckets.items())
        ]
    except Exception as e:
        logger.error(f"Timeline query failed: {e}")
        return []
