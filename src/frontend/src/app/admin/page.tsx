'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import UrlAnalysisForm from '@/components/UrlAnalysisForm'

export default function AdminPage() {
  const router = useRouter()
  const { token, loading: authLoading } = useAuth()
  const [articleId, setArticleId] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [discovering, setDiscovering] = useState(false)
  const [discoverCountry, setDiscoverCountry] = useState('FI')
  const [discoverKeywords, setDiscoverKeywords] = useState('climate, renewable, emissions')
  const [discoverDaysBack, setDiscoverDaysBack] = useState(3)
  const [discoverMaxArticles, setDiscoverMaxArticles] = useState(10)
  const [discoverVerify, setDiscoverVerify] = useState(true)

  // Client guard (audit FE-03): bounce non-authenticated visitors. The backend
  // additionally enforces admin (require_admin / QuotaService) on every endpoint
  // this panel calls — that is the real security boundary.
  useEffect(() => {
    if (!authLoading && !token) {
      router.replace('/login?next=/admin')
    }
  }, [authLoading, token, router])

  const handleVerify = async () => {
    if (!articleId) {
      setError('Please enter an article ID')
      return
    }

    setVerifying(true)
    setError(null)
    setResult(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'
      const response = await fetch(
        `${apiUrl}/api/v2/intelligence/verify/${articleId}`,
        {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  const handleVerifyAll = async () => {
    setVerifying(true)
    setError(null)
    setResult(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'
      
      // First, fetch unverified articles
      const articlesRes = await fetch(`${apiUrl}/api/articles?limit=10`)
      if (!articlesRes.ok) throw new Error('Failed to fetch articles')
      
      const articles = await articlesRes.json()
      const articleIds = articles
        .filter((a: any) => (a.claim_count || 0) === 0)
        .slice(0, 5)
        .map((a: any) => a.article_id)

      if (articleIds.length === 0) {
        setError('No unverified articles found')
        setVerifying(false)
        return
      }

      // Trigger batch verification
      const response = await fetch(
        `${apiUrl}/api/v2/intelligence/verify-batch`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ article_ids: articleIds })
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Batch verification failed')
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-3xl font-bold text-gray-900">
              Admin - Fact-Checking Control Panel
            </h1>
            <a
              href="/admin/analytics"
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium"
            >
              Analytics Dashboard
            </a>
          </div>
          <p className="text-gray-600 mb-8">
            Trigger AI-powered claim extraction and verification for articles
          </p>

          {/* URL Analysis Form */}
          <div className="mb-8">
            <UrlAnalysisForm />
          </div>

          {/* Single Article Verification */}
          <div className="mb-8 p-6 bg-blue-50 rounded-lg border border-blue-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Verify Single Article
            </h2>
            
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="Enter article UUID (e.g., 83ca8eda-29db-...)"
                value={articleId}
                onChange={(e) => setArticleId(e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleVerify}
                disabled={verifying}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                {verifying ? 'Processing...' : 'Verify Article'}
              </button>
            </div>

            <p className="mt-2 text-sm text-gray-600">
              This will extract claims and run fact-checking (30-60 seconds)
            </p>
          </div>

          {/* Batch Verification */}
          <div className="mb-8 p-6 bg-green-50 rounded-lg border border-green-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Batch Verification
            </h2>
            
            <button
              onClick={handleVerifyAll}
              disabled={verifying}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {verifying ? 'Processing...' : 'Verify Next 5 Unverified Articles'}
            </button>

            <p className="mt-2 text-sm text-gray-600">
              Automatically verifies articles that haven't been fact-checked yet
            </p>
          </div>

          {/* On-demand discovery */}
          <div className="mb-8 p-6 bg-purple-50 rounded-lg border border-purple-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Discover Fresh News (Perplexity)</h2>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <input
                type="text"
                value={discoverCountry}
                onChange={(e) => setDiscoverCountry(e.target.value.toUpperCase().slice(0, 2))}
                placeholder="FI"
                className="md:col-span-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <input
                type="text"
                value={discoverKeywords}
                onChange={(e) => setDiscoverKeywords(e.target.value)}
                placeholder="comma-separated keywords"
                className="md:col-span-4 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div className="mt-3 grid grid-cols-1 md:grid-cols-5 gap-3">
              <input
                type="number"
                min={1}
                max={14}
                value={discoverDaysBack}
                onChange={(e) => setDiscoverDaysBack(Number(e.target.value))}
                className="md:col-span-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                title="Days back"
              />
              <input
                type="number"
                min={1}
                max={25}
                value={discoverMaxArticles}
                onChange={(e) => setDiscoverMaxArticles(Number(e.target.value))}
                className="md:col-span-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                title="Max articles"
              />
              <label className="md:col-span-2 flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={discoverVerify}
                  onChange={(e) => setDiscoverVerify(e.target.checked)}
                />
                Queue verification after insert
              </label>
              <button
                onClick={async () => {
                  setDiscovering(true)
                  setError(null)
                  setResult(null)
                  try {
                    const keywords = discoverKeywords
                      .split(',')
                      .map((k) => k.trim())
                      .filter(Boolean)
                    const data = await api.discoverNews({
                      country_code: discoverCountry,
                      keywords,
                      days_back: discoverDaysBack,
                      max_articles: discoverMaxArticles,
                      verify: discoverVerify,
                    })
                    setResult(data)
                  } catch (err: any) {
                    setError(err?.message || 'Discovery failed')
                  } finally {
                    setDiscovering(false)
                  }
                }}
                disabled={discovering}
                className="md:col-span-1 px-6 py-2 bg-purple-700 text-white rounded-lg hover:bg-purple-800 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                {discovering ? 'Discovering...' : 'Discover'}
              </button>
            </div>

            <p className="mt-2 text-sm text-gray-600">
              Requires <code className="bg-white/60 px-1 rounded">PERPLEXITY_API_KEY</code> in <code className="bg-white/60 px-1 rounded">.env</code>.
            </p>
          </div>

          {/* Results */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 font-medium">Error:</p>
              <p className="text-red-600 text-sm mt-1">{error}</p>
            </div>
          )}

          {result && (
            <div className="p-6 bg-gray-50 rounded-lg border border-gray-200">
              <h3 className="font-semibold text-gray-900 mb-4">Result:</h3>
              <pre className="text-sm bg-gray-900 text-green-400 p-4 rounded overflow-auto">
                {JSON.stringify(result, null, 2)}
              </pre>
              {Array.isArray(result.article_ids) && result.article_ids.length > 0 && (
                <div className="mt-4 p-4 bg-white rounded border">
                  <h4 className="font-semibold mb-2">Inserted articles</h4>
                  <ul className="text-sm space-y-1">
                    {result.article_ids.slice(0, 10).map((id: string) => (
                      <li key={id}>
                        <a className="underline" href={`/articles/${id}`}>
                          {id}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.claims_extracted > 0 && (
                <div className="mt-4 p-4 bg-white rounded border">
                  <h4 className="font-semibold mb-2">Summary:</h4>
                  <ul className="text-sm space-y-1">
                    <li>✓ Claims extracted: {result.claims_extracted}</li>
                    <li>✓ Claims verified: {result.claims_verified}</li>
                    <li>✓ Claims disputed: {result.claims_disputed}</li>
                    <li>✓ Article credibility: {(result.article_credibility * 100).toFixed(0)}% ({result.credibility_level})</li>
                    <li>✓ Processing time: {result.total_processing_time_seconds?.toFixed(1)}s</li>
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Quick Reference */}
        <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            API Endpoints Reference
          </h2>
          <ul className="space-y-2 text-sm text-gray-700">
            <li><code className="bg-gray-100 px-2 py-1 rounded">GET /api/v2/articles</code> - List articles (DDD)</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">GET /api/v2/stats</code> - Platform statistics</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">POST /api/v2/intelligence/verify/:id</code> - Verify article</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">GET /api/articles</code> - Legacy endpoint</li>
            <li><code className="bg-gray-100 px-2 py-1 rounded">GET /docs</code> - Interactive API documentation</li>
          </ul>
          
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-sm text-yellow-800">
              <strong>Note:</strong> To get article UUIDs, visit{' '}
              <a 
                href={`${process.env.NEXT_PUBLIC_API_URL || ""}/api/articles`} 
                target="_blank"
                className="underline hover:text-yellow-900"
              >
                /api/articles
              </a>
              {' '}and copy an <code>article_id</code> value.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

