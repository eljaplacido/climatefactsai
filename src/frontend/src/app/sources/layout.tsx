import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Source Registry — Climatefacts.ai",
  description:
    "Browse climate news sources with editorial standards, fact-check records, and transparency scores.",
};

export default function SourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
