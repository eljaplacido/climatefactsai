"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SavedItemType, SavedItemRequest } from "@/types";

const TOKEN_KEY = "clilens_token";

function hasAuthToken(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem(TOKEN_KEY));
}

// localStorage cache key so anonymous users get optimistic toggle UX
// (lost on logout / clear, but covers the "did I already save this" case
// across page reloads).
function cacheKey(type: SavedItemType, ref: string): string {
  return `clilens-saved:${type}:${ref}`;
}

function getCachedSaved(type: SavedItemType, ref: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(cacheKey(type, ref)) === "1";
  } catch {
    return false;
  }
}

function setCachedSaved(type: SavedItemType, ref: string, saved: boolean) {
  if (typeof window === "undefined") return;
  try {
    if (saved) localStorage.setItem(cacheKey(type, ref), "1");
    else localStorage.removeItem(cacheKey(type, ref));
  } catch {
    /* localStorage full or unavailable — ignore */
  }
}

export interface UseSaveArgs {
  type: SavedItemType;
  /** UUID for FK-able types (article, analysis, claim, company). */
  id?: string | null;
  /** Free-text ref for non-UUID types (search URL, country code, JSON payload). */
  ref?: string | null;
  /** Optional metadata sent on save. */
  label?: string;
  notes?: string;
  folder?: string;
  payload?: Record<string, unknown>;
}

export interface UseSaveReturn {
  saved: boolean;
  busy: boolean;
  /** Error message from the last failed save attempt, or null. */
  error: string | null;
  /** Toggle save state — handles both POST (create) and DELETE. */
  toggle: () => Promise<void>;
}

/**
 * Generic save hook over the polymorphic /api/user/saved API.
 *
 * Replaces the per-type save plumbing (BookmarkButton's article-only path,
 * legacy /api/user/bookmarks/{id}). Works for any of the 8 item types.
 *
 *   const { saved, busy, toggle } = useSave({ type: "article", id: articleId });
 *   const { saved, busy, toggle } = useSave({ type: "company", id: companyId });
 *   const { saved, busy, toggle } = useSave({ type: "search", ref: searchUrl });
 */
export function useSave(args: UseSaveArgs): UseSaveReturn {
  const { type, id, ref, label, notes, folder, payload } = args;
  const cacheRef = id ?? ref ?? "";
  const [saved, setSaved] = useState<boolean>(() => getCachedSaved(type, cacheRef));
  const [savedId, setSavedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Confirm server truth on mount (cache may be stale for cross-device users).
  useEffect(() => {
    if (!cacheRef || !hasAuthToken()) return;
    let cancelled = false;
    api
      .checkSavedItem({ item_type: type, item_id: id || undefined, item_ref: ref || undefined })
      .then((resp) => {
        if (cancelled) return;
        setSaved(resp.saved);
        setSavedId(resp.saved_id);
        setCachedSaved(type, cacheRef, resp.saved);
      })
      .catch(() => {
        /* keep cached state on transport error */
      });
    return () => {
      cancelled = true;
    };
  }, [type, id, ref, cacheRef]);

  const toggle = useCallback(async () => {
    if (busy || !cacheRef) return;
    setBusy(true);
    setError(null);

    const prev = saved;
    setSaved(!prev);
    setCachedSaved(type, cacheRef, !prev);

    if (!hasAuthToken()) {
      // Anonymous toggle stays local-only; FE prompts auth where it matters.
      setBusy(false);
      return;
    }

    try {
      if (!prev) {
        const req: SavedItemRequest = {
          item_type: type,
          item_id: id ?? null,
          item_ref: ref ?? null,
          label: label ?? null,
          notes: notes ?? null,
          folder: folder ?? null,
          payload: payload ?? null,
        };
        await api.createSavedItem(req);
        // Re-fetch saved_id for subsequent delete.
        try {
          const check = await api.checkSavedItem({
            item_type: type,
            item_id: id || undefined,
            item_ref: ref || undefined,
          });
          setSavedId(check.saved_id);
        } catch {
          /* non-fatal */
        }
      } else if (savedId) {
        await api.deleteSavedItem(savedId);
        setSavedId(null);
      }
    } catch (err: unknown) {
      // Revert optimistic state on server failure.
      setSaved(prev);
      setCachedSaved(type, cacheRef, prev);
      const status =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { status?: number; data?: { detail?: unknown } } })
              .response
          : undefined;
      if (status?.status === 429) {
        const detail = status?.data?.detail as
          | { message?: string; limit?: number; tier?: string }
          | undefined;
        setError(
          detail?.message ??
            `Free-tier limit reached (${detail?.limit ?? "?"} ${type}s). Upgrade to save more.`
        );
      } else if (status?.status === 401) {
        setError("Sign in to save.");
      } else {
        setError("Couldn't save. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }, [busy, cacheRef, saved, savedId, type, id, ref, label, notes, folder, payload]);

  return { saved, busy, error, toggle };
}
