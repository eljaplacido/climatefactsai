"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { MapPin, ArrowLeft, Loader2 } from "lucide-react";
import type { ActiveLayer, CountryStatEntry } from "@/components/map/InteractiveClimateMap";
import MapLayerControl from "@/components/map/MapLayerControl";
import MapFilterPanel from "@/components/map/MapFilterPanel";
import MapCountryPanel from "@/components/map/MapCountryPanel";
import MapAgenticChat from "@/components/map/MapAgenticChat";
import MapTimeline from "@/components/map/MapTimeline";
import MapCompareView from "@/components/map/MapCompareView";

// Dynamic import of the Leaflet-based map (no SSR)
const InteractiveClimateMap = dynamic(
  () => import("@/components/map/InteractiveClimateMap"),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-slate-900 rounded-lg flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-teal-500" />
      </div>
    ),
  }
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface AvailableSource {
  source_name: string;
  article_count: number;
  avg_reliability?: number;
}

interface MapFilters {
  dateFrom: string;
  dateTo: string;
  reliabilityTier: "All" | "HIGH" | "MEDIUM" | "LOW";
  categories: Set<string>;
  source: string;
  keyword: string;
}

const INITIAL_FILTERS: MapFilters = {
  dateFrom: "",
  dateTo: "",
  reliabilityTier: "All",
  categories: new Set(),
  source: "",
  keyword: "",
};

function getCurrentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function MapPage() {
  // Core state
  const [countryStats, setCountryStats] = useState<CountryStatEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Map interaction state
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<ActiveLayer>("article_density");
  const [highlightedCountries, setHighlightedCountries] = useState<string[]>([]);

  // Filter state
  const [filters, setFilters] = useState<MapFilters>(INITIAL_FILTERS);
  const [availableSources, setAvailableSources] = useState<AvailableSource[]>([]);

  // Timeline state
  const [timelineDate, setTimelineDate] = useState(getCurrentYearMonth);

  // Compare mode
  const [compareMode, setCompareMode] = useState(false);
  const [compareCountryA, setCompareCountryA] = useState("");
  const [compareCountryB, setCompareCountryB] = useState("");

  // Fetch country stats
  const fetchCountryStats = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.source) params.set("source", filters.source);
    if (filters.dateFrom) params.set("date_from", filters.dateFrom);
    if (filters.dateTo) params.set("date_to", filters.dateTo);
    if (filters.reliabilityTier !== "All")
      params.set("credibility", filters.reliabilityTier);
    if (filters.keyword) params.set("keyword", filters.keyword);
    if (filters.categories.size > 0)
      params.set("categories", Array.from(filters.categories).join(","));
    if (timelineDate) params.set("month", timelineDate);

    const qs = params.toString() ? `?${params.toString()}` : "";

    try {
      const res = await fetch(`${API_BASE}/api/map/country-stats${qs}`);
      if (res.ok) {
        setCountryStats(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch country stats:", err);
    } finally {
      setLoading(false);
    }
  }, [filters, timelineDate]);

  // Fetch available sources
  useEffect(() => {
    async function fetchSources() {
      try {
        const res = await fetch(`${API_BASE}/api/map/available-sources`);
        if (res.ok) setAvailableSources(await res.json());
      } catch {
        // silently fail
      }
    }
    fetchSources();
  }, []);

  // Fetch stats on mount and when filters/timeline change
  useEffect(() => {
    fetchCountryStats();
  }, [fetchCountryStats]);

  // Handlers
  function handleCountryClick(cc: string) {
    setSelectedCountry(cc === selectedCountry ? null : cc);
  }

  function handleApplyFilters() {
    fetchCountryStats();
  }

  function handleClearFilters() {
    setFilters(INITIAL_FILTERS);
  }

  function handleHighlightCountries(codes: string[]) {
    setHighlightedCountries(codes);
  }

  function handleTimelineChange(date: string) {
    setTimelineDate(date);
  }

  function handleOpenCompare(ccA?: string) {
    setCompareCountryA(ccA || selectedCountry || "");
    setCompareCountryB("");
    setCompareMode(true);
  }

  function handleRegionZoom(region: string) {
    // This is a UI convenience - in a real scenario we would call map.flyToBounds
    // For now we filter the keyword to the region
    const regionKeywords: Record<string, string> = {
      africa: "Africa",
      asia: "Asia",
      europe: "Europe",
      americas: "Americas",
      middle_east: "Middle East",
      oceania: "Oceania",
    };
    setFilters((prev) => ({
      ...prev,
      keyword: regionKeywords[region] || "",
    }));
  }

  // Client-side filtering for keyword (server handles the rest)
  const filteredStats =
    filters.keyword && !loading
      ? countryStats.filter((s) => {
          const lc = filters.keyword.toLowerCase();
          return (
            s.country_name.toLowerCase().includes(lc) ||
            s.country_code.toLowerCase().includes(lc) ||
            (s.top_topics || []).some((t) => t.toLowerCase().includes(lc)) ||
            (s.region || "").toLowerCase().includes(lc)
          );
        })
      : countryStats;

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-900 overflow-hidden">
      {/* Compact header */}
      <header className="bg-slate-800 border-b border-slate-700 flex-shrink-0 z-[1100]">
        <div className="flex items-center justify-between px-4 py-2.5">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-slate-400 hover:text-slate-200 transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="flex items-center gap-2">
              <MapPin className="h-5 w-5 text-teal-500" />
              <h1 className="text-lg font-bold text-slate-100">
                Climate Intelligence Map
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Stats summary */}
            <div className="hidden md:flex items-center gap-4 text-xs text-slate-400">
              <span>
                <strong className="text-slate-200">{countryStats.length}</strong>{" "}
                countries
              </span>
              <span>
                <strong className="text-slate-200">
                  {countryStats.reduce((sum, s) => sum + s.article_count, 0).toLocaleString()}
                </strong>{" "}
                articles
              </span>
            </div>

            {/* Compare button */}
            <button
              type="button"
              onClick={() => handleOpenCompare()}
              className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg transition-colors"
            >
              Compare Countries
            </button>
          </div>
        </div>
      </header>

      {/* Map area */}
      <main className="flex-1 relative overflow-hidden">
        {/* Full-screen map */}
        <InteractiveClimateMap
          countryStats={filteredStats}
          selectedCountry={selectedCountry}
          onCountryClick={handleCountryClick}
          activeLayer={activeLayer}
          highlightedCountries={highlightedCountries}
          timelineDate={timelineDate}
        />

        {/* Layer control - top left */}
        <MapLayerControl
          activeLayer={activeLayer}
          onChange={setActiveLayer}
        />

        {/* Filter panel - left, offset past layer control */}
        <MapFilterPanel
          filters={filters}
          onFiltersChange={setFilters}
          onApply={handleApplyFilters}
          onClear={handleClearFilters}
          availableSources={availableSources}
          onRegionZoom={handleRegionZoom}
        />

        {/* Country detail panel - right side */}
        {selectedCountry && (
          <MapCountryPanel
            countryCode={selectedCountry}
            onClose={() => setSelectedCountry(null)}
            onCompare={(cc) => handleOpenCompare(cc)}
          />
        )}

        {/* Timeline - bottom bar (above chat) */}
        <MapTimeline
          currentDate={timelineDate}
          onChange={handleTimelineChange}
        />

        {/* Agentic chat - bottom center */}
        <MapAgenticChat
          onHighlightCountries={handleHighlightCountries}
          onCountryClick={handleCountryClick}
        />

        {/* Compare overlay */}
        {compareMode && (
          <MapCompareView
            initialCountryA={compareCountryA}
            initialCountryB={compareCountryB}
            onClose={() => setCompareMode(false)}
          />
        )}

        {/* Loading overlay */}
        {loading && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1001]">
            <div className="bg-slate-800/90 backdrop-blur-sm rounded-full px-4 py-2 border border-slate-700 flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-teal-400" />
              <span className="text-xs text-slate-300">Updating map...</span>
            </div>
          </div>
        )}

        {/* Layer legend */}
        <div className="absolute bottom-4 right-4 z-[999]">
          <div className="bg-slate-800/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-slate-700">
            <LayerLegend activeLayer={activeLayer} />
          </div>
        </div>
      </main>
    </div>
  );
}

