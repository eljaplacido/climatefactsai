"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import type { Article, LocationWeatherContext } from "@/types";
import {
  MapPin,
  ArrowLeft,
  Loader2,
  Search,
  ChevronDown,
  Cloud,
  Thermometer,
  Droplets,
  Wind,
  AlertTriangle,
  Sparkles,
  X,
  Filter,
} from "lucide-react";

// Dynamically import the map component (SSR-incompatible)
const EuropeMap = dynamic(() => import("@/components/EuropeMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[600px] bg-gray-100 rounded-xl flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-clilens-primary" />
    </div>
  ),
});

interface CountryStatsData {
  country_code: string;
  country_name: string;
  article_count: number;
  top_topics: string[];
  top_sources?: string[];
  last_updated?: string;
  avg_credibility_score?: number;
  region?: string;
}

interface AvailableSource {
  source_name: string;
  article_count: number;
  avg_reliability?: number;
}

interface MapQueryHighlight {
  country_code: string;
  country_name: string;
  article_count: number;
  avg_credibility_score?: number;
}

interface MapQueryResult {
  query?: string;
  country_highlights: MapQueryHighlight[];
  matching_articles: number;
  answer?: string;
  filters_applied: Record<string, any>;
  queried_at: string;
}

const RELIABILITY_TIERS = ["All", "HIGH", "MEDIUM", "LOW"] as const;
type ReliabilityTier = (typeof RELIABILITY_TIERS)[number];

const RELIABILITY_LABELS: Record<ReliabilityTier, string> = {
  All: "All tiers",
  HIGH: "High credibility",
  MEDIUM: "Medium credibility",
  LOW: "Low credibility",
};

const CONTENT_CATEGORIES = [
  "Climate Science",
  "Sustainability",
  "Policy",
  "Green Transition",
  "Circular Economy",
] as const;
type ContentCategory = (typeof CONTENT_CATEGORIES)[number];

