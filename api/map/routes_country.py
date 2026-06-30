"""Map routes — country detail, trends, climate, companies, biome, projections."""
from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from .models import (CountryDetail, WeatherInfo, ArticleBrief, TrendPoint,
                     ClimateDataPoint, CountryClimateData, CountryCompanyItem, REGION_COUNTRIES)
from .services import (_get_country_names, _country_region, fetch_warming_risk_map,
                       _fetch_current_weather, _fetch_historical_weather)
from .cache import _cache_get, _cache_set
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("map-api")
router = APIRouter()

# ---------------------------------------------------------------------------
# 1. GET /country/{cc}/detail
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/detail", response_model=CountryDetail)
async def get_country_detail(cc: str):
    """
    Rich country detail endpoint.

    Returns country metadata, current weather, temperature anomaly,
    article statistics, top 5 recent articles, source coverage,
    and climate risk indicators from article claims.
    """
    from app.domains.content.forecast_service import COUNTRY_COORDS, COUNTRY_NAMES

    cc = cc.upper()
    db = get_postgres()

    # --- Country info from DB -------------------------------------------------
    country_row = None
    try:
        rows = db.execute_query(
            """SELECT country_code, country_name, continent, flag_emoji,
                      latitude, longitude
               FROM countries WHERE country_code = :cc""",
            {"cc": cc},
        )
        if rows:
            country_row = rows[0]
    except Exception:
        pass

    country_name = (
        (country_row or {}).get("country_name")
        or COUNTRY_NAMES.get(cc, cc)
    )
    continent = (country_row or {}).get("continent")
    flag = (country_row or {}).get("flag_emoji")
    lat = float((country_row or {}).get("latitude") or 0)
    lon = float((country_row or {}).get("longitude") or 0)

    coords = COUNTRY_COORDS.get(cc)
    if coords:
        lat = lat or coords["lat"]
        lon = lon or coords["lon"]

    # --- Weather (Open-Meteo) -------------------------------------------------
    weather = None
    if lat and lon:
        current_wx = await _fetch_current_weather(lat, lon)
        if current_wx:
            # Historical average for same month to compute anomaly
            today = date.today()
            hist_start = date(today.year - 1, today.month, 1).isoformat()
            hist_end = date(today.year - 1, today.month,
                           min(28, today.day)).isoformat()
            hist = await _fetch_historical_weather(lat, lon, hist_start, hist_end)
            anomaly = None
            if hist and hist.get("temperature_avg") is not None and current_wx.get("temperature_c") is not None:
                anomaly = round(current_wx["temperature_c"] - hist["temperature_avg"], 1)
            weather = WeatherInfo(
                temperature_c=current_wx.get("temperature_c"),
                humidity_pct=current_wx.get("humidity_pct"),
                precipitation_mm=current_wx.get("precipitation_mm"),
                wind_speed_kmh=current_wx.get("wind_speed_kmh"),
                temperature_anomaly_c=anomaly,
            )

    # --- Article statistics ---------------------------------------------------
    try:
        stat_rows = db.execute_query("""
            SELECT COUNT(*) as total,
                   AVG(reliability_score) as avg_cred
            FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
        """, {"cc": cc})
        total = stat_rows[0]["total"] if stat_rows else 0
        avg_cred = (
            round(float(stat_rows[0]["avg_cred"]), 1)
            if stat_rows and stat_rows[0].get("avg_cred") else None
        )
    except Exception:
        total, avg_cred = 0, None

    # Count by category
    articles_by_cat: Dict[str, int] = {}
    try:
        cat_rows = db.execute_query("""
            SELECT COALESCE(content_category, 'uncategorised') as cat, COUNT(*) as cnt
            FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
            GROUP BY cat ORDER BY cnt DESC
        """, {"cc": cc})
        articles_by_cat = {r["cat"]: r["cnt"] for r in (cat_rows or [])}
    except Exception:
        pass

    # --- Top 5 recent articles ------------------------------------------------
    recent: List[ArticleBrief] = []
    try:
        art_rows = db.execute_query("""
            SELECT article_id, title, source_name, published_date,
                   overall_credibility, excerpt
            FROM articles WHERE country_code = :cc AND is_synthetic = FALSE AND is_off_topic = FALSE
            ORDER BY created_at DESC LIMIT 5
        """, {"cc": cc})
        recent = [
            ArticleBrief(
                article_id=str(r["article_id"]),
                title=r.get("title", ""),
                source_name=r.get("source_name"),
                published_date=str(r["published_date"]) if r.get("published_date") else None,
                credibility=r.get("overall_credibility"),
                excerpt=(r.get("excerpt") or "")[:200],
            )
            for r in (art_rows or [])
        ]
    except Exception:
        pass

    # --- Source coverage -------------------------------------------------------
    # End2End audit (2026-05-27 §7.4 + §8.2): top-source breakdown was a single
    # "avg_credibility" number per source. Now JOIN source_credibility_tiers
    # (mig 027 + 041) so the map country panel can render the 3-axis editorial
    # / factcheck / transparency chip per source instead of a single rolled-up
    # number. LEFT JOIN so un-tiered sources still appear (with NULL axes).
    source_coverage: List[Dict[str, Any]] = []
    try:
        src_rows = db.execute_query("""
            SELECT a.source_name,
                   COUNT(*) as cnt,
                   AVG(a.reliability_score) as avg_rel,
                   MAX(sct.tier) as tier,
                   MAX(sct.editorial_score) as editorial_score,
                   MAX(sct.factcheck_score) as factcheck_score,
                   MAX(sct.transparency_score) as transparency_score
            FROM articles a
            LEFT JOIN source_credibility_tiers sct
              ON sct.domain = LOWER(a.source_name)
              OR sct.source_name = a.source_name
            WHERE a.country_code = :cc
              AND a.source_name IS NOT NULL
              AND a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
            GROUP BY a.source_name
            ORDER BY cnt DESC
            LIMIT 10
        """, {"cc": cc})
        source_coverage = [
            {
                "source_name": r["source_name"],
                "article_count": r["cnt"],
                "avg_credibility": round(float(r["avg_rel"]), 1) if r.get("avg_rel") else None,
                "tier": r.get("tier"),
                "editorial_score": int(r["editorial_score"]) if r.get("editorial_score") is not None else None,
                "factcheck_score": int(r["factcheck_score"]) if r.get("factcheck_score") is not None else None,
                "transparency_score": int(r["transparency_score"]) if r.get("transparency_score") is not None else None,
            }
            for r in (src_rows or [])
        ]
    except Exception:
        pass

    # --- Climate risk indicators from claims -----------------------------------
    high_severity = 0
    disputed_ratio: Optional[float] = None
    total_claims = 0
    disputed_count = 0
    try:
        risk_rows = db.execute_query("""
            SELECT
                COUNT(c.claim_id) as total_claims,
                COUNT(CASE WHEN fc.verification_status IN ('FALSE','MISLEADING','LACKS_CONTEXT')
                      THEN 1 END) as disputed,
                COUNT(CASE WHEN c.claim_type IN ('prediction','factual_data')
                      THEN 1 END) as high_severity
            FROM claims c
            JOIN articles a ON a.article_id = c.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.country_code = :cc
        """, {"cc": cc})
        if risk_rows and risk_rows[0]["total_claims"]:
            total_claims = risk_rows[0]["total_claims"]
            high_severity = risk_rows[0].get("high_severity", 0) or 0
            disputed_count = risk_rows[0].get("disputed", 0) or 0
            disputed_ratio = round(disputed_count / total_claims, 3) if total_claims > 0 else 0.0
    except Exception:
        pass

    # Physical climate risk = projected warming (IPCC AR6 SSP2-4.5, 2050) —
    # the SAME source as /compare + the choropleth layer (2026-06-30), so the
    # panel's risk card matches the map coloring. None when no AR6 projection
    # exists (panel renders "no data"/grey, not a misleading 0/10).
    climate_risk_score = fetch_warming_risk_map(db).get(cc)

    return CountryDetail(
        country_code=cc,
        country_name=country_name,
        continent=continent,
        region=_country_region(cc),
        flag_emoji=flag,
        latitude=lat or None,
        longitude=lon or None,
        weather=weather,
        article_count=total,
        articles_by_category=articles_by_cat,
        avg_credibility=avg_cred,
        recent_articles=recent,
        source_coverage=source_coverage,
        high_severity_claims=high_severity,
        disputed_claims_ratio=disputed_ratio,
        climate_risk_score=climate_risk_score,
    )


