"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  History,
  BookOpen,
  Clock,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Filter,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface HistoryItem {
  article_id: string;
  title: string;
  source_name: string;
  read_at: string;
  read_duration_seconds?: number;
  scroll_depth_pct?: number;
  credibility?: string;
}

const DATE_RANGES = [
  { label: "Last 7 days", value: "7" },
  { label: "Last 30 days", value: "30" },
  { label: "Last 90 days", value: "90" },
  { label: "All time", value: "all" },
];

export default function ReadingHistoryPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [dateRange, setDateRange] = useState("30");

  const limit = 20;

  const fetchHistory = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (dateRange !== "all") {
        params.set("days", dateRange);
      }

      const resp = await fetch(
        `${API_URL}/api/user/reading-history?${params}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (resp.ok) {
        const data = await resp.json();
        const list = data.items || data || [];
        setItems(list);
        setHasMore(list.length >= limit);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token, page, dateRange]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  function formatDuration(seconds?: number): string {
    if (!seconds) return "-";
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <History className="h-6 w-6 text-teal-600" />
            Reading History
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Articles you have read recently
          </p>
        </div>

        {/* Date range filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={dateRange}
            onChange={(e) => {
              setDateRange(e.target.value);
              setPage(1);
            }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
          >
            {DATE_RANGES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="bg-white rounded-xl border border-gray-200">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <BookOpen className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No reading history found</p>
            <p className="text-sm text-gray-400 mt-1">
              Start reading articles and they will appear here.
            </p>
            <Link
              href="/"
              className="inline-block mt-4 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
            >
              Browse Articles
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {items.map((item) => (
              <Link
                key={`${item.article_id}-${item.read_at}`}
                href={`/articles/${item.article_id}`}
                className="flex items-center gap-4 p-4 hover:bg-gray-50 transition-colors group"
              >
                <div className="w-10 h-10 rounded-lg bg-teal-50 flex items-center justify-center flex-shrink-0">
                  <BookOpen className="h-5 w-5 text-teal-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate group-hover:text-teal-700">
                    {item.title}
                  </p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500">
                      {item.source_name}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(item.read_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                    {item.read_duration_seconds != null && (
                      <span className="text-xs text-gray-400 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDuration(item.read_duration_seconds)}
                      </span>
                    )}
                  </div>
                </div>
                {item.credibility && (
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded flex-shrink-0 ${
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

        {/* Pagination */}
        {!loading && items.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <span className="text-sm text-gray-500">Page {page}</span>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!hasMore}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
