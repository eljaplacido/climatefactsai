"use client";

import { useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import AgenticAssistant from "./AgenticAssistant";
import { useViewContext } from "@/lib/view-context";

function extractPage(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  // /articles/[id]/transparency is still about the article — keep page=transparency
  // for example chips, but the article id itself is published below.
  if (segments[0] === "articles" && segments[2] === "transparency") return "transparency";
  if (segments[0] === "articles") return "articles";
  return segments[0] || "default";
}

function extractArticleId(pathname: string): string | undefined {
  const match = pathname.match(/^\/articles\/([^/]+)/);
  if (!match) return undefined;
  const id = match[1];
  // Guard against the literal "new" / unrelated subroutes
  if (id === "new" || id === "") return undefined;
  return id;
}

export default function ContextualAssistant() {
  const pathname = usePathname() || "/";
  const currentPage = extractPage(pathname);
  const articleIdFromPath = extractArticleId(pathname);
  const { view, setView } = useViewContext();

  // Keep the route / article id in shared view-context so other surfaces
  // (e.g. the map's chat) can read it too.
  useEffect(() => {
    setView({ route: pathname, articleId: articleIdFromPath });
  }, [pathname, articleIdFromPath, setView]);

  // Prefer the article id published by a page (e.g. transparency page) over
  // the path-derived value, but fall back to the path so the article detail
  // page works even if it does not publish into view-context.
  const currentArticleId = view.articleId || articleIdFromPath;

  const compareCountriesLabel = useMemo(() => {
    if (!view.compareCountries || view.compareCountries.length < 2) return undefined;
    return view.compareCountries.join(" vs ");
  }, [view.compareCountries]);

  return (
    <AgenticAssistant
      currentPage={currentPage}
      currentArticleId={currentArticleId}
      currentCountry={view.countryCode}
      currentAnalysisId={view.analysisId}
      currentDeepSearchQuery={view.deepSearchQuery}
      currentDeepSearchCompare={view.deepSearchCompare}
      currentCompareCountries={view.compareCountries}
      currentSourceId={view.sourceId}
      currentRoute={pathname}
      contextLabel={view.label || compareCountriesLabel}
    />
  );
}