# ---------------------------------------------------------------------------
# 2. GET /country/{cc}/trends
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/trends", response_model=List[TrendPoint])
async def get_country_trends(
    cc: str,
    period: str = Query("6m", description="Time period: 1m, 3m, 6m, 1y, 2y"),
    granularity: str = Query("month", description="Granularity: week or month"),
):
    """
    Article volume time series for a country.
    Returns array of {date, article_count, avg_credibility} grouped by month or week.
    """
    cc = cc.upper()
    db = get_postgres()

    # Resolve period to an interval string
    period_map = {"1m": "1 month", "3m": "3 months", "6m": "6 months", "1y": "1 year", "2y": "2 years"}
    interval = period_map.get(period, "6 months")

    trunc = "month" if granularity != "week" else "week"

    try:
        rows = db.execute_query(f"""
            SELECT DATE_TRUNC(:trunc, created_at) as bucket,
                   COUNT(*) as article_count,
                   AVG(reliability_score) as avg_cred
            FROM articles
            WHERE country_code = :cc
              AND is_synthetic = FALSE
              AND is_off_topic = FALSE
              AND created_at >= NOW() - INTERVAL '{interval}'
            GROUP BY bucket
            ORDER BY bucket ASC
        """, {"cc": cc, "trunc": trunc})

        return [
            TrendPoint(
                date=str(r["bucket"].date()) if hasattr(r["bucket"], "date") else str(r["bucket"]),
                article_count=r["article_count"],
                avg_credibility=round(float(r["avg_cred"]), 1) if r.get("avg_cred") else None,
            )
            for r in (rows or [])
        ]
    except Exception as e:
        logger.error(f"Country trends query failed for {cc}: {e}")
        return []


