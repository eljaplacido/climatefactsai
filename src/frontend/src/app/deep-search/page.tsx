"use client";

// Phase 8 (2026-05-24) — disable static prerender; useSearchParams below
// can't be statically rendered.
export const dynamic = "force-dynamic";

import { Suspense, useState, useEffect, useRef } from "react";
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
import AIProvenanceBadge from "@/components/AIProvenanceBadge";
import SentenceGroundedAnswer from "@/components/SentenceGroundedAnswer";
import DeepSearchFollowupChat from "@/components/DeepSearchFollowupChat";
import QuotaCounter from "@/components/QuotaCounter";
import UpgradeModal, { type UpgradeModalQuotaEnvelope } from "@/components/UpgradeModal";
import MultiViewTabs from "@/components/MultiViewTabs";
import { useQuota } from "@/lib/useQuota";
import { useViewContext } from "@/lib/view-context";
import { useUrlState, URL_STATE_SERIALIZERS } from "@/lib/useUrlState";
import { formatEvidenceStrengthPlain } from "@/lib/plainLanguage";

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

// Phase 1B (2026-05-23) — URL-persistent state per the competitive UX
// audit's MH1 must-have. Every selection (mode, queries, country, weather
// toggle) is encoded into the URL so sharing a link reproduces the exact
// view. Mode-string serializer is inline since we only have two values.
const modeSerializer = {
  encode: (v: Mode) => (v === "compare" ? "compare" : null),  // search is the default; null drops the key
  decode: (raw: string | null): Mode => (raw === "compare" ? "compare" : "search"),
};

export default function DeepSearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading deep search…</div>}>
      <DeepSearchPageInner />
    </Suspense>
  );
}

