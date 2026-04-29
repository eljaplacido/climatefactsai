"use client";

import { Sparkles } from "lucide-react";

interface Props {
  suggestions: string[];
  /** Called when the user clicks a chip; parent should restart the search using the chip text */
  onPick: (suggestion: string) => void;
  /** Optional headline override */
  headline?: string;
}

export default function ClarificationChips({ suggestions, onPick, headline }: Props) {
  if (!suggestions || suggestions.length === 0) return null;
  return (
    <div className="bg-amber-950/15 border border-amber-900/40 rounded-lg p-3.5 space-y-2">
      <p className="text-xs uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
        <Sparkles className="w-3.5 h-3.5" />
        {headline ?? "Try a more specific query"}
      </p>
      <p className="text-xs text-amber-100/70 leading-relaxed">
        Your search returned no results. Pick one of the suggested refinements below to try again.
      </p>
      <div className="flex flex-wrap gap-1.5 pt-1">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="px-2.5 py-1.5 rounded-full bg-amber-900/30 hover:bg-amber-800/50 text-amber-100 text-xs border border-amber-800/60 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
