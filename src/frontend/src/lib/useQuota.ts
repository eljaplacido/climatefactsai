"use client";

import { useEffect, useState, useCallback } from "react";

/**
 * useQuota — Phase 2A (2026-05-23) frontend hook for the freemium quota
 * dashboard endpoint (`GET /api/quota`).
 *
 * Returns the user's standing across every quota key + a refresh()
 * callback for manual re-fetch after a quota-consuming action.
 *
 * Components that gate behaviour on a specific key (the "2/3 remaining"
 * inline counter, the upgrade modal, the disabled-CTA state) read from
 * this hook and use the per-key helper `getQuota(key)`.
 *
 * Anonymous users get the zero envelope from the backend — no special
 * handling needed on the client.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export type QuotaKey =
  | "saved_articles"
  | "saved_searches"
  | "deep_research"
  | "url_analysis"
  | "compare";

export interface QuotaState {
  quota_key: QuotaKey;
  allowed: boolean;
  used: number;
  limit: number;          // -1 = unlimited
  period: "lifetime" | "monthly";
  reset_at: string | null; // ISO 8601 (UTC) or null for lifetime
  upgrade_url: string;
  tier: string;
  label: string;
}

export interface QuotaSummary {
  tier: string;
  quotas: QuotaState[];
}

export interface UseQuotaResult {
  loading: boolean;
  error: string | null;
  summary: QuotaSummary | null;
  /** Get the per-key state. Returns null if the key isn't loaded yet. */
  getQuota: (key: QuotaKey) => QuotaState | null;
  /** Re-fetch the dashboard. Call after a quota-consuming action so the
   *  inline counter ticks immediately rather than waiting for the page reload. */
  refresh: () => Promise<void>;
}

export function useQuota(): UseQuotaResult {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<QuotaSummary | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = typeof window !== "undefined"
        ? localStorage.getItem("clilens_token")
        : null;
      const resp = await fetch(`${API_URL}/api/quota`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!resp.ok) {
        // 4xx/5xx — fall back to anonymous-zero so the UI still renders
        // (with quota gates blocking on the backend side anyway).
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = (await resp.json()) as QuotaSummary;
      setSummary(data);
    } catch (e: any) {
      setError(e?.message || "Failed to load quota");
      // Synthesize the zero envelope so callers always have something to
      // render. The backend still does the real gating.
      setSummary({
        tier: "anonymous",
        quotas: [
          "saved_articles",
          "saved_searches",
          "deep_research",
          "url_analysis",
          "compare",
        ].map((k) => ({
          quota_key: k as QuotaKey,
          allowed: false,
          used: 0,
          limit: 0,
          period: k === "saved_articles" || k === "saved_searches" ? "lifetime" : "monthly",
          reset_at: null,
          upgrade_url: "/dashboard/subscription",
          tier: "anonymous",
          label: k.replace(/_/g, " "),
        })),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const getQuota = useCallback(
    (key: QuotaKey): QuotaState | null => {
      if (!summary) return null;
      return summary.quotas.find((q) => q.quota_key === key) ?? null;
    },
    [summary],
  );

  return {
    loading,
    error,
    summary,
    getQuota,
    refresh: fetchSummary,
  };
}


/**
 * Format the "X/Y remaining" string for inline counters.
 *
 *   freemium deep_research used=2 limit=2 → "0 deep research queries left this month"
 *   freemium url_analysis used=0 limit=1 → "1 URL analysis left this month"
 *   professional saved_articles limit=-1 → "Unlimited"
 *
 * The Y/X (used/limit) ordering is intentional: we lead with what they
 * have LEFT, not what they've USED — converts better.
 */
export function formatQuotaCounter(q: QuotaState | null): string {
  if (!q) return "";
  if (q.limit === -1) return "Unlimited";
  const remaining = Math.max(0, q.limit - q.used);
  const periodLabel =
    q.period === "lifetime"
      ? ""
      : " this month";
  if (remaining === 0) {
    return `0 ${q.label} left${periodLabel} — upgrade for more`;
  }
  if (remaining === 1) {
    // Singular form — the label is plural by default ("saved articles");
    // strip the trailing s for the singular if applicable. Cheap hack
    // good enough for the 5 quota keys we have.
    const singular = q.label.endsWith("es") ? q.label.slice(0, -2) : q.label.endsWith("s") ? q.label.slice(0, -1) : q.label;
    return `1 ${singular} left${periodLabel}`;
  }
  return `${remaining} ${q.label} left${periodLabel}`;
}
