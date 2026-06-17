"use client";

// Phase 8 (2026-05-24) — disable static prerender; useSearchParams below
// can't be statically rendered.
export const dynamic = "force-dynamic";

import { Suspense, useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import nextDynamic from "next/dynamic";
import { MapPin, ArrowLeft, Loader2, Briefcase, User } from "lucide-react";
import type { ActiveLayer } from "@/components/map/layers/registry";
import { getLayer, MAP_LAYERS } from "@/components/map/layers/registry";
import type { CountryStatEntry } from "@/components/map/InteractiveClimateMap";
import MapLayerControl from "@/components/map/MapLayerControl";
import MapFilterPanel from "@/components/map/MapFilterPanel";
import MapCountryPanel from "@/components/map/MapCountryPanel";
import MapAgenticChat from "@/components/map/MapAgenticChat";
import MapTimeline from "@/components/map/MapTimeline";
import MapCompareView from "@/components/map/MapCompareView";
import MapWalkthrough, { MapWalkthroughTrigger } from "@/components/map/MapWalkthrough";
import MapBiomeLegend from "@/components/map/MapBiomeLegend";
import { useViewContext } from "@/lib/view-context";
import { useUrlState, URL_STATE_SERIALIZERS } from "@/lib/useUrlState";
import type { ViewMode } from "@/lib/plainLanguage";
import type { ChatActionSpec } from "@/lib/chatActionDispatcher";

// Dynamic import of the Leaflet-based map (no SSR)
const InteractiveClimateMap = nextDynamic(
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

// Phase 2D (2026-05-23) — MH1 rollout per the competitive UX audit.
// The shareable state on the map is: country (selectedCountry), layer
// (activeLayer), compare mode + the two compared countries, plus the
// most-useful filter (keyword). Other filters (dateFrom/dateTo, source
// dropdown, categories Set) stay session-local for now — they encode
// poorly into URL params and aren't typically what people share.
const layerSerializer = {
  encode: (v: ActiveLayer) => (v === "article_density" ? null : v),
  decode: (raw: string | null): ActiveLayer => {
    const known = MAP_LAYERS.map((l) => l.id);
    return (known.find((k) => k === raw) ?? "article_density") as ActiveLayer;
  },
};

const compareModeSerializer = {
  encode: (v: boolean) => (v ? "1" : null),
  decode: (raw: string | null): boolean => raw === "1" || raw === "true",
};

const viewModeSerializer = {
  encode: (v: ViewMode) => (v === "business" ? "business" : null),
  decode: (raw: string | null): ViewMode => (raw === "business" ? "business" : "public"),
};

export default function MapPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading map…</div>}>
      <MapPageInner />
    </Suspense>
  );
}

