"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ArticleWeatherContext, LocationWeatherContext } from "@/types";
import { Cloud, Thermometer, Droplets, Wind, AlertTriangle, MapPin } from "lucide-react";

interface Props {
  articleId: string;
}

const WEATHER_CODES: Record<number, string> = {
  0: "Clear sky",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Rime fog",
  51: "Light drizzle",
  53: "Moderate drizzle",
  55: "Dense drizzle",
  61: "Slight rain",
  63: "Moderate rain",
  65: "Heavy rain",
  71: "Slight snow",
  73: "Moderate snow",
  75: "Heavy snow",
  80: "Slight showers",
  81: "Moderate showers",
  82: "Violent showers",
  95: "Thunderstorm",
  96: "Thunderstorm with hail",
};

function WeatherCodeLabel({ code }: { code?: number }) {
  if (code == null) return null;
  return <span className="text-xs text-gray-500">{WEATHER_CODES[code] || `Code ${code}`}</span>;
}

function LocationCard({ ctx }: { ctx: LocationWeatherContext }) {
  const cw = ctx.current_weather;
  const anomaly = ctx.anomaly;
  const normals = ctx.historical_normals;

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5 mb-3">
        <MapPin className="h-4 w-4 text-clilens-teal-600" />
        {ctx.location_name}
        <span className="text-xs text-gray-400 font-normal">
          ({ctx.coordinates.lat.toFixed(2)}, {ctx.coordinates.lon.toFixed(2)})
        </span>
      </h4>

      {/* Current conditions */}
      {cw && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="text-center">
            <Thermometer className="h-4 w-4 text-orange-500 mx-auto mb-1" />
            <p className="text-lg font-semibold text-gray-900">
              {cw.temperature_c != null ? `${cw.temperature_c}°C` : "--"}
            </p>
            <WeatherCodeLabel code={cw.weather_code} />
          </div>
          <div className="text-center">
            <Droplets className="h-4 w-4 text-blue-500 mx-auto mb-1" />
            <p className="text-lg font-semibold text-gray-900">
              {cw.precipitation_mm != null ? `${cw.precipitation_mm}mm` : "--"}
            </p>
            <span className="text-xs text-gray-500">Precipitation</span>
          </div>
          <div className="text-center">
            <Wind className="h-4 w-4 text-gray-500 mx-auto mb-1" />
            <p className="text-lg font-semibold text-gray-900">
              {cw.wind_speed_kmh != null ? `${cw.wind_speed_kmh}km/h` : "--"}
            </p>
            <span className="text-xs text-gray-500">Wind</span>
          </div>
        </div>
      )}

      {/* Anomaly indicator */}
      {anomaly && (
        <div className={`rounded-md px-3 py-2 text-sm mb-3 ${
          anomaly.is_anomalous
            ? "bg-amber-50 border border-amber-200 text-amber-800"
            : "bg-green-50 border border-green-200 text-green-800"
        }`}>
          <div className="flex items-center gap-1.5">
            {anomaly.is_anomalous && <AlertTriangle className="h-4 w-4" />}
            <span className="font-medium">
              {anomaly.temperature_deviation_c > 0 ? "+" : ""}
              {anomaly.temperature_deviation_c}°C vs. last year
            </span>
          </div>
          <p className="text-xs mt-0.5">{anomaly.anomaly_description}</p>
        </div>
      )}

      {/* Historical normals */}
      {normals && (
        <div className="text-xs text-gray-500 border-t pt-2">
          <p>
            Historical avg: {normals.avg_temperature_c}°C, {normals.avg_precipitation_mm}mm precip
          </p>
          <p className="text-gray-400">{normals.period}</p>
        </div>
      )}
    </div>
  );
}

export default function WeatherContext({ articleId }: Props) {
  const [data, setData] = useState<ArticleWeatherContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timeout = setTimeout(() => {
      if (!cancelled) setLoading(false);
    }, 15000); // 15s hard timeout

    setLoading(true);
    setError(false);

    api
      .getArticleWeatherContext(articleId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [articleId]);

  if (loading) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-blue-700 text-sm">
          <Cloud className="h-4 w-4 animate-pulse" />
          Loading weather context...
        </div>
        <div className="mt-2 h-2 bg-blue-100 rounded-full animate-pulse" />
      </div>
    );
  }

  if (error || !data || data.weather_contexts.length === 0) {
    return null; // Silently hide if no weather context available
  }

  return (
    <div className="space-y-3" role="region" aria-label="Local weather context">
      <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Cloud className="h-4 w-4 text-blue-600" />
        Local Weather Context
        <span className="text-xs font-normal text-gray-500">
          {data.locations_found} location{data.locations_found !== 1 ? "s" : ""} detected
        </span>
      </h3>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data.weather_contexts.map((ctx, i) => (
          <LocationCard key={i} ctx={ctx} />
        ))}
      </div>
    </div>
  );
}
