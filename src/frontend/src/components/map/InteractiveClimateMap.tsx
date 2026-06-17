"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Marker,
  Tooltip,
  useMap,
} from "react-leaflet";
import type { Layer, PathOptions, LeafletMouseEvent, LatLngTuple } from "leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Self-hosted (public/geo/) — the prod CSP `connect-src 'self' https://*.run.app
// https://*.googleapis.com` blocks the jsdelivr CDN, which silently broke the
// entire map (base geography never loaded). Serving from 'self' fixes it AND
// removes the runtime dependency on an external CDN.
const GEO_URL = "/geo/countries-110m.json";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Phase 11 (2026-05-25) — biome+Köppen overlay response shape.
// Matches biome_overview_payload() in country_biome_map.py.
interface BiomeEntry {
  country_code: string;
  biome_id: string;
  biome_label: string;
  biome_emoji: string;
  koppen_id: string;
  koppen_label: string;
  koppen_color: string;
  koppen_description: string;
}

// ISO 3166-1 numeric -> alpha-2 (same as EuropeMap.tsx)
const NUM_TO_A2: Record<string, string> = {
  "4":"AF","8":"AL","12":"DZ","20":"AD","24":"AO","31":"AZ","32":"AR",
  "36":"AU","40":"AT","50":"BD","51":"AM","56":"BE","64":"BT","68":"BO",
  "70":"BA","72":"BW","76":"BR","100":"BG","104":"MM","108":"BI","112":"BY",
  "116":"KH","120":"CM","124":"CA","140":"CF","144":"LK","148":"TD","152":"CL",
  "156":"CN","170":"CO","178":"CG","180":"CD","188":"CR","191":"HR","192":"CU",
  "196":"CY","203":"CZ","208":"DK","214":"DO","218":"EC","222":"SV","226":"GQ",
  "231":"ET","232":"ER","233":"EE","242":"FJ","246":"FI","250":"FR","266":"GA",
  "268":"GE","270":"GM","276":"DE","288":"GH","300":"GR","320":"GT","324":"GN",
  "328":"GY","332":"HT","340":"HN","348":"HU","352":"IS","356":"IN","360":"ID",
  "364":"IR","368":"IQ","372":"IE","376":"IL","380":"IT","388":"JM","392":"JP",
  "398":"KZ","400":"JO","404":"KE","408":"KP","410":"KR","414":"KW","417":"KG",
  "418":"LA","422":"LB","426":"LS","428":"LV","430":"LR","434":"LY","440":"LT",
  "442":"LU","450":"MG","454":"MW","458":"MY","466":"ML","478":"MR","484":"MX",
  "496":"MN","498":"MD","504":"MA","508":"MZ","512":"OM","516":"NA","524":"NP",
  "528":"NL","554":"NZ","558":"NI","562":"NE","566":"NG","578":"NO","586":"PK",
  "591":"PA","598":"PG","600":"PY","604":"PE","608":"PH","616":"PL","620":"PT",
  "634":"QA","642":"RO","643":"RU","646":"RW","682":"SA","686":"SN","688":"RS",
  "694":"SL","702":"SG","703":"SK","704":"VN","705":"SI","706":"SO","710":"ZA",
  "716":"ZW","724":"ES","728":"SS","729":"SD","740":"SR","748":"SZ","752":"SE",
  "756":"CH","760":"SY","762":"TJ","764":"TH","768":"TG","780":"TT","784":"AE",
  "788":"TN","792":"TR","795":"TM","800":"UG","804":"UA","807":"MK","818":"EG",
  "826":"GB","834":"TZ","840":"US","854":"BF","858":"UY","860":"UZ","862":"VE",
  "887":"YE","894":"ZM","10":"AQ","158":"TW","260":"TF","275":"PS","304":"GL",
  "732":"EH","90":"SB","548":"VU","174":"KM","480":"MU",
  "499":"ME","383":"XK","438":"LI","492":"MC","674":"SM","336":"VA",
  "833":"IM","831":"GG","832":"JE","234":"FO","292":"GI",
};

