from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CountryStats(BaseModel):
    """Per-country article statistics for the map view."""
    country_code: str
    country_name: str
    article_count: int = 0
    top_topics: List[str] = []
    last_updated: Optional[str] = None
    avg_credibility_score: Optional[float] = None
    top_sources: List[str] = []
    region: Optional[str] = None
    temperature_anomaly: Optional[float] = None
    climate_risk_score: Optional[float] = None
    source_count: Optional[int] = None
    company_count: Optional[int] = None
    sbti_validated_count: Optional[int] = None
    net_zero_target_count: Optional[int] = None


class TopicDensityItem(BaseModel):
    """Topic density per country for heatmap overlay."""
    country_code: str
    topic: str
    article_count: int = 0
    density: float = 0.0


class SourceCoverageItem(BaseModel):
    """Which sources cover which countries."""
    source_name: str
    country_code: str
    article_count: int = 0
    avg_credibility: Optional[float] = None


class MapQueryRequest(BaseModel):
    """Natural-language or structured query for map-driven exploration."""
    query: Optional[str] = Field(None, max_length=500, description="Natural language query")
    countries: List[str] = Field(default_factory=list, description="Filter by country codes")
    region: Optional[str] = Field(None, description="Filter by region: europe, africa, asia, etc.")
    sources: List[str] = Field(default_factory=list, description="Filter by source names")
    reliability_min: Optional[int] = Field(None, ge=0, le=100)
    categories: List[str] = Field(default_factory=list)
    topic: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    session_id: Optional[str] = Field(None, description="Session ID for follow-up queries")
    view_context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "What the user is currently viewing on the map (selected country, "
            "compare overlay, etc.). Used to ground pronoun resolution in the "
            "agentic answer; same shape as /api/chat view_context."
        ),
    )
    source_mode: Optional[str] = Field(
        "platform",
        description=(
            "Answer grounding: 'platform' (corpus only — default), 'web' "
            "(external web search), or 'both'. web/both use deep-search."
        ),
    )


class MapQueryResponse(BaseModel):
    """Response with map-ready data from a query."""
    query: Optional[str] = None
    country_highlights: List[CountryStats] = []
    matching_articles: int = 0
    answer: Optional[str] = None
    # Agentic next-step suggestions (audit 2026-06-10) — the frontend renders
    # data.actions for every chat mode, so the map assistant can now act, not
    # just answer.
    actions: List[Dict[str, Any]] = []
    highlighted_countries: List[str] = []
    filters_applied: Dict[str, Any] = {}
    session_id: Optional[str] = None
    queried_at: str


# ---------------------------------------------------------------------------
# New response models for extended endpoints
# ---------------------------------------------------------------------------

class ArticleBrief(BaseModel):
    """Brief article representation for country detail."""
    article_id: str
    title: str
    source_name: Optional[str] = None
    published_date: Optional[str] = None
    credibility: Optional[str] = None
    excerpt: Optional[str] = None


class WeatherInfo(BaseModel):
    """Current weather snapshot."""
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    temperature_anomaly_c: Optional[float] = None


class CountryDetail(BaseModel):
    """Rich detail for a single country."""
    country_code: str
    country_name: str
    continent: Optional[str] = None
    region: Optional[str] = None
    flag_emoji: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    weather: Optional[WeatherInfo] = None
    article_count: int = 0
    articles_by_category: Dict[str, int] = {}
    avg_credibility: Optional[float] = None
    recent_articles: List[ArticleBrief] = []
    source_coverage: List[Dict[str, Any]] = []
    high_severity_claims: int = 0
    disputed_claims_ratio: Optional[float] = None
    # seq-11 (2026-06-02): the panel's risk card read this but /detail never
    # returned it (only /compare did), so every country showed 0/10. Now
    # computed with the same _compute_climate_risk_score as compare + the layer.
    climate_risk_score: Optional[float] = None


class TrendPoint(BaseModel):
    """Single data point in a time series."""
    date: str
    article_count: int = 0
    avg_credibility: Optional[float] = None


class ClimateDataPoint(BaseModel):
    """Temperature / precipitation comparison point."""
    period: str
    temperature_avg_c: Optional[float] = None
    precipitation_avg_mm: Optional[float] = None


class CountryClimateData(BaseModel):
    """Climate comparison data for a country."""
    country_code: str
    current_month: Optional[ClimateDataPoint] = None
    last_year_same_month: Optional[ClimateDataPoint] = None
    five_years_ago_same_month: Optional[ClimateDataPoint] = None
    temperature_trend: Optional[str] = None  # rising / falling / stable
    precipitation_comparison: Optional[str] = None


class CountryComparison(BaseModel):
    """Comparison metrics for one country — includes green transition dimensions."""
    country_code: str
    country_name: str
    article_count: int = 0
    source_count: int = 0
    avg_credibility: Optional[float] = None
    top_topics: List[str] = []
    topic_count: Optional[int] = None
    climate_risk_score: Optional[float] = None
    climate_risk: Optional[float] = None  # frontend-compatible alias
    category_breakdown: Optional[Dict[str, int]] = None
    # Green-transition dimensions (0–10 score derived from article coverage)
    green_transition_score: Optional[float] = None
    renewable_energy_score: Optional[float] = None
    cleantech_score: Optional[float] = None
    circular_economy_score: Optional[float] = None
    resource_efficiency_score: Optional[float] = None
    regenerative_score: Optional[float] = None
    sustainability_score: Optional[float] = None
    # Recent articles for the side-by-side compare view. Keys match the
    # frontend MapCompareView shape (overall_credibility, not `credibility`).
    recent_articles: List[Dict[str, Any]] = []


