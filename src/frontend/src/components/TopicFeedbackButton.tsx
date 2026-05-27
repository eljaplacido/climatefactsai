"use client";

// "Mark off-topic" button on the article-detail page.
//
// Stage 3 / M4 — feeds the evolving validation corpus. The golden
// pipeline daemon queries /api/feedback/topic/off-topic-ids at
// selection time and excludes flagged articles from future waves.
//
// MVP design: single anonymous click flags; an authenticated reporter
// id attaches automatically when present. Optional reason + category
// (politics / sports / finance / crime / etc.) for future per-category
// training of a topic classifier.

import { useState } from "react";
import { Flag, Check, X } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const OFF_TOPIC_CATEGORIES = [
  "politics",
  "sports",
  "finance",
  "crime",
  "celebrity",
  "general_news",
  "other",
];

interface Props {
  articleId: string;
}

export default function TopicFeedbackButton({ articleId }: Props) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<"on_topic" | "off_topic" | null>(null);
  const [reason, setReason] = useState("");
  const [category, setCategory] = useState("");

  const submit = async (verdict: "on_topic" | "off_topic") => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("clilens_token") : null;
      const res = await fetch(
        `${API_BASE}/api/feedback/topic/${encodeURIComponent(articleId)}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            verdict,
            reason: reason || null,
            off_topic_category: verdict === "off_topic" ? (category || null) : null,
          }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSubmitted(verdict);
      setOpen(false);
    } catch (e) {
      console.error("topic-feedback submit failed", e);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted === "off_topic") {
    return (
      <div className="inline-flex items-center gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 px-3 py-1.5 rounded-md">
        <Check className="h-3.5 w-3.5" />
        Flagged as off-topic — thanks. Daemon will exclude this from future waves.
      </div>
    );
  }
  if (submitted === "on_topic") {
    return (
      <div className="inline-flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-md">
        <Check className="h-3.5 w-3.5" />
        Confirmed on-topic — thanks.
      </div>
    );
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-xs text-gray-600 hover:text-rose-700 hover:bg-rose-50 px-2.5 py-1 rounded-md border border-gray-200 hover:border-rose-200 transition-colors"
      >
        <Flag className="h-3.5 w-3.5" />
        Mark off-topic
      </button>
    );
  }

  return (
    <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 my-3 max-w-2xl">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h4 className="text-sm font-semibold text-rose-900">
            Is this article actually about climate?
          </h4>
          <p className="text-xs text-rose-700 mt-0.5">
            Your verdict goes into the evolving validation corpus and excludes
            off-topic articles from future enrichment.
          </p>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-rose-700 hover:text-rose-900"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="space-y-2">
        <label className="block">
          <span className="text-xs text-rose-800 font-medium">
            Reason (optional)
          </span>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={500}
            placeholder="e.g. about housing prices, not climate"
            className="mt-1 w-full px-2 py-1.5 text-sm border border-rose-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-rose-400"
          />
        </label>
        <label className="block">
          <span className="text-xs text-rose-800 font-medium">
            Actually about:
          </span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mt-1 w-full px-2 py-1.5 text-sm border border-rose-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-rose-400"
          >
            <option value="">— pick a category —</option>
            {OFF_TOPIC_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-2 pt-2">
          <button
            onClick={() => submit("off_topic")}
            disabled={submitting}
            className="px-3 py-1.5 text-sm bg-rose-600 text-white rounded-md hover:bg-rose-700 disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Confirm off-topic"}
          </button>
          <button
            onClick={() => submit("on_topic")}
            disabled={submitting}
            className="px-3 py-1.5 text-sm text-rose-700 border border-rose-300 rounded-md hover:bg-rose-100 disabled:opacity-50"
          >
            Actually it IS climate
          </button>
        </div>
      </div>
    </div>
  );
}
