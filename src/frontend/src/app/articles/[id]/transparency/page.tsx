"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Beaker,
  Search,
  Scale,
  ExternalLink,
  CheckCircle,
  XCircle,
  Minus,
  ShieldCheck,
  GitBranch,
  BarChart3,
  Info,
  FlaskConical,
  HelpCircle,
  AlertTriangle,
  TrendingUp,
} from "lucide-react";
import type { DecomposedConfidence, EvidenceChainLink } from "@/types";

/* ---------- local types for the transparency API response ---------- */

interface MethodologyStep {
  method: string;
  model?: string;
  sources?: string[];
  description: string;
}

interface ReliabilityFactor {
  label: string;
  score: number;
  weight: number;
  weighted_score: number;
}

interface ClaimTransparency {
  claim_text: string;
  verdict: string;
  confidence_score: number;
  evidence_chain: EvidenceChainLink[];
  justification: string;
}

interface SourceProfileTransparency {
  source_name: string;
  credibility_score: number;
  reliability_tier: string;
  editorial_standards: string;
}

interface CausalAnalysis {
  [key: string]: unknown;
}

interface TransparencyData {
  article_id: string;
  title: string;
  methodology: Record<string, MethodologyStep>;
  reliability_breakdown: Record<string, ReliabilityFactor>;
  decomposed_confidence: DecomposedConfidence;
  claims: ClaimTransparency[];
  source_profile: SourceProfileTransparency;
  causal_analysis?: CausalAnalysis | null;
}

/* ---------- helpers ---------- */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

function pct(v: number | null | undefined): number {
  if (v == null || isNaN(v)) return 0;
  return Math.round(v * 100);
}

function scoreColor(pctValue: number): string {
  if (pctValue > 70) return "bg-emerald-500";
  if (pctValue >= 40) return "bg-amber-500";
  if (pctValue > 0) return "bg-red-500";
  return "bg-gray-300";
}

function scoreGradient(pctValue: number): string {
  if (pctValue > 70) return "from-emerald-400 to-emerald-600";
  if (pctValue >= 40) return "from-amber-400 to-amber-600";
  if (pctValue > 0) return "from-red-400 to-red-600";
  return "from-gray-300 to-gray-400";
}

function scoreTextColor(pctValue: number): string {
  if (pctValue > 70) return "text-emerald-700";
  if (pctValue >= 40) return "text-amber-700";
  if (pctValue > 0) return "text-red-700";
  return "text-gray-500";
}

function scoreBgLight(pctValue: number): string {
  if (pctValue > 70) return "bg-emerald-50 border-emerald-200";
  if (pctValue >= 40) return "bg-amber-50 border-amber-200";
  if (pctValue > 0) return "bg-red-50 border-red-200";
  return "bg-gray-50 border-gray-200";
}

function scoreLabel(pctValue: number): string {
  if (pctValue > 70) return "Strong";
  if (pctValue >= 40) return "Moderate";
  if (pctValue > 0) return "Weak";
  return "N/A";
}

function confidenceGradient(score: number): string {
  const p = pct(score);
  if (p > 70) return "from-emerald-400 to-emerald-500";
  if (p >= 40) return "from-amber-400 to-amber-500";
  return "from-red-400 to-red-500";
}

function tierBadge(tier: string): { label: string; bg: string; text: string } {
  switch (tier.toLowerCase()) {
    case "research":
    case "academic":
      return { label: "Research", bg: "bg-purple-100", text: "text-purple-700" };
    case "mainstream":
    case "major":
      return { label: "Mainstream", bg: "bg-blue-100", text: "text-blue-700" };
    case "government":
    case "official":
      return { label: "Official", bg: "bg-emerald-100", text: "text-emerald-700" };
    case "independent":
      return { label: "Independent", bg: "bg-amber-100", text: "text-amber-700" };
    case "blog":
    case "social":
      return { label: "Blog/Social", bg: "bg-red-100", text: "text-red-700" };
    default:
      return { label: tier, bg: "bg-gray-100", text: "text-gray-700" };
  }
}

function supportIcon(supports: boolean | null) {
  if (supports === true) return <CheckCircle className="h-4 w-4 text-emerald-500" />;
  if (supports === false) return <XCircle className="h-4 w-4 text-red-500" />;
  return <Minus className="h-4 w-4 text-gray-400" />;
}