# ---------------------------------------------------------------------------
# 3. GET /country/{cc}/climate-data
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/climate-data", response_model=CountryClimateData)
async def get_country_climate_data(cc: str):
    """
    Temperature anomaly and precipitation data for a country.

    Compares current month averages against the same month last year
    and five years ago using the Open-Meteo archive API.
    """
    from app.domains.content.forecast_service import COUNTRY_COORDS

    cc = cc.upper()
    coords = COUNTRY_COORDS.get(cc)
    if not coords:
        # Return an empty payload rather than 404 so the UI can render
        # an article-only view for countries without coordinate data.
        return CountryClimateData(country_code=cc)

    lat, lon = coords["lat"], coords["lon"]
    today = date.today()
    m, d = today.month, min(today.day, 28)

    async def _period_data(year: int) -> Optional[ClimateDataPoint]:
        start = date(year, m, 1).isoformat()
        end = date(year, m, d).isoformat()
        h = await _fetch_historical_weather(lat, lon, start, end)
        if not h:
            return None
        return ClimateDataPoint(
            period=f"{year}-{m:02d}",
            temperature_avg_c=h.get("temperature_avg"),
            precipitation_avg_mm=h.get("precipitation_avg"),
        )

    current = await _period_data(today.year)
    last_year = await _period_data(today.year - 1)
    five_ago = await _period_data(today.year - 5)

    # Determine trend
    trend = None
    if current and last_year and five_ago:
        temps = [
            p.temperature_avg_c for p in [five_ago, last_year, current]
            if p and p.temperature_avg_c is not None
        ]
        if len(temps) >= 2:
            diff = temps[-1] - temps[0]
            if diff > 0.5:
                trend = "rising"
            elif diff < -0.5:
                trend = "falling"
            else:
                trend = "stable"

    # Precipitation comparison
    precip_cmp = None
    if current and last_year:
        cp = current.precipitation_avg_mm
        lp = last_year.precipitation_avg_mm
        if cp is not None and lp is not None and lp > 0:
            pct = ((cp - lp) / lp) * 100
            if pct > 10:
                precip_cmp = f"{pct:+.0f}% wetter than last year"
            elif pct < -10:
                precip_cmp = f"{pct:+.0f}% drier than last year"
            else:
                precip_cmp = "similar to last year"

    return CountryClimateData(
        country_code=cc,
        current_month=current,
        last_year_same_month=last_year,
        five_years_ago_same_month=five_ago,
        temperature_trend=trend,
        precipitation_comparison=precip_cmp,
    )


