import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Search Climate News — Climatefacts.ai",
  description:
    "Search verified climate news articles with credibility scores, source tiers, and fact-check status.",
};

export default function SearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
