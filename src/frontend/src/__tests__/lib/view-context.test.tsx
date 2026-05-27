import React, { useEffect } from 'react'
import { describe, it, expect } from 'vitest'
import { render, act } from '@testing-library/react'
import {
  ViewContextProvider,
  useViewContext,
  serializeViewContext,
  type ViewContextState,
} from '@/lib/view-context'

/**
 * Helper: render the provider and capture its useViewContext value into a ref
 * so individual tests can call setView / clearKey / reset and assert state.
 */
function renderProviderWithCapture() {
  const captured: { current: ReturnType<typeof useViewContext> | null } = { current: null }
  function Inner() {
    captured.current = useViewContext()
    return null
  }
  render(
    <ViewContextProvider>
      <Inner />
    </ViewContextProvider>
  )
  return captured
}

describe('view-context: ViewContextProvider', () => {
  it('starts with empty view state', () => {
    const captured = renderProviderWithCapture()
    expect(captured.current?.view).toEqual({})
  })

  it('setView adds keys', () => {
    const captured = renderProviderWithCapture()
    act(() => {
      captured.current?.setView({ countryCode: 'FI', articleId: 'art-1' })
    })
    expect(captured.current?.view.countryCode).toBe('FI')
    expect(captured.current?.view.articleId).toBe('art-1')
  })

  it('explicit null/undefined/"" removes the key', () => {
    const captured = renderProviderWithCapture()
    act(() => {
      captured.current?.setView({ countryCode: 'FI', articleId: 'a-1', sourceId: 'src' })
    })
    // remove via undefined
    act(() => {
      captured.current?.setView({ countryCode: undefined })
    })
    expect(captured.current?.view.countryCode).toBeUndefined()
    expect(captured.current?.view.articleId).toBe('a-1')

    // remove via null
    act(() => {
      captured.current?.setView({ articleId: null as any })
    })
    expect(captured.current?.view.articleId).toBeUndefined()

    // remove via empty string
    act(() => {
      captured.current?.setView({ sourceId: '' })
    })
    expect(captured.current?.view.sourceId).toBeUndefined()
  })

  it('empty arrays are dropped from state', () => {
    const captured = renderProviderWithCapture()
    act(() => {
      captured.current?.setView({ compareCountries: ['FI', 'SE'] })
    })
    expect(captured.current?.view.compareCountries).toEqual(['FI', 'SE'])
    act(() => {
      captured.current?.setView({ compareCountries: [] })
    })
    expect(captured.current?.view.compareCountries).toBeUndefined()
  })

  it('clearKey only removes the named key', () => {
    const captured = renderProviderWithCapture()
    act(() => {
      captured.current?.setView({ countryCode: 'FI', analysisId: 'ana-9' })
    })
    act(() => {
      captured.current?.clearKey('countryCode')
    })
    expect(captured.current?.view.countryCode).toBeUndefined()
    expect(captured.current?.view.analysisId).toBe('ana-9')
  })

  it('clearKey is a no-op when key is absent', () => {
    const captured = renderProviderWithCapture()
    const before = captured.current?.view
    act(() => {
      captured.current?.clearKey('articleId')
    })
    // identity should be preserved by the implementation when key is missing
    expect(captured.current?.view).toBe(before)
  })

  it('reset empties everything', () => {
    const captured = renderProviderWithCapture()
    act(() => {
      captured.current?.setView({
        countryCode: 'DE',
        articleId: 'a-9',
        compareCountries: ['DE', 'FR'],
        sourceId: 's-1',
      })
    })
    act(() => {
      captured.current?.reset()
    })
    expect(captured.current?.view).toEqual({})
  })
})

describe('view-context: useViewContext outside provider', () => {
  it('returns the no-op shim', () => {
    const captured: { current: ReturnType<typeof useViewContext> | null } = { current: null }
    function Inner() {
      captured.current = useViewContext()
      return null
    }
    render(<Inner />)
    expect(captured.current?.view).toEqual({})
    // setView/clearKey/reset should be functions that don't throw
    expect(() => captured.current?.setView({ countryCode: 'X' })).not.toThrow()
    expect(() => captured.current?.clearKey('countryCode')).not.toThrow()
    expect(() => captured.current?.reset()).not.toThrow()
  })
})

describe('view-context: serializeViewContext', () => {
  it('outputs snake_case fields and skips undefined entries', () => {
    const view: ViewContextState = {
      route: '/map',
      articleId: 'art-1',
      countryCode: 'FI',
      compareCountries: ['FI', 'SE'],
      analysisId: 'ana-1',
      deepSearchQuery: 'drought',
      deepSearchCompare: { query_a: 'a', query_b: 'b' },
      sourceId: 'src-9',
      label: 'Finland vs Sweden',
    }
    const out = serializeViewContext(view)!
    expect(out).toEqual({
      route: '/map',
      article_id: 'art-1',
      country: 'FI',
      compare_countries: ['FI', 'SE'],
      analysis_id: 'ana-1',
      deep_search_query: 'drought',
      deep_search_compare: { query_a: 'a', query_b: 'b' },
      source_id: 'src-9',
      label: 'Finland vs Sweden',
    })
  })

  it('returns undefined when state has nothing serializable', () => {
    expect(serializeViewContext({})).toBeUndefined()
  })

  it('omits empty compareCountries', () => {
    const out = serializeViewContext({
      route: '/map',
      compareCountries: [],
    })
    expect(out).toEqual({ route: '/map' })
    expect(out!.compare_countries).toBeUndefined()
  })

  it('only emits the keys that are actually set', () => {
    const out = serializeViewContext({
      countryCode: 'NO',
    })
    expect(out).toEqual({ country: 'NO' })
    expect(Object.keys(out!)).toEqual(['country'])
  })
})