// Approximate capital / center coordinates for weather lookups
const COUNTRY_COORDS: Record<string, { lat: number; lon: number; name: string }> = {
  FI: { lat: 60.17, lon: 24.94, name: "Helsinki, Finland" },
  SE: { lat: 59.33, lon: 18.07, name: "Stockholm, Sweden" },
  NO: { lat: 59.91, lon: 10.75, name: "Oslo, Norway" },
  DK: { lat: 55.68, lon: 12.57, name: "Copenhagen, Denmark" },
  DE: { lat: 52.52, lon: 13.41, name: "Berlin, Germany" },
  FR: { lat: 48.86, lon: 2.35, name: "Paris, France" },
  NL: { lat: 52.37, lon: 4.90, name: "Amsterdam, Netherlands" },
  BE: { lat: 50.85, lon: 4.35, name: "Brussels, Belgium" },
  LU: { lat: 49.61, lon: 6.13, name: "Luxembourg" },
  ES: { lat: 40.42, lon: -3.70, name: "Madrid, Spain" },
  PT: { lat: 38.72, lon: -9.14, name: "Lisbon, Portugal" },
  IT: { lat: 41.90, lon: 12.50, name: "Rome, Italy" },
  AT: { lat: 48.21, lon: 16.37, name: "Vienna, Austria" },
  CH: { lat: 46.95, lon: 7.45, name: "Bern, Switzerland" },
  PL: { lat: 52.23, lon: 21.01, name: "Warsaw, Poland" },
  CZ: { lat: 50.08, lon: 14.44, name: "Prague, Czech Republic" },
  SK: { lat: 48.15, lon: 17.11, name: "Bratislava, Slovakia" },
  HU: { lat: 47.50, lon: 19.04, name: "Budapest, Hungary" },
  RO: { lat: 44.43, lon: 26.10, name: "Bucharest, Romania" },
  BG: { lat: 42.70, lon: 23.32, name: "Sofia, Bulgaria" },
  HR: { lat: 45.81, lon: 15.98, name: "Zagreb, Croatia" },
  SI: { lat: 46.06, lon: 14.51, name: "Ljubljana, Slovenia" },
  GR: { lat: 37.98, lon: 23.73, name: "Athens, Greece" },
  CY: { lat: 35.17, lon: 33.36, name: "Nicosia, Cyprus" },
  MT: { lat: 35.90, lon: 14.51, name: "Valletta, Malta" },
  IE: { lat: 53.35, lon: -6.26, name: "Dublin, Ireland" },
  EE: { lat: 59.44, lon: 24.75, name: "Tallinn, Estonia" },
  LV: { lat: 56.95, lon: 24.11, name: "Riga, Latvia" },
  LT: { lat: 54.69, lon: 25.28, name: "Vilnius, Lithuania" },
  GB: { lat: 51.51, lon: -0.13, name: "London, United Kingdom" },
  US: { lat: 38.91, lon: -77.04, name: "Washington D.C., United States" },
  UA: { lat: 50.45, lon: 30.52, name: "Kyiv, Ukraine" },
  RS: { lat: 44.79, lon: 20.47, name: "Belgrade, Serbia" },
  BA: { lat: 43.86, lon: 18.41, name: "Sarajevo, Bosnia" },
  MK: { lat: 41.99, lon: 21.43, name: "Skopje, North Macedonia" },
  AL: { lat: 41.33, lon: 19.82, name: "Tirana, Albania" },
  ME: { lat: 42.44, lon: 19.26, name: "Podgorica, Montenegro" },
  IS: { lat: 64.15, lon: -21.95, name: "Reykjavik, Iceland" },
  TR: { lat: 39.93, lon: 32.85, name: "Ankara, Turkey" },
  RU: { lat: 55.76, lon: 37.62, name: "Moscow, Russia" },
  BY: { lat: 53.90, lon: 27.57, name: "Minsk, Belarus" },
  MD: { lat: 47.01, lon: 28.86, name: "Chisinau, Moldova" },
  CA: { lat: 45.42, lon: -75.70, name: "Ottawa, Canada" },
  MX: { lat: 19.43, lon: -99.13, name: "Mexico City, Mexico" },
  AU: { lat: -33.87, lon: 151.21, name: "Sydney, Australia" },
  JP: { lat: 35.68, lon: 139.69, name: "Tokyo, Japan" },
  CN: { lat: 39.91, lon: 116.40, name: "Beijing, China" },
  IN: { lat: 28.61, lon: 77.21, name: "New Delhi, India" },
  BR: { lat: -15.79, lon: -47.88, name: "Brasilia, Brazil" },
  ZA: { lat: -33.93, lon: 18.42, name: "Cape Town, South Africa" },
  KR: { lat: 37.57, lon: 126.98, name: "Seoul, South Korea" },
  // Africa
  KE: { lat: -1.29, lon: 36.82, name: "Nairobi, Kenya" },
  NG: { lat: 9.06, lon: 7.49, name: "Abuja, Nigeria" },
  GH: { lat: 5.56, lon: -0.19, name: "Accra, Ghana" },
  TZ: { lat: -6.79, lon: 39.28, name: "Dar es Salaam, Tanzania" },
  UG: { lat: 0.35, lon: 32.58, name: "Kampala, Uganda" },
  RW: { lat: -1.95, lon: 30.06, name: "Kigali, Rwanda" },
  ET: { lat: 9.02, lon: 38.75, name: "Addis Ababa, Ethiopia" },
  EG: { lat: 30.04, lon: 31.24, name: "Cairo, Egypt" },
  MA: { lat: 33.97, lon: -6.85, name: "Rabat, Morocco" },
  SN: { lat: 14.72, lon: -17.47, name: "Dakar, Senegal" },
  ZM: { lat: -15.39, lon: 28.32, name: "Lusaka, Zambia" },
  MW: { lat: -13.96, lon: 33.77, name: "Lilongwe, Malawi" },
  MZ: { lat: -25.97, lon: 32.57, name: "Maputo, Mozambique" },
  // Latin America
  AR: { lat: -34.60, lon: -58.38, name: "Buenos Aires, Argentina" },
  CO: { lat: 4.71, lon: -74.07, name: "Bogota, Colombia" },
  CL: { lat: -33.45, lon: -70.67, name: "Santiago, Chile" },
  PE: { lat: -12.05, lon: -77.04, name: "Lima, Peru" },
  EC: { lat: -0.18, lon: -78.47, name: "Quito, Ecuador" },
  VE: { lat: 10.49, lon: -66.88, name: "Caracas, Venezuela" },
  // Asia
  ID: { lat: -6.21, lon: 106.85, name: "Jakarta, Indonesia" },
  TH: { lat: 13.76, lon: 100.50, name: "Bangkok, Thailand" },
  VN: { lat: 21.03, lon: 105.85, name: "Hanoi, Vietnam" },
  PH: { lat: 14.60, lon: 120.98, name: "Manila, Philippines" },
  SG: { lat: 1.35, lon: 103.82, name: "Singapore" },
  MY: { lat: 3.14, lon: 101.69, name: "Kuala Lumpur, Malaysia" },
  BD: { lat: 23.81, lon: 90.41, name: "Dhaka, Bangladesh" },
  PK: { lat: 33.69, lon: 73.04, name: "Islamabad, Pakistan" },
  NZ: { lat: -41.29, lon: 174.78, name: "Wellington, New Zealand" },
  TW: { lat: 25.03, lon: 121.57, name: "Taipei, Taiwan" },
  // Middle East
  AE: { lat: 24.45, lon: 54.65, name: "Abu Dhabi, UAE" },
  SA: { lat: 24.71, lon: 46.68, name: "Riyadh, Saudi Arabia" },
  IL: { lat: 31.77, lon: 35.22, name: "Jerusalem, Israel" },
  JO: { lat: 31.95, lon: 35.93, name: "Amman, Jordan" },
  LB: { lat: 33.89, lon: 35.50, name: "Beirut, Lebanon" },
  IQ: { lat: 33.31, lon: 44.37, name: "Baghdad, Iraq" },
  IR: { lat: 35.69, lon: 51.39, name: "Tehran, Iran" },
  QA: { lat: 25.29, lon: 51.53, name: "Doha, Qatar" },
  KW: { lat: 29.38, lon: 47.99, name: "Kuwait City, Kuwait" },
};

