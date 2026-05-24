"use client";

import { CheckCircle2, AlertTriangle, MinusCircle, Scale } from "lucide-react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { CompareResult, ComparativeAnalysisStructured } from "@/types";
import { TREND_LINE_COLORS } from "@/lib/climateColors";

interface Props {
  data: CompareResult;
}

const STRENGTH_COPY: Record<string, { label: string; tone: string; icon: React.ComponentType<any> }> = {
  balanced: { label: "Balanced evidence", tone: "text-slate-300", icon: Scale },
  topic_a_stronger: { label: "Topic A has stronger evidence", tone: "text-teal-300", icon: CheckCircle2 },
  topic_b_stronger: { label: "Topic B has stronger evidence", tone: "text-violet-300", icon: CheckCircle2 },
  weak: { label: "Both topics have weak evidence", tone: "text-amber-300", icon: AlertTriangle },
};

export default function CompareCharts({ data }: Props) {
  const structured: ComparativeAnalysisStructured | undefined = data.comparative_analysis_structured ?? undefined;

  // Coverage chart: side-by-side internal/external/citations counts
  const coverageData = [
    {
      name: "Internal articles",
      A: data.result_a.internal_articles_count ?? 0,
      B: data.result_b.internal_articles_count ?? 0,
    },
    {
      name: "External sources",
      A: data.result_a.external_sources_count ?? 0,
      B: data.result_b.external_sources_count ?? 0,
    },
    {
      name: "Citations",
      A: (data.result_a.citations || []).length,
      B: (data.result_b.citations || []).length,
    },
  ];

  return (
    <div className="space-y-4">
      {/* Headline */}
      {structured?.summary && (
        <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3.5 text-sm text-slate-200 leading-relaxed">
          {structured.summary}
        </div>
      )}

      {/* Evidence-strength badge */}
      {structured?.evidence_strength && (() => {
        const meta = STRENGTH_COPY[structured.evidence_strength] ?? STRENGTH_COPY.balanced;
        const Icon = meta.icon;
        return (
          <div className={`flex items-center gap-2 text-sm ${meta.tone} bg-slate-800/30 border border-slate-700 rounded-lg px-3 py-2`}>
            <Icon className="w-4 h-4" />
            <span className="font-medium">{meta.label}</span>
          </div>
        );
      })()}

      {/* Coverage chart */}
      <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3">
        <h4 className="text-xs uppercase tracking-wider text-slate-400 mb-2">Coverage breakdown</h4>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={coverageData}>
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} allowDecimals={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 6 }}
              labelStyle={{ color: "#cbd5e1" }}
              itemStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: "#cbd5e1" }} />
            <Bar dataKey="A" name={truncate(data.query_a)} fill={TREND_LINE_COLORS.topicA} radius={[3, 3, 0, 0]} />
            <Bar dataKey="B" name={truncate(data.query_b)} fill={TREND_LINE_COLORS.topicB} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Similarities + differences */}
      {structured && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {structured.similarities?.length > 0 && (
            <div className="bg-slate-800/40 border border-teal-800/40 rounded-lg p-3.5">
              <h4 className="text-xs uppercase tracking-wider text-teal-300 mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> Similarities
              </h4>
              <ul className="space-y-1.5 text-sm text-slate-300">
                {structured.similarities.map((s, i) => (
                  <li key={i} className="flex gap-2 leading-snug">
                    <span className="text-teal-400 flex-shrink-0">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {structured.differences?.length > 0 && (
            <div className="bg-slate-800/40 border border-violet-800/40 rounded-lg p-3.5">
              <h4 className="text-xs uppercase tracking-wider text-violet-300 mb-2 flex items-center gap-1.5">
                <MinusCircle className="w-3.5 h-3.5" /> Differences
              </h4>
              <ul className="space-y-1.5 text-sm text-slate-300">
                {structured.differences.map((s, i) => (
                  <li key={i} className="flex gap-2 leading-snug">
                    <span className="text-violet-400 flex-shrink-0">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Common gaps */}
      {structured?.common_gaps && structured.common_gaps.length > 0 && (
        <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-3.5">
          <h4 className="text-xs uppercase tracking-wider text-amber-300 mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> Common gaps
          </h4>
          <ul className="space-y-1 text-sm text-amber-100/80">
            {structured.common_gaps.map((s, i) => (
              <li key={i} className="flex gap-2 leading-snug">
                <span className="text-amber-400 flex-shrink-0">•</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function truncate(s: string, n = 28) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
