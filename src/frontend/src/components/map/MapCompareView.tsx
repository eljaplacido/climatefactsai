"use client";

import { useState, useEffect } from "react";
import {
  X,
  Loader2,
  GitCompare,
} from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Legend,
} from "recharts";
import Link from "next/link";
import CountrySelector from "@/components/CountrySelector";
import type { ActiveLayer } from "@/components/map/InteractiveClimateMap";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Which metric the side-by-side headline leads with, per active map layer —
// so changing the layer/scope changes what the comparison emphasises (the old
// view always showed the same axes regardless of layer).
const LAYER_METRIC: Record<
  ActiveLayer,
  {
    label: string;
    get?: (c: CompareCountryData) => number;
    unit?: string;
    higherBetter?: boolean;
    note?: string;
  }
> = {
  article_density: { label: "Article coverage", get: (c) => c.article_count, unit: " articles", higherBetter: true },
  source_diversity: { label: "Source diversity", get: (c) => c.source_count, unit: " sources", higherBetter: true },
  climate_risk: { label: "Climate-risk score", get: (c) => c.climate_risk, unit: " / 10", higherBetter: false },
  temperature_anomaly: {
    label: "Temperature anomaly",
    note: "Temperature anomaly is shown on the map layer; a side-by-side temperature compare is coming next.",
  },
  corporate_density: {
    label: "Corporate density",
    note: "Corporate disclosure density is shown on the map layer; side-by-side company density compare is coming next.",
  },
  news_events: {
    label: "News events",
    note: "Recent event intensity and controversy hotspots are shown on the map layer; side-by-side events compare is coming next.",
  },
  ndc_status: {
    label: "NDC targets",
    note: "Country climate pledges and CAT ratings are shown on the map layer; side-by-side policy ambition compare is coming next.",
  },
  biomes: {
    label: "Biomes & climate zones",
    note: "Köppen biome zones are shown on the map layer (they aren't a single comparable number).",
  },
};

