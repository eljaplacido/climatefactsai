"use client";

import { useState } from "react";
import clsx from "clsx";
import { ChevronDown, ChevronUp, ExternalLink, FileText, Search, CheckCircle, XCircle, Minus } from "lucide-react";
import type { EvidenceChainLink } from "../types";

interface EvidenceChainProps {
  claim: string;
  evidenceChain: EvidenceChainLink[];
  verdict: string;
  confidence: number;
}

function getSupportIcon(supports: boolean | null) {
  if (supports === true) return <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />;
  if (supports === false) return <XCircle className="h-3.5 w-3.5 text-red-500" />;
  return <Minus className="h-3.5 w-3.5 text-gray-400" />;
}

function getSupportLabel(supports: boolean | null) {
  if (supports === true) return "Supports";
  if (supports === false) return "Contradicts";
  return "Neutral";
}

function getVerdictColor(verdict: string) {
  switch (verdict) {
    case "verified": case "VERIFIED": return "bg-emerald-50 border-emerald-200 text-emerald-700";
    case "disputed": case "DISPUTED": case "FALSE": return "bg-red-50 border-red-200 text-red-700";
    case "partially_true": case "PARTIALLY_VERIFIED": return "bg-yellow-50 border-yellow-200 text-yellow-700";
    default: return "bg-gray-50 border-gray-200 text-gray-700";
  }
}

function EvidenceChain({ claim, evidenceChain, verdict, confidence }: EvidenceChainProps) {
  const [expanded, setExpanded] = useState(false);

  if (!evidenceChain || evidenceChain.length === 0) {
    return null;
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center space-x-2">
          <Search className="h-4 w-4 text-clilens-primary" />
          <span className="text-sm font-medium text-gray-700">
            Evidence Chain ({evidenceChain.length} sources)
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="p-4">
          {/* Claim node */}
          <div className="flex items-start space-x-3 mb-1">
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                <FileText className="h-4 w-4 text-blue-600" />
              </div>
              <div className="w-px h-4 bg-gray-300" />
            </div>
            <div className="flex-1 pt-1">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Claim</p>
              <p className="text-sm text-gray-800 line-clamp-2">{claim}</p>
            </div>
          </div>

          {/* Evidence nodes */}
          {evidenceChain.map((link, idx) => (
            <div key={idx} className="flex items-start space-x-3 mb-1">
              <div className="flex flex-col items-center">
                <div className="w-px h-2 bg-gray-300" />
                <div className={clsx(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold",
                  link.supports_claim === true ? "bg-emerald-100 text-emerald-700" :
                  link.supports_claim === false ? "bg-red-100 text-red-700" :
                  "bg-gray-100 text-gray-600"
                )}>
                  {link.step_number}
                </div>
                {idx < evidenceChain.length - 1 && (
                  <div className="w-px h-4 bg-gray-300" />
                )}
                {idx === evidenceChain.length - 1 && (
                  <div className="w-px h-4 bg-gray-300" />
                )}
              </div>
              <div className="flex-1 pt-2">
                <div className="bg-white border border-gray-100 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    {link.source_url ? (
                      <a
                        href={link.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-semibold text-clilens-primary hover:text-clilens-teal-700 hover:underline inline-flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {link.source}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-xs font-semibold text-gray-600">{link.source}</span>
                    )}
                    <div className="flex items-center space-x-1.5">
                      {getSupportIcon(link.supports_claim)}
                      <span className="text-[10px] text-gray-500">{getSupportLabel(link.supports_claim)}</span>
                    </div>
                  </div>
                  <p className="text-sm text-gray-700">{link.description}</p>
                  <div className="flex items-center justify-between mt-2">
                    <div className="flex items-center space-x-1">
                      <div className="w-16 bg-gray-100 rounded-full h-1">
                        <div
                          className="h-1 rounded-full bg-clilens-primary"
                          style={{ width: `${Math.round(link.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-400">{Math.round(link.confidence * 100)}%</span>
                    </div>
                    {link.source_url && (
                      <a
                        href={link.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-clilens-primary hover:underline inline-flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <span className="truncate max-w-[120px]">
                          {(() => { try { return new URL(link.source_url).hostname; } catch { return "Source"; } })()}
                        </span>
                        <ExternalLink className="h-3 w-3 flex-shrink-0" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Verdict node */}
          <div className="flex items-start space-x-3">
            <div className="flex flex-col items-center">
              <div className="w-px h-2 bg-gray-300" />
              <div className={clsx(
                "w-8 h-8 rounded-full flex items-center justify-center border-2",
                getVerdictColor(verdict)
              )}>
                {verdict === "verified" || verdict === "VERIFIED" ? (
                  <CheckCircle className="h-4 w-4" />
                ) : verdict === "disputed" || verdict === "DISPUTED" || verdict === "FALSE" ? (
                  <XCircle className="h-4 w-4" />
                ) : (
                  <Minus className="h-4 w-4" />
                )}
              </div>
            </div>
            <div className="flex-1 pt-2">
              <div className={clsx("rounded-lg border px-3 py-2", getVerdictColor(verdict))}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide">Verdict: {verdict}</span>
                  <span className="text-xs font-bold">{Math.round(confidence * 100)}% confidence</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EvidenceChain;
