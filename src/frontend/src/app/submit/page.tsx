'use client'

import { useState } from 'react'
import Link from 'next/link'
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

export default function SubmitArticlePage() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch('http://localhost:5400/api/articles/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: url,
          process_claims: true,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to submit article')
      }

      const data = await response.json()
      setResult(data)
      setUrl('') // Clear form
    } catch (err: any) {
      setError(err.message || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <Link href="/" className="text-2xl font-bold text-clilens-primary">
              CliLens
            </Link>
            <nav className="flex space-x-6">
              <Link
                href="/"
                className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
              >
                Home
              </Link>
              <Link
                href="/analyze"
                className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
              >
                Analyze URL
              </Link>
              <Link
                href="/search"
                className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
              >
                Search
              </Link>
            </nav>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Submit Climate Article
          </h1>
          <p className="text-gray-600 mb-8">
            Submit a climate news article URL for automatic fact-checking and claim verification.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                Article URL
              </label>
              <input
                type="url"
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                placeholder="https://example.com/climate-article"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
                disabled={loading}
              />
              <p className="mt-2 text-sm text-gray-500">
                Enter the URL of a climate news article from any major news source.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading || !url}
              className="w-full bg-clilens-primary text-white px-6 py-3 rounded-lg font-medium hover:bg-clilens-teal-600 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                'Submit Article'
              )}
            </button>
          </form>

          {/* Success Message */}
          {result && (
            <div className="mt-8 p-6 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start">
                <CheckCircle className="w-6 h-6 text-green-600 mr-3 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-green-900 mb-2">
                    Article Submitted Successfully!
                  </h3>
                  <div className="text-sm text-green-800 space-y-2">
                    <p><strong>Title:</strong> {result.title}</p>
                    <p><strong>Status:</strong> {result.status}</p>
                    <p className="mt-3">{result.message}</p>
                    {result.processing_started && (
                      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                        <p className="text-blue-800 text-sm">
                          ⏳ Claims are being extracted and verified in the background.
                          This typically takes 15-30 seconds.
                        </p>
                      </div>
                    )}
                    <div className="mt-4 flex space-x-3">
                      <Link
                        href={`/articles/${result.article_id}`}
                        className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                      >
                        View Article
                      </Link>
                      <Link
                        href="/"
                        className="inline-flex items-center px-4 py-2 bg-white text-green-700 border border-green-300 rounded-lg hover:bg-green-50 transition-colors text-sm font-medium"
                      >
                        Back to Home
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-8 p-6 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start">
                <AlertCircle className="w-6 h-6 text-red-600 mr-3 mt-0.5" />
                <div>
                  <h3 className="text-lg font-semibold text-red-900 mb-2">
                    Submission Failed
                  </h3>
                  <p className="text-sm text-red-800">{error}</p>
                  <p className="text-sm text-red-700 mt-3">
                    Please check the URL and try again. Some websites may block automated scraping.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Info Section */}
          <div className="mt-8 p-6 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="text-lg font-semibold text-blue-900 mb-3">
              How It Works
            </h3>
            <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800">
              <li>Submit a climate news article URL</li>
              <li>Our system scrapes and extracts the article content</li>
              <li>AI analyzes the text and identifies factual claims</li>
              <li>Each claim is automatically fact-checked against scientific sources</li>
              <li>Results are available within 30 seconds</li>
            </ol>
          </div>

          {/* Supported Sources */}
          <div className="mt-6 p-6 bg-gray-50 border border-gray-200 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Supported Sources
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-gray-600">
              <div>• The Guardian</div>
              <div>• AP News</div>
              <div>• Nat Geo</div>
              <div>• NASA Climate</div>
              <div>• NOAA</div>
              <div>• Scientific American</div>
              <div>• Nature</div>
              <div>• And many more...</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
