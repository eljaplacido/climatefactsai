/**
 * Plain-language interpretation helpers — Phase 2C (2026-05-23).
 *
 * The competitive UX audit's A4: every metric on the platform should have
 * a templated companion sentence that turns the number into a human
 * meaning. IQAir does this for AQI ("This means sensitive groups should
 * stay indoors"); Probable Futures does it for warming levels ("At 2°C,
 * heat days double").
 *
 * Our version is intentionally template-based (not LLM-generated): low
 * latency, deterministic, translatable, auditable. Every sentence shows
 * the SAME math the dashboard already shows — we just put it in words.
 *
 * Design rules:
 *   1. NEVER invent context the data doesn't have. "Helsinki's temperature
 *      is high" is wrong; "Helsinki is 2°C warmer than last year" is right.
 *   2. Always include the comparison reference (last year, baseline,
 *      sector average) — a number with no reference is meaningless.
 *   3. Lead with the WHAT, then the WHY MATTERS in the second clause.
 *   4. Keep it under ~20 words so it fits inside a KPI card.
 *
 * Each helper returns a `PlainLanguageResult` with optional severity
 * tone so the UI can colour-tone the sentence consistently with the
 * underlying chip/badge.
 */

export type PlainLanguageTone = "ok" | "warn" | "alert" | "neutral";

export interface PlainLanguageResult {
  /** The interpretation sentence, ready to render. */
  sentence: string;
  /** Optional UI tone hint paired with the value's severity. */
  tone: PlainLanguageTone;
}

const NULL_RESULT: PlainLanguageResult = { sentence: "", tone: "neutral" };


// ---------------------------------------------------------------------------
// Temperature anomaly — degrees Celsius vs a baseline period
// ---------------------------------------------------------------------------

export function formatTemperatureAnomalyPlain(
  anomalyC: number | null | undefined,
  context?: { locationName?: string; baselineLabel?: string },
): PlainLanguageResult {
  if (anomalyC === null || anomalyC === undefined || Number.isNaN(anomalyC)) {
    return NULL_RESULT;
  }
  const location = context?.locationName || "This location";
  const baseline = context?.baselineLabel || "the same month last year";
  const abs = Math.abs(anomalyC);
  const dir = anomalyC > 0 ? "warmer" : anomalyC < 0 ? "cooler" : "the same temperature as";

  let tone: PlainLanguageTone;
  if (abs < 0.5) tone = "ok";
  else if (abs < 1.5) tone = "warn";
  else tone = "alert";

  if (anomalyC === 0) {
    return {
      sentence: `${location} is the same temperature as ${baseline}.`,
      tone: "ok",
    };
  }

  // Severity narrative — context helps the reader feel WHY it matters.
  let severityNote = "";
  if (abs >= 2) {
    severityNote = " — an unusually large deviation";
  } else if (abs >= 1) {
    severityNote = " — above typical year-to-year variation";
  }

  return {
    sentence: `${location} is ${abs.toFixed(1)}°C ${dir} than ${baseline}${severityNote}.`,
    tone,
  };
}


// ---------------------------------------------------------------------------
// Credibility score — 0-100 scale, higher = better
// ---------------------------------------------------------------------------

export function formatCredibilityPlain(
  score: number | null | undefined,
  context?: { entity?: string; sampleSize?: number },
): PlainLanguageResult {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return NULL_RESULT;
  }
  const entity = context?.entity || "Sources here";
  const sampleHint =
    context?.sampleSize !== undefined
      ? ` (based on ${context.sampleSize} article${context.sampleSize === 1 ? "" : "s"})`
      : "";

  if (score >= 80) {
    return {
      sentence: `${entity} score in the highly-trusted band${sampleHint} — independently corroborated and methodology-transparent.`,
      tone: "ok",
    };
  }
  if (score >= 60) {
    return {
      sentence: `${entity} are generally reliable${sampleHint} — most claims hold up, but cross-check controversial ones.`,
      tone: "ok",
    };
  }
  if (score >= 40) {
    return {
      sentence: `${entity} show mixed reliability${sampleHint} — treat individual claims with caution and seek corroboration.`,
      tone: "warn",
    };
  }
  return {
    sentence: `${entity} score below the platform's reliability threshold${sampleHint} — claims here need independent verification.`,
    tone: "alert",
  };
}


// ---------------------------------------------------------------------------
// Climate risk score — 0-100 scale, higher = worse exposure
// ---------------------------------------------------------------------------

export function formatClimateRiskPlain(
  score: number | null | undefined,
  context?: { entity?: string },
): PlainLanguageResult {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return NULL_RESULT;
  }
  const entity = context?.entity || "This area";
  if (score >= 70) {
    return {
      sentence: `${entity} faces severe climate exposure — extreme events are likely in this decade without significant adaptation.`,
      tone: "alert",
    };
  }
  if (score >= 50) {
    return {
      sentence: `${entity} has high climate exposure — adaptation planning is overdue.`,
      tone: "alert",
    };
  }
  if (score >= 30) {
    return {
      sentence: `${entity} has moderate climate exposure — manageable with the planning currently underway.`,
      tone: "warn",
    };
  }
  return {
    sentence: `${entity} has low immediate climate exposure — focus on long-horizon adaptation.`,
    tone: "ok",
  };
}


