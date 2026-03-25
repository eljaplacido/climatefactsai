'use client'

import { useState, useEffect } from 'react'
import { Play, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react'

interface PipelineStatus {
  total_articles: number
  needs_claim_extraction: number
  needs_verification: number
  completed: number
  failed: number
}

interface PipelineResponse {
  status: string
  message: string
  articles_processed: number
  claims_extracted: number
  claims_verified: number
  errors: string[]
}

export default function PipelinePage() {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState<PipelineResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchStatus = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'
      const response = await fetch(`${apiUrl}/api/admin/pipeline/status`)
      const data = await response.json()
      setStatus(data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch pipeline status:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const triggerExtraction = async () => {
    setProcessing(true)
    setResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'
      const response = await fetch(`${apiUrl}/api/admin/pipeline/extract-claims`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 10, extract_claims: true, verify_claims: false })
      })
      const data = await response.json()
      setResult(data)
      fetchStatus() // Refresh status
    } catch (error) {
      console.error('Failed to trigger extraction:', error)
    } finally {
      setProcessing(false)
    }
  }

  const triggerVerification = async () => {
    setProcessing(true)
    setResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'
      const response = await fetch(`${apiUrl}/api/admin/pipeline/verify-claims`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 10 })
      })
      const data = await response.json()
      setResult(data)
      fetchStatus()
    } catch (error) {
      console.error('Failed to trigger verification:', error)
    } finally {
      setProcessing(false)
    }
  }

  const triggerFullPipeline = async () => {
    setProcessing(true)
    setResult(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'
      const response = await fetch(`${apiUrl}/api/admin/pipeline/process-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 10, extract_claims: true, verify_claims: true })
      })
      const data = await response.json()
      setResult(data)
      fetchStatus()
    } catch (error) {
      console.error('Failed to trigger pipeline:', error)
    } finally {
      setProcessing(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Pipeline Management</h1>
        <p className="text-gray-600">
          Trigger claim extraction and verification for articles
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Total Articles</span>
            <RefreshCw
              className="h-4 w-4 text-gray-400 cursor-pointer hover:text-gray-600"
              onClick={fetchStatus}
            />
          </div>
          <div className="text-3xl font-bold text-gray-900">{status?.total_articles || 0}</div>
        </div>

        <div className="bg-yellow-50 p-6 rounded-lg border border-yellow-200 shadow-sm">
          <div className="text-sm font-medium text-yellow-800 mb-2">Needs Extraction</div>
          <div className="text-3xl font-bold text-yellow-900">{status?.needs_claim_extraction || 0}</div>
        </div>

        <div className="bg-blue-50 p-6 rounded-lg border border-blue-200 shadow-sm">
          <div className="text-sm font-medium text-blue-800 mb-2">Needs Verification</div>
          <div className="text-3xl font-bold text-blue-900">{status?.needs_verification || 0}</div>
        </div>

        <div className="bg-green-50 p-6 rounded-lg border border-green-200 shadow-sm">
          <div className="text-sm font-medium text-green-800 mb-2">Completed</div>
          <div className="text-3xl font-bold text-green-900">{status?.completed || 0}</div>
        </div>

        <div className="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm">
          <div className="text-sm font-medium text-red-800 mb-2">Failed</div>
          <div className="text-3xl font-bold text-red-900">{status?.failed || 0}</div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Pipeline Actions</h2>

        <div className="space-y-3">
          <button
            onClick={triggerExtraction}
            disabled={processing || (status?.needs_claim_extraction || 0) === 0}
            className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="h-5 w-5" />
            <span>Extract Claims (Next 10 Articles)</span>
          </button>

          <button
            onClick={triggerVerification}
            disabled={processing || (status?.needs_verification || 0) === 0}
            className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <CheckCircle className="h-5 w-5" />
            <span>Verify Claims (Next 10 Articles)</span>
          </button>

          <button
            onClick={triggerFullPipeline}
            disabled={processing || (status?.needs_claim_extraction || 0) === 0}
            className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gradient-to-r from-green-600 to-blue-600 text-white rounded-lg hover:from-green-700 hover:to-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="h-5 w-5" />
            <span>Full Pipeline (Extract + Verify - Next 10)</span>
          </button>
        </div>

        {processing && (
          <div className="mt-4 flex items-center justify-center space-x-2 text-blue-600">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
            <span>Processing...</span>
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className={`p-6 rounded-lg border ${
          result.status === 'completed' ? 'bg-green-50 border-green-200' :
          result.status === 'partial' ? 'bg-yellow-50 border-yellow-200' :
          'bg-red-50 border-red-200'
        }`}>
          <h3 className="font-semibold text-lg mb-2">
            {result.status === 'completed' ? '✅ Success' :
             result.status === 'partial' ? '⚠️ Partial Success' :
             '❌ Failed'}
          </h3>
          <p className="text-sm text-gray-700 mb-3">{result.message}</p>

          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-gray-600">Articles Processed</div>
              <div className="font-bold text-lg">{result.articles_processed}</div>
            </div>
            <div>
              <div className="text-gray-600">Claims Extracted</div>
              <div className="font-bold text-lg">{result.claims_extracted}</div>
            </div>
            <div>
              <div className="text-gray-600">Claims Verified</div>
              <div className="font-bold text-lg">{result.claims_verified}</div>
            </div>
          </div>

          {result.errors && result.errors.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium text-red-900 mb-2">Errors:</div>
              <ul className="text-sm text-red-800 space-y-1">
                {result.errors.map((error, i) => (
                  <li key={i}>• {error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Instructions */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-2">How it works:</h3>
        <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
          <li>Click "Extract Claims" to analyze articles and extract factual claims</li>
          <li>Click "Verify Claims" to fact-check extracted claims</li>
          <li>Or click "Full Pipeline" to do both in one step</li>
          <li>Each action processes up to 10 articles at a time</li>
          <li>Refresh the page or wait 10 seconds to see updated statistics</li>
        </ol>
      </div>
    </div>
  )
}
