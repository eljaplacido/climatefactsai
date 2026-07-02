"use client";

import clsx from "clsx";
import { Shield, ExternalLink, FileText, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import type { SourceProfile } from "../types";
import AskAboutButton from "./AskAboutButton";

interface SourceProfileCardProps {
  profile: SourceProfile;
  compact?: boolean;
}

const EDITORIAL_CONFIG: Record<string, { label: string; color: string }> = {
  rigorous: { label: "Rigorous", color: "text-emerald-700" },
  moderate: { label: "Moderate", color: "text-amber-700" },
  low: { label: "Low", color: "text-red-700" },
  unknown: { label: "Awaiting analysis", color: "text-gray-400 dark:text-slate-500 dark:text-slate-400" },
};

const FACTCHECK_CONFIG: Record<string, { label: string; color: string }> = {
  excellent: { label: "Excellent", color: "text-emerald-700" },
  good: { label: "Good", color: "text-emerald-600" },
  mixed: { label: "Mixed", color: "text-amber-700" },
  poor: { label: "Poor", color: "text-red-700" },
  unknown: { label: "Awaiting analysis", color: "text-gray-400 dark:text-slate-500 dark:text-slate-400" },
};

function getCredibilityBand(score: number): { label: string; color: string; bg: string } {
  if (score >= 80) return { label: "Highly Trusted", color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200" };
  if (score >= 60) return { label: "Generally Reliable", color: "text-amber-700", bg: "bg-amber-50 border-amber-200" };
  if (score >= 40) return { label: "Mixed Reliability", color: "text-orange-700", bg: "bg-orange-50 border-orange-200" };
  return { label: "Low Reliability", color: "text-red-700", bg: "bg-red-50 border-red-200" };
}

function SourceProfileCard({ profile, compact = false }: SourceProfileCardProps) {
  const band = getCredibilityBand(profile.credibility_score);
  const editorial = EDITORIAL_CONFIG[profile.editorial_standards] || EDITORIAL_CONFIG.unknown;
  const factcheck = FACTCHECK_CONFIG[profile.fact_check_record] || FACTCHECK_CONFIG.unknown;
  // At least one trust factor carries a derived (non-"unknown") label. Those
  // labels are derived from the platform's own reliability tiering + historical
  // analysis, NOT an independent third-party audit — disclose that honestly.
  const hasDerivedAssessment =
    (profile.editorial_standards && profile.editorial_standards !== "unknown") ||
    (profile.fact_check_record && profile.fact_check_record !== "unknown") ||
    (profile.transparency_level && profile.transparency_level !== "unknown");
  // ML-12: an evidence-backed credibility tier (source_credibility_tiers) IS a
  // signal — so suppress the "awaiting GX10 analysis" copy for tiered sources
  // and surface the public evidence link instead.
  const hasTier = Boolean(profile.tier);

  if (compact) {
    return (
      <div className={clsx("inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg border text-sm", band.bg)}>
        <Shield className={clsx("h-4 w-4", band.color)} />
        <span className={clsx("font-medium", band.color)}>{profile.source_name}</span>
        <span className="text-gray-500 dark:text-slate-400">|</span>
        <span className={clsx("font-semibold", band.color)}>{profile.credibility_score}/100</span>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden bg-white dark:bg-slate-800">
      {/* Header */}
      <div className={clsx("px-4 py-3 border-b", band.bg)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 min-w-0">
            <Shield className={clsx("h-5 w-5 flex-shrink-0", band.color)} />
            <h3 className="font-semibold text-gray-900 dark:text-slate-100 truncate">{profile.source_name}</h3>
          </div>
          <div className="flex items-center space-x-2 flex-shrink-0">
            <span className={clsx("text-2xl font-bold", band.color)}>{profile.credibility_score}</span>
            <span className="text-xs text-gray-500 dark:text-slate-400">/100</span>
          </div>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 flex-wrap">
          <p className={clsx("text-xs flex items-center gap-1", band.color)}>
            {band.label}
            <AskAboutButton
              prompt={`Explain why ${profile.source_name} is rated ${profile.credibility_score}/100 — what factors went into this credibility score and how is the tier (T1/T2/T3) decided?`}
              ariaLabel={`Ask the assistant: explain ${profile.source_name}'s credibility rating`}
            />
          </p>
          {/* Phase 0 day 2 (2026-05-23): tier badge from source_credibility_tiers
              (migration 027). Renders only when the profile has been tier-classified
              — sources without a tier match show only the band label so we don't
              mislead users into thinking unknown sources have been vetted.
              ML-12 (2026-07-02): add a public "Why this tier?" evidence link so
              auditors can verify the classification. */}
          {profile.tier && (
            <div className="inline-flex items-center gap-1.5 flex-shrink-0">
              <span
                title={
                  profile.tier_prior_bonus != null
                    ? `Tier ${profile.tier} · prior_bonus +${profile.tier_prior_bonus}`
                    : `Tier ${profile.tier}`
                }
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider bg-white/70 dark:bg-slate-800/70 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-600"
              >
                {profile.tier}
                {profile.tier_prior_bonus != null && (
                  <span className="text-slate-500 dark:text-slate-400">+{profile.tier_prior_bonus}</span>
                )}
              </span>
              {profile.evidence_url && (
                <a
                  href={profile.evidence_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={
                    profile.classification
                      ? `Classification: ${profile.classification}`
                      : "Evidence for this tier classification"
                  }
                  className="inline-flex items-center gap-0.5 text-[10px] text-clilens-primary dark:text-teal-400 hover:underline"
                >
                  <ExternalLink className="h-2.5 w-2.5" />
                  Why this tier?
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Trust factors with optional 3-axis numeric scores (mig 041). */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-slate-400 mb-0.5">Editorial Standards</p>
            <p className={clsx("text-sm font-medium flex items-center gap-1", editorial.color)}>
              {profile.editorial_standards === "unknown" && <Clock className="w-3 h-3" />}
              {editorial.label}
            </p>
            {typeof profile.editorial_score === "number" && (
              <p className="text-[10px] text-gray-500 dark:text-slate-400 mt-0.5 font-mono">{profile.editorial_score}/100</p>
            )}
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-slate-400 mb-0.5">Fact-Check Record</p>
            <p className={clsx("text-sm font-medium flex items-center gap-1", factcheck.color)}>
              {profile.fact_check_record === "unknown" && <Clock className="w-3 h-3" />}
              {factcheck.label}
            </p>
            {typeof profile.factcheck_score === "number" && (
              <p className="text-[10px] text-gray-500 dark:text-slate-400 mt-0.5 font-mono">{profile.factcheck_score}/100</p>
            )}
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-slate-400 mb-0.5">Transparency</p>
            <p className={clsx("text-sm font-medium flex items-center gap-1",
              profile.transparency_level === "high" ? "text-emerald-700" :
              profile.transparency_level === "moderate" ? "text-amber-700" :
              profile.transparency_level === "low" ? "text-red-700" : "text-gray-400 dark:text-slate-500 dark:text-slate-400"
            )}>
              {profile.transparency_level === "unknown" && <Clock className="w-3 h-3" />}
              {profile.transparency_level === "unknown" ? "Awaiting analysis" :
               profile.transparency_level.charAt(0).toUpperCase() + profile.transparency_level.slice(1)}
            </p>
            {typeof profile.transparency_score === "number" && (
              <p className="text-[10px] text-gray-500 dark:text-slate-400 mt-0.5 font-mono">{profile.transparency_score}/100</p>
            )}
          </div>
        </div>

        {/* Honesty disclosure: the editorial / fact-check / transparency labels
            are DERIVED from this platform's reliability tiering + historical
            analysis — they are not independent third-party audits. */}
        {hasDerivedAssessment && (
          <p className="text-[10px] text-gray-400 dark:text-slate-500 leading-relaxed">
            Editorial, fact-check and transparency ratings are derived from this platform&rsquo;s
            reliability tiering and historical analysis &mdash; not independent third-party audits.
          </p>
        )}

        {/* Historical stats */}
        {profile.total_articles_analyzed > 0 && (
          <div className="pt-3 border-t border-gray-100 dark:border-slate-800">
            <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-slate-400 mb-2">Historical Performance</p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex items-center space-x-1.5">
                <FileText className="h-3.5 w-3.5 text-gray-400 dark:text-slate-500 dark:text-slate-400" />
                <span className="text-gray-600 dark:text-slate-400">{profile.total_articles_analyzed} articles analyzed</span>
              </div>
              {profile.average_reliability_score !== null && (
                <div className="flex items-center space-x-1.5">
                  <Shield className="h-3.5 w-3.5 text-gray-400 dark:text-slate-500 dark:text-slate-400" />
                  <span className="text-gray-600 dark:text-slate-400">Avg reliability: {Math.round(profile.average_reliability_score)}/100</span>
                </div>
              )}
              <div className="flex items-center space-x-1.5">
                <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                <span className="text-gray-600 dark:text-slate-400">{profile.total_claims_verified} claims verified</span>
              </div>
              {profile.total_claims_disputed > 0 && (
                <div className="flex items-center space-x-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                  <span className="text-gray-600 dark:text-slate-400">{profile.total_claims_disputed} disputed</span>
                </div>
              )}
            </div>
            {profile.false_claim_rate > 0 && (
              <div className="mt-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-500 dark:text-slate-400">False claim rate</span>
                  <span className={clsx("font-semibold",
                    profile.false_claim_rate < 0.05 ? "text-emerald-600" :
                    profile.false_claim_rate < 0.15 ? "text-amber-600" : "text-red-600"
                  )}>
                    {(profile.false_claim_rate * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-100 dark:bg-slate-700 rounded-full h-1">
                  <div
                    className={clsx("h-1 rounded-full",
                      profile.false_claim_rate < 0.05 ? "bg-emerald-400" :
                      profile.false_claim_rate < 0.15 ? "bg-amber-400" : "bg-red-400"
                    )}
                    style={{ width: `${Math.min(100, profile.false_claim_rate * 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* GX10 pending-assessment notice — shown when any trust factor is unknown
            AND the source has no evidence-backed tier (a tier IS an assessment). */}
        {!hasTier && (profile.editorial_standards === "unknown" || profile.fact_check_record === "unknown" || profile.transparency_level === "unknown") && (
          <div className="flex items-start gap-2 pt-2 border-t border-gray-100 dark:border-slate-800">
            <Clock className="w-3.5 h-3.5 text-gray-400 dark:text-slate-500 dark:text-slate-400 mt-0.5 flex-shrink-0" />
            <p className="text-[10px] text-gray-400 dark:text-slate-500 dark:text-slate-400 leading-relaxed">
              This source will be automatically assessed by our GX10 analysis pipeline once sufficient articles have been ingested.
            </p>
          </div>
        )}

        {/* Description */}
        {profile.description && (
          <p className="text-xs text-gray-500 dark:text-slate-400 pt-2 border-t border-gray-100 dark:border-slate-800">{profile.description}</p>
        )}

        {/* Link */}
        {profile.website_url && (
          <a
            href={profile.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1 text-xs text-clilens-primary dark:text-teal-400 hover:underline"
          >
            <ExternalLink className="h-3 w-3" />
            <span>{profile.source_domain}</span>
          </a>
        )}
      </div>
    </div>
  );
}

export default SourceProfileCard;
