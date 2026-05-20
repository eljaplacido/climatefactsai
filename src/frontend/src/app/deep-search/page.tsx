"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import CountrySelector from "@/components/CountrySelector";
import type { DeepSearchResult, CompareResult } from "@/types";
import {
  Search,
  GitCompareArrows,
  Loader2,
  ExternalLink,
  BookOpen,
  Cloud,
  CheckCircle,
  MessageCircle,
  TrendingUp,
  BarChart3,
  AlertTriangle,
  Activity,
  HelpCircle,
  Microscope,
  Database,
} from "lucide-react";
import TranslatableText from "@/components/TranslatableText";
import MethodologyDrawer from "@/components/MethodologyDrawer";
import CompareCharts from "@/components/CompareCharts";
import ClarificationChips from "@/components/ClarificationChips";
import { useViewContext } from "@/lib/view-context";

type Mode = "search" | "compare";

const SEARCH_STEPS = [
  { label: "Searching internal article corpus", duration: 3 },
  { label: "Querying external research sources", duration: 8 },
  { label: "Fetching weather & climate data", duration: 4 },
  { label: "Synthesizing answer with AI", duration: 12 },
];

const COMPARE_STEPS = [
  { label: "Researching Topic A", duration: 8 },
  { label: "Researching Topic B", duration: 8 },
  { label: "Generating comparative analysis", duration: 10 },
];

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
  const [activeStep, setActiveStep] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const openAssistant = (prompt?: string) => {
    if (typeof window !== "undefined" && prompt) {
      window.dispatchEvent(
        new CustomEvent("climatenews:assistant-prefill", {
          detail: { prompt },
        })
      );
    }
    const assistant = document.querySelector<HTMLElement>("[data-chat-toggle]");
    assistant?.click();
  };

  // Publish active deep-search context so the global chat can reference it.
  const { setView, clearKey } = useViewContext();
  useEffect(() => {
    if (mode === "search" && searchResult && query) {
      setView({
        deepSearchQuery: query,
        countryCode: country || undefined,
        label: `Deep-search: "${query}"`,
      });
    } else if (mode === "compare" && compareResult && queryA && queryB) {
      setView({
        deepSearchCompare: { query_a: queryA, query_b: queryB },
        countryCode: country || undefined,
        label: `Deep-search compare: "${queryA}" vs "${queryB}"`,
      });
    } else {
      clearKey("deepSearchQuery");
      clearKey("deepSearchCompare");
      clearKey("label");
    }
  }, [mode, searchResult, compareResult, query, queryA, queryB, country, setView, clearKey]);

  // Progress timer
  useEffect(() => {
    if (loading) {
      setActiveStep(0);
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((s) => s + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [loading]);

  // Advance progress steps based on elapsed time
  useEffect(() => {
    if (!loading) return;
    const steps = mode === "compare" ? COMPARE_STEPS : SEARCH_STEPS;
    let cumulative = 0;
    for (let i = 0; i < steps.length; i++) {
      cumulative += steps[i].duration;
      if (elapsedSeconds < cumulative) {
        setActiveStep(i);
        return;
      }
    }
    setActiveStep(steps.length - 1);
  }, [elapsedSeconds, loading, mode]);

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
            <button onClick={() => setMode("search")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${mode === "search" ? "bg-clilens-teal-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
              <Search className="h-4 w-4" /> Research
            </button>
            <button onClick={() => setMode("compare")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${mode === "compare" ? "bg-clilens-teal-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
              <GitCompareArrows className="h-4 w-4" /> Compare
            </button>
          </div>

          {/* Suggested comparison topics */}
          {mode === "compare" && !queryA && !queryB && (
            <div className="mb-4">
              <p className="text-xs text-gray-500 mb-2 flex items-center gap-1"><TrendingUp className="w-3 h-3"/> Suggested comparisons</p>
              <div className="flex flex-wrap gap-2">
                {[ {a:"Drought in Southern Europe 2025",b:"Southern Europe drought 2018-2023"},
                   {a:"Germany renewable energy targets",b:"France nuclear energy strategy"},
                   {a:"India extreme heat 2025 trends",b:"India heatwaves 2015-2020"},
                   {a:"Arctic ice melt acceleration",b:"Antarctic ice shelf loss comparison"},
                   {a:"EU carbon emissions 2024",b:"China emissions growth trajectory"} ].map((s,i) => (
                  <button key={i} onClick={() => { setQueryA(s.a); setQueryB(s.b); }}
                    className="text-xs px-3 py-1.5 bg-gray-50 hover:bg-teal-50 border border-gray-200 hover:border-teal-200 rounded-full text-gray-600 hover:text-teal-700 transition-colors">
                    {s.a} vs {s.b}
                  </button>
                ))}
              </div>
            </div>
          )}

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
                <div className="w-64">
                  <CountrySelector
                    value={country}
                    onChange={setCountry}
                    searchable={true}
                  />
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
                <div className="w-64">
                  <CountrySelector
                    value={country}
                    onChange={setCountry}
                    searchable={true}
                  />
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

      {/* Loading with progress steps */}
      {loading && (() => {
        const steps = mode === "compare" ? COMPARE_STEPS : SEARCH_STEPS;
        const totalEstimate = steps.reduce((s, st) => s + st.duration, 0);
        const progressPct = Math.min(95, Math.round((elapsedSeconds / totalEstimate) * 100));
        return (
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Loader2 className="h-5 w-5 animate-spin text-clilens-teal-600" />
                  <h3 className="text-base font-semibold text-gray-900">
                    {mode === "compare" ? "Comparing topics..." : "Analyzing your query..."}
                  </h3>
                </div>
                <span className="text-sm text-gray-500">
                  ~{Math.max(0, totalEstimate - elapsedSeconds)}s remaining
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-gray-100 rounded-full h-2 mb-5 overflow-hidden">
                <div
                  className="h-2 rounded-full bg-gradient-to-r from-clilens-teal-400 to-clilens-teal-600 transition-all duration-1000"
                  style={{ width: `${progressPct}%` }}
                />
              </div>

              {/* Steps */}
              <div className="space-y-2.5">
                {steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-3">
                    {i < activeStep ? (
                      <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                    ) : i === activeStep ? (
                      <Loader2 className="h-4 w-4 animate-spin text-clilens-teal-600 flex-shrink-0" />
                    ) : (
                      <div className="h-4 w-4 rounded-full border-2 border-gray-300 flex-shrink-0" />
                    )}
                    <span className={`text-sm ${
                      i < activeStep ? "text-emerald-700 font-medium" :
                      i === activeStep ? "text-gray-900 font-medium" :
                      "text-gray-400"
                    }`}>
                      {step.label}
                    </span>
                  </div>
                ))}
              </div>

              <p className="text-xs text-gray-400 mt-4">
                You can navigate to other pages &mdash; results will appear when you return.
              </p>
            </div>
          </div>
        );
      })()}

      {/* Search Results */}
      {searchResult && !loading && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
          {/* Synthesized Answer */}
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Research Summary</h2>
            <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
              <TranslatableText text={searchResult.answer} as="div" maxLength={5000} />
            </div>
            {/* Ask in Chat button */}
            <div className="mt-4 pt-3 border-t border-gray-100">
                <button
                  onClick={() => {
                    openAssistant(`Help me interpret this deep-search result for \"${searchResult.query}\" and suggest a more scientifically robust follow-up query.`);
                  }}
                  className="text-xs text-teal-700 hover:text-teal-900 flex items-center gap-1.5"
                >
                  <MessageCircle className="w-3.5 h-3.5" />
                  Ask about this result in chat
              </button>
            </div>
          </div>

          {/* Insights dashboard */}
          {(() => {
            const citations = searchResult.citations || [];
            const credCounts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
            let internalWithLowRel = 0;
            let avgReliability = 0;
            let relSamples = 0;
            citations.forEach(c => {
              if (c.credibility === "HIGH") credCounts.HIGH++;
              else if (c.credibility === "MEDIUM") credCounts.MEDIUM++;
              else credCounts.LOW++;
              if (c.type === "internal_article" && (c.reliability_score ?? 0) < 40) {
                internalWithLowRel += 1;
              }
              if (c.reliability_score != null) {
                avgReliability += c.reliability_score;
                relSamples += 1;
              }
            });
            const total = citations.length || 1;
            const totalReal = citations.length;
            const halInfo = searchResult.methodology?.hallucination_check;
            const grounded = halInfo?.is_grounded;
            const avgRel = relSamples > 0 ? Math.round(avgReliability / relSamples) : null;
            const retrieval = searchResult.methodology?.queries_run || [];
            const internalHits = retrieval.find((q: any) => q.layer === "internal_corpus")?.hits ?? searchResult.internal_articles_count;
            const externalHits = retrieval.find((q: any) => q.layer === "perplexity_external")?.hits ?? searchResult.external_sources_count;
            const guidance = (searchResult.methodology as any)?.guidance;
            const lowCoverage = totalReal <= 3;
            const likelyWeakEvidence = lowCoverage || (externalHits === 0 && internalHits < 5) || internalWithLowRel >= 3;
            return (
              <div className="bg-white rounded-lg border p-4">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <BarChart3 className="w-3.5 h-3.5" /> Analysis Insights
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-center">
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-lg font-bold text-gray-900">{searchResult.internal_articles_count}</div>
                    <div className="text-[10px] text-gray-500">Internal articles</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-lg font-bold text-gray-900">{searchResult.external_sources_count}</div>
                    <div className="text-[10px] text-gray-500">External sources</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="flex gap-1 justify-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-500" title={`${credCounts.HIGH} HIGH`}/>
                      <span className="w-2.5 h-2.5 rounded-full bg-yellow-500" title={`${credCounts.MEDIUM} MEDIUM`}/>
                      <span className="w-2.5 h-2.5 rounded-full bg-red-500" title={`${credCounts.LOW} LOW`}/>
                    </div>
                    <div className="text-[10px] text-gray-500 mt-1">Credibility spread</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className={`text-lg font-bold ${grounded ? 'text-green-600' : grounded === false ? 'text-red-600' : 'text-gray-400'}`}>
                      {grounded ? 'Grounded' : grounded === false ? 'Weak' : '—'}
                    </div>
                    <div className="text-[10px] text-gray-500">Hallucination check</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-lg font-bold text-gray-900">
                      {halInfo?.hallucination_risk != null ? `${Math.round((1 - halInfo.hallucination_risk) * 100)}%` : '—'}
                    </div>
                    <div className="text-[10px] text-gray-500">Scientific confidence</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className={`text-lg font-bold ${avgRel != null ? avgRel > 70 ? "text-green-600" : avgRel > 40 ? "text-yellow-600" : "text-red-600" : "text-gray-400"}`}>
                      {avgRel != null ? `${avgRel}%` : "—"}
                    </div>
                    <div className="text-[10px] text-gray-500">Avg reliability</div>
                  </div>
                </div>
                {searchResult.citations.length > 0 && (
                  <div className="mt-3 flex gap-1 h-1.5 rounded-full overflow-hidden bg-gray-100">
                    {credCounts.HIGH > 0 && <div className="bg-green-500" style={{width:`${(credCounts.HIGH/total)*100}%`}} title={`${credCounts.HIGH} HIGH`}/>}
                    {credCounts.MEDIUM > 0 && <div className="bg-yellow-500" style={{width:`${(credCounts.MEDIUM/total)*100}%`}} title={`${credCounts.MEDIUM} MEDIUM`}/>}
                    {credCounts.LOW > 0 && <div className="bg-red-500" style={{width:`${(credCounts.LOW/total)*100}%`}} title={`${credCounts.LOW} LOW`}/>}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                  <div className="rounded border border-slate-200 bg-slate-50 px-2.5 py-2 text-slate-600 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-slate-500" />
                    Retrieval: {internalHits} internal / {externalHits} external
                  </div>
                  <div className="rounded border border-slate-200 bg-slate-50 px-2.5 py-2 text-slate-600 flex items-center gap-1.5">
                    <Microscope className="w-3.5 h-3.5 text-slate-500" />
                    Evidence quality: {likelyWeakEvidence ? "Potentially weak" : "Acceptable"}
                  </div>
                  <button
                    type="button"
                    onClick={() => openAssistant(`Help me improve this deep-search query for stronger scientific evidence: \"${searchResult.query}\"`)}
                    className="rounded border border-teal-200 bg-teal-50 px-2.5 py-2 text-teal-700 hover:bg-teal-100 transition-colors flex items-center gap-1.5 justify-center"
                  >
                    <HelpCircle className="w-3.5 h-3.5" /> Improve query with chat
                  </button>
                </div>
                {(guidance || likelyWeakEvidence) && (
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
                    <p className="text-xs font-medium text-amber-800 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Guidance
                    </p>
                    <p className="text-xs text-amber-700 mt-1">
                      {guidance?.message || "This result may have weak or narrow evidence coverage. Consider refining scope before relying on conclusions."}
                    </p>
                    {Array.isArray(guidance?.suggested_actions) && guidance.suggested_actions.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {guidance.suggested_actions.slice(0, 3).map((act: string) => (
                          <span key={act} className="px-2 py-1 rounded-full text-[10px] bg-amber-100 text-amber-800 border border-amber-200">
                            {act}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })()}

          {searchResult.citations.length === 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-amber-900 flex items-center gap-2 mb-2">
                <Activity className="h-4 w-4" /> Limited evidence found
              </h3>
              <p className="text-sm text-amber-800 mb-3">
                The system found little or no relevant evidence for this query. Use one of these options to get a more robust answer.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => openAssistant(`Help me reformulate this deep-search query with scientific rigor: \"${searchResult.query}\"`)}
                  className="px-3 py-1.5 text-xs rounded-full bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 transition-colors"
                >
                  Get query help in chat
                </button>
                <button
                  type="button"
                  onClick={() => setMode("compare")}
                  className="px-3 py-1.5 text-xs rounded-full bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 transition-colors"
                >
                  Switch to compare mode
                </button>
              </div>
            </div>
          )}

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

          {/* Clarification chips when search returned no results */}
          {searchResult.clarification_needed && searchResult.clarification_needed.length > 0 && (
            <ClarificationChips
              suggestions={searchResult.clarification_needed}
              onPick={(s) => {
                setQuery(s);
                // brief defer so state lands before search fires
                setTimeout(() => handleSearch(), 0);
              }}
            />
          )}

          {/* Methodology drawer — How this was answered */}
          <MethodologyDrawer
            methodology={searchResult.methodology}
            internalCount={searchResult.internal_articles_count}
            externalCount={searchResult.external_sources_count}
            filters={searchResult.filters}
          />

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
                        <span>Relevance: {Math.min(100, Math.round((c.relevance_score ?? 0) * 100))}%</span>
                      )}
                      {c.reliability_score != null && (
                        <span className={c.reliability_score > 70 ? 'text-green-600' : c.reliability_score > 40 ? 'text-yellow-600' : 'text-red-600'}>
                          Reliability: {Math.min(100, c.reliability_score)}%
                        </span>
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
          {/* Visual comparative analysis (preferred when structured data is present) */}
          {compareResult.comparative_analysis_structured ? (
            <div className="bg-white rounded-lg border p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Comparative Analysis</h2>
              <CompareCharts data={compareResult} />
            </div>
          ) : (
            <div className="bg-white rounded-lg border p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Comparative Analysis</h2>
              <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                <TranslatableText text={compareResult.comparative_analysis} as="div" maxLength={5000} />
              </div>
            </div>
          )}

          {/* Methodology drawers — one per side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <MethodologyDrawer
              methodology={compareResult.result_a.methodology}
              internalCount={compareResult.result_a.internal_articles_count}
              externalCount={compareResult.result_a.external_sources_count}
              filters={compareResult.result_a.filters}
            />
            <MethodologyDrawer
              methodology={compareResult.result_b.methodology}
              internalCount={compareResult.result_b.internal_articles_count}
              externalCount={compareResult.result_b.external_sources_count}
              filters={compareResult.result_b.filters}
            />
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