# ---------------------------------------------------------------------------
# 4. GET /country/{cc}/companies
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/companies", response_model=List[CountryCompanyItem])
async def get_country_companies(
    cc: str,
    sbti_only: bool = Query(False, description="Only companies with SBTi-validated disclosures"),
    limit: int = Query(25, ge=1, le=200),
):
    """Return companies associated with a country code.

    This is the map-side reverse lookup for the Corporate Tracker surface,
    powering the country panel's Companies tab.
    """
    db = get_postgres()
    cc = (cc or "").upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")

    try:
        rows = db.execute_query(
            """
            SELECT c.company_id,
                   c.name,
                   c.ticker,
                   c.country_code,
                   c.sector_nace,
                   COUNT(cd.disclosure_id) AS disclosure_count,
                   MAX(cd.reporting_year) AS latest_disclosure_year,
                   COALESCE(BOOL_OR(cd.sbti_validated), FALSE) AS sbti_validated,
                   MAX(cd.net_zero_target_year) AS net_zero_target_year
            FROM companies c
            LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
            WHERE c.country_code = :cc
            GROUP BY c.company_id, c.name, c.ticker, c.country_code, c.sector_nace
            HAVING (:sbti_only = FALSE OR COALESCE(BOOL_OR(cd.sbti_validated), FALSE) = TRUE)
            ORDER BY COALESCE(BOOL_OR(cd.sbti_validated), FALSE) DESC,
                     COUNT(cd.disclosure_id) DESC,
                     c.name ASC
            LIMIT :limit
            """,
            {"cc": cc, "sbti_only": sbti_only, "limit": limit},
        )
    except Exception as exc:
        logger.error(f"Country companies query failed for {cc}: {exc}")
        return []

    return [
        CountryCompanyItem(
            company_id=str(r["company_id"]),
            name=r.get("name") or "",
            ticker=r.get("ticker"),
            country_code=r.get("country_code"),
            sector_nace=r.get("sector_nace"),
            disclosure_count=int(r.get("disclosure_count") or 0),
            latest_disclosure_year=int(r["latest_disclosure_year"]) if r.get("latest_disclosure_year") is not None else None,
            sbti_validated=bool(r.get("sbti_validated") or False),
            net_zero_target_year=int(r["net_zero_target_year"]) if r.get("net_zero_target_year") is not None else None,
        )
        for r in (rows or [])
    ]


