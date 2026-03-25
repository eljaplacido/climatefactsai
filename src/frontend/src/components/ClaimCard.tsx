"use client";

import { useState } from "react";
import clsx from "clsx";
import {
  ChevronDown,
  ChevronUp,
  Beaker,
  BarChart3,
  Scale,
  Eye,
  TrendingUp,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";
import type { ClaimDetail, DecomposedConfidence } from "../types";
import FactCheckBadge from "./FactCheckBadge";
import EvidenceChain from "./EvidenceChain";
import Markdown from "./Markdown";

interface ClaimCardProps {
  claim: ClaimDetail;
  index: number;
}

const CATEGORY_CONFIG: Record<string, { icon: any; label: string; color: string; bg: string }> = {
  scientific_causal: {
    icon: Beaker,
    label: "Scientific/Causal",
    color: "text-purple-700",
    bg: "bg-purple-50 border-purple-200",
  },
  statistical: {
    icon: BarChart3,
    label: "Statistical",
    color: "text-blue-700",
    bg: "bg-blue-50 border-blue-200",
  },
  policy: {
    icon: Scale,
    label: "Policy",
    color: "text-amber-700",
    bg: "bg-amber-50 border-amber-200",
  },
  anecdotal: {
    icon: Eye,
    label: "Anecdotal",
    color: "text-gray-700",
    bg: "bg-gray-50 border-gray-200",
  },
  predictive: {
    icon: TrendingUp,
    label: "Predictive",
    color: "text-cyan-700",
    bg: "bg-cyan-50 border-cyan-200",
  },
};

function getConfidenceColor(score: number): string {
  if (score >= 0.75) return "from-emerald-400 to-emerald-500";
  if (score >= 0.50) return "from-amber-400 to-amber-500";
  return "from-red-400 to-red-500";
}

function DecomposedBars({ dc }: { dc: DecomposedConfidence }) {
  const factors = [
    { key: "model_confidence", label: "AI Confidence", value: dc.model_confidence },
    { key: "source_quality", label: "Source Quality", value: dc.source_quality },
    { key: "evidence_breadth", label: "Evidence Breadth", value: dc.evidence_breadth },
    { key: "cross_reference_score", label: "Cross-Reference", value: dc.cross_reference_score },
    { key: "temporal_relevance", label: "Recency", value: dc.temporal_relevance },
  ];

  return (
    <div className="grid grid-cols-5 gap-2">
      {factors.map((f) => (
        <div key={f.key} className="text-center">
          <div className="w-full bg-gray-100 rounded-full h-1 mb-1">
            <div
              className="h-1 rounded-full bg-clilens-primary transition-all"
              style={{ width: `${Math.round(f.value * 100)}%` }}
            />
          </div>
          <span className="text-[9px] text-gray-500 leading-tight block">{f.label}</span>
          <span className="text-[10px] font-semibold text-gray-700">{Math.round(f.value * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function ClaimCard({ claim, index }: ClaimCardProps) {
  const [expanded, setExpanded] = useState(false);

  const category = claim.claim_category || "statistical";
  const catConfig = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.statistical;
  const CatIcon = catConfig.icon;

  const confidence = claim.fact_check?.confidence_score ?? 0;
  const verdict = claim.fact_check?.verification_status ?? "UNKNOWN";
  const dc = claim.fact_check?.decomposed_confidence;
  const chain = claim.fact_check?.evidence_chain;

  return (
    <div className={clsx(
      "border rounded-xl overflow-hidden transition-all",
      expanded ? "border-clilens-teal-200 shadow-md" : "border-gray-200 shadow-sm"
    )}>
      {/* Header - always visible */}
      <div className="p-4 bg-white">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-bold text-gray-400">#{index + 1}</span>
            <div className={clsx("inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium border", catConfig.bg, catConfig.color)}>
              <CatIcon className="h-3 w-3" />
              <span>{catConfig.label}</span>
            </div>
          </div>
          {claim.fact_check && (
            <FactCheckBadge factCheck={claim.fact_check} size="sm" />
          )}
        </div>

        <p className="text-sm text-gray-800 font-medium leading-relaxed mb-3">
          &ldquo;{claim.claim_text}&rdquo;
        </p>

        {/* Confidence bar */}
        <div className="flex items-center space-x-3 mb-2">
          <div className="flex-1 bg-gray-100 rounded-full h-2">
            <div
              className={clsx("h-2 rounded-full bg-gradient-to-r transition-all duration-500", getConfidenceColor(confidence))}
              style={{ width: `${Math.round(confidence * 100)}%` }}
            />
          </div>
          <span className="text-sm font-semibold text-gray-700 w-12 text-right">
            {Math.round(confidence * 100)}%
          </span>
        </div>

        {/* Decomposed confidence mini bars */}
        {dc && <DecomposedBars dc={dc} />}

        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 flex items-center text-sm text-clilens-primary hover:text-clilens-teal-700 font-medium"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-4 w-4 mr-1" />
              Hide details
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4 mr-1" />
              View evidence &amp; details
              {chain && chain.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 bg-gray-100 rounded text-[10px] text-gray-500">
                  {chain.length} sources
                </span>
              )}
            </>
          )}
        </button>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50 p-4 space-y-4">
          {/* Context */}
          {claim.claim_context && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Context</h4>
              <p className="text-sm text-gray-600 italic">{claim.claim_context}</p>
            </div>
          )}

          {/* Justification */}
          {claim.fact_check?.justification && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Verification Summary</h4>
              {claim.fact_check.justification.includes("temporarily unavailable") || claim.fact_check.justification.includes("Verification error") ? (
                <div className="bg-amber-50 rounded-lg p-3 border border-amber-200 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-700">{claim.fact_check.justification}</p>
                </div>
              ) : (
                <div className="bg-white rounded-lg p-3 border border-gray-200">
                  <Markdown content={claim.fact_check.justification} />
                </div>
              )}
            </div>
          )}

          {/* Evidence Sources — traceable hyperlinks */}
          {chain && chain.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Evidence Sources</h4>
              <div className="space-y-1.5">
                {chain.filter(link => link.source_url).map((link, idx) => (
                  <a
                    key={idx}
                    href={link.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-clilens-primary hover:text-clilens-teal-700 hover:underline"
                  >
                    <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate">{link.source || new URL(link.source_url).hostname}</span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0">
                      {Math.round(link.confidence * 100)}% confidence
                    </span>
                  </a>
                ))}
                {chain.filter(link => !link.source_url).length > 0 && (
                  <p className="text-xs text-gray-400 italic">
                    {chain.filter(link => !link.source_url).length} source(s) without direct URL
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Evidence Chain */}
          {chain && chain.length > 0 && (
            <EvidenceChain
              claim={claim.claim_text}
              evidenceChain={chain}
              verdict={verdict}
              confidence={confidence}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default ClaimCard;
