"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Bookmark,
  Building2,
  Globe,
  Newspaper,
  Search,
  Sparkles,
  Trash2,
  Settings,
  Activity,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SavedItem, SavedItemType } from "@/types";

// Slice 3 (2026-05-25) — polymorphic My Saves page. Replaces the
// article-only /dashboard/saved listing (which stays for backward
// compat). Shows all 8 saved_items types with type-appropriate
// affordances (link, label, delete).

interface TypeMeta {
  label: string;
  icon: typeof Bookmark;
  href: (item: SavedItem) => string | null;
  describe: (item: SavedItem) => string;
}

const TYPE_META: Record<SavedItemType, TypeMeta> = {
  article: {
    label: "Articles",
    icon: Newspaper,
    href: (i) => (i.item_id ? `/articles/${i.item_id}` : null),
    describe: (i) => i.label || "Untitled article",
  },
  analysis: {
    label: "URL analyses",
    icon: Sparkles,
    href: (i) => (i.item_id ? `/analyze?id=${i.item_id}` : null),
    describe: (i) => i.label || "Untitled analysis",
  },
  claim: {
    label: "Claims",
    icon: Activity,
    href: () => null,
    describe: (i) => i.label || i.notes || "Claim",
  },
  search: {
    label: "Searches",
    icon: Search,
    href: (i) => (i.item_ref ? i.item_ref : null),
    describe: (i) => i.label || i.item_ref || "Search",
  },
  company: {
    label: "Companies",
    icon: Building2,
    href: (i) => (i.item_id ? `/companies/${i.item_id}` : null),
    describe: (i) => i.label || "Company",
  },
  feed_setting: {
    label: "Feed settings",
    icon: Settings,
    href: () => null,
    describe: (i) => i.label || "Feed configuration",
  },
  deep_search: {
    label: "Deep searches",
    icon: Sparkles,
    href: () => "/deep-search",
    describe: (i) => i.label || i.item_ref || "Deep search query",
  },
  country: {
    label: "Countries",
    icon: Globe,
    href: (i) => (i.item_ref ? `/country/${i.item_ref}` : null),
    describe: (i) => i.label || i.item_ref || "Country",
  },
};

const TYPE_ORDER: SavedItemType[] = [
  "article",
  "analysis",
  "company",
  "country",
  "search",
  "deep_search",
  "claim",
  "feed_setting",
];

export default function SavesPage() {
  const [items, setItems] = useState<SavedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<SavedItemType | "all">("all");
  const [removing, setRemoving] = useState<string | null>(null);

  const fetchSaves = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.listSavedItems({
        item_type: activeFilter === "all" ? undefined : activeFilter,
        limit: 200,
      });
      setItems(resp.items);
    } catch (err: unknown) {
      const status =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      if (status === 401) setError("Sign in to view your saves.");
      else setError("Couldn't load saves. Try again.");
    } finally {
      setLoading(false);
    }
  }, [activeFilter]);

  useEffect(() => {
    fetchSaves();
  }, [fetchSaves]);

  async function handleRemove(item: SavedItem) {
    if (removing) return;
    setRemoving(item.saved_id);
    try {
      await api.deleteSavedItem(item.saved_id);
      setItems((prev) => prev.filter((i) => i.saved_id !== item.saved_id));
    } catch {
      setError("Couldn't remove that item. Try again.");
    } finally {
      setRemoving(null);
    }
  }

  const counts = useMemo(() => {
    const c: Partial<Record<SavedItemType, number>> = {};
    for (const item of items) c[item.item_type] = (c[item.item_type] ?? 0) + 1;
    return c;
  }, [items]);

  const filteredItems = useMemo(
    () =>
      activeFilter === "all"
        ? items
        : items.filter((i) => i.item_type === activeFilter),
    [items, activeFilter]
  );

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex items-center gap-3 mb-2">
        <Bookmark className="h-6 w-6 text-amber-500" />
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          My Saves
        </h1>
      </div>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
        Everything you&apos;ve saved across the platform — articles, analyses,
        companies, countries, searches, and more.
      </p>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-2 mb-6">
        <FilterChip
          label={`All (${items.length})`}
          active={activeFilter === "all"}
          onClick={() => setActiveFilter("all")}
        />
        {TYPE_ORDER.map((t) => {
          const meta = TYPE_META[t];
          const n = counts[t] ?? 0;
          if (n === 0 && activeFilter !== t) return null;
          return (
            <FilterChip
              key={t}
              label={`${meta.label} (${n})`}
              active={activeFilter === t}
              onClick={() => setActiveFilter(t)}
            />
          );
        })}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-slate-500" data-testid="saves-loading">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading saves…
        </div>
      )}

      {error && !loading && (
        <div className="rounded border border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700 p-4 text-sm text-amber-800 dark:text-amber-200">
          {error}
        </div>
      )}

      {!loading && !error && filteredItems.length === 0 && (
        <div className="text-center py-12 text-slate-500 dark:text-slate-400">
          <Bookmark className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">Nothing saved yet.</p>
          <p className="text-xs mt-1">
            Tap the Save button on any article, company, or search result.
          </p>
        </div>
      )}

      <ul className="space-y-3">
        {filteredItems.map((item) => {
          const meta = TYPE_META[item.item_type];
          const Icon = meta.icon;
          const href = meta.href(item);
          const description = meta.describe(item);

          return (
            <li
              key={item.saved_id}
              className="flex items-start gap-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3 hover:border-clilens-primary transition-colors"
            >
              <div className="mt-1 flex-shrink-0">
                <Icon className="h-5 w-5 text-clilens-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400 font-medium">
                    {meta.label.replace(/s$/, "")}
                  </span>
                  {item.folder && item.folder !== "default" && (
                    <span className="text-[10px] text-slate-400">
                      · {item.folder}
                    </span>
                  )}
                </div>
                {href ? (
                  <Link
                    href={href}
                    className="block text-sm font-medium text-slate-900 dark:text-slate-100 hover:text-clilens-primary truncate"
                  >
                    {description}
                  </Link>
                ) : (
                  <span className="block text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                    {description}
                  </span>
                )}
                {item.notes && (
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                    {item.notes}
                  </p>
                )}
                {item.created_at && (
                  <p className="text-[11px] text-slate-400 mt-1">
                    Saved {new Date(item.created_at).toLocaleDateString()}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleRemove(item)}
                disabled={removing === item.saved_id}
                className="flex-shrink-0 p-1.5 text-slate-400 hover:text-red-500 disabled:opacity-40 disabled:cursor-wait"
                aria-label={`Remove saved ${item.item_type}`}
                title="Remove from saves"
              >
                {removing === item.saved_id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "px-3 py-1 text-xs rounded-full bg-clilens-primary text-white"
          : "px-3 py-1 text-xs rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
      }
    >
      {label}
    </button>
  );
}
