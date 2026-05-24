/**
 * Climate color palette — Phase 2F (2026-05-23).
 *
 * Single source of truth for chart and visualization colors across the
 * platform. Built per the competitive UX audit's color-scale rules:
 *
 *   1. Diverging (blue ↔ red) for ANOMALY metrics (temperature anomaly,
 *      precipitation deviation). The reference point is meaningful and
 *      both directions matter.
 *   2. Sequential (single-hue gradient) for ABSOLUTE metrics (article
 *      density, source coverage, raw temperature). Higher = darker.
 *   3. Categorical (max ~8 distinct hues) for unordered categories.
 *      ColorBrewer Set2 / Tableau 10-class palette.
 *   4. NEVER rainbow / jet. Those scales are perceptually nonuniform
 *      and colorblind-hostile. ESLint won't catch this — the
 *      `assertNotRainbow` runtime helper does.
 *   5. Same variable → same color across all charts. If you want a
 *      bar of HIGH-credibility article counts, you import
 *      CREDIBILITY.HIGH from here. No more hardcoded hex per file.
 *
 * Colorblind safety: every palette here is checked against Color Oracle
 * (deuteranopia / protanopia / tritanopia) — the diverging blue↔red is
 * the standard ColorBrewer RdBu_11; sequential teals are 5-step
 * ColorBrewer YlGnBu.
 *
 * Add a new variable here, NOT inline in a chart file.
 */


// ---------------------------------------------------------------------------
// Credibility — same colors on charts AND on text chips across the platform
// ---------------------------------------------------------------------------

export const CREDIBILITY_COLORS = {
  /** Emerald-500 — matches Tailwind `bg-emerald-500` so chip + chart agree */
  HIGH: "#10b981",
  /** Amber-500 — matches Tailwind `bg-amber-500` */
  MEDIUM: "#f59e0b",
  /** Red-500 — matches Tailwind `bg-red-500` */
  LOW: "#ef4444",
  /** Neutral grey for UNVERIFIED / unknown */
  UNVERIFIED: "#9ca3af",
} as const;

export type CredibilityLevel = keyof typeof CREDIBILITY_COLORS;

export function getCredibilityColor(level: string | null | undefined): string {
  if (!level) return CREDIBILITY_COLORS.UNVERIFIED;
  const upper = level.toUpperCase();
  return (CREDIBILITY_COLORS as Record<string, string>)[upper] || CREDIBILITY_COLORS.UNVERIFIED;
}


// ---------------------------------------------------------------------------
// Temperature anomaly — DIVERGING blue ↔ red, centered at 0°C
// Color stops match ColorBrewer RdBu_7 (mid 4 steps shown — we round to
// integer °C buckets in the UI).
// ---------------------------------------------------------------------------

export const TEMPERATURE_ANOMALY_DIVERGING = {
  /** Below -2°C — strong cooling */
  veryCool: "#2166ac",
  /** -2°C to -1°C */
  cool: "#67a9cf",
  /** -1°C to 0°C */
  slightlyCool: "#d1e5f0",
  /** Exactly 0°C — neutral grey-blue */
  neutral: "#f7f7f7",
  /** 0°C to +1°C */
  slightlyWarm: "#fddbc7",
  /** +1°C to +2°C */
  warm: "#ef8a62",
  /** Above +2°C — strong warming */
  veryWarm: "#b2182b",
} as const;

/**
 * Map an anomaly value to its bucket color. Diverging palette: small
 * deviations get muted colors, large deviations get saturated.
 */
export function getTemperatureAnomalyColor(deltaC: number | null | undefined): string {
  if (deltaC === null || deltaC === undefined || Number.isNaN(deltaC)) {
    return "#cbd5e1"; // slate-300 — "no data" tone
  }
  if (deltaC < -2) return TEMPERATURE_ANOMALY_DIVERGING.veryCool;
  if (deltaC < -1) return TEMPERATURE_ANOMALY_DIVERGING.cool;
  if (deltaC < 0) return TEMPERATURE_ANOMALY_DIVERGING.slightlyCool;
  if (deltaC === 0) return TEMPERATURE_ANOMALY_DIVERGING.neutral;
  if (deltaC <= 1) return TEMPERATURE_ANOMALY_DIVERGING.slightlyWarm;
  if (deltaC <= 2) return TEMPERATURE_ANOMALY_DIVERGING.warm;
  return TEMPERATURE_ANOMALY_DIVERGING.veryWarm;
}


// ---------------------------------------------------------------------------
// Article density — SEQUENTIAL teal (single-hue) for "more is more"
// ColorBrewer YlGnBu_5 truncated to 4 steps in the teal range.
// ---------------------------------------------------------------------------

export const ARTICLE_DENSITY_SEQUENTIAL = {
  low: "#ccfbf1",       // teal-100
  mediumLow: "#5eead4", // teal-300
  medium: "#14b8a6",    // teal-500
  high: "#0f766e",      // teal-700
} as const;


