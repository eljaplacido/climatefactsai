import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Corporate Climate Tracker — Climatefacts.ai",
  description:
    "Verify corporate climate claims against CDP, SBTi, and Net Zero Tracker disclosures. Standards compliance for CSRD, TCFD, IFRS S2.",
};

export default function CompaniesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
