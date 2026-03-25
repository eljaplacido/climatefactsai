'use client'

import UrlAnalysisForm from '@/components/UrlAnalysisForm'

export default function AnalyzePage() {
  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Analyze Article URL</h1>
        <p className="text-gray-600">
          Submit any climate news article URL for automated fact-checking and credibility analysis
        </p>
      </div>

      <UrlAnalysisForm />

      <div className="mt-12 bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h2 className="font-semibold text-gray-900 mb-3">How it works:</h2>
        <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside">
          <li>Paste the URL of a climate news article (must be HTTPS)</li>
          <li>We fetch and analyze the article content</li>
          <li>AI extracts factual claims from the article</li>
          <li>Each claim is verified against scientific sources</li>
          <li>You get a detailed credibility report in ~30 seconds</li>
        </ol>

        <div className="mt-4 text-sm text-gray-600">
          <strong>Note:</strong> This feature requires authentication.
          Free tier: 0 analyses/month. Basic: 5/month. Professional: 20/month. Enterprise: Unlimited.
        </div>
      </div>
    </div>
  )
}