function resolveCC(id: string): string {
  return NUM_TO_A2[id] || NUM_TO_A2[String(parseInt(id, 10))] || "";
}

import type { ActiveLayer } from "./layers/registry";
export type { ActiveLayer };

export interface CountryStatEntry {
  country_code: string;
  country_name: string;
  article_count: number;
  top_topics: string[];
  top_sources?: string[];
  last_updated?: string;
  avg_credibility_score?: number;
  region?: string;
  temperature_anomaly?: number;
  climate_risk_score?: number;
  source_count?: number;
  company_count?: number;
  sbti_validated_count?: number;
  net_zero_target_count?: number;
  event_count?: number;
  disputed_count?: number;
  controversy_score?: number;
  latest_event_at?: string;
  ndc_status_category?: string;
  cat_overall_rating?: number;
  ndc_target_reduction_pct?: number;
  best_estimate_c?: number;
  warming_covered?: boolean;
}

interface InteractiveClimateMapProps {
  countryStats: CountryStatEntry[];
  selectedCountry: string | null;
  onCountryClick: (countryCode: string) => void;
  activeLayer: ActiveLayer;
  highlightedCountries: string[];
  timelineDate?: string;
  /** Region key (africa/asia/europe/americas/middle_east/oceania) to fly to. */
  zoomRegion?: string | null;
}

// Color scales for each layer
function getLayerColor(
  cc: string,
  layer: ActiveLayer,
  statsMap: Record<string, CountryStatEntry>,
  maxArticle: number,
  maxSourceCount: number,
  maxCompanyCount: number,
  biomeData: Record<string, BiomeEntry>
): string {
  if (layer === "biomes") {
    return biomeData[cc]?.koppen_color || "#9CA3AF"; // slate-400 — unclassified
  }

  const stat = statsMap[cc];
  if (!stat) return "#334155"; // slate-700 (no data)

  switch (layer) {
    case "article_density": {
      const count = stat.article_count;
      if (count === 0 || maxArticle === 0) return "#334155";
      const ratio = Math.log(count + 1) / Math.log(maxArticle + 1);
      if (ratio > 0.75) return "#0d9488"; // teal-600
      if (ratio > 0.5) return "#14b8a6"; // teal-500
      if (ratio > 0.25) return "#5eead4"; // teal-300
      return "#99f6e4"; // teal-200
    }
    case "temperature_anomaly": {
      const anomaly = stat.temperature_anomaly ?? 0;
      if (anomaly > 3) return "#dc2626"; // red-600
      if (anomaly > 2) return "#f97316"; // orange-500
      if (anomaly > 1) return "#facc15"; // yellow-400
      if (anomaly > 0) return "#fef08a"; // yellow-200
      if (anomaly > -1) return "#bfdbfe"; // blue-200
      return "#3b82f6"; // blue-500
    }
    case "climate_risk": {
      // Backend may provide 0-10 or legacy 0-100 risk values.
      const rawRisk = stat.climate_risk_score ?? 0;
      const risk = rawRisk > 10 ? rawRisk / 10 : rawRisk;
      if (risk >= 7) return "#dc2626";   // red-600 — extreme
      if (risk >= 5) return "#f97316";   // orange-500 — high
      if (risk >= 3) return "#facc15";   // yellow-400 — moderate
      if (risk > 0) return "#86efac";    // green-300 — low
      return "#334155";                   // slate-700 — no data
    }
    case "source_diversity": {
      const sources = stat.source_count ?? 0;
      if (sources <= 0) return "#334155";

      const dynamicMax = Math.max(1, maxSourceCount);
      const ratio = Math.min(sources / dynamicMax, 1);

      // Keep low values visible on dark basemap (avoid near-white shades).
      if (ratio >= 0.75) return "#6d28d9"; // violet-700 — top coverage
      if (ratio >= 0.5) return "#7c3aed";  // violet-600
      if (ratio >= 0.25) return "#8b5cf6"; // violet-500
      if (ratio > 0) return "#a78bfa";     // violet-400 — minimal but visible
      return "#334155";                    // slate-700 — no sources
    }
    case "corporate_density": {
      const companies = stat.company_count ?? 0;
      if (companies <= 0) return "#334155";

      const dynamicMax = Math.max(1, maxCompanyCount);
      const ratio = Math.min(companies / dynamicMax, 1);

      if (ratio >= 0.75) return "#3730a3"; // indigo-800
      if (ratio >= 0.5) return "#4338ca";  // indigo-700
      if (ratio >= 0.25) return "#6366f1"; // indigo-500
      return "#a5b4fc";                    // indigo-300
    }
    case "news_events": {
      const score = stat.controversy_score ?? 0;
      if (score >= 7) return "#dc2626";   // red-600
      if (score >= 5) return "#f97316";   // orange-500
      if (score >= 3) return "#f59e0b";   // amber-500
      if (score > 0) return "#fde68a";    // amber-200
      return "#334155";
    }
    case "ndc_status": {
      const status = stat.ndc_status_category;
      if (status === "net_zero") return "#059669";  // emerald-600
      if (status === "strong") return "#34d399";    // emerald-400
      if (status === "moderate") return "#f59e0b";  // amber-400
      if (status === "weak") return "#f87171";      // red-400
      return "#334155";                              // no data
    }
    case "warming_outlook": {
      const anomaly = stat.best_estimate_c ?? 0;
      if (!stat.warming_covered) return "#334155";
      if (anomaly > 3.5) return "#dc2626";   // red-600
      if (anomaly > 2.5) return "#f97316";   // orange-500
      if (anomaly > 1.5) return "#fde047";   // yellow-300
      if (anomaly > 0) return "#bfdbfe";     // blue-200
      return "#334155";
    }
    default:
      return "#334155";
  }
}

