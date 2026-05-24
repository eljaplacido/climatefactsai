"use client";

import { useState, type ReactNode } from "react";
import { BarChart3, Map as MapIcon, Table2 } from "lucide-react";

/**
 * MultiViewTabs — Phase 2G (2026-05-23) MH2 from the competitive UX audit.
 *
 * OWID Grapher pattern: every data panel offers the SAME dataset in
 * three different forms — chart (default), map, and table — via a
 * lightweight tab strip. The reader picks the form they think best
 * (chart for trends, map for geography, table for precise readings or
 * download).
 *
 * Three properties hold by contract:
 *   1. The chart / map / table views ALL render the SAME underlying
 *      dataset. No view-specific aggregation.
 *   2. State is local — switching tabs doesn't refetch.
 *   3. The renderer can hide views that don't apply (e.g. omit `map`
 *      when there's no geographic dimension).
 *
 * The component is intentionally NOT URL-persistent at this level —
 * tab state belongs to a single panel, not the page. Hoist to URL
 * state at the page level when needed (Country Passport tabs do this).
 */

export type MultiViewKey = "chart" | "map" | "table";

export interface MultiViewTabsProps {
  /** Chart renderer — almost always required. */
  chart: ReactNode;
  /** Map renderer — pass undefined when there's no geographic dimension. */
  map?: ReactNode;
  /** Table renderer — usually a tabular form of the same data, with download option. */
  table?: ReactNode;
  /** Which tab opens by default. Defaults to "chart". */
  defaultView?: MultiViewKey;
  /** Optional className for the outer wrapper. */
  className?: string;
  /** Accessible label for the tablist. Defaults to "Data view". */
  ariaLabel?: string;
}

const TAB_META: Record<MultiViewKey, { label: string; icon: any }> = {
  chart: { label: "Chart", icon: BarChart3 },
  map: { label: "Map", icon: MapIcon },
  table: { label: "Table", icon: Table2 },
};

export default function MultiViewTabs({
  chart,
  map,
  table,
  defaultView = "chart",
  className = "",
  ariaLabel = "Data view",
}: MultiViewTabsProps) {
  // Build the list of views the caller actually provided.
  const availableViews: MultiViewKey[] = [
    "chart",
    ...(map !== undefined ? (["map"] as MultiViewKey[]) : []),
    ...(table !== undefined ? (["table"] as MultiViewKey[]) : []),
  ];

  // Default to the requested view IFF it's available; else fall back to chart.
  const initialView: MultiViewKey = availableViews.includes(defaultView)
    ? defaultView
    : "chart";
  const [view, setView] = useState<MultiViewKey>(initialView);

  const renderers: Record<MultiViewKey, ReactNode> = {
    chart,
    map: map ?? null,
    table: table ?? null,
  };

  return (
    <div className={className} data-testid="multi-view-tabs">
      <div
        role="tablist"
        aria-label={ariaLabel}
        className="flex items-center gap-0.5 mb-3 p-0.5 bg-gray-100 dark:bg-slate-800 rounded-md w-fit"
      >
        {availableViews.map((v) => {
          const meta = TAB_META[v];
          const Icon = meta.icon;
          const active = v === view;
          return (
            <button
              key={v}
              role="tab"
              type="button"
              aria-selected={active}
              aria-controls={`multiview-panel-${v}`}
              id={`multiview-tab-${v}`}
              data-testid={`multiview-tab-${v}`}
              onClick={() => setView(v)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                active
                  ? "bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 shadow-sm"
                  : "text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-200"
              }`}
            >
              <Icon className="w-3 h-3" aria-hidden="true" />
              {meta.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`multiview-panel-${view}`}
        aria-labelledby={`multiview-tab-${view}`}
        data-testid={`multiview-panel-${view}`}
        tabIndex={0}
      >
        {renderers[view]}
      </div>
    </div>
  );
}
