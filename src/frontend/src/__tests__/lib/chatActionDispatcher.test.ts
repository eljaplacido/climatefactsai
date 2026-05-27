import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  dispatchChatAction,
  ACTION_MODES,
  ACTION_CONFIRM_COPY,
  type ChatActionSpec,
} from '@/lib/chatActionDispatcher'

describe('chatActionDispatcher — Phase 1C action protocol', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Stub window.location.assign so tests don't actually navigate.
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, assign: vi.fn() },
    })
    // Stub fetch for telemetry + async dispatchers.
    ;(global as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    })
  })

  describe('ACTION_MODES classification', () => {
    it('classifies all 6 navigational actions as auto', () => {
      expect(ACTION_MODES.navigate).toBe('auto')
      expect(ACTION_MODES.apply_search_filters).toBe('auto')
      expect(ACTION_MODES.apply_map_filters).toBe('auto')
      expect(ACTION_MODES.open_methodology_section).toBe('auto')
      expect(ACTION_MODES.open_country).toBe('auto')
      expect(ACTION_MODES.start_deep_search).toBe('auto')
    })

    it('classifies all 3 destructive/quota actions as confirm', () => {
      expect(ACTION_MODES.analyze_url).toBe('confirm')
      expect(ACTION_MODES.bookmark_article).toBe('confirm')
      expect(ACTION_MODES.start_calibration_label).toBe('confirm')
    })

    it('every confirm-mode action has user-facing copy', () => {
      for (const [type, mode] of Object.entries(ACTION_MODES)) {
        if (mode === 'confirm') {
          const copy = ACTION_CONFIRM_COPY[type as keyof typeof ACTION_CONFIRM_COPY]
          expect(copy.title, `${type} missing title`).toBeTruthy()
          expect(copy.cta, `${type} missing cta`).toBeTruthy()
        }
      }
    })
  })

  describe('AUTO-mode actions execute immediately', () => {
    it('navigate calls window.location.assign with the path', async () => {
      const action: ChatActionSpec = {
        type: 'navigate',
        params: { path: '/map' },
        label: 'Open map',
      }
      const result = await dispatchChatAction(action)
      expect(result.status).toBe('executed')
      expect(window.location.assign).toHaveBeenCalledWith('/map')
    })

    it('open_country navigates to /map?country=XX', async () => {
      await dispatchChatAction({
        type: 'open_country',
        params: { code: 'de' },
        label: 'Open Germany',
      })
      expect(window.location.assign).toHaveBeenCalledWith('/map?country=DE')
    })

    it('start_deep_search navigates to /deep-search?q=...', async () => {
      await dispatchChatAction({
        type: 'start_deep_search',
        params: { q: 'arctic ice' },
        label: 'Search',
      })
      expect(window.location.assign).toHaveBeenCalledWith(
        '/deep-search?q=arctic%20ice',
      )
    })

    it('apply_search_filters encodes all params', async () => {
      await dispatchChatAction({
        type: 'apply_search_filters',
        params: { q: 'flood', country: 'IN', credibility: 'HIGH' },
        label: 'Filter',
      })
      const url = (window.location.assign as any).mock.calls[0][0]
      expect(url).toContain('/search?')
      expect(url).toContain('q=flood')
      expect(url).toContain('country=IN')
      expect(url).toContain('credibility=HIGH')
    })

    it('auto-mode does NOT call requestConfirmation', async () => {
      const requestConfirmation = vi.fn().mockResolvedValue(true)
      await dispatchChatAction(
        { type: 'navigate', params: { path: '/sources' }, label: 'Sources' },
        { requestConfirmation },
      )
      expect(requestConfirmation).not.toHaveBeenCalled()
    })
  })

  describe('CONFIRM-mode actions require user confirmation', () => {
    it('fails closed when no requestConfirmation hook is provided', async () => {
      const result = await dispatchChatAction({
        type: 'bookmark_article',
        params: { article_id: 'a1' },
        label: 'Save',
      })
      // Critical safety property — misconfigured host cannot silently
      // execute a destructive action.
      expect(result.status).toBe('declined')
    })

    it('returns declined when user cancels confirmation', async () => {
      const requestConfirmation = vi.fn().mockResolvedValue(false)
      const result = await dispatchChatAction(
        {
          type: 'bookmark_article',
          params: { article_id: 'a1' },
          label: 'Save',
        },
        { requestConfirmation },
      )
      expect(result.status).toBe('declined')
      // Bookmark fetch must NOT have been called when declined
      const fetchCalls = (global.fetch as any).mock.calls
      const bookmarkPosts = fetchCalls.filter((c: any[]) =>
        String(c[0]).includes('/api/user/bookmarks'),
      )
      expect(bookmarkPosts).toHaveLength(0)
    })

    it('executes when user confirms bookmark_article', async () => {
      const requestConfirmation = vi.fn().mockResolvedValue(true)
      const result = await dispatchChatAction(
        {
          type: 'bookmark_article',
          params: { article_id: 'art-42' },
          label: 'Save',
        },
        { requestConfirmation },
      )
      expect(result.status).toBe('executed')
      // Slice 3 (2026-05-25): bookmark_article was migrated from
      // /api/user/bookmarks/{id} to the polymorphic /api/user/saved
      // endpoint. article_id now lives in the JSON body, not the URL.
      const fetchCalls = (global.fetch as any).mock.calls
      const bookmarkCall = fetchCalls.find((c: any[]) =>
        String(c[0]).includes('/api/user/saved'),
      )
      expect(bookmarkCall).toBeDefined()
      expect(bookmarkCall[1].method).toBe('POST')
      const body = JSON.parse(bookmarkCall[1].body)
      expect(body.item_type).toBe('article')
      expect(body.item_id).toBe('art-42')
    })

    it('surfaces 429 quota-exceeded as structured error', async () => {
      ;(global.fetch as any).mockImplementation((url: string) => {
        // Slice 3 (2026-05-25): match the migrated /api/user/saved
        // endpoint (was /api/user/bookmarks pre-slice-3).
        if (String(url).includes('/api/user/saved')) {
          return Promise.resolve({
            ok: false,
            status: 429,
            json: async () => ({
              detail: {
                error: 'quota_exceeded',
                message: 'You have used 3 of 3 saved articles.',
              },
            }),
          })
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
      })

      const result = await dispatchChatAction(
        {
          type: 'bookmark_article',
          params: { article_id: 'art-99' },
          label: 'Save',
        },
        { requestConfirmation: vi.fn().mockResolvedValue(true) },
      )
      expect(result.status).toBe('error')
      if (result.status === 'error') {
        expect(result.quotaExceeded).toBe(true)
        expect(result.message).toContain('3 of 3 saved articles')
      }
    })

    it('returns error when bookmark_article missing article_id', async () => {
      const result = await dispatchChatAction(
        {
          type: 'bookmark_article',
          params: {},
          label: 'Save',
        } as any,
        { requestConfirmation: vi.fn().mockResolvedValue(true) },
      )
      expect(result.status).toBe('error')
    })
  })

  describe('unknown action types', () => {
    it('returns error for an unknown action type', async () => {
      const result = await dispatchChatAction({
        type: 'send_email' as any,
        params: { to: 'a@b' },
        label: 'Send',
      })
      expect(result.status).toBe('error')
      if (result.status === 'error') {
        expect(result.message).toMatch(/unknown/i)
      }
    })
  })
})
