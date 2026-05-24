"use client";

import { useState, useEffect } from "react";
import { Bell, X, AlertTriangle, Check } from "lucide-react";

/**
 * AOISubscribeButton — Phase 3B (2026-05-23) MH5.
 *
 * Button that opens a small modal for creating an AOI alert subscription
 * scoped to a single country. Used on the Country Climate Passport
 * header — clicking "Subscribe to alerts" opens this dialog.
 *
 * Tier semantics:
 *   - Freemium/Anonymous: the button still renders, but clicking opens
 *     the modal in "upgrade-required" state with a one-CTA path to
 *     /dashboard/subscription. Better UX than hiding the button (users
 *     should know the feature exists; that's the conversion hook).
 *   - Basic+: the modal opens in form mode for picking variable +
 *     comparison + threshold.
 *
 * Backend integration:
 *   GET  /api/aoi-subscriptions/tier-info — initial tier check
 *   POST /api/aoi-subscriptions           — create on confirm
 *
 * Competitive bar: GFW (Global Forest Watch) is the gold standard for
 * AOI alerts but their flow takes ~6 clicks. Ours is 2 (open modal,
 * confirm). We match GFW on capability and beat them on friction.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

const VARIABLE_OPTIONS = [
  {
    id: "temperature_anomaly_c",
    label: "Temperature anomaly (°C above last year)",
    defaultComparison: "gt" as const,
    defaultThreshold: 2,
    unit: "°C",
  },
  {
    id: "renewable_share_pct",
    label: "Renewable share (%)",
    defaultComparison: "gte" as const,
    defaultThreshold: 50,
    unit: "%",
  },
  {
    id: "co2_emissions_per_capita",
    label: "CO₂ emissions per capita (t)",
    defaultComparison: "gt" as const,
    defaultThreshold: 8,
    unit: "t",
  },
  {
    id: "climate_risk_score",
    label: "Climate risk score (0–100)",
    defaultComparison: "gte" as const,
    defaultThreshold: 60,
    unit: "",
  },
];

const COMPARISON_OPTIONS = [
  { value: "gt", label: "exceeds (>)" },
  { value: "gte", label: "is at or above (≥)" },
  { value: "lt", label: "falls below (<)" },
  { value: "lte", label: "is at or below (≤)" },
  { value: "eq", label: "equals (=)" },
];

interface TierInfo {
  tier: string;
  limit: number;
  used: number;
  allowed: boolean;
  upgrade_url: string;
}

interface AOISubscribeButtonProps {
  countryCode: string;
  countryName: string;
  /** Auth token from localStorage; null = anonymous. */
  authToken?: string | null;
}

