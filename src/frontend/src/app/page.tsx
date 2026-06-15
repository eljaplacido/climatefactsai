'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { api } from '../lib/api'
import type { Article, Country } from '../types'
import ArticleCard from '../components/ArticleCard'
import SkeletonCard from '../components/SkeletonCard'
import TrendingTopics from '../components/TrendingTopics'
import CountrySelector from '../components/CountrySelector'

type ViewMode = 'grid' | 'list' | 'compact'

export default function Home() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterCountry, setFilterCountry] = useState<string | null>(null)
  const [filterCredibility, setFilterCredibility] = useState<string>('all')
  const [filterTag, setFilterTag] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')

  const fetchArticles = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = { limit: 50 }
      if (filterCountry) params.country = filterCountry
      if (filterCredibility !== 'all') params.credibility = filterCredibility
      if (filterTag) params.tags = [filterTag]
      const data = await api.getArticles(params)
      setArticles(data)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch articles:', err)
      setError('Could not connect to API. Please ensure the backend is running.')
      setArticles([])
    } finally {
      setLoading(false)
    }
  }, [filterCountry, filterCredibility, filterTag])

  useEffect(() => {
    fetchArticles()
  }, [fetchArticles])

  // Featured articles: top-scored recent articles
  const featured = articles
    .filter((a) => a.overall_credibility === 'HIGH' && (a.reliability_score ?? 0) >= 70)
    .slice(0, 3)

  const gridClass =
    viewMode === 'grid'
      ? 'grid gap-6 md:grid-cols-2 lg:grid-cols-3'
      : viewMode === 'list'
      ? 'space-y-4'
      : 'grid gap-3 md:grid-cols-2 lg:grid-cols-4'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-clilens-teal-700 via-clilens-teal-600 to-clilens-teal-500 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
          <div className="mb-4">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-white/20 backdrop-blur-sm">
              <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              AI-Powered Fact Verification
            </span>
          </div>

          <h1 className="text-5xl font-bold mb-4">
            Climate Truth, <span className="text-clilens-teal-200">Verified by AI</span>
          </h1>

          <p className="text-xl text-clilens-teal-100 max-w-3xl mx-auto mb-8">
            Cut through the noise with fact-checked climate news synthesized from trusted sources.
            Every claim, every source, transparently verified.
          </p>

          <div className="flex items-center justify-center space-x-8 text-sm mb-6">
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2 text-clilens-teal-200" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Automated fact-checking
            </div>
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2 text-clilens-teal-200" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Scientific sources only
            </div>
            <div className="flex items-center">
              <svg className="w-5 h-5 mr-2 text-clilens-teal-200" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              100% transparent
            </div>
          </div>

          {/* Slice 3 / chat-as-heart (2026-05-27) — promote the
              agentic assistant alongside the map CTA. Clicking sets
              the URL hash to #chat which AgenticAssistant auto-expands
              on, so visitors land directly inside the chat. */}
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/#chat"
              className="inline-flex items-center px-6 py-3 bg-white text-clilens-teal-700 font-semibold rounded-lg hover:bg-clilens-teal-50 transition-colors shadow-md"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              Ask the climate assistant
            </Link>
            <Link
              href="/map"
              className="inline-flex items-center px-6 py-3 bg-white/15 backdrop-blur-sm text-white font-medium rounded-lg hover:bg-white/25 transition-colors border border-white/20"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
              Explore Climate Intelligence Map
            </Link>
          </div>
        </div>
      </div>

      {/* Trending Topics */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <TrendingTopics
            onTopicClick={(tag) => setFilterTag(filterTag === tag ? null : tag)}
            activeTag={filterTag}
            country={filterCountry || undefined}
          />
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-end gap-4 flex-wrap">
            <div className="flex-shrink-0 w-64">
              <CountrySelector value={filterCountry} onChange={setFilterCountry} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Credibility</label>
              <select
                value={filterCredibility}
                onChange={(e) => setFilterCredibility(e.target.value)}
                className="px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
              >
                <option value="all">All Levels</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            {/* View mode toggle */}
            <div className="ml-auto flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {([
                { mode: 'grid' as ViewMode, label: 'Grid', icon: 'M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z' },
                { mode: 'list' as ViewMode, label: 'List', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
                { mode: 'compact' as ViewMode, label: 'Compact', icon: 'M4 5h16a1 1 0 010 2H4a1 1 0 010-2zm0 4h16a1 1 0 010 2H4a1 1 0 010-2zm0 4h16a1 1 0 010 2H4a1 1 0 010-2zm0 4h16a1 1 0 010 2H4a1 1 0 010-2z' },
              ]).map(({ mode, label, icon }) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  title={label}
                  className={`p-1.5 rounded ${
                    viewMode === mode
                      ? 'bg-white shadow-sm text-clilens-primary'
                      : 'text-gray-400 hover:text-gray-600'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Featured Analysis section */}
        {!loading && featured.length > 0 && !filterTag && (
          <div className="mb-8">
            <h2 className="text-lg font-bold text-gray-900 mb-3">Featured Analysis</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {featured.map((a) => (
                <Link
                  key={a.article_id}
                  href={`/articles/${a.article_id}`}
                  className="block p-4 bg-gradient-to-br from-clilens-teal-50 to-white rounded-xl border border-clilens-teal-200 hover:shadow-md transition-all duration-200"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium text-clilens-primary px-2 py-0.5 bg-clilens-teal-100 rounded-full">
                      Featured
                    </span>
                    <span className="text-xs text-gray-400">{a.source_name}</span>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900 line-clamp-2">{a.title}</h3>
                  {a.executive_brief && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{a.executive_brief}</p>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Latest Verified Reports</h2>
            <p className="text-gray-600 mt-1">All articles are fact-checked and verified using AI-powered analysis of scientific sources</p>
          </div>
          {filterTag && (
            <button
              onClick={() => setFilterTag(null)}
              className="text-sm text-clilens-primary hover:underline"
            >
              Clear topic filter
            </button>
          )}
        </div>

        {error && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className={gridClass}>
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : articles.length > 0 ? (
          <div className={gridClass}>
            {articles.map((article) => (
              <ArticleCard key={article.article_id} article={article} />
            ))}
          </div>
        ) : !error ? (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <p className="text-gray-500 text-lg mb-2">No articles found</p>
            <p className="text-gray-400 text-sm">Try adjusting your filters or check back later for new reports.</p>
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={() => {
                  const params = []
                  if (filterCountry) params.push(`country: ${filterCountry}`)
                  if (filterCredibility !== 'all') params.push(`credibility: ${filterCredibility}`)
                  if (filterTag) params.push(`tag: ${filterTag}`)
                  const filterDesc = params.length > 0 ? ` with filters [${params.join(', ')}]` : ''
                  window.dispatchEvent(
                    new CustomEvent('climatenews:assistant-prefill', {
                      detail: {
                        prompt: `I'm looking at the home feed${filterDesc} and getting zero articles. Help me find what I'm looking for — should I broaden a filter, change the country, or pick a different topic?`,
                      },
                    }),
                  )
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-clilens-teal-50 hover:bg-clilens-teal-100 text-clilens-teal-700 border border-clilens-teal-200"
                data-testid="empty-feed-ask-assistant"
              >
                Ask the assistant to help me find articles
              </button>
            </div>
          </div>
        ) : null}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-clilens-primary rounded-full flex items-center justify-center">
                  <span className="text-white font-bold text-sm">C</span>
                </div>
                <span className="font-bold text-xl text-gray-900">Climatefacts.ai</span>
              </div>
              <p className="text-sm text-gray-600">
                Global climate trust intelligence: making claims auditable, uncertainty explicit, and evidence usable.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 mb-4">Platform</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><Link href="/about" className="hover:text-clilens-primary">How it works</Link></li>
                <li><Link href="/methodology" className="hover:text-clilens-primary">Methodology</Link></li>
                <li><Link href="/sources" className="hover:text-clilens-primary">Data sources</Link></li>
                <li><Link href="/map" className="hover:text-clilens-primary">Intelligence Map</Link></li>
                <li><Link href="/forecasts" className="hover:text-clilens-primary">Forecasts</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 mb-4">Resources</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><Link href="/about" className="hover:text-clilens-primary">About us</Link></li>
                <li><Link href="/analyze" className="hover:text-clilens-primary">Analyze URL</Link></li>
                <li><Link href="/search" className="hover:text-clilens-primary">Search</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 mb-4">Legal</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><Link href="/privacy" className="hover:text-clilens-primary">Privacy policy</Link></li>
                <li><Link href="/terms" className="hover:text-clilens-primary">Terms of service</Link></li>
                <li><Link href="/cookies" className="hover:text-clilens-primary">Cookie policy</Link></li>
              </ul>
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-gray-200 text-center text-sm text-gray-500">
            <p>&copy; {new Date().getFullYear()} Climatefacts.ai. Powered by Multi-Agent AI System.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
