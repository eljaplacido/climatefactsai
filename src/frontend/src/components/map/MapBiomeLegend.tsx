"use client";

// Map Biome Legend — Phase 11 (2026-05-25).
//
// Companion to the "Biomes & Climate" layer in MapLayerControl.
// Renders a corner legend showing the Köppen-Geiger primary climate
// zones (colour fill) + the biome emoji taxonomy (centroid markers).
//
// Fetches /api/map/biome-overview once on first activation; the
// frontend caches the taxonomy for the session.

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface BiomeTaxon {
  id: string;
  label: string;
  emoji: string;
}

interface KoppenTaxon {
  id: string;
  label: string;
  color: string;
  description: string;
}

interface BiomeOverviewPayload {
  countries: unknown[];
  biome_taxonomy: BiomeTaxon[];
  koppen_taxonomy: KoppenTaxon[];
  total_countries: number;
}

interface MapBiomeLegendProps {
  active: boolean;
}

export default function MapBiomeLegend({ active }: MapBiomeLegendProps) {
  const [data, setData] = useState<BiomeOverviewPayload | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!active || data) return;
    fetch(`${API_BASE}/api/map/biome-overview`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));
  }, [active, data]);

  if (!active) return null;
  if (!data) {
    return (
      <div
        className="absolute bottom-4 right-4 z-[1000] bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl text-slate-400 text-xs px-3 py-2"
        data-testid="biome-legend-loading"
      >
        Loading biome taxonomy…
      </div>
    );
  }

  return (
    <div
      className="absolute bottom-4 right-4 z-[1000] w-72 bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl overflow-hidden"
      role="region"
      aria-label="Biome and climate zone legend"
      data-testid="biome-legend"
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full px-3 py-2.5 border-b border-slate-700 flex items-center justify-between text-left"
        aria-expanded={!collapsed}
        data-testid="biome-legend-toggle"
      >
        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Biomes &amp; Climate ({data.total_countries})
        </h3>
        <span className="text-slate-500 text-sm">{collapsed ? "+" : "−"}</span>
      </button>

      {!collapsed && (
        <div className="p-3 space-y-3 max-h-[60vh] overflow-y-auto">
          {/* Köppen climate zones — colour fill on the map */}
          <div>
            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
              Climate zone (Köppen-Geiger)
            </h4>
            <ul className="space-y-1">
              {data.koppen_taxonomy.map((k) => (
                <li
                  key={k.id}
                  className="flex items-center gap-2 text-xs text-slate-300"
                  data-testid={`biome-legend-koppen-${k.id}`}
                >
                  <span
                    className="inline-block w-4 h-4 rounded-sm flex-shrink-0 border border-slate-600"
                    style={{ backgroundColor: k.color }}
                    aria-hidden="true"
                  />
                  <span className="font-medium">{k.label}</span>
                  <span className="text-slate-500 truncate text-[11px]">
                    — {k.description}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Biome taxa — emoji markers at centroids */}
          <div>
            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
              Biome marker (emoji at centroid)
            </h4>
            <ul className="grid grid-cols-2 gap-x-2 gap-y-1">
              {data.biome_taxonomy.map((b) => (
                <li
                  key={b.id}
                  className="flex items-center gap-1.5 text-xs text-slate-300"
                  data-testid={`biome-legend-biome-${b.id}`}
                >
                  <span className="text-base leading-none" aria-hidden="true">
                    {b.emoji}
                  </span>
                  <span className="truncate text-[11px]">{b.label}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-[10px] text-slate-500 leading-tight border-t border-slate-700 pt-2">
            Data: WWF Terrestrial Ecoregions + Köppen-Geiger primary zone.
            Click a country to read its full biome + climate-effects passport.
          </p>
        </div>
      )}
    </div>
  );
}