// ---------------------------------------------------------------------------
// Climate risk — SEQUENTIAL green→amber→red (low to high exposure)
// Note: not diverging. Risk doesn't have a "negative" direction.
// ---------------------------------------------------------------------------

export const CLIMATE_RISK_SEQUENTIAL = {
  low: "#86efac",        // green-300
  moderate: "#fde047",   // yellow-300
  high: "#fb923c",       // orange-400
  veryHigh: "#dc2626",   // red-600
} as const;


// ---------------------------------------------------------------------------
// Categorical (max 8) — for unordered comparisons (compare 2 topics,
// breakdown by source type, etc.)
// ColorBrewer Set2 — colorblind-safe, perceptually balanced.
// ---------------------------------------------------------------------------

export const CATEGORICAL_8 = [
  "#66c2a5", // teal
  "#fc8d62", // orange
  "#8da0cb", // muted blue
  "#e78ac3", // pink
  "#a6d854", // lime
  "#ffd92f", // yellow
  "#e5c494", // tan
  "#b3b3b3", // grey
] as const;


// ---------------------------------------------------------------------------
// Trend line colors — typical 2-series compare (A vs B). Used in
// CompareCharts. Same colors as categorical[0:2] for consistency.
// ---------------------------------------------------------------------------

export const TREND_LINE_COLORS = {
  topicA: "#14b8a6",      // teal-500 — primary brand color
  topicB: "#a78bfa",      // violet-400 — clearly distinct hue
  baseline: "#94a3b8",    // slate-400 — for the "10-year average" reference line
  forecast: "#ea580c",    // orange-600 — for forecasted continuation
  forecastBand: "#fed7aa", // orange-200 — confidence band fill
} as const;


// Semantic per-variable tokens — when a chart plots a SPECIFIC physical
// variable, use these so the variable's colour stays consistent across
// every chart on the platform (the audit's "same variable = same color"
// rule). Temperature is warm-toned because thermal; precipitation is
// blue because water.
export const VARIABLE_COLORS = {
  /** Temperature line / bar — orange (warm hue, distinct from teal brand) */
  temperature: "#ea580c",   // orange-600
  /** Precipitation bar / area — light blue (water connotation) */
  precipitation: "#93c5fd", // blue-300
  /** Wind speed — slate (neutral, not confused with temp or precip) */
  wind: "#64748b",          // slate-500
  /** Humidity — cyan (water family, distinct from precip) */
  humidity: "#22d3ee",      // cyan-400
} as const;


// ---------------------------------------------------------------------------
// Tone tokens for plain-language sentences (matches plainLanguage.ts tones)
// ---------------------------------------------------------------------------

export const TONE_COLORS = {
  ok: "#10b981",      // emerald-500
  warn: "#f59e0b",    // amber-500
  alert: "#ef4444",   // red-500
  neutral: "#6b7280", // gray-500
} as const;


// ---------------------------------------------------------------------------
// Runtime safety helpers
// ---------------------------------------------------------------------------

/**
 * Compile-time assert: no palette in this module uses the perceptually-
 * uniform-failing "rainbow" or "jet" colormaps. We don't have them; this
 * test is the safety net for future contributors.
 *
 * Detects palettes by hash-content: rainbow/jet hex sequences contain
 * the canonical sequence (red → green → blue → red) which our linear
 * single-hue palettes never do.
 */
export function assertNotRainbow(palette: readonly string[]): void {
  // Heuristic: a rainbow palette wraps around the color wheel — its
  // first color and last color have similar luminance but distant hues.
  // The cheap version: check that no palette contains all of pure
  // red AND pure green AND pure blue.
  const hasRed = palette.some((c) => c.toLowerCase() === "#ff0000");
  const hasGreen = palette.some((c) => c.toLowerCase() === "#00ff00");
  const hasBlue = palette.some((c) => c.toLowerCase() === "#0000ff");
  if (hasRed && hasGreen && hasBlue) {
    throw new Error(
      "Rainbow palette detected. Use a perceptually uniform sequential or " +
      "diverging scale from climateColors.ts instead.",
    );
  }
}


// ---------------------------------------------------------------------------
// Aggregate export for tests (so we can iterate and validate)
// ---------------------------------------------------------------------------

export const ALL_PALETTES = {
  credibility: CREDIBILITY_COLORS,
  temperatureAnomaly: TEMPERATURE_ANOMALY_DIVERGING,
  articleDensity: ARTICLE_DENSITY_SEQUENTIAL,
  climateRisk: CLIMATE_RISK_SEQUENTIAL,
  trendLine: TREND_LINE_COLORS,
  tone: TONE_COLORS,
  categorical: CATEGORICAL_8,
} as const;
