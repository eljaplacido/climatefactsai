"use client";

import { Bookmark, Loader2 } from "lucide-react";
import clsx from "clsx";
import { useSave, type UseSaveArgs } from "@/lib/useSave";

interface SaveButtonProps extends UseSaveArgs {
  /** Display variant — chip is compact (icon+label), full is the longer button. */
  variant?: "chip" | "full";
  /** Override the default Save/Saved labels. */
  labelSaved?: string;
  labelUnsaved?: string;
  className?: string;
}

/**
 * Polymorphic save button for any of the 8 saved_items types. Wraps the
 * useSave hook — see lib/useSave.ts for state + error semantics.
 *
 * Examples:
 *   <SaveButton type="company" id={company.company_id} label={company.name} />
 *   <SaveButton type="country" ref="DE" label="Germany" />
 *   <SaveButton type="search" ref={searchUrl} label={query} />
 *   <SaveButton type="deep_search" ref={JSON.stringify(payload)} label={q} />
 */
export default function SaveButton({
  variant = "chip",
  labelSaved = "Saved",
  labelUnsaved = "Save",
  className,
  ...saveArgs
}: SaveButtonProps) {
  const { saved, busy, error, toggle } = useSave(saveArgs);

  function handleClick(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    toggle();
  }

  const base =
    variant === "chip"
      ? "inline-flex items-center gap-1 px-2 py-1 text-xs border rounded transition-colors"
      : "inline-flex items-center gap-2 px-3 py-1.5 text-sm border rounded-md transition-colors";

  const stateClasses = saved
    ? "border-amber-300 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 hover:border-amber-400"
    : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-clilens-primary hover:text-clilens-primary";

  return (
    <span className="inline-flex flex-col gap-0.5">
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className={clsx(base, stateClasses, busy && "opacity-60 cursor-wait", className)}
        aria-pressed={saved}
        title={saved ? labelSaved : labelUnsaved}
      >
        {busy ? (
          <Loader2 className={variant === "chip" ? "h-3 w-3 animate-spin" : "h-4 w-4 animate-spin"} />
        ) : (
          <Bookmark
            className={clsx(
              variant === "chip" ? "h-3 w-3" : "h-4 w-4",
              saved && "fill-current"
            )}
          />
        )}
        <span>{saved ? labelSaved : labelUnsaved}</span>
      </button>
      {error && (
        <span className="text-[11px] text-amber-600 dark:text-amber-400" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
