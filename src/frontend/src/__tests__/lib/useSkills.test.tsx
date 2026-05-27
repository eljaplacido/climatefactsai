import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useSkills } from '@/lib/useSkills'

const BACKEND_REGISTRY = {
  skills: [
    {
      name: 'navigate',
      description: 'Open a platform route.',
      mode: 'auto' as const,
      parameters: [
        { name: 'path', type: 'string', description: 'Route', required: true },
      ],
      target_surfaces: ['/map', '/search'],
    },
    {
      name: 'bookmark_article',
      description: 'Save an article to bookmarks.',
      mode: 'confirm' as const,
      parameters: [
        { name: 'article_id', type: 'string', description: '', required: true },
      ],
      target_surfaces: ['/api/user/bookmarks'],
    },
  ],
  total: 2,
  modes: { auto: 1, confirm: 1 },
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('useSkills — Phase 5B', () => {
  it('starts in loading state with the fallback registry pre-populated', () => {
    ;(global as any).fetch = vi.fn(() => new Promise(() => {})) // never resolves
    const { result } = renderHook(() => useSkills())
    expect(result.current.loading).toBe(true)
    // Fallback registry is non-empty so consumers don't render blank UI
    expect(result.current.registry.total).toBeGreaterThan(0)
    expect(result.current.registry.skills.length).toBeGreaterThan(0)
  })

  it('fetches /api/skills and uses the backend registry on success', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => BACKEND_REGISTRY,
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.registry).toEqual(BACKEND_REGISTRY)
  })

  it('falls back to local registry on fetch failure (no broken UI)', async () => {
    ;(global as any).fetch = vi.fn().mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('network')
    // Fallback registry covers all 9 action types
    const names = result.current.registry.skills.map((s) => s.name)
    expect(names).toContain('navigate')
    expect(names).toContain('bookmark_article')
    expect(names).toContain('analyze_url')
  })

  it('falls back when backend returns a malformed shape', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ unexpected: 'shape' }),
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toContain('Invalid')
    // Still has the fallback registry available
    expect(result.current.registry.skills.length).toBeGreaterThan(0)
  })

  it('falls back when backend returns non-OK HTTP status', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toContain('500')
  })

  it('getSkill returns the matching entry', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => BACKEND_REGISTRY,
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    const skill = result.current.getSkill('navigate')
    expect(skill).not.toBeNull()
    expect(skill!.mode).toBe('auto')
  })

  it('getSkill returns null for unknown skill', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => BACKEND_REGISTRY,
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.getSkill('send_email')).toBeNull()
  })

  it('getSkillMode returns the backend mode when registered', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => BACKEND_REGISTRY,
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.getSkillMode('bookmark_article')).toBe('confirm')
    expect(result.current.getSkillMode('navigate')).toBe('auto')
  })

  it('getSkillMode falls back to local mapping for unfetched skills', () => {
    // Don't resolve the fetch — getSkillMode should still return confirm
    // for known destructive types via the fallback table.
    ;(global as any).fetch = vi.fn(() => new Promise(() => {}))
    const { result } = renderHook(() => useSkills())
    expect(result.current.getSkillMode('bookmark_article')).toBe('confirm')
    expect(result.current.getSkillMode('analyze_url')).toBe('confirm')
    expect(result.current.getSkillMode('navigate')).toBe('auto')
  })

  it('getSkillMode defaults to "auto" for truly unknown skills', async () => {
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => BACKEND_REGISTRY,
    })
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    // 'send_email' isn't in either backend OR fallback
    expect(result.current.getSkillMode('send_email')).toBe('auto')
  })

  it('refresh() re-fetches the registry', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => BACKEND_REGISTRY,
    })
    ;(global as any).fetch = fetchMock
    const { result } = renderHook(() => useSkills())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await act(async () => {
      await result.current.refresh()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
