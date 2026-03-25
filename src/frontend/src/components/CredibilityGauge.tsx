"use client";

import { useState, useEffect } from "react";
import clsx from "clsx";
import type { DecomposedConfidence } from "../types";

interface CredibilityGaugeProps {
  score: number;
  level: string;
  decomposedConfidence?: DecomposedConfidence;
  size?: "sm" | "md" | "lg";
}

const SIZE_CONFIG = {
  sm: { diameter: 64, strokeWidth: 5, fontSize: "text-sm", labelSize: "text-[9px]" },
  md: { diameter: 100, strokeWidth: 7, fontSize: "text-xl", labelSize: "text-xs" },
  lg: { diameter: 140, strokeWidth: 9, fontSize: "text-3xl", labelSize: "text-sm" },
};

const FACTOR_LABELS: Record<string, string> = {
  model_confidence: "AI Confidence",
  source_quality: "Source Quality",
  evidence_breadth: "Evidence Breadth",
  cross_reference_score: "Cross-Reference",
  temporal_relevance: "Recency",
};

const FACTOR_COLORS: Record<string, string> = {
  model_confidence: "bg-blue-500",
  source_quality: "bg-emerald-500",
  evidence_breadth: "bg-purple-500",
  cross_reference_score: "bg-amber-500",
  temporal_relevance: "bg-cyan-500",
};

function getScoreColor(score: number): string {
  if (score >= 80) return "#10b981"; // emerald-500
  if (score >= 50) return "#f59e0b"; // amber-500
  return "#ef4444"; // red-500
}

function getLevelLabel(level: string): string {
  switch (level) {
    case "HIGH": return "High";
    case "MEDIUM": return "Moderate";
    case "LOW": return "Low";
    case "MIXED": return "Mixed";
    default: return "Unknown";
  }
}

function CredibilityGauge({ score, level, decomposedConfidence, size = "md" }: CredibilityGaugeProps) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [animated, setAnimated] = useState(false);
  const config = SIZE_CONFIG[size];

  const radius = (config.diameter - config.strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const normalizedScore = Math.min(100, Math.max(0, score));
  const targetOffset = circumference - (normalizedScore / 100) * circumference;
  const strokeDashoffset = animated ? targetOffset : circumference;
  const color = getScoreColor(normalizedScore);

  // Animate on mount
  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="relative inline-flex flex-col items-center" role="img" aria-label={`Credibility score: ${normalizedScore} out of 100, level: ${getLevelLabel(level)}`}>
      <div
        className="relative cursor-pointer"
        onMouseEnter={() => setShowBreakdown(true)}
        onMouseLeave={() => setShowBreakdown(false)}
        onClick={() => setShowBreakdown(!showBreakdown)}
      >
        <svg
          width={config.diameter}
          height={config.diameter}
          className="transform -rotate-90"
          aria-hidden="true"
        >
          {/* Background circle */}
          <circle
            cx={config.diameter / 2}
            cy={config.diameter / 2}
            r={radius}
            stroke="#e5e7eb"
            strokeWidth={config.strokeWidth}
            fill="none"
          />
          {/* Score arc */}
          <circle
            cx={config.diameter / 2}
            cy={config.diameter / 2}
            r={radius}
            stroke={color}
            strokeWidth={config.strokeWidth}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={clsx("font-bold", config.fontSize)} style={{ color }}>
            {normalizedScore}
          </span>
          {size !== "sm" && (
            <span className={clsx("text-gray-500 font-medium", config.labelSize)}>
              {getLevelLabel(level)}
            </span>
          )}
        </div>
      </div>

      {/* Decomposed confidence breakdown popover */}
      {showBreakdown && decomposedConfidence && size !== "sm" && (
        <div className="absolute top-full mt-2 z-50 bg-white rounded-xl shadow-xl border border-gray-200 p-4 w-72">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Confidence Breakdown</h4>
          <div className="space-y-2.5">
            {Object.entries(FACTOR_LABELS).map(([key, label]) => {
              const value = decomposedConfidence[key as keyof DecomposedConfidence] as number;
              const pct = Math.round(value * 100);
              return (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-600">{label}</span>
                    <span className="text-xs font-semibold text-gray-900">{pct}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className={clsx("h-1.5 rounded-full transition-all duration-500", FACTOR_COLORS[key])}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-2 border-t border-gray-100">
            <p className="text-[10px] text-gray-400">
              Hover over each factor to learn more. Scores are computed from evidence quality, source diversity, and model agreement.
            </p>
          </div>
          {/* Arrow pointing up */}
          <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-white border-l border-t border-gray-200 rotate-45" />
        </div>
      )}
    </div>
  );
}

export default CredibilityGauge;
