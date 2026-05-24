"use client";

import type {
  SentenceGrounding,
  SentenceGroundingLevel,
  ConfidenceEnvelope,
} from "@/types";
import { AlertTriangle, Info } from "lucide-react";

/**
 * Renders an LLM answer with inline per-sentence grounding pills.
 *
 * Shipped 2026-05-23 (Phase 0 day 3, §3.3). When the low-evidence prompt
 * routes (internal+external < 3 sources), the backend returns a
 * `sentence_grounding` array tagging each sentence as
 * HIGH | MEDIUM | LOW | NONE grounded against the retrieved evidence.
 *
 * This component renders the prose plus a small pill after each sentence
 * so the reader can see — without leaving the page — which parts of the
 * answer are grounded in retrieval vs. drawn from general training
 * knowledge vs. speculative. This is the C2PA progressive-disclosure
 * pattern applied at sentence granularity.
 *
 * Fallback: when `sentence_grounding` is absent (high-evidence path),
 * the parent component renders the plain prose answer directly. This
 * component is ONLY for the calibrated low-evidence path.
 */

const LEVEL_STYLES: Record<SentenceGroundingLevel, { bg: string; text: string; border: string; label: string; title: string }> = {
  HIGH: {
    bg: "bg-emerald-100 dark:bg-emerald-900/40",
    text: "text-emerald-800 dark:text-emerald-200",
    border: "border-emerald-200 dark:border-emerald-700/50",
    label: "Grounded",
    title: "Restates a fact from a retrieved source.",
  },
  MEDIUM: {
    bg: "bg-blue-100 dark:bg-blue-900/40",
    text: "text-blue-800 dark:text-blue-200",
    border: "border-blue-200 dark:border-blue-700/50",
    label: "Consensus",
    title: "Well-established knowledge the model knows but retrieval did not surface.",
  },
  LOW: {
    bg: "bg-amber-100 dark:bg-amber-900/40",
    text: "text-amber-800 dark:text-amber-200",
    border: "border-amber-200 dark:border-amber-700/50",
    label: "Inference",
    title: "A reasonable inference, not directly verifiable from retrieval.",
  },
  NONE: {
    bg: "bg-red-100 dark:bg-red-900/40",
    text: "text-red-800 dark:text-red-200",
    border: "border-red-200 dark:border-red-700/50",
    label: "Speculation",
    title: "Framing or speculation — not a verifiable claim.",
  },
};

interface SentenceGroundedAnswerProps {
  sentences: SentenceGrounding[];
  confidence?: ConfidenceEnvelope | null;
}

export default function SentenceGroundedAnswer({
  sentences,
  confidence,
}: SentenceGroundedAnswerProps) {
  // Defensive: if backend ever returns malformed entries, drop them rather
  // than throwing.
  const valid = (sentences || []).filter(
    (s) => s && typeof s.text === "string" && s.text.length > 0
  );

  // Aggregate counts for the optional summary chip row.
  const counts: Record<SentenceGroundingLevel, number> = {
    HIGH: 0,
    MEDIUM: 0,
    LOW: 0,
    NONE: 0,
  };
  for (const s of valid) {
    if (s.level in counts) counts[s.level as SentenceGroundingLevel] += 1;
  }
  const total = valid.length;

  return (
    <div data-testid="sentence-grounded-answer" className="space-y-3">
      {/* Top-line confidence envelope — the EU AI Act "is this AI-generated
          + how confident is it" disclosure surfaces here so the reader sees
          it before reading the answer. */}
      {confidence?.confidence && (
        <div
          className="flex items-start gap-2 px-3 py-2 rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/40"
          role="note"
          data-testid="sentence-grounded-confidence-banner"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-700 dark:text-amber-300 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-amber-900 dark:text-amber-100">
            <span className="font-semibold capitalize">{confidence.confidence}</span>
            {" confidence answer"}
            {confidence.reason && (
              <span className="text-amber-800 dark:text-amber-200 ml-1">
                &middot; {confidence.reason}
              </span>
            )}
            <span className="block text-[11px] text-amber-700 dark:text-amber-300 mt-0.5">
              Each sentence carries a calibration pill below. Treat NONE / LOW sentences as inference, not fact.
            </span>
          </div>
        </div>
      )}

      {/* Per-sentence rendering */}
      <div className="prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-slate-100 leading-relaxed">
        {valid.map((s, i) => {
          const style = LEVEL_STYLES[s.level] || LEVEL_STYLES.NONE;
          return (
            <span key={i}>
              {s.text}{" "}
              <span
                className={`inline-flex items-center gap-1 px-1.5 py-0 text-[10px] font-mono uppercase tracking-wider rounded border ${style.bg} ${style.text} ${style.border} align-middle whitespace-nowrap`}
                title={`${style.label} — ${s.reason ? `${s.reason}. ` : ""}${style.title}`}
                aria-label={`Sentence grounding: ${style.label}`}
                data-testid={`sentence-pill-${s.level}`}
              >
                {style.label}
              </span>{" "}
            </span>
          );
        })}
      </div>

      {/* Calibration footer — small distribution so the reader can see at a
          glance how much of the answer is HIGH-grounded vs speculative. */}
      {total > 0 && (
        <div
          className="flex items-center gap-3 pt-2 border-t border-gray-100 dark:border-slate-800 text-[11px] text-gray-600 dark:text-slate-400"
          data-testid="sentence-grounded-summary"
        >
          <Info className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
          <span>Grounding distribution:</span>
          {(["HIGH", "MEDIUM", "LOW", "NONE"] as SentenceGroundingLevel[]).map(
            (lvl) => {
              const c = counts[lvl];
              if (c === 0) return null;
              const style = LEVEL_STYLES[lvl];
              return (
                <span
                  key={lvl}
                  className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${style.bg} ${style.text}`}
                >
                  {style.label}: {c}/{total}
                </span>
              );
            }
          )}
        </div>
      )}
    </div>
  );
}
