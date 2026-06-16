"use client";

import { ExternalLink, AlertTriangle, Info } from "lucide-react";

export interface ProvenanceInfo {
  sourceName?: string;
  sourceUrl?: string;
  methodologyUrl?: string;
  methodologyVersion?: string;
  datasetYear?: string;
  uncertainty?: string;
  license?: string;
  note?: string;
}

interface ProvenanceCardProps {
  provenance: ProvenanceInfo;
  compact?: boolean;
}

export default function ProvenanceCard({ provenance, compact = false }: ProvenanceCardProps) {
  if (compact) {
    return (
      <div className="bg-slate-800/60 rounded-lg p-2 border border-slate-700/50">
        <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
          {provenance.uncertainty && (
            <span className="flex items-center gap-0.5 text-amber-400">
              <AlertTriangle className="h-2.5 w-2.5" />
              {provenance.uncertainty}
            </span>
          )}
          {provenance.sourceName && (
            <span>· {provenance.sourceName}</span>
          )}
          {provenance.sourceUrl && (
            <a
              href={provenance.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-400 hover:text-teal-300 ml-auto"
            >
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50 space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
        <Info className="h-3 w-3 text-teal-400" />
        Methodology & Provenance
      </div>

      {provenance.note && (
        <p className="text-[11px] text-slate-400 leading-relaxed">{provenance.note}</p>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px]">
        {provenance.sourceName && (
          <>
            <span className="text-slate-500">Data source</span>
            <span className="text-slate-300">{provenance.sourceName}</span>
          </>
        )}
        {provenance.datasetYear && (
          <>
            <span className="text-slate-500">Dataset year</span>
            <span className="text-slate-300">{provenance.datasetYear}</span>
          </>
        )}
        {provenance.methodologyVersion && (
          <>
            <span className="text-slate-500">Methodology</span>
            <span className="text-slate-300">{provenance.methodologyVersion}</span>
          </>
        )}
        {provenance.uncertainty && (
          <>
            <span className="text-slate-500">Uncertainty</span>
            <span className="text-amber-400 flex items-center gap-0.5">
              <AlertTriangle className="h-2.5 w-2.5" />
              {provenance.uncertainty}
            </span>
          </>
        )}
        {provenance.license && (
          <>
            <span className="text-slate-500">License</span>
            <span className="text-slate-300">{provenance.license}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-3 text-[10px]">
        {provenance.sourceUrl && (
          <a
            href={provenance.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-teal-400 hover:text-teal-300 flex items-center gap-1"
          >
            <ExternalLink className="h-2.5 w-2.5" />
            Source
          </a>
        )}
        {provenance.methodologyUrl && (
          <a
            href={provenance.methodologyUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-teal-400 hover:text-teal-300 flex items-center gap-1"
          >
            <ExternalLink className="h-2.5 w-2.5" />
            Methodology
          </a>
        )}
      </div>
    </div>
  );
}

export { ProvenanceCard };
