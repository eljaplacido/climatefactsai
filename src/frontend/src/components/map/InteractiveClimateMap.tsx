"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Tooltip,
  useMap,
} from "react-leaflet";
import type { Layer, PathOptions, LeafletMouseEvent } from "leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const GEO_URL =
  "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

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

export type ActiveLayer =
  | "article_density"
  | "temperature_anomaly"
  | "climate_risk"
  | "source_diversity";

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
}

interface InteractiveClimateMapProps {
  countryStats: CountryStatEntry[];
  selectedCountry: string | null;
  onCountryClick: (countryCode: string) => void;
  activeLayer: ActiveLayer;
  highlightedCountries: string[];
  timelineDate?: string;
}

// Color scales for each layer
function getLayerColor(
  cc: string,
  layer: ActiveLayer,
  statsMap: Record<string, CountryStatEntry>,
  maxArticle: number
): string {
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
      const risk = stat.climate_risk_score ?? 0;
      if (risk > 75) return "#dc2626";
      if (risk > 50) return "#f97316";
      if (risk > 25) return "#facc15";
      if (risk > 0) return "#86efac"; // green-300
      return "#334155";
    }
    case "source_diversity": {
      const sources = stat.source_count ?? 0;
      if (sources > 10) return "#7c3aed"; // violet-600
      if (sources > 5) return "#a78bfa"; // violet-400
      if (sources > 2) return "#c4b5fd"; // violet-300
      if (sources > 0) return "#ede9fe"; // violet-100
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

    if (feature) {
      const layer = L.geoJSON(feature);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 5, duration: 0.8 });
      }
    }
  }, [selectedCountry, geoData, map]);

  return null;
}

export default function InteractiveClimateMap({
  countryStats,
  selectedCountry,
  onCountryClick,
  activeLayer,
  highlightedCountries,
}: InteractiveClimateMapProps) {
  const [geoData, setGeoData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const geoJsonRef = useRef<L.GeoJSON | null>(null);

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

  const highlightedSet = useMemo(
    () => new Set(highlightedCountries),
    [highlightedCountries]
  );

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
      const fillColor = getLayerColor(cc, activeLayer, statsMap, maxArticle);

      return {
        fillColor,
        fillOpacity: isHighlighted ? 0.9 : isSelected ? 0.85 : 0.7,
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
    [selectedCountry, highlightedSet, activeLayer, statsMap, maxArticle]
  );

  const onEachFeature = useCallback(
    (feature: GeoJSON.Feature, layer: Layer) => {
      const cc = feature.properties?.cc as string;
      const stat = statsMap[cc];
      const name = stat?.country_name || feature.properties?.name || cc;

      // Tooltip
      const tooltipContent = stat
        ? `<div class="text-xs">
            <strong class="text-sm">${name}</strong><br/>
            ${stat.article_count} articles
            ${stat.avg_credibility_score != null ? ` | Credibility: ${stat.avg_credibility_score}` : ""}
            ${stat.temperature_anomaly != null ? `<br/>Temp anomaly: ${stat.temperature_anomaly > 0 ? "+" : ""}${stat.temperature_anomaly}\u00B0C` : ""}
          </div>`
        : `<div class="text-xs"><strong class="text-sm">${name}</strong><br/>No data</div>`;

      layer.bindTooltip(tooltipContent, {
        sticky: true,
        direction: "top",
        offset: [0, -10],
        className:
          "!bg-slate-900 !text-white !border-none !rounded-lg !shadow-lg !px-3 !py-2",
      });

      // Click
      layer.on("click", () => {
        if (cc) onCountryClick(cc);
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
    [statsMap, onCountryClick]
  );

  // Force re-render of GeoJSON when styling deps change
  const geoJsonKey = useMemo(
    () =>
      `${activeLayer}-${selectedCountry}-${highlightedCountries.join(",")}-${countryStats.length}`,
    [activeLayer, selectedCountry, highlightedCountries, countryStats.length]
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

        <FlyToCountry selectedCountry={selectedCountry} geoData={geoData} />
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
      `}</style>
    </div>
  );
}