function DeepSearchPageInner() {
  const [mode, setMode] = useUrlState<Mode>("mode", "search", modeSerializer);
  const [query, setQuery] = useUrlState("q", "", URL_STATE_SERIALIZERS.string);
  const [queryA, setQueryA] = useUrlState("qa", "", URL_STATE_SERIALIZERS.string);
  const [queryB, setQueryB] = useUrlState("qb", "", URL_STATE_SERIALIZERS.string);
  const [country, setCountry] = useUrlState<string | null>(
    "country",
    null,
    URL_STATE_SERIALIZERS.nullableString,
  );
  // F5a — platform-only vs external-enriched deep search.
  const [platformOnly, setPlatformOnly] = useState(false);
  const [includeWeather, setIncludeWeather] = useUrlState(
    "weather",
    true,
    URL_STATE_SERIALIZERS.boolean,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<DeepSearchResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Phase 2A (2026-05-23) — quota envelope captured from a 429 response
  // and shown via the UpgradeModal. refresh() ticks the inline counter
  // after a successful deep-search consumes quota.
  const { refresh: refreshQuota } = useQuota();
  const [upgradeQuota, setUpgradeQuota] = useState<UpgradeModalQuotaEnvelope | null>(null);
  const [upgradeMessage, setUpgradeMessage] = useState<string | null>(null);

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

  // Phase 2A: when an API call returns 429 with the structured envelope,
  // surface the UpgradeModal instead of an opaque error string. The
  // backend returns shape: { detail: { error, quota: {...}, message } }.
  const handleQuotaError = (e: any): boolean => {
    const status = e?.response?.status;
    const detail = e?.response?.data?.detail;
    if (status === 429 && detail && typeof detail === "object" && detail.quota) {
      setUpgradeQuota(detail.quota as UpgradeModalQuotaEnvelope);
      setUpgradeMessage(typeof detail.message === "string" ? detail.message : null);
      return true;
    }
    return false;
  };

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
        platform_only: platformOnly,
      });
      setSearchResult(result);
      // Tick the inline counter so the user sees "1 left this month"
      // immediately after a successful search.
      refreshQuota();
    } catch (e: any) {
      if (handleQuotaError(e)) return; // upgrade modal owns the surface
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Deep search failed. Please try again.");
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
      refreshQuota();
    } catch (e: any) {
      if (handleQuotaError(e)) return;
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Comparison failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-slate-950">
      {/* Header */}
      <section className="border-b border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100 mb-1">Deep Search</h1>
          <p className="text-gray-600 dark:text-slate-300 text-sm mb-6">
            Research climate topics across our verified corpus and external sources.
            <span className="ml-1 text-xs text-clilens-teal-700 dark:text-teal-300 bg-clilens-teal-50 dark:bg-teal-900/30 px-2 py-0.5 rounded">
              Professional
            </span>
          </p>

          {/* Mode toggle */}
          <div className="flex gap-2 mb-6">
            <button onClick={() => setMode("search")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${mode === "search" ? "bg-clilens-teal-600 text-white" : "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-200 hover:bg-gray-200 dark:hover:bg-slate-700"}`}>
              <Search className="h-4 w-4" /> Research
            </button>
            <button onClick={() => setMode("compare")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${mode === "compare" ? "bg-clilens-teal-600 text-white" : "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-200 hover:bg-gray-200 dark:hover:bg-slate-700"}`}>
              <GitCompareArrows className="h-4 w-4" /> Compare
            </button>
          </div>

          {/* Suggested comparison topics */}
          {mode === "compare" && !queryA && !queryB && (
            <div className="mb-4">
              <p className="text-xs text-gray-500 dark:text-slate-400 mb-2 flex items-center gap-1"><TrendingUp className="w-3 h-3"/> Suggested comparisons</p>
              <div className="flex flex-wrap gap-2">
                {[ {a:"Drought in Southern Europe 2025",b:"Southern Europe drought 2018-2023"},
                   {a:"Germany renewable energy targets",b:"France nuclear energy strategy"},
                   {a:"India extreme heat 2025 trends",b:"India heatwaves 2015-2020"},
                   {a:"Arctic ice melt acceleration",b:"Antarctic ice shelf loss comparison"},
                   {a:"EU carbon emissions 2024",b:"China emissions growth trajectory"} ].map((s,i) => (
                  <button key={i} onClick={() => { setQueryA(s.a); setQueryB(s.b); }}
                    className="text-xs px-3 py-1.5 bg-gray-50 dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-900/30 border border-gray-200 dark:border-slate-700 hover:border-teal-200 dark:hover:border-teal-700/50 rounded-full text-gray-600 dark:text-slate-300 hover:text-teal-700 dark:hover:text-teal-300 transition-colors">
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
                className="w-full px-4 py-3 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary resize-none"
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
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-200">
                  <input
                    type="checkbox"
                    checked={includeWeather}
                    onChange={(e) => setIncludeWeather(e.target.checked)}
                    className="rounded border-gray-300 dark:border-slate-600 text-clilens-teal-600"
                  />
                  <Cloud className="h-4 w-4" />
                  Include weather data
                </label>
                <label
                  className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-200"
                  title={
                    platformOnly
                      ? "Searching only Climatefacts-verified sources (no external web)."
                      : "Including external web search to broaden coverage."
                  }
                >
                  <input
                    type="checkbox"
                    checked={platformOnly}
                    onChange={(e) => setPlatformOnly(e.target.checked)}
                    className="rounded border-gray-300 dark:border-slate-600 text-clilens-teal-600"
                  />
                  Platform sources only
                </label>
                <div className="ml-auto flex items-center gap-3">
                  <QuotaCounter quotaKey="deep_research" hideWhenUnlimited />
                  <button
                    onClick={handleSearch}
                    disabled={loading || !query.trim()}
                    className="px-6 py-2 bg-clilens-teal-600 text-white rounded-lg hover:bg-clilens-teal-700 disabled:opacity-50 flex items-center gap-2"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    Search
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-1">Topic A</label>
                  <input
                    value={queryA}
                    onChange={(e) => setQueryA(e.target.value)}
                    placeholder="e.g. Wind energy in Northern Europe"
                    className="w-full px-4 py-2 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-1">Topic B</label>
                  <input
                    value={queryB}
                    onChange={(e) => setQueryB(e.target.value)}
                    placeholder="e.g. Solar energy in Southern Europe"
                    className="w-full px-4 py-2 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary"
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
                <div className="ml-auto flex items-center gap-3">
                  <QuotaCounter quotaKey="compare" hideWhenUnlimited />
                  <button
                    onClick={handleCompare}
                    disabled={loading || !queryA.trim() || !queryB.trim()}
                    className="px-6 py-2 bg-clilens-teal-600 text-white rounded-lg hover:bg-clilens-teal-700 disabled:opacity-50 flex items-center gap-2"
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompareArrows className="h-4 w-4" />}
                    Compare
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Error */}
      {error && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/50 text-red-700 dark:text-red-200 px-4 py-3 rounded-lg" role="alert">
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
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Loader2 className="h-5 w-5 animate-spin text-clilens-teal-600 dark:text-teal-400" />
                  <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100">
                    {mode === "compare" ? "Comparing topics..." : "Analyzing your query..."}
                  </h3>
                </div>
                <span className="text-sm text-gray-500 dark:text-slate-400">
                  ~{Math.max(0, totalEstimate - elapsedSeconds)}s remaining
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-gray-100 dark:bg-slate-800 rounded-full h-2 mb-5 overflow-hidden">
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
                      <CheckCircle className="h-4 w-4 text-emerald-500 dark:text-emerald-400 flex-shrink-0" />
                    ) : i === activeStep ? (
                      <Loader2 className="h-4 w-4 animate-spin text-clilens-teal-600 dark:text-teal-400 flex-shrink-0" />
                    ) : (
                      <div className="h-4 w-4 rounded-full border-2 border-gray-300 dark:border-slate-600 flex-shrink-0" />
                    )}
                    <span className={`text-sm ${
                      i < activeStep ? "text-emerald-700 dark:text-emerald-300 font-medium" :
                      i === activeStep ? "text-gray-900 dark:text-slate-100 font-medium" :
                      "text-gray-400 dark:text-slate-500"
                    }`}>
                      {step.label}
                    </span>
                  </div>
                ))}
              </div>

              <p className="text-xs text-gray-400 dark:text-slate-500 mt-4">
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
          <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Research Summary</h2>
              {/* Phase 0 day 3 (2026-05-23) — EU AI Act Art. 50 disclosure.
                  The badge is visible; the matching <script type="application/ld+json">
                  ships alongside it (machine-readable disclosure). */}
              <AIProvenanceBadge
                provenance={{
                  model: searchResult.methodology?.synthesis_model || "unknown",
                  prompt_name: searchResult.methodology?.prompts_used?.synthesis?.name,
                  prompt_version: searchResult.methodology?.prompts_used?.synthesis?.version,
                  prompt_fingerprint: searchResult.methodology?.prompts_used?.synthesis?.fingerprint,
                  retrieval_strategy: searchResult.methodology?.retrieval_strategy,
                  timestamp: searchResult.searched_at,
                  surface: "deep_search",
                  content_summary: `Deep-search synthesis for: "${searchResult.query}"`,
                }}
                variant="inline"
              />
            </div>
            {/* F5c — surface WHY the answer is low-confidence prominently,
                ABOVE the prose. The user reported deep-search "always shows
                weak evidence" with no explanation; here we render the
                backend's confidence_envelope.reason + the internal/external
                evidence counts + an actionable next step, instead of burying
                it in a small pill inside the prose. */}
            {(() => {
              const env = searchResult.confidence_envelope;
              const internal = searchResult.internal_articles_count ?? 0;
              const external = searchResult.external_sources_count ?? 0;
              const isLow = env?.confidence === "low" || internal + external < 3;
              if (!isLow) return null;
              const ev = formatEvidenceStrengthPlain(internal, external);
              return (
                <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-4">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-semibold text-amber-900">
                        Why this answer is low-confidence
                      </p>
                      {env?.reason && (
                        <p className="text-amber-800 mt-1">{env.reason}</p>
                      )}
                      <p className="text-amber-800 mt-1">{ev.sentence}</p>
                      <p className="text-amber-700/90 text-xs mt-2">
                        {platformOnly
                          ? "You searched platform sources only — enable external sources, or broaden the query, for wider corroboration."
                          : "Try broadening the query or rephrasing it to match how the platform's climate sources frame the topic."}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })()}
            {/* Phase 0 day 3 (§3.3): when the backend routed to the
                low-evidence prompt, render the sentence-grounded view
                with per-sentence calibration pills + confidence banner.
                Falls back to the plain prose answer when grounding is
                absent (high-evidence path). */}
            {searchResult.sentence_grounding && searchResult.sentence_grounding.length > 0 ? (
              <SentenceGroundedAnswer
                sentences={searchResult.sentence_grounding}
                confidence={searchResult.confidence_envelope ?? null}
              />
            ) : (
              <>
                {/* v2.0 structured synthesis (2026-06-14) — key findings,
                    agreement/disagreement, evidence gauge, limitations. */}
                {searchResult.structured_synthesis && (
                  <div className="space-y-4 mb-4">
                    {/* Key Findings */}
                    {searchResult.structured_synthesis.key_findings.length > 0 && (
                      <div className="rounded-lg border border-teal-200 bg-teal-50/50 p-4">
                        <h3 className="text-sm font-semibold text-teal-800 mb-2 flex items-center gap-1.5">
                          <CheckCircle className="w-4 h-4" /> Key Findings
                        </h3>
                        <ul className="space-y-1.5">
                          {searchResult.structured_synthesis.key_findings.map((f, i) => (
                            <li key={i} className="text-sm text-teal-900 flex gap-2">
                              <span className="font-bold text-teal-500 shrink-0">{i + 1}.</span>
                              <span>{f}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Agreement / Disagreement */}
                    {(searchResult.structured_synthesis.agreement_areas.length > 0 ||
                      searchResult.structured_synthesis.disagreement_areas.length > 0) && (
                      <div className="grid sm:grid-cols-2 gap-3">
                        {searchResult.structured_synthesis.agreement_areas.length > 0 && (
                          <div className="rounded-lg border border-green-200 bg-green-50/50 p-3">
                            <h3 className="text-xs font-semibold text-green-700 mb-1.5 flex items-center gap-1">
                              <CheckCircle className="w-3.5 h-3.5" /> Sources Agree
                            </h3>
                            <ul className="space-y-1">
                              {searchResult.structured_synthesis.agreement_areas.map((a, i) => (
                                <li key={i} className="text-xs text-green-800">{a}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {searchResult.structured_synthesis.disagreement_areas.length > 0 && (
                          <div className="rounded-lg border border-red-200 bg-red-50/50 p-3">
                            <h3 className="text-xs font-semibold text-red-700 mb-1.5 flex items-center gap-1">
                              <AlertTriangle className="w-3.5 h-3.5" /> Sources Disagree
                            </h3>
                            <ul className="space-y-1">
                              {searchResult.structured_synthesis.disagreement_areas.map((d, i) => (
                                <li key={i} className="text-xs text-red-800">{d}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Evidence Strength + Limitations */}
                    <div className="flex flex-wrap gap-2 items-center text-xs">
                      <span className={`
                        px-2 py-0.5 rounded-full font-medium
                        ${searchResult.structured_synthesis.evidence_strength === "strong"
                          ? "bg-green-100 text-green-700"
                          : searchResult.structured_synthesis.evidence_strength === "moderate"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-red-100 text-red-700"}
                      `}>
                        Evidence: {searchResult.structured_synthesis.evidence_strength}
                      </span>
                      {searchResult.structured_synthesis.confidence_score != null && (
                        <span className="text-gray-500">
                          Confidence: {(searchResult.structured_synthesis.confidence_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>

                    {searchResult.structured_synthesis.limitations.length > 0 && (
                      <div className="text-xs text-gray-500 bg-gray-50 rounded-lg p-3">
                        <span className="font-medium text-gray-600">Limitations: </span>
                        {searchResult.structured_synthesis.limitations.join(" · ")}
                      </div>
                    )}
                  </div>
                )}

                <div className="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-slate-200 whitespace-pre-wrap">
                  <TranslatableText text={searchResult.answer} as="div" maxLength={5000} />
                </div>
              </>
            )}
            {/* Slice 6 (2026-05-25) — inline follow-up chat. Replaces
                the prior fire-and-forget "open in global assistant"
                button so the user can iterate on the deep-search
                result with the query carried forward via
                view_context.deep_search_query. */}
            <DeepSearchFollowupChat
              searchQuery={searchResult.query}
              searchAnswer={searchResult.answer || ""}
              countryCode={country || undefined}
            />
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
            const evidencePlain = formatEvidenceStrengthPlain(internalHits, externalHits);
            return (
              <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-4">
                <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
                  <h3 className="text-xs font-semibold text-gray-600 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5" /> Analysis Insights
                  </h3>
                  {/* Phase 2C (2026-05-23): plain-language evidence summary
                      — turns "5 internal + 2 external" into "Evidence is
                      moderate — main findings are corroborated…" so the
                      reader gets the meaning without parsing counts. */}
                  {evidencePlain.sentence && (
                    <p
                      className={`text-[11px] leading-snug max-w-md ${
                        evidencePlain.tone === "alert"
                          ? "text-red-700 dark:text-red-300"
                          : evidencePlain.tone === "warn"
                            ? "text-amber-700 dark:text-amber-300"
                            : "text-emerald-700 dark:text-emerald-300"
                      }`}
                      data-testid="deep-search-evidence-plain"
                    >
                      {evidencePlain.sentence}
                    </p>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-center">
                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-2">
                    <div className="text-lg font-bold text-gray-900 dark:text-slate-100">{searchResult.internal_articles_count}</div>
                    <div className="text-xs text-gray-600 dark:text-slate-400">Internal articles</div>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-2">
                    <div className="text-lg font-bold text-gray-900 dark:text-slate-100">{searchResult.external_sources_count}</div>
                    <div className="text-xs text-gray-600 dark:text-slate-400">External sources</div>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-2">
                    <div className="flex gap-1 justify-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-500" title={`${credCounts.HIGH} HIGH`}/>
                      <span className="w-2.5 h-2.5 rounded-full bg-yellow-500" title={`${credCounts.MEDIUM} MEDIUM`}/>
                      <span className="w-2.5 h-2.5 rounded-full bg-red-500" title={`${credCounts.LOW} LOW`}/>
                    </div>
                    <div className="text-xs text-gray-600 dark:text-slate-400 mt-1">Credibility spread</div>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-2">
                    <div className={`text-lg font-bold ${grounded ? 'text-green-600 dark:text-green-400' : grounded === false ? 'text-red-600 dark:text-red-400' : 'text-gray-400 dark:text-slate-500'}`}>
                      {grounded ? 'Grounded' : grounded === false ? 'Weak' : '—'}
                    </div>
                    <div className="text-xs text-gray-600 dark:text-slate-400">Hallucination check</div>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-2">
                    <div className="text-lg font-bold text-gray-900 dark:text-slate-100">
                      {halInfo?.hallucination_risk != null ? `${Math.round((1 - halInfo.hallucination_risk) * 100)}%` : '—'}
                    </div>
                    <div className="text-xs text-gray-600 dark:text-slate-400">Scientific confidence</div>
                  </div>
                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-2">
                    <div className={`text-lg font-bold ${avgRel != null ? avgRel > 70 ? "text-green-600 dark:text-green-400" : avgRel > 40 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400" : "text-gray-400 dark:text-slate-500"}`}>
                      {avgRel != null ? `${avgRel}%` : "—"}
                    </div>
                    <div className="text-xs text-gray-600 dark:text-slate-400">Avg reliability</div>
                  </div>
                </div>
                {searchResult.citations.length > 0 && (
                  <div className="mt-3 flex gap-1 h-1.5 rounded-full overflow-hidden bg-gray-100 dark:bg-slate-800">
                    {credCounts.HIGH > 0 && <div className="bg-green-500" style={{width:`${(credCounts.HIGH/total)*100}%`}} title={`${credCounts.HIGH} HIGH`}/>}
                    {credCounts.MEDIUM > 0 && <div className="bg-yellow-500" style={{width:`${(credCounts.MEDIUM/total)*100}%`}} title={`${credCounts.MEDIUM} MEDIUM`}/>}
                    {credCounts.LOW > 0 && <div className="bg-red-500" style={{width:`${(credCounts.LOW/total)*100}%`}} title={`${credCounts.LOW} LOW`}/>}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                  <div className="rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-2.5 py-2 text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
                    Retrieval: {internalHits} internal / {externalHits} external
                  </div>
                  <div className="rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-2.5 py-2 text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                    <Microscope className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
                    Evidence quality: {likelyWeakEvidence ? "Potentially weak" : "Acceptable"}
                  </div>
                  <button
                    type="button"
                    onClick={() => openAssistant(`Help me improve this deep-search query for stronger scientific evidence: \"${searchResult.query}\"`)}
                    className="rounded border border-teal-200 dark:border-teal-700/50 bg-teal-50 dark:bg-teal-900/30 px-2.5 py-2 text-teal-700 dark:text-teal-200 hover:bg-teal-100 dark:hover:bg-teal-800/40 transition-colors flex items-center gap-1.5 justify-center"
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
            <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/40 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-100 flex items-center gap-2 mb-2">
                <Activity className="h-4 w-4" /> Limited evidence found
              </h3>
              <p className="text-sm text-amber-800 dark:text-amber-200 mb-3">
                The system found little or no relevant evidence for this query. Use one of these options to get a more robust answer.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => openAssistant(`Help me reformulate this deep-search query with scientific rigor: \"${searchResult.query}\"`)}
                  className="px-3 py-1.5 text-xs rounded-full bg-amber-100 dark:bg-amber-900/40 hover:bg-amber-200 dark:hover:bg-amber-800/50 text-amber-900 dark:text-amber-100 border border-amber-300 dark:border-amber-700/50 transition-colors"
                >
                  Get query help in chat
                </button>
                <button
                  type="button"
                  onClick={() => setMode("compare")}
                  className="px-3 py-1.5 text-xs rounded-full bg-amber-100 dark:bg-amber-900/40 hover:bg-amber-200 dark:hover:bg-amber-800/50 text-amber-900 dark:text-amber-100 border border-amber-300 dark:border-amber-700/50 transition-colors"
                >
                  Switch to compare mode
                </button>
              </div>
            </div>
          )}

          {/* Weather Context */}
          {searchResult.weather_context && (
            <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800/40 p-4">
              <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-100 flex items-center gap-2 mb-2">
                <Cloud className="h-4 w-4" /> Weather Data ({searchResult.weather_context.country_code})
              </h3>
              <div className="space-y-1">
                {searchResult.weather_context.data_points.map((dp, i) => (
                  <p key={i} className="text-sm text-blue-800 dark:text-blue-200">
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

          {/* Citations — Phase 2I (2026-05-23) MH2 rollout: same source
              data offered as a List view (visual cards with chips) or a
              Table view (precise sortable rows the reader can scan or
              copy-paste). */}
          <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-6">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-3">
              Sources ({searchResult.internal_articles_count} internal, {searchResult.external_sources_count} external)
            </h3>
            <MultiViewTabs
              ariaLabel="Citations view"
              chart={
                <div className="space-y-3" data-testid="citations-list-view">
                  {searchResult.citations.map((c, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      {c.type === "internal_article" ? (
                        <BookOpen className="h-4 w-4 text-clilens-teal-600 dark:text-teal-400 mt-0.5 flex-shrink-0" />
                      ) : (
                        <ExternalLink className="h-4 w-4 text-gray-400 dark:text-slate-500 mt-0.5 flex-shrink-0" />
                      )}
                      <div>
                        <p className="text-gray-900 dark:text-slate-100 font-medium">
                          {c.title || c.source_name || c.source_url}
                        </p>
                        {c.excerpt && (
                          <p className="text-gray-600 dark:text-slate-300 text-xs mt-0.5">{c.excerpt}</p>
                        )}
                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-slate-400">
                          {c.credibility && (
                            <span className={`px-1.5 py-0.5 rounded ${
                              c.credibility === "HIGH" ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-200" :
                              c.credibility === "MEDIUM" ? "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-200" :
                              "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-200"
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
                            <span className={c.reliability_score > 70 ? 'text-green-600 dark:text-green-400' : c.reliability_score > 40 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}>
                              Reliability: {Math.min(100, c.reliability_score)}%
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              }
              table={
                <div className="overflow-x-auto" data-testid="citations-table-view">
                  <table className="w-full text-xs border border-gray-200 dark:border-slate-700">
                    <caption className="sr-only">
                      Citations supporting this deep-search result — type, source, credibility, relevance
                    </caption>
                    <thead className="bg-gray-50 dark:bg-slate-800 uppercase text-gray-500 dark:text-slate-400">
                      <tr>
                        <th className="px-3 py-2 text-left">Type</th>
                        <th className="px-3 py-2 text-left">Title / URL</th>
                        <th className="px-3 py-2 text-left">Source</th>
                        <th className="px-3 py-2 text-left">Date</th>
                        <th className="px-3 py-2 text-right">Credibility</th>
                        <th className="px-3 py-2 text-right">Relevance</th>
                        <th className="px-3 py-2 text-right">Reliability</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
                      {searchResult.citations.map((c, i) => (
                        <tr key={i}>
                          <td className="px-3 py-2 text-gray-700 dark:text-slate-300">
                            {c.type === "internal_article" ? "Internal" : "External"}
                          </td>
                          <td className="px-3 py-2 text-gray-900 dark:text-slate-100 max-w-xs truncate">
                            {c.title || c.source_url}
                          </td>
                          <td className="px-3 py-2 text-gray-700 dark:text-slate-300">
                            {c.source_name || "—"}
                          </td>
                          <td className="px-3 py-2 text-gray-700 dark:text-slate-300">
                            {c.published_date || "—"}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-900 dark:text-slate-100">
                            {c.credibility || "—"}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-900 dark:text-slate-100">
                            {c.relevance_score != null
                              ? `${Math.min(100, Math.round((c.relevance_score ?? 0) * 100))}%`
                              : "—"}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-900 dark:text-slate-100">
                            {c.reliability_score != null
                              ? `${Math.min(100, c.reliability_score)}%`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              }
            />
          </div>
        </div>
      )}

      {/* Compare Results */}
      {compareResult && !loading && (
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
          {/* Aggregate guidance (§3.1 fix on 2026-05-23). Surfaces the
              evidence-empty / asymmetric / weak status PROMINENTLY at the
              top of the compare result — before the comparative card — so
              the user sees the honesty signal before the LLM narrative. */}
          {compareResult.guidance && (
            <div
              className={`rounded-lg border px-4 py-3 ${
                compareResult.guidance.status === "empty"
                  ? "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/40"
                  : compareResult.guidance.status === "asymmetric"
                  ? "bg-orange-50 dark:bg-orange-950/30 border-orange-200 dark:border-orange-800/40"
                  : "bg-yellow-50 dark:bg-yellow-950/30 border-yellow-200 dark:border-yellow-800/40"
              }`}
              role="status"
              data-testid="compare-guidance-block"
              data-status={compareResult.guidance.status}
            >
              <div className="flex items-start gap-2.5">
                <AlertTriangle
                  className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                    compareResult.guidance.status === "empty"
                      ? "text-amber-600 dark:text-amber-400"
                      : compareResult.guidance.status === "asymmetric"
                      ? "text-orange-600 dark:text-orange-400"
                      : "text-yellow-700 dark:text-yellow-400"
                  }`}
                  aria-hidden="true"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p
                      className={`text-sm font-semibold capitalize ${
                        compareResult.guidance.status === "empty"
                          ? "text-amber-900 dark:text-amber-100"
                          : compareResult.guidance.status === "asymmetric"
                          ? "text-orange-900 dark:text-orange-100"
                          : "text-yellow-900 dark:text-yellow-100"
                      }`}
                    >
                      {compareResult.guidance.status === "empty"
                        ? "No evidence on either side"
                        : compareResult.guidance.status === "asymmetric"
                        ? "Asymmetric evidence"
                        : "Weak combined evidence"}
                    </p>
                    {compareResult.guidance.per_side && (
                      <span className="text-[11px] font-mono text-gray-600 dark:text-gray-400 bg-white/70 dark:bg-black/30 px-1.5 py-0.5 rounded">
                        A: {compareResult.guidance.per_side.a.internal}i+
                        {compareResult.guidance.per_side.a.external}e &middot;{" "}
                        B: {compareResult.guidance.per_side.b.internal}i+
                        {compareResult.guidance.per_side.b.external}e
                      </span>
                    )}
                  </div>
                  <p
                    className={`text-xs mt-1 leading-relaxed ${
                      compareResult.guidance.status === "empty"
                        ? "text-amber-800 dark:text-amber-200"
                        : compareResult.guidance.status === "asymmetric"
                        ? "text-orange-800 dark:text-orange-200"
                        : "text-yellow-800 dark:text-yellow-200"
                    }`}
                  >
                    {compareResult.guidance.message}
                  </p>
                  {Array.isArray(compareResult.guidance.suggested_actions) &&
                    compareResult.guidance.suggested_actions.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {compareResult.guidance.suggested_actions.slice(0, 4).map((act, i) => (
                          <li
                            key={i}
                            className={`text-[11px] flex items-start gap-1.5 ${
                              compareResult.guidance!.status === "empty"
                                ? "text-amber-700 dark:text-amber-300"
                                : compareResult.guidance!.status === "asymmetric"
                                ? "text-orange-700 dark:text-orange-300"
                                : "text-yellow-700 dark:text-yellow-300"
                            }`}
                          >
                            <span aria-hidden="true">&bull;</span>
                            <span>{act}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                </div>
              </div>
            </div>
          )}

          {/* Unified refinement chips at compare level (§3.1 fix). When
              both sides were empty OR the aggregate was weak, the backend
              merges per-side `_suggest_scope_refinements` into one chip
              row here. Clicking sets Topic A or B and re-runs. */}
          {compareResult.clarification_needed && compareResult.clarification_needed.length > 0 && (
            <div
              className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-lg p-4"
              data-testid="compare-refinement-chips"
            >
              <p className="text-xs font-semibold text-gray-700 dark:text-slate-200 mb-2 flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5" />
                Try a refined query to get substantive evidence
              </p>
              <div className="flex flex-wrap gap-2">
                {compareResult.clarification_needed.map((s, i) => (
                  <div key={i} className="inline-flex items-stretch rounded-full border border-teal-200 dark:border-teal-700/40 bg-teal-50 dark:bg-teal-900/30 overflow-hidden">
                    <span className="px-2.5 py-1 text-xs text-teal-800 dark:text-teal-200 max-w-md truncate">
                      {s}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setQueryA(s);
                        setTimeout(() => handleCompare(), 0);
                      }}
                      className="px-2 py-1 text-[10px] font-semibold uppercase bg-teal-100 dark:bg-teal-800/60 text-teal-800 dark:text-teal-100 hover:bg-teal-200 dark:hover:bg-teal-700/60 border-l border-teal-200 dark:border-teal-700/40"
                      aria-label={`Use as Topic A: ${s}`}
                    >
                      A
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setQueryB(s);
                        setTimeout(() => handleCompare(), 0);
                      }}
                      className="px-2 py-1 text-[10px] font-semibold uppercase bg-teal-100 dark:bg-teal-800/60 text-teal-800 dark:text-teal-100 hover:bg-teal-200 dark:hover:bg-teal-700/60 border-l border-teal-200 dark:border-teal-700/40"
                      aria-label={`Use as Topic B: ${s}`}
                    >
                      B
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Visual comparative analysis (preferred when structured data is present) */}
          {compareResult.comparative_analysis_structured ? (
            <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-6">
              <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Comparative Analysis</h2>
                <div className="flex items-center gap-2 flex-wrap">
                  {compareResult.low_confidence && (
                    <span
                      className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 border border-amber-200 dark:border-amber-700/40 rounded-full"
                      title={
                        compareResult.comparative_analysis_structured.low_confidence_reason ||
                        "This comparison is structurally low-confidence."
                      }
                      data-testid="compare-low-confidence-pill"
                    >
                      <AlertTriangle className="w-3 h-3" />
                      Low confidence
                    </span>
                  )}
                  <AIProvenanceBadge
                    provenance={{
                      model: compareResult.result_a.methodology?.synthesis_model || "unknown",
                      prompt_name: "deep_search_compare_synthesis",
                      retrieval_strategy: compareResult.result_a.methodology?.retrieval_strategy,
                      timestamp: compareResult.compared_at,
                      surface: "deep_search_compare",
                      content_summary: `Comparative analysis: "${compareResult.query_a}" vs "${compareResult.query_b}"`,
                    }}
                    variant="inline"
                  />
                </div>
              </div>
              {compareResult.comparative_analysis_structured.low_confidence_reason && (
                <p className="text-xs text-amber-700 dark:text-amber-300 mb-3 italic">
                  {compareResult.comparative_analysis_structured.low_confidence_reason}
                </p>
              )}
              <CompareCharts data={compareResult} />
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-6">
              <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Comparative Analysis</h2>
                <div className="flex items-center gap-2 flex-wrap">
                  {compareResult.low_confidence && (
                    <span
                      className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 border border-amber-200 dark:border-amber-700/40 rounded-full"
                      data-testid="compare-low-confidence-pill"
                    >
                      <AlertTriangle className="w-3 h-3" />
                      Low confidence
                    </span>
                  )}
                  <AIProvenanceBadge
                    provenance={{
                      model: compareResult.result_a.methodology?.synthesis_model || "unknown",
                      prompt_name: "deep_search_compare_synthesis",
                      retrieval_strategy: compareResult.result_a.methodology?.retrieval_strategy,
                      timestamp: compareResult.compared_at,
                      surface: "deep_search_compare",
                      content_summary: `Comparative analysis: "${compareResult.query_a}" vs "${compareResult.query_b}"`,
                    }}
                    variant="inline"
                  />
                </div>
              </div>
              <div className="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-slate-200 whitespace-pre-wrap">
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
              <div key={label} className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-4">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-1">{label}: {q}</h3>
                <p className="text-xs text-gray-600 dark:text-slate-400 mb-3">
                  {r.internal_articles_count} internal, {r.external_sources_count} external sources
                </p>
                <div className="text-sm text-gray-700 dark:text-slate-200 whitespace-pre-wrap line-clamp-[12]">
                  {r.answer}
                </div>
                {r.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-800">
                    <p className="text-xs font-medium text-gray-600 dark:text-slate-400 mb-2">Top sources:</p>
                    {r.citations.slice(0, 3).map((c, i) => (
                      <p key={i} className="text-xs text-gray-700 dark:text-slate-300 truncate">
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

      {/* Phase 2A (2026-05-23) — upgrade modal mounts here, rendered
          when a gated endpoint returns HTTP 429 with the structured
          envelope. Backend copy flows through verbatim. */}
      <UpgradeModal
        quota={upgradeQuota}
        message={upgradeMessage}
        onClose={() => {
          setUpgradeQuota(null);
          setUpgradeMessage(null);
        }}
      />
    </main>
  );
}
