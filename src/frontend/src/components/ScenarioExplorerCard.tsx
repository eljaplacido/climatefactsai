"use client";

import { useState } from "react";
import {
  Thermometer, Calendar, Loader2, AlertCircle, Info,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Polish wave 2 (2026-05-26, deferred audit item #14 UI) — interactive
// scenario explorer that calls GET /api/scenario/country/{cc}. The
// underlying endpoint is IPCC AR6 SSP interpolation (NOT a model
// simulation); the disclaimer is preserved in the response and
// re-rendered verbatim so the user understands the limitation.

interface ScenarioResponse {
  country_code: string;
  horizon_year: number;
  target_warming_c: number;
  interpolated_anomaly_c: number;
  method: string;
  bracketing_scenarios: { scenario: string; temp_anomaly_c: number }[];
  available_scenarios: { scenario: string; temp_anomaly_c: number }[];
  methodology: string;
  disclaimer: string;
}

interface Props {
  countryCode: string;
  countryName: string;
}

const HORIZONS = [2030, 2050, 2100] as const;

export default function ScenarioExplorerCard({ countryCode, countryName }: Props) {
  const [targetWarming, setTargetWarming] = useState(2.5);
  const [horizon, setHorizon] = useState<2030 | 2050 | 2100>(2050);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function explore() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(
        `${API_URL}/api/scenario/country/${countryCode}?target_warming_c=${targetWarming}&horizon_year=${horizon}`
      );
      if (resp.status === 404) {
        setError(
          `No IPCC AR6 projections stored for ${countryName}. Currently the platform covers ~20 countries — see the Projections tab for full coverage.`
        );
        return;
      }
      if (!resp.ok) {
        setError(`Scenario lookup failed (HTTP ${resp.status})`);
        return;
      }
      setResult(await resp.json());
    } catch (e: any) {
      setError(e?.message || "Network error");
    } finally {
      setLoading(false);
    }
  }

  const methodLabel: Record<string, { label: string; color: string }> = {
    exact: { label: "Exact SSP match", color: "bg-green-100 text-green-800" },
    interpolated: { label: "Interpolated between SSPs", color: "bg-blue-100 text-blue-800" },
    extrapolated_below: { label: "Below lowest SSP (clamped)", color: "bg-amber-100 text-amber-800" },
    extrapolated_above: { label: "Above highest SSP (clamped)", color: "bg-amber-100 text-amber-800" },
  };

  return (
    <section
      className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-5 shadow-sm space-y-4"
      data-testid="scenario-explorer-card"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100 flex items-center gap-2">
            <Thermometer className="h-4 w-4 text-orange-500" />
            Warming scenario explorer
          </h3>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
            Interpolates IPCC AR6 SSP scenarios for {countryName} at a target warming level.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-600 dark:text-slate-400 block mb-1">
            Target warming (°C above pre-industrial)
          </label>
          <input
            type="range"
            min={0.5}
            max={4.5}
            step={0.1}
            value={targetWarming}
            onChange={(e) => setTargetWarming(parseFloat(e.target.value))}
            className="w-full accent-orange-500"
            data-testid="scenario-warming-slider"
          />
          <p className="text-xl font-bold text-orange-600 mt-1 text-center">
            +{targetWarming.toFixed(1)}°C
          </p>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 dark:text-slate-400 block mb-1">
            Horizon year
          </label>
          <div className="flex gap-1.5">
            {HORIZONS.map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setHorizon(h)}
                className={`flex-1 px-3 py-2 text-sm rounded transition-colors ${
                  horizon === h
                    ? "bg-teal-600 text-white"
                    : "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-300 hover:bg-gray-200"
                }`}
                data-testid={`scenario-horizon-${h}`}
              >
                {h}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-gray-500 mt-1 flex items-center gap-1">
            <Calendar className="h-3 w-3" /> IPCC standard horizons
          </p>
        </div>

        <div className="flex items-end">
          <button
            type="button"
            onClick={explore}
            disabled={loading}
            className="w-full py-2 bg-teal-600 text-white rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50 flex items-center justify-center gap-1.5"
            data-testid="scenario-explore-btn"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Thermometer className="h-4 w-4" />
            )}
            Explore
          </button>
        </div>
      </div>

      {error && (
        <div
          className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 p-3 rounded flex items-start gap-2"
          role="alert"
        >
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {result && (
        <div className="border-t border-gray-100 dark:border-slate-700 pt-4 space-y-3">
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="text-3xl font-bold text-orange-600">
              +{result.interpolated_anomaly_c.toFixed(2)}°C
            </span>
            <span className="text-sm text-gray-600 dark:text-slate-400">
              for {countryName} at {result.horizon_year}
            </span>
            <span
              className={`px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide rounded ${methodLabel[result.method]?.color || "bg-gray-100 text-gray-800"}`}
              data-testid="scenario-method-badge"
            >
              {methodLabel[result.method]?.label || result.method}
            </span>
          </div>

          {result.bracketing_scenarios.length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              {result.bracketing_scenarios.map((b) => (
                <div
                  key={b.scenario}
                  className="bg-gray-50 dark:bg-slate-800 rounded p-3 text-xs"
                >
                  <div className="font-mono font-semibold text-gray-700 dark:text-slate-300">
                    {b.scenario}
                  </div>
                  <div className="text-orange-600 font-bold text-base mt-0.5">
                    +{b.temp_anomaly_c.toFixed(2)}°C
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded p-3 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2">
            <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
            <span>{result.disclaimer}</span>
          </div>
        </div>
      )}
    </section>
  );
}
