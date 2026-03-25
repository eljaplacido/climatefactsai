'use client'

import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type { AnalyzeUrlResponse, Article, DecomposedConfidence } from '@/types'
import CredibilityGauge from './CredibilityGauge'
import Markdown from './Markdown'

export default function UrlAnalysisForm() {
  const [url, setUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'failed'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [article, setArticle] = useState<Article | null>(null)
  const [estimatedTime, setEstimatedTime] = useState<number | null>(null)
  const [decomposedConfidence, setDecomposedConfidence] = useState<DecomposedConfidence | null>(null)
  const [insightSummary, setInsightSummary] = useState<string | null>(null)

  // URL validation
  const validateUrl = (urlString: string): boolean => {
    if (!urlString || urlString.trim() === '') return false

    try {
      const urlObj = new URL(urlString)
      // Must be HTTPS
      if (urlObj.protocol !== 'https:') return false
      // Must have a valid hostname
      if (!urlObj.hostname || urlObj.hostname.length < 3) return false
      return true
    } catch {
      return false
    }
  }

  // Poll status every 3 seconds
  const pollStatus = useCallback(async (currentJobId: string) => {
    try {
      const response = await api.getAnalysisStatus(currentJobId)

      setStatus(response.status)

      if (response.status === 'completed') {
        setArticle(response.article || null)
        setDecomposedConfidence(response.decomposed_confidence || null)
        setInsightSummary(response.insight_summary || null)
        setJobId(null)
      } else if (response.status === 'failed') {
        setError(response.error || 'Analysis failed')
        setJobId(null)
      }
    } catch (err: any) {
      console.error('Error polling status:', err)
      setError(err?.response?.data?.error || 'Failed to check analysis status')
      setStatus('failed')
      setJobId(null)
    }
  }, [])

  // Auto-poll when jobId exists
  useEffect(() => {
    if (!jobId) return

    const intervalId = setInterval(() => {
      pollStatus(jobId)
    }, 3000)

    return () => clearInterval(intervalId)
  }, [jobId, pollStatus])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Reset state
    setError(null)
    setArticle(null)
    setJobId(null)
    setEstimatedTime(null)

    // Validate URL
    if (!validateUrl(url)) {
      setError('Please enter a valid HTTPS URL (e.g., https://example.com/article)')
      return
    }

    setIsSubmitting(true)
    setStatus('processing')

    try {
      const response = await api.analyzeUrl(url)

      if (response.status === 'processing') {
        setJobId(response.job_id)
        setEstimatedTime(response.estimated_time || null)
      } else if (response.status === 'completed') {
        setArticle(response.article || null)
        setDecomposedConfidence(response.decomposed_confidence || null)
        setInsightSummary(response.insight_summary || null)
        setStatus('completed')
      } else if (response.status === 'failed') {
        setError(response.error || 'Analysis failed')
        setStatus('failed')
      }
    } catch (err: any) {
      console.error('Error submitting URL:', err)

      // Handle specific error cases
      if (err?.response?.status === 503) {
        setError('ANTHROPIC_API_KEY is not configured. Please add it to the backend .env file.')
      } else if (err?.response?.status === 400) {
        setError(err?.response?.data?.error || 'Invalid URL provided')
      } else {
        setError(err?.response?.data?.error || 'Failed to analyze URL. Please try again.')
      }

      setStatus('failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    setUrl('')
    setStatus('idle')
    setError(null)
    setArticle(null)
    setJobId(null)
    setEstimatedTime(null)
    setDecomposedConfidence(null)
    setInsightSummary(null)
  }

  return (
    <div className="p-6 bg-gradient-to-br from-teal-50 to-cyan-50 rounded-lg border border-teal-200">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Analyze Climate News URL
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="url-input" className="block text-sm font-medium text-gray-700 mb-2">
            Article URL
          </label>
          <div className="flex gap-3">
            <input
              id="url-input"
              type="text"
              placeholder="https://example.com/climate-article"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isSubmitting || status === 'processing'}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={isSubmitting || status === 'processing' || !url.trim()}
              className="px-6 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {isSubmitting || status === 'processing' ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Analyzing...
                </span>
              ) : (
                'Analyze'
              )}
            </button>
          </div>
          <p className="mt-2 text-sm text-gray-600">
            Enter a climate news article URL (HTTPS required). The system will extract claims and verify credibility.
          </p>
        </div>

        {/* Status Messages */}
        {status === 'processing' && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <svg className="animate-spin h-5 w-5 text-blue-600 mt-0.5" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <div>
                <p className="text-blue-800 font-medium">Processing your request...</p>
                <p className="text-blue-600 text-sm mt-1">
                  Extracting content and analyzing claims. This may take {estimatedTime ? `${estimatedTime} seconds` : '30-60 seconds'}.
                </p>
                {jobId && (
                  <p className="text-blue-500 text-xs mt-2">Job ID: {jobId}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Error State */}
        {status === 'failed' && error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-3">
              <svg className="h-5 w-5 text-red-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <p className="text-red-800 font-medium">Analysis Failed</p>
                <p className="text-red-600 text-sm mt-1">{error}</p>
                <button
                  type="button"
                  onClick={handleReset}
                  className="mt-2 text-sm text-red-700 hover:text-red-800 underline"
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success State */}
        {status === 'completed' && article && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-start gap-3">
              <svg className="h-5 w-5 text-green-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="flex-1">
                <p className="text-green-800 font-medium mb-2">Analysis Complete</p>

                <div className="bg-white rounded-lg p-4 border border-green-200">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <h3 className="font-semibold text-gray-900 flex-1">{article.title}</h3>
                    <CredibilityGauge
                      score={article.source_credibility_score ?? 0}
                      level={article.overall_credibility}
                      decomposedConfidence={decomposedConfidence ?? undefined}
                      size="md"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                    <div>
                      <span className="text-gray-600">Source:</span>{' '}
                      <span className="font-medium">{article.source_name}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Published:</span>{' '}
                      <span className="font-medium">
                        {article.published_date ? new Date(article.published_date).toLocaleDateString() : 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Claims Extracted:</span>{' '}
                      <span className="font-medium">{article.claim_count}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Verified Claims:</span>{' '}
                      <span className="font-medium">{article.verified_claim_count}</span>
                    </div>
                  </div>

                  {insightSummary && (
                    <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-sm text-blue-800">{insightSummary}</p>
                    </div>
                  )}

                  {article.excerpt && (
                    <div className="text-gray-700 text-sm mb-3 italic border-l-4 border-green-300 pl-3">
                      <Markdown content={article.excerpt} />
                    </div>
                  )}

                  {article.tags && article.tags.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-3">
                      {article.tags.map((tag, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-teal-100 text-teal-800 text-xs rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <a
                      href={`/articles/${article.article_id}`}
                      className="text-sm text-teal-700 hover:text-teal-800 underline font-medium"
                    >
                      View Full Analysis →
                    </a>
                    <button
                      type="button"
                      onClick={handleReset}
                      className="text-sm text-gray-600 hover:text-gray-800 underline"
                    >
                      Analyze Another URL
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </form>
    </div>
  )
}
