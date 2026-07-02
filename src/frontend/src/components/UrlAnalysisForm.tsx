'use client'

import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type {
  AnalyzeUrlResponse,
  AnalyzeUrlFailureDetail,
  AnalyzeUrlFailureReason,
  Article,
  DecomposedConfidence,
} from '@/types'
import CredibilityGauge from './CredibilityGauge'
import Markdown from './Markdown'
import AIProvenanceBadge from './AIProvenanceBadge'
import QuotaCounter from './QuotaCounter'
import UpgradeModal, { type UpgradeModalQuotaEnvelope } from './UpgradeModal'
import { useQuota } from '@/lib/useQuota'
import { useViewContext } from '@/lib/view-context'
import { useAuth } from '@/lib/auth'

// Per-reason icon emoji. Plain emoji on purpose — `lucide-react` doesn't
// have great visual differentiators for "paywall" vs "JS-SPA" vs
// "robots-blocked", and the emoji communicates the failure class in <40ms.
const REASON_ICON: Record<AnalyzeUrlFailureReason, string> = {
  http_forbidden: '\u{1F6AB}',         // 🚫
  http_not_found: '\u{1F50D}',         // 🔍
  http_legal_block: '\u{2696}',        // ⚖
  http_4xx_other: '\u{26A0}',          // ⚠
  http_5xx: '\u{1F4A5}',               // 💥
  timeout: '\u{23F1}',                 // ⏱
  response_too_large: '\u{1F4E6}',     // 📦
  extraction_too_short: '\u{1F4DD}',   // 📝
  paywall_suspected: '\u{1F4B3}',      // 💳
  js_rendered_spa: '\u{1F310}',        // 🌐
  redirect_blocked: '\u{1F512}',       // 🔒
  network_error: '\u{1F50C}',          // 🔌
  validation_failed: '\u{1F6AB}',      // 🚫
  claim_extraction_failed: '\u{1F916}', // 🤖
  unknown: '\u{2753}',                 // ❓
}

