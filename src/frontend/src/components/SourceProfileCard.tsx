"use client";

import clsx from "clsx";
import { Shield, ExternalLink, FileText, AlertTriangle, CheckCircle } from "lucide-react";
import type { SourceProfile } from "../types";

interface SourceProfileCardProps {
  profile: SourceProfile;
  compact?: boolean;
}

const EDITORIAL_CONFIG: Record<string, { label: string; color: string }> = {
  rigorous: { label: "Rigorous", color: "text-emerald-700" },
  moderate: { label: "Moderate", color: "text-amber-700" },
  low: { label: "Low", color: "text-red-700" },
  unknown: { label: "Not assessed", color: "text-gray-500" },
};

const FACTCHECK_CONFIG: Record<string, { label: string; color: string }> = {
  excellent: { label: "Excellent", color: "text-emerald-700" },
  good: { label: "Good", color: "text-emerald-600" },
  mixed: { label: "Mixed", color: "text-amber-700" },
  poor: { label: "Poor", color: "text-red-700" },
  unknown: { label: "Not assessed", color: "text-gray-500" },
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

  if (compact) {
    return (
      <div className={clsx("inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg border text-sm", band.bg)}>
        <Shield className={clsx("h-4 w-4", band.color)} />
        <span className={clsx("font-medium", band.color)}>{profile.source_name}</span>
        <span className="text-gray-500">|</span>
        <span className={clsx("font-semibold", band.color)}>{profile.credibility_score}/100</span>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
      {/* Header */}
      <div className={clsx("px-4 py-3 border-b", band.bg)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Shield className={clsx("h-5 w-5", band.color)} />
            <h3 className="font-semibold text-gray-900">{profile.source_name}</h3>
          </div>
          <div className="flex items-center space-x-2">
            <span className={clsx("text-2xl font-bold", band.color)}>{profile.credibility_score}</span>
            <span className="text-xs text-gray-500">/100</span>
          </div>
        </div>
        <p className={clsx("text-xs mt-1", band.color)}>{band.label}</p>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Trust factors */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-0.5">Editorial Standards</p>
            <p className={clsx("text-sm font-medium", editorial.color)}>{editorial.label}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-0.5">Fact-Check Record</p>
            <p className={clsx("text-sm font-medium", factcheck.color)}>{factcheck.label}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-0.5">Transparency</p>
            <p className={clsx("text-sm font-medium",
              profile.transparency_level === "high" ? "text-emerald-700" :
              profile.transparency_level === "moderate" ? "text-amber-700" :
              profile.transparency_level === "low" ? "text-red-700" : "text-gray-500"
            )}>
              {profile.transparency_level === "unknown" ? "Not assessed" :
               profile.transparency_level.charAt(0).toUpperCase() + profile.transparency_level.slice(1)}
            </p>
          </div>
        </div>

        {/* Historical stats */}
        {profile.total_articles_analyzed > 0 && (
          <div className="pt-3 border-t border-gray-100">
            <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-2">Historical Performance</p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex items-center space-x-1.5">
                <FileText className="h-3.5 w-3.5 text-gray-400" />
                <span className="text-gray-600">{profile.total_articles_analyzed} articles analyzed</span>
              </div>
              {profile.average_reliability_score !== null && (
                <div className="flex items-center space-x-1.5">
                  <Shield className="h-3.5 w-3.5 text-gray-400" />
                  <span className="text-gray-600">Avg reliability: {Math.round(profile.average_reliability_score)}/100</span>
                </div>
              )}
              <div className="flex items-center space-x-1.5">
                <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                <span className="text-gray-600">{profile.total_claims_verified} claims verified</span>
              </div>
              {profile.total_claims_disputed > 0 && (
                <div className="flex items-center space-x-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                  <span className="text-gray-600">{profile.total_claims_disputed} disputed</span>
                </div>
              )}
            </div>
            {profile.false_claim_rate > 0 && (
              <div className="mt-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-gray-500">False claim rate</span>
                  <span className={clsx("font-semibold",
                    profile.false_claim_rate < 0.05 ? "text-emerald-600" :
                    profile.false_claim_rate < 0.15 ? "text-amber-600" : "text-red-600"
                  )}>
                    {(profile.false_claim_rate * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-1">
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

        {/* Description */}
        {profile.description && (
          <p className="text-xs text-gray-500 pt-2 border-t border-gray-100">{profile.description}</p>
        )}

        {/* Link */}
        {profile.website_url && (
          <a
            href={profile.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1 text-xs text-clilens-primary hover:underline"
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
