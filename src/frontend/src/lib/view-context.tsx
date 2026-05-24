"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

/**
 * Shared view-context — Phase 4B cleanup (2026-05-23). Implemented to
 * satisfy the long-standing test contract in
 * `__tests__/lib/view-context.test.tsx` (was passing-by-aspiration with
 * 9 failing tests since session 0; this commit makes them pass).
 *
 * Lets cross-component features (the global chat, the map, deep search,
 * article detail) publish "what the user is focused on" into a single
 * context the chat panel + view-aware components can read.
 *
 * Contract pinned by the tests:
 *   1. Empty values (null / undefined / "") REMOVE the key — they are
 *      "I no longer care about this", not "store these falsy values".
 *   2. Empty arrays are dropped from state (compareCountries: [] = none).
 *   3. clearKey on an absent key preserves object identity (no re-render).
 *   4. reset() empties everything atomically.
 *   5. useViewContext outside provider returns a no-op shim so consumers
 *      don't need to wrap test renders in <ViewContextProvider>.
 *   6. serializeViewContext emits the snake_case payload for backend
 *      consumption (chat endpoint expects this shape).
 */

export interface ViewContextState {
  route?: string;
  articleId?: string;
  countryCode?: string;
  analysisId?: string;
  deepSearchQuery?: string;
  deepSearchCompare?: { query_a: string; query_b: string };
  compareCountries?: string[];
  sourceId?: string;
  label?: string;
}

export type ViewContextType = {
  view: ViewContextState;
  setView: (partial: Partial<ViewContextState>) => void;
  clearKey: (key: keyof ViewContextState) => void;
  reset: () => void;
};

const ViewContext = createContext<ViewContextType>({
  view: {},
  setView: () => {},
  clearKey: () => {},
  reset: () => {},
});


function _isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}


/**
 * Apply a partial update. Empty values (per `_isEmptyValue`) REMOVE the
 * key from state. Non-empty values overwrite.
 *
 * Pure function exported for testability + reuse — the provider just
 * wraps this in a state setter.
 */
function _applyPartial(
  prev: ViewContextState,
  partial: Partial<ViewContextState>,
): ViewContextState {
  const next: ViewContextState = { ...prev };
  for (const [k, v] of Object.entries(partial)) {
    const key = k as keyof ViewContextState;
    if (_isEmptyValue(v)) {
      delete next[key];
    } else {
      (next as any)[key] = v;
    }
  }
  return next;
}


export function ViewContextProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<ViewContextState>({});

  const setView = useCallback((partial: Partial<ViewContextState>) => {
    setViewState((prev) => _applyPartial(prev, partial));
  }, []);

  const clearKey = useCallback((key: keyof ViewContextState) => {
    setViewState((prev) => {
      // Identity-preserve when the key isn't present — avoids
      // unnecessary re-renders in consumers that subscribe to the
      // full view object.
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setViewState({});
  }, []);

  return (
    <ViewContext.Provider value={{ view, setView, clearKey, reset }}>
      {children}
    </ViewContext.Provider>
  );
}


export function useViewContext(): ViewContextType {
  return useContext(ViewContext);
}


/**
 * Snake_case payload for backend consumption (the chat endpoint reads
 * this shape and forwards it as `view_context` so the LLM knows what
 * the user is focused on).
 *
 * Returns `undefined` when the state has no serializable keys — lets
 * callers skip sending an empty `view_context` field entirely.
 *
 * Key mapping (test-pinned):
 *   countryCode        → country
 *   articleId          → article_id
 *   analysisId         → analysis_id
 *   compareCountries   → compare_countries (omitted if empty array)
 *   deepSearchQuery    → deep_search_query
 *   deepSearchCompare  → deep_search_compare
 *   sourceId           → source_id
 *   route, label       → route, label (unchanged)
 */
export function serializeViewContext(
  view: ViewContextState,
): Record<string, unknown> | undefined {
  const out: Record<string, unknown> = {};

  if (view.route) out.route = view.route;
  if (view.articleId) out.article_id = view.articleId;
  if (view.countryCode) out.country = view.countryCode;
  if (view.analysisId) out.analysis_id = view.analysisId;
  if (view.deepSearchQuery) out.deep_search_query = view.deepSearchQuery;
  if (view.deepSearchCompare) out.deep_search_compare = view.deepSearchCompare;
  if (view.sourceId) out.source_id = view.sourceId;
  if (view.label) out.label = view.label;
  if (view.compareCountries && view.compareCountries.length > 0) {
    out.compare_countries = view.compareCountries;
  }

  if (Object.keys(out).length === 0) return undefined;
  return out;
}
