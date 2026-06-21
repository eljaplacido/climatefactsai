"use client";

import { useEffect, useState } from "react";
import nextDynamic from "next/dynamic";
import type { ActiveLayer } from "@/components/map/layers/registry";
import type { CountryStatEntry } from "@/components/map/InteractiveClimateMap";
import { MapPin, ArrowUpRight, Loader2 } from "lucide-react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const InteractiveClimateMap = nextDynamic(
  () => import("@/components/map/InteractiveClimateMap"),
  { ssr: false, loading: () => <MiniMapLoader /> }
);

interface ClimateMiniMapProps {
  countries: string[];
  title?: string;
  layer?: ActiveLayer;
  height?: "compact" | "full";
  linkToMap?: string;
}

function MiniMapLoader() {
  return (
    <div className="w-full h-full bg-slate-800 rounded-lg flex items-center justify-center">
      <Loader2 className="h-4 w-4 animate-spin text-teal-500" />
    </div>
  );
}

export default function ClimateMiniMap({
  countries,
  title,
  layer = "article_density",
  height = "compact",
  linkToMap,
}: ClimateMiniMapProps) {
  if (!countries || countries.length === 0) return null;

  const [countryStatsData, setCountryStatsData] = useState<CountryStatEntry[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const countrySet = new Set(countries);

    async function fetchData() {
      try {
        // Always fetch base country-stats (provides article_count, top_topics,
        // country_name, climate_risk_score, etc.)
        const baseRes = await fetch(`${API_BASE}/api/map/country-stats`);
        if (!baseRes.ok || cancelled) return;
        const baseData: CountryStatEntry[] = await baseRes.json();

        let merged: CountryStatEntry[] = baseData.filter((s) =>
          countrySet.has(s.country_code)
        );

        // Merge layer-specific data for layers whose key fields aren't in
        // the base /country-stats response.
        if (layer === "corporate_density") {
          const res = await fetch(`${API_BASE}/api/map/layers/corporate-density`);
          if (res.ok && !cancelled) {
            const data: { country_code: string; company_count: number; sbti_validated_count: number; net_zero_target_count: number }[] = await res.json();
            const densityMap: Record<string, { company_count: number; sbti_validated_count: number; net_zero_target_count: number }> = {};
            for (const d of data) densityMap[d.country_code] = d;
            merged = merged.map((s) => {
              const d = densityMap[s.country_code];
              if (!d) return s;
              return { ...s, company_count: d.company_count, sbti_validated_count: d.sbti_validated_count, net_zero_target_count: d.net_zero_target_count };
            });
            const present = new Set(merged.map((s) => s.country_code));
            for (const d of data) {
              if (present.has(d.country_code) || !countrySet.has(d.country_code)) continue;
              merged.push({ country_code: d.country_code, country_name: d.country_code, article_count: 0, top_topics: [], company_count: d.company_count, sbti_validated_count: d.sbti_validated_count, net_zero_target_count: d.net_zero_target_count });
            }
          }
        } else if (layer === "warming_outlook") {
          const res = await fetch(`${API_BASE}/api/map/layers/warming-outlook?horizon_year=2050`);
          if (res.ok && !cancelled) {
            const data: { country_code: string; best_estimate_c?: number; covered: boolean; ssp126_anomaly_c?: number; ssp370_anomaly_c?: number }[] = await res.json();
            const outlookMap: Record<string, { best_estimate_c?: number; covered: boolean; ssp126_anomaly_c?: number; ssp370_anomaly_c?: number }> = {};
            for (const d of data) outlookMap[d.country_code] = d;
            merged = merged.map((s) => {
              const o = outlookMap[s.country_code];
              if (!o) return s;
              return { ...s, best_estimate_c: o.best_estimate_c, warming_covered: o.covered, ssp126_anomaly_c: o.ssp126_anomaly_c, ssp370_anomaly_c: o.ssp370_anomaly_c };
            });
            const present = new Set(merged.map((s) => s.country_code));
            for (const o of data) {
              if (present.has(o.country_code) || !countrySet.has(o.country_code)) continue;
              merged.push({ country_code: o.country_code, country_name: o.country_code, article_count: 0, top_topics: [], best_estimate_c: o.best_estimate_c, warming_covered: o.covered, ssp126_anomaly_c: o.ssp126_anomaly_c, ssp370_anomaly_c: o.ssp370_anomaly_c });
            }
          }
        } else if (layer === "temperature_anomaly") {
          const res = await fetch(`${API_BASE}/api/map/layers/temperature-anomaly`);
          if (res.ok && !cancelled) {
            const data: { country_code: string; anomaly_celsius: number | null }[] = await res.json();
            const anomalyMap: Record<string, number | null> = {};
            for (const d of data) anomalyMap[d.country_code] = d.anomaly_celsius;
            merged = merged.map((s) => ({ ...s, temperature_anomaly: anomalyMap[s.country_code] ?? s.temperature_anomaly }));
          }
        }

        if (!cancelled) setCountryStatsData(merged);
      } catch {
        /* silent fallback — stubs retain map shape */
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [layer, countries]);

  const hClass = height === "compact" ? "h-48" : "h-80";
  const countryStats: CountryStatEntry[] =
    countryStatsData ?? countries.map((cc) => ({
      country_code: cc,
      country_name: cc,
      article_count: 1,
      top_topics: [],
    }));

  const mapParams = new URLSearchParams();
  mapParams.set("layer", layer);
  if (countries.length === 1) mapParams.set("country", countries[0]);

  return (
    <div className={`${hClass} rounded-lg overflow-hidden border border-slate-700 bg-slate-800 relative group`}>
      {title && (
        <div className="absolute top-2 left-2 z-[500] bg-slate-900/85 backdrop-blur-sm rounded-md px-2.5 py-1 border border-slate-700 flex items-center gap-1.5 text-xs text-slate-300">
          <MapPin className="h-3 w-3 text-teal-400" />
          {title}
        </div>
      )}

      <InteractiveClimateMap
        countryStats={countryStats}
        selectedCountry={countries.length === 1 ? countries[0] : null}
        onCountryClick={() => {}}
        activeLayer={layer}
        highlightedCountries={countries}
      />

      <Link
        href={linkToMap || `/map?${mapParams.toString()}`}
        className="absolute bottom-2 right-2 z-[500] bg-slate-900/85 backdrop-blur-sm rounded-md px-2 py-1 border border-slate-700 text-[10px] text-teal-400 hover:text-teal-300 transition-colors flex items-center gap-1 opacity-0 group-hover:opacity-100"
      >
        Open map <ArrowUpRight className="h-2.5 w-2.5" />
      </Link>
    </div>
  );
}
