"use client";

import type { ActiveLayer } from "./layers/registry";
import { MAP_LAYERS } from "./layers/registry";

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
          {MAP_LAYERS.map((layer) => {
            const isActive = activeLayer === layer.id;
            const Icon = layer.icon;
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
                  <Icon className="h-4 w-4" />
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
