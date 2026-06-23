import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "API Access — Climatefacts.ai",
  description:
    "Access climate intelligence data via REST API. Free tier: 1,000 calls/day. Pro: 10,000/day.",
};

export default function ApiAccessLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