# ---------------------------------------------------------------------------
# 5. GET /country/{cc}/claim-ledger
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/claim-ledger")
async def get_country_claim_ledger(
    cc: str,
    since_days: int = Query(365, ge=1, le=730),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_postgres()
    cc = cc.upper()[:2]
    interval = f"{int(since_days)} days"
    try:
        rows = db.execute_query(
            """SELECT c.claim_id, c.claim_text, c.claim_type, c.claim_category,
                      a.title AS article_title, a.source_name, a.published_date,
                      a.overall_credibility, cp.confidence
               FROM claims c
               JOIN articles a ON a.article_id = c.article_id
               LEFT JOIN claim_provenance cp ON cp.claim_id = c.claim_id
               WHERE a.country_code = :cc AND a.is_synthetic = FALSE AND a.is_off_topic = FALSE
                 AND c.created_at > NOW() - :interval::interval
               ORDER BY c.created_at DESC LIMIT :limit""",
            {"cc": cc, "interval": interval, "limit": limit},
        )
    except Exception as exc:
        logger.warning(f"claim_ledger query failed: {exc}")
        rows = []
    claims = []
    for r in rows or []:
        claims.append({
            "claim_id": str(r["claim_id"]),
            "claim_text": r["claim_text"],
            "claim_type": r.get("claim_type"),
            "claim_category": r.get("claim_category"),
            "article_title": r.get("article_title"),
            "source_name": r.get("source_name"),
            "published_date": str(r.get("published_date")) if r.get("published_date") else None,
            "overall_credibility": r.get("overall_credibility"),
            "confidence": r.get("confidence"),
        })
    return {"country_code": cc, "since_days": since_days, "claims": claims, "total": len(claims)}


# ---------------------------------------------------------------------------
# 6. GET /country/{cc}/biome
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/biome")
async def get_country_biome_route(cc: str):
    """Per-country biome + climate-effects narrative + drill-down hooks
    + symbol metadata for map rendering.

    Phase 11 (2026-05-25) — merges the curated narrative (22 countries)
    with the comprehensive biome+Köppen mapping (195 countries) so the
    Country Passport biome panel + the world map biome layer pull from
    the same response.
    """
    from app.domains.content.country_biome import country_biome_payload
    from app.domains.content.country_biome_map import country_biome_map_entry

    cc = (cc or "").upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")

    narrative = country_biome_payload(cc)
    map_entry = country_biome_map_entry(cc)
    # Merge: keep the narrative shape but add the symbol/koppen metadata.
    return {
        **narrative,
        "biome_symbol": {
            "biome_id": map_entry["biome_id"],
            "biome_label": map_entry["biome_label"],
            "biome_emoji": map_entry["biome_emoji"],
            "koppen_id": map_entry["koppen_id"],
            "koppen_label": map_entry["koppen_label"],
            "koppen_color": map_entry["koppen_color"],
        },
    }


# ---------------------------------------------------------------------------
# 7. GET /country/{cc}/projections
# ---------------------------------------------------------------------------

@router.get("/country/{cc}/projections")
async def get_country_projections(cc: str):
    """Warming projections per scenario + horizon for a single country."""
    cc = cc.upper().strip()
    if len(cc) != 2 or not cc.isalpha():
        raise HTTPException(status_code=400, detail="Invalid country code")

    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT scenario, horizon_year, temp_anomaly_c,
                      methodology_version, citation_url
               FROM country_projections
               WHERE country_code = :cc
               ORDER BY scenario, horizon_year""",
            {"cc": cc},
        )
    except Exception as exc:
        logger.warning(f"Country projections query failed for {cc}: {exc}")
        rows = []

    # Group rows by scenario for the frontend.
    scenarios: dict = {}
    citation_url = None
    methodology_version = None
    for r in rows or []:
        sc = r["scenario"]
        scenarios.setdefault(sc, []).append({
            "horizon_year": r["horizon_year"],
            "temp_anomaly_c": float(r["temp_anomaly_c"]),
        })
        citation_url = citation_url or r.get("citation_url")
        methodology_version = methodology_version or r.get("methodology_version")

    return {
        "country_code": cc,
        "scenarios": scenarios,
        "available": bool(scenarios),
        "methodology_version": methodology_version,
        "citation_url": citation_url,
        "baseline_note": "Warming relative to 1850-1900 pre-industrial baseline.",
    }
