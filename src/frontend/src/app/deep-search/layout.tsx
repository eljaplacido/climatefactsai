import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Deep Search — Climatefacts.ai",
  description:
    "AI-powered climate research with multi-source evidence retrieval, citation grounding, and confidence scoring.",
};

export default function DeepSearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
