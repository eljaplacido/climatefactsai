"use client";

// Country biome + climate-effects summary — Phase 9 (2026-05-25).
//
// Rendered on the Country Passport Overview tab. Reads
// GET /api/map/country/{cc}/biome and surfaces:
//   - A 2-3 sentence biome-characterisation prose block
//   - Bulleted climate-change effects (4-6 per country)
//   - Key facts (per-capita CO2, renewable share, net-zero year)
//   - Drill-down suggestion chips that the user can click to ask
//     the chat assistant
//
// When the country has no curated narrative, renders a soft empty state
// with a generic chat CTA so the user is never staring at a blank panel.

import { useEffect, useState } from "react";
import { Leaf, AlertTriangle, MessageCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface BiomeSymbol {
  biome_id: string;
  biome_label: string;
  biome_emoji: string;
  koppen_id: string;
  koppen_label: string;
  koppen_color: string;
}

export interface BiomePayload {
  country_code: string;
  available: boolean;
  biome_summary: string;
  climate_effects: string[];
  key_facts: string[];
  drill_down_suggestions: string[];
  // Phase 11 (2026-05-25) — visual biome symbol from biome_map
  biome_symbol?: BiomeSymbol;
}

interface Props {
  countryCode: string;
  countryName: string;
  onAskAssistant?: (question: string) => void;
}

export default function CountryBiomeSummary({
  countryCode, countryName, onAskAssistant,
}: Props) {
  const [data, setData] = useState<BiomePayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!countryCode) return;
    setLoading(true);
    fetch(`${API_BASE}/api/map/country/${countryCode}/biome`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [countryCode]);

  if (loading) {
    return (
      <div
        className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5 animate-pulse"
        data-testid="biome-loading"
      >
        <div className="h-4 w-1/3 bg-gray-200 dark:bg-slate-700 rounded mb-3" />
        <div className="h-3 w-full bg-gray-200 dark:bg-slate-700 rounded mb-1.5" />
        <div className="h-3 w-2/3 bg-gray-200 dark:bg-slate-700 rounded" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <section
      className="bg-white dark:bg-slate-900 rounded-lg border border-gray-200 dark:border-slate-700 p-5 space-y-4"
      data-testid="biome-summary"
      aria-labelledby="biome-heading"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 min-w-0">
          <Leaf className="w-5 h-5 text-teal-600 mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <h3
              id="biome-heading"
              className="text-base font-semibold text-gray-900 dark:text-slate-50"
            >
              {countryName} — biome + climate context
            </h3>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
              {data.available
                ? "Curated narrative + drill-down chat hooks"
                : "Generic summary — ask the assistant for country-specific detail"}
            </p>
          </div>
        </div>

        {/* Phase 11 (2026-05-25) — visual biome + climate-zone symbol.
            Mirrors what the world map renders for this country. */}
        {data.biome_symbol && data.biome_symbol.biome_id !== "unclassified" && (
          <div
            className="flex-shrink-0 flex flex-col items-center gap-1"
            data-testid="biome-symbol-badge"
            title={`${data.biome_symbol.biome_label} / ${data.biome_symbol.koppen_label}`}
          >
            <span
              className="text-2xl leading-none"
              aria-label={data.biome_symbol.biome_label}
            >
              {data.biome_symbol.biome_emoji}
            </span>
            <span
              className="text-[10px] font-semibold px-1.5 py-0.5 rounded text-white whitespace-nowrap"
              style={{ backgroundColor: data.biome_symbol.koppen_color }}
            >
              {data.biome_symbol.koppen_label}
            </span>
          </div>
        )}
      </header>

      <p
        className="text-sm text-gray-800 dark:text-slate-200 leading-relaxed"
        data-testid="biome-summary-prose"
      >
        {data.biome_summary}
      </p>

      {data.climate_effects.length > 0 && (
        <div data-testid="biome-effects">
          <div className="flex items-center gap-1.5 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <h4 className="text-xs uppercase tracking-wider text-gray-700 dark:text-slate-300 font-semibold">
              Observed climate effects
            </h4>
          </div>
          <ul className="space-y-1.5 text-sm text-gray-800 dark:text-slate-200">
            {data.climate_effects.map((effect, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-amber-600 mt-1.5 flex-shrink-0">•</span>
                <span className="leading-snug">{effect}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.key_facts.length > 0 && (
        <div data-testid="biome-key-facts">
          <h4 className="text-xs uppercase tracking-wider text-gray-700 dark:text-slate-300 font-semibold mb-2">
            Key facts
          </h4>
          <ul className="space-y-1 text-sm text-gray-700 dark:text-slate-300">
            {data.key_facts.map((fact, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-teal-600 mt-1.5 flex-shrink-0">›</span>
                <span className="leading-snug">{fact}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.drill_down_suggestions.length > 0 && (
        <div
          className="pt-3 border-t border-gray-100 dark:border-slate-800"
          data-testid="biome-drilldown"
        >
          <div className="flex items-center gap-1.5 mb-2">
            <MessageCircle className="w-4 h-4 text-teal-600" />
            <h4 className="text-xs uppercase tracking-wider text-gray-700 dark:text-slate-300 font-semibold">
              Ask the assistant
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.drill_down_suggestions.map((q, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onAskAssistant?.(q)}
                className="text-xs px-3 py-1.5 bg-teal-50 dark:bg-teal-900/30 hover:bg-teal-100 dark:hover:bg-teal-900/50 text-teal-800 dark:text-teal-200 rounded-full border border-teal-200 dark:border-teal-800 transition-colors text-left"
                data-testid={`biome-drilldown-chip-${i}`}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
