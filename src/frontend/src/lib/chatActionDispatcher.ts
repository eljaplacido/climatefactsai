"use client";

/**
 * Chat action dispatcher — Phase 1C (2026-05-23).
 *
 * The platform's agentic chat endpoints can return an `actions[]` payload
 * listing 0-3 suggested follow-up actions the user might take. This module
 * is the single place that knows how to safely execute each action type.
 *
 * Safety model — every action is classified as either:
 *   - AUTO: navigational, no server side-effect, no quota consumption.
 *     Executes immediately on click.
 *   - CONFIRM: consumes quota OR mutates server state. The dispatcher
 *     calls the host-provided `requestConfirmation` callback BEFORE
 *     executing. If the user declines, the action is recorded as
 *     'declined' and the side effect is skipped entirely.
 *
 * Quota-aware: the host can pre-check quota via QuotaService and disable
 * the action button in the UI; the backend still enforces 429 on the
 * actual gated endpoint. The dispatcher surfaces quota errors via the
 * returned Promise so the host can render the upgrade modal.
 */

export type ChatActionType =
  | "navigate"
  | "analyze_url"
  | "apply_search_filters"
  | "apply_map_filters"
  | "open_methodology_section"
  | "open_country"
  | "start_deep_search"
  | "bookmark_article"
  | "start_calibration_label"
  | "open_company"
  | "verify_corporate_claim"
  // Polish wave 1 (2026-05-25) — 4 new skills wrapping the endpoint
  // families shipped in deferred items 11/12/13/14 + Slice 3.
  // Keep in lockstep with backend SKILLS_REGISTRY in skills.py.
  | "save_item"
  | "subscribe_research_topic"
  | "explore_scenario"
  | "analyze_corporate_report";

export interface ChatActionSpec {
  type: ChatActionType;
  params: Record<string, string | number | boolean>;
  label: string;
}

export type ActionMode = "auto" | "confirm";

/**
 * Auto vs. confirm classification. Add new action types here when extending.
 *
 * Confirm-list = consumes quota OR mutates server-side state OR sends
 * messages on the user's behalf. Auto-list = pure navigation that the
 * user can always undo with the browser back button.
 */
export const ACTION_MODES: Record<ChatActionType, ActionMode> = {
  navigate: "auto",
  apply_search_filters: "auto",
  apply_map_filters: "auto",
  open_methodology_section: "auto",
  open_country: "auto",
  start_deep_search: "auto", // navigates to /deep-search?q=... — user still clicks Search
  open_company: "auto", // navigates to /companies/[ticker] — pure read
  analyze_url: "confirm",     // consumes url_analysis quota the moment it lands
  bookmark_article: "confirm", // consumes saved_articles quota + writes DB row
  start_calibration_label: "confirm", // submits a calibration rating
  verify_corporate_claim: "confirm", // POSTs a claim row + ECGT-sensitive verdict
  // Polish wave 1 (2026-05-25)
  save_item: "confirm",            // polymorphic save — consumes tier quota
  subscribe_research_topic: "confirm", // mutates server state + tier quota
  explore_scenario: "auto",        // read-only IPCC AR6 interpolation
  analyze_corporate_report: "confirm", // heavy LLM + persists claims
};

/**
 * Human-readable confirmation copy used by the host's confirmation modal.
 * Keep these short and action-oriented — they're what the user reads at
 * the decision moment.
 */
export const ACTION_CONFIRM_COPY: Record<
  ChatActionType,
  { title: string; message: (params: any) => string; cta: string }
