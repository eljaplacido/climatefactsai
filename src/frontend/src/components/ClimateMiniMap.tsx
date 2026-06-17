"use client";

import nextDynamic from "next/dynamic";
import type { ActiveLayer } from "@/components/map/layers/registry";
import type { CountryStatEntry } from "@/components/map/InteractiveClimateMap";
import { MapPin, ArrowUpRight, Loader2 } from "lucide-react";
import Link from "next/link";

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

  const hClass = height === "compact" ? "h-48" : "h-80";
  const countryStats: CountryStatEntry[] = countries.map((cc) => ({
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
