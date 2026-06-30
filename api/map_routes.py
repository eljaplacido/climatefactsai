"""
Map Routes — backward-compatible re-export shim.

Monolith split (2026-06-17 audit): api/map_routes.py (2530 lines) was
refactored into the modular api/map/ package. This file re-exports all
public symbols to keep existing imports working across tests and e2e code.

New code should import directly from api.map.* sub-modules.
"""
from api.map import router
from api.map.models import (
    CountryStats,
    TopicDensityItem,
    SourceCoverageItem,
    MapQueryRequest,
    MapQueryResponse,
    ArticleBrief,
    WeatherInfo,
    CountryDetail,
    TrendPoint,
    ClimateDataPoint,
    CountryClimateData,
    CountryComparison,
    CompareResponse,
    TimelineEntry,
    TemperatureAnomalyItem,
    ClimateRiskItem,
    CountryCompanyItem,
    CorporateDensityItem,
    NewsEventItem,
    NdcStatusItem,
    WarmingOutlookItem,
    AdaptationGapItem,
    REGION_COUNTRIES,
)
from api.map.services import (
    _get_country_names,
    _country_region,
    fetch_warming_risk_map,
    warming_to_risk_score,
    _fetch_current_weather,
    _fetch_historical_weather,
    _llm_parse_query,
    _llm_generate_map_answer,
)
from api.map.cache import _cache, _cache_get, _cache_set, _query_sessions

__all__ = [
    "router",
    "CountryStats",
    "TopicDensityItem",
    "SourceCoverageItem",
    "MapQueryRequest",
    "MapQueryResponse",
    "ArticleBrief",
    "WeatherInfo",
    "CountryDetail",
    "TrendPoint",
    "ClimateDataPoint",
    "CountryClimateData",
    "CountryComparison",
    "CompareResponse",
    "TimelineEntry",
    "TemperatureAnomalyItem",
    "ClimateRiskItem",
    "CountryCompanyItem",
    "CorporateDensityItem",
    "NewsEventItem",
    "NdcStatusItem",
    "WarmingOutlookItem",
    "AdaptationGapItem",
    "REGION_COUNTRIES",
    "_get_country_names",
    "_country_region",
    "fetch_warming_risk_map",
    "warming_to_risk_score",
    "_fetch_current_weather",
    "_fetch_historical_weather",
    "_llm_parse_query",
    "_llm_generate_map_answer",
    "_cache_get",
    "_cache_set",
    "_query_sessions",
]
