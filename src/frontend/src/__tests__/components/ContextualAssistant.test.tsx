import React, { useEffect } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { ViewContextProvider, useViewContext } from '@/lib/view-context'

// Mock next/navigation: usePathname is the only hook used by ContextualAssistant.
const pathnameMock = vi.fn(() => '/')
vi.mock('next/navigation', () => ({
  usePathname: () => pathnameMock(),
}))

// Capture the props that ContextualAssistant forwards into AgenticAssistant.
const capturedProps: Array<Record<string, any>> = []
vi.mock('@/components/AgenticAssistant', () => ({
  __esModule: true,
  default: (props: Record<string, any>) => {
    capturedProps.push(props)
    return <div data-testid="agentic-stub" />
  },
}))

// Import AFTER the mocks so they take effect.
// eslint-disable-next-line import/first
import ContextualAssistant from '@/components/ContextualAssistant'

beforeEach(() => {
  capturedProps.length = 0
  pathnameMock.mockReset()
})

function lastProps() {
  return capturedProps[capturedProps.length - 1]
}

describe('ContextualAssistant', () => {
  it('forwards currentPage derived from pathname', () => {
    pathnameMock.mockReturnValue('/map')
    render(
      <ViewContextProvider>
        <ContextualAssistant />
      </ViewContextProvider>
    )
    expect(lastProps().currentPage).toBe('map')
    expect(lastProps().currentRoute).toBe('/map')
  })

  it('uses "default" when on the root path', () => {
    pathnameMock.mockReturnValue('/')
    render(
      <ViewContextProvider>
        <ContextualAssistant />
      </ViewContextProvider>
    )
    expect(lastProps().currentPage).toBe('default')
  })

  it('keeps article id linked on /articles/abc/transparency (regression)', () => {
    pathnameMock.mockReturnValue('/articles/abc/transparency')
    render(
      <ViewContextProvider>
        <ContextualAssistant />
      </ViewContextProvider>
    )
    const props = lastProps()
    // page label should be "transparency" but the article id stays attached
    expect(props.currentPage).toBe('transparency')
    expect(props.currentArticleId).toBe('abc')
  })

  it('does NOT pass currentArticleId for /articles/new', () => {
    pathnameMock.mockReturnValue('/articles/new')
    render(
      <ViewContextProvider>
        <ContextualAssistant />
      </ViewContextProvider>
    )
    expect(lastProps().currentArticleId).toBeUndefined()
  })

  it('passes article id from path on regular article detail route', () => {
    pathnameMock.mockReturnValue('/articles/xyz-123')
    render(
      <ViewContextProvider>
        <ContextualAssistant />
      </ViewContextProvider>
    )
    expect(lastProps().currentPage).toBe('articles')
    expect(lastProps().currentArticleId).toBe('xyz-123')
  })

  it('forwards values published into ViewContextProvider (countryCode, compareCountries, etc.)', () => {
    pathnameMock.mockReturnValue('/map')

    function Publisher() {
      const { setView } = useViewContext()
      useEffect(() => {
        setView({
          countryCode: 'FI',
          compareCountries: ['FI', 'SE'],
          analysisId: 'analysis-7',
          deepSearchQuery: 'drought',
          sourceId: 'src-1',
        })
      }, [setView])
      return null
    }

    render(
      <ViewContextProvider>
        <Publisher />
        <ContextualAssistant />
      </ViewContextProvider>
    )

    const props = lastProps()
    expect(props.currentCountry).toBe('FI')
    expect(props.currentCompareCountries).toEqual(['FI', 'SE'])
    expect(props.currentAnalysisId).toBe('analysis-7')
    expect(props.currentDeepSearchQuery).toBe('drought')
    expect(props.currentSourceId).toBe('src-1')
    // Auto-derived label: "FI vs SE"
    expect(props.contextLabel).toBe('FI vs SE')
  })

  it('keeps the article id even when pathname has additional segments under /articles/{id}', () => {
    // Sub-routes like /articles/abc/transparency still keep the article id
    // attached so chat can resolve "this article".
    pathnameMock.mockReturnValue('/articles/article-77/transparency')
    render(
      <ViewContextProvider>
        <ContextualAssistant />
      </ViewContextProvider>
    )
    const props = lastProps()
    expect(props.currentArticleId).toBe('article-77')
    expect(props.currentPage).toBe('transparency')
  })
})
