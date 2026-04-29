'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { RefreshCw, Globe, Clock, ChevronDown, Search, Loader2, AlertCircle } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5400'

// Available countries for selection — global coverage
const AVAILABLE_COUNTRIES = [
  // Europe
  { code: 'FI', name: 'Finland', flag: '\u{1F1EB}\u{1F1EE}' },
  { code: 'SE', name: 'Sweden', flag: '\u{1F1F8}\u{1F1EA}' },
  { code: 'NO', name: 'Norway', flag: '\u{1F1F3}\u{1F1F4}' },
  { code: 'DK', name: 'Denmark', flag: '\u{1F1E9}\u{1F1F0}' },
  { code: 'DE', name: 'Germany', flag: '\u{1F1E9}\u{1F1EA}' },
  { code: 'FR', name: 'France', flag: '\u{1F1EB}\u{1F1F7}' },
  { code: 'NL', name: 'Netherlands', flag: '\u{1F1F3}\u{1F1F1}' },
  { code: 'ES', name: 'Spain', flag: '\u{1F1EA}\u{1F1F8}' },
  { code: 'IT', name: 'Italy', flag: '\u{1F1EE}\u{1F1F9}' },
  { code: 'PL', name: 'Poland', flag: '\u{1F1F5}\u{1F1F1}' },
  { code: 'GB', name: 'United Kingdom', flag: '\u{1F1EC}\u{1F1E7}' },
  // North America
  { code: 'US', name: 'United States', flag: '\u{1F1FA}\u{1F1F8}' },
  { code: 'CA', name: 'Canada', flag: '\u{1F1E8}\u{1F1E6}' },
  { code: 'MX', name: 'Mexico', flag: '\u{1F1F2}\u{1F1FD}' },
  // Latin America
  { code: 'BR', name: 'Brazil', flag: '\u{1F1E7}\u{1F1F7}' },
  { code: 'AR', name: 'Argentina', flag: '\u{1F1E6}\u{1F1F7}' },
  { code: 'CO', name: 'Colombia', flag: '\u{1F1E8}\u{1F1F4}' },
  { code: 'CL', name: 'Chile', flag: '\u{1F1E8}\u{1F1F1}' },
  // Africa
  { code: 'KE', name: 'Kenya', flag: '\u{1F1F0}\u{1F1EA}' },
  { code: 'NG', name: 'Nigeria', flag: '\u{1F1F3}\u{1F1EC}' },
  { code: 'ZA', name: 'South Africa', flag: '\u{1F1FF}\u{1F1E6}' },
  { code: 'EG', name: 'Egypt', flag: '\u{1F1EA}\u{1F1EC}' },
  { code: 'GH', name: 'Ghana', flag: '\u{1F1EC}\u{1F1ED}' },
  // Asia & Oceania
  { code: 'CN', name: 'China', flag: '\u{1F1E8}\u{1F1F3}' },
  { code: 'IN', name: 'India', flag: '\u{1F1EE}\u{1F1F3}' },
  { code: 'JP', name: 'Japan', flag: '\u{1F1EF}\u{1F1F5}' },
  { code: 'AU', name: 'Australia', flag: '\u{1F1E6}\u{1F1FA}' },
  { code: 'ID', name: 'Indonesia', flag: '\u{1F1EE}\u{1F1E9}' },
  { code: 'SG', name: 'Singapore', flag: '\u{1F1F8}\u{1F1EC}' },
  // Middle East
  { code: 'AE', name: 'UAE', flag: '\u{1F1E6}\u{1F1EA}' },
  { code: 'SA', name: 'Saudi Arabia', flag: '\u{1F1F8}\u{1F1E6}' },
  { code: 'IL', name: 'Israel', flag: '\u{1F1EE}\u{1F1F1}' },
  { code: 'QA', name: 'Qatar', flag: '\u{1F1F6}\u{1F1E6}' },
  // International
  { code: 'XX', name: 'International', flag: '\u{1F30D}' },
]

interface FeedStatus {
  country_code: string
  last_update: string | null
  article_count: number
}

interface FeedPreferences {
  country_codes: string[]
  update_frequency: string
  keywords: string[]
  source_types: string[]
  last_updated_at: string | null
}

