"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Bookmark,
  Loader2,
  Trash2,
  FolderOpen,
  ChevronLeft,
  ChevronRight,
  BookmarkPlus,
  StickyNote,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface BookmarkItem {
  article_id: string;
  title: string;
  source_name: string;
  bookmarked_at: string;
  folder: string;
  notes?: string;
  credibility?: string;
}

export default function SavedArticlesPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<BookmarkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [folders, setFolders] = useState<string[]>(["default"]);
  const [activeFolder, setActiveFolder] = useState("default");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  const limit = 20;

  const fetchBookmarks = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
        folder: activeFolder,
      });

      const resp = await fetch(`${API_URL}/api/user/bookmarks?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        const data = await resp.json();
        const list = data.items || data || [];
        setItems(list);
        setHasMore(list.length >= limit);

        // Extract unique folders from all bookmarks
        if (data.folders) {
          setFolders(data.folders);
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token, page, activeFolder]);

  useEffect(() => {
    fetchBookmarks();
  }, [fetchBookmarks]);

  async function removeBookmark(articleId: string) {
    if (!token) return;
    setRemoving(articleId);
    try {
      const resp = await fetch(`${API_URL}/api/user/bookmarks/${articleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        setItems((prev) => prev.filter((i) => i.article_id !== articleId));
      }
    } catch {
      // ignore
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Bookmark className="h-6 w-6 text-teal-600" />
          Saved Articles
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Your bookmarked articles organized by folder
        </p>
      </div>

      {/* Folder tabs */}
      <div className="flex items-center gap-1 border-b border-gray-200 overflow-x-auto">
        {folders.map((folder) => (
          <button
            key={folder}
            onClick={() => {
              setActiveFolder(folder);
              setPage(1);
            }}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeFolder === folder
                ? "border-teal-500 text-teal-700"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            <FolderOpen className="h-3.5 w-3.5" />
            {folder === "default" ? "All Saved" : folder}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 text-center py-20">
          <BookmarkPlus className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No saved articles yet</p>
          <p className="text-sm text-gray-400 mt-1">
            Start saving articles to keep track of important climate news.
          </p>
          <Link
            href="/"
            className="inline-block mt-4 px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
          >
            Browse Articles
          </Link>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <div
              key={item.article_id}
              className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow group"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
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
                <button
                  onClick={() => removeBookmark(item.article_id)}
                  disabled={removing === item.article_id}
                  className="text-gray-400 hover:text-red-500 transition-colors p-1 -m-1 opacity-0 group-hover:opacity-100"
                  title="Remove bookmark"
                >
                  {removing === item.article_id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
              </div>

              <Link
                href={`/articles/${item.article_id}`}
                className="block mb-2"
              >
                <h3 className="text-sm font-semibold text-gray-900 line-clamp-2 group-hover:text-teal-700 transition-colors">
                  {item.title}
                </h3>
              </Link>

              <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
                <span>{item.source_name}</span>
                <span className="text-gray-300">|</span>
                <span>
                  {new Date(item.bookmarked_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </div>

              {item.notes && (
                <div className="flex items-start gap-1.5 p-2 bg-yellow-50 rounded-lg">
                  <StickyNote className="h-3 w-3 text-yellow-500 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-yellow-700 line-clamp-2">
                    {item.notes}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {!loading && items.length > 0 && (
        <div className="flex items-center justify-between">
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
  );
}
