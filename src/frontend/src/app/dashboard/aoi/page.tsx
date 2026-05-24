"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  Loader2,
  Trash2,
  AlertTriangle,
  Globe,
  Activity,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

/**
 * AOI subscriptions management page — Phase 5A (2026-05-24).
 *
 * Lists the user's active alert subscriptions and lets them delete
 * (soft-delete) any of them. Each row shows:
 *   - country code + variable + rule + threshold (the "what")
 *   - last_fired_at + last_observed_value + fire_count (the "is it working")
 *   - delete button (soft-delete)
 *
 * Closes the Phase 3 UX loop: the user can already CREATE subscriptions
 * from the Country Passport `<AOISubscribeButton>`, but until this page
 * there was no way to LIST or DELETE them. Without this view the AOI
 * feature is a one-way valve (subscriptions accumulate, can't be pruned).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface AOISubscription {
  subscription_id: string;
  country_code: string;
  variable: string;
  comparison: string;
  threshold: number;
  delivery_channel: string;
  active: boolean;
  last_fired_at: string | null;
  last_observed_value: number | null;
  fire_count: number;
  label: string | null;
  created_at: string | null;
}

const COMPARISON_VERB: Record<string, string> = {
  gt: "exceeds",
  gte: "≥",
  lt: "is below",
  lte: "≤",
  eq: "equals",
};

const VARIABLE_LABEL: Record<string, string> = {
  temperature_anomaly_c: "Temperature anomaly (°C)",
  renewable_share_pct: "Renewable share (%)",
  co2_emissions_per_capita: "CO₂ emissions per capita (t)",
  climate_risk_score: "Climate risk score (0–100)",
};

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH} hr ago`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 30) return `${diffD} day${diffD === 1 ? "" : "s"} ago`;
    return d.toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function AOIManagementPage() {
  const { token, isLoggedIn } = useAuth();
  const [subscriptions, setSubscriptions] = useState<AOISubscription[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchSubscriptions = useCallback(async () => {
    if (!token) {
      setSubscriptions([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/aoi-subscriptions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data: AOISubscription[] = await resp.json();
      setSubscriptions(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || "Failed to load subscriptions");
      setSubscriptions([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  async function handleDelete(subscriptionId: string) {
    if (!token) return;
    setDeletingId(subscriptionId);
    try {
      const resp = await fetch(
        `${API_BASE}/api/aoi-subscriptions/${encodeURIComponent(subscriptionId)}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (resp.status === 204 || resp.ok) {
        // Optimistically drop from local state — saves one refetch
        setSubscriptions((prev) =>
          prev ? prev.filter((s) => s.subscription_id !== subscriptionId) : prev,
        );
      } else {
        setError(`Could not delete (HTTP ${resp.status})`);
      }
    } catch (e: any) {
      setError(e?.message || "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  if (!isLoggedIn) {
    return (
      <div className="max-w-3xl mx-auto text-center py-16">
        <Bell className="h-12 w-12 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">My alerts</h1>
        <p className="text-gray-500 mb-6">
          Sign in to manage your climate alert subscriptions.
        </p>
        <Link
          href="/login?redirect=/dashboard/aoi"
          className="px-6 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition"
        >
          Sign In
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="aoi-management-page">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100 flex items-center gap-2">
          <Bell className="h-6 w-6 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          My alerts
        </h1>
        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
          Threshold-based climate alerts you've subscribed to. We poll hourly
          and email you when a threshold crosses.
        </p>
      </div>

      {error && (
        <div
          className="p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 rounded-lg flex items-center gap-2 text-sm text-red-700 dark:text-red-300"
          role="alert"
          data-testid="aoi-management-error"
        >
          <AlertTriangle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20" data-testid="aoi-management-loading">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" aria-hidden="true" />
        </div>
      ) : !subscriptions || subscriptions.length === 0 ? (
        <div
          className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 text-center py-16"
          data-testid="aoi-management-empty"
        >
          <Bell className="h-10 w-10 text-gray-300 dark:text-slate-600 mx-auto mb-3" aria-hidden="true" />
          <p className="text-gray-500 dark:text-slate-400 font-medium">
            No active alerts yet
          </p>
          <p className="text-sm text-gray-400 dark:text-slate-500 mt-1 max-w-md mx-auto">
            Open any country's climate passport and click "Subscribe to alerts"
            to set a threshold rule for a climate variable.
          </p>
          <Link
            href="/map"
            className="inline-block mt-4 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
          >
            Open the map
          </Link>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 divide-y divide-gray-100 dark:divide-slate-800">
          {subscriptions.map((sub) => {
            const verb = COMPARISON_VERB[sub.comparison] || sub.comparison;
            const varLabel = VARIABLE_LABEL[sub.variable] || sub.variable;
            const isDeleting = deletingId === sub.subscription_id;
            return (
              <div
                key={sub.subscription_id}
                className="p-4 hover:bg-gray-50 dark:hover:bg-slate-800/50"
                data-testid="aoi-management-row"
                data-subscription-id={sub.subscription_id}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link
                        href={`/country/${sub.country_code}`}
                        className="inline-flex items-center gap-1 text-sm font-semibold text-gray-900 dark:text-slate-100 hover:text-teal-700 dark:hover:text-teal-300"
                      >
                        <Globe className="h-3.5 w-3.5" aria-hidden="true" />
                        {sub.country_code}
                      </Link>
                      <span className="text-xs text-gray-400 dark:text-slate-500">·</span>
                      <span className="text-sm text-gray-700 dark:text-slate-300">
                        {varLabel} <strong>{verb} {sub.threshold}</strong>
                      </span>
                    </div>
                    {sub.label && (
                      <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5 italic truncate">
                        {sub.label}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-500 dark:text-slate-400">
                      <span className="inline-flex items-center gap-1">
                        <Activity className="h-3 w-3" aria-hidden="true" />
                        Last fired: <strong>{formatRelativeTime(sub.last_fired_at)}</strong>
                      </span>
                      <span>
                        Fires: <strong>{sub.fire_count}</strong>
                      </span>
                      {sub.last_observed_value != null && (
                        <span>
                          Last value: <strong>{sub.last_observed_value}</strong>
                        </span>
                      )}
                      <span className="text-gray-400 dark:text-slate-500">
                        via {sub.delivery_channel}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(sub.subscription_id)}
                    disabled={isDeleting}
                    className="p-1.5 text-gray-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 rounded transition-colors disabled:opacity-50"
                    aria-label={`Delete alert for ${sub.country_code} ${sub.variable}`}
                    data-testid="aoi-management-delete"
                  >
                    {isDeleting ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
