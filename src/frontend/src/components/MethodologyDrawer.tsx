"use client";

import { useState } from "react";
import {
  ChevronDown,
  Layers,
  Brain,
  Cloud,
  Globe,
  FileText,
  AlertCircle,
  ShieldCheck,
  ShieldAlert,
  Fingerprint,
  Route,
} from "lucide-react";
import type { DeepSearchMethodology, HallucinationCheck } from "@/types";

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

        {/* Retrieval strategy (Phase 4 wave 1) */}
        {methodology.retrieval_strategy && (
          <div className="flex items-center gap-1.5 text-[11px]">
            <Route className="w-3 h-3 text-slate-500" />
            <span className="text-slate-500">Retrieval:</span>
            <code className="text-slate-300 bg-slate-800/60 px-1.5 py-0.5 rounded text-[10px]">
              {methodology.retrieval_strategy}
            </code>
          </div>
        )}

        {/* Prompt fingerprints used (Phase 4 wave 1) */}
        {methodology.prompts_used && Object.keys(methodology.prompts_used).length > 0 && (
          <div>
            <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1.5">
              <Fingerprint className="w-3 h-3" /> Versioned prompts
            </p>
            <ul className="space-y-1">
              {Object.entries(methodology.prompts_used).map(([role, prompt]) =>
                prompt ? (
                  <li
                    key={role}
                    className="flex items-center gap-2 text-[11px] pl-1"
                    title={`fingerprint=${prompt.fingerprint}`}
                  >
                    <span className="text-slate-500">{role}:</span>
                    <code className="text-slate-300">{prompt.name}</code>
                    <span className="text-teal-400 font-mono">{prompt.version}</span>
                    <code
                      className="text-slate-500 text-[10px] font-mono truncate"
                      style={{ maxWidth: 110 }}
                    >
                      {prompt.fingerprint}
                    </code>
                  </li>
                ) : null,
              )}
            </ul>
          </div>
        )}

        {/* Hallucination grounding (Phase 6 wave 2) */}
        {methodology.hallucination_check && (
          <HallucinationBlock check={methodology.hallucination_check} />
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

function HallucinationBlock({ check }: { check: HallucinationCheck }) {
  const risk = check.hallucination_risk;
  const grounded = check.is_grounded;
  const flaggedCount = check.flagged_segments?.length ?? 0;

  // Colour the badge per severity bucket.
  const tone = grounded
    ? { wrap: "border-teal-900/40 bg-teal-950/20 text-teal-300", icon: ShieldCheck }
    : risk > 0.7
      ? { wrap: "border-red-900/40 bg-red-950/20 text-red-300", icon: ShieldAlert }
      : { wrap: "border-amber-900/40 bg-amber-950/20 text-amber-300", icon: ShieldAlert };

  const Icon = tone.icon;
  const pct = Math.round((risk ?? 0) * 100);

  return (
    <div className={`border rounded px-2 py-1.5 text-[11px] ${tone.wrap}`}>
      <div className="flex items-center gap-1.5">
        <Icon className="w-3 h-3 flex-shrink-0" />
        <span className="font-medium">
          Hallucination grounding: {grounded ? "grounded" : "weakly grounded"}
        </span>
        <span className="ml-auto font-mono">risk {pct}%</span>
      </div>
      {(check.entity_overlap_score !== undefined || check.statistic_accuracy !== undefined) && (
        <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] opacity-90">
          {check.entity_overlap_score !== undefined && (
            <span>
              entity match: {Math.round(check.entity_overlap_score * 100)}%
            </span>
          )}
          {check.statistic_accuracy !== undefined && (
            <span>
              statistic match: {Math.round(check.statistic_accuracy * 100)}%
            </span>
          )}
        </div>
      )}
      {flaggedCount > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-[10px] underline decoration-dotted opacity-80">
            {flaggedCount} flagged segment{flaggedCount === 1 ? "" : "s"} — show
          </summary>
          <ul className="mt-1 space-y-1 max-h-32 overflow-y-auto pr-1">
            {check.flagged_segments.map((f, i) => (
              <li
                key={i}
                className="pl-2 border-l border-current/30 text-[10px] opacity-95"
              >
                <span className="opacity-70 uppercase text-[9px] mr-1">{f.severity}</span>
                <span className="italic">&ldquo;{f.text}&rdquo;</span>
                <span className="opacity-70"> — {f.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
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
