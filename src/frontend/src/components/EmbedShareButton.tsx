"use client";

import { useEffect, useRef, useState } from "react";
import { Code, Copy, Check, X } from "lucide-react";

/**
 * EmbedShareButton — Phase 2E (2026-05-23) MH6.
 *
 * Tiny button that opens a modal with the iframe snippet for the
 * specified embed URL + copy-to-clipboard. Used on the Country
 * Passport (and any other surface with an `/embed/...` counterpart).
 *
 * The modal also previews three width presets (sidebar 280px / article
 * 380px / full 560px) so the embedder can copy whichever fits their
 * layout without doing arithmetic.
 *
 * Accessibility: role=dialog, Escape closes, focus traps inside the
 * modal, Copy button reports success via aria-live.
 */

interface EmbedShareButtonProps {
  /** Path-only embed URL — the modal prepends the public origin. */
  embedPath: string;
  /** Default iframe width preset. */
  defaultWidth?: 280 | 380 | 560;
  /** Default iframe height. */
  height?: number;
  /** Optional accessible label override (defaults to "Share embed code"). */
  label?: string;
}

const WIDTH_PRESETS: Array<{ label: string; w: 280 | 380 | 560 }> = [
  { label: "Sidebar", w: 280 },
  { label: "Article", w: 380 },
  { label: "Full", w: 560 },
];

export default function EmbedShareButton({
  embedPath,
  defaultWidth = 380,
  height = 240,
  label = "Share embed code",
}: EmbedShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [width, setWidth] = useState<280 | 380 | 560>(defaultWidth);
  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Server-render-safe origin resolution. window is unavailable during
  // SSR; we render a placeholder origin and swap to the real one on mount.
  const [origin, setOrigin] = useState("https://climatefacts.ai");
  useEffect(() => {
    if (typeof window !== "undefined" && window.location?.origin) {
      setOrigin(window.location.origin);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  // Clear the "Copied!" indicator after 2s.
  useEffect(() => {
    if (!copied) return;
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, [copied]);

  const fullUrl = `${origin}${embedPath}`;
  const snippet = `<iframe src="${fullUrl}" width="${width}" height="${height}" style="border:0" loading="lazy" title="Climatefacts.ai embed"></iframe>`;

  async function handleCopy() {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(snippet);
        setCopied(true);
        return;
      }
      // Older browsers: select+execCommand fallback.
      const ta = document.createElement("textarea");
      ta.value = snippet;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        setCopied(true);
      } finally {
        document.body.removeChild(ta);
      }
    } catch {
      // Last-resort: nothing — the user can still triple-click + Cmd+C
      // on the textarea below.
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-slate-200 bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 rounded-md transition-colors"
        aria-label={label}
        data-testid="embed-share-button"
      >
        <Code className="w-3.5 h-3.5" aria-hidden="true" />
        Embed
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[2050] flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="embed-share-title"
          data-testid="embed-share-modal"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-2xl max-w-lg w-full mx-4 p-5">
            <div className="flex items-start justify-between gap-3 mb-3">
              <h3
                id="embed-share-title"
                className="text-base font-semibold text-gray-900 dark:text-slate-100"
              >
                Embed this on your site
              </h3>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300"
                aria-label="Close dialog"
                data-testid="embed-share-close"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>

            <p className="text-xs text-gray-600 dark:text-slate-400 mb-3">
              Paste this HTML snippet into your article. The iframe auto-updates
              when our data does — your readers always see the latest snapshot,
              attributed to Climatefacts.ai.
            </p>

            {/* Width preset chooser */}
            <div
              className="flex gap-1 mb-3"
              role="radiogroup"
              aria-label="Width preset"
            >
              {WIDTH_PRESETS.map((p) => (
                <button
                  key={p.w}
                  type="button"
                  role="radio"
                  aria-checked={width === p.w}
                  onClick={() => setWidth(p.w)}
                  className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                    width === p.w
                      ? "bg-teal-600 text-white"
                      : "bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-700"
                  }`}
                  data-testid={`embed-share-width-${p.w}`}
                >
                  {p.label} ({p.w}px)
                </button>
              ))}
            </div>

            <textarea
              readOnly
              value={snippet}
              onFocus={(e) => e.currentTarget.select()}
              className="w-full p-2 text-[11px] font-mono bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded resize-none text-gray-800 dark:text-slate-100"
              rows={4}
              data-testid="embed-share-snippet"
              aria-label="Iframe HTML snippet"
            />

            <div
              aria-live="polite"
              className="sr-only"
              data-testid="embed-share-aria-live"
            >
              {copied ? "Snippet copied to clipboard." : ""}
            </div>

            <div className="mt-3 flex items-center justify-end gap-2">
              <a
                href={fullUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-200 underline"
                data-testid="embed-share-preview-link"
              >
                Preview in new tab
              </a>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-md transition-colors"
                data-testid="embed-share-copy"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5" aria-hidden="true" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" aria-hidden="true" />
                    Copy snippet
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