/** Flies to the bounds of a given country code */
function FlyToCountry({
  selectedCountry,
  geoData,
}: {
  selectedCountry: string | null;
  geoData: GeoJSON.FeatureCollection | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (!selectedCountry || !geoData) return;

    const feature = geoData.features.find((f: any) => {
      const cc = resolveCC(String(f.id ?? f.properties?.id ?? ""));
      return cc === selectedCountry;
    });

    if (!feature) return;

    // Deep-link landings (?country=XX from "Open country on map") mount the
    // map and read the param in the same tick — flying before the pane is
    // laid out silently no-ops. Defer a frame + invalidateSize, then fly
    // once bounds are valid. Effect re-fires when geoData loads. (F6b)
    const timer = setTimeout(() => {
      try {
        map.invalidateSize();
      } catch {
        /* map container not ready — deps will re-fire */
      }
      const layer = L.geoJSON(feature);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 5, duration: 0.8 });
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [selectedCountry, geoData, map]);

  return null;
}

/** Quick Region Zoom — flies to a continent/region's bounds without filtering
 * out the rest of the map's data (the old handler only set a keyword filter,
 * which emptied statsMap and left a blank grey map). */
const REGION_BOUNDS: Record<string, [LatLngTuple, LatLngTuple]> = {
  africa: [[-35, -18], [38, 52]],
  asia: [[5, 60], [55, 150]],
  europe: [[34, -25], [71, 45]],
  americas: [[-56, -170], [72, -34]],
  middle_east: [[12, 25], [42, 63]],
  oceania: [[-48, 110], [0, 180]],
};

