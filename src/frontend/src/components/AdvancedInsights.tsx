'use client'

import { useState, useEffect } from 'react'
import { Loader2, ShieldCheck, GitBranch, BarChart3, Info } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'

interface TransparencyData {
  article_id: string
  methodology: {
    scoring_model: string
    factors: Record<string, { weight: number; score?: number; description: string }>
    final_score: number
    credibility_level: string
  }
  evidence_chain: Array<{
    claim_id: string
    claim_text: string
    verdict: string
    confidence: number | null
    evidence_summary: string
  }>
  confidence_intervals: {
    mean_confidence: number | null
    lower_bound: number | null
    upper_bound: number | null
    claim_count: number
  }
  source_reliability: {
    source_name: string
    overall_score: number
    reliability_tier: string
  }
  causal_analysis?: Array<{
    claim_id: string
    cause: string
    effect: string
    mechanism: string
    confidence: number
    causal_chain: string[]
  }>
}

export default function AdvancedInsights({ articleId }: { articleId: string }) {
  const [data, setData] = useState<TransparencyData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchTransparency() {
      try {
        const res = await fetch(`${API_URL}/api/v2/articles/${articleId}/transparency`)
        if (res.ok) {
          setData(await res.json())
        } else {
          setError('Transparency data unavailable')
        }
      } catch {
        setError('Failed to load transparency data')
      }
      setLoading(false)
    }
    fetchTransparency()
  }, [articleId])

  if (loading) return <div className="flex items-center gap-2 text-sm text-gray-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading insights...</div>
  if (error || !data) return null

  return (
    <div className="space-y-6">
      {/* Source Reliability */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-green-600" />
          Source Reliability
        </h3>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div>
            <div className="text-2xl font-bold text-gray-900">{data.source_reliability.overall_score}</div>
            <div className="text-xs text-gray-500">Overall Score</div>
          </div>
          <div>
            <div className="text-sm font-medium text-gray-700">{data.source_reliability.source_name}</div>
            <div className="text-xs text-gray-500">Source</div>
          </div>
          <div>
            <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
              data.source_reliability.reliability_tier === 'scientific' ? 'bg-blue-100 text-blue-700' :
              data.source_reliability.reliability_tier === 'research' ? 'bg-green-100 text-green-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {data.source_reliability.reliability_tier}
            </span>
            <div className="text-xs text-gray-500 mt-1">Tier</div>
          </div>
        </div>
      </div>

      {/* Confidence Intervals */}
      {data.confidence_intervals.mean_confidence !== null && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-indigo-600" />
            Confidence Interval
          </h3>
          <div className="relative h-8 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="absolute h-full bg-indigo-200 rounded-full"
              style={{
                left: `${data.confidence_intervals.lower_bound}%`,
                width: `${(data.confidence_intervals.upper_bound ?? 0) - (data.confidence_intervals.lower_bound ?? 0)}%`,
              }}
            />
            <div
              className="absolute top-0 h-full w-1 bg-indigo-600 rounded"
              style={{ left: `${data.confidence_intervals.mean_confidence}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>{data.confidence_intervals.lower_bound}%</span>
            <span className="font-medium text-indigo-700">{data.confidence_intervals.mean_confidence}% mean</span>
            <span>{data.confidence_intervals.upper_bound}%</span>
          </div>
          <p className="text-xs text-gray-400 mt-1">Based on {data.confidence_intervals.claim_count} verified claims</p>
        </div>
      )}

      {/* Causal Analysis */}
      {data.causal_analysis && data.causal_analysis.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-purple-600" />
            Causal Analysis
          </h3>
          <div className="space-y-4">
            {data.causal_analysis.map((ca, i) => (
              <div key={i} className="bg-purple-50 rounded-lg p-3 border border-purple-100">
                <div className="grid grid-cols-2 gap-2 text-sm mb-2">
                  <div><span className="text-xs text-gray-500">Cause:</span> <span className="text-gray-800">{ca.cause}</span></div>
                  <div><span className="text-xs text-gray-500">Effect:</span> <span className="text-gray-800">{ca.effect}</span></div>
                </div>
                <p className="text-xs text-gray-600 mb-2"><span className="font-medium">Mechanism:</span> {ca.mechanism}</p>
                {ca.causal_chain.length > 0 && (
                  <div className="flex items-center gap-1 flex-wrap">
                    {ca.causal_chain.map((step, j) => (
                      <span key={j} className="inline-flex items-center">
                        {j > 0 && <span className="text-gray-300 mx-1">{'\u2192'}</span>}
                        <span className="text-xs bg-white px-2 py-0.5 rounded border border-purple-200 text-purple-700">{step}</span>
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-2 text-xs text-gray-400">Confidence: {Math.round(ca.confidence * 100)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Methodology */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <Info className="h-4 w-4 text-gray-500" />
          Scoring Methodology
        </h3>
        <p className="text-xs text-gray-500 mb-3">{data.methodology.scoring_model}</p>
        <div className="space-y-2">
          {Object.entries(data.methodology.factors).map(([key, factor]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-gray-600">{factor.description.slice(0, 60)}</span>
              <div className="flex items-center gap-2">
                {factor.score !== undefined && <span className="font-medium text-gray-800">{factor.score}</span>}
                <span className="text-xs text-gray-400">w={factor.weight}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
