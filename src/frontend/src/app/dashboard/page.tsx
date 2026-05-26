"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Bookmark,
  Search,
  CalendarDays,
  Crown,
  Globe,
  Sparkles,
  FileText,
  Rss,
  ArrowRight,
  Loader2,
  TrendingUp,
  Briefcase,
  GraduationCap,
  Newspaper,
  Building2,
  ShieldCheck,
  Download,
  ScrollText,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface DashboardStats {
  articles_read_week: number;
  articles_read_total: number;
  bookmarks_count: number;
  searches_count: number;
  days_active: number;
  current_tier: string;
  tier_usage: {
    articles_used: number;
    articles_limit: number;
    searches_used: number;
    searches_limit: number;
  };
}

interface ReadingHistoryItem {
  article_id: string;
  title: string;
  source_name: string;
  read_at: string;
  credibility?: string;
}

interface SavedItemCounts {
  article: number;
  company: number;
  country: number;
  analysis: number;
  claim: number;
  search: number;
  deep_search: number;
  feed_setting: number;
}

// Polish wave 3 (2026-05-27): personas + export wiring for logged-in users.
// Each lens points to the surface that's the entry point for that workflow.
const PERSONA_LENSES = [
  {
    id: "journalist",
    label: "Journalist",
    icon: Newspaper,
    href: "/search?credibility_min=70",
    color: "bg-blue-50 text-blue-700 border-blue-200",
    blurb: "Verified-source feed + provenance ledger walks",
  },
  {
    id: "esg",
    label: "ESG Officer",
    icon: Briefcase,
    href: "/companies?view=business",
    color: "bg-emerald-50 text-emerald-700 border-emerald-200",
    blurb: "Corporate disclosures + SBTi + ECGT compliance chips",
  },
  {
    id: "researcher",
    label: "Researcher",
    icon: GraduationCap,
    href: "/research",
    color: "bg-purple-50 text-purple-700 border-purple-200",
    blurb: "PDF upload + CrossRef subscriptions + methodology",
  },
  {
    id: "policymaker",
    label: "Policymaker",
    icon: ShieldCheck,
    href: "/map",
    color: "bg-amber-50 text-amber-700 border-amber-200",
    blurb: "Country passport + scenario explorer + NDC indicators",
  },
  {
    id: "analyst",
    label: "Financial Analyst",
    icon: TrendingUp,
    href: "/companies",
    color: "bg-teal-50 text-teal-700 border-teal-200",
    blurb: "SBTi-validated portfolio + transition risk",
  },
  {
    id: "business",
    label: "Business Decision-maker",
    icon: Building2,
    href: "/country/DE?view=business",
    color: "bg-indigo-50 text-indigo-700 border-indigo-200",
    blurb: "Board-ready risk framing + jurisdiction snapshots",
  },
];

const TIER_COLORS: Record<string, string> = {
  freemium: "bg-gray-100 text-gray-700",
  basic: "bg-blue-100 text-blue-700",
  professional: "bg-teal-100 text-teal-700",
  enterprise: "bg-purple-100 text-purple-700",
};

const TIER_LABELS: Record<string, string> = {
  freemium: "Free",
  basic: "Basic",
  professional: "Professional",
  enterprise: "Enterprise",
};

const QUICK_ACTIONS = [
  { href: "/map", label: "Browse Map", icon: Globe, color: "bg-emerald-50 text-emerald-600" },
  { href: "/deep-search", label: "Deep Search", icon: Sparkles, color: "bg-purple-50 text-purple-600" },
  { href: "/analyze", label: "Analyze URL", icon: FileText, color: "bg-orange-50 text-orange-600" },
  { href: "/feed", label: "My Feed", icon: Rss, color: "bg-blue-50 text-blue-600" },
];