const SOURCE_TYPES = [
  { id: 'climate_news', label: 'Climate News', desc: 'Breaking climate stories from major outlets' },
  { id: 'weather_anomalies', label: 'Weather Anomalies', desc: 'Extreme weather events and forecasts' },
  { id: 'research_releases', label: 'Research & Science', desc: 'Academic papers and scientific reports' },
  { id: 'industrial_reports', label: 'Industry & ESG', desc: 'Corporate sustainability and ESG reports' },
  { id: 'policy_updates', label: 'Policy & Regulation', desc: 'Government climate policies and legislation' },
  { id: 'green_transition', label: 'Green Transition', desc: 'Renewable energy, cleantech, circular economy' },
  { id: 'sustainability_data', label: 'Sustainability Data', desc: 'Environmental metrics and indicators' },
  { id: 'ngo_reports', label: 'NGO & Think Tanks', desc: 'Reports from environmental organizations' },
]

export default function FeedPage() {
  const [preferences, setPreferences] = useState<FeedPreferences | null>(null)
  const [feedStatus, setFeedStatus] = useState<FeedStatus[]>([])
  const [selectedCountries, setSelectedCountries] = useState<string[]>([])
  const [selectedSourceTypes, setSelectedSourceTypes] = useState<string[]>(
    ['climate_news', 'weather_anomalies', 'research_releases']
  )
  const [keywords, setKeywords] = useState('')
  const [updateFrequency, setUpdateFrequency] = useState('daily')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const token = typeof window !== 'undefined' ? localStorage.getItem('clilens_token') : null

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const fetchPreferences = useCallback(async () => {
    if (!token) { setLoading(false); return }
    try {
      const res = await fetch(`${API_URL}/api/feed/preferences`, { headers })
      if (res.ok) {
        const data: FeedPreferences = await res.json()
        setPreferences(data)
        setSelectedCountries(data.country_codes || [])
        setKeywords((data.keywords || []).join(', '))
        if (data.update_frequency) setUpdateFrequency(data.update_frequency)
        if (data.source_types?.length) setSelectedSourceTypes(data.source_types)
      }
    } catch (e) {
      console.error('Failed to fetch preferences', e)
    }
    setLoading(false)
  }, [token])

  const fetchStatus = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${API_URL}/api/feed/status`, { headers })
      if (res.ok) {
        setFeedStatus(await res.json())
      }
    } catch (e) {
      console.error('Failed to fetch feed status', e)
    }
  }, [token])

  useEffect(() => {
    fetchPreferences()
    fetchStatus()
  }, [fetchPreferences, fetchStatus])

  const toggleCountry = (code: string) => {
    setSelectedCountries(prev =>
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    )
  }

  const savePreferences = async () => {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const kw = keywords.split(',').map(k => k.trim()).filter(Boolean)
      const res = await fetch(`${API_URL}/api/feed/preferences`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ country_codes: selectedCountries, keywords: kw, update_frequency: updateFrequency, source_types: selectedSourceTypes }),
      })
      if (res.ok) {
        const data = await res.json()
        setPreferences(data)
        setSuccess('Feed preferences saved!')
        fetchStatus()
      } else {
        const err = await res.json()
        setError(err.detail || 'Failed to save preferences')
      }
    } catch {
      setError('Network error')
    }
    setSaving(false)
  }

  const refreshFeed = async () => {
    setRefreshing(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await fetch(`${API_URL}/api/feed/refresh`, {
        method: 'POST',
        headers,
      })
      if (res.ok) {
        const data = await res.json()
        setSuccess(data.message || 'Feed refresh dispatched!')
      } else {
        const err = await res.json()
        setError(err.detail || 'Refresh failed')
      }
    } catch {
      setError('Network error')
    }
    setRefreshing(false)
  }

  if (!token) {
    return (
      <div className="max-w-3xl mx-auto text-center py-16">
        <Globe className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">My Feed</h1>
        <p className="text-gray-500 mb-6">
          Sign in to configure your personalized climate news feed.
        </p>
        <Link href="/login" className="px-6 py-2 bg-clilens-primary text-white rounded-lg hover:bg-clilens-teal-700 transition">
          Sign In
        </Link>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-clilens-primary" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">My Feed</h1>
        <p className="text-gray-500 mt-1">
          Select countries and keywords for your personalized climate news feed.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          {success}
        </div>
      )}

      {/* Country Selection */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Globe className="h-5 w-5 text-clilens-primary" />
          Countries
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Select which countries to track. Limit depends on your subscription tier.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {AVAILABLE_COUNTRIES.map(c => (
            <button
              key={c.code}
              onClick={() => toggleCountry(c.code)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition ${
                selectedCountries.includes(c.code)
                  ? 'bg-clilens-teal-50 border-clilens-primary text-clilens-teal-700 font-medium'
                  : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <span>{c.flag}</span>
              <span>{c.name}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Keywords */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Search className="h-5 w-5 text-clilens-primary" />
          Keywords
        </h2>
        <input
          type="text"
          value={keywords}
          onChange={e => setKeywords(e.target.value)}
          placeholder="e.g. carbon tax, renewable energy, IPCC"
          className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary"
        />
        <p className="mt-1 text-xs text-gray-400">Comma-separated keywords to filter articles</p>
      </section>

      {/* Source Types */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Globe className="h-5 w-5 text-clilens-primary" />
          Source Types
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          Choose what kinds of climate intelligence you want in your feed.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {SOURCE_TYPES.map((st) => {
            const isSelected = selectedSourceTypes.includes(st.id)
            return (
              <button
                key={st.id}
                onClick={() =>
                  setSelectedSourceTypes((prev) =>
                    isSelected ? prev.filter((t) => t !== st.id) : [...prev, st.id]
                  )
                }
                className={`flex flex-col items-start px-3 py-2.5 rounded-lg border text-left transition-all ${
                  isSelected
                    ? 'border-clilens-primary bg-teal-50 ring-1 ring-clilens-primary'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <span className={`text-sm font-medium ${isSelected ? 'text-clilens-primary' : 'text-gray-700'}`}>
                  {st.label}
                </span>
                <span className="text-xs text-gray-400 mt-0.5">{st.desc}</span>
              </button>
            )
          })}
        </div>
      </section>

      {/* Update Frequency */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Clock className="h-5 w-5 text-clilens-primary" />
          Update Frequency
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          How often should we check for new articles from your selected countries?
        </p>
        <select
          value={updateFrequency}
          onChange={e => setUpdateFrequency(e.target.value)}
          className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-clilens-primary bg-white"
        >
          <option value="daily">Daily (once per day)</option>
          <option value="twice_daily">Twice daily</option>
          <option value="four_times_daily">4 times daily</option>
          <option value="hourly">Hourly (Professional tier)</option>
        </select>
      </section>

      {/* Actions */}
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={savePreferences}
          disabled={saving || selectedCountries.length === 0}
          className="px-5 py-2 bg-clilens-primary text-white rounded-lg hover:bg-clilens-teal-700 transition disabled:opacity-50 flex items-center gap-2"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Preferences
        </button>
        <button
          onClick={refreshFeed}
          disabled={refreshing || !preferences?.country_codes?.length}
          className="px-5 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition disabled:opacity-50 flex items-center gap-2 text-sm"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh Now
        </button>
      </div>

      {/* Feed Status */}
      {feedStatus.length > 0 && (
        <section className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="h-5 w-5 text-clilens-primary" />
            Feed Status
          </h2>
          <div className="divide-y divide-gray-100">
            {feedStatus.map(s => {
              const country = AVAILABLE_COUNTRIES.find(c => c.code === s.country_code)
              return (
                <div key={s.country_code} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-2">
                    <span>{country?.flag || '\u{1F310}'}</span>
                    <span className="font-medium text-gray-800">{country?.name || s.country_code}</span>
                  </div>
                  <div className="text-right text-sm">
                    <div className="text-gray-600">{s.article_count} articles</div>
                    {s.last_update && (
                      <div className="text-xs text-gray-400">
                        Last: {new Date(s.last_update).toLocaleDateString('en-GB')}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Update frequency info */}
      {preferences && (
        <div className="mt-4 text-center text-sm text-gray-400">
          Update frequency: <span className="font-medium">{preferences.update_frequency.replace('_', ' ')}</span>
        </div>
      )}
    </div>
  )
}
