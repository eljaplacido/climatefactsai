"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Globe,
  Newspaper,
  Thermometer,
  Shield,
  AlertTriangle,
  ScrollText,
  Loader2,
  Map as MapIcon,
  GitCompare,
  TrendingUp,
} from "lucide-react";
import { useUrlState, URL_STATE_SERIALIZERS } from "@/lib/useUrlState";
import {
  formatTemperatureAnomalyPlain,
  formatCredibilityPlain,
  formatClimateRiskPlain,
  formatArticleCountPlain,
  formatTemperatureAnomalyBusiness,
  formatCredibilityBusiness,
  formatClimateRiskBusiness,
  formatArticleCountBusiness,
  getComplianceFrameworks,
  type ViewMode,
} from "@/lib/plainLanguage";
import EmbedShareButton from "@/components/EmbedShareButton";
import SaveButton from "@/components/SaveButton";
import MultiViewTabs from "@/components/MultiViewTabs";
import AOISubscribeButton from "@/components/AOISubscribeButton";
import ProjectionsPanel from "@/components/ProjectionsPanel";
import CountryBiomeSummary from "@/components/CountryBiomeSummary";

/**
 * Country Climate Passport — Phase 2B (2026-05-23), MH3 from the
 * competitive UX audit. Pattern lifted from Climate Watch's country
 * profile + World Bank CCKP's structure: one modular tabbed page per
 * country with deep-linkable tabs.
 *
 * Tabs:
 *   - overview: KPIs + headline summary
 *   - news: most recent articles in our corpus for this country
 *   - climate: temperature anomaly + precipitation trends (Open-Meteo)
 *   - sources: ranked source coverage with credibility tiers
 *   - claims: claim ledger (per-claim verdicts mentioning this country)
 *
 * Tab selection is URL-persistent via `?tab=...` so deep-links and
 * shared URLs land directly on the right pane.
 *
 * Backend: composed entirely from existing routes — no new aggregator
 * endpoint needed:
 *   GET /api/map/country/{cc}/detail        → KPIs + sources + articles
 *   GET /api/map/country/{cc}/climate-data  → climate trends
 *   GET /api/map/country/{cc}/claim-ledger  → claim ledger
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

type TabKey = "overview" | "news" | "climate" | "projections" | "sources" | "claims";

const TABS: { key: TabKey; label: string; icon: any }[] = [
  { key: "overview", label: "Overview", icon: Globe },
  { key: "news", label: "News", icon: Newspaper },
  { key: "climate", label: "Climate Data", icon: Thermometer },
  { key: "projections", label: "Projections", icon: TrendingUp },
  { key: "sources", label: "Sources", icon: Shield },
  { key: "claims", label: "Claim Ledger", icon: ScrollText },
];

// Inline tab-key serializer for useUrlState. Drops the param when the
// value is the default ('overview'), keeping clean URLs.
const tabSerializer = {
  encode: (v: TabKey) => (v === "overview" ? null : v),
  decode: (raw: string | null): TabKey => {
    const candidates: TabKey[] = [
      "overview", "news", "climate", "projections", "sources", "claims",
    ];
    return (candidates.find((t) => t === raw) ?? "overview") as TabKey;
  },
};

interface CountryDetail {
  country_code: string;
  country_name: string;
  flag?: string;
  continent?: string;
  article_count: number;
  avg_credibility: number | null;
  climate_risk_score: number | null;
  category_breakdown?: Record<string, number>;
  weather?: {
    temperature_c?: number;
    humidity_pct?: number;
    precipitation_mm?: number;
    wind_speed_kmh?: number;
    temperature_anomaly_c?: number | null;
  } | null;
  sources?: Array<{
    source_name: string;
    article_count: number;
    avg_credibility?: number | null;
  }>;
  recent_articles?: Array<{
    article_id: string;
    title: string;
    source_name: string;
    published_date?: string | null;
    credibility?: string | null;
    reliability_score?: number | null;
  }>;
}

interface ClimateData {
  country_code: string;
  current_month?: { period: string; temperature_avg_c?: number | null; precipitation_avg_mm?: number | null } | null;
  last_year_same_month?: { period: string; temperature_avg_c?: number | null; precipitation_avg_mm?: number | null } | null;
  five_years_ago_same_month?: { period: string; temperature_avg_c?: number | null; precipitation_avg_mm?: number | null } | null;
  temperature_trend?: "rising" | "falling" | "stable" | null;
  precipitation_comparison?: string | null;
}

interface ClaimLedgerEntry {
  claim_id: string;
  claim_text: string;
  verification_status?: string;
  confidence_score?: number;
  article_id?: string;
  article_title?: string;
  published_date?: string;
}

export default function CountryPassportPage() {
  const params = useParams();
  const rawCode = Array.isArray(params?.code) ? params.code[0] : (params?.code as string);
  const code = (rawCode || "").toUpperCase();

  const [tab, setTab] = useUrlState<TabKey>("tab", "overview", tabSerializer);

  // Phase 6 (2026-05-24) — view mode toggle. Public is the default
  // (consumer + journalist + scientist framing). Business swaps the
  // plain-language sentences to a fiduciary-audience framing and shows
  // compliance-framework chips on KPIs. URL-persistent so business
  // users can share a "boardroom view" link with their colleagues.
  const viewSerializer = {
    encode: (v: ViewMode) => (v === "business" ? "business" : null),
    decode: (raw: string | null): ViewMode =>
      raw === "business" ? "business" : "public",
  };
  const [viewMode, setViewMode] = useUrlState<ViewMode>(
    "view",
    "public",
    viewSerializer,
  );

  const [detail, setDetail] = useState<CountryDetail | null>(null);
  const [climate, setClimate] = useState<ClimateData | null>(null);
  const [claims, setClaims] = useState<ClaimLedgerEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch the headline detail on every code change.
  useEffect(() => {
    if (!code || code.length !== 2) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/map/country/${code}/detail`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: CountryDetail) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load country");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  // Lazy-load climate + claims data only when their tab is selected.
  useEffect(() => {
    if (!code || code.length !== 2) return;
    if (tab === "climate" && climate === null) {
      fetch(`${API_BASE}/api/map/country/${code}/climate-data`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => setClimate(data))
        .catch(() => setClimate(null));
    }
    if (tab === "claims" && claims === null) {
      fetch(`${API_BASE}/api/map/country/${code}/claim-ledger`)
        .then((r) => (r.ok ? r.json() : []))
        .then((data) => setClaims(Array.isArray(data) ? data : (data?.items ?? [])))
        .catch(() => setClaims([]));
    }
  }, [tab, code, climate, claims]);

  if (!code || code.length !== 2) {
    return (
      <main className="min-h-screen bg-gray-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 dark:text-slate-300">Invalid country code.</p>
          <Link href="/map" className="text-clilens-primary underline">Back to map</Link>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 dark:bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-teal-500" />
      </main>
    );
  }

  if (error || !detail) {
    return (
      <main className="min-h-screen bg-gray-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <p className="text-gray-700 dark:text-slate-200 mb-2">Could not load country data.</p>
          <p className="text-xs text-gray-500 dark:text-slate-400 mb-4">{error}</p>
          <Link
            href="/map"
            className="inline-flex items-center gap-1.5 text-sm text-clilens-primary hover:underline"
          >
            <ArrowLeft className="w-4 h-4" /> Back to map
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-slate-950" data-testid="country-passport">
      {/* Header — country name, flag, KPIs */}
      <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link
            href="/map"
            className="inline-flex items-center gap-1.5 text-xs text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200 mb-3"
          >
            <ArrowLeft className="w-3 h-3" /> Back to map
          </Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <span className="text-4xl" aria-hidden="true">{detail.flag || "🌍"}</span>
              <div>
                <h1
                  className="text-2xl font-bold text-gray-900 dark:text-slate-100"
                  data-testid="country-passport-title"
                >
                  {detail.country_name}
                  <span className="ml-2 text-sm font-mono text-gray-500 dark:text-slate-400">
                    {detail.country_code}
                  </span>
                </h1>
                {detail.continent && (
                  <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
                    {detail.continent}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href={`/map?country=${code}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-slate-200 bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 rounded-md transition-colors"
              >
                <MapIcon className="w-3.5 h-3.5" /> View on map
              </Link>
              <Link
                href={`/deep-search?mode=compare&country=${code}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-slate-200 bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 rounded-md transition-colors"
              >
                <GitCompare className="w-3.5 h-3.5" /> Compare with…
              </Link>
              {/* Slice 3 (2026-05-25) — save country to polymorphic
                  /api/user/saved (item_type=country). */}
              <SaveButton
                type="country"
                itemRef={code}
                label={detail.country_name}
                variant="chip"
              />
              {/* Phase 2E (2026-05-23) — MH6 distribution play. Journalists
                  embed the KPI snapshot into their own articles via the
                  /embed/country/{code} iframe. */}
              <EmbedShareButton
                embedPath={`/embed/country/${code}`}
                label={`Share embed code for ${detail.country_name}`}
              />
              {/* Phase 3 (2026-05-23) — MH5 AOI alerts. Tier-gated to Basic+
                  via the backend; freemium/anonymous users see an upgrade
                  state in the modal. */}
              <AOISubscribeButton
                countryCode={code}
                countryName={detail.country_name}
                authToken={
                  typeof window !== "undefined"
                    ? localStorage.getItem("clilens_token")
                    : null
                }
              />
            </div>
          </div>

          {/* Phase 6 (2026-05-24) — View mode toggle.
              Public (default) shows consumer-grade plain language;
              Business swaps to fiduciary-audience framing + compliance
              chips. URL-persistent so the link itself encodes the view. */}
          <div
            className="mt-5 flex items-center gap-1 p-0.5 bg-gray-100 dark:bg-slate-800 rounded-md w-fit"
            role="radiogroup"
            aria-label="View mode"
            data-testid="passport-view-mode-toggle"
          >
            <button
              type="button"
              role="radio"
              aria-checked={viewMode === "public"}
              onClick={() => setViewMode("public")}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                viewMode === "public"
                  ? "bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 shadow-sm"
                  : "text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-200"
              }`}
              data-testid="passport-view-public"
            >
              Public view
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={viewMode === "business"}
              onClick={() => setViewMode("business")}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                viewMode === "business"
                  ? "bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 shadow-sm"
                  : "text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-200"
              }`}
              data-testid="passport-view-business"
            >
              Business view
            </button>
          </div>

          {/* KPI strip — Phase 2C + Phase 6: each KPI now carries a
              templated plain-language interpretation sentence below the
              raw number. The viewMode swaps between public-audience and
              business-audience framings. Business view also surfaces
              compliance-framework chips. */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
            <KpiCard
              label="Articles tracked"
              value={detail.article_count.toLocaleString()}
              plain={
                viewMode === "business"
                  ? formatArticleCountBusiness(detail.article_count, {
                      entity: detail.country_name,
                    })
                  : formatArticleCountPlain(detail.article_count, {
                      entity: detail.country_name,
                      periodLabel: "in our verified corpus",
                    })
              }
              complianceFrameworks={
                viewMode === "business" ? getComplianceFrameworks("article_count") : []
              }
              testId="kpi-articles"
            />
            <KpiCard
              label="Avg credibility"
              value={
                detail.avg_credibility != null
                  ? `${Math.round(detail.avg_credibility)}/100`
                  : "—"
              }
              plain={
                viewMode === "business"
                  ? formatCredibilityBusiness(detail.avg_credibility, {
                      entity: `${detail.country_name}'s sources`,
                    })
                  : formatCredibilityPlain(detail.avg_credibility, {
                      entity: `${detail.country_name}'s sources`,
                      sampleSize: detail.article_count,
                    })
              }
              complianceFrameworks={
                viewMode === "business" ? getComplianceFrameworks("credibility") : []
              }
              testId="kpi-credibility"
            />
            <KpiCard
              label="Climate risk"
              value={
                detail.climate_risk_score != null
                  ? `${Math.round(detail.climate_risk_score)}/100`
                  : "—"
              }
              plain={
                viewMode === "business"
                  ? formatClimateRiskBusiness(detail.climate_risk_score, {
                      entity: detail.country_name,
                    })
                  : formatClimateRiskPlain(detail.climate_risk_score, {
                      entity: detail.country_name,
                    })
              }
              complianceFrameworks={
                viewMode === "business" ? getComplianceFrameworks("climate_risk") : []
              }
              testId="kpi-risk"
            />
            <KpiCard
              label="Temp anomaly"
              value={
                detail.weather?.temperature_anomaly_c != null
                  ? `${detail.weather.temperature_anomaly_c > 0 ? "+" : ""}${detail.weather.temperature_anomaly_c}°C`
                  : "—"
              }
              plain={
                viewMode === "business"
                  ? formatTemperatureAnomalyBusiness(
                      detail.weather?.temperature_anomaly_c,
                      { locationName: detail.country_name },
                    )
                  : formatTemperatureAnomalyPlain(
                      detail.weather?.temperature_anomaly_c,
                      {
                        locationName: detail.country_name,
                        baselineLabel: "the same month last year",
                      },
                    )
              }
              complianceFrameworks={
                viewMode === "business" ? getComplianceFrameworks("temperature_anomaly") : []
              }
              testId="kpi-anomaly"
            />
          </div>
        </div>

        {/* Tab bar */}
        <nav
          className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 -mb-px flex gap-1 overflow-x-auto"
          role="tablist"
          aria-label="Country sections"
        >
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                role="tab"
                type="button"
                aria-selected={active}
                aria-controls={`passport-panel-${t.key}`}
                id={`passport-tab-${t.key}`}
                data-testid={`passport-tab-${t.key}`}
                onClick={() => setTab(t.key)}
                className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  active
                    ? "border-teal-500 text-teal-700 dark:text-teal-300"
                    : "border-transparent text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-200 hover:border-gray-300 dark:hover:border-slate-600"
                }`}
              >
                <Icon className="w-4 h-4" aria-hidden="true" />
                {t.label}
              </button>
            );
          })}
        </nav>
      </header>

      {/* Tab panels */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {tab === "overview" && (
          <Panel id="overview" testId="passport-panel-overview">
            <OverviewTab detail={detail} />
          </Panel>
        )}
        {tab === "news" && (
          <Panel id="news" testId="passport-panel-news">
            <NewsTab detail={detail} />
          </Panel>
        )}
        {tab === "climate" && (
          <Panel id="climate" testId="passport-panel-climate">
            <ClimateTab climate={climate} countryName={detail.country_name} />
          </Panel>
        )}
        {tab === "projections" && (
          <Panel id="projections" testId="passport-panel-projections">
            <ProjectionsPanel
              countryCode={detail.country_code}
              countryName={detail.country_name}
            />
          </Panel>
        )}
        {tab === "sources" && (
          <Panel id="sources" testId="passport-panel-sources">
            <SourcesTab detail={detail} />
          </Panel>
        )}
        {tab === "claims" && (
          <Panel id="claims" testId="passport-panel-claims">
            <ClaimsTab claims={claims} countryName={detail.country_name} />
          </Panel>
        )}
      </section>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function Panel({
  id,
  testId,
  children,
}: {
  id: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role="tabpanel"
      id={`passport-panel-${id}`}
      aria-labelledby={`passport-tab-${id}`}
      data-testid={testId}
      tabIndex={0}
    >
      {children}
    </div>
  );
}

function KpiCard({
  label,
  value,
  tone,
  plain,
  complianceFrameworks,
  testId,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "alert" | "neutral";
  /** Optional plain-language interpretation (Phase 2C). When provided,
   *  takes precedence over the explicit `tone` prop so value colour and
   *  sentence colour stay aligned. */
  plain?: { sentence: string; tone: "ok" | "warn" | "alert" | "neutral" };
  /** Phase 6 (2026-05-24) — compliance framework chips shown in
   *  business view. Empty array = no chips. */
  complianceFrameworks?: string[];
  testId?: string;
}) {
  const resolvedTone = plain?.tone ?? tone ?? "neutral";
  const valueToneClass =
    resolvedTone === "ok"
      ? "text-emerald-700 dark:text-emerald-300"
      : resolvedTone === "warn"
        ? "text-amber-700 dark:text-amber-300"
        : resolvedTone === "alert"
          ? "text-red-700 dark:text-red-300"
          : "text-gray-900 dark:text-slate-100";
  // Lower-contrast secondary text for the sentence so the value stays
  // the dominant element.
  const sentenceToneClass =
    resolvedTone === "ok"
      ? "text-emerald-700/80 dark:text-emerald-300/90"
      : resolvedTone === "warn"
        ? "text-amber-700/90 dark:text-amber-300/90"
        : resolvedTone === "alert"
          ? "text-red-700/90 dark:text-red-300/90"
          : "text-gray-600 dark:text-slate-400";
  return (
    <div
      className="bg-gray-50 dark:bg-slate-800 rounded-lg p-3"
      data-testid={testId}
    >
      <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-slate-400">
        {label}
      </p>
      <p className={`text-xl font-bold mt-1 ${valueToneClass}`}>{value}</p>
      {plain?.sentence && (
        <p
          className={`text-[11px] leading-snug mt-1.5 ${sentenceToneClass}`}
          data-testid={testId ? `${testId}-plain` : undefined}
        >
          {plain.sentence}
        </p>
      )}
      {complianceFrameworks && complianceFrameworks.length > 0 && (
        <div
          className="mt-2 flex flex-wrap gap-1"
          data-testid={testId ? `${testId}-compliance` : undefined}
        >
          {complianceFrameworks.map((fw) => (
            <span
              key={fw}
              className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200"
              title={`Relevant to ${fw} disclosure`}
            >
              {fw}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function OverviewTab({ detail }: { detail: CountryDetail }) {
  const cats = Object.entries(detail.category_breakdown || {});
  return (
    <div className="space-y-6">
      {/* Phase 9 (2026-05-25) — biome + climate-effects narrative.
          Renders BEFORE the news-corpus snapshot so users get
          'what's at stake' framing first. */}
      <CountryBiomeSummary
        countryCode={detail.country_code}
        countryName={detail.country_name}
        onAskAssistant={(q) => {
          // Best-effort: dispatch a window event the chat panel listens
          // for. The panel is mounted by the global layout, so we
          // can't pass a direct callback.
          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new CustomEvent("clilens:ask-chat", {
                detail: { question: q, source: "country-biome" },
              }),
            );
          }
        }}
      />

      <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-3">
          Current snapshot
        </h2>
        <p className="text-sm text-gray-700 dark:text-slate-200">
          {detail.country_name} has{" "}
          <strong>{detail.article_count.toLocaleString()}</strong> articles in
          our verified corpus
          {detail.avg_credibility != null && (
            <>
              {" "}with an average credibility score of{" "}
              <strong>{Math.round(detail.avg_credibility)}/100</strong>
            </>
          )}
          {detail.weather?.temperature_anomaly_c != null && (
            <>
              . The current temperature is{" "}
              <strong>
                {detail.weather.temperature_anomaly_c > 0 ? "+" : ""}
                {detail.weather.temperature_anomaly_c}°C
              </strong>{" "}
              relative to the same month last year
            </>
          )}
          .
        </p>
      </div>

      {cats.length > 0 && (
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-3">
            Article topics
          </h2>
          <div className="flex flex-wrap gap-2">
            {cats.map(([cat, count]) => (
              <span
                key={cat}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-200 border border-gray-200 dark:border-slate-700"
              >
                {cat.replace(/_/g, " ")}
                <span className="font-semibold">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function NewsTab({ detail }: { detail: CountryDetail }) {
  const articles = detail.recent_articles || [];
  if (articles.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-8 text-center">
        <Newspaper className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
        <p className="text-sm text-gray-500 dark:text-slate-400">
          No articles tracked yet for {detail.country_name}.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 divide-y divide-gray-100 dark:divide-slate-800">
      {articles.map((a) => (
        <Link
          key={a.article_id}
          href={`/articles/${a.article_id}`}
          className="block p-4 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
        >
          <div className="flex items-center gap-2 text-[11px] text-gray-500 dark:text-slate-400 mb-1">
            <span>{a.source_name}</span>
            {a.published_date && (
              <>
                <span>·</span>
                <span>{new Date(a.published_date).toLocaleDateString()}</span>
              </>
            )}
            {a.credibility && (
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] uppercase ${
                  a.credibility === "HIGH"
                    ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-200"
                    : a.credibility === "MEDIUM"
                      ? "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-200"
                      : "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-200"
                }`}
              >
                {a.credibility}
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-gray-900 dark:text-slate-100">
            {a.title}
          </p>
        </Link>
      ))}
    </div>
  );
}

