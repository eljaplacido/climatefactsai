"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ForecastComparison } from "@/types";
import { ArrowLeft, CloudSun, Loader2, Thermometer, Droplets, Wind, AlertTriangle, CheckCircle2 } from "lucide-react";
import ForecastChart from "@/components/ForecastChart";

const COUNTRIES = [
  { code: "FI", name: "Finland" }, { code: "SE", name: "Sweden" },
  { code: "NO", name: "Norway" }, { code: "DK", name: "Denmark" },
  { code: "DE", name: "Germany" }, { code: "FR", name: "France" },
  { code: "NL", name: "Netherlands" }, { code: "ES", name: "Spain" },
  { code: "IT", name: "Italy" }, { code: "PT", name: "Portugal" },
  { code: "PL", name: "Poland" }, { code: "GB", name: "United Kingdom" },
  { code: "IE", name: "Ireland" }, { code: "AT", name: "Austria" },
  { code: "BE", name: "Belgium" }, { code: "CZ", name: "Czechia" },
  { code: "EE", name: "Estonia" }, { code: "LV", name: "Latvia" },
  { code: "LT", name: "Lithuania" }, { code: "GR", name: "Greece" },
  { code: "HU", name: "Hungary" }, { code: "RO", name: "Romania" },
  { code: "BG", name: "Bulgaria" }, { code: "HR", name: "Croatia" },
  { code: "SK", name: "Slovakia" }, { code: "SI", name: "Slovenia" },
];

function DiscrepancyBadge({ score }: { score: number }) {
  if (score < 0.15) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="h-3 w-3" />
        High agreement
      </span>
    );
  }
  if (score < 0.35) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
        Minor differences
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
      <AlertTriangle className="h-3 w-3" />
      Significant discrepancies
    </span>
  );
}

