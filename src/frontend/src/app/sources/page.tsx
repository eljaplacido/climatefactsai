'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Shield, Search, Filter } from 'lucide-react'
import { api } from '../../lib/api'
import type { SourceProfile } from '../../types'
import SourceProfileCard from '../../components/SourceProfileCard'

export default function DataSourcesPage() {
  const [profiles, setProfiles] = useState<SourceProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [minCredibility, setMinCredibility] = useState<number | undefined>(undefined)
  const [sourceType, setSourceType] = useState<string>('all')

  useEffect(() => {
    const fetchProfiles = async () => {
      try {
        setLoading(true)
        const data = await api.getSourceProfiles({
          limit: 100,
          min_credibility: minCredibility,
          source_type: sourceType === 'all' ? undefined : sourceType,
        })
        setProfiles(data)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch source profiles:', err)
        setError('Could not load source profiles. The API may be unavailable.')
        setProfiles([])
      } finally {
        setLoading(false)
      }
    }

    fetchProfiles()
  }, [minCredibility, sourceType])

  const filteredProfiles = profiles.filter((p) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (
      p.source_name.toLowerCase().includes(q) ||
      p.source_domain.toLowerCase().includes(q) ||
      (p.description && p.description.toLowerCase().includes(q))
    )
  })

  const sourceTypes = ['all', 'news_outlet', 'government_agency', 'research_institution', 'ngo', 'blog']
  const sourceTypeLabels: Record<string, string> = {
    all: 'All Types',
    news_outlet: 'News Outlets',
    government_agency: 'Government',
    research_institution: 'Research',
    ngo: 'NGO',
    blog: 'Blog',
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Link href="/" className="text-2xl font-bold text-clilens-primary">
                Climatefacts.ai
              </Link>
              <span className="text-gray-300">/</span>
              <h1 className="text-lg font-semibold text-gray-900">Source Trust Profiles</h1>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-500">
              <Shield className="h-4 w-4" />
              <span>{profiles.length} sources tracked</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search sources..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
              />
            </div>

            {/* Source type filter */}
            <div className="flex items-center space-x-2">
              <Filter className="h-4 w-4 text-gray-400" />
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
              >
                {sourceTypes.map((st) => (
                  <option key={st} value={st}>{sourceTypeLabels[st]}</option>
                ))}
              </select>
            </div>

            {/* Min credibility filter */}
            <select
              value={minCredibility ?? ''}
              onChange={(e) => setMinCredibility(e.target.value ? Number(e.target.value) : undefined)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary focus:border-transparent"
            >
              <option value="">All credibility</option>
              <option value="80">80+ (Highly Trusted)</option>
              <option value="60">60+ (Generally Reliable)</option>
              <option value="40">40+ (Mixed+)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-clilens-primary"></div>
          </div>
        ) : error ? (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">{error}</p>
            <p className="text-sm text-gray-400">Source profiles are populated as articles are analyzed.</p>
          </div>
        ) : filteredProfiles.length === 0 ? (
          <div className="text-center py-16">
            <Shield className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">
              {searchQuery
                ? `No sources matching "${searchQuery}"`
                : 'No source profiles yet. Profiles are created as articles are ingested and analyzed.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filteredProfiles.map((profile) => (
              <SourceProfileCard key={profile.source_id} profile={profile} />
            ))}
          </div>
        )}

        {/* Static reference section */}
        {!loading && (
          <div className="mt-16 border-t border-gray-200 pt-12">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Reference Scientific Sources</h2>
            <p className="text-gray-600 mb-8">
              These institutions are used as primary references for climate claim verification,
              regardless of whether articles from them have been analyzed yet.
            </p>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { name: 'NASA Climate', domain: 'climate.nasa.gov', type: 'Government' },
                { name: 'NOAA', domain: 'noaa.gov', type: 'Government' },
                { name: 'IPCC', domain: 'ipcc.ch', type: 'International' },
                { name: 'EPA', domain: 'epa.gov', type: 'Government' },
                { name: 'Nature Climate Change', domain: 'nature.com', type: 'Journal' },
                { name: 'Science', domain: 'science.org', type: 'Journal' },
                { name: 'Climate Feedback', domain: 'climatefeedback.org', type: 'Fact-check' },
                { name: 'FactCheck.org', domain: 'factcheck.org', type: 'Fact-check' },
              ].map((ref) => (
                <div key={ref.domain} className="border border-gray-200 rounded-lg p-4 bg-white">
                  <p className="font-medium text-gray-900 text-sm">{ref.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{ref.domain}</p>
                  <span className="inline-block mt-2 px-2 py-0.5 bg-gray-100 text-gray-500 text-[10px] rounded-full">
                    {ref.type}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
