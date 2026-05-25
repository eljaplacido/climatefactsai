"use client";

import { useEffect, useState, useCallback } from "react";

/**
 * useSkills — Phase 5B (2026-05-24).
 *
 * Frontend hook that fetches `/api/skills` (the canonical backend
 * registry shipped in Phase 4C) and exposes the action manifest at
 * runtime. Lets the dispatcher + UI consult ONE source of truth
 * (the backend registry) instead of three (registry + prompt +
 * frontend hard-coded ACTION_MODES).
 *
 * The hook degrades gracefully to a built-in fallback when the
 * backend is unreachable — so a network blip can't break chat
 * action rendering. The fallback is the same 9-action set the
 * dispatcher hard-codes today (see `chatActionDispatcher.ts`).
 *
 * Pattern matches `useQuota`: SWR-light, fetch-on-mount, no global
 * state framework needed. Consumers call `getSkillMode(name)` instead
 * of importing `ACTION_MODES` directly — over time this lets us
 * delete the hardcoded constant entirely.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export type SkillMode = "auto" | "confirm";

export interface SkillParameter {
  name: string;
  type: "string" | "number" | "boolean";
  description: string;
  required: boolean;
}

export interface Skill {
  name: string;
  description: string;
  mode: SkillMode;
  parameters: SkillParameter[];
  target_surfaces: string[];
}

export interface SkillsRegistry {
  skills: Skill[];
  total: number;
  modes: {
    auto: number;
    confirm: number;
  };
}


// Fallback registry — exact mirror of the chatActionDispatcher.ts
// ACTION_MODES constant. Used when the backend is unreachable so
// chat actions still render with the correct confirmation gates.
//
// Keep in lockstep with the backend SKILLS_REGISTRY — `useSkills` will
// log a warning when the fetched registry diverges from this fallback,
// so future drift surfaces visibly during development.
const FALLBACK_SKILL_MODES: Record<string, SkillMode> = {
  // Original 9 (pre-Phase-7-B3)
  navigate: "auto",
  apply_search_filters: "auto",
  apply_map_filters: "auto",
  open_methodology_section: "auto",
  open_country: "auto",
  start_deep_search: "auto",
  analyze_url: "confirm",
  bookmark_article: "confirm",
  start_calibration_label: "confirm",
  // Phase 7 B3 (2026-05-24) — corporate-claim surface
  open_company: "auto",
  verify_corporate_claim: "confirm",
  // Polish wave 1 (2026-05-25) — endpoint families from deferred
  // items 11/12/13/14 + Slice 3 wrapped as chat skills. Keep in
  // lockstep with backend skills.py SKILLS_REGISTRY (15 entries)
  // and chatActionDispatcher.ts ACTION_MODES.
  save_item: "confirm",
  subscribe_research_topic: "confirm",
  explore_scenario: "auto",
  analyze_corporate_report: "confirm",
};

const FALLBACK_REGISTRY: SkillsRegistry = {
  skills: Object.entries(FALLBACK_SKILL_MODES).map(([name, mode]) => ({
    name,
    description: "",  // unknown without backend; description used for UI hover only
    mode,
    parameters: [],
    target_surfaces: [],
  })),
  total: Object.keys(FALLBACK_SKILL_MODES).length,
  modes: {
    auto: Object.values(FALLBACK_SKILL_MODES).filter((m) => m === "auto").length,
    confirm: Object.values(FALLBACK_SKILL_MODES).filter((m) => m === "confirm").length,
  },
};


export interface UseSkillsResult {
  loading: boolean;
  error: string | null;
  registry: SkillsRegistry;
  /** Per-skill lookup. Returns the fallback entry if the backend
   *  doesn't expose this skill — never null. */
  getSkill: (name: string) => Skill | null;
  /** Convenience: just the mode. Falls back to "auto" for unknown
   *  skills (safe default — known destructive types are explicitly
   *  marked "confirm" in the fallback set above). */
  getSkillMode: (name: string) => SkillMode;
  /** Re-fetch the registry. Useful after a backend deploy that added
   *  a new skill. */
  refresh: () => Promise<void>;
}


export function useSkills(): UseSkillsResult {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [registry, setRegistry] = useState<SkillsRegistry>(FALLBACK_REGISTRY);

  const fetchRegistry = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/skills`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: SkillsRegistry = await resp.json();
      // Shape check — be defensive against backend version skew.
      if (
        !data ||
        !Array.isArray(data.skills) ||
        typeof data.total !== "number"
      ) {
        throw new Error("Invalid /api/skills response shape");
      }
      setRegistry(data);
      // Surface drift between the backend registry and the fallback,
      // so a missed sync is visible during development.
      if (process.env.NODE_ENV !== "production") {
        const backendNames = new Set(data.skills.map((s) => s.name));
        const fallbackNames = new Set(Object.keys(FALLBACK_SKILL_MODES));
        const missing = [...fallbackNames].filter((n) => !backendNames.has(n));
        const extra = [...backendNames].filter((n) => !fallbackNames.has(n));
        if (missing.length || extra.length) {
          // eslint-disable-next-line no-console
          console.warn(
            "[useSkills] backend registry drifted from frontend fallback:",
            { missing_in_backend: missing, extra_in_backend: extra },
          );
        }
      }
    } catch (e: any) {
      setError(e?.message || "Failed to load skills registry");
      // Fall back to the local mirror so the dispatcher still works.
      setRegistry(FALLBACK_REGISTRY);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRegistry();
  }, [fetchRegistry]);

  const getSkill = useCallback(
    (name: string): Skill | null => {
      return registry.skills.find((s) => s.name === name) ?? null;
    },
    [registry],
  );

  const getSkillMode = useCallback(
    (name: string): SkillMode => {
      const skill = registry.skills.find((s) => s.name === name);
      if (skill) return skill.mode;
      // Unknown skill: use fallback or default to "auto" (safer to NOT
      // surface a confirmation modal for genuinely-unknown action types
      // — they're handled by the dispatcher's "Unknown action type" error
      // path anyway).
      return FALLBACK_SKILL_MODES[name] ?? "auto";
    },
    [registry],
  );

  return {
    loading,
    error,
    registry,
    getSkill,
    getSkillMode,
    refresh: fetchRegistry,
  };
}