export default function DashboardPage() {
  const { user, token } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [history, setHistory] = useState<ReadingHistoryItem[]>([]);
  const [savedCounts, setSavedCounts] = useState<SavedItemCounts | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;

    async function fetchData() {
      try {
        const headers = { Authorization: `Bearer ${token}` };

        // Polish wave 3 (2026-05-27): pull saved-items breakdown so the
        // dashboard can show how many items the user has parked per type.
        const [statsResp, historyResp, savedResp] = await Promise.all([
          fetch(`${API_URL}/api/user/dashboard-stats`, { headers }),
          fetch(`${API_URL}/api/user/reading-history?limit=5`, { headers }),
          fetch(`${API_URL}/api/user/saved?limit=200`, { headers }),
        ]);

        if (statsResp.ok) {
          setStats(await statsResp.json());
        }
        if (historyResp.ok) {
          const data = await historyResp.json();
          setHistory(data.items || data || []);
        }
        if (savedResp.ok) {
          const sd = await savedResp.json();
          const items: Array<{ item_type: string }> = sd?.items || sd || [];
          const counts: SavedItemCounts = {
            article: 0, company: 0, country: 0, analysis: 0,
            claim: 0, search: 0, deep_search: 0, feed_setting: 0,
          };
          for (const it of items) {
            const k = (it.item_type || "") as keyof SavedItemCounts;
            if (k in counts) counts[k] = (counts[k] || 0) + 1;
          }
          setSavedCounts(counts);
        }
      } catch {
        // Non-critical: dashboard still renders
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [token]);

  const tier = user?.subscription_tier || "freemium";

  return (
    <div className="space-y-6">
      {/* Welcome header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.full_name?.split(" ")[0] || "there"}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Here is what is happening with your climate intelligence.
          </p>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1 rounded-full ${TIER_COLORS[tier]}`}
        >
          <Crown className="h-4 w-4" />
          {TIER_LABELS[tier] || tier} Plan
        </span>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Articles This Week"
          value={stats?.articles_read_week ?? "-"}
          icon={BookOpen}
          loading={loading}
        />
        <StatCard
          label="Bookmarks"
          value={stats?.bookmarks_count ?? "-"}
          icon={Bookmark}
          loading={loading}
        />
        <StatCard
          label="Searches"
          value={stats?.searches_count ?? "-"}
          icon={Search}
          loading={loading}
        />
        <StatCard
          label="Days Active"
          value={stats?.days_active ?? "-"}
          icon={CalendarDays}
          loading={loading}
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent reading history */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Recent Reading</h2>
            <Link
              href="/dashboard/history"
              className="text-sm text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-12">
              <BookOpen className="h-10 w-10 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No reading history yet.</p>
              <Link
                href="/"
                className="text-sm text-teal-600 hover:text-teal-700 font-medium mt-1 inline-block"
              >
                Browse articles
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {history.map((item) => (
                <Link
                  key={item.article_id}
                  href={`/articles/${item.article_id}`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors group"
                >
                  <div className="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center flex-shrink-0">
                    <BookOpen className="h-4 w-4 text-teal-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate group-hover:text-teal-700">
                      {item.title}
                    </p>
                    <p className="text-xs text-gray-500">
                      {item.source_name} &middot;{" "}
                      {new Date(item.read_at).toLocaleDateString()}
                    </p>
                  </div>
                  {item.credibility && (
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        item.credibility === "HIGH"
                          ? "bg-green-100 text-green-700"
                          : item.credibility === "MEDIUM"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-red-100 text-red-700"
                      }`}
                    >
                      {item.credibility}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Subscription status & Quick actions */}
        <div className="space-y-6">
          {/* Subscription card */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-900 mb-3">Subscription</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Current Plan</span>
                <span className="text-sm font-semibold text-gray-900">
                  {TIER_LABELS[tier] || tier}
                </span>
              </div>
              {stats?.tier_usage && (
                <>
                  <div>
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>Articles today</span>
                      <span>
                        {stats.tier_usage.articles_used}
                        {stats.tier_usage.articles_limit > 0
                          ? ` / ${stats.tier_usage.articles_limit}`
                          : " / Unlimited"}
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-teal-500 rounded-full transition-all"
                        style={{
                          width: `${
                            stats.tier_usage.articles_limit > 0
                              ? Math.min(
                                  (stats.tier_usage.articles_used /
                                    stats.tier_usage.articles_limit) *
                                    100,
                                  100,
                                )
                              : 10
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                </>
              )}
              {tier === "freemium" && (
                <Link
                  href="/dashboard/subscription"
                  className="block w-full text-center py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
                >
                  Upgrade Plan
                </Link>
              )}
              {tier !== "freemium" && (
                <Link
                  href="/dashboard/subscription"
                  className="block w-full text-center py-2 border border-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  Manage Subscription
                </Link>
              )}
            </div>
          </div>

          {/* Quick actions */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-900 mb-3">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_ACTIONS.map(({ href, label, icon: Icon, color }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex flex-col items-center gap-1.5 p-3 rounded-lg hover:bg-gray-50 transition-colors group"
                >
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}
                  >
                    <Icon className="h-4.5 w-4.5" />
                  </div>
                  <span className="text-xs font-medium text-gray-700 group-hover:text-gray-900">
                    {label}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Polish wave 3 (2026-05-27) — persona-tied analytics + exports.
          Closes End2End audit §5/§9: every persona has a real entry point,
          and saved-item-type counts surface what the user has actively
          collected per workflow. Premium-gated exports link directly to
          the upgrade page rather than failing inline. */}
      <PersonaLensSection
        tier={tier}
        savedCounts={savedCounts}
        loading={loading}
      />

      <ExportsAndAnalyticsSection tier={tier} savedCounts={savedCounts} />
    </div>
  );
}

function PersonaLensSection({
  tier,
  savedCounts,
  loading,
}: {
  tier: string;
  savedCounts: SavedItemCounts | null;
  loading: boolean;
}) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <header className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-gray-900">Persona Lens</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Jump into the workflow that matches your role. Each lens preloads
            credibility + view filters appropriate to that audience.
          </p>
        </div>
        {!loading && savedCounts && (
          <div className="text-xs text-gray-500 hidden sm:flex gap-2">
            <span>{savedCounts.article} saved articles</span>
            <span>·</span>
            <span>{savedCounts.company} companies</span>
            <span>·</span>
            <span>{savedCounts.country} countries</span>
          </div>
        )}
      </header>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {PERSONA_LENSES.map((p) => {
          const Icon = p.icon;
          return (
            <Link
              key={p.id}
              href={p.href}
              className={`group block rounded-lg border p-3 transition-colors hover:shadow-sm ${p.color}`}
            >
              <div className="flex items-start gap-2.5">
                <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="font-semibold text-sm">{p.label}</div>
                  <div className="text-xs opacity-90 mt-0.5">{p.blurb}</div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
      {tier === "freemium" && (
        <p className="text-xs text-gray-500 mt-3 italic">
          Some persona surfaces (corporate report analysis, deep search,
          research upload) require a paid tier — see{" "}
          <Link href="/dashboard/subscription" className="text-teal-700 hover:underline">
            Subscription
          </Link>{" "}
          to upgrade.
        </p>
      )}
    </section>
  );
}

function ExportsAndAnalyticsSection({
  tier,
  savedCounts,
}: {
  tier: string;
  savedCounts: SavedItemCounts | null;
}) {
  const isPaid = ["standard", "basic", "professional", "enterprise"].includes(tier);
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <header className="mb-4">
        <h2 className="font-semibold text-gray-900">Analytics & Exports</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Pull your saved items as a report or feed the API directly. Paid
          tiers required for the heavy exports.
        </p>
      </header>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <ExportTile
          label="Saved articles → CSV"
          icon={Download}
          count={savedCounts?.article ?? 0}
          href="/saves?export=csv&type=article"
          enabled={isPaid}
        />
        <ExportTile
          label="Saved companies → CSV"
          icon={Building2}
          count={savedCounts?.company ?? 0}
          href="/saves?export=csv&type=company"
          enabled={isPaid}
        />
        <ExportTile
          label="Country comparison brief"
          icon={ScrollText}
          count={savedCounts?.country ?? 0}
          href="/saves?export=pdf&type=country"
          enabled={isPaid}
        />
        <ExportTile
          label="My saved searches"
          icon={Search}
          count={(savedCounts?.search ?? 0) + (savedCounts?.deep_search ?? 0)}
          href="/saves?type=search"
          enabled={true}
        />
      </div>
      {!isPaid && (
        <p className="text-xs text-gray-500 mt-3 italic">
          Article / company / country exports require a Standard subscription
          or higher. Saved searches are available to all tiers.
        </p>
      )}
    </section>
  );
}

function ExportTile({
  label, icon: Icon, count, href, enabled,
}: {
  label: string;
  icon: any;
  count: number;
  href: string;
  enabled: boolean;
}) {
  return (
    <Link
      href={enabled ? href : "/dashboard/subscription"}
      className={`flex flex-col gap-1 p-3 rounded-lg border transition-colors ${
        enabled
          ? "border-gray-200 hover:bg-gray-50"
          : "border-gray-100 bg-gray-50 opacity-70 hover:opacity-100"
      }`}
    >
      <div className="flex items-center justify-between">
        <Icon className="h-4 w-4 text-gray-500" />
        <span className="text-sm font-semibold text-gray-900">{count}</span>
      </div>
      <span className="text-xs text-gray-700 leading-snug">{label}</span>
      {!enabled && (
        <span className="text-[10px] text-amber-700 mt-0.5">Standard+</span>
      )}
    </Link>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  loading,
}: {
  label: string;
  value: number | string;
  icon: any;
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <Icon className="h-5 w-5 text-gray-400" />
        <TrendingUp className="h-3.5 w-3.5 text-teal-500" />
      </div>
      {loading ? (
        <div className="h-8 w-16 animate-shimmer rounded" />
      ) : (
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      )}
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}
