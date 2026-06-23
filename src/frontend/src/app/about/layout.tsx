import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About — Climatefacts.ai",
  description:
    "Climatefacts.ai is a transparent climate intelligence platform that fact-checks climate news with verifiable evidence.",
};

export default function AboutLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
