"use client";

import { useState } from "react";
import { ChevronDown, Layers, Brain, Cloud, Globe, FileText, AlertCircle } from "lucide-react";
import type { DeepSearchMethodology } from "@/types";

interface Props {
  methodology?: DeepSearchMethodology | null;
  internalCount?: number;
  externalCount?: number;
  /** When the search succeeded but was constrained, expose which constraints applied */
  filters?: Record<string, any> | null;
  className?: string;
}

export default function MethodologyDrawer({
  methodology,
  internalCount,
  externalCount,
  filters,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  if (!methodology) return null;

  const layers = methodology.queries_run ?? [];
  const sources = methodology.sources_consulted ?? [];

  return (
    <details
      className={`group bg-slate-800/40 border border-slate-700 rounded-lg overflow-hidden ${className ?? ""}`}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer list-none px-4 py-2.5 flex items-center justify-between text-sm hover:bg-slate-800/70 transition-colors">
        <span className="flex items-center gap-2 text-slate-300 font-medium">
          <Brain className="w-4 h-4 text-teal-400" />
          How this was answered
        </span>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </summary>

      <div className="px-4 pb-4 pt-1 space-y-3 text-xs text-slate-400 border-t border-slate-700/50">
        {/* Search layers */}
        <div>
          <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1.5">
            <Layers className="w-3 h-3" /> Search layers
          </p>
          <ul className="space-y-1">
            {layers.map((layer, i) => (
              <li key={i} className="flex items-center gap-2 pl-1">
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full ${
                    layer.skipped ? "bg-slate-600" : (layer.hits ?? 0) > 0 ? "bg-teal-400" : "bg-amber-500"
                  }`}
                />
                <span className="text-slate-300">{layer.layer.replace(/_/g, " ")}</span>
                {layer.skipped ? (
                  <span className="text-slate-500 italic">— skipped (no API key)</span>
                ) : (
                  <span className="text-slate-500">
                    — {layer.hits ?? 0} {((layer.hits ?? 0) === 1 ? "hit" : "hits")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>

        {/* Models + signals */}
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <Stat icon={<Brain className="w-3 h-3" />} label="Synthesis" value={methodology.synthesis_model ?? "n/a"} />
          <Stat icon={<FileText className="w-3 h-3" />} label="Embeddings" value={methodology.embedding_model ?? "n/a"} />
          <Stat
            icon={<Cloud className="w-3 h-3" />}
            label="Weather context"
            value={methodology.weather_used ? "yes" : "no"}
          />
          <Stat
            icon={<Globe className="w-3 h-3" />}
            label="External provider"
            value={methodology.external_provider_configured ? "Perplexity" : "not configured"}
          />
        </div>

        {/* Sources consulted */}
        {sources.length > 0 && (
          <div>
            <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">
              Sources consulted ({sources.length})
            </p>
            <div className="flex flex-wrap gap-1">
              {sources.slice(0, 12).map((s) => (
                <span
                  key={s}
                  className="px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-300 text-[10px] border border-slate-600/60"
                >
                  {s}
                </span>
              ))}
              {sources.length > 12 && (
                <span className="px-1.5 py-0.5 text-slate-500 text-[10px]">+{sources.length - 12} more</span>
              )}
            </div>
          </div>
        )}

        {/* Result counts */}
        {(internalCount !== undefined || externalCount !== undefined) && (
          <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-700/40">
            <span>
              {internalCount ?? 0} internal articles · {externalCount ?? 0} external citations
            </span>
            {filters && Object.values(filters).some((v) => v) && (
              <span className="ml-2">
                · constraints:{" "}
                {Object.entries(filters)
                  .filter(([, v]) => v)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(", ")}
              </span>
            )}
          </div>
        )}

        {/* External-not-configured advisory */}
        {!methodology.external_provider_configured && (
          <div className="flex items-start gap-1.5 text-[11px] text-amber-400/80 bg-amber-950/20 border border-amber-900/40 rounded px-2 py-1.5">
            <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
            <span>
              External web search disabled — answer drawn only from the platform's curated corpus.
              Set <code className="text-amber-300">PERPLEXITY_API_KEY</code> to enable hybrid retrieval.
            </span>
          </div>
        )}
      </div>
    </details>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-800/60 rounded border border-slate-700/40">
      <span className="text-slate-500">{icon}</span>
      <span className="text-slate-500">{label}:</span>
      <span className="text-slate-200 font-medium truncate">{value}</span>
    </div>
  );
}
