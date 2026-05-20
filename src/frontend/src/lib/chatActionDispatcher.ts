"use client";

export type ChatActionType =
  | "navigate"
  | "analyze_url"
  | "apply_search_filters"
  | "apply_map_filters"
  | "open_methodology_section"
  | "open_country"
  | "start_deep_search"
  | "bookmark_article"
  | "start_calibration_label";

export interface ChatActionSpec {
  type: ChatActionType;
  params: Record<string, string | number | boolean>;
  label: string;
}

const DISPATCHERS: Record<
  ChatActionType,
  (params: Record<string, any>) => void
> = {
  navigate: ({ path }: any) => {
    if (typeof path === "string" && path.startsWith("/")) {
      window.location.assign(path as string);
    }
  },
  analyze_url: ({ url }: any) => {
    if (typeof url === "string") {
      window.location.assign(`/analyze?url=${encodeURIComponent(url as string)}`);
    }
  },
  apply_search_filters: ({
    q,
    credibility,
    country,
    tags,
    category,
  }: any) => {
    const sp = new URLSearchParams();
    if (q) sp.set("q", String(q));
    if (credibility) sp.set("credibility", String(credibility));
    if (country) sp.set("country", String(country));
    if (tags) sp.set("tags", String(tags));
    if (category) sp.set("category", String(category));
    window.location.assign(`/search?${sp.toString()}`);
  },
  apply_map_filters: ({ country, layer }: any) => {
    const sp = new URLSearchParams();
    if (country) sp.set("country", String(country));
    if (layer) sp.set("layer", String(layer));
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
      window.location.assign(
        `/deep-search?q=${encodeURIComponent(q as string)}`
      );
    }
  },
  bookmark_article: ({ article_id }: any) => {
    if (typeof article_id === "string") {
      import("@/lib/api").then(({ api }) => {
        fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/bookmarks`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("clilens_token") || ""}`,
          },
          body: JSON.stringify({
            article_id,
            folder: "from-chat",
          }),
        }).catch(() => {});
      });
    }
  },
  start_calibration_label: ({ url_analysis_id }: any) => {
    if (typeof url_analysis_id === "string") {
      window.location.assign(
        `/analyze?label=${encodeURIComponent(url_analysis_id as string)}`
      );
    }
  },
};

export function dispatchChatAction(action: ChatActionSpec): void {
  const handler = DISPATCHERS[action.type];
  if (!handler) return;
  handler(action.params);
  recordActionClick(action);
}

async function recordActionClick(action: ChatActionSpec) {
  try {
    await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || ""}/api/chat/actions/click`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(action),
      }
    );
  } catch {
    // telemetry is best-effort
  }
}
