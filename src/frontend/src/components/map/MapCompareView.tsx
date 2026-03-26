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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

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
  recent_articles: {
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
  onClose: () => void;
}

export default function MapCompareView({
  initialCountryA = "",
  initialCountryB = "",
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
          <div className="flex items-center gap-4 mb-6">
            <div className="flex-1">
              <label className="text-xs text-slate-400 mb-1 block">
                Country A
              </label>
              <div className="flex items-center gap-2">
                <span className="text-xl">
                  {countryA ? getFlagEmoji(countryA) : ""}
                </span>
                <input
                  type="text"
                  value={countryA}
                  onChange={(e) =>
                    setCountryA(e.target.value.toUpperCase().slice(0, 2))
                  }
                  placeholder="e.g. FI"
                  maxLength={2}
                  className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-teal-500 uppercase"
                />
              </div>
            </div>

            <div className="text-slate-500 mt-5 font-bold">vs</div>

            <div className="flex-1">
              <label className="text-xs text-slate-400 mb-1 block">
                Country B
              </label>
              <div className="flex items-center gap-2">
                <span className="text-xl">
                  {countryB ? getFlagEmoji(countryB) : ""}
                </span>
                <input
                  type="text"
                  value={countryB}
                  onChange={(e) =>
                    setCountryB(e.target.value.toUpperCase().slice(0, 2))
                  }
                  placeholder="e.g. SE"
                  maxLength={2}
                  className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-violet-500 uppercase"
                />
              </div>
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
                      {country.recent_articles.slice(0, 5).map((a) => (
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
                      {country.recent_articles.length === 0 && (
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