function MapPageInner() {
  // Core state
  const [countryStats, setCountryStats] = useState<CountryStatEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Phase 9 (2026-05-25) — onboarding walkthrough. Opens automatically
  // on first visit; re-openable via the "Take the tour" trigger.
  const [tourOpen, setTourOpen] = useState(false);

  // Map interaction state — Phase 2D: URL-persistent so `/map?country=DE`
  // and `/map?layer=temperature_anomaly` work as deeplinks.
  const [selectedCountry, setSelectedCountry] = useUrlState<string | null>(
    "country",
    null,
    URL_STATE_SERIALIZERS.nullableString,
  );
  const [activeLayer, setActiveLayer] = useUrlState<ActiveLayer>(
    "layer",
    "article_density",
    layerSerializer,
  );
  const [viewMode, setViewMode] = useUrlState<ViewMode>(
    "view",
    "public",
    viewModeSerializer,
  );
  const [highlightedCountries, setHighlightedCountries] = useState<string[]>([]);
  // Quick Region Zoom target (region key + "#nonce" so repeat clicks re-fire).
  const [zoomRegion, setZoomRegion] = useState<string | null>(null);
  const zoomNonce = useRef(0);

  // Filter state — most filters stay session-local; only `keyword` lands
  // in the URL since it's the one users routinely want to share.
  const [filters, setFilters] = useState<MapFilters>(INITIAL_FILTERS);
  const [urlKeyword, setUrlKeyword] = useUrlState(
    "q",
    "",
    URL_STATE_SERIALIZERS.string,
  );
  const [availableSources, setAvailableSources] = useState<AvailableSource[]>([]);

  // Timeline state — empty until we discover the latest month with data on mount
  const [timelineDate, setTimelineDate] = useState("");

  // Compare mode — Phase 2D: URL-persistent so sharing a compare view
  // (`/map?compare=1&compareA=DE&compareB=FR`) reproduces it.
  const [compareMode, setCompareMode] = useUrlState(
    "compare",
    false,
    compareModeSerializer,
  );
  const [compareCountryA, setCompareCountryA] = useUrlState(
    "compareA",
    "",
    URL_STATE_SERIALIZERS.string,
  );
  const [compareCountryB, setCompareCountryB] = useUrlState(
    "compareB",
    "",
    URL_STATE_SERIALIZERS.string,
  );

  // Mirror the URL keyword into the filters Set on mount + when URL changes.
  useEffect(() => {
    if (urlKeyword !== filters.keyword) {
      setFilters((prev) => ({ ...prev, keyword: urlKeyword }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlKeyword]);

  // Publish current map state into shared view-context so the global chat
  // (ContextualAssistant) and the inline MapAgenticChat both know what the
  // user is focused on.
  const { setView, clearKey } = useViewContext();
  useEffect(() => {
    setView({ countryCode: selectedCountry || undefined });
  }, [selectedCountry, setView]);
  useEffect(() => {
    if (compareMode && compareCountryA && compareCountryB) {
      setView({ compareCountries: [compareCountryA, compareCountryB] });
    } else {
      clearKey("compareCountries");
    }
  }, [compareMode, compareCountryA, compareCountryB, setView, clearKey]);

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

  // On mount, discover the latest YYYY-MM with data so the timeline starts on
  // a populated month (instead of "today", which can be empty if seed is older).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/map/country-stats`);
        if (!res.ok || cancelled) return;
        const data: CountryStatEntry[] = await res.json();
        if (cancelled) return;
        let latest = "";
        for (const s of data) {
          const m = s.last_updated ? String(s.last_updated).slice(0, 7) : "";
          if (m && m > latest) latest = m;
        }
        if (latest) setTimelineDate(latest);
      } catch {
        // silently fail — fetchCountryStats will still load unfiltered data
      }
    })();
    return () => { cancelled = true; };
  }, []);

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

  // Fetch layer-specific data when switching to temp anomaly layer
  useEffect(() => {
    if (activeLayer !== "temperature_anomaly") return;
    // Check if we already have anomaly data
    if (countryStats.some((s) => s.temperature_anomaly != null)) return;

    async function fetchTempAnomalies() {
      try {
        const res = await fetch(`${API_BASE}/api/map/layers/temperature-anomaly`);
        if (!res.ok) return;
        const data: { country_code: string; anomaly_celsius: number | null; current_temp: number | null }[] =
          await res.json();
        if (!data.length) return;
        const anomalyMap = Object.fromEntries(
          data.map((d) => [d.country_code, d.anomaly_celsius])
        );
        setCountryStats((prev) =>
          prev.map((s) => ({
            ...s,
            temperature_anomaly: anomalyMap[s.country_code] ?? s.temperature_anomaly,
          }))
        );
      } catch {
        // silently fail
      }
    }
    fetchTempAnomalies();
  }, [activeLayer, countryStats]);

  // Fetch layer-specific data when switching to corporate density layer.
  // We keep /country-stats article-centric and merge company metrics lazily.
  useEffect(() => {
    if (activeLayer !== "corporate_density") return;
    if (countryStats.some((s) => s.company_count != null)) return;

    async function fetchCorporateDensity() {
      try {
        const res = await fetch(`${API_BASE}/api/map/layers/corporate-density`);
        if (!res.ok) return;
        const data: {
          country_code: string;
          company_count: number;
          sbti_validated_count: number;
          net_zero_target_count: number;
        }[] = await res.json();
        if (!data.length) return;

        const densityMap = Object.fromEntries(
          data.map((d) => [d.country_code, d])
        );

        setCountryStats((prev) =>
          {
            const merged = prev.map((s) => {
              const d = densityMap[s.country_code];
              if (!d) return s;
              return {
                ...s,
                company_count: d.company_count,
                sbti_validated_count: d.sbti_validated_count,
                net_zero_target_count: d.net_zero_target_count,
              };
            });

            const present = new Set(merged.map((s) => s.country_code));
            for (const d of data) {
              if (present.has(d.country_code)) continue;
              merged.push({
                country_code: d.country_code,
                country_name: d.country_code,
                article_count: 0,
                top_topics: [],
                company_count: d.company_count,
                sbti_validated_count: d.sbti_validated_count,
                net_zero_target_count: d.net_zero_target_count,
              });
            }
            return merged;
          }
        );
      } catch {
        // silently fail
      }
    }

    fetchCorporateDensity();
  }, [activeLayer, countryStats]);

  // Handlers
  function handleCountryClick(cc: string) {
    setSelectedCountry(cc === selectedCountry ? null : cc);
  }

  function handleApplyFilters() {
    // Phase 2D — push the keyword filter to the URL on Apply so the
    // resulting view is shareable. Other filters stay session-local.
    if (filters.keyword !== urlKeyword) {
      setUrlKeyword(filters.keyword);
    }
    fetchCountryStats();
  }

  function handleClearFilters() {
    setFilters(INITIAL_FILTERS);
    setUrlKeyword("");
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
    // Fly the map to the region's bounds (handled by InteractiveClimateMap's
    // FlyToRegion). The old version only set a keyword filter, which emptied
    // statsMap and produced a blank grey map. Append a nonce so clicking the
    // same region twice still re-zooms (effect deps change).
    setZoomRegion(`${region}#${zoomNonce.current++}`);
  }

  // Phase 0 map extensions (2026-06-16) — execute chat-suggested actions
  const handleActionClick = useCallback(
    (action: ChatActionSpec) => {
      const p = action.params || {};
      switch (action.type) {
        case "open_country":
          if (typeof p.code === "string" && p.code.length === 2)
            setSelectedCountry(p.code.toUpperCase());
          break;
        case "apply_map_filters":
          if (p.layer) setActiveLayer(p.layer as ActiveLayer);
          if (p.country && typeof p.country === "string")
            setSelectedCountry(p.country.toUpperCase());
          break;
        case "navigate":
          if (typeof p.path === "string") window.location.assign(p.path);
          break;
        case "open_company":
          if (typeof p.ticker === "string")
            window.location.assign(`/companies/${encodeURIComponent(p.ticker.toUpperCase())}`);
          break;
        case "start_deep_search":
          if (typeof p.q === "string")
            window.location.assign(`/deep-search?q=${encodeURIComponent(p.q)}`);
          break;
        // Other actions (confirm-mode) are handled by the global chat's
        // dispatchChatAction — the MapAgenticChat only fires auto-mode actions
      }
    },
    [setSelectedCountry, setActiveLayer],
  );

  // Client-side filtering for keyword (server handles the rest)
  const filteredStats =
    filters.keyword && !loading
      ? countryStats.filter((s) => {
          // Defensive — country_name / country_code can be null in
          // some rows, and top_topics can contain null entries.
          const lc = (filters.keyword || "").toLowerCase();
          const name = (s.country_name || "").toLowerCase();
          const code = (s.country_code || "").toLowerCase();
          const region = (s.region || "").toLowerCase();
          const topics = (s.top_topics || []).filter(
            (t): t is string => typeof t === "string"
          );
          return (
            name.includes(lc) ||
            code.includes(lc) ||
            topics.some((t) => t.toLowerCase().includes(lc)) ||
            region.includes(lc)
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
            {/* View mode toggle — public / business */}
            <div
              role="radiogroup"
              aria-label="View mode"
              className="flex items-center gap-1 p-0.5 bg-slate-700 rounded-md"
            >
              <button
                type="button"
                role="radio"
                aria-checked={viewMode === "public"}
                onClick={() => setViewMode("public")}
                className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded transition-colors ${
                  viewMode === "public"
                    ? "bg-slate-600 text-slate-100 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <User className="h-3 w-3" />
                Public
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={viewMode === "business"}
                onClick={() => setViewMode("business")}
                className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded transition-colors ${
                  viewMode === "business"
                    ? "bg-slate-600 text-slate-100 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Briefcase className="h-3 w-3" />
                Business
              </button>
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
          zoomRegion={zoomRegion}
        />

        {/* Layer control - top left */}
        <MapLayerControl
          activeLayer={activeLayer}
          onChange={setActiveLayer}
        />

        {/* Phase 9 (2026-05-25) — onboarding overlay + re-open trigger */}
        <MapWalkthrough
          forceOpen={tourOpen}
          onClose={() => setTourOpen(false)}
        />

        {/* Phase 11 (2026-05-25) — biome layer legend (renders only when active) */}
        <MapBiomeLegend active={activeLayer === "biomes"} />
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-30 bg-white/95 dark:bg-slate-900/95 border border-gray-200 dark:border-slate-700 rounded-full px-3 py-1 shadow-sm">
          <MapWalkthroughTrigger onClick={() => setTourOpen(true)} />
        </div>

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
            viewMode={viewMode}
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
          selectedCountry={selectedCountry}
          compareCountries={
            compareMode && compareCountryA && compareCountryB
              ? [compareCountryA, compareCountryB]
              : undefined
          }
          onActionClick={handleActionClick}
        />

        {/* Compare overlay */}
        {compareMode && (
          <MapCompareView
            initialCountryA={compareCountryA}
            initialCountryB={compareCountryB}
            activeLayer={activeLayer}
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

/** Inline legend that pulls from the layer registry */
function LayerLegend({ activeLayer }: { activeLayer: ActiveLayer }) {
  const layer = getLayer(activeLayer);
  const legendItems = layer?.legend ?? [];
  const label = layer?.label ?? activeLayer.replace(/_/g, " ");

  return (
    <div>
      <p className="text-[10px] text-slate-400 mb-1.5 font-medium">
        {label}
      </p>
      <div className="flex items-center gap-2">
        {legendItems.map((item) => (
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
