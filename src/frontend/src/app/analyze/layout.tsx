import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analyze URL — Climatefacts.ai",
  description:
    "Submit a climate news article URL for automated claim extraction and credibility verification.",
};

export default function AnalyzeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
