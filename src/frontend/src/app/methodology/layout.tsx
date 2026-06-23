import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology — Climatefacts.ai",
  description:
    "How Climatefacts.ai verifies climate claims: versioned prompts, calibration metrics, hallucination rates, drift detection, and the full audit surface.",
};

export default function MethodologyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