// ---------------------------------------------------------------------------
// Article count — context-dependent (small = sparse coverage, large = good)
// ---------------------------------------------------------------------------

export function formatArticleCountPlain(
  count: number | null | undefined,
  context?: { entity?: string; periodLabel?: string },
): PlainLanguageResult {
  if (count === null || count === undefined || Number.isNaN(count)) {
    return NULL_RESULT;
  }
  const entity = context?.entity || "This country";
  const period = context?.periodLabel || "tracked";

  if (count === 0) {
    return {
      sentence: `${entity} has no articles ${period} yet — this is itself a coverage signal worth noting.`,
      tone: "alert",
    };
  }
  if (count < 10) {
    return {
      sentence: `${entity} has thin coverage (${count} article${count === 1 ? "" : "s"} ${period}) — claims here may not be triangulable.`,
      tone: "warn",
    };
  }
  if (count < 50) {
    return {
      sentence: `${entity} has modest coverage (${count} articles ${period}) — enough for trend reading but limited claim-level depth.`,
      tone: "warn",
    };
  }
  if (count < 200) {
    return {
      sentence: `${entity} has good coverage (${count} articles ${period}) — most major claims are triangulable.`,
      tone: "ok",
    };
  }
  return {
    sentence: `${entity} has extensive coverage (${count.toLocaleString()} articles ${period}) — deep claim-level depth available.`,
    tone: "ok",
  };
}


// ---------------------------------------------------------------------------
// Evidence strength for deep-search results
// ---------------------------------------------------------------------------

export function formatEvidenceStrengthPlain(
  internalCount: number | null | undefined,
  externalCount: number | null | undefined,
): PlainLanguageResult {
  const i = internalCount ?? 0;
  const e = externalCount ?? 0;
  const total = i + e;
  if (total === 0) {
    return {
      sentence: "No matching evidence found — the answer below is a deterministic explainer, not a synthesised finding.",
      tone: "alert",
    };
  }
  if (total < 3) {
    return {
      sentence: `Evidence is thin (${i} internal + ${e} external sources). Treat conclusions as low-confidence and refine scope before relying on them.`,
      tone: "warn",
    };
  }
  if (total < 8) {
    return {
      sentence: `Evidence is moderate (${i} internal + ${e} external sources). Main findings are corroborated but edge claims should be verified.`,
      tone: "warn",
    };
  }
  return {
    sentence: `Evidence is strong (${i} internal + ${e} external sources). Findings rest on cross-source corroboration.`,
    tone: "ok",
  };
}


// ---------------------------------------------------------------------------
// Phase 6 (2026-05-24) — Business-decision-maker persona framings
// ---------------------------------------------------------------------------
// Same underlying metrics; different translation. A board chair reading
// "Germany is 1.4°C warmer than last year" doesn't know what to DO with
// that — but "Germany faces material physical risk to fixed assets;
// review your operational footprint there" is actionable.
//
// The business-view helpers below take the SAME inputs as the consumer
// helpers and emit a parallel sentence tuned for a fiduciary audience.
// The Country Passport's view-mode toggle swaps between them.
//
// Compliance-framework chips (CSRD / IFRS S2 / TCFD / TNFD) flow through
// `getComplianceFrameworks()` — surface them on the KPI cards so a
// reader knows which regulatory regime the data point speaks to.
// ---------------------------------------------------------------------------


export function formatTemperatureAnomalyBusiness(
  anomalyC: number | null | undefined,
  context?: { locationName?: string },
): PlainLanguageResult {
  if (anomalyC === null || anomalyC === undefined || Number.isNaN(anomalyC)) {
    return NULL_RESULT;
  }
  const location = context?.locationName || "This location";
  const abs = Math.abs(anomalyC);

  if (abs < 0.5) {
    return {
      sentence: `${location} is operating within typical year-on-year variation — no near-term physical-risk action required.`,
      tone: "ok",
    };
  }
  if (abs < 1.5) {
    return {
      sentence: `${location} shows elevated thermal deviation — review heat-exposed assets and supplier dependencies as part of CSRD physical-risk disclosure.`,
      tone: "warn",
    };
  }
  return {
    sentence: `${location} faces material physical-risk signal — anomaly exceeds 1.5°C, which IFRS S2 flags as a disclosure trigger. Engage risk + sustainability teams.`,
    tone: "alert",
  };
}