export default function ForecastsPage() {
  const [selectedCountry, setSelectedCountry] = useState("FI");
  const [forecast, setForecast] = useState<ForecastComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchForecast(selectedCountry);
  }, [selectedCountry]);

  async function fetchForecast(cc: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getForecasts(cc);
      setForecast(data);
    } catch (err) {
      console.error("Failed to fetch forecast:", err);
      setError("Could not load forecast. The backend may be unavailable.");
      setForecast(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-300 dark:text-slate-300">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="flex items-center gap-2">
              <CloudSun className="h-5 w-5 text-clilens-primary dark:text-teal-400" />
              <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">
                Climate Forecast Comparison
              </h1>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Country selector */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
            Select Country
          </label>
          <select
            value={selectedCountry}
            onChange={(e) => setSelectedCountry(e.target.value)}
            className="px-4 py-2.5 border border-gray-300 dark:border-slate-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent w-64"
          >
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-clilens-primary dark:text-teal-400" />
          </div>
        ) : error ? (
          <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-200 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        ) : forecast ? (
          <div className="space-y-6">
            {/* Summary card */}
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-900 dark:text-slate-100">
                    {forecast.country_name}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-slate-400">{forecast.date_range}</p>
                </div>
                <DiscrepancyBadge score={forecast.discrepancy_score} />
              </div>
              <p className="text-sm text-gray-600 dark:text-slate-400 mb-4">{forecast.consensus_summary}</p>

              {/* Confidence bar */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500 dark:text-slate-400">Composite confidence:</span>
                <div className="flex-1 max-w-xs bg-gray-200 dark:bg-slate-700 rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-clilens-primary transition-all duration-500"
                    style={{ width: `${((forecast as any).composite_confidence || 0.5) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-semibold text-gray-700 dark:text-slate-300">
                  {Math.round(((forecast as any).composite_confidence || 0.5) * 100)}%
                </span>
              </div>
            </div>

            {/* Source comparison cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {forecast.sources.map((src) => (
                <div
                  key={src.source_name}
                  className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-gray-900 dark:text-slate-100">{src.source_name}</h3>
                    <span className="text-xs text-gray-400 dark:text-slate-500">
                      Confidence: {Math.round(src.confidence * 100)}%
                    </span>
                  </div>

                  <div className="space-y-3">
                    {src.temperature_avg != null && (
                      <div className="flex items-center gap-3">
                        <Thermometer className="h-4 w-4 text-red-400" />
                        <span className="text-sm text-gray-600 dark:text-slate-400">Temperature</span>
                        <span className="ml-auto text-sm font-semibold text-gray-900 dark:text-slate-100">
                          {src.temperature_avg}&deg;C
                        </span>
                      </div>
                    )}

                    {src.precipitation_mm != null && (
                      <div className="flex items-center gap-3">
                        <Droplets className="h-4 w-4 text-blue-400" />
                        <span className="text-sm text-gray-600 dark:text-slate-400">Precipitation</span>
                        <span className="ml-auto text-sm font-semibold text-gray-900 dark:text-slate-100">
                          {src.precipitation_mm} mm
                        </span>
                      </div>
                    )}

                    {src.wind_speed_ms != null && (
                      <div className="flex items-center gap-3">
                        <Wind className="h-4 w-4 text-cyan-400" />
                        <span className="text-sm text-gray-600 dark:text-slate-400">Wind Speed</span>
                        <span className="ml-auto text-sm font-semibold text-gray-900 dark:text-slate-100">
                          {src.wind_speed_ms} m/s
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Confidence indicator bar */}
                  <div className="mt-4 pt-3 border-t border-gray-100 dark:border-slate-800">
                    <div className="w-full bg-gray-100 dark:bg-slate-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full transition-all duration-500 ${
                          src.confidence >= 0.8
                            ? "bg-emerald-500"
                            : src.confidence >= 0.5
                            ? "bg-amber-500"
                            : "bg-red-400"
                        }`}
                        style={{ width: `${src.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Cross-source comparison table */}
            {forecast.sources.length >= 2 && (
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 shadow-sm overflow-x-auto">
                <h3 className="text-sm font-bold text-gray-900 dark:text-slate-100 mb-4">
                  Side-by-Side Comparison
                </h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-slate-700">
                      <th className="text-left py-2 pr-4 text-gray-500 dark:text-slate-400 font-medium">Metric</th>
                      {forecast.sources.map((s) => (
                        <th key={s.source_name} className="text-right py-2 px-3 text-gray-500 dark:text-slate-400 font-medium">
                          {s.source_name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-gray-100 dark:border-slate-800">
                      <td className="py-2 pr-4 text-gray-600 dark:text-slate-400">Temperature (&deg;C)</td>
                      {forecast.sources.map((s) => (
                        <td key={s.source_name} className="text-right py-2 px-3 font-medium text-gray-900 dark:text-slate-100">
                          {s.temperature_avg != null ? `${s.temperature_avg}` : "—"}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-gray-100 dark:border-slate-800">
                      <td className="py-2 pr-4 text-gray-600 dark:text-slate-400">Precipitation (mm)</td>
                      {forecast.sources.map((s) => (
                        <td key={s.source_name} className="text-right py-2 px-3 font-medium text-gray-900 dark:text-slate-100">
                          {s.precipitation_mm != null ? `${s.precipitation_mm}` : "—"}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-gray-100 dark:border-slate-800">
                      <td className="py-2 pr-4 text-gray-600 dark:text-slate-400">Wind (m/s)</td>
                      {forecast.sources.map((s) => (
                        <td key={s.source_name} className="text-right py-2 px-3 font-medium text-gray-900 dark:text-slate-100">
                          {s.wind_speed_ms != null ? `${s.wind_speed_ms}` : "—"}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 text-gray-600 dark:text-slate-400">Confidence</td>
                      {forecast.sources.map((s) => (
                        <td key={s.source_name} className="text-right py-2 px-3 font-medium text-gray-900 dark:text-slate-100">
                          {Math.round(s.confidence * 100)}%
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            {/* Visual forecast comparison chart */}
            {forecast.sources.length >= 2 && (
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 shadow-sm">
                <ForecastChart
                  title="Source Comparison"
                  data={forecast.sources
                    .filter((s) => s.temperature_avg != null || s.precipitation_mm != null)
                    .map((s) => ({
                      date: s.source_name,
                      temperature: s.temperature_avg ?? 0,
                      precipitation: s.precipitation_mm ?? 0,
                    }))}
                  height={280}
                />
              </div>
            )}

            {/* Methodology note */}
            <div className="bg-gray-50 dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
              <p className="text-xs text-gray-500 dark:text-slate-400">
                Forecasts are compared from Open-Meteo (weather API), NASA POWER (satellite observations),
                and Copernicus ERA5 (reanalysis). Discrepancy scores measure inter-source agreement.
                Higher composite confidence = more agreement between independent sources.
                Data is cached for 6 hours to minimize API load.
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
