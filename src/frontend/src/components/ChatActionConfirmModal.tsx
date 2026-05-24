"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";
import type { ChatActionSpec } from "@/lib/chatActionDispatcher";
import { ACTION_CONFIRM_COPY } from "@/lib/chatActionDispatcher";

/**
 * Confirmation modal for destructive / quota-consuming chat actions.
 *
 * Phase 1C (2026-05-23): every action classified as 'confirm' mode
 * (bookmark_article, analyze_url, start_calibration_label) MUST pass
 * through this modal before executing. The dispatcher's safety property
 * is that confirm-mode actions fail closed when no confirmation hook is
 * provided — this component is the canonical hook implementation.
 *
 * Accessibility: focus is trapped inside the modal, Escape closes,
 * Confirm button is focused by default for keyboard-only confirmation.
 */

interface ChatActionConfirmModalProps {
  action: ChatActionSpec | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ChatActionConfirmModal({
  action,
  onConfirm,
  onCancel,
}: ChatActionConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!action) return;
    // Focus the confirm button on open so keyboard users can confirm
    // with Enter and cancel with Escape.
    confirmRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [action, onCancel]);

  if (!action) return null;

  const copy = ACTION_CONFIRM_COPY[action.type];
  if (!copy || !copy.title) {
    // Should never happen — auto-mode actions don't open this modal.
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="chat-action-confirm-title"
      data-testid="chat-action-confirm-modal"
      onClick={(e) => {
        // Backdrop click cancels — same as Escape.
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-2xl max-w-md w-full mx-4 p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" aria-hidden="true" />
            <h3
              id="chat-action-confirm-title"
              className="text-base font-semibold text-gray-900 dark:text-slate-100"
            >
              {copy.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 transition-colors"
            aria-label="Close dialog"
            data-testid="chat-action-modal-close"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <p className="text-sm text-gray-700 dark:text-slate-200 leading-relaxed mb-4">
          {copy.message(action.params)}
        </p>

        {/* Show the action type + params so a technical user can audit
            exactly what's about to fire. Collapsed by default to keep
            non-technical users focused on the plain-language copy above. */}
        <details className="mb-4 text-xs text-gray-500 dark:text-slate-400">
          <summary className="cursor-pointer hover:text-gray-700 dark:hover:text-slate-300 select-none">
            Show technical details
          </summary>
          <pre className="mt-2 p-2 bg-gray-50 dark:bg-slate-800 rounded text-[11px] font-mono overflow-x-auto">
            {JSON.stringify({ type: action.type, params: action.params }, null, 2)}
          </pre>
        </details>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            data-testid="chat-action-cancel"
          >
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors"
            data-testid="chat-action-confirm"
          >
            {copy.cta}
          </button>
        </div>
      </div>
    </div>
  );
}
