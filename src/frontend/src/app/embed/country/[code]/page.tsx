import Link from "next/link";
import { notFound } from "next/navigation";
import {
  formatTemperatureAnomalyPlain,
  formatCredibilityPlain,
  formatClimateRiskPlain,
  formatArticleCountPlain,
  type PlainLanguageResult,
} from "@/lib/plainLanguage";

/**
 * Country KPI embed widget — Phase 2E (2026-05-23) MH6.
 *
 * Renders a minimal-layout single-country snapshot that newsrooms and
 * NGOs can iframe into their own pages. Strict design rules:
 *
 *   1. No global nav, no chat, no auth UI. The embed is a standalone
 *      pane that lives inside someone else's article.
 *   2. Watermark + back-link to climatefacts.ai/country/{code} are
 *      MANDATORY — the embed only travels with attribution.
 *   3. Server-rendered (Next.js RSC) so it loads instantly with no
 *      client JS — important for iframe perf budgets.
 *   4. Same KPIs as the full Passport header, same plain-language layer.
 *
 * Embed URL: `/embed/country/{ISO2}`
 * Iframe shape: `<iframe src="…/embed/country/DE" width="380" height="220" />`
 *
 * The host platform's CSP needs to allow `frame-src climatefacts.ai`
 * for the iframe to render. Documented at /methodology.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_INTERNAL_URL ||
  "http://localhost:5400";

interface CountryDetail {
  country_code: string;
  country_name: string;
  flag?: string;
  article_count: number;
  avg_credibility: number | null;
  climate_risk_score: number | null;
  weather?: {
    temperature_anomaly_c?: number | null;
  } | null;
}

async function fetchCountryDetail(code: string): Promise<CountryDetail | null> {
  try {
    const res = await fetch(`${API_BASE}/api/map/country/${code}/detail`, {
      // Cache aggressively — KPIs update at most a few times a day, and
      // every cache hit is one less server round-trip for the embed.
      next: { revalidate: 600 },
    });
    if (!res.ok) return null;
    return (await res.json()) as CountryDetail;
  } catch {
    return null;
  }
}

export const metadata = {
  // Robots-noindex the embed pages — the canonical content lives at
  // /country/[code]. This avoids dupe-content penalties.
  robots: { index: false, follow: true },
};

export default async function CountryEmbedPage({
  params,
}: {
  params: { code: string };
}) {
  const code = (params.code || "").toUpperCase();
  if (!code || code.length !== 2) return notFound();

  const detail = await fetchCountryDetail(code);
  if (!detail) {
    return (
      <div
        className="bg-white text-slate-900 p-3 text-sm"
        data-testid="country-embed-error"
      >
        Could not load {code}.{" "}
        <a
          href={`https://climatefacts.ai/country/${code}`}
          target="_top"
          rel="noopener noreferrer"
          className="text-teal-700 underline"
        >
          Open on climatefacts.ai →
        </a>
      </div>
    );
  }

  const tempPlain = formatTemperatureAnomalyPlain(
    detail.weather?.temperature_anomaly_c,
    {
      locationName: detail.country_name,
      baselineLabel: "the same month last year",
    },
  );
  const credPlain = formatCredibilityPlain(detail.avg_credibility, {
    entity: `${detail.country_name}'s sources`,
    sampleSize: detail.article_count,
  });
  const riskPlain = formatClimateRiskPlain(detail.climate_risk_score, {
    entity: detail.country_name,
  });
  const articlesPlain = formatArticleCountPlain(detail.article_count, {
    entity: detail.country_name,
    periodLabel: "in our verified corpus",
  });

  // Pick the single most-newsworthy plain-language sentence as the
  // headline — climate risk > temperature anomaly > article count > credibility.
  // Newsrooms embedding this want the one signal that's worth a click.
  const headlinePlain: PlainLanguageResult =
    (riskPlain.tone === "alert" && riskPlain) ||
    (tempPlain.tone === "alert" && tempPlain) ||
    (tempPlain.tone === "warn" && tempPlain) ||
    (articlesPlain.tone === "alert" && articlesPlain) ||
    credPlain;

  return (
    <main
      className="min-h-screen bg-white text-slate-900 font-sans p-4 max-w-md mx-auto"
      data-testid="country-embed-root"
    >
      {/* Header — flag, country name, attribution */}
      <header className="flex items-start justify-between gap-3 mb-3 pb-2 border-b border-gray-100">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-3xl" aria-hidden="true">
            {detail.flag || "\u{1F30D}"}
          </span>
          <div className="min-w-0">
            <h1
              className="text-base font-bold text-slate-900 truncate"
              data-testid="country-embed-title"
            >
              {detail.country_name}
            </h1>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Climate snapshot
            </p>
          </div>
        </div>
        <Link
          href={`/country/${code}`}
          target="_top"
          className="text-[10px] text-teal-700 hover:underline whitespace-nowrap"
          data-testid="country-embed-deeplink"
        >
          Full passport →
        </Link>
      </header>

      {/* Headline plain-language sentence — the editorial hook */}
      {headlinePlain.sentence && (
        <p
          className={`text-sm leading-snug mb-3 ${
            headlinePlain.tone === "alert"
              ? "text-red-700 font-medium"
              : headlinePlain.tone === "warn"
                ? "text-amber-700"
                : "text-slate-700"
          }`}
          data-testid="country-embed-headline"
        >
          {headlinePlain.sentence}
        </p>
      )}

      {/* 4-up KPI mini-grid */}
      <div className="grid grid-cols-4 gap-1.5 mb-3">
        <EmbedKpi
          label="Articles"
          value={detail.article_count.toLocaleString()}
          testId="embed-kpi-articles"
        />
        <EmbedKpi
          label="Credibility"
          value={
            detail.avg_credibility != null
              ? `${Math.round(detail.avg_credibility)}`
              : "—"
          }
          suffix={detail.avg_credibility != null ? "/100" : ""}
          tone={credPlain.tone}
          testId="embed-kpi-credibility"
        />
        <EmbedKpi
          label="Risk"
          value={
            detail.climate_risk_score != null
              ? `${Math.round(detail.climate_risk_score)}`
              : "—"
          }
          suffix={detail.climate_risk_score != null ? "/100" : ""}
          tone={riskPlain.tone}
          testId="embed-kpi-risk"
        />
        <EmbedKpi
          label="Temp"
          value={
            detail.weather?.temperature_anomaly_c != null
              ? `${detail.weather.temperature_anomaly_c > 0 ? "+" : ""}${detail.weather.temperature_anomaly_c}°`
              : "—"
          }
          tone={tempPlain.tone}
          testId="embed-kpi-temp"
        />
      </div>

      {/* Watermark — non-negotiable. Removing this breaks attribution. */}
      <footer
        className="flex items-center justify-between pt-2 border-t border-gray-100 text-[10px] text-slate-500"
        data-testid="country-embed-watermark"
      >
        <span>
          Source:{" "}
          <a
            href="https://climatefacts.ai"
            target="_top"
            rel="noopener noreferrer"
            className="text-teal-700 hover:underline font-medium"
          >
            Climatefacts.ai
          </a>
        </span>
        <span>Updated: {new Date().toISOString().slice(0, 10)}</span>
      </footer>
    </main>
  );
}

function EmbedKpi({
  label,
  value,
  suffix = "",
  tone = "neutral",
  testId,
}: {
  label: string;
  value: string;
  suffix?: string;
  tone?: "ok" | "warn" | "alert" | "neutral";
  testId?: string;
}) {
  const toneClass =
    tone === "alert"
      ? "text-red-700"
      : tone === "warn"
        ? "text-amber-700"
        : tone === "ok"
          ? "text-emerald-700"
          : "text-slate-900";
  return (
    <div className="bg-gray-50 rounded p-1.5 text-center" data-testid={testId}>
      <p className="text-[9px] uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className={`text-base font-bold leading-tight mt-0.5 ${toneClass}`}>
        {value}
        {suffix && (
          <span className="text-[10px] opacity-60 ml-0.5">{suffix}</span>
        )}
      </p>
    </div>
  );
}
