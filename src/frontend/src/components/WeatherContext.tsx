"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ArticleWeatherContext, LocationWeatherContext } from "@/types";
import { Cloud, Thermometer, Droplets, Wind, AlertTriangle, MapPin } from "lucide-react";
import AskAboutButton from "./AskAboutButton";

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

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; data: ArticleWeatherContext }
  | { kind: "empty" }
  | { kind: "auth" }
  | { kind: "tier" }
  | { kind: "error" };

export default function WeatherContext({ articleId }: Props) {
  // Deferred #21 (2026-05-25) — distinguish auth / tier / empty / error
  // states so the user understands WHY weather context isn't loading.
  // Previously this silently hid on ANY error including 401/403, so the
  // platform looked broken to anyone not on Standard+.
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const { isLoggedIn } = useAuth();

  useEffect(() => {
    let cancelled = false;

    // Weather context is a Standard+ feature — anonymous always 403s. Skip the
    // doomed request entirely and render the auth prompt, instead of spamming
    // the console with 401/403/404 for every article view.
    if (!isLoggedIn) {
      setState({ kind: "auth" });
      return;
    }

    const timeout = setTimeout(() => {
      if (!cancelled) setState({ kind: "error" });
    }, 15000);

    setState({ kind: "loading" });

    api
      .getArticleWeatherContext(articleId)
      .then((res) => {
        if (cancelled) return;
        if (!res || !res.weather_contexts || res.weather_contexts.length === 0) {
          setState({ kind: "empty" });
        } else {
          setState({ kind: "ready", data: res });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const status =
          typeof err === "object" && err && "response" in err
            ? (err as { response?: { status?: number } }).response?.status
            : undefined;
        if (status === 401) setState({ kind: "auth" });
        else if (status === 403) setState({ kind: "tier" });
        else if (status === 404) setState({ kind: "empty" });
        else setState({ kind: "error" });
      })
      .finally(() => {
        if (!cancelled) clearTimeout(timeout);
      });

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [articleId, isLoggedIn]);

  if (state.kind === "loading") {
    return (
      <div
        className="bg-blue-50 border border-blue-200 rounded-lg p-4"
        data-testid="weather-loading"
      >
        <div className="flex items-center gap-2 text-blue-700 text-sm">
          <Cloud className="h-4 w-4 animate-pulse" />
          Loading weather context...
        </div>
        <div className="mt-2 h-2 bg-blue-100 rounded-full animate-pulse" />
      </div>
    );
  }

  if (state.kind === "auth") {
    return (
      <div
        className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-4"
        data-testid="weather-auth-required"
      >
        <div className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
          <Cloud className="h-4 w-4 mt-0.5 flex-shrink-0 text-blue-500" />
          <div>
            <p className="font-medium">Weather context requires sign-in.</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              <a href="/login" className="text-clilens-primary hover:underline">Sign in</a> to see
              current conditions, anomalies vs historical normals, and 5-year trends
              for the locations mentioned in this article.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (state.kind === "tier") {
    return (
      <div
        className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4"
        data-testid="weather-tier-required"
      >
        <div className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-200">
          <Cloud className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium">Weather context requires Standard or higher.</p>
            <p className="text-xs mt-0.5">
              Free tier limits prevent live weather + anomaly lookups.{" "}
              <a
                href="/dashboard/subscription"
                className="underline hover:no-underline font-medium"
              >
                Upgrade
              </a>{" "}
              to enable for every article.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (state.kind === "empty") {
    return (
      <div
        className="bg-slate-50 dark:bg-slate-800/50 border border-dashed border-slate-200 dark:border-slate-700 rounded-lg p-3 space-y-2"
        data-testid="weather-empty"
      >
        <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
          <Cloud className="h-3.5 w-3.5" />
          No geographic locations detected in this article — weather context unavailable.
        </p>
        <AskAboutButton
          prompt="Why couldn't we detect geographic locations in this article, and what would help surface weather context for it?"
          variant="chip"
        />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div
        className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-3"
        data-testid="weather-error"
      >
        <p className="text-xs text-red-700 dark:text-red-300 flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5" />
          Weather context temporarily unavailable. Try refreshing in a moment.
        </p>
      </div>
    );
  }

  const data = state.data;

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
