"use client";

// Stage 6 / M7 — SDG chip strip on article / company / research pages.
//
// Calls POST /api/sdg/tag with the artifact's text (title + brief +
// excerpt typically), renders the top SDGs as colored chips. Each
// chip links to /sdg/[goal_id] for cross-artifact browse.

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface SdgTag {
  goal_id: number;
  title: string;
  color: string;
  icon: string;
  matched_count: number;
  confidence: number;
}

interface Props {
  text: string;
  maxChips?: number;
  minMatchCount?: number;
}

export default function SDGChips({ text, maxChips = 5, minMatchCount = 1 }: Props) {
  const [tags, setTags] = useState<SdgTag[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!text || text.length < 10) {
      setLoaded(true);
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/api/sdg/tag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, min_match_count: minMatchCount }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        setTags((d.sdgs || []).slice(0, maxChips));
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [text, maxChips, minMatchCount]);

  if (!loaded || tags.length === 0) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-800">
        Related UN Sustainable Development Goals
      </h3>
      <p className="text-xs text-gray-500 mt-0.5 mb-2">
        This coverage maps to {tags.length === 1 ? "this global goal" : "these global goals"}
        {" "}— tap one to browse other articles, research and companies linked to it.
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        {tags.map((t) => (
          <Link
            key={t.goal_id}
            href={`/sdg/${t.goal_id}`}
            title={`SDG ${t.goal_id}: ${t.title} — ${t.matched_count} keyword match${t.matched_count === 1 ? "" : "es"}. Tap to browse related coverage.`}
            className="inline-flex items-center gap-1.5 pl-1.5 pr-2 py-1 rounded-md text-[11px] font-medium text-white hover:opacity-90 transition-opacity"
            style={{ backgroundColor: t.color }}
          >
            <span aria-hidden>{t.icon}</span>
            <span className="font-bold tabular-nums">{t.goal_id}</span>
            <span className="font-normal">{t.title}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
