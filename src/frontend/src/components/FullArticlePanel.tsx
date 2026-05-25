"use client";

import { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp } from "lucide-react";

// Polish wave 1 / Audit item 2 (2026-05-25) — the Executive Brief +
// Enriched In-Depth panels are intentional 200-400-word summaries.
// The audit noted the full source content lives in
// articles.extracted_text but no panel rendered it. This component
// adds a collapsible "Full source article" panel — opt-in expansion
// keeps the article page concise by default while letting users
// reach the raw 1500-3000-word body when they want to.

interface FullArticlePanelProps {
  extractedText: string;
  /** Optional source URL to link the user to the canonical original. */
  sourceUrl?: string | null;
}

const PREVIEW_LIMIT = 600;

export default function FullArticlePanel({
  extractedText,
  sourceUrl,
}: FullArticlePanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (!extractedText || extractedText.trim().length < 200) {
    // Nothing meaningful to expand to — RSS-only article with just an
    // excerpt. Skip the panel entirely rather than showing an empty UI.
    return null;
  }

  const wordCount = extractedText.trim().split(/\s+/).length;
  const charCount = extractedText.length;
  const preview = extractedText.slice(0, PREVIEW_LIMIT);
  const truncated = extractedText.length > PREVIEW_LIMIT;

  return (
    <section
      className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden"
      data-testid="full-article-panel"
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors text-left"
        aria-expanded={expanded}
        aria-controls="full-article-body"
      >
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-9 h-9 bg-gray-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
            <BookOpen className="h-4 w-4 text-gray-600 dark:text-slate-300" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100">
              Full source article
            </h3>
            <p className="text-xs text-gray-500 dark:text-slate-400">
              {wordCount.toLocaleString()} words · {charCount.toLocaleString()} characters
              {sourceUrl ? " · original link in footer" : ""}
            </p>
          </div>
        </div>
        <span className="flex-shrink-0 text-xs text-gray-500 dark:text-slate-400 flex items-center gap-1">
          {expanded ? "Collapse" : "Expand"}
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
      </button>

      {expanded && (
        <div
          id="full-article-body"
          className="px-4 pb-4 border-t border-gray-100 dark:border-slate-700"
        >
          <div className="pt-3 prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
            {extractedText}
          </div>
          {sourceUrl && (
            <p className="mt-4 pt-3 text-xs text-gray-500 dark:text-slate-400 border-t border-gray-100 dark:border-slate-700">
              Read on original site:{" "}
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-clilens-primary hover:underline break-all"
              >
                {sourceUrl}
              </a>
            </p>
          )}
        </div>
      )}

      {!expanded && truncated && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-slate-700">
          <p className="pt-3 text-sm text-gray-600 dark:text-slate-400 line-clamp-3 italic">
            {preview}…
          </p>
        </div>
      )}
    </section>
  );
}