function FlyToRegion({ region }: { region: string | null | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (!region) return;
    // region may carry a "#nonce" suffix so re-clicking the same region
    // re-triggers this effect; strip it before the bounds lookup.
    const key = region.split("#")[0];
    const bounds = REGION_BOUNDS[key];
    if (!bounds) return;
    const timer = setTimeout(() => {
      try {
        map.invalidateSize();
      } catch {
        /* container not ready — deps re-fire */
      }
      map.flyToBounds(bounds, { padding: [20, 20], duration: 0.8 });
    }, 100);
    return () => clearTimeout(timer);
  }, [region, map]);
  return null;
}

export default function InteractiveClimateMap({
  countryStats,
  selectedCountry,
  onCountryClick,
  activeLayer,
  highlightedCountries,
  zoomRegion,
}: InteractiveClimateMapProps) {
  const [geoData, setGeoData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const [biomeData, setBiomeData] = useState<Record<string, BiomeEntry>>({});
  const geoJsonRef = useRef<L.GeoJSON | null>(null);

  // Phase 11 (2026-05-25) — lazy-load biome+Köppen overlay only when its
  // layer is selected. Cached for the session afterwards.
  useEffect(() => {
    if (activeLayer !== "biomes" || Object.keys(biomeData).length) return;
    let cancelled = false;
    fetch(`${API_BASE}/api/map/biome-overview`)
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => {
        if (cancelled || !payload?.countries) return;
        const map: Record<string, BiomeEntry> = {};
        for (const entry of payload.countries as BiomeEntry[]) {
          map[entry.country_code] = entry;
        }
        setBiomeData(map);
      })
      .catch(() => {
        /* silent — legend surfaces the loading state */
      });
    return () => {
      cancelled = true;
    };
  }, [activeLayer, biomeData]);

  const statsMap = useMemo(
    () =>
      Object.fromEntries(
        countryStats.map((s) => [s.country_code, s])
      ),
    [countryStats]
  );

  const maxArticle = useMemo(
    () => Math.max(1, ...countryStats.map((s) => s.article_count)),
    [countryStats]
  );

  const maxSourceCount = useMemo(
    () => Math.max(1, ...countryStats.map((s) => s.source_count ?? 0)),
    [countryStats]
  );

  const maxCompanyCount = useMemo(
    () => Math.max(1, ...countryStats.map((s) => s.company_count ?? 0)),
    [countryStats]
  );

  const highlightedSet = useMemo(
    () => new Set(highlightedCountries),
    [highlightedCountries]
  );

  // Phase 11 — centroid per country, derived from the same GeoJSON we
  // already render so we don't need a hardcoded 195-entry lookup.
  // Memoised because L.geoJSON().getBounds() is non-trivial.
  const countryCentroids = useMemo<Record<string, LatLngTuple>>(() => {
    if (!geoData) return {};
    const out: Record<string, LatLngTuple> = {};
    for (const feat of geoData.features) {
      const cc = feat.properties?.cc as string | undefined;
      if (!cc) continue;
      try {
        const bounds = L.geoJSON(feat).getBounds();
        if (!bounds.isValid()) continue;
        const c = bounds.getCenter();
        out[cc] = [c.lat, c.lng];
      } catch {
        /* skip malformed geometry */
      }
    }
    return out;
  }, [geoData]);

  // Load and convert TopoJSON -> GeoJSON
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [topoClient, resp] = await Promise.all([
          import("topojson-client"),
          fetch(GEO_URL),
        ]);
        if (cancelled) return;
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const world = await resp.json();

        const countries = topoClient.feature(
          world,
          world.objects.countries
        ) as unknown as GeoJSON.FeatureCollection;

        // Countries that wrap around the antimeridian (180 longitude) cause
        // rendering artefacts — they render as lines spanning the whole map.
        // Antarctica is also excluded since it adds no editorial value.
        const SKIP_COUNTRIES = new Set(["RU", "FJ", "AQ"]);

        // Attach alpha-2 country code as property and filter problematic entries
        countries.features = countries.features.filter((feat) => {
          const cc = resolveCC(String((feat as any).id ?? ""));
          feat.properties = feat.properties || {};
          feat.properties.cc = cc;
          feat.properties.name = feat.properties.name || cc;
          return !SKIP_COUNTRIES.has(cc);
        });

        if (!cancelled) {
          setGeoData(countries);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load map GeoJSON:", err);
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const styleFeature = useCallback(
    (feature: GeoJSON.Feature | undefined): PathOptions => {
      if (!feature?.properties) return {};

      const cc = feature.properties.cc as string;
      const isSelected = cc === selectedCountry;
      const isHighlighted = highlightedSet.has(cc);
      const fillColor = getLayerColor(
        cc,
        activeLayer,
        statsMap,
        maxArticle,
        maxSourceCount,
        maxCompanyCount,
        biomeData
      );

      // Biome layer uses softer fill so the emoji marker reads cleanly.
      const baseOpacity = activeLayer === "biomes" ? 0.55 : 0.7;

      return {
        fillColor,
        fillOpacity: isHighlighted ? 0.9 : isSelected ? 0.85 : baseOpacity,
        color: isSelected
          ? "#0d9488"
          : isHighlighted
          ? "#f59e0b"
          : "#475569",
        weight: isSelected ? 2.5 : isHighlighted ? 2 : 0.5,
        opacity: 1,
        // dashArray for highlighted pulsing effect handled via className
      };
    },
    [
      selectedCountry,
      highlightedSet,
      activeLayer,
      statsMap,
      maxArticle,
      maxSourceCount,
      maxCompanyCount,
      biomeData,
    ]
  );

  const onEachFeature = useCallback(
    (feature: GeoJSON.Feature, layer: Layer) => {
      const cc = feature.properties?.cc as string;
      const stat = statsMap[cc];
      const name = stat?.country_name || feature.properties?.name || cc;
      const biome = biomeData[cc];

      // Tooltip \u2014 biome layer prefers the biome+K\u00F6ppen story; other layers
      // keep the coverage/credibility story. Countries without coverage still
      // surface the suggest-source CTA on the data layers.
      let tooltipContent: string;
      if (activeLayer === "biomes" && biome) {
        tooltipContent = `<div class="text-xs">
            <strong class="text-sm">${name}</strong><br/>
            <span>${biome.biome_emoji} ${biome.biome_label}</span><br/>
            <span class="text-slate-300">K\u00F6ppen: ${biome.koppen_label}</span>
          </div>`;
      } else if (stat) {
        tooltipContent = `<div class="text-xs">
            <strong class="text-sm">${name}</strong><br/>
            ${
              activeLayer === "corporate_density"
                ? `${stat.company_count ?? 0} companies`
                : activeLayer === "news_events"
                ? `${stat.event_count ?? 0} recent events`
                : `${stat.article_count} articles`
            }
            ${stat.avg_credibility_score != null ? ` | Credibility: ${stat.avg_credibility_score}` : ""}
            ${stat.temperature_anomaly != null ? `<br/>Temp anomaly: ${stat.temperature_anomaly > 0 ? "+" : ""}${stat.temperature_anomaly}\u00B0C` : ""}
            ${activeLayer === "corporate_density" ? `<br/>SBTi validated: ${stat.sbti_validated_count ?? 0}` : ""}
            ${activeLayer === "news_events" ? `<br/>Controversy score: ${stat.controversy_score ?? 0}/10` : ""}
            ${activeLayer === "ndc_status" ? `<br/>CAT rating: ${stat.cat_overall_rating ?? "—"}/100` : ""}
          </div>`;
      } else {
        tooltipContent = `<div class="text-xs">
            <strong class="text-sm">${name}</strong><br/>
            <span class="text-amber-300">No coverage yet</span><br/>
            <span class="text-slate-300">Click to suggest a source</span>
          </div>`;
      }

      layer.bindTooltip(tooltipContent, {
        sticky: true,
        direction: "top",
        offset: [0, -10],
        className:
          "!bg-slate-900 !text-white !border-none !rounded-lg !shadow-lg !px-3 !py-2",
      });

      // Click — for countries with no coverage, route to the suggest-source flow
      // (in a new tab so the user keeps their map context). Otherwise open the
      // country panel as usual.
      layer.on("click", () => {
        if (!cc) return;
        if (!stat || stat.article_count === 0) {
          if (typeof window !== "undefined") {
            window.open(`/suggest-source?country=${cc}`, "_blank", "noopener");
          }
          return;
        }
        onCountryClick(cc);
      });

      // Hover highlight
      layer.on("mouseover", (e: LeafletMouseEvent) => {
        const target = e.target;
        target.setStyle({ fillOpacity: 0.9, weight: 2 });
        target.bringToFront();
      });

      layer.on("mouseout", (e: LeafletMouseEvent) => {
        if (geoJsonRef.current) {
          geoJsonRef.current.resetStyle(e.target);
        }
      });
    },
    [statsMap, onCountryClick, activeLayer, biomeData]
  );

  // Force re-render of GeoJSON when styling deps change. `biomeData` key
  // is the count so the layer redraws once the lazy fetch resolves.
  const geoJsonKey = useMemo(
    () =>
      `${activeLayer}-${selectedCountry}-${highlightedCountries.join(",")}-${countryStats.length}-b${Object.keys(biomeData).length}`,
    [activeLayer, selectedCountry, highlightedCountries, countryStats.length, biomeData]
  );

  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-900 rounded-lg">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400 text-sm">Loading map data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={[20, 0]}
        zoom={2}
        minZoom={2}
        maxZoom={8}
        scrollWheelZoom={true}
        zoomControl={true}
        className="w-full h-full rounded-lg"
        style={{ background: "#0f172a" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
        />

        {geoData && (
          <GeoJSON
            key={geoJsonKey}
            ref={(ref) => {
              geoJsonRef.current = ref;
            }}
            data={geoData}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        )}

        {/* Phase 11 — biome emoji markers at country centroids. Only render
            when the biome layer is active and the centroid is known. Markers
            are non-interactive so clicks still hit the underlying polygon. */}
        {activeLayer === "biomes" &&
          Object.values(biomeData).map((entry) => {
            const centroid = countryCentroids[entry.country_code];
            if (!centroid) return null;
            return (
              <Marker
                key={`biome-${entry.country_code}`}
                position={centroid}
                interactive={false}
                keyboard={false}
                icon={L.divIcon({
                  html: `<span style="font-size:18px;line-height:1;text-shadow:0 1px 2px rgba(0,0,0,0.6)">${entry.biome_emoji}</span>`,
                  iconSize: [24, 24],
                  iconAnchor: [12, 12],
                  className: "biome-emoji-marker",
                })}
              />
            );
          })}

        <FlyToCountry selectedCountry={selectedCountry} geoData={geoData} />
        <FlyToRegion region={zoomRegion} />
      </MapContainer>

      {/* Pulsing highlight overlay for agentic chat results */}
      {highlightedCountries.length > 0 && (
        <div className="absolute top-3 right-3 z-[1000] bg-slate-800/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-amber-500/30">
          <span className="text-xs text-amber-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            {highlightedCountries.length} countries highlighted
          </span>
        </div>
      )}

      <style jsx global>{`
        .leaflet-tooltip {
          background: #0f172a !important;
          color: #e2e8f0 !important;
          border: 1px solid #334155 !important;
          border-radius: 8px !important;
          padding: 8px 12px !important;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4) !important;
          font-family: inherit !important;
        }
        .leaflet-tooltip-top::before {
          border-top-color: #0f172a !important;
        }
        .leaflet-container {
          font-family: inherit !important;
        }
        .biome-emoji-marker {
          background: transparent !important;
          border: none !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          pointer-events: none !important;
        }
      `}</style>
    </div>
  );
}
