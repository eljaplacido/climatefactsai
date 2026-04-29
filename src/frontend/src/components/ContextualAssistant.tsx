"use client";

import { usePathname } from "next/navigation";
import AgenticAssistant from "./AgenticAssistant";

function extractPage(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  if (segments[0] === "articles" && segments[2] === "transparency") return "transparency";
  if (segments[0] === "articles") return "articles";
  return segments[0] || "default";
}

function extractArticleId(pathname: string): string | undefined {
  const match = pathname.match(/^\/articles\/([^/]+)/);
  return match?.[1];
}

export default function ContextualAssistant() {
  const pathname = usePathname() || "/";
  const currentPage = extractPage(pathname);
  const articleId = extractArticleId(pathname);

  return (
    <AgenticAssistant
      currentPage={currentPage}
      currentArticleId={articleId}
    />
  );
}