function ClimateTab({
  climate,
  countryName,
}: {
  climate: ClimateData | null;
  countryName: string;
}) {
  if (climate === null) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-teal-500" />
      </div>
    );
  }
  const cm = climate.current_month;
  const ly = climate.last_year_same_month;
  const fy = climate.five_years_ago_same_month;
  const hasAny = cm || ly || fy;
  if (!hasAny) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-8 text-center">
        <Thermometer className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
        <p className="text-sm text-gray-500 dark:text-slate-400">
          No climate data available for {countryName}.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {(climate.temperature_trend || climate.precipitation_comparison) && (
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-3">
            Trend summary
          </h2>
          {climate.temperature_trend && (
            <p className="text-sm text-gray-700 dark:text-slate-200">
              Temperature trend over the last five years:{" "}
              <strong className="capitalize">{climate.temperature_trend}</strong>
            </p>
          )}
          {climate.precipitation_comparison && (
            <p className="text-sm text-gray-700 dark:text-slate-200 mt-1">
              Precipitation: {climate.precipitation_comparison}
            </p>
          )}
        </div>
      )}

      {/* Phase 2G (2026-05-23) — MH2 multi-view tabs from the
          competitive UX audit: the same climate dataset offered as a
          chart, map (omitted here since we have one country, not many),
          or raw table. Reader picks the form. */}
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-3">
          Monthly comparison
        </h2>
        <MultiViewTabs
          ariaLabel="Climate data view"
          chart={
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <ClimatePeriodCard label="Current month" data={cm} highlight />
              <ClimatePeriodCard label="Last year, same month" data={ly} />
              <ClimatePeriodCard label="5 years ago, same month" data={fy} />
            </div>
          }
          table={<ClimateTableView climate={climate} countryName={countryName} />}
        />
      </div>
    </div>
  );
}

