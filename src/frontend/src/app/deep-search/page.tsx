"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import CountrySelector from "@/components/CountrySelector";
import type { DeepSearchResult, CompareResult } from "@/types";
import { Search, GitCompareArrows, Loader2, ExternalLink, BookOpen, Cloud } from "lucide-react";

type Mode = "search" | "compare";

export default function DeepSearchPage() {
  const [mode, setMode] = useState<Mode>("search");
  const [query, setQuery] = useState("");
  const [queryA, setQueryA] = useState("");
  const [queryB, setQueryB] = useState("");
  const [country, setCountry] = useState<string | null>(null);
  const [includeWeather, setIncludeWeather] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<DeepSearchResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSearchResult(null);
    try {
      const result = await api.deepSearch({
        query: query.trim(),
        country: country ?? undefined,
        include_weather: includeWeather,
      });
      setSearchResult(result);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(detail || "Deep search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!queryA.trim() || !queryB.trim()) return;
    setLoading(true);
    setError(null);
    setCompareResult(null);
    try {
      const result = await api.compareTopics({
        query_a: queryA.trim(),
        query_b: queryB.trim(),
        country: country ?? undefined,
      });
      setCompareResult(result);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(detail || "Comparison failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <section className="border-b bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Deep Search</h1>
          <p className="text-gray-600 text-sm mb-6">
            Research climate topics across our verified corpus and external sources.
            <span className="ml-1 text-xs text-clilens-teal-700 bg-clilens-teal-50 px-2 py-0.5 rounded">
              Professional
            </span>
          </p>

          {/* Mode toggle */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setMode("search")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                mode === "search"
                  ? "bg-clilens-teal-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              <Search className="h-4 w-4" /> Research
            </button>
            <button
              onClick={() => setMode("compare")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                mode === "compare"
                  ? "bg-clilens-teal-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              <GitCompareArrows className="h-4 w-4" /> Compare
            </button>
          </div>

          {/* Search input */}
          {mode === "search" ? (
            <div className="space-y-4">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a climate research question... e.g. 'How does drought in Southern Europe in 2025 compare to historical patterns?'"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary resize-none"
                rows={3}
              />
              <div className="flex items-center gap-4">
                <div className="w-48">
                  <CountrySelector value={country} onChange={setCountry} />
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={includeWeather}
                    onChange={(e) => setIncludeWeather(e.target.checked)}
                    className="rounded border-gray-300 text-clilens-teal-600"
                  />
                  <Cloud className="h-4 w-4" />
                  Include weather data
                </label>
                <button
                  onClick={handleSearch}
                  disabled={loading || !query.trim()}
                  className="ml-auto px-6 py-2 bg-clilens-teal-600 text-white rounded-lg hover:bg-clilens-teal-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Search
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Topic A</label>
                  <input
                    value={queryA}
                    onChange={(e) => setQueryA(e.target.value)}
                    placeholder="e.g. Wind energy in Northern Europe"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Topic B</label>
                  <input
                    value={queryB}
                    onChange={(e) => setQueryB(e.target.value)}
                    placeholder="e.g. Solar energy in Southern Europe"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary"
                  />
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-48">
                  <CountrySelector value={country} onChange={setCountry} />
                </div>
                <button
                  onClick={handleCompare}
                  disabled={loading || !queryA.trim() || !queryB.trim()}
                  className="ml-auto px-6 py-2 bg-clilens-teal-600 text-white rounded-lg hover:bg-clilens-teal-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompareArrows className="h-4 w-4" />}
                  Compare
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Error */}
      {error && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-clilens-teal-600 mx-auto mb-3" />
          <p className="text-gray-600">Searching across internal corpus and external sources...</p>
        </div>
      )}

      {/* Search Results */}
      {searchResult && !loading && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
          {/* Synthesized Answer */}
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Research Summary</h2>
            <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
              {searchResult.answer}
            </div>
          </div>

          {/* Weather Context */}
          {searchResult.weather_context && (
            <div className="bg-blue-50 rounded-lg border border-blue-200 p-4">
              <h3 className="text-sm font-semibold text-blue-900 flex items-center gap-2 mb-2">
                <Cloud className="h-4 w-4" /> Weather Data ({searchResult.weather_context.country_code})
              </h3>
              <div className="space-y-1">
                {searchResult.weather_context.data_points.map((dp, i) => (
                  <p key={i} className="text-sm text-blue-800">
                    <span className="font-medium">{dp.source}:</span> {dp.content}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Citations */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Sources ({searchResult.internal_articles_count} internal, {searchResult.external_sources_count} external)
            </h3>
            <div className="space-y-3">
              {searchResult.citations.map((c, i) => (
                <div key={i} className="flex items-start gap-3 text-sm">
                  {c.type === "internal_article" ? (
                    <BookOpen className="h-4 w-4 text-clilens-teal-600 mt-0.5 flex-shrink-0" />
                  ) : (
                    <ExternalLink className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  )}
                  <div>
                    <p className="text-gray-900 font-medium">
                      {c.title || c.source_name || c.source_url}
                    </p>
                    {c.excerpt && (
                      <p className="text-gray-500 text-xs mt-0.5">{c.excerpt}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                      {c.credibility && (
                        <span className={`px-1.5 py-0.5 rounded ${
                          c.credibility === "HIGH" ? "bg-green-100 text-green-700" :
                          c.credibility === "MEDIUM" ? "bg-yellow-100 text-yellow-700" :
                          "bg-red-100 text-red-700"
                        }`}>
                          {c.credibility}
                        </span>
                      )}
                      {c.source_name && <span>{c.source_name}</span>}
                      {c.published_date && <span>{c.published_date}</span>}
                      {c.relevance_score != null && (
                        <span>Relevance: {(c.relevance_score * 100).toFixed(0)}%</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Compare Results */}
      {compareResult && !loading && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
          {/* Comparative Analysis */}
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Comparative Analysis</h2>
            <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
              {compareResult.comparative_analysis}
            </div>
          </div>

          {/* Side by side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { label: "Topic A", q: compareResult.query_a, r: compareResult.result_a },
              { label: "Topic B", q: compareResult.query_b, r: compareResult.result_b },
            ].map(({ label, q, r }) => (
              <div key={label} className="bg-white rounded-lg border p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-1">{label}: {q}</h3>
                <p className="text-xs text-gray-500 mb-3">
                  {r.internal_articles_count} internal, {r.external_sources_count} external sources
                </p>
                <div className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-[12]">
                  {r.answer}
                </div>
                {r.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <p className="text-xs font-medium text-gray-500 mb-2">Top sources:</p>
                    {r.citations.slice(0, 3).map((c, i) => (
                      <p key={i} className="text-xs text-gray-600 truncate">
                        {c.title || c.source_name || c.source_url}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
