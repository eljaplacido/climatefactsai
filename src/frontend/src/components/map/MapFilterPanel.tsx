"use client";

import { useState } from "react";
import {
  Filter,
  ChevronLeft,
  ChevronRight,
  Search,
  X,
  Calendar,
  Globe,
} from "lucide-react";
interface MapFilters {
  dateFrom: string;
  dateTo: string;
  reliabilityTier: "All" | "HIGH" | "MEDIUM" | "LOW";
  categories: Set<string>;
  source: string;
  keyword: string;
}

interface MapFilterPanelProps {
  filters: MapFilters;
  onFiltersChange: (filters: MapFilters) => void;
  onApply: () => void;
  onClear: () => void;
  availableSources: { source_name: string; article_count: number }[];
  onRegionZoom?: (region: string) => void;
}

const CONTENT_CATEGORIES: {
  value: string;
  label: string;
}[] = [
  { value: "climate_science", label: "Climate Science" },
  { value: "sustainability", label: "Sustainability" },
  { value: "green_transition", label: "Green Transition" },
  { value: "policy", label: "Policy" },
  { value: "circular_economy", label: "Circular Economy" },
  { value: "localized_forecast", label: "Localized Forecast" },
];

const REGIONS: { label: string; value: string }[] = [
  { label: "Africa", value: "africa" },
  { label: "Asia", value: "asia" },
  { label: "Europe", value: "europe" },
  { label: "Americas", value: "americas" },
  { label: "Middle East", value: "middle_east" },
  { label: "Oceania", value: "oceania" },
];

export default function MapFilterPanel({
  filters,
  onFiltersChange,
  onApply,
  onClear,
  availableSources,
  onRegionZoom,
}: MapFilterPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [sourceSearch, setSourceSearch] = useState("");

  const filteredSources = availableSources.filter((s) =>
    s.source_name.toLowerCase().includes(sourceSearch.toLowerCase())
  );

  function updateFilter<K extends keyof MapFilters>(
    key: K,
    value: MapFilters[K]
  ) {
    onFiltersChange({ ...filters, [key]: value });
  }

  function toggleCategory(cat: string) {
    const next = new Set(filters.categories);
    if (next.has(cat)) {
      next.delete(cat);
    } else {
      next.add(cat);
    }
    updateFilter("categories", next);
  }

  const activeFilterCount =
    (filters.dateFrom ? 1 : 0) +
    (filters.dateTo ? 1 : 0) +
    (filters.reliabilityTier !== "All" ? 1 : 0) +
    filters.categories.size +
    (filters.source ? 1 : 0) +
    (filters.keyword ? 1 : 0);

  if (collapsed) {
    return (
      <div className="absolute top-4 left-[15.5rem] z-[1000]">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl p-3 text-slate-400 hover:text-slate-200 transition-colors relative"
          title="Show filters"
        >
          <Filter className="h-5 w-5" />
          {activeFilterCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-teal-500 text-white text-[10px] font-bold flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="absolute top-4 left-[15.5rem] z-[1000] w-72">
      <div className="bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl max-h-[calc(100vh-8rem)] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-700 sticky top-0 bg-slate-800/95 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Filters
            </h3>
            {activeFilterCount > 0 && (
              <span className="bg-teal-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {activeFilterCount}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        <div className="p-3 space-y-4">
          {/* Date range */}
          <div>
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5 mb-1.5">
              <Calendar className="h-3 w-3" />
              Date Range
            </label>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => updateFilter("dateFrom", e.target.value)}
                className="bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500"
                placeholder="From"
              />
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) => updateFilter("dateTo", e.target.value)}
                className="bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500"
                placeholder="To"
              />
            </div>
          </div>

          {/* Reliability tier */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">
              Reliability Tier
            </label>
            <select
              value={filters.reliabilityTier}
              onChange={(e) =>
                updateFilter(
                  "reliabilityTier",
                  e.target.value as MapFilters["reliabilityTier"]
                )
              }
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500"
            >
              <option value="All">All tiers</option>
              <option value="HIGH">High credibility</option>
              <option value="MEDIUM">Medium credibility</option>
              <option value="LOW">Low credibility</option>
            </select>
          </div>

          {/* Content categories */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">
              Content Category
            </label>
            <div className="space-y-1">
              {CONTENT_CATEGORIES.map((cat) => (
                <label
                  key={cat.value}
                  className="flex items-center gap-2 cursor-pointer group"
                >
                  <input
                    type="checkbox"
                    checked={filters.categories.has(cat.value)}
                    onChange={() => toggleCategory(cat.value)}
                    className="w-3.5 h-3.5 rounded border-slate-500 bg-slate-700 text-teal-500 focus:ring-teal-500 focus:ring-offset-0"
                  />
                  <span className="text-xs text-slate-300 group-hover:text-slate-100">
                    {cat.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Source filter */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">
              Source
            </label>
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-slate-500" />
              <input
                type="text"
                value={sourceSearch}
                onChange={(e) => setSourceSearch(e.target.value)}
                placeholder="Search sources..."
                className="w-full bg-slate-700 border border-slate-600 rounded-lg pl-7 pr-2 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>
            {sourceSearch && filteredSources.length > 0 && (
              <div className="mt-1 max-h-28 overflow-y-auto bg-slate-700 rounded-lg border border-slate-600">
                {filteredSources.slice(0, 10).map((s) => (
                  <button
                    key={s.source_name}
                    type="button"
                    onClick={() => {
                      updateFilter("source", s.source_name);
                      setSourceSearch("");
                    }}
                    className={`w-full text-left px-2 py-1 text-xs hover:bg-slate-600 transition-colors ${
                      filters.source === s.source_name
                        ? "text-teal-300 bg-slate-600"
                        : "text-slate-300"
                    }`}
                  >
                    {s.source_name}{" "}
                    <span className="text-slate-500">({s.article_count})</span>
                  </button>
                ))}
              </div>
            )}
            {filters.source && (
              <div className="mt-1 flex items-center gap-1 bg-teal-600/20 rounded-md px-2 py-1">
                <span className="text-xs text-teal-300 truncate flex-1">
                  {filters.source}
                </span>
                <button
                  type="button"
                  onClick={() => updateFilter("source", "")}
                  className="text-teal-400 hover:text-teal-200"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>

          {/* Keyword search */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 block">
              Keyword
            </label>
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-slate-500" />
              <input
                type="text"
                value={filters.keyword}
                onChange={(e) => updateFilter("keyword", e.target.value)}
                placeholder="Filter by keyword..."
                className="w-full bg-slate-700 border border-slate-600 rounded-lg pl-7 pr-2 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>
          </div>

          {/* Region quick-select */}
          <div>
            <label className="text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
              <Globe className="h-3 w-3" />
              Quick Region Zoom
            </label>
            <div className="grid grid-cols-3 gap-1">
              {REGIONS.map((region) => (
                <button
                  key={region.value}
                  type="button"
                  onClick={() => onRegionZoom?.(region.value)}
                  className="px-2 py-1.5 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 hover:text-slate-100 rounded-lg border border-slate-600 transition-colors text-center"
                >
                  {region.label}
                </button>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-2 border-t border-slate-700">
            <button
              type="button"
              onClick={onApply}
              className="flex-1 px-3 py-2 bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium rounded-lg transition-colors"
            >
              Apply Filters
            </button>
            <button
              type="button"
              onClick={onClear}
              className="px-3 py-2 text-slate-400 hover:text-slate-200 text-xs transition-colors"
            >
              Clear All
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
