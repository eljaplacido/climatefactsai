"use client";

// Weather + 5-year temperature trend card for the article-detail page.
//
// Reads enrichment_metadata.weather (current snapshot) and
// .temperature_trend (5-yr annual averages from Open-Meteo archive).
// Both populated by ArticleEnrichmentService at enrichment time.
//
// Stage 2 (M2) of the Golden Artifact roadmap — surfaces the climate
// signal the user has been asking to see visually. Previously the
// enrichment fetched these data points and used them in the LLM prompt
// but threw them away; now stored in enrichment_metadata so this
// component can render a sparkline + the current conditions.
//
// Renders nothing when no data — degrades gracefully for older articles
// enriched before the metadata extension shipped.

import { CloudSun, TrendingDown, TrendingUp, Minus } from "lucide-react";

interface WeatherSnapshot {
  current_temp_c?: number | null;
  current_humidity_pct?: number | null;
  current_precipitation_mm?: number | null;
  weather_code?: number | null;
}

interface TemperatureTrend {
  direction?: string;
  total_change_c?: number;
  period?: string;
  annual_averages?: Record<string, number>;
}

interface Props {
  weather?: WeatherSnapshot | null;
  trend?: TemperatureTrend | null;
  countryCode?: string | null;
}

function trendIcon(direction?: string) {
  if (direction === "warming" || direction === "increasing") {
    return <TrendingUp className="h-4 w-4 text-rose-600" />;
  }
  if (direction === "cooling" || direction === "decreasing") {
    return <TrendingDown className="h-4 w-4 text-sky-600" />;
  }
  return <Minus className="h-4 w-4 text-gray-500" />;
}

function Sparkline({ values, color = "#0891b2" }: { values: number[]; color?: string }) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 180;
  const h = 36;
  const padX = 2;
  const padY = 2;
  const step = (w - padX * 2) / (values.length - 1);
  const points = values.map((v, i) => {
    const x = padX + i * step;
    const y = padY + (h - padY * 2) * (1 - (v - min) / range);
    return [x, y] as [number, number];
  });
  const path = points
    .map(([x, y], i) => (i === 0 ? `M ${x},${y}` : `L ${x},${y}`))
    .join(" ");
  const areaPath = `${path} L ${padX + (values.length - 1) * step},${h - padY} L ${padX},${h - padY} Z`;
  return (
    <svg width={w} height={h} aria-hidden className="overflow-visible">
      <path d={areaPath} fill={color} fillOpacity={0.12} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
      {points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={1.8} fill={color} />
      ))}
    </svg>
  );
}

export default function WeatherTrendCard({ weather, trend, countryCode }: Props) {
  const hasWeather = !!weather && (
    weather.current_temp_c != null ||
    weather.current_humidity_pct != null ||
    weather.current_precipitation_mm != null
  );
  const annual = trend?.annual_averages || {};
  const years = Object.keys(annual).sort();
  const values = years.map((y) => annual[y]).filter((v) => typeof v === "number");
  const hasTrend = values.length >= 2;

  if (!hasWeather && !hasTrend) return null;

  return (
    <section className="bg-gradient-to-br from-sky-50 to-teal-50 border border-sky-200 rounded-xl p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 bg-sky-600 rounded-full flex items-center justify-center flex-shrink-0">
          <CloudSun className="h-5 w-5 text-white" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-gray-900">Climate signal</h2>
          <p className="text-sm text-gray-600">
            Current weather + 5-year temperature trend for {countryCode || "this region"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Current conditions */}
        {hasWeather && (
          <div className="bg-white/70 rounded-lg p-4 border border-white">
            <div className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
              Current conditions
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              {weather?.current_temp_c != null && (
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {weather.current_temp_c.toFixed(1)}°
                  </div>
                  <div className="text-xs text-gray-500">Temp (C)</div>
                </div>
              )}
              {weather?.current_humidity_pct != null && (
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {Math.round(weather.current_humidity_pct)}%
                  </div>
                  <div className="text-xs text-gray-500">Humidity</div>
                </div>
              )}
              {weather?.current_precipitation_mm != null && (
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {weather.current_precipitation_mm.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-500">Precip (mm)</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 5-yr trend sparkline */}
        {hasTrend && (
          <div className="bg-white/70 rounded-lg p-4 border border-white">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                5-yr temperature trend
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-600">
                {trendIcon(trend?.direction)}
                <span className="font-medium">
                  {trend?.direction || "stable"}
                </span>
                {typeof trend?.total_change_c === "number" && (
                  <span className="ml-1">
                    ({trend.total_change_c > 0 ? "+" : ""}
                    {trend.total_change_c.toFixed(2)}°C)
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center justify-center my-2">
              <Sparkline values={values} />
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>{years[0]}</span>
              <span className="text-gray-700 font-medium">
                {values.length > 0 ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1) : "—"}°C avg
              </span>
              <span>{years[years.length - 1]}</span>
            </div>
            <div className="text-xs text-gray-400 text-center mt-2">
              Source: Open-Meteo archive
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
