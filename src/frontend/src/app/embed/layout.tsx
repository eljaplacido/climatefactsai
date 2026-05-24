import "../globals.css";

/**
 * Embed layout — Phase 2E (2026-05-23) MH6.
 *
 * Strips the global nav, chat, translator, and any other shell chrome
 * so embed pages live as standalone iframe-ready panes inside other
 * sites' articles. ONLY the embed content + the platform stylesheet
 * ship.
 *
 * This file overrides the root layout via Next.js App-Router nested
 * layouts: any route under /embed/* uses this body shell instead of
 * the full RootLayout from src/app/layout.tsx.
 */

export const metadata = {
  title: "Climatefacts.ai embed",
  // Belt-and-braces: also marked noindex inside the page metadata.
  robots: { index: false, follow: true },
};

export default function EmbedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className="bg-white text-slate-900"
        suppressHydrationWarning
        data-embed="true"
      >
        {children}
      </body>
    </html>
  );
}