export default function UrlAnalysisForm() {
  const [url, setUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  // Access token returned by POST — required on GET for anonymous reads (S7).
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'failed'>('idle')
  const [error, setError] = useState<string | null>(null)
  // Structured failure (§3.4 fix on 2026-05-23). When present, the rich
  // failure block is rendered instead of the free-form `error` line.
  const [failureDetail, setFailureDetail] = useState<AnalyzeUrlFailureDetail | null>(null)
  const [article, setArticle] = useState<Article | null>(null)
  const [estimatedTime, setEstimatedTime] = useState<number | null>(null)
  const [decomposedConfidence, setDecomposedConfidence] = useState<DecomposedConfidence | null>(null)
  const [insightSummary, setInsightSummary] = useState<string | null>(null)

  // Phase 2A (2026-05-23) — quota envelope from a 429; refresh() ticks the
  // counter immediately after a successful submission.
  const { refresh: refreshQuota } = useQuota()
  const [upgradeQuota, setUpgradeQuota] = useState<UpgradeModalQuotaEnvelope | null>(null)
  const [upgradeMessage, setUpgradeMessage] = useState<string | null>(null)

  const { setView, clearKey } = useViewContext()
  const { isLoggedIn, loading: authLoading } = useAuth()

  // Publish the in-flight / completed analysis id into the shared view-context
  // so the chat assistant can answer "explain this analysis" without guessing.
  useEffect(() => {
    if (jobId) {
      setView({
        analysisId: jobId,
        label: url ? `URL analysis: ${url}` : undefined,
      })
    } else {
      clearKey('analysisId')
    }
  }, [jobId, url, setView, clearKey])

  useEffect(() => {
    // The completed `article.article_id` is the analysis_id (the URL flow does
    // not produce a canonical article the chat can hydrate), so publish it as
    // analysisId — not articleId — to keep the assistant's context honest.
    if (status === 'completed' && article?.article_id) {
      setView({
        analysisId: article.article_id,
        label: `URL analysis result: ${article.title || url}`,
      })
    }
    if (status === 'idle') {
      clearKey('articleId')
      clearKey('analysisId')
      clearKey('label')
    }
  }, [status, article, url, setView, clearKey])

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
  const pollStatus = useCallback(async (currentJobId: string, currentToken: string | null) => {
    try {
      const response = await api.getAnalysisStatus(currentJobId, currentToken ?? undefined)

      setStatus(response.status)

      if (response.status === 'completed') {
        setArticle(response.article || null)
        setDecomposedConfidence(response.decomposed_confidence || null)
        setInsightSummary(response.insight_summary || null)
        setFailureDetail(null)
        setJobId(null)
      } else if (response.status === 'failed') {
        setError(response.error || response.failure_detail?.message || 'Analysis failed')
        setFailureDetail(response.failure_detail || null)
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
      pollStatus(jobId, accessToken)
    }, 3000)

    return () => clearInterval(intervalId)
  }, [jobId, accessToken, pollStatus])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Reset state
    setError(null)
    setArticle(null)
    setJobId(null)
    setAccessToken(null)
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
        setAccessToken(response.access_token || null)
        setEstimatedTime(response.estimated_time || null)
        // The url_analysis quota was consumed on the backend at submission
        // time — tick the inline counter so the user sees their remaining
        // quota update immediately.
        refreshQuota()
      } else if (response.status === 'completed') {
        setArticle(response.article || null)
        setDecomposedConfidence(response.decomposed_confidence || null)
        setInsightSummary(response.insight_summary || null)
        setFailureDetail(null)
        setStatus('completed')
        refreshQuota()
      } else if (response.status === 'failed') {
        setError(response.error || response.failure_detail?.message || 'Analysis failed')
        setFailureDetail(response.failure_detail || null)
        setStatus('failed')
      }
    } catch (err: any) {
      console.error('Error submitting URL:', err)

      // Phase 2A — surface 429 via the UpgradeModal, not the inline error
      // line. The backend returns { detail: { error, quota, message } }.
      const detail = err?.response?.data?.detail
      if (err?.response?.status === 429 && detail && typeof detail === 'object' && detail.quota) {
        setUpgradeQuota(detail.quota as UpgradeModalQuotaEnvelope)
        setUpgradeMessage(typeof detail.message === 'string' ? detail.message : null)
        setStatus('idle')
        return
      }

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
    setFailureDetail(null)
    setArticle(null)
    setJobId(null)
    setAccessToken(null)
    setEstimatedTime(null)
    setDecomposedConfidence(null)
    setInsightSummary(null)
  }

  const openAssistant = (prompt?: string) => {
    if (typeof window !== 'undefined' && prompt) {
      window.dispatchEvent(
        new CustomEvent('climatenews:assistant-prefill', {
          detail: { prompt },
        })
      )
    }

    const assistantToggle = document.querySelector<HTMLElement>('[data-chat-toggle]')
    assistantToggle?.click()
  }

  return (
    <div className="p-6 bg-gradient-to-br from-teal-50 to-cyan-50 rounded-lg border border-teal-200">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Analyze Climate News URL
      </h2>

      {!authLoading && !isLoggedIn && (
        <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm text-amber-900 font-medium">Sign in to analyze URLs</p>
          <p className="text-sm text-amber-800 mt-1">
            URL credibility analysis is available on the Basic plan and above. Your
            session may also have expired — sign in again to continue.
          </p>
          <a
            href={`/login?redirect=${encodeURIComponent('/analyze')}`}
            className="inline-block mt-2 text-sm font-medium text-amber-900 underline hover:text-amber-700"
          >
            Sign in →
          </a>
        </div>
      )}

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
            <div className="flex flex-col items-end gap-1">
              <QuotaCounter quotaKey="url_analysis" hideWhenUnlimited />
            </div>
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

        {/* Error State — structured failure block (§3.4 fix on 2026-05-23).
            When the backend classified the failure (failureDetail present),
            we render the icon + title + message + remediation + a
            type-specific deeplink. Otherwise we fall back to the legacy
            free-form `error` line so older backends keep working. */}
        {status === 'failed' && (failureDetail || error) && (
          <div
            className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/50 rounded-lg"
            role="alert"
            aria-live="polite"
            data-testid="url-analysis-failure"
          >
            {failureDetail ? (
              <div className="flex items-start gap-3">
                <span
                  className="text-2xl leading-none flex-shrink-0"
                  aria-hidden="true"
                >
                  {REASON_ICON[failureDetail.reason] || REASON_ICON.unknown}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p
                      className="text-red-900 dark:text-red-100 font-semibold"
                      data-testid="url-analysis-failure-title"
                    >
                      {failureDetail.title}
                    </p>
                    <span
                      className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider bg-red-100 dark:bg-red-900/60 text-red-700 dark:text-red-300 rounded"
                      data-testid="url-analysis-failure-reason"
                    >
                      {failureDetail.reason}
                    </span>
                    {failureDetail.status_code !== undefined && (
                      <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono bg-red-100 dark:bg-red-900/60 text-red-700 dark:text-red-300 rounded">
                        HTTP {failureDetail.status_code}
                      </span>
                    )}
                  </div>
                  <p className="text-red-800 dark:text-red-200 text-sm mt-1.5 leading-relaxed">
                    {failureDetail.message}
                  </p>
                  <div className="mt-3 p-3 bg-white dark:bg-red-950/60 border border-red-100 dark:border-red-800/40 rounded">
                    <p className="text-xs font-semibold text-red-800 dark:text-red-300 uppercase tracking-wide mb-1">
                      What to try
                    </p>
                    <p className="text-sm text-red-700 dark:text-red-200 leading-relaxed">
                      {failureDetail.remediation}
                    </p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-3 items-center">
                    <button
                      type="button"
                      onClick={handleReset}
                      className="text-sm font-medium text-red-700 dark:text-red-300 hover:text-red-900 dark:hover:text-red-100 underline"
                    >
                      Try a different URL
                    </button>
                    {(failureDetail.reason === 'paywall_suspected' ||
                      failureDetail.reason === 'js_rendered_spa' ||
                      failureDetail.reason === 'extraction_too_short' ||
                      failureDetail.reason === 'http_legal_block') && (
                      <a
                        href="/research"
                        className="text-sm font-medium text-red-700 dark:text-red-300 hover:text-red-900 dark:hover:text-red-100 underline"
                        data-testid="url-analysis-failure-paste-deeplink"
                      >
                        Open /research → Paste text
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() =>
                        openAssistant(
                          `My URL analysis failed (${failureDetail.reason}) for ${url || 'a submitted URL'}. The platform said: "${failureDetail.message}". Help me work around this.`
                        )
                      }
                      className="text-sm font-medium text-red-700 dark:text-red-300 hover:text-red-900 dark:hover:text-red-100 underline"
                    >
                      Get help in chat
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3">
                <svg
                  className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
                <div>
                  <p className="text-red-800 dark:text-red-100 font-medium">Analysis Failed</p>
                  <p className="text-red-600 dark:text-red-300 text-sm mt-1">{error}</p>
                  <button
                    type="button"
                    onClick={handleReset}
                    className="mt-2 text-sm text-red-700 dark:text-red-300 hover:text-red-800 dark:hover:text-red-100 underline"
                  >
                    Try again
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      openAssistant(
                        `My URL analysis failed for ${url || 'a submitted URL'}. Help me troubleshoot input format and source accessibility.`
                      )
                    }
                    className="mt-2 ml-3 text-sm text-red-700 dark:text-red-300 hover:text-red-800 dark:hover:text-red-100 underline"
                  >
                    Get help in chat
                  </button>
                </div>
              </div>
            )}
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

                  {/* ML-09 — make the credibility label self-explaining. When the
                      score came from the extraction heuristic (nothing verified),
                      say so plainly rather than letting a HIGH-looking gauge imply
                      the claims held up against evidence. */}
                  {article.score_basis && (
                    <div className="mb-3">
                      {article.score_basis === 'verification_backed' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Verification-backed score
                        </span>
                      ) : (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-amber-50 text-amber-800 border border-amber-200"
                          title="Score derived from text length and claim density — no claim reached a supporting verdict against external evidence."
                        >
                          Unverified — extraction heuristic (no claims verified)
                        </span>
                      )}
                    </div>
                  )}

                  {/* Phase 0 day 3 (2026-05-23) — EU AI Act Art. 50 disclosure
                      for AI-produced URL credibility verdicts. */}
                  <div className="mb-3">
                    <AIProvenanceBadge
                      provenance={{
                        model: (article.provenance?.model_name as string) || "deepseek-chat",
                        prompt_name: (article.provenance?.prompt_name as string) || "claim_extraction",
                        prompt_version: (article.provenance?.prompt_version as string) || undefined,
                        prompt_fingerprint: (article.provenance?.prompt_fingerprint as string) || undefined,
                        retrieval_strategy: "user_submitted_url",
                        timestamp: article.created_at || new Date().toISOString(),
                        surface: "url_analysis",
                        content_summary: `URL credibility analysis: ${article.title}`,
                      }}
                      variant="inline"
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
                      href={`/research/analysis/${article.article_id}`}
                      className="text-sm text-teal-700 hover:text-teal-800 underline font-medium"
                    >
                      View Full Analysis →
                    </a>
                    <button
                      type="button"
                      onClick={() =>
                        openAssistant(
                          `Explain this URL analysis result for \"${article.title || url}\" and what the credibility score implies.`
                        )
                      }
                      className="text-sm text-teal-700 hover:text-teal-800 underline font-medium"
                    >
                      Ask chat to explain
                    </button>
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

      {/* Phase 2A (2026-05-23) — upgrade modal mounts at form root,
          shown when 429 fires with the structured envelope. */}
      <UpgradeModal
        quota={upgradeQuota}
        message={upgradeMessage}
        onClose={() => {
          setUpgradeQuota(null)
          setUpgradeMessage(null)
        }}
      />
    </div>
  )
}
