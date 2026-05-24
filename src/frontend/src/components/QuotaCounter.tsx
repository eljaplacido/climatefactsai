"use client";

import Link from "next/link";
import { useQuota, formatQuotaCounter, type QuotaKey } from "@/lib/useQuota";

/**
 * Inline quota counter rendered next to gated CTAs.
 *
 * Renders nothing while loading (no layout shift) and nothing when the
 * tier is unlimited on this key. Otherwise renders "X left this month"
 * (or just "X left" for lifetime quotas) with a colour ladder:
 *
 *   ≥50% remaining: gray-500 (neutral)
 *   <50% remaining: amber-600 (warning)
 *   0 remaining: red-600 with inline "Upgrade" CTA
 *
 * Phase 2A — paired with the 3/3/2 freemium decision (memory) and the
 * `useQuota` hook. The backend is still the source of truth for gating;
 * this is a UX nicety to convert users BEFORE they hit the wall.
 */

interface QuotaCounterProps {
  quotaKey: QuotaKey;
  /** Optional className for layout integration. */
  className?: string;
  /** When true, hides itself rather than rendering "Unlimited" copy.
   *  Useful inside small CTA buttons. */
  hideWhenUnlimited?: boolean;
}

export default function QuotaCounter({
  quotaKey,
  className = "",
  hideWhenUnlimited = false,
}: QuotaCounterProps) {
  const { getQuota, loading } = useQuota();
  if (loading) return null;
  const q = getQuota(quotaKey);
  if (!q) return null;
  if (q.limit === -1) {
    if (hideWhenUnlimited) return null;
    return (
      <span
        className={`text-xs text-gray-500 dark:text-slate-400 ${className}`}
        data-testid={`quota-counter-${quotaKey}`}
        data-quota-state="unlimited"
      >
        Unlimited
      </span>
    );
  }

  const remaining = Math.max(0, q.limit - q.used);
  const colour =
    remaining === 0
      ? "text-red-600 dark:text-red-400 font-medium"
      : remaining < q.limit / 2
        ? "text-amber-600 dark:text-amber-400"
        : "text-gray-500 dark:text-slate-400";

  return (
    <span
      className={`text-xs ${colour} ${className} inline-flex items-center gap-1`}
      data-testid={`quota-counter-${quotaKey}`}
      data-quota-state={
        remaining === 0 ? "exhausted" : remaining < q.limit / 2 ? "low" : "ok"
      }
      data-quota-remaining={remaining}
      data-quota-limit={q.limit}
    >
      <span>{formatQuotaCounter(q)}</span>
      {remaining === 0 && (
        <Link
          href={q.upgrade_url}
          className="underline hover:text-red-700 dark:hover:text-red-300 font-semibold"
          data-testid={`quota-counter-${quotaKey}-upgrade`}
        >
          Upgrade
        </Link>
      )}
    </span>
  );
}
