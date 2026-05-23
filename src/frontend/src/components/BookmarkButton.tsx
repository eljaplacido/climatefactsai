"use client";

import { useState, useEffect } from "react";
import { Bookmark } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";

const STORAGE_KEY = "clilens-bookmarks";

function getBookmarks(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function setBookmarks(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // localStorage full or unavailable
  }
}

interface BookmarkButtonProps {
  articleId: string;
  size?: "sm" | "md";
}

function hasAuthToken(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem("clilens_token"));
}

export default function BookmarkButton({ articleId, size = "md" }: BookmarkButtonProps) {
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function syncStatus() {
      const localSaved = getBookmarks().includes(articleId);
      setSaved(localSaved);

      if (!hasAuthToken()) {
        return;
      }

      try {
        const status = await api.getBookmarkStatus(articleId);
        if (!cancelled) {
          setSaved(Boolean(status.bookmarked));
          const current = getBookmarks();
          if (status.bookmarked && !current.includes(articleId)) {
            setBookmarks([...current, articleId]);
          }
          if (!status.bookmarked && current.includes(articleId)) {
            setBookmarks(current.filter((id) => id !== articleId));
          }
        }
      } catch {
        // Keep local fallback state.
      }
    }

    syncStatus();
    return () => {
      cancelled = true;
    };
  }, [articleId]);

  async function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;

    setBusy(true);

    const current = getBookmarks();
    let next: string[];

    if (current.includes(articleId)) {
      next = current.filter((id) => id !== articleId);
      setSaved(false);
    } else {
      next = [...current, articleId];
      setSaved(true);
    }
    setBookmarks(next);

    if (hasAuthToken()) {
      try {
        if (next.includes(articleId)) {
          await api.createBookmark(articleId);
        } else {
          await api.deleteBookmark(articleId);
        }
      } catch {
        // Revert optimistic state on server failure.
        setBookmarks(current);
        setSaved(current.includes(articleId));
      }
    }

    setBusy(false);
  }

  const iconSize = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  return (
    <button
      onClick={toggle}
      className={clsx(
        "inline-flex items-center gap-1 transition-colors",
        size === "sm" ? "text-xs" : "text-sm",
        saved
          ? "text-amber-500 hover:text-amber-600"
          : "text-gray-400 hover:text-gray-600"
      )}
      disabled={busy}
      title={saved ? "Remove bookmark" : "Bookmark article"}
    >
      <Bookmark
        className={clsx(iconSize, saved && "fill-current")}
      />
      {size === "md" && <span>{saved ? "Saved" : "Save"}</span>}
    </button>
  );
}
