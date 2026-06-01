"use client";

import { useEffect, useState, useRef, useCallback, memo } from "react";
import { Loader2 } from "lucide-react";

// Self-hosted (public/geo/) — prod CSP blocks the jsdelivr CDN. See InteractiveClimateMap.
const GEO_URL = "/geo/countries-110m.json";

interface CountryStatsData {
  country_code: string;
  country_name: string;
  article_count: number;
  top_topics: string[];
  avg_credibility_score?: number;
}

interface EuropeMapProps {
  countryStats: CountryStatsData[];
  selectedCountry: string | null;
  onCountryClick: (countryCode: string) => void;
}

interface CountryFeature {
  cc: string;
  name: string;
  pathD: string;
}

// ISO 3166-1 numeric → alpha-2
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
  // Additional small European states and territories
  "499":"ME","383":"XK","438":"LI","492":"MC","674":"SM","336":"VA",
  "833":"IM","831":"GG","832":"JE","234":"FO","292":"GI",
};

function resolveCC(id: string): string {
  return NUM_TO_A2[id] || NUM_TO_A2[String(parseInt(id, 10))] || "";
}

function getHeatColor(count: number, maxCount: number): string {
  if (maxCount === 0 || count === 0) return "#e2e8f0";
  // Log-scale for better distribution across varied article counts
  const logRatio = Math.log(count + 1) / Math.log(maxCount + 1);
  if (logRatio > 0.75) return "#0f766e";
  if (logRatio > 0.5) return "#14b8a6";
  if (logRatio > 0.25) return "#5eead4";
  if (logRatio > 0) return "#99f6e4";
  return "#e2e8f0";
}

/**
 * Convert a GeoJSON ring (array of [lon,lat] pairs) to an SVG path string
 * using a Natural Earth 1-like projection baked inline.
 */
function projectCoords(
  coords: number[][],
  projFn: (lon: number, lat: number) => [number, number]
): string {
  let d = "";
  for (let i = 0; i < coords.length; i++) {
    const [x, y] = projFn(coords[i][0], coords[i][1]);
    d += (i === 0 ? "M" : "L") + x.toFixed(1) + "," + y.toFixed(1);
  }
  return d + "Z";
}

function geoToPath(
  geometry: any,
  projFn: (lon: number, lat: number) => [number, number]
): string {
  if (!geometry) return "";
  const { type, coordinates } = geometry;
  let d = "";
  if (type === "Polygon") {
    for (const ring of coordinates) {
      d += projectCoords(ring, projFn);
    }
  } else if (type === "MultiPolygon") {
    for (const polygon of coordinates) {
      for (const ring of polygon) {
        d += projectCoords(ring, projFn);
      }
    }
  }
  return d;
}

function WorldMap({ countryStats, selectedCountry, onCountryClick }: EuropeMapProps) {
  const [features, setFeatures] = useState<CountryFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    name: string; count: number; x: number; y: number; credibility?: number;
  } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const maxCount = Math.max(1, ...countryStats.map((s) => s.article_count));
  const statsMap = Object.fromEntries(
    countryStats.map((s) => [s.country_code, s])
  );

  useEffect(() => {
    let cancelled = false;

    async function loadMap() {
      try {
        const [topojsonClient, d3Geo, resp] = await Promise.all([
          import("topojson-client"),
          import("d3-geo"),
          fetch(GEO_URL),
        ]);

        if (cancelled) return;
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const world = await resp.json();

        const projection = d3Geo
          .geoNaturalEarth1()
          .fitSize([800, 500], { type: "Sphere" } as any);
        const pathGen = d3Geo.geoPath(projection);

        const countriesGeo = topojsonClient.feature(
          world,
          world.objects.countries
        ) as any;

        const mapped: CountryFeature[] = [];
        for (const feat of countriesGeo.features) {
          const cc = resolveCC(String(feat.id));
          const pathD = pathGen(feat) || "";
          if (pathD) {
            mapped.push({
              cc,
              name: feat.properties?.name || cc,
              pathD,
            });
          }
        }

        if (!cancelled) {
          setFeatures(mapped);
          setLoading(false);
        }
      } catch (e: any) {
        if (!cancelled) {
          console.error("Map load failed:", e);
          setError(e.message || "Failed to load map");
          setLoading(false);
        }
      }
    }

    loadMap();
    return () => { cancelled = true; };
  }, []);

  const handleMouseEnter = useCallback(
    (e: React.MouseEvent, feat: CountryFeature) => {
      const stats = statsMap[feat.cc];
      // Prefer API country_name (from DB) over TopoJSON feature name
      // This fixes issues like French Guiana showing "France" from TopoJSON
      const displayName = stats?.country_name || feat.name;
      setTooltip({
        name: displayName,
        count: stats?.article_count || 0,
        credibility: stats?.avg_credibility_score ?? undefined,
        x: e.clientX,
        y: e.clientY,
      });
    },
    [statsMap]
  );

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    setTooltip((prev) =>
      prev ? { ...prev, x: e.clientX, y: e.clientY } : null
    );
  }, []);

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  if (loading) {
    return (
      <div className="w-full h-[500px] bg-sky-50 rounded-xl flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-clilens-primary" />
      </div>
    );
  }

  if (error || features.length === 0) {
    return (
      <div className="w-full h-[500px] bg-sky-50 rounded-xl flex items-center justify-center text-gray-500 text-sm">
        {error ? `Map unavailable: ${error}` : "No map data loaded."}
      </div>
    );
  }

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox="0 0 800 500"
        className="w-full h-[500px]"
        style={{ background: "#f0f9ff" }}
        role="img"
        aria-label="Interactive climate news world map showing article coverage by country"
      >
        <title>Climate news world map - article coverage by country</title>
        {features.map((feat, i) => {
          const stats = statsMap[feat.cc];
          const count = stats?.article_count || 0;
          const isSelected = selectedCountry === feat.cc;
          const fill = count > 0 ? getHeatColor(count, maxCount) : "#e2e8f0";

          return (
            <path
              key={i}
              d={feat.pathD}
              fill={fill}
              stroke={isSelected ? "#0d9488" : "#fff"}
              strokeWidth={isSelected ? 1.5 : 0.4}
              className="transition-colors duration-150 cursor-pointer hover:opacity-80"
              onClick={() => feat.cc && onCountryClick(feat.cc)}
              onMouseEnter={(e) => handleMouseEnter(e, feat)}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
            />
          );
        })}
      </svg>

      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg"
          style={{ left: tooltip.x + 12, top: tooltip.y - 32 }}
        >
          <p className="font-semibold">{tooltip.name}</p>
          <p className="text-gray-300">
            {tooltip.count > 0 ? `${tooltip.count} articles` : "No articles yet"}
          </p>
          {tooltip.credibility != null && (
            <p className="text-gray-400">Avg credibility: {tooltip.credibility}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default memo(WorldMap);