class CompareResponse(BaseModel):
    """Response for /compare endpoint."""
    countries: List[CountryComparison] = []
    comparison_summary: Optional[str] = None
    # Convenience keys for frontend two-country compare view
    country_a: Optional[CountryComparison] = None
    country_b: Optional[CountryComparison] = None


class TimelineEntry(BaseModel):
    """One time bucket in the timeline."""
    date: str
    data: Dict[str, int] = {}


class TemperatureAnomalyItem(BaseModel):
    """Per-country temperature anomaly for map layer."""
    country_code: str
    anomaly_celsius: Optional[float] = None
    trend: Optional[str] = None
    current_temp: Optional[float] = None
    historical_avg: Optional[float] = None
    current_precipitation_mm: Optional[float] = None
    historical_precipitation_avg_mm: Optional[float] = None


class ClimateRiskItem(BaseModel):
    """Per-country climate risk from article claims."""
    country_code: str
    risk_score: float = 0.0
    claim_count: int = 0
    disputed_ratio: float = 0.0
    top_risks: List[str] = []


class CountryCompanyItem(BaseModel):
    """Company summary scoped to a country."""
    company_id: str
    name: str
    ticker: Optional[str] = None
    country_code: Optional[str] = None
    sector_nace: Optional[str] = None
    disclosure_count: int = 0
    latest_disclosure_year: Optional[int] = None
    sbti_validated: bool = False
    net_zero_target_year: Optional[int] = None


class CorporateDensityItem(BaseModel):
    """Per-country corporate climate-data density for map layer rendering."""
    country_code: str
    company_count: int = 0
    sbti_validated_count: int = 0
    net_zero_target_count: int = 0


class NewsEventItem(BaseModel):
    """Per-country recent news/event intensity for map overlay."""
    country_code: str
    event_count: int = 0
    disputed_count: int = 0
    controversy_score: float = 0.0
    latest_event_at: Optional[str] = None


class NdcStatusItem(BaseModel):
    """Per-country NDC target status for map layer."""
    country_code: str
    ndc_target_year: Optional[int] = None
    ndc_target_reduction_pct: Optional[float] = None
    cat_overall_rating: Optional[float] = None
    status_category: str = "no_data"  # net_zero | strong | moderate | weak | no_data


class WarmingOutlookItem(BaseModel):
    """Per-country projected warming at a given horizon."""
    country_code: str
    ssp126_anomaly_c: Optional[float] = None
    ssp245_anomaly_c: Optional[float] = None
    ssp370_anomaly_c: Optional[float] = None
    best_estimate_c: Optional[float] = None
    covered: bool = False


class AdaptationGapItem(BaseModel):
    """Per-country adaptation finance gap indicator for map layer."""
    country_code: str
    nd_gain_index: Optional[float] = None
    vulnerability_score: Optional[float] = None
    readiness_score: Optional[float] = None
    adaptation_gap_score: Optional[float] = None
    covered: bool = False


# Region → country code mapping for region-based queries (comprehensive — 80%+ of world)
REGION_COUNTRIES = {
    "europe": [
        "FI", "SE", "NO", "DK", "IS", "GB", "IE", "FR", "DE", "NL", "BE", "LU",
        "CH", "AT", "LI", "ES", "PT", "IT", "MT", "GR", "CY", "TR", "PL", "CZ",
        "SK", "HU", "SI", "RO", "BG", "HR", "RS", "BA", "ME", "MK", "AL", "XK",
        "EE", "LV", "LT", "UA", "MD", "BY", "GE", "AM", "AZ", "RU", "MC", "AD",
        "SM", "VA",
    ],
    "north_america": ["US", "CA", "MX", "GL"],
    "central_america": [
        "GT", "HN", "SV", "NI", "CR", "PA", "BZ",
        "CU", "DO", "HT", "JM", "TT", "BS", "BB",
        "AG", "GD", "DM", "KN", "LC", "VC",
    ],
    "latin_america": [
        "BR", "AR", "CO", "CL", "PE", "EC", "VE", "UY", "PY", "BO",
        "CR", "PA", "GT", "HN", "SV", "NI", "CU", "DO", "HT", "JM",
        "TT", "GY", "SR", "BS", "BB", "BZ",
    ],
    "africa": [
        "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD",
        "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET",
        "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG",
        "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW",
        "SN", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG",
        "ZM", "ZW", "ST", "SC", "EH",
    ],
    "asia": [
        "AF", "BD", "BT", "BN", "KH", "CN", "HK", "IN", "ID", "IR", "IQ",
        "IL", "JP", "JO", "KZ", "KW", "KG", "LA", "LB", "MY", "MV",
        "MN", "MM", "NP", "PK", "PH", "QA", "SA", "SG", "KR", "LK",
        "SY", "TW", "TJ", "TH", "TL", "TM", "AE", "UZ", "VN", "YE",
        "OM", "BH", "PS", "GE", "AM", "AZ",
    ],
    "middle_east": [
        "AE", "SA", "IL", "JO", "LB", "IQ", "IR", "QA", "KW", "OM",
        "BH", "YE", "SY", "PS",
    ],
    "oceania": [
        "AU", "NZ", "PG", "FJ", "WS", "SB", "TO", "VU",
        "KI", "MH", "FM", "NR", "PW", "TV",
    ],
    "central_asia": ["KZ", "UZ", "TM", "KG", "TJ"],
}
