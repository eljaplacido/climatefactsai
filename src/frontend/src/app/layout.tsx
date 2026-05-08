import type { Metadata } from 'next'
import './globals.css'
import GlobalNav from '@/components/GlobalNav'
import ContextualAssistant from '@/components/ContextualAssistant'
import PageTranslator from '@/components/PageTranslator'
import ErrorBoundary from '@/components/ErrorBoundary'
import { AuthProvider } from '@/lib/auth'
import { I18nProvider } from '@/lib/i18n-context'
import { ViewContextProvider } from '@/lib/view-context'

export const metadata: Metadata = {
  title: 'CliLens.AI - Fact-Checked Climate News',
  description: 'AI-powered climate news verification and fact-checking platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-gray-50 dark:bg-gray-900" suppressHydrationWarning>
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
            </ViewContextProvider>
          </I18nProvider>
        </AuthProvider>
      </body>
    </html>
  )
}
