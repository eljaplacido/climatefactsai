"use client";

import { useEffect, useState } from "react";
import {
  Loader2, Plus, Check, Microscope, Scale, Building2, TrendingUp,
  AlertTriangle, BookOpen,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Golden Example #6 (2026-05-27) — surfaces the curated catalogue
// of climate-research topics (mig 048: default_research_topics, 12 rows
// covering science / policy / corporate / finance / risk). Users one-
// click subscribe; the cn-research-poll cron then delivers CrossRef
// DOIs to their feed.

interface DefaultTopic {
  topic_id: string;
  slug: string;
  label: string;
  description?: string;
  keywords: string[];
  category?: string;
  sort_order: number;
}

const CATEGORY_ICON: Record<string, any> = {
  science: Microscope,
  policy: Scale,
  corporate: Building2,
  finance: TrendingUp,
  risk: AlertTriangle,
};

const CATEGORY_TONE: Record<string, string> = {
  science: "bg-blue-50 text-blue-800 border-blue-200",
  policy: "bg-amber-50 text-amber-800 border-amber-200",
  corporate: "bg-emerald-50 text-emerald-800 border-emerald-200",
  finance: "bg-teal-50 text-teal-800 border-teal-200",
  risk: "bg-red-50 text-red-800 border-red-200",
};

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("clilens_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface Props {
  /** Slugs the current user is already subscribed to (so we can show "Following" state). */
  subscribedTopicLabels?: string[];
  /** Notify parent after subscribe so it can refresh its own state. */
  onSubscribed?: () => void;
}

export default function DefaultTopicsBrowser({
  subscribedTopicLabels = [],
  onSubscribed,
}: Props) {
  const [topics, setTopics] = useState<DefaultTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API_URL}/api/research/default-topics`);
        if (r.ok) {
          const data = await r.json();
          setTopics(Array.isArray(data) ? data : []);
        }
      } catch {
        // public endpoint — degrade silently
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSubscribe(slug: string, label: string) {
    if (busy) return;
    const auth = authHeaders();
    if (!auth.Authorization) {
      setError("Sign in to subscribe to research topics.");
      return;
    }
    setBusy(slug);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/api/research/subscriptions/default`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth },
        body: JSON.stringify({ slugs: [slug] }),
      });
      if (r.status === 429) {
        const d = await r.json().catch(() => ({}));
        setError(
          d?.detail?.message ||
            "Subscription quota reached. Upgrade for more.",
        );
        return;
      }
      if (!r.ok) {
        setError(`Subscribe failed (HTTP ${r.status})`);
        return;
      }
      onSubscribed?.();
    } catch (e: any) {
      setError(e?.message || "Subscribe failed");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-gray-500 text-sm py-6">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading curated topics…
      </div>
    );
  }

  if (topics.length === 0) {
    return (
      <div className="text-sm text-gray-500 py-6">
        No curated topics available. The default catalogue ships via mig 048;
        re-run migrations if you don't see anything here.
      </div>
    );
  }

  // Group by category for visual organization.
  const byCategory: Record<string, DefaultTopic[]> = {};
  topics.forEach((t) => {
    const k = t.category || "other";
    (byCategory[k] = byCategory[k] || []).push(t);
  });

  return (
    <div className="space-y-5">
      <header>
        <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-teal-600" />
          Curated research topics
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Subscribe to any of these to receive newly published peer-reviewed
          papers via CrossRef. The poller runs daily at 03:30 UTC.
        </p>
      </header>

      {error && (
        <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2.5">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {Object.entries(byCategory).map(([cat, list]) => {
        const Icon = CATEGORY_ICON[cat] || BookOpen;
        const tone = CATEGORY_TONE[cat] || "bg-gray-50 text-gray-800 border-gray-200";
        return (
          <div key={cat}>
            <h4 className="text-xs uppercase tracking-wider text-gray-500 font-medium mb-2 flex items-center gap-1.5">
              <Icon className="h-3 w-3" /> {cat}
            </h4>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {list.map((t) => {
                const subscribed = subscribedTopicLabels.includes(t.label);
                return (
                  <div
                    key={t.slug}
                    className={`rounded-lg border p-3 ${tone} flex flex-col gap-1.5`}
                  >
                    <div className="font-medium text-sm">{t.label}</div>
                    {t.description && (
                      <div className="text-[11px] opacity-80 leading-relaxed">
                        {t.description}
                      </div>
                    )}
                    {t.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1 text-[10px]">
                        {t.keywords.slice(0, 4).map((kw) => (
                          <span
                            key={kw}
                            className="bg-white/70 border border-current/20 px-1.5 py-0.5 rounded"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      disabled={subscribed || busy === t.slug}
                      onClick={() => handleSubscribe(t.slug, t.label)}
                      className={`mt-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded text-xs font-medium transition-colors ${
                        subscribed
                          ? "bg-gray-100 text-gray-500 cursor-default"
                          : "bg-white border border-current/30 hover:bg-white/80"
                      }`}
                    >
                      {busy === t.slug ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" /> Adding…
                        </>
                      ) : subscribed ? (
                        <>
                          <Check className="h-3 w-3" /> Following
                        </>
                      ) : (
                        <>
                          <Plus className="h-3 w-3" /> Subscribe
                        </>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
