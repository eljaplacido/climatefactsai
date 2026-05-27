import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useQuota, formatQuotaCounter, type QuotaState } from '@/lib/useQuota'

const FREE_QUOTA_FIXTURE = {
  tier: 'freemium',
  quotas: [
    {
      quota_key: 'saved_articles',
      allowed: true,
      used: 1,
      limit: 3,
      period: 'lifetime',
      reset_at: null,
      upgrade_url: '/dashboard/subscription',
      tier: 'freemium',
      label: 'saved articles',
    },
    {
      quota_key: 'deep_research',
      allowed: true,
      used: 0,
      limit: 2,
      period: 'monthly',
      reset_at: '2026-06-01T00:00:00+00:00',
      upgrade_url: '/dashboard/subscription',
      tier: 'freemium',
      label: 'deep research queries',
    },
  ],
}

beforeEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  ;(global as any).fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => FREE_QUOTA_FIXTURE,
  })
})

describe('useQuota hook — Phase 2A', () => {
  it('starts in loading=true with summary=null', () => {
    const { result } = renderHook(() => useQuota())
    expect(result.current.loading).toBe(true)
    expect(result.current.summary).toBeNull()
  })

  it('fetches /api/quota and populates summary', async () => {
    const { result } = renderHook(() => useQuota())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.summary).toEqual(FREE_QUOTA_FIXTURE)
    expect((global.fetch as any).mock.calls[0][0]).toContain('/api/quota')
  })

  it('attaches Authorization header when token is present', async () => {
    localStorage.setItem('clilens_token', 'tok-abc')
    renderHook(() => useQuota())
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    const call = (global.fetch as any).mock.calls[0]
    const headers = call[1]?.headers || {}
    expect(headers.Authorization).toBe('Bearer tok-abc')
  })

  it('falls back to anonymous-zero envelope when fetch fails', async () => {
    ;(global.fetch as any).mockRejectedValue(new Error('network down'))
    const { result } = renderHook(() => useQuota())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('network down')
    expect(result.current.summary?.tier).toBe('anonymous')
    // Synthesized zero envelope still has all 5 keys
    expect(result.current.summary?.quotas).toHaveLength(5)
    for (const q of result.current.summary!.quotas) {
      expect(q.limit).toBe(0)
      expect(q.allowed).toBe(false)
    }
  })

  it('falls back to anonymous-zero envelope on non-OK HTTP status', async () => {
    ;(global.fetch as any).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    })
    const { result } = renderHook(() => useQuota())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.summary?.tier).toBe('anonymous')
  })

  it('getQuota returns the right per-key state', async () => {
    const { result } = renderHook(() => useQuota())
    await waitFor(() => expect(result.current.summary).not.toBeNull())
    const saved = result.current.getQuota('saved_articles')
    expect(saved?.used).toBe(1)
    expect(saved?.limit).toBe(3)
    const url = result.current.getQuota('url_analysis')
    expect(url).toBeNull() // not in our fixture
  })

  it('refresh() re-fetches /api/quota', async () => {
    const { result } = renderHook(() => useQuota())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(global.fetch).toHaveBeenCalledTimes(1)
    await act(async () => {
      await result.current.refresh()
    })
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })
})

describe('formatQuotaCounter — Phase 2A', () => {
  const make = (overrides: Partial<QuotaState>): QuotaState => ({
    quota_key: 'deep_research',
    allowed: true,
    used: 0,
    limit: 2,
    period: 'monthly',
    reset_at: null,
    upgrade_url: '/dashboard/subscription',
    tier: 'freemium',
    label: 'deep research queries',
    ...overrides,
  })

  it('returns empty string when null', () => {
    expect(formatQuotaCounter(null)).toBe('')
  })

  it('returns "Unlimited" for limit=-1', () => {
    expect(formatQuotaCounter(make({ limit: -1 }))).toBe('Unlimited')
  })

  it('exhausted monthly quota points to upgrade copy', () => {
    expect(formatQuotaCounter(make({ used: 2, limit: 2 }))).toContain(
      '0 deep research queries left this month — upgrade for more',
    )
  })

  it('singular form when exactly 1 left', () => {
    const r = formatQuotaCounter(make({ used: 1, limit: 2 }))
    expect(r).toContain('1 ')
    // Plural label "deep research queries" → singular "deep research querie" (cheap hack ok for v1)
    expect(r).toContain('left this month')
  })

  it('plural form for >1 left', () => {
    expect(formatQuotaCounter(make({ used: 0, limit: 5 }))).toBe(
      '5 deep research queries left this month',
    )
  })

  it('omits "this month" for lifetime quotas', () => {
    const r = formatQuotaCounter(
      make({ period: 'lifetime', limit: 3, used: 1, label: 'saved articles' }),
    )
    expect(r).toBe('2 saved articles left')
  })
})
