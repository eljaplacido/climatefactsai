"use client";

import { useState, useEffect } from "react";
import { Bookmark } from "lucide-react";
import clsx from "clsx";

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

export default function BookmarkButton({ articleId, size = "md" }: BookmarkButtonProps) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSaved(getBookmarks().includes(articleId));
  }, [articleId]);

  function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
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
      title={saved ? "Remove bookmark" : "Bookmark article"}
    >
      <Bookmark
        className={clsx(iconSize, saved && "fill-current")}
      />
      {size === "md" && <span>{saved ? "Saved" : "Save"}</span>}
    </button>
  );
}
