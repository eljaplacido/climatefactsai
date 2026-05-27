"use client";

/**
 * FirstTimerTour — 4-step walkthrough overlay (2026-05-27).
 *
 * Surfaces on first visit (no localStorage flag), dismissible at any
 * step. Re-openable from the floating help button at the bottom-right.
 *
 * Design choice: centered modal cards rather than spotlight-on-DOM.
 * Spotlight tours rely on querySelector + position math that breaks
 * the moment a component re-renders or moves; a self-contained modal
 * survives layout changes and works on mobile.
 *
 * Each step has a Try-it CTA that deep-links to the feature, so the
 * tour doubles as a "where do I start" guide.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Map as MapIcon,
  Search,
  Building2,
  HelpCircle,
  X,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";

const STORAGE_KEY = "climatefacts_tour_completed_v1";

interface Step {
  title: string;
  body: string;
  icon: React.ComponentType<{ className?: string }>;
  cta: { label: string; href: string };
}

const STEPS: Step[] = [
  {
    title: "Welcome to Climatefacts.ai",
    body:
      "We surface fact-checked climate news from 168+ trusted feeds, with every claim traced to its source. The fastest way in: ask the chat assistant anything about climate.",
    icon: MessageSquare,
    cta: { label: "Open the chat", href: "/#chat" },
  },
  {
    title: "Explore the world map",
    body:
      "See climate intelligence by country: temperature trends, emissions, latest articles, projections. Click any country for a passport view.",
    icon: MapIcon,
    cta: { label: "Open the map", href: "/map" },
  },
  {
    title: "Search & analyze a URL",
    body:
      "Paste any climate article URL — we extract claims, grade source credibility on three axes (methodology, citation, relevance), and surface a verdict per claim.",
    icon: Search,
    cta: { label: "Analyze a URL", href: "/analyze" },
  },
  {
    title: "Corporate Climate Tracker",
    body:
      "Audit-ready disclosures from CDP, SBTi, Net Zero Tracker. Companies are scored on disclosure depth, and we grade claims against the 5 major reporting standards (CSRD / SBTi / TCFD / IFRS S2 / GRI).",
    icon: Building2,
    cta: { label: "Open the tracker", href: "/companies" },
  },
];

export default function FirstTimerTour() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [hydrated, setHydrated] = useState(false);

  // Defer the localStorage check to after hydration so SSR + first paint
  // don't flash the tour to returning users.
  useEffect(() => {
    setHydrated(true);
    try {
      const done = localStorage.getItem(STORAGE_KEY);
      if (done !== "true") setOpen(true);
    } catch {
      // localStorage may be unavailable (private mode); just show once.
      setOpen(true);
    }
  }, []);

  const close = (markDone: boolean) => {
    setOpen(false);
    if (markDone) {
      try {
        localStorage.setItem(STORAGE_KEY, "true");
      } catch {
        /* private-mode fallback: tour will re-appear next visit */
      }
    }
  };

  if (!hydrated) return null;

  return (
    <>
      {/* Floating help button — always available to re-open the tour */}
      <button
        type="button"
        onClick={() => {
          setStep(0);
          setOpen(true);
        }}
        className="fixed bottom-4 left-4 z-40 inline-flex items-center gap-1.5 rounded-full bg-white text-gray-700 shadow-lg border border-gray-200 px-3 py-2 text-xs font-medium hover:bg-gray-50 hover:shadow-xl transition-all"
        aria-label="Open quick tour"
        title="Quick tour for first-time visitors"
        data-testid="first-timer-tour-button"
      >
        <HelpCircle className="w-4 h-4 text-clilens-primary" />
        <span className="hidden sm:inline">Quick tour</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="tour-step-title"
          data-testid="first-timer-tour-modal"
        >
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl">
            <button
              type="button"
              onClick={() => close(true)}
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-700"
              aria-label="Close tour"
            >
              <X className="w-5 h-5" />
            </button>

            <Step
              step={STEPS[step]}
              index={step}
              total={STEPS.length}
              onPrev={step > 0 ? () => setStep(step - 1) : undefined}
              onNext={
                step < STEPS.length - 1
                  ? () => setStep(step + 1)
                  : undefined
              }
              onFinish={() => close(true)}
              onSkip={() => close(true)}
            />
          </div>
        </div>
      )}
    </>
  );
}

function Step({
  step,
  index,
  total,
  onPrev,
  onNext,
  onFinish,
  onSkip,
}: {
  step: Step;
  index: number;
  total: number;
  onPrev?: () => void;
  onNext?: () => void;
  onFinish: () => void;
  onSkip: () => void;
}) {
  const Icon = step.icon;
  const isLast = index === total - 1;
  return (
    <div className="p-6 sm:p-8 space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-clilens-teal-50 flex items-center justify-center">
          <Icon className="w-5 h-5 text-clilens-primary" />
        </div>
        <div>
          <p className="text-xs text-gray-400">
            Step {index + 1} of {total}
          </p>
          <h2 id="tour-step-title" className="text-lg font-semibold text-gray-900">
            {step.title}
          </h2>
        </div>
      </div>

      <p className="text-sm text-gray-600 leading-relaxed">{step.body}</p>

      <Link
        href={step.cta.href}
        onClick={onFinish}
        className="block w-full text-center px-4 py-2.5 bg-clilens-primary text-white text-sm font-medium rounded-lg hover:bg-clilens-teal-700 transition-colors"
      >
        {step.cta.label}
      </Link>

      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-1.5" aria-label="Tour progress">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === index
                  ? "w-6 bg-clilens-primary"
                  : "w-1.5 bg-gray-200"
              }`}
            />
          ))}
        </div>
        <div className="flex items-center gap-2">
          {onPrev && (
            <button
              type="button"
              onClick={onPrev}
              className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 px-2 py-1"
            >
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
          )}
          {onNext ? (
            <button
              type="button"
              onClick={onNext}
              className="inline-flex items-center gap-1 text-sm text-clilens-primary hover:text-clilens-teal-700 px-2 py-1 font-medium"
            >
              Next <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onFinish}
              className="text-sm text-clilens-primary hover:text-clilens-teal-700 px-2 py-1 font-medium"
            >
              Finish
            </button>
          )}
        </div>
      </div>

      {!isLast && (
        <button
          type="button"
          onClick={onSkip}
          className="block w-full text-xs text-gray-400 hover:text-gray-600 pt-1"
        >
          Skip tour
        </button>
      )}
    </div>
  );
}
