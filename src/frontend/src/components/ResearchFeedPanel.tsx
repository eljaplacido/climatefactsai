"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell, BellOff, Loader2, Plus, Trash2, ExternalLink, BookOpen, AlertCircle,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Polish wave 2 (2026-05-26) — frontend for deferred audit item #13
// (research feed). Wraps three shipped endpoints:
//   POST   /api/research/subscriptions
//   GET    /api/research/subscriptions
//   DELETE /api/research/subscriptions/{id}
//   GET    /api/research/feed
// Auth-gated — shows a "Sign in to follow topics" stub when no token.

interface Subscription {
  subscription_id: string;
  topic: string;
  keywords: string[];
  is_active: boolean;
  last_polled_at: string | null;
  created_at: string;
}

interface FeedItem {
  item_id: string;
  topic: string;
  doi: string | null;
  title: string;
  authors: string[];
  journal: string | null;
  published_date: string | null;
  crossref_url: string | null;
  discovered_at: string;
}

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("clilens_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function hasAuth(): boolean {
  return Boolean(authHeaders().Authorization);
}

export default function ResearchFeedPanel() {
  const [authed, setAuthed] = useState(false);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [newTopic, setNewTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthed(hasAuth());
  }, []);

  const refresh = useCallback(async () => {
    if (!hasAuth()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [subsResp, feedResp] = await Promise.all([
        fetch(`${API_URL}/api/research/subscriptions`, { headers: authHeaders() }),
        fetch(`${API_URL}/api/research/feed?limit=30`, { headers: authHeaders() }),
      ]);
      if (subsResp.ok) setSubs(await subsResp.json());
      if (feedResp.ok) setFeed(await feedResp.json());
    } catch (e: any) {
      setError(e?.message || "Failed to load research feed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleSubscribe() {
    const topic = newTopic.trim();
    if (!topic || busy) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/api/research/subscriptions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ topic }),
      });
      if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        setError(
          body?.detail?.message ||
            "Free tier subscription quota reached. Upgrade for more."
        );
        return;
      }
      if (!resp.ok) {
        setError(`Subscribe failed (HTTP ${resp.status})`);
        return;
      }
      setNewTopic("");
      await refresh();
    } catch (e: any) {
      setError(e?.message || "Subscribe failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleUnsubscribe(subscription_id: string) {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`${API_URL}/api/research/subscriptions/${subscription_id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  if (!authed) {
    return (
      <div
        className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm"
        data-testid="research-feed-auth-required"
      >
        <div className="flex items-start gap-3">
          <Bell className="h-5 w-5 text-teal-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-base font-semibold text-gray-900">Research feed</h3>
            <p className="text-sm text-gray-600 mt-1">
              Subscribe to a research topic (e.g. <em>Arctic sea ice</em>,
              <em> CBAM compliance</em>, <em>methane emissions accounting</em>)
              and the platform's CrossRef poller will deliver new papers here daily.
            </p>
            <p className="text-xs text-gray-500 mt-2">
              <a href="/login" className="text-clilens-primary hover:underline font-medium">
                Sign in
              </a>{" "}
              to manage subscriptions and see your feed.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-5"
      data-testid="research-feed-panel"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <Bell className="h-4 w-4 text-teal-600" />
            Research feed
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Subscribe to topics. Daily CrossRef poll discovers new papers automatically.
          </p>
        </div>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-gray-400" />}
      </div>

      {/* Subscribe form */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newTopic}
          onChange={(e) => setNewTopic(e.target.value)}
          placeholder="Topic to follow (e.g. CBAM compliance, methane accounting)"
          className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubscribe();
          }}
          data-testid="research-feed-topic-input"
        />
        <button
          type="button"
          onClick={handleSubscribe}
          disabled={busy || newTopic.trim().length < 2}
          className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 disabled:opacity-50 flex items-center gap-1.5"
          data-testid="research-feed-subscribe-btn"
        >
          <Plus className="h-4 w-4" />
          Subscribe
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2.5" role="alert">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* Active subscriptions */}
      {subs.length > 0 && (
        <div>
          <h4 className="text-xs uppercase tracking-wider text-gray-500 font-medium mb-2">
            Following ({subs.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {subs.map((s) => (
              <span
                key={s.subscription_id}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-50 text-teal-800 text-xs rounded-full border border-teal-200"
                data-testid={`research-feed-subscription-${s.topic}`}
              >
                {s.topic}
                <button
                  type="button"
                  onClick={() => handleUnsubscribe(s.subscription_id)}
                  disabled={busy}
                  className="text-teal-600 hover:text-red-600"
                  aria-label={`Unsubscribe ${s.topic}`}
                  title="Unsubscribe"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {subs.length === 0 && !loading && (
        <div className="text-center py-6 text-xs text-gray-400">
          <BellOff className="h-5 w-5 mx-auto mb-1.5 opacity-50" />
          No active subscriptions yet. Subscribe above to start receiving papers.
        </div>
      )}

      {/* Discovered papers */}
      {feed.length > 0 && (
        <div>
          <h4 className="text-xs uppercase tracking-wider text-gray-500 font-medium mb-2">
            Recent papers in your feed ({feed.length})
          </h4>
          <ul className="space-y-2">
            {feed.map((item) => (
              <li
                key={item.item_id}
                className="p-3 rounded-lg border border-gray-100 hover:border-teal-300 bg-gray-50/50 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <BookOpen className="h-4 w-4 text-teal-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] uppercase tracking-wide text-teal-700 font-medium">
                      {item.topic}
                    </div>
                    {item.crossref_url ? (
                      <a
                        href={item.crossref_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-sm font-medium text-gray-900 hover:text-clilens-primary"
                      >
                        {item.title}{" "}
                        <ExternalLink className="inline h-3 w-3 opacity-60" />
                      </a>
                    ) : (
                      <span className="block text-sm font-medium text-gray-900">
                        {item.title}
                      </span>
                    )}
                    <div className="flex flex-wrap gap-2 mt-1 text-[11px] text-gray-500">
                      {item.authors.length > 0 && (
                        <span>{item.authors.slice(0, 3).join(", ")}</span>
                      )}
                      {item.journal && (
                        <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">
                          {item.journal}
                        </span>
                      )}
                      {item.published_date && (
                        <span>Published {item.published_date.slice(0, 10)}</span>
                      )}
                      {item.doi && (
                        <span className="text-purple-700">DOI: {item.doi}</span>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
