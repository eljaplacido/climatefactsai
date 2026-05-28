"use client";

/**
 * AskAboutButton — small "?" affordance that fires a page-context-prefilled
 * prompt into the AgenticAssistant chat (chat-as-heart step 2).
 *
 * Pattern from CLAUDE.md: chat is the central place for "I don't get
 * this" moments. Direct manipulation (filters, buttons) stays as-is;
 * this component is sprinkled next to confusing UI elements (credibility
 * badges, source tier chips, KG drill-down, projections charts) so the
 * user can drill in without leaving the page.
 *
 * Wires into AgenticAssistant.tsx via the existing
 * `climatenews:assistant-prefill` CustomEvent (already used by other
 * page-level surfaces). The assistant opens, prefills the prompt, and
 * the user sends with one keystroke.
 */

import { HelpCircle } from "lucide-react";

interface Props {
  /** The prompt to drop into the chat input — should be a complete
   *  question that the assistant can answer from the surrounding page
   *  context (which it auto-injects via view-context). */
  prompt: string;
  /** Optional aria-label override. Defaults to the prompt itself. */
  ariaLabel?: string;
  /** Style variant. "inline" = small ? next to a label; "chip" = a
   *  full clickable chip with the question text visible. */
  variant?: "inline" | "chip";
  /** Optional extra className for layout integration. */
  className?: string;
}

export default function AskAboutButton({
  prompt,
  ariaLabel,
  variant = "inline",
  className = "",
}: Props) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (typeof window === "undefined") return;
    window.dispatchEvent(
      new CustomEvent("climatenews:assistant-prefill", {
        detail: { prompt },
      }),
    );
  };

  if (variant === "chip") {
    return (
      <button
        type="button"
        onClick={handleClick}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full bg-clilens-teal-50 hover:bg-clilens-teal-100 text-clilens-teal-700 border border-clilens-teal-200 transition-colors ${className}`}
        aria-label={ariaLabel ?? prompt}
        title={`Ask the assistant: ${prompt}`}
        data-testid="ask-about-chip"
      >
        <HelpCircle className="h-3.5 w-3.5" />
        <span>{prompt}</span>
      </button>
    );
  }

  // inline variant — tiny ? icon, fits next to any heading or label
  return (
    <button
      type="button"
      onClick={handleClick}
      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-gray-400 hover:text-clilens-primary hover:bg-clilens-teal-50 transition-colors align-middle ${className}`}
      aria-label={ariaLabel ?? `Ask the assistant: ${prompt}`}
      title={`Ask the assistant: ${prompt}`}
      data-testid="ask-about-inline"
    >
      <HelpCircle className="h-3.5 w-3.5" />
    </button>
  );
}
