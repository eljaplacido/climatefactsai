'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type {
  AnalyticsDashboard,
  PipelineStatus,
  VerificationVerdictDistribution,
  ArticleTrend,
  SourcePerformance,
  ClaimCategoryBreakdown,
  CountryArticleStats,
} from '@/types'

function StatBox({
  label,
  value,
  subtitle,
  color = 'blue',
}: {
  label: string
  value: string | number
  subtitle?: string
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'gray'
}) {
  const colors = {
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    green: 'bg-green-50 border-green-200 text-green-900',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-900',
    red: 'bg-red-50 border-red-200 text-red-900',
    purple: 'bg-purple-50 border-purple-200 text-purple-900',
    gray: 'bg-gray-50 border-gray-200 text-gray-900',
  }

  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-75">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {subtitle && <p className="text-xs opacity-60 mt-1">{subtitle}</p>}
    </div>
  )
}

function ProgressBar({
  value,
  max,
  color = 'blue',
  label,
}: {
  value: number
  max: number
  color?: string
  label?: string
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  const bgColors: Record<string, string> = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
    purple: 'bg-purple-500',
  }

  return (
    <div className="flex items-center gap-3">
      {label && <span className="text-sm text-gray-600 w-24 truncate">{label}</span>}
      <div className="flex-1 bg-gray-200 rounded-full h-3">
        <div
          className={`h-3 rounded-full ${bgColors[color] || 'bg-blue-500'}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-sm text-gray-500 w-12 text-right">{pct}%</span>
    </div>
  )
}

function TrendChart({ trends }: { trends: ArticleTrend[] }) {
  if (!trends.length) return <p className="text-gray-500 text-sm">No trend data available</p>

  const maxVal = Math.max(
    ...trends.map((t) => Math.max(t.articles_ingested, t.articles_verified, t.articles_failed)),
    1
  )

  return (
    <div className="space-y-1">
      <div className="flex items-end gap-1 h-40">
        {trends.map((t, i) => {
          const ingH = (t.articles_ingested / maxVal) * 100
          const verH = (t.articles_verified / maxVal) * 100
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${t.date}: ${t.articles_ingested} ingested, ${t.articles_verified} verified`}>
              <div className="w-full flex flex-col justify-end h-32">
                <div
                  className="w-full bg-blue-400 rounded-t"
                  style={{ height: `${ingH}%`, minHeight: t.articles_ingested > 0 ? '2px' : 0 }}
                />
                <div
                  className="w-full bg-green-500 rounded-b"
                  style={{ height: `${verH}%`, minHeight: t.articles_verified > 0 ? '2px' : 0 }}
                />
              </div>
              <span className="text-[9px] text-gray-400 rotate-45 origin-left whitespace-nowrap">
                {t.date.slice(5)}
              </span>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 text-xs text-gray-500 mt-2">
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 rounded inline-block" /> Ingested</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 rounded inline-block" /> Verified</span>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const dashboard = await api.getAnalyticsDashboard()
      setData(dashboard)
    } catch (err: any) {
      setError(err?.message || 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading analytics...</p>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-50 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-red-800">Error loading analytics</h2>
            <p className="text-red-600 mt-2">{error || 'Unknown error'}</p>
            <button onClick={fetchData} className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  const { pipeline, verdict_distribution, trends_7d, top_sources, claim_categories, country_stats } = data

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p className="text-gray-500 mt-1">
              Real-time verification pipeline and content intelligence metrics
            </p>
          </div>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            Refresh
          </button>
        </div>

        {/* Pipeline Status */}
        <section>
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Pipeline Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            <StatBox label="Total Articles" value={pipeline.total_articles} color="gray" />
            <StatBox label="Pending" value={pipeline.pending} color="yellow" />
            <StatBox label="Processing" value={pipeline.processing} color="blue" />
            <StatBox label="Completed" value={pipeline.completed} color="green" subtitle={`${(pipeline.verification_rate * 100).toFixed(1)}% rate`} />
            <StatBox label="Failed" value={pipeline.failed} color="red" />
            <StatBox label="Ingested Today" value={pipeline.ingested_today} color="purple" />
            <StatBox label="Verified Today" value={pipeline.verified_today} color="green" />
          </div>
        </section>

        {/* Two Column: Trends + Verdicts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Trend Chart */}
          <section className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">7-Day Trend</h2>
            <TrendChart trends={trends_7d} />
          </section>

          {/* Verdict Distribution */}
          <section className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Verdict Distribution</h2>
            {verdict_distribution.total === 0 ? (
              <p className="text-gray-500 text-sm">No fact-checks recorded yet</p>
            ) : (
              <div className="space-y-3">
                <ProgressBar
                  label="Verified"
                  value={verdict_distribution.verified}
                  max={verdict_distribution.total}
                  color="green"
                />
                <ProgressBar
                  label="Disputed"
                  value={verdict_distribution.disputed}
                  max={verdict_distribution.total}
                  color="red"
                />
                <ProgressBar
                  label="Partial"
                  value={verdict_distribution.partially_true}
                  max={verdict_distribution.total}
                  color="yellow"
                />
                <ProgressBar
                  label="Unverified"
                  value={verdict_distribution.unverified}
                  max={verdict_distribution.total}
                  color="purple"
                />
                <p className="text-xs text-gray-400 mt-2">Total: {verdict_distribution.total} fact-checks</p>
              </div>
            )}
          </section>
        </div>

        {/* Claim Categories */}
        <section className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Claim Categories</h2>
          {claim_categories.length === 0 ? (
            <p className="text-gray-500 text-sm">No claims extracted yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4 text-right">Total</th>
                    <th className="py-2 pr-4 text-right">Verified</th>
                    <th className="py-2 pr-4 text-right">Disputed</th>
                    <th className="py-2 pr-4 text-right">Unverified</th>
                    <th className="py-2 text-right">Avg Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {claim_categories.map((cat) => (
                    <tr key={cat.category} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 pr-4 font-medium capitalize">
                        {cat.category.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2 pr-4 text-right">{cat.count}</td>
                      <td className="py-2 pr-4 text-right text-green-600">{cat.verified}</td>
                      <td className="py-2 pr-4 text-right text-red-600">{cat.disputed}</td>
                      <td className="py-2 pr-4 text-right text-gray-400">{cat.unverified}</td>
                      <td className="py-2 text-right">
                        {cat.avg_confidence > 0 ? `${(cat.avg_confidence * 100).toFixed(0)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Two Column: Sources + Countries */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Sources */}
          <section className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Top Sources</h2>
            {top_sources.length === 0 ? (
              <p className="text-gray-500 text-sm">No source data available</p>
            ) : (
              <div className="space-y-3">
                {top_sources.slice(0, 8).map((src) => (
                  <div key={src.source_name} className="flex items-center justify-between text-sm">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-800 truncate">{src.source_name}</p>
                      <p className="text-xs text-gray-400">
                        {src.total_articles} articles, {src.total_claims} claims
                      </p>
                    </div>
                    <div className="text-right ml-4">
                      <span className="text-green-600 text-xs">{src.verified_claims} verified</span>
                      {src.disputed_claims > 0 && (
                        <span className="text-red-600 text-xs ml-2">{src.disputed_claims} disputed</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Country Stats */}
          <section className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Countries</h2>
            {country_stats.length === 0 ? (
              <p className="text-gray-500 text-sm">No country data available</p>
            ) : (
              <div className="space-y-3">
                {country_stats.slice(0, 10).map((cs) => (
                  <div key={cs.country_code} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-medium text-gray-800">
                        {cs.country_name || cs.country_code}
                      </span>
                      <span className="text-gray-400 ml-1 text-xs">({cs.country_code})</span>
                    </div>
                    <div className="text-right">
                      <span className="text-gray-600">{cs.article_count} articles</span>
                      <span className="text-green-600 text-xs ml-2">{cs.verified_count} verified</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Footer */}
        <p className="text-xs text-gray-400 text-center">
          Generated at {new Date(data.generated_at).toLocaleString()} |{' '}
          <a href="/admin" className="underline hover:text-gray-600">Back to Admin</a>
        </p>
      </div>
    </div>
  )
}