function ClimateTableView({
  climate,
  countryName,
}: {
  climate: ClimateData;
  countryName: string;
}) {
  const rows = [
    { label: "Current month", data: climate.current_month },
    { label: "Last year, same month", data: climate.last_year_same_month },
    { label: "5 years ago, same month", data: climate.five_years_ago_same_month },
  ].filter((r) => r.data);
  return (
    <div className="overflow-x-auto">
      <table
        className="w-full text-sm border border-gray-200 dark:border-slate-700"
        data-testid="climate-table-view"
      >
        <caption className="sr-only">
          Climate comparison table for {countryName} — temperature and precipitation by period
        </caption>
        <thead className="bg-gray-50 dark:bg-slate-800 text-xs uppercase text-gray-500 dark:text-slate-400">
          <tr>
            <th className="px-3 py-2 text-left">Period</th>
            <th className="px-3 py-2 text-right">Year-month</th>
            <th className="px-3 py-2 text-right">Avg temperature (°C)</th>
            <th className="px-3 py-2 text-right">Avg precipitation (mm)</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
          {rows.map((r) => (
            <tr key={r.label}>
              <td className="px-3 py-2 text-gray-900 dark:text-slate-100">
                {r.label}
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-gray-700 dark:text-slate-300">
                {r.data?.period ?? "—"}
              </td>
              <td className="px-3 py-2 text-right text-gray-900 dark:text-slate-100">
                {r.data?.temperature_avg_c != null
                  ? r.data.temperature_avg_c.toFixed(1)
                  : "—"}
              </td>
              <td className="px-3 py-2 text-right text-gray-900 dark:text-slate-100">
                {r.data?.precipitation_avg_mm != null
                  ? r.data.precipitation_avg_mm.toFixed(1)
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClimatePeriodCard({
  label,
  data,
  highlight = false,
}: {
  label: string;
  data: ClimateData["current_month"];
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-md p-3 ${
        highlight
          ? "bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800/40"
          : "bg-gray-50 dark:bg-slate-800"
      }`}
    >
      <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-slate-400">
        {label}
      </p>
      {data ? (
        <>
          <p className="text-xs text-gray-600 dark:text-slate-400 mt-1">
            {data.period}
          </p>
          <p className="text-base font-bold text-gray-900 dark:text-slate-100 mt-1">
            {data.temperature_avg_c != null
              ? `${data.temperature_avg_c.toFixed(1)}°C`
              : "—"}
          </p>
          <p className="text-[11px] text-gray-500 dark:text-slate-400">
            Avg precip: {data.precipitation_avg_mm != null
              ? `${data.precipitation_avg_mm.toFixed(1)} mm`
              : "—"}
          </p>
        </>
      ) : (
        <p className="text-xs text-gray-400 dark:text-slate-500 mt-2">No data</p>
      )}
    </div>
  );
}

function SourcesTab({ detail }: { detail: CountryDetail }) {
  const sources = detail.sources || [];
  if (sources.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-8 text-center">
        <Shield className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
        <p className="text-sm text-gray-500 dark:text-slate-400">
          No source coverage recorded for {detail.country_name}.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 dark:bg-slate-800 text-xs uppercase text-gray-500 dark:text-slate-400">
          <tr>
            <th className="px-4 py-2 text-left">Source</th>
            <th className="px-4 py-2 text-right">Articles</th>
            <th className="px-4 py-2 text-right">Avg credibility</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
          {sources.map((s) => (
            <tr key={s.source_name}>
              <td className="px-4 py-2 text-gray-900 dark:text-slate-100">
                {s.source_name}
              </td>
              <td className="px-4 py-2 text-right text-gray-700 dark:text-slate-300">
                {s.article_count.toLocaleString()}
              </td>
              <td className="px-4 py-2 text-right">
                {s.avg_credibility != null
                  ? `${Math.round(s.avg_credibility)}/100`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClaimsTab({
  claims,
  countryName,
}: {
  claims: ClaimLedgerEntry[] | null;
  countryName: string;
}) {
  if (claims === null) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-teal-500" />
      </div>
    );
  }
  if (claims.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-8 text-center">
        <ScrollText className="w-8 h-8 text-gray-300 dark:text-slate-600 mx-auto mb-2" />
        <p className="text-sm text-gray-500 dark:text-slate-400">
          No verified claims yet for {countryName}.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 divide-y divide-gray-100 dark:divide-slate-800">
      {claims.map((c) => (
        <div key={c.claim_id} className="p-4">
          <p className="text-sm text-gray-900 dark:text-slate-100 mb-2">
            {c.claim_text}
          </p>
          <div className="flex items-center gap-2 text-[11px] text-gray-500 dark:text-slate-400">
            {c.verification_status && (
              <span
                className={`px-1.5 py-0.5 rounded uppercase text-[10px] ${
                  c.verification_status === "VERIFIED"
                    ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-200"
                    : c.verification_status === "DISPUTED"
                      ? "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-200"
                      : "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-200"
                }`}
              >
                {c.verification_status}
              </span>
            )}
            {c.confidence_score != null && (
              <span>Confidence: {Math.round(c.confidence_score * 100)}%</span>
            )}
            {c.article_id && (
              <Link
                href={`/articles/${c.article_id}`}
                className="text-teal-600 dark:text-teal-400 hover:underline"
              >
                View source article →
              </Link>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
