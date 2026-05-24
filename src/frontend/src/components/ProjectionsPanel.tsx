"use client";

// Phase 8 MH4 (2026-05-24) — Country warming projections panel.
//
// Surfaces IPCC AR6 SSP-based warming projections (SSP1-2.6 / SSP2-4.5 /
// SSP3-7.0) at 2030 / 2050 / 2100 horizons for a single country. Backed by
// `GET /api/map/country/{cc}/projections` and migration 035.
//
// Three personas served:
//   - Consumer: "If we do nothing, my country is +N°C by 2050."
//   - Journalist: scenario comparison for explainer pieces.
//   - Business decision-maker: physical-risk planning horizon for IFRS S2
//     scenario analysis (1.5°C / 2°C / 3°C bracket).
//
// MVP scope: static seed data per country (20 countries seeded). No live
// regression refresh; downstream AR6 Atlas ingestion will overwrite the
// seed rows.

import { useEffect, useState } from "react";
import { Loader2, TrendingUp, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type ScenarioKey = "SSP1-2.6" | "SSP2-4.5" | "SSP3-7.0";

interface HorizonPoint {
  horizon_year: number;
  temp_anomaly_c: number;
}

interface ProjectionsPayload {
  country_code: string;
  scenarios: Record<ScenarioKey, HorizonPoint[]>;
  available: boolean;
  methodology_version: string | null;
  citation_url: string | null;
  baseline_note: string;
}

const SCENARIO_LABELS: Record<ScenarioKey, { short: string; long: string; tone: string }> = {
  "SSP1-2.6": {
    short: "Sustainability",
    long: "SSP1-2.6 — below 2°C pathway, strong mitigation",
    tone: "text-teal-700 bg-teal-50 border-teal-200",
  },
  "SSP2-4.5": {
    short: "Middle path",
    long: "SSP2-4.5 — middle-of-the-road emissions trajectory",
    tone: "text-amber-700 bg-amber-50 border-amber-200",
  },
  "SSP3-7.0": {
    short: "High emissions",
    long: "SSP3-7.0 — regional rivalry, high emissions, weak coordination",
    tone: "text-red-700 bg-red-50 border-red-200",
  },
};

const SCENARIO_ORDER: ScenarioKey[] = ["SSP1-2.6", "SSP2-4.5", "SSP3-7.0"];

interface ProjectionsPanelProps {
  countryCode: string;
  countryName: string;
}

export default function ProjectionsPanel({
  countryCode,
  countryName,
}: ProjectionsPanelProps) {
  const [data, setData] = useState<ProjectionsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeScenario, setActiveScenario] = useState<ScenarioKey>("SSP2-4.5");

  useEffect(() => {
    if (!countryCode) return;
    setLoading(true);
    fetch(`${API_BASE}/api/map/country/${countryCode}/projections`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [countryCode]);

  if (loading) {
    return (
      <div
        className="bg-white rounded-lg border border-gray-200 p-6 flex items-center gap-2 text-gray-500 text-sm"
        data-testid="projections-loading"
      >
        <Loader2 className="w-4 h-4 animate-spin" /> Loading projection scenarios…
      </div>
    );
  }

  if (!data || !data.available) {
    return (
      <div
        className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-500"
        data-testid="projections-unavailable"
      >
        IPCC AR6 scenario projections for {countryName} have not been ingested
        yet. The 20-country seed covers major emitters and climate-vulnerable
        nations; broader coverage follows from the full Atlas ingestion.
      </div>
    );
  }

  const activeData = data.scenarios[activeScenario] || [];

  return (
    <section
      className="bg-white rounded-lg border border-gray-200 p-5 space-y-4"
      data-testid="projections-panel"
    >
      <header className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-teal-600" />
            Warming projections — {countryName}
          </h3>
          <p className="text-xs text-gray-500 mt-1">{data.baseline_note}</p>
        </div>
      </header>

      {/* Scenario selector tabs */}
      <div
        className="flex gap-1.5"
        role="tablist"
        aria-label="Scenario selector"
        data-testid="projections-scenario-tabs"
      >
        {SCENARIO_ORDER.map((sc) => {
          const isActive = activeScenario === sc;
          const label = SCENARIO_LABELS[sc];
          return (
            <button
              key={sc}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveScenario(sc)}
              className={`flex-1 text-xs px-3 py-2 rounded border transition-colors ${
                isActive
                  ? label.tone + " font-semibold"
                  : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
              }`}
              data-testid={`projections-scenario-${sc}`}
            >
              <div className="font-mono text-[10px] uppercase tracking-wider">
                {sc}
              </div>
              <div className="mt-0.5">{label.short}</div>
            </button>
          );
        })}
      </div>

      {/* Scenario description */}
      <p
        className="text-xs text-gray-600 italic"
        data-testid="projections-scenario-description"
      >
        {SCENARIO_LABELS[activeScenario].long}
      </p>

      {/* Horizon cards */}
      <div
        className="grid grid-cols-3 gap-3"
        data-testid="projections-horizons"
      >
        {activeData.map((point) => {
          // Visual bar normalised against 7°C (worst-case Arctic ceiling)
          const barPct = Math.min(100, Math.round((point.temp_anomaly_c / 7) * 100));
          // Bar color matches the scenario tone — graded red intensity for the
          // worst scenario.
          const barColor =
            activeScenario === "SSP1-2.6"
              ? "bg-teal-500"
              : activeScenario === "SSP2-4.5"
              ? "bg-amber-500"
              : "bg-red-500";
          return (
            <div
              key={point.horizon_year}
              className="bg-gray-50 rounded-lg p-3 border border-gray-200"
              data-testid={`projections-horizon-${point.horizon_year}`}
            >
              <div className="text-[11px] uppercase tracking-wider text-gray-500">
                By {point.horizon_year}
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-1 font-mono">
                +{point.temp_anomaly_c.toFixed(1)}°C
              </div>
              <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${barColor} rounded-full transition-all`}
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Citation footer */}
      {data.citation_url && (
        <footer className="text-[11px] text-gray-500 border-t border-gray-100 pt-3">
          Source:{" "}
          <a
            href={data.citation_url}
            target="_blank"
            rel="noreferrer"
            className="text-teal-700 hover:underline inline-flex items-center gap-1"
          >
            IPCC AR6 Interactive Atlas
            <ExternalLink className="w-3 h-3" />
          </a>
          {data.methodology_version && (
            <span className="ml-2 font-mono">
              ({data.methodology_version})
            </span>
          )}
        </footer>
      )}
    </section>
  );
}