export function formatCredibilityBusiness(
  score: number | null | undefined,
  context?: { entity?: string },
): PlainLanguageResult {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return NULL_RESULT;
  }
  const entity = context?.entity || "Sources here";
  if (score >= 80) {
    return {
      sentence: `${entity} meet audit-grade evidence standards — citations from this band are defensible in CSRD assurance review.`,
      tone: "ok",
    };
  }
  if (score >= 60) {
    return {
      sentence: `${entity} are corroboration-grade — usable for internal briefings, but cross-check before citing in disclosure filings.`,
      tone: "ok",
    };
  }
  if (score >= 40) {
    return {
      sentence: `${entity} carry reputational risk if cited externally — substantiate independently before any forward-looking statement.`,
      tone: "warn",
    };
  }
  return {
    sentence: `${entity} fall below the platform's evidence floor — do NOT use as substantiation for any public claim. Greenwashing exposure.`,
    tone: "alert",
  };
}


export function formatClimateRiskBusiness(
  score: number | null | undefined,
  context?: { entity?: string },
): PlainLanguageResult {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return NULL_RESULT;
  }
  const entity = context?.entity || "This area";
  if (score >= 70) {
    return {
      sentence: `${entity} carries severe physical-risk exposure — material to asset valuation; flag in board risk register; mandatory TCFD physical-risk disclosure trigger.`,
      tone: "alert",
    };
  }
  if (score >= 50) {
    return {
      sentence: `${entity} has high physical-risk exposure — scenario-model your operations there at 1.5°C and 2°C warming pathways.`,
      tone: "alert",
    };
  }
  if (score >= 30) {
    return {
      sentence: `${entity} has moderate physical-risk exposure — manageable, but review insurance coverage and supplier continuity plans.`,
      tone: "warn",
    };
  }
  return {
    sentence: `${entity} has low near-term physical-risk exposure — monitor as a 2030+ planning horizon rather than an immediate fiduciary concern.`,
    tone: "ok",
  };
}


export function formatArticleCountBusiness(
  count: number | null | undefined,
  context?: { entity?: string },
): PlainLanguageResult {
  if (count === null || count === undefined || Number.isNaN(count)) {
    return NULL_RESULT;
  }
  const entity = context?.entity || "This country";

  if (count === 0) {
    return {
      sentence: `${entity} has no tracked climate signal — diligence is constrained; commission a dedicated risk review before market commitments.`,
      tone: "alert",
    };
  }
  if (count < 10) {
    return {
      sentence: `${entity} has thin information coverage — sufficient for awareness but not for substantive due-diligence; treat conclusions as preliminary.`,
      tone: "warn",
    };
  }
  if (count < 50) {
    return {
      sentence: `${entity} has adequate information coverage for trend reading — supplement with primary research for specific transactions.`,
      tone: "warn",
    };
  }
  return {
    sentence: `${entity} has robust information coverage — sufficient for fiduciary due-diligence on most climate-related decisions.`,
    tone: "ok",
  };
}


// ---------------------------------------------------------------------------
// Compliance framework relevance — which regimes a given metric
// matters under. Used for the chip row on KPI cards in business view.
// ---------------------------------------------------------------------------

export type ComplianceFramework = "CSRD" | "IFRS S2" | "TCFD" | "TNFD" | "GHG Protocol";

export function getComplianceFrameworks(
  metric: "temperature_anomaly" | "credibility" | "climate_risk" | "article_count",
): ComplianceFramework[] {
  // Hardcoded mapping of which disclosure regimes care about each metric.
  // Not exhaustive — purely guidance for the business view. A separate
  // table-driven mapping is Phase 7 work if we ship the per-company view.
  switch (metric) {
    case "climate_risk":
      // Physical risk → all the climate-disclosure regimes
      return ["CSRD", "IFRS S2", "TCFD"];
    case "temperature_anomaly":
      // Temperature signal → physical risk regimes
      return ["CSRD", "IFRS S2", "TCFD"];
    case "credibility":
      // Source credibility → CSRD assurance + greenwashing regimes
      return ["CSRD", "IFRS S2"];
    case "article_count":
      // Coverage volume → CSRD diligence layer
      return ["CSRD"];
    default:
      return [];
  }
}


// ---------------------------------------------------------------------------
// Registry — useful for tests + future generic helper
// ---------------------------------------------------------------------------

export const PLAIN_LANGUAGE_FORMATTERS = {
  temperature_anomaly: formatTemperatureAnomalyPlain,
  credibility: formatCredibilityPlain,
  climate_risk: formatClimateRiskPlain,
  article_count: formatArticleCountPlain,
  evidence_strength: formatEvidenceStrengthPlain,
} as const;

export const BUSINESS_PLAIN_LANGUAGE_FORMATTERS = {
  temperature_anomaly: formatTemperatureAnomalyBusiness,
  credibility: formatCredibilityBusiness,
  climate_risk: formatClimateRiskBusiness,
  article_count: formatArticleCountBusiness,
} as const;

export type PlainLanguageMetric = keyof typeof PLAIN_LANGUAGE_FORMATTERS;
export type ViewMode = "public" | "business";