function getFlagEmoji(cc: string): string {
  if (!cc || cc.length !== 2) return "";
  const codePoints = cc
    .toUpperCase()
    .split("")
    .map((c) => 127397 + c.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}

interface CompareCountryData {
  country_code: string;
  country_name: string;
  article_count: number;
  source_count: number;
  avg_credibility: number;
  climate_risk: number;
  topic_count: number;
  top_topics: string[];
  recent_articles?: {
    article_id: string;
    title: string;
    source_name: string;
    published_date?: string;
    overall_credibility: string;
  }[];
}

interface CompareResponse {
  country_a: CompareCountryData;
  country_b: CompareCountryData;
}

interface MapCompareViewProps {
  initialCountryA?: string;
  initialCountryB?: string;
  activeLayer?: ActiveLayer;
  onClose: () => void;
}

export default function MapCompareView({
  initialCountryA = "",
  initialCountryB = "",
  activeLayer = "article_density",
  onClose,
}: MapCompareViewProps) {
  const [countryA, setCountryA] = useState(initialCountryA);
  const [countryB, setCountryB] = useState(initialCountryB);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialCountryA && initialCountryB) {
      fetchComparison(initialCountryA, initialCountryB);
    }
  }, [initialCountryA, initialCountryB]);

  async function fetchComparison(cA: string, cB: string) {
    if (!cA || !cB || cA.length !== 2 || cB.length !== 2) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/map/compare?countries=${cA},${cB}`
      );
      if (res.ok) {
        setData(await res.json());
      } else {
        setError("Failed to load comparison data.");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleCompare() {
    fetchComparison(countryA, countryB);
  }

  function credibilityColor(level: string): string {
    switch (level) {
      case "HIGH":
        return "text-emerald-400";
      case "MEDIUM":
        return "text-amber-400";
      case "LOW":
        return "text-red-400";
      default:
        return "text-slate-400";
    }
  }

  const radarData =
    data?.country_a && data?.country_b
      ? [
          {
            axis: "Articles",
            a: Math.min(
              100,
              (data.country_a.article_count /
                Math.max(
                  data.country_a.article_count,
                  data.country_b.article_count,
                  1
                )) *
                100
            ),
            b: Math.min(
              100,
              (data.country_b.article_count /
                Math.max(
                  data.country_a.article_count,
                  data.country_b.article_count,
                  1
                )) *
                100
            ),
          },
          {
            axis: "Sources",
            a: Math.min(
              100,
              (data.country_a.source_count /
                Math.max(
                  data.country_a.source_count,
                  data.country_b.source_count,
                  1
                )) *
                100
            ),
            b: Math.min(
              100,
              (data.country_b.source_count /
                Math.max(
                  data.country_a.source_count,
                  data.country_b.source_count,
                  1
                )) *
                100
            ),
          },
          {
            axis: "Credibility",
            a: data.country_a.avg_credibility,
            b: data.country_b.avg_credibility,
          },
          {
            axis: "Topics",
            a: Math.min(
              100,
              (data.country_a.topic_count /
                Math.max(
                  data.country_a.topic_count,
                  data.country_b.topic_count,
                  1
                )) *
                100
            ),
            b: Math.min(
              100,
              (data.country_b.topic_count /
                Math.max(
                  data.country_a.topic_count,
                  data.country_b.topic_count,
                  1
                )) *
                100
            ),
          },
          {
            axis: "Climate Risk",
            a: data.country_a.climate_risk,
            b: data.country_b.climate_risk,
          },
        ]
      : [];

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-slate-800 rounded-2xl border border-slate-700 shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700 sticky top-0 bg-slate-800 z-10">
          <div className="flex items-center gap-2.5">
            <GitCompare className="h-5 w-5 text-teal-400" />
            <h2 className="text-lg font-bold text-slate-100">
              Country Comparison
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-200 transition-colors p-1 rounded-md hover:bg-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6">
          {/* Country selectors */}
          <div className="flex items-end gap-4 mb-6">
            <div className="flex-1">
              <CountrySelector
                value={countryA || null}
                onChange={(v) => setCountryA(v || "")}
                label="Country A"
                allOptionLabel="Select country"
                showAllOption={false}
                searchable={true}
                showSelectedChip={false}
                theme="dark"
              />
            </div>
            <div className="text-slate-400 mb-2 font-bold text-sm">vs</div>
            <div className="flex-1">
              <CountrySelector
                value={countryB || null}
                onChange={(v) => setCountryB(v || "")}
                label="Country B"
                allOptionLabel="Select country"
                showAllOption={false}
                searchable={true}
                showSelectedChip={false}
                theme="dark"
              />
            </div>
            <button
              type="button"
              onClick={handleCompare}
              disabled={
                loading ||
                countryA.length !== 2 ||
                countryB.length !== 2 ||
                countryA === countryB
              }
              className="mt-5 px-5 py-2 bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Compare"
              )}
            </button>
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2 mb-4">
              {error}
            </div>
          )}

          {data && (
            <div className="space-y-6">
              {/* Layer-aware headline — leads with the metric for the active
                  map layer so the comparison responds to the chosen scope. */}
              {(() => {
                const m = LAYER_METRIC[activeLayer] ?? LAYER_METRIC.article_density;
                if (!m.get) {
                  return (
                    <div className="bg-slate-700/40 rounded-xl p-4 border border-slate-600">
                      <p className="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
                        Active layer · {m.label}
                      </p>
                      <p className="text-xs text-slate-400">{m.note}</p>
                    </div>
                  );
                }
                const va = m.get(data.country_a);
                const vb = m.get(data.country_b);
                const leader =
                  va === vb ? "tie" : (m.higherBetter ? va > vb : va < vb) ? "a" : "b";
                const cell = (val: number, side: "a" | "b", name: string, accent: string) => (
                  <div
                    className={`flex-1 rounded-lg p-3 border ${
                      leader === side ? "border-emerald-500/40 bg-emerald-500/10" : "border-slate-600 bg-slate-700/40"
                    }`}
                  >
                    <p className={`text-xs ${accent}`}>{name}</p>
                    <p className="text-2xl font-bold text-slate-100">
                      {val.toLocaleString()}
                      <span className="text-xs font-normal text-slate-400">{m.unit}</span>
                    </p>
                    {leader === side && (
                      <p className="text-[10px] text-emerald-400 font-medium mt-0.5">
                        {m.higherBetter ? "Higher" : "Lower"} {m.label.toLowerCase()}
                      </p>
                    )}
                  </div>
                );
                return (
                  <div className="bg-slate-700/40 rounded-xl p-4 border border-slate-600">
                    <p className="text-[11px] uppercase tracking-wider text-slate-400 mb-2">
                      Comparing by active layer · {m.label}
                    </p>
                    <div className="flex items-stretch gap-3">
                      {cell(va, "a", data.country_a.country_name, "text-teal-300")}
                      {cell(vb, "b", data.country_b.country_name, "text-violet-300")}
                    </div>
                  </div>
                );
              })()}

              {/* Metrics comparison cards */}
              <div className="grid grid-cols-2 gap-4">
                {/* Country A */}
                <div className="bg-slate-700/50 rounded-xl p-4 border border-teal-500/20">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-2xl">
                      {getFlagEmoji(data.country_a.country_code)}
                    </span>
                    <div>
                      <h3 className="text-base font-bold text-teal-300">
                        {data.country_a.country_name}
                      </h3>
                      <p className="text-xs text-slate-400">
                        {data.country_a.country_code}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_a.article_count}
                      </p>
                      <p className="text-[10px] text-slate-400">Articles</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_a.source_count}
                      </p>
                      <p className="text-[10px] text-slate-400">Sources</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_a.avg_credibility.toFixed(0)}
                      </p>
                      <p className="text-[10px] text-slate-400">Credibility</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_a.climate_risk}
                      </p>
                      <p className="text-[10px] text-slate-400">
                        Climate Risk
                      </p>
                    </div>
                  </div>
                  {data.country_a.top_topics.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {data.country_a.top_topics.slice(0, 5).map((t) => (
                        <span
                          key={t}
                          className="text-[10px] bg-teal-600/20 text-teal-300 px-1.5 py-0.5 rounded"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Country B */}
                <div className="bg-slate-700/50 rounded-xl p-4 border border-violet-500/20">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-2xl">
                      {getFlagEmoji(data.country_b.country_code)}
                    </span>
                    <div>
                      <h3 className="text-base font-bold text-violet-300">
                        {data.country_b.country_name}
                      </h3>
                      <p className="text-xs text-slate-400">
                        {data.country_b.country_code}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_b.article_count}
                      </p>
                      <p className="text-[10px] text-slate-400">Articles</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_b.source_count}
                      </p>
                      <p className="text-[10px] text-slate-400">Sources</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_b.avg_credibility.toFixed(0)}
                      </p>
                      <p className="text-[10px] text-slate-400">Credibility</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-slate-100">
                        {data.country_b.climate_risk}
                      </p>
                      <p className="text-[10px] text-slate-400">
                        Climate Risk
                      </p>
                    </div>
                  </div>
                  {data.country_b.top_topics.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {data.country_b.top_topics.slice(0, 5).map((t) => (
                        <span
                          key={t}
                          className="text-[10px] bg-violet-600/20 text-violet-300 px-1.5 py-0.5 rounded"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Radar chart */}
              {radarData.length > 0 && (
                <div className="bg-slate-700/50 rounded-xl p-4 border border-slate-600">
                  <h3 className="text-sm font-semibold text-slate-300 mb-3">
                    5-Axis Comparison
                  </h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="#475569" />
                      <PolarAngleAxis
                        dataKey="axis"
                        tick={{ fill: "#94a3b8", fontSize: 12 }}
                      />
                      <PolarRadiusAxis
                        angle={30}
                        domain={[0, 100]}
                        tick={{ fill: "#64748b", fontSize: 10 }}
                      />
                      <Radar
                        name={data?.country_a.country_name || countryA}
                        dataKey="a"
                        stroke="#14b8a6"
                        fill="#14b8a6"
                        fillOpacity={0.3}
                      />
                      <Radar
                        name={data?.country_b.country_name || countryB}
                        dataKey="b"
                        stroke="#a78bfa"
                        fill="#a78bfa"
                        fillOpacity={0.3}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: 12, color: "#94a3b8" }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Side-by-side recent articles */}
              <div className="grid grid-cols-2 gap-4">
                {[data.country_a, data.country_b].map((country, idx) => (
                  <div key={country.country_code}>
                    <h4 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                      Recent from {country.country_name}
                    </h4>
                    <div className="space-y-2">
                      {(country.recent_articles || []).slice(0, 5).map((a) => (
                        <Link
                          key={a.article_id}
                          href={`/articles/${a.article_id}`}
                          className="block p-2.5 bg-slate-700/50 rounded-lg border border-slate-600 hover:border-slate-500 transition-colors"
                        >
                          <p className="text-xs font-medium text-slate-200 line-clamp-2">
                            {a.title}
                          </p>
                          <div className="flex items-center gap-1.5 mt-1">
                            <span className="text-[10px] text-slate-400">
                              {a.source_name}
                            </span>
                            <span
                              className={`text-[10px] font-medium ${credibilityColor(
                                a.overall_credibility
                              )}`}
                            >
                              {a.overall_credibility}
                            </span>
                          </div>
                        </Link>
                      ))}
                      {(country.recent_articles || []).length === 0 && (
                        <p className="text-xs text-slate-500 text-center py-4">
                          No recent articles
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!data && !loading && !error && (
            <div className="text-center py-12">
              <GitCompare className="h-10 w-10 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-400">
                Select two countries and click Compare to see a side-by-side
                analysis of their climate news coverage.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