const WEATHER_CODES: Record<number, string> = {
  0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
  45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
  55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
  71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Slight showers",
  81: "Moderate showers", 82: "Violent showers", 95: "Thunderstorm", 96: "Thunderstorm with hail",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export default function MapPage() {
  const [countryStats, setCountryStats] = useState<CountryStatsData[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [articlesLoading, setArticlesLoading] = useState(false);

  // Weather overlay state
  const [weatherData, setWeatherData] = useState<LocationWeatherContext | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);

  // --- Filter state ---
  const [mapMode, setMapMode] = useState<"publisher" | "discussed">("publisher");
  const [reliabilityTier, setReliabilityTier] = useState<ReliabilityTier>("All");
  const [selectedCategories, setSelectedCategories] = useState<Set<ContentCategory>>(new Set());
  const [keyword, setKeyword] = useState("");

  // --- Source filter state ---
  const [availableSources, setAvailableSources] = useState<AvailableSource[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>("");

  // --- Agentic query state ---
  const [agentQuery, setAgentQuery] = useState("");
  const [agentResult, setAgentResult] = useState<MapQueryResult | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);

  useEffect(() => {
    fetchAvailableSources();
  }, []);

  useEffect(() => {
    fetchCountryStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapMode, selectedSource]);

  useEffect(() => {
    if (selectedCountry) {
      fetchCountryArticles(selectedCountry);
      fetchWeatherForCountry(selectedCountry);
    } else {
      setWeatherData(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCountry]);

  async function fetchAvailableSources() {
    try {
      const res = await fetch(`${API_BASE}/api/map/available-sources`);
      if (res.ok) setAvailableSources(await res.json());
    } catch {
      // silently fail, dropdown will be empty
    }
  }

  async function fetchCountryStats() {
    setLoading(true);
    setAgentResult(null); // clear agentic results when filters change
    const endpoint =
      mapMode === "publisher"
        ? "/api/map/country-stats"
        : "/api/map/discussed-country-stats";
    const params = new URLSearchParams();
    if (selectedSource) params.set("source", selectedSource);
    const qs = params.toString() ? `?${params.toString()}` : "";
    try {
      const res = await fetch(`${API_BASE}${endpoint}${qs}`);
      if (res.ok) {
        const data = await res.json();
        setCountryStats(data);
      }
    } catch (err) {
      console.error("Failed to fetch country stats:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleAgentQuery(e?: React.FormEvent) {
    e?.preventDefault();
    if (!agentQuery.trim()) return;
    setAgentLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/map/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: agentQuery,
          sources: selectedSource ? [selectedSource] : [],
          reliability_min: reliabilityTier === "HIGH" ? 75 : reliabilityTier === "MEDIUM" ? 50 : undefined,
          limit: 30,
        }),
      });
      if (res.ok) {
        const result: MapQueryResult = await res.json();
        setAgentResult(result);
        // Transform query results into countryStats format for map highlighting
        if (result.country_highlights.length > 0) {
          setCountryStats(
            result.country_highlights.map((h) => ({
              country_code: h.country_code,
              country_name: h.country_name,
              article_count: h.article_count,
              top_topics: [],
              avg_credibility_score: h.avg_credibility_score ?? undefined,
            }))
          );
        }
      }
    } catch (err) {
      console.error("Agent query failed:", err);
    } finally {
      setAgentLoading(false);
    }
  }

  function clearAgentQuery() {
    setAgentQuery("");
    setAgentResult(null);
    fetchCountryStats();
  }

  async function fetchWeatherForCountry(cc: string) {
    const coords = COUNTRY_COORDS[cc];
    if (!coords) {
      setWeatherData(null);
      return;
    }
    setWeatherLoading(true);
    try {
      const data = await api.getLocationWeather(coords.lat, coords.lon, coords.name);
      setWeatherData(data);
    } catch {
      setWeatherData(null);
    } finally {
      setWeatherLoading(false);
    }
  }

  // Client-side filtering: keyword + reliability tier + content categories
  const filteredStats = countryStats.filter((s) => {
    // Keyword filter
    if (keyword.trim()) {
      const lc = keyword.toLowerCase();
      const matchesKeyword =
        s.country_name.toLowerCase().includes(lc) ||
        s.top_topics.some((t) => t.toLowerCase().includes(lc));
      if (!matchesKeyword) return false;
    }

    // Reliability tier filter (HIGH / MEDIUM / LOW based on avg_credibility_score)
    if (reliabilityTier !== "All") {
      const avg = s.avg_credibility_score ?? 0;
      if (reliabilityTier === "HIGH" && avg < 75) return false;
      if (reliabilityTier === "MEDIUM" && (avg < 50 || avg >= 75)) return false;
      if (reliabilityTier === "LOW" && avg >= 50) return false;
    }

    // Content category filter
    if (selectedCategories.size > 0) {
      const categoryKeywords: Record<ContentCategory, string[]> = {
        "Climate Science": ["climate", "science", "arctic", "ocean", "sea-ice", "permafrost", "temperature", "emissions", "co2", "carbon"],
        "Sustainability": ["sustainability", "conservation", "bioeconomy", "biodiversity", "ecosystem", "nature"],
        "Policy": ["policy", "eu-policy", "environmental-policy", "green-deal", "regulation", "legislation", "cop", "paris-agreement"],
        "Green Transition": ["energy-transition", "renewable-energy", "clean-energy", "solar", "wind-power", "hydrogen", "electric"],
        "Circular Economy": ["circular", "recycling", "waste", "reuse", "upcycling"],
      };
      const topicsLower = s.top_topics.map((t) => t.toLowerCase());
      const matchesCategory = Array.from(selectedCategories).some((cat) => {
        const kws = categoryKeywords[cat] || [];
        return kws.some((kw) => topicsLower.some((t) => t.includes(kw)));
      });
      if (!matchesCategory) return false;
    }

    return true;
  });

  function toggleCategory(cat: ContentCategory) {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  }

  async function fetchCountryArticles(cc: string) {
    setArticlesLoading(true);
    try {
      const data = await api.getArticles({ country: cc, limit: 12 });
      setArticles(data);
    } catch {
      setArticles([]);
    } finally {
      setArticlesLoading(false);
    }
  }

  const selectedStats = filteredStats.find(
    (s) => s.country_code === selectedCountry
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="flex items-center gap-2">
              <MapPin className="h-5 w-5 text-clilens-primary" />
              <h1 className="text-xl font-bold text-gray-900">
                Climate Intelligence World Map
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Filter bar */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex flex-wrap items-center gap-4">
            {/* Toggle: publisher origin vs countries discussed */}
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
              <button
                type="button"
                onClick={() => setMapMode("publisher")}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  mapMode === "publisher"
                    ? "bg-clilens-primary text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                Publisher Origin
              </button>
              <button
                type="button"
                onClick={() => setMapMode("discussed")}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  mapMode === "discussed"
                    ? "bg-clilens-primary text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                Countries Discussed
              </button>
            </div>

            {/* Divider */}
            <div className="h-6 w-px bg-gray-200" />

            {/* Reliability tier dropdown */}
            <div className="relative">
              <select
                value={reliabilityTier}
                onChange={(e) =>
                  setReliabilityTier(e.target.value as ReliabilityTier)
                }
                className="appearance-none bg-gray-50 border border-gray-200 rounded-lg pl-3 pr-8 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
              >
                {RELIABILITY_TIERS.map((tier) => (
                  <option key={tier} value={tier}>
                    {RELIABILITY_LABELS[tier]}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            </div>

            {/* Divider */}
            <div className="h-6 w-px bg-gray-200" />

            {/* Content category pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              {CONTENT_CATEGORIES.map((cat) => {
                const active = selectedCategories.has(cat);
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? "bg-clilens-primary text-white border-clilens-primary"
                        : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>

            {/* Divider */}
            <div className="h-6 w-px bg-gray-200" />

            {/* Source filter dropdown */}
            <div className="relative">
              <select
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                className="appearance-none bg-gray-50 border border-gray-200 rounded-lg pl-3 pr-8 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent max-w-[180px]"
              >
                <option value="">All sources</option>
                {availableSources.map((s) => (
                  <option key={s.source_name} value={s.source_name}>
                    {s.source_name} ({s.article_count})
                  </option>
                ))}
              </select>
              <Filter className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            </div>

            {/* Divider */}
            <div className="h-6 w-px bg-gray-200" />

            {/* Keyword search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Filter by keyword..."
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="pl-8 pr-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent w-48"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Agentic Query Bar */}
      <div className="bg-gradient-to-r from-clilens-primary/5 to-blue-50 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5">
          <form onSubmit={handleAgentQuery} className="flex items-center gap-3">
            <Sparkles className="h-4 w-4 text-clilens-primary flex-shrink-0" />
            <input
              type="text"
              placeholder="Ask about climate news... e.g. &quot;drought in East Africa&quot; or &quot;renewable energy in Asia&quot;"
              value={agentQuery}
              onChange={(e) => setAgentQuery(e.target.value)}
              className="flex-1 bg-white border border-gray-200 rounded-lg pl-3 pr-3 py-1.5 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
            />
            <button
              type="submit"
              disabled={agentLoading || !agentQuery.trim()}
              className="px-4 py-1.5 bg-clilens-primary text-white text-sm font-medium rounded-lg hover:bg-clilens-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {agentLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Query Map
            </button>
            {agentResult && (
              <button
                type="button"
                onClick={clearAgentQuery}
                className="p-1.5 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-100"
                title="Clear query results"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </form>
          {agentResult && (
            <div className="mt-2 text-sm">
              {agentResult.answer && (
                <p className="text-gray-700">{agentResult.answer}</p>
              )}
              <p className="text-xs text-gray-400 mt-0.5">
                {agentResult.matching_articles} articles across {agentResult.country_highlights.length} countries
                {Object.keys(agentResult.filters_applied).length > 0 && (
                  <> &bull; Filters: {Object.entries(agentResult.filters_applied).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}</>
                )}
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex gap-6">
          {/* Map panel */}
          <div className="flex-1">
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <EuropeMap
                countryStats={filteredStats}
                selectedCountry={selectedCountry}
                onCountryClick={setSelectedCountry}
              />
            </div>

            {/* Legend */}
            <div className="mt-4 flex items-center gap-4 text-xs text-gray-500">
              <span>Article density:</span>
              <div className="flex items-center gap-1">
                <div className="w-4 h-3 rounded bg-clilens-teal-100" />
                <span>Low</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-4 h-3 rounded bg-clilens-teal-400" />
                <span>Medium</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-4 h-3 rounded bg-clilens-teal-700" />
                <span>High</span>
              </div>
              <div className="ml-auto text-gray-400">
                Mode: {mapMode === "publisher" ? "Publisher origin" : "Countries discussed in news"}
              </div>
            </div>
          </div>

          {/* Sidebar: country detail + weather */}
          <div className="w-96 flex-shrink-0 space-y-4">
            {selectedCountry && selectedStats ? (
              <>
                {/* Country info card */}
                <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
                  <h2 className="text-lg font-bold text-gray-900 mb-1">
                    {selectedStats.country_name}
                  </h2>
                  <p className="text-sm text-gray-500 mb-4">
                    {selectedStats.article_count} articles analyzed
                    {selectedStats.avg_credibility_score != null && (
                      <> &bull; Avg credibility: {selectedStats.avg_credibility_score}</>
                    )}
                  </p>

                  {selectedStats.top_topics.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-1.5">Top topics</p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedStats.top_topics.map((t) => (
                          <span
                            key={t}
                            className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full border border-gray-200"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedStats.top_sources && selectedStats.top_sources.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs text-gray-500 mb-1.5">Top sources</p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedStats.top_sources.map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => setSelectedSource(s)}
                            className={`px-2 py-0.5 text-xs rounded-full border transition-colors cursor-pointer ${
                              selectedSource === s
                                ? "bg-blue-100 text-blue-700 border-blue-300"
                                : "bg-blue-50 text-blue-600 border-blue-200 hover:bg-blue-100"
                            }`}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="border-t border-gray-100 pt-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">
                      Recent Articles
                    </h3>
                    {articlesLoading ? (
                      <div className="flex justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-clilens-primary" />
                      </div>
                    ) : articles.length > 0 ? (
                      <div className="space-y-3 max-h-[320px] overflow-y-auto">
                        {articles.map((a) => (
                          <Link
                            key={a.article_id}
                            href={`/articles/${a.article_id}`}
                            className="block p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                          >
                            <p className="text-sm font-medium text-gray-900 line-clamp-2">
                              {a.title}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              {a.source_name} &bull; {a.claim_count} claims
                            </p>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400 text-center py-4">
                        No articles found for this country.
                      </p>
                    )}
                  </div>
                </div>

                {/* Weather overlay card */}
                <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3">
                    <Cloud className="h-4 w-4 text-blue-600" />
                    Current Weather Conditions
                  </h3>
                  {weatherLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                      <span className="ml-2 text-sm text-gray-500">Loading weather...</span>
                    </div>
                  ) : weatherData?.current_weather ? (
                    <div>
                      <p className="text-xs text-gray-500 mb-3">{weatherData.location_name}</p>
                      <div className="grid grid-cols-3 gap-3 mb-3">
                        <div className="text-center">
                          <Thermometer className="h-4 w-4 text-orange-500 mx-auto mb-1" />
                          <p className="text-lg font-semibold text-gray-900">
                            {weatherData.current_weather.temperature_c != null
                              ? `${weatherData.current_weather.temperature_c}\u00B0C`
                              : "--"}
                          </p>
                          <span className="text-xs text-gray-500">
                            {weatherData.current_weather.weather_code != null
                              ? WEATHER_CODES[weatherData.current_weather.weather_code] || "Unknown"
                              : "Temperature"}
                          </span>
                        </div>
                        <div className="text-center">
                          <Droplets className="h-4 w-4 text-blue-500 mx-auto mb-1" />
                          <p className="text-lg font-semibold text-gray-900">
                            {weatherData.current_weather.precipitation_mm != null
                              ? `${weatherData.current_weather.precipitation_mm}mm`
                              : "--"}
                          </p>
                          <span className="text-xs text-gray-500">Precipitation</span>
                        </div>
                        <div className="text-center">
                          <Wind className="h-4 w-4 text-gray-500 mx-auto mb-1" />
                          <p className="text-lg font-semibold text-gray-900">
                            {weatherData.current_weather.wind_speed_kmh != null
                              ? `${weatherData.current_weather.wind_speed_kmh}km/h`
                              : "--"}
                          </p>
                          <span className="text-xs text-gray-500">Wind</span>
                        </div>
                      </div>

                      {/* Anomaly indicator */}
                      {weatherData.anomaly && (
                        <div
                          className={`rounded-md px-3 py-2 text-sm ${
                            weatherData.anomaly.is_anomalous
                              ? "bg-amber-50 border border-amber-200 text-amber-800"
                              : "bg-green-50 border border-green-200 text-green-800"
                          }`}
                        >
                          <div className="flex items-center gap-1.5">
                            {weatherData.anomaly.is_anomalous && (
                              <AlertTriangle className="h-4 w-4" />
                            )}
                            <span className="font-medium">
                              {weatherData.anomaly.temperature_deviation_c > 0 ? "+" : ""}
                              {weatherData.anomaly.temperature_deviation_c}\u00B0C vs. last year
                            </span>
                          </div>
                          <p className="text-xs mt-0.5">{weatherData.anomaly.anomaly_description}</p>
                        </div>
                      )}

                      {/* Historical normals */}
                      {weatherData.historical_normals && (
                        <div className="text-xs text-gray-500 border-t border-gray-100 pt-2 mt-3">
                          <p>
                            Historical avg: {weatherData.historical_normals.avg_temperature_c}\u00B0C,{" "}
                            {weatherData.historical_normals.avg_precipitation_mm}mm precip
                          </p>
                          <p className="text-gray-400">{weatherData.historical_normals.period}</p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 text-center py-3">
                      {COUNTRY_COORDS[selectedCountry]
                        ? "Weather data unavailable."
                        : "No coordinates available for this country."}
                    </p>
                  )}
                </div>
              </>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 p-8 shadow-sm text-center">
                <MapPin className="h-8 w-8 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 text-sm">
                  Click a country on the map to view its climate intelligence
                  reports and current weather conditions.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
