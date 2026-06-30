"use client";

// Map walkthrough overlay — Phase 9 (2026-05-25).
//
// Problem: production-review feedback said the world map felt "plain
// and not engaging" with no signal of what users could do with it.
// Solution: a 4-step onboarding overlay that introduces the four
// layers + compare mode + the chat affordance. Triggered on first
// visit (localStorage flag) or via the "Take the tour" button in
// the layer control. Dismissable; never blocks the underlying map.
//
// Design inspiration from worldmonitor.app's onboarding pass — short
// captions, single-action steps, persistent skip.

import { useEffect, useState } from "react";
import { X, ArrowRight, ArrowLeft, MapPin, Thermometer, AlertTriangle,
         Shield, GitCompare, MessageCircle, Leaf } from "lucide-react";

const STORAGE_KEY = "clilens_map_walkthrough_dismissed";

interface Step {
  title: string;
  body: string;
  icon: React.ReactNode;
  highlightSelector?: string;
}

const STEPS: Step[] = [
  {
    title: "Welcome to the world climate map",
    body:
      "190+ countries, four climate layers, live news + projection data. "
      + "Click any country to open its full climate passport.",
    icon: <MapPin className="w-6 h-6 text-teal-600" />,
    highlightSelector: undefined,
  },
  {
    title: "Layer 1 — Article density",
    body:
      "How much climate news a country generates. Useful for spotting "
      + "regions in heightened coverage (heatwaves, policy debates, COP cycles).",
    icon: <MapPin className="w-6 h-6 text-blue-600" />,
    highlightSelector: '[data-testid="map-layer-article_density"]',
  },
  {
    title: "Layer 2 — Temperature anomaly",
    body:
      "Live deviation from the same month last year — provisional, "
      + "year-over-year (not a 30-year baseline). Countries with no live "
      + "reading show as grey. Arctic countries still warm 2-3× faster than "
      + "the global average, visible immediately here.",
    icon: <Thermometer className="w-6 h-6 text-red-600" />,
    highlightSelector: '[data-testid="map-layer-temperature_anomaly"]',
  },
  {
    title: "Layer 3 — Climate risk score",
    body:
      "Projected warming by 2050 under IPCC AR6 SSP2-4.5 (middle path). "
      + "Higher = more physical climate risk — this is hazard, not media "
      + "coverage. Countries without an AR6 projection show as grey.",
    icon: <AlertTriangle className="w-6 h-6 text-amber-600" />,
    highlightSelector: '[data-testid="map-layer-climate_risk"]',
  },
  {
    title: "Layer 4 — Source diversity",
    body:
      "How many independent newsrooms cover a country. Low diversity = "
      + "fewer voices = higher single-source bias risk.",
    icon: <Shield className="w-6 h-6 text-emerald-600" />,
    highlightSelector: '[data-testid="map-layer-source_diversity"]',
  },
  {
    title: "Layer 5 — Biomes & climate zones",
    body:
      "WWF biome type (emoji marker at country centroid) + Köppen-Geiger "
      + "climate zone (colour fill). Lets you see at a glance which "
      + "countries share ecological + climatic context.",
    icon: <Leaf className="w-6 h-6 text-teal-600" />,
    highlightSelector: '[data-testid="map-layer-biomes"]',
  },
  {
    title: "Compare two countries",
    body:
      "Hit the Compare toggle in the top-right, pick a second country. "
      + "Side-by-side indicators + side-by-side scenarios.",
    icon: <GitCompare className="w-6 h-6 text-violet-600" />,
  },
  {
    title: "Ask the climate assistant",
    body:
      "The chat button in the bottom-right. Ask things like 'compare DE "
      + "and FR climate risk' or 'what would +2°C do to AU by 2050'. The "
      + "agent suggests follow-up actions that wire directly into the map.",
    icon: <MessageCircle className="w-6 h-6 text-teal-600" />,
  },
];

interface MapWalkthroughProps {
  /** Force-open via "Take the tour" button. */
  forceOpen?: boolean;
  onClose?: () => void;
}

export default function MapWalkthrough({ forceOpen, onClose }: MapWalkthroughProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setStep(0);
      return;
    }
    if (typeof window === "undefined") return;
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (!dismissed) {
      // Defer by 600ms so the map paints first.
      const t = window.setTimeout(() => setOpen(true), 600);
      return () => window.clearTimeout(t);
    }
  }, [forceOpen]);

  const close = () => {
    setOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* localStorage unavailable */
    }
    onClose?.();
  };

  if (!open) return null;
  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const isFirst = step === 0;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end md:items-center justify-center pointer-events-none"
      data-testid="map-walkthrough"
      role="dialog"
      aria-modal="false"
      aria-labelledby="map-walkthrough-title"
    >
      {/* Soft scrim, only at the bottom on mobile */}
      <div
        className="absolute inset-x-0 bottom-0 h-72 md:hidden bg-gradient-to-t from-black/40 to-transparent pointer-events-none"
        aria-hidden="true"
      />
      <div className="relative mx-4 mb-8 md:mb-0 max-w-md w-full bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-gray-200 dark:border-slate-700 p-5 pointer-events-auto">
        <button
          type="button"
          onClick={close}
          aria-label="Close walkthrough"
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-700 dark:hover:text-slate-200"
          data-testid="map-walkthrough-close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-3 mb-3">
          <div className="flex-shrink-0">{current.icon}</div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-slate-400 mb-0.5">
              Step {step + 1} of {STEPS.length}
            </div>
            <h2
              id="map-walkthrough-title"
              className="text-base font-semibold text-gray-900 dark:text-slate-50"
            >
              {current.title}
            </h2>
          </div>
        </div>

        <p className="text-sm text-gray-700 dark:text-slate-300 leading-relaxed mb-4">
          {current.body}
        </p>

        {/* Step dots */}
        <div className="flex items-center justify-center gap-1.5 mb-4">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={`block h-1.5 rounded-full transition-all ${
                i === step
                  ? "w-6 bg-teal-600"
                  : "w-1.5 bg-gray-300 dark:bg-slate-600"
              }`}
              aria-hidden="true"
            />
          ))}
        </div>

        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={close}
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {!isFirst && (
              <button
                type="button"
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-slate-200 bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 rounded inline-flex items-center gap-1"
                data-testid="map-walkthrough-prev"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
            )}
            <button
              type="button"
              onClick={() => (isLast ? close() : setStep((s) => s + 1))}
              className="px-3 py-1.5 text-xs font-medium text-white bg-teal-600 hover:bg-teal-500 rounded inline-flex items-center gap-1"
              data-testid={isLast ? "map-walkthrough-done" : "map-walkthrough-next"}
            >
              {isLast ? "Done" : "Next"}{" "}
              {!isLast && <ArrowRight className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


/**
 * Small helper button shown in the layer control: re-opens the walkthrough.
 */
export function MapWalkthroughTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-xs text-teal-700 dark:text-teal-300 hover:underline inline-flex items-center gap-1"
      data-testid="map-walkthrough-trigger"
    >
      <MessageCircle className="w-3.5 h-3.5" />
      Take the tour
    </button>
  );
}
