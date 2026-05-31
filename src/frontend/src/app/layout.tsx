import type { Metadata } from 'next'
import './globals.css'
import GlobalNav from '@/components/GlobalNav'
import ContextualAssistant from '@/components/ContextualAssistant'
import PageTranslator from '@/components/PageTranslator'
import ErrorBoundary from '@/components/ErrorBoundary'
import FirstTimerTour from '@/components/FirstTimerTour'
import { AuthProvider } from '@/lib/auth'
import { I18nProvider } from '@/lib/i18n-context'
import { ViewContextProvider } from '@/lib/view-context'
import { ToastProvider } from '@/components/Toast'

// Slice 5b (2026-05-25) — metadataBase makes per-page generateMetadata
// relative URLs (og:image, twitter:image, canonical) resolve to absolute
// for social-network crawlers. NEXT_PUBLIC_SITE_URL overrides for non-prod.
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  'https://climatenews-frontend-srzwxdzmaq-ez.a.run.app'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: 'Climatefacts.ai - Fact-Checked Climate News',
  description: 'AI-powered climate news verification and fact-checking platform',
  openGraph: {
    siteName: 'Climatefacts.ai',
    type: 'website',
  },
  twitter: { card: 'summary_large_image', site: '@climatefactsai' },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    // Pin color-scheme to light: the platform's dark-mode support is
    // partial (some components have `dark:` variants, most don't, and
    // no toggle wires `html.dark` to OS preference). Without this meta,
    // user OS dark mode + a stray `dark:text-gray-300` on a card with
    // no `dark:bg-...` partner produces 'light text on white' bug the
    // user reported. Forcing color-scheme=light gives every component
    // a known background to render against until a real theme system
    // ships. Audit loop 4 / slice S14 / gap §user-dashboard.
    <html lang="en" className="light" style={{ colorScheme: "light" }} suppressHydrationWarning>
      <body className="bg-gray-50" suppressHydrationWarning>
        <AuthProvider>
          <I18nProvider>
            <ViewContextProvider>
              <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-teal-600 focus:text-white focus:rounded">Skip to main content</a>
              <GlobalNav />
              <ErrorBoundary>
                <main className="pb-14">
                  {children}
                </main>
              </ErrorBoundary>
              <PageTranslator />
              <ContextualAssistant />
              <FirstTimerTour />
            </ViewContextProvider>
          </I18nProvider>
        </AuthProvider>
      </body>
    </html>
  )
}