> = {
  navigate: { title: "", message: () => "", cta: "" },
  apply_search_filters: { title: "", message: () => "", cta: "" },
  apply_map_filters: { title: "", message: () => "", cta: "" },
  open_methodology_section: { title: "", message: () => "", cta: "" },
  open_country: { title: "", message: () => "", cta: "" },
  start_deep_search: { title: "", message: () => "", cta: "" },
  open_company: { title: "", message: () => "", cta: "" },
  analyze_url: {
    title: "Run URL analysis?",
    message: (p) =>
      `Analysing "${p.url}" will use one of your monthly URL-analysis quotas. Continue?`,
    cta: "Analyse URL",
  },
  bookmark_article: {
    title: "Save this article?",
    message: () =>
      "This will count against your saved-articles quota. You can remove it later from your Saved tab.",
    cta: "Save article",
  },
  start_calibration_label: {
    title: "Submit calibration rating?",
    message: () =>
      "Your rating will be recorded against this URL analysis for our calibration set.",
    cta: "Open rating form",
  },
  verify_corporate_claim: {
    title: "Verify corporate climate claim?",
    message: (p) =>
      `This will grade "${p.claim_text}" against ${p.ticker}'s public disclosure ledger (CDP / SBTi) and record the verdict on the company profile. Continue?`,
    cta: "Verify claim",
  },
  // Polish wave 1 (2026-05-25)
  save_item: {
    title: "Save this item?",
    message: (p) =>
      `This will count against your saved-${p.item_type ?? "item"}s quota. You can remove it later from your Saves page.`,
    cta: "Save",
  },
  subscribe_research_topic: {
    title: "Subscribe to research topic?",
    message: (p) =>
      `New papers matching "${p.topic}" will land in your Research feed daily. Counts against your research-subscription quota.`,
    cta: "Subscribe",
  },
  explore_scenario: { title: "", message: () => "", cta: "" }, // auto-mode
  analyze_corporate_report: {
    title: "Analyse corporate sustainability report?",
    message: (p) =>
      `This will fetch "${p.report_url}", extract every claim, and grade each against ${p.ticker}'s disclosure ledger. Heavy LLM work — counts against quotas. Continue?`,
    cta: "Analyse report",
  },
};

export type DispatchResult =
  | { status: "executed" }
  | { status: "declined" }
  | { status: "error"; message: string; quotaExceeded?: boolean };

export interface DispatchOptions {
  /**
   * Host-provided confirmation hook. When the action's mode is 'confirm',
   * the dispatcher awaits this. Resolve true to proceed, false to decline.
   *
   * If not provided, confirm-mode actions FAIL CLOSED — they return
   * status: 'declined' rather than silently executing. This prevents a
   * misconfigured host from accidentally bypassing the confirmation gate.
   */
  requestConfirmation?: (action: ChatActionSpec) => Promise<boolean>;
}

const NAV_DISPATCHERS: Record<ChatActionType, (params: Record<string, any>) => void> = {
  navigate: ({ path }: any) => {
    if (typeof path === "string" && path.startsWith("/")) {
      window.location.assign(path);
    }
  },
  analyze_url: ({ url }: any) => {
    if (typeof url === "string") {
      window.location.assign(`/analyze?url=${encodeURIComponent(url)}`);
    }
  },
  apply_search_filters: (p: any) => {
    const sp = new URLSearchParams();
    if (p.q) sp.set("q", String(p.q));
    if (p.credibility) sp.set("credibility", String(p.credibility));
    if (p.country) sp.set("country", String(p.country));
    if (p.tags) sp.set("tags", String(p.tags));
    if (p.category) sp.set("category", String(p.category));
    window.location.assign(`/search?${sp.toString()}`);
  },
  apply_map_filters: (p: any) => {
    const sp = new URLSearchParams();
    if (p.country) sp.set("country", String(p.country));
    if (p.layer) sp.set("layer", String(p.layer));
    window.location.assign(`/map?${sp.toString()}`);
  },
  open_methodology_section: ({ section }: any) => {
    const hash = section ? `#${String(section)}` : "";
    window.location.assign(`/methodology${hash}`);
  },
  open_country: ({ code }: any) => {
    if (typeof code === "string" && code.length === 2) {
      window.location.assign(`/map?country=${code.toUpperCase()}`);
    }
  },
  start_deep_search: ({ q }: any) => {
    if (typeof q === "string") {
      // Uses the URL-persistent state hook on /deep-search to pre-fill
      // the input (mode=search by default).
      window.location.assign(`/deep-search?q=${encodeURIComponent(q)}`);
    }
  },
  bookmark_article: () => {
    // Handled below via async path — this nav-side stub is a no-op so
    // the dispatcher map stays uniform.
  },
  start_calibration_label: ({ url_analysis_id }: any) => {
    if (typeof url_analysis_id === "string") {
      window.location.assign(
        `/analyze?label=${encodeURIComponent(url_analysis_id)}`,
      );
    }
  },
  open_company: ({ ticker }: any) => {
    if (typeof ticker === "string" && ticker.length > 0) {
      window.location.assign(
        `/companies/${encodeURIComponent(ticker.toUpperCase())}`,
      );
    }
  },
  verify_corporate_claim: () => {
    // Handled via the async path below — POSTs the claim then navigates
    // the user to the company detail page where the verdict surfaces.
  },
  // Polish wave 1 (2026-05-25) — async-path stubs. The real work
  // lives in ASYNC_DISPATCHERS below; these placeholders keep the
  // dispatcher map uniform so TypeScript catches missing entries.
  save_item: () => {},
  subscribe_research_topic: () => {},
  explore_scenario: ({ country_code }: any) => {
    // Read-only — nav to the country passport where existing
    // ProjectionsPanel renders SSP scenarios. The interpolated
    // explorer endpoint is available at /api/scenario/country/{cc}
    // for direct chat answers; future iteration can render an
    // inline scenario card.
    if (typeof country_code === "string" && country_code.length === 2) {
      window.location.assign(`/country/${country_code.toUpperCase()}#projections`);
    }
  },
  analyze_corporate_report: () => {},
};