function supportLabel(supports: boolean | null): string {
  if (supports === true) return "Supports";
  if (supports === false) return "Contradicts";
  return "Neutral";
}

/** Metric explanation text */
const METRIC_EXPLANATIONS: Record<string, string> = {
  model_confidence: "How confident the AI model is in its assessment based on text analysis and pattern recognition.",
  source_quality: "Rating of the publishing source's track record, editorial standards, and journalistic practices.",
  evidence_breadth: "How many independent sources and data points corroborate the claims in this article.",
  cross_reference_score: "Degree to which claims are supported by cross-referencing against known databases and fact-check repositories.",
  temporal_relevance: "How current and timely the evidence and data cited in this article are.",
};

const RELIABILITY_EXPLANATIONS: Record<string, string> = {
  source_credibility: "Overall trustworthiness of the publisher based on historical accuracy and editorial reputation.",
  editorial_standards: "Quality of editorial processes including fact-checking, corrections policy, and transparency.",
  citation_quality: "Strength and relevance of scientific citations and references used to support claims.",
  consistency: "Internal consistency of claims and alignment with established scientific consensus.",
  claim_verification: "Proportion of verifiable claims that have been confirmed through independent evidence.",
};

/** Reason a metric might be missing */
const MISSING_REASONS: Record<string, string> = {
  model_confidence: "AI analysis has not been completed for this article yet.",
  source_quality: "Source credibility data is not available for this publisher.",
  evidence_breadth: "Evidence gathering is still in progress or no corroborating sources were found.",
  cross_reference_score: "Cross-referencing against fact-check databases has not been performed.",
  temporal_relevance: "Temporal analysis data is pending.",
  source_credibility: "This publisher has not been profiled in our source database yet.",
  editorial_standards: "Editorial standards assessment is pending for this source.",
  citation_quality: "Citation analysis requires additional processing time.",
  consistency: "Consistency checking has not been performed for this article.",
  claim_verification: "Claim verification is pending or no verifiable claims were detected.",
};

/* ---------- Data availability badge ---------- */