/** Inline legend that changes based on the active layer */
function LayerLegend({ activeLayer }: { activeLayer: ActiveLayer }) {
  const legends: Record<
    ActiveLayer,
    { label: string; items: { color: string; text: string }[] }
  > = {
    article_density: {
      label: "Article Density",
      items: [
        { color: "bg-teal-200", text: "Low" },
        { color: "bg-teal-300", text: "Medium" },
        { color: "bg-teal-500", text: "High" },
        { color: "bg-teal-600", text: "Very High" },
      ],
    },
    temperature_anomaly: {
      label: "Temp Anomaly",
      items: [
        { color: "bg-blue-500", text: "< -1\u00B0C" },
        { color: "bg-blue-200", text: "-1 to 0\u00B0C" },
        { color: "bg-yellow-200", text: "0 to +1\u00B0C" },
        { color: "bg-yellow-400", text: "+1 to +2\u00B0C" },
        { color: "bg-orange-500", text: "+2 to +3\u00B0C" },
        { color: "bg-red-600", text: "> +3\u00B0C" },
      ],
    },
    climate_risk: {
      label: "Climate Risk",
      items: [
        { color: "bg-green-300", text: "Low" },
        { color: "bg-yellow-400", text: "Moderate" },
        { color: "bg-orange-500", text: "High" },
        { color: "bg-red-600", text: "Very High" },
      ],
    },
    source_diversity: {
      label: "Source Diversity",
      items: [
        { color: "bg-violet-100", text: "1-2" },
        { color: "bg-violet-300", text: "3-5" },
        { color: "bg-violet-400", text: "6-10" },
        { color: "bg-violet-600", text: "10+" },
      ],
    },
  };

  const legend = legends[activeLayer];

  return (
    <div>
      <p className="text-[10px] text-slate-400 mb-1.5 font-medium">
        {legend.label}
      </p>
      <div className="flex items-center gap-2">
        {legend.items.map((item) => (
          <div key={item.text} className="flex items-center gap-1">
            <div className={`w-3 h-2.5 rounded-sm ${item.color}`} />
            <span className="text-[9px] text-slate-500">{item.text}</span>
          </div>
        ))}
        <div className="flex items-center gap-1 ml-1">
          <div className="w-3 h-2.5 rounded-sm bg-slate-700" />
          <span className="text-[9px] text-slate-500">No data</span>
        </div>
      </div>
    </div>
  );
}
