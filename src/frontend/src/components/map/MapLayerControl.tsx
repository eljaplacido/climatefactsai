"use client";

import {
  BarChart3,
  Thermometer,
  ShieldAlert,
  Network,
} from "lucide-react";
import type { ActiveLayer } from "./InteractiveClimateMap";

interface LayerOption {
  id: ActiveLayer;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const LAYERS: LayerOption[] = [
  {
    id: "article_density",
    label: "Article Density",
    description: "Number of climate articles per country",
    icon: <BarChart3 className="h-4 w-4" />,
  },
  {
    id: "temperature_anomaly",
    label: "Temperature Anomaly",
    description: "Deviation from historical temperature averages",
    icon: <Thermometer className="h-4 w-4" />,
  },
  {
    id: "climate_risk",
    label: "Climate Risk",
    description: "Composite climate risk score by country",
    icon: <ShieldAlert className="h-4 w-4" />,
  },
  {
    id: "source_diversity",
    label: "Source Diversity",
    description: "Number of distinct sources covering each country",
    icon: <Network className="h-4 w-4" />,
  },
];

interface MapLayerControlProps {
  activeLayer: ActiveLayer;
  onChange: (layer: ActiveLayer) => void;
}

export default function MapLayerControl({
  activeLayer,
  onChange,
}: MapLayerControlProps) {
  return (
    <div className="absolute top-4 left-4 z-[1000] w-56">
      <div className="bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700 shadow-xl overflow-hidden">
        <div className="px-3 py-2.5 border-b border-slate-700">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Map Layer
          </h3>
        </div>
        <div className="p-1.5 space-y-0.5">
          {LAYERS.map((layer) => {
            const isActive = activeLayer === layer.id;
            return (
              <button
                key={layer.id}
                type="button"
                onClick={() => onChange(layer.id)}
                className={`w-full flex items-start gap-2.5 px-2.5 py-2 rounded-lg text-left transition-colors ${
                  isActive
                    ? "bg-teal-600/20 text-teal-300"
                    : "text-slate-400 hover:bg-slate-700/50 hover:text-slate-200"
                }`}
              >
                <div
                  className={`mt-0.5 flex-shrink-0 ${
                    isActive ? "text-teal-400" : "text-slate-500"
                  }`}
                >
                  {layer.icon}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2.5 h-2.5 rounded-full border-2 flex-shrink-0 ${
                        isActive
                          ? "border-teal-400 bg-teal-400"
                          : "border-slate-500 bg-transparent"
                      }`}
                    />
                    <span className="text-sm font-medium">{layer.label}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5 ml-[18px]">
                    {layer.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
