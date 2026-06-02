"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  X,
  Loader2,
  Thermometer,
  Droplets,
  Wind,
  AlertTriangle,
  BarChart3,
  Newspaper,
  Globe,
  GitCompare,
  ChevronRight,
  Shield,
} from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import type { Article } from "@/types";
import CountrySelector from "@/components/CountrySelector";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const WEATHER_CODES: Record<number, string> = {
  0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
  45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
  55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
  71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Slight showers",
  81: "Moderate showers", 82: "Violent showers", 95: "Thunderstorm",
  96: "Thunderstorm with hail",
};

// Country flag emoji from code
function getFlagEmoji(cc: string): string {
  if (!cc || cc.length !== 2) return "";
  const codePoints = cc
    .toUpperCase()
    .split("")
    .map((c) => 127397 + c.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}

interface CountryDetail {
  country_code: string;
  country_name: string;
  article_count: number;
  avg_credibility: number;
  climate_risk_score: number;
  category_breakdown: Record<string, number>;
  weather?: {
    temperature_c?: number;
    precipitation_mm?: number;
    wind_speed_kmh?: number;
    weather_code?: number;
  };
  temperature_anomaly?: {
    deviation_c: number;
    is_anomalous: boolean;
    description: string;
  };
  source_coverage: {
    source_name: string;
    article_count: number;
    avg_credibility: number;
    // Polish wave 3 (2026-05-27, End2End audit §7.4): 3-axis source scores
    // joined from source_credibility_tiers so the per-source breakdown can
    // render editorial/factcheck/transparency instead of one rolled number.
    tier?: string | null;
    editorial_score?: number | null;
    factcheck_score?: number | null;
    transparency_score?: number | null;
  }[];
}

interface CountryArticle {
  article_id: string;
  title: string;
  source_name: string;
  published_date?: string;
  overall_credibility: string;
  enriched_excerpt?: string;
  excerpt?: string;
}

type TabId = "overview" | "articles" | "sources" | "compare";

interface MapCountryPanelProps {
  countryCode: string;
  onClose: () => void;
  onCompare?: (countryCode: string) => void;
}

export default function MapCountryPanel({
  countryCode,
  onClose,
  onCompare,
}: MapCountryPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [detail, setDetail] = useState<CountryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [articles, setArticles] = useState<CountryArticle[]>([]);
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [articlesPage, setArticlesPage] = useState(0);
  const [hasMoreArticles, setHasMoreArticles] = useState(true);
  const [compareCountry, setCompareCountry] = useState("");
  const [compareData, setCompareData] = useState<any>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const fetchDetail = useCallback(async () => {
    setDetailLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/map/country/${countryCode}/detail`
      );
      if (res.ok) {
        const data = await res.json();
        // Normalize potentially null fields to prevent Object.keys crashes
        if (data) {
          data.category_breakdown = data.category_breakdown || {};
          data.source_coverage = data.source_coverage || [];
          data.article_count = data.article_count ?? 0;
          data.avg_credibility = data.avg_credibility ?? 0;
          data.climate_risk_score = data.climate_risk_score ?? 0;
        }
        setDetail(data);
      }
    } catch (err) {
      console.error("Failed to fetch country detail:", err);
    } finally {
      setDetailLoading(false);
    }
  }, [countryCode]);

  const fetchArticles = useCallback(
    async (page: number) => {
      setArticlesLoading(true);
      try {
        const limit = 10;
        const res = await fetch(
          `${API_BASE}/api/articles?country=${countryCode}&limit=${limit}&offset=${page * limit}`
        );
        if (res.ok) {
          const data = await res.json();
          if (page === 0) {
            setArticles(data);
          } else {
            setArticles((prev) => [...prev, ...data]);
          }
          setHasMoreArticles(data.length === limit);
        }
      } catch (err) {
        console.error("Failed to fetch articles:", err);
      } finally {
        setArticlesLoading(false);
      }
    },
    [countryCode]
  );

  useEffect(() => {
    fetchDetail();
    setArticles([]);
    setArticlesPage(0);
    setHasMoreArticles(true);
    setActiveTab("overview");
    setCompareCountry("");
    setCompareData(null);
  }, [countryCode, fetchDetail]);

  useEffect(() => {
    if (activeTab === "articles" && articles.length === 0) {
      fetchArticles(0);
    }
  }, [activeTab, articles.length, fetchArticles]);

  function loadMoreArticles() {
    const nextPage = articlesPage + 1;
    setArticlesPage(nextPage);
    fetchArticles(nextPage);
  }

  async function fetchComparison() {
    if (!compareCountry) return;
    setCompareLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/map/compare?countries=${countryCode},${compareCountry}`
      );
      if (res.ok) {
        setCompareData(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch comparison:", err);
    } finally {
      setCompareLoading(false);
    }
  }

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "Overview", icon: <BarChart3 className="h-3.5 w-3.5" /> },
    { id: "articles", label: "Articles", icon: <Newspaper className="h-3.5 w-3.5" /> },
    { id: "sources", label: "Sources", icon: <Globe className="h-3.5 w-3.5" /> },
    { id: "compare", label: "Compare", icon: <GitCompare className="h-3.5 w-3.5" /> },
  ];

  function credibilityColor(level: string): string {
    switch (level) {
      case "HIGH":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "MEDIUM":
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      case "LOW":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      default:
        return "bg-slate-600/20 text-slate-400 border-slate-500/30";
    }
  }

  // Safely access nested detail properties with null guards
  const categoryBreakdown = detail?.category_breakdown || {};
  const avgCredibility = detail?.avg_credibility ?? 0;
  const articleCount = detail?.article_count ?? 0;
  const climateRiskScore = detail?.climate_risk_score ?? 0;
  const sources = detail?.source_coverage || [];
  const weather = detail?.weather;
  const tempAnomaly = detail?.temperature_anomaly;

  return (
    <div className="absolute top-0 right-0 z-[1000] w-96 h-full">
      <div className="h-full bg-slate-800/95 backdrop-blur-sm border-l border-slate-700 shadow-2xl flex flex-col animate-slide-in-right">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 flex-shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-2xl flex-shrink-0">
              {getFlagEmoji(countryCode)}
            </span>
            <div className="min-w-0">
              <h2 className="text-base font-bold text-slate-100 truncate">
                {detail?.country_name || countryCode}
              </h2>
              <p className="text-xs text-slate-400">{countryCode}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Phase 2B (2026-05-23) — link from the map sidebar into the
                full Country Climate Passport. The sidebar shows a quick
                snapshot; the passport opens the modular tabbed deep view. */}
            <Link
              href={`/country/${countryCode}`}
              className="text-[11px] text-teal-400 hover:text-teal-300 px-2 py-1 rounded-md hover:bg-teal-900/30 transition-colors whitespace-nowrap"
              data-testid="open-country-passport"
            >
              Open passport →
            </Link>
            <button
              type="button"
              onClick={onClose}
              className="text-slate-500 hover:text-slate-200 transition-colors p-1 rounded-md hover:bg-slate-700"
              aria-label="Close country panel"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700 flex-shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2.5 text-xs font-medium transition-colors ${
                activeTab === tab.id
                  ? "text-teal-400 border-b-2 border-teal-400 bg-teal-600/5"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-700/30"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {detailLoading && activeTab === "overview" ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Loader2 className="h-6 w-6 animate-spin text-teal-500" />
              <p className="text-xs text-slate-400">Loading country data...</p>
            </div>
          ) : (
            <>
              {/* Overview Tab */}
              {activeTab === "overview" && detail && (
                <div className="p-4 space-y-4">
                  {/* Weather card */}
                  {weather && (
                    <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600">
                      <h4 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                        Current Weather
                      </h4>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="text-center">
                          <Thermometer className="h-4 w-4 text-orange-400 mx-auto mb-1" />
                          <p className="text-lg font-bold text-slate-100">
                            {weather.temperature_c != null
                              ? `${weather.temperature_c}\u00B0C`
                              : "--"}
                          </p>
                          <span className="text-[10px] text-slate-400">
                            {weather.weather_code != null
                              ? WEATHER_CODES[weather.weather_code] || "Unknown"
                              : "Temperature"}
                          </span>
                        </div>
                        <div className="text-center">
                          <Droplets className="h-4 w-4 text-blue-400 mx-auto mb-1" />
                          <p className="text-lg font-bold text-slate-100">
                            {weather.precipitation_mm != null
                              ? `${weather.precipitation_mm}mm`
                              : "--"}
                          </p>
                          <span className="text-[10px] text-slate-400">Precipitation</span>
                        </div>
                        <div className="text-center">
                          <Wind className="h-4 w-4 text-slate-400 mx-auto mb-1" />
                          <p className="text-lg font-bold text-slate-100">
                            {weather.wind_speed_kmh != null
                              ? `${weather.wind_speed_kmh}km/h`
                              : "--"}
                          </p>
                          <span className="text-[10px] text-slate-400">Wind</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Temperature anomaly */}
                  {tempAnomaly && (
                    <div
                      className={`rounded-lg px-3 py-2 border text-sm ${
                        tempAnomaly.is_anomalous
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                          : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        {tempAnomaly.is_anomalous && (
                          <AlertTriangle className="h-4 w-4" />
                        )}
                        <span className="font-medium text-sm">
                          {(tempAnomaly.deviation_c ?? 0) > 0 ? "+" : ""}
                          {tempAnomaly.deviation_c ?? 0}{"\u00B0C"} vs historical
                        </span>
                      </div>
                      <p className="text-xs mt-0.5 opacity-80">
                        {tempAnomaly.description ?? ""}
                      </p>
                    </div>
                  )}

                  {/* Article stats */}
                  <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600">
                    <h4 className="text-xs font-semibold text-slate-300 mb-3">
                      Article Intelligence
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-2xl font-bold text-slate-100">
                          {articleCount}
                        </p>
                        <p className="text-[10px] text-slate-400">Total articles</p>
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <p className="text-2xl font-bold text-slate-100">
                            {avgCredibility.toFixed(0)}
                          </p>
                          <span className="text-xs text-slate-400">/100</span>
                        </div>
                        <p className="text-[10px] text-slate-400">Avg credibility</p>
                      </div>
                    </div>

                    {/* Credibility gauge */}
                    <div className="mt-3">
                      <div className="w-full h-2 bg-slate-600 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            avgCredibility >= 75
                              ? "bg-emerald-500"
                              : avgCredibility >= 50
                              ? "bg-amber-500"
                              : "bg-red-500"
                          }`}
                          style={{ width: `${avgCredibility}%` }}
                        />
                      </div>
                    </div>

                    {/* Category breakdown */}
                    {Object.keys(categoryBreakdown).length > 0 && (
                      <div className="mt-3 space-y-1.5">
                        <p className="text-[10px] text-slate-400 uppercase tracking-wider">
                          Category breakdown
                        </p>
                        {Object.entries(categoryBreakdown)
                          .sort(([, a], [, b]) => b - a)
                          .map(([cat, count]) => (
                            <div key={cat} className="flex items-center gap-2">
                              <span className="text-xs text-slate-300 truncate flex-1">
                                {cat.replace(/_/g, " ")}
                              </span>
                              <div className="w-20 h-1.5 bg-slate-600 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-teal-500 rounded-full"
                                  style={{
                                    width: `${articleCount > 0 ? (count / articleCount) * 100 : 0}%`,
                                  }}
                                />
                              </div>
                              <span className="text-[10px] text-slate-500 w-6 text-right">
                                {count}
                              </span>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>

                  {/* Climate risk score */}
                  {climateRiskScore > 0 && (
                    <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600">
                      <h4 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                        <Shield className="h-3.5 w-3.5" />
                        Climate Risk Score
                      </h4>
                      <div className="flex items-center gap-3">
                        <p className="text-3xl font-bold text-slate-100">
                          {climateRiskScore}
                        </p>
                        <div className="flex-1">
                          <div className="w-full h-3 bg-slate-600 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                climateRiskScore > 75
                                  ? "bg-red-500"
                                  : climateRiskScore > 50
                                  ? "bg-orange-500"
                                  : climateRiskScore > 25
                                  ? "bg-yellow-500"
                                  : "bg-emerald-500"
                              }`}
                              style={{ width: `${climateRiskScore}%` }}
                            />
                          </div>
                          <p className="text-[10px] text-slate-500 mt-0.5">
                            {climateRiskScore > 75
                              ? "Very High"
                              : climateRiskScore > 50
                              ? "High"
                              : climateRiskScore > 25
                              ? "Moderate"
                              : "Low"}{" "}
                            risk
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Overview fallback when no detail but not loading */}
              {activeTab === "overview" && !detail && !detailLoading && (
                <div className="p-4 text-center">
                  <p className="text-sm text-slate-400">
                    No detailed data available for this country.
                  </p>
                </div>
              )}

              {/* Articles Tab */}
              {activeTab === "articles" && (
                <div className="p-4">
                  {articlesLoading && articles.length === 0 ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="h-5 w-5 animate-spin text-teal-500" />
                    </div>
                  ) : articles.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-8">
                      No articles found for this country.
                    </p>
                  ) : (
                    <div className="space-y-2.5">
                      {articles.map((a) => (
                        <Link
                          key={a.article_id}
                          href={`/articles/${a.article_id}`}
                          className="block p-3 bg-slate-700/50 rounded-lg border border-slate-600 hover:border-slate-500 hover:bg-slate-700 transition-colors group"
                        >
                          <p className="text-sm font-medium text-slate-200 line-clamp-2 group-hover:text-teal-300 transition-colors">
                            {a.title}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="text-[10px] text-slate-400">
                              {a.source_name}
                            </span>
                            {a.published_date && (
                              <>
                                <span className="text-slate-600">|</span>
                                <span className="text-[10px] text-slate-500">
                                  {new Date(a.published_date).toLocaleDateString()}
                                </span>
                              </>
                            )}
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded border ${credibilityColor(
                                a.overall_credibility
                              )}`}
                            >
                              {a.overall_credibility}
                            </span>
                          </div>
                          {(a.enriched_excerpt || a.excerpt) && (
                            <p className="text-xs text-slate-400 mt-1.5 line-clamp-2">
                              {(a.enriched_excerpt || a.excerpt || "").slice(0, 200)}
                            </p>
                          )}
                        </Link>
                      ))}

                      {hasMoreArticles && (
                        <button
                          type="button"
                          onClick={loadMoreArticles}
                          disabled={articlesLoading}
                          className="w-full py-2 text-xs text-teal-400 hover:text-teal-300 font-medium flex items-center justify-center gap-1 transition-colors"
                        >
                          {articlesLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                          Load more
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Sources Tab */}
              {activeTab === "sources" && (
                <div className="p-4">
                  {sources.length > 0 ? (
                    <div className="space-y-2">
                      {sources.map((source) => {
                        const hasAxes =
                          typeof source.editorial_score === "number" ||
                          typeof source.factcheck_score === "number" ||
                          typeof source.transparency_score === "number";
                        return (
                          <div
                            key={source.source_name}
                            className="p-3 bg-slate-700/50 rounded-lg border border-slate-600"
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-sm font-medium text-slate-200 flex items-center gap-2">
                                {source.source_name}
                                {source.tier && (
                                  <span
                                    className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-600 text-slate-200 border border-slate-500"
                                    title={`Source tier ${source.tier}`}
                                  >
                                    {source.tier}
                                  </span>
                                )}
                              </span>
                              <span className="text-xs text-slate-400">
                                {source.article_count} articles
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-slate-600 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  source.avg_credibility >= 75
                                    ? "bg-emerald-500"
                                    : source.avg_credibility >= 50
                                    ? "bg-amber-500"
                                    : "bg-red-500"
                                }`}
                                style={{ width: `${source.avg_credibility}%` }}
                              />
                            </div>
                            <p className="text-[10px] text-slate-500 mt-1">
                              Credibility: {source.avg_credibility.toFixed(0)}/100
                            </p>
                            {hasAxes && (
                              <div className="mt-2 flex gap-1 text-[9px] font-mono">
                                {typeof source.editorial_score === "number" && (
                                  <span
                                    className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-600"
                                    title="Editorial standards (0-100)"
                                  >
                                    ED {source.editorial_score}
                                  </span>
                                )}
                                {typeof source.factcheck_score === "number" && (
                                  <span
                                    className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-600"
                                    title="Fact-check record (0-100)"
                                  >
                                    FC {source.factcheck_score}
                                  </span>
                                )}
                                {typeof source.transparency_score === "number" && (
                                  <span
                                    className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-600"
                                    title="Transparency (0-100)"
                                  >
                                    TR {source.transparency_score}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400 text-center py-8">
                      No source data available.
                    </p>
                  )}
                </div>
              )}

              {/* Compare Tab */}
              {activeTab === "compare" && (
                <div className="p-4 space-y-4">
                  <div>
                    <label className="text-xs font-medium text-slate-400 mb-1.5 block">
                      Compare with country
                    </label>
                    <div className="flex gap-2 items-end">
                      <div className="flex-1">
                        <CountrySelector
                          value={compareCountry || null}
                          onChange={(v) => setCompareCountry(v || "")}
                          label=""
                          allOptionLabel="Select country"
                          showAllOption={false}
                          searchable={true}
                          showSelectedChip={false}
                          theme="dark"
                          className="[&>label]:hidden"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={fetchComparison}
                        disabled={
                          !compareCountry ||
                          compareCountry.length !== 2 ||
                          compareLoading
                        }
                        className="px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {compareLoading ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          "Compare"
                        )}
                      </button>
                    </div>
                  </div>

                  {compareData && (
                    <div className="space-y-3">
                      {/* Side-by-side metrics */}
                      <div className="grid grid-cols-2 gap-3">
                        {/* Country A */}
                        <div className="bg-slate-700/50 rounded-lg p-3 border border-teal-500/30">
                          <p className="text-sm font-bold text-teal-300 mb-2 flex items-center gap-1.5">
                            {getFlagEmoji(countryCode)} {countryCode}
                          </p>
                          <div className="space-y-1.5 text-xs text-slate-300">
                            <p>Articles: {compareData.country_a?.article_count ?? "-"}</p>
                            <p>Sources: {compareData.country_a?.source_count ?? "-"}</p>
                            <p>Credibility: {compareData.country_a?.avg_credibility?.toFixed(0) ?? "-"}</p>
                            <p>Risk: {compareData.country_a?.climate_risk_score?.toFixed(1) ?? "-"}/10</p>
                          </div>
                        </div>

                        {/* Country B */}
                        <div className="bg-slate-700/50 rounded-lg p-3 border border-violet-500/30">
                          <p className="text-sm font-bold text-violet-300 mb-2 flex items-center gap-1.5">
                            {getFlagEmoji(compareCountry)} {compareCountry}
                          </p>
                          <div className="space-y-1.5 text-xs text-slate-300">
                            <p>Articles: {compareData.country_b?.article_count ?? "-"}</p>
                            <p>Sources: {compareData.country_b?.source_count ?? "-"}</p>
                            <p>Credibility: {compareData.country_b?.avg_credibility?.toFixed(0) ?? "-"}</p>
                            <p>Risk: {compareData.country_b?.climate_risk_score?.toFixed(1) ?? "-"}/10</p>
                          </div>
                        </div>
                      </div>

                      {/* Green Transition Scorecard */}
                      {compareData.country_a && compareData.country_b && (
                        <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600">
                          <h4 className="text-xs font-semibold text-slate-300 mb-2.5">
                            Green Transition Dimensions
                          </h4>
                          <div className="space-y-2">
                            {[
                              { label: "Green Transition", ka: "green_transition_score" },
                              { label: "Renewable Energy", ka: "renewable_energy_score" },
                              { label: "Cleantech", ka: "cleantech_score" },
                              { label: "Circular Economy", ka: "circular_economy_score" },
                              { label: "Resource Efficiency", ka: "resource_efficiency_score" },
                              { label: "Regenerative", ka: "regenerative_score" },
                              { label: "Sustainability", ka: "sustainability_score" },
                            ].map(({ label, ka }) => {
                              const a: number = compareData.country_a[ka] ?? 0;
                              const b: number = compareData.country_b[ka] ?? 0;
                              return (
                                <div key={ka}>
                                  <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
                                  <div className="grid grid-cols-2 gap-1.5">
                                    <div className="flex items-center gap-1">
                                      <div className="flex-1 h-1.5 bg-slate-600 rounded-full overflow-hidden">
                                        <div className="h-full bg-teal-500 rounded-full transition-all duration-500" style={{ width: `${a * 10}%` }} />
                                      </div>
                                      <span className="text-[9px] text-teal-400 w-5 text-right">{a.toFixed(1)}</span>
                                    </div>
                                    <div className="flex items-center gap-1">
                                      <div className="flex-1 h-1.5 bg-slate-600 rounded-full overflow-hidden">
                                        <div className="h-full bg-violet-500 rounded-full transition-all duration-500" style={{ width: `${b * 10}%` }} />
                                      </div>
                                      <span className="text-[9px] text-violet-400 w-5 text-right">{b.toFixed(1)}</span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                          <div className="flex justify-between mt-2 pt-2 border-t border-slate-600">
                            <span className="text-[9px] text-teal-400 flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-teal-500 inline-block" /> {countryCode}
                            </span>
                            <span className="text-[9px] text-slate-400">score /10</span>
                            <span className="text-[9px] text-violet-400 flex items-center gap-1">
                              {compareCountry} <span className="w-2 h-2 rounded-full bg-violet-500 inline-block" />
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Radar chart — green-transition expanded axes */}
                      {compareData.country_a && compareData.country_b && (
                        <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600">
                          <h4 className="text-xs font-semibold text-slate-300 mb-2">
                            Comparison Radar
                          </h4>
                          <ResponsiveContainer width="100%" height={230}>
                            <RadarChart
                              data={[
                                {
                                  axis: "Articles",
                                  a: Math.min(100, (compareData.country_a.article_count / Math.max(compareData.country_a.article_count, compareData.country_b.article_count, 1)) * 100),
                                  b: Math.min(100, (compareData.country_b.article_count / Math.max(compareData.country_a.article_count, compareData.country_b.article_count, 1)) * 100),
                                },
                                {
                                  axis: "Credibility",
                                  a: compareData.country_a.avg_credibility ?? 0,
                                  b: compareData.country_b.avg_credibility ?? 0,
                                },
                                {
                                  axis: "Green Trans.",
                                  a: (compareData.country_a.green_transition_score ?? 0) * 10,
                                  b: (compareData.country_b.green_transition_score ?? 0) * 10,
                                },
                                {
                                  axis: "Renewable",
                                  a: (compareData.country_a.renewable_energy_score ?? 0) * 10,
                                  b: (compareData.country_b.renewable_energy_score ?? 0) * 10,
                                },
                                {
                                  axis: "Circular",
                                  a: (compareData.country_a.circular_economy_score ?? 0) * 10,
                                  b: (compareData.country_b.circular_economy_score ?? 0) * 10,
                                },
                                {
                                  axis: "Resource Eff.",
                                  a: (compareData.country_a.resource_efficiency_score ?? 0) * 10,
                                  b: (compareData.country_b.resource_efficiency_score ?? 0) * 10,
                                },
                                {
                                  axis: "Climate Risk",
                                  a: (compareData.country_a.climate_risk_score ?? 0) * 10,
                                  b: (compareData.country_b.climate_risk_score ?? 0) * 10,
                                },
                              ]}
                            >
                              <PolarGrid stroke="#475569" />
                              <PolarAngleAxis
                                dataKey="axis"
                                tick={{ fill: "#94a3b8", fontSize: 9 }}
                              />
                              <PolarRadiusAxis
                                angle={30}
                                domain={[0, 100]}
                                tick={{ fill: "#64748b", fontSize: 7 }}
                              />
                              <Radar
                                name={countryCode}
                                dataKey="a"
                                stroke="#14b8a6"
                                fill="#14b8a6"
                                fillOpacity={0.3}
                              />
                              <Radar
                                name={compareCountry}
                                dataKey="b"
                                stroke="#a78bfa"
                                fill="#a78bfa"
                                fillOpacity={0.3}
                              />
                            </RadarChart>
                          </ResponsiveContainer>
                        </div>
                      )}

                      {/* Comparison summary */}
                      {compareData.comparison_summary && (
                        <p className="text-xs text-slate-400 bg-slate-700/30 rounded-lg p-2.5 border border-slate-600">
                          {compareData.comparison_summary}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slide-in-right {
          from {
            transform: translateX(100%);
          }
          to {
            transform: translateX(0);
          }
        }
        .animate-slide-in-right {
          animation: slide-in-right 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
