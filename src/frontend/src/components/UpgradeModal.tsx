"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { Crown, X, ArrowRight } from "lucide-react";

/**
 * UpgradeModal — Phase 2A (2026-05-23).
 *
 * Rendered when a gated endpoint returns HTTP 429 with the structured
 * quota_exceeded envelope. The modal:
 *   1. Names the specific quota the user hit ("URL analyses", "saved articles")
 *   2. Shows used/limit so they see exactly where they stand
 *   3. Surfaces a "Reset on …" for monthly quotas so they know they can
 *      wait it out
 *   4. Carries one primary CTA — `quota.upgrade_url` (typically
 *      `/dashboard/subscription`) — and one secondary "Got it" close
 *
 * The 429 envelope comes from `QuotaService.check_and_raise` in the
 * backend; this modal renders it verbatim so backend copy edits flow
 * through without a frontend deploy.
 */

export interface UpgradeModalQuotaEnvelope {
  quota_key: string;
  used: number;
  limit: number;
  period: "lifetime" | "monthly" | string;
  reset_at: string | null;
  upgrade_url: string;
  tier: string;
  label: string;
}

interface UpgradeModalProps {
  /** The quota envelope from the 429 response detail. Null = closed. */
  quota: UpgradeModalQuotaEnvelope | null;
  /** Optional explainer message from the backend. */
  message?: string | null;
  onClose: () => void;
}

export default function UpgradeModal({ quota, message, onClose }: UpgradeModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!quota) return;
    closeRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [quota, onClose]);

  if (!quota) return null;

  const resetLabel = (() => {
    if (quota.period === "lifetime") return "Lifetime cap on the free tier";
    if (!quota.reset_at) return "Resets monthly";
    try {
      const d = new Date(quota.reset_at);
      return `Resets on ${d.toLocaleDateString(undefined, {
        month: "long",
        day: "numeric",
      })}`;
    } catch {
      return "Resets monthly";
    }
  })();

  return (
    <div
      className="fixed inset-0 z-[2100] flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upgrade-modal-title"
      data-testid="upgrade-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden">
        {/* Header with the crown icon — same visual language as the
            existing /dashboard/subscription page. */}
        <div className="px-5 pt-5 pb-3 bg-gradient-to-br from-amber-50 to-teal-50 dark:from-amber-950/30 dark:to-teal-950/30 border-b border-gray-100 dark:border-slate-800">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-amber-500/20 flex items-center justify-center">
                <Crown
                  className="w-5 h-5 text-amber-600 dark:text-amber-400"
                  aria-hidden="true"
                />
              </div>
              <div>
                <h3
                  id="upgrade-modal-title"
                  className="text-base font-semibold text-gray-900 dark:text-slate-100"
                >
                  You've reached your {quota.label} limit
                </h3>
                <p
                  className="text-xs text-gray-600 dark:text-slate-400"
                  data-testid="upgrade-modal-tier"
                >
                  on the {quota.tier} tier
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 transition-colors"
              aria-label="Close dialog"
              data-testid="upgrade-modal-close"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 dark:bg-slate-800 rounded-lg p-3 text-center">
              <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-slate-400">
                Used
              </p>
              <p
                className="text-2xl font-bold text-gray-900 dark:text-slate-100"
                data-testid="upgrade-modal-used"
              >
                {quota.used} / {quota.limit}
              </p>
            </div>
            <div className="bg-gray-50 dark:bg-slate-800 rounded-lg p-3 text-center">
              <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-slate-400">
                {quota.period === "lifetime" ? "Cap" : "Resets"}
              </p>
              <p
                className="text-sm font-medium text-gray-900 dark:text-slate-100 mt-1"
                data-testid="upgrade-modal-reset"
              >
                {resetLabel}
              </p>
            </div>
          </div>

          {message && (
            <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed">
              {message}
            </p>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              ref={closeRef}
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              data-testid="upgrade-modal-dismiss"
            >
              Got it
            </button>
            <Link
              href={quota.upgrade_url}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors"
              data-testid="upgrade-modal-upgrade-cta"
              onClick={onClose}
            >
              See plans
              <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
