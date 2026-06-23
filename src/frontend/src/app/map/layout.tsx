import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Climate Intelligence Map — Climatefacts.ai",
  description:
    "Interactive world map of climate data: temperature anomalies, NDC targets, corporate density, warming projections, and adaptation gaps.",
};

export default function MapLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
