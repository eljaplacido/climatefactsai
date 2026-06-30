"""Map layer endpoints — temperature, climate risk, corporate density, news, warming, adaptation, NDC."""
from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
import httpx, math, asyncio

from .models import (TemperatureAnomalyItem, ClimateRiskItem, CorporateDensityItem,
                     NewsEventItem, WarmingOutlookItem, AdaptationGapItem, NdcStatusItem)
from .services import (_fetch_current_weather, _fetch_historical_weather, fetch_warming_risk_map)
from .cache import _cache_get, _cache_set
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("map-api")
router = APIRouter()


@router.get("/layers/temperature-anomaly", response_model=List[TemperatureAnomalyItem])
async def get_temperature_anomaly_layer():
    """
    Per-country temperature anomaly data for map layer rendering.

    For each country with articles in the DB, fetches current temperature
    and compares to the same month last year. Results cached for 6 hours.
    """
    from app.domains.content.forecast_service import COUNTRY_COORDS

    cache_key = "layer:temp_anomaly"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()

    # Countries that have articles
    try:
        cc_rows = db.execute_query("""
            SELECT DISTINCT country_code FROM articles
            WHERE country_code IS NOT NULL AND is_synthetic = FALSE AND is_off_topic = FALSE
        """)
        active_codes = [r["country_code"] for r in (cc_rows or [])]
    except Exception:
        active_codes = []

    results: List[TemperatureAnomalyItem] = []
    today = date.today()
    hist_start = date(today.year - 1, today.month, 1).isoformat()
    hist_end = date(today.year - 1, today.month, min(28, today.day)).isoformat()

    async def _fetch_anomaly_for(cc: str) -> Optional[TemperatureAnomalyItem]:
        coords = COUNTRY_COORDS.get(cc)
        if not coords:
            logger.debug(f"Skipping temperature anomaly for {cc}: no coordinates registered")
            return None
        lat, lon = coords["lat"], coords["lon"]
        current_wx = await _fetch_current_weather(lat, lon)
        hist = await _fetch_historical_weather(lat, lon, hist_start, hist_end)
        current_temp = current_wx.get("temperature_c") if current_wx else None
        current_precip = current_wx.get("precipitation_mm") if current_wx else None
        hist_avg = hist.get("temperature_avg") if hist else None
        hist_precip = hist.get("precipitation_avg") if hist else None
        anomaly = None
        trend = None
        if current_temp is not None and hist_avg is not None:
            anomaly = round(current_temp - hist_avg, 1)
            trend = "warmer" if anomaly > 1.0 else ("cooler" if anomaly < -1.0 else "normal")
        return TemperatureAnomalyItem(
            country_code=cc, anomaly_celsius=anomaly,
            trend=trend, current_temp=current_temp, historical_avg=hist_avg,
            current_precipitation_mm=current_precip,
            historical_precipitation_avg_mm=hist_precip,
        )

    # Fetch all countries concurrently (batches of 10 to avoid flooding)
    for i in range(0, len(active_codes), 10):
        batch = active_codes[i:i+10]
        batch_results = await asyncio.gather(
            *[_fetch_anomaly_for(cc) for cc in batch],
            return_exceptions=True,
        )
        for item in batch_results:
            if isinstance(item, TemperatureAnomalyItem):
                results.append(item)

    _cache_set(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# 7. GET /layers/climate-risk
# ---------------------------------------------------------------------------

@router.get("/layers/climate-risk", response_model=List[ClimateRiskItem])
async def get_climate_risk_layer():
    """
    Per-country PHYSICAL climate risk (0-10) from projected warming.

    The score is derived from IPCC AR6 SSP2-4.5 warming at 2050
    (`country_projections`, migration 035) — NOT article volume (2026-06-29).
    claim_count / disputed_ratio / top_risks are kept as supplementary
    article-derived context. Countries without a projection get risk_score
    None so the frontend can render them as "no data" grey.
    """
    cache_key = "layer:climate_risk"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()

    # Physical-risk scores keyed by country (excludes 'XX').
    warming_risk = fetch_warming_risk_map(db)

    try:
        rows = db.execute_query("""
            SELECT
                a.country_code,
                COUNT(DISTINCT a.article_id) as article_count,
                AVG(a.reliability_score) as avg_reliability,
                COUNT(c.claim_id) as total_claims,
                COUNT(CASE WHEN fc.verification_status
                      IN ('FALSE','MISLEADING','LACKS_CONTEXT','DISPUTED')
                      THEN 1 END) as disputed,
                COUNT(CASE WHEN fc.verification_status = 'UNVERIFIED'
                      THEN 1 END) as unverified
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.country_code IS NOT NULL AND a.is_synthetic = FALSE AND a.is_off_topic = FALSE
            GROUP BY a.country_code
            ORDER BY article_count DESC
        """)
    except Exception as e:
        logger.error(f"Climate risk layer query failed: {e}")
        return []

    results: List[ClimateRiskItem] = []
    for r in (rows or []):
        cc = r["country_code"]
        if cc == "XX":
            continue
        tc = r["total_claims"] or 0
        disp = r.get("disputed", 0) or 0
        unver = r.get("unverified", 0) or 0
        ratio = round((disp + unver) / tc, 3) if tc > 0 else 0.0
        # Physical risk from projected warming; None → frontend renders grey.
        score = warming_risk.get(cc)

        # Top risk categories
        top_risks: List[str] = []
        if tc > 0:
            try:
                risk_type_rows = db.execute_query("""
                    SELECT c.claim_type, COUNT(*) as cnt
                    FROM claims c
                    JOIN articles a ON a.article_id = c.article_id
                    WHERE a.country_code = :cc AND c.claim_type IS NOT NULL
                    GROUP BY c.claim_type ORDER BY cnt DESC LIMIT 3
                """, {"cc": r["country_code"]})
                top_risks = [rt["claim_type"] for rt in (risk_type_rows or [])]
            except Exception:
                pass

        results.append(ClimateRiskItem(
            country_code=r["country_code"],
            risk_score=score,
            claim_count=tc,
            disputed_ratio=ratio,
            top_risks=top_risks,
        ))

    _cache_set(cache_key, results)
    return results


@router.get("/layers/corporate-density", response_model=List[CorporateDensityItem])
async def get_corporate_density_layer():
    """Per-country corporate disclosure density for map choropleth rendering."""
    cache_key = "layer:corporate_density"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()
    try:
        rows = db.execute_query(
            """
            SELECT c.country_code,
                   COUNT(DISTINCT c.company_id) AS company_count,
                   COUNT(DISTINCT CASE WHEN cd.sbti_validated THEN c.company_id END) AS sbti_validated_count,
                   COUNT(DISTINCT CASE WHEN cd.net_zero_target_year IS NOT NULL THEN c.company_id END) AS net_zero_target_count
            FROM companies c
            LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
            WHERE c.country_code IS NOT NULL AND c.country_code <> ''
            GROUP BY c.country_code
            ORDER BY company_count DESC
            """
        )
    except Exception as exc:
        logger.error(f"Corporate density layer query failed: {exc}")
        return []

    payload = [
        CorporateDensityItem(
            country_code=r["country_code"],
            company_count=int(r.get("company_count") or 0),
            sbti_validated_count=int(r.get("sbti_validated_count") or 0),
            net_zero_target_count=int(r.get("net_zero_target_count") or 0),
        )
        for r in (rows or [])
    ]
    _cache_set(cache_key, payload)
    return payload


@router.get("/layers/news-events", response_model=List[NewsEventItem])
async def get_news_events_layer(
    window_days: int = Query(21, ge=1, le=90, description="Lookback window in days"),
):
    """Recent country-level news/event intensity with a controversy signal.

    Uses article volume in a rolling window plus disputed/unverified claim ratio
    to expose where climate news is currently most contentious.
    """
    cache_key = f"layer:news_events:{window_days}"
    cached = _cache_get(cache_key, ttl_seconds=3600)
    if cached is not None:
        return cached

    db = get_postgres()
    days = int(window_days)
    try:
        rows = db.execute_query(
            """
            SELECT a.country_code,
                   COUNT(DISTINCT a.article_id) AS event_count,
                   COUNT(CASE WHEN fc.verification_status
                         IN ('FALSE','MISLEADING','LACKS_CONTEXT','DISPUTED','UNVERIFIED')
                         THEN 1 END) AS disputed_count,
                   MAX(a.created_at) AS latest_event_at
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.article_id
            LEFT JOIN fact_checks fc ON fc.claim_id = c.claim_id
            WHERE a.country_code IS NOT NULL
              AND a.country_code <> ''
              AND a.is_synthetic = FALSE
              AND a.is_off_topic = FALSE
              AND a.created_at >= NOW() - make_interval(days => :days)
            GROUP BY a.country_code
            ORDER BY event_count DESC
            """,
            {"days": days},
        )
    except Exception as exc:
        logger.error(f"News-events layer query failed: {exc}")
        return []

    payload: List[NewsEventItem] = []
    for r in (rows or []):
        event_count = int(r.get("event_count") or 0)
        disputed_count = int(r.get("disputed_count") or 0)
        disputed_ratio = (disputed_count / event_count) if event_count > 0 else 0.0
        # Dense but bounded 0-10 score; volume + controversy contribution.
        controversy_score = round(min(10.0, math.log1p(event_count) * 1.8 + disputed_ratio * 4.0), 1)
        payload.append(
            NewsEventItem(
                country_code=r["country_code"],
                event_count=event_count,
                disputed_count=disputed_count,
                controversy_score=controversy_score,
                latest_event_at=str(r["latest_event_at"]) if r.get("latest_event_at") else None,
            )
        )

    _cache_set(cache_key, payload)
    return payload


@router.get("/layers/warming-outlook", response_model=List[WarmingOutlookItem])
async def get_warming_outlook_layer(
    horizon_year: int = Query(2050, ge=2030, le=2100, description="Target horizon year"),
):
    """Per-country projected warming from the IPCC AR6 country_projections table."""
    cache_key = f"layer:warming_outlook:{horizon_year}"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()
    try:
        rows = db.execute_query(
            """
            SELECT cc.country_code,
                   MAX(CASE WHEN cp.scenario = 'SSP1-2.6' THEN cp.temp_anomaly_c END) AS ssp126,
                   MAX(CASE WHEN cp.scenario = 'SSP2-4.5' THEN cp.temp_anomaly_c END) AS ssp245,
                   MAX(CASE WHEN cp.scenario = 'SSP3-7.0' THEN cp.temp_anomaly_c END) AS ssp370
            FROM countries cc
            LEFT JOIN country_projections cp
              ON cp.country_code = cc.country_code AND cp.horizon_year = :horizon
            WHERE cc.enabled = TRUE
            GROUP BY cc.country_code
            """
            , {"horizon": horizon_year},
        )
    except Exception as exc:
        logger.error(f"Warming outlook layer query failed: {exc}")
        return []

    payload: List[WarmingOutlookItem] = []
    for r in (rows or []):
        best = r.get("ssp245")
        payload.append(WarmingOutlookItem(
            country_code=r["country_code"],
            ssp126_anomaly_c=float(r["ssp126"]) if r.get("ssp126") is not None else None,
            ssp245_anomaly_c=float(r["ssp245"]) if r.get("ssp245") is not None else None,
            ssp370_anomaly_c=float(r["ssp370"]) if r.get("ssp370") is not None else None,
            best_estimate_c=float(best) if best is not None else None,
            covered=best is not None,
        ))

    _cache_set(cache_key, payload)
    return payload


@router.get("/layers/adaptation-finance-gap", response_model=List[AdaptationGapItem])
async def get_adaptation_finance_gap_layer():
    """Per-country adaptation finance gap estimate using ND-GAIN indicators.

    Reads ND-GAIN index, vulnerability, and readiness from country_indicators.
    The gap score combines low readiness + high vulnerability relative to the index.
    """
    cache_key = "layer:adaptation_gap"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()
    try:
        rows = db.execute_query(
            """
            SELECT ci.country_code,
                   MAX(CASE WHEN ci.indicator_id = 'nd_gain_index' THEN ci.value END) AS nd_gain,
                   MAX(CASE WHEN ci.indicator_id = 'nd_gain_vulnerability' THEN ci.value END) AS vulnerability,
                   MAX(CASE WHEN ci.indicator_id = 'nd_gain_readiness' THEN ci.value END) AS readiness
            FROM country_indicators ci
            WHERE ci.indicator_id IN ('nd_gain_index', 'nd_gain_vulnerability', 'nd_gain_readiness')
            GROUP BY ci.country_code
            """
        )
    except Exception as exc:
        logger.error(f"Adaptation gap layer query failed: {exc}")
        return []

    # Count total countries for coverage note
    try:
        total = db.execute_query("SELECT count(*) as cnt FROM countries WHERE enabled = TRUE")[0]["cnt"]
    except Exception:
        total = 0

    payload: List[AdaptationGapItem] = []
    for r in (rows or []):
        nd_gain = float(r["nd_gain"]) if r.get("nd_gain") is not None else None
        vuln = float(r["vulnerability"]) if r.get("vulnerability") is not None else None
        readiness = float(r["readiness"]) if r.get("readiness") is not None else None

        gap_score = None
        if nd_gain is not None:
            gap_score = round(max(0.0, min(10.0, (100.0 - nd_gain) / 10.0)), 1)

        payload.append(AdaptationGapItem(
            country_code=r["country_code"],
            nd_gain_index=nd_gain,
            vulnerability_score=vuln,
            readiness_score=readiness,
            adaptation_gap_score=gap_score,
            covered=nd_gain is not None,
        ))

    if total and int(total) > len(payload):
        logger.info(f"adaptation-finance-gap covers {len(payload)} of {total} countries")

    _cache_set(cache_key, payload)
    return payload


@router.get("/layers/ndc-status", response_model=List[NdcStatusItem])
async def get_ndc_status_layer():
    """Per-country NDC target status and CAT rating for map choropleth rendering.

    Reads from country_indicators (populated by UNFCCC NDC and CAT adapters).
    Coverage depends on prior syncs — countries with no NDC/CAT data show as 'no_data'.
    """
    cache_key = "layer:ndc_status"
    cached = _cache_get(cache_key, ttl_seconds=21600)
    if cached is not None:
        return cached

    db = get_postgres()
    try:
        rows = db.execute_query(
            """
            SELECT cc.country_code,
                   MAX(CASE WHEN ci.indicator_id = 'ndc_target_year' THEN ci.value END) AS ndc_target_year,
                   MAX(CASE WHEN ci.indicator_id = 'ndc_target_reduction_percent' THEN ci.value END) AS ndc_target_reduction_pct,
                   MAX(CASE WHEN ci.indicator_id = 'cat_overall_rating' THEN ci.value END) AS cat_overall_rating
            FROM countries cc
            LEFT JOIN country_indicators ci ON ci.country_code = cc.country_code
               AND ci.indicator_id IN ('ndc_target_year', 'ndc_target_reduction_percent', 'cat_overall_rating')
            WHERE cc.enabled = TRUE
            GROUP BY cc.country_code
            ORDER BY cc.country_code
            """
        )
    except Exception as exc:
        logger.error(f"NDC status layer query failed: {exc}")
        return []

    payload: List[NdcStatusItem] = []
    for r in (rows or []):
        year = int(r["ndc_target_year"]) if r.get("ndc_target_year") is not None else None
        pct = float(r["ndc_target_reduction_pct"]) if r.get("ndc_target_reduction_pct") is not None else None
        cat = float(r["cat_overall_rating"]) if r.get("cat_overall_rating") is not None else None

        # Classification logic: CAT rating > NDC ambition > no data
        if pct is not None and pct >= 90:
            status = "net_zero"
        elif cat is not None and cat >= 60:
            status = "strong"
        elif cat is not None and cat >= 30:
            status = "moderate"
        elif cat is not None:
            status = "weak"
        elif year is not None or pct is not None:
            status = "moderate"
        else:
            status = "no_data"

        payload.append(NdcStatusItem(
            country_code=r["country_code"],
            ndc_target_year=year,
            ndc_target_reduction_pct=pct,
            cat_overall_rating=cat,
            status_category=status,
        ))

    _cache_set(cache_key, payload)
    return payload


@router.get("/biome-overview")
async def get_biome_overview_route():
    """All-countries biome + Köppen-Geiger climate-zone map (Phase 11).

    Single response feeds the world-map biome layer (chloropleth fill
    by Köppen colour + emoji marker at country centroid). Includes the
    biome + Köppen taxonomies so the frontend renders a legend without
    a second round-trip.
    """
    from app.domains.content.country_biome_map import biome_overview_payload
    return biome_overview_payload()
