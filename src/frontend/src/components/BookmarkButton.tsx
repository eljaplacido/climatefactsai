"use client";

import { Bookmark } from "lucide-react";
import clsx from "clsx";
import { useSave } from "@/lib/useSave";

interface BookmarkButtonProps {
  articleId: string;
  size?: "sm" | "md";
}

/**
 * Article-save button. Slice 3 (2026-05-25) migrated this from the legacy
 * /api/user/bookmarks/{id} endpoint to the polymorphic /api/user/saved
 * surface via the generic useSave hook. Other surfaces (companies, search,
 * deep-search) use useSave directly with their own item_type.
 */
export default function BookmarkButton({ articleId, size = "md" }: BookmarkButtonProps) {
  const { saved, busy, error, toggle } = useSave({
    type: "article",
    id: articleId,
  });

  function handleClick(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    toggle();
  }

  const iconSize = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  return (
    <span className="inline-flex flex-col gap-0.5">
      <button
        onClick={handleClick}
        className={clsx(
          "inline-flex items-center gap-1 transition-colors",
          size === "sm" ? "text-xs" : "text-sm",
          saved
            ? "text-amber-500 hover:text-amber-600"
            : "text-gray-400 hover:text-gray-600",
          busy && "opacity-60 cursor-wait"
        )}
        disabled={busy}
        title={saved ? "Remove from saved" : "Save article"}
        aria-pressed={saved}
      >
        <Bookmark className={clsx(iconSize, saved && "fill-current")} />
        {size === "md" && <span>{saved ? "Saved" : "Save"}</span>}
      </button>
      {error && (
        <span className="text-[11px] text-amber-600 dark:text-amber-400" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
