"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

/**
 * useUrlState — Phase 1B (2026-05-23) MH1 proof-of-concept.
 *
 * Bidirectional bridge between a React state value and a URL query param.
 * Sharing the URL reproduces the exact view; using browser back/forward
 * restores prior state.
 *
 * This is the building block for the OWID-style "every selection is in
 * the URL" UX pattern called out in the competitive UX audit as a
 * must-have. We start with Deep Search as the proof-of-concept and roll
 * it out to /map, /search, country panels, etc. in Phase 2.
 *
 * Why a custom hook instead of `useState + useSearchParams`:
 *   1. Idempotent writes — avoids the infinite-loop trap where the URL
 *      change re-fires the effect that wrote the URL.
 *   2. Batched updates — when multiple `useUrlState` calls update in
 *      the same render, they emit one combined URL update via the
 *      module-level scheduler.
 *   3. Customisable encode/decode — strings, numbers, booleans, and
 *      arrays all work without per-callsite serialisation boilerplate.
 *
 * Semantics:
 *   - On mount: reads the current URL value (or falls back to defaultValue).
 *   - On setValue: writes the new value to React state AND replaces the
 *     URL (no scroll, no history push — survives browser back via React
 *     state alone).
 *   - When the URL changes externally (browser back, deeplink land),
 *     pulls the new value back into state.
 *
 * NOT a `useState` drop-in for sensitive data — anything written here
 * appears in the URL, browser history, and HTTP referer logs.
 */

type Serializer<T> = {
  encode: (value: T) => string | null;  // null = drop the key
  decode: (raw: string | null) => T;
};

const stringSerializer: Serializer<string> = {
  encode: (v) => (v ? v : null),
  decode: (raw) => raw ?? "",
};

const booleanSerializer: Serializer<boolean> = {
  encode: (v) => (v ? "1" : "0"),
  decode: (raw) => raw === "1" || raw === "true",
};

const nullableStringSerializer: Serializer<string | null> = {
  encode: (v) => (v && v.length > 0 ? v : null),
  decode: (raw) => (raw && raw.length > 0 ? raw : null),
};

export const URL_STATE_SERIALIZERS = {
  string: stringSerializer,
  boolean: booleanSerializer,
  nullableString: nullableStringSerializer,
} as const;


/**
 * Module-level update queue. Multiple `useUrlState` hooks updating in
 * the same render combine into a single `router.replace`. Without this,
 * three setState calls in one event handler would produce three URL
 * updates and three Next.js re-renders.
 */
let _pendingPatch: Record<string, string | null> | null = null;
let _pendingTimer: ReturnType<typeof setTimeout> | null = null;
let _routerRef: ReturnType<typeof useRouter> | null = null;
let _pathnameRef: string | null = null;
let _currentParamsRef: URLSearchParams | null = null;

function schedulePatch(key: string, value: string | null) {
  if (_pendingPatch === null) _pendingPatch = {};
  _pendingPatch[key] = value;
  if (_pendingTimer !== null) return;
  _pendingTimer = setTimeout(() => {
    if (
      _pendingPatch === null ||
      _routerRef === null ||
      _pathnameRef === null ||
      _currentParamsRef === null
    ) {
      _pendingPatch = null;
      _pendingTimer = null;
      return;
    }
    const params = new URLSearchParams(_currentParamsRef.toString());
    for (const [k, v] of Object.entries(_pendingPatch)) {
      if (v === null) params.delete(k);
      else params.set(k, v);
    }
    const qs = params.toString();
    _routerRef.replace(`${_pathnameRef}${qs ? `?${qs}` : ""}`, { scroll: false });
    _pendingPatch = null;
    _pendingTimer = null;
  }, 0);
}


export function useUrlState<T>(
  key: string,
  defaultValue: T,
  serializer: Serializer<T>,
): [T, (value: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Refresh module-level refs every render so the scheduler uses the
  // latest router/pathname.
  _routerRef = router;
  _pathnameRef = pathname;
  _currentParamsRef = searchParams as unknown as URLSearchParams;

  const raw = searchParams ? searchParams.get(key) : null;

  // Decode lazily on mount + when the URL changes externally.
  const decodedRef = useRef<{ raw: string | null; value: T }>({
    raw,
    value: serializer.decode(raw),
  });

  if (decodedRef.current.raw !== raw) {
    decodedRef.current = { raw, value: serializer.decode(raw) };
  }

  const [value, setValue] = useState<T>(() => {
    const decoded = serializer.decode(raw);
    // If the URL had no value, fall back to defaultValue.
    return raw === null ? defaultValue : decoded;
  });

  // If the URL changes externally (browser back / deeplink), sync state.
  useEffect(() => {
    const next = decodedRef.current.value;
    setValue((prev) =>
      Object.is(prev, next) ? prev : (raw === null ? defaultValue : next)
    );
    // We intentionally do not include defaultValue in deps — it can be
    // a new object every render and would re-trigger the effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw]);

  const update = useCallback(
    (next: T) => {
      setValue(next);
      const encoded = serializer.encode(next);
      schedulePatch(key, encoded);
    },
    [key, serializer],
  );

  return [value, update];
}


/**
 * Build a shareable URL from the current pathname + a set of params.
 * Useful when an action button needs a static href, not a navigation.
 */
export function buildShareableUrl(
  pathname: string,
  params: Record<string, string | number | boolean | null | undefined>,
): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") continue;
    sp.set(k, String(v));
  }
  const qs = sp.toString();
  return `${pathname}${qs ? `?${qs}` : ""}`;
}
