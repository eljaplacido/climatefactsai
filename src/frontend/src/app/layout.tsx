import type { Metadata } from 'next'
import './globals.css'
import GlobalNav from '@/components/GlobalNav'
import ErrorBoundary from '@/components/ErrorBoundary'
import { AuthProvider } from '@/lib/auth'

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
    <html lang="en">
      <body className="bg-gray-50 dark:bg-gray-900">
        <AuthProvider>
          <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-teal-600 focus:text-white focus:rounded">Skip to main content</a>
          <GlobalNav />
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </AuthProvider>
      </body>
    </html>
  )
}