function DataNotAvailable({ metricKey, articleId, onTrigger }: { metricKey: string; articleId?: string; onTrigger?: () => void }) {
  const reason = MISSING_REASONS[metricKey] || "This metric has not been analyzed yet.";
  return (
    <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50 border border-amber-200 rounded-lg">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center mt-0.5">
        <AlertTriangle className="h-4 w-4 text-amber-500" />
      </div>
      <div className="flex-1">
        <p className="text-sm font-semibold text-amber-800">Not yet analyzed</p>
        <p className="text-xs text-amber-600 mt-1 leading-relaxed">{reason}</p>
        {onTrigger && (
          <button
            onClick={onTrigger}
            className="mt-2 px-3 py-1.5 text-xs font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-md transition-colors inline-flex items-center gap-1.5"
          >
            <TrendingUp className="h-3 w-3" />
            Analyze Now
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------- Scoring legend ---------- */

function ScoringLegend() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Info className="h-4 w-4 text-teal-600" />
        <h3 className="text-sm font-semibold text-gray-800">Scoring System</h3>
      </div>
      <div className="flex flex-wrap gap-4 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-8 h-2.5 rounded-full bg-emerald-500" />
          <span className="text-gray-600">
            <span className="font-medium text-emerald-700">Strong</span> (&gt;70%)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-2.5 rounded-full bg-amber-500" />
          <span className="text-gray-600">
            <span className="font-medium text-amber-700">Moderate</span> (40-70%)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-2.5 rounded-full bg-red-500" />
          <span className="text-gray-600">
            <span className="font-medium text-red-700">Weak</span> (&lt;40%)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-2.5 rounded-full bg-gray-300" />
          <span className="text-gray-600">
            <span className="font-medium text-gray-500">N/A</span> (not analyzed)
          </span>
        </div>
      </div>
    </div>
  );
}

/* ---------- Overall assessment card ---------- */

function OverallAssessment({ data }: { data: TransparencyData }) {
  // Count available metrics
  const confidenceDims = ["model_confidence", "source_quality", "evidence_breadth", "cross_reference_score", "temporal_relevance"] as const;
  const availableConfidence = confidenceDims.filter(
    (k) => data.decomposed_confidence && data.decomposed_confidence[k] != null && data.decomposed_confidence[k] > 0
  ).length;

  const reliabilityCount = data.reliability_breakdown ? Object.keys(data.reliability_breakdown).length : 0;
  const reliabilityAvailable = data.reliability_breakdown
    ? Object.values(data.reliability_breakdown).filter((f) => f.score > 0).length
    : 0;

  const claimsCount = data.claims?.length || 0;
  const hasSource = data.source_profile && data.source_profile.source_name;
  const hasMethodology = data.methodology && Object.keys(data.methodology).length > 0;

  const totalMetrics = confidenceDims.length + reliabilityCount + (claimsCount > 0 ? 1 : 0) + (hasSource ? 1 : 0) + (hasMethodology ? 1 : 0);
  const availableMetrics = availableConfidence + reliabilityAvailable + (claimsCount > 0 ? 1 : 0) + (hasSource ? 1 : 0) + (hasMethodology ? 1 : 0);

  const overallScore = data.decomposed_confidence?.overall;
  const overallPct = pct(overallScore);
  const isFullyAnalyzed = availableMetrics >= totalMetrics - 1; // allow one missing
  const isMostlyMissing = availableMetrics < totalMetrics / 2;
  const completionPct = totalMetrics > 0 ? Math.round((availableMetrics / totalMetrics) * 100) : 0;

  return (
    <div className={`rounded-xl p-5 border shadow-sm ${
      isFullyAnalyzed
        ? "bg-gradient-to-r from-teal-50 to-emerald-50 border-teal-200"
        : isMostlyMissing
        ? "bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200"
        : "bg-gradient-to-r from-slate-50 to-gray-50 border-slate-200"
    }`}>
      <div className="flex items-start gap-4">
        <div className={`flex-shrink-0 w-14 h-14 rounded-full flex items-center justify-center ${
          isFullyAnalyzed ? "bg-teal-100" : isMostlyMissing ? "bg-amber-100" : "bg-slate-200"
        }`}>
          {overallScore != null && overallScore > 0 ? (
            <span className={`text-xl font-bold ${scoreTextColor(overallPct)}`}>{overallPct}%</span>
          ) : (
            <AlertTriangle className={`h-6 w-6 ${isMostlyMissing ? "text-amber-500" : "text-slate-400"}`} />
          )}
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-bold text-gray-900 mb-1">Overall Assessment</h2>

          {isMostlyMissing ? (
            <div className="bg-amber-100 border border-amber-300 rounded-lg px-4 py-3 mb-3">
              <p className="text-sm font-semibold text-amber-800">
                Analysis in progress &mdash; limited data available
              </p>
              <p className="text-xs text-amber-700 mt-1">
                Only {availableMetrics} of {totalMetrics} metrics have been computed so far.
                Sections marked &ldquo;Not yet analyzed&rdquo; are still being processed.
                Results will improve as more data becomes available.
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-600 mb-2">
              {isFullyAnalyzed
                ? `This article has been fully analyzed. ${availableMetrics} of ${totalMetrics} metrics are available.`
                : `This article has been partially analyzed. ${availableMetrics} of ${totalMetrics} metrics are available.`}
            </p>
          )}

          {/* Analysis completion progress */}
          <div className="mb-2">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Analysis completion</span>
              <span className="font-semibold">{completionPct}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all duration-700 ${
                  completionPct >= 80 ? "bg-emerald-500" : completionPct >= 40 ? "bg-amber-500" : "bg-red-400"
                }`}
                style={{ width: `${completionPct}%` }}
              />
            </div>
          </div>

          {overallScore != null && overallScore > 0 && (
            <div className="flex items-center gap-3 mt-3">
              <div className="flex-1 bg-gray-200 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-2.5 rounded-full bg-gradient-to-r ${scoreGradient(overallPct)} transition-all duration-700`}
                  style={{ width: `${overallPct}%` }}
                />
              </div>
              <span className={`text-sm font-bold ${scoreTextColor(overallPct)}`}>
                {scoreLabel(overallPct)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- sub-components ---------- */

function MethodologySection({ methodology }: { methodology: Record<string, MethodologyStep> }) {
  const STEP_ICONS: Record<string, typeof Beaker> = {
    claim_extraction: FlaskConical,
    evidence_retrieval: Search,
    verdict_adjudication: Scale,
  };

  const STEP_LABELS: Record<string, string> = {
    claim_extraction: "Claim Extraction",
    evidence_retrieval: "Evidence Retrieval",
    verdict_adjudication: "Verdict Adjudication",
  };

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <Beaker className="h-5 w-5 text-clilens-primary" />
        <h2 className="text-lg font-semibold text-gray-900">Methodology</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Object.entries(methodology).map(([key, step]) => {
          const Icon = STEP_ICONS[key] || Beaker;
          const label = STEP_LABELS[key] || key.replace(/_/g, " ");
          return (
            <div
              key={key}
              className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-clilens-teal-50 flex items-center justify-center">
                  <Icon className="h-4 w-4 text-clilens-primary" />
                </div>
                <h3 className="text-sm font-semibold text-gray-800 capitalize">{label}</h3>
              </div>
              <p className="text-sm text-gray-600 leading-relaxed mb-3">{step.description}</p>
              <div className="space-y-1.5 text-xs text-gray-500">
                <p>
                  <span className="font-medium text-gray-700">Method:</span> {step.method}
                </p>
                {step.model && (
                  <p>
                    <span className="font-medium text-gray-700">Model:</span> {step.model}
                  </p>
                )}
                {step.sources && step.sources.length > 0 && (
                  <p>
                    <span className="font-medium text-gray-700">Sources:</span>{" "}
                    {step.sources.join(", ")}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ReliabilitySection({
  breakdown,
}: {
  breakdown: Record<string, ReliabilityFactor>;
}) {
  const sorted = Object.entries(breakdown).sort(
    ([, a], [, b]) => b.weighted_score - a.weighted_score
  );

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <ShieldCheck className="h-5 w-5 text-clilens-primary" />
        <h2 className="text-lg font-semibold text-gray-900">Reliability Breakdown</h2>
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-5">
        {sorted.map(([key, factor]) => {
          const score = pct(factor.score);
          const hasData = score > 0;
          const explanation = RELIABILITY_EXPLANATIONS[key] || `Measures the ${factor.label.toLowerCase()} of the article.`;

          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-gray-800">{factor.label}</span>
                {hasData && (
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>Weight: {pct(factor.weight)}%</span>
                    <span className={`font-bold text-sm ${scoreTextColor(score)}`}>{score}%</span>
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-500 mb-2">{explanation}</p>
              {hasData ? (
                <>
                  <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                    <div
                      className={`h-3 rounded-full bg-gradient-to-r ${scoreGradient(score)} transition-all duration-700`}
                      style={{ width: `${Math.max(score, 4)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className={`text-[11px] font-medium ${scoreTextColor(score)}`}>
                      {scoreLabel(score)}
                    </span>
                    <span className="text-[11px] text-gray-400">
                      Weighted contribution: {pct(factor.weighted_score)}%
                    </span>
                  </div>
                </>
              ) : (
                <DataNotAvailable metricKey={key} />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ConfidenceSection({ confidence }: { confidence: DecomposedConfidence }) {
  const dimensions = [
    { key: "model_confidence" as const, label: "AI Model Confidence", color: "from-cyan-400 to-cyan-600" },
    { key: "source_quality" as const, label: "Source Quality", color: "from-emerald-400 to-emerald-600" },
    { key: "evidence_breadth" as const, label: "Evidence Breadth", color: "from-violet-400 to-violet-600" },
    { key: "cross_reference_score" as const, label: "Cross-Reference", color: "from-rose-400 to-rose-600" },
    { key: "temporal_relevance" as const, label: "Temporal Relevance", color: "from-orange-400 to-orange-600" },
  ];

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="h-5 w-5 text-clilens-primary" />
        <h2 className="text-lg font-semibold text-gray-900">Confidence Intervals</h2>
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        {/* Overall score */}
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-100">
          <div className={`text-3xl font-bold ${
            pct(confidence.overall) > 0 ? scoreTextColor(pct(confidence.overall)) : "text-gray-400"
          }`}>
            {pct(confidence.overall) > 0 ? `${pct(confidence.overall)}%` : "N/A"}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700">Overall Confidence</p>
            <p className="text-xs text-gray-500">Composite of all sub-dimensions</p>
          </div>
        </div>

        {/* Dimension bars */}
        <div className="space-y-5">
          {dimensions.map((dim) => {
            const rawValue = confidence[dim.key];
            const hasData = rawValue != null && rawValue > 0;
            const value = rawValue ?? 0;
            const pctVal = pct(value);
            const explanation = METRIC_EXPLANATIONS[dim.key] || "";

            return (
              <div key={dim.key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-bold text-gray-800">{dim.label}</span>
                  {hasData && (
                    <span className={`text-sm font-bold ${scoreTextColor(pctVal)}`}>{pctVal}%</span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mb-2">{explanation}</p>
                {hasData ? (
                  <>
                    <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                      <div
                        className={`h-3 rounded-full bg-gradient-to-r ${dim.color} transition-all duration-700`}
                        style={{ width: `${pctVal}%` }}
                      />
                    </div>
                    <p className={`text-[11px] font-medium mt-1 ${scoreTextColor(pctVal)}`}>
                      {scoreLabel(pctVal)}
                    </p>
                  </>
                ) : (
                  <DataNotAvailable metricKey={dim.key} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function EvidenceChainSection({ claims }: { claims: ClaimTransparency[] }) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="h-5 w-5 text-clilens-primary" />
        <h2 className="text-lg font-semibold text-gray-900">Evidence Chains</h2>
      </div>
      <div className="space-y-6">
        {claims.map((claim, ci) => (
          <div
            key={ci}
            className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm"
          >
            {/* Claim header */}
            <div className="p-5 border-b border-gray-100">
              <div className="flex items-start justify-between gap-3 mb-2">
                <p className="text-sm font-medium text-gray-800 leading-relaxed flex-1">
                  <span className="text-xs font-bold text-gray-400 mr-2">Claim #{ci + 1}</span>
                  &ldquo;{claim.claim_text}&rdquo;
                </p>
                <span
                  className={`flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${
                    claim.verdict === "verified" || claim.verdict === "VERIFIED"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : claim.verdict === "disputed" || claim.verdict === "DISPUTED" || claim.verdict === "FALSE"
                      ? "bg-red-50 text-red-700 border border-red-200"
                      : "bg-amber-50 text-amber-700 border border-amber-200"
                  }`}
                >
                  {claim.verdict}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-100 rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full bg-gradient-to-r ${confidenceGradient(claim.confidence_score)} transition-all duration-500`}
                    style={{ width: `${pct(claim.confidence_score)}%` }}
                  />
                </div>
                <span className={`text-sm font-bold w-14 text-right ${scoreTextColor(pct(claim.confidence_score))}`}>
                  {pct(claim.confidence_score)}%
                </span>
              </div>
              {claim.justification && (
                <p className="mt-3 text-sm text-gray-600 leading-relaxed">{claim.justification}</p>
              )}
            </div>

            {/* Evidence chain links */}
            {claim.evidence_chain && claim.evidence_chain.length > 0 ? (
              <div className="p-5 bg-gray-50 space-y-3">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Evidence Trail ({claim.evidence_chain.length} sources)
                </p>
                {claim.evidence_chain.map((link, li) => (
                  <div key={li} className="flex items-start gap-3">
                    {/* Step connector */}
                    <div className="flex flex-col items-center pt-1">
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                          link.supports_claim === true
                            ? "bg-emerald-100 text-emerald-700"
                            : link.supports_claim === false
                            ? "bg-red-100 text-red-700"
                            : "bg-gray-200 text-gray-600"
                        }`}
                      >
                        {link.step_number}
                      </div>
                      {li < claim.evidence_chain.length - 1 && (
                        <div className="w-px h-full min-h-[16px] bg-gray-300 mt-1" />
                      )}
                    </div>

                    {/* Link content */}
                    <div className="flex-1 bg-white border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        {link.source_url ? (
                          <a
                            href={link.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-semibold text-clilens-primary hover:text-clilens-teal-700 hover:underline inline-flex items-center gap-1.5"
                          >
                            {link.source || (() => { try { return new URL(link.source_url).hostname; } catch { return "Source"; } })()}
                            <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                          </a>
                        ) : (
                          <span className="text-sm font-semibold text-gray-700">{link.source}</span>
                        )}
                        <div className="flex items-center gap-1.5">
                          {supportIcon(link.supports_claim)}
                          <span className="text-xs text-gray-500">{supportLabel(link.supports_claim)}</span>
                        </div>
                      </div>
                      <p className="text-sm text-gray-600 leading-relaxed">{link.description}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <div className="w-20 bg-gray-100 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${scoreColor(pct(link.confidence))}`}
                            style={{ width: `${pct(link.confidence)}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-gray-400">
                          {pct(link.confidence)}% confidence
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-5 bg-gray-50">
                <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center mt-0.5">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-amber-800">Evidence chain not yet available</p>
                    <p className="text-xs text-amber-600 mt-1 leading-relaxed">
                      Evidence gathering for this claim is still in progress, or no corroborating sources were found. This section will update automatically once evidence retrieval completes.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function SourceProfileSection({ profile }: { profile: SourceProfileTransparency }) {
  const tier = tierBadge(profile.reliability_tier);
  const credPct = pct(profile.credibility_score);
  const hasCredibility = credPct > 0;

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <Info className="h-5 w-5 text-clilens-primary" />
        <h2 className="text-lg font-semibold text-gray-900">Source Profile</h2>
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-4 mb-4">
          <h3 className="text-base font-semibold text-gray-900">{profile.source_name}</h3>
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${tier.bg} ${tier.text}`}>
            {tier.label}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className={`rounded-lg p-3 border ${hasCredibility ? scoreBgLight(credPct) : "bg-slate-50 border-slate-200"}`}>
            <p className="text-xs text-gray-500 mb-1 font-medium">Credibility Score</p>
            {hasCredibility ? (
              <>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2.5">
                    <div
                      className={`h-2.5 rounded-full bg-gradient-to-r ${scoreGradient(credPct)}`}
                      style={{ width: `${credPct}%` }}
                    />
                  </div>
                  <span className={`text-sm font-bold ${scoreTextColor(credPct)}`}>{credPct}%</span>
                </div>
                <p className={`text-[11px] mt-1 ${scoreTextColor(credPct)}`}>{scoreLabel(credPct)}</p>
              </>
            ) : (
              <div className="flex items-center gap-1.5 mt-1">
                <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-xs text-slate-400">Not yet assessed</span>
              </div>
            )}
          </div>
          <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
            <p className="text-xs text-gray-500 mb-1 font-medium">Editorial Standards</p>
            {profile.editorial_standards && profile.editorial_standards !== "unknown" ? (
              <p className="text-sm font-semibold text-gray-800 capitalize">{profile.editorial_standards}</p>
            ) : (
              <div className="flex items-center gap-1.5 mt-1">
                <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-xs text-slate-400">Assessment pending</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function CausalAnalysisSection({ analysis }: { analysis: CausalAnalysis }) {
  const entries = Object.entries(analysis);
  if (entries.length === 0) return null;

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="h-5 w-5 text-purple-600" />
        <h2 className="text-lg font-semibold text-gray-900">Causal Analysis</h2>
      </div>
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-5">
        <div className="space-y-3">
          {entries.map(([key, value]) => (
            <div key={key} className="bg-white/80 rounded-lg p-4 border border-purple-100">
              <h4 className="text-sm font-semibold text-purple-800 capitalize mb-1">
                {key.replace(/_/g, " ")}
              </h4>
              <p className="text-sm text-gray-700 leading-relaxed">
                {typeof value === "string"
                  ? value
                  : typeof value === "number"
                  ? String(value)
                  : JSON.stringify(value, null, 2)}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- main page ---------- */

export default function TransparencyPage() {
  const params = useParams();
  const articleId = params?.id as string;

  const [data, setData] = useState<TransparencyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!articleId) return;

    let cancelled = false;

    async function fetchTransparency() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `${API_BASE}/api/v2/articles/${encodeURIComponent(articleId)}/transparency`
        );
        if (!res.ok) {
          throw new Error(
            res.status === 404
              ? "Transparency report not found for this article."
              : `Failed to load transparency data (${res.status}).`
          );
        }
        const json = (await res.json()) as TransparencyData;
        if (!cancelled) setData(json);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "An unexpected error occurred.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchTransparency();
    return () => {
      cancelled = true;
    };
  }, [articleId]);

  /* ---- loading state ---- */
  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-24 flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 text-clilens-primary animate-spin" />
        <p className="text-sm text-gray-500">Loading transparency report...</p>
      </div>
    );
  }

  /* ---- error state ---- */
  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto py-16 px-4">
        <Link
          href={`/articles/${articleId}`}
          className="inline-flex items-center gap-1 text-sm text-clilens-primary hover:underline mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to article
        </Link>
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <h2 className="text-base font-semibold text-red-800 mb-1">
              Could not load transparency report
            </h2>
            <p className="text-sm text-red-700">{error || "No data returned."}</p>
          </div>
        </div>
      </div>
    );
  }

  /* ---- main render ---- */
  return (
    <div className="max-w-4xl mx-auto px-4">
      {/* Back link */}
      <div className="mb-6">
        <Link
          href={`/articles/${articleId}`}
          className="inline-flex items-center gap-1.5 text-sm text-clilens-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to article
        </Link>
      </div>

      {/* Page header */}
      <div className="bg-gradient-to-r from-clilens-teal-50 to-blue-50 border border-clilens-teal-200 rounded-xl p-6 mb-6">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-10 h-10 bg-clilens-primary rounded-full flex items-center justify-center">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 mb-1">Transparency Report</h1>
            <p className="text-sm text-gray-700 leading-relaxed">{data.title}</p>
            <p className="mt-2 text-xs text-gray-500">
              Full methodological breakdown, evidence trails, and confidence decomposition for this
              analysis.
            </p>
          </div>
        </div>
      </div>

      {/* Overall Assessment Card */}
      <div className="mb-6">
        <OverallAssessment data={data} />
      </div>

      {/* Scoring Legend */}
      <div className="mb-8">
        <ScoringLegend />
      </div>

      {/* Sections */}
      <div className="space-y-10">
        {/* 1. Methodology */}
        {data.methodology && Object.keys(data.methodology).length > 0 ? (
          <MethodologySection methodology={data.methodology} />
        ) : (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Beaker className="h-5 w-5 text-clilens-primary" />
              <h2 className="text-lg font-semibold text-gray-900">Methodology</h2>
            </div>
            <DataNotAvailable metricKey="methodology" />
          </section>
        )}

        {/* 2. Reliability Breakdown */}
        {data.reliability_breakdown && Object.keys(data.reliability_breakdown).length > 0 ? (
          <ReliabilitySection breakdown={data.reliability_breakdown} />
        ) : (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="h-5 w-5 text-clilens-primary" />
              <h2 className="text-lg font-semibold text-gray-900">Reliability Breakdown</h2>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <DataNotAvailable metricKey="source_credibility" />
            </div>
          </section>
        )}

        {/* 3. Decomposed Confidence */}
        {data.decomposed_confidence ? (
          <ConfidenceSection confidence={data.decomposed_confidence} />
        ) : (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="h-5 w-5 text-clilens-primary" />
              <h2 className="text-lg font-semibold text-gray-900">Confidence Intervals</h2>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <DataNotAvailable metricKey="model_confidence" />
            </div>
          </section>
        )}

        {/* 4. Evidence Chains */}
        {data.claims && data.claims.length > 0 ? (
          <EvidenceChainSection claims={data.claims} />
        ) : (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <GitBranch className="h-5 w-5 text-clilens-primary" />
              <h2 className="text-lg font-semibold text-gray-900">Evidence Chains</h2>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center mt-0.5">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-amber-800">No claims analyzed yet</p>
                  <p className="text-xs text-amber-600 mt-1 leading-relaxed">
                    Claim extraction and verification has not been completed for this article. This process runs automatically and may take some time. Once complete, each claim will show its verdict, confidence score, and supporting evidence trail.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* 5. Source Profile */}
        {data.source_profile ? (
          <SourceProfileSection profile={data.source_profile} />
        ) : (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Info className="h-5 w-5 text-clilens-primary" />
              <h2 className="text-lg font-semibold text-gray-900">Source Profile</h2>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <DataNotAvailable metricKey="source_credibility" />
            </div>
          </section>
        )}

        {/* 6. Causal Analysis (optional) */}
        {data.causal_analysis &&
          typeof data.causal_analysis === "object" &&
          Object.keys(data.causal_analysis).length > 0 && (
            <CausalAnalysisSection analysis={data.causal_analysis} />
          )}
      </div>

      {/* Footer disclaimer */}
      <div className="mt-10 pt-4 border-t border-gray-100 mb-8">
        <p className="text-xs text-gray-400">
          This transparency report is auto-generated to provide full traceability of the AI analysis
          pipeline. All source links point to the original evidence used during verification.
          Metrics marked as &ldquo;not available&rdquo; are either pending analysis or do not have sufficient data for this article.
        </p>
      </div>
    </div>
  );
}