export default function AOISubscribeButton({
  countryCode,
  countryName,
  authToken,
}: AOISubscribeButtonProps) {
  const [open, setOpen] = useState(false);
  const [tierInfo, setTierInfo] = useState<TierInfo | null>(null);
  const [tierLoading, setTierLoading] = useState(false);
  const [variable, setVariable] = useState(VARIABLE_OPTIONS[0].id);
  const [comparison, setComparison] = useState<"gt" | "gte" | "lt" | "lte" | "eq">(
    VARIABLE_OPTIONS[0].defaultComparison,
  );
  const [threshold, setThreshold] = useState<number>(
    VARIABLE_OPTIONS[0].defaultThreshold,
  );
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lazy tier check — only when modal opens, not on page load.
  useEffect(() => {
    if (!open || tierInfo) return;
    if (!authToken) {
      setTierInfo({
        tier: "anonymous",
        limit: 0,
        used: 0,
        allowed: false,
        upgrade_url: "/login",
      });
      return;
    }
    setTierLoading(true);
    fetch(`${API_BASE}/api/aoi-subscriptions/tier-info`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: TierInfo | null) => {
        if (data) setTierInfo(data);
      })
      .catch(() => {
        // Network blip — leave tierInfo null; we'll just show the form
        // and let the backend 429 if the user actually tries to create.
      })
      .finally(() => setTierLoading(false));
  }, [open, authToken, tierInfo]);

  // Update threshold + comparison when variable changes
  useEffect(() => {
    const v = VARIABLE_OPTIONS.find((o) => o.id === variable);
    if (v) {
      setComparison(v.defaultComparison);
      setThreshold(v.defaultThreshold);
    }
  }, [variable]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!authToken) return;
    setSubmitting(true);
    setError(null);
    try {
      const variableLabel =
        VARIABLE_OPTIONS.find((o) => o.id === variable)?.label || variable;
      const comparisonLabel =
        COMPARISON_OPTIONS.find((o) => o.value === comparison)?.label || comparison;
      const resp = await fetch(`${API_BASE}/api/aoi-subscriptions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          country_code: countryCode,
          variable,
          comparison,
          threshold,
          label: `${countryName}: ${variableLabel} ${comparisonLabel} ${threshold}`,
        }),
      });
      if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        setError(body?.detail?.message || "Upgrade required to add this alert.");
        return;
      }
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setError(
          body?.detail?.message ||
            body?.detail ||
            `Failed to create alert (HTTP ${resp.status})`,
        );
        return;
      }
      setSuccess(true);
      // Auto-close after a beat so the user sees the success state
      setTimeout(() => {
        setOpen(false);
        setSuccess(false);
      }, 1500);
    } catch (err: any) {
      setError(err?.message || "Network error");
    } finally {
      setSubmitting(false);
    }
  }

  const upgradeRequired = tierInfo && !tierInfo.allowed;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800/50 rounded-md hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
        aria-label={`Subscribe to ${countryName} alerts`}
        data-testid="aoi-subscribe-button"
      >
        <Bell className="w-3.5 h-3.5" aria-hidden="true" />
        Subscribe to alerts
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[2200] flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="aoi-subscribe-title"
          data-testid="aoi-subscribe-modal"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-2xl max-w-md w-full mx-4 p-5">
            <div className="flex items-start justify-between gap-3 mb-3">
              <h3
                id="aoi-subscribe-title"
                className="text-base font-semibold text-gray-900 dark:text-slate-100 flex items-center gap-2"
              >
                <Bell className="w-4 h-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                Alert me when&hellip;
              </h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300"
                aria-label="Close dialog"
                data-testid="aoi-subscribe-close"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>

            {tierLoading ? (
              <p className="text-sm text-gray-500 dark:text-slate-400 py-4 text-center">
                Checking your tier&hellip;
              </p>
            ) : upgradeRequired ? (
              <div data-testid="aoi-subscribe-upgrade-state">
                <div className="p-3 mb-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/40 rounded-lg flex items-start gap-2">
                  <AlertTriangle
                    className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0"
                    aria-hidden="true"
                  />
                  <p className="text-sm text-amber-900 dark:text-amber-100">
                    {tierInfo?.tier === "anonymous"
                      ? "Sign in to subscribe to alerts."
                      : `AOI alerts are a Basic+ feature. You're on the ${tierInfo?.tier} tier.`}
                  </p>
                </div>
                <a
                  href={tierInfo?.upgrade_url || "/dashboard/subscription"}
                  className="block w-full text-center px-4 py-2 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-md"
                  data-testid="aoi-subscribe-upgrade-cta"
                >
                  {tierInfo?.tier === "anonymous" ? "Sign in" : "See plans"}
                </a>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-3" data-testid="aoi-subscribe-form">
                <p className="text-xs text-gray-600 dark:text-slate-400">
                  Alert scope: <strong>{countryName}</strong> ({countryCode})
                </p>
                <div>
                  <label htmlFor="aoi-variable" className="block text-xs font-medium text-gray-700 dark:text-slate-300 mb-1">
                    Variable
                  </label>
                  <select
                    id="aoi-variable"
                    value={variable}
                    onChange={(e) => setVariable(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 rounded"
                    data-testid="aoi-subscribe-variable"
                  >
                    {VARIABLE_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor="aoi-comparison" className="block text-xs font-medium text-gray-700 dark:text-slate-300 mb-1">
                      When it
                    </label>
                    <select
                      id="aoi-comparison"
                      value={comparison}
                      onChange={(e) => setComparison(e.target.value as any)}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 rounded"
                      data-testid="aoi-subscribe-comparison"
                    >
                      {COMPARISON_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="aoi-threshold" className="block text-xs font-medium text-gray-700 dark:text-slate-300 mb-1">
                      Threshold
                    </label>
                    <input
                      id="aoi-threshold"
                      type="number"
                      step="any"
                      value={threshold}
                      onChange={(e) => setThreshold(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 rounded"
                      data-testid="aoi-subscribe-threshold"
                    />
                  </div>
                </div>

                {tierInfo && tierInfo.limit !== -1 && (
                  <p className="text-[11px] text-gray-500 dark:text-slate-400">
                    {tierInfo.used} of {tierInfo.limit} alerts used on the {tierInfo.tier} tier.
                  </p>
                )}

                {error && (
                  <p className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950/30 p-2 rounded" data-testid="aoi-subscribe-error">
                    {error}
                  </p>
                )}

                {success && (
                  <p className="text-xs text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/30 p-2 rounded flex items-center gap-1.5" data-testid="aoi-subscribe-success">
                    <Check className="w-3 h-3" aria-hidden="true" />
                    Alert created. You'll get an email when the threshold is crossed.
                  </p>
                )}

                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="px-3 py-1.5 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-800 rounded"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || success}
                    className="px-4 py-1.5 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded disabled:opacity-50"
                    data-testid="aoi-subscribe-submit"
                  >
                    {submitting ? "Creating…" : "Create alert"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