/**
 * Async-side handlers — run when the action needs an API round-trip.
 * Returns a DispatchResult so the host can surface success/failure.
 */
const ASYNC_DISPATCHERS: Partial<
  Record<ChatActionType, (params: Record<string, any>) => Promise<DispatchResult>>
> = {
  bookmark_article: async ({ article_id }: any) => {
    if (typeof article_id !== "string") {
      return { status: "error", message: "Missing article_id" };
    }
    // Slice 3 (2026-05-25) — migrated from legacy /api/user/bookmarks/{id}
    // to polymorphic /api/user/saved so the chat skill goes through the same
    // backend path as in-app Save buttons. Quota gate + 429 shape preserved.
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(`${base}/api/user/saved`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${
            typeof window !== "undefined"
              ? localStorage.getItem("clilens_token") || ""
              : ""
          }`,
        },
        body: JSON.stringify({
          item_type: "article",
          item_id: article_id,
          folder: "from-chat",
        }),
      });
      if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        return {
          status: "error",
          message:
            body?.detail?.message ||
            "You've used all your saved-article quota. Upgrade for more.",
          quotaExceeded: true,
        };
      }
      if (!resp.ok) {
        return { status: "error", message: `Save failed (HTTP ${resp.status})` };
      }
      return { status: "executed" };
    } catch (e: any) {
      return { status: "error", message: e?.message || "Network error" };
    }
  },
  // Phase 7 B3 (2026-05-24) — verify a corporate climate claim against the
  // disclosure ledger. POSTs to /api/companies/{ticker}/analyze; on success,
  // navigates the user to the company detail page where the verified claim
  // appears in the right-hand sidebar.
  verify_corporate_claim: async ({ ticker, claim_text }: any) => {
    if (typeof ticker !== "string" || typeof claim_text !== "string") {
      return { status: "error", message: "Missing ticker or claim_text" };
    }
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(
        `${base}/api/companies/${encodeURIComponent(ticker.toUpperCase())}/analyze`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ claim_text }),
        },
      );
      if (resp.status === 404) {
        return {
          status: "error",
          message: `Company ${ticker.toUpperCase()} is not in the disclosure ledger yet.`,
        };
      }
      if (!resp.ok) {
        return {
          status: "error",
          message: `Claim verification failed (HTTP ${resp.status})`,
        };
      }
      if (typeof window !== "undefined") {
        window.location.assign(
          `/companies/${encodeURIComponent(ticker.toUpperCase())}`,
        );
      }
      return { status: "executed" };
    } catch (e: any) {
      return { status: "error", message: e?.message || "Network error" };
    }
  },
  // Polish wave 1 (2026-05-25) — save_item: polymorphic /api/user/saved.
  // Same 429 quota shape as bookmark_article for FE error-handling parity.
  save_item: async ({ item_type, item_id, item_ref, label }: any) => {
    if (typeof item_type !== "string") {
      return { status: "error", message: "Missing item_type" };
    }
    if ((item_id == null) === (item_ref == null)) {
      return {
        status: "error",
        message: "Exactly one of item_id or item_ref must be provided",
      };
    }
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(`${base}/api/user/saved`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${
            typeof window !== "undefined"
              ? localStorage.getItem("clilens_token") || ""
              : ""
          }`,
        },
        body: JSON.stringify({
          item_type,
          item_id: item_id ?? null,
          item_ref: item_ref ?? null,
          label: label ?? null,
          folder: "from-chat",
        }),
      });
      if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        return {
          status: "error",
          message:
            body?.detail?.message ||
            `Free tier limit reached for ${item_type}s. Upgrade for more.`,
          quotaExceeded: true,
        };
      }
      if (!resp.ok) {
        return { status: "error", message: `Save failed (HTTP ${resp.status})` };
      }
      return { status: "executed" };
    } catch (e: any) {
      return { status: "error", message: e?.message || "Network error" };
    }
  },
  // subscribe_research_topic: POST /api/research/subscriptions, then
  // nav to /research so the user sees the existing feed start filling.
  subscribe_research_topic: async ({ topic }: any) => {
    if (typeof topic !== "string" || topic.length < 2) {
      return { status: "error", message: "Missing topic" };
    }
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(`${base}/api/research/subscriptions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${
            typeof window !== "undefined"
              ? localStorage.getItem("clilens_token") || ""
              : ""
          }`,
        },
        body: JSON.stringify({ topic }),
      });
      if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        return {
          status: "error",
          message:
            body?.detail?.message ||
            "Research-subscription quota reached. Upgrade for more.",
          quotaExceeded: true,
        };
      }
      if (!resp.ok) {
        return { status: "error", message: `Subscribe failed (HTTP ${resp.status})` };
      }
      if (typeof window !== "undefined") {
        window.location.assign("/research");
      }
      return { status: "executed" };
    } catch (e: any) {
      return { status: "error", message: e?.message || "Network error" };
    }
  },
  // analyze_corporate_report: POST /api/companies/{ticker}/analyze-report
  // then nav to /companies/{ticker} where verdicts surface in the claim
  // ledger. Heavy LLM work — confirm-gated.
  analyze_corporate_report: async ({ ticker, report_url }: any) => {
    if (typeof ticker !== "string" || typeof report_url !== "string") {
      return { status: "error", message: "Missing ticker or report_url" };
    }
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(
        `${base}/api/companies/${encodeURIComponent(ticker.toUpperCase())}/analyze-report`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${
              typeof window !== "undefined"
                ? localStorage.getItem("clilens_token") || ""
                : ""
            }`,
          },
          body: JSON.stringify({ report_url }),
        },
      );
      if (resp.status === 404) {
        return {
          status: "error",
          message: `Company ${ticker.toUpperCase()} not found in the corporate registry.`,
        };
      }
      if (resp.status === 422) {
        const body = await resp.json().catch(() => ({}));
        return {
          status: "error",
          message:
            body?.detail ||
            "Could not extract usable text from that URL. Try a different report.",
        };
      }
      if (!resp.ok) {
        return {
          status: "error",
          message: `Corporate report analysis failed (HTTP ${resp.status})`,
        };
      }
      if (typeof window !== "undefined") {
        window.location.assign(
          `/companies/${encodeURIComponent(ticker.toUpperCase())}`,
        );
      }
      return { status: "executed" };
    } catch (e: any) {
      return { status: "error", message: e?.message || "Network error" };
    }
  },
};

/**
 * Execute a chat-emitted action with safety classification.
 *
 * - AUTO actions: run immediately.
 * - CONFIRM actions: await host confirmation first; declined = no-op.
 *
 * Returns a DispatchResult that the host can use to surface inline
 * success / upgrade-modal / error toast.
 */
export async function dispatchChatAction(
  action: ChatActionSpec,
  options: DispatchOptions = {},
): Promise<DispatchResult> {
  const mode = ACTION_MODES[action.type];
  if (!mode) {
    return { status: "error", message: `Unknown action type: ${action.type}` };
  }

  if (mode === "confirm") {
    if (!options.requestConfirmation) {
      // Fail closed when the host did not wire a confirmation hook.
      // This is the safety property — a misconfigured host CANNOT silently
      // execute destructive actions.
      return { status: "declined" };
    }
    let confirmed = false;
    try {
      confirmed = await options.requestConfirmation(action);
    } catch {
      confirmed = false;
    }
    if (!confirmed) {
      recordActionEvent(action, "declined");
      return { status: "declined" };
    }
  }

  // Async path (API round-trip) takes precedence over navigation path.
  const asyncHandler = ASYNC_DISPATCHERS[action.type];
  if (asyncHandler) {
    const result = await asyncHandler(action.params);
    recordActionEvent(action, result.status === "executed" ? "executed" : "error");
    return result;
  }

  // Navigation path.
  const navHandler = NAV_DISPATCHERS[action.type];
  if (navHandler) {
    navHandler(action.params);
    recordActionEvent(action, "executed");
    return { status: "executed" };
  }

  return { status: "error", message: `No handler registered for ${action.type}` };
}

type ActionOutcome = "executed" | "declined" | "error";

/**
 * Best-effort telemetry. Records action clicks + outcomes for the action
 * usage report on /methodology and to feed the future quota-aware UX.
 */
async function recordActionEvent(
  action: ChatActionSpec,
  outcome: ActionOutcome,
): Promise<void> {
  try {
    await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || ""}/api/chat/actions/click`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...action, outcome }),
      },
    );
  } catch {
    // telemetry is best-effort
  }
}
